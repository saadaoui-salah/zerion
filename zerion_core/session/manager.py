"""Session manager: orchestrates all session subsystems."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from zerion_core.llm.ollama import OllamaClient
from zerion_core.session.context_builder import ContextBuilder
from zerion_core.session.memory import ProjectMemoryManager
from zerion_core.session.models import (
    Message,
    MessageRole,
    ProjectMemory,
    SessionData,
    SessionMeta,
    SessionSearchResult,
    SessionState,
    ToolEvent,
    _utcnow,
)
from zerion_core.session.search import SessionSearcher
from zerion_core.session.state_tracker import StateTracker, track_tool_call
from zerion_core.session.store import SessionStore
from zerion_core.session.summarizer import SessionSummarizer


class SessionManager:
    """High-level session management: create, resume, summarize, search."""

    def __init__(
        self,
        llm: OllamaClient | None = None,
        on_event: Callable[[str, str], None] | None = None,
    ) -> None:
        self.store = SessionStore()
        self.llm = llm or OllamaClient()
        self.on_event = on_event or (lambda _s, _m: None)

        self.summarizer = SessionSummarizer(self.llm)
        self.context_builder = ContextBuilder(self.summarizer)
        self.project_memory = ProjectMemoryManager(self.store, self.llm)
        self.searcher = SessionSearcher(self.store, self.llm)

        self._active_session_id: str | None = None
        self._state_tracker: StateTracker | None = None
        self._conversation: list[Message] = []

    # --- Session Lifecycle ---

    async def create_session(
        self,
        project_id: str = "",
        title: str = "",
        tags: list[str] | None = None,
    ) -> SessionData:
        """Create a new session."""
        meta = SessionMeta(
            project_id=project_id,
            title=title,
            tags=tags or [],
        )
        self.store.create_session(meta)
        self._active_session_id = meta.id
        self._state_tracker = StateTracker(meta.id)
        self._conversation = []

        self.on_event("session", f"Created session: {meta.id}")
        return SessionData(meta=meta)

    async def resume_session(self, session_id: str) -> SessionData | None:
        """Resume an existing session, restoring all state."""
        data = self.store.load_full_session(session_id)
        if not data:
            return None

        self._active_session_id = session_id
        self._state_tracker = StateTracker(session_id, data.state)
        self._conversation = data.messages

        self.on_event("session", f"Resumed session: {session_id} ({len(data.messages)} messages)")
        return data

    async def save_session(self) -> SessionMeta | None:
        """Save the current session state."""
        if not self._active_session_id:
            return None

        meta = self.store.get_session_meta(self._active_session_id)
        if not meta:
            return None

        meta.updated_at = _utcnow()
        meta.message_count = len(self._conversation)
        meta.total_tokens = sum(m.token_count for m in self._conversation)

        # Auto-generate title if empty
        if not meta.title and self._conversation:
            meta.title = await self.summarizer.generate_title(self._conversation)

        self.store.update_session_meta(meta)

        # Save messages
        if self._conversation:
            self.store.add_messages(self._active_session_id, self._conversation)

        # Save state
        if self._state_tracker:
            self.store.save_state(self._active_session_id, self._state_tracker.get_state_snapshot())
            # Save tool events
            events = self._state_tracker.get_recent_events()
            if events:
                self.store.add_tool_events(self._active_session_id, events)

        # Update summary if needed
        if self.summarizer.should_summarize(len(self._conversation)):
            await self._update_summary()

        self.on_event("session", f"Saved session: {meta.id}")
        return meta

    async def close_session(self) -> None:
        """Save and close the current session."""
        await self.save_session()
        self._active_session_id = None
        self._state_tracker = None
        self._conversation = []

    def list_sessions(self, project_id: str | None = None) -> list[SessionMeta]:
        return self.store.list_sessions(project_id=project_id)

    def delete_session(self, session_id: str) -> bool:
        return self.store.delete_session(session_id)

    def rename_session(self, session_id: str, new_title: str) -> bool:
        meta = self.store.get_session_meta(session_id)
        if not meta:
            return False
        meta.title = new_title
        meta.updated_at = _utcnow()
        self.store.update_session_meta(meta)
        return True

    # --- Message Management ---

    def add_message(
        self,
        role: MessageRole,
        content: str,
        token_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        msg = Message(
            role=role,
            content=content,
            token_count=token_count,
            metadata=metadata or {},
        )
        self._conversation.append(msg)

        # Auto-save periodically
        if len(self._conversation) % 10 == 0 and self._active_session_id:
            self.store.add_messages(self._active_session_id, [msg])

        return msg

    def add_user_message(self, content: str) -> Message:
        return self.add_message(MessageRole.USER, content)

    def add_assistant_message(self, content: str, token_count: int = 0) -> Message:
        return self.add_message(MessageRole.ASSISTANT, content, token_count)

    def add_system_message(self, content: str) -> Message:
        return self.add_message(MessageRole.SYSTEM, content)

    def get_conversation(self) -> list[Message]:
        return list(self._conversation)

    def get_messages_raw(self) -> list[dict[str, str]]:
        return [{"role": m.role.value, "content": m.content} for m in self._conversation]

    # --- Tool Tracking ---

    def track_tool(
        self,
        tool_name: str,
        target: str,
        success: bool = True,
        summary: str = "",
        error: str = "",
        diff_preview: str = "",
        duration_ms: float = 0.0,
    ) -> ToolEvent:
        if not self._state_tracker:
            self._state_tracker = StateTracker(self._active_session_id or "unknown")
        return track_tool_call(
            self._state_tracker, tool_name, target, success,
            summary, error, diff_preview, duration_ms,
        )

    def get_state_tracker(self) -> StateTracker | None:
        return self._state_tracker

    # --- Context Building ---

    def build_context(
        self,
        system_prompt: str = "",
        rag_context: str = "",
        project_id: str = "",
        user_request: str = "",
    ) -> list[dict[str, str]]:
        """Build the full context for an LLM call."""
        summary = ""
        if self._active_session_id:
            summary = self.store.get_summary(self._active_session_id)

        project_mem_text = ""
        if project_id:
            project_mem_text = self.project_memory.format_for_context(project_id)

        state = self._state_tracker.get_state_snapshot() if self._state_tracker else None

        return self.context_builder.build(
            summary=summary,
            messages=self._conversation,
            system_prompt=system_prompt,
            rag_context=rag_context,
            project_memory=project_mem_text,
            state=state,
            user_request=user_request,
        )

    async def build_context_async(
        self,
        system_prompt: str = "",
        rag_context: str = "",
        project_id: str = "",
        user_request: str = "",
    ) -> list[dict[str, str]]:
        """Build context with updated summary (async)."""
        summary = ""
        if self._active_session_id:
            summary = self.store.get_summary(self._active_session_id)

        # Update summary if needed
        if self.summarizer.should_summarize(len(self._conversation)):
            summary = await self.summarizer.summarize_messages(
                summary, self._conversation,
                self._state_tracker.get_recent_events() if self._state_tracker else None,
            )
            if self._active_session_id:
                self.store.save_summary(self._active_session_id, summary)

        project_mem_text = ""
        if project_id:
            project_mem_text = self.project_memory.format_for_context(project_id)

        state = self._state_tracker.get_state_snapshot() if self._state_tracker else None

        return self.context_builder.build(
            summary=summary,
            messages=self._conversation,
            system_prompt=system_prompt,
            rag_context=rag_context,
            project_memory=project_mem_text,
            state=state,
            user_request=user_request,
        )

    # --- Summarization ---

    async def _update_summary(self) -> None:
        if not self._active_session_id:
            return
        old_summary = self.store.get_summary(self._active_session_id)
        new_summary = await self.summarizer.summarize_messages(
            old_summary, self._conversation,
            self._state_tracker.get_recent_events() if self._state_tracker else None,
        )
        self.store.save_summary(self._active_session_id, new_summary)

        # Update session meta
        meta = self.store.get_session_meta(self._active_session_id)
        if meta:
            meta.summary = new_summary[:500]
            meta.updated_at = _utcnow()
            self.store.update_session_meta(meta)

    # --- Search ---

    def search(self, query: str, project_id: str | None = None) -> list[SessionSearchResult]:
        return self.searcher.keyword_search(query, project_id)

    async def semantic_search(self, query: str, project_id: str | None = None) -> list[SessionSearchResult]:
        return await self.searcher.semantic_search(query, project_id)

    def get_timeline(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return self.searcher.get_session_timeline(project_id)

    # --- Branching ---

    async def branch_session(self, from_session_id: str, at_message_index: int) -> SessionData:
        """Create a branch from an existing session at a specific message."""
        original = self.store.load_full_session(from_session_id)
        if not original:
            raise FileNotFoundError(f"Session {from_session_id} not found")

        # Create new session with branch metadata
        meta = SessionMeta(
            project_id=original.meta.project_id,
            title=f"Branch of {original.meta.title}",
            is_branch=True,
            branch_parent_id=from_session_id,
            tags=original.meta.tags + ["branch"],
        )
        self.store.create_session(meta)

        # Copy messages up to the branch point
        branch_messages = original.messages[:at_message_index]
        if branch_messages:
            self.store.add_messages(meta.id, branch_messages)

        # Copy state
        self.store.save_state(meta.id, original.state)

        # Set as active
        self._active_session_id = meta.id
        self._state_tracker = StateTracker(meta.id, original.state)
        self._conversation = branch_messages

        return SessionData(meta=meta, messages=branch_messages, state=original.state)

    # --- Export/Import ---

    def export_session(self, session_id: str) -> dict[str, Any] | None:
        """Export a session as a JSON-serializable dict."""
        data = self.store.load_full_session(session_id)
        if not data:
            return None
        return data.model_dump()

    def import_session(self, data: dict[str, Any]) -> SessionMeta | None:
        """Import a session from a dict."""
        try:
            session_data = SessionData(**data)
            session_data.meta.id = SessionMeta().id  # new ID
            session_data.meta.updated_at = _utcnow()
            self.store.save_full_session(session_data)
            return session_data.meta
        except Exception:
            return None

    def export_session_file(self, session_id: str, path: Path) -> bool:
        """Export a session to a JSON file."""
        data = self.export_session(session_id)
        if not data:
            return False
        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except OSError:
            return False

    def import_session_file(self, path: Path) -> SessionMeta | None:
        """Import a session from a JSON file."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return self.import_session(data)
        except (json.JSONDecodeError, OSError):
            return None

    # --- Event Detection ---

    def detect_important_events(self) -> list[dict[str, str]]:
        """Scan recent messages for important events (bugs, decisions, errors)."""
        events: list[dict[str, str]] = []
        recent = self._conversation[-20:]

        keywords = {
            "bug": ["bug", "error", "fix", "broken", "crash", "fail", "issue"],
            "decision": ["decided", "chose", "selected", "architecture", "pattern", "approach"],
            "milestone": ["completed", "done", "finished", "working", "success", "deployed"],
        }

        for msg in recent:
            lower = msg.content.lower()
            for event_type, words in keywords.items():
                if any(w in lower for w in words):
                    events.append({
                        "type": event_type,
                        "content": msg.content[:200],
                        "timestamp": msg.timestamp,
                    })
                    break

        return events

    # --- Properties ---

    @property
    def active_session_id(self) -> str | None:
        return self._active_session_id

    @property
    def message_count(self) -> int:
        return len(self._conversation)

    def close(self) -> None:
        self.store.close()
