from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zerion_core.cli.app import run_cli
from zerion_core.config import settings
from zerion_core.llm.ollama import OllamaClient
from zerion_core.orchestrator.pipeline import Orchestrator


console = Console()


def _print_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Zerion-Core[/] — Local-first multi-agent coding platform\n"
            "[dim]Memory • Routing • Dynamic Teams • Repository Intelligence[/]",
            border_style="cyan",
        )
    )


async def _run_once(request: str) -> int:
    orch = Orchestrator(on_event=lambda e: console.print(f"[dim][{e.stage}][/] {e.message}"))
    await orch.start()
    try:
        healthy = await orch.llm.health()
        if not healthy:
            console.print("[yellow]Warning:[/] Ollama not reachable at", settings.ollama_base_url)
        result = await orch.run(request)
        console.print(Panel(result.get("output", "Done"), title="Result", border_style="green"))
        return 0
    finally:
        await orch.stop()


async def _check_health() -> int:
    client = OllamaClient()
    try:
        ok = await client.health()
        models = await client.list_models() if ok else []
        table = Table(title="Ollama Status")
        table.add_column("Check")
        table.add_column("Status")
        table.add_row("Connection", "[green]OK[/]" if ok else "[red]FAIL[/]")
        table.add_row("Models", ", ".join(models[:8]) if models else "none")
        console.print(table)
        return 0 if ok else 1
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="zerion", description="Zerion-Core multi-agent platform")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # Run command (default)
    run_parser = subparsers.add_parser("run", help="Run a task")
    run_parser.add_argument("request", nargs="?", help="Task request")
    run_parser.add_argument("--tui", action="store_true", help="Launch Textual dashboard")
    run_parser.add_argument("--once", action="store_true", help="Run single request and exit")
    
    # Session command
    session_parser = subparsers.add_parser("session", help="Manage sessions")
    session_sub = session_parser.add_subparsers(dest="session_action")
    
    session_list = session_sub.add_parser("list", help="List all saved sessions")
    session_list.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    
    session_save = session_sub.add_parser("save", help="Save current session")
    session_save.add_argument("-n", "--name", default="", help="Session name")
    session_save.add_argument("-d", "--description", default="", help="Session description")
    session_save.add_argument("-t", "--tags", nargs="*", default=[], help="Tags")
    
    session_load = session_sub.add_parser("load", help="Load a session")
    session_load.add_argument("session_id", help="Session ID to load")
    
    session_delete = session_sub.add_parser("delete", help="Delete a session")
    session_delete.add_argument("session_id", help="Session ID to delete")
    session_delete.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    
    session_rename = session_sub.add_parser("rename", help="Rename a session")
    session_rename.add_argument("session_id", help="Session ID")
    session_rename.add_argument("new_name", help="New name")
    
    session_new = session_sub.add_parser("new", help="Start a fresh session (clear memory)")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create a custom skill (model)")
    create_parser.add_argument("name", help="Name of the skill")
    create_parser.add_argument("-f", "--file", required=True, help="Path to the Modelfile/MD file")
    
    # Legacy/Global flags
    parser.add_argument("--health", action="store_true", help="Check Ollama connectivity")
    parser.add_argument("--create-skill", metavar="MD_FILE", help="[DEPRECATED] Create a skill from a file")
    
    # Handle old-style arguments for backward compatibility
    if len(sys.argv) > 1 and sys.argv[1] not in ("run", "create", "session", "--help", "-h", "--health"):
        # If first arg isn't a command, assume it's a request for 'run'
        if not sys.argv[1].startswith("-"):
            sys.argv.insert(1, "run")

    args = parser.parse_args()

    _print_banner()

    if args.health:
        sys.exit(asyncio.run(_check_health()))

    if args.command == "session":
        from zerion_core.session import SessionManager
        sessions = SessionManager()
        
        if args.session_action == "list":
            all_sessions = sessions.list_sessions()
            if getattr(args, 'as_json', False):
                import json
                print(json.dumps([s.model_dump() for s in all_sessions], indent=2))
            else:
                if not all_sessions:
                    console.print("[dim]No saved sessions.[/]")
                else:
                    table = Table(title="Saved Sessions")
                    table.add_column("ID", style="cyan")
                    table.add_column("Name", style="white")
                    table.add_column("Tasks", justify="right")
                    table.add_column("Updated", style="dim")
                    table.add_column("Tags", style="dim")
                    for s in all_sessions:
                        table.add_row(
                            s.id,
                            s.name or "(unnamed)",
                            str(s.task_count),
                            s.updated_at[:16],
                            ", ".join(s.tags) if s.tags else "",
                        )
                    console.print(table)
        
        elif args.session_action == "save":
            meta = sessions.save(
                memory=None,
                name=args.name,
                description=args.description,
                tags=args.tags,
            )
            console.print(f"[bold green]Session saved:[/] {meta.name} ({meta.id})")
        
        elif args.session_action == "load":
            try:
                session = sessions.load(args.session_id)
                console.print(f"[bold]Session:[/] {session.meta.name} ({session.meta.id})")
                console.print(f"[dim]Created:[/] {session.meta.created_at}")
                console.print(f"[dim]Tasks:[/] {session.meta.task_count}")
                if session.conversation:
                    console.print(f"[dim]Messages:[/] {len(session.conversation)}")
                console.print("\n[dim]To restore this session's memory, use the TUI or Python API.[/]")
            except FileNotFoundError:
                console.print(f"[bold red]Session not found:[/] {args.session_id}")
                sys.exit(1)
        
        elif args.session_action == "delete":
            if not args.yes:
                confirm = input(f"Delete session {args.session_id}? [y/N] ").strip().lower()
                if confirm != "y":
                    console.print("[dim]Cancelled.[/]")
                    sys.exit(0)
            if sessions.delete(args.session_id):
                console.print(f"[bold green]Deleted:[/] {args.session_id}")
            else:
                console.print(f"[bold red]Session not found:[/] {args.session_id}")
                sys.exit(1)
        
        elif args.session_action == "rename":
            if sessions.rename(args.session_id, args.new_name):
                console.print(f"[bold green]Renamed to:[/] {args.new_name}")
            else:
                console.print(f"[bold red]Session not found:[/] {args.session_id}")
                sys.exit(1)
        
        elif args.session_action == "new":
            console.print("[bold green]New session started.[/] Memory will be fresh.")
        
        else:
            console.print("[dim]Use: session list|save|load|delete|rename|new[/]")
        
        sys.exit(0)

    if args.command == "create":
        from pathlib import Path
        from zerion_core.tools.skill_creator import parse_skill_md, save_skill
        from zerion_core.llm.ollama import OllamaClient
        
        md_path = Path(args.file)
        if not md_path.exists():
            console.print(f"[bold red]Error:[/] File {args.file} not found")
            sys.exit(1)
            
        skill = parse_skill_md(md_path)
        if skill:
            # 2. Trigger actual Ollama creation
            async def do_create():
                client = OllamaClient()
                try:
                    from_model = skill.get("model", settings.default_model)
                    system_prompt = skill.get("system_prompt")
                    
                    console.print(f"Creating Ollama model '[bold]{args.name}[/]' from [bold]{from_model}[/]...")
                    async for status in client.create_model(args.name, from_model, system_prompt):
                        if msg := status.get("status"):
                            console.print(f"  [dim]ollama:[/] {msg}")
                    
                    # Store the registered model name
                    target = save_skill(args.name, skill, f"{args.name}:latest")
                    
                    console.print(f"[bold green]Success![/] Skill/Model '[bold]{args.name}[/]' is now ready.")
                    console.print(f"[dim]Metadata:[/] {target}")
                except Exception as exc:
                    console.print(f"[bold red]Ollama Error:[/] {exc}")
                finally:
                    await client.close()
            
            asyncio.run(do_create())
            sys.exit(0)
        else:
            console.print(f"[bold red]Error:[/] Could not parse skill from {args.file}")
            sys.exit(1)

    # Legacy support
    if args.create_skill:
        from pathlib import Path
        from zerion_core.tools.skill_creator import parse_skill_md, save_skill
        md_path = Path(args.create_skill)
        skill = parse_skill_md(md_path)
        if skill:
            save_skill(md_path.stem, skill, f"{md_path.stem}:latest")
            console.print(f"[bold green]Success![/] Skill '{md_path.stem}' created")
            sys.exit(0)

    # Run command logic
    if args.command == "run" or (not args.command and getattr(args, 'request', None)):
        request = getattr(args, 'request', None)
        once = getattr(args, 'once', False)
        tui = getattr(args, 'tui', True)
        
        if request and (once or not tui):
            sys.exit(asyncio.run(_run_once(request)))

    run_cli()


if __name__ == "__main__":
    main()
