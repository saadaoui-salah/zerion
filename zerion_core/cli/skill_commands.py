"""CLI commands for the /skill system."""

from __future__ import annotations

import json
import asyncio
from typing import TYPE_CHECKING

from rich.text import Text

if TYPE_CHECKING:
    from zerion_core.cli.app import ZerionApp


def register_skill_commands(app: "ZerionApp") -> None:
    """Register /skill commands with the app's command registry."""
    from zerion_core.cli.commands import CommandRegistry

    app._commands.register("skill", "Skill management",
                          usage="/skill install|uninstall|list|info|search|enable|disable|reload|evolve|consolidate|distill|maintain",
                          subcommands=["install", "uninstall", "update", "list", "info", "search", "enable", "disable", "reload", "export", "import", "evolve", "consolidate", "distill", "maintain"])


def _get_all_skill_names(app: "ZerionApp") -> list[str]:
    """Get all available skill names (installed + built-in)."""
    if not app.orchestrator or not hasattr(app.orchestrator, 'skill_manager'):
        return []
    sm = app.orchestrator.skill_manager
    names = set(sm._loaded.keys())
    available = sm.list_available()
    for s in available:
        names.add(s["name"])
    return sorted(names)


def _get_installed_skill_names(app: "ZerionApp") -> list[str]:
    """Get installed skill names."""
    if not app.orchestrator or not hasattr(app.orchestrator, 'skill_manager'):
        return []
    return sorted(app.orchestrator.skill_manager._loaded.keys())


def handle_skill_command(app: "ZerionApp", args: list[str]) -> None:
    """Handle /skill subcommands.

    Args come from _handle_slash_command which does maxsplit=2, so we may
    get ["install", "a b c"] — we flatten the remaining parts to get
    ["install", "a", "b", "c"].
    """
    plog = app.query_one("#pipeline-log")

    if not args:
        plog.write("[dim]Usage: /skill <subcommand> [args][/]")
        plog.write("[dim]Subcommands: install, uninstall, update, list, info, search, enable, disable, reload, export, import[/]")
        plog.write("[dim]Advanced: evolve, consolidate, distill, maintain[/]")
        plog.write("[dim]Tip: Multiple skills can be separated by spaces (e.g., /skill install a b c)[/]")
        return

    action = args[0]
    # Flatten remaining args: each part may contain space-separated skill names
    rest = []
    for part in args[1:]:
        rest.extend(part.split())

    # Actions that accept multiple skill names
    multi_actions = {"install", "uninstall", "update", "enable", "disable", "reload", "evolve", "consolidate", "distill"}

    if action in multi_actions:
        if not rest:
            plog.write(f"[red]Usage: /skill {action} <name> [name2] [name3] ...[/]")
            return
        if action == "install":
            asyncio.ensure_future(_skill_install_multi(app, rest))
        elif action == "uninstall":
            asyncio.ensure_future(_skill_uninstall_multi(app, rest))
        elif action == "update":
            asyncio.ensure_future(_skill_update_multi(app, rest))
        elif action == "enable":
            _skill_enable_multi(app, rest)
        elif action == "disable":
            _skill_disable_multi(app, rest)
        elif action == "reload":
            _skill_reload_multi(app, rest)
        elif action == "evolve":
            asyncio.ensure_future(_skill_evolve_multi(app, rest))
        elif action == "consolidate":
            asyncio.ensure_future(_skill_consolidate_multi(app, rest))
        elif action == "distill":
            asyncio.ensure_future(_skill_distill_multi(app, rest))

    elif action == "list":
        _skill_list(app)

    elif action == "info":
        if not rest:
            plog.write("[red]Usage: /skill info <name>[/]")
            return
        _skill_info(app, rest[0])

    elif action == "search":
        if not rest:
            plog.write("[red]Usage: /skill search <query>[/]")
            return
        asyncio.ensure_future(_skill_search(app, " ".join(rest)))

    elif action == "compose":
        plog.write("[red]Skill composition not yet implemented[/]")

    elif action == "export":
        if not rest:
            plog.write("[red]Usage: /skill export <name>[/]")
            return
        asyncio.ensure_future(_skill_export(app, rest[0]))

    elif action == "import":
        if not rest:
            plog.write("[red]Usage: /skill import <path>[/]")
            return
        asyncio.ensure_future(_skill_import(app, rest[0]))

    elif action == "maintain":
        asyncio.ensure_future(_skill_maintain(app))

    else:
        plog.write(f"[red]Unknown skill subcommand: {action}[/]")


# --- Async handlers (multi-skill support) ---

def _sm(app: "ZerionApp"):
    if app.orchestrator and hasattr(app.orchestrator, 'skill_manager'):
        return app.orchestrator.skill_manager
    return None


async def _skill_install_multi(app: "ZerionApp", sources: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for source in sources:
        plog.write(f"[bold #a78bfa]Installing: {source}...[/]")
        try:
            ok, msg = await sm.install(source)
            plog.write(f"[bold #4ec9b0]{msg}[/]" if ok else f"[red]{msg}[/]")
        except Exception as e:
            plog.write(f"[red]Failed to install {source}: {e}[/]")
    if len(sources) > 1:
        plog.write(f"[bold #4ec9b0]Installed {len(sources)} skill(s)[/]")


async def _skill_uninstall_multi(app: "ZerionApp", names: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for name in names:
        plog.write(f"[bold #a78bfa]Uninstalling: {name}...[/]")
        try:
            ok, msg = await sm.uninstall(name)
            plog.write(f"[bold #4ec9b0]{msg}[/]" if ok else f"[red]{msg}[/]")
        except Exception as e:
            plog.write(f"[red]Failed to uninstall {name}: {e}[/]")


async def _skill_update_multi(app: "ZerionApp", names: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for name in names:
        plog.write(f"[bold #a78bfa]Updating: {name}...[/]")
        try:
            ok, msg = await sm.installer.update(name)
            plog.write(f"[bold #4ec9b0]{msg}[/]" if ok else f"[red]{msg}[/]")
        except Exception as e:
            plog.write(f"[red]Failed to update {name}: {e}[/]")


def _skill_enable_multi(app: "ZerionApp", names: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for name in names:
        if sm.enable(name):
            plog.write(f"[bold #4ec9b0]Enabled:[/] {name}")
        else:
            plog.write(f"[red]Skill not found: {name}[/]")


def _skill_disable_multi(app: "ZerionApp", names: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for name in names:
        sm.disable(name)
        plog.write(f"[bold #d7ba7d]Disabled:[/] {name}")


def _skill_reload_multi(app: "ZerionApp", names: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for name in names:
        skill = sm.reload(name)
        if skill:
            plog.write(f"[bold #4ec9b0]Reloaded:[/] {name} v{skill.manifest.version}")
        else:
            plog.write(f"[red]Failed to reload: {name}[/]")


async def _skill_evolve_multi(app: "ZerionApp", names: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for name in names:
        if not sm.get_skill(name):
            plog.write(f"[red]Skill not found: {name}[/]")
            continue
        plog.write(f"[bold #a78bfa]Evolving: {name}...[/]")
        try:
            result = await sm.evolve_skill(name)
            if result:
                maturity = result.get("maturity", "unknown")
                patterns = len(result.get("patterns", []))
                plog.write(f"[bold #4ec9b0]Evolved:[/] {name} → {maturity}, {patterns} patterns")
            else:
                plog.write(f"[dim]{name}: No evolution data available[/]")
        except Exception as e:
            plog.write(f"[red]Evolution failed for {name}: {e}[/]")


async def _skill_consolidate_multi(app: "ZerionApp", names: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for name in names:
        if not sm.get_skill(name):
            plog.write(f"[red]Skill not found: {name}[/]")
            continue
        plog.write(f"[bold #a78bfa]Consolidating: {name}...[/]")
        try:
            result = await sm.consolidate_skill(name)
            if result:
                merged = result.get("merged", 0)
                plog.write(f"[bold #4ec9b0]Consolidated:[/] {name} → {merged} merged")
            else:
                plog.write(f"[dim]{name}: No memories to consolidate[/]")
        except Exception as e:
            plog.write(f"[red]Consolidation failed for {name}: {e}[/]")


async def _skill_distill_multi(app: "ZerionApp", names: list[str]) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return
    for name in names:
        if not sm.get_skill(name):
            plog.write(f"[red]Skill not found: {name}[/]")
            continue
        plog.write(f"[bold #a78bfa]Distilling: {name}...[/]")
        try:
            brain_content = await sm.distill_knowledge(name)
            if brain_content:
                plog.write(f"[bold #4ec9b0]Distilled:[/] {name} ({len(brain_content)} chars)")
            else:
                plog.write(f"[dim]{name}: No knowledge to distill[/]")
        except Exception as e:
            plog.write(f"[red]Distillation failed for {name}: {e}[/]")


# --- Single-skill commands ---

def _skill_list(app: "ZerionApp") -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return

    skills = sm.list_installed()
    active = [s.manifest.name for s in sm.list_active()]
    disabled = sm.list_disabled()
    available = sm.list_available()

    if skills:
        plog.write("[bold]Installed Skills:[/]")
        for skill in skills:
            name = skill.manifest.name
            status_icon = "[green]ACTIVE[/]" if name in active else "[dim]installed[/]"
            if name in disabled:
                status_icon = "[red]disabled[/]"
            tags = ", ".join(skill.manifest.tags[:3])
            plog.write(f"  {status_icon} [cyan]{name}[/] [dim]v{skill.manifest.version}[/] ({tags})")
    else:
        plog.write("[dim]No skills installed.[/]")

    not_installed = [s for s in available if not s["installed"]]
    if not_installed:
        plog.write("\n[bold]Available Built-in Skills:[/]")
        for skill in not_installed:
            tags = ", ".join(skill["tags"])
            plog.write(f"  [dim]○[/] [cyan]{skill['name']}[/] [dim]v{skill['version']}[/] ({tags})")
            if skill["description"]:
                plog.write(f"    [dim]{skill['description'][:80]}[/]")
        plog.write("\n[dim]Use /skill install <name> to install[/]")


def _skill_info(app: "ZerionApp", name: str) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return

    info = sm.get_skill_info(name)
    if not info:
        plog.write(f"[red]Skill not found: {name}[/]")
        return

    plog.write(f"[bold]Skill: {info['name']}[/] v{info['version']}")
    plog.write(f"  Description: {info['description']}")
    plog.write(f"  Author: {info['author'] or '—'}")
    plog.write(f"  Tags: {', '.join(info['tags'])}")
    plog.write(f"  Status: {info['status']} | Active: {info['active']} | Disabled: {info['disabled']}")
    plog.write(f"  Reputation: {info['reputation']:.2f}")
    plog.write(f"  Doc Chunks: {info['doc_chunks']}")
    plog.write(f"  Workflow: {'Yes' if info['has_workflow'] else 'No'}")
    plog.write(f"  RAG: {'Yes' if info['has_rag'] else 'No'}")
    mem = info.get("memory", {})
    if mem:
        plog.write(f"  Memory: {mem.get('total_memories', 0)} entries")
    collab = info.get("collaboration", {})
    if collab:
        plog.write(f"  Collaborations: {collab.get('total_collaborations', 0)}")


async def _skill_search(app: "ZerionApp", query: str) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return

    matches = await sm.semantic_search(query, top_k=5)
    if not matches:
        plog.write(f"[dim]No skills matching '{query}'[/]")
        return

    plog.write(f"[bold]Skills matching '{query}':[/]")
    for m in matches:
        plog.write(f"  [cyan]{m.skill_name}[/] [dim](score={m.score:.2f})[/] — {m.reason}")


async def _skill_export(app: "ZerionApp", name: str) -> None:
    from pathlib import Path
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return

    dest = Path(f"./{name}_export")
    ok, msg = sm.installer.export_skill(name, dest)
    plog.write(f"[bold #4ec9b0]{msg}[/]" if ok else f"[red]{msg}[/]")


async def _skill_import(app: "ZerionApp", path: str) -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return

    ok, msg = await sm.install(path)
    plog.write(f"[bold #4ec9b0]{msg}[/]" if ok else f"[red]{msg}[/]")


async def _skill_maintain(app: "ZerionApp") -> None:
    plog = app.query_one("#pipeline-log")
    sm = _sm(app)
    if not sm:
        plog.write("[red]Skill system not initialized[/]")
        return

    plog.write("[bold #a78bfa]Running maintenance on all skills...[/]")
    try:
        results = await sm.run_maintenance()
        if results:
            plog.write(f"[bold #4ec9b0]Maintenance complete:[/]")
            for skill_name, res in results.items():
                if "error" in res:
                    plog.write(f"  [red]✗ {skill_name}: {res['error']}[/]")
                else:
                    consolidation = res.get("consolidation", {})
                    merged = consolidation.get("merged", 0) if isinstance(consolidation, dict) else 0
                    patterns = res.get("patterns", 0)
                    brain = "✓" if res.get("brain_updated") else "—"
                    plog.write(f"  [green]✓[/] {skill_name}: {merged} merged, {patterns} patterns, brain={brain}")
        else:
            plog.write("[dim]No skills to maintain[/]")
    except Exception as e:
        plog.write(f"[red]Maintenance failed: {e}[/]")
