"""Project memory: persistent 'brain file' for each project.

This is ALWAYS injected into context. It evolves over time as the agent
works on the project, accumulating decisions, patterns, bugs, and structure.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zerion_core.config import settings
from zerion_core.llm.ollama import OllamaClient
from zerion_core.llm.model_router import ModelRouter

_PROJECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_brains (
    project_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER DEFAULT 1
);
"""

EXTRACT_BRAIN_SYSTEM = """You are a project memory manager. Given new information about a project, extract and maintain a structured "brain file".

Return JSON only:
{
  "summary": "one paragraph project overview",
  "key_decisions": ["decision 1", "decision 2"],
  "known_bugs": ["bug 1"],
  "important_files": {"path": "description"},
  "patterns": ["pattern 1"],
  "conventions": ["convention 1"],
  "api_surface": ["endpoint/func 1"],
  "test_commands": ["command 1"],
  "tech_stack": ["tech 1"],
  "architecture": "brief architecture description"
}

Only include NEW information not already in existing brain. If no new info, return empty arrays.
"""


class ProjectBrain:
    """Persistent project intelligence that evolves over time."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.summary: str = ""
        self.key_decisions: list[str] = []
        self.known_bugs: list[str] = []
        self.important_files: dict[str, str] = {}
        self.patterns: list[str] = []
        self.conventions: list[str] = []
        self.api_surface: list[str] = []
        self.test_commands: list[str] = []
        self.tech_stack: list[str] = []
        self.architecture: str = ""
        self.updated_at: str = ""
        self.version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "summary": self.summary,
            "key_decisions": self.key_decisions,
            "known_bugs": self.known_bugs,
            "important_files": self.important_files,
            "patterns": self.patterns,
            "conventions": self.conventions,
            "api_surface": self.api_surface,
            "test_commands": self.test_commands,
            "tech_stack": self.tech_stack,
            "architecture": self.architecture,
            "updated_at": self.updated_at,
            "version": self.version,
        }

    def format_for_context(self) -> str:
        """Format the brain file for LLM context injection."""
        if not self.summary and not self.key_decisions:
            return ""

        lines: list[str] = [f"## Project Brain: {self.project_id}"]

        if self.summary:
            lines.append(f"\n{self.summary}")

        if self.architecture:
            lines.append(f"\n### Architecture\n{self.architecture}")

        if self.tech_stack:
            lines.append(f"\n### Tech Stack\n{', '.join(self.tech_stack)}")

        if self.key_decisions:
            lines.append("\n### Key Decisions")
            for d in self.key_decisions[-15:]:
                lines.append(f"- {d}")

        if self.known_bugs:
            lines.append("\n### Known Bugs")
            for b in self.known_bugs[-10:]:
                lines.append(f"- {b}")

        if self.important_files:
            lines.append("\n### Important Files")
            for path, desc in list(self.important_files.items())[-15:]:
                lines.append(f"- `{path}`: {desc}")

        if self.patterns:
            lines.append("\n### Patterns")
            for p in self.patterns[-10:]:
                lines.append(f"- {p}")

        if self.conventions:
            lines.append("\n### Conventions")
            for c in self.conventions[-10:]:
                lines.append(f"- {c}")

        if self.api_surface:
            lines.append("\n### API Surface")
            for a in self.api_surface[-10:]:
                lines.append(f"- {a}")

        if self.test_commands:
            lines.append("\n### Test Commands")
            for t in self.test_commands[-5:]:
                lines.append(f"- `{t}`")

        lines.append(f"\n_Updated: {self.updated_at[:10]} | v{self.version}_")
        return "\n".join(lines)


class ProjectBrainStore:
    """SQLite-backed persistent project brain storage."""

    def __init__(self) -> None:
        self._db_path = settings.memory_root / "longterm.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path), timeout=10.0)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(_PROJECT_SCHEMA)
        conn.commit()

    def get_brain(self, project_id: str) -> ProjectBrain:
        """Load or create a project brain."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT data, version, updated_at FROM project_brains WHERE project_id = ?",
            (project_id,),
        ).fetchone()

        if row:
            brain_data = json.loads(row["data"])
            brain = ProjectBrain(project_id=project_id)
            brain.summary = brain_data.get("summary", "")
            brain.key_decisions = brain_data.get("key_decisions", [])
            brain.known_bugs = brain_data.get("known_bugs", [])
            brain.important_files = brain_data.get("important_files", {})
            brain.patterns = brain_data.get("patterns", [])
            brain.conventions = brain_data.get("conventions", [])
            brain.api_surface = brain_data.get("api_surface", [])
            brain.test_commands = brain_data.get("test_commands", [])
            brain.tech_stack = brain_data.get("tech_stack", [])
            brain.architecture = brain_data.get("architecture", "")
            brain.updated_at = row["updated_at"]
            brain.version = row["version"]
            return brain

        return ProjectBrain(project_id=project_id)

    def save_brain(self, brain: ProjectBrain) -> None:
        """Save a project brain."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        brain.updated_at = now
        conn.execute(
            """INSERT OR REPLACE INTO project_brains
               (project_id, data, updated_at, version)
               VALUES (?, ?, ?, ?)""",
            (
                brain.project_id,
                json.dumps(brain.to_dict(), ensure_ascii=False),
                now,
                brain.version,
            ),
        )
        conn.commit()

    def list_brains(self) -> list[str]:
        """List all project IDs with brain files."""
        conn = self._get_conn()
        rows = conn.execute("SELECT project_id FROM project_brains").fetchall()
        return [r["project_id"] for r in rows]


class ProjectBrainManager:
    """High-level manager for project brain updates using LLM extraction."""

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm
        self.store = ProjectBrainStore()

    async def update_from_output(
        self,
        project_id: str,
        agent_output: str,
        context: str = "",
    ) -> ProjectBrain:
        """Extract new knowledge from agent output and merge into project brain."""
        brain = self.store.get_brain(project_id)
        existing_text = brain.format_for_context()

        prompt = f"## Existing Brain\n{existing_text}\n\n## New Output\n{agent_output[:3000]}"

        try:
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=ModelRouter.for_task("memory_extraction"),
                system=EXTRACT_BRAIN_SYSTEM,
                json_mode=True,
                temperature=0.1,
            )
            extracted = json.loads(resp.content)
        except (json.JSONDecodeError, Exception):
            return brain

        # Merge extracted info
        if extracted.get("summary"):
            brain.summary = extracted["summary"]
        if extracted.get("architecture"):
            brain.architecture = extracted["architecture"]
        if extracted.get("tech_stack"):
            brain.tech_stack = list(set(brain.tech_stack + extracted["tech_stack"]))[:20]
        if extracted.get("key_decisions"):
            brain.key_decisions = self._merge_unique(brain.key_decisions, extracted["key_decisions"])
        if extracted.get("known_bugs"):
            brain.known_bugs = self._merge_unique(brain.known_bugs, extracted["known_bugs"])
        if extracted.get("important_files"):
            if isinstance(extracted["important_files"], dict):
                brain.important_files.update(extracted["important_files"])
            elif isinstance(extracted["important_files"], list):
                for f in extracted["important_files"]:
                    if isinstance(f, str) and ":" in f:
                        k, v = f.split(":", 1)
                        brain.important_files[k.strip()] = v.strip()
                    elif isinstance(f, str):
                        brain.important_files[f] = ""
        if extracted.get("patterns"):
            brain.patterns = self._merge_unique(brain.patterns, extracted["patterns"])
        if extracted.get("conventions"):
            brain.conventions = self._merge_unique(brain.conventions, extracted["conventions"])
        if extracted.get("api_surface"):
            brain.api_surface = self._merge_unique(brain.api_surface, extracted["api_surface"])
        if extracted.get("test_commands"):
            brain.test_commands = self._merge_unique(brain.test_commands, extracted["test_commands"])

        brain.version += 1
        self.store.save_brain(brain)
        return brain

    def add_decision(self, project_id: str, decision: str) -> None:
        brain = self.store.get_brain(project_id)
        if decision not in brain.key_decisions:
            brain.key_decisions.append(decision)
            brain.version += 1
            self.store.save_brain(brain)

    def add_bug(self, project_id: str, bug: str) -> None:
        brain = self.store.get_brain(project_id)
        if bug not in brain.known_bugs:
            brain.known_bugs.append(bug)
            brain.version += 1
            self.store.save_brain(brain)

    def add_pattern(self, project_id: str, pattern: str) -> None:
        brain = self.store.get_brain(project_id)
        if pattern not in brain.patterns:
            brain.patterns.append(pattern)
            brain.version += 1
            self.store.save_brain(brain)

    def get_context(self, project_id: str) -> str:
        """Get the brain file formatted for LLM context."""
        brain = self.store.get_brain(project_id)
        return brain.format_for_context()

    def _merge_unique(self, existing: list[str], new: list[str], max_items: int = 20) -> list[str]:
        result = list(existing)
        for item in new:
            item_lower = item.lower().strip()
            if not any(item_lower in e.lower() or e.lower() in item_lower for e in result):
                result.append(item)
        return result[-max_items:]
