"""Collaboration analytics — measure skill combinations."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from zerion_core.benchmark.engine import BenchmarkEngine


class CollaborationAnalytics:
    """Measures and analyzes skill collaboration effectiveness."""

    def __init__(
        self,
        benchmark_engine: BenchmarkEngine,
        on_event: Any = None,
    ):
        self._engine = benchmark_engine
        self._on_event = on_event or (lambda s, m: None)
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._engine._db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def record_collaboration(
        self,
        skill_ids: list[str],
        success: bool,
        duration_ms: int = 0,
        project_id: str = "",
        task_type: str = "",
    ) -> None:
        """Record a collaboration event between skills."""
        if len(skill_ids) < 2:
            return

        # Generate canonical pair key
        sorted_ids = sorted(skill_ids)
        pair_key = "+".join(sorted_ids)

        conn = self._get_conn()

        # Update collaboration record
        row = conn.execute(
            "SELECT * FROM collaboration_metrics WHERE pair_key = ?",
            (pair_key,),
        ).fetchone()

        if row:
            total_runs = row["total_runs"] + 1
            successes = int(row["success_rate"] * row["total_runs"]) + (1 if success else 0)
            success_rate = successes / total_runs
            old_avg = row["avg_duration_ms"]
            avg_duration = old_avg + (duration_ms - old_avg) / total_runs
        else:
            total_runs = 1
            success_rate = 1.0 if success else 0.0
            avg_duration = float(duration_ms)

        conn.execute(
            """INSERT OR REPLACE INTO collaboration_metrics
               (pair_key, skill_ids_json, success_rate, total_runs,
                avg_duration_ms, last_used)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (
                pair_key,
                json.dumps(sorted_ids),
                success_rate,
                total_runs,
                avg_duration,
            ),
        )
        conn.commit()

        self._on_event(
            "collaboration",
            f"Collaboration {pair_key}: {'success' if success else 'failure'} "
            f"(rate={success_rate:.2f}, runs={total_runs})",
        )

    def get_collaboration(self, skill_ids: list[str]) -> dict[str, Any] | None:
        """Get collaboration metrics for a skill pair/group."""
        sorted_ids = sorted(skill_ids)
        pair_key = "+".join(sorted_ids)

        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM collaboration_metrics WHERE pair_key = ?",
            (pair_key,),
        ).fetchone()

        if not row:
            return None

        return {
            "pair_key": row["pair_key"],
            "skill_ids": json.loads(row["skill_ids_json"]),
            "success_rate": row["success_rate"],
            "total_runs": row["total_runs"],
            "avg_duration_ms": row["avg_duration_ms"],
            "last_used": row["last_used"],
        }

    def get_all_collaborations(self) -> list[dict[str, Any]]:
        """Get all collaboration metrics."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM collaboration_metrics ORDER BY success_rate DESC"
        ).fetchall()

        return [
            {
                "pair_key": row["pair_key"],
                "skill_ids": json.loads(row["skill_ids_json"]),
                "success_rate": row["success_rate"],
                "total_runs": row["total_runs"],
                "avg_duration_ms": row["avg_duration_ms"],
                "last_used": row["last_used"],
            }
            for row in rows
        ]

    def get_best_collaborations(
        self, min_runs: int = 3, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get top performing collaborations."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM collaboration_metrics
               WHERE total_runs >= ?
               ORDER BY success_rate DESC LIMIT ?""",
            (min_runs, limit),
        ).fetchall()

        return [
            {
                "pair_key": row["pair_key"],
                "skill_ids": json.loads(row["skill_ids_json"]),
                "success_rate": row["success_rate"],
                "total_runs": row["total_runs"],
            }
            for row in rows
        ]

    def get_worst_collaborations(
        self, min_runs: int = 3, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get worst performing collaborations."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM collaboration_metrics
               WHERE total_runs >= ?
               ORDER BY success_rate ASC LIMIT ?""",
            (min_runs, limit),
        ).fetchall()

        return [
            {
                "pair_key": row["pair_key"],
                "skill_ids": json.loads(row["skill_ids_json"]),
                "success_rate": row["success_rate"],
                "total_runs": row["total_runs"],
            }
            for row in rows
        ]

    def get_skill_network(self, skill_id: str) -> dict[str, Any]:
        """Get collaboration network for a specific skill."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM collaboration_metrics"
        ).fetchall()

        connections = []
        for row in rows:
            skill_ids = json.loads(row["skill_ids_json"])
            if skill_id in skill_ids:
                partners = [s for s in skill_ids if s != skill_id]
                connections.append({
                    "partners": partners,
                    "success_rate": row["success_rate"],
                    "total_runs": row["total_runs"],
                })

        # Sort by success rate
        connections.sort(key=lambda x: x["success_rate"], reverse=True)

        return {
            "skill_id": skill_id,
            "total_collaborations": len(connections),
            "connections": connections,
        }

    def suggest_collaborations(
        self, skill_id: str, all_skill_ids: list[str], min_runs: int = 2
    ) -> list[dict[str, Any]]:
        """Suggest skills to collaborate with."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM collaboration_metrics"
        ).fetchall()

        known_partners: dict[str, dict[str, Any]] = {}
        for row in rows:
            skill_ids = json.loads(row["skill_ids_json"])
            if skill_id in skill_ids:
                for partner in skill_ids:
                    if partner != skill_id:
                        if partner not in known_partners or row["total_runs"] > known_partners[partner]["total_runs"]:
                            known_partners[partner] = {
                                "partner": partner,
                                "success_rate": row["success_rate"],
                                "total_runs": row["total_runs"],
                            }

        # Find untried collaborations
        untried = [
            sid for sid in all_skill_ids
            if sid != skill_id and sid not in known_partners
        ]

        # Rank by global success rate of the untried skill
        suggestions = []
        for partner_id in untried:
            suggestions.append({
                "partner": partner_id,
                "reason": "untried",
                "success_rate": 0.0,
            })

        # Also suggest known good partners
        for partner_id, data in known_partners.items():
            if data["success_rate"] > 0.7:
                suggestions.insert(0, {
                    "partner": partner_id,
                    "reason": "proven",
                    "success_rate": data["success_rate"],
                    "total_runs": data["total_runs"],
                })

        return suggestions[:10]

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
