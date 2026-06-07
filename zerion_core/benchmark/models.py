"""Benchmark data models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    OPTIMIZATION = "optimization"
    TEST = "test"
    DOCUMENTATION = "debug"
    DEBUG = "debug"
    OTHER = "other"


class OutcomeType(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    REVERTED = "reverted"


class BenchmarkMetrics(BaseModel):
    """Objective metrics for a benchmark event."""

    # Test pass rate
    total_tests: int = 0
    tests_passed: int = 0
    tests_failed: int = 0

    # Build success
    build_success: bool = False
    lint_success: bool = False
    compile_success: bool = False

    # Bug recurrence
    bug_fixed: bool = False
    bug_reappeared: bool = False
    regression_detected: bool = False

    # Patch acceptance
    user_accepted: bool = False
    patch_reverted: bool = False
    patch_modified_heavily: bool = False

    # Execution speed (ms)
    retrieval_time_ms: int = 0
    reasoning_time_ms: int = 0
    tool_execution_time_ms: int = 0
    total_time_ms: int = 0

    # Token efficiency
    prompt_tokens: int = 0
    completion_tokens: int = 0
    retrieval_tokens: int = 0

    # Error tracking
    hallucination_count: int = 0
    invalid_patch_count: int = 0
    failed_command_count: int = 0
    incorrect_assumption_count: int = 0

    @property
    def test_pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.tests_passed / self.total_tests

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens + self.retrieval_tokens

    @property
    def error_rate(self) -> float:
        total = (
            self.hallucination_count
            + self.invalid_patch_count
            + self.failed_command_count
            + self.incorrect_assumption_count
        )
        return min(total / 10.0, 1.0)  # Normalize 0-10 errors to 0-1


class BenchmarkOutcome(BaseModel):
    """Outcome of a benchmark event."""

    outcome_type: OutcomeType = OutcomeType.SUCCESS
    quality_per_token: float = 0.0
    effectiveness_score: float = 0.0
    user_satisfaction: float = 0.0


class BenchmarkEvent(BaseModel):
    """Single benchmark event for a skill execution."""

    benchmark_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    skill_id: str
    project_id: str = ""
    session_id: str = ""
    task_id: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    task_type: TaskType = TaskType.OTHER
    duration_ms: int = 0
    metrics: BenchmarkMetrics = Field(default_factory=BenchmarkMetrics)
    outcome: BenchmarkOutcome = Field(default_factory=BenchmarkOutcome)
    workflow_id: str = ""
    files_modified: list[str] = Field(default_factory=list)
    error_output: str = ""
    tags: list[str] = Field(default_factory=list)


class SkillScore(BaseModel):
    """Composite score for a skill."""

    skill_id: str
    project_id: str = ""
    test_pass_rate: float = 0.0
    patch_acceptance_rate: float = 0.0
    build_success_rate: float = 0.0
    bug_non_recurrence: float = 0.0
    execution_efficiency: float = 0.0
    user_feedback: float = 0.0
    total_score: float = 0.0
    sample_count: int = 0
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())


class SkillReputation(BaseModel):
    """Reputation for a skill."""

    skill_id: str
    global_reputation: float = 50.0
    project_reputations: dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0
    sample_size: int = 0
    trend: str = "stable"  # improving, stable, declining
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())


class ABTestResult(BaseModel):
    """Result of an A/B test between two skills."""

    test_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    skill_a_id: str
    skill_b_id: str
    task_type: str
    task_description: str = ""
    skill_a_score: float = 0.0
    skill_b_score: float = 0.0
    skill_a_metrics: BenchmarkMetrics = Field(default_factory=BenchmarkMetrics)
    skill_b_metrics: BenchmarkMetrics = Field(default_factory=BenchmarkMetrics)
    winner: str = ""
    confidence: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class WorkflowBenchmark(BaseModel):
    """Benchmark result for a workflow."""

    workflow_id: str
    workflow_name: str
    skill_ids: list[str] = Field(default_factory=list)
    success_rate: float = 0.0
    avg_time_ms: float = 0.0
    regression_rate: float = 0.0
    total_runs: int = 0
    score: float = 0.0
    last_used: str = Field(default_factory=lambda: datetime.now().isoformat())


class FailureRecord(BaseModel):
    """Record of a failure for analysis."""

    failure_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    skill_id: str
    project_id: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    task_description: str = ""
    failure_type: str = ""
    root_cause: str = ""
    tools_used: list[str] = Field(default_factory=list)
    workflow_used: str = ""
    files_modified: list[str] = Field(default_factory=list)
    error_output: str = ""
    fix_suggestion: str = ""
    cluster_id: str = ""


class LeaderboardEntry(BaseModel):
    """Entry in a leaderboard."""

    rank: int = 0
    skill_id: str
    score: float = 0.0
    tasks_completed: int = 0
    success_rate: float = 0.0
    trend: str = "stable"


class BenchmarkConsolidated(BaseModel):
    """Consolidated benchmark summary."""

    skill_id: str
    project_id: str = ""
    period_start: str = ""
    period_end: str = ""
    total_events: int = 0
    avg_score: float = 0.0
    success_rate: float = 0.0
    avg_time_ms: float = 0.0
    top_task_type: str = ""
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
