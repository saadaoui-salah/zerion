"""A/B testing framework for comparing skills."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from zerion_core.benchmark.engine import BenchmarkEngine
from zerion_core.benchmark.models import ABTestResult, BenchmarkMetrics


class ABTestingFramework:
    """Supports comparing skills on identical tasks."""

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

    def record_test(
        self,
        skill_a_id: str,
        skill_b_id: str,
        task_type: str,
        skill_a_metrics: BenchmarkMetrics,
        skill_b_metrics: BenchmarkMetrics,
        task_description: str = "",
    ) -> ABTestResult:
        """Record an A/B test result.

        Scores are computed from the metrics and a winner is determined.
        """
        # Compute scores from metrics
        score_a = self._compute_ab_score(skill_a_metrics)
        score_b = self._compute_ab_score(skill_b_metrics)

        # Determine winner
        if abs(score_a - score_b) < 0.05:
            winner = "tie"
            confidence = 0.5
        elif score_a > score_b:
            winner = skill_a_id
            confidence = min(0.95, 0.5 + (score_a - score_b) * 2)
        else:
            winner = skill_b_id
            confidence = min(0.95, 0.5 + (score_b - score_a) * 2)

        result = ABTestResult(
            skill_a_id=skill_a_id,
            skill_b_id=skill_b_id,
            task_type=task_type,
            task_description=task_description,
            skill_a_score=score_a,
            skill_b_score=score_b,
            skill_a_metrics=skill_a_metrics,
            skill_b_metrics=skill_b_metrics,
            winner=winner,
            confidence=confidence,
        )

        # Persist
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO ab_tests
               (test_id, skill_a_id, skill_b_id, task_type, task_description,
                skill_a_score, skill_b_score, skill_a_metrics_json,
                skill_b_metrics_json, winner, confidence, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.test_id,
                result.skill_a_id,
                result.skill_b_id,
                result.task_type,
                result.task_description,
                result.skill_a_score,
                result.skill_b_score,
                result.skill_a_metrics.model_dump_json(),
                result.skill_b_metrics.model_dump_json(),
                result.winner,
                result.confidence,
                result.timestamp,
            ),
        )
        conn.commit()

        self._on_event(
            "ab_test",
            f"A/B test {result.test_id}: {winner} won (confidence={confidence:.2f})",
        )

        return result

    def _compute_ab_score(self, metrics: BenchmarkMetrics) -> float:
        """Compute a score for A/B comparison from metrics."""
        score = 0.0

        # Test pass rate (40%)
        if metrics.total_tests > 0:
            score += 0.4 * (metrics.tests_passed / metrics.total_tests)

        # Build success (20%)
        if metrics.build_success:
            score += 0.2
        if metrics.lint_success:
            score += 0.1

        # Speed (20%) — assume 30s is baseline
        if metrics.total_time_ms > 0:
            speed_score = max(0.0, 1.0 - (metrics.total_time_ms / 30000.0))
            score += 0.2 * speed_score

        # User acceptance (10%)
        if metrics.user_accepted:
            score += 0.1

        # Error penalty (10%)
        error_count = (
            metrics.hallucination_count
            + metrics.invalid_patch_count
            + metrics.failed_command_count
        )
        error_penalty = min(0.1, error_count * 0.02)
        score -= error_penalty

        return max(0.0, min(1.0, score))

    def get_test(self, test_id: str) -> ABTestResult | None:
        """Get a specific A/B test result."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM ab_tests WHERE test_id = ?", (test_id,)
        ).fetchone()

        if not row:
            return None

        return self._row_to_result(row)

    def get_tests_for_skill(
        self, skill_id: str, limit: int = 50
    ) -> list[ABTestResult]:
        """Get all A/B tests involving a skill."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM ab_tests
               WHERE skill_a_id = ? OR skill_b_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (skill_id, skill_id, limit),
        ).fetchall()

        return [self._row_to_result(row) for row in rows]

    def get_head_to_head(
        self, skill_a_id: str, skill_b_id: str
    ) -> dict[str, Any]:
        """Get head-to-head comparison between two skills."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM ab_tests
               WHERE (skill_a_id = ? AND skill_b_id = ?)
                  OR (skill_a_id = ? AND skill_b_id = ?)""",
            (skill_a_id, skill_b_id, skill_b_id, skill_a_id),
        ).fetchall()

        if not rows:
            return {
                "skill_a": skill_a_id,
                "skill_b": skill_b_id,
                "total_tests": 0,
                "skill_a_wins": 0,
                "skill_b_wins": 0,
                "ties": 0,
            }

        a_wins = 0
        b_wins = 0
        ties = 0
        a_scores = []
        b_scores = []

        for row in rows:
            result = self._row_to_result(row)
            a_scores.append(result.skill_a_score)
            b_scores.append(result.skill_b_score)

            if result.winner == skill_a_id:
                a_wins += 1
            elif result.winner == skill_b_id:
                b_wins += 1
            else:
                ties += 1

        return {
            "skill_a": skill_a_id,
            "skill_b": skill_b_id,
            "total_tests": len(rows),
            "skill_a_wins": a_wins,
            "skill_b_wins": b_wins,
            "ties": ties,
            "avg_score_a": sum(a_scores) / len(a_scores) if a_scores else 0.0,
            "avg_score_b": sum(b_scores) / len(b_scores) if b_scores else 0.0,
        }

    def get_leaderboard(self, task_type: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """Get skill rankings from A/B test results."""
        conn = self._get_conn()
        if task_type:
            rows = conn.execute(
                """SELECT * FROM ab_tests WHERE task_type = ? ORDER BY timestamp DESC""",
                (task_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ab_tests ORDER BY timestamp DESC"
            ).fetchall()

        # Tally wins
        wins: dict[str, int] = {}
        totals: dict[str, int] = {}
        scores: dict[str, list[float]] = {}

        for row in rows:
            result = self._row_to_result(row)
            for sid in [result.skill_a_id, result.skill_b_id]:
                totals[sid] = totals.get(sid, 0) + 1
                if sid not in scores:
                    scores[sid] = []

            if result.winner == result.skill_a_id:
                wins[result.skill_a_id] = wins.get(result.skill_a_id, 0) + 1
                scores[result.skill_a_id].append(result.skill_a_score)
            elif result.winner == result.skill_b_id:
                wins[result.skill_b_id] = wins.get(result.skill_b_id, 0) + 1
                scores[result.skill_b_id].append(result.skill_b_score)
            else:
                scores[result.skill_a_id].append(result.skill_a_score)
                scores[result.skill_b_id].append(result.skill_b_score)

        # Rank by win rate
        leaderboard = []
        for sid in totals:
            win_count = wins.get(sid, 0)
            total = totals[sid]
            avg_score = sum(scores[sid]) / len(scores[sid]) if scores[sid] else 0.0
            leaderboard.append({
                "skill_id": sid,
                "wins": win_count,
                "total_tests": total,
                "win_rate": win_count / total if total > 0 else 0.0,
                "avg_score": avg_score,
            })

        return sorted(leaderboard, key=lambda x: x["win_rate"], reverse=True)[:limit]

    def _row_to_result(self, row: sqlite3.Row) -> ABTestResult:
        """Convert a database row to ABTestResult."""
        return ABTestResult(
            test_id=row["test_id"],
            skill_a_id=row["skill_a_id"],
            skill_b_id=row["skill_b_id"],
            task_type=row["task_type"],
            task_description=row["task_description"],
            skill_a_score=row["skill_a_score"],
            skill_b_score=row["skill_b_score"],
            skill_a_metrics=BenchmarkMetrics.model_validate_json(row["skill_a_metrics_json"]),
            skill_b_metrics=BenchmarkMetrics.model_validate_json(row["skill_b_metrics_json"]),
            winner=row["winner"],
            confidence=row["confidence"],
            timestamp=row["timestamp"],
        )

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
