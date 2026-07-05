"""L1 transient retry layer with exponential backoff.

Bounded by ``max_attempts`` (default 3). The first attempt runs immediately;
subsequent attempts sleep for ``base_delay * backoff_factor ** (attempt-1)``
seconds. Raises ``L1Exhausted`` when every attempt fails. The final
(failed) attempt does NOT sleep — only ``max_attempts - 1`` sleeps occur.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


class L1Exhausted(Exception):
    """Raised when all L1 retry attempts fail.

    Carries the chained cause (the last underlying exception).
    """

    def __init__(self, message: str, attempts: int, cause: BaseException) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.cause = cause


@dataclass(frozen=True)
class L1Retry:
    """Lightweight record describing an L1 retry trace.

    Used by callers who want to surface the retry context to L2/L3 without
    having to catch ``L1Exhausted`` themselves.
    """

    operation: str
    attempts: int
    last_error: str


async def retry_with_backoff[T](
    op: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    backoff_factor: float = 2.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run ``op`` with exponential-backoff retry.

    Args:
        op: zero-arg async callable.
        max_attempts: total attempts including the first (default 3).
        base_delay: initial sleep duration in seconds (default 0.5).
        backoff_factor: multiplier per attempt (default 2.0).
        sleep: injectable sleep for tests (default ``asyncio.sleep``).

    Returns:
        The first successful return value from ``op``.

    Raises:
        L1Exhausted: when every attempt fails.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    last_exc: BaseException | None = None
    delay = base_delay

    for attempt in range(1, max_attempts + 1):
        try:
            return await op()
        except BaseException as exc:  # noqa: BLE001 — captured and re-raised as L1Exhausted
            last_exc = exc
            if attempt == max_attempts:
                break
            await sleep(delay)
            delay *= backoff_factor

    assert last_exc is not None  # invariant: at least one attempt ran
    raise L1Exhausted(
        f"L1 exhausted after {max_attempts} attempts: "
        f"{type(last_exc).__name__}: {last_exc}",
        attempts=max_attempts,
        cause=last_exc,
    )


# Public alias for ergonomic call sites.
l1_retry = retry_with_backoff


__all__ = [
    "L1Exhausted",
    "L1Retry",
    "l1_retry",
    "retry_with_backoff",
]


# Type alias retained for legacy callers; not exported but referenced in
# L2/L3 stubs that accept Any context blobs.
_ = Any
