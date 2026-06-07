"""LongTermMemory: unified interface for the entire long-term memory system.

Orchestrates:
- Episodic event storage
- Semantic vector indexing
- Importance scoring + decay
- Project brain files
- Cross-session retrieval
- Optimized context injection
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from zerion_core.llm.ollama import OllamaClient
from zerion_core.memory.longterm.context_builder import OptimizedContextBuilder
from zerion_core.memory.longterm.decay import DecayEngine
from zerion_core.memory.longterm.episodic_store import EpisodicStore, MemoryEvent
from zerion_core.memory.longterm.importance import EventType, compute_importance
from zerion_core.memory.longterm.project_memory import ProjectBrainManager
from zerion_core.memory.longterm.retrieval import CrossSessionRetriever
from zerion_core.memory.longterm.semantic_store import SemanticStore


class LongTermMemory:
    """Unified long-term memory system with episodic, semantic, and project-level intelligence.

    Usage:
        ltm = LongTermMemory(llm)

        # Record a memory event
        await ltm.record_event(
            project_id="my_app",
            event_type="bug_fix",
            content="Fixed authentication middleware null pointer in auth.py",
            files_affected=["src/auth.py"],
        )

        # Retrieve relevant memories
        results = await ltm.recall("what auth bugs did I fix?", project_id="my_app")

        # Get optimized context for LLM
        context = await ltm.get_context("my_app", "add refresh token support")

        # Update project brain
        await ltm.update_project_brain("my_app", "Decided to use JWT with refresh tokens")
    """

    def __init__(
        self,
        llm: OllamaClient,
        on_event: Callable[[str, str], None] | None = None,
    ) -> None:
        self.llm = llm
        self.on_event = on_event or (lambda _s, _m: None)

        # Core stores
        self.episodic = EpisodicStore()
        self.semantic = SemanticStore(llm)

        # Engines
        self.decay = DecayEngine(self.episodic)
        self.retriever = CrossSessionRetriever(self.episodic, self.semantic, llm)
        self.project_brain = ProjectBrainManager(llm)
        self.context_builder = OptimizedContextBuilder()

    # === Event Recording ===

    async def record_event(
        self,
        project_id: str,
        event_type: str,
        content: str,
        session_id: str = "",
        files_affected: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        user_boost: float = 1.0,
    ) -> MemoryEvent:
        """Record a memory event with automatic importance scoring and vector indexing."""
        now = datetime.now(timezone.utc).isoformat()

        # Compute importance
        importance = compute_importance(
            EventType(event_type) if event_type in EventType.__members__.values() else EventType.QUERY,
            now,
            times_accessed=0,
            user_boost=user_boost,
        )

        event = MemoryEvent(
            session_id=session_id,
            project_id=project_id,
            event_type=event_type,
            content=content,
            files_affected=files_affected or [],
            importance=importance,
            created_at=now,
            accessed_at=now,
            tags=tags or [],
            metadata=metadata or {},
        )

        # Store in episodic DB
        self.episodic.store_event(event)

        # Index in semantic vector DB
        await self.semantic.index_event(
            event_id=event.id,
            content=content,
            metadata={
                "project_id": project_id,
                "event_type": event_type,
                "importance": str(importance),
                "created_at": now,
                "session_id": session_id,
            },
        )

        self.on_event("memory", f"Recorded {event_type}: {content[:80]}")
        return event

    async def record_from_agent_output(
        self,
        project_id: str,
        agent_output: str,
        session_id: str = "",
        agent_name: str = "",
    ) -> list[MemoryEvent]:
        """Extract and record memory events from agent output.

        Uses LLM to extract meaningful events from the output.
        """
        events: list[MemoryEvent] = []

        # Heuristic extraction first
        extracted = self._heuristic_extract_events(agent_output)

        for event_data in extracted:
            event = await self.record_event(
                project_id=project_id,
                event_type=event_data["type"],
                content=event_data["content"],
                session_id=session_id,
                files_affected=event_data.get("files", []),
                metadata={"agent": agent_name},
            )
            events.append(event)

        # If heuristic found nothing meaningful, try LLM extraction
        if not events and len(agent_output) > 100:
            llm_events = await self._llm_extract_events(agent_output, project_id, session_id)
            events.extend(llm_events)

        return events

    # === Memory Retrieval ===

    async def recall(
        self,
        query: str,
        project_id: str | None = None,
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> list[RetrievalResult]:
        """Recall relevant memories across all sessions.

        Supports natural language queries:
        - "what did I do 3 days ago?"
        - "where did I fix auth bug?"
        - "what decisions did I make about RAG?"
        """
        results = await self.retriever.retrieve(
            query=query,
            project_id=project_id,
            min_importance=min_importance,
            limit=limit,
        )

        # Reinforce accessed memories
        for r in results:
            self.decay.reinforce_event(r.event.id, boost=0.02)

        return results

    async def recall_by_time(
        self,
        time_description: str,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEvent]:
        """Recall memories by time description: '3 days ago', 'last week', etc."""
        from zerion_core.memory.longterm.retrieval import parse_time_query

        time_range = parse_time_query(time_description)
        if not time_range:
            return []

        return self.episodic.search_by_time_range(
            time_range.start, time_range.end,
            project_id=project_id,
            limit=limit,
        )

    async def recall_by_type(
        self,
        event_type: str,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEvent]:
        """Recall memories by type: 'bug_fix', 'architecture_decision', etc."""
        return self.episodic.search_by_type(
            event_type, project_id=project_id, limit=limit,
        )

    async def recall_by_file(
        self,
        file_path: str,
        project_id: str | None = None,
    ) -> list[MemoryEvent]:
        """Recall all memories related to a specific file."""
        return self.episodic.search_by_files(file_path, project_id=project_id)

    # === Context Building ===

    async def get_context(
        self,
        project_id: str,
        user_request: str = "",
        rag_context: str = "",
        session_summary: str = "",
        max_tokens: int = 2000,
    ) -> str:
        """Get optimized long-term memory context for LLM injection.

        Applies TurboQuant-inspired compression:
        - Clusters similar memories
        - Deduplicates
        - Prioritizes by importance
        - Enforces token budget
        """
        # 1. Retrieve relevant memories
        results = await self.retriever.retrieve(
            query=user_request or "recent activity",
            project_id=project_id,
            limit=12,
        )

        # 2. Get project brain
        brain_context = self.project_brain.get_context(project_id)

        # 3. Build optimized context
        return self.context_builder.build_context(
            retrieval_results=results,
            project_brain=brain_context,
            session_summary=session_summary,
            user_request=user_request,
            rag_context=rag_context,
        )

    # === Project Brain ===

    async def update_project_brain(
        self,
        project_id: str,
        agent_output: str,
        context: str = "",
    ) -> None:
        """Update project brain from agent output."""
        await self.project_brain.update_from_output(project_id, agent_output, context)

    def get_project_brain(self, project_id: str) -> str:
        """Get the project brain formatted for context."""
        return self.project_brain.get_context(project_id)

    # === Maintenance ===

    def run_decay(self) -> dict[str, int]:
        """Run importance decay across all memories."""
        return self.decay.run_decay()

    def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        return {
            "episodic_events": self.episodic.count_events(),
            "semantic_vectors": self.semantic.count(),
            "decay_stats": self.decay.get_decay_stats(),
            "project_brains": len(self.project_brain.store.list_brains()),
        }

    # === Internal Helpers ===

    def _heuristic_extract_events(self, text: str) -> list[dict[str, Any]]:
        """Fast heuristic event extraction from agent output."""
        events: list[dict[str, Any]] = []
        lower = text.lower()

        # Bug fixes
        if any(w in lower for w in ("fixed:", "bug:", "fix:", "resolved:")):
            events.append({"type": "bug_fix", "content": text[:300]})

        # Architecture decisions
        if any(w in lower for w in ("decided:", "decision:", "chose:", "architecture:")):
            events.append({"type": "architecture_decision", "content": text[:300]})

        # Features
        if any(w in lower for w in ("implemented:", "created:", "added:", "feature:")):
            events.append({"type": "feature_implemented", "content": text[:300]})

        # Refactoring
        if any(w in lower for w in ("refactored:", "restructured:", "reorganized:")):
            events.append({"type": "refactor", "content": text[:300]})

        # Lessons
        if any(w in lower for w in ("lesson:", "learned:", "note:", "important:")):
            events.append({"type": "lesson_learned", "content": text[:300]})

        # Extract file paths
        import re
        files = re.findall(r"(?:src/|lib/|app/|[\w/]+\.\w+)", text)

        if events:
            events[0]["files"] = files[:5]

        return events

    async def _llm_extract_events(
        self,
        text: str,
        project_id: str,
        session_id: str,
    ) -> list[MemoryEvent]:
        """Use LLM to extract meaningful events from text."""
        from zerion_core.llm.model_router import ModelRouter
        import json

        extract_prompt = """Extract meaningful memory events from this text.
Return JSON array:
[{"event_type": "bug_fix|feature_implemented|architecture_decision|lesson_learned|refactor|pattern_identified",
   "content": "concise summary of the event",
   "files_affected": ["file.py"]}]

Only extract genuinely important events. Return empty array if nothing noteworthy.
Rules:
- event_type must be one of the listed types
- content should be concise (under 200 chars)
- files_affected should list actual file paths mentioned"""

        try:
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": f"Text:\n{text[:3000]}"}],
                model=ModelRouter.for_task("memory_extraction"),
                system=extract_prompt,
                json_mode=True,
                temperature=0.0,
            )
            extracted = json.loads(resp.content)
            if not isinstance(extracted, list):
                return []

            events: list[MemoryEvent] = []
            for item in extracted:
                if not isinstance(item, dict):
                    continue
                event_type = item.get("event_type", "lesson_learned")
                content = item.get("content", "")
                if not content:
                    continue

                event = await self.record_event(
                    project_id=project_id,
                    event_type=event_type,
                    content=content,
                    session_id=session_id,
                    files_affected=item.get("files_affected", []),
                )
                events.append(event)

            return events
        except (json.JSONDecodeError, Exception):
            return []
