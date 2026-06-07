"""Episodic memory store: structured memory events from sessions.

Each session produces meaningful events (not raw chat logs) that are stored
in SQLite with full metadata for efficient querying.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zerion_core.config import settings
from zerion_core.memory.longterm.importance import (
    BASE_SCORES,
    EventType,
    compute_importance,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    project_id TEXT DEFAULT '',
    event_type TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT DEFAULT '',
    files_affected TEXT DEFAULT '[]',
    importance REAL DEFAULT 0.5,
    embedding_id TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    accessed_at TEXT NOT NULL,
    times_accessed INTEGER DEFAULT 0,
    is_core INTEGER DEFAULT 0,
    tags TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_session ON memory_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_project ON memory_events(project_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON memory_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_importance ON memory_events(importance DESC);
CREATE INDEX IF NOT EXISTS idx_events_created ON memory_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_core ON memory_events(is_core);
"""


class MemoryEvent:
    """A single episodic memory event."""

    def __init__(
        self,
        id: str = "",
        session_id: str = "",
        project_id: str = "",
        event_type: str = "query",
        content: str = "",
        summary: str = "",
        files_affected: list[str] | None = None,
        importance: float = 0.5,
        embedding_id: str = "",
        created_at: str = "",
        accessed_at: str = "",
        times_accessed: int = 0,
        is_core: bool = False,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.id = id or uuid.uuid4().hex[:12]
        self.session_id = session_id
        self.project_id = project_id
        self.event_type = event_type
        self.content = content
        self.summary = summary
        self.files_affected = files_affected or []
        self.importance = importance
        self.embedding_id = embedding_id
        self.created_at = created_at or now
        self.accessed_at = accessed_at or now
        self.times_accessed = times_accessed
        self.is_core = is_core
        self.tags = tags or []
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "event_type": self.event_type,
            "content": self.content,
            "summary": self.summary,
            "files_affected": self.files_affected,
            "importance": self.importance,
            "embedding_id": self.embedding_id,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "times_accessed": self.times_accessed,
            "is_core": self.is_core,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class EpisodicStore:
    """SQLite-backed episodic memory store with importance scoring."""

    def __init__(self) -> None:
        self._db_path = settings.memory_root / "longterm.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path), timeout=10.0)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    def store_event(self, event: MemoryEvent) -> None:
        """Store a memory event, computing importance if not set."""
        conn = self._get_conn()
        if event.importance == 0.5 and event.event_type in BASE_SCORES:
            event.importance = compute_importance(
                EventType(event.event_type),
                event.created_at,
                event.times_accessed,
            )
            if event.importance >= 0.7:
                event.is_core = True

        conn.execute(
            """INSERT OR REPLACE INTO memory_events
               (id, session_id, project_id, event_type, content, summary, files_affected,
                importance, embedding_id, created_at, accessed_at, times_accessed, is_core, tags, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id, event.session_id, event.project_id, event.event_type,
                event.content, event.summary, json.dumps(event.files_affected),
                event.importance, event.embedding_id, event.created_at,
                event.accessed_at, event.times_accessed, int(event.is_core),
                json.dumps(event.tags), json.dumps(event.metadata),
            ),
        )
        conn.commit()

    def store_events(self, events: list[MemoryEvent]) -> None:
        """Batch store memory events."""
        for event in events:
            self.store_event(event)

    def get_event(self, event_id: str) -> MemoryEvent | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM memory_events WHERE id = ?", (event_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_event(row)

    def mark_accessed(self, event_id: str) -> None:
        """Reinforce a memory event when it's accessed."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE memory_events
               SET accessed_at = ?, times_accessed = times_accessed + 1
               WHERE id = ?""",
            (now, event_id),
        )
        conn.commit()

    def search_by_type(
        self,
        event_type: str,
        project_id: str | None = None,
        limit: int = 20,
        min_importance: float = 0.0,
    ) -> list[MemoryEvent]:
        """Search events by type with optional project filter."""
        conn = self._get_conn()
        if project_id:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE event_type = ? AND project_id = ? AND importance >= ?
                   ORDER BY importance DESC, created_at DESC LIMIT ?""",
                (event_type, project_id, min_importance, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE event_type = ? AND importance >= ?
                   ORDER BY importance DESC, created_at DESC LIMIT ?""",
                (event_type, min_importance, limit),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def search_by_project(
        self,
        project_id: str,
        limit: int = 50,
        min_importance: float = 0.0,
    ) -> list[MemoryEvent]:
        """Get all events for a project, sorted by importance."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM memory_events
               WHERE project_id = ? AND importance >= ?
               ORDER BY importance DESC, created_at DESC LIMIT ?""",
            (project_id, min_importance, limit),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def search_by_time_range(
        self,
        start: str,
        end: str,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEvent]:
        """Search events within a time range."""
        conn = self._get_conn()
        if project_id:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE created_at >= ? AND created_at <= ? AND project_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (start, end, project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE created_at >= ? AND created_at <= ?
                   ORDER BY created_at DESC LIMIT ?""",
                (start, end, limit),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def search_by_files(
        self,
        file_path: str,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEvent]:
        """Find events that affected a specific file."""
        conn = self._get_conn()
        if project_id:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE files_affected LIKE ? AND project_id = ?
                   ORDER BY importance DESC LIMIT ?""",
                (f"%{file_path}%", project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE files_affected LIKE ?
                   ORDER BY importance DESC LIMIT ?""",
                (f"%{file_path}%", limit),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_core_memories(
        self,
        project_id: str | None = None,
        limit: int = 30,
    ) -> list[MemoryEvent]:
        """Get the most important 'core' memories that persist."""
        conn = self._get_conn()
        if project_id:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE is_core = 1 AND project_id = ?
                   ORDER BY importance DESC, created_at DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE is_core = 1
                   ORDER BY importance DESC, created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_recent_events(
        self,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEvent]:
        """Get most recent events."""
        conn = self._get_conn()
        if project_id:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   WHERE project_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM memory_events
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count_events(self, project_id: str | None = None) -> int:
        conn = self._get_conn()
        if project_id:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM memory_events WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM memory_events",
            ).fetchone()
        return row["cnt"] if row else 0

    def update_importance(self, event_id: str, new_importance: float) -> None:
        conn = self._get_conn()
        is_core = 1 if new_importance >= 0.7 else 0
        conn.execute(
            "UPDATE memory_events SET importance = ?, is_core = ? WHERE id = ?",
            (new_importance, is_core, event_id),
        )
        conn.commit()

    def delete_event(self, event_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM memory_events WHERE id = ?", (event_id,))
        conn.commit()
        return cur.rowcount > 0

    def _row_to_event(self, row: sqlite3.Row) -> MemoryEvent:
        return MemoryEvent(
            id=row["id"],
            session_id=row["session_id"],
            project_id=row["project_id"],
            event_type=row["event_type"],
            content=row["content"],
            summary=row["summary"],
            files_affected=json.loads(row["files_affected"]),
            importance=row["importance"],
            embedding_id=row["embedding_id"],
            created_at=row["created_at"],
            accessed_at=row["accessed_at"],
            times_accessed=row["times_accessed"],
            is_core=bool(row["is_core"]),
            tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"]),
        )

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
