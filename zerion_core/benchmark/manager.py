"""Benchmark manager — orchestrates all benchmarking components."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from zerion_core.benchmark.engine import BenchmarkEngine
from zerion_core.benchmark.score_engine import ScoreEngine
from zerion_core.benchmark.reputation import ReputationEngine
from zerion_core.benchmark.ab_testing import ABTestingFramework
from zerion_core.benchmark.workflow_bench import WorkflowBenchmarker
from zerion_core.benchmark.collaboration import CollaborationAnalytics
from zerion_core.benchmark.failure_analysis import FailureAnalyzer
from zerion_core.benchmark.leaderboard import LeaderboardEngine
from zerion_core.benchmark.consolidation import BenchmarkConsolidator
from zerion_core.benchmark.models import (
    BenchmarkEvent,
    BenchmarkMetrics,
    BenchmarkOutcome,
    FailureRecord,
    LeaderboardEntry,
    OutcomeType,
    TaskType,
)


class BenchmarkManager:
    """High-level benchmark manager that orchestrates all components."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        on_event: Callable[[str, str], None] | None = None,
    ):
        self._on_event = on_event or (lambda s, m: None)

        # Initialize all engines
        self.engine = BenchmarkEngine(db_path=db_path, on_event=self._on_event)
        self.score_engine = ScoreEngine(self.engine, on_event=self._on_event)
        self.reputation = ReputationEngine(self.engine, on_event=self._on_event)
        self.ab_testing = ABTestingFramework(self.engine, on_event=self._on_event)
        self.workflow_bench = WorkflowBenchmarker(self.engine, on_event=self._on_event)
        self.collaboration = CollaborationAnalytics(self.engine, on_event=self._on_event)
        self.failure_analyzer = FailureAnalyzer(self.engine, on_event=self._on_event)
        self.leaderboard = LeaderboardEngine(
            self.engine, self.score_engine, self.reputation, on_event=self._on_event
        )
        self.consolidation = BenchmarkConsolidator(self.engine, on_event=self._on_event)

    # --- High-Level API ---

    def record_task_completion(
        self,
        skill_id: str,
        project_id: str = "",
        session_id: str = "",
        task_type: TaskType = TaskType.OTHER,
        duration_ms: int = 0,
        tests_total: int = 0,
        tests_passed: int = 0,
        build_success: bool = False,
        lint_success: bool = False,
        user_accepted: bool = False,
        patch_reverted: bool = False,
        bug_fixed: bool = False,
        regression_detected: bool = False,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        hallucination_count: int = 0,
        invalid_patch_count: int = 0,
        workflow_id: str = "",
        files_modified: list[str] | None = None,
        error_output: str = "",
    ) -> BenchmarkEvent:
        """Record a full task completion with all metrics."""
        # Build metrics
        metrics = BenchmarkMetrics(
            total_tests=tests_total,
            tests_passed=tests_passed,
            tests_failed=tests_total - tests_passed,
            build_success=build_success,
            lint_success=lint_success,
            user_accepted=user_accepted,
            patch_reverted=patch_reverted,
            bug_fixed=bug_fixed,
            regression_detected=regression_detected,
            total_time_ms=duration_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            hallucination_count=hallucination_count,
            invalid_patch_count=invalid_patch_count,
        )

        # Determine outcome
        if patch_reverted:
            outcome_type = OutcomeType.REVERTED
        elif tests_passed == tests_total and tests_total > 0 and build_success:
            outcome_type = OutcomeType.SUCCESS
        elif tests_passed > 0 or user_accepted:
            outcome_type = OutcomeType.PARTIAL
        else:
            outcome_type = OutcomeType.FAILURE

        # Compute effectiveness score
        effectiveness = 0.0
        if tests_total > 0:
            effectiveness += 0.4 * (tests_passed / tests_total)
        if build_success:
            effectiveness += 0.2
        if user_accepted:
            effectiveness += 0.2
        if not regression_detected:
            effectiveness += 0.1
        if hallucination_count == 0:
            effectiveness += 0.1

        outcome = BenchmarkOutcome(
            outcome_type=outcome_type,
            effectiveness_score=effectiveness,
        )

        # Record event
        event = self.engine.record_execution(
            skill_id=skill_id,
            project_id=project_id,
            session_id=session_id,
            task_type=task_type,
            duration_ms=duration_ms,
            metrics=metrics,
            outcome=outcome,
            workflow_id=workflow_id,
            files_modified=files_modified,
            error_output=error_output,
        )

        # Update score
        score = self.score_engine.compute_score(skill_id, project_id)

        # Update reputation
        score_delta = (effectiveness - 0.5) * 20  # -10 to +10
        self.reputation.update_reputation(skill_id, score_delta, project_id)

        # Record workflow if specified
        if workflow_id:
            self.workflow_bench.record_workflow_run(
                workflow_id=workflow_id,
                workflow_name=workflow_id,
                skill_ids=[skill_id],
                success=outcome_type == OutcomeType.SUCCESS,
                duration_ms=duration_ms,
                regression_detected=regression_detected,
            )

        # Record failure if applicable
        if outcome_type == OutcomeType.FAILURE:
            self.failure_analyzer.record_failure(
                skill_id=skill_id,
                task_description=f"Task type: {task_type.value}",
                failure_type="task_failure",
                root_cause=error_output[:500] if error_output else "unknown",
                workflow_used=workflow_id,
                files_modified=files_modified,
                project_id=project_id,
            )

        return event

    def record_collaboration(
        self,
        skill_ids: list[str],
        project_id: str = "",
        session_id: str = "",
        task_type: TaskType = TaskType.OTHER,
        duration_ms: int = 0,
        success: bool = True,
        workflow_id: str = "",
    ) -> None:
        """Record a multi-skill collaboration."""
        self.collaboration.record_collaboration(
            skill_ids=skill_ids,
            success=success,
            duration_ms=duration_ms,
            project_id=project_id,
            task_type=task_type.value,
        )

    def record_ab_test(
        self,
        skill_a_id: str,
        skill_b_id: str,
        task_type: str,
        skill_a_metrics: BenchmarkMetrics,
        skill_b_metrics: BenchmarkMetrics,
        task_description: str = "",
    ) -> Any:
        """Record an A/B test result."""
        return self.ab_testing.record_test(
            skill_a_id=skill_a_id,
            skill_b_id=skill_b_id,
            task_type=task_type,
            skill_a_metrics=skill_a_metrics,
            skill_b_metrics=skill_b_metrics,
            task_description=task_description,
        )

    # --- Query API ---

    def get_leaderboard(
        self, project_id: str | None = None, limit: int = 20
    ) -> list[LeaderboardEntry]:
        """Get skill leaderboard."""
        return self.leaderboard.get_leaderboard(project_id, limit)

    def get_project_health(self, project_id: str) -> dict[str, Any]:
        """Get project health report."""
        return self.leaderboard.get_project_health(project_id)

    def get_skill_report(
        self, skill_id: str, project_id: str = ""
    ) -> dict[str, Any]:
        """Get detailed skill report."""
        return self.leaderboard.get_skill_report(skill_id, project_id)

    def get_regression_report(
        self, project_id: str | None = None, days: int = 7
    ) -> dict[str, Any]:
        """Get regression report."""
        return self.leaderboard.get_regression_report(project_id, days)

    def compare_skills(
        self, skill_ids: list[str], project_id: str = ""
    ) -> list[dict[str, Any]]:
        """Compare multiple skills."""
        return self.score_engine.compare_skills(skill_ids, project_id)

    def get_head_to_head(self, skill_a: str, skill_b: str) -> dict[str, Any]:
        """Get head-to-head A/B comparison."""
        return self.ab_testing.get_head_to_head(skill_a, skill_b)

    def get_failure_recommendations(self, skill_id: str) -> list[str]:
        """Get failure-based recommendations for a skill."""
        return self.failure_analyzer.get_recommendations(skill_id)

    # --- Maintenance ---

    def run_consolidation(self, older_than_days: int = 30) -> int:
        """Run benchmark consolidation."""
        results = self.consolidation.consolidate_all(older_than_days)
        return len(results)

    def apply_time_decay(self, days: int = 1) -> None:
        """Apply reputation time decay."""
        self.reputation.apply_time_decay(days)

    def close(self) -> None:
        """Close all database connections."""
        self.engine.close()
        self.score_engine.close()
        self.reputation.close()
        self.ab_testing.close()
        self.workflow_bench.close()
        self.collaboration.close()
        self.failure_analyzer.close()
        self.leaderboard.close()
        self.consolidation.close()
