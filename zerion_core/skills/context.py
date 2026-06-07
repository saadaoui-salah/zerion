"""Skill context builder: merges skill content into the prompt pipeline."""

from __future__ import annotations

from typing import Any

from zerion_core.skills.models import Skill


class SkillContextBuilder:
    """Builds merged context from active skills, session, project, and RAG."""

    def __init__(self) -> None:
        self._max_tokens = 8000

    def build_context(
        self,
        active_skills: dict[str, Skill],
        base_system: str = "",
        session_memory: str = "",
        project_memory: str = "",
        rag_context: str = "",
        user_request: str = "",
    ) -> str:
        """Build complete context with skill injection."""
        sections: list[str] = []

        # Base system prompt
        if base_system:
            sections.append(("System", base_system))

        # Active skill expertise
        skill_sections = self._build_skill_sections(active_skills)
        if skill_sections:
            sections.append(("Active Expertise", skill_sections))

        # Active skill workflows
        workflow_sections = self._build_workflow_sections(active_skills)
        if workflow_sections:
            sections.append(("Workflows", workflow_sections))

        # Active skill examples
        example_sections = self._build_example_sections(active_skills)
        if example_sections:
            sections.append(("Examples", example_sections))

        # Session memory
        if session_memory:
            sections.append(("Session Context", session_memory))

        # Project memory
        if project_memory:
            sections.append(("Project Context", project_memory))

        # RAG context
        if rag_context:
            sections.append(("Code Context", rag_context))

        # Skill-specific RAG
        skill_rag = self._build_skill_rag(active_skills, user_request)
        if skill_rag:
            sections.append(("Documentation", skill_rag))

        return self._assemble(sections)

    def _build_skill_sections(self, skills: dict[str, Skill]) -> str:
        """Build expertise sections from active skills."""
        parts: list[str] = []
        for name, skill in skills.items():
            if skill.content.system_prompt:
                parts.append(f"### {name} Expertise\n{skill.content.system_prompt}")
        return "\n\n".join(parts)

    def _build_workflow_sections(self, skills: dict[str, Skill]) -> str:
        """Build workflow sections from active skills."""
        parts: list[str] = []
        for name, skill in skills.items():
            if skill.manifest.workflow.steps:
                steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(skill.manifest.workflow.steps))
                parts.append(f"### {name} Workflow\n{skill.manifest.workflow.name or 'Standard'}:\n{steps}")
            elif skill.content.workflow:
                parts.append(f"### {name} Workflow\n{skill.content.workflow}")
        return "\n\n".join(parts)

    def _build_example_sections(self, skills: dict[str, Skill]) -> str:
        """Build example sections from active skills."""
        parts: list[str] = []
        for name, skill in skills.items():
            if skill.content.examples:
                truncated = skill.content.examples[:2000]
                parts.append(f"### {name} Examples\n{truncated}")
        return "\n\n".join(parts)

    def _build_skill_rag(self, skills: dict[str, Skill], query: str) -> str:
        """Retrieve relevant documentation from skill RAG."""
        parts: list[str] = []
        for name, skill in skills.items():
            if not skill.doc_chunks or not skill.manifest.rag.enabled:
                continue
            relevant = self._retrieve_from_chunks(skill.doc_chunks, query, skill.manifest.rag.top_k)
            if relevant:
                parts.append(f"### {name} Documentation\n{relevant}")
        return "\n\n".join(parts)

    def _retrieve_from_chunks(
        self,
        chunks: list[dict[str, Any]],
        query: str,
        top_k: int,
    ) -> str:
        """Simple keyword-based retrieval from doc chunks."""
        query_words = set(query.lower().split())
        scored: list[tuple[float, str]] = []

        for chunk in chunks:
            content = chunk.get("content", "")
            content_words = set(content.lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                scored.append((score, content))

        scored.sort(key=lambda x: x[0], reverse=True)
        return "\n\n---\n\n".join(c for _, c in scored[:top_k])

    def _assemble(self, sections: list[tuple[str, str]]) -> str:
        """Assemble sections into a single context string."""
        if not sections:
            return ""

        parts: list[str] = []
        total_len = 0

        for title, content in sections:
            section = f"## {title}\n{content}"
            if total_len + len(section) > self._max_tokens:
                remaining = self._max_tokens - total_len
                if remaining > 200:
                    section = section[:remaining] + "\n[truncated]"
                    parts.append(section)
                break
            parts.append(section)
            total_len += len(section) + 2

        return "\n\n".join(parts)

    def build_skill_summary(self, skills: dict[str, Skill]) -> str:
        """Build a compact summary of active skills."""
        if not skills:
            return "No active skills."

        lines = ["Active Skills:"]
        for name, skill in skills.items():
            tags = ", ".join(skill.manifest.tags[:3])
            lines.append(f"  - {name} ({tags}) — {skill.manifest.description[:60]}")
        return "\n".join(lines)

    def inject_skill_prompts(
        self,
        messages: list[dict[str, str]],
        skills: dict[str, Skill],
    ) -> list[dict[str, str]]:
        """Inject skill system prompts into message history."""
        if not skills:
            return messages

        skill_system = []
        for name, skill in skills.items():
            if skill.content.system_prompt:
                skill_system.append(f"[Skill: {name}]\n{skill.content.system_prompt}")

        if not skill_system:
            return messages

        injection = "\n\n".join(skill_system)
        enhanced = list(messages)

        if enhanced and enhanced[0].get("role") == "system":
            enhanced[0]["content"] += f"\n\n{injection}"
        else:
            enhanced.insert(0, {"role": "system", "content": injection})

        return enhanced
