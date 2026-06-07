"""Skill manager: orchestrates all skill subsystems."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from zerion_core.skills.context import SkillContextBuilder
from zerion_core.skills.installer import SkillInstaller
from zerion_core.skills.loader import SkillLoader
from zerion_core.skills.matcher import SkillMatcher
from zerion_core.skills.memory import SkillMemory
from zerion_core.skills.models import (
    Skill,
    SkillRegistryEntry,
    SkillSearchResult,
    SkillStatus,
    _utcnow,
)
from zerion_core.skills.permissions import SkillPermissions
from zerion_core.skills.rag import SkillRAG
from zerion_core.skills.registry import SkillRegistry
from zerion_core.skills.workflow import SkillWorkflowEngine


class SkillManager:
    """Main skill manager: orchestrates loading, matching, activation, context injection."""

    def __init__(
        self,
        skills_dir: Path | None = None,
        db_path: Path | None = None,
        embedding_fn: Any = None,
        on_event: Callable[[str, str], None] | None = None,
    ) -> None:
        self._skills_dir = skills_dir or Path("skills")
        self._on_event = on_event or (lambda s, m: None)

        self.loader = SkillLoader(self._skills_dir)
        self.registry = SkillRegistry(db_path)
        self.matcher = SkillMatcher(embedding_fn)
        self.memory = SkillMemory(self.registry)
        self.context_builder = SkillContextBuilder()
        self.installer = SkillInstaller(self.loader, self.registry, self._skills_dir)
        self.permissions = SkillPermissions()
        self.rag = SkillRAG()
        self.workflow = SkillWorkflowEngine()

        self._loaded: dict[str, Skill] = {}
        self._active: dict[str, Skill] = {}
        self._composites: dict[str, dict[str, Skill]] = {}
        self._disabled: set[str] = set()

        self._load_index()

    def _emit(self, stage: str, message: str) -> None:
        self._on_event(stage, message)

    def _load_index(self) -> None:
        """Load skill embeddings index."""
        index_path = self._skills_dir / "_index" / "skill_embeddings.json"
        if index_path.exists():
            self.matcher.load_index(index_path)

    def _save_index(self) -> None:
        """Save skill embeddings index."""
        index_path = self._skills_dir / "_index" / "skill_embeddings.json"
        self.matcher.save_index(index_path)

    # --- Core Operations ---

    def load_all(self) -> dict[str, Skill]:
        """Load all installed skills."""
        self._loaded = self.loader.load_all()
        for name, skill in self._loaded.items():
            self.matcher.index_skill(skill)
            if skill.doc_chunks and skill.manifest.rag.enabled:
                self.rag.index_skill_docs(name, skill.doc_chunks)
        return dict(self._loaded)

    async def install(self, source: str) -> tuple[bool, str]:
        """Install a skill from a source."""
        self._emit("skill", f"Installing from {source}...")
        ok, msg = await self.installer.install(source)
        if ok:
            skill = self.loader.reload(source.split("/")[-1].split(":")[-1])
            if skill:
                self._loaded[skill.manifest.name] = skill
                await self.matcher.embed_skill(skill)
                self._save_index()
                self._emit("skill", f"Installed: {skill.manifest.name}")
        return ok, msg

    async def uninstall(self, name: str) -> tuple[bool, str]:
        """Uninstall a skill."""
        self._active.pop(name, None)
        self._loaded.pop(name, None)
        self._disabled.discard(name)
        self.rag.clear_skill(name)
        ok, msg = await self.installer.uninstall(name)
        self._save_index()
        self._emit("skill", f"Uninstalled: {name}")
        return ok, msg

    async def update(self, name: str) -> tuple[bool, str]:
        """Update a skill."""
        ok, msg = await self.installer.update(name)
        if ok:
            skill = self.loader.reload(name)
            if skill:
                self._loaded[name] = skill
                await self.matcher.embed_skill(skill)
                self._save_index()
        return ok, msg

    def enable(self, name: str) -> bool:
        """Enable a skill."""
        if name not in self._loaded:
            return False
        self._disabled.discard(name)
        self._active[name] = self._loaded[name]
        self._emit("skill", f"Enabled: {name}")
        return True

    def disable(self, name: str) -> bool:
        """Disable a skill."""
        self._disabled.add(name)
        self._active.pop(name, None)
        self._emit("skill", f"Disabled: {name}")
        return True

    def reload(self, name: str) -> Skill | None:
        """Hot-reload a skill."""
        skill = self.loader.reload(name)
        if skill:
            self._loaded[name] = skill
            if name in self._active:
                self._active[name] = skill
            self.matcher.index_skill(skill)
        return skill

    # --- Matching & Auto-Activation ---

    async def match_skills(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[SkillSearchResult]:
        """Find skills matching a query."""
        available = {n: s for n, s in self._loaded.items() if n not in self._disabled}
        return await self.matcher.find_matches(query, available, top_k, min_score)

    async def auto_activate(self, query: str) -> list[str]:
        """Auto-activate skills matching a query. Returns activated names."""
        matches = await self.match_skills(query, top_k=3, min_score=0.6)
        activated = []
        for match in matches:
            skill = self._loaded.get(match.skill_name)
            if skill and skill.manifest.auto_activate:
                self._active[match.skill_name] = skill
                activated.append(match.skill_name)
                self._emit("skill", f"Auto-activated: {match.skill_name} (score={match.score:.2f})")
        return activated

    # --- Context & Prompts ---

    def build_context(
        self,
        user_request: str,
        base_system: str = "",
        session_memory: str = "",
        project_memory: str = "",
        rag_context: str = "",
    ) -> str:
        """Build complete context with active skills."""
        return self.context_builder.build_context(
            active_skills=self._active,
            base_system=base_system,
            session_memory=session_memory,
            project_memory=project_memory,
            rag_context=rag_context,
            user_request=user_request,
        )

    def inject_skill_prompts(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Inject active skill prompts into messages."""
        return self.context_builder.inject_skill_prompts(messages, self._active)

    def get_workflow_prompt(self, user_request: str) -> str:
        """Get workflow prompt from active skills."""
        prompts = []
        for skill in self._active.values():
            if skill.manifest.workflow.steps or skill.content.workflow:
                prompts.append(self.workflow.build_workflow_prompt(skill, user_request))
        return "\n\n".join(prompts)

    # --- Composition ---

    def compose(self, skill_names: list[str], composite_name: str = "") -> tuple[bool, str]:
        """Create a composite skill from multiple skills."""
        skills = {}
        for name in skill_names:
            skill = self._loaded.get(name)
            if not skill:
                return False, f"Skill not found: {name}"
            skills[name] = skill

        comp_name = composite_name or "+".join(skill_names)
        self._composites[comp_name] = skills
        return True, f"Created composite: {comp_name}"

    def activate_composite(self, name: str) -> bool:
        """Activate a composite skill."""
        skills = self._composites.get(name)
        if not skills:
            return False
        for skill_name, skill in skills.items():
            self._active[skill_name] = skill
        return True

    # --- Memory ---

    def record_usage(self, skill_name: str, success: bool, score: float = 0.5) -> None:
        """Record skill usage for learning."""
        skill = self._loaded.get(skill_name)
        if skill:
            skill.record_use(success, score)
            self.registry.record_activation(skill_name, "", score, success)

    def recall_skill_memory(self, skill_name: str, query: str = "") -> str:
        """Get formatted memory context for a skill."""
        return self.memory.format_for_prompt(skill_name, query)

    # --- Queries ---

    def list_installed(self) -> list[Skill]:
        return list(self._loaded.values())

    def list_active(self) -> list[Skill]:
        return list(self._active.values())

    def list_disabled(self) -> list[str]:
        return list(self._disabled)

    def get_skill(self, name: str) -> Skill | None:
        return self._loaded.get(name)

    def get_active(self, name: str) -> Skill | None:
        return self._active.get(name)

    def is_active(self, name: str) -> bool:
        return name in self._active

    def search(self, query: str) -> list[Skill]:
        """Simple text search of loaded skills."""
        query_lower = query.lower()
        results = []
        for skill in self._loaded.values():
            text = f"{skill.manifest.name} {skill.manifest.description} {' '.join(skill.manifest.tags)}".lower()
            if query_lower in text:
                results.append(skill)
        return results

    # --- Info & Stats ---

    def get_skill_info(self, name: str) -> dict[str, Any]:
        """Get detailed info about a skill."""
        skill = self._loaded.get(name)
        if not skill:
            return {}

        stats = self.registry.get_activation_stats(name)
        mem_stats = self.memory.get_stats(name)

        return {
            "name": skill.manifest.name,
            "version": skill.manifest.version,
            "description": skill.manifest.description,
            "author": skill.manifest.author,
            "tags": skill.manifest.tags,
            "status": skill.status.value,
            "active": name in self._active,
            "disabled": name in self._disabled,
            "usage_count": stats["usage_count"],
            "success_count": stats["success_count"],
            "avg_score": stats["avg_score"],
            "memory_entries": mem_stats["total"],
            "memory_successful": mem_stats["successful"],
            "doc_chunks": len(skill.doc_chunks),
            "has_workflow": bool(skill.manifest.workflow.steps),
            "has_rag": skill.manifest.rag.enabled,
            "tools_required": skill.manifest.tools.required,
            "tools_denied": skill.manifest.tools.denied,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get overall skill system stats."""
        return {
            "installed": len(self._loaded),
            "active": len(self._active),
            "disabled": len(self._disabled),
            "composites": len(self._composites),
            "total_usage": sum(s.usage_count for s in self._loaded.values()),
            "total_doc_chunks": sum(len(s.doc_chunks) for s in self._loaded.values()),
        }

    def close(self) -> None:
        """Cleanup resources."""
        self._save_index()
        self.registry.close()
