"""Semantic memory store: vector embeddings for memory events with hybrid retrieval."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from zerion_core.config import settings
from zerion_core.llm.ollama import OllamaClient


class SemanticStore:
    """ChromaDB-backed semantic store for memory event embeddings."""

    COLLECTION = "zerion_longterm"

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm
        db_path = settings.memory_root / "longterm_chroma"
        db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(db_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self._keyword_index: dict[str, dict[str, Any]] = {}
        self._load_keyword_index()

    def _load_keyword_index(self) -> None:
        idx_path = settings.memory_root / "longterm_keyword.json"
        if idx_path.exists():
            try:
                self._keyword_index = json.loads(idx_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._keyword_index = {}

    def _save_keyword_index(self) -> None:
        idx_path = settings.memory_root / "longterm_keyword.json"
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(
            json.dumps(self._keyword_index, ensure_ascii=False),
            encoding="utf-8",
        )

    def _doc_id(self, event_id: str) -> str:
        return hashlib.sha256(f"lt:{event_id}".encode()).hexdigest()[:20]

    async def index_event(
        self,
        event_id: str,
        content: str,
        metadata: dict[str, Any],
    ) -> None:
        """Index a memory event with embedding."""
        embedding = await self.llm.embed(content)
        doc_id = self._doc_id(event_id)

        meta = {k: str(v) for k, v in metadata.items()}
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta],
        )

        # Build keyword index
        words = set()
        for token in content.lower().split():
            if len(token) > 2:
                words.add(token)
        self._keyword_index[doc_id] = {
            "event_id": event_id,
            "content": content[:500],
            "words": list(words)[:50],
            **{k: str(v) for k, v in metadata.items()},
        }
        self._save_keyword_index()

    async def index_batch(
        self,
        event_ids: list[str],
        contents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Batch index memory events."""
        for eid, content, meta in zip(event_ids, contents, metadatas):
            await self.index_event(eid, content, meta)

    async def search(
        self,
        query: str,
        limit: int = 10,
        project_filter: str | None = None,
        event_type_filter: str | None = None,
        time_start: str | None = None,
        time_end: str | None = None,
        min_importance: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Hybrid search: vector similarity + keyword fallback with metadata filtering."""
        results: list[dict[str, Any]] = []

        # Vector search
        try:
            embedding = await self.llm.embed(query)
            where_conditions: list[dict[str, str]] = []

            if project_filter:
                where_conditions.append({"project_id": project_filter})
            if event_type_filter:
                where_conditions.append({"event_type": event_type_filter})

            where = None
            if len(where_conditions) == 1:
                where = where_conditions[0]
            elif len(where_conditions) > 1:
                where = {"$and": where_conditions}

            query_results = self._collection.query(
                query_embeddings=[embedding],
                n_results=min(limit * 2, 30),
                where=where if where else None,
            )

            if query_results["documents"] and query_results["documents"][0]:
                for doc, meta, dist in zip(
                    query_results["documents"][0],
                    query_results["metadatas"][0] or [{}] * len(query_results["documents"][0]),
                    query_results["distances"][0] if query_results.get("distances") else [0.5] * len(query_results["documents"][0]),
                ):
                    score = max(0.0, 1.0 - float(dist))
                    imp = float(meta.get("importance", 0.5))
                    if imp < min_importance:
                        continue
                    results.append({
                        "event_id": meta.get("event_id", ""),
                        "content": doc,
                        "vector_score": score,
                        "importance": imp,
                        "project_id": meta.get("project_id", ""),
                        "event_type": meta.get("event_type", ""),
                        "created_at": meta.get("created_at", ""),
                        "source": "vector",
                    })
        except Exception:
            pass

        # Keyword fallback (if no good vector results)
        if len(results) < limit:
            kw_results = self._keyword_search(query, limit * 2)
            seen_ids = {r["event_id"] for r in results}
            for kr in kw_results:
                if kr["event_id"] not in seen_ids:
                    results.append(kr)

        # Sort by combined score
        results.sort(key=lambda r: r.get("vector_score", 0) * 0.7 + r.get("importance", 0.5) * 0.3, reverse=True)
        return results[:limit]

    def _keyword_search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fast keyword-based fallback search."""
        query_words = set(query.lower().split())
        scores: dict[str, float] = {}

        for doc_id, entry in self._keyword_index.items():
            entry_words = set(entry.get("words", []))
            overlap = query_words & entry_words
            if overlap:
                score = len(overlap) / max(len(query_words), 1)
                scores[entry["event_id"]] = score

        sorted_ids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)[:limit]

        results: list[dict[str, Any]] = []
        for eid in sorted_ids:
            entry = next(
                (e for e in self._keyword_index.values() if e.get("event_id") == eid),
                None,
            )
            if entry:
                results.append({
                    "event_id": eid,
                    "content": entry.get("content", ""),
                    "vector_score": 0.0,
                    "keyword_score": scores[eid],
                    "importance": float(entry.get("importance", 0.5)),
                    "project_id": entry.get("project_id", ""),
                    "event_type": entry.get("event_type", ""),
                    "created_at": entry.get("created_at", ""),
                    "source": "keyword",
                })
        return results

    def count(self) -> int:
        return self._collection.count()

    def delete_event(self, event_id: str) -> None:
        doc_id = self._doc_id(event_id)
        try:
            self._collection.delete(ids=[doc_id])
        except Exception:
            pass
        self._keyword_index.pop(doc_id, None)
        self._save_keyword_index()

    def reset(self) -> None:
        self._client.delete_collection(self.COLLECTION)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self._keyword_index.clear()
        self._save_keyword_index()
