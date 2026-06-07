"""Score calculation engine for composite skill scoring."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from zerion_core.benchmark.engine import BenchmarkEngine
from zerion_core.benchmark.models import BenchmarkEvent, SkillScore


class ScoreEngine:
    """Computes composite scores for skills."""

    # Default weights
    DEFAULT_WEIGHTS = {
        "test_pass_rate": 0.35,
        "patch_acceptance_rate": 0.20,
        "build_success_rate": 0.15,
        "bug_non_recurrence": 0.15,
        "execution_efficiency": 0.10,
        "user_feedback": 0.05,
    }

    def __init__(
        self,
        benchmark_engine: BenchmarkEngine,
        weights: dict[str, float] | None = None,
        on_event: Any = None,
    ):
        self._engine = benchmark_engine
        self._weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._on_event = on_event or (lambda s, m: None)
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._engine._db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def compute_score(
        self, skill_id: str, project_id: str = "", window_size: int = 50
    ) -> SkillScore:
        """Compute composite score for a skill from recent events."""
        events = self._engine.get_events(skill_id=skill_id, project_id=project_id, limit=window_size)

        if not events:
            return SkillScore(skill_id=skill_id, project_id=project_id, sample_count=0)

        # Aggregate metrics
        total_tests = 0
        passed_tests = 0
        build_successes = 0
        user_accepted = 0
        patches_reverted = 0
        bugs_fixed = 0
        bugs_reappeared = 0
        total_tokens = 0
        total_duration = 0
        successful = 0

        for event in events:
            m = event.metrics
            o = event.outcome

            total_tests += m.total_tests
            passed_tests += m.tests_passed
            build_successes += 1 if m.build_success else 0
            user_accepted += 1 if m.user_accepted else 0
            patches_reverted += 1 if m.patch_reverted else 0
            bugs_fixed += 1 if m.bug_fixed else 0
            bugs_reappeared += 1 if m.bug_reappeared else 0
            total_tokens += m.total_tokens
            total_duration += event.duration_ms
            successful += 1 if o.outcome_type.value == "success" else 0

        n = len(events)

        # Compute component scores (0-1)
        test_pass_rate = passed_tests / total_tests if total_tests > 0 else 0.0
        patch_acceptance_rate = (user_accepted - patches_reverted) / n if n > 0 else 0.0
        patch_acceptance_rate = max(0.0, min(1.0, patch_acceptance_rate))
        build_success_rate = build_successes / n if n > 0 else 0.0
        bug_non_recurrence = 1.0 - (bugs_reappeared / bugs_fixed) if bugs_fixed > 0 else 1.0
        bug_non_recurrence = max(0.0, min(1.0, bug_non_recurrence))

        # Execution efficiency: inverse of time (normalized)
        avg_time_ms = total_duration / n if n > 0 else 0
        # Assume 60s is "slow", 0 is "fast" — normalize
        execution_efficiency = max(0.0, 1.0 - (avg_time_ms / 60000.0))

        # User feedback: acceptance rate
        user_feedback = user_accepted / n if n > 0 else 0.5

        # Weighted composite
        total_score = (
            self._weights["test_pass_rate"] * test_pass_rate
            + self._weights["patch_acceptance_rate"] * patch_acceptance_rate
            + self._weights["build_success_rate"] * build_success_rate
            + self._weights["bug_non_recurrence"] * bug_non_recurrence
            + self._weights["execution_efficiency"] * execution_efficiency
            + self._weights["user_feedback"] * user_feedback
        )

        # Normalize to 0-100
        score_100 = total_score * 100.0

        skill_score = SkillScore(
            skill_id=skill_id,
            project_id=project_id,
            test_pass_rate=test_pass_rate,
            patch_acceptance_rate=patch_acceptance_rate,
            build_success_rate=build_success_rate,
            bug_non_recurrence=bug_non_recurrence,
            execution_efficiency=execution_efficiency,
            user_feedback=user_feedback,
            total_score=score_100,
            sample_count=n,
        )

        # Persist score
        self._save_score(skill_score)

        return skill_score

    def _save_score(self, score: SkillScore) -> None:
        """Persist a skill score."""
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO skill_scores
               (skill_id, project_id, test_pass_rate, patch_acceptance_rate,
                build_success_rate, bug_non_recurrence, execution_efficiency,
                user_feedback, total_score, sample_count, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                score.skill_id,
                score.project_id,
                score.test_pass_rate,
                score.patch_acceptance_rate,
                score.build_success_rate,
                score.bug_non_recurrence,
                score.execution_efficiency,
                score.user_feedback,
                score.total_score,
                score.sample_count,
                score.last_updated,
            ),
        )
        conn.commit()

    def get_score(self, skill_id: str, project_id: str = "") -> SkillScore | None:
        """Retrieve persisted score."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM skill_scores WHERE skill_id = ? AND project_id = ?",
            (skill_id, project_id),
        ).fetchone()

        if not row:
            return None

        return SkillScore(
            skill_id=row["skill_id"],
            project_id=row["project_id"],
            test_pass_rate=row["test_pass_rate"],
            patch_acceptance_rate=row["patch_acceptance_rate"],
            build_success_rate=row["build_success_rate"],
            bug_non_recurrence=row["bug_non_recurrence"],
            execution_efficiency=row["execution_efficiency"],
            user_feedback=row["user_feedback"],
            total_score=row["total_score"],
            sample_count=row["sample_count"],
            last_updated=row["last_updated"],
        )

    def get_all_scores(self, project_id: str = "") -> list[SkillScore]:
        """Get scores for all skills."""
        conn = self._get_conn()
        if project_id:
            rows = conn.execute(
                "SELECT * FROM skill_scores WHERE project_id = ? ORDER BY total_score DESC",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM skill_scores ORDER BY total_score DESC"
            ).fetchall()

        return [
            SkillScore(
                skill_id=row["skill_id"],
                project_id=row["project_id"],
                test_pass_rate=row["test_pass_rate"],
                patch_acceptance_rate=row["patch_acceptance_rate"],
                build_success_rate=row["build_success_rate"],
                bug_non_recurrence=row["bug_non_recurrence"],
                execution_efficiency=row["execution_efficiency"],
                user_feedback=row["user_feedback"],
                total_score=row["total_score"],
                sample_count=row["sample_count"],
                last_updated=row["last_updated"],
            )
            for row in rows
        ]

    def compare_skills(
        self, skill_ids: list[str], project_id: str = ""
    ) -> list[dict[str, Any]]:
        """Compare multiple skills side-by-side."""
        results = []
        for skill_id in skill_ids:
            score = self.get_score(skill_id, project_id)
            if score:
                results.append(score.model_dump())
            else:
                results.append({
                    "skill_id": skill_id,
                    "total_score": 0.0,
                    "sample_count": 0,
                })
        return sorted(results, key=lambda x: x.get("total_score", 0), reverse=True)

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
