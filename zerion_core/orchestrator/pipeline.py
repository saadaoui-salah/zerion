from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from zerion_core.agents.base import Agent, AgentStatus, TaskResult
from zerion_core.agents.cli_agent import CLIAgent, task_needs_cli
from zerion_core.agents.core_agents import (
    ArchitectAgent,
    CEOAgent,
    ContextEngineer,
    CriticAgent,
    DocumentationAgent,
    IntegratorAgent,
    MemoryAgent,
    QAAgent,
    ResearchAgent,
    ReviewerAgent,
    RouterAgent,
    SelfReflectionAgent,
    UserAdvocateAgent,
)
from zerion_core.agents.planner import DynamicTeamFactory, PlannerAgent
from zerion_core.bus.message_bus import MessageBus, MessagePriority
from zerion_core.llm.ollama import OllamaClient
from zerion_core.memory.manager import MemoryManager
from zerion_core.repo_intel.generator import RepositoryIntelligence
from zerion_core.session import SessionManager, SessionMeta


class UserAgent(Agent):
    """Bridge between agents and the TUI for user interaction."""

    def __init__(self, *args: Any, on_input_request: Callable[[str, str, str], None] | None = None, **kwargs: Any) -> None:
        super().__init__("User", "user", *args, **kwargs)
        self.on_input_request = on_input_request or (lambda _a, _q, _id: None)
        self._pending: dict[str, asyncio.Future[str]] = {}

    async def handle_message(self, msg: AgentMessage) -> TaskResult | None:
        if msg.task == "ask":
            question = msg.payload.get("question", "No question provided.")
            future: asyncio.Future[str] = asyncio.Future()
            self._pending[msg.id] = future
            self.on_input_request(msg.from_agent, question, msg.id)
            try:
                answer = await future
                return TaskResult(success=True, output=answer)
            finally:
                self._pending.pop(msg.id, None)
        return await super().handle_message(msg)

    def resolve_request(self, message_id: str, answer: str) -> None:
        if message_id in self._pending:
            self._pending[message_id].set_result(answer)


@dataclass
class PipelineEvent:
    stage: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


EventCallback = Callable[[PipelineEvent], None]


class Orchestrator:
    """Full coding workflow: Router → Planner → Team → Review → QA → Docs → Memory."""

    def __init__(
        self,
        llm: OllamaClient | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self.llm = llm or OllamaClient()
        self.memory = MemoryManager(self.llm)
        self.bus = MessageBus()
        self.on_event = on_event or (lambda e: None)
        self.sessions = SessionManager()
        self._active_session_id: str | None = None
        self._conversation: list[dict[str, str]] = []

        self.ceo = CEOAgent(self.llm, self.memory, self.bus)
        self.router = RouterAgent(self.llm, self.memory, self.bus)
        self.memory_agent = MemoryAgent(self.llm, self.memory, self.bus)
        self.research = ResearchAgent(self.llm, self.memory, self.bus)
        self.planner = PlannerAgent(self.llm, self.memory, self.bus)
        self.context_engineer = ContextEngineer(self.llm, self.memory, self.bus)
        self.architect = ArchitectAgent(self.llm, self.memory, self.bus)
        self.cli = CLIAgent(self.llm, self.memory, self.bus, on_cli_event=self._on_cli_event)
        self.critic = CriticAgent(self.llm, self.memory, self.bus)
        self.integrator = IntegratorAgent(self.llm, self.memory, self.bus)
        self.reviewer = ReviewerAgent(self.llm, self.memory, self.bus)
        self.qa = QAAgent(self.llm, self.memory, self.bus)
        self.documentation = DocumentationAgent(self.llm, self.memory, self.bus)
        self.reflection = SelfReflectionAgent(self.llm, self.memory, self.bus)
        self.advocate = UserAdvocateAgent(self.llm, self.memory, self.bus)
        self.user_proxy = UserAgent(self.llm, self.memory, self.bus, on_input_request=self._on_user_input_request)
        self.team_factory = DynamicTeamFactory(self.planner)
        self.repo_intel = RepositoryIntelligence(self.memory, self.llm)

        self.core_agents: list[Agent] = [
            self.ceo,
            self.router,
            self.memory_agent,
            self.research,
            self.planner,
            self.context_engineer,
            self.architect,
            self.cli,
            self.critic,
            self.integrator,
            self.reviewer,
            self.qa,
            self.documentation,
            self.user_proxy,
        ]
        self.dynamic_team: list[Agent] = []
        self._bus_task: asyncio.Task | None = None

    def all_agents(self) -> list[Agent]:
        return self.core_agents + self.dynamic_team

    async def start(self) -> None:
        self._bus_task = asyncio.create_task(self.bus.start())

    async def stop(self) -> None:
        self.bus.stop()
        if self._bus_task:
            self._bus_task.cancel()
            try:
                await self._bus_task
            except asyncio.CancelledError:
                pass
        await self.llm.close()
        self.memory.close()

    # --- Session Management ---

    def save_session(self, name: str = "", description: str = "", tags: list[str] | None = None) -> SessionMeta:
        """Save the current memory state as a named session."""
        meta = self.sessions.save(
            memory=self.memory,
            name=name,
            description=description,
            tags=tags,
            conversation=self._conversation,
            session_id=self._active_session_id,
        )
        self._active_session_id = meta.id
        self._emit("session", f"Session saved: {meta.name} ({meta.id})")
        return meta

    def load_session(self, session_id: str) -> bool:
        """Restore a session's memory state."""
        ok = self.sessions.restore(session_id, self.memory)
        if ok:
            self._active_session_id = session_id
            self._conversation = self.sessions.get_conversation(session_id)
            self._emit("session", f"Session loaded: {session_id}")
        return ok

    def list_sessions(self) -> list[SessionMeta]:
        """List all saved sessions."""
        return self.sessions.list_sessions()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        ok = self.sessions.delete(session_id)
        if ok and self._active_session_id == session_id:
            self._active_session_id = None
            self._conversation = []
        return ok

    def new_session(self) -> None:
        """Start a fresh session (clear active session tracking)."""
        self._active_session_id = None
        self._conversation = []

    def get_active_session_id(self) -> str | None:
        return self._active_session_id

    def _emit(self, stage: str, message: str, **data: Any) -> None:
        self.on_event(PipelineEvent(stage=stage, message=message, data=data))

    def _on_cli_event(self, event_type: str, data: dict[str, Any]) -> None:
        payload = dict(data)
        message = str(payload.pop("message", ""))
        self._emit(event_type, message, **payload)

    def _on_user_input_request(self, agent_name: str, question: str, message_id: str) -> None:
        self._emit("user_input_request", question, agent=agent_name, message_id=message_id)

    def log_agent(self, message: str) -> None:
        self._emit("agent_log", message)

    async def run(self, user_request: str) -> dict[str, Any]:
        results: dict[str, Any] = {"request": user_request, "stages": []}

        # Track conversation
        self._conversation.append({"role": "user", "content": user_request})

        self.memory.refresh_project_structure()
        
        # 1. Router (Classify + Complexity + Memory Check)
        self._emit("router", "Analyzing request and determining workflow...")
        classification = await self.router.classify(user_request)
        category = classification.get("category", "chat")
        needs_memory = classification.get("needs_memory", False)
        is_complex = classification.get("is_complex", True)
        complexity_score = classification.get("complexity_score", 0)
        
        results["category"] = category
        results["needs_memory"] = needs_memory
        results["is_complex"] = is_complex
        results["complexity_score"] = complexity_score

        # Smart Memory: Multi-Project Detection
        self._emit("memory", "Detecting project context...")
        project_info = await self.memory.detect_project(user_request)
        results["project_detection"] = {
            "project_name": project_info.get("project_name", ""),
            "status": project_info.get("status", "none"),
            "confidence": project_info.get("confidence", 0.0),
        }
        project_name = project_info.get("project_name", "")
        is_new = project_info.get("is_new", False)
        if project_name:
            self._emit(
                "memory",
                f"{'New' if is_new else 'Existing'} project detected: {project_name} "
                f"(confidence={project_info.get('confidence', 0):.2f})",
            )
            # set in working memory for current session
            self.memory.working.set("current_project", project_name)
            self.memory.working.set("project_status", "new" if is_new else "existing")

        # Smart Memory: Only inject if needed
        context_data = {}
        if needs_memory:
            self._emit("memory", "Injecting relevant project context...")
            ctx_obj = await self.context_engineer.engineer(user_request, project_name or "project")
            context_data["engineered_context"] = ctx_obj
            if project_name:
                context_data["project"] = project_name
        else:
            self._emit("memory", "Skipping memory (independent request)")
            if project_name:
                context_data["project"] = project_name

        # === FastTrack: Simple tasks (score <= 1, is_complex=False) ===
        if not is_complex:
            self._emit("implement", f"Executing simple {category} task...")
            if category == "chat":
                return await self._run_chat(user_request, context_data)
            
            agent = self.cli if category == "cli" else self._pick_agent({"title": user_request}, category)
            res = await agent.execute(user_request, context_data)
            
            self._emit("complete", "Simple task completed")
            results["output"] = res.output
            self._conversation.append({"role": "assistant", "content": res.output[:2000]})
            return results

        # === LightPipeline: Moderate tasks (score 2-3) ===
        if complexity_score <= 3:
            self._emit("planner", "Moderate task. Spawning light pipeline...")
            
            plan_result = await self.planner.execute("create_light_plan", {"goal": user_request, "category": category})
            plan = plan_result.artifacts
            project = plan.get("project_name", "project")
            results["plan"] = plan

            # Execute tasks sequentially with existing core agents (no dynamic team)
            self._emit("implement", "Executing light pipeline tasks...")
            task_results = []
            for task in plan.get("tasks", []):
                agent = self.cli if category == "cli" else self._pick_agent(task, category)
                task_ctx = {"project": project, "task_type": category}
                task_ctx.update(context_data)
                res = await agent.execute(task.get("title", ""), task_ctx)
                task_results.append(res.output)
            
            results["implementation"] = task_results

            # Review + QA only (skip Docs/Reflection for moderate tasks)
            self._emit("review", "Review and QA...")
            integrated = "\n\n".join(task_results)
            await asyncio.gather(
                self.reviewer.execute("Review", {"project": project, "code": integrated}),
                self.qa.execute("Test", {"project": project, "code": integrated}),
            )

            self._emit("complete", "Light pipeline completed")
            results["output"] = integrated
            self._conversation.append({"role": "assistant", "content": integrated[:2000]})
            return results

        # === FullPipeline: Complex tasks (score > 3) ===
        self._emit("planner", "Task identified as complex. Spawning full pipeline...")
        
        # 2. Research (Optional if memory provided enough context)
        research_context = ""
        if needs_memory:
             self._emit("research", "Performing deep repository research...")
             r_res = await self.research.execute(f"Research requirements for: {user_request}")
             research_context = r_res.output
        results["research"] = research_context

        # 3. Architecture
        self._emit("architect", "Defining architecture...")
        arch = await self.architect.analyze("project")
        results["architecture"] = arch
        
        # Inject conventions into context
        context_data["stack_conventions"] = arch.get("stack_conventions", {})

        # 4. Planner
        self._emit("planner", "Creating parallel execution plan...")
        plan_result = await self.planner.execute("create_plan", {"goal": user_request, "category": category})
        plan = plan_result.artifacts
        project = plan.get("project_name", "project")
        results["plan"] = plan

        # 5. Team spawning
        self.dynamic_team = self.team_factory.spawn_team(plan, logger_callback=self.log_agent)
        self._emit("team", f"Spawned {len(self.dynamic_team)} specialists")

        # 6. Parallel Implementation
        self._emit("implement", "Starting parallel execution...")
        tasks = []
        for task in plan.get("tasks", []):
            assignee = self._pick_agent(task, category)
            task_ctx = {"project": project, "task_type": category}
            task_ctx.update(context_data)
            tasks.append(self._run_parallel_task(assignee, task, project, category, task_ctx))
        
        implementation_results = await asyncio.gather(*tasks)
        results["implementation"] = [r.output for r in implementation_results]

        # 7. Integration
        self._emit("integrator", "Merging work streams...")
        integrated = await self.integrator.integrate(project, results["implementation"])
        results["integrated_code"] = integrated

        # 8-11. Review, QA, Docs, Advocate
        self._emit("review", "Final verification and auditing...")
        await asyncio.gather(
            self.reviewer.execute("Review", {"project": project, "code": integrated}),
            self.qa.execute("Test", {"project": project, "code": integrated}),
            self.documentation.execute("Document", {"project": project}),
            self.advocate.advocate(project, results)
        )

        # 12. Reflection
        self._emit("reflection", "Learning from this task...")
        await self.reflection.reflect(project, results)

        self._emit("complete", "Complex workflow successful")
        results["output"] = integrated
        self._conversation.append({"role": "assistant", "content": integrated[:2000]})
        return results

    async def _run_parallel_task(self, agent: Agent, task: dict[str, Any], project: str, category: str, ctx: dict[str, Any]) -> TaskResult:
        task_title = task.get("title", "")
        self._emit("agent_work", f"{agent.name} working on {task_title}", agent=agent.name)
        return await agent.execute(task_title, ctx)

    async def _run_chat(self, user_request: str, context: dict[str, Any]) -> dict[str, Any]:
        from zerion_core.llm.model_router import ModelRouter
        
        prompt = user_request
        if "engineered_context" in context:
            prompt = f"Context:\n{json.dumps(context['engineered_context'], indent=2)}\n\nUser Request: {user_request}"
            
        resp = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=ModelRouter.for_task("chat"),
        )
        self._conversation.append({"role": "assistant", "content": resp.content[:2000]})
        return {"output": resp.content, "request": user_request, "category": "chat"}

    def _pick_agent(self, task: dict[str, Any], category: str) -> Agent:
        if category == "cli" or task_needs_cli(task):
            return self.cli

        title = (task.get("title", "") + task.get("description", "")).lower()
        for agent in self.dynamic_team:
            if agent.role == "cli":
                return agent
        for agent in self.dynamic_team:
            role = agent.role.lower()
            if role in title or role.replace("_", " ") in title:
                return agent
        role_map = {
            "web_dev": "frontend",
            "discord_bot": "discord",
            "telegram_bot": "telegram",
            "scraping": "scraping",
        }
        preferred = role_map.get(category, "backend")
        for agent in self.dynamic_team:
            if agent.role == preferred:
                return agent
        if task_needs_cli(task):
            return self.cli
        return self.dynamic_team[0] if self.dynamic_team else self.cli
