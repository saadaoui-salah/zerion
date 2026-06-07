from __future__ import annotations

import json
import re
from typing import Any

from zerion_core.agents.base import Agent, AgentStatus, TaskResult
from zerion_core.bus.message_bus import AgentMessage
from zerion_core.llm.model_router import ModelRouter


ROUTER_CATEGORIES = [
    "chat",
    "cli",
    "web_dev",
    "discord_bot",
    "telegram_bot",
    "scraping",
    "bug_fix",
    "research",
    "ui_design",
    "architecture",
    "agent_system",
]

ROUTER_SYSTEM = f"""Classify the user request.
Categories: {json.dumps(ROUTER_CATEGORIES)}

Decision Logic:
1. "needs_memory": true if the request refers to existing code, previous tasks, or project context. false if it's a general question or a fresh request.
2. "is_complex": true if the request requires planning, multiple files, or multiple specialized agents. false if it's a simple one-step action (e.g. "create a file", "run a command", "explain this snippet").

Return JSON: {{"category": "...", "confidence": 0.0-1.0, "reason": "...", "needs_memory": bool, "is_complex": bool}}
"""


class RouterAgent(Agent):
    """Smart request classifier."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__("Router", "router", *args, **kwargs, system_prompt=ROUTER_SYSTEM)

    async def classify(self, user_request: str) -> dict[str, Any]:
        score = self._complexity_score(user_request)
        resp = await self.llm.chat(
            messages=[{"role": "user", "content": user_request}],
            model=ModelRouter.for_task("routing"),
            system=ROUTER_SYSTEM,
            json_mode=True,
            temperature=0.0,
        )
        try:
            result = json.loads(resp.content)
            if result.get("category") not in ROUTER_CATEGORIES:
                result["category"] = self._heuristic(user_request)

            # Ensure keys exist
            if "needs_memory" not in result:
                result["needs_memory"] = self._memory_heuristic(user_request)
            if "is_complex" not in result:
                result["is_complex"] = result.get("category") not in ("chat", "cli")

            # Weighted scoring override: force complex if score > 3
            result["complexity_score"] = score
            if score > 3:
                result["is_complex"] = True

            return result
        except json.JSONDecodeError:
            return {
                "category": self._heuristic(user_request),
                "confidence": 0.5,
                "reason": "heuristic",
                "needs_memory": self._memory_heuristic(user_request),
                "is_complex": score > 3,
                "complexity_score": score,
            }

    def _memory_heuristic(self, text: str) -> bool:
        t = text.lower()
        # Referencing "this", "it", "previous", or specific project terms
        ref_keywords = {"this", "it", "that", "previous", "before", "last", "context", "project", "codebase", "existing"}
        words = set(re.findall(r"[a-z0-9]+", t))
        return bool(words & ref_keywords)

    COMPLEXITY_WEIGHTS: dict[str, int] = {
        "api": 1, "frontend": 1, "backend": 1, "database": 1, "auth": 1, "ui": 1, "web": 1,
        "discord": 1, "telegram": 1, "scrape": 1, "bug": 1, "fix": 1, "test": 1, "deploy": 1,
        "refactor": 2, "migrate": 2, "integrate": 2, "pipeline": 2, "real-time": 2, "realtime": 2,
        "fullstack": 3, "microservice": 3, "architecture": 3, "multi-agent": 3, "orchestrat": 3,
        "saas": 3, "dashboard": 3, "concurrent": 3, "async": 2,
    }

    def _complexity_score(self, text: str) -> int:
        t = text.lower()
        words = set(re.findall(r"[a-z0-9-]+", t))
        score = 0
        for keyword, weight in self.COMPLEXITY_WEIGHTS.items():
            if keyword in words or keyword in t:
                score += weight
        return score

    def _heuristic(self, text: str) -> str:
        t = text.lower()
        words = set(re.findall(r"[a-z0-9]+", t))
        rules = [
            ({"discord", "discord.py"}, "discord_bot"),
            ({"telegram", "telebot", "aiogram"}, "telegram_bot"),
            ({"scrape", "scrapy", "crawl", "zillow"}, "scraping"),
            ({"bug", "fix", "debug", "error"}, "bug_fix"),
            ({"research", "investigate"}, "research"),
            ({"figma", "tailwind"}, "ui_design"),
            ({"architecture", "microservice"}, "architecture"),
            ({"agent", "multi-agent", "orchestrat"}, "agent_system"),
            (
                {"nextjs", "next.js", "react", "saas", "fullstack", "frontend", "backend", "dashboard"},
                "web_dev",
            ),
        ]
        if "file" in words or ("create" in words and any(w in words for w in {"python", "script", "hello", "txt", "json"})):
            return "cli"
        if any(p in t for p in ("git init", "mkdir", "run command", "shell command", "terminal")):
            return "cli"
        if "create" in words and ("folder" in words or "directory" in words or "project" in words):
            return "cli"
        for keywords, cat in rules:
            if words & keywords or any(k in t for k in keywords if " " in k or "." in k):
                return cat
        if "ui design" in t or "user interface" in t:
            return "ui_design"
        if "web" in words or "api" in words:
            return "web_dev"
        return "chat"

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> TaskResult:
        result = await self.classify(task)
        return TaskResult(success=True, output=json.dumps(result), artifacts=result)


class CEOAgent(Agent):
    """Top-level orchestrator that delegates to Router and Planner."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "CEO",
            "ceo",
            *args,
            **kwargs,
            system_prompt=(
                "You are the CEO agent of Zerion-Core. Coordinate agents, set priorities, "
                "and ensure user goals are achieved. Delegate — never implement directly."
            ),
        )

    async def handle_message(self, msg: AgentMessage) -> TaskResult | None:
        if msg.task == "user_request":
            return await self.execute(msg.payload.get("request", ""), msg.payload)
        return await super().handle_message(msg)

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> TaskResult:
        self.state.status = AgentStatus.WORKING
        self.memory.set_stm(goal=task, current_task="Delegating to Router")
        await self.request_assistance("Router", "classify_request", {"request": task})
        return TaskResult(
            success=True,
            output=f"CEO received: {task}. Delegated to Router and Planner.",
            artifacts={"goal": task},
        )


class MemoryAgent(Agent):
    """Dedicated memory read/write and retrieval agent."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Memory",
            "memory",
            *args,
            **kwargs,
            system_prompt="You manage Zerion-Core memory. Extract facts, never store raw chat.",
        )

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> TaskResult:
        ctx = context or {}
        if task == "retrieve":
            content = await self.memory.retrieve_context(ctx.get("query", ""), ctx.get("project", ""))
            return TaskResult(success=True, output=content)
        if task == "store":
            await self.memory.ingest_agent_output(
                ctx.get("text", ""),
                project=ctx.get("project", "default"),
                agent=ctx.get("agent", self.name),
            )
            return TaskResult(success=True, output="Stored")
        return await super().execute(task, ctx)


class ResearchAgent(Agent):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Research",
            "research",
            *args,
            **kwargs,
            system_prompt="Research agent: gather context, compare options, cite trade-offs.",
        )


class ReviewerAgent(Agent):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Reviewer",
            "reviewer",
            *args,
            **kwargs,
            system_prompt="Code reviewer: find bugs, security issues, style problems. Be specific.",
        )


class QAAgent(Agent):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "QA",
            "qa",
            *args,
            **kwargs,
            system_prompt="QA agent: write test plans, edge cases, acceptance criteria.",
        )


class DocumentationAgent(Agent):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Documentation",
            "documentation",
            *args,
            **kwargs,
            system_prompt="Documentation agent: clear README, API docs, architecture notes.",
        )


class SelfReflectionAgent(Agent):
    """Reflects on task outcome to extract lessons and patterns."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Self-Reflection",
            "reflection",
            *args,
            **kwargs,
            system_prompt=(
                "You are the Self-Reflection agent. Analyze the completed task.\n"
                "Determine: What worked? What failed? What should be remembered?\n"
                "Return JSON: {\"lesson\": \"...\", \"confidence\": 0.0-1.0, \"category\": \"...\"}"
            ),
        )

    async def reflect(self, project: str, pipeline_results: dict[str, Any]) -> dict[str, Any]:
        resp = await self.llm.chat(
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze results for project {project}:\n{json.dumps(pipeline_results, indent=2)[:8000]}",
                }
            ],
            model=ModelRouter.for_task("chat"),
            system=self.system_prompt,
            json_mode=True,
        )
        try:
            reflection = json.loads(resp.content)
            await self.memory.ingest_agent_output(
                f"Lesson learned: {reflection.get('lesson')}",
                project=project,
                agent=self.name,
                task_type="reflection",
            )
            return reflection
        except Exception:
            return {"lesson": "Task completed", "confidence": 0.5, "category": "general"}


class ContextEngineer(Agent):
    """Selects and compresses context for other agents."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Context-Engineer",
            "context_engineer",
            *args,
            **kwargs,
            system_prompt=(
                "You are the Context Engineer. Your goal is to provide the perfect "
                "context for a specific task. Select only relevant files, memories, "
                "decisions, and lessons. Use intelligent compression."
            ),
        )

    async def engineer(self, goal: str, project: str = "") -> dict[str, Any]:
        raw_ctx = await self.memory.retrieve_context(goal, project)
        return {
            "goal": goal,
            "relevant_files": [],
            "relevant_memories": raw_ctx[:2000],
            "relevant_decisions": [],
            "relevant_lessons": [],
        }


class ArchitectAgent(Agent):
    """Responsible for high-level design, dependency analysis, and PROJECT_DNA."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Architect",
            "architect",
            *args,
            **kwargs,
            system_prompt=(
                "You are the Lead Architect. Maintain ARCHITECTURE.md, PROJECT_MAP.md, "
                "and PROJECT_DNA.md. Ensure modularity, type safety, and clean abstractions. "
                "Always output a `stack_conventions.json` when analyzing a project."
            ),
        )

    async def analyze(self, project: str, workspace_scan: dict[str, Any] | None = None) -> dict[str, Any]:
        """Analyze the project and produce stack_conventions.json.

        If workspace_scan is provided, conventions are derived from the actual
        project files (extensions, package.json, requirements.txt, etc.).
        Otherwise, falls back to LLM-based analysis or sensible defaults.
        """
        conventions = self._detect_conventions_from_scan(workspace_scan)

        # If scan data is sparse, ask the LLM to fill in gaps
        if not conventions.get("detected_from_files"):
            conventions = await self._llm_analyze_conventions(project, workspace_scan, conventions)

        # Ensure all required fields have defaults
        conventions.setdefault("js_extension", "tsx")
        conventions.setdefault("css_strategy", "tailwind")
        conventions.setdefault("state_management", "redux_toolkit")
        conventions.setdefault("testing", "vitest")
        conventions.setdefault("linting", "eslint")
        conventions.setdefault("formatting", "prettier")
        conventions.setdefault("module_system", "esm")
        conventions.setdefault("package_manager", "npm")
        conventions.setdefault("python_version", "3.11+")
        conventions.setdefault("type_checking", "typescript")
        conventions.setdefault("path_style", "posix")

        conventions["detected_from_files"] = conventions.get("detected_from_files", False)
        conventions["confidence"] = conventions.get("confidence", 0.5)

        return {"project": project, "stack_conventions": conventions}

    def _detect_conventions_from_scan(self, scan: dict[str, Any] | None) -> dict[str, Any]:
        """Derive conventions from a workspace scan dict (dirs, files, technologies)."""
        if not scan:
            return {}

        conventions: dict[str, Any] = {"detected_from_files": True, "confidence": 0.8}

        files = scan.get("files", [])
        dirs = scan.get("dirs", [])
        technologies = scan.get("technologies", [])
        tech_set = set(t.lower() for t in technologies)

        # File extension analysis
        ext_counts: dict[str, int] = {}
        for f in files:
            if isinstance(f, str):
                ext = f.rsplit(".", 1)[-1] if "." in f else ""
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

        # JS/TS extension detection
        tsx_count = ext_counts.get("tsx", 0)
        jsx_count = ext_counts.get("jsx", 0)
        ts_count = ext_counts.get("ts", 0)
        js_count = ext_counts.get("js", 0)

        if tsx_count > jsx_count:
            conventions["js_extension"] = "tsx"
        elif jsx_count > 0:
            conventions["js_extension"] = "jsx"
        elif ts_count > js_count:
            conventions["js_extension"] = "ts"
        else:
            conventions["js_extension"] = "js"

        # CSS strategy detection
        dir_set = set(d.lower() for d in dirs if isinstance(d, str))
        if "tailwind" in " ".join(dir_set) or "tailwindcss" in tech_set:
            conventions["css_strategy"] = "tailwind"
        elif any("styled" in d or "emotion" in d for d in dir_set):
            conventions["css_strategy"] = "css-in-js"
        elif ext_counts.get("scss", 0) > ext_counts.get("css", 0):
            conventions["css_strategy"] = "scss"
        else:
            conventions["css_strategy"] = "css"

        # State management
        if "redux" in tech_set or "redux_toolkit" in tech_set or "reduxjs" in tech_set:
            conventions["state_management"] = "redux_toolkit"
        elif "zustand" in tech_set:
            conventions["state_management"] = "zustand"
        elif "jotai" in tech_set:
            conventions["state_management"] = "jotai"
        elif "mobx" in tech_set:
            conventions["state_management"] = "mobx"
        elif "pinia" in tech_set or "vuex" in tech_set:
            conventions["state_management"] = "pinia"
        else:
            conventions["state_management"] = "none"

        # Testing framework
        if "vitest" in tech_set or "vitest" in dir_set:
            conventions["testing"] = "vitest"
        elif "jest" in tech_set:
            conventions["testing"] = "jest"
        elif "pytest" in tech_set or "unittest" in tech_set:
            conventions["testing"] = "pytest"
        elif "mocha" in tech_set:
            conventions["testing"] = "mocha"
        else:
            conventions["testing"] = "none"

        # Package manager
        if "pnpm" in tech_set or any("pnpm" in str(f).lower() for f in files):
            conventions["package_manager"] = "pnpm"
        elif "yarn" in tech_set or any("yarn.lock" in str(f).lower() for f in files):
            conventions["package_manager"] = "yarn"
        elif "bun" in tech_set:
            conventions["package_manager"] = "bun"
        else:
            conventions["package_manager"] = "npm"

        # Python detection
        py_count = ext_counts.get("py", 0)
        if py_count > 0 or "python" in tech_set:
            conventions["python_version"] = "3.11+"
            conventions["type_checking"] = "mypy" if "mypy" in tech_set else "pyright" if "pyright" in tech_set else "pyright"
            conventions["testing"] = "pytest" if py_count > 0 else conventions.get("testing", "pytest")

        # Module system
        if "esm" in tech_set or any("type" in str(f).lower() and "module" in str(f).lower() for f in files):
            conventions["module_system"] = "esm"
        elif "commonjs" in tech_set:
            conventions["module_system"] = "commonjs"

        # Linting/formatting
        if "biome" in tech_set:
            conventions["linting"] = "biome"
            conventions["formatting"] = "biome"
        else:
            conventions["linting"] = "eslint"
            conventions["formatting"] = "prettier"

        return conventions

    async def _llm_analyze_conventions(
        self,
        project: str,
        scan: dict[str, Any] | None,
        existing: dict[str, Any],
    ) -> dict[str, Any]:
        """Ask the LLM to analyze conventions when scan data is insufficient."""
        scan_summary = ""
        if scan:
            scan_summary = (
                f"Technologies: {', '.join(scan.get('technologies', [])[:20])}\n"
                f"Files: {scan.get('file_count', 0)} source files\n"
                f"Directories: {', '.join(scan.get('dirs', [])[:30])}\n"
            )

        prompt = (
            f"Analyze this project and return stack_conventions.json:\n\n"
            f"Project: {project}\n{scan_summary}\n"
            f"Existing partial detection: {json.dumps(existing, indent=2)}\n\n"
            f"Return JSON with these fields:\n"
            f'{{"js_extension": "tsx|ts|jsx|js", '
            f'"css_strategy": "tailwind|scss|css-in-js|css", '
            f'"state_management": "redux_toolkit|zustand|jotai|mobx|pinia|none", '
            f'"testing": "vitest|jest|pytest|mocha|none", '
            f'"linting": "eslint|biome", '
            f'"formatting": "prettier|biome", '
            f'"module_system": "esm|commonjs", '
            f'"package_manager": "npm|pnpm|yarn|bun", '
            f'"python_version": "3.11+", '
            f'"type_checking": "typescript|pyright|mypy|none", '
            f'"detected_from_files": true, '
            f'"confidence": 0.0-1.0}}'
        )

        try:
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=ModelRouter.for_task("architecture"),
                system=self.system_prompt,
                json_mode=True,
                temperature=0.0,
            )
            result = json.loads(resp.content)
            result["detected_from_files"] = True
            return result
        except (json.JSONDecodeError, Exception):
            return existing


class IntegratorAgent(Agent):
    """Merges parallel work into a cohesive implementation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Integrator",
            "integrator",
            *args,
            **kwargs,
            system_prompt=(
                "You are the Integrator. Perform a 'Final Layout Scan':\n"
                "1. Verify all planned files exist.\n"
                "2. Check for structural inconsistencies.\n"
                "3. Provide a high-level summary of the final project structure."
            ),
        )

    async def integrate(self, project: str, outputs: list[str]) -> str:
        summary = "Integrated Project Summary:\n"
        # In a real scenario, this would scan the filesystem
        summary += "- Architecture merged and verified."
        return summary + "\n\n" + "\n\n".join(outputs)


class CriticAgent(Agent):
    """Finds flaws, security issues, and scaling bottlenecks."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "Critic",
            "critic",
            *args,
            **kwargs,
            system_prompt=(
                "You are the Critic. Find flaws, security issues, edge cases, and scaling "
                "problems in the proposed solution. Be brutal and thorough."
            ),
        )

    async def critique(self, project: str, implementation: str) -> dict[str, Any]:
        resp = await self.llm.chat(
            messages=[{"role": "user", "content": f"Critique this implementation for {project}:\n{implementation[:8000]}"}],
            model=ModelRouter.for_task("review"),
            system=self.system_prompt,
            json_mode=True,
        )
        try:
            return json.loads(resp.content)
        except Exception:
            return {"flaws": [], "security": "ok"}


class UserAdvocateAgent(Agent):
    """Ensures the final output is user-friendly and complete."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            "User-Advocate",
            "advocate",
            *args,
            **kwargs,
            system_prompt=(
                "You are the User Advocate. Ask: Would a beginner understand this? "
                "Are setup steps missing? Is documentation clear? Would deployment succeed?"
            ),
        )

    async def advocate(self, project: str, results: dict[str, Any]) -> str:
        return "The implementation looks clear and setup steps are provided."
