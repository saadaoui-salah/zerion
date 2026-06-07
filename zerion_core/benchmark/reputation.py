"""Reputation engine for skills — global and per-project."""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from zerion_core.benchmark.engine import BenchmarkEngine
from zerion_core.benchmark.models import SkillReputation


class ReputationEngine:
    """Maintains global and per-project reputation for skills."""

    # Reputation decay per day (0.995 = 0.5% decay per day)
    DECAY_RATE = 0.995
    # Minimum samples before confidence rises
    MIN_SAMPLES_CONFIDENCE = 10
    # Maximum confidence
    MAX_CONFIDENCE = 0.95

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

    def update_reputation(
        self,
        skill_id: str,
        score_delta: float,
        project_id: str = "",
    ) -> SkillReputation:
        """Update reputation based on a benchmark event.

        Args:
            skill_id: The skill to update.
            score_delta: Change in score (-100 to +100).
            project_id: Project context.
        """
        conn = self._get_conn()
        now = datetime.now().isoformat()

        # Get current reputation
        row = conn.execute(
            "SELECT * FROM skill_reputation WHERE skill_id = ?", (skill_id,)
        ).fetchone()

        if row:
            global_rep = row["global_reputation"]
            project_reps = json.loads(row["project_reputations_json"])
            sample_size = row["sample_size"]
            trend = row["trend"]
        else:
            global_rep = 50.0
            project_reps = {}
            sample_size = 0
            trend = "stable"

        # Apply update with diminishing returns
        old_rep = global_rep
        # Smaller updates have larger impact at lower reputation
        impact = score_delta * (1.0 - global_rep / 200.0)
        global_rep = max(0.0, min(100.0, global_rep + impact))

        # Update project-specific reputation
        if project_id:
            proj_rep = project_reps.get(project_id, 50.0)
            proj_impact = score_delta * (1.0 - proj_rep / 200.0)
            project_reps[project_id] = max(0.0, min(100.0, proj_rep + proj_impact))

        # Update sample size and confidence
        sample_size += 1
        confidence = min(
            self.MAX_CONFIDENCE,
            sample_size / self.MIN_SAMPLES_CONFIDENCE,
        )

        # Determine trend
        if global_rep > old_rep + 1.0:
            trend = "improving"
        elif global_rep < old_rep - 1.0:
            trend = "declining"
        else:
            trend = "stable"

        # Persist
        conn.execute(
            """INSERT OR REPLACE INTO skill_reputation
               (skill_id, global_reputation, project_reputations_json,
                confidence, sample_size, trend, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                skill_id,
                global_rep,
                json.dumps(project_reps),
                confidence,
                sample_size,
                trend,
                now,
            ),
        )
        conn.commit()

        self._on_event(
            "reputation",
            f"Updated {skill_id}: {global_rep:.1f} (confidence={confidence:.2f})",
        )

        return SkillReputation(
            skill_id=skill_id,
            global_reputation=global_rep,
            project_reputations=project_reps,
            confidence=confidence,
            sample_size=sample_size,
            trend=trend,
            last_updated=now,
        )

    def get_reputation(self, skill_id: str) -> SkillReputation | None:
        """Get current reputation for a skill."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM skill_reputation WHERE skill_id = ?", (skill_id,)
        ).fetchone()

        if not row:
            return None

        return SkillReputation(
            skill_id=row["skill_id"],
            global_reputation=row["global_reputation"],
            project_reputations=json.loads(row["project_reputations_json"]),
            confidence=row["confidence"],
            sample_size=row["sample_size"],
            trend=row["trend"],
            last_updated=row["last_updated"],
        )

    def get_project_reputation(self, skill_id: str, project_id: str) -> float:
        """Get project-specific reputation for a skill."""
        rep = self.get_reputation(skill_id)
        if not rep:
            return 50.0
        return rep.project_reputations.get(project_id, rep.global_reputation)

    def get_all_reputations(self) -> list[SkillReputation]:
        """Get reputations for all skills."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM skill_reputation ORDER BY global_reputation DESC"
        ).fetchall()

        return [
            SkillReputation(
                skill_id=row["skill_id"],
                global_reputation=row["global_reputation"],
                project_reputations=json.loads(row["project_reputations_json"]),
                confidence=row["confidence"],
                sample_size=row["sample_size"],
                trend=row["trend"],
                last_updated=row["last_updated"],
            )
            for row in rows
        ]

    def apply_time_decay(self, days: int = 1) -> None:
        """Apply time-based decay to all reputations.

        Call periodically (e.g., daily) to reduce stale reputations.
        """
        conn = self._get_conn()
        rows = conn.execute("SELECT skill_id, global_reputation FROM skill_reputation").fetchall()

        for row in rows:
            old_rep = row["global_reputation"]
            # Decay toward 50.0 (neutral)
            new_rep = 50.0 + (old_rep - 50.0) * (self.DECAY_RATE ** days)
            conn.execute(
                "UPDATE skill_reputation SET global_reputation = ? WHERE skill_id = ?",
                (new_rep, row["skill_id"]),
            )
        conn.commit()
        self._on_event("reputation", f"Applied time decay ({days} days) to {len(rows)} skills")

    def rank_skills(self, project_id: str | None = None) -> list[dict[str, Any]]:
        """Rank skills by reputation."""
        conn = self._get_conn()
        if project_id:
            rows = conn.execute(
                """SELECT skill_id, global_reputation, project_reputations_json,
                          confidence, sample_size, trend
                   FROM skill_reputation
                   ORDER BY global_reputation DESC"""
            ).fetchall()

            ranked = []
            for row in rows:
                reps = json.loads(row["project_reputations_json"])
                proj_rep = reps.get(project_id, 50.0)
                ranked.append({
                    "skill_id": row["skill_id"],
                    "reputation": proj_rep,
                    "global_reputation": row["global_reputation"],
                    "confidence": row["confidence"],
                    "trend": row["trend"],
                })
            return sorted(ranked, key=lambda x: x["reputation"], reverse=True)
        else:
            rows = conn.execute(
                """SELECT skill_id, global_reputation, confidence, sample_size, trend
                   FROM skill_reputation
                   ORDER BY global_reputation DESC"""
            ).fetchall()
            return [
                {
                    "skill_id": row["skill_id"],
                    "reputation": row["global_reputation"],
                    "confidence": row["confidence"],
                    "sample_size": row["sample_size"],
                    "trend": row["trend"],
                }
                for row in rows
            ]

    def get_trend_data(self, skill_id: str, days: int = 30) -> list[dict[str, Any]]:
        """Get reputation trend from benchmark events."""
        events = self._engine.get_events(skill_id=skill_id, limit=500)

        # Group by date
        daily: dict[str, list[float]] = {}
        for event in events:
            date = event.timestamp[:10]
            score = event.outcome.effectiveness_score
            if date not in daily:
                daily[date] = []
            daily[date].append(score)

        return [
            {
                "date": date,
                "avg_score": sum(scores) / len(scores) if scores else 0.0,
                "executions": len(scores),
            }
            for date, scores in sorted(daily.items())
        ]

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
