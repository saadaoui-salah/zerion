from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zerion_core.rag.embeddings import EmbeddingProvider
from zerion_core.rag.indexer import CodeChunk
from zerion_core.rag.vectorstore import CodeVectorStore


@dataclass
class RetrievalResult:
    chunk: CodeChunk
    vector_score: float = 0.0
    keyword_score: float = 0.0
    final_score: float = 0.0
    source: str = "vector"

    def to_context(self, include_line_numbers: bool = True) -> str:
        prefix = f"{self.chunk.file_path}"
        if self.chunk.symbol_name and self.chunk.symbol_name not in ("__header__", "__imports__"):
            prefix += f" :: {self.chunk.symbol_name}"
        if include_line_numbers:
            prefix += f" (L{self.chunk.start_line}-{self.chunk.end_line})"
        return f"--- {prefix} [{self.source} score={self.final_score:.3f}] ---\n{self.chunk.content}"


class CodeRetriever:
    """Hybrid retrieval: vector similarity + keyword matching + reranking."""

    def __init__(
        self,
        embeddings: EmbeddingProvider,
        store: CodeVectorStore,
    ) -> None:
        self.embeddings = embeddings
        self.store = store
        self._keyword_index: dict[str, list[dict[str, Any]]] = {}

    def build_keyword_index(self, chunks: list[CodeChunk]) -> None:
        """Build an inverted index for fast keyword search."""
        self._keyword_index.clear()
        for chunk in chunks:
            # Index by file name, symbol names, and meaningful words
            tokens = set()
            tokens.add(Path(chunk.file_path).stem.lower())
            if chunk.symbol_name:
                tokens.add(chunk.symbol_name.lower())
            if chunk.parent_class:
                tokens.add(chunk.parent_class.lower())

            # Extract identifiers and keywords from content
            words = re.findall(r"\b[a-zA-Z_]\w*\b", chunk.content.lower())
            # Filter stop words and very short tokens
            stop = {"self", "cls", "import", "from", "return", "if", "else", "for",
                     "while", "def", "class", "async", "await", "with", "as", "try",
                     "except", "finally", "raise", "pass", "none", "true", "false",
                     "and", "or", "not", "in", "is", "lambda", "yield", "global",
                     "nonlocal", "assert", "del", "print", "len", "range", "type"}
            for w in words:
                if len(w) > 2 and w not in stop:
                    tokens.add(w)

            for token in tokens:
                if token not in self._keyword_index:
                    self._keyword_index[token] = []
                self._keyword_index[token].append({
                    "chunk_id": chunk.id,
                    "token": token,
                })

    async def retrieve(
        self,
        query: str,
        k: int = 10,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
        language_filter: str | None = None,
        file_filter: str | None = None,
    ) -> list[RetrievalResult]:
        """Hybrid retrieval with vector + keyword fusion and reranking."""
        # Vector search
        vector_results = await self._vector_search(query, k=k * 2, language_filter=language_filter, file_filter=file_filter)

        # Keyword search
        keyword_hits = self._keyword_search(query, k=k * 2)

        # Merge and rerank
        merged = self._merge_results(vector_results, keyword_hits, vector_weight, keyword_weight)

        # Top-k
        merged.sort(key=lambda r: r.final_score, reverse=True)
        return merged[:k]

    async def _vector_search(
        self,
        query: str,
        k: int = 20,
        language_filter: str | None = None,
        file_filter: str | None = None,
    ) -> dict[str, RetrievalResult]:
        embedding = await self.embeddings.embed(query)
        where = None
        if language_filter:
            where = {"language": language_filter}
        elif file_filter:
            where = {"file_path": file_filter}

        try:
            results = await self.store.query(embedding=embedding, n_results=k, where=where)
        except Exception:
            return {}

        hits: dict[str, RetrievalResult] = {}
        if not results.get("documents") or not results["documents"][0]:
            return hits

        docs = results["documents"][0]
        metas = results["metadatas"][0] or [{}] * len(docs)
        dists = results["distances"][0] if results.get("distances") else [0.5] * len(docs)
        ids = results["ids"][0] if results.get("ids") else [""] * len(docs)

        for doc, meta, dist, cid in zip(docs, metas, dists, ids):
            score = max(0.0, 1.0 - float(dist))
            chunk = CodeChunk(
                id=cid,
                file_path=meta.get("file_path", ""),
                content=doc,
                start_line=int(meta.get("start_line", 1)),
                end_line=int(meta.get("end_line", 1)),
                chunk_type=meta.get("chunk_type", ""),
                symbol_name=meta.get("symbol_name", ""),
                parent_class=meta.get("parent_class", ""),
                language=meta.get("language", ""),
            )
            hits[cid] = RetrievalResult(chunk=chunk, vector_score=score, source="vector")

        return hits

    def _keyword_search(self, query: str, k: int = 20) -> dict[str, RetrievalResult]:
        query_lower = query.lower()
        query_tokens = set(re.findall(r"\b[a-zA-Z_]\w*\b", query_lower))
        query_tokens = {t for t in query_tokens if len(t) > 2}

        if not query_tokens:
            return {}

        # Score each chunk by token overlap
        scores: dict[str, float] = {}
        chunk_ids: dict[str, str] = {}
        for token in query_tokens:
            for entry in self._keyword_index.get(token, []):
                cid = entry["chunk_id"]
                scores[cid] = scores.get(cid, 0.0) + 1.0
                chunk_ids[cid] = cid

        if not scores:
            return {}

        # Normalize scores
        max_score = max(scores.values()) if scores else 1.0
        results: dict[str, RetrievalResult] = {}
        for cid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]:
            # We don't have the full chunk here, just the score
            # The full chunk will be filled from vector results or re-fetched
            results[cid] = RetrievalResult(
                chunk=CodeChunk(id=cid, file_path="", content="", start_line=0, end_line=0, chunk_type=""),
                keyword_score=score / max_score,
                source="keyword",
            )

        return results

    def _merge_results(
        self,
        vector_results: dict[str, RetrievalResult],
        keyword_results: dict[str, RetrievalResult],
        vector_weight: float,
        keyword_weight: float,
    ) -> list[RetrievalResult]:
        """Merge vector and keyword results with weighted scoring."""
        all_ids = set(vector_results.keys()) | set(keyword_results.keys())
        merged: list[RetrievalResult] = []

        for cid in all_ids:
            v = vector_results.get(cid)
            k = keyword_results.get(cid)

            v_score = v.vector_score * vector_weight if v else 0.0
            k_score = k.keyword_score * keyword_weight if k else 0.0
            final = v_score + k_score

            chunk = v.chunk if v else k.chunk
            source = "hybrid" if (v and k) else ("vector" if v else "keyword")

            merged.append(RetrievalResult(
                chunk=chunk,
                vector_score=v.vector_score if v else 0.0,
                keyword_score=k.keyword_score if k else 0.0,
                final_score=final,
                source=source,
            ))

        return merged
