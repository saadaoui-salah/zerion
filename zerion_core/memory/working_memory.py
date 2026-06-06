from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from zerion_core.memory.models import WorkingMemorySlot


class WorkingMemory:
    """Letta-style working memory with bounded slots."""

    MAX_SLOTS = 32

    def __init__(self) -> None:
        self._slots: dict[str, WorkingMemorySlot] = {}

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        if len(self._slots) >= self.MAX_SLOTS and key not in self._slots:
            oldest = min(self._slots.values(), key=lambda s: s.created_at)
            self._slots.pop(oldest.key, None)
        self._slots[key] = WorkingMemorySlot(key=key, value=value, ttl_seconds=ttl_seconds)

    def get(self, key: str, default: str | None = None) -> str | None:
        slot = self._slots.get(key)
        if not slot:
            return default
        if slot.ttl_seconds is not None:
            created = datetime.fromisoformat(slot.created_at)
            age = (datetime.now(timezone.utc) - created).total_seconds()
            if age > slot.ttl_seconds:
                self._slots.pop(key, None)
                return default
        return slot.value

    def dump(self) -> dict[str, str]:
        self._purge_expired()
        return {k: v.value for k, v in self._slots.items()}

    def _purge_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired = []
        for key, slot in self._slots.items():
            if slot.ttl_seconds is None:
                continue
            created = datetime.fromisoformat(slot.created_at)
            if (now - created).total_seconds() > slot.ttl_seconds:
                expired.append(key)
        for key in expired:
            self._slots.pop(key, None)

    def context_block(self) -> str:
        items = self.dump()
        if not items:
            return ""
        lines = ["## Working Memory"]
        for k, v in items.items():
            lines.append(f"- {k}: {v[:200]}")
        return "\n".join(lines)
