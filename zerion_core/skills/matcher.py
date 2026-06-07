"""Semantic skill matching: embed queries, find relevant skills, auto-activate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from zerion_core.skills.models import Skill, SkillSearchResult


class SkillMatcher:
    """Embeds skills and queries, finds semantic matches."""

    def __init__(self, embedding_fn: Any = None) -> None:
        self._embedding_fn = embedding_fn
        self._skill_embeddings: dict[str, list[float]] = {}
        self._skill_texts: dict[str, str] = {}

    def set_embedding_fn(self, fn: Any) -> None:
        self._embedding_fn = fn

    def index_skill(self, skill: Skill) -> None:
        """Generate and cache embedding for a skill."""
        text = self._skill_to_text(skill)
        self._skill_texts[skill.manifest.name] = text

    def _skill_to_text(self, skill: Skill) -> str:
        """Convert skill to searchable text."""
        parts = [
            skill.manifest.name,
            skill.manifest.description,
            " ".join(skill.manifest.tags),
        ]
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

    async def find_matches(
        self,
        query: str,
        skills: dict[str, Skill],
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[SkillSearchResult]:
        """Find skills matching a query."""
        query_embedding = await self.embed_query(query)
        if not query_embedding:
            return self._keyword_fallback(query, skills, top_k)

        results: list[SkillSearchResult] = []
        for name, skill in skills.items():
            skill_embedding = self._skill_embeddings.get(name, [])
            if not skill_embedding:
                skill_embedding = await self.embed_skill(skill)

            if not skill_embedding:
                continue

            score = self._cosine_similarity(query_embedding, skill_embedding)

            # Boost score based on tag matches
            tag_boost = self._tag_match_score(query, skill.manifest.tags)
            score = min(1.0, score + tag_boost * 0.15)

            # Boost based on usage success rate
            if skill.usage_count > 0:
                success_boost = skill.success_rate * 0.05
                score = min(1.0, score + success_boost)

            if score >= min_score:
                reason = self._generate_reason(query, skill, score)
                results.append(SkillSearchResult(
                    skill_name=name,
                    score=round(score, 4),
                    reason=reason,
                    manifest=skill.manifest,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def find_matches_by_embedding(
        self,
        embedding: list[float],
        skills: dict[str, Skill],
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[SkillSearchResult]:
        """Find skills matching a pre-computed embedding."""
        if not embedding:
            return []

        results: list[SkillSearchResult] = []
        for name, skill in skills.items():
            skill_embedding = self._skill_embeddings.get(name, [])
            if not skill_embedding:
                skill_embedding = await self.embed_skill(skill)

            if not skill_embedding:
                continue

            score = self._cosine_similarity(embedding, skill_embedding)
            if score >= min_score:
                results.append(SkillSearchResult(
                    skill_name=name,
                    score=round(score, 4),
                    reason=f"Semantic match (score={score:.2f})",
                    manifest=skill.manifest,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _keyword_fallback(
        self,
        query: str,
        skills: dict[str, Skill],
        top_k: int,
    ) -> list[SkillSearchResult]:
        """Fallback to keyword matching when embeddings unavailable."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        results: list[SkillSearchResult] = []
        for name, skill in skills.items():
            text = self._skill_to_text(skill).lower()
            text_words = set(text.split())

            overlap = len(query_words & text_words)
            if overlap > 0:
                score = min(1.0, overlap / max(len(query_words), 1))
                if score >= 0.3:
                    results.append(SkillSearchResult(
                        skill_name=name,
                        score=round(score, 4),
                        reason=f"Keyword match ({overlap} terms)",
                        manifest=skill.manifest,
                    ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        a_arr = np.array(a, dtype=np.float32)
        b_arr = np.array(b, dtype=np.float32)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))

    def _tag_match_score(self, query: str, tags: list[str]) -> float:
        """Score based on tag matches."""
        query_lower = query.lower()
        matches = sum(1 for tag in tags if tag.lower() in query_lower)
        return matches / max(len(tags), 1)

    def _generate_reason(self, query: str, skill: Skill, score: float) -> str:
        """Generate human-readable reason for match."""
        reasons = []
        query_lower = query.lower()

        for tag in skill.manifest.tags:
            if tag.lower() in query_lower:
                reasons.append(f"tag '{tag}'")

        if skill.manifest.description:
            desc_words = set(skill.manifest.description.lower().split())
            query_words = set(query_lower.split())
            if desc_words & query_words:
                reasons.append("description match")

        if not reasons:
            reasons.append("semantic similarity")

        return f"Matches: {', '.join(reasons)} (score={score:.2f})"

    def save_index(self, path: Path) -> None:
        """Save embeddings index to disk."""
        data = {
            "embeddings": self._skill_embeddings,
            "texts": self._skill_texts,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    def load_index(self, path: Path) -> bool:
        """Load embeddings index from disk."""
        if not path.exists():
            return False
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self._skill_embeddings = data.get("embeddings", {})
            self._skill_texts = data.get("texts", {})
            return True
        except Exception:
            return False
