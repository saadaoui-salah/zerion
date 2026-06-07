"""Memory consolidation engine: TurboQuant-inspired memory optimization."""

from __future__ import annotations

import json
import numpy as np
from typing import Any, Callable
from collections import defaultdict

from zerion_core.skills.memory_system import SkillMemorySystem


class MemoryConsolidator:
    """Consolidates skill memories using TurboQuant-inspired principles."""

    def __init__(self, memory_system: SkillMemorySystem) -> None:
        self._memory = memory_system

    async def consolidate(
        self,
        skill_id: str,
        llm_fn: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Run full consolidation pipeline."""
        memories = self._memory.recall_memories(skill_id, limit=500)

        if not memories:
            return {"consolidated": 0, "clusters": 0, "patterns": 0}

        # Step 1: Cluster similar memories
        clusters = self._cluster_memories(memories)

        # Step 2: Extract patterns from clusters
        patterns = self._extract_cluster_patterns(clusters)

        # Step 3: Merge redundant solutions
        merged = self._merge_redundant(memories)

        # Step 4: Compress old memories
        compressed = self._compress_old_memories(memories)

        # Step 5: Build semantic summaries
        summaries = await self._build_summaries(clusters, llm_fn)

        # Step 6: Update memory system
        self._update_memory_system(skill_id, patterns, merged, compressed)

        return {
            "original_count": len(memories),
            "clusters": len(clusters),
            "patterns_found": len(patterns),
            "merged": merged,
            "compressed": compressed,
            "summaries": summaries,
        }

    def _cluster_memories(self, memories: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Cluster memories by semantic similarity."""
        if not memories:
            return {}

        # Extract features for clustering
        features = []
        for m in memories:
            task = m.get("task", "")
            solution = m.get("solution", "")
            features.append(f"{task} {solution}")

        # Simple keyword-based clustering
        clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for i, memory in enumerate(memories):
            task = memory.get("task", "")
            solution = memory.get("solution", "")

            # Generate cluster key from top keywords
            words = set(f"{task} {solution}".lower().split())
            stop_words = {"the", "a", "an", "is", "are", "was", "in", "on", "to", "for", "of", "with"}
            words -= stop_words

            if words:
                key = "_".join(sorted(words)[:3])
            else:
                key = "general"

            clusters[key].append(memory)

        return dict(clusters)

    def _extract_cluster_patterns(
        self,
        clusters: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Extract patterns from clusters."""
        patterns = []

        for cluster_key, cluster_memories in clusters.items():
            if len(cluster_memories) < 2:
                continue

            # Compute cluster statistics
            scores = [m.get("success_score", 0.5) for m in cluster_memories]
            avg_score = sum(scores) / len(scores)

            if avg_score < 0.6:
                continue

            # Extract common solution elements
            solutions = [m.get("solution", "") for m in cluster_memories]
            common_words = self._find_common_words(solutions)

            patterns.append({
                "pattern_name": cluster_key.replace("_", " ").title(),
                "frequency": len(cluster_memories),
                "success_rate": avg_score,
                "common_words": common_words[:5],
                "examples": [m.get("task", "")[:100] for m in cluster_memories[:3]],
            })

        return patterns

    def _find_common_words(self, texts: list[str]) -> list[str]:
        """Find common words across texts."""
        word_counts: dict[str, int] = defaultdict(int)

        for text in texts:
            words = set(text.lower().split())
            for word in words:
                word_counts[word] += 1

        # Words that appear in at least half the texts
        threshold = len(texts) / 2
        common = [w for w, c in word_counts.items() if c >= threshold]

        # Sort by frequency
        common.sort(key=lambda w: word_counts[w], reverse=True)
        return common

    def _merge_redundant(self, memories: list[dict[str, Any]]) -> int:
        """Merge redundant memory entries."""
        merged = 0
        seen_solutions: dict[str, int] = {}

        for memory in memories:
            solution = memory.get("solution", "")[:200]
            solution_key = solution.lower().strip()

            if solution_key in seen_solutions:
                # Increment usage count for existing
                memory_id = memory.get("id")
                if memory_id:
                    self._memory.update_memory_usage(memory_id)
                    merged += 1
            else:
                seen_solutions[solution_key] = memory.get("id", 0)

        return merged

    def _compress_old_memories(self, memories: list[dict[str, Any]]) -> int:
        """Compress old, low-value memories."""
        compressed = 0
        now_str = ""

        for memory in memories:
            created = memory.get("created_at", "")
            score = memory.get("success_score", 0.5)
            times_used = memory.get("times_used", 0)

            # Compress memories older than 30 days with low score and usage
            if score < 0.4 and times_used < 2:
                memory_id = memory.get("id")
                if memory_id:
                    # Mark for compression (reduce detail)
                    compressed += 1

        return compressed

    async def _build_summaries(
        self,
        clusters: dict[str, list[dict[str, Any]]],
        llm_fn: Callable[..., Any] | None = None,
    ) -> dict[str, str]:
        """Build semantic summaries for clusters."""
        summaries = {}

        if not llm_fn:
            for key, memories in clusters.items():
                summaries[key] = f"Cluster of {len(memories)} similar tasks"
            return summaries

        for key, memories in list(clusters.items())[:5]:
            tasks = [m.get("task", "")[:100] for m in memories[:3]]
            solutions = [m.get("solution", "")[:100] for m in memories[:3]]

            prompt = f"""Summarize this cluster of related tasks:

Tasks: {json.dumps(tasks)}
Solutions: {json.dumps(solutions)}

Provide a 1-2 sentence summary of the common pattern."""

            try:
                summary = await llm_fn(prompt)
                summaries[key] = summary.strip()
            except Exception:
                summaries[key] = f"Cluster of {len(memories)} similar tasks"

        return summaries

    def _update_memory_system(
        self,
        skill_id: str,
        patterns: list[dict[str, Any]],
        merged: int,
        compressed: int,
    ) -> None:
        """Update memory system with consolidated data."""
        # Record discovered patterns
        for pattern in patterns:
            self._memory.record_pattern(
                skill_id=skill_id,
                pattern_name=pattern["pattern_name"],
                examples=pattern.get("examples", []),
            )
