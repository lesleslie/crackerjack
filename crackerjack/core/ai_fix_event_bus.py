from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import Protocol

from .ai_fix_events import AIFixEvent

logger = logging.getLogger(__name__)


class Sink(Protocol):
    async def handle(self, event: AIFixEvent) -> None: ...


class AIFixEventBus:
    def __init__(self) -> None:
        self._sinks: list[Sink] = []

    def subscribe(self, sink: Sink) -> None:
        self._sinks.append(sink)

    def unsubscribe(self, sink: Sink) -> None:
        self._sinks.remove(sink)

    async def emit(self, event: AIFixEvent) -> None:
        for sink in self._sinks:
            try:
                await sink.handle(event)
            except Exception:
                logger.exception(
                    "Sink %s raised on event %s",
                    type(sink).__name__,
                    type(event).__name__,
                )

    def emit_nowait(self, event: AIFixEvent) -> None:
        """Schedule emit as a task in the running event loop (fire-and-forget).

        Safe to call from synchronous code that runs within an async context.
        Silently no-ops if there is no running event loop.
        """
        try:
            asyncio.get_running_loop().create_task(self.emit(event))
        except RuntimeError:
            pass

    @staticmethod
    def new_run_id() -> str:
        ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
        return f"{ts}-{uuid.uuid4().hex[:4]}"
