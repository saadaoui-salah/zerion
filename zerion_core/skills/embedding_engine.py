"""Skill embedding engine: semantic search, related discovery, recommendations."""

from __future__ import annotations

import json
import numpy as np
from pathlib import Path
from typing import Any, Callable
from collections import defaultdict

from zerion_core.skills.models import Skill, SkillSearchResult


class SkillEmbeddingEngine:
    """Advanced embedding engine for semantic skill operations."""

    def __init__(self, embedding_fn: Callable[..., Any] | None = None) -> None:
        self._embedding_fn = embedding_fn
        self._skill_embeddings: dict[str, list[float]] = {}
        self._skill_texts: dict[str, str] = {}
        self._skill_vectors: dict[str, np.ndarray] = {}
        self._index_path: Path | None = None

    def set_embedding_fn(self, fn: Callable[..., Any]) -> None:
        self._embedding_fn = fn

    def set_index_path(self, path: Path) -> None:
        self._index_path = path

    def _skill_to_text(self, skill: Skill) -> str:
        """Convert skill to rich searchable text."""
        parts = [
            skill.manifest.name,
            skill.manifest.description,
            " ".join(skill.manifest.tags),
        ]
        if skill.content.system_prompt:
            parts.append(skill.content.system_prompt[:1000])
        if skill.content.examples:
            parts.append(skill.content.examples[:500])
        if skill.content.workflow:
            parts.append(skill.content.workflow[:500])
        return " | ".join(p for p in parts if p)

    async def embed_skill(self, skill: Skill) -> list[float]:
        """Generate embedding for a skill."""
        if not self._embedding_fn:
            return []
        text = self._skill_to_text(skill)
        try:
            embedding = await self._embedding_fn(text)
            self._skill_embeddings[skill.manifest.name] = embedding
            self._skill_texts[skill.manifest.name] = text
            self._skill_vectors[skill.manifest.name] = np.array(embedding, dtype=np.float32)
            return embedding
        except Exception:
            return []

    async def embed_query(self, query: str) -> list[float]:
        """Embed a user query."""
        if not self._embedding_fn:
            return []
        try:
            return await self._embedding_fn(query)
        except Exception:
            return []

    async def semantic_search(
        self,
        query: str,
        skills: dict[str, Skill],
        top_k: int = 5,
        min_score: float = 0.4,
    ) -> list[SkillSearchResult]:
        """Semantic search across all skills."""
        query_embedding = await self.embed_query(query)
        if not query_embedding:
            return self._keyword_fallback(query, skills, top_k)

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        results: list[SkillSearchResult] = []
        for name, skill in skills.items():
            skill_vec = self._skill_vectors.get(name)
            if skill_vec is None:
                await self.embed_skill(skill)
                skill_vec = self._skill_vectors.get(name)
            if skill_vec is None:
                continue

            skill_norm = np.linalg.norm(skill_vec)
            if skill_norm == 0:
                continue

            score = float(np.dot(query_vec, skill_vec) / (query_norm * skill_norm))

            # Boost based on tag relevance
            tag_boost = self._tag_relevance(query, skill.manifest.tags)
            score = min(1.0, score + tag_boost * 0.1)

            # Boost based on description word overlap
            desc_boost = self._word_overlap(query, skill.manifest.description)
            score = min(1.0, score + desc_boost * 0.05)

            if score >= min_score:
                results.append(SkillSearchResult(
                    skill_name=name,
                    score=round(score, 4),
                    reason=self._explain_match(query, skill, score),
                    manifest=skill.manifest,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def find_related(
        self,
        skill_name: str,
        skills: dict[str, Skill],
        top_k: int = 5,
    ) -> list[SkillSearchResult]:
        """Find skills related to a given skill."""
        source_vec = self._skill_vectors.get(skill_name)
        if source_vec is None:
            return []

        source_norm = np.linalg.norm(source_vec)
        if source_norm == 0:
            return []

        results: list[SkillSearchResult] = []
        for name, skill in skills.items():
            if name == skill_name:
                continue

            target_vec = self._skill_vectors.get(name)
            if target_vec is None:
                continue

            target_norm = np.linalg.norm(target_vec)
            if target_norm == 0:
                continue

            score = float(np.dot(source_vec, target_vec) / (source_norm * target_norm))

            # Boost based on shared tags
            shared_tags = set(skill.manifest.tags) & set(skills[skill_name].manifest.tags)
            tag_boost = len(shared_tags) * 0.05
            score = min(1.0, score + tag_boost)

            if score >= 0.3:
                results.append(SkillSearchResult(
                    skill_name=name,
                    score=round(score, 4),
                    reason=f"Related to {skill_name} (shared: {', '.join(shared_tags[:3])})",
                    manifest=skill.manifest,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def recommend_skills(
        self,
        query: str,
        project_context: str,
        skills: dict[str, Skill],
        history: list[dict[str, Any]] | None = None,
        top_k: int = 3,
    ) -> list[SkillSearchResult]:
        """Recommend skills based on query, project context, and history."""
        query_embedding = await self.embed_query(query)
        project_embedding = await self.embed_query(project_context) if project_context else None

        combined_embedding = self._combine_embeddings(query_embedding, project_embedding)

        if not combined_embedding:
            return self._keyword_fallback(query, skills, top_k)

        results = await self.semantic_search(query, skills, top_k=top_k * 2, min_score=0.3)

        # Apply historical success boost
        if history:
            success_map = self._build_success_map(history)
            for result in results:
                if result.skill_name in success_map:
                    boost = success_map[result.skill_name] * 0.15
                    result.score = min(1.0, result.score + boost)

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def nearest_neighbor(
        self,
        embedding: list[float],
        skills: dict[str, Skill],
        top_k: int = 5,
    ) -> list[SkillSearchResult]:
        """Find nearest neighbors to an embedding."""
        if not embedding:
            return []

        query_vec = np.array(embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        results: list[SkillSearchResult] = []
        for name, skill in skills.items():
            skill_vec = self._skill_vectors.get(name)
            if skill_vec is None:
                continue

            skill_norm = np.linalg.norm(skill_vec)
            if skill_norm == 0:
                continue

            score = float(np.dot(query_vec, skill_vec) / (query_norm * skill_norm))
            if score >= 0.3:
                results.append(SkillSearchResult(
                    skill_name=name,
                    score=round(score, 4),
                    reason=f"Nearest neighbor (score={score:.2f})",
                    manifest=skill.manifest,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _combine_embeddings(
        self,
        *embeddings: list[float] | None,
    ) -> list[float] | None:
        """Combine multiple embeddings into one."""
        valid = [e for e in embeddings if e]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0]

        arrays = [np.array(e, dtype=np.float32) for e in valid]
        max_len = max(len(a) for a in arrays)
        padded = []
        for a in arrays:
            if len(a) < max_len:
                padded.append(np.pad(a, (0, max_len - len(a))))
            else:
                padded.append(a)

        combined = np.mean(padded, axis=0)
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm
        return combined.tolist()

    def _tag_relevance(self, query: str, tags: list[str]) -> float:
        """Calculate tag relevance to query."""
        query_lower = query.lower()
        matches = sum(1 for tag in tags if tag.lower() in query_lower)
        return matches / max(len(tags), 1)

    def _word_overlap(self, text1: str, text2: str) -> float:
        """Calculate word overlap between two texts."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        overlap = len(words1 & words2)
        return overlap / min(len(words1), len(words2))

    def _keyword_fallback(
        self,
        query: str,
        skills: dict[str, Skill],
        top_k: int,
    ) -> list[SkillSearchResult]:
        """Fallback to keyword matching."""
        query_words = set(query.lower().split())
        results: list[SkillSearchResult] = []

        for name, skill in skills.items():
            text = self._skill_to_text(skill).lower()
            text_words = set(text.split())
            overlap = len(query_words & text_words)
            if overlap > 0:
                score = min(1.0, overlap / max(len(query_words), 1))
                if score >= 0.2:
                    results.append(SkillSearchResult(
                        skill_name=name,
                        score=round(score, 4),
                        reason=f"Keyword match ({overlap} terms)",
                        manifest=skill.manifest,
                    ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _explain_match(self, query: str, skill: Skill, score: float) -> str:
        """Generate explanation for a match."""
        reasons = []
        query_lower = query.lower()

        for tag in skill.manifest.tags:
            if tag.lower() in query_lower:
                reasons.append(f"tag '{tag}'")

        if any(w in skill.manifest.description.lower() for w in query_lower.split()):
            reasons.append("description match")

        if not reasons:
            reasons.append("semantic similarity")

        return f"Matches: {', '.join(reasons)} (score={score:.2f})"

    def _build_success_map(self, history: list[dict[str, Any]]) -> dict[str, float]:
        """Build success rate map from history."""
        counts: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})

        for entry in history:
            skill_name = entry.get("skill_name", "")
            success = entry.get("success", False)
            if skill_name:
                counts[skill_name]["total"] += 1
                if success:
                    counts[skill_name]["success"] += 1

        return {
            name: data["success"] / max(data["total"], 1)
            for name, data in counts.items()
        }

    def save_index(self, path: Path | None = None) -> None:
        """Save embeddings index to disk."""
        save_path = path or self._index_path
        if not save_path:
            return

        data = {
            "embeddings": self._skill_embeddings,
            "texts": self._skill_texts,
        }
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(data, f)

    def load_index(self, path: Path | None = None) -> bool:
        """Load embeddings index from disk."""
        load_path = path or self._index_path
        if not load_path or not load_path.exists():
            return False

        try:
            with open(load_path, "r") as f:
                data = json.load(f)
            self._skill_embeddings = data.get("embeddings", {})
            self._skill_texts = data.get("texts", {})

            for name, emb in self._skill_embeddings.items():
                self._skill_vectors[name] = np.array(emb, dtype=np.float32)

            return True
        except Exception:
            return False
