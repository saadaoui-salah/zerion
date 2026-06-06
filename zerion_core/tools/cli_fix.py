from __future__ import annotations

import re
from pathlib import Path

from zerion_core.tools.project_map import ensure_dir, is_windows, remove_dir


def parse_mkdir_path(cmd: str) -> str | None:
    cmd = cmd.strip()
    # Handle quoted paths first
    m = re.match(r"^mkdir\s+(?:-p\s+)?['\"]([^'\"]+)['\"]", cmd, re.I)
    if m:
        return m.group(1).replace("\\", "/")
    # Handle unquoted paths
    m = re.match(r"^mkdir\s+(?:-p\s+)?([^\s;]+)", cmd, re.I)
    if m:
        return m.group(1).replace("\\", "/")
    return None


def parse_rmdir_path(cmd: str) -> str | None:
    cmd = cmd.strip()
    # Handle quoted paths
    for pattern in (
        r"^rmdir\s+(?:/s\s+)?(?:/q\s+)?['\"]([^'\"]+)['\"]",
        r"^rm\s+-rf\s+['\"]([^'\"]+)['\"]",
    ):
        m = re.match(pattern, cmd, re.I)
        if m:
            return m.group(1).replace("\\", "/")
    # Handle unquoted paths
    for pattern in (
        r"^rmdir\s+(?:/s\s+)?(?:/q\s+)?([^\s;]+)",
        r"^rm\s+-rf\s+([^\s;]+)",
    ):
        m = re.match(pattern, cmd, re.I)
        if m:
            return m.group(1).replace("\\", "/")
    return None


def try_pathlib_fallback(cmd: str, error: str, workspace: Path) -> tuple[bool, str] | None:
    """Handle mkdir/rmdir via Python instead of shell."""
    lower_err = error.lower()

    mkdir_path = parse_mkdir_path(cmd)
    if mkdir_path:
        if "already exists" in lower_err or "cannot create" in lower_err:
            ok, msg = ensure_dir(mkdir_path, workspace)
            return ok, f"[auto-fix] {msg}"
        if is_windows() and ("syntax" in lower_err or "incorrect" in lower_err):
            ok, msg = ensure_dir(mkdir_path, workspace)
            return ok, f"[auto-fix] {msg}"

    rmdir_path = parse_rmdir_path(cmd)
    if rmdir_path:
        if "cannot find" in lower_err or "not find" in lower_err or "does not exist" in lower_err:
            return True, f"[auto-fix] skip rmdir (not found): {rmdir_path}"
        if "already exists" not in lower_err:
            ok, msg = remove_dir(rmdir_path, workspace)
            return ok, f"[auto-fix] {msg}"

    return None


def auto_fix_command(cmd: str, error: str, workspace: Path) -> str | None:
    """Return a corrected command string, or None if handled via skip/pathlib."""
    lower_err = error.lower()
    cmd_stripped = cmd.strip()

    # mkdir when already exists → no retry needed (handled by fallback)
    if parse_mkdir_path(cmd) and "already exists" in lower_err:
        return None

    # rmdir when missing → no retry
    if parse_rmdir_path(cmd) and ("cannot find" in lower_err or "not find" in lower_err):
        return None

    if is_windows():
        # mkdir static/css → mkdir static\css
        if cmd_stripped.lower().startswith("mkdir ") and "/" in cmd_stripped:
            parts = cmd_stripped.split(None, 1)
            if len(parts) == 2:
                path = parts[1].strip().strip('"').replace("/", "\\")
                return f"mkdir {path}"

        # Use python -c for nested mkdir on Windows
        mkdir_path = parse_mkdir_path(cmd)
        if mkdir_path and ("syntax" in lower_err or "incorrect" in lower_err):
            return (
                f'python -c "from pathlib import Path; '
                f"Path(r'{mkdir_path}').mkdir(parents=True, exist_ok=True)\""
            )

    return None


def should_skip_command(cmd: str, workspace: Path, dirs: list[str]) -> tuple[bool, str]:
    """Skip redundant commands based on known project structure."""
    mkdir_path = parse_mkdir_path(cmd)
    if mkdir_path:
        normalized = mkdir_path.replace("\\", "/")
        if normalized in dirs or (workspace / normalized).is_dir():
            return True, f"skip mkdir (already in project): {mkdir_path}"

    rmdir_path = parse_rmdir_path(cmd)
    if rmdir_path:
        normalized = rmdir_path.replace("\\", "/")
        if normalized not in dirs and not (workspace / normalized).exists():
            return True, f"skip rmdir (not in project): {rmdir_path}"

    return False, ""
