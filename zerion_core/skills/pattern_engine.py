"""Pattern extraction engine: automatic pattern detection from skill usage."""

from __future__ import annotations

import json
import hashlib
from collections import defaultdict, Counter
from typing import Any, Callable

from zerion_core.skills.memory_system import SkillMemorySystem


class PatternExtractor:
    """Extracts patterns from skill memory and usage."""

    def __init__(self, memory_system: SkillMemorySystem) -> None:
        self._memory = memory_system
        self._min_frequency = 2
        self._min_success_rate = 0.6

    async def extract_patterns(
        self,
        skill_id: str,
        llm_fn: Callable[..., Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Extract patterns from skill memories."""
        memories = self._memory.recall_memories(skill_id, limit=100)
        if len(memories) < self._min_frequency:
            return []

        # Cluster memories by task similarity
        clusters = self._cluster_memories(memories)

        patterns = []
        for cluster_name, cluster_memories in clusters.items():
            if len(cluster_memories) < self._min_frequency:
                continue

            success_count = sum(1 for m in cluster_memories if m["success_score"] >= 0.6)
            success_rate = success_count / len(cluster_memories)

            if success_rate < self._min_success_rate:
                continue

            pattern_name = await self._generate_pattern_name(
                cluster_name, cluster_memories, llm_fn
            )

            pattern_id = self._memory.record_pattern(
                skill_id=skill_id,
                pattern_name=pattern_name,
                examples=[m["task"][:200] for m in cluster_memories[:5]],
            )

            self._memory.update_pattern_success(pattern_id, True)

            patterns.append({
                "pattern_id": pattern_id,
                "pattern_name": pattern_name,
                "frequency": len(cluster_memories),
                "success_rate": success_rate,
                "examples": [m["task"][:100] for m in cluster_memories[:3]],
            })

        return patterns

    def _cluster_memories(self, memories: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Cluster memories by task similarity."""
        clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for memory in memories:
            task = memory.get("task", "")
            solution = memory.get("solution", "")

            # Simple keyword-based clustering
            key = self._generate_cluster_key(task, solution)
            clusters[key].append(memory)

        return dict(clusters)

    def _generate_cluster_key(self, task: str, solution: str) -> str:
        """Generate a cluster key from task and solution."""
        # Extract common patterns
        task_words = set(task.lower().split())
        solution_words = set(solution.lower().split())

        # Remove common stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "with", "by"}
        task_words -= stop_words
        solution_words -= stop_words

        # Use top keywords as cluster key
        all_words = task_words | solution_words
        if not all_words:
            return "general"

        # Sort by frequency in original text
        word_freq = Counter()
        for word in task.lower().split() + solution.lower().split():
            if word not in stop_words:
                word_freq[word] += 1

        top_words = [w for w, _ in word_freq.most_common(3)]
        return "_".join(sorted(top_words))

    async def _generate_pattern_name(
        self,
        cluster_key: str,
        memories: list[dict[str, Any]],
        llm_fn: Callable[..., Any] | None = None,
    ) -> str:
        """Generate a human-readable pattern name."""
        if llm_fn:
            tasks = [m["task"][:100] for m in memories[:5]]
            prompt = f"""Generate a short, descriptive pattern name for these related tasks:
{json.dumps(tasks, indent=2)}

Return only the pattern name, nothing else."""

            try:
                response = await llm_fn(prompt)
                return response.strip()[:100]
            except Exception:
                pass

        # Fallback: use cluster key
        return cluster_key.replace("_", " ").title()

    async def detect_new_patterns(
        self,
        skill_id: str,
        recent_memories: list[dict[str, Any]],
        llm_fn: Callable[..., Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Detect new patterns from recent memories."""
        existing_patterns = self._memory.get_patterns(skill_id, min_frequency=1)

        # Find tasks that don't match existing patterns
        new_tasks = []
        for memory in recent_memories:
            is_new = True
            for pattern in existing_patterns:
                if self._task_matches_pattern(memory["task"], pattern):
                    is_new = False
                    break
            if is_new:
                new_tasks.append(memory)

        if len(new_tasks) < self._min_frequency:
            return []

        # Extract new patterns
        return await self.extract_patterns(skill_id, llm_fn)

    def _task_matches_pattern(self, task: str, pattern: dict[str, Any]) -> bool:
        """Check if a task matches an existing pattern."""
        pattern_name = pattern.get("pattern_name", "").lower()
        task_lower = task.lower()

        # Simple word overlap check
        pattern_words = set(pattern_name.split())
        task_words = set(task_lower.split())

        overlap = len(pattern_words & task_words)
        return overlap >= 2

    def get_recommended_patterns(
        self,
        skill_id: str,
        task: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Get recommended patterns for a task."""
        patterns = self._memory.get_patterns(
            skill_id,
            min_frequency=self._min_frequency,
            min_success_rate=self._min_success_rate,
        )

        if not patterns:
            return []

        # Score patterns by relevance to task
        task_words = set(task.lower().split())
        scored = []

        for pattern in patterns:
            pattern_words = set(pattern.get("pattern_name", "").lower().split())
            examples = " ".join(json.loads(pattern.get("examples", "[]"))).lower()
            example_words = set(examples.split())

            # Combine pattern name and example relevance
            name_overlap = len(task_words & pattern_words)
            example_overlap = len(task_words & example_words)
            score = (name_overlap * 0.6 + example_overlap * 0.4) * pattern.get("success_rate", 0.5)

            if score > 0:
                scored.append((score, pattern))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:top_k]]
