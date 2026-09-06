"""Tests for ``crackerjack.core.self_heal.l2_noop``.

Covers the ``L2Noop`` dataclass marker and the ``l2_noop`` async recovery stub.
"""

from __future__ import annotations

import asyncio

import pytest

from crackerjack.core.self_heal.l2_noop import L2Noop, l2_noop


@pytest.fixture(autouse=True)
def _restore_marker() -> None:
    """Snapshot and restore the class-level MARKER constant around tests.

    Tests must not permanently mutate the constant even if they probe mutability.
    """
    saved = L2Noop.MARKER
    yield  # type: ignore[misc]
    L2Noop.MARKER = saved  # type: ignore[misc]


def test_l2_noop_marker_is_constant_string() -> None:
    assert L2Noop.MARKER == "noop_recovery"


@pytest.mark.asyncio
async def test_l2_noop_function_returns_marker() -> None:
    result = await l2_noop(operation="any_op", l1_context={"k": "v"})
    assert result == "noop_recovery"


@pytest.mark.asyncio
async def test_l2_noop_accepts_optional_claude_turn_callable() -> None:
    async def fake_turn(*_args: object, **_kwargs: object) -> tuple[str, int]:
        return ("ok", 0)

    result = await l2_noop(
        operation="anything",
        l1_context={},
        claude_turn=fake_turn,
    )
    assert result == "noop_recovery"


@pytest.mark.asyncio
async def test_l2_noop_returns_marker_for_arbitrary_inputs() -> None:
    """Inputs are explicitly discarded; output is always the marker."""
    cases = [
        {"operation": "", "l1_context": {}},
        {"operation": "x" * 1000, "l1_context": {"deep": {"nested": [1, 2, 3]}}},
    ]
    for kwargs in cases:
        result = await l2_noop(**kwargs)  # type: ignore[arg-type]
        assert result == "noop_recovery"


def test_l2_noop_callable_synchronously_via_asyncio_run() -> None:
    """The async function can be driven from sync tests via ``asyncio.run``."""
    result = asyncio.run(l2_noop(operation="sync", l1_context={}))
    assert result == "noop_recovery"

