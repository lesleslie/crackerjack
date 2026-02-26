from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class SessionEventEmitterProtocol(Protocol):

    @property
    def available(self) -> bool: ...

    async def emit_session_start(
        self,
        shell_type: str = "UnknownShell",
        metadata: dict[str, Any] | None = None,
    ) -> str | None: ...

    async def emit_session_end(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    async def close(self) -> None: ...


class _FallbackSessionEventEmitter:

    def __init__(
        self,
        component_name: str,
        **kwargs: Any,
    ) -> None:
        self.component_name = component_name
        self._available = False
        logger.debug(
            f"Session tracking unavailable for {component_name} "
            "(Oneiric session tracker not found)"
        )

    async def emit_session_start(
        self,
        shell_type: str = "UnknownShell",
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        logger.debug(
            f"Session start emitted (fallback mode): {shell_type} "
            f"for {self.component_name}"
        )
        return None

    async def emit_session_end(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        logger.debug(
            f"Session end emitted (fallback mode): {session_id} "
            f"for {self.component_name}"
        )

    async def close(self) -> None:
        logger.debug(f"Session emitter closed (fallback mode): {self.component_name}")

    @property
    def available(self) -> bool:
        return self._available


try:
    from oneiric.shell.session_tracker import (
        SessionEventEmitter as SessionEventEmitter,
    )

    logger.debug("Using Oneiric SessionEventEmitter")
except ImportError:
    SessionEventEmitter = _FallbackSessionEventEmitter  # type: ignore[misc, assignment]
    logger.debug(
        "Using fallback SessionEventEmitter (Oneiric session tracker unavailable)"
    )
