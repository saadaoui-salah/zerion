"""Enhanced skill manager: orchestrates all advanced skill subsystems."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from zerion_core.skills.collaboration import SkillCollaborationGraph
from zerion_core.skills.consolidation import MemoryConsolidator
from zerion_core.skills.context import SkillContextBuilder
from zerion_core.skills.distillation import KnowledgeDistiller
from zerion_core.skills.embedding_engine import SkillEmbeddingEngine
from zerion_core.skills.evolution import SkillEvolution
from zerion_core.skills.installer import SkillInstaller
from zerion_core.skills.loader import SkillLoader
from zerion_core.skills.memory_system import SkillMemorySystem
from zerion_core.config import settings
from zerion_core.skills.models import (
    Skill,
    SkillRegistryEntry,
    SkillSearchResult,
    SkillStatus,
    _utcnow,
)
from zerion_core.skills.pattern_engine import PatternExtractor
from zerion_core.skills.permissions import SkillPermissions
from zerion_core.skills.rag import SkillRAG
from zerion_core.skills.registry import SkillRegistry
from zerion_core.skills.reputation import SkillReputation
from zerion_core.skills.success_scoring import SuccessScorer, OutcomeSignals
from zerion_core.skills.workflow import SkillWorkflowEngine


class EnhancedSkillManager:
    """Main skill manager with all advanced capabilities."""

    def __init__(
        self,
        skills_dir: Path | None = None,
        db_path: Path | None = None,
        embedding_fn: Any = None,
        llm_fn: Any = None,
        on_event: Callable[[str, str], None] | None = None,
    ) -> None:
        self._skills_dir = skills_dir or Path("skills")
        self._on_event = on_event or (lambda s, m: None)
        self._llm_fn = llm_fn

        # Resolve db_path to absolute path based on skills_dir's parent memory directory
        if db_path is None:
            # Use the memory directory from the workspace (parent of skills dir)
            memory_dir = settings.memory_root
            db_path = memory_dir / "skill_registry.db"

        # Core systems
        self.loader = SkillLoader(self._skills_dir)
        self.registry = SkillRegistry(db_path)
        self.context_builder = SkillContextBuilder()
        self.installer = SkillInstaller(self.loader, self.registry, self._skills_dir)
        self.permissions = SkillPermissions()
        self.rag = SkillRAG()
        self.workflow = SkillWorkflowEngine()

        # Advanced systems
        self.embedding_engine = SkillEmbeddingEngine(embedding_fn)
        self.memory_system = SkillMemorySystem()
        self.pattern_engine = PatternExtractor(self.memory_system)
        self.success_scorer = SuccessScorer()
        self.reputation = SkillReputation(self.memory_system)
        self.collaboration = SkillCollaborationGraph()
        self.consolidation = MemoryConsolidator(self.memory_system)
        self.evolution = SkillEvolution(self.memory_system, self.pattern_engine)
        self.distillation = KnowledgeDistiller(
            self.memory_system, self.pattern_engine,
            self.collaboration, self.reputation, self._skills_dir,
        )

        # State
        self._loaded: dict[str, Skill] = {}
        self._active: dict[str, Skill] = {}
        self._disabled: set[str] = set()
        self._activation_history: list[dict[str, Any]] = []

        # Set embedding function for all systems
        if embedding_fn:
            self.embedding_engine.set_embedding_fn(embedding_fn)

        # Load index
        index_path = self._skills_dir / "_index" / "skill_embeddings.json"
        self.embedding_engine.set_index_path(index_path)
        self.embedding_engine.load_index()

    def _emit(self, stage: str, message: str) -> None:
        self._on_event(stage, message)

    # --- Core Operations ---

    async def load_all(self) -> dict[str, Skill]:
        """Load all installed skills."""
        self._loaded = self.loader.load_all()
        for name, skill in self._loaded.items():
            await self.embedding_engine.embed_skill(skill)
            if skill.doc_chunks and skill.manifest.rag.enabled:
                self.rag.index_skill_docs(name, skill.doc_chunks)
        return dict(self._loaded)

    def list_installed(self) -> list[Skill]:
        """List all installed skills (registered in registry)."""
        installed = []
        for name, skill in self._loaded.items():
            # Check if registered in registry
            registry_entry = self.registry.get_skill(name)
            if registry_entry:
                installed.append(skill)
        return installed

    def list_active(self) -> list[Skill]:
        """List all active (enabled and loaded) skills."""
        return list(self._active.values())

    def list_disabled(self) -> list[str]:
        """List all disabled skill names."""
        return list(self._disabled)

    def list_available(self) -> list[dict[str, str]]:
        """List all available built-in skills from the skills directory."""
        available = []
        
        # Check package's built-in skills directory
        try:
            import zerion_core
            package_skills_dir = Path(zerion_core.__file__).parent.parent / "skills"
            if package_skills_dir.exists():
                for skill_dir in package_skills_dir.iterdir():
                    if skill_dir.is_dir() and not skill_dir.name.startswith("_") and not skill_dir.name.startswith("."):
                        manifest_path = skill_dir / "skill.yaml"
                        if manifest_path.exists():
                            try:
                                import yaml
                                with open(manifest_path, "r", encoding="utf-8") as f:
                                    manifest = yaml.safe_load(f)
                                name = manifest.get("name", skill_dir.name)
                                version = manifest.get("version", "1.0.0")
                                description = manifest.get("description", "")
                                tags = manifest.get("tags", [])
                                # Check if installed in registry
                                registry_entry = self.registry.get_skill(name)
                                installed = registry_entry is not None
                                available.append({
                                    "name": name,
                                    "version": version,
                                    "description": description,
                                    "tags": tags[:3],
                                    "installed": installed,
                                })
                            except Exception:
                                pass
        except Exception:
            pass
        
        return available

    async def install(self, source: str) -> tuple[bool, str]:
        """Install a skill from a source."""
        self._emit("skill", f"Installing from {source}...")
        ok, msg = await self.installer.install(source)
        if ok:
            skill = self.loader.reload(source.split("/")[-1].split(":")[-1])
            if skill:
                self._loaded[skill.manifest.name] = skill
                await self.embedding_engine.embed_skill(skill)
                self.embedding_engine.save_index()
                self._emit("skill", f"Installed: {skill.manifest.name}")
        return ok, msg

    async def uninstall(self, name: str) -> tuple[bool, str]:
        """Uninstall a skill."""
        self._active.pop(name, None)
        self._loaded.pop(name, None)
        self._disabled.discard(name)
        self.rag.clear_skill(name)
        ok, msg = await self.installer.uninstall(name)
        self.embedding_engine.save_index()
        return ok, msg

    def enable(self, name: str) -> bool:
        """Enable a skill."""
        if name not in self._loaded:
            return False
        self._disabled.discard(name)
        self._active[name] = self._loaded[name]
        return True

    def disable(self, name: str) -> bool:
        """Disable a skill."""
        self._disabled.add(name)
        self._active.pop(name, None)
        return True

    def reload(self, name: str) -> Skill | None:
        """Hot-reload a skill."""
        skill = self.loader.reload(name)
        if skill:
            self._loaded[name] = skill
            if name in self._active:
                self._active[name] = skill
        return skill

    # --- Advanced Matching ---

    async def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.4,
    ) -> list[SkillSearchResult]:
        """Semantic search across skills."""
        available = {n: s for n, s in self._loaded.items() if n not in self._disabled}
        return await self.embedding_engine.semantic_search(query, available, top_k, min_score)

    async def find_related(
        self,
        skill_name: str,
        top_k: int = 5,
    ) -> list[SkillSearchResult]:
        """Find skills related to a given skill."""
        return await self.embedding_engine.find_related(skill_name, self._loaded, top_k)

    async def auto_activate(
        self,
        query: str,
        project_id: str = "",
    ) -> list[str]:
        """Auto-activate skills based on query, project context, and history."""
        # Get recommendations
        recommendations = await self.embedding_engine.recommend_skills(
            query=query,
            project_context=project_id,
            skills=self._loaded,
            history=self._activation_history,
            top_k=3,
        )

        activated = []
        for rec in recommendations:
            skill = self._loaded.get(rec.skill_name)
            if skill and skill.manifest.auto_activate:
                self._active[rec.skill_name] = skill
                activated.append(rec.skill_name)
                self._emit("skill", f"Auto-activated: {rec.skill_name} (score={rec.score:.2f})")

        # Predict co-activations
        if activated:
            co_predictions = self.collaboration.predict_co_activation(
                activated, list(self._loaded.keys()), top_k=2
            )
            for pred in co_predictions:
                if pred["skill_id"] not in self._active:
                    skill = self._loaded.get(pred["skill_id"])
                    if skill and skill.manifest.auto_activate:
                        self._active[pred["skill_id"]] = skill
                        activated.append(pred["skill_id"])

        return activated

    # --- Context & Prompts ---

    def build_context(
        self,
        user_request: str,
        base_system: str = "",
        session_memory: str = "",
        project_memory: str = "",
        rag_context: str = "",
        project_id: str = "",
    ) -> str:
        """Build complete context with active skills."""
        # Add skill memory context
        skill_memory_context = self._build_skill_memory_context(user_request)
        project_context = self._build_project_context(project_id)

        return self.context_builder.build_context(
            active_skills=self._active,
            base_system=base_system,
            session_memory=session_memory,
            project_memory=project_memory,
            rag_context=rag_context + skill_memory_context + project_context,
            user_request=user_request,
        )

    def _build_skill_memory_context(self, query: str) -> str:
        """Build context from skill memories."""
        parts = []
        for skill_name in self._active:
            memory_context = self.memory_system.recall_memories(
                skill_name, query=query, limit=3
            )
            if memory_context:
                formatted = "\n".join(
                    f"- [{m.get('memory_type', 'exp')}] {m.get('task', '')[:100]}"
                    for m in memory_context
                )
                parts.append(f"### {skill_name} Experience\n{formatted}")
        return "\n\n".join(parts)

    def _build_project_context(self, project_id: str) -> str:
        """Build context from project skill profiles."""
        if not project_id:
            return ""

        project_skills = self.memory_system.get_project_skills(project_id)
        if not project_skills:
            return ""

        lines = [f"### Project {project_id} Skill Profiles"]
        for ps in project_skills[:3]:
            lines.append(f"- {ps['skill_id']}: success_rate={ps['avg_score']:.2f}, "
                        f"interactions={ps['total_interactions']}")

        return "\n".join(lines)

    # --- Memory & Learning ---

    async def record_outcome(
        self,
        skill_name: str,
        task: str,
        solution: str,
        outcome: dict[str, Any],
        project_id: str = "",
        files_modified: list[str] | None = None,
    ) -> None:
        """Record outcome for a skill."""
        # Compute success score
        signals = OutcomeSignals(
            tests_passed=outcome.get("tests_passed", False),
            build_succeeded=outcome.get("build_succeeded", False),
            user_accepted=outcome.get("user_accepted", False),
            patch_retained=outcome.get("patch_retained", True),
            bug_not_reintroduced=outcome.get("bug_not_reintroduced", True),
            no_regressions=outcome.get("no_regressions", True),
        )
        score_result = self.success_scorer.compute_score(signals)

        # Record memory
        self.memory_system.record_memory(
            skill_id=skill_name,
            task=task,
            solution=solution,
            project_id=project_id,
            outcome=json.dumps(outcome),
            success_score=score_result.total,
            files_modified=files_modified,
        )

        # Record collaboration if multiple skills active
        if len(self._active) > 1:
            self.collaboration.record_activation(
                list(self._active.keys()),
                query=task,
                score=score_result.total,
                success=score_result.total >= 0.6,
            )

        # Update project profile
        if project_id:
            self.memory_system.update_project_profile(
                project_id=project_id,
                skill_id=skill_name,
                success_score=score_result.total,
            )

        # Track activation
        self._activation_history.append({
            "skill_name": skill_name,
            "task": task,
            "success": score_result.total >= 0.6,
            "score": score_result.total,
        })

        # Extract patterns periodically
        if len(self._activation_history) % 10 == 0:
            await self.pattern_engine.extract_patterns(skill_name, self._llm_fn)

    async def record_failure(
        self,
        skill_name: str,
        task: str,
        failure_type: str,
        error_description: str,
        project_id: str = "",
        attempted_solution: str = "",
        root_cause: str = "",
    ) -> None:
        """Record a failure."""
        self.memory_system.record_failure(
            skill_id=skill_name,
            task=task,
            failure_type=failure_type,
            error_description=error_description,
            project_id=project_id,
            attempted_solution=attempted_solution,
            root_cause=root_cause,
        )

        # Update activation history
        self._activation_history.append({
            "skill_name": skill_name,
            "task": task,
            "success": False,
            "score": 0.0,
        })

    # --- Evolution & Consolidation ---

    async def evolve_skill(self, skill_name: str) -> dict[str, Any]:
        """Evolve a skill based on experience."""
        return await self.evolution.evolve_skill(skill_name, self._llm_fn)

    async def consolidate_skill(self, skill_name: str) -> dict[str, Any]:
        """Consolidate skill memories."""
        return await self.consolidation.consolidate(skill_name, self._llm_fn)

    async def distill_knowledge(self, skill_name: str) -> str:
        """Distill skill knowledge into brain file."""
        return await self.distillation.distill(skill_name, self._llm_fn)

    async def run_maintenance(self) -> dict[str, Any]:
        """Run maintenance tasks on all skills."""
        results = {}
        for skill_name in self._loaded:
            try:
                # Consolidate memories
                consolidation = await self.consolidation.consolidate(skill_name)

                # Extract patterns
                patterns = await self.pattern_engine.extract_patterns(skill_name)

                # Distill knowledge
                brain = await self.distillation.distill(skill_name)

                results[skill_name] = {
                    "consolidation": consolidation,
                    "patterns": len(patterns),
                    "brain_updated": bool(brain),
                }
            except Exception as e:
                results[skill_name] = {"error": str(e)}

        return results

    # --- Queries ---

    def get_skill(self, name: str) -> Skill | None:
        return self._loaded.get(name)

    def is_active(self, name: str) -> bool:
        return name in self._active

    def search(self, query: str) -> list[Skill]:
        """Simple text search."""
        query_lower = query.lower()
        return [
            s for s in self._loaded.values()
            if query_lower in f"{s.manifest.name} {s.manifest.description}".lower()
        ]

    def get_skill_info(self, name: str) -> dict[str, Any]:
        """Get detailed skill info with advanced metrics."""
        skill = self._loaded.get(name)
        if not skill:
            return {}

        rep = self.reputation.compute_reputation(name)
        stats = self.memory_system.get_stats(name)
        collab_stats = self.collaboration.get_skill_stats(name)

        return {
            "name": skill.manifest.name,
            "version": skill.manifest.version,
            "description": skill.manifest.description,
            "author": skill.manifest.author,
            "tags": skill.manifest.tags,
            "status": skill.status.value,
            "active": name in self._active,
            "disabled": name in self._disabled,
            "reputation": rep["reputation"],
            "memory": stats,
            "collaboration": collab_stats,
            "doc_chunks": len(skill.doc_chunks),
            "has_workflow": bool(skill.manifest.workflow.steps),
            "has_rag": skill.manifest.rag.enabled,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get overall skill system stats."""
        return {
            "installed": len(self._loaded),
            "active": len(self._active),
            "disabled": len(self._disabled),
            "total_usage": sum(s.usage_count for s in self._loaded.values()),
            "total_doc_chunks": sum(len(s.doc_chunks) for s in self._loaded.values()),
            "activation_history": len(self._activation_history),
        }

    def close(self) -> None:
        """Cleanup resources."""
        self.embedding_engine.save_index()
        self.registry.close()
        self.memory_system.close()
        self.collaboration.close()
