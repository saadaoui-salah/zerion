"""Failure analysis engine — store, cluster, and analyze failures."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from zerion_core.benchmark.engine import BenchmarkEngine
from zerion_core.benchmark.models import FailureRecord


class FailureAnalyzer:
    """Records failures, clusters them, and generates recommendations."""

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

    def record_failure(
        self,
        skill_id: str,
        task_description: str = "",
        failure_type: str = "",
        root_cause: str = "",
        tools_used: list[str] | None = None,
        workflow_used: str = "",
        files_modified: list[str] | None = None,
        error_output: str = "",
        project_id: str = "",
    ) -> FailureRecord:
        """Record a failure for analysis."""
        record = FailureRecord(
            skill_id=skill_id,
            project_id=project_id,
            task_description=task_description,
            failure_type=failure_type,
            root_cause=root_cause,
            tools_used=tools_used or [],
            workflow_used=workflow_used,
            files_modified=files_modified or [],
            error_output=error_output,
        )

        # Auto-cluster by keywords
        cluster_id = self._compute_cluster_id(failure_type, root_cause, error_output)
        record.cluster_id = cluster_id

        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO failure_analysis
               (failure_id, skill_id, project_id, timestamp, task_description,
                failure_type, root_cause, tools_used_json, workflow_used,
                files_modified_json, error_output, fix_suggestion, cluster_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.failure_id,
                record.skill_id,
                record.project_id,
                record.timestamp,
                record.task_description,
                record.failure_type,
                record.root_cause,
                json.dumps(record.tools_used),
                record.workflow_used,
                json.dumps(record.files_modified),
                record.error_output,
                record.fix_suggestion,
                record.cluster_id,
            ),
        )
        conn.commit()

        self._on_event(
            "failure",
            f"Recorded failure {record.failure_id} for {skill_id} "
            f"(type={failure_type}, cluster={cluster_id})",
        )

        return record

    def _compute_cluster_id(
        self, failure_type: str, root_cause: str, error_output: str
    ) -> str:
        """Compute a cluster ID based on failure characteristics."""
        # Simple keyword-based clustering
        keywords = []

        # From failure type
        if failure_type:
            keywords.extend(failure_type.lower().split())

        # From root cause
        if root_cause:
            keywords.extend(root_cause.lower().split()[:5])

        # From error output (first line)
        if error_output:
            first_line = error_output.split("\n")[0][:100]
            keywords.extend(first_line.lower().split()[:3])

        # Deduplicate and sort
        unique_keywords = sorted(set(keywords))[:8]
        return "-".join(unique_keywords) if unique_keywords else "unknown"

    def get_failures(
        self,
        skill_id: str | None = None,
        project_id: str | None = None,
        failure_type: str | None = None,
        limit: int = 100,
    ) -> list[FailureRecord]:
        """Retrieve failures with filters."""
        conn = self._get_conn()
        query = "SELECT * FROM failure_analysis WHERE 1=1"
        params: list[Any] = []

        if skill_id:
            query += " AND skill_id = ?"
            params.append(skill_id)
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if failure_type:
            query += " AND failure_type = ?"
            params.append(failure_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_clusters(
        self, skill_id: str | None = None, min_count: int = 2
    ) -> list[dict[str, Any]]:
        """Get failure clusters (groups of similar failures)."""
        conn = self._get_conn()
        query = """
            SELECT cluster_id, COUNT(*) as count,
                   GROUP_CONCAT(DISTINCT failure_type) as failure_types,
                   GROUP_CONCAT(DISTINCT skill_id) as skill_ids
            FROM failure_analysis
        """
        params: list[Any] = []

        if skill_id:
            query += " WHERE skill_id = ?"
            params.append(skill_id)

        query += " GROUP BY cluster_id HAVING COUNT(*) >= ? ORDER BY count DESC"
        params.append(min_count)

        rows = conn.execute(query, params).fetchall()

        clusters = []
        for row in rows:
            # Get sample failure for the cluster
            sample = conn.execute(
                """SELECT * FROM failure_analysis
                   WHERE cluster_id = ? LIMIT 1""",
                (row["cluster_id"],),
            ).fetchone()

            clusters.append({
                "cluster_id": row["cluster_id"],
                "count": row["count"],
                "failure_types": row["failure_types"],
                "skill_ids": row["skill_ids"],
                "sample_root_cause": sample["root_cause"] if sample else "",
                "sample_fix": sample["fix_suggestion"] if sample else "",
            })

        return clusters

    def get_failure_rate(self, skill_id: str) -> dict[str, Any]:
        """Get failure statistics for a skill."""
        conn = self._get_conn()

        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM failure_analysis WHERE skill_id = ?",
            (skill_id,),
        ).fetchone()["cnt"]

        by_type = conn.execute(
            """SELECT failure_type, COUNT(*) as cnt
               FROM failure_analysis WHERE skill_id = ?
               GROUP BY failure_type ORDER BY cnt DESC""",
            (skill_id,),
        ).fetchall()

        by_project = conn.execute(
            """SELECT project_id, COUNT(*) as cnt
               FROM failure_analysis WHERE skill_id = ?
               GROUP BY project_id ORDER BY cnt DESC""",
            (skill_id,),
        ).fetchall()

        return {
            "total_failures": total,
            "by_type": {row["failure_type"]: row["cnt"] for row in by_type},
            "by_project": {row["project_id"]: row["cnt"] for row in by_project},
        }

    def get_recommendations(self, skill_id: str) -> list[str]:
        """Generate recommendations based on failure analysis."""
        clusters = self.get_clusters(skill_id=skill_id)
        failure_stats = self.get_failure_rate(skill_id)

        recommendations = []

        # Check most common failure type
        if failure_stats["by_type"]:
            top_type = max(failure_stats["by_type"], key=failure_stats["by_type"].get)
            count = failure_stats["by_type"][top_type]
            recommendations.append(
                f"Most common failure: {top_type} ({count} occurrences). "
                f"Consider adding specific handling for this type."
            )

        # Check for recurring clusters
        for cluster in clusters[:3]:
            if cluster["count"] >= 3:
                recommendations.append(
                    f"Recurring failure cluster '{cluster['cluster_id']}' "
                    f"({cluster['count']} times). "
                    f"Root cause: {cluster['sample_root_cause']}"
                )

        # Check project-specific issues
        if failure_stats["by_project"]:
            top_project = max(
                failure_stats["by_project"], key=failure_stats["by_project"].get
            )
            count = failure_stats["by_project"][top_project]
            if count >= 3:
                recommendations.append(
                    f"Project '{top_project}' has {count} failures. "
                    f"Consider project-specific configuration."
                )

        if not recommendations:
            recommendations.append("No significant failure patterns detected.")

        return recommendations

    def update_fix_suggestion(
        self, failure_id: str, fix_suggestion: str
    ) -> None:
        """Update fix suggestion for a failure."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE failure_analysis SET fix_suggestion = ? WHERE failure_id = ?",
            (fix_suggestion, failure_id),
        )
        conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> FailureRecord:
        """Convert a database row to FailureRecord."""
        return FailureRecord(
            failure_id=row["failure_id"],
            skill_id=row["skill_id"],
            project_id=row["project_id"],
            timestamp=row["timestamp"],
            task_description=row["task_description"],
            failure_type=row["failure_type"],
            root_cause=row["root_cause"],
            tools_used=json.loads(row["tools_used_json"]),
            workflow_used=row["workflow_used"],
            files_modified=json.loads(row["files_modified_json"]),
            error_output=row["error_output"],
            fix_suggestion=row["fix_suggestion"],
            cluster_id=row["cluster_id"],
        )

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
