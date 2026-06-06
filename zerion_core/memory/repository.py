from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zerion_core.config import settings


class RepositoryMemory:
    """Repository-level intelligence: decisions, bugs, patterns, implementations."""

    FILES = {
        "architecture": "ARCHITECTURE.md",
        "project_map": "PROJECT_MAP.md",
        "bugs": "BUG_HISTORY.md",
        "decisions": "DECISIONS.md",
        "lessons": "LESSONS.md",
    }

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.repo_intel_dir
        self.json_path = settings.memory_root / "repository.json"
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.json_path.exists():
            self._write_json(
                {
                    "architecture_decisions": [],
                    "bugs_fixed": [],
                    "patterns": [],
                    "implementations": [],
                }
            )

    def _read_json(self) -> dict[str, Any]:
        return json.loads(self.json_path.read_text(encoding="utf-8"))

    def _write_json(self, data: dict[str, Any]) -> None:
        self.json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_decision(self, decision: str, project: str = "") -> None:
        data = self._read_json()
        data["architecture_decisions"].append(
            {"text": decision, "project": project, "at": datetime.now(timezone.utc).isoformat()}
        )
        self._write_json(data)

    def add_bug_fix(self, bug: str, fix: str, project: str = "") -> None:
        data = self._read_json()
        data["bugs_fixed"].append(
            {
                "bug": bug,
                "fix": fix,
                "project": project,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._write_json(data)

    def add_pattern(self, pattern: str, tags: list[str] | None = None) -> None:
        data = self._read_json()
        data["patterns"].append(
            {"text": pattern, "tags": tags or [], "at": datetime.now(timezone.utc).isoformat()}
        )
        self._write_json(data)

    def add_implementation(self, name: str, summary: str, project: str = "") -> None:
        data = self._read_json()
        data["implementations"].append(
            {
                "name": name,
                "summary": summary,
                "project": project,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._write_json(data)

    def snapshot(self) -> dict[str, Any]:
        return self._read_json()
