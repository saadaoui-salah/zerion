from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, Static, Tree

from zerion_core.cli.diff import git_status_short, render_diff_lines, render_ndiff_preview, render_side_by_side, unified_diff
from zerion_core.config import settings


class Branding(Static):
    """Animated or static branding for Zerion-Core."""
    
    def render(self) -> Text:
        banner = Text()
        banner.append("Z E R I O N ", style="bold #d7ba7d")
        banner.append("C O R E", style="bold #8957e5")
        banner.append(" — ", style="dim")
        banner.append("A I   E N G I N E E R", style="italic #b5cea8")
        return banner


class AgentStrip(Static):
    """Compact horizontal agent status row."""

    def update_agents(self, lines: list[str]) -> None:
        if not lines:
            self.update(Text("No active agents", style="dim italic"))
            return
            
        body = Text()
        for i, line in enumerate(lines):
            if i > 0:
                body.append("  ", style="dim")
            
            # Parse: "Name         ● Status"
            parts = line.split()
            if len(parts) >= 3:
                name = parts[0]
                sym = parts[1]
                status = parts[2]
                
                color = "#808080" # Idle
                if status == "Working":
                    color = "#b5cea8"
                elif status == "Waiting":
                    color = "#d7ba7d"
                elif status == "Error":
                    color = "#f44747"
                
                body.append(f"{sym} ", style=f"bold {color}")
                body.append(f"{name}", style="bold white")
                body.append(f" {status.lower()}", style="dim")
            else:
                body.append(line)
                
        self.update(body)


class TaskBar(Static):
    def set_task(self, task: str) -> None:
        self.update(Text(f"● {task or 'Ready'}", style="bold #3fb950"))


class ActivityPanel(RichLog):
    """Agent-to-agent conversation stream."""

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=True, markup=True, max_lines=300, **kwargs)

    def agent_line(self, stage: str, message: str) -> None:
        color = {
            "router": "#4fc1ff",
            "planner": "#569cd6",
            "implement": "#4ec9b0",
            "review": "#ce9178",
            "qa": "#dcdcaa",
            "user": "#d7ba7d"
        }.get(stage, "#8957e5")
        
        self.write(Text.from_markup(f"[bold {color}]{stage.upper()}[/] [dim]→[/] {message}"))


class CLITerminalPanel(RichLog):
    """Live shell command + output while CLI agent works."""

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=True, markup=True, max_lines=500, **kwargs)
        self.write(Text("Terminal ready\n", style="dim italic"))

    def command(self, cmd: str) -> None:
        self.write(Text(f"\n❯ {cmd}\n", style="bold #d7ba7d"))

    def stream(self, line: str, stream: str = "stdout") -> None:
        style = "#b5cea8" if stream == "stdout" else "#f44747"
        self.write(Text(f"  {line}\n", style=style))

    def done(self, exit_code: int) -> None:
        color = "#b5cea8" if exit_code == 0 else "#f44747"
        sym = "✓" if exit_code == 0 else "✗"
        self.write(Text(f"  {sym} exit {exit_code}\n", style=f"bold {color}"))

    def file_op(self, message: str, ok: bool = True) -> None:
        style = "#b5cea8" if ok else "#f44747"
        sym = "✎" if ok else "✗"
        self.write(Text(f"  {sym} {message}\n", style=f"bold {style}"))

    def idle_note(self, message: str) -> None:
        self.write(Text(f"  … {message}\n", style="dim #808080"))


class DiffViewerPanel(RichLog):
    """Git-style +/- diff for file writes and edits."""

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=True, markup=False, max_lines=400, **kwargs)
        self._change_count = 0
        self.write(Text("Diff viewer — file changes appear here\n", style="dim italic"))

    def show_change(self, path: str, old: str | None, new: str) -> None:
        self._change_count += 1
        header = Text(f"\n── Change #{self._change_count}: ", style="bold #8957e5")
        header.append(path, style="bold white")
        header.append("\n")
        self.write(header)
        self.write(render_side_by_side(old, new, path))

    def show_unified(self, path: str, old: str | None, new: str) -> None:
        lines = unified_diff(old, new, path)
        if lines:
            self.write(render_diff_lines(lines))

    def show_git_diff(self, diff_text: str, path: str = "") -> None:
        if not diff_text:
            return
        title = f"\n── git diff {path}\n" if path else "\n── git diff\n"
        self.write(Text(title, style="bold #ce9178"))
        self.write(render_diff_lines(diff_text.splitlines()))


class GitPanel(Static):
    """Git branch, status, and diff stats."""

    changes: reactive[int] = reactive(0)

    def refresh_status(self) -> None:
        info = git_status_short()
        branch = info.get("branch") or "no repo"
        lines = info.get("status", [])
        stat = info.get("stat", "")

        body = Text()
        body.append(f" {branch}\n", style="bold #ce9178")
        if lines:
            for ln in lines[:12]:
                if ln.startswith("??"):
                    body.append(f"  ? {ln[3:]}\n", style="#808080")
                elif ln.startswith("A") or "A " in ln[:2]:
                    body.append(f"  + {ln[3:]}\n", style="bold #b5cea8")
                elif ln.startswith("M") or "M " in ln[:2]:
                    body.append(f"  ~ {ln[3:]}\n", style="bold #d7ba7d")
                elif ln.startswith("R") or "R " in ln[:2]:
                    body.append(f"  → {ln[3:]}\n", style="bold #4fc1ff")
                elif ln.startswith("D") or "D " in ln[:2]:
                    body.append(f"  - {ln[3:]}\n", style="bold #f44747")
                else:
                    body.append(f"  {ln}\n", style="white")
            if len(lines) > 12:
                body.append(f"  … +{len(lines) - 12} more\n", style="dim")
        else:
            body.append("  clean\n", style="dim #b5cea8")

        self.changes = len(lines)
        self.update(Panel(body, title="GIT", border_style="#ce9178", padding=(0, 1)))


class DashboardPanel(Static):
    """Real-time metrics for the CEO."""
    
    metrics: reactive[dict[str, Any]] = reactive({
        "task_progress": 0,
        "memory_hits": 0,
        "model": settings.default_model,
        "errors": 0,
        "warnings": 0
    })

    def set_model(self, model: str) -> None:
        new_metrics = dict(self.metrics)
        new_metrics["model"] = model
        self.metrics = new_metrics

    def render(self) -> Panel:
        m = self.metrics
        body = Text()
        body.append(f"Model:  ", style="dim")
        body.append(f"{m['model']}\n", style="bold white")
        body.append(f"Memory: ", style="dim")
        body.append(f"{m['memory_hits']} hits\n", style="bold #4fc1ff")
        body.append(f"Status: ", style="dim")
        body.append(f"Healthy\n", style="bold #b5cea8")
        body.append(f"Issues: ", style="dim")
        body.append(f"{m['errors']} errors", style="bold #f44747")
        body.append(", ", style="dim")
        body.append(f"{m['warnings']} warnings", style="bold #d7ba7d")
        
        return Panel(body, title="CEO DASHBOARD", border_style="#569cd6", padding=(0, 1))


class TokenBar(Static):
    tokens: reactive[int] = reactive(0)
    cost: reactive[float] = reactive(0.0)

    def watch_tokens(self, value: int) -> None:
        body = Text()
        body.append(f"⚡ {value:,} tokens\n", style="bold #d7ba7d")
        body.append(f"💰 Est. ${self.cost:.4f}", style="dim")
        self.update(Panel(body, title="USAGE", border_style="#d7ba7d", padding=(0, 1)))



class FileTreePanel(Tree):
    SKIP_DIRS = frozenset({
        ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
        "chroma", ".pytest_cache", ".mypy_cache", "egg-info",
    })
    MAX_DEPTH = 6
    MAX_ENTRIES = 60

    def __init__(self, root: Path, **kwargs) -> None:
        super().__init__(f"📁 {root.name}", **kwargs)
        self.root_path = root.resolve()
        self.reload()

    def reload(self) -> None:
        self.clear()
        self.root = self.root.add(f"📁 {self.root_path.name}")
        self._add_dir(self.root_path, self.root, depth=0)

    def _add_dir(self, path: Path, node: Tree, depth: int) -> None:
        if depth > self.MAX_DEPTH:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return
        for entry in entries[: self.MAX_ENTRIES]:
            if entry.name.startswith(".") and entry.name not in (".env.example",):
                continue
            if entry.is_dir() and entry.name in self.SKIP_DIRS:
                continue
            if entry.is_dir():
                branch = node.add(f"📁 {entry.name}")
                self._add_dir(entry, branch, depth + 1)
            else:
                node.add_leaf(f"📄 {entry.name}")
