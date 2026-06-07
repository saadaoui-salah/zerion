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
    
    # Global flags
    parser.add_argument("-w", "--workspace", default="", help="Working directory (default: cwd)")
    
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
    
    # RAG command
    rag_parser = subparsers.add_parser("rag", help="Manage RAG code index")
    rag_sub = rag_parser.add_subparsers(dest="rag_action")
    
    rag_index = rag_sub.add_parser("index", help="Build/update the code index")
    rag_index.add_argument("--stats", action="store_true", help="Show index statistics")
    
    rag_query = rag_sub.add_parser("query", help="Query the code index")
    rag_query.add_argument("query_text", help="Search query")
    rag_query.add_argument("-k", type=int, default=5, help="Number of results")
    
    rag_reset = rag_sub.add_parser("reset", help="Reset the code index")
    rag_reset.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    
    # Memory command (long-term memory)
    memory_parser = subparsers.add_parser("memory", help="Manage long-term memory")
    memory_sub = memory_parser.add_subparsers(dest="memory_action")
    
    memory_recall = memory_sub.add_parser("recall", help="Recall memories")
    memory_recall.add_argument("query_text", help="Search query")
    memory_recall.add_argument("-p", "--project", default="", help="Project filter")
    memory_recall.add_argument("-k", type=int, default=10, help="Number of results")
    
    memory_stats = memory_sub.add_parser("stats", help="Show memory statistics")
    
    memory_decay = memory_sub.add_parser("decay", help="Run importance decay")
    
    memory_brain = memory_sub.add_parser("brain", help="View project brain")
    memory_brain.add_argument("project_id", help="Project ID")
    
    memory_search = memory_sub.add_parser("search", help="Search by time range")
    memory_search.add_argument("time_text", help="Time description (e.g. '3 days ago', 'last week')")
    memory_search.add_argument("-p", "--project", default="", help="Project filter")
    
    # Skill command
    skill_parser = subparsers.add_parser("skill", help="Manage skills")
    skill_sub = skill_parser.add_subparsers(dest="skill_action")
    
    skill_list = skill_sub.add_parser("list", help="List all available skills")
    skill_list.add_argument("-a", "--all", action="store_true", dest="show_all", help="Show all available built-in skills")
    
    skill_install = skill_sub.add_parser("install", help="Install a skill")
    skill_install.add_argument("source", help="Skill name or source (local path, github:user/repo, URL)")
    
    skill_uninstall = skill_sub.add_parser("uninstall", help="Uninstall a skill")
    skill_uninstall.add_argument("name", help="Skill name")
    skill_uninstall.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    
    skill_enable = skill_sub.add_parser("enable", help="Enable a skill")
    skill_enable.add_argument("name", help="Skill name")
    
    skill_disable = skill_sub.add_parser("disable", help="Disable a skill")
    skill_disable.add_argument("name", help="Skill name")
    
    skill_info = skill_sub.add_parser("info", help="Show skill details")
    skill_info.add_argument("name", help="Skill name")
    
    skill_search = skill_sub.add_parser("search", help="Search skills by tags")
    skill_search.add_argument("tags", nargs="+", help="Tags to search for")
    
    # Legacy/Global flags
    parser.add_argument("--health", action="store_true", help="Check Ollama connectivity")
    parser.add_argument("--create-skill", metavar="MD_FILE", help="[DEPRECATED] Create a skill from a file")
    
    # Handle old-style arguments for backward compatibility
    if len(sys.argv) > 1 and sys.argv[1] not in ("run", "create", "session", "rag", "memory", "skill", "--help", "-h", "--health", "-w", "--workspace"):
        # If first arg isn't a command, assume it's a request for 'run'
        if not sys.argv[1].startswith("-"):
            sys.argv.insert(1, "run")

    args = parser.parse_args()

    # Initialize workspace from flag or environment
    if args.workspace:
        import os
        os.environ["ZERION_WORKSPACE"] = args.workspace

    _print_banner()

    if args.health:
        sys.exit(asyncio.run(_check_health()))

    if args.command == "session":
        from zerion_core.session import SessionManager, SessionStore
        store = SessionStore()
        
        if args.session_action == "list":
            all_sessions = store.list_sessions()
            if getattr(args, 'as_json', False):
                import json
                print(json.dumps([s.model_dump() for s in all_sessions], indent=2))
            else:
                if not all_sessions:
                    console.print("[dim]No saved sessions.[/]")
                else:
                    table = Table(title="Saved Sessions")
                    table.add_column("ID", style="cyan")
                    table.add_column("Title", style="white")
                    table.add_column("Project", style="dim")
                    table.add_column("Messages", justify="right")
                    table.add_column("Updated", style="dim")
                    table.add_column("Tags", style="dim")
                    for s in all_sessions:
                        table.add_row(
                            s.id,
                            s.title or "(untitled)",
                            s.project_id or "-",
                            str(s.message_count),
                            s.updated_at[:16],
                            ", ".join(s.tags) if s.tags else "",
                        )
                    console.print(table)
        
        elif args.session_action == "save":
            # Save requires an active session from the orchestrator
            console.print("[dim]Use 'zerion run' to create and save sessions interactively.[/]")
            console.print("[dim]Or use the TUI with Ctrl+S to save the current session.[/]")
        
        elif args.session_action == "load":
            data = store.load_full_session(args.session_id)
            if data:
                console.print(f"[bold]Session:[/] {data.meta.title or data.meta.id}")
                console.print(f"[dim]Created:[/] {data.meta.created_at}")
                console.print(f"[dim]Messages:[/] {data.meta.message_count}")
                console.print(f"[dim]Project:[/] {data.meta.project_id or '(none)'}")
                if data.summary:
                    console.print(f"\n[bold]Summary:[/]\n{data.summary[:500]}")
                if data.messages:
                    console.print(f"\n[bold]Last messages:[/]")
                    for m in data.messages[-5:]:
                        console.print(f"  [{m.role.value}]: {m.content[:100]}...")
            else:
                console.print(f"[bold red]Session not found:[/] {args.session_id}")
                sys.exit(1)
        
        elif args.session_action == "delete":
            if not args.yes:
                confirm = input(f"Delete session {args.session_id}? [y/N] ").strip().lower()
                if confirm != "y":
                    console.print("[dim]Cancelled.[/]")
                    sys.exit(0)
            if store.delete_session(args.session_id):
                console.print(f"[bold green]Deleted:[/] {args.session_id}")
            else:
                console.print(f"[bold red]Session not found:[/] {args.session_id}")
                sys.exit(1)
        
        elif args.session_action == "rename":
            meta = store.get_session_meta(args.session_id)
            if meta:
                meta.title = args.new_name
                store.update_session_meta(meta)
                console.print(f"[bold green]Renamed to:[/] {args.new_name}")
            else:
                console.print(f"[bold red]Session not found:[/] {args.session_id}")
                sys.exit(1)
        
        elif args.session_action == "new":
            console.print("[bold green]New session started.[/] Use 'zerion run' to begin.")
        
        else:
            console.print("[dim]Use: session list|save|load|delete|rename|new[/]")
        
        store.close()
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

    if args.command == "rag":
        from pathlib import Path
        from zerion_core.rag.indexer import CodeIndexer
        from zerion_core.rag.embeddings import EmbeddingProvider
        from zerion_core.rag.retriever import CodeRetriever
        from zerion_core.rag.vectorstore import CodeVectorStore
        
        indexer = CodeIndexer()
        
        if args.rag_action == "index":
            if getattr(args, 'stats', False):
                indexer._load_manifest()
                manifest = indexer._manifest
                if not manifest:
                    console.print("[dim]No index found. Run 'zerion rag index' to build.[/]")
                else:
                    total_chunks = sum(v.get("chunks", 0) for v in manifest.values())
                    table = Table(title="RAG Index Stats")
                    table.add_column("Metric")
                    table.add_column("Value")
                    table.add_row("Files indexed", str(len(manifest)))
                    table.add_row("Total chunks", str(total_chunks))
                    table.add_row("Index path", str(indexer.index_path))
                    console.print(table)
            else:
                async def do_index():
                    llm = OllamaClient()
                    try:
                        embeddings = EmbeddingProvider(llm)
                        store = CodeVectorStore()
                        
                        console.print("[bold]Indexing codebase...[/]")
                        chunks = indexer.index_full(
                            on_progress=lambda i, total, path: console.print(f"  [dim][{i}/{total}][/] {path}")
                        )
                        
                        if chunks:
                            retriever = CodeRetriever(embeddings, store)
                            retriever.build_keyword_index(chunks)
                            
                            # Batch store
                            batch_size = 32
                            for i in range(0, len(chunks), batch_size):
                                batch = chunks[i:i + batch_size]
                                ids = [c.id for c in batch]
                                texts = [c.content for c in batch]
                                embs = await embeddings.embed_batch(texts)
                                metadatas = [
                                    {"file_path": c.file_path, "chunk_type": c.chunk_type,
                                     "symbol_name": c.symbol_name, "parent_class": c.parent_class,
                                     "language": c.language, "start_line": str(c.start_line),
                                     "end_line": str(c.end_line)}
                                    for c in batch
                                ]
                                await store.upsert(ids, embs, texts, metadatas)
                            
                            console.print(f"[bold green]Indexed {len(chunks)} chunks from {len(set(c.file_path for c in chunks))} files[/]")
                        else:
                            console.print("[yellow]No chunks found[/]")
                        
                        indexer._save_manifest()
                        embeddings.save_cache()
                    finally:
                        await llm.close()
                
                asyncio.run(do_index())
        
        elif args.rag_action == "query":
            async def do_query():
                llm = OllamaClient()
                try:
                    embeddings = EmbeddingProvider(llm)
                    store = CodeVectorStore()
                    retriever = CodeRetriever(embeddings, store)
                    
                    # Load keyword index
                    chunks_data = indexer._manifest
                    # For keyword search, we need to rebuild from manifest or use vector only
                    
                    results = await retriever.retrieve(args.query_text, k=args.k)
                    
                    if not results:
                        console.print("[dim]No results found[/]")
                    else:
                        for r in results:
                            console.print(
                                f"\n[bold cyan]{r.chunk.file_path}[/] :: "
                                f"[bold]{r.chunk.symbol_name or r.chunk.chunk_type}[/] "
                                f"(L{r.chunk.start_line}-{r.chunk.end_line}) "
                                f"[dim]score={r.final_score:.3f} {r.source}[/]"
                            )
                            # Show first few lines
                            preview = r.chunk.content[:300].splitlines()
                            for line in preview[:8]:
                                console.print(f"  {line}")
                            if len(r.chunk.content.splitlines()) > 8:
                                console.print(f"  [dim]... ({len(r.chunk.content.splitlines())} lines total)[/]")
                finally:
                    await llm.close()
            
            asyncio.run(do_query())
        
        elif args.rag_action == "reset":
            if not getattr(args, 'yes', False):
                confirm = input("Reset RAG index? [y/N] ").strip().lower()
                if confirm != "y":
                    console.print("[dim]Cancelled.[/]")
                    sys.exit(0)
            indexer._manifest = {}
            indexer._save_manifest()
            store = CodeVectorStore()
            store.reset()
            console.print("[bold green]RAG index reset.[/]")
        
        else:
            console.print("[dim]Use: rag index|query|reset[/]")
        
        sys.exit(0)

    if args.command == "memory":
        from zerion_core.memory.longterm import LongTermMemory
        from zerion_core.memory.longterm.context_builder import format_retrieval_results
        from zerion_core.llm.ollama import OllamaClient as MemOllamaClient
        
        async def do_memory():
            llm = MemOllamaClient()
            try:
                ltm = LongTermMemory(llm)
                
                if args.memory_action == "recall":
                    console.print(f"[bold]Recalling memories for:[/] {args.query_text}")
                    project = args.project if hasattr(args, 'project') and args.project else None
                    results = await ltm.recall(args.query_text, project_id=project, limit=args.k)
                    
                    if not results:
                        console.print("[dim]No relevant memories found.[/]")
                    else:
                        console.print(format_retrieval_results(results, max_results=args.k))
                
                elif args.memory_action == "stats":
                    stats = ltm.get_stats()
                    table = Table(title="Long-Term Memory Stats")
                    table.add_column("Metric")
                    table.add_column("Value")
                    table.add_row("Episodic Events", str(stats["episodic_events"]))
                    table.add_row("Semantic Vectors", str(stats["semantic_vectors"]))
                    table.add_row("Project Brains", str(stats["project_brains"]))
                    decay = stats["decay_stats"]
                    table.add_row("Core Memories", str(decay.get("core_memories", 0)))
                    table.add_row("High Importance", str(decay.get("high_importance", 0)))
                    table.add_row("Medium Importance", str(decay.get("medium_importance", 0)))
                    table.add_row("Low Importance", str(decay.get("low_importance", 0)))
                    console.print(table)
                
                elif args.memory_action == "decay":
                    console.print("[bold]Running importance decay...[/]")
                    stats = ltm.run_decay()
                    console.print(f"[green]Decayed:[/] {stats['decayed']} memories")
                    console.print(f"[green]Pruned:[/] {stats['pruned']} memories")
                    console.print(f"[green]Core protected:[/] {stats['core_protected']} memories")
                
                elif args.memory_action == "brain":
                    brain_text = ltm.get_project_brain(args.project_id)
                    if brain_text:
                        console.print(brain_text)
                    else:
                        console.print(f"[dim]No brain file for project: {args.project_id}[/]")
                
                elif args.memory_action == "search":
                    console.print(f"[bold]Searching memories from:[/] {args.time_text}")
                    project = args.project if hasattr(args, 'project') and args.project else None
                    events = await ltm.recall_by_time(args.time_text, project_id=project)
                    
                    if not events:
                        console.print("[dim]No memories found for that time range.[/]")
                    else:
                        for event in events[:15]:
                            type_label = event.event_type.replace("_", " ").title()
                            console.print(
                                f"  [{type_label}] (imp={event.importance:.2f}) "
                                f"{event.created_at[:10]} — {event.content[:100]}"
                            )
                
                else:
                    console.print("[dim]Use: memory recall|stats|decay|brain|search[/]")
            finally:
                await llm.close()
        
        asyncio.run(do_memory())
        sys.exit(0)

    if args.command == "skill":
        from zerion_core.skills.enhanced_manager import EnhancedSkillManager
        from zerion_core.skills.loader import SkillLoader
        from zerion_core.config import Settings
        
        async def do_skill():
            settings = Settings()
            loader = SkillLoader(settings.skills_dir)
            sm = EnhancedSkillManager(skills_dir=settings.skills_dir)
            await sm.load_all()
            
            try:
                if args.skill_action == "list":
                    skills = sm.list_installed()
                    active = [s.manifest.name for s in sm.list_active()]
                    disabled = sm.list_disabled()
                    available = sm.list_available()
                    
                    if skills:
                        table = Table(title="Installed Skills")
                        table.add_column("Status", justify="center")
                        table.add_column("Name", style="cyan")
                        table.add_column("Version", style="dim")
                        table.add_column("Tags", style="dim")
                        for skill in skills:
                            name = skill.manifest.name
                            status = "[green]ACTIVE[/]" if name in active else "[dim]installed[/]"
                            if name in disabled:
                                status = "[red]disabled[/]"
                            tags = ", ".join(skill.manifest.tags[:3])
                            table.add_row(status, name, skill.manifest.version, tags)
                        console.print(table)
                    
                    not_installed = [s for s in available if not s["installed"]]
                    if not_installed:
                        table = Table(title="Available Built-in Skills (not installed)")
                        table.add_column("Name", style="cyan")
                        table.add_column("Version", style="dim")
                        table.add_column("Description", style="dim")
                        table.add_column("Tags", style="dim")
                        for s in not_installed:
                            tags = ", ".join(s["tags"])
                            desc = s["description"][:60] if s["description"] else "-"
                            table.add_row(s["name"], s["version"], desc, tags)
                        console.print(table)
                    
                    if not skills and not not_installed:
                        console.print("[dim]No skills found.[/]")
                
                elif args.skill_action == "install":
                    ok, msg = await sm.install(args.source)
                    if ok:
                        console.print(f"[bold green]{msg}[/]")
                    else:
                        console.print(f"[bold red]{msg}[/]")
                        sys.exit(1)
                
                elif args.skill_action == "uninstall":
                    if not args.yes:
                        confirm = input(f"Uninstall skill '{args.name}'? [y/N] ").strip().lower()
                        if confirm != "y":
                            console.print("[dim]Cancelled.[/]")
                            sys.exit(0)
                    ok, msg = await sm.uninstall(args.name)
                    if ok:
                        console.print(f"[bold green]{msg}[/]")
                    else:
                        console.print(f"[bold red]{msg}[/]")
                        sys.exit(1)
                
                elif args.skill_action == "enable":
                    ok, msg = sm.enable(args.name)
                    if ok:
                        console.print(f"[bold green]{msg}[/]")
                    else:
                        console.print(f"[bold red]{msg}[/]")
                        sys.exit(1)
                
                elif args.skill_action == "disable":
                    ok, msg = sm.disable(args.name)
                    if ok:
                        console.print(f"[bold green]{msg}[/]")
                    else:
                        console.print(f"[bold red]{msg}[/]")
                        sys.exit(1)
                
                elif args.skill_action == "info":
                    info = sm.get_skill_info(args.name)
                    if not info:
                        console.print(f"[bold red]Skill not found: {args.name}[/]")
                        sys.exit(1)
                    
                    table = Table(title=f"Skill: {info['name']}")
                    table.add_column("Field")
                    table.add_column("Value")
                    table.add_row("Version", info["version"])
                    table.add_row("Description", info["description"])
                    table.add_row("Author", info["author"] or "-")
                    table.add_row("Tags", ", ".join(info["tags"]))
                    table.add_row("Status", info["status"])
                    table.add_row("Active", str(info["active"]))
                    table.add_row("Disabled", str(info["disabled"]))
                    table.add_row("Usage Count", str(info["usage_count"]))
                    table.add_row("Success Count", str(info["success_count"]))
                    table.add_row("Memory Entries", str(info["memory_entries"]))
                    table.add_row("Doc Chunks", str(info["doc_chunks"]))
                    table.add_row("Has Workflow", str(info["has_workflow"]))
                    table.add_row("Has RAG", str(info["has_rag"]))
                    console.print(table)
                
                elif args.skill_action == "search":
                    skills = sm.search_by_tags(args.tags)
                    if not skills:
                        console.print(f"[dim]No skills found for tags: {args.tags}[/]")
                    else:
                        console.print(f"[bold]Skills matching tags:[/]")
                        for skill in skills:
                            tags = ", ".join(skill.manifest.tags[:3])
                            console.print(f"  [cyan]{skill.manifest.name}[/] [dim]{tags}[/]")
                
                else:
                    console.print("[dim]Use: skill list|install|uninstall|enable|disable|info|search[/]")
            finally:
                sm.close()
        
        asyncio.run(do_skill())
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
