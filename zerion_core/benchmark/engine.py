"""Core benchmark engine for tracking skill performance."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable

from zerion_core.benchmark.models import (
    BenchmarkEvent,
    BenchmarkMetrics,
    BenchmarkOutcome,
    FailureRecord,
    OutcomeType,
    TaskType,
)
from zerion_core.config import settings


class BenchmarkEngine:
    """Tracks benchmark events for every skill execution."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        on_event: Callable[[str, str], None] | None = None,
    ):
        self._db_path = Path(db_path) if db_path else settings.memory_root / "benchmark.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._on_event = on_event or (lambda s, m: None)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS benchmark_events (
                benchmark_id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                project_id TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                task_id TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                task_type TEXT DEFAULT 'other',
                duration_ms INTEGER DEFAULT 0,
                metrics_json TEXT DEFAULT '{}',
                outcome_json TEXT DEFAULT '{}',
                workflow_id TEXT DEFAULT '',
                files_modified_json TEXT DEFAULT '[]',
                error_output TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS skill_scores (
                skill_id TEXT NOT NULL,
                project_id TEXT DEFAULT '',
                test_pass_rate REAL DEFAULT 0.0,
                patch_acceptance_rate REAL DEFAULT 0.0,
                build_success_rate REAL DEFAULT 0.0,
                bug_non_recurrence REAL DEFAULT 0.0,
                execution_efficiency REAL DEFAULT 0.0,
                user_feedback REAL DEFAULT 0.0,
                total_score REAL DEFAULT 0.0,
                sample_count INTEGER DEFAULT 0,
                last_updated TEXT DEFAULT '',
                PRIMARY KEY (skill_id, project_id)
            );

            CREATE TABLE IF NOT EXISTS skill_reputation (
                skill_id TEXT PRIMARY KEY,
                global_reputation REAL DEFAULT 50.0,
                project_reputations_json TEXT DEFAULT '{}',
                confidence REAL DEFAULT 0.0,
                sample_size INTEGER DEFAULT 0,
                trend TEXT DEFAULT 'stable',
                last_updated TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS workflow_benchmarks (
                workflow_id TEXT PRIMARY KEY,
                workflow_name TEXT DEFAULT '',
                skill_ids_json TEXT DEFAULT '[]',
                success_rate REAL DEFAULT 0.0,
                avg_time_ms REAL DEFAULT 0.0,
                regression_rate REAL DEFAULT 0.0,
                total_runs INTEGER DEFAULT 0,
                score REAL DEFAULT 0.0,
                last_used TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS failure_analysis (
                failure_id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                project_id TEXT DEFAULT '',
                timestamp TEXT DEFAULT '',
                task_description TEXT DEFAULT '',
                failure_type TEXT DEFAULT '',
                root_cause TEXT DEFAULT '',
                tools_used_json TEXT DEFAULT '[]',
                workflow_used TEXT DEFAULT '',
                files_modified_json TEXT DEFAULT '[]',
                error_output TEXT DEFAULT '',
                fix_suggestion TEXT DEFAULT '',
                cluster_id TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS ab_tests (
                test_id TEXT PRIMARY KEY,
                skill_a_id TEXT NOT NULL,
                skill_b_id TEXT NOT NULL,
                task_type TEXT DEFAULT '',
                task_description TEXT DEFAULT '',
                skill_a_score REAL DEFAULT 0.0,
                skill_b_score REAL DEFAULT 0.0,
                skill_a_metrics_json TEXT DEFAULT '{}',
                skill_b_metrics_json TEXT DEFAULT '{}',
                winner TEXT DEFAULT '',
                confidence REAL DEFAULT 0.0,
                timestamp TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS benchmark_consolidated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                project_id TEXT DEFAULT '',
                period_start TEXT DEFAULT '',
                period_end TEXT DEFAULT '',
                total_events INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0.0,
                success_rate REAL DEFAULT 0.0,
                avg_time_ms REAL DEFAULT 0.0,
                top_task_type TEXT DEFAULT '',
                key_findings_json TEXT DEFAULT '[]',
                recommendations_json TEXT DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_benchmark_skill ON benchmark_events(skill_id);
            CREATE INDEX IF NOT EXISTS idx_benchmark_project ON benchmark_events(project_id);
            CREATE INDEX IF NOT EXISTS idx_benchmark_timestamp ON benchmark_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_failure_skill ON failure_analysis(skill_id);
            CREATE INDEX IF NOT EXISTS idx_failure_cluster ON failure_analysis(cluster_id);
        """)
        conn.commit()

    def record_event(self, event: BenchmarkEvent) -> None:
        """Record a benchmark event."""
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO benchmark_events
               (benchmark_id, skill_id, project_id, session_id, task_id,
                timestamp, task_type, duration_ms, metrics_json, outcome_json,
                workflow_id, files_modified_json, error_output, tags_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.benchmark_id,
                event.skill_id,
                event.project_id,
                event.session_id,
                event.task_id,
                event.timestamp,
                event.task_type.value,
                event.duration_ms,
                event.metrics.model_dump_json(),
                event.outcome.model_dump_json(),
                event.workflow_id,
                json.dumps(event.files_modified),
                event.error_output,
                json.dumps(event.tags),
            ),
        )
        conn.commit()
        self._on_event("benchmark", f"Recorded event {event.benchmark_id} for {event.skill_id}")

    def record_execution(
        self,
        skill_id: str,
        project_id: str = "",
        session_id: str = "",
        task_type: TaskType = TaskType.OTHER,
        duration_ms: int = 0,
        metrics: BenchmarkMetrics | None = None,
        outcome: BenchmarkOutcome | None = None,
        workflow_id: str = "",
        files_modified: list[str] | None = None,
        error_output: str = "",
    ) -> BenchmarkEvent:
        """Convenience method to record a skill execution."""
        event = BenchmarkEvent(
            skill_id=skill_id,
            project_id=project_id,
            session_id=session_id,
            task_type=task_type,
            duration_ms=duration_ms,
            metrics=metrics or BenchmarkMetrics(),
            outcome=outcome or BenchmarkOutcome(),
            workflow_id=workflow_id,
            files_modified=files_modified or [],
            error_output=error_output,
        )
        self.record_event(event)
        return event

    def get_events(
        self,
        skill_id: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BenchmarkEvent]:
        """Retrieve benchmark events with filters."""
        conn = self._get_conn()
        query = "SELECT * FROM benchmark_events WHERE 1=1"
        params: list[Any] = []

        if skill_id:
            query += " AND skill_id = ?"
            params.append(skill_id)
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        events = []
        for row in rows:
            event = BenchmarkEvent(
                benchmark_id=row["benchmark_id"],
                skill_id=row["skill_id"],
                project_id=row["project_id"],
                session_id=row["session_id"],
                task_id=row["task_id"],
                timestamp=row["timestamp"],
                task_type=TaskType(row["task_type"]),
                duration_ms=row["duration_ms"],
                metrics=BenchmarkMetrics.model_validate_json(row["metrics_json"]),
                outcome=BenchmarkOutcome.model_validate_json(row["outcome_json"]),
                workflow_id=row["workflow_id"],
                files_modified=json.loads(row["files_modified_json"]),
                error_output=row["error_output"],
                tags=json.loads(row["tags_json"]),
            )
            events.append(event)
        return events

    def get_skill_stats(self, skill_id: str, project_id: str | None = None) -> dict[str, Any]:
        """Get aggregate statistics for a skill."""
        conn = self._get_conn()
        query = "SELECT * FROM benchmark_events WHERE skill_id = ?"
        params: list[Any] = [skill_id]

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        rows = conn.execute(query, params).fetchall()
        if not rows:
            return {"total_executions": 0, "avg_duration_ms": 0}

        total = len(rows)
        durations = [row["duration_ms"] for row in rows]
        metrics_list = [BenchmarkMetrics.model_validate_json(row["metrics_json"]) for row in rows]
        outcomes = [BenchmarkOutcome.model_validate_json(row["outcome_json"]) for row in rows]

        # Compute aggregates
        total_tests = sum(m.total_tests for m in metrics_list)
        passed_tests = sum(m.tests_passed for m in metrics_list)
        successful_outcomes = sum(1 for o in outcomes if o.outcome_type == OutcomeType.SUCCESS)
        reverted = sum(1 for o in outcomes if o.outcome_type == OutcomeType.REVERTED)
        build_successes = sum(1 for m in metrics_list if m.build_success)
        regressions = sum(1 for m in metrics_list if m.regression_detected)

        # Task type distribution
        task_types: dict[str, int] = {}
        for row in rows:
            tt = row["task_type"]
            task_types[tt] = task_types.get(tt, 0) + 1

        top_task = max(task_types, key=task_types.get) if task_types else "other"

        return {
            "total_executions": total,
            "avg_duration_ms": sum(durations) / total if total else 0,
            "total_tests": total_tests,
            "test_pass_rate": passed_tests / total_tests if total_tests > 0 else 0.0,
            "success_rate": successful_outcomes / total if total else 0.0,
            "revert_rate": reverted / total if total else 0.0,
            "build_success_rate": build_successes / total if total else 0.0,
            "regression_rate": regressions / total if total else 0.0,
            "top_task_type": top_task,
            "task_type_distribution": task_types,
        }

    def get_project_stats(self, project_id: str) -> dict[str, Any]:
        """Get aggregate statistics for a project."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM benchmark_events WHERE project_id = ?", (project_id,)
        ).fetchall()

        if not rows:
            return {"total_executions": 0, "skills_used": 0}

        skills_used: dict[str, int] = {}
        for row in rows:
            sid = row["skill_id"]
            skills_used[sid] = skills_used.get(sid, 0) + 1

        return {
            "total_executions": len(rows),
            "skills_used": len(skills_used),
            "skill_usage": skills_used,
            "most_used_skill": max(skills_used, key=skills_used.get) if skills_used else "",
        }

    def get_trend(
        self, skill_id: str, days: int = 30, project_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get performance trend over time."""
        conn = self._get_conn()
        query = """
            SELECT DATE(timestamp) as date, COUNT(*) as count,
                   AVG(duration_ms) as avg_duration
            FROM benchmark_events
            WHERE skill_id = ? AND timestamp >= datetime('now', ?)
        """
        params: list[Any] = [skill_id, f"-{days} days"]

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        query += " GROUP BY DATE(timestamp) ORDER BY date"
        rows = conn.execute(query, params).fetchall()

        return [
            {
                "date": row["date"],
                "executions": row["count"],
                "avg_duration_ms": row["avg_duration"],
            }
            for row in rows
        ]

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
