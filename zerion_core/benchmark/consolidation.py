"""Benchmark consolidation — TurboQuant-inspired optimization.

Compresses old benchmark records, clusters similar events,
summarizes historical performance, and preserves high-information data.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from zerion_core.benchmark.engine import BenchmarkEngine
from zerion_core.benchmark.models import BenchmarkConsolidated


class BenchmarkConsolidator:
    """Consolidates old benchmark data to reduce storage and improve query speed."""

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

    def consolidate(
        self,
        skill_id: str,
        project_id: str = "",
        older_than_days: int = 30,
    ) -> BenchmarkConsolidated | None:
        """Consolidate old benchmark events into a summary.

        Keeps recent events intact, compresses older ones into summaries.
        """
        conn = self._get_conn()

        # Get old events
        query = """
            SELECT * FROM benchmark_events
            WHERE skill_id = ?
              AND timestamp < datetime('now', ?)
        """
        params: list[Any] = [skill_id, f"-{older_than_days} days"]

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        rows = conn.execute(query, params).fetchall()

        if not rows:
            return None

        # Compute consolidated metrics
        total = len(rows)
        durations = [row["duration_ms"] for row in rows]
        metrics_list = [
            json.loads(row["metrics_json"]) for row in rows
        ]
        outcomes = [
            json.loads(row["outcome_json"]) for row in rows
        ]

        total_tests = sum(m.get("total_tests", 0) for m in metrics_list)
        passed_tests = sum(m.get("tests_passed", 0) for m in metrics_list)
        successful = sum(
            1 for o in outcomes
            if o.get("outcome_type") == "success"
        )
        build_successes = sum(
            1 for m in metrics_list if m.get("build_success")
        )

        # Task type distribution
        task_types: dict[str, int] = {}
        for row in rows:
            tt = row["task_type"]
            task_types[tt] = task_types.get(tt, 0) + 1
        top_task = max(task_types, key=task_types.get) if task_types else "other"

        # Generate findings
        findings = []
        if total_tests > 0:
            test_rate = passed_tests / total_tests
            findings.append(f"Test pass rate: {test_rate:.1%}")

        success_rate = successful / total if total else 0
        findings.append(f"Success rate: {success_rate:.1%}")

        avg_time = sum(durations) / total if total else 0
        findings.append(f"Avg execution time: {avg_time:.0f}ms")

        build_rate = build_successes / total if total else 0
        findings.append(f"Build success rate: {build_rate:.1%}")

        # Generate recommendations
        recommendations = []
        if success_rate < 0.7:
            recommendations.append("Consider reviewing skill configuration")
        if avg_time > 30000:
            recommendations.append("Execution time is high — optimize retrieval")
        if build_rate < 0.8:
            recommendations.append("Build failures are frequent — check tool integration")

        # Create summary
        consolidated = BenchmarkConsolidated(
            skill_id=skill_id,
            project_id=project_id,
            period_start=rows[-1]["timestamp"] if rows else "",
            period_end=rows[0]["timestamp"] if rows else "",
            total_events=total,
            avg_score=sum(
                o.get("effectiveness_score", 0) for o in outcomes
            ) / total if total else 0.0,
            success_rate=success_rate,
            avg_time_ms=avg_time,
            top_task_type=top_task,
            key_findings=findings,
            recommendations=recommendations,
        )

        # Persist consolidated record
        conn.execute(
            """INSERT INTO benchmark_consolidated
               (skill_id, project_id, period_start, period_end,
                total_events, avg_score, success_rate, avg_time_ms,
                top_task_type, key_findings_json, recommendations_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                consolidated.skill_id,
                consolidated.project_id,
                consolidated.period_start,
                consolidated.period_end,
                consolidated.total_events,
                consolidated.avg_score,
                consolidated.success_rate,
                consolidated.avg_time_ms,
                consolidated.top_task_type,
                json.dumps(consolidated.key_findings),
                json.dumps(consolidated.recommendations),
            ),
        )

        # Delete consolidated events
        benchmark_ids = [row["benchmark_id"] for row in rows]
        placeholders = ",".join("?" * len(benchmark_ids))
        conn.execute(
            f"DELETE FROM benchmark_events WHERE benchmark_id IN ({placeholders})",
            benchmark_ids,
        )

        conn.commit()

        self._on_event(
            "consolidation",
            f"Consolidated {total} events for {skill_id} "
            f"(avg_score={consolidated.avg_score:.2f})",
        )

        return consolidated

    def consolidate_all(self, older_than_days: int = 30) -> list[BenchmarkConsolidated]:
        """Consolidate all skills' old benchmark data."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT DISTINCT skill_id, project_id FROM benchmark_events
               WHERE timestamp < datetime('now', ?)""",
            (f"-{older_than_days} days",),
        ).fetchall()

        results = []
        for row in rows:
            result = self.consolidate(
                row["skill_id"],
                row["project_id"],
                older_than_days,
            )
            if result:
                results.append(result)

        return results

    def get_consolidated(
        self, skill_id: str, project_id: str = ""
    ) -> list[BenchmarkConsolidated]:
        """Get consolidated records for a skill."""
        conn = self._get_conn()
        query = "SELECT * FROM benchmark_consolidated WHERE skill_id = ?"
        params: list[Any] = [skill_id]

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        query += " ORDER BY period_end DESC"
        rows = conn.execute(query, params).fetchall()

        return [
            BenchmarkConsolidated(
                skill_id=row["skill_id"],
                project_id=row["project_id"],
                period_start=row["period_start"],
                period_end=row["period_end"],
                total_events=row["total_events"],
                avg_score=row["avg_score"],
                success_rate=row["success_rate"],
                avg_time_ms=row["avg_time_ms"],
                top_task_type=row["top_task_type"],
                key_findings=json.loads(row["key_findings_json"]),
                recommendations=json.loads(row["recommendations_json"]),
            )
            for row in rows
        ]

    def cluster_similar_events(
        self, skill_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Cluster similar benchmark events for the same skill.

        Groups events by task_type and outcome similarity.
        """
        events = self._engine.get_events(skill_id=skill_id, limit=limit)

        # Group by task type and outcome
        clusters: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            key = f"{event.task_type.value}:{event.outcome.outcome_type.value}"
            if key not in clusters:
                clusters[key] = []
            clusters[key].append({
                "benchmark_id": event.benchmark_id,
                "duration_ms": event.duration_ms,
                "test_pass_rate": event.metrics.test_pass_rate,
                "outcome": event.outcome.outcome_type.value,
                "timestamp": event.timestamp,
            })

        # Summarize each cluster
        result = []
        for key, items in clusters.items():
            task_type, outcome = key.split(":")
            durations = [i["duration_ms"] for i in items]
            test_rates = [i["test_pass_rate"] for i in items]

            result.append({
                "cluster_key": key,
                "task_type": task_type,
                "outcome": outcome,
                "count": len(items),
                "avg_duration_ms": sum(durations) / len(durations),
                "avg_test_pass_rate": sum(test_rates) / len(test_rates),
                "date_range": (
                    items[-1]["timestamp"][:10],
                    items[0]["timestamp"][:10],
                ),
            })

        return sorted(result, key=lambda x: x["count"], reverse=True)

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
