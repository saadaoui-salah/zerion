"""Enhanced skill memory: per-skill memory with patterns, failures, project learning."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from collections import defaultdict

from zerion_core.config import settings
from zerion_core.skills.models import _utcnow


SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    project_id TEXT DEFAULT '',
    memory_type TEXT NOT NULL,
    task TEXT NOT NULL,
    solution TEXT NOT NULL,
    files_modified TEXT DEFAULT '[]',
    outcome TEXT DEFAULT '',
    success_score REAL DEFAULT 0.0,
    embedding TEXT DEFAULT '[]',
    context TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    times_used INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    last_used TEXT DEFAULT '',
    UNIQUE(skill_id, task, solution)
);

CREATE TABLE IF NOT EXISTS skill_patterns (
    pattern_id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    success_rate REAL DEFAULT 0.5,
    embedding TEXT DEFAULT '[]',
    examples TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS failure_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    project_id TEXT DEFAULT '',
    task TEXT NOT NULL,
    failure_type TEXT NOT NULL,
    error_description TEXT NOT NULL,
    attempted_solution TEXT DEFAULT '',
    root_cause TEXT DEFAULT '',
    embedding TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_skill_profiles (
    project_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    architecture TEXT DEFAULT '',
    coding_style TEXT DEFAULT '',
    framework_conventions TEXT DEFAULT '',
    successful_patterns TEXT DEFAULT '[]',
    failure_lessons TEXT DEFAULT '[]',
    avg_success_score REAL DEFAULT 0.5,
    total_interactions INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_mem_skill ON skill_memory(skill_id);
CREATE INDEX IF NOT EXISTS idx_mem_project ON skill_memory(project_id);
CREATE INDEX IF NOT EXISTS idx_mem_type ON skill_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_patterns_skill ON skill_patterns(skill_id);
CREATE INDEX IF NOT EXISTS idx_failures_skill ON failure_memory(skill_id);
"""


class SkillMemorySystem:
    """Comprehensive memory system for skills."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or settings.memory_root / "skill_memory.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- Memory Operations ---

    def record_memory(
        self,
        skill_id: str,
        task: str,
        solution: str,
        project_id: str = "",
        outcome: str = "",
        success_score: float = 0.5,
        files_modified: list[str] | None = None,
        context: str = "",
        tags: list[str] | None = None,
        embedding: list[float] | None = None,
    ) -> int:
        """Record a memory entry."""
        cursor = self._conn.execute(
            """INSERT OR REPLACE INTO skill_memory
            (skill_id, project_id, memory_type, task, solution, files_modified,
             outcome, success_score, embedding, context, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                skill_id, project_id, "experience", task, solution,
                json.dumps(files_modified or []), outcome, success_score,
                json.dumps(embedding or []), context,
                json.dumps(tags or []), _utcnow(),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def recall_memories(
        self,
        skill_id: str,
        query: str = "",
        project_id: str | None = None,
        min_score: float = 0.0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Recall relevant memories."""
        conditions = ["skill_id = ?"]
        params: list[Any] = [skill_id]

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        if min_score > 0:
            conditions.append("success_score >= ?")
            params.append(min_score)

        if query:
            conditions.append("(task LIKE ? OR solution LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"""SELECT * FROM skill_memory WHERE {where}
            ORDER BY success_score DESC, times_used DESC LIMIT ?""",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def get_success_rate(self, skill_id: str, project_id: str | None = None) -> float:
        """Get success rate for a skill."""
        conditions = ["skill_id = ?"]
        params: list[Any] = [skill_id]

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        where = " AND ".join(conditions)
        row = self._conn.execute(
            f"SELECT AVG(success_score) as avg_score, COUNT(*) as total FROM skill_memory WHERE {where}",
            params,
        ).fetchone()
        if not row or row["total"] == 0:
            return 0.5
        return row["avg_score"] or 0.5

    def update_memory_usage(self, memory_id: int) -> None:
        """Update usage stats for a memory entry."""
        self._conn.execute(
            "UPDATE skill_memory SET times_used = times_used + 1, last_used = ? WHERE id = ?",
            (_utcnow(), memory_id),
        )
        self._conn.commit()

    # --- Pattern Operations ---

    def record_pattern(
        self,
        skill_id: str,
        pattern_name: str,
        embedding: list[float] | None = None,
        examples: list[str] | None = None,
    ) -> str:
        """Record or update a pattern."""
        pattern_id = f"{skill_id}:{pattern_name.lower().replace(' ', '_')}"

        existing = self._conn.execute(
            "SELECT * FROM skill_patterns WHERE pattern_id = ?", (pattern_id,)
        ).fetchone()

        if existing:
            self._conn.execute(
                """UPDATE skill_patterns
                SET frequency = frequency + 1, updated_at = ?
                WHERE pattern_id = ?""",
                (_utcnow(), pattern_id),
            )
        else:
            self._conn.execute(
                """INSERT INTO skill_patterns
                (pattern_id, skill_id, pattern_name, frequency, success_rate,
                 embedding, examples, created_at, updated_at)
                VALUES (?, ?, ?, 1, 0.5, ?, ?, ?, ?)""",
                (
                    pattern_id, skill_id, pattern_name,
                    json.dumps(embedding or []),
                    json.dumps(examples or []),
                    _utcnow(), _utcnow(),
                ),
            )
        self._conn.commit()
        return pattern_id

    def update_pattern_success(self, pattern_id: str, success: bool) -> None:
        """Update pattern success rate."""
        row = self._conn.execute(
            "SELECT frequency, success_rate FROM skill_patterns WHERE pattern_id = ?",
            (pattern_id,),
        ).fetchone()
        if not row:
            return

        freq = row["frequency"]
        old_rate = row["success_rate"]
        new_rate = ((old_rate * (freq - 1)) + (1.0 if success else 0.0)) / freq

        self._conn.execute(
            "UPDATE skill_patterns SET success_rate = ?, updated_at = ? WHERE pattern_id = ?",
            (new_rate, _utcnow(), pattern_id),
        )
        self._conn.commit()

    def get_patterns(
        self,
        skill_id: str,
        min_frequency: int = 2,
        min_success_rate: float = 0.6,
    ) -> list[dict[str, Any]]:
        """Get successful patterns for a skill."""
        rows = self._conn.execute(
            """SELECT * FROM skill_patterns
            WHERE skill_id = ? AND frequency >= ? AND success_rate >= ?
            ORDER BY success_rate DESC, frequency DESC""",
            (skill_id, min_frequency, min_success_rate),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Failure Operations ---

    def record_failure(
        self,
        skill_id: str,
        task: str,
        failure_type: str,
        error_description: str,
        project_id: str = "",
        attempted_solution: str = "",
        root_cause: str = "",
        embedding: list[float] | None = None,
    ) -> int:
        """Record a failure."""
        cursor = self._conn.execute(
            """INSERT INTO failure_memory
            (skill_id, project_id, task, failure_type, error_description,
             attempted_solution, root_cause, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                skill_id, project_id, task, failure_type, error_description,
                attempted_solution, root_cause,
                json.dumps(embedding or []), _utcnow(),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_failures(
        self,
        skill_id: str,
        project_id: str | None = None,
        failure_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recorded failures."""
        conditions = ["skill_id = ?"]
        params: list[Any] = [skill_id]

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        if failure_type:
            conditions.append("failure_type = ?")
            params.append(failure_type)

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"SELECT * FROM failure_memory WHERE {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def get_failure_lessons(self, skill_id: str) -> list[str]:
        """Get lessons learned from failures."""
        failures = self.get_failures(skill_id, limit=50)
        lessons = []
        for f in failures:
            if f["root_cause"]:
                lessons.append(f"Avoid: {f['task']} - {f['root_cause']}")
        return lessons

    # --- Project Profile Operations ---

    def update_project_profile(
        self,
        project_id: str,
        skill_id: str,
        success_score: float,
        architecture: str = "",
        coding_style: str = "",
        framework_conventions: str = "",
    ) -> None:
        """Update project-skill profile."""
        existing = self._conn.execute(
            "SELECT * FROM project_skill_profiles WHERE project_id = ? AND skill_id = ?",
            (project_id, skill_id),
        ).fetchone()

        if existing:
            total = existing["total_interactions"] + 1
            old_avg = existing["avg_success_score"]
            new_avg = ((old_avg * existing["total_interactions"]) + success_score) / total

            self._conn.execute(
                """UPDATE project_skill_profiles
                SET avg_success_score = ?, total_interactions = ?, updated_at = ?
                WHERE project_id = ? AND skill_id = ?""",
                (new_avg, total, _utcnow(), project_id, skill_id),
            )
        else:
            self._conn.execute(
                """INSERT INTO project_skill_profiles
                (project_id, skill_id, architecture, coding_style,
                 framework_conventions, avg_success_score, total_interactions, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (project_id, skill_id, architecture, coding_style,
                 framework_conventions, success_score, _utcnow()),
            )
        self._conn.commit()

    def get_project_profile(
        self,
        project_id: str,
        skill_id: str,
    ) -> dict[str, Any] | None:
        """Get project-skill profile."""
        row = self._conn.execute(
            "SELECT * FROM project_skill_profiles WHERE project_id = ? AND skill_id = ?",
            (project_id, skill_id),
        ).fetchone()
        return dict(row) if row else None

    def get_project_skills(self, project_id: str) -> list[dict[str, Any]]:
        """Get all skills used in a project."""
        rows = self._conn.execute(
            """SELECT * FROM project_skill_profiles
            WHERE project_id = ? ORDER BY avg_success_score DESC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Stats ---

    def get_stats(self, skill_id: str) -> dict[str, int]:
        """Get memory statistics for a skill."""
        mem_count = self._conn.execute(
            "SELECT COUNT(*) as c FROM skill_memory WHERE skill_id = ?", (skill_id,)
        ).fetchone()["c"]

        pattern_count = self._conn.execute(
            "SELECT COUNT(*) as c FROM skill_patterns WHERE skill_id = ?", (skill_id,)
        ).fetchone()["c"]

        failure_count = self._conn.execute(
            "SELECT COUNT(*) as c FROM failure_memory WHERE skill_id = ?", (skill_id,)
        ).fetchone()["c"]

        return {
            "memories": mem_count,
            "patterns": pattern_count,
            "failures": failure_count,
        }

    def prune_memories(self, skill_id: str, max_entries: int = 1000) -> int:
        """Prune low-value memories."""
        self._conn.execute(
            """DELETE FROM skill_memory WHERE skill_id = ? AND id NOT IN
            (SELECT id FROM skill_memory WHERE skill_id = ?
             ORDER BY success_score DESC, times_used DESC LIMIT ?)""",
            (skill_id, skill_id, max_entries),
        )
        self._conn.commit()
        return self._conn.total_changes
