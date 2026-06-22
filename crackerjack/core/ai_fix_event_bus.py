from __future__ import annotations

import asyncio
import datetime
import logging
from contextlib import suppress

from uuid_utils import uuid4 as _uuid4
from typing import Protocol

from .ai_fix_events import AIFixEvent

logger = logging.getLogger(__name__)


class Sink(Protocol):
    async def handle(self, event: AIFixEvent) -> None: ...


class AIFixEventBus:
    def __init__(self) -> None:
        self._sinks: list[Sink] = []
        self._fix_seq: int = 0

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
        with suppress(RuntimeError):
            asyncio.get_running_loop().create_task(self.emit(event))

    def next_fix_task_id(self) -> str:
        task_id = f"fix-{self._fix_seq:04d}"
        self._fix_seq += 1
        return task_id

    @staticmethod
    def new_run_id() -> str:
        ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
        return f"{ts}-{_uuid4().hex[:4]}"
