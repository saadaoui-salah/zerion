"""Pydantic models for the session management system."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: MessageRole
    content: str
    timestamp: str = Field(default_factory=_utcnow)
    token_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolEvent(BaseModel):
    """Tracks a single tool execution (file read, patch, command, etc.)."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: str = Field(default_factory=_utcnow)
    tool_name: str  # "file_read", "file_write", "edit", "command", "retrieval"
    target: str = ""  # file path, command string, etc.
    success: bool = True
    summary: str = ""
    diff_preview: str = ""
    error: str = ""
    duration_ms: float = 0.0


class SessionState(BaseModel):
    """Runtime state snapshot for crash recovery."""
    open_files: list[str] = Field(default_factory=list)
    last_errors: list[str] = Field(default_factory=list)
    applied_patches: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    active_task: str = ""
    current_goal: str = ""


class SessionMeta(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: str = ""
    title: str = ""
    summary: str = ""
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    message_count: int = 0
    total_tokens: int = 0
    tags: list[str] = Field(default_factory=list)
    is_branch: bool = False
    branch_parent_id: str = ""


class SessionData(BaseModel):
    """Full session data stored in SQLite."""
    meta: SessionMeta
    messages: list[Message] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    state: SessionState = Field(default_factory=SessionState)
    summary: str = ""
    summary_updated_at: str = ""


class ProjectMemory(BaseModel):
    """Persistent project-level memory (survives across sessions)."""
    project_id: str
    architecture_decisions: list[str] = Field(default_factory=list)
    known_bugs: list[str] = Field(default_factory=list)
    important_files: list[str] = Field(default_factory=list)
    coding_conventions: list[str] = Field(default_factory=list)
    api_patterns: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    description: str = ""
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)


class SessionSearchResult(BaseModel):
    session_id: str
    title: str
    summary: str
    score: float
    snippet: str = ""
    created_at: str = ""
    project_id: str = ""
