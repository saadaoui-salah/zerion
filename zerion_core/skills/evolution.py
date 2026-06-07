"""Skill evolution engine: skills improve themselves over time."""

from __future__ import annotations

import json
from typing import Any, Callable

from zerion_core.skills.memory_system import SkillMemorySystem
from zerion_core.skills.pattern_engine import PatternExtractor


class SkillEvolution:
    """Evolves skills based on accumulated experience."""

    def __init__(
        self,
        memory_system: SkillMemorySystem,
        pattern_extractor: PatternExtractor,
    ) -> None:
        self._memory = memory_system
        self._patterns = pattern_extractor

    async def evolve_skill(
        self,
        skill_id: str,
        llm_fn: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze and evolve a skill based on its memory."""
        # Get recent memories
        memories = self._memory.recall_memories(skill_id, limit=100)
        patterns = self._memory.get_patterns(skill_id, min_frequency=1)
        failures = self._memory.get_failures(skill_id, limit=50)

        # Analyze current state
        analysis = self._analyze_skill_state(memories, patterns, failures)

        # Detect new patterns
        new_patterns = await self._patterns.detect_new_patterns(
            skill_id, memories, llm_fn
        )

        # Generate improved workflow
        improved_workflow = await self._generate_improved_workflow(
            skill_id, analysis, new_patterns, llm_fn
        )

        # Generate optimized system prompt
        optimized_prompt = await self._optimize_system_prompt(
            skill_id, analysis, patterns, failures, llm_fn
        )

        evolution_result = {
            "skill_id": skill_id,
            "analysis": analysis,
            "new_patterns": new_patterns,
            "improved_workflow": improved_workflow,
            "optimized_prompt": optimized_prompt,
            "recommendations": self._generate_recommendations(analysis),
        }

        return evolution_result

    def _analyze_skill_state(
        self,
        memories: list[dict[str, Any]],
        patterns: list[dict[str, Any]],
        failures: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze current skill state."""
        if not memories:
            return {
                "maturity": "new",
                "success_rate": 0.5,
                "total_experience": 0,
                "pattern_count": 0,
                "failure_count": 0,
            }

        scores = [m.get("success_score", 0.5) for m in memories]
        avg_score = sum(scores) / len(scores)

        if len(memories) < 5:
            maturity = "novice"
        elif len(memories) < 20:
            maturity = "developing"
        elif len(memories) < 100:
            maturity = "experienced"
        else:
            maturity = "expert"

        return {
            "maturity": maturity,
            "success_rate": round(avg_score, 4),
            "total_experience": len(memories),
            "pattern_count": len(patterns),
            "failure_count": len(failures),
            "score_trend": self._compute_score_trend(memories),
        }

    def _compute_score_trend(self, memories: list[dict[str, Any]]) -> str:
        """Compute score trend from memories."""
        if len(memories) < 5:
            return "insufficient_data"

        sorted_memories = sorted(memories, key=lambda m: m.get("created_at", ""))
        recent = sorted_memories[-5:]
        older = sorted_memories[:5] if len(sorted_memories) > 5 else sorted_memories[:1]

        recent_avg = sum(m.get("success_score", 0.5) for m in recent) / len(recent)
        older_avg = sum(m.get("success_score", 0.5) for m in older) / len(older)

        delta = recent_avg - older_avg
        if delta > 0.1:
            return "improving"
        elif delta < -0.1:
            return "declining"
        return "stable"

    async def _generate_improved_workflow(
        self,
        skill_id: str,
        analysis: dict[str, Any],
        new_patterns: list[dict[str, Any]],
        llm_fn: Callable[..., Any] | None = None,
    ) -> list[str]:
        """Generate improved workflow based on patterns."""
        if not llm_fn:
            return []

        patterns_text = json.dumps(new_patterns[:5], indent=2)
        prompt = f"""Based on these discovered patterns for {skill_id}:
{patterns_text}

Current maturity: {analysis.get('maturity', 'unknown')}
Success rate: {analysis.get('success_rate', 0.5):.2%}

Generate an improved workflow as a JSON array of step names.
Focus on steps that address the most common patterns.

Return only the JSON array."""

        try:
            response = await llm_fn(prompt)
            workflow = json.loads(response)
            if isinstance(workflow, list):
                return [str(s) for s in workflow]
        except Exception:
            pass

        return []

    async def _optimize_system_prompt(
        self,
        skill_id: str,
        analysis: dict[str, Any],
        patterns: list[dict[str, Any]],
        failures: list[dict[str, Any]],
        llm_fn: Callable[..., Any] | None = None,
    ) -> str:
        """Generate optimized system prompt based on experience."""
        if not llm_fn:
            return ""

        patterns_text = "\n".join(
            f"- {p.get('pattern_name', 'Unknown')} (success: {p.get('success_rate', 0):.0%})"
            for p in patterns[:5]
        )

        failures_text = "\n".join(
            f"- Avoid: {f.get('task', '')[:50]} - {f.get('root_cause', '')[:50]}"
            for f in failures[:5]
        )

        prompt = f"""Optimize the system prompt for {skill_id} based on experience.

Current state:
- Maturity: {analysis.get('maturity', 'unknown')}
- Success rate: {analysis.get('success_rate', 0.5):.2%}
- Total experience: {analysis.get('total_experience', 0)} tasks

Successful patterns:
{patterns_text or 'None yet'}

Lessons from failures:
{failures_text or 'None yet'}

Generate an optimized system prompt that incorporates these learnings.
Focus on actionable guidance that improves success rate."""

        try:
            return await llm_fn(prompt)
        except Exception:
            return ""

    def _generate_recommendations(self, analysis: dict[str, Any]) -> list[str]:
        """Generate recommendations for skill improvement."""
        recommendations = []

        if analysis.get("success_rate", 0.5) < 0.6:
            recommendations.append("Focus on more successful patterns to improve success rate")

        if analysis.get("failure_count", 0) > 10:
            recommendations.append("Review and learn from recorded failures")

        if analysis.get("pattern_count", 0) < 3:
            recommendations.append("Continue using to discover more patterns")

        if analysis.get("maturity") == "novice":
            recommendations.append("Gain more experience before complex tasks")

        if analysis.get("score_trend") == "declining":
            recommendations.append("Recent performance declining - review recent changes")

        return recommendations

    async def consolidate_knowledge(
        self,
        skill_id: str,
        llm_fn: Callable[..., Any] | None = None,
    ) -> str:
        """Consolidate all knowledge into a brain file."""
        memories = self._memory.recall_memories(skill_id, limit=50)
        patterns = self._memory.get_patterns(skill_id, min_frequency=2)
        failures = self._memory.get_failures(skill_id, limit=20)

        # Group memories by outcome
        successful = [m for m in memories if m.get("success_score", 0) >= 0.7]
        failed = [m for m in memories if m.get("success_score", 0) < 0.5]

        brain_content = f"# {skill_id} Knowledge Brain\n\n"

        # Most common successful tasks
        brain_content += "## Most Successful Tasks\n"
        for m in successful[:5]:
            brain_content += f"- {m.get('task', '')[:100]} (score: {m.get('success_score', 0):.2f})\n"

        # Discovered patterns
        brain_content += "\n## Discovered Patterns\n"
        for p in patterns[:5]:
            brain_content += f"- {p.get('pattern_name', 'Unknown')} (frequency: {p.get('frequency', 0)}, success: {p.get('success_rate', 0):.0%})\n"

        # Lessons from failures
        brain_content += "\n## Lessons from Failures\n"
        for f in failures[:5]:
            brain_content += f"- Avoid: {f.get('task', '')[:80]} - {f.get('root_cause', '')[:80]}\n"

        # Best workflows
        brain_content += "\n## Best Workflows\n"
        brain_content += "Based on successful patterns:\n"
        for p in patterns[:3]:
            brain_content += f"1. {p.get('pattern_name', 'Step')}\n"

        return brain_content
