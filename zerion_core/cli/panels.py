from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.table import Table
from rich.columns import Columns
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.widgets import RichLog, Static, ProgressBar

from zerion_core.cli.diff import git_status_short, render_diff_lines, render_ndiff_preview, render_side_by_side, unified_diff
from zerion_core.config import settings


# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    """Consistent color palette for the entire UI."""
    # Backgrounds
    BG_PRIMARY = "#0f1117"
    BG_SECONDARY = "#161822"
    BG_TERTIARY = "#1c1f2e"
    BG_CARD = "#1a1d2e"
    BG_INPUT = "#252840"
    
    # Borders
    BORDER_DIM = "#2a2d3e"
    BORDER_ACTIVE = "#3d4155"
    BORDER_FOCUS = "#7c3aed"
    
    # Text
    TEXT_PRIMARY = "#e2e8f0"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_DIM = "#64748b"
    TEXT_MUTED = "#475569"
    
    # Accent Colors
    ACCENT_PURPLE = "#a78bfa"
    ACCENT_BLUE = "#60a5fa"
    ACCENT_CYAN = "#22d3ee"
    ACCENT_GREEN = "#34d399"
    ACCENT_YELLOW = "#fbbf24"
    ACCENT_ORANGE = "#fb923c"
    ACCENT_RED = "#f87171"
    ACCENT_PINK = "#f472b6"
    
    # Semantic Colors
    SUCCESS = "#34d399"
    WARNING = "#fbbf24"
    ERROR = "#f87171"
    INFO = "#60a5fa"
    
    # Agent Colors
    AGENT_CEO = "#a78bfa"
    AGENT_ROUTER = "#60a5fa"
    AGENT_PLANNER = "#22d3ee"
    AGENT_WORKER = "#34d399"
    AGENT_QA = "#fbbf24"
    AGENT_REVIEW = "#fb923c"
    
    # Diff Colors
    DIFF_ADD_BG = "#0d2818"
    DIFF_ADD_TEXT = "#34d399"
    DIFF_DEL_BG = "#2d1117"
    DIFF_DEL_TEXT = "#f87171"
    DIFF_CTX_TEXT = "#94a3b8"


class Typography:
    """Typography constants."""
    BOLD = "bold"
    DIM = "dim"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"


class Spacing:
    """Spacing constants."""
    XS = 1
    SM = 2
    MD = 3
    LG = 4
    XL = 6


# ═══════════════════════════════════════════════════════════════════════════════
# BASE COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

class StatusBar(Static):
    """Status indicator dot."""
    
    STATUS_COLORS = {
        "active": Colors.SUCCESS,
        "working": Colors.ACCENT_YELLOW,
        "thinking": Colors.ACCENT_ORANGE,
        "idle": Colors.TEXT_DIM,
        "error": Colors.ERROR,
        "offline": Colors.TEXT_MUTED,
    }
    
    def __init__(self, status: str = "idle", **kwargs) -> None:
        super().__init__(**kwargs)
        self._status = status
    
    def set_status(self, status: str) -> None:
        self._status = status
        self._render()
    
    def _render(self) -> None:
        color = self.STATUS_COLORS.get(self._status, Colors.TEXT_DIM)
        self.update(Text(f"●", style=f"bold {color}"))


class SectionHeader(Static):
    """Styled section header with optional icon."""
    
    def __init__(self, title: str, icon: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._icon = icon
    
    def render(self) -> Text:
        text = Text()
        if self._icon:
            text.append(f"{self._icon} ", style=f"bold {Colors.ACCENT_PURPLE}")
        text.append(self._title.upper(), style=f"bold {Colors.TEXT_PRIMARY}")
        text.append(" ", style="dim")
        return text


class CardPanel(Static):
    """A styled card container."""
    
    def __init__(self, title: str = "", icon: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._icon = icon
    
    def render_card(self, content: Text, border_color: str = Colors.BORDER_DIM) -> Panel:
        if self._title:
            title_text = Text()
            if self._icon:
                title_text.append(f"{self._icon} ", style=f"bold {Colors.ACCENT_PURPLE}")
            title_text.append(self._title, style=f"bold {Colors.TEXT_PRIMARY}")
            return Panel(content, title=title_text, border_style=border_color, padding=(0, 1))
        return Panel(content, border_style=border_color, padding=(0, 1))


class AgentStrip(Static):
    """Compact horizontal agent status row."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._lines: list[str] = []

    def update_agents(self, lines: list[str]) -> None:
        self._lines = lines
        self.refresh()

    def render(self) -> Text:
        if not self._lines:
            return Text("No active agents", style=f"dim italic {Colors.TEXT_MUTED}")
            
        body = Text()
        for i, line in enumerate(self._lines):
            if i > 0:
                body.append("  ", style=f"dim {Colors.BORDER_ACTIVE}")
            
            parts = line.split()
            if len(parts) >= 3:
                name = parts[0]
                sym = parts[1]
                status = parts[2]
                
                color = Colors.TEXT_DIM
                if status == "Working":
                    color = Colors.SUCCESS
                elif status == "Waiting":
                    color = Colors.WARNING
                elif status == "Error":
                    color = Colors.ERROR
                
                body.append(f"{sym} ", style=f"bold {color}")
                body.append(f"{name}", style=f"bold {Colors.TEXT_PRIMARY}")
                body.append(f" {status.lower()}", style=f"dim {Colors.TEXT_SECONDARY}")
            else:
                body.append(line)
        return body


class TaskBar(Static):
    def set_task(self, task: str) -> None:
        self.update(Text(f"● {task or 'Ready'}", style=f"bold {Colors.SUCCESS}"))


class Branding(Static):
    """Styled branding for Zerion-Core."""
    
    def render(self) -> Text:
        banner = Text()
        banner.append(" ZERION", style=f"bold {Colors.ACCENT_YELLOW}")
        banner.append("CORE", style=f"bold {Colors.ACCENT_PURPLE}")
        banner.append(" — ", style=f"dim {Colors.TEXT_MUTED}")
        banner.append("AI Engineering Command Center", style=f"italic {Colors.ACCENT_GREEN}")
        return banner


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
        body.append("▸ DASHBOARD\n", style=f"bold {Colors.ACCENT_PURPLE}")
        body.append(f"  {m['model']}\n", style=f"bold {Colors.TEXT_PRIMARY}")
        errs = m['errors']
        warns = m['warnings']
        body.append(f"  {errs} errors", style=f"bold {Colors.ERROR}" if errs else f"dim {Colors.TEXT_MUTED}")
        body.append(f"  {warns} warnings\n", style=f"bold {Colors.WARNING}" if warns else f"dim {Colors.TEXT_MUTED}")
        return Panel(body, border_style=Colors.BORDER_DIM, padding=(0, 1))


class TokenBar(Static):
    tokens: reactive[int] = reactive(0)
    cost: reactive[float] = reactive(0.0)

    def watch_tokens(self, value: int) -> None:
        body = Text()
        body.append("▸ USAGE\n", style=f"bold {Colors.ACCENT_PURPLE}")
        body.append(f"  {value:,} tokens\n", style=f"bold {Colors.TEXT_PRIMARY}")
        if self.cost > 0:
            body.append(f"  ${self.cost:.4f}\n", style=f"dim {Colors.TEXT_SECONDARY}")
        self.update(body)


# ═══════════════════════════════════════════════════════════════════════════════
# LEFT PANEL - SYSTEM & AGENTS
# ═══════════════════════════════════════════════════════════════════════════════

class AgentCard(Static):
    """Individual agent status card."""
    
    def __init__(self, name: str = "Agent", status: str = "idle", **kwargs) -> None:
        super().__init__(**kwargs)
        self._name = name
        self._status = status
        self._last_message = ""
        self._model = ""
    
    def update_status(self, name: str, status: str, message: str = "", model: str = "") -> None:
        self._name = name
        self._status = status
        self._last_message = message
        self._model = model
        self._render()
    
    def _render(self) -> None:
        body = Text()
        
        # Status indicator
        status_colors = {
            "Working": Colors.SUCCESS,
            "Waiting": Colors.WARNING,
            "Error": Colors.ERROR,
            "Idle": Colors.TEXT_DIM,
        }
        color = status_colors.get(self._status, Colors.TEXT_DIM)
        body.append("● ", style=f"bold {color}")
        
        # Agent name
        body.append(self._name, style=f"bold {Colors.TEXT_PRIMARY}")
        
        # Status
        body.append(f" {self._status.lower()}", style=f"dim {Colors.TEXT_SECONDARY}")
        
        # Model if available
        if self._model:
            body.append(f"\n  ", style="dim")
            body.append(f"{self._model}", style=f"dim {Colors.TEXT_MUTED}")
        
        self.update(body)


class SystemPanel(Static):
    """Left panel showing system status and agents."""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._agents: list[dict[str, str]] = []
        self._system_status = "healthy"
        self._memory_hits = 0
        self._router_state = "ready"
    
    def update_agents(self, agents: list[dict[str, str]]) -> None:
        self._agents = agents
        self.refresh()
    
    def update_system(self, status: str = "", memory: int = -1, router: str = "") -> None:
        if status:
            self._system_status = status
        if memory >= 0:
            self._memory_hits = memory
        if router:
            self._router_state = router
        self.refresh()
    
    def render(self) -> Panel:
        body = Text()
        
        # System status - compact single line
        status_color = Colors.SUCCESS if self._system_status == "healthy" else Colors.ERROR
        body.append("▸ SYSTEM\n", style=f"bold {Colors.ACCENT_PURPLE}")
        body.append(f"  {self._system_status.upper()}", style=f"bold {status_color}")
        body.append(f"  {self._memory_hits} hits", style=f"dim {Colors.INFO}")
        body.append(f"  {self._router_state}\n", style=f"dim {Colors.ACCENT_PURPLE}")
        body.append("\n")
        
        # Agents - compact grid
        body.append("▸ AGENTS\n", style=f"bold {Colors.ACCENT_PURPLE}")
        if not self._agents:
            body.append("  none active\n", style=f"dim italic {Colors.TEXT_MUTED}")
        else:
            # Count by status
            working = [a for a in self._agents if a.get("status") == "Working"]
            idle = [a for a in self._agents if a.get("status") != "Working"]
            
            if working:
                for a in working:
                    name = a.get("name", "?")[:10]
                    body.append(f"  ● ", style=f"bold {Colors.SUCCESS}")
                    body.append(f"{name}\n", style=f"bold {Colors.TEXT_PRIMARY}")
            
            # Show idle count
            if idle:
                body.append(f"  ○ ", style=f"dim {Colors.TEXT_MUTED}")
                body.append(f"{len(idle)} idle\n", style=f"dim {Colors.TEXT_SECONDARY}")
        
        return Panel(body, border_style=Colors.BORDER_DIM, padding=(0, 1))


# ═══════════════════════════════════════════════════════════════════════════════
# CENTER PANEL - MAIN WORK AREA
# ═══════════════════════════════════════════════════════════════════════════════

class TodoItem:
    """A single todo item with status tracking."""
    
    def __init__(self, text: str, done: bool = False) -> None:
        self.text = text
        self.done = done
        self.substeps: list["TodoItem"] = []
    
    def toggle(self) -> None:
        self.done = not self.done
    
    def render(self, indent: int = 0) -> Text:
        prefix = "  " * indent
        text = Text()
        
        if self.done:
            text.append(f"{prefix}✓ ", style=f"bold {Colors.SUCCESS}")
            text.append(self.text, style=f"dim {Colors.TEXT_MUTED} strikethrough")
        else:
            text.append(f"{prefix}○ ", style=f"bold {Colors.ACCENT_YELLOW}")
            text.append(self.text, style=f"{Colors.TEXT_PRIMARY}")
        
        text.append("\n")
        for sub in self.substeps:
            text.append_text(sub.render(indent + 1))
        return text


class TodosPanel(Static):
    """Task pipeline visualization with step tracking."""
    
    _todos: reactive[list[TodoItem]] = reactive([])
    _title: reactive[str] = reactive("PLAN")
    _current_step: reactive[int] = reactive(0)
    
    def set_title(self, title: str) -> None:
        self._title = title
        self._render_panel()
    
    def set_todos(self, todos: list[str]) -> None:
        self._todos = [TodoItem(t) for t in todos]
        self._current_step = 0
        self._render_panel()
    
    def add_todo(self, text: str, index: int = -1) -> None:
        item = TodoItem(text)
        new_todos = list(self._todos)
        if index < 0:
            new_todos.append(item)
        else:
            new_todos.insert(index, item)
        self._todos = new_todos
        self._render_panel()
    
    def complete_todo(self, text_substring: str) -> bool:
        """Auto-complete a todo by matching text substring. Returns True if found."""
        new_todos = list(self._todos)
        for i, item in enumerate(new_todos):
            if text_substring.lower() in item.text.lower() and not item.done:
                item.done = True
                self._current_step = i + 1
                self._todos = new_todos
                self._render_panel()
                return True
        # Try substeps
        for item in new_todos:
            for sub in item.substeps:
                if text_substring.lower() in sub.text.lower() and not sub.done:
                    sub.done = True
                    self._todos = new_todos
                    self._render_panel()
                    return True
        return False
    
    def add_substep(self, parent_text: str, substep_text: str) -> None:
        for item in self._todos:
            if parent_text.lower() in item.text.lower():
                item.substeps.append(TodoItem(substep_text))
                self._render_panel()
                return
    
    def clear(self) -> None:
        self._todos = []
        self._current_step = 0
        self._render_panel()
    
    def _render_panel(self) -> None:
        body = Text()
        
        # Header
        body.append("┌─ ", style=f"dim {Colors.BORDER_ACTIVE}")
        body.append(f"{self._title}", style=f"bold {Colors.ACCENT_PURPLE}")
        body.append(" ─", style=f"dim {Colors.BORDER_ACTIVE}")
        
        if self._todos:
            done_count = sum(1 for t in self._todos if t.done)
            total = len(self._todos)
            progress = done_count / total if total > 0 else 0
            
            body.append(" ", style="dim")
            body.append(f"[{done_count}/{total}]", style=f"bold {Colors.TEXT_SECONDARY}")
            body.append(f" {progress:.0%}", style=f"dim {Colors.TEXT_MUTED}")
        
        body.append("\n", style="dim")
        body.append("─" * 40 + "\n", style=f"dim {Colors.BORDER_DIM}")
        
        if not self._todos:
            body.append("  No tasks yet\n", style=f"dim italic {Colors.TEXT_MUTED}")
        else:
            # Pipeline visualization
            body.append("\n  PIPELINE\n", style=f"bold {Colors.TEXT_SECONDARY}")
            body.append("  ", style="dim")
            
            for i, todo in enumerate(self._todos):
                if i > 0:
                    body.append(" → ", style=f"dim {Colors.BORDER_ACTIVE}")
                
                if todo.done:
                    body.append("✓", style=f"bold {Colors.SUCCESS}")
                elif i == self._current_step:
                    body.append("●", style=f"bold {Colors.ACCENT_YELLOW}")
                else:
                    body.append("○", style=f"dim {Colors.TEXT_MUTED}")
            
            body.append("\n\n")
            
            # Detailed steps
            body.append("  STEPS\n", style=f"bold {Colors.TEXT_SECONDARY}")
            body.append("  ", style="dim")
            body.append("─" * 36 + "\n", style=f"dim {Colors.BORDER_DIM}")
            
            for todo in self._todos:
                body.append_text(todo.render())
        
        self.update(Panel(body, title="TODOS", border_style=Colors.ACCENT_PURPLE, padding=(0, 1)))
    
    def render(self) -> Panel:
        self._render_panel()
        return Panel(Text(""), title="TODOS", border_style=Colors.ACCENT_PURPLE, padding=(0, 1))


class ActivityPanel(RichLog):
    """Chat-style conversation thread with thinking states."""

    AGENT_COLORS = {
        "router": Colors.AGENT_ROUTER,
        "planner": Colors.AGENT_PLANNER,
        "implement": Colors.AGENT_WORKER,
        "review": Colors.AGENT_REVIEW,
        "qa": Colors.AGENT_QA,
        "user": Colors.ACCENT_YELLOW,
        "ceo": Colors.AGENT_CEO,
        "research": Colors.AGENT_ROUTER,
        "architect": Colors.AGENT_PLANNER,
        "memory": Colors.SUCCESS,
        "docs": Colors.TEXT_PRIMARY,
        "reflection": Colors.ACCENT_PURPLE,
    }

    AGENT_ICONS = {
        "user": "›",
        "router": "⁇",
        "planner": "⊞",
        "implement": "▸",
        "review": "⊘",
        "qa": "◈",
        "ceo": "★",
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=False, markup=True, max_lines=500, **kwargs)
        self._thinking: dict[str, str] = {}

    def _get_color(self, stage: str) -> str:
        return self.AGENT_COLORS.get(stage, Colors.ACCENT_PURPLE)

    def _get_icon(self, stage: str) -> str:
        return self.AGENT_ICONS.get(stage, "·")

    def user_message(self, text: str) -> None:
        """Display a user message."""
        t = Text()
        t.append("  you", style=f"bold {Colors.ACCENT_YELLOW}")
        t.append(f" {text}\n", style=Colors.TEXT_PRIMARY)
        self.write(t)

    def thinking(self, agent: str) -> None:
        """Show thinking indicator for an agent."""
        self._thinking[agent] = "active"
        color = self._get_color(agent)
        icon = self._get_icon(agent)
        t = Text()
        t.append(f"  {icon} ", style=f"bold {color}")
        t.append(f"{agent}", style=f"bold {color}")
        t.append(" thinking", style=f"dim {Colors.TEXT_MUTED}")
        t.append(" …\n", style=f"dim {Colors.TEXT_MUTED}")
        self.write(t)

    def agent_line(self, stage: str, message: str) -> None:
        """Display an agent message in chat style."""
        self._thinking.pop(stage, None)
        color = self._get_color(stage)
        icon = self._get_icon(stage)
        t = Text()
        t.append(f"  {icon} ", style=f"bold {color}")
        t.append(f"{stage}", style=f"bold {color}")
        t.append(f" {message}\n", style=Colors.TEXT_PRIMARY)
        self.write(t)


class CLITerminalPanel(RichLog):
    """Styled terminal with command blocks."""

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=True, markup=True, max_lines=500, **kwargs)
        self.write(Text("Terminal ready\n", style=f"dim italic {Colors.TEXT_MUTED}"))

    def command(self, cmd: str) -> None:
        """Show a running command with styled block."""
        self.write(Text(f"\n┌─ COMMAND ──────────────────────────┐\n", style=f"bold {Colors.BORDER_ACTIVE}"))
        self.write(Text(f"│ ❯ {cmd}\n", style=f"bold {Colors.ACCENT_YELLOW}"))
        self.write(Text(f"└────────────────────────────────────┘\n", style=f"dim {Colors.BORDER_ACTIVE}"))

    def stream(self, line: str, stream: str = "stdout") -> None:
        """Show command output line."""
        style = Colors.ACCENT_GREEN if stream == "stdout" else Colors.ERROR
        self.write(Text(f"  {line}\n", style=style))

    def done(self, exit_code: int) -> None:
        """Show command completion status."""
        color = Colors.SUCCESS if exit_code == 0 else Colors.ERROR
        sym = "✓" if exit_code == 0 else "✗"
        self.write(Text(f"  {sym} exit {exit_code}\n", style=f"bold {color}"))

    def file_op(self, message: str, ok: bool = True) -> None:
        """Show file operation result."""
        style = Colors.SUCCESS if ok else Colors.ERROR
        sym = "✎" if ok else "✗"
        self.write(Text(f"  {sym} {message}\n", style=f"bold {style}"))

    def idle_note(self, message: str) -> None:
        """Show idle note."""
        self.write(Text(f"  … {message}\n", style=f"dim {Colors.TEXT_MUTED}"))

    def show_command_with_output(self, cmd: str, output: str, exit_code: int = 0) -> None:
        """Show a complete command with its output and status."""
        self.write(Text(f"\n┌─ COMMAND ──────────────────────────┐\n", style=f"bold {Colors.BORDER_ACTIVE}"))
        self.write(Text(f"│ ❯ {cmd}\n", style=f"bold {Colors.ACCENT_YELLOW}"))
        self.write(Text(f"└────────────────────────────────────┘\n", style=f"dim {Colors.BORDER_ACTIVE}"))
        
        if output:
            for line in output.splitlines():
                self.write(Text(f"  {line}\n", style=Colors.ACCENT_GREEN))
        
        color = Colors.SUCCESS if exit_code == 0 else Colors.ERROR
        sym = "✓" if exit_code == 0 else "✗"
        self.write(Text(f"  {sym} exit {exit_code}\n", style=f"bold {color}"))

    def show_task_step(self, step_num: int, total: int, description: str, status: str = "running") -> None:
        """Show a task step with progress."""
        if status == "running":
            icon = "⟳"
            color = Colors.ACCENT_YELLOW
        elif status == "done":
            icon = "✓"
            color = Colors.SUCCESS
        elif status == "failed":
            icon = "✗"
            color = Colors.ERROR
        else:
            icon = "○"
            color = Colors.TEXT_MUTED

        self.write(Text(f"  {icon} [{step_num}/{total}] {description}\n", style=f"bold {color}"))


class DiffViewerPanel(RichLog):
    """Enhanced diff viewer with syntax highlighting."""

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=True, markup=False, max_lines=400, **kwargs)
        self._change_count = 0
        self.write(Text("Diff viewer — file changes appear here\n", style=f"dim italic {Colors.TEXT_MUTED}"))

    def show_change(self, path: str, old: str | None, new: str) -> None:
        self._change_count += 1
        
        # Header with file path
        header = Text()
        header.append("┌─ CHANGE #", style=f"bold {Colors.ACCENT_PURPLE}")
        header.append(f"{self._change_count}", style=f"bold {Colors.TEXT_PRIMARY}")
        header.append(" ─ ", style=f"dim {Colors.BORDER_ACTIVE}")
        header.append(path, style=f"bold {Colors.ACCENT_CYAN}")
        header.append(" ", style="dim")
        header.append("─" * (35 - len(path)) + "┐\n", style=f"dim {Colors.BORDER_ACTIVE}")
        self.write(header)
        
        # Diff content
        self.write(render_side_by_side(old, new, path))
        
        # Footer
        self.write(Text(f"└{'─' * 40}┘\n\n", style=f"dim {Colors.BORDER_ACTIVE}"))

    def show_unified(self, path: str, old: str | None, new: str) -> None:
        lines = unified_diff(old, new, path)
        if lines:
            self.write(render_diff_lines(lines, path))

    def show_git_diff(self, diff_text: str, path: str = "") -> None:
        if not diff_text:
            return
        
        # Header
        title = Text()
        title.append("┌─ GIT DIFF ", style=f"bold {Colors.ACCENT_ORANGE}")
        if path:
            title.append(path, style=f"bold {Colors.ACCENT_CYAN}")
        title.append(" ", style="dim")
        title.append("─" * (38 - len(path)) + "┐\n", style=f"dim {Colors.BORDER_ACTIVE}")
        self.write(title)
        
        # Diff content
        self.write(render_diff_lines(diff_text.splitlines(), path))
        
        # Footer
        self.write(Text(f"└{'─' * 40}┘\n\n", style=f"dim {Colors.BORDER_ACTIVE}"))


# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL - ANALYTICS & CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════

class GitPanel(Static):
    """Git branch, status, and diff stats."""

    changes: reactive[int] = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._branch = "no repo"
        self._lines: list[str] = []
        self._stat = ""

    def refresh_status(self) -> None:
        info = git_status_short()
        self._branch = info.get("branch") or "no repo"
        self._lines = info.get("status", [])
        self._stat = info.get("stat", "")
        self.changes = len(self._lines)
        self.refresh()

    def render(self) -> Panel:
        body = Text()
        body.append("▸ GIT\n", style=f"bold {Colors.ACCENT_PURPLE}")
        body.append(f"  ⎇ {self._branch}\n", style=f"bold {Colors.TEXT_PRIMARY}")
        if self._lines:
            for ln in self._lines[:5]:
                if ln.startswith("??"):
                    body.append(f"  ? {ln[3:]}\n", style=f"{Colors.TEXT_SECONDARY}")
                elif ln.startswith("A") or "A " in ln[:2]:
                    body.append(f"  + {ln[3:]}\n", style=f"{Colors.SUCCESS}")
                elif ln.startswith("M") or "M " in ln[:2]:
                    body.append(f"  ~ {ln[3:]}\n", style=f"{Colors.WARNING}")
                elif ln.startswith("D") or "D " in ln[:2]:
                    body.append(f"  - {ln[3:]}\n", style=f"{Colors.ERROR}")
                else:
                    body.append(f"  {ln[:28]}\n", style=f"{Colors.TEXT_SECONDARY}")
            if len(self._lines) > 5:
                body.append(f"  … +{len(self._lines) - 5}\n", style=f"dim {Colors.TEXT_MUTED}")
        else:
            body.append("  clean\n", style=f"dim {Colors.SUCCESS}")
        return Panel(body, border_style=Colors.BORDER_DIM, padding=(0, 1))


class ModelInfoPanel(Static):
    """Model information and token usage."""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._model = settings.default_model
        self._tokens = 0
        self._latency = 0.0
    
    def update_info(self, model: str = "", tokens: int = -1, latency: float = -1) -> None:
        if model:
            self._model = model
        if tokens >= 0:
            self._tokens = tokens
        if latency >= 0:
            self._latency = latency
        self.refresh()
    
    def render(self) -> Panel:
        body = Text()
        body.append("▸ MODEL\n", style=f"bold {Colors.ACCENT_PURPLE}")
        body.append(f"  {self._model}\n", style=f"bold {Colors.TEXT_PRIMARY}")
        tok = f"{self._tokens:,}" if self._tokens else "0"
        body.append(f"  {tok} tokens", style=f"bold {Colors.ACCENT_YELLOW}")
        if self._latency > 0:
            body.append(f"  {self._latency:.1f}s", style=f"bold {Colors.INFO}")
        body.append("\n")
        return Panel(body, border_style=Colors.BORDER_DIM, padding=(0, 1))


class TaskSummaryPanel(Static):
    """Current task summary and progress."""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._task = "Ready"
        self._progress = 0.0
        self._stage = ""
    
    def update_task(self, task: str, progress: float = -1, stage: str = "") -> None:
        if task:
            self._task = task
        if progress >= 0:
            self._progress = progress
        if stage:
            self._stage = stage
        self.refresh()
    
    def render(self) -> Panel:
        body = Text()
        body.append("▸ TASK\n", style=f"bold {Colors.ACCENT_PURPLE}")
        # Truncate task to fit
        task_text = self._task[:30] if self._task else "Ready"
        body.append(f"  {task_text}\n", style=f"bold {Colors.TEXT_PRIMARY}")
        if self._stage:
            body.append(f"  {self._stage}", style=f"dim {Colors.ACCENT_PURPLE}")
            if self._progress > 0:
                body.append(f"  {self._progress:.0%}", style=f"dim {Colors.TEXT_SECONDARY}")
            body.append("\n")
        return Panel(body, border_style=Colors.BORDER_DIM, padding=(0, 1))


class MemoryHitsPanel(Static):
    """Memory system hits and context."""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hits = 0
        self._recent: list[str] = []
    
    def update_hits(self, hits: int, recent: list[str] = None) -> None:
        self._hits = hits
        if recent is not None:
            self._recent = recent
        self.refresh()
    
    def render(self) -> Panel:
        body = Text()
        body.append("▸ MEMORY\n", style=f"bold {Colors.ACCENT_PURPLE}")
        body.append(f"  {self._hits} hits\n", style=f"bold {Colors.INFO}")
        if self._recent:
            for hit in self._recent[:2]:
                body.append(f"  {hit[:28]}\n", style=f"dim {Colors.TEXT_SECONDARY}")
        return Panel(body, border_style=Colors.BORDER_DIM, padding=(0, 1))


class IssuesPanel(Static):
    """Errors and warnings display."""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._errors: list[str] = []
        self._warnings: list[str] = []
    
    def add_error(self, error: str) -> None:
        self._errors.append(error)
        if len(self._errors) > 5:
            self._errors.pop(0)
        self.refresh()
    
    def add_warning(self, warning: str) -> None:
        self._warnings.append(warning)
        if len(self._warnings) > 5:
            self._warnings.pop(0)
        self.refresh()
    
    def clear(self) -> None:
        self._errors.clear()
        self._warnings.clear()
        self.refresh()
    
    def render(self) -> Panel:
        body = Text()
        body.append("▸ ISSUES\n", style=f"bold {Colors.ACCENT_PURPLE}")
        if not self._errors and not self._warnings:
            body.append("  ", style="dim")
            body.append("clean\n", style=f"dim {Colors.SUCCESS}")
        else:
            for err in self._errors[-2:]:
                body.append(f"  ✗ {err[:26]}\n", style=f"dim {Colors.ERROR}")
            for warn in self._warnings[-2:]:
                body.append(f"  ⚠ {warn[:26]}\n", style=f"dim {Colors.WARNING}")
        return Panel(body, border_style=Colors.BORDER_DIM, padding=(0, 1))


class FileTreePanel(RichLog):
    """Styled file tree with proper icons using RichLog."""
    
    SKIP_DIRS = frozenset({
        ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
        "chroma", ".pytest_cache", ".mypy_cache", "egg-info",
    })
    MAX_DEPTH = 4
    MAX_ENTRIES = 40

    def __init__(self, root: Path, **kwargs) -> None:
        super().__init__(highlight=False, markup=True, max_lines=200, **kwargs)
        self.root_path = root.resolve()
        self.reload()

    def reload(self) -> None:
        self.clear()
        body = Text()
        body.append(f"📁 {self.root_path.name}\n", style=f"bold {Colors.TEXT_PRIMARY}")
        self._add_dir(self.root_path, body, depth=0, prefix="")
        self.write(body)

    def _add_dir(self, path: Path, body: Text, depth: int, prefix: str) -> None:
        if depth > self.MAX_DEPTH:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        count = 0
        dirs = [e for e in entries if e.is_dir() and e.name not in self.SKIP_DIRS and not e.name.startswith(".")]
        files = [e for e in entries if e.is_dir() and (e.name in self.SKIP_DIRS or e.name.startswith(".")) == False and not e.is_dir()]
        
        for entry in dirs + files:
            if count >= self.MAX_ENTRIES:
                body.append(f"{prefix}  … +{len(entries) - count} more\n", style=f"dim {Colors.TEXT_MUTED}")
                break

            if entry.is_dir():
                child_prefix = prefix + "  "
                body.append(f"{prefix}📁 ", style=f"bold {Colors.ACCENT_YELLOW}")
                body.append(f"{entry.name}\n", style=f"bold {Colors.TEXT_PRIMARY}")
                self._add_dir(entry, body, depth + 1, child_prefix)
                count += 1
            else:
                ext = entry.suffix.lower()
                icon = {
                    ".py": "🐍", ".js": "📜", ".ts": "📘", ".tsx": "⚛️",
                    ".jsx": "⚛️", ".html": "🌐", ".css": "🎨", ".json": "📋",
                    ".yaml": "⚙️", ".yml": "⚙️", ".md": "📝", ".txt": "📄",
                    ".sh": "🐚", ".vue": "💚", ".svelte": "🔥", ".go": "🐹",
                    ".rs": "🦀", ".java": "☕",
                }.get(ext, "📄")
                body.append(f"{prefix}{icon} ", style="dim")
                body.append(f"{entry.name}\n", style=f"{Colors.TEXT_SECONDARY}")
                count += 1
