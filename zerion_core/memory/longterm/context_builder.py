"""Optimized context builder with TurboQuant-inspired compression principles.

Applies:
A. Context Compression — never raw logs, always semantic summaries
B. Redundant memory elimination — merge similar memories
C. Attention efficiency — prioritize high-importance memories only
D. Sliding memory window — only recent + important memories enter context
E. Memory clustering — group similar memories before injection
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from zerion_core.memory.longterm.episodic_store import MemoryEvent
from zerion_core.memory.longterm.retrieval import RetrievalResult


MAX_CONTEXT_CHARS = 10000
MAX_MEMORIES_IN_CONTEXT = 12


class MemoryCluster:
    """A cluster of related memory events."""

    def __init__(self, label: str, events: list[MemoryEvent]) -> None:
        self.label = label
        self.events = events
        self.total_importance = sum(e.importance for e in events)

    def summary(self, max_items: int = 3) -> str:
        """Compressed summary of the cluster."""
        lines: list[str] = [f"**{self.label}** ({len(self.events)} events)"]
        for event in sorted(self.events, key=lambda e: e.importance, reverse=True)[:max_items]:
            snippet = event.content[:120].replace("\n", " ")
            lines.append(f"  - {snippet}")
        if len(self.events) > max_items:
            lines.append(f"  ... and {len(self.events) - max_items} more")
        return "\n".join(lines)


class OptimizedContextBuilder:
    """Builds compressed, optimized context for LLM calls.

    Principles (TurboQuant-inspired):
    1. Never send raw memory logs
    2. Merge similar memories into clusters
    3. Only high-importance memories enter context
    4. Sliding window: recent + important only
    5. Token budget enforced
    """

    def __init__(self, max_chars: int = MAX_CONTEXT_CHARS) -> None:
        self.max_chars = max_chars

    def build_context(
        self,
        retrieval_results: list[RetrievalResult],
        project_brain: str = "",
        session_summary: str = "",
        user_request: str = "",
        rag_context: str = "",
    ) -> str:
        """Build the final optimized context block.

        Applies clustering, dedup, and budget enforcement.
        """
        parts: list[str] = []
        budget = self.max_chars

        # 1. Project brain (highest priority, always included)
        if project_brain:
            brain_block = f"## Project Intelligence\n{project_brain}"
            if len(brain_block) < budget * 0.25:
                parts.append(brain_block)
                budget -= len(brain_block)

        # 2. Session summary (compressed recent memory)
        if session_summary:
            summary_block = f"## Recent Session\n{session_summary}"
            if len(summary_block) < budget * 0.2:
                parts.append(summary_block)
                budget -= len(summary_block)

        # 3. Long-term memories (clustered and compressed)
        if retrieval_results:
            memory_block = self._compress_memories(retrieval_results, budget * 0.4)
            if memory_block:
                parts.append(memory_block)
                budget -= len(memory_block)

        # 4. RAG code context
        if rag_context:
            if len(rag_context) < budget * 0.3:
                parts.append(rag_context)
                budget -= len(rag_context)

        # 5. User request (always last, always included)
        if user_request:
            parts.append(f"## Task\n{user_request}")

        return "\n\n".join(parts)

    def _compress_memories(
        self,
        results: list[RetrievalResult],
        max_chars: int,
    ) -> str:
        """Apply TurboQuant-inspired compression to memory results.

        Steps:
        1. Deduplicate similar memories
        2. Cluster related memories
        3. Prioritize by importance
        4. Compress into summary
        """
        if not results:
            return ""

        # Step 1: Deduplicate by content similarity
        deduped = self._deduplicate(results)

        # Step 2: Cluster by event type
        clusters = self._cluster_by_type(deduped)

        # Step 3: Sort clusters by total importance
        clusters.sort(key=lambda c: c.total_importance, reverse=True)

        # Step 4: Build compressed output within budget
        lines: list[str] = ["## Long-Term Memory"]
        total_chars = len(lines[0])

        for cluster in clusters:
            cluster_text = cluster.summary(max_items=2)
            if total_chars + len(cluster_text) > max_chars:
                # Try with fewer items
                cluster_text = cluster.summary(max_items=1)
                if total_chars + len(cluster_text) > max_chars:
                    break
            lines.append(cluster_text)
            total_chars += len(cluster_text) + 1

        return "\n".join(lines) if len(lines) > 1 else ""

    def _deduplicate(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """Remove near-duplicate memories."""
        if not results:
            return []

        seen_content: list[str] = []
        deduped: list[RetrievalResult] = []

        for r in results:
            # Normalize content for comparison
            normalized = re.sub(r"\s+", " ", r.event.content.lower().strip())[:200]
            is_dup = False
            for seen in seen_content:
                if self._similarity(normalized, seen) > 0.7:
                    is_dup = True
                    break
            if not is_dup:
                seen_content.append(normalized)
                deduped.append(r)

        return deduped

    def _cluster_by_type(self, results: list[RetrievalResult]) -> list[MemoryCluster]:
        """Cluster memories by event type."""
        type_groups: dict[str, list[MemoryEvent]] = defaultdict(list)
        for r in results:
            type_groups[r.event.event_type].append(r.event)

        type_labels = {
            "architecture_decision": "Architecture Decisions",
            "bug_fix": "Bug Fixes",
            "feature_implemented": "Features Implemented",
            "lesson_learned": "Lessons Learned",
            "pattern_identified": "Patterns Identified",
            "refactor": "Refactoring",
            "error_occurred": "Errors",
            "code_review": "Code Reviews",
            "test_result": "Test Results",
            "deployment": "Deployments",
            "user_confirmation": "User Confirmations",
            "query": "Queries",
        }

        clusters: list[MemoryCluster] = []
        for event_type, events in type_groups.items():
            label = type_labels.get(event_type, event_type.replace("_", " ").title())
            clusters.append(MemoryCluster(label=label, events=events))

        return clusters

    def _similarity(self, a: str, b: str) -> float:
        """Jaccard similarity between two strings."""
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)


def format_memory_events(events: list[MemoryEvent], max_events: int = 10) -> str:
    """Format memory events for human-readable output."""
    if not events:
        return "No memories found."

    lines: list[str] = []
    for event in events[:max_events]:
        type_label = event.event_type.replace("_", " ").title()
        snippet = event.content[:150].replace("\n", " ")
        lines.append(
            f"[{type_label}] (imp={event.importance:.2f}) {snippet}"
        )
    if len(events) > max_events:
        lines.append(f"... and {len(events) - max_events} more")
    return "\n".join(lines)


def format_retrieval_results(results: list[RetrievalResult], max_results: int = 10) -> str:
    """Format retrieval results for human-readable output."""
    if not results:
        return "No memories found."

    lines: list[str] = []
    for r in results[:max_results]:
        type_label = r.event.event_type.replace("_", " ").title()
        snippet = r.snippet[:150].replace("\n", " ")
        lines.append(
            f"[{type_label}] score={r.score:.2f} | {snippet}"
        )
    if len(results) > max_results:
        lines.append(f"... and {len(results) - max_results} more")
    return "\n".join(lines)
