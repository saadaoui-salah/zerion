"""Runtime agent state tracker for crash recovery and context persistence."""

from __future__ import annotations

import time
from typing import Any

from zerion_core.session.models import SessionState, ToolEvent


class StateTracker:
    """Tracks runtime agent state: files, errors, patches, commands."""

    def __init__(self, session_id: str, state: SessionState | None = None) -> None:
        self.session_id = session_id
        self.state = state or SessionState()
        self._events: list[ToolEvent] = []
        self._dirty = False

    @property
    def dirty(self) -> bool:
        return self._dirty

    def record_file_open(self, file_path: str) -> None:
        if file_path not in self.state.open_files:
            self.state.open_files.append(file_path)
            self._dirty = True

    def record_file_close(self, file_path: str) -> None:
        if file_path in self.state.open_files:
            self.state.open_files.remove(file_path)
            self._dirty = True

    def record_error(self, error: str) -> None:
        self.state.last_errors.append(error)
        if len(self.state.last_errors) > 20:
            self.state.last_errors = self.state.last_errors[-20:]
        self._dirty = True

    def record_patch(self, file_path: str, diff: str, summary: str = "") -> None:
        self.state.applied_patches.append({
            "file": file_path,
            "summary": summary,
            "diff_preview": diff[:500],
            "timestamp": time.time(),
        })
        if len(self.state.applied_patches) > 50:
            self.state.applied_patches = self.state.applied_patches[-50:]
        self._dirty = True

    def record_retrieval(self, chunks: list[dict[str, Any]]) -> None:
        self.state.retrieved_chunks = chunks[-20:]
        self._dirty = True

    def set_active_task(self, task: str) -> None:
        self.state.active_task = task
        self._dirty = True

    def set_current_goal(self, goal: str) -> None:
        self.state.current_goal = goal
        self._dirty = True

    def add_tool_event(self, event: ToolEvent) -> None:
        self._events.append(event)
        if len(self._events) > 200:
            self._events = self._events[-200:]
        self._dirty = True

    def get_recent_events(self, limit: int = 50) -> list[ToolEvent]:
        return self._events[-limit:]

    def get_tool_summary(self) -> str:
        if not self._events:
            return ""

        lines: list[str] = []
        for e in self._events[-15:]:
            status = "ok" if e.success else f"err: {e.error[:50]}"
            lines.append(f"  {e.tool_name}({e.target[:40]}) = {status}")

        return "\n".join(lines)

    def get_diff_summary(self) -> str:
        if not self.state.applied_patches:
            return ""

        lines: list[str] = []
        for p in self.state.applied_patches[-10:]:
            lines.append(f"  {p['file']}: {p.get('summary', 'edited')}")
        return "\n".join(lines)

    def get_state_snapshot(self) -> SessionState:
        return self.state.model_copy()

    def mark_clean(self) -> None:
        self._dirty = False

    def reset(self) -> None:
        self.state = SessionState()
        self._events.clear()
        self._dirty = True


def track_tool_call(
    tracker: StateTracker,
    tool_name: str,
    target: str,
    success: bool = True,
    summary: str = "",
    error: str = "",
    diff_preview: str = "",
    duration_ms: float = 0.0,
) -> ToolEvent:
    """Convenience function to record a tool call."""
    event = ToolEvent(
        tool_name=tool_name,
        target=target,
        success=success,
        summary=summary,
        error=error,
        diff_preview=diff_preview,
        duration_ms=duration_ms,
    )
    tracker.add_tool_event(event)

    if not success and error:
        tracker.record_error(f"{tool_name}({target}): {error}")

    if tool_name in ("file_write", "edit") and success:
        tracker.record_patch(target, diff_preview, summary)

    if tool_name == "file_read" and success:
        tracker.record_file_open(target)

    return event
