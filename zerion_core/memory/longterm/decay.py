"""Auto-decay engine: time-based importance decay with core memory protection."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from zerion_core.memory.longterm.episodic_store import EpisodicStore
from zerion_core.memory.longterm.importance import (
    CORE_MEMORY_FLOOR,
    DECAY_HALF_LIFE_DAYS,
    EventType,
    compute_importance,
    decay_score,
)


class DecayEngine:
    """Manages importance decay for all memory events.

    Core memories (architecture decisions, bug fixes) never decay below
    a configured floor. Regular memories decay exponentially over time
    but can be reinforced by access.
    """

    def __init__(self, store: EpisodicStore) -> None:
        self.store = store

    def run_decay(self, now: datetime | None = None) -> dict[str, int]:
        """Run a full decay pass over all events.

        Returns stats: {"decayed": N, "pruned": N, "core_protected": N}
        """
        if now is None:
            now = datetime.now(timezone.utc)

        stats = {"decayed": 0, "pruned": 0, "core_protected": 0}

        # Get all non-core events for decay
        all_events = self.store.get_recent_events(limit=10000)

        for event in all_events:
            try:
                created = datetime.fromisoformat(event.created_at)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                days_old = (now - created).total_seconds() / 86400.0
            except (ValueError, TypeError):
                continue

            if days_old < 1.0:
                continue  # Don't decay events less than 1 day old

            event_type = EventType(event.event_type) if event.event_type in EventType.__members__.values() else None
            floor = CORE_MEMORY_FLOOR.get(event_type, 0.0) if event_type else 0.0

            # Calculate new importance with decay
            new_importance = decay_score(event.importance, days_old, floor=floor)

            # Check if this is a core memory that was protected
            if event.is_core and new_importance < event.importance:
                # Core memory floor prevented further decay
                if event_type and event_type in CORE_MEMORY_FLOOR:
                    stats["core_protected"] += 1

            # Apply the decayed score
            if abs(new_importance - event.importance) > 0.001:
                self.store.update_importance(event.id, new_importance)
                stats["decayed"] += 1

            # Prune very low importance old memories (> 90 days, importance < 0.05)
            if days_old > 90 and new_importance < 0.05 and not event.is_core:
                self.store.delete_event(event.id)
                stats["pruned"] += 1

        return stats

    def reinforce_event(self, event_id: str, boost: float = 0.05) -> None:
        """Boost importance when a memory is accessed or reinforced."""
        event = self.store.get_event(event_id)
        if not event:
            return

        new_score = min(1.0, event.importance + boost)
        self.store.update_importance(event_id, new_score)
        self.store.mark_accessed(event_id)

    def get_decay_stats(self) -> dict[str, Any]:
        """Get statistics about memory health."""
        conn = self.store._get_conn()

        # Count by importance buckets
        rows = conn.execute(
            """SELECT
                SUM(CASE WHEN importance >= 0.8 THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN importance >= 0.5 AND importance < 0.8 THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN importance < 0.5 THEN 1 ELSE 0 END) as low,
                SUM(CASE WHEN is_core = 1 THEN 1 ELSE 0 END) as core,
                COUNT(*) as total
            FROM memory_events"""
        ).fetchone()

        return {
            "total": rows["total"] or 0,
            "high_importance": rows["high"] or 0,
            "medium_importance": rows["medium"] or 0,
            "low_importance": rows["low"] or 0,
            "core_memories": rows["core"] or 0,
        }


from typing import Any
