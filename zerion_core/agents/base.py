from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from zerion_core.bus.message_bus import AgentMessage, MessageBus, MessagePriority
from zerion_core.llm.model_router import ModelRouter
from zerion_core.llm.ollama import OllamaClient, LLMResponse
from zerion_core.memory.manager import MemoryManager


class AgentStatus(str, Enum):
    IDLE = "Idle"
    WORKING = "Working"
    WAITING = "Waiting"
    ERROR = "Error"


@dataclass
class AgentState:
    name: str
    role: str
    status: AgentStatus = AgentStatus.IDLE
    current_task: str = ""
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    tokens_used: int = 0
    last_model: str | None = None


@dataclass
class TaskResult:
    success: bool
    output: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class Agent:
    """Base agent with memory, bus, delegation, and sub-agent creation."""

    def __init__(
        self,
        name: str,
        role: str,
        llm: OllamaClient,
        memory: MemoryManager,
        bus: MessageBus,
        system_prompt: str = "",
        parent: str | None = None,
    ) -> None:
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.role = role
        self.llm = llm
        self.memory = memory
        self.bus = bus
        self.system_prompt = system_prompt or self._default_system()
        self.parent = parent
        self.state = AgentState(name=name, role=role, parent=parent)
        self.sub_agents: list[Agent] = []
        self.model_override: str | None = None
        self.logger: Callable[[str], None] | None = None
        self._register_bus()

    def set_logger(self, logger: Callable[[str], None]) -> None:
        self.logger = logger

    def _default_system(self) -> str:
        return (
            f"You are {self.name}, a {self.role} agent in Zerion-Core. "
            "Collaborate via the agent bus. Read/write memory for durable facts only. "
            "If you have doubts or need clarification from the user, you can use the 'ask_user' capability. "
            "Be concise and actionable."
        )

    def _register_bus(self) -> None:
        async def handler(msg: AgentMessage) -> AgentMessage | None:
            if msg.to_agent.lower() not in (self.name.lower(), "*"):
                return None
            self.state.status = AgentStatus.WORKING
            self.state.current_task = msg.task
            result = await self.handle_message(msg)
            self.state.status = AgentStatus.IDLE
            self.state.current_task = ""
            if result:
                return AgentMessage(
                    **{
                        "from": self.name,
                        "to": msg.from_agent,
                        "task": "response",
                        "payload": {"output": result.output, "success": result.success},
                        "reply_to": msg.id,
                    }
                )
            return None

        self.bus.subscribe(self.name, handler)

    async def handle_message(self, msg: AgentMessage) -> TaskResult | None:
        return await self.execute(msg.task, msg.payload)

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> TaskResult:
        self.state.status = AgentStatus.WORKING
        self.state.current_task = task
        ctx = context or {}
        
        # Requirement 1: Standardized input format
        if "engineered_context" in ctx:
            agent_input = ctx["engineered_context"]
        else:
            # Fallback to simple retrieval if ContextEngineer wasn't used
            memory_ctx = await self.memory.retrieve_context(task, project=ctx.get("project", ""))
            agent_input = {
                "goal": task,
                "relevant_files": [],
                "relevant_memories": memory_ctx[:4000],
                "relevant_decisions": [],
                "relevant_lessons": [],
            }

        messages = [
            {
                "role": "user",
                "content": f"Context:\n{json.dumps(agent_input, indent=2)}\n\nAdditional Context:\n{json.dumps(ctx, indent=2)}",
            }
        ]
        try:
            resp = await self._chat(messages)
            self.state.tokens_used += resp.usage.total
            await self.memory.ingest_agent_output(
                resp.content,
                project=ctx.get("project", "default"),
                agent=self.name,
                task_type=ctx.get("task_type", self.role),
            )
            return TaskResult(success=True, output=resp.content)
        except Exception as exc:
            return TaskResult(success=False, output="", errors=[str(exc)])
        finally:
            self.state.status = AgentStatus.IDLE
            self.state.current_task = ""

    async def _chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> LLMResponse:
        model = self.model_override or ModelRouter.for_agent(self.role)
        self.state.last_model = model
        
        # Log model usage if a logger callback is registered
        if self.logger:
            self.logger(f"Agent {self.name} using model: {model}")
        
        return await self.llm.chat(
            messages=messages,
            model=model,
            system=self.system_prompt,
            json_mode=json_mode,
        )

    async def request_assistance(
        self,
        to_agent: str,
        task: str,
        payload: dict[str, Any] | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        self.state.status = AgentStatus.WAITING
        msg = await self.bus.request(self.name, to_agent, task, payload, priority)
        self.state.status = AgentStatus.IDLE
        return msg

    def create_sub_agent(self, name: str, role: str, system_prompt: str = "") -> Agent:
        sub = Agent(
            name=name,
            role=role,
            llm=self.llm,
            memory=self.memory,
            bus=self.bus,
            system_prompt=system_prompt or f"You are {name}, specialized in {role}.",
            parent=self.name,
        )
        self.sub_agents.append(sub)
        self.state.children.append(name)
        return sub

    async def read_memory(self, query: str, project: str = "") -> str:
        return await self.memory.retrieve_context(query, project)

    async def write_memory(self, key: str, value: str) -> None:
        self.memory.upsert_semantic(key, value, source=self.name)

    async def ask_user(self, question: str) -> str:
        """Wait for user input via the message bus."""
        self.state.status = AgentStatus.WAITING
        self.state.current_task = f"Waiting for user: {question[:40]}..."
        
        msg = await self.bus.request(
            self.name,
            "User",
            "ask",
            {"question": question},
            priority=MessagePriority.URGENT,
        )
        
        # Wait for the reply message on the bus
        reply = await self.bus.wait_for_reply(msg.id)
        
        # The reply will contain the answer in payload['output']
        answer = reply.payload.get("output", "")
        
        self.state.status = AgentStatus.IDLE
        self.state.current_task = ""
        return answer

    def status_line(self) -> str:
        indicator = {"Idle": "○", "Working": "●", "Waiting": "◐", "Error": "✗"}
        sym = indicator.get(self.state.status.value, "○")
        return f"{self.name:<12} {sym} {self.state.status.value}"
