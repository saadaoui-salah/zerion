"""Skill RAG: per-skill documentation retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class SkillRAG:
    """Manages per-skill documentation indexing and retrieval."""

    def __init__(self) -> None:
        self._indexes: dict[str, list[dict[str, Any]]] = {}
        self._embeddings: dict[str, list[list[float]]] = {}

    def index_skill_docs(
        self,
        skill_name: str,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Index documentation chunks for a skill."""
        self._indexes[skill_name] = chunks
        if embeddings:
            self._embeddings[skill_name] = embeddings
        return len(chunks)

    def retrieve(
        self,
        skill_name: str,
        query: str,
        query_embedding: list[float] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant docs for a skill."""
        chunks = self._indexes.get(skill_name, [])
        if not chunks:
            return []

        if query_embedding and skill_name in self._embeddings:
            return self._semantic_retrieve(
                chunks, self._embeddings[skill_name], query_embedding, top_k
            )

        return self._keyword_retrieve(chunks, query, top_k)

    def _keyword_retrieve(
        self,
        chunks: list[dict[str, Any]],
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Simple keyword-based retrieval."""
        query_words = set(query.lower().split())
        scored: list[tuple[float, dict[str, Any]]] = []

        for chunk in chunks:
            content = chunk.get("content", "").lower()
            content_words = set(content.split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def _semantic_retrieve(
        self,
        chunks: list[dict[str, Any]],
        chunk_embeddings: list[list[float]],
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Semantic retrieval using cosine similarity."""
        import numpy as np

        query_arr = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_arr)
        if query_norm == 0:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for i, chunk in enumerate(chunks):
            if i >= len(chunk_embeddings):
                break
            emb = np.array(chunk_embeddings[i], dtype=np.float32)
            emb_norm = np.linalg.norm(emb)
            if emb_norm == 0:
                continue
            score = float(np.dot(query_arr, emb) / (query_norm * emb_norm))
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def get_skill_chunks(self, skill_name: str) -> list[dict[str, Any]]:
        """Get all chunks for a skill."""
        return self._indexes.get(skill_name, [])

    def clear_skill(self, skill_name: str) -> None:
        """Clear index for a skill."""
        self._indexes.pop(skill_name, None)
        self._embeddings.pop(skill_name, None)

    def clear_all(self) -> None:
        """Clear all indexes."""
        self._indexes.clear()
        self._embeddings.clear()

    def get_stats(self) -> dict[str, int]:
        """Get indexing stats."""
        return {name: len(chunks) for name, chunks in self._indexes.items()}
