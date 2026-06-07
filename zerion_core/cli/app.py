from __future__ import annotations

import asyncio
from typing import Any

from rich.markdown import Markdown
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, RichLog, TabbedContent, TabPane

from zerion_core.cli.commands import CommandRegistry
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
    TodosPanel,
    SystemPanel,
    ModelInfoPanel,
    TaskSummaryPanel,
    MemoryHitsPanel,
    IssuesPanel,
    Colors,
)
from zerion_core.config import settings
from zerion_core.orchestrator.pipeline import Orchestrator, PipelineEvent


class PipelineUpdate(Message):
    def __init__(self, event: PipelineEvent) -> None:
        super().__init__()
        self.event = event


class ZerionApp(App):
    """AI Engineering Command Center - Modern TUI."""

    async def _close_all(self) -> None:
        """Override to fix Textual shutdown crash on Python 3.14+.
        
        Textual's _message_loop_exit can fail if `node._task` contains a non-awaitable object.
        We must clear these before the widget tree is processed.
        """
        for widget in self.query('*'):
            # Check if _task is a task-like object or a Future
            t = getattr(widget, "_task", None)
            if t is not None:
                # If it's not a valid asyncio task/coroutine/future, clear it
                if not (asyncio.isfuture(t) or asyncio.iscoroutine(t) or isinstance(t, asyncio.Task)):
                    widget._task = None
        
        await super()._close_all()

    CSS = """
    Screen {
        background: #0f1117;
        color: #e2e8f0;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* HEADER                                                            */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    #top-bar {
        height: auto;
        padding: 0 1;
        background: #161822;
        border-bottom: solid #2a2d3e;
    }

    Branding {
        margin-bottom: 0;
    }

    #status-row {
        height: 1;
        background: #161822;
    }

    AgentStrip {
        width: 2fr;
    }

    TaskBar {
        width: 1fr;
        content-align: right middle;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* 3-COLUMN LAYOUT                                                   */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    #body {
        height: 1fr;
    }

    /* LEFT PANEL - System & Agents */
    #left-panel {
        width: 26;
        min-width: 22;
        background: #161822;
        border-right: solid #2a2d3e;
        padding: 0 1;
    }

    /* CENTER PANEL - Main Work Area */
    #center-panel {
        width: 1fr;
        min-width: 40;
    }

    /* RIGHT PANEL - Analytics & Context */
    #right-panel {
        width: 28;
        min-width: 24;
        background: #161822;
        border-left: solid #2a2d3e;
        padding: 0 1;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* CENTER PANEL TABS                                                 */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    TabbedContent {
        height: 1fr;
        background: #0f1117;
    }

    TabPane {
        padding: 0;
    }

    .tab--active {
        background: #0f1117;
        color: #a78bfa;
    }

    .tab--inactive {
        background: #161822;
        color: #64748b;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* CONTENT PANELS                                                    */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    ActivityPanel, CLITerminalPanel, DiffViewerPanel, RichLog {
        background: #0f1117;
        border: none;
        height: 1fr;
    }

    #pipeline-log {
        height: 8;
        border-top: solid #2a2d3e;
        background: #161822;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* RIGHT PANEL COMPONENTS                                            */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    SystemPanel, ModelInfoPanel, TaskSummaryPanel, MemoryHitsPanel, IssuesPanel, GitPanel {
        height: auto;
        margin: 0 0 0 0;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* COMMAND MENU                                                      */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    #command-menu {
        height: 1fr;
        max-height: 0;
        background: #161822;
        overflow: hidden;
    }

    #command-menu.visible {
        max-height: 20;
        height: auto;
    }

    #command-menu RichLog {
        background: #161822;
        border: none;
        height: auto;
        padding: 0 2;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* INPUT BAR                                                         */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    #input-container {
        dock: bottom;
        height: auto;
        background: #161822;
        border-top: solid #2a2d3e;
        padding: 1 2;
    }

    #input-bar {
        background: #252840;
        border: solid #2a2d3e;
        color: #e2e8f0;
    }

    #input-bar:focus {
        border: tall #7c3aed;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* HEADER & FOOTER                                                   */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    Header {
        background: #1c1f2e;
        color: #e2e8f0;
    }

    Footer {
        background: #7c3aed;
        color: #ffffff;
    }

    /* ═══════════════════════════════════════════════════════════════════ */
    /* FILE TREE                                                         */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    #tree {
        background: #161822;
        border: solid #2a2d3e;
        height: 1fr;
        padding: 0;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+r", "refresh_all", "Refresh"),
        ("ctrl+g", "refresh_git", "Git"),
        ("ctrl+1", "switch_tab('activity')", "Activity"),
        ("ctrl+2", "switch_tab('terminal')", "Terminal"),
        ("ctrl+3", "switch_tab('diff')", "Diff"),
        ("ctrl+4", "switch_tab('todos')", "Todos"),
        ("ctrl+s", "save_session", "Save Session"),
        ("ctrl+l", "list_sessions", "List Sessions"),
        ("tab", "autocomplete", "Complete"),
        ("escape", "dismiss_menu", "Close Menu"),
    ]

    TITLE = "Zerion-Core AI Engineering Command Center"
    show_command_menu: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self.orchestrator: Orchestrator | None = None
        self._token_count = 0
        self._pending_user_input: str | None = None
        self._commands = CommandRegistry()
        self._autocomplete_candidates: list[str] = []
        self._autocomplete_index: int = -1
        self._last_input_text: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Vertical(id="top-bar"):
            yield Branding()
            with Horizontal(id="status-row"):
                yield AgentStrip(id="agents")
                yield TaskBar(id="task")
        
        with Horizontal(id="body"):
            # LEFT PANEL - System & Agents
            with Vertical(id="left-panel"):
                yield SystemPanel(id="system")
            
            # CENTER PANEL - Main Work Area
            with Vertical(id="center-panel"):
                with TabbedContent(initial="activity"):
                    with TabPane("Activity", id="activity"):
                        yield ActivityPanel(id="activity-view")
                    with TabPane("Terminal", id="terminal"):
                        yield CLITerminalPanel(id="terminal-view")
                    with TabPane("Diff", id="diff"):
                        yield DiffViewerPanel(id="diff-view")
                    with TabPane("Todos", id="todos"):
                        yield TodosPanel(id="todos-view")
                yield RichLog(id="pipeline-log", highlight=True, markup=True, max_lines=100)
            
            # RIGHT PANEL - Analytics & Context
            with Vertical(id="right-panel"):
                yield ModelInfoPanel(id="model-info")
                yield TaskSummaryPanel(id="task-summary")
                yield MemoryHitsPanel(id="memory-hits")
                yield IssuesPanel(id="issues")
                yield GitPanel(id="git")
                yield FileTreePanel(settings.workspace, id="tree")
        
        yield Container(
            RichLog(id="command-menu-log", highlight=True, markup=True, max_lines=16),
            id="command-menu",
        )

        with Container(id="input-container"):
            yield Input(placeholder="Ask Zerion-Core… (type / for commands)", id="input-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.orchestrator = Orchestrator(on_event=self._on_pipeline_event)
        await self.orchestrator.start()

        # Initialize memory systems
        await self.orchestrator.init_ltm()

        # Auto-create a new session on startup
        await self.orchestrator.new_session()

        self.query_one("#task", TaskBar).set_task("Ready")
        self._refresh_agents()
        self.query_one("#git", GitPanel).refresh_status()
        
        plog = self.query_one("#pipeline-log", RichLog)
        plog.write(f"[bold {Colors.SUCCESS}]Zerion-Core[/] online — AI Engineering Command Center initialized")
        
        self._wire_dynamic_completers()
        self._refresh_command_menu()
        
        # Update system panels
        system = self.query_one("#system", SystemPanel)
        system.update_system(status="healthy", memory=0, router="ready")
        
        model_info = self.query_one("#model-info", ModelInfoPanel)
        model_info.update_info(model=settings.default_model)
        
        task_summary = self.query_one("#task-summary", TaskSummaryPanel)
        task_summary.update_task("Ready", 0, "idle")

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
        todos = self.query_one("#todos-view", TodosPanel)
        system = self.query_one("#system", SystemPanel)
        model_info = self.query_one("#model-info", ModelInfoPanel)
        task_summary = self.query_one("#task-summary", TaskSummaryPanel)
        memory_hits = self.query_one("#memory-hits", MemoryHitsPanel)
        issues = self.query_one("#issues", IssuesPanel)
        tabs = self.query_one(TabbedContent)

        # Update Dashboard Metrics
        if stage == "memory":
            memory_hits.update_hits(memory_hits._hits + 1)
        elif stage == "error":
            issues.add_error(msg[:50])
        elif "warning" in msg.lower():
            issues.add_warning(msg[:50])

        # --- Todo updates ---
        if stage == "todo_set":
            items = data.get("items", [])
            todos.set_todos(items)
            if tabs.active != "todos":
                tabs.active = "todos"
        elif stage == "todo_add":
            todos.add_todo(msg)
        elif stage == "todo_done":
            todos.complete_todo(msg)
        elif stage == "todo_title":
            todos.set_title(msg)

        # --- CLI live stream ---
        elif stage.startswith("cli_"):
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
            plog.write(f"[{Colors.ACCENT_PURPLE}]diff[/] {data.get('path')} [{Colors.SUCCESS}]+{added}[/] [{Colors.ERROR}]-{removed}[/]")
        elif stage == "git_diff":
            if tabs.active != "diff":
                tabs.active = "diff"
            diff.show_git_diff(data.get("diff", ""), data.get("path", ""))

        # --- Agent activity ---
        elif stage == "user_input_request":
            agent = data.get("agent", "agent")
            self._pending_user_input = data.get("message_id")
            plog.write(f"[bold {Colors.ACCENT_YELLOW}]QUESTION from {agent}:[/] {msg}")
            ibar = self.query_one("#input-bar", Input)
            ibar.placeholder = f"Reply to {agent}..."
            ibar.border_style = f"bold {Colors.ACCENT_YELLOW}"
            self.bell()

        elif stage == "agent_log":
            plog.write(f"[dim]{msg}[/]")

        elif stage == "agent_work":
            activity.thinking(data.get("agent", "agent"))
            if self.orchestrator:
                agent_name = data.get("agent")
                if agent_name:
                    for a in self.orchestrator.all_agents():
                        if a.name == agent_name and a.state.last_model:
                            model_info.update_info(model=a.state.last_model)
                            break
        elif stage in ("implement", "review", "qa", "planner", "router"):
            activity.agent_line(stage, msg)

        # --- Session events ---
        elif stage == "session":
            plog.write(f"[bold {Colors.SUCCESS}]SESSION[/] {msg}")

        # --- Pipeline log (compact) ---
        if stage not in ("cli_output", "user_input_request", "session"):
            style = {
                "router": Colors.AGENT_ROUTER,
                "planner": Colors.AGENT_PLANNER,
                "team": Colors.ACCENT_PURPLE,
                "implement": Colors.AGENT_WORKER,
                "review": Colors.AGENT_REVIEW,
                "qa": Colors.AGENT_QA,
                "docs": Colors.TEXT_PRIMARY,
                "memory": Colors.SUCCESS,
                "complete": f"bold {Colors.SUCCESS}",
            }.get(stage, Colors.TEXT_DIM)
            plog.write(Text.from_markup(f"[{style}]{stage.upper()}[/] {msg[:120]}"))

        self.query_one("#task", TaskBar).set_task(msg)
        task_summary.update_task(msg, stage=stage)
        self._refresh_agents()

        if stage in ("implement", "complete", "memory", "team", "file_diff", "git_diff", "cli_exit"):
            self.query_one("#tree", FileTreePanel).reload()
            self.query_one("#git", GitPanel).refresh_status()

    def _refresh_agents(self) -> None:
        if self.orchestrator:
            agents = []
            for a in self.orchestrator.all_agents():
                agents.append({
                    "name": a.name,
                    "status": a.state.status.value if hasattr(a.state.status, 'value') else str(a.state.status),
                    "model": a.state.last_model or "",
                })
            self.query_one("#system", SystemPanel).update_agents(agents)

    @on(Input.Submitted, "#input-bar")
    def handle_input(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        
        # Reset autocomplete state
        self._autocomplete_candidates = []
        self._autocomplete_index = -1
        self.show_command_menu = False

        # Handle slash commands
        if text.startswith("/"):
            self._handle_slash_command(text)
            event.input.value = ""
            return

        if self._pending_user_input and self.orchestrator:
            mid = self._pending_user_input
            self._pending_user_input = None
            event.input.value = ""
            event.input.placeholder = "Ask Zerion-Core…"
            
            self.orchestrator.user_proxy.resolve_request(mid, text)
            self.query_one("#pipeline-log", RichLog).write(f"[bold {Colors.AGENT_ROUTER}]user reply:[/] {text}")
            return

        event.input.value = ""
        self.run_task(text)

    def watch_show_command_menu(self, visible: bool) -> None:
        """Toggle command menu visibility."""
        menu = self.query_one("#command-menu")
        if visible:
            menu.add_class("visible")
            self._refresh_command_menu()
        else:
            menu.remove_class("visible")

    @on(Input.Changed, "#input-bar")
    def on_input_changed(self, event: Input.Changed) -> None:
        """Show/hide command menu as user types."""
        text = event.value
        if text.startswith("/"):
            self.show_command_menu = True
            self._refresh_command_menu()
        else:
            self.show_command_menu = False

    def _refresh_command_menu(self) -> None:
        """Redraw the command menu based on current input."""
        menu_log = self.query_one("#command-menu-log", RichLog)
        menu_log.clear()

        ibar = self.query_one("#input-bar", Input)
        text = ibar.value

        # If typing a command, show filtered results
        if text.startswith("/"):
            completions = self._commands.get_completions_for_input(text)
            if completions:
                menu_log.write(Text("Commands", style=f"bold {Colors.ACCENT_PURPLE}"))
                cmd_text = text[1:].split(maxsplit=1)
                parent_cmd = self._commands.get(cmd_text[0]) if cmd_text else None
                is_subcmd = parent_cmd and parent_cmd.subcommands
                for c in completions:
                    if is_subcmd:
                        display = f"/{cmd_text[0]} {c}"
                        desc = ""
                        menu_log.write(Text(f"  {display:<24} {desc}", style=Colors.TEXT_PRIMARY))
                    else:
                        display = c if c.startswith("/") else f"/{c}"
                        cmd = self._commands.get(c.lstrip("/"))
                        desc = cmd.description if cmd else ""
                        menu_log.write(Text(f"  {display:<16} {desc}", style=Colors.TEXT_PRIMARY))
                return

        # Default: show all commands grouped by category
        menu_log.write(Text("Slash Commands", style=f"bold {Colors.ACCENT_PURPLE}"))
        menu_log.write(Text("  Type / + command name, then Enter to execute", style=f"dim {Colors.TEXT_MUTED}"))
        menu_log.write(Text("  Tab to autocomplete, Esc to close", style=f"dim {Colors.TEXT_MUTED}"))
        menu_log.write(Text(""))

        groups = {
            "Session": ["save", "load", "sessions", "session", "history", "search"],
            "Project": ["projects", "project", "newproject"],
            "Memory": ["recall", "memory", "brain"],
            "Skill": ["skill"],
            "Benchmark": ["benchmark"],
            "Tasks": ["todo"],
            "Utility": ["help", "clear", "health", "models", "tabs"],
        }
        for group, names in groups.items():
            menu_log.write(Text(f"  {group}", style=f"bold {Colors.ACCENT_YELLOW}"))
            for name in names:
                cmd = self._commands.get(name)
                if cmd:
                    menu_log.write(Text(f"    /{name:<14} {cmd.description}", style=Colors.TEXT_PRIMARY))

    def action_autocomplete(self) -> None:
        """Tab-completion for slash commands."""
        ibar = self.query_one("#input-bar", Input)
        text = ibar.value

        if not text.startswith("/"):
            return

        completions = self._commands.get_completions_for_input(text)
        if not completions:
            return

        if self._autocomplete_candidates == completions and self._autocomplete_index >= 0:
            self._autocomplete_index = (self._autocomplete_index + 1) % len(completions)
        else:
            self._autocomplete_candidates = completions
            self._autocomplete_index = 0

        parts = text[1:].split(maxsplit=1)
        cmd_name = parts[0] if parts else ""
        has_space = text.endswith(" ")

        choice = completions[self._autocomplete_index]
        choice_clean = choice.lstrip("/")

        # Determine if we're completing an arg (skill name) vs a subcommand
        cmd = self._commands.get(cmd_name)
        is_arg_completion = False
        if cmd and has_space:
            rest_text = parts[1] if len(parts) > 1 else ""
            sub_parts = rest_text.split(maxsplit=1)
            if len(sub_parts) >= 1 and sub_parts[0] in cmd.arg_completers:
                is_arg_completion = True

        if len(completions) == 1:
            if is_arg_completion:
                ibar.value = f"/{cmd_name} {sub_parts[0]} {choice_clean}"
            elif cmd and cmd.subcommands:
                ibar.value = f"/{cmd_name} {choice_clean} "
            elif not has_space:
                ibar.value = f"/{choice_clean} "
            else:
                ibar.value = f"/{cmd_name} {choice_clean} "
        else:
            if is_arg_completion:
                ibar.value = f"/{cmd_name} {sub_parts[0]} {choice_clean}"
            elif not has_space:
                ibar.value = f"/{choice_clean} "
            else:
                ibar.value = f"/{cmd_name} {choice_clean} "

        ibar.cursor_position = len(ibar.value)

        if len(completions) > 1:
            plog = self.query_one("#pipeline-log", RichLog)
            display = "  ".join(f"[{Colors.ACCENT_PURPLE}]/{c.lstrip('/')}[/]" for c in completions)
            plog.write(f"[dim]Completions:[/] {display}")

    def _handle_slash_command(self, text: str) -> None:
        """Route slash commands to the appropriate handler."""
        plog = self.query_one("#pipeline-log", RichLog)
        cmd_text = text.lstrip("/")
        parts = cmd_text.split(maxsplit=2)
        cmd_name = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        cmd = self._commands.get(cmd_name)
        if not cmd:
            plog.write(f"[{Colors.ERROR}]Unknown command: /{cmd_name}[/]. Type /help for available commands.")
            return

        if cmd_name == "help":
            self._cmd_help()
        elif cmd_name == "clear":
            self._cmd_clear()
        elif cmd_name == "health":
            self._cmd_health()
        elif cmd_name == "models":
            self._cmd_models()
        elif cmd_name == "tabs":
            self._cmd_tabs(args)
        elif cmd_name == "projects":
            self._cmd_projects()
        elif cmd_name == "project":
            self._cmd_project_switch(args)
        elif cmd_name == "newproject":
            self._cmd_new_project(args)
        elif cmd_name == "sessions":
            self.action_list_sessions()
        elif cmd_name == "session":
            self._handle_session_command(text)
        elif cmd_name == "save":
            name = args[0] if args else ""
            self._save_session_async(name)
        elif cmd_name == "load":
            if not args:
                plog.write(f"[{Colors.ERROR}]Usage: /load <session_id>[/]")
                return
            self._load_session_async(args[0])
        elif cmd_name == "history":
            self.action_list_sessions()
        elif cmd_name == "search":
            self._cmd_search_sessions(args)
        elif cmd_name == "recall":
            self._cmd_recall(args)
        elif cmd_name == "memory":
            self._cmd_memory_stats()
        elif cmd_name == "brain":
            self._cmd_brain(args)
        elif cmd_name == "skill":
            from zerion_core.cli.skill_commands import handle_skill_command
            handle_skill_command(self, args)
        elif cmd_name == "benchmark":
            from zerion_core.cli.benchmark_commands import handle_benchmark_command
            handle_benchmark_command(self, args)
        elif cmd_name == "todo":
            self._cmd_todo(args)

    # --- Command Handlers ---

    def _cmd_help(self) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        plog.write(f"[bold]Available Commands:[/]")
        plog.write(self._commands.get_all_help_text())

    def _cmd_clear(self) -> None:
        self.query_one("#pipeline-log", RichLog).clear()

    def _cmd_health(self) -> None:
        self._run_health_check()

    @work(exclusive=True)
    async def _run_health_check(self) -> None:
        from zerion_core.llm.ollama import OllamaClient
        plog = self.query_one("#pipeline-log", RichLog)
        llm = OllamaClient()
        try:
            ok = await llm.health()
            if ok:
                plog.write(f"[bold {Colors.SUCCESS}]Ollama:[/] Connected")
            else:
                plog.write(f"[bold {Colors.ERROR}]Ollama:[/] Not reachable")
        except Exception as e:
            plog.write(f"[bold {Colors.ERROR}]Ollama:[/] Error — {e}")

    def _cmd_models(self) -> None:
        self._run_list_models()

    @work(exclusive=True)
    async def _run_list_models(self) -> None:
        from zerion_core.llm.ollama import OllamaClient
        plog = self.query_one("#pipeline-log", RichLog)
        llm = OllamaClient()
        try:
            models = await llm.list_models()
            if models:
                plog.write("[bold]Available Models:[/]")
                for m in models:
                    plog.write(f"  [{Colors.INFO}]{m}[/]")
            else:
                plog.write("[dim]No models found.[/]")
        except Exception as e:
            plog.write(f"[{Colors.ERROR}]Error listing models: {e}[/]")

    def _cmd_tabs(self, args: list[str]) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if not args:
            plog.write("[dim]Usage: /tabs activity|terminal|diff|todos[/]")
            return
        tab = args[0]
        if tab in ("activity", "terminal", "diff", "todos"):
            self.action_switch_tab(tab)
        else:
            plog.write(f"[{Colors.ERROR}]Unknown tab: {tab}[/]. Use: activity, terminal, diff, todos")

    def _cmd_projects(self) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if not self.orchestrator:
            plog.write(f"[{Colors.ERROR}]Orchestrator not ready[/]")
            return
        projects = self.orchestrator.memory.get_all_projects() if hasattr(self.orchestrator, 'memory') else []
        if not projects:
            plog.write("[dim]No registered projects.[/]")
            plog.write("[dim]Use /newproject <name> to register one.[/]")
            return
        plog.write("[bold]Registered Projects:[/]")
        for p in projects:
            techs = ", ".join(p.tech_stack[:5]) if p.tech_stack else "—"
            plog.write(f"  [{Colors.INFO}]{p.name}[/] [dim]({techs})[/] — {p.description[:60] or '(no description)'}")

    def _cmd_project_switch(self, args: list[str]) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if not args:
            plog.write(f"[{Colors.ERROR}]Usage: /project <name>[/]")
            return
        name = args[0]
        if not self.orchestrator or not hasattr(self.orchestrator, 'memory'):
            plog.write(f"[{Colors.ERROR}]Orchestrator not ready[/]")
            return
        project = self.orchestrator.memory.get_project(name)
        if project:
            settings.set_workspace(project.name)
            plog.write(f"[bold {Colors.SUCCESS}]Switched to project:[/] {name}")
        else:
            plog.write(f"[{Colors.ERROR}]Project not found: {name}[/]")

    def _cmd_new_project(self, args: list[str]) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if not args:
            plog.write(f"[{Colors.ERROR}]Usage: /newproject <name> [description][/]")
            return
        name = args[0]
        desc = args[1] if len(args) > 1 else ""
        if not self.orchestrator or not hasattr(self.orchestrator, 'memory'):
            plog.write(f"[{Colors.ERROR}]Orchestrator not ready[/]")
            return
        self._register_project_async(name, desc)

    def _cmd_search_sessions(self, args: list[str]) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if not args:
            plog.write(f"[{Colors.ERROR}]Usage: /search <query>[/]")
            return
        query = " ".join(args)
        if not self.orchestrator:
            plog.write(f"[{Colors.ERROR}]Orchestrator not ready[/]")
            return
        results = self.orchestrator.session.searcher.search(query, limit=5)
        if not results:
            plog.write("[dim]No matching sessions found.[/]")
            return
        plog.write(f"[bold]Session Search Results for '{query}':[/]")
        for r in results:
            plog.write(f"  [{Colors.INFO}]{r.session_id}[/] — {r.title or '(untitled)'} [dim](score: {r.relevance_score:.2f})[/]")

    def _cmd_recall(self, args: list[str]) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if not args:
            plog.write(f"[{Colors.ERROR}]Usage: /recall <query>[/]")
            return
        query = " ".join(args)
        if not self.orchestrator or not hasattr(self.orchestrator, 'ltm'):
            plog.write(f"[{Colors.ERROR}]Long-term memory not initialized[/]")
            return
        import asyncio
        asyncio.ensure_future(self._recall_async(query))

    def _cmd_memory_stats(self) -> None:
        if not self.orchestrator or not hasattr(self.orchestrator, 'ltm'):
            plog = self.query_one("#pipeline-log", RichLog)
            plog.write(f"[{Colors.ERROR}]Long-term memory not initialized[/]")
            return
        import asyncio
        asyncio.ensure_future(self._memory_stats_async())

    def _cmd_brain(self, args: list[str]) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if not self.orchestrator or not hasattr(self.orchestrator, 'ltm'):
            plog.write(f"[{Colors.ERROR}]Long-term memory not initialized[/]")
            return
        project = args[0] if args else settings.project_name
        if not project:
            plog.write(f"[{Colors.ERROR}]No project specified or active.[/]")
            return
        import asyncio
        asyncio.ensure_future(self._brain_async(project))

    @work(exclusive=True)
    async def _save_session_async(self, name: str = "") -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if self.orchestrator:
            meta = await self.orchestrator.save_session(name=name)
            if meta:
                plog.write(f"[bold {Colors.SUCCESS}]Session saved:[/] {meta.title or meta.id}")

    @work(exclusive=True)
    async def _load_session_async(self, session_id: str) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if self.orchestrator:
            ok = await self.orchestrator.load_session(session_id)
            if ok:
                plog.write(f"[bold {Colors.SUCCESS}]Session loaded:[/] {session_id}")
            else:
                plog.write(f"[{Colors.ERROR}]Session not found: {session_id}[/]")

    @work(exclusive=True)
    async def _new_session_async(self) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if self.orchestrator:
            await self.orchestrator.new_session()
            plog.write(f"[bold {Colors.SUCCESS}]New session started.[/]")

    @work(exclusive=True)
    async def run_task(self, request: str) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        activity = self.query_one("#activity-view", ActivityPanel)
        task_summary = self.query_one("#task-summary", TaskSummaryPanel)
        
        plog.write(Text.from_markup(f"[bold {Colors.ACCENT_YELLOW}]USER[/] {request}"))
        activity.user_message(request)
        task_summary.update_task(request, 0.1, "routing")
        
        if not self.orchestrator:
            return
        try:
            result = await self.orchestrator.run(request)
            output = result.get("output", "")
            category = result.get("category", "")
            plog.write(Text.from_markup(f"[bold {Colors.SUCCESS}]COMPLETE[/] ({category})"))
            task_summary.update_task(request, 1.0, "complete")
            
            if output and category == "chat":
                plog.write(Markdown(output[:3000]))
            self._token_count += self.orchestrator.llm.total_usage.total
            self.query_one("#model-info", ModelInfoPanel).update_info(tokens=self._token_count)
        except Exception as exc:
            plog.write(Text.from_markup(f"[bold {Colors.ERROR}]ERROR[/] {exc}"))
            task_summary.update_task(request, 0, "error")
        
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
        self._save_session_async()

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
                    plog.write(f"  [{Colors.INFO}]{s.id}[/] — {s.title or '(untitled)'} [dim]({s.message_count} msgs)[/]")

    def action_dismiss_menu(self) -> None:
        """Close command menu via Escape."""
        self.show_command_menu = False

    async def on_unmount(self) -> None:
        if self.orchestrator:
            try:
                await self.orchestrator.save_session()
            except Exception:
                pass
            await self.orchestrator.stop()

    def _wire_dynamic_completers(self) -> None:
        """Wire dynamic completers for projects, sessions, and skill names."""
        def get_project_names() -> list[str]:
            if self.orchestrator and hasattr(self.orchestrator, 'memory'):
                return [p.name for p in self.orchestrator.memory.get_all_projects()]
            return []

        def get_session_ids() -> list[str]:
            if self.orchestrator:
                return [s.id for s in self.orchestrator.list_sessions()]
            return []

        def get_all_skill_names() -> list[str]:
            if self.orchestrator and hasattr(self.orchestrator, 'skill_manager'):
                sm = self.orchestrator.skill_manager
                names = set(sm._loaded.keys())
                available = sm.list_available()
                for s in available:
                    names.add(s["name"])
                return sorted(names)
            return []

        def get_installed_skill_names() -> list[str]:
            if self.orchestrator and hasattr(self.orchestrator, 'skill_manager'):
                return sorted(self.orchestrator.skill_manager._loaded.keys())
            return []

        self._commands.set_dynamic_completer("project", get_project_names)
        self._commands.set_dynamic_completer("newproject", get_project_names)
        self._commands.set_dynamic_completer("brain", get_project_names)
        self._commands.set_dynamic_completer("load", get_session_ids)
        self._commands.set_dynamic_completer("search", get_session_ids)

        # Skill arg completers: /skill install <names>, /skill uninstall <names>, etc.
        skill_names_getters = {
            "install": get_all_skill_names,
            "uninstall": get_installed_skill_names,
            "update": get_installed_skill_names,
            "enable": get_all_skill_names,
            "disable": get_installed_skill_names,
            "reload": get_installed_skill_names,
            "info": get_all_skill_names,
            "evolve": get_installed_skill_names,
            "consolidate": get_installed_skill_names,
            "distill": get_installed_skill_names,
        }
        for subcmd, getter in skill_names_getters.items():
            self._commands.set_arg_completer("skill", subcmd, getter)

    def _handle_session_command(self, text: str) -> None:
        """Handle /session subcommands."""
        plog = self.query_one("#pipeline-log", RichLog)
        cmd_text = text.lstrip("/")
        parts = cmd_text.split(maxsplit=2)
        action = parts[1] if len(parts) > 1 else ""

        if not self.orchestrator:
            plog.write(f"[{Colors.ERROR}]Orchestrator not ready[/]")
            return

        if action == "save":
            name = parts[2] if len(parts) > 2 else ""
            self._save_session_async(name)
        elif action == "list":
            self.action_list_sessions()
        elif action == "load":
            sid = parts[2].strip() if len(parts) > 2 else ""
            if not sid:
                plog.write(f"[{Colors.ERROR}]Usage: /session load <id>[/]")
                return
            self._load_session_async(sid)
        elif action == "delete":
            sid = parts[2].strip() if len(parts) > 2 else ""
            if not sid:
                plog.write(f"[{Colors.ERROR}]Usage: /session delete <id>[/]")
                return
            if self.orchestrator.delete_session(sid):
                plog.write(f"[bold {Colors.SUCCESS}]Deleted:[/] {sid}")
            else:
                plog.write(f"[{Colors.ERROR}]Session not found: {sid}[/]")
        elif action == "new":
            self._new_session_async()
        elif action == "switch":
            sid = parts[2].strip() if len(parts) > 2 else ""
            if not sid:
                plog.write(f"[{Colors.ERROR}]Usage: /session switch <id>[/]")
                return
            self._load_session_async(sid)
        elif action == "rename":
            plog.write("[dim]Usage: /session rename <id> <new_name>[/]")
        else:
            plog.write("[dim]Commands: /session save [name] | list | load <id> | delete <id> | new | switch <id>[/]")

    @work(exclusive=True)
    async def _register_project_async(self, name: str, desc: str) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if self.orchestrator and hasattr(self.orchestrator, 'memory'):
            try:
                entry = await self.orchestrator.memory.register_project(name, desc)
                plog.write(f"[bold {Colors.SUCCESS}]Project registered:[/] {name} ({', '.join(entry.tech_stack[:3])})")
            except Exception as e:
                plog.write(f"[{Colors.ERROR}]Error registering project: {e}[/]")

    @work(exclusive=True)
    async def _recall_async(self, query: str) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if self.orchestrator and hasattr(self.orchestrator, 'ltm'):
            results = await self.orchestrator.ltm.recall(query, k=5)
            if not results:
                plog.write(f"[dim]No memories found for '{query}'[/]")
                return
            plog.write(f"[bold]Memories for '{query}':[/]")
            for r in results:
                plog.write(f"  [{Colors.INFO}]{r['event_type']}[/] (imp: {r['importance']:.2f}) — {r['content'][:120]}")

    @work(exclusive=True)
    async def _memory_stats_async(self) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if self.orchestrator and hasattr(self.orchestrator, 'ltm'):
            stats = await self.orchestrator.ltm.stats()
            plog.write("[bold]Long-Term Memory Stats:[/]")
            plog.write(f"  Episodic Events: {stats['total_events']}")
            plog.write(f"  Project Brains: {stats['total_brains']}")
            plog.write(f"  Core Memories: {stats['core_memories']}")
            plog.write(f"  Avg Importance: {stats['avg_importance']:.2f}")

    @work(exclusive=True)
    async def _brain_async(self, project: str) -> None:
        plog = self.query_one("#pipeline-log", RichLog)
        if self.orchestrator and hasattr(self.orchestrator, 'ltm'):
            brain = await self.orchestrator.ltm.get_project_brain(project)
            if not brain:
                plog.write(f"[dim]No brain found for project '{project}'[/]")
                return
            plog.write(f"[bold]Project Brain: {project}[/]")
            for key, values in brain.items():
                if values:
                    plog.write(f"  [{Colors.INFO}]{key}:[/]")
                    for v in values[:5]:
                        plog.write(f"    - {v[:100]}")

    def _cmd_todo(self, args: list[str]) -> None:
        """Handle /todo commands."""
        plog = self.query_one("#pipeline-log", RichLog)
        todos = self.query_one("#todos-view", TodosPanel)

        if not args:
            plog.write("[dim]Usage: /todo <subcommand> [args][/]")
            plog.write("[dim]Subcommands: add, done, clear, set, list[/]")
            return

        action = args[0]
        rest = args[1:]

        if action == "set":
            if not rest:
                plog.write(f"[{Colors.ERROR}]Usage: /todo set <task1>, <task2>, ...[/]")
                return
            text = " ".join(rest)
            items = [t.strip() for t in text.split(",") if t.strip()]
            todos.set_todos(items)
            plog.write(f"[{Colors.SUCCESS}]Set {len(items)} todos[/]")

        elif action == "add":
            if not rest:
                plog.write(f"[{Colors.ERROR}]Usage: /todo add <task>[/]")
                return
            text = " ".join(rest)
            todos.add_todo(text)
            plog.write(f"[{Colors.SUCCESS}]Added: {text}[/]")

        elif action == "done":
            if not rest:
                plog.write(f"[{Colors.ERROR}]Usage: /todo done <task text to match>[/]")
                return
            text = " ".join(rest)
            if todos.complete_todo(text):
                plog.write(f"[{Colors.SUCCESS}]Completed: {text}[/]")
            else:
                plog.write(f"[{Colors.WARNING}]No matching todo found: {text}[/]")

        elif action == "clear":
            todos.clear()
            plog.write(f"[{Colors.SUCCESS}]Todos cleared[/]")

        elif action == "list":
            if not todos._todos:
                plog.write("[dim]No todos set[/]")
            else:
                done = sum(1 for t in todos._todos if t.done)
                total = len(todos._todos)
                plog.write(f"[bold]Todos ({done}/{total}):[/]")
                for t in todos._todos:
                    status = f"[{Colors.SUCCESS}]✓[/]" if t.done else f"[{Colors.WARNING}]○[/]"
                    plog.write(f"  {status} {t.text}")

        else:
            plog.write(f"[{Colors.ERROR}]Unknown action: {action}[/]")


def run_cli() -> None:
    ZerionApp().run()
