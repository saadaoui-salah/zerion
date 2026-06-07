"""Skill reputation system: dynamic reputation scoring based on usage and outcomes."""

from __future__ import annotations

import math
from typing import Any
from datetime import datetime, timezone, timedelta

from zerion_core.skills.memory_system import SkillMemorySystem


class SkillReputation:
    """Computes and maintains dynamic skill reputation scores."""

    def __init__(self, memory_system: SkillMemorySystem) -> None:
        self._memory = memory_system

    def compute_reputation(
        self,
        skill_id: str,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Compute comprehensive reputation score."""
        # Get memory stats
        memories = self._memory.recall_memories(skill_id, project_id=project_id, limit=1000)
        patterns = self._memory.get_patterns(skill_id, min_frequency=1)
        failures = self._memory.get_failures(skill_id, project_id=project_id)

        if not memories and not patterns:
            return {
                "skill_id": skill_id,
                "reputation": 50.0,
                "confidence": 0.1,
                "breakdown": {},
            }

        # Compute components
        success_rate = self._compute_success_rate(memories)
        frequency_score = self._compute_frequency_score(memories)
        pattern_score = self._compute_pattern_score(patterns)
        failure_penalty = self._compute_failure_penalty(failures)
        recency_bonus = self._compute_recency_bonus(memories)
        consistency_score = self._compute_consistency_score(memories)

        # Weighted combination
        breakdown = {
            "success_rate": success_rate * 0.30,
            "frequency": frequency_score * 0.15,
            "patterns": pattern_score * 0.15,
            "failure_penalty": failure_penalty * -0.15,
            "recency": recency_bonus * 0.15,
            "consistency": consistency_score * 0.10,
        }

        raw_score = 50.0 + sum(breakdown.values()) * 50.0
        reputation = max(0.0, min(100.0, raw_score))

        # Confidence based on data volume
        data_points = len(memories) + len(patterns) + len(failures)
        confidence = min(1.0, data_points / 50)

        return {
            "skill_id": skill_id,
            "reputation": round(reputation, 2),
            "confidence": round(confidence, 4),
            "breakdown": {k: round(v, 4) for k, v in breakdown.items()},
            "stats": {
                "total_memories": len(memories),
                "total_patterns": len(patterns),
                "total_failures": len(failures),
            },
        }

    def rank_skills(
        self,
        skill_ids: list[str],
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Rank skills by reputation."""
        rankings = []
        for skill_id in skill_ids:
            rep = self.compute_reputation(skill_id, project_id)
            rankings.append(rep)

        rankings.sort(key=lambda x: x["reputation"], reverse=True)

        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return rankings

    def _compute_success_rate(self, memories: list[dict[str, Any]]) -> float:
        """Compute success rate from memories."""
        if not memories:
            return 0.5

        scores = [m.get("success_score", 0.5) for m in memories]
        return sum(scores) / len(scores)

    def _compute_frequency_score(self, memories: list[dict[str, Any]]) -> float:
        """Compute frequency score (logarithmic scaling)."""
        count = len(memories)
        if count == 0:
            return 0.0
        # Logarithmic scaling: 1=0.0, 10=0.5, 100=1.0
        return min(1.0, math.log10(count + 1) / 2)

    def _compute_pattern_score(self, patterns: list[dict[str, Any]]) -> float:
        """Compute score from discovered patterns."""
        if not patterns:
            return 0.0

        total_score = 0.0
        for p in patterns:
            freq = p.get("frequency", 1)
            success_rate = p.get("success_rate", 0.5)
            # Patterns with higher frequency and success rate contribute more
            pattern_score = min(1.0, (freq / 10) * success_rate)
            total_score += pattern_score

        # Normalize by number of patterns
        return min(1.0, total_score / max(len(patterns), 1))

    def _compute_failure_penalty(self, failures: list[dict[str, Any]]) -> float:
        """Compute penalty from failures."""
        if not failures:
            return 0.0

        # More failures = higher penalty, but with diminishing returns
        return min(1.0, len(failures) / 20)

    def _compute_recency_bonus(self, memories: list[dict[str, Any]]) -> float:
        """Compute bonus for recent successful usage."""
        if not memories:
            return 0.0

        now = datetime.now(timezone.utc)
        recent_successes = 0

        for m in memories:
            created = m.get("created_at", "")
            score = m.get("success_score", 0.5)

            if not created:
                continue

            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                days_ago = (now - created_dt).days

                if days_ago <= 7 and score >= 0.7:
                    recent_successes += 1
            except (ValueError, TypeError):
                continue

        return min(1.0, recent_successes / 5)

    def _compute_consistency_score(self, memories: list[dict[str, Any]]) -> float:
        """Compute consistency of success scores."""
        if len(memories) < 3:
            return 0.5

        scores = [m.get("success_score", 0.5) for m in memories]
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = math.sqrt(variance)

        # Lower std_dev = higher consistency
        # std_dev of 0 = perfect consistency (1.0)
        # std_dev of 0.5 = moderate consistency (0.5)
        # std_dev of 1.0 = low consistency (0.0)
        return max(0.0, 1.0 - std_dev * 2)
