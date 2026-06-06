from __future__ import annotations

from rich.markdown import Markdown
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.message import Message
from textual.widgets import Footer, Header, Input, RichLog, TabbedContent, TabPane

from zerion_core.cli.panels import (
    ActivityPanel,
    AgentStrip,
    Branding,
    CLITerminalPanel,
    DashboardPanel,
    DiffViewerPanel,
    FileTreePanel,
    GitPanel,
    TaskBar,
    TokenBar,
)
from zerion_core.config import settings
from zerion_core.orchestrator.pipeline import Orchestrator, PipelineEvent


class PipelineUpdate(Message):
    def __init__(self, event: PipelineEvent) -> None:
        super().__init__()
        self.event = event


class ZerionApp(App):
    """Claude Code inspired UI for Zerion-Core."""

    CSS = """
    Screen {
        background: #1e1e1e;
        color: #d4d4d4;
    }

    #top-bar {
        height: auto;
        padding: 1 2;
        background: #252526;
        border-bottom: hkey #333333;
    }

    Branding {
        margin-bottom: 1;
    }

    #status-row {
        height: 1;
    }

    AgentStrip {
        width: 1fr;
    }

    TaskBar {
        width: auto;
        min-width: 30;
        content-align: right middle;
    }

    #body {
        height: 1fr;
    }

    #sidebar {
        width: 36;
        border-left: solid #333333;
        background: #252526;
    }

    #main-content {
        width: 1fr;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 0;
    }

    ActivityPanel, CLITerminalPanel, DiffViewerPanel, RichLog {
        background: #1e1e1e;
        border: none;
        height: 1fr;
    }

    #pipeline-log {
        height: 10;
        border-top: solid #333333;
        background: #1e1e1e;
    }

    DashboardPanel, TokenBar, GitPanel {
        height: auto;
        margin: 0 1;
    }

    #input-container {
        dock: bottom;
        height: auto;
        background: #252526;
        border-top: solid #333333;
        padding: 1 2;
    }

    #input-bar {
        background: #3c3c3c;
        border: none;
        color: #ffffff;
    }

    #input-bar:focus {
        border: tall #007acc;
    }

    Header {
        background: #333333;
        color: #ffffff;
    }

    Footer {
        background: #007acc;
        color: #ffffff;
    }

    Tree {
        background: #252526;
        border: none;
        padding: 1;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+r", "refresh_all", "Refresh"),
        ("ctrl+g", "refresh_git", "Git"),
        ("ctrl+1", "switch_tab('activity')", "Activity"),
        ("ctrl+2", "switch_tab('terminal')", "Terminal"),
        ("ctrl+3", "switch_tab('diff')", "Diff"),
        ("ctrl+s", "save_session", "Save Session"),
        ("ctrl+l", "list_sessions", "List Sessions"),
    ]

    TITLE = "Zerion-Core"

    def __init__(self) -> None:
        super().__init__()
        self.orchestrator: Orchestrator | None = None
        self._token_count = 0
        self._pending_user_input: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="top-bar"):
            yield Branding()
            with Horizontal(id="status-row"):
                yield AgentStrip(id="agents")
                yield TaskBar(id="task")
        
        with Horizontal(id="body"):
            with Vertical(id="main-content"):
                with TabbedContent(initial="activity"):
                    with TabPane("Activity", id="activity"):
                        yield ActivityPanel(id="activity-view")
                    with TabPane("Terminal", id="terminal"):
                        yield CLITerminalPanel(id="terminal-view")
                    with TabPane("Diff", id="diff"):
                        yield DiffViewerPanel(id="diff-view")
                yield RichLog(id="pipeline-log", highlight=True, markup=True, max_lines=100)
            
            with Vertical(id="sidebar"):
                yield DashboardPanel(id="dashboard")
                yield TokenBar(id="tokens")
                yield GitPanel(id="git")
                yield FileTreePanel(settings.workspace, id="tree")
        
        with Container(id="input-container"):
            yield Input(placeholder="Ask Zerion-Core…", id="input-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.orchestrator = Orchestrator(on_event=self._on_pipeline_event)
        await self.orchestrator.start()
        self.query_one("#task", TaskBar).set_task("Ready")
        self._refresh_agents()
        self.query_one("#git", GitPanel).refresh_status()
        plog = self.query_one("#pipeline-log", RichLog)
        plog.write("[bold #4ec9b0]Zerion-Core[/] online — inspired by Claude Code UI")

    def _on_pipeline_event(self, event: PipelineEvent) -> None:
        self.post_message(PipelineUpdate(event))

    def on_pipeline_update(self, message: PipelineUpdate) -> None:
        self._handle_event(message.event)

    def _handle_event(self, event: PipelineEvent) -> None:
        stage = event.stage
        msg = event.message
        data = event.data

        plog = self.query_one("#pipeline-log", RichLog)
        activity = self.query_one("#activity-view", ActivityPanel)
        terminal = self.query_one("#terminal-view", CLITerminalPanel)
        diff = self.query_one("#diff-view", DiffViewerPanel)
        dashboard = self.query_one("#dashboard", DashboardPanel)
        tabs = self.query_one(TabbedContent)

        # Update Dashboard Metrics
        new_metrics = dict(dashboard.metrics)
        if stage == "memory":
            new_metrics["memory_hits"] += 1
        elif stage == "error":
            new_metrics["errors"] += 1
        elif "warning" in msg.lower():
            new_metrics["warnings"] += 1
        dashboard.metrics = new_metrics

        # --- CLI live stream ---
        if stage.startswith("cli_"):
            if tabs.active != "terminal":
                tabs.active = "terminal"
            
            if stage == "cli_command":
                terminal.command(data.get("command", msg))
            elif stage == "cli_output":
                terminal.stream(msg, stream=data.get("stream", "stdout"))
            elif stage == "cli_exit":
                terminal.done(int(data.get("exit_code", 0)))
            elif stage == "cli_error":
                terminal.stream(msg, stream="stderr")
            elif stage == "cli_task":
                terminal.idle_note(f"CLI agent: {msg}")
            elif stage == "cli_done":
                terminal.file_op(f"Done — {msg}", ok=data.get("success", True))
            elif stage == "cli_retry":
                terminal.stream(f"↻ {msg}", stream="stdout")

        elif stage == "file_write":
            terminal.file_op(msg, ok=True)
        elif stage == "file_error":
            terminal.file_op(msg, ok=False)
        elif stage == "file_diff":
            if tabs.active != "diff":
                tabs.active = "diff"
            diff.show_change(
                data.get("path", "?"),
                data.get("old"),
                data.get("new", ""),
            )
            added = data.get("added", 0)
            removed = data.get("removed", 0)
            plog.write(f"[#8957e5]diff[/] {data.get('path')} [green]+{added}[/] [red]-{removed}[/]")
        elif stage == "git_diff":
            if tabs.active != "diff":
                tabs.active = "diff"
            diff.show_git_diff(data.get("diff", ""), data.get("path", ""))

        # --- Agent activity ---
        elif stage == "user_input_request":
            agent = data.get("agent", "agent")
            self._pending_user_input = data.get("message_id")
            plog.write(f"[bold #d7ba7d]QUESTION from {agent}:[/] {msg}")
            ibar = self.query_one("#input-bar", Input)
            ibar.placeholder = f"Reply to {agent}..."
            ibar.border_style = "bold #d7ba7d"
            self.bell()

        elif stage == "agent_log":
            plog.write(f"[dim]{msg}[/]")

        elif stage == "agent_work":
            activity.agent_line(data.get("agent", "agent"), msg)
            if self.orchestrator:
                agent_name = data.get("agent")
                if agent_name:
                    for a in self.orchestrator.all_agents():
                        if a.name == agent_name and a.state.last_model:
                            dashboard.set_model(a.state.last_model)
                            break
        elif stage in ("implement", "review", "qa", "planner", "router"):
            activity.agent_line(stage, msg)

        # --- Session events ---
        elif stage == "session":
            plog.write(f"[bold #b5cea8]SESSION[/] {msg}")

        # --- Pipeline log (compact) ---
        if stage not in ("cli_output", "user_input_request"):
            style = {
                "router": "#4fc1ff",
                "planner": "#569cd6",
                "team": "#8957e5",
                "implement": "#4ec9b0",
                "review": "#ce9178",
                "qa": "#dcdcaa",
                "docs": "#ffffff",
                "memory": "#b5cea8",
                "complete": "bold #4ec9b0",
            }.get(stage, "dim")
            plog.write(Text.from_markup(f"[{style}]{stage.upper()}[/] {msg[:120]}"))

        self.query_one("#task", TaskBar).set_task(msg)
        self._refresh_agents()

        if stage in ("implement", "complete", "memory", "team", "file_diff", "git_diff", "cli_exit"):
            self.query_one("#tree", FileTreePanel).reload()
            self.query_one("#git", GitPanel).refresh_status()

    def _refresh_agents(self) -> None:
        if self.orchestrator:
            self.query_one("#agents", AgentStrip).update_agents(
                [a.status_line() for a in self.orchestrator.all_agents()]
            )

    @on(Input.Submitted, "#input-bar")
    def handle_input(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        
        # Handle session commands
        if text.startswith("/session"):
            self._handle_session_command(text)
            event.input.value = ""
            return

        if self._pending_user_input and self.orchestrator:
            mid = self._pending_user_input
            self._pending_user_input = None
            event.input.value = ""
            event.input.placeholder = "Ask Zerion-Core…"
            
            self.orchestrator.user_proxy.resolve_request(mid, text)
            self.query_one("#pipeline-log", RichLog).write(f"[bold #569cd6]user reply:[/] {text}")
            return

        event.input.value = ""
        self.run_task(text)

    def _handle_session_command(self, text: str) -> None:
        """Handle /session commands typed in the input bar."""
        plog = self.query_one("#pipeline-log", RichLog)
        parts = text.split(maxsplit=2)
        action = parts[1] if len(parts) > 1 else ""

        if not self.orchestrator:
            plog.write("[red]Orchestrator not ready[/]")
            return

        if action == "save":
            name = parts[2] if len(parts) > 2 else ""
            meta = self.orchestrator.save_session(name=name)
            plog.write(f"[bold #4ec9b0]Session saved:[/] {meta.name} ({meta.id})")

        elif action == "list":
            sessions = self.orchestrator.list_sessions()
            if not sessions:
                plog.write("[dim]No saved sessions.[/]")
            else:
                plog.write("[bold]Saved Sessions:[/]")
                for s in sessions:
                    plog.write(f"  [cyan]{s.id}[/] — {s.name or '(unnamed)'} [dim]({s.task_count} tasks)[/]")

        elif action == "load":
            if len(parts) < 3:
                plog.write("[red]Usage: /session load <id>[/]")
                return
            sid = parts[2].strip()
            if self.orchestrator.load_session(sid):
                plog.write(f"[bold #4ec9b0]Session loaded:[/] {sid}")
            else:
                plog.write(f"[red]Session not found: {sid}[/]")

        elif action == "delete":
            if len(parts) < 3:
                plog.write("[red]Usage: /session delete <id>[/]")
                return
            sid = parts[2].strip()
            if self.orchestrator.delete_session(sid):
                plog.write(f"[bold #4ec9b0]Deleted:[/] {sid}")
            else:
                plog.write(f"[red]Session not found: {sid}[/]")

        elif action == "new":
            self.orchestrator.new_session()
            plog.write("[bold #4ec9b0]New session started.[/]")

        else:
            plog.write("[dim]Commands: /session save [name] | list | load <id> | delete <id> | new[/]")

    @work(exclusive=True)
    async def run_task(self, request: str) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        activity = self.query_one("#activity-view", ActivityPanel)
        plog.write(Text.from_markup(f"[bold #d7ba7d]USER[/] {request}"))
        activity.agent_line("user", request)
        if not self.orchestrator:
            return
        try:
            result = await self.orchestrator.run(request)
            output = result.get("output", "")
            category = result.get("category", "")
            plog.write(Text.from_markup(f"[bold #4ec9b0]COMPLETE[/] ({category})"))
            if output and category == "chat":
                plog.write(Markdown(output[:3000]))
            self._token_count += self.orchestrator.llm.total_usage.total
            self.query_one("#tokens", TokenBar).tokens = self._token_count
        except Exception as exc:
            plog.write(Text.from_markup(f"[bold #f44747]ERROR[/] {exc}"))
        self.query_one("#tree", FileTreePanel).reload()
        self.query_one("#git", GitPanel).refresh_status()

    def action_switch_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    def action_refresh_all(self) -> None:
        self.query_one("#tree", FileTreePanel).reload()
        self.query_one("#git", GitPanel).refresh_status()
        self._refresh_agents()

    def action_refresh_git(self) -> None:
        self.query_one("#git", GitPanel).refresh_status()

    def action_save_session(self) -> None:
        """Save current session via Ctrl+S."""
        if self.orchestrator:
            meta = self.orchestrator.save_session()
            plog = self.query_one("#pipeline-log", RichLog)
            plog.write(f"[bold #4ec9b0]Session saved:[/] {meta.name} ({meta.id})")

    def action_list_sessions(self) -> None:
        """List sessions via Ctrl+L."""
        if self.orchestrator:
            plog = self.query_one("#pipeline-log", RichLog)
            sessions = self.orchestrator.list_sessions()
            if not sessions:
                plog.write("[dim]No saved sessions.[/]")
            else:
                plog.write("[bold]Saved Sessions:[/]")
                for s in sessions:
                    plog.write(f"  [cyan]{s.id}[/] — {s.name or '(unnamed)'} [dim]({s.task_count} tasks)[/]")

    async def on_unmount(self) -> None:
        if self.orchestrator:
            await self.orchestrator.stop()


def run_cli() -> None:
    ZerionApp().run()
