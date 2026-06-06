from __future__ import annotations

import json
from typing import Any

from zerion_core.agents.base import Agent, TaskResult
from zerion_core.config import settings
from zerion_core.llm.model_router import ModelRouter

PLANNER_SYSTEM = """You are the Planner agent. Break user goals into tasks and define a dynamic team.
Return JSON:
{
  "project_name": "snake_case",
  "summary": "...",
  "tasks": [{"id": "t1", "title": "...", "description": "...", "depends_on": []}],
  "team": [{"name": "...", "role": "...", "responsibility": "..."}]
}
Never use fixed teams — create roles based on the specific goal.
Include Reviewer and QA in every team.
"""

TEAM_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "web_dev": [
        {"name": "Frontend", "role": "frontend", "responsibility": "React/NextJS UI components"},
        {"name": "Backend", "role": "backend", "responsibility": "FastAPI business logic"},
        {"name": "Database", "role": "database", "responsibility": "SQLAlchemy schema"},
        {"name": "Auth", "role": "auth", "responsibility": "Security and JWT"},
    ],
    "discord_bot": [
        {"name": "Discord", "role": "discord", "responsibility": "Bot commands"},
        {"name": "Database", "role": "database", "responsibility": "Persistence"},
    ],
    "telegram_bot": [
        {"name": "Telegram", "role": "telegram", "responsibility": "Handlers"},
        {"name": "Database", "role": "database", "responsibility": "Storage"},
    ],
    "scraping": [
        {"name": "Scraper", "role": "scraping", "responsibility": "Scrapy Spiders"},
        {"name": "Database", "role": "database", "responsibility": "Export"},
    ],
    "devops": [
        {"name": "DevOps", "role": "deployment", "responsibility": "Docker/CI-CD"},
    ],
    "security": [
        {"name": "Security", "role": "security", "responsibility": "Audit and Hardening"},
    ],
}


LIGHT_PLANNER_SYSTEM = """You are the Light Planner agent. Break a moderately complex goal into 2-4 focused tasks.
Do NOT define a dynamic team — the existing core agents will handle execution.
Return JSON:
{
  "project_name": "snake_case",
  "summary": "...",
  "tasks": [{"id": "t1", "title": "...", "description": "...", "depends_on": []}]
}
Keep the plan lightweight: no team definition, no parallel specialist spawning.
"""


class PlannerAgent(Agent):
    """Creates task breakdowns and dynamic teams."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__("Planner", "planner", *args, **kwargs, system_prompt=PLANNER_SYSTEM)
        self._update_system_prompt_with_skills()

    def _update_system_prompt_with_skills(self) -> None:
        """Inject available custom skills into the system prompt."""
        from zerion_core.tools.skill_creator import list_custom_skills
        custom = list_custom_skills()
        if custom:
            skills_list = "\n".join([f"- {role}" for role in custom.keys()])
            self.system_prompt += f"\n\nAvailable custom specialist roles:\n{skills_list}"

    async def plan(self, goal: str, category: str) -> dict[str, Any]:
        memory_ctx = await self.memory.retrieve_context(goal)
        resp = await self.llm.chat(
            messages=[
                {
                    "role": "user",
                    "content": f"Goal: {goal}\nCategory: {category}\n\n{memory_ctx}",
                }
            ],
            model=ModelRouter.for_task("planning"),
            system=PLANNER_SYSTEM,
            json_mode=True,
        )
        try:
            plan = json.loads(resp.content)
        except json.JSONDecodeError:
            plan = self._fallback_plan(goal, category)

        if not plan.get("team"):
            plan["team"] = self._default_team(category)
        existing = {m["name"] for m in plan.get("team", [])}
        for member in (
            {"name": "Reviewer", "role": "reviewer", "responsibility": "Code review"},
            {"name": "QA", "role": "qa", "responsibility": "Testing"},
        ):
            if member["name"] not in existing:
                plan["team"].append(member)
                existing.add(member["name"])
        return plan

    async def light_plan(self, goal: str, category: str) -> dict[str, Any]:
        memory_ctx = await self.memory.retrieve_context(goal, depth="shallow")
        resp = await self.llm.chat(
            messages=[
                {
                    "role": "user",
                    "content": f"Goal: {goal}\nCategory: {category}\n\n{memory_ctx}",
                }
            ],
            model=ModelRouter.for_task("planning"),
            system=LIGHT_PLANNER_SYSTEM,
            json_mode=True,
        )
        try:
            plan = json.loads(resp.content)
        except json.JSONDecodeError:
            plan = self._fallback_plan(goal, category)
        return plan

    def _default_team(self, category: str) -> list[dict[str, str]]:
        return TEAM_TEMPLATES.get(category, [
            {"name": "Implementer", "role": "backend", "responsibility": "Core implementation"},
        ])

    def _fallback_plan(self, goal: str, category: str) -> dict[str, Any]:
        slug = goal.lower().replace(" ", "_")[:30]
        return {
            "project_name": slug,
            "summary": goal,
            "tasks": [
                {"id": "t1", "title": "Analyze requirements", "description": goal, "depends_on": []},
                {"id": "t2", "title": "Implement solution", "description": goal, "depends_on": ["t1"]},
                {"id": "t3", "title": "Review and test", "description": "Review and QA", "depends_on": ["t2"]},
            ],
            "team": self._default_team(category),
        }

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> TaskResult:
        ctx = context or {}
        if task == "create_plan":
            plan = await self.plan(ctx.get("goal", ""), ctx.get("category", "web_dev"))
            self.memory.set_stm(
                goal=ctx.get("goal", ""),
                current_task="Planning complete",
                context=json.dumps(plan.get("summary", "")),
            )
            return TaskResult(success=True, output=json.dumps(plan, indent=2), artifacts=plan)
        if task == "create_light_plan":
            plan = await self.light_plan(ctx.get("goal", ""), ctx.get("category", "web_dev"))
            self.memory.set_stm(
                goal=ctx.get("goal", ""),
                current_task="Light planning complete",
                context=json.dumps(plan.get("summary", "")),
            )
            return TaskResult(success=True, output=json.dumps(plan, indent=2), artifacts=plan)
        return await super().execute(task, ctx)


class DynamicTeamFactory:
    """Instantiate planner-defined teams as live agents."""

    ROLE_PROMPTS: dict[str, str] = {
        "frontend": "Expert in React, Next.js, TypeScript, Tailwind. Build polished UIs.",
        "backend": "Expert in FastAPI, Node, Python. Build robust APIs.",
        "database": "Expert in PostgreSQL, SQLite, migrations, ORM design.",
        "auth": "Expert in JWT, OAuth, session management, security best practices.",
        "discord": "Expert in discord.py, cogs, slash commands, moderation bots.",
        "telegram": "Expert in python-telegram-bot, aiogram, inline keyboards.",
        "scraping": "Expert in Scrapy, selectors, pipelines, rate limiting.",
        "deployment": "Expert in Docker, CI/CD, cloud deployment.",
        "reviewer": "Thorough code reviewer focusing on correctness and security.",
        "qa": "QA engineer writing test plans and edge case analysis.",
        "cli": "Execute shell commands, create files, run git/npm/pip in the workspace.",
    }
    
    ROLE_MODELS: dict[str, str] = {}

    def __init__(self, planner: PlannerAgent) -> None:
        self.planner = planner
        self._load_custom_skills()

    def _load_custom_skills(self) -> None:
        """Merge custom skills from the skills directory into ROLE_PROMPTS and ROLE_MODELS."""
        if not settings.skills_dir.exists():
            return

        for path in settings.skills_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    role = data.get("role")
                    prompt = data.get("system_prompt")
                    model = data.get("registered_model") or data.get("model")
                    if role and prompt:
                        self.ROLE_PROMPTS[role] = prompt
                        if model:
                            self.ROLE_MODELS[role] = model
            except Exception:
                continue

    def spawn_team(self, plan: dict[str, Any], logger_callback: Callable[[str], None] | None = None) -> list[Agent]:
        agents: list[Agent] = []
        seen: set[str] = set()
        for member in plan.get("team", []):
            name = member["name"]
            if name in seen:
                continue
            seen.add(name)
            role = member.get("role", "backend")
            prompt = self.ROLE_PROMPTS.get(role, f"Specialist in {role}.")
            model_override = self.ROLE_MODELS.get(role)
            
            agent = self.planner.create_sub_agent(name, role, system_prompt=prompt)
            if model_override:
                # Add a way to override the model for this specific agent
                agent.model_override = model_override
            
            if logger_callback:
                agent.set_logger(logger_callback)
                
            agents.append(agent)
        return agents
