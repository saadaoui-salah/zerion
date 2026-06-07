"""Skill loader: loads, validates, caches, and hot-reloads skills."""

from __future__ import annotations

import hashlib
import json
import shutil
import yaml
from pathlib import Path
from typing import Any, Callable

from zerion_core.skills.models import (
    Skill,
    SkillContent,
    SkillManifest,
    SkillMemory,
    SkillRAG,
    SkillStatus,
    SkillTools,
    SkillTrigger,
    SkillWorkflow,
)


class SkillLoader:
    """Loads skills from disk, validates manifests, caches loaded skills."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or Path("skills")
        self._cache: dict[str, Skill] = {}
        self._file_hashes: dict[str, str] = {}
        self._watchers: list[Callable[[str, str], None]] = []

    @property
    def skills_dir(self) -> Path:
        return self._skills_dir

    def set_skills_dir(self, path: Path) -> None:
        self._skills_dir = path

    def list_skill_dirs(self) -> list[Path]:
        """List all skill directories (excluding _index)."""
        if not self._skills_dir.exists():
            return []
        return [
            d for d in self._skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        ]

    def load_skill(self, name: str, force: bool = False) -> Skill | None:
        """Load a single skill by name."""
        if name in self._cache and not force:
            return self._cache[name]

        # First check the primary skills directory
        skill_dir = self._skills_dir / name
        
        # If not found, check the package's built-in skills directory
        if not skill_dir.exists():
            import zerion_core
            package_dir = Path(zerion_core.__file__).parent.parent / "skills"
            if (package_dir / name).exists():
                skill_dir = package_dir / name
        
        # If still not found, check current working directory
        if not skill_dir.exists():
            cwd_skills = Path.cwd() / "skills" / name
            if cwd_skills.exists():
                skill_dir = cwd_skills

        if not skill_dir.exists():
            return None

        manifest_path = skill_dir / "skill.yaml"
        if not manifest_path.exists():
            return None

        try:
            manifest = self._load_manifest(manifest_path)
            content = self._load_content(skill_dir)
            skill = Skill(
                manifest=manifest,
                content=content,
                path=skill_dir,
                status=SkillStatus.INSTALLED,
            )
            skill.doc_chunks = self._load_doc_chunks(skill_dir, manifest)
            self._cache[name] = skill
            self._file_hashes[name] = self._hash_dir(skill_dir)
            return skill
        except Exception as e:
            return None

    def load_all(self) -> dict[str, Skill]:
        """Load all skills from the skills directory and built-in locations."""
        skills = {}
        
        # Load from primary skills directory
        for skill_dir in self.list_skill_dirs():
            skill = self.load_skill(skill_dir.name)
            if skill:
                skills[skill.manifest.name] = skill
        
        # Load from package's built-in skills directory
        try:
            import zerion_core
            package_skills_dir = Path(zerion_core.__file__).parent.parent / "skills"
            if package_skills_dir.exists() and package_skills_dir != self._skills_dir:
                for skill_dir in package_skills_dir.iterdir():
                    if skill_dir.is_dir() and not skill_dir.name.startswith("_") and not skill_dir.name.startswith("."):
                        if skill_dir.name not in skills:
                            skill = self.load_skill(skill_dir.name)
                            if skill:
                                skills[skill.manifest.name] = skill
        except Exception:
            pass
        
        return skills

    def unload(self, name: str) -> bool:
        """Unload a skill from cache."""
        if name in self._cache:
            del self._cache[name]
            self._file_hashes.pop(name, None)
            return True
        return False

    def reload(self, name: str) -> Skill | None:
        """Hot-reload a skill from disk."""
        self.unload(name)
        return self.load_skill(name, force=True)

    def check_for_changes(self) -> list[tuple[str, str]]:
        """Check for file changes. Returns list of (name, 'changed'|'removed')."""
        changes = []
        for name, old_hash in list(self._file_hashes.items()):
            skill_dir = self._skills_dir / name
            if not skill_dir.exists():
                changes.append((name, "removed"))
                continue
            new_hash = self._hash_dir(skill_dir)
            if new_hash != old_hash:
                changes.append((name, "changed"))

        for skill_dir in self.list_skill_dirs():
            if skill_dir.name not in self._file_hashes:
                changes.append((skill_dir.name, "added"))

        return changes

    def get_cached(self, name: str) -> Skill | None:
        return self._cache.get(name)

    def get_all_cached(self) -> dict[str, Skill]:
        return dict(self._cache)

    def _load_manifest(self, path: Path) -> SkillManifest:
        """Load and validate skill.yaml manifest."""
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"Invalid manifest at {path}")

        trigger_data = raw.pop("triggers", {})
        if isinstance(trigger_data, dict):
            raw["triggers"] = SkillTrigger(**trigger_data)

        tools_data = raw.pop("tools", {})
        if isinstance(tools_data, dict):
            raw["tools"] = SkillTools(**tools_data)

        memory_data = raw.pop("memory", {})
        if isinstance(memory_data, dict):
            raw["memory"] = SkillMemory(**memory_data)

        rag_data = raw.pop("rag", {})
        if isinstance(rag_data, dict):
            raw["rag"] = SkillRAG(**rag_data)

        workflow_data = raw.pop("workflow", {})
        if isinstance(workflow_data, dict):
            raw["workflow"] = SkillWorkflow(**workflow_data)

        return SkillManifest(**raw)

    def _load_content(self, skill_dir: Path) -> SkillContent:
        """Load markdown content files."""
        content = SkillContent()

        system_file = skill_dir / "system.md"
        if system_file.exists():
            content.system_prompt = system_file.read_text(encoding="utf-8")

        workflow_file = skill_dir / "workflow.md"
        if workflow_file.exists():
            content.workflow = workflow_file.read_text(encoding="utf-8")

        examples_file = skill_dir / "examples.md"
        if examples_file.exists():
            content.examples = examples_file.read_text(encoding="utf-8")

        memory_file = skill_dir / "memory.md"
        if memory_file.exists():
            content.memory_seed = memory_file.read_text(encoding="utf-8")

        return content

    def _load_doc_chunks(self, skill_dir: Path, manifest: SkillManifest) -> list[dict[str, Any]]:
        """Load and chunk documentation files."""
        docs_dir = skill_dir / manifest.rag.docs_path
        if not docs_dir.exists():
            return []

        chunks = []
        for md_file in docs_dir.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            file_chunks = self._chunk_text(
                text,
                chunk_size=manifest.rag.chunk_size,
                chunk_overlap=manifest.rag.chunk_overlap,
                source=str(md_file.relative_to(skill_dir)),
            )
            chunks.extend(file_chunks)

        for txt_file in docs_dir.rglob("*.txt"):
            text = txt_file.read_text(encoding="utf-8")
            file_chunks = self._chunk_text(
                text,
                chunk_size=manifest.rag.chunk_size,
                chunk_overlap=manifest.rag.chunk_overlap,
                source=str(txt_file.relative_to(skill_dir)),
            )
            chunks.extend(file_chunks)

        return chunks

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        source: str = "",
    ) -> list[dict[str, Any]]:
        """Split text into overlapping chunks."""
        chunks = []
        lines = text.split("\n")
        current_chunk: list[str] = []
        current_len = 0

        for line in lines:
            current_chunk.append(line)
            current_len += len(line) + 1

            if current_len >= chunk_size:
                chunk_text = "\n".join(current_chunk)
                chunks.append({
                    "content": chunk_text,
                    "source": source,
                    "start_line": max(0, len(chunks) * (chunk_size // 100)),
                })
                overlap_lines = max(1, chunk_overlap // 100)
                current_chunk = current_chunk[-overlap_lines:]
                current_len = sum(len(l) + 1 for l in current_chunk)

        if current_chunk:
            chunks.append({
                "content": "\n".join(current_chunk),
                "source": source,
                "start_line": max(0, len(chunks) * (chunk_size // 100)),
            })

        return chunks

    def _hash_dir(self, skill_dir: Path) -> str:
        """Compute hash of all files in a skill directory."""
        hasher = hashlib.sha256()
        for f in sorted(skill_dir.rglob("*")):
            if f.is_file() and not f.name.endswith(".pyc"):
                hasher.update(f.read_bytes())
        return hasher.hexdigest()[:16]

    def watch(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for skill changes."""
        self._watchers.append(callback)

    def notify_watchers(self, skill_name: str, change_type: str) -> None:
        for cb in self._watchers:
            try:
                cb(skill_name, change_type)
            except Exception:
                pass
