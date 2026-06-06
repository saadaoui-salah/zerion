from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from zerion_core.config import settings
from zerion_core.llm.ollama import OllamaClient
from zerion_core.memory.graph import TemporalGraph


@dataclass
class RetrievalHit:
    content: str
    source: str
    score: float
    metadata: dict[str, Any]


class HybridRetriever:
    """Combine vector, graph, and keyword search with multi-project awareness."""

    COLLECTION = "zerion_memory"
    PROJECT_COLLECTION = "project_embeddings"

    def __init__(self, llm: OllamaClient, graph: TemporalGraph) -> None:
        self.llm = llm
        self.graph = graph
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self.chroma = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self.project_collection = self.chroma.get_or_create_collection(
            name=self.PROJECT_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self._keyword_index: dict[str, dict[str, Any]] = {}
        self._load_keyword_index()

    def _load_keyword_index(self) -> None:
        idx_path = settings.memory_root / "keyword_index.json"
        if idx_path.exists():
            self._keyword_index = json.loads(idx_path.read_text(encoding="utf-8"))

    def _save_keyword_index(self) -> None:
        idx_path = settings.memory_root / "keyword_index.json"
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(json.dumps(self._keyword_index, indent=2), encoding="utf-8")

    def _doc_id(self, text: str, source: str) -> str:
        return hashlib.sha256(f"{source}:{text}".encode()).hexdigest()[:24]

    async def index(self, text: str, source: str, metadata: dict[str, Any] | None = None) -> None:
        meta = {k: str(v) for k, v in (metadata or {}).items()}
        meta["source"] = source
        doc_id = self._doc_id(text, source)
        embedding = await self.llm.embed(text)
        self.collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[meta],
        )
        self._keyword_index[doc_id] = {"text": text, "source": source, **meta}
        self._save_keyword_index()

    async def index_project(
        self,
        project_name: str,
        description: str,
        tech_stack: list[str],
    ) -> None:
        text = f"Project: {project_name}\nDescription: {description}\nTech Stack: {', '.join(tech_stack)}"
        embedding = await self.llm.embed(text)
        doc_id = f"project:{project_name}"
        self.project_collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas={
                "project": project_name,
                "description": description[:500],
                "tech_stack": ",".join(tech_stack),
            },
        )

    async def search(
        self,
        query: str,
        limit: int = 8,
        vector_weight: float = 0.5,
        graph_weight: float = 0.3,
        keyword_weight: float = 0.2,
        project_filter: str | None = None,
    ) -> list[RetrievalHit]:
        hits: dict[str, RetrievalHit] = {}

        q_lower = query.lower()

        # Vector search (with optional project filter)
        try:
            q_emb = await self.llm.embed(query)
            where_clause = {"project": project_filter} if project_filter else None
            results = self.collection.query(
                query_embeddings=[q_emb],
                n_results=min(limit * 2, 20),
                where=where_clause,
            )
            if results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0] or [{}] * len(results["documents"][0]),
                    results["distances"][0] if results["distances"] else [0.5] * len(results["documents"][0]),
                ):
                    key = self._doc_id(doc, meta.get("source", "vector"))
                    score = max(0.0, 1.0 - float(dist)) * vector_weight
                    hits[key] = RetrievalHit(
                        content=doc,
                        source=meta.get("source", "vector"),
                        score=score,
                        metadata=dict(meta),
                    )
        except Exception:
            pass

        # Graph search
        for item in self.graph.search_keyword(query):
            key = f"graph:{item['id']}"
            score = graph_weight
            if project_filter and project_filter not in key and project_filter not in json.dumps(item["attrs"]):
                score *= 0.3
            hits[key] = RetrievalHit(
                content=json.dumps(item["attrs"]),
                source=f"graph:{item['id']}",
                score=score,
                metadata={"entity": item["id"]},
            )

        # Keyword search (with optional project filter)
        for doc_id, entry in self._keyword_index.items():
            text = entry.get("text", "")
            entry_project = entry.get("project", "")
            if project_filter and entry_project and entry_project != project_filter:
                continue
            if q_lower in text.lower():
                words = q_lower.split()
                matches = sum(1 for w in words if w in text.lower())
                score = (matches / max(len(words), 1)) * keyword_weight
                key = f"kw:{doc_id}"
                if key not in hits or hits[key].score < score:
                    hits[key] = RetrievalHit(
                        content=text,
                        source=entry.get("source", "keyword"),
                        score=score,
                        metadata=entry,
                    )

        ranked = sorted(hits.values(), key=lambda h: h.score, reverse=True)
        return ranked[:limit]

    async def search_similar_projects(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find projects similar to the given query using vector similarity."""
        try:
            q_emb = await self.llm.embed(query)
            results = self.project_collection.query(
                query_embeddings=[q_emb],
                n_results=limit,
            )
            projects = []
            if results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0] or [],
                    results["distances"][0] or [],
                ):
                    similarity = 1.0 - float(dist)
                    projects.append({
                        "project": meta.get("project", "unknown"),
                        "description": meta.get("description", ""),
                        "tech_stack": meta.get("tech_stack", "").split(",") if meta.get("tech_stack") else [],
                        "similarity": round(similarity, 4),
                        "document": doc,
                    })
            return projects
        except Exception:
            return []

    def format_context(self, hits: list[RetrievalHit]) -> str:
        if not hits:
            return ""
        lines = ["## Retrieved Memory"]
        for h in hits:
            lines.append(f"- [{h.source} score={h.score:.2f}] {h.content[:300]}")
        return "\n".join(lines)
