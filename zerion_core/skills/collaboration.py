"""Skill collaboration graph: tracks skill cooperation and relationships."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from collections import defaultdict

from zerion_core.config import settings
from zerion_core.skills.models import _utcnow


SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_collaborations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_a TEXT NOT NULL,
    skill_b TEXT NOT NULL,
    collaboration_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    avg_score REAL DEFAULT 0.5,
    last_collaboration TEXT NOT NULL,
    context TEXT DEFAULT '',
    UNIQUE(skill_a, skill_b)
);

CREATE TABLE IF NOT EXISTS skill_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    session_id TEXT DEFAULT '',
    query TEXT DEFAULT '',
    score REAL DEFAULT 0.0,
    success INTEGER DEFAULT 1,
    activated_at TEXT NOT NULL,
    co_activated TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_collab_a ON skill_collaborations(skill_a);
CREATE INDEX IF NOT EXISTS idx_collab_b ON skill_collaborations(skill_b);
CREATE INDEX IF NOT EXISTS idx_act_skill ON skill_activations(skill_id);
"""


class SkillCollaborationGraph:
    """Tracks and queries skill collaboration patterns."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or settings.memory_root / "skill_collaborations.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record_activation(
        self,
        skill_ids: list[str],
        query: str = "",
        session_id: str = "",
        score: float = 0.5,
        success: bool = True,
    ) -> None:
        """Record skill activation and co-activations."""
        if not skill_ids:
            return

        # Record each skill activation
        for skill_id in skill_ids:
            self._conn.execute(
                """INSERT INTO skill_activations
                (skill_id, session_id, query, score, success, activated_at, co_activated)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    skill_id, session_id, query, score,
                    1 if success else 0, _utcnow(),
                    json.dumps([s for s in skill_ids if s != skill_id]),
                ),
            )

        # Record co-activations
        for i, skill_a in enumerate(skill_ids):
            for skill_b in skill_ids[i + 1:]:
                self._record_collaboration(skill_a, skill_b, score, success)

        self._conn.commit()

    def _record_collaboration(
        self,
        skill_a: str,
        skill_b: str,
        score: float,
        success: bool,
    ) -> None:
        """Record collaboration between two skills."""
        # Ensure consistent ordering
        a, b = sorted([skill_a, skill_b])

        existing = self._conn.execute(
            "SELECT * FROM skill_collaborations WHERE skill_a = ? AND skill_b = ?",
            (a, b),
        ).fetchone()

        if existing:
            count = existing["collaboration_count"] + 1
            success_count = existing["success_count"] + (1 if success else 0)
            old_avg = existing["avg_score"]
            new_avg = ((old_avg * existing["collaboration_count"]) + score) / count

            self._conn.execute(
                """UPDATE skill_collaborations
                SET collaboration_count = ?, success_count = ?, avg_score = ?, last_collaboration = ?
                WHERE skill_a = ? AND skill_b = ?""",
                (count, success_count, new_avg, _utcnow(), a, b),
            )
        else:
            self._conn.execute(
                """INSERT INTO skill_collaborations
                (skill_a, skill_b, collaboration_count, success_count, avg_score, last_collaboration)
                VALUES (?, ?, 1, ?, ?, ?)""",
                (a, b, 1 if success else 0, score, _utcnow()),
            )

    def get_collaborators(
        self,
        skill_id: str,
        min_count: int = 2,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Get skills that frequently collaborate with a skill."""
        rows = self._conn.execute(
            """SELECT * FROM skill_collaborations
            WHERE (skill_a = ? OR skill_b = ?) AND collaboration_count >= ?
            ORDER BY collaboration_count DESC, avg_score DESC
            LIMIT ?""",
            (skill_id, skill_id, min_count, top_k),
        ).fetchall()

        results = []
        for row in rows:
            collaborator = row["skill_b"] if row["skill_a"] == skill_id else row["skill_a"]
            results.append({
                "skill_id": collaborator,
                "collaboration_count": row["collaboration_count"],
                "success_count": row["success_count"],
                "avg_score": row["avg_score"],
                "success_rate": row["success_count"] / max(row["collaboration_count"], 1),
            })

        return results

    def get_frequent_pairs(
        self,
        min_count: int = 3,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Get most frequent skill pairs."""
        rows = self._conn.execute(
            """SELECT * FROM skill_collaborations
            WHERE collaboration_count >= ?
            ORDER BY collaboration_count DESC
            LIMIT ?""",
            (min_count, top_k),
        ).fetchall()

        return [
            {
                "skill_a": row["skill_a"],
                "skill_b": row["skill_b"],
                "count": row["collaboration_count"],
                "avg_score": row["avg_score"],
            }
            for row in rows
        ]

    def predict_co_activation(
        self,
        activated_skills: list[str],
        all_skills: list[str],
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Predict which skills should be co-activated."""
        if not activated_skills:
            return []

        # Get collaborators for each activated skill
        collaborator_scores: dict[str, float] = defaultdict(float)

        for skill_id in activated_skills:
            collaborators = self.get_collaborators(skill_id, min_count=1)
            for collab in collaborators:
                if collab["skill_id"] not in activated_skills:
                    # Weight by collaboration frequency and success rate
                    weight = collab["collaboration_count"] * collab["success_rate"]
                    collaborator_scores[collab["skill_id"]] += weight

        # Sort by score
        ranked = sorted(
            collaborator_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [
            {"skill_id": skill_id, "prediction_score": round(score, 4)}
            for skill_id, score in ranked[:top_k]
        ]

    def get_skill_stats(self, skill_id: str) -> dict[str, Any]:
        """Get collaboration statistics for a skill."""
        # Count as skill_a
        count_a = self._conn.execute(
            "SELECT COUNT(*) as c FROM skill_collaborations WHERE skill_a = ?",
            (skill_id,),
        ).fetchone()["c"]

        # Count as skill_b
        count_b = self._conn.execute(
            "SELECT COUNT(*) as c FROM skill_collaborations WHERE skill_b = ?",
            (skill_id,),
        ).fetchone()["c"]

        # Total activations
        activations = self._conn.execute(
            "SELECT COUNT(*) as c FROM skill_activations WHERE skill_id = ?",
            (skill_id,),
        ).fetchone()["c"]

        # Success rate
        success_row = self._conn.execute(
            "SELECT AVG(success) as rate FROM skill_activations WHERE skill_id = ?",
            (skill_id,),
        ).fetchone()

        return {
            "skill_id": skill_id,
            "unique_collaborators": count_a + count_b,
            "total_activations": activations,
            "success_rate": success_row["rate"] or 0.5,
        }

    def build_relationship_map(self) -> dict[str, list[dict[str, Any]]]:
        """Build complete relationship map for all skills."""
        rows = self._conn.execute(
            "SELECT * FROM skill_collaborations ORDER BY collaboration_count DESC"
        ).fetchall()

        relationships: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for row in rows:
            relationships[row["skill_a"]].append({
                "skill_id": row["skill_b"],
                "count": row["collaboration_count"],
                "score": row["avg_score"],
            })
            relationships[row["skill_b"]].append({
                "skill_id": row["skill_a"],
                "count": row["collaboration_count"],
                "score": row["avg_score"],
            })

        return dict(relationships)

    def suggest_multi_skill(
        self,
        query: str,
        primary_skill: str,
        top_k: int = 2,
    ) -> list[str]:
        """Suggest additional skills to activate with a primary skill."""
        collaborators = self.get_collaborators(primary_skill, min_count=2, top_k=top_k)

        # Filter by query relevance (simple keyword matching)
        query_words = set(query.lower().split())
        relevant = []

        for collab in collaborators:
            skill_words = set(collab["skill_id"].lower().replace("-", " ").split())
            overlap = len(query_words & skill_words)
            if overlap > 0 or collab["success_rate"] > 0.7:
                relevant.append(collab["skill_id"])

        return relevant[:top_k]
