from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zerion_core.config import settings
from zerion_core.llm.ollama import OllamaClient
from zerion_core.llm.model_router import ModelRouter
from zerion_core.memory.manager import MemoryManager


class RepositoryIntelligence:
    """Auto-generate ARCHITECTURE.md, PROJECT_MAP.md, BUG_HISTORY.md, DECISIONS.md, LESSONS.md."""

    def __init__(self, memory: MemoryManager, llm: OllamaClient) -> None:
        self.memory = memory
        self.llm = llm
        self.root = settings.repo_intel_dir

    async def generate_all(self, project: str, pipeline_results: dict[str, Any]) -> None:
        snap = self.memory.repository.snapshot()
        episodic = self.memory.get_episodic(project)
        plan = pipeline_results.get("plan", {})

        await self._write_architecture(project, plan, pipeline_results)
        await self._write_project_map(project, plan)
        self._write_bugs(snap)
        self._write_decisions(snap)
        self._write_lessons(episodic, snap)
        await self._write_dna(project, episodic)
        await self._write_refactor_opportunities(project, snap)

    async def _write_architecture(
        self, project: str, plan: dict[str, Any], results: dict[str, Any]
    ) -> None:
        content = await self._llm_section(
            "Write ARCHITECTURE.md for this project. Include components, data flow, tech stack.",
            {"project": project, "plan": plan, "category": results.get("category")},
        )
        self._save("ARCHITECTURE.md", content)

    async def _write_project_map(self, project: str, plan: dict[str, Any]) -> None:
        team = plan.get("team", [])
        tasks = plan.get("tasks", [])
        lines = [
            f"# Project Map: {project}",
            f"\nUpdated: {datetime.now(timezone.utc).isoformat()}",
            "\n## Team",
        ]
        for m in team:
            lines.append(f"- **{m.get('name')}** ({m.get('role')}): {m.get('responsibility', '')}")
        lines.append("\n## Tasks")
        for t in tasks:
            deps = ", ".join(t.get("depends_on", [])) or "none"
            lines.append(f"- [{t.get('id')}] {t.get('title')} (depends: {deps})")
        self._save("PROJECT_MAP.md", "\n".join(lines))

    def _write_bugs(self, snap: dict[str, Any]) -> None:
        lines = ["# Bug History", ""]
        for b in snap.get("bugs_fixed", [])[-50:]:
            lines.append(f"## {b.get('at', '')}")
            lines.append(f"**Project:** {b.get('project', 'n/a')}")
            lines.append(f"- Bug: {b.get('bug')}")
            lines.append(f"- Fix: {b.get('fix')}\n")
        self._save("BUG_HISTORY.md", "\n".join(lines) if len(lines) > 2 else "# Bug History\n\nNo bugs recorded yet.\n")

    def _write_decisions(self, snap: dict[str, Any]) -> None:
        lines = ["# Architecture Decisions", ""]
        for d in snap.get("architecture_decisions", [])[-50:]:
            lines.append(f"- [{d.get('at', '')}] ({d.get('project', '')}) {d.get('text')}")
        self._save("DECISIONS.md", "\n".join(lines) if len(lines) > 2 else "# Decisions\n\nNo decisions yet.\n")

    def _write_lessons(self, episodic: Any, snap: dict[str, Any]) -> None:
        lines = ["# Lessons Learned", ""]
        for lesson in episodic.lessons:
            lines.append(f"- {lesson}")
        for p in snap.get("patterns", [])[-30:]:
            lines.append(f"- [{p.get('at', '')}] {p.get('text')}")
        self._save("LESSONS.md", "\n".join(lines) if len(lines) > 2 else "# Lessons\n\nNo lessons yet.\n")

    async def _write_dna(self, project: str, episodic: Any) -> None:
        content = await self._llm_section(
            "Write PROJECT_DNA.md. Track coding style, architecture preferences, common mistakes, and successful patterns.",
            {"project": project, "lessons": episodic.lessons},
        )
        self._save("PROJECT_DNA.md", content)

    async def _write_refactor_opportunities(self, project: str, snap: dict[str, Any]) -> None:
        content = await self._llm_section(
            "Write REFACTOR_OPPORTUNITIES.md. Analyze dependency issues, module structure, and technical debt.",
            {"project": project, "history": snap.get("architecture_decisions", [])},
        )
        self._save("REFACTOR_OPPORTUNITIES.md", content)

    async def _llm_section(self, instruction: str, context: dict[str, Any]) -> str:
        try:
            resp = await self.llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": f"{instruction}\n\nContext:\n{json.dumps(context, indent=2)[:6000]}",
                    }
                ],
                model=ModelRouter.for_task("documentation"),
                system="Write clear markdown documentation. No preamble.",
            )
            return resp.content
        except Exception:
            return f"# Architecture\n\nProject: {context.get('project', 'unknown')}\n"

    def _save(self, filename: str, content: str) -> None:
        path = self.root / filename
        path.write_text(content, encoding="utf-8")
