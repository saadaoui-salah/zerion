from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

from zerion_core.config import settings


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    task: str
    priority: MessagePriority = MessagePriority.NORMAL
    status: str = "pending"
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reply_to: str | None = None
    retries: int = 0

    model_config = {"populate_by_name": True}

    def to_bus_record(self) -> dict[str, Any]:
        return {
            "from": self.from_agent,
            "to": self.to_agent,
            "task": self.task,
            "priority": self.priority.value,
            "status": self.status,
            "id": self.id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


MessageHandler = Callable[[AgentMessage], Coroutine[Any, Any, AgentMessage | None]]


class MessageBus:
    """Event-driven agent communication bus with file persistence."""

    def __init__(self, bus_dir: Path | None = None) -> None:
        self.bus_dir = bus_dir or settings.agent_bus_dir
        self.bus_dir.mkdir(parents=True, exist_ok=True)
        self.inbox_dir = self.bus_dir / "inbox"
        self.outbox_dir = self.bus_dir / "outbox"
        self.inbox_dir.mkdir(exist_ok=True)
        self.outbox_dir.mkdir(exist_ok=True)
        self._handlers: dict[str, list[MessageHandler]] = defaultdict(list)
        self._global_handlers: list[MessageHandler] = []
        self._queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._running = False
        self._history: list[AgentMessage] = []
        self._reply_futures: dict[str, asyncio.Future[AgentMessage]] = {}

    def subscribe(self, agent_name: str, handler: MessageHandler) -> None:
        self._handlers[agent_name.lower()].append(handler)

    def subscribe_all(self, handler: MessageHandler) -> None:
        self._global_handlers.append(handler)

    async def publish(self, message: AgentMessage) -> None:
        self._persist(message)
        self._history.append(message)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        
        # Check if this is a reply to something we are waiting for
        if message.reply_to in self._reply_futures:
            future = self._reply_futures.pop(message.reply_to)
            if not future.done():
                future.set_result(message)

        await self._queue.put(message)

    async def wait_for_reply(self, message_id: str, timeout: float = 300.0) -> AgentMessage:
        future: asyncio.Future[AgentMessage] = asyncio.Future()
        self._reply_futures[message_id] = future
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._reply_futures.pop(message_id, None)
            raise

    async def request(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        payload: dict[str, Any] | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        msg = AgentMessage(
            **{
                "from": from_agent,
                "to": to_agent,
                "task": task,
                "priority": priority,
                "payload": payload or {},
            }
        )
        await self.publish(msg)
        return msg

    def _persist(self, message: AgentMessage) -> None:
        path = self.outbox_dir / f"{message.timestamp.replace(':', '-')}_{message.id}.json"
        path.write_text(json.dumps(message.to_bus_record(), indent=2), encoding="utf-8")

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                message = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await self._dispatch(message)

    def stop(self) -> None:
        self._running = False

    async def _dispatch(self, message: AgentMessage) -> None:
        target = message.to_agent.lower()
        handlers = list(self._handlers.get(target, []))
        handlers.extend(self._handlers.get("*", []))
        handlers.extend(self._global_handlers)

        if not handlers and target != "*" and target != "bus":
            if message.retries < 3:
                message.retries += 1
                await asyncio.sleep(0.1 * message.retries)
                await self.publish(message)
                return

        for handler in handlers:
            try:
                reply = await handler(message)
                if reply:
                    await self.publish(reply)
            except Exception as exc:
                if message.retries < 3:
                    message.retries += 1
                    await self.publish(message)
                else:
                    err = AgentMessage(
                        **{
                            "from": "bus",
                            "to": message.from_agent,
                            "task": "error",
                            "payload": {"error": str(exc), "original_id": message.id},
                        }
                    )
                    await self.publish(err)

    def recent_messages(self, limit: int = 50) -> list[AgentMessage]:
        return self._history[-limit:]

    def conversation_lines(self, limit: int = 20) -> list[str]:
        lines = []
        for msg in self._history[-limit:]:
            lines.append(f"{msg.from_agent} → {msg.to_agent}: {msg.task[:80]}")
        return lines
