"""Skill registry: SQLite-backed storage for installed skills and their state."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from zerion_core.config import settings
from zerion_core.skills.models import (
    SkillMemoryEntry,
    SkillRegistryEntry,
    _utcnow,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    name TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    description TEXT DEFAULT '',
    author TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    source TEXT DEFAULT 'local',
    source_url TEXT DEFAULT '',
    installed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT DEFAULT 'installed',
    usage_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_score REAL DEFAULT 0.0,
    embedding TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS skill_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    content TEXT NOT NULL,
    context TEXT DEFAULT '',
    success INTEGER DEFAULT 1,
    score REAL DEFAULT 0.5,
    times_used INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    last_used TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    FOREIGN KEY (skill_name) REFERENCES skills(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS skill_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    session_id TEXT DEFAULT '',
    query TEXT DEFAULT '',
    score REAL DEFAULT 0.0,
    success INTEGER DEFAULT 1,
    activated_at TEXT NOT NULL,
    FOREIGN KEY (skill_name) REFERENCES skills(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_skill_memory_name ON skill_memory(skill_name);
CREATE INDEX IF NOT EXISTS idx_skill_memory_type ON skill_memory(entry_type);
CREATE INDEX IF NOT EXISTS idx_activations_name ON skill_activations(skill_name);
"""


class SkillRegistry:
    """SQLite-backed skill registry and memory store."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or settings.memory_root / "skill_registry.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- Skills Registry ---

    def register_skill(self, entry: SkillRegistryEntry) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO skills
            (name, version, description, author, tags, source, source_url,
             installed_at, updated_at, status, usage_count, success_count,
             failure_count, avg_score, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.name, entry.version, entry.description, entry.author,
                entry.tags, entry.source, entry.source_url,
                entry.installed_at, entry.updated_at, entry.status,
                entry.usage_count, entry.success_count, 0,
                entry.avg_score, entry.embedding,
            ),
        )
        self._conn.commit()

    def get_skill(self, name: str) -> SkillRegistryEntry | None:
        row = self._conn.execute("SELECT * FROM skills WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        return self._row_to_entry(row)

    def list_skills(self, status: str | None = None) -> list[SkillRegistryEntry]:
        if status:
            rows = self._conn.execute("SELECT * FROM skills WHERE status = ? ORDER BY name", (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM skills ORDER BY name").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def update_skill(self, name: str, **kwargs: Any) -> bool:
        if not kwargs:
            return False
        kwargs["updated_at"] = _utcnow()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [name]
        self._conn.execute(f"UPDATE skills SET {set_clause} WHERE name = ?", values)
        self._conn.commit()
        return self._conn.total_changes > 0

    def delete_skill(self, name: str) -> bool:
        self._conn.execute("DELETE FROM skill_memory WHERE skill_name = ?", (name,))
        self._conn.execute("DELETE FROM skill_activations WHERE skill_name = ?", (name,))
        self._conn.execute("DELETE FROM skills WHERE name = ?", (name,))
        self._conn.commit()
        return True

    def record_activation(self, skill_name: str, query: str, score: float, success: bool, session_id: str = "") -> None:
        self._conn.execute(
            "INSERT INTO skill_activations (skill_name, session_id, query, score, success, activated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (skill_name, session_id, query, score, 1 if success else 0, _utcnow()),
        )
        self._conn.execute(
            "UPDATE skills SET usage_count = usage_count + 1, success_count = success_count + ? WHERE name = ?",
            (1 if success else 0, skill_name),
        )
        self._conn.commit()

    def get_activation_stats(self, skill_name: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT usage_count, success_count, avg_score FROM skills WHERE name = ?",
            (skill_name,),
        ).fetchone()
        if not row:
            return {"usage_count": 0, "success_count": 0, "avg_score": 0.0}
        return dict(row)

    # --- Skill Memory ---

    def add_memory(self, entry: SkillMemoryEntry) -> int:
        cursor = self._conn.execute(
            """INSERT INTO skill_memory
            (skill_name, entry_type, content, context, success, score,
             times_used, created_at, last_used, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.skill_name, entry.entry_type, entry.content,
                entry.context, 1 if entry.success else 0, entry.score,
                entry.times_used, entry.created_at, entry.last_used,
                entry.tags,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def search_memory(
        self,
        skill_name: str,
        query: str = "",
        entry_type: str | None = None,
        limit: int = 10,
    ) -> list[SkillMemoryEntry]:
        conditions = ["skill_name = ?"]
        params: list[Any] = [skill_name]

        if entry_type:
            conditions.append("entry_type = ?")
            params.append(entry_type)

        if query:
            conditions.append("content LIKE ?")
            params.append(f"%{query}%")

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"SELECT * FROM skill_memory WHERE {where} ORDER BY score DESC, times_used DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def update_memory_usage(self, memory_id: int) -> None:
        self._conn.execute(
            "UPDATE skill_memory SET times_used = times_used + 1, last_used = ? WHERE id = ?",
            (_utcnow(), memory_id),
        )
        self._conn.commit()

    def get_memory_stats(self, skill_name: str) -> dict[str, int]:
        row = self._conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful FROM skill_memory WHERE skill_name = ?",
            (skill_name,),
        ).fetchone()
        if not row:
            return {"total": 0, "successful": 0}
        return {"total": row["total"], "successful": row["successful"] or 0}

    def prune_memory(self, skill_name: str, max_entries: int = 1000) -> int:
        self._conn.execute(
            """DELETE FROM skill_memory WHERE skill_name = ? AND id NOT IN
            (SELECT id FROM skill_memory WHERE skill_name = ? ORDER BY score DESC, times_used DESC LIMIT ?)""",
            (skill_name, skill_name, max_entries),
        )
        self._conn.commit()
        return self._conn.total_changes

    # --- Internal ---

    def _row_to_entry(self, row: sqlite3.Row) -> SkillRegistryEntry:
        return SkillRegistryEntry(
            name=row["name"],
            version=row["version"],
            description=row["description"],
            author=row["author"],
            tags=row["tags"],
            source=row["source"],
            source_url=row["source_url"],
            installed_at=row["installed_at"],
            updated_at=row["updated_at"],
            status=row["status"],
            usage_count=row["usage_count"],
            success_count=row["success_count"],
            avg_score=row["avg_score"],
            embedding=row["embedding"],
        )

    def _row_to_memory(self, row: sqlite3.Row) -> SkillMemoryEntry:
        return SkillMemoryEntry(
            id=str(row["id"]),
            skill_name=row["skill_name"],
            entry_type=row["entry_type"],
            content=row["content"],
            context=row["context"],
            success=bool(row["success"]),
            score=row["score"],
            times_used=row["times_used"],
            created_at=row["created_at"],
            last_used=row["last_used"],
            tags=row["tags"],
        )
