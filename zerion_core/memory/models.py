from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


def coerce_str(value: Any) -> str:
    """Normalize memory values — LLMs often return lists or dicts instead of strings."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryMetadata(BaseModel):
    importance: float = 0.5
    last_accessed: str = Field(default_factory=_utcnow)
    times_used: int = 0
    confidence: float = 0.8
    created_at: str = Field(default_factory=_utcnow)

    def mark_access(self) -> None:
        self.last_accessed = _utcnow()
        self.times_used += 1


class ShortTermMemory(BaseModel):
    goal: str = ""
    current_task: str = ""
    context: str = ""
    updated_at: str = Field(default_factory=_utcnow)
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)


class EpisodicEntry(BaseModel):
    project: str
    completed_tasks: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=_utcnow)
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)


class SemanticFact(BaseModel):
    key: str
    value: str
    confidence: float = 1.0
    source: str = "agent"
    updated_at: str = Field(default_factory=_utcnow)
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)

    @field_validator("key", "value", mode="before")
    @classmethod
    def _coerce_text_fields(cls, v: Any) -> str:
        return coerce_str(v)


class ProceduralEntry(BaseModel):
    name: str
    description: str = ""
    template: str = ""
    steps: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=_utcnow)
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)


class MethodInfo(BaseModel):
    name: str
    line_number: int = 0
    docstring: str = ""
    params: list[str] = Field(default_factory=list)


class ClassInfo(BaseModel):
    name: str
    line_number: int = 0
    docstring: str = ""
    methods: list[MethodInfo] = Field(default_factory=list)


class FileInfo(BaseModel):
    path: str
    type: str = ""
    size: int = 0
    classes: list[ClassInfo] = Field(default_factory=list)
    functions: list[MethodInfo] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)


class ProjectStructureSnapshot(BaseModel):
    project_path: str
    technologies: list[str] = Field(default_factory=list)
    description: str = ""
    files: list[FileInfo] = Field(default_factory=list)
    indexed_at: str = Field(default_factory=_utcnow)


class ProjectRegistryEntry(BaseModel):
    name: str
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    memory_count: int = 0
    similarity_threshold: float = 0.65
    snapshot: ProjectStructureSnapshot | None = None


class TemporalChange(BaseModel):
    entity: str
    field: str
    old_value: str | None = None
    new_value: str
    reason: str = ""
    timestamp: str = Field(default_factory=_utcnow)


class WorkingMemorySlot(BaseModel):
    key: str
    value: str
    ttl_seconds: int | None = None
    created_at: str = Field(default_factory=_utcnow)


class JsonStore:
    """File-backed JSON store for a memory layer."""

    def __init__(self, directory: Path, filename: str = "store.json") -> None:
        self.path = directory / filename
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_all(self) -> dict[str, Any]:
        return self._read()

    def set(self, key: str, value: Any) -> None:
        data = self._read()
        data[key] = value
        self._write(data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._read().get(key, default)

    def delete(self, key: str) -> None:
        data = self._read()
        data.pop(key, None)
        self._write(data)

    def list_keys(self) -> list[str]:
        return list(self._read().keys())
