"""Semantic search across sessions and messages."""

from __future__ import annotations

import json
from typing import Any

from zerion_core.llm.ollama import OllamaClient
from zerion_core.session.models import SessionMeta, SessionSearchResult
from zerion_core.session.store import SessionStore


class SessionSearcher:
    """Search past sessions by semantic similarity or keyword matching."""

    def __init__(self, store: SessionStore, llm: OllamaClient | None = None) -> None:
        self.store = store
        self.llm = llm

    def keyword_search(
        self,
        query: str,
        project_id: str | None = None,
        limit: int = 10,
    ) -> list[SessionSearchResult]:
        """Fast keyword-based search across sessions and messages."""
        results: list[SessionSearchResult] = []

        # Search session titles and summaries
        sessions = self.store.search_sessions(query, limit=limit)
        for s in sessions:
            results.append(SessionSearchResult(
                session_id=s.id,
                title=s.title,
                summary=s.summary,
                score=0.8,
                snippet=s.summary[:200],
                created_at=s.created_at,
                project_id=s.project_id,
            ))

        # Search messages
        msg_results = self.store.search_messages(query, limit=limit)
        seen_sessions = {r.session_id for r in results}
        for mr in msg_results:
            sid = mr["session_id"]
            if sid not in seen_sessions:
                seen_sessions.add(sid)
                results.append(SessionSearchResult(
                    session_id=sid,
                    title=mr.get("session_title", ""),
                    summary="",
                    score=0.6,
                    snippet=mr.get("content", "")[:200],
                    created_at=mr.get("timestamp", ""),
                    project_id=mr.get("project_id", ""),
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def semantic_search(
        self,
        query: str,
        project_id: str | None = None,
        limit: int = 10,
    ) -> list[SessionSearchResult]:
        """Semantic search using embeddings (requires LLM client)."""
        if not self.llm:
            return self.keyword_search(query, project_id, limit)

        # Get all sessions
        sessions = self.store.list_sessions(project_id=project_id, limit=100)
        if not sessions:
            return []

        # Generate query embedding
        try:
            q_emb = await self.llm.embed(query)
        except Exception:
            return self.keyword_search(query, project_id, limit)

        # Score each session by embedding similarity to query
        scored: list[tuple[float, SessionMeta]] = []
        for s in sessions:
            # Build a text representation for embedding
            text = f"{s.title} {s.summary}"
            if not text.strip():
                continue
            try:
                s_emb = await self.llm.embed(text)
                sim = self._cosine_similarity(q_emb, s_emb)
                scored.append((sim, s))
            except Exception:
                continue

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[SessionSearchResult] = []
        for sim, s in scored[:limit]:
            results.append(SessionSearchResult(
                session_id=s.id,
                title=s.title,
                summary=s.summary,
                score=round(sim, 4),
                created_at=s.created_at,
                project_id=s.project_id,
            ))

        return results

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_session_timeline(self, project_id: str | None = None) -> list[dict[str, Any]]:
        """Get sessions ordered by time, with key events."""
        sessions = self.store.list_sessions(project_id=project_id, limit=50)
        timeline: list[dict[str, Any]] = []
        for s in sessions:
            events = self.store.get_tool_events(s.id, limit=5)
            timeline.append({
                "session_id": s.id,
                "title": s.title,
                "created_at": s.created_at,
                "message_count": s.message_count,
                "event_count": len(events),
                "summary_preview": s.summary[:150] if s.summary else "",
            })
        return timeline
