from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from zerion_core.config import settings
from zerion_core.llm.ollama import OllamaClient
from zerion_core.llm.model_router import ModelRouter
from zerion_core.memory.fact_extractor import FactExtractor
from zerion_core.memory.graph import Neo4jGraph, TemporalGraph
from zerion_core.memory.models import (
    EpisodicEntry,
    FileInfo,
    JsonStore,
    MethodInfo,
    ClassInfo,
    ProceduralEntry,
    ProjectRegistryEntry,
    ProjectStructureSnapshot,
    SemanticFact,
    ShortTermMemory,
    TemporalChange,
    _utcnow,
    coerce_str,
)
from zerion_core.memory.repository import RepositoryMemory
from zerion_core.memory.retrieval import HybridRetriever
from zerion_core.memory.working_memory import WorkingMemory

PROJECT_DETECTION_PROMPT = """Analyze the user request and determine project information.
Return JSON only:
{
  "project_name": "short_snake_case_name_or_empty",
  "description": "one-line summary",
  "tech_stack": ["technology1", "technology2"],
  "is_new_project": true/false,
  "confidence": 0.0-1.0
}
Rules:
- project_name: use empty string if not a software project (chat, question)
- is_new_project: true only if confidence is high that this is a NEW project
- tech_stack: list technologies mentioned (django, react, python, etc.)
- Extract from both explicit mentions and implicit clues
"""


class MemoryManager:
    """Unified interface for all four memory layers plus multi-project RAG."""

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm
        self.stm_store = JsonStore(settings.stm_dir, "current.json")
        self.episodic_store = JsonStore(settings.episodic_dir, "projects.json")
        self.semantic_store = JsonStore(settings.semantic_dir, "facts.json")
        self.procedural_store = JsonStore(settings.procedural_dir, "procedures.json")
        self.project_registry = JsonStore(settings.memory_root, "project_registry.json")
        self.graph = TemporalGraph()
        self.neo4j = Neo4jGraph()
        self.working = WorkingMemory()
        self.repository = RepositoryMemory()
        self.extractor = FactExtractor(llm)
        self.retriever = HybridRetriever(llm, self.graph)

    # =========================================================
    #  Multi-Project Registry & Smart Detection
    # =========================================================

    def _get_registered_projects(self) -> dict[str, ProjectRegistryEntry]:
        raw = self.project_registry.get("projects", {})
        return {k: ProjectRegistryEntry(**v) for k, v in raw.items()}

    def _save_registered_projects(self, projects: dict[str, ProjectRegistryEntry]) -> None:
        self.project_registry.set(
            "projects",
            {k: v.model_dump() for k, v in projects.items()},
        )

    def get_all_projects(self) -> list[ProjectRegistryEntry]:
        return list(self._get_registered_projects().values())

    def get_project(self, name: str) -> ProjectRegistryEntry | None:
        return self._get_registered_projects().get(name)

    async def build_project_snapshot(self, name: str, root: Path | None = None) -> ProjectStructureSnapshot:
        """Deep-scan the project and index the result in RAG."""
        from zerion_core.tools.project_map import deep_scan_project, format_rich_snapshot

        raw = deep_scan_project(root)
        snapshot = ProjectStructureSnapshot(**raw)

        # Index in vector store for RAG retrieval
        # 1. Index the project overview
        overview = (
            f"Project: {name}\n"
            f"Path: {snapshot.project_path}\n"
            f"Technologies: {', '.join(snapshot.technologies)}\n"
            f"Description: {snapshot.description}\n"
        )
        await self.retriever.index(
            overview,
            source="project_overview",
            metadata={"project": name, "type": "overview", "kind": "project_structure"},
        )

        # 2. Index per-file detail
        for fi in snapshot.files:
            file_text_parts = [f"File: {fi.path} ({fi.type})"]
            for cls in fi.classes:
                file_text_parts.append(f"  Class: {cls.name}")
                for m in cls.methods:
                    params = ", ".join(m.params)
                    file_text_parts.append(f"    Method: {m.name}({params}) line {m.line_number}")
                    if m.docstring:
                        file_text_parts.append(f"      {m.docstring[:200]}")
            for fn in fi.functions:
                params = ", ".join(fn.params)
                file_text_parts.append(f"  Function: {fn.name}({params}) line {fn.line_number}")
            if fi.imports:
                file_text_parts.append(f"  Imports: {', '.join(fi.imports[:10])}")

            await self.retriever.index(
                "\n".join(file_text_parts),
                source="file_detail",
                metadata={
                    "project": name,
                    "file_path": fi.path,
                    "type": "file_structure",
                    "kind": "project_structure",
                    "tech": fi.type,
                },
            )

        # 3. Build a rich text block and store in working memory
        rich = format_rich_snapshot(raw)
        self.working.set(f"deep_structure:{name}", rich)

        # 4. Store in graph
        self.graph.upsert_node(
            f"project_structure:{name}",
            {
                "project": name,
                "tech": ",".join(snapshot.technologies),
                "file_count": len(snapshot.files),
                "description": snapshot.description[:200],
            },
            reason="deep_scan",
        )

        return snapshot

    async def register_project(
        self,
        name: str,
        description: str = "",
        tech_stack: list[str] | None = None,
        deep_scan: bool = True,
    ) -> ProjectRegistryEntry:
        projects = self._get_registered_projects()
        now = _utcnow()
        if name in projects:
            entry = projects[name]
            entry.description = description or entry.description
            if tech_stack:
                existing = set(entry.tech_stack)
                entry.tech_stack = list(existing | set(tech_stack))
            entry.updated_at = now
        else:
            entry = ProjectRegistryEntry(
                name=name,
                description=description,
                tech_stack=tech_stack or [],
                created_at=now,
                updated_at=now,
            )

        # Deep-scan the workspace and build the structured snapshot
        if deep_scan:
            snapshot = await self.build_project_snapshot(name)
            entry.snapshot = snapshot
            # merge detected technologies with what was provided
            for t in snapshot.technologies:
                if t not in entry.tech_stack:
                    entry.tech_stack.append(t)
            if not entry.description and snapshot.description:
                entry.description = snapshot.description

        # index in vector store for project similarity search
        await self.retriever.index_project(name, entry.description, entry.tech_stack)
        # store embedding
        text_for_embed = (
            f"Project: {name}\n"
            f"Description: {entry.description}\n"
            f"Tech Stack: {', '.join(entry.tech_stack)}\n"
        )
        entry.embedding = await self.llm.embed(text_for_embed)
        projects[name] = entry
        self._save_registered_projects(projects)

        # also add to graph
        self.graph.upsert_node(
            f"project:{name}",
            {
                "name": name,
                "description": entry.description[:200],
                "tech": ",".join(entry.tech_stack),
                "files": str(len(entry.snapshot.files)) if entry.snapshot else "0",
            },
            reason="project_registered",
        )
        return entry

    async def detect_project(self, request: str) -> dict[str, Any]:
        """Detect if request relates to an existing project or a new one."""
        # 1. LLM-based extraction
        try:
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": f"Request: {request}"}],
                model=ModelRouter.for_task("memory_extraction"),
                system=PROJECT_DETECTION_PROMPT,
                json_mode=True,
                temperature=0.0,
            )
            info = json.loads(resp.content)
        except (json.JSONDecodeError, Exception):
            info = {"project_name": "", "description": "", "tech_stack": [], "is_new_project": False, "confidence": 0.0}

        project_name = info.get("project_name", "")
        is_new = info.get("is_new_project", False)
        confidence = info.get("confidence", 0.0)

        # 2. Check registry for exact name match
        registered = self._get_registered_projects()
        if project_name and project_name in registered:
            return {
                "project": registered[project_name],
                "project_name": project_name,
                "status": "existing",
                "confidence": 1.0,
                "is_new": False,
                "description": info.get("description", ""),
                "tech_stack": info.get("tech_stack", []),
            }

        # 3. Vector similarity search against known projects
        similar = await self.retriever.search_similar_projects(request, limit=3)
        high_sim = [s for s in similar if s.get("similarity", 0) >= 0.65]

        if high_sim:
            best = high_sim[0]
            best_name = best["project"]
            if best_name in registered:
                return {
                    "project": registered[best_name],
                    "project_name": best_name,
                    "status": "existing",
                    "confidence": best["similarity"],
                    "is_new": False,
                    "description": info.get("description", ""),
                    "tech_stack": info.get("tech_stack", []),
                    "similar_projects": high_sim,
                }

        # 4. Check if this is clearly a new project based on LLM signal
        if project_name and (is_new or confidence >= 0.7):
            entry = await self.register_project(
                name=project_name,
                description=info.get("description", request[:200]),
                tech_stack=info.get("tech_stack", []),
            )
            # also find cross-project patterns
            cross = await self._find_cross_project_patterns(request, entry)
            return {
                "project": entry,
                "project_name": project_name,
                "status": "new",
                "confidence": confidence,
                "is_new": True,
                "description": info.get("description", ""),
                "tech_stack": info.get("tech_stack", []),
                "cross_project_insights": cross,
            }

        # 5. No project detected (chat, question, etc.)
        return {
            "project": None,
            "project_name": "",
            "status": "none",
            "confidence": 0.0,
            "is_new": False,
            "description": info.get("description", ""),
            "tech_stack": info.get("tech_stack", []),
        }

    async def _find_cross_project_patterns(
        self, request: str, new_project: ProjectRegistryEntry
    ) -> list[dict[str, Any]]:
        """Find relevant patterns and decisions from existing projects for a new project."""
        results = []

        # Search for patterns from other projects
        known = self._get_registered_projects()
        if len(known) <= 1:
            return results

        hits = await self.retriever.search(
            f"{request} pattern decision architecture {' '.join(new_project.tech_stack)}",
            limit=6,
        )

        for h in hits:
            meta_project = h.metadata.get("project", "")
            if meta_project and meta_project != new_project.name:
                results.append({
                    "from_project": meta_project,
                    "content": h.content[:300],
                    "source": h.source,
                    "score": h.score,
                })

        # also fetch lessons from most similar projects
        similar = await self.retriever.search_similar_projects(request, limit=2)
        for s in similar:
            pname = s["project"]
            if pname != new_project.name:
                ep = self.get_episodic(pname)
                if ep.lessons:
                    results.append({
                        "from_project": pname,
                        "content": "Lessons from " + pname + ": " + "; ".join(ep.lessons[-3:]),
                        "source": "episodic",
                        "score": s.get("similarity", 0.5) * 0.8,
                    })

        return sorted(results, key=lambda r: r["score"], reverse=True)[:5]

    def increment_project_memory_count(self, project: str) -> None:
        projects = self._get_registered_projects()
        if project in projects:
            projects[project].memory_count += 1
            projects[project].updated_at = _utcnow()
            self._save_registered_projects(projects)

    # --- Short Term ---
    def get_stm(self) -> ShortTermMemory:
        data = self.stm_store.get("active", {})
        if not data:
            return ShortTermMemory()
        stm = ShortTermMemory(**data)
        stm.metadata.mark_access()
        self.stm_store.set("active", stm.model_dump())
        return stm

    def set_stm(self, goal: str = "", current_task: str = "", context: str = "") -> ShortTermMemory:
        stm = ShortTermMemory(goal=goal, current_task=current_task, context=context)
        self.stm_store.set("active", stm.model_dump())
        return stm

    def update_stm(self, **kwargs: str) -> ShortTermMemory:
        stm = self.get_stm()
        data = stm.model_dump()
        data.update(kwargs)
        updated = ShortTermMemory(**data)
        updated.metadata.mark_access()
        self.stm_store.set("active", updated.model_dump())
        return updated

    # --- Episodic ---
    def get_episodic(self, project: str) -> EpisodicEntry:
        raw = dict(self.episodic_store.get(project, {}))
        raw.pop("project", None)
        entry = EpisodicEntry(project=project, **raw)
        entry.metadata.mark_access()
        self.save_episodic(entry)
        return entry

    def save_episodic(self, entry: EpisodicEntry) -> None:
        self.episodic_store.set(entry.project, entry.model_dump())

    def record_task_complete(self, project: str, task: str) -> None:
        entry = self.get_episodic(project)
        entry.completed_tasks.append(task)
        self.save_episodic(entry)
        self.graph.upsert_node(f"project:{project}", {"name": project, "last_task": task})
        self.increment_project_memory_count(project)

    def record_failure(self, project: str, failure: str) -> None:
        entry = self.get_episodic(project)
        entry.failures.append(failure)
        self.save_episodic(entry)

    def record_lesson(self, project: str, lesson: str) -> None:
        entry = self.get_episodic(project)
        entry.lessons.append(lesson)
        self.save_episodic(entry)
        self.repository.add_pattern(lesson, tags=[project])
        self.increment_project_memory_count(project)

    # --- Semantic ---
    def get_semantic_facts(self) -> list[SemanticFact]:
        raw = self.semantic_store.get("facts", [])
        return [SemanticFact(**f) for f in raw]

    def upsert_semantic(self, key: str, value: str, confidence: float = 1.0, source: str = "agent", importance: float = 0.5) -> None:
        facts = self.get_semantic_facts()
        updated = False
        for f in facts:
            if f.key == key:
                f.value = value
                f.confidence = confidence
                f.source = source
                f.metadata.importance = max(f.metadata.importance, importance)
                f.metadata.mark_access()
                updated = True
                break
        if not updated:
            fact = SemanticFact(key=key, value=value, confidence=confidence, source=source)
            fact.metadata.importance = importance
            facts.append(fact)
        self.semantic_store.set("facts", [f.model_dump() for f in facts])
        self.graph.upsert_node(f"fact:{key}", {"key": key, "value": value}, reason="semantic_update")
        if self.neo4j.available:
            self.neo4j.upsert_fact("preferences", key, value)

    # --- Decay Logic ---
    def decay_memories(self, threshold: float = 0.1) -> int:
        """Archive low-value memories based on importance, recency, and usage."""
        archived_count = 0
        now = datetime.now(timezone.utc)

        # Decay Semantic Facts
        facts = self.get_semantic_facts()
        kept_facts = []
        for f in facts:
            score = self._calculate_score(f.metadata, now)
            if score >= threshold:
                kept_facts.append(f)
            else:
                archived_count += 1
        self.semantic_store.set("facts", [f.model_dump() for f in kept_facts])

        return archived_count

    def _calculate_score(self, meta: Any, now: datetime) -> float:
        """Calculate memory survival score with complexity-aware heuristics.

        Improvements over naive linear scoring:
        - Importance ceiling boost: memories with importance > 0.8 get extra protection
        - Freshness cliff: very recent memories (< 2h) get a bonus, old memories (> 7d) get
          penalized more aggressively via a non-linear decay curve
        - Usage momentum: memories used recently (last 24h) get boosted usage weight
        - Domain relevance: higher-importance memories are less susceptible to decay
        """
        last = datetime.fromisoformat(meta.last_accessed)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        hours_since = (now - last).total_seconds() / 3600

        # --- Recency (non-linear) ---
        # Freshness cliff: boost for < 2h, steep decay after 7 days
        if hours_since < 2:
            recency = 1.0 + 0.15 * (1.0 - hours_since / 2.0)  # up to +15% bonus
        elif hours_since < 24:
            recency = 1.0 / (1.0 + (hours_since / 24.0))
        elif hours_since < 168:  # 7 days
            # Steeper decay for the first week
            recency = 0.5 / (1.0 + ((hours_since - 24) / 48.0))
        else:
            # Very old: floor at 0.05 with exponential tail
            recency = max(0.05, 0.3 * (0.9 ** ((hours_since - 168) / 168.0)))

        # --- Usage (momentum-aware) ---
        # If the memory was used recently (< 24h), boost usage weight
        recent_usage_boost = 1.0
        if hours_since < 24:
            recent_usage_boost = 1.3  # 30% bonus for recently used memories

        base_usage = min(1.0, meta.times_used / 10.0)
        usage = min(1.0, base_usage * recent_usage_boost)

        # --- Importance (ceiling boost) ---
        # Very important memories (> 0.8) get a 20% bonus and resist decay better
        importance = meta.importance
        if importance > 0.8:
            importance = min(1.0, importance * 1.2)
            # High-importance memories decay 30% slower
            recency = max(recency, recency * 0.7 + 0.3 * recency)

        # --- Weighted combination ---
        # Shift weights toward importance for high-value memories
        if meta.importance > 0.8:
            # 50% importance, 30% recency, 20% usage
            return (importance * 0.5) + (recency * 0.3) + (usage * 0.2)
        elif meta.importance > 0.5:
            # 40% importance, 40% recency, 20% usage (default)
            return (importance * 0.4) + (recency * 0.4) + (usage * 0.2)
        else:
            # Low-importance: rely more on recency and usage
            # 25% importance, 45% recency, 30% usage
            return (importance * 0.25) + (recency * 0.45) + (usage * 0.3)

    # --- Procedural ---
    def get_procedures(self) -> list[ProceduralEntry]:
        raw = self.procedural_store.get("entries", [])
        return [ProceduralEntry(**e) for e in raw]

    def save_procedure(self, entry: ProceduralEntry) -> None:
        entries = self.get_procedures()
        entries = [e for e in entries if e.name != entry.name]
        entries.append(entry)
        self.procedural_store.set("entries", [e.model_dump() for e in entries])

    # --- Smart write from agent output ---
    async def ingest_agent_output(
        self,
        text: str,
        project: str,
        agent: str,
        task_type: str = "",
    ) -> dict[str, Any]:
        extracted = await self.extractor.extract(text, context=f"{project}/{agent}/{task_type}")
        if extracted.get("ignore"):
            return extracted

        for fact in extracted.get("facts", []):
            key = coerce_str(fact.get("key", "fact"))
            value = coerce_str(fact.get("value", ""))
            if not value:
                continue
            self.upsert_semantic(key, value, fact.get("confidence", 0.8), source=agent)
            await self.retriever.index(
                f"{key}: {value}",
                source="semantic",
                metadata={"project": project, "agent": agent},
            )

        for decision in extracted.get("decisions", []):
            decision_text = coerce_str(decision)
            if not decision_text:
                continue
            self.repository.add_decision(decision_text, project)
            await self.retriever.index(decision_text, source="decision", metadata={"project": project})

        for pref in extracted.get("preferences", []):
            if isinstance(pref, dict):
                self.upsert_semantic(
                    coerce_str(pref.get("key", "preference")),
                    coerce_str(pref.get("value", "")),
                    source=agent,
                )

        for pattern in extracted.get("patterns", []):
            pattern_text = coerce_str(pattern)
            if not pattern_text:
                continue
            self.record_lesson(project, pattern_text)
            await self.retriever.index(pattern_text, source="procedural", metadata={"project": project})

        if project:
            self.increment_project_memory_count(project)

        return extracted

    async def retrieve_context(self, query: str, project: str = "", depth: str = "deep") -> str:
        blocks: list[str] = []

        if depth == "shallow":
            stm = self.get_stm()
            if stm.goal or stm.current_task:
                blocks.append(f"## Current Task\nGoal: {stm.goal}\nTask: {stm.current_task}")

            project_map = self.working.get("project_structure")
            if project_map:
                blocks.append(project_map)

            return "\n\n".join(b for b in blocks if b)

        # depth == "deep" — project-aware retrieval with complexity-adaptive limits
        # Estimate task complexity from query length and technical term density
        words = query.lower().split()
        complexity_hint = min(1.0, len(words) / 20.0)  # 0.0 (simple) to 1.0 (complex)
        tech_density = sum(1 for w in words if len(w) > 6) / max(len(words), 1)
        effective_complexity = (complexity_hint + tech_density) / 2.0

        # For moderately complex tasks, retrieve more results
        base_limit = 8
        if effective_complexity > 0.4:
            retrieval_limit = min(15, base_limit + int(effective_complexity * 10))
        else:
            retrieval_limit = base_limit

        hits = await self.retriever.search(query, limit=retrieval_limit, project_filter=project if project else None)
        blocks.append(self.retriever.format_context(hits))

        # cross-project insights for known projects
        if project:
            registered = self._get_registered_projects()
            if project in registered:
                entry = registered[project]
                if entry.tech_stack:
                    cross_hits = await self.retriever.search(
                        f"{query} {' '.join(entry.tech_stack)}",
                        limit=4,
                        project_filter=None,
                    )
                    cross_filtered = [
                        h for h in cross_hits
                        if h.metadata.get("project", "") and h.metadata["project"] != project
                    ]
                    if cross_filtered:
                        blocks.append(
                            "## Cross-Project Insights\n"
                            + "\n".join(
                                f"- [{h.metadata['project']} score={h.score:.2f}] {h.content[:250]}"
                                for h in cross_filtered[:3]
                            )
                        )

        stm = self.get_stm()
        if stm.goal or stm.current_task:
            blocks.append(f"## Current Task\nGoal: {stm.goal}\nTask: {stm.current_task}")

        wm = self.working.context_block()
        if wm:
            blocks.append(wm)

        project_map = self.working.get("project_structure")
        if project_map:
            blocks.append(project_map)

        if project:
            ep = self.get_episodic(project)
            if ep.lessons:
                blocks.append("## Project Lessons\n" + "\n".join(f"- {l}" for l in ep.lessons[-5:]))

        facts = self.get_semantic_facts()
        if facts:
            blocks.append("## Known Facts\n" + "\n".join(f"- {f.key}: {f.value}" for f in facts[:10]))

        return "\n\n".join(b for b in blocks if b)

    def refresh_project_structure(self) -> str:
        from zerion_core.tools.project_map import (
            deep_scan_project,
            format_project_context,
            format_rich_snapshot,
            save_snapshot,
            scan_workspace,
        )

        # Basic tree scan
        snapshot = scan_workspace()
        save_snapshot(snapshot)
        text = format_project_context(snapshot)
        self.working.set("project_structure", text)
        self.graph.upsert_node(
            "workspace:structure",
            {"dirs": ",".join(snapshot["dirs"][:50]), "files": str(snapshot["file_count"])},
            reason="structure_scan",
        )

        # Deep class/method/tech scan
        try:
            deep = deep_scan_project()
            rich = format_rich_snapshot(deep)
            self.working.set("project_structure_deep", rich)

            # index tech summary into RAG
            import asyncio
            overview = (
                f"Technologies: {', '.join(deep['technologies'])}\n"
                f"Description: {deep['description']}\n"
                f"Files: {len(deep['files'])} source files scanned\n"
            )
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.retriever.index(
                        overview,
                        source="workspace_overview",
                        metadata={
                            "project": "workspace",
                            "type": "overview",
                            "kind": "project_structure",
                        },
                    )
                )
            except RuntimeError:
                pass
        except Exception:
            pass

        return text

    def close(self) -> None:
        self.neo4j.close()
