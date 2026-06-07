"""Importance scoring system for memory events.

Computes a 0.0-1.0 importance score for each memory event using:
- base_score(event_type) — intrinsic importance of the event type
- frequency_boost — how often this memory has been accessed/reinforced
- recency_decay — exponential decay over time
- user_signal_weight — explicit user importance signals

Formula:
  importance = base_score * (1 + frequency_boost) * recency_decay * user_signal_weight
  clamped to [0.0, 1.0]
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum


class EventType(str, Enum):
    ARCHITECTURE_DECISION = "architecture_decision"
    BUG_FIX = "bug_fix"
    FEATURE_IMPLEMENTED = "feature_implemented"
    REFACTOR = "refactor"
    ERROR_OCCURRED = "error_occurred"
    LESSON_LEARNED = "lesson_learned"
    USER_CONFIRMATION = "user_confirmation"
    QUERY = "query"
    DEPLOYMENT = "deployment"
    TEST_RESULT = "test_result"
    CODE_REVIEW = "code_review"
    PATTERN_IDENTIFIED = "pattern_identified"


# Base importance scores per event type (0.0 - 1.0)
BASE_SCORES: dict[EventType, float] = {
    EventType.ARCHITECTURE_DECISION: 0.95,
    EventType.BUG_FIX: 0.85,
    EventType.FEATURE_IMPLEMENTED: 0.80,
    EventType.LESSON_LEARNED: 0.80,
    EventType.PATTERN_IDENTIFIED: 0.75,
    EventType.CODE_REVIEW: 0.70,
    EventType.REFACTOR: 0.65,
    EventType.DEPLOYMENT: 0.65,
    EventType.TEST_RESULT: 0.60,
    EventType.USER_CONFIRMATION: 0.90,
    EventType.ERROR_OCCURRED: 0.50,
    EventType.QUERY: 0.20,
}

# Core memory types that never decay below this threshold
CORE_MEMORY_FLOOR: dict[EventType, float] = {
    EventType.ARCHITECTURE_DECISION: 0.70,
    EventType.BUG_FIX: 0.60,
    EventType.LESSON_LEARNED: 0.55,
    EventType.USER_CONFIRMATION: 0.65,
}

# Half-life in days for exponential decay
DECAY_HALF_LIFE_DAYS = 14.0


def compute_importance(
    event_type: EventType,
    created_at: str,
    times_accessed: int = 0,
    user_boost: float = 1.0,
    now: datetime | None = None,
) -> float:
    """Compute the importance score for a memory event.

    Args:
        event_type: The type of event
        created_at: ISO timestamp of when the event was created
        times_accessed: How many times this memory has been retrieved/reinforced
        user_boost: User explicit signal (1.0 = neutral, >1.0 = boost, <1.0 = deprioritize)
        now: Current time (for testing; defaults to UTC now)

    Returns:
        Importance score between 0.0 and 1.0
    """
    base = BASE_SCORES.get(event_type, 0.5)

    # Frequency boost: logarithmic scaling, diminishing returns
    freq_boost = 1.0 + 0.1 * math.log(1 + times_accessed)

    # Recency decay: exponential with half-life
    recency = _recency_factor(created_at, now)

    # User signal weight
    user_weight = max(0.1, min(2.0, user_boost))

    raw = base * freq_boost * recency * user_weight

    # Clamp
    score = max(0.0, min(1.0, raw))

    # Enforce core memory floor
    floor = CORE_MEMORY_FLOOR.get(event_type)
    if floor is not None:
        score = max(score, floor)

    return round(score, 4)


def _recency_factor(created_at: str, now: datetime | None = None) -> float:
    """Exponential decay based on age. Never drops below 0.1."""
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        created = datetime.fromisoformat(created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - created).total_seconds() / 86400.0)
    except (ValueError, TypeError):
        return 0.5

    # Exponential decay: e^(-lambda * t) where lambda = ln(2) / half_life
    decay_rate = math.log(2) / DECAY_HALF_LIFE_DAYS
    return max(0.1, math.exp(-decay_rate * age_days))


def reinforce_importance(current_score: float, boost: float = 0.05) -> float:
    """Boost importance when a memory is accessed/reinforced."""
    return min(1.0, current_score + boost)


def decay_score(current_score: float, days_elapsed: float, floor: float = 0.0) -> float:
    """Apply time-based decay to an existing score, clamped to floor."""
    if days_elapsed <= 0:
        return current_score
    decay_rate = math.log(2) / DECAY_HALF_LIFE_DAYS
    decayed = current_score * math.exp(-decay_rate * days_elapsed)
    return max(floor, decayed)
