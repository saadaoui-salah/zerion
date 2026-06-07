"""Persistent project-level memory layer (survives across sessions)."""

from __future__ import annotations

from typing import Any

from zerion_core.llm.ollama import OllamaClient
from zerion_core.llm.model_router import ModelRouter
from zerion_core.session.models import ProjectMemory
from zerion_core.session.store import SessionStore

PROJECT_MEMORY_SYSTEM = """You are a project memory manager. Given a conversation or code change, extract and maintain persistent project knowledge.

Extract:
1. Architecture decisions (why a pattern was chosen)
2. Known bugs or issues
3. Important files and their roles
4. Coding conventions observed
5. API patterns used
6. Test commands and how to run them

Return JSON only:
{
  "architecture_decisions": ["..."],
  "known_bugs": ["..."],
  "important_files": ["path/to/file.py - description"],
  "coding_conventions": ["..."],
  "api_patterns": ["..."],
  "test_commands": ["..."]
}

Only include NEW information not already in existing memory. If no new info, return empty arrays.
"""


class ProjectMemoryManager:
    """Maintains persistent project-level knowledge across sessions."""

    def __init__(self, store: SessionStore, llm: OllamaClient) -> None:
        self.store = store
        self.llm = llm

    def get_memory(self, project_id: str) -> ProjectMemory:
        """Load or create project memory."""
        mem = self.store.get_project_memory(project_id)
        if mem is None:
            mem = ProjectMemory(project_id=project_id)
            self.store.save_project_memory(mem)
        return mem

    async def update_from_conversation(
        self,
        project_id: str,
        messages: list[dict[str, str]],
        tool_events_summary: str = "",
    ) -> ProjectMemory:
        """Extract new knowledge from conversation and merge into project memory."""
        existing = self.get_memory(project_id)
        existing_text = self._memory_to_text(existing)

        # Build extraction prompt
        conv_text = "\n".join(
            f"[{m.get('role', 'user')}]: {m.get('content', '')[:1500]}"
            for m in messages[-20:]
        )
        if tool_events_summary:
            conv_text += f"\n\nTool activity:\n{tool_events_summary}"

        prompt = f"## Existing Project Memory\n{existing_text}\n\n## Recent Conversation\n{conv_text}"

        try:
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=ModelRouter.for_task("memory_extraction"),
                system=PROJECT_MEMORY_SYSTEM,
                json_mode=True,
                temperature=0.1,
            )
            extracted = json.loads(resp.content)
        except (json.JSONDecodeError, Exception):
            return existing

        # Merge extracted info into existing memory
        from zerion_core.session.models import _utcnow
        if extracted.get("architecture_decisions"):
            existing.architecture_decisions = self._merge_lists(
                existing.architecture_decisions, extracted["architecture_decisions"]
            )
        if extracted.get("known_bugs"):
            existing.known_bugs = self._merge_lists(
                existing.known_bugs, extracted["known_bugs"]
            )
        if extracted.get("important_files"):
            existing.important_files = self._merge_lists(
                existing.important_files, extracted["important_files"]
            )
        if extracted.get("coding_conventions"):
            existing.coding_conventions = self._merge_lists(
                existing.coding_conventions, extracted["coding_conventions"]
            )
        if extracted.get("api_patterns"):
            existing.api_patterns = self._merge_lists(
                existing.api_patterns, extracted["api_patterns"]
            )
        if extracted.get("test_commands"):
            existing.test_commands = self._merge_lists(
                existing.test_commands, extracted["test_commands"]
            )

        existing.updated_at = _utcnow()
        self.store.save_project_memory(existing)
        return existing

    def add_decision(self, project_id: str, decision: str) -> None:
        mem = self.get_memory(project_id)
        if decision not in mem.architecture_decisions:
            mem.architecture_decisions.append(decision)
            from zerion_core.session.models import _utcnow
            mem.updated_at = _utcnow()
            self.store.save_project_memory(mem)

    def add_bug(self, project_id: str, bug: str) -> None:
        mem = self.get_memory(project_id)
        if bug not in mem.known_bugs:
            mem.known_bugs.append(bug)
            from zerion_core.session.models import _utcnow
            mem.updated_at = _utcnow()
            self.store.save_project_memory(mem)

    def add_important_file(self, project_id: str, file_path: str, description: str = "") -> None:
        mem = self.get_memory(project_id)
        entry = f"{file_path} - {description}" if description else file_path
        if not any(file_path in f for f in mem.important_files):
            mem.important_files.append(entry)
            from zerion_core.session.models import _utcnow
            mem.updated_at = _utcnow()
            self.store.save_project_memory(mem)

    def add_convention(self, project_id: str, convention: str) -> None:
        mem = self.get_memory(project_id)
        if convention not in mem.coding_conventions:
            mem.coding_conventions.append(convention)
            from zerion_core.session.models import _utcnow
            mem.updated_at = _utcnow()
            self.store.save_project_memory(mem)

    def add_test_command(self, project_id: str, command: str) -> None:
        mem = self.get_memory(project_id)
        if command not in mem.test_commands:
            mem.test_commands.append(command)
            from zerion_core.session.models import _utcnow
            mem.updated_at = _utcnow()
            self.store.save_project_memory(mem)

    def format_for_context(self, project_id: str) -> str:
        """Format project memory as a context block for LLM."""
        mem = self.get_memory(project_id)
        if not self._has_content(mem):
            return ""

        lines: list[str] = ["## Project Memory"]

        if mem.description:
            lines.append(f"Description: {mem.description}")
        if mem.tech_stack:
            lines.append(f"Tech Stack: {', '.join(mem.tech_stack)}")
        if mem.architecture_decisions:
            lines.append("\n### Architecture Decisions")
            for d in mem.architecture_decisions[-10:]:
                lines.append(f"- {d}")
        if mem.known_bugs:
            lines.append("\n### Known Bugs")
            for b in mem.known_bugs[-10:]:
                lines.append(f"- {b}")
        if mem.important_files:
            lines.append("\n### Important Files")
            for f in mem.important_files[-15:]:
                lines.append(f"- {f}")
        if mem.coding_conventions:
            lines.append("\n### Coding Conventions")
            for c in mem.coding_conventions[-10:]:
                lines.append(f"- {c}")
        if mem.api_patterns:
            lines.append("\n### API Patterns")
            for p in mem.api_patterns[-10:]:
                lines.append(f"- {p}")
        if mem.test_commands:
            lines.append("\n### Test Commands")
            for t in mem.test_commands[-5:]:
                lines.append(f"- `{t}`")

        return "\n".join(lines)

    def _memory_to_text(self, mem: ProjectMemory) -> str:
        parts: list[str] = []
        if mem.architecture_decisions:
            parts.append("Decisions: " + "; ".join(mem.architecture_decisions[-5:]))
        if mem.known_bugs:
            parts.append("Bugs: " + "; ".join(mem.known_bugs[-5:]))
        if mem.important_files:
            parts.append("Files: " + "; ".join(mem.important_files[-5:]))
        if mem.coding_conventions:
            parts.append("Conventions: " + "; ".join(mem.coding_conventions[-5:]))
        return "\n".join(parts) if parts else "(no existing memory)"

    def _has_content(self, mem: ProjectMemory) -> bool:
        return bool(
            mem.description
            or mem.tech_stack
            or mem.architecture_decisions
            or mem.known_bugs
            or mem.important_files
            or mem.coding_conventions
            or mem.api_patterns
            or mem.test_commands
        )

    def _merge_lists(self, existing: list[str], new: list[str], max_items: int = 20) -> list[str]:
        """Merge new items into existing list, dedup by similarity."""
        result = list(existing)
        for item in new:
            item_lower = item.lower().strip()
            if not any(item_lower in e.lower() or e.lower() in item_lower for e in result):
                result.append(item)
        return result[-max_items:]
