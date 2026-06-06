from __future__ import annotations

from zerion_core.config import settings

TASK_MODEL_MAP: dict[str, str] = {
    "chat": settings.chat_model,
    "cli": settings.fast_model,
    "web_dev": settings.heavy_model,
    "discord_bot": settings.default_model,
    "telegram_bot": settings.default_model,
    "scraping": settings.default_model,
    "bug_fix": settings.heavy_model,
    "research": settings.chat_model,
    "ui_design": settings.default_model,
    "architecture": settings.heavy_model,
    "agent_system": settings.heavy_model,
    "routing": settings.fast_model,
    "planning": settings.default_model,
    "review": settings.default_model,
    "qa": settings.fast_model,
    "documentation": settings.chat_model,
    "memory_extraction": settings.fast_model,
    "embedding": settings.embedding_model,
}


class ModelRouter:
    """Select Ollama model based on task classification and complexity."""

    @staticmethod
    def for_task(task_type: str, complexity: str = "medium") -> str:
        if complexity == "simple":
            return settings.fast_model
        if complexity == "complex":
            return settings.heavy_model
        if complexity == "extreme":
            return settings.heavy_model # Multi-agent handled by Orchestrator
            
        return TASK_MODEL_MAP.get(task_type, settings.default_model)

    @staticmethod
    def estimate_complexity(task: str) -> str:
        t = task.lower()
        if len(t) < 50 and not any(w in t for w in ["refactor", "architect", "complex"]):
            return "simple"
        if any(w in t for w in ["rewrite", "optimize", "security", "distributed"]):
            return "complex"
        return "medium"

    @staticmethod
    def for_agent(agent_role: str) -> str:
        role_map = {
            "ceo": settings.chat_model,
            "router": settings.fast_model,
            "memory": settings.fast_model,
            "research": settings.chat_model,
            "planner": settings.default_model,
            "reviewer": settings.default_model,
            "qa": settings.heavy_model,
            "documentation": settings.chat_model,
            "cli": settings.heavy_model,
            "frontend": settings.default_model,
            "backend": settings.default_model,
            "database": settings.default_model,
            "auth": settings.default_model,
            "discord": settings.default_model,
            "telegram": settings.default_model,
            "scraping": settings.default_model,
            "deployment": settings.fast_model,
        }
        return role_map.get(agent_role.lower(), settings.default_model)
