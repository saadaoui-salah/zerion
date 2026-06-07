"""Knowledge distillation: creates skill_brain.md files from accumulated experience."""

from __future__ import annotations

import json
from typing import Any, Callable
from pathlib import Path

from zerion_core.skills.memory_system import SkillMemorySystem
from zerion_core.skills.pattern_engine import PatternExtractor
from zerion_core.skills.collaboration import SkillCollaborationGraph
from zerion_core.skills.reputation import SkillReputation


class KnowledgeDistiller:
    """Distills skill knowledge into brain files."""

    def __init__(
        self,
        memory_system: SkillMemorySystem,
        pattern_engine: PatternExtractor,
        collaboration: SkillCollaborationGraph,
        reputation: SkillReputation,
        skills_dir: Path | None = None,
    ) -> None:
        self._memory = memory_system
        self._patterns = pattern_engine
        self._collaboration = collaboration
        self._reputation = reputation
        self._skills_dir = skills_dir or Path("skills")

    async def distill(
        self,
        skill_id: str,
        llm_fn: Callable[..., Any] | None = None,
    ) -> str:
        """Create skill_brain.md for a skill."""
        # Gather all knowledge
        memories = self._memory.recall_memories(skill_id, limit=50)
        patterns = self._memory.get_patterns(skill_id, min_frequency=2)
        failures = self._memory.get_failures(skill_id, limit=20)
        collaborators = self._collaboration.get_collaborators(skill_id, min_count=2)
        rep_data = self._reputation.compute_reputation(skill_id)

        # Build brain content
        brain = self._build_brain_content(
            skill_id, memories, patterns, failures, collaborators, rep_data
        )

        # Write to file
        skill_dir = self._skills_dir / skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        brain_path = skill_dir / "skill_brain.md"
        brain_path.write_text(brain, encoding="utf-8")

        return brain

    def _build_brain_content(
        self,
        skill_id: str,
        memories: list[dict[str, Any]],
        patterns: list[dict[str, Any]],
        failures: list[dict[str, Any]],
        collaborators: list[dict[str, Any]],
        reputation: dict[str, Any],
    ) -> str:
        """Build brain content from knowledge."""
        lines = [
            f"# {skill_id} Knowledge Brain",
            "",
            f"Generated from {len(memories)} experiences",
            f"Reputation: {reputation.get('reputation', 50):.1f}/100",
            "",
        ]

        # Most common bugs
        lines.append("## Most Common Bugs")
        if failures:
            bug_types: dict[str, int] = {}
            for f in failures:
                bug_type = f.get("failure_type", "unknown")
                bug_types[bug_type] = bug_types.get(bug_type, 0) + 1

            for bug, count in sorted(bug_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                lines.append(f"- {bug} (occurred {count} times)")
        else:
            lines.append("- No failures recorded yet")
        lines.append("")

        # Most successful fixes
        lines.append("## Most Successful Fixes")
        successful = [m for m in memories if m.get("success_score", 0) >= 0.7]
        if successful:
            for m in successful[:5]:
                lines.append(f"- {m.get('task', '')[:80]} (score: {m.get('success_score', 0):.2f})")
        else:
            lines.append("- No successful fixes recorded yet")
        lines.append("")

        # Discovered patterns
        lines.append("## Discovered Patterns")
        if patterns:
            for p in patterns[:5]:
                lines.append(f"- {p.get('pattern_name', 'Unknown')} "
                           f"(frequency: {p.get('frequency', 0)}, "
                           f"success: {p.get('success_rate', 0):.0%})")
        else:
            lines.append("- No patterns discovered yet")
        lines.append("")

        # Best workflows
        lines.append("## Best Workflows")
        lines.append("Based on successful patterns:")
        if patterns:
            for i, p in enumerate(patterns[:3], 1):
                lines.append(f"{i}. {p.get('pattern_name', 'Step')}")
        else:
            lines.append("- Default workflow applies")
        lines.append("")

        # Common project patterns
        lines.append("## Common Project Patterns")
        lines.append("Works well with:")
        if collaborators:
            for c in collaborators[:3]:
                lines.append(f"- {c['skill_id']} (collaborated {c['collaboration_count']} times, "
                           f"success: {c['success_rate']:.0%})")
        else:
            lines.append("- No collaboration data yet")
        lines.append("")

        # Lessons from failures
        lines.append("## Lessons from Failures")
        if failures:
            for f in failures[:5]:
                lines.append(f"- Avoid: {f.get('task', '')[:60]}")
                if f.get("root_cause"):
                    lines.append(f"  Root cause: {f['root_cause'][:60]}")
        else:
            lines.append("- No failure lessons recorded yet")
        lines.append("")

        # Statistics
        lines.append("## Statistics")
        lines.append(f"- Total experiences: {len(memories)}")
        lines.append(f"- Successful: {len(successful)}")
        lines.append(f"- Patterns discovered: {len(patterns)}")
        lines.append(f"- Failures recorded: {len(failures)}")
        lines.append(f"- Unique collaborators: {len(collaborators)}")

        return "\n".join(lines)

    async def distill_all(
        self,
        skill_ids: list[str],
        llm_fn: Callable[..., Any] | None = None,
    ) -> dict[str, str]:
        """Distill knowledge for multiple skills."""
        results = {}
        for skill_id in skill_ids:
            try:
                brain = await self.distill(skill_id, llm_fn)
                results[skill_id] = brain
            except Exception:
                results[skill_id] = ""
        return results

    def get_brain_path(self, skill_id: str) -> Path:
        """Get path to skill brain file."""
        return self._skills_dir / skill_id / "skill_brain.md"

    def load_brain(self, skill_id: str) -> str | None:
        """Load existing skill brain."""
        path = self.get_brain_path(skill_id)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
