from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Callable

from zerion_core.config import settings
from zerion_core.rag.indexer import CodeIndexer


class FileWatcher:
    """Watches source files for changes and triggers incremental re-indexing."""

    def __init__(
        self,
        indexer: CodeIndexer,
        on_change: Callable[[list[Path]], None] | None = None,
        poll_interval: float = 5.0,
    ) -> None:
        self.indexer = indexer
        self.on_change = on_change or (lambda _p: None)
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_check: float = 0.0

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _watch_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.poll_interval)
                changed = self.indexer.get_changed_files()
                if changed:
                    self._last_check = time.time()
                    self.on_change(changed)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self.poll_interval)

    def check_now(self) -> list[Path]:
        """Synchronous check for changed files."""
        changed = self.indexer.get_changed_files()
        if changed:
            self._last_check = time.time()
        return changed
