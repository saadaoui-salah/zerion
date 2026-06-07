"""Workflow benchmarking — measure and compare workflows."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from zerion_core.benchmark.engine import BenchmarkEngine
from zerion_core.benchmark.models import WorkflowBenchmark


class WorkflowBenchmarker:
    """Measures and compares workflow performance."""

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

    def record_workflow_run(
        self,
        workflow_id: str,
        workflow_name: str,
        skill_ids: list[str],
        success: bool,
        duration_ms: int,
        regression_detected: bool = False,
    ) -> None:
        """Record a single workflow execution."""
        conn = self._get_conn()

        # Get existing record
        row = conn.execute(
            "SELECT * FROM workflow_benchmarks WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()

        if row:
            total_runs = row["total_runs"] + 1
            successes = int(row["success_rate"] * row["total_runs"]) + (1 if success else 0)
            regressions = int(row["regression_rate"] * row["total_runs"]) + (1 if regression_detected else 0)
            old_avg_time = row["avg_time_ms"]
            new_avg_time = old_avg_time + (duration_ms - old_avg_time) / total_runs

            success_rate = successes / total_runs
            regression_rate = regressions / total_runs

            # Score: high success, low regression, fast
            score = success_rate * 0.6 + (1.0 - regression_rate) * 0.3 + max(0.0, 1.0 - new_avg_time / 60000.0) * 0.1
        else:
            total_runs = 1
            success_rate = 1.0 if success else 0.0
            regression_rate = 1.0 if regression_detected else 0.0
            new_avg_time = float(duration_ms)
            score = success_rate * 0.6 + (1.0 - regression_rate) * 0.3

        conn.execute(
            """INSERT OR REPLACE INTO workflow_benchmarks
               (workflow_id, workflow_name, skill_ids_json, success_rate,
                avg_time_ms, regression_rate, total_runs, score, last_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                workflow_id,
                workflow_name,
                json.dumps(skill_ids),
                success_rate,
                new_avg_time,
                regression_rate,
                total_runs,
                score,
            ),
        )
        conn.commit()
        self._on_event(
            "workflow",
            f"Workflow {workflow_name}: {'success' if success else 'failure'} "
            f"(score={score:.2f}, runs={total_runs})",
        )

    def get_workflow(self, workflow_id: str) -> WorkflowBenchmark | None:
        """Get a specific workflow benchmark."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM workflow_benchmarks WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()

        if not row:
            return None

        return self._row_to_benchmark(row)

    def get_all_workflows(self) -> list[WorkflowBenchmark]:
        """Get all workflow benchmarks."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM workflow_benchmarks ORDER BY score DESC"
        ).fetchall()

        return [self._row_to_benchmark(row) for row in rows]

    def get_best_workflow_for_task(
        self, skill_ids: list[str] | None = None
    ) -> WorkflowBenchmark | None:
        """Find the best performing workflow, optionally filtered by skills."""
        conn = self._get_conn()

        if skill_ids:
            # Find workflows that use all specified skills
            rows = conn.execute(
                "SELECT * FROM workflow_benchmarks ORDER BY score DESC"
            ).fetchall()
            matching = []
            for row in rows:
                wf_skills = json.loads(row["skill_ids_json"])
                if all(s in wf_skills for s in skill_ids):
                    matching.append(row)
            if matching:
                return self._row_to_benchmark(matching[0])
            return None
        else:
            row = conn.execute(
                "SELECT * FROM workflow_benchmarks ORDER BY score DESC LIMIT 1"
            ).fetchone()
            return self._row_to_benchmark(row) if row else None

    def compare_workflows(
        self, workflow_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Compare multiple workflows."""
        results = []
        for wf_id in workflow_ids:
            wf = self.get_workflow(wf_id)
            if wf:
                results.append(wf.model_dump())
        return sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    def get_workflow_trend(
        self, workflow_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get recent executions for a workflow from benchmark events."""
        events = self._engine.get_events(limit=500)
        workflow_events = [e for e in events if e.workflow_id == workflow_id]

        # Group by date
        daily: dict[str, list[dict[str, Any]]] = {}
        for event in workflow_events[-limit:]:
            date = event.timestamp[:10]
            if date not in daily:
                daily[date] = []
            daily[date].append({
                "benchmark_id": event.benchmark_id,
                "success": event.outcome.outcome_type.value == "success",
                "duration_ms": event.duration_ms,
            })

        trend = []
        for date, runs in sorted(daily.items()):
            successes = sum(1 for r in runs if r["success"])
            trend.append({
                "date": date,
                "runs": len(runs),
                "success_rate": successes / len(runs) if runs else 0.0,
                "avg_duration_ms": sum(r["duration_ms"] for r in runs) / len(runs),
            })

        return trend

    def _row_to_benchmark(self, row: sqlite3.Row) -> WorkflowBenchmark:
        """Convert a database row to WorkflowBenchmark."""
        return WorkflowBenchmark(
            workflow_id=row["workflow_id"],
            workflow_name=row["workflow_name"],
            skill_ids=json.loads(row["skill_ids_json"]),
            success_rate=row["success_rate"],
            avg_time_ms=row["avg_time_ms"],
            regression_rate=row["regression_rate"],
            total_runs=row["total_runs"],
            score=row["score"],
            last_used=row["last_used"],
        )

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
