"""Pydantic models for the skill system."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pathlib import Path

from pydantic import BaseModel, Field


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SkillStatus(str, Enum):
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    LOADING = "loading"
    ERROR = "error"


class SkillTrigger(BaseModel):
    """Defines when a skill should auto-activate."""
    keywords: list[str] = Field(default_factory=list)
    file_patterns: list[str] = Field(default_factory=list)
    description_patterns: list[str] = Field(default_factory=list)
    min_complexity: int = 0


class SkillTools(BaseModel):
    """Tools the skill requires."""
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    denied: list[str] = Field(default_factory=list)


class SkillRAG(BaseModel):
    """RAG configuration for the skill."""
    enabled: bool = False
    docs_path: str = "docs/"
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5


class SkillMemory(BaseModel):
    """Memory configuration for the skill."""
    enabled: bool = True
    max_entries: int = 1000
    decay_days: int = 30


class SkillWorkflow(BaseModel):
    """Workflow steps defined by the skill."""
    name: str = ""
    steps: list[str] = Field(default_factory=list)
    auto_follow: bool = True


class SkillManifest(BaseModel):
    """Complete skill manifest (skill.yaml)."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    triggers: SkillTrigger = Field(default_factory=SkillTrigger)
    priority: int = 50
    dependencies: list[str] = Field(default_factory=list)
    tools: SkillTools = Field(default_factory=SkillTools)
    permissions: list[str] = Field(default_factory=list)
    memory: SkillMemory = Field(default_factory=SkillMemory)
    rag: SkillRAG = Field(default_factory=SkillRAG)
    workflow: SkillWorkflow = Field(default_factory=SkillWorkflow)
    auto_activate: bool = True
    project_aware: bool = False
    min_score: float = 0.6

    class Config:
        json_schema_extra = {
            "example": {
                "name": "django-expert",
                "version": "1.0.0",
                "description": "Expert Django development assistant",
                "tags": ["django", "python", "web"],
                "auto_activate": True,
            }
        }


class SkillContent(BaseModel):
    """Loaded content files for a skill."""
    system_prompt: str = ""
    workflow: str = ""
    examples: str = ""
    memory_seed: str = ""


class Skill(BaseModel):
    """Fully loaded skill with manifest and content."""
    manifest: SkillManifest
    content: SkillContent = Field(default_factory=SkillContent)
    path: Path
    status: SkillStatus = SkillStatus.INSTALLED
    doc_chunks: list[dict[str, Any]] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_used: str = ""
    avg_score: float = 0.0
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.5

    def record_use(self, success: bool, score: float = 0.0) -> None:
        self.usage_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.last_used = _utcnow()
        total = self.success_count + self.failure_count
        self.avg_score = ((self.avg_score * (total - 1)) + score) / total


class SkillSearchResult(BaseModel):
    """Result from skill search/matching."""
    skill_name: str
    score: float
    reason: str = ""
    manifest: SkillManifest | None = None


class SkillRegistryEntry(BaseModel):
    """Entry in the skill registry database."""
    name: str
    version: str
    description: str
    author: str
    tags: str  # JSON array
    source: str  # local, github, url
    source_url: str = ""
    installed_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    status: str = "installed"
    usage_count: int = 0
    success_count: int = 0
    avg_score: float = 0.0
    embedding: str = ""  # JSON array of floats


class SkillMemoryEntry(BaseModel):
    """Entry in skill memory."""
    id: str = ""
    skill_name: str
    entry_type: str  # fix, pattern, workflow, solution
    content: str
    context: str = ""
    success: bool = True
    score: float = 0.5
    times_used: int = 0
    created_at: str = Field(default_factory=_utcnow)
    last_used: str = ""
    tags: str = ""  # JSON array
