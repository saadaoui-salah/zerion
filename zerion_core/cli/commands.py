"""Slash command system with autocomplete for the TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Command:
    name: str
    description: str
    usage: str = ""
    handler: Callable[..., Any] | None = None
    subcommands: list[str] = field(default_factory=list)
    dynamic_completer: Callable[[], list[str]] | None = None
    arg_completers: dict[str, Callable[[], list[str]]] = field(default_factory=dict)


class CommandRegistry:
    """Registry of all available slash commands with autocomplete support."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._dynamic_completers: dict[str, Callable[[], list[str]]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("help", "Show available commands", usage="/help")
        self.register("clear", "Clear the pipeline log", usage="/clear")
        self.register("health", "Check Ollama connectivity", usage="/health")
        self.register("models", "List available models", usage="/models")
        self.register("tabs", "Switch tabs", usage="/tabs activity|terminal|diff",
                      subcommands=["activity", "terminal", "diff"])

        # Project commands
        self.register("projects", "List all registered projects", usage="/projects")
        self.register("project", "Switch active project", usage="/project <name>")
        self.register("newproject", "Register a new project", usage="/newproject <name> <description>")

        # Session commands
        self.register("sessions", "List all sessions", usage="/sessions")
        self.register("session", "Session management", usage="/session save|list|load|delete|new|rename|switch",
                      subcommands=["save", "list", "load", "delete", "new", "rename", "switch"])
        self.register("save", "Save current session", usage="/save [name]")
        self.register("load", "Load a session", usage="/load <id>")
        self.register("history", "Show recent sessions", usage="/history")
        self.register("search", "Search sessions", usage="/search <query>")

        # Memory commands
        self.register("recall", "Recall long-term memories", usage="/recall <query>")
        self.register("memory", "Show memory stats", usage="/memory")
        self.register("brain", "View project brain", usage="/brain [project]")

        # Skill commands
        self.register("skill", "Skill management", usage="/skill install|uninstall|list|info|search|enable|disable|reload|compose|export|import",
                      subcommands=["install", "uninstall", "update", "list", "info", "search", "enable", "disable", "reload", "compose", "export", "import"])

        # Benchmark commands
        self.register("benchmark", "Skill benchmarking and performance evaluation",
                      usage="/benchmark leaderboard|report|compare|health|failures|workflow|consolidate|ab_test|skill_report",
                      subcommands=["leaderboard", "report", "compare", "health", "failures", "workflow", "consolidate", "ab_test", "skill_report"])

        # Todo commands
        self.register("todo", "Todo list management",
                      usage="/todo add|done|clear|set|list",
                      subcommands=["add", "done", "clear", "set", "list"])

    def register(
        self,
        name: str,
        description: str,
        usage: str = "",
        subcommands: list[str] | None = None,
        handler: Callable[..., Any] | None = None,
        dynamic_completer: Callable[[], list[str]] | None = None,
    ) -> None:
        self._commands[name] = Command(
            name=name,
            description=description,
            usage=usage,
            handler=handler,
            subcommands=subcommands or [],
            dynamic_completer=dynamic_completer,
        )
        if dynamic_completer:
            self._dynamic_completers[name] = dynamic_completer

    def set_dynamic_completer(self, command_name: str, completer: Callable[[], list[str]]) -> None:
        """Set a dynamic completer for a command after registration."""
        if command_name in self._commands:
            self._commands[command_name].dynamic_completer = completer
            self._dynamic_completers[command_name] = completer

    def set_arg_completer(self, command_name: str, subcommand: str, completer: Callable[[], list[str]]) -> None:
        """Set a completer for a specific subcommand's arguments (e.g., /skill install <skill_names>)."""
        if command_name in self._commands:
            self._commands[command_name].arg_completers[subcommand] = completer

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def all_commands(self) -> list[Command]:
        return list(self._commands.values())

    def command_names(self) -> list[str]:
        return list(self._commands.keys())

    def fuzzy_match(self, prefix: str) -> list[str]:
        prefix_lower = prefix.lower()
        matches: list[str] = []
        for name in self._commands:
            if name.startswith(prefix_lower):
                matches.append(name)
        return sorted(matches)

    def get_completions(self, text: str) -> list[str]:
        """Get autocomplete suggestions for the current input text.

        Handles:
        - "/he" → ["health", "help"]
        - "/project " → [dynamic project list]
        - "/load se" → ["session_abc123"]
        - "/skill install " → [skill names]
        - "/skill install d" → ["django-expert"]
        """
        if not text.startswith("/"):
            return []

        parts = text[1:].split(maxsplit=2)
        if not parts:
            return [f"/{name}" for name in sorted(self._commands.keys())]

        cmd_name = parts[0]
        args_text = parts[1] if len(parts) > 1 else ""

        # Still typing the command name
        if len(parts) == 1 and not text.endswith(" "):
            matches = self.fuzzy_match(cmd_name)
            return [f"/{m}" for m in matches]

        # Command is complete — subcommand completions
        cmd = self._commands.get(cmd_name)
        if cmd:
            if cmd.subcommands:
                if text.endswith(" "):
                    return cmd.subcommands
                return [s for s in cmd.subcommands if s.startswith(args_text)]

            # Dynamic completions (projects, sessions, etc.)
            if cmd.dynamic_completer:
                all_items = cmd.dynamic_completer()
                if text.endswith(" "):
                    return all_items
                return [item for item in all_items if item.startswith(args_text)]

        return []

    def get_completions_for_input(self, text: str) -> list[str]:
        """Get autocomplete suggestions, including per-subcommand arg completers.

        If the user has typed /skill install d, detect that 'install' is the
        subcommand and offer skill names (filtered by 'd') instead of subcommands.
        """
        if not text.startswith("/"):
            return []

        parts = text[1:].split(maxsplit=2)
        if not parts:
            return [f"/{name}" for name in sorted(self._commands.keys())]

        cmd_name = parts[0]
        rest_text = parts[1] if len(parts) > 1 else ""

        # Still typing the command name
        if len(parts) == 1 and not text.endswith(" "):
            matches = self.fuzzy_match(cmd_name)
            return [f"/{m}" for m in matches]

        cmd = self._commands.get(cmd_name)
        if not cmd:
            return []

        # Check if we have an arg_completer for this subcommand
        subcmd, sub_args = "", ""
        if rest_text:
            sub_parts = rest_text.split(maxsplit=1)
            subcmd = sub_parts[0]
            sub_args = sub_parts[1] if len(sub_parts) > 1 else ""

        if subcmd in cmd.arg_completers and (text.endswith(" ") or sub_args):
            completer = cmd.arg_completers[subcmd]
            all_items = completer()
            if text.endswith(" "):
                return all_items
            return [item for item in all_items if item.startswith(sub_args)]

        # Fall back to normal subcommand completions
        if cmd.subcommands:
            if text.endswith(" "):
                return cmd.subcommands
            return [s for s in cmd.subcommands if s.startswith(rest_text)]

        # Dynamic completions
        if cmd.dynamic_completer:
            all_items = cmd.dynamic_completer()
            if text.endswith(" "):
                return all_items
            return [item for item in all_items if item.startswith(rest_text)]

        return []

    def get_all_help_text(self) -> str:
        lines = []
        for cmd in sorted(self._commands.values(), key=lambda c: c.name):
            usage = cmd.usage or f"/{cmd.name}"
            lines.append(f"  /{cmd.name:<14} {cmd.description}")
        return "\n".join(lines)
