"""Skill installer: installs skills from GitHub, URLs, or local paths."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from zerion_core.skills.loader import SkillLoader
from zerion_core.skills.models import SkillRegistryEntry, _utcnow
from zerion_core.skills.registry import SkillRegistry


class SkillInstaller:
    """Installs skills from various sources."""

    def __init__(
        self,
        loader: SkillLoader,
        registry: SkillRegistry,
        skills_dir: Path | None = None,
    ) -> None:
        self._loader = loader
        self._registry = registry
        self._skills_dir = skills_dir or Path("skills")

    async def install(self, source: str) -> tuple[bool, str]:
        """Install a skill from a source string.

        Sources:
          - "skill-name" (local/built-in)
          - "github:user/repo" or "github:user/repo/path/to/skill"
          - "https://github.com/org/repo"
          - "/path/to/local/skill"
        """
        source = source.strip()

        if source.startswith("/") or source.startswith("."):
            return await self._install_local(Path(source))

        if source.startswith("github:"):
            return await self._install_github(source[7:])

        if "github.com" in source:
            return await self._install_github_url(source)

        return await self._install_builtin(source)

    async def uninstall(self, name: str) -> tuple[bool, str]:
        """Uninstall a skill."""
        skill_dir = self._skills_dir / name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

        self._loader.unload(name)
        self._registry.delete_skill(name)
        return True, f"Uninstalled {name}"

    async def update(self, name: str) -> tuple[bool, str]:
        """Update a skill by reloading from disk."""
        skill = self._loader.reload(name)
        if not skill:
            return False, f"Failed to reload {name}"

        entry = self._registry.get_skill(name)
        if entry:
            entry.version = skill.manifest.version
            entry.description = skill.manifest.description
            entry.updated_at = _utcnow()
            self._registry.register_skill(entry)

        return True, f"Updated {name} to v{skill.manifest.version}"

    async def _install_local(self, path: Path) -> tuple[bool, str]:
        """Install from a local directory."""
        if not path.exists():
            return False, f"Path not found: {path}"

        if not (path / "skill.yaml").exists():
            return False, f"No skill.yaml found in {path}"

        skill = self._loader.load_skill(str(path.name), force=True)
        if not skill:
            return False, f"Failed to load skill from {path}"

        dest = self._skills_dir / skill.manifest.name
        if dest.exists():
            shutil.rmtree(dest)

        if path.parent != self._skills_dir.parent:
            shutil.copytree(path, dest)

        entry = self._make_registry_entry(skill.manifest.name, skill, "local", str(path))
        self._registry.register_skill(entry)

        return True, f"Installed {skill.manifest.name} v{skill.manifest.version}"

    async def _install_github(self, repo_path: str) -> tuple[bool, str]:
        """Install from a GitHub repo path (user/repo or user/repo/path)."""
        parts = repo_path.strip("/").split("/")
        if len(parts) < 2:
            return False, "Invalid GitHub path. Use: github:user/repo or github:user/repo/path"

        user, repo = parts[0], parts[1]
        subpath = "/".join(parts[2:]) if len(parts) > 2 else ""
        url = f"https://github.com/{user}/{repo}.git"

        return await self._clone_and_install(url, subpath, f"github:{repo_path}")

    async def _install_github_url(self, url: str) -> tuple[bool, str]:
        """Install from a GitHub URL."""
        url = url.rstrip("/")
        if not url.endswith(".git"):
            url += ".git"

        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            return False, "Invalid GitHub URL"

        user, repo = match.group(1), match.group(2)
        return await self._clone_and_install(url, "", f"github:{user}/{repo}")

    async def _install_builtin(self, name: str) -> tuple[bool, str]:
        """Install a built-in skill (already in skills/ directory)."""
        # First check workspace skills directory
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
            return False, f"Skill '{name}' not found. Available sources: local path, github:user/repo, or URL"
        
        if not (skill_dir / "skill.yaml").exists():
            return False, f"Skill '{name}' has no skill.yaml file"
        
        # Load the skill
        skill = self._loader.load_skill(str(skill_dir), force=True)
        if not skill:
            return False, f"Failed to load skill '{name}'"
        
        # Register it
        entry = self._make_registry_entry(name, skill, "local", str(skill_dir))
        self._registry.register_skill(entry)
        
        return True, f"Installed {name} v{skill.manifest.version}"

    async def _clone_and_install(
        self,
        git_url: str,
        subpath: str,
        source: str,
    ) -> tuple[bool, str]:
        """Clone a repo and install the skill from it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            result = subprocess.run(
                ["git", "clone", "--depth", "1", git_url, str(tmp / "repo")],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return False, f"Git clone failed: {result.stderr[:200]}"

            repo_dir = tmp / "repo"
            if subpath:
                skill_dir = repo_dir / subpath
            else:
                # Find skill.yaml in repo root or first subdirectory
                skill_dir = self._find_skill_in_repo(repo_dir)

            if not skill_dir or not (skill_dir / "skill.yaml").exists():
                return False, "No skill.yaml found in repository"

            skill = self._loader.load_skill(str(skill_dir), force=True)
            if not skill:
                return False, "Failed to load skill from repository"

            dest = self._skills_dir / skill.manifest.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill_dir, dest)

            entry = self._make_registry_entry(skill.manifest.name, skill, "github", source)
            self._registry.register_skill(entry)

            return True, f"Installed {skill.manifest.name} v{skill.manifest.version} from {source}"

    def _find_skill_in_repo(self, repo_dir: Path) -> Path | None:
        """Find skill directory in a repository."""
        if (repo_dir / "skill.yaml").exists():
            return repo_dir

        for child in repo_dir.iterdir():
            if child.is_dir() and (child / "skill.yaml").exists():
                return child

        return None

    def _make_registry_entry(
        self,
        name: str,
        skill: Any,
        source: str,
        source_url: str,
    ) -> SkillRegistryEntry:
        """Create a registry entry for an installed skill."""
        manifest = skill.manifest if hasattr(skill, "manifest") else skill
        return SkillRegistryEntry(
            name=name,
            version=getattr(manifest, "version", "1.0.0"),
            description=getattr(manifest, "description", ""),
            author=getattr(manifest, "author", ""),
            tags=json.dumps(getattr(manifest, "tags", [])),
            source=source,
            source_url=source_url,
            installed_at=_utcnow(),
            updated_at=_utcnow(),
            status="installed",
        )

    def export_skill(self, name: str, dest: Path) -> tuple[bool, str]:
        """Export a skill to a directory."""
        skill_dir = self._skills_dir / name
        if not skill_dir.exists():
            return False, f"Skill {name} not found"

        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_dir, dest / name, dirs_exist_ok=True)
        return True, f"Exported {name} to {dest}"

    def import_skill(self, path: Path) -> tuple[bool, str]:
        """Import a skill from a directory."""
        return self._install_local(path)

    async def uninstall(self, name: str) -> tuple[bool, str]:
        """Uninstall a skill."""
        # Check if skill exists in registry
        entry = self._registry.get_skill(name)
        if not entry:
            return False, f"Skill '{name}' not found in registry"
        
        # Delete from registry (cascades to memory and activations)
        self._registry.delete_skill(name)
        
        return True, f"Uninstalled {name}"
