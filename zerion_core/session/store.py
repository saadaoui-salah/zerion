"""SQLite-backed persistent storage for sessions and project memory."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from zerion_core.config import settings
from zerion_core.session.models import (
    Message,
    MessageRole,
    ProjectMemory,
    SessionData,
    SessionMeta,
    SessionState,
    ToolEvent,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT DEFAULT '',
    title TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    tags TEXT DEFAULT '[]',
    is_branch INTEGER DEFAULT 0,
    branch_parent_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tool_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    target TEXT DEFAULT '',
    success INTEGER DEFAULT 1,
    summary TEXT DEFAULT '',
    diff_preview TEXT DEFAULT '',
    error TEXT DEFAULT '',
    duration_ms REAL DEFAULT 0.0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_state (
    session_id TEXT PRIMARY KEY,
    open_files TEXT DEFAULT '[]',
    last_errors TEXT DEFAULT '[]',
    applied_patches TEXT DEFAULT '[]',
    retrieved_chunks TEXT DEFAULT '[]',
    active_task TEXT DEFAULT '',
    current_goal TEXT DEFAULT '',
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id TEXT PRIMARY KEY,
    summary TEXT DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_memory (
    project_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
CREATE INDEX IF NOT EXISTS idx_tool_events_session ON tool_events(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
"""


class SessionStore:
    """Thread-safe SQLite store for all session data."""

    def __init__(self) -> None:
        self._db_path = settings.memory_root / "sessions.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path), timeout=10.0)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    # --- Session CRUD ---

    def create_session(self, meta: SessionMeta) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO sessions (id, project_id, title, summary, created_at, updated_at,
               message_count, total_tokens, tags, is_branch, branch_parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meta.id, meta.project_id, meta.title, meta.summary,
                meta.created_at, meta.updated_at, meta.message_count,
                meta.total_tokens, json.dumps(meta.tags),
                int(meta.is_branch), meta.branch_parent_id,
            ),
        )
        conn.commit()

    def get_session_meta(self, session_id: str) -> SessionMeta | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return self._row_to_meta(row)

    def update_session_meta(self, meta: SessionMeta) -> None:
        conn = self._get_conn()
        conn.execute(
            """UPDATE sessions SET project_id=?, title=?, summary=?, updated_at=?,
               message_count=?, total_tokens=?, tags=?, is_branch=?, branch_parent_id=?
               WHERE id=?""",
            (
                meta.project_id, meta.title, meta.summary, meta.updated_at,
                meta.message_count, meta.total_tokens, json.dumps(meta.tags),
                int(meta.is_branch), meta.branch_parent_id, meta.id,
            ),
        )
        conn.commit()

    def delete_session(self, session_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cur.rowcount > 0

    def list_sessions(
        self,
        project_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SessionMeta]:
        conn = self._get_conn()
        if project_id:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE project_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (project_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_meta(r) for r in rows]

    def get_latest_session(self, project_id: str | None = None) -> SessionMeta | None:
        sessions = self.list_sessions(project_id=project_id, limit=1)
        return sessions[0] if sessions else None

    # --- Messages ---

    def add_messages(self, session_id: str, messages: list[Message]) -> None:
        conn = self._get_conn()
        conn.executemany(
            """INSERT OR REPLACE INTO messages (id, session_id, role, content, timestamp, token_count, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (m.id, session_id, m.role.value, m.content, m.timestamp, m.token_count, json.dumps(m.metadata))
                for m in messages
            ],
        )
        conn.commit()

    def get_messages(
        self,
        session_id: str,
        limit: int | None = None,
        offset: int = 0,
        role: MessageRole | None = None,
    ) -> list[Message]:
        conn = self._get_conn()
        if role:
            if limit:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id=? AND role=? ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                    (session_id, role.value, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id=? AND role=? ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                    (session_id, role.value, 10000, offset),
                ).fetchall()
        else:
            if limit:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id=? ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                    (session_id, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id=? ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                    (session_id, 10000, offset),
                ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def get_message_count(self, session_id: str) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE session_id=?", (session_id,)
        ).fetchone()
        return row["cnt"] if row else 0

    def delete_old_messages(self, session_id: str, keep_last: int) -> int:
        """Delete messages older than the last N. Returns count deleted."""
        conn = self._get_conn()
        ids = conn.execute(
            "SELECT id FROM messages WHERE session_id=? ORDER BY timestamp ASC",
            (session_id,),
        ).fetchall()
        if len(ids) <= keep_last:
            return 0
        to_delete = [r["id"] for r in ids[: len(ids) - keep_last]]
        placeholders = ",".join("?" * len(to_delete))
        conn.execute(
            f"DELETE FROM messages WHERE id IN ({placeholders})",
            to_delete,
        )
        conn.commit()
        return len(to_delete)

    # --- Tool Events ---

    def add_tool_events(self, session_id: str, events: list[ToolEvent]) -> None:
        conn = self._get_conn()
        conn.executemany(
            """INSERT INTO tool_events (id, session_id, timestamp, tool_name, target,
               success, summary, diff_preview, error, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (e.id, session_id, e.timestamp, e.tool_name, e.target,
                 int(e.success), e.summary, e.diff_preview, e.error, e.duration_ms)
                for e in events
            ],
        )
        conn.commit()

    def get_tool_events(self, session_id: str, limit: int = 100) -> list[ToolEvent]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM tool_events WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [self._row_to_tool_event(r) for r in rows]

    # --- Session State ---

    def save_state(self, session_id: str, state: SessionState) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO session_state
               (session_id, open_files, last_errors, applied_patches, retrieved_chunks, active_task, current_goal)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                json.dumps(state.open_files),
                json.dumps(state.last_errors),
                json.dumps(state.applied_patches),
                json.dumps(state.retrieved_chunks),
                state.active_task,
                state.current_goal,
            ),
        )
        conn.commit()

    def get_state(self, session_id: str) -> SessionState:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM session_state WHERE session_id=?", (session_id,)
        ).fetchone()
        if not row:
            return SessionState()
        return SessionState(
            open_files=json.loads(row["open_files"]),
            last_errors=json.loads(row["last_errors"]),
            applied_patches=json.loads(row["applied_patches"]),
            retrieved_chunks=json.loads(row["retrieved_chunks"]),
            active_task=row["active_task"],
            current_goal=row["current_goal"],
        )

    # --- Summaries ---

    def save_summary(self, session_id: str, summary: str) -> None:
        conn = self._get_conn()
        from zerion_core.session.models import _utcnow
        conn.execute(
            "INSERT OR REPLACE INTO session_summaries (session_id, summary, updated_at) VALUES (?, ?, ?)",
            (session_id, summary, _utcnow()),
        )
        conn.commit()

    def get_summary(self, session_id: str) -> str:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT summary FROM session_summaries WHERE session_id=?", (session_id,)
        ).fetchone()
        return row["summary"] if row else ""

    # --- Project Memory ---

    def save_project_memory(self, memory: ProjectMemory) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO project_memory (project_id, data, updated_at) VALUES (?, ?, ?)",
            (memory.project_id, memory.model_dump_json(), memory.updated_at),
        )
        conn.commit()

    def get_project_memory(self, project_id: str) -> ProjectMemory | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT data FROM project_memory WHERE project_id=?", (project_id,)
        ).fetchone()
        if not row:
            return None
        return ProjectMemory.model_validate_json(row["data"])

    def list_project_memories(self) -> list[ProjectMemory]:
        conn = self._get_conn()
        rows = conn.execute("SELECT data FROM project_memory ORDER BY updated_at DESC").fetchall()
        return [ProjectMemory.model_validate_json(r["data"]) for r in rows]

    # --- Full Session Load/Save ---

    def load_full_session(self, session_id: str) -> SessionData | None:
        meta = self.get_session_meta(session_id)
        if not meta:
            return None
        return SessionData(
            meta=meta,
            messages=self.get_messages(session_id),
            tool_events=self.get_tool_events(session_id),
            state=self.get_state(session_id),
            summary=self.get_summary(session_id),
        )

    def save_full_session(self, session: SessionData) -> None:
        existing = self.get_session_meta(session.meta.id)
        if existing:
            self.update_session_meta(session.meta)
        else:
            self.create_session(session.meta)
        if session.messages:
            self.add_messages(session.meta.id, session.messages)
        if session.tool_events:
            self.add_tool_events(session.meta.id, session.tool_events)
        self.save_state(session.meta.id, session.state)
        if session.summary:
            self.save_summary(session.meta.id, session.summary)

    # --- Search (basic LIKE-based, overridden by semantic search) ---

    def search_sessions(self, query: str, limit: int = 10) -> list[SessionMeta]:
        conn = self._get_conn()
        pattern = f"%{query}%"
        rows = conn.execute(
            """SELECT * FROM sessions
               WHERE title LIKE ? OR summary LIKE ? OR project_id LIKE ?
               ORDER BY updated_at DESC LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_meta(r) for r in rows]

    def search_messages(self, query: str, session_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._get_conn()
        pattern = f"%{query}%"
        if session_id:
            rows = conn.execute(
                """SELECT m.*, s.title as session_title, s.project_id
                   FROM messages m JOIN sessions s ON m.session_id = s.id
                   WHERE m.session_id = ? AND m.content LIKE ?
                   ORDER BY m.timestamp DESC LIMIT ?""",
                (session_id, pattern, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT m.*, s.title as session_title, s.project_id
                   FROM messages m JOIN sessions s ON m.session_id = s.id
                   WHERE m.content LIKE ?
                   ORDER BY m.timestamp DESC LIMIT ?""",
                (pattern, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Helpers ---

    def _row_to_meta(self, row: sqlite3.Row) -> SessionMeta:
        return SessionMeta(
            id=row["id"],
            project_id=row["project_id"],
            title=row["title"],
            summary=row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            message_count=row["message_count"],
            total_tokens=row["total_tokens"],
            tags=json.loads(row["tags"]),
            is_branch=bool(row["is_branch"]),
            branch_parent_id=row["branch_parent_id"],
        )

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            timestamp=row["timestamp"],
            token_count=row["token_count"],
            metadata=json.loads(row["metadata"]),
        )

    def _row_to_tool_event(self, row: sqlite3.Row) -> ToolEvent:
        return ToolEvent(
            id=row["id"],
            timestamp=row["timestamp"],
            tool_name=row["tool_name"],
            target=row["target"],
            success=bool(row["success"]),
            summary=row["summary"],
            diff_preview=row["diff_preview"],
            error=row["error"],
            duration_ms=row["duration_ms"],
        )

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
