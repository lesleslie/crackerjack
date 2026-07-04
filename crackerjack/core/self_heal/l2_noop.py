"""L2 no-op stub layer.

Spec #4 originally specified a bounded agentic heal (3 Claude turns with
wire-truth verification). The C4 fix reverted L2 to a no-op: it now returns
``L2Noop.MARKER`` without invoking any Claude session. The wire-truth path
still runs end-to-end elsewhere (L1 retry + L3 rule extraction), so L2's
no-op status is observable and regression-tested.

Dhara substrate (audit log table) is currently ``sql_blocked``; this no-op
is a deliberate deferral of the agentic heal until the substrate unblocks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class L2Noop:
    """Marker class for the L2 no-op outcome.

    Exposes the constant ``MARKER`` returned by ``l2_noop()`` so callers
    can assert on a stable string without depending on the literal.
    """

    MARKER: str = "noop_recovery"


async def l2_noop(
    *,
    operation: str,
    l1_context: dict[str, Any],
    claude_turn: Callable[..., Awaitable[tuple[str, int]]] | None = None,
) -> str:
    """Return the L2 no-op marker.

    Args:
        operation: operation name (for future logging when the agentic
            path is reinstated). Currently ignored.
        l1_context: context blob from the L1 abort. Currently ignored.
        claude_turn: optional Claude session callable. If provided it is
            NEVER called — the stub is hard-wired to the no-op path.

    Returns:
        The constant ``"noop_recovery"``.
    """
    _ = (operation, l1_context, claude_turn)  # explicit: stub ignores all args
    return L2Noop.MARKER


__all__ = ["L2Noop", "l2_noop"]
