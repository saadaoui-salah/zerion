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
        """Search across vector, graph, and keyword stores with adaptive scoring.

        Adaptivity for moderately complex tasks:
        - Longer/more specific queries increase keyword weight (exact matches matter)
        - Queries with tech terms increase graph weight (structured knowledge is valuable)
        - Short/vague queries increase vector weight (semantic similarity is more useful)
        """
        hits: dict[str, RetrievalHit] = {}

        q_lower = query.lower()
        words = q_lower.split()

        # --- Adaptive weight adjustment based on query characteristics ---
        adapted_vector = vector_weight
        adapted_graph = graph_weight
        adapted_keyword = keyword_weight

        # Longer queries (> 4 words) signal specificity → boost keyword matching
        if len(words) > 4:
            adapted_keyword += 0.1
            adapted_vector -= 0.05
            adapted_graph -= 0.05

        # Queries with technical terms → boost graph (structured knowledge)
        tech_terms = {
            "api", "database", "auth", "deploy", "test", "config", "schema",
            "endpoint", "middleware", "component", "service", "handler",
            "class", "function", "module", "package", "dependency",
        }
        tech_overlap = set(words) & tech_terms
        if tech_overlap:
            boost = min(0.15, len(tech_overlap) * 0.05)
            adapted_graph += boost
            adapted_vector -= boost / 2
            adapted_keyword -= boost / 2

        # Very short queries (1-2 words) → boost vector (semantic is better for vague)
        if len(words) <= 2:
            adapted_vector += 0.1
            adapted_keyword -= 0.05
            adapted_graph -= 0.05

        # Normalize weights to sum to 1.0
        total = adapted_vector + adapted_graph + adapted_keyword
        if total > 0:
            adapted_vector /= total
            adapted_graph /= total
            adapted_keyword /= total

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
                    score = max(0.0, 1.0 - float(dist)) * adapted_vector
                    hits[key] = RetrievalHit(
                        content=doc,
                        source=meta.get("source", "vector"),
                        score=score,
                        metadata=dict(meta),
                    )
        except Exception:
            pass

        # Graph search — with recency-aware scoring
        for item in self.graph.search_keyword(query):
            key = f"graph:{item['id']}"
            score = adapted_graph

            # Recency bonus: graph entries with recent timestamps score higher
            attrs = item.get("attrs", {})
            ts = attrs.get("timestamp") or attrs.get("updated_at")
            if ts:
                try:
                    from datetime import datetime, timezone
                    entry_time = datetime.fromisoformat(str(ts))
                    if entry_time.tzinfo is None:
                        entry_time = entry_time.replace(tzinfo=timezone.utc)
                    hours_old = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
                    if hours_old < 24:
                        score *= 1.2  # 20% bonus for very recent graph entries
                    elif hours_old < 168:  # 7 days
                        score *= 1.0 + 0.1 * max(0, 1.0 - hours_old / 168.0)
                except (ValueError, TypeError):
                    pass

            # Cross-project penalty
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
                matches = sum(1 for w in words if w in text.lower())
                # Use adapted keyword weight and boost for high match ratios
                match_ratio = matches / max(len(words), 1)
                # Bonus for matching more words (superlinear)
                score = (match_ratio ** 0.8) * adapted_keyword
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
