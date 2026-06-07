"""Cross-session retrieval engine: semantic + temporal + importance-ranked search."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from zerion_core.llm.ollama import OllamaClient
from zerion_core.memory.longterm.episodic_store import EpisodicStore, MemoryEvent
from zerion_core.memory.longterm.importance import EventType
from zerion_core.memory.longterm.semantic_store import SemanticStore


class TimeRange:
    """Parsed time range for queries like '3 days ago', 'last week'."""

    def __init__(self, start: str, end: str, label: str = "") -> None:
        self.start = start
        self.end = end
        self.label = label

    def to_dict(self) -> dict[str, str]:
        return {"start": self.start, "end": self.end, "label": self.label}


def parse_time_query(query: str) -> TimeRange | None:
    """Parse natural language time references."""
    now = datetime.now(timezone.utc)
    q = query.lower().strip()

    # "N days/hours/weeks ago"
    m = re.search(r"(\d+)\s*(day|hour|week|month)s?\s*ago", q)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "hour":
            start = now - timedelta(hours=n)
        elif unit == "day":
            start = now - timedelta(days=n)
        elif unit == "week":
            start = now - timedelta(weeks=n)
        elif unit == "month":
            start = now - timedelta(days=n * 30)
        else:
            start = now - timedelta(days=n)
        return TimeRange(
            start=start.isoformat(),
            end=now.isoformat(),
            label=f"last {n} {unit}{'s' if n > 1 else ''}",
        )

    # "today"
    if "today" in q:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return TimeRange(start=start.isoformat(), end=now.isoformat(), label="today")

    # "yesterday"
    if "yesterday" in q:
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return TimeRange(start=start.isoformat(), end=end.isoformat(), label="yesterday")

    # "this week"
    if "this week" in q:
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return TimeRange(start=start.isoformat(), end=now.isoformat(), label="this week")

    # "last week"
    if "last week" in q:
        end = now - timedelta(days=now.weekday())
        start = end - timedelta(days=7)
        return TimeRange(start=start.isoformat(), end=end.isoformat(), label="last week")

    # "this month"
    if "this month" in q:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return TimeRange(start=start.isoformat(), end=now.isoformat(), label="this month")

    # "last month"
    if "last month" in q:
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_this - timedelta(days=1)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return TimeRange(start=start.isoformat(), end=end.isoformat(), label="last month")

    return None


class RetrievalResult:
    """A single retrieval result with scoring."""

    def __init__(
        self,
        event: MemoryEvent,
        score: float = 0.0,
        source: str = "hybrid",
        snippet: str = "",
    ) -> None:
        self.event = event
        self.score = score
        self.source = source
        self.snippet = snippet or event.content[:200]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event.id,
            "session_id": self.event.session_id,
            "project_id": self.event.project_id,
            "event_type": self.event.event_type,
            "content": self.event.content,
            "importance": self.event.importance,
            "created_at": self.event.created_at,
            "score": self.score,
            "source": self.source,
            "snippet": self.snippet,
        }


class CrossSessionRetriever:
    """Retrieves memories across sessions using semantic + temporal + importance ranking."""

    def __init__(
        self,
        episodic: EpisodicStore,
        semantic: SemanticStore,
        llm: OllamaClient,
    ) -> None:
        self.episodic = episodic
        self.semantic = semantic
        self.llm = llm

    async def retrieve(
        self,
        query: str,
        project_id: str | None = None,
        time_range: TimeRange | None = None,
        event_types: list[str] | None = None,
        min_importance: float = 0.0,
        limit: int = 15,
    ) -> list[RetrievalResult]:
        """Full cross-session retrieval with semantic + temporal + importance ranking.

        Supports:
        - "what did I do 3 days ago?" — temporal query
        - "where did I fix auth bug?" — semantic query
        - "what decisions did I make about RAG?" — type-filtered semantic
        - "bugs in project X" — project + type filtered
        """
        results: list[RetrievalResult] = []

        # 1. Parse time references from query
        time_ref = time_range or parse_time_query(query)
        clean_query = self._remove_time_phrases(query)

        # 2. Semantic search (vector + keyword)
        semantic_hits = await self.semantic.search(
            clean_query,
            limit=limit * 2,
            project_filter=project_id,
            event_type_filter=event_types[0] if event_types and len(event_types) == 1 else None,
            min_importance=min_importance,
        )

        # Map semantic hits to events
        for hit in semantic_hits:
            event_id = hit.get("event_id", "")
            event = self.episodic.get_event(event_id)
            if not event:
                continue

            # Apply time filter
            if time_ref:
                if event.created_at < time_ref.start or event.created_at > time_ref.end:
                    continue

            # Apply event type filter
            if event_types and event.event_type not in event_types:
                continue

            # Apply importance filter
            if event.importance < min_importance:
                continue

            # Combined score: 60% vector + 25% importance + 15% recency
            vector_score = hit.get("vector_score", 0.0)
            importance_score = event.importance
            recency_score = self._recency_score(event.created_at)
            combined = (
                vector_score * 0.60
                + importance_score * 0.25
                + recency_score * 0.15
            )

            results.append(RetrievalResult(
                event=event,
                score=combined,
                source=hit.get("source", "hybrid"),
            ))

        # 3. Episodic fallback: if semantic didn't find enough, search directly
        if len(results) < limit:
            existing_ids = {r.event.id for r in results}

            if time_ref:
                episodic_hits = self.episodic.search_by_time_range(
                    time_ref.start, time_ref.end,
                    project_id=project_id,
                    limit=limit * 2,
                )
            elif event_types:
                episodic_hits = []
                for et in event_types:
                    episodic_hits.extend(self.episodic.search_by_type(
                        et, project_id=project_id, limit=limit,
                    ))
            else:
                episodic_hits = self.episodic.get_recent_events(
                    project_id=project_id, limit=limit * 2,
                )

            for event in episodic_hits:
                if event.id in existing_ids:
                    continue
                if event.importance < min_importance:
                    continue

                # Keyword relevance score
                kw_score = self._keyword_relevance(clean_query, event.content)
                importance_score = event.importance
                recency_score = self._recency_score(event.created_at)
                combined = (
                    kw_score * 0.40
                    + importance_score * 0.35
                    + recency_score * 0.25
                )

                if combined > 0.1:
                    results.append(RetrievalResult(
                        event=event,
                        score=combined,
                        source="episodic",
                    ))

        # 4. Sort by score and return top-k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def retrieve_for_context(
        self,
        project_id: str,
        max_tokens: int = 2000,
    ) -> str:
        """Retrieve the most relevant memories for LLM context injection.

        Returns a compressed, optimized context block.
        """
        # Get core memories (high importance, always relevant)
        core = self.episodic.get_core_memories(project_id=project_id, limit=10)

        # Get recent memories
        recent = self.episodic.get_recent_events(project_id=project_id, limit=5)

        # Deduplicate
        seen_ids = set()
        events: list[MemoryEvent] = []
        for e in core + recent:
            if e.id not in seen_ids:
                seen_ids.add(e.id)
                events.append(e)

        if not events:
            return ""

        # Compress into context block
        lines: list[str] = ["## Long-Term Memory"]
        total_chars = 0

        for event in events:
            line = f"- [{event.event_type}] {event.content[:150]}"
            if total_chars + len(line) > max_tokens * 4:
                break
            lines.append(line)
            total_chars += len(line)

        return "\n".join(lines)

    def _keyword_relevance(self, query: str, content: str) -> float:
        """Simple keyword overlap score."""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        if not query_words:
            return 0.0
        overlap = query_words & content_words
        return len(overlap) / len(query_words)

    def _recency_score(self, created_at: str) -> float:
        """Recency score: more recent = higher."""
        try:
            created = datetime.fromisoformat(created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_days = max(0.0, (now - created).total_seconds() / 86400.0)
            return max(0.1, 1.0 / (1.0 + age_days / 7.0))
        except (ValueError, TypeError):
            return 0.5

    def _remove_time_phrases(self, query: str) -> str:
        """Remove time-related phrases from query for cleaner semantic search."""
        patterns = [
            r"\d+\s*(day|hour|week|month)s?\s*ago",
            r"today|yesterday|this\s+week|last\s+week|this\s+month|last\s+month",
        ]
        result = query
        for pat in patterns:
            result = re.sub(pat, "", result, flags=re.IGNORECASE)
        return " ".join(result.split()).strip()
