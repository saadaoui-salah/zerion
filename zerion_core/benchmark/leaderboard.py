"""Leaderboard and project health reporting."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from zerion_core.benchmark.engine import BenchmarkEngine
from zerion_core.benchmark.score_engine import ScoreEngine
from zerion_core.benchmark.reputation import ReputationEngine
from zerion_core.benchmark.models import LeaderboardEntry


class LeaderboardEngine:
    """Generates leaderboards and project health reports."""

    def __init__(
        self,
        benchmark_engine: BenchmarkEngine,
        score_engine: ScoreEngine,
        reputation_engine: ReputationEngine,
        on_event: Any = None,
    ):
        self._engine = benchmark_engine
        self._score_engine = score_engine
        self._reputation = reputation_engine
        self._on_event = on_event or (lambda s, m: None)
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._engine._db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def get_leaderboard(
        self,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[LeaderboardEntry]:
        """Get skill leaderboard."""
        scores = self._score_engine.get_all_scores(project_id=project_id)

        entries = []
        for rank, score in enumerate(scores[:limit], 1):
            trend = "stable"
            rep = self._reputation.get_reputation(score.skill_id)
            if rep:
                trend = rep.trend

            entries.append(LeaderboardEntry(
                rank=rank,
                skill_id=score.skill_id,
                score=score.total_score,
                tasks_completed=score.sample_count,
                success_rate=score.test_pass_rate,
                trend=trend,
            ))

        return entries

    def get_project_health(self, project_id: str) -> dict[str, Any]:
        """Generate a comprehensive project health report."""
        conn = self._get_conn()

        # Get project stats
        project_stats = self._engine.get_project_stats(project_id)

        # Get skill scores for project
        scores = self._score_engine.get_all_scores(project_id=project_id)

        # Get failures
        failure_rows = conn.execute(
            """SELECT failure_type, COUNT(*) as cnt
               FROM failure_analysis WHERE project_id = ?
               GROUP BY failure_type ORDER BY cnt DESC""",
            (project_id,),
        ).fetchall()

        # Get recent benchmark events
        recent_events = self._engine.get_events(project_id=project_id, limit=100)

        # Compute health metrics
        total_events = len(recent_events)
        successful = sum(
            1 for e in recent_events
            if e.outcome.outcome_type.value == "success"
        )

        # Find best and worst skills
        sorted_scores = sorted(scores, key=lambda s: s.total_score, reverse=True)
        best_skill = sorted_scores[0].skill_id if sorted_scores else "none"
        worst_skill = sorted_scores[-1].skill_id if sorted_scores else "none"

        # Regression trend
        regression_count = sum(
            1 for e in recent_events if e.metrics.regression_detected
        )
        regression_trend = "stable"
        if total_events > 0:
            regression_rate = regression_count / total_events
            if regression_rate > 0.1:
                regression_trend = "increasing"
            elif regression_rate < 0.02:
                regression_trend = "decreasing"

        return {
            "project_id": project_id,
            "total_executions": project_stats.get("total_executions", 0),
            "skills_used": project_stats.get("skills_used", 0),
            "overall_success_rate": successful / total_events if total_events > 0 else 0.0,
            "best_performing_skill": best_skill,
            "worst_performing_skill": worst_skill,
            "regression_trend": regression_trend,
            "regression_count": regression_count,
            "failure_breakdown": {
                row["failure_type"]: row["cnt"] for row in failure_rows
            },
            "skill_scores": [
                {
                    "skill_id": s.skill_id,
                    "score": s.total_score,
                    "sample_count": s.sample_count,
                }
                for s in sorted_scores
            ],
        }

    def get_skill_report(self, skill_id: str, project_id: str = "") -> dict[str, Any]:
        """Generate a detailed report for a specific skill."""
        # Get stats
        stats = self._engine.get_skill_stats(skill_id, project_id or None)

        # Get score
        score = self._score_engine.get_score(skill_id, project_id)

        # Get reputation
        rep = self._reputation.get_reputation(skill_id)

        # Get trend
        trend = self._engine.get_trend(skill_id, days=30, project_id=project_id or None)

        # Get failures
        failure_stats = self._engine._get_conn().execute(
            """SELECT COUNT(*) as cnt FROM failure_analysis
               WHERE skill_id = ?""",
            (skill_id,),
        ).fetchone()["cnt"]

        return {
            "skill_id": skill_id,
            "project_id": project_id,
            "total_executions": stats.get("total_executions", 0),
            "avg_duration_ms": stats.get("avg_duration_ms", 0),
            "test_pass_rate": stats.get("test_pass_rate", 0.0),
            "success_rate": stats.get("success_rate", 0.0),
            "revert_rate": stats.get("revert_rate", 0.0),
            "build_success_rate": stats.get("build_success_rate", 0.0),
            "regression_rate": stats.get("regression_rate", 0.0),
            "composite_score": score.total_score if score else 0.0,
            "reputation": rep.global_reputation if rep else 50.0,
            "reputation_trend": rep.trend if rep else "stable",
            "total_failures": failure_stats,
            "top_task_type": stats.get("top_task_type", "other"),
            "task_distribution": stats.get("task_type_distribution", {}),
            "trend": trend,
        }

    def get_regression_report(
        self, project_id: str | None = None, days: int = 7
    ) -> dict[str, Any]:
        """Report on regressions detected."""
        conn = self._get_conn()
        query = """
            SELECT skill_id, COUNT(*) as regression_count
            FROM benchmark_events
            WHERE regression_detected = 1
              AND timestamp >= datetime('now', ?)
        """
        params: list[Any] = [f"-{days} days"]

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        query += " GROUP BY skill_id ORDER BY regression_count DESC"
        rows = conn.execute(query, params).fetchall()

        return {
            "period_days": days,
            "project_id": project_id,
            "regressions_by_skill": [
                {"skill_id": row["skill_id"], "count": row["regression_count"]}
                for row in rows
            ],
            "total_regressions": sum(row["regression_count"] for row in rows),
        }

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
