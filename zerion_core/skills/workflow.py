"""Skill workflow engine: executes skill-defined workflows."""

from __future__ import annotations

from typing import Any, Callable

from zerion_core.skills.models import Skill


class WorkflowStep:
    """A single step in a skill workflow."""

    def __init__(
        self,
        name: str,
        description: str = "",
        agent: str = "",
        tools: list[str] | None = None,
        prompt_template: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self.agent = agent
        self.tools = tools or []
        self.prompt_template = prompt_template


class WorkflowState:
    """Tracks state of a running workflow."""

    def __init__(self, skill_name: str, steps: list[str]) -> None:
        self.skill_name = skill_name
        self.steps = steps
        self.current_index = 0
        self.results: dict[str, Any] = {}
        self.completed: list[str] = []
        self.failed: list[str] = []

    @property
    def current_step(self) -> str | None:
        if self.current_index < len(self.steps):
            return self.steps[self.current_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_index >= len(self.steps)

    @property
    def progress(self) -> float:
        if not self.steps:
            return 1.0
        return len(self.completed) / len(self.steps)

    def advance(self, result: Any = None) -> None:
        if self.current_step:
            self.completed.append(self.current_step)
            self.results[self.current_step] = result
        self.current_index += 1

    def fail(self, error: str = "") -> None:
        if self.current_step:
            self.failed.append(self.current_step)
            self.results[self.current_step] = {"error": error}
        self.current_index += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "current_step": self.current_step,
            "progress": self.progress,
            "completed": self.completed,
            "failed": self.failed,
            "is_complete": self.is_complete,
        }


class SkillWorkflowEngine:
    """Manages and executes skill workflows."""

    def __init__(self) -> None:
        self._active_workflows: dict[str, WorkflowState] = {}
        self._step_handlers: dict[str, Callable[..., Any]] = {}
        self._default_steps = [
            "inspect",
            "locate",
            "root_cause",
            "patch",
            "test",
            "verify",
        ]

    def register_handler(self, step_name: str, handler: Callable[..., Any]) -> None:
        """Register a handler for a workflow step."""
        self._step_handlers[step_name] = handler

    def start_workflow(self, skill: Skill, context: dict[str, Any] | None = None) -> WorkflowState:
        """Start a workflow for a skill."""
        steps = skill.manifest.workflow.steps or self._default_steps
        state = WorkflowState(skill.manifest.name, steps)
        self._active_workflows[skill.manifest.name] = state
        return state

    def get_state(self, skill_name: str) -> WorkflowState | None:
        return self._active_workflows.get(skill_name)

    def advance_workflow(
        self,
        skill_name: str,
        result: Any = None,
    ) -> WorkflowState | None:
        """Advance a workflow to the next step."""
        state = self._active_workflows.get(skill_name)
        if not state or state.is_complete:
            return None
        state.advance(result)
        return state

    def fail_workflow(
        self,
        skill_name: str,
        error: str = "",
    ) -> WorkflowState | None:
        """Mark current step as failed and advance."""
        state = self._active_workflows.get(skill_name)
        if not state or state.is_complete:
            return None
        state.fail(error)
        return state

    def end_workflow(self, skill_name: str) -> WorkflowState | None:
        """End and remove a workflow."""
        return self._active_workflows.pop(skill_name, None)

    def build_workflow_prompt(self, skill: Skill, user_request: str) -> str:
        """Build a prompt that instructs the agent to follow the workflow."""
        steps = skill.manifest.workflow.steps or self._default_steps
        workflow_name = skill.manifest.workflow.name or f"{skill.manifest.name} Workflow"

        steps_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(steps))

        return f"""When handling this request, follow the {workflow_name}:

{steps_text}

For each step:
1. Complete the step thoroughly
2. Document what you found/did
3. Only proceed to the next step when the current one is complete

User Request: {user_request}"""

    def format_workflow_status(self, skill_name: str) -> str:
        """Format current workflow status for display."""
        state = self._active_workflows.get(skill_name)
        if not state:
            return f"No active workflow for {skill_name}"

        lines = [
            f"Workflow: {state.skill_name} ({state.progress:.0%} complete)",
            f"Current: {state.current_step or 'Done'}",
        ]
        if state.completed:
            lines.append(f"Completed: {', '.join(state.completed)}")
        if state.failed:
            lines.append(f"Failed: {', '.join(state.failed)}")

        return "\n".join(lines)

    def get_all_active(self) -> dict[str, dict[str, Any]]:
        """Get all active workflows."""
        return {name: state.to_dict() for name, state in self._active_workflows.items()}
