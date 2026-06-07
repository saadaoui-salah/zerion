"""Skill memory: per-skill memory for fixes, patterns, and solutions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from zerion_core.skills.models import SkillMemoryEntry, _utcnow
from zerion_core.skills.registry import SkillRegistry


class SkillMemory:
    """Per-skill memory that learns from successful usage."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def record_fix(
        self,
        skill_name: str,
        problem: str,
        solution: str,
        context: str = "",
        score: float = 0.8,
    ) -> int:
        """Record a successful fix."""
        entry = SkillMemoryEntry(
            skill_name=skill_name,
            entry_type="fix",
            content=f"Problem: {problem}\nSolution: {solution}",
            context=context,
            success=True,
            score=score,
            tags=json.dumps(["fix", "solution"]),
        )
        return self._registry.add_memory(entry)

    def record_pattern(
        self,
        skill_name: str,
        pattern: str,
        context: str = "",
        score: float = 0.7,
    ) -> int:
        """Record a discovered pattern."""
        entry = SkillMemoryEntry(
            skill_name=skill_name,
            entry_type="pattern",
            content=pattern,
            context=context,
            success=True,
            score=score,
            tags=json.dumps(["pattern"]),
        )
        return self._registry.add_memory(entry)

    def record_workflow(
        self,
        skill_name: str,
        workflow: str,
        success: bool = True,
        score: float = 0.6,
    ) -> int:
        """Record a workflow outcome."""
        entry = SkillMemoryEntry(
            skill_name=skill_name,
            entry_type="workflow",
            content=workflow,
            success=success,
            score=score if success else score * 0.5,
            tags=json.dumps(["workflow"]),
        )
        return self._registry.add_memory(entry)

    def record_solution(
        self,
        skill_name: str,
        problem: str,
        solution: str,
        context: str = "",
        score: float = 0.7,
    ) -> int:
        """Record a general solution."""
        entry = SkillMemoryEntry(
            skill_name=skill_name,
            entry_type="solution",
            content=f"{problem}: {solution}",
            context=context,
            success=True,
            score=score,
            tags=json.dumps(["solution"]),
        )
        return self._registry.add_memory(entry)

    def recall_fixes(
        self,
        skill_name: str,
        query: str = "",
        limit: int = 5,
    ) -> list[SkillMemoryEntry]:
        """Recall relevant fixes."""
        return self._registry.search_memory(
            skill_name, query=query, entry_type="fix", limit=limit
        )

    def recall_patterns(
        self,
        skill_name: str,
        query: str = "",
        limit: int = 5,
    ) -> list[SkillMemoryEntry]:
        """Recall relevant patterns."""
        return self._registry.search_memory(
            skill_name, query=query, entry_type="pattern", limit=limit
        )

    def recall_all(
        self,
        skill_name: str,
        query: str = "",
        limit: int = 10,
    ) -> list[SkillMemoryEntry]:
        """Recall all relevant memory entries."""
        return self._registry.search_memory(
            skill_name, query=query, limit=limit
        )

    def get_context(
        self,
        skill_name: str,
        query: str = "",
        max_entries: int = 5,
    ) -> str:
        """Get formatted memory context for a skill."""
        entries = self.recall_all(skill_name, query=query, limit=max_entries)
        if not entries:
            return ""

        parts = [f"## {skill_name} Memory"]
        for entry in entries:
            icon = "+" if entry.success else "-"
            parts.append(f"[{icon}] [{entry.entry_type}] {entry.content[:200]}")

        return "\n".join(parts)

    def update_usage(self, memory_id: int) -> None:
        """Update usage stats for a memory entry."""
        self._registry.update_memory_usage(memory_id)

    def get_stats(self, skill_name: str) -> dict[str, int]:
        """Get memory statistics for a skill."""
        return self._registry.get_memory_stats(skill_name)

    def prune(self, skill_name: str, max_entries: int = 1000) -> int:
        """Prune low-value memory entries."""
        return self._registry.prune_memory(skill_name, max_entries)

    def format_for_prompt(
        self,
        skill_name: str,
        query: str = "",
        max_tokens: int = 1000,
    ) -> str:
        """Format memory for injection into prompts."""
        entries = self.recall_all(skill_name, query=query, limit=8)
        if not entries:
            return ""

        parts = [f"### {skill_name} Learned Knowledge"]
        total_len = 0

        for entry in entries:
            text = f"- [{entry.entry_type}] {entry.content[:300]}"
            if total_len + len(text) > max_tokens:
                break
            parts.append(text)
            total_len += len(text)

        return "\n".join(parts)
