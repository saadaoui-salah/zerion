from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

from rich.text import Text

from zerion_core.config import settings


def unified_diff(old: str | None, new: str, path: str) -> list[str]:
    old_lines = (old or "").splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    if not old_lines and not old:
        old_lines = []
    return list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def diff_stats(old: str | None, new: str) -> tuple[int, int]:
    old_set = (old or "").splitlines()
    new_set = new.splitlines()
    diff = list(difflib.ndiff(old_set, new_set))
    added = sum(1 for d in diff if d.startswith("+ "))
    removed = sum(1 for d in diff if d.startswith("- "))
    return added, removed


def render_diff_lines(lines: list[str]) -> Text:
    """Render unified diff with git-style green + / red - coloring."""
    text = Text()
    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            text.append(line + "\n", style="bold white")
        elif line.startswith("@@"):
            text.append(line + "\n", style="bold cyan")
        elif line.startswith("+"):
            text.append(line + "\n", style="bold #3fb950 on #0d1117")
        elif line.startswith("-"):
            text.append(line + "\n", style="bold #f85149 on #0d1117")
        else:
            text.append(line + "\n", style="#8b949e")
    return text


def render_ndiff_preview(old: str | None, new: str, path: str, max_lines: int = 80) -> Text:
    """Compact +/- preview for new or edited files."""
    text = Text()
    text.append(f"📄 {path}\n", style="bold white")
    if old is None or old == "":
        for i, line in enumerate(new.splitlines()[:max_lines]):
            text.append(f"+ {line}\n", style="bold #3fb950")
        if new.count("\n") > max_lines:
            text.append(f"  … {new.count(chr(10)) - max_lines} more lines\n", style="dim")
        return text

    lines = unified_diff(old, new, path)
    if not lines:
        text.append("  (no changes)\n", style="dim")
        return text
    for line in lines[:max_lines]:
        if line.startswith("+"):
            text.append(line + "\n", style="bold #3fb950 on #0d1117")
        elif line.startswith("-"):
            text.append(line + "\n", style="bold #f85149 on #0d1117")
        elif line.startswith("@@"):
            text.append(line + "\n", style="cyan")
        elif not line.startswith(("---", "+++")):
            text.append("  " + line + "\n", style="#6e7681")
    return text


def render_side_by_side(old: str | None, new: str, path: str, context_lines: int = 3) -> Text:
    """Render a side-by-side diff with line numbers, matching the editor-style layout."""
    old_lines = (old or "").splitlines()
    new_lines = new.splitlines()
    text = Text()

    text.append(f"← Edit {path}\n", style="bold #4fc1ff")

    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    opcodes = sm.get_opcodes()

    if not opcodes or (len(opcodes) == 1 and opcodes[0][0] == "equal"):
        text.append("\n", style="dim")
        return text

    # Build hunks: only regions around changes + context
    hunks: list[tuple[int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue
        start_i = max(0, i1 - context_lines)
        end_i = min(len(old_lines), i2 + context_lines)
        start_j = max(0, j1 - context_lines)
        end_j = min(len(new_lines), j2 + context_lines)
        hunks.append((start_i, end_i, start_j, end_j))

    if not hunks:
        text.append("\n", style="dim")
        return text

    # Merge overlapping hunks
    merged: list[list[int]] = []
    for h in hunks:
        if merged and h[0] <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], h[1])
            merged[-1][3] = max(merged[-1][3], h[3])
        else:
            merged.append(list(h))

    gutter = max(3, len(str(len(old_lines))))

    for h_start_i, h_end_i, h_start_j, h_end_j in merged:
        i = h_start_i
        j = h_start_j

        while i < h_end_i or j < h_end_j:
            # Find opcodes that overlap current position
            matched_op = None
            for tag, i1, i2, j1, j2 in opcodes:
                if tag == "equal":
                    continue
                if i1 <= i < i2 and j1 <= j < j2:
                    matched_op = (tag, i1, i2, j1, j2)
                    break

            if matched_op:
                tag, i1, i2, j1, j2 = matched_op
                # Render all lines in this change block
                while i < i2 and j < j2:
                    old_line = old_lines[i] if i < len(old_lines) else ""
                    new_line = new_lines[j] if j < len(new_lines) else ""

                    # Left side: removed line
                    text.append(f" {i+1:>{gutter}} ", style="#6e7681")
                    text.append(f"-", style="bold #f85149")
                    text.append(f" {old_line}\n", style="#f85149")
                    # Right side: added line
                    text.append(f" {j+1:>{gutter}} ", style="#6e7681")
                    text.append(f"+", style="bold #3fb950")
                    text.append(f" {new_line}\n", style="#3fb950")
                    i += 1
                    j += 1

                # Handle unequal lengths (delete or insert)
                while i < i2:
                    old_line = old_lines[i] if i < len(old_lines) else ""
                    text.append(f" {i+1:>{gutter}} ", style="#6e7681")
                    text.append(f"-", style="bold #f85149")
                    text.append(f" {old_line}\n", style="#f85149")
                    text.append(f" {'':>{gutter}} ", style="#6e7681")
                    text.append(f" \n", style="#6e7681")
                    i += 1

                while j < j2:
                    new_line = new_lines[j] if j < len(new_lines) else ""
                    text.append(f" {'':>{gutter}} ", style="#6e7681")
                    text.append(f" \n", style="#6e7681")
                    text.append(f" {j+1:>{gutter}} ", style="#6e7681")
                    text.append(f"+", style="bold #3fb950")
                    text.append(f" {new_line}\n", style="#3fb950")
                    j += 1
            else:
                # Context line (equal)
                line = old_lines[i] if i < len(old_lines) else ""
                text.append(f" {i+1:>{gutter}} ", style="#6e7681")
                text.append(f"  {line}\n", style="#8b949e")
                i += 1
                j += 1

        text.append("\n")

    return text


def git_status_short(workspace: Path | None = None) -> dict[str, str | list[str]]:
    root = (workspace or settings.workspace).resolve()
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        stat = subprocess.check_output(
            ["git", "diff", "--stat", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return {"branch": branch, "status": status.splitlines() if status else [], "stat": stat}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"branch": "", "status": [], "stat": ""}


def git_diff_file(path: str, workspace: Path | None = None) -> str:
    root = (workspace or settings.workspace).resolve()
    try:
        return subprocess.check_output(
            ["git", "diff", "--no-color", "--", path],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
