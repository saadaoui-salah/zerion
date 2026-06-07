"""Success scoring system: tracks outcomes and computes success scores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone


@dataclass
class OutcomeSignals:
    """Signals that contribute to success scoring."""
    tests_passed: bool = False
    build_succeeded: bool = False
    user_accepted: bool = False
    patch_retained: bool = False
    bug_not_reintroduced: bool = False
    no_regressions: bool = False
    performance_improved: bool = False
    code_review_approved: bool = False


@dataclass
class SuccessScore:
    """Computed success score with breakdown."""
    total: float = 0.0
    confidence: float = 0.0
    signals: OutcomeSignals = field(default_factory=OutcomeSignals)
    breakdown: dict[str, float] = field(default_factory=dict)


class SuccessScorer:
    """Computes success scores from outcome signals."""

    # Weights for different signals
    DEFAULT_WEIGHTS = {
        "tests_passed": 0.25,
        "build_succeeded": 0.15,
        "user_accepted": 0.20,
        "patch_retained": 0.15,
        "bug_not_reintroduced": 0.10,
        "no_regressions": 0.10,
        "performance_improved": 0.03,
        "code_review_approved": 0.02,
    }

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or self.DEFAULT_WEIGHTS

    def compute_score(
        self,
        signals: OutcomeSignals,
        context: dict[str, Any] | None = None,
    ) -> SuccessScore:
        """Compute success score from outcome signals."""
        breakdown: dict[str, float] = {}
        total = 0.0

        signal_dict = {
            "tests_passed": signals.tests_passed,
            "build_succeeded": signals.build_succeeded,
            "user_accepted": signals.user_accepted,
            "patch_retained": signals.patch_retained,
            "bug_not_reintroduced": signals.bug_not_reintroduced,
            "no_regressions": signals.no_regressions,
            "performance_improved": signals.performance_improved,
            "code_review_approved": signals.code_review_approved,
        }

        for signal_name, weight in self._weights.items():
            value = signal_dict.get(signal_name, False)
            score = weight if value else 0.0
            breakdown[signal_name] = score
            total += score

        # Normalize to 0-1 range
        max_possible = sum(self._weights.values())
        normalized = total / max_possible if max_possible > 0 else 0.0

        # Compute confidence based on number of signals available
        available_signals = sum(1 for v in signal_dict.values() if v is not None)
        confidence = available_signals / len(signal_dict) if signal_dict else 0.0

        return SuccessScore(
            total=round(normalized, 4),
            confidence=round(confidence, 4),
            signals=signals,
            breakdown=breakdown,
        )

    def compute_from_dict(self, data: dict[str, Any]) -> SuccessScore:
        """Compute score from a dictionary of signals."""
        signals = OutcomeSignals(
            tests_passed=data.get("tests_passed", False),
            build_succeeded=data.get("build_succeeded", False),
            user_accepted=data.get("user_accepted", False),
            patch_retained=data.get("patch_retained", False),
            bug_not_reintroduced=data.get("bug_not_reintroduced", False),
            no_regressions=data.get("no_regressions", False),
            performance_improved=data.get("performance_improved", False),
            code_review_approved=data.get("code_review_approved", False),
        )
        return self.compute_score(signals)

    def compute_historical_score(
        self,
        outcomes: list[dict[str, Any]],
        recency_weight: float = 0.7,
    ) -> float:
        """Compute score from historical outcomes with recency weighting."""
        if not outcomes:
            return 0.5

        sorted_outcomes = sorted(
            outcomes,
            key=lambda x: x.get("timestamp", ""),
            reverse=True,
        )

        total_score = 0.0
        total_weight = 0.0

        for i, outcome in enumerate(sorted_outcomes):
            # Recency weight: more recent outcomes have higher weight
            recency = recency_weight ** i
            score = outcome.get("success_score", 0.5)
            total_score += score * recency
            total_weight += recency

        return total_score / total_weight if total_weight > 0 else 0.5

    def trend_analysis(
        self,
        outcomes: list[dict[str, Any]],
        window: int = 10,
    ) -> dict[str, Any]:
        """Analyze success score trends."""
        if len(outcomes) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}

        sorted_outcomes = sorted(
            outcomes,
            key=lambda x: x.get("timestamp", ""),
        )

        recent = sorted_outcomes[-window:]
        older = sorted_outcomes[:-window] if len(sorted_outcomes) > window else sorted_outcomes[:1]

        recent_avg = sum(o.get("success_score", 0.5) for o in recent) / len(recent)
        older_avg = sum(o.get("success_score", 0.5) for o in older) / len(older)

        delta = recent_avg - older_avg

        if delta > 0.1:
            trend = "improving"
        elif delta < -0.1:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "delta": round(delta, 4),
            "recent_avg": round(recent_avg, 4),
            "older_avg": round(older_avg, 4),
            "sample_size": len(recent),
        }
