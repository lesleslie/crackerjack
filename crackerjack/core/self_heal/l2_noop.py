
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class L2Noop:

    MARKER: str = "noop_recovery"


async def l2_noop(
    *,
    operation: str,
    l1_context: dict[str, Any],
    claude_turn: Callable[..., Awaitable[tuple[str, int]]] | None = None,
) -> str:
    _ = (operation, l1_context, claude_turn)
    return L2Noop.MARKER


__all__ = ["L2Noop", "l2_noop"]
