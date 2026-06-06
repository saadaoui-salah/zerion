from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from zerion_core.config import settings
from zerion_core.memory.models import (
    EpisodicEntry,
    JsonStore,
    SemanticFact,
    ShortTermMemory,
    WorkingMemorySlot,
    _utcnow,
)


class SessionMeta(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    task_count: int = 0
    tags: list[str] = Field(default_factory=list)


class SessionData(BaseModel):
    meta: SessionMeta
    stm: dict[str, Any] = Field(default_factory=dict)
    working_memory: dict[str, str] = Field(default_factory=dict)
    episodic: dict[str, Any] = Field(default_factory=dict)
    semantic_facts: list[dict[str, Any]] = Field(default_factory=list)
    procedures: list[dict[str, Any]] = Field(default_factory=list)
    conversation: list[dict[str, str]] = Field(default_factory=list)


class SessionManager:
    """Persistent session management: save, load, list, delete."""

    def __init__(self) -> None:
        self._dir = settings.sessions_dir

    def _session_path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json"

    def _list_index(self) -> dict[str, Any]:
        index_path = self._dir / "_index.json"
        if index_path.exists():
            return json.loads(index_path.read_text(encoding="utf-8"))
        return {}

    def _save_index(self, index: dict[str, Any]) -> None:
        index_path = self._dir / "_index.json"
        index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    def save(
        self,
        memory: Any | None = None,
        name: str = "",
        description: str = "",
        tags: list[str] | None = None,
        conversation: list[dict[str, str]] | None = None,
        session_id: str | None = None,
    ) -> SessionMeta:
        """Save current memory state as a session."""
        now = _utcnow()

        if session_id and self._session_path(session_id).exists():
            existing = self.load(session_id)
            meta = existing.meta
            meta.name = name or meta.name
            meta.description = description or meta.description
            meta.updated_at = now
            meta.task_count += 1
            if tags:
                meta.tags = list(set(meta.tags + tags))
        else:
            meta = SessionMeta(
                name=name or f"session-{now[:10]}",
                description=description,
                created_at=now,
                updated_at=now,
                tags=tags or [],
            )

        # Snapshot STM
        stm_data = {}
        if memory:
            try:
                stm = memory.get_stm()
                stm_data = stm.model_dump()
            except Exception:
                pass

        # Snapshot working memory
        working_data = {}
        if memory:
            try:
                working_data = memory.working.dump()
            except Exception:
                pass

        # Snapshot episodic (per-project)
        episodic_data = {}
        if memory:
            try:
                for key in memory.episodic_store.list_keys():
                    episodic_data[key] = memory.episodic_store.get(key)
            except Exception:
                pass

        # Snapshot semantic facts
        semantic_data = []
        if memory:
            try:
                facts = memory.get_semantic_facts()
                semantic_data = [f.model_dump() for f in facts]
            except Exception:
                pass

        # Snapshot procedures
        procedure_data = []
        if memory:
            try:
                for key in memory.procedural_store.list_keys():
                    procedure_data.append(memory.procedural_store.get(key))
            except Exception:
                pass

        session = SessionData(
            meta=meta,
            stm=stm_data,
            working_memory=working_data,
            episodic=episodic_data,
            semantic_facts=semantic_data,
            procedures=procedure_data,
            conversation=conversation or [],
        )

        # Write session file
        path = self._session_path(meta.id)
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

        # Update index
        index = self._list_index()
        index[meta.id] = {
            "name": meta.name,
            "description": meta.description,
            "created_at": meta.created_at,
            "updated_at": meta.updated_at,
            "task_count": meta.task_count,
            "tags": meta.tags,
        }
        self._save_index(index)

        return meta

    def load(self, session_id: str) -> SessionData:
        """Load a session by ID."""
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session {session_id} not found")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return SessionData(**raw)

    def restore(self, session_id: str, memory: Any) -> bool:
        """Restore a session's state into the given MemoryManager."""
        try:
            session = self.load(session_id)
        except FileNotFoundError:
            return False

        # Restore STM
        if session.stm:
            try:
                stm = ShortTermMemory(**session.stm)
                memory.stm_store.set("active", stm.model_dump())
            except Exception:
                pass

        # Restore working memory
        for key, value in session.working_memory.items():
            memory.working.set(key, value)

        # Restore episodic
        for project, data in session.episodic.items():
            if isinstance(data, dict):
                memory.episodic_store.set(project, data)

        # Restore semantic facts
        for fact_data in session.semantic_facts:
            try:
                fact = SemanticFact(**fact_data)
                memory.upsert_semantic(
                    fact.key,
                    fact.value,
                    fact.confidence,
                    source=fact.source,
                )
            except Exception:
                pass

        # Restore procedures
        for proc_data in session.procedures:
            if isinstance(proc_data, dict):
                try:
                    from zerion_core.memory.models import ProceduralEntry
                    entry = ProceduralEntry(**proc_data)
                    memory.save_procedure(entry)
                except Exception:
                    pass

        return True

    def list_sessions(self) -> list[SessionMeta]:
        """List all saved sessions, sorted by most recent."""
        index = self._list_index()
        sessions = []
        for sid, info in index.items():
            sessions.append(SessionMeta(id=sid, **info))
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
        index = self._list_index()
        if session_id in index:
            del index[session_id]
            self._save_index(index)
            return True
        return False

    def rename(self, session_id: str, new_name: str) -> bool:
        """Rename a session."""
        index = self._list_index()
        if session_id not in index:
            return False
        index[session_id]["name"] = new_name
        index[session_id]["updated_at"] = _utcnow()
        self._save_index(index)

        # Also update the session file
        path = self._session_path(session_id)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["meta"]["name"] = new_name
            raw["meta"]["updated_at"] = _utcnow()
            path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        return True

    def get_conversation(self, session_id: str) -> list[dict[str, str]]:
        """Get the conversation history from a session."""
        try:
            session = self.load(session_id)
            return session.conversation
        except FileNotFoundError:
            return []
