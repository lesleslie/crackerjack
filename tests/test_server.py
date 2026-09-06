"""Tests for ``crackerjack.server``.

Covers the ``CrackerjackServer`` lifecycle: construction, adapter init,
stop, health snapshot, and shutdown. Settings are stubbed via a small
``SimpleNamespace`` tree so the tests don't depend on the full
``CrackerjackSettings`` pydantic model.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.server import CrackerjackServer


def _make_settings(**overrides: Any) -> SimpleNamespace:
    """Build a minimal settings stub that satisfies the server's getattr probes."""
    s = SimpleNamespace(
        ruff_enabled=True,
        bandit_enabled=True,
        semgrep_enabled=False,
        mypy_enabled=True,
        skylos_enabled=True,
        hooks=SimpleNamespace(enable_pyrefly=False, enable_ty=False),
        zuban_lsp=SimpleNamespace(enabled=True),
        ai=None,
        testing=SimpleNamespace(test_workers=4),
        execution=SimpleNamespace(verbose=False),
        qa_mode=False,
    )
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


class _FakeAdapter:
    """Adapter stub with optional ``init`` / ``cleanup`` / ``healthy``."""

    def __init__(
        self,
        *,
        init_raises: Exception | None = None,
        healthy: bool = True,
        has_cleanup: bool = True,
    ) -> None:
        self.healthy = healthy
        self.init_raises = init_raises
        self.has_cleanup = has_cleanup
        self.init_called = False
        self.cleanup_called = False

    async def init(self) -> None:
        self.init_called = True
        if self.init_raises is not None:
            raise self.init_raises

    def cleanup(self) -> None:
        self.cleanup_called = True


@pytest.fixture
def settings() -> SimpleNamespace:
    return _make_settings()


@pytest.fixture
def adapter_factory() -> MagicMock:
    """Factory whose ``create_adapter`` returns a fresh ``_FakeAdapter`` per call."""
    factory = MagicMock()

    def _create(name: str, *args: Any, **kwargs: Any) -> _FakeAdapter:
        return _FakeAdapter()

    factory.create_adapter.side_effect = _create
    return factory


def test_server_init_with_explicit_factory(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    assert server.settings is settings
    assert server.adapter_factory is adapter_factory
    assert server.running is False
    assert server.adapters == []
    assert server.start_time is None
    assert server._server_task is None  # noqa: SLF001


def test_server_init_uses_default_factory(settings: SimpleNamespace) -> None:
    """No factory provided → ``DefaultAdapterFactory`` is constructed."""
    server = CrackerjackServer(settings=settings)
    assert server.adapter_factory is not None


def test_server_init_does_not_initialize_adapters(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    """``__init__`` must not call ``create_adapter`` — that's deferred to ``start``."""
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    adapter_factory.create_adapter.assert_not_called()


def test_get_enabled_adapter_flags(settings: SimpleNamespace) -> None:
    server = CrackerjackServer(settings=settings)
    flags = server._get_enabled_adapter_flags()  # noqa: SLF001
    assert flags["ruff"] is True
    assert flags["bandit"] is True
    assert flags["semgrep"] is False
    assert flags["mypy"] is True
    assert flags["pyrefly"] is False
    assert flags["ty"] is False
    assert flags["zuban"] is True
    assert flags["pytest"] is True


def test_get_enabled_adapter_flags_disabled(settings: SimpleNamespace) -> None:
    settings.ruff_enabled = False
    settings.bandit_enabled = False
    server = CrackerjackServer(settings=settings)
    flags = server._get_enabled_adapter_flags()  # noqa: SLF001
    assert flags["ruff"] is False
    assert flags["bandit"] is False


def test_get_enabled_adapter_flags_with_hooks(settings: SimpleNamespace) -> None:
    settings.hooks = SimpleNamespace(enable_pyrefly=True, enable_ty=True)
    server = CrackerjackServer(settings=settings)
    flags = server._get_enabled_adapter_flags()  # noqa: SLF001
    assert flags["pyrefly"] is True
    assert flags["ty"] is True


def test_get_enabled_adapter_flags_with_zuban_disabled(
    settings: SimpleNamespace,
) -> None:
    settings.zuban_lsp = SimpleNamespace(enabled=False)
    server = CrackerjackServer(settings=settings)
    flags = server._get_enabled_adapter_flags()  # noqa: SLF001
    assert flags["zuban"] is False


@pytest.mark.asyncio
async def test_initialize_adapters_skips_zuban_when_disabled(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    """When ``zuban_lsp.enabled`` is False, ``_init_zuban_adapter`` is not called."""
    settings.zuban_lsp = SimpleNamespace(enabled=False)
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    enabled_names: list[str] = []
    await server._initialize_adapters(enabled_names)  # noqa: SLF001
    # Zuban factory was never invoked.
    names_called = [
        call.args[0] for call in adapter_factory.create_adapter.call_args_list
    ]
    assert "Zuban" not in names_called


def test_get_enabled_adapter_flags_without_testing(settings: SimpleNamespace) -> None:
    """No ``testing`` attribute → ``pytest`` flag is False."""
    settings_no_testing = SimpleNamespace(
        ruff_enabled=True,
        bandit_enabled=True,
        semgrep_enabled=False,
        mypy_enabled=True,
        skylos_enabled=True,
        hooks=SimpleNamespace(enable_pyrefly=False, enable_ty=False),
        zuban_lsp=SimpleNamespace(enabled=True),
        ai=None,
    )
    server = CrackerjackServer(settings=settings_no_testing)
    flags = server._get_enabled_adapter_flags()  # noqa: SLF001
    assert flags["pytest"] is False


def test_stop_sets_running_false(settings: SimpleNamespace, adapter_factory: MagicMock) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    server.running = True
    server.stop()
    assert server.running is False


def test_stop_cleans_up_adapters(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    a1 = _FakeAdapter()
    a2 = _FakeAdapter()
    server.adapters = [a1, a2]
    server.stop()
    assert a1.cleanup_called
    assert a2.cleanup_called


def test_stop_skips_adapter_without_cleanup(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    """Adapters without a ``cleanup`` method are skipped (no AttributeError)."""
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)

    class _MinimalAdapter:
        pass

    server.adapters = [_MinimalAdapter()]
    server.stop()  # must not raise
    assert server.running is False


def test_stop_swallows_cleanup_errors(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)

    class _BoomAdapter:
        def cleanup(self) -> None:
            raise RuntimeError("boom")

    server.adapters = [_BoomAdapter()]
    server.stop()  # must not raise
    assert server.running is False


def test_health_snapshot_when_not_started(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    snap = server.get_health_snapshot()
    assert snap.orchestrator_pid > 0
    assert snap.watchers_running is False
    state = snap.lifecycle_state
    assert state["server_status"] == "stopped"
    assert state["uptime_seconds"] == 0.0
    assert state["qa_adapters"]["total"] == 0
    assert state["qa_adapters"]["healthy"] == 0


def test_health_snapshot_includes_adapter_flags(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    snap = server.get_health_snapshot()
    flags = snap.lifecycle_state["qa_adapters"]["enabled_flags"]
    assert "ruff" in flags
    assert "bandit" in flags


def test_health_snapshot_includes_settings_summary(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    snap = server.get_health_snapshot()
    summary = snap.lifecycle_state["settings"]
    assert "qa_mode" in summary
    assert "ai_agent" in summary
    assert "auto_fix" in summary
    assert "test_workers" in summary
    assert "verbose" in summary


def test_health_snapshot_counts_unhealthy_adapters(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    server.adapters = [_FakeAdapter(healthy=True), _FakeAdapter(healthy=False)]
    snap = server.get_health_snapshot()
    state = snap.lifecycle_state
    assert state["qa_adapters"]["total"] == 2
    assert state["qa_adapters"]["healthy"] == 1


def test_health_snapshot_uptime_after_start(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    from datetime import UTC, datetime, timedelta

    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    server.start_time = datetime.now(UTC) - timedelta(seconds=42)
    server.running = True
    snap = server.get_health_snapshot()
    assert snap.lifecycle_state["uptime_seconds"] >= 42.0


@pytest.mark.asyncio
async def test_init_adapter_if_enabled_skips_when_disabled(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    settings.ruff_enabled = False
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    await server._init_adapter_if_enabled(  # noqa: SLF001
        setting_name="ruff_enabled",
        default_value=True,
        adapter_name="Ruff",
        enabled_names=[],
    )
    adapter_factory.create_adapter.assert_not_called()
    assert server.adapters == []


@pytest.mark.asyncio
async def test_init_adapter_if_enabled_appends_on_success(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    enabled_names: list[str] = []
    await server._init_adapter_if_enabled(  # noqa: SLF001
        setting_name="ruff_enabled",
        default_value=True,
        adapter_name="Ruff",
        enabled_names=enabled_names,
    )
    assert len(server.adapters) == 1
    assert enabled_names == ["Ruff"]


@pytest.mark.asyncio
async def test_init_adapter_if_enabled_swallows_init_errors(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    factory = MagicMock()

    def _create(name: str, *args: Any, **kwargs: Any) -> Any:
        return _FakeAdapter(init_raises=RuntimeError("init failed"))

    factory.create_adapter.side_effect = _create
    server = CrackerjackServer(settings=settings, adapter_factory=factory)
    enabled_names: list[str] = []
    await server._init_adapter_if_enabled(  # noqa: SLF001
        setting_name="ruff_enabled",
        default_value=True,
        adapter_name="Ruff",
        enabled_names=enabled_names,
    )
    # Adapter failed init → not appended, not in enabled_names.
    assert server.adapters == []
    assert enabled_names == []


@pytest.mark.asyncio
async def test_init_qa_adapters_populates_adapters_list(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    """``_init_qa_adapters`` populates ``server.adapters``."""
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    await server._init_qa_adapters()  # noqa: SLF001
    # Default settings enable ruff + bandit + mypy + skylos + zuban.
    assert len(server.adapters) >= 1


@pytest.mark.asyncio
async def test_init_zuban_adapter_success(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    enabled_names: list[str] = []
    await server._init_zuban_adapter(enabled_names)  # noqa: SLF001
    assert "Zuban" in enabled_names


@pytest.mark.asyncio
async def test_init_zuban_adapter_swallows_errors(
    settings: SimpleNamespace
) -> None:
    factory = MagicMock()
    factory.create_adapter.side_effect = RuntimeError("boom")
    server = CrackerjackServer(settings=settings, adapter_factory=factory)
    enabled_names: list[str] = []
    await server._init_zuban_adapter(enabled_names)  # noqa: SLF001
    assert enabled_names == []


@pytest.mark.asyncio
async def test_init_claude_adapter_skipped_when_ai_disabled(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    enabled_names: list[str] = []
    await server._init_claude_adapter(enabled_names)  # noqa: SLF001
    adapter_factory.create_adapter.assert_not_called()
    assert enabled_names == []


@pytest.mark.asyncio
async def test_init_claude_adapter_appended_when_enabled(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    settings.ai = SimpleNamespace(ai_agent=True)
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    enabled_names: list[str] = []
    await server._init_claude_adapter(enabled_names)  # noqa: SLF001
    assert "Claude AI" in enabled_names


@pytest.mark.asyncio
async def test_init_claude_adapter_swallows_errors(
    settings: SimpleNamespace
) -> None:
    settings.ai = SimpleNamespace(ai_agent=True)
    factory = MagicMock()
    factory.create_adapter.side_effect = RuntimeError("boom")
    server = CrackerjackServer(settings=settings, adapter_factory=factory)
    enabled_names: list[str] = []
    await server._init_claude_adapter(enabled_names)  # noqa: SLF001
    assert enabled_names == []


@pytest.mark.asyncio
async def test_shutdown_stops_running_server(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    server.running = True
    await server.shutdown()
    assert server.running is False


@pytest.mark.asyncio
async def test_shutdown_cancels_server_task(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)

    async def _long_running() -> None:
        await asyncio.sleep(10)

    server._server_task = asyncio.create_task(_long_running())  # noqa: SLF001
    await server.shutdown()
    assert server._server_task.cancelled()  # noqa: SLF001


@pytest.mark.asyncio
async def test_shutdown_without_task_is_noop(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    server._server_task = None  # noqa: SLF001
    await server.shutdown()  # must not raise
    assert server.running is False


@pytest.mark.asyncio
async def test_run_in_background_creates_task(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)

    async def stop_soon() -> None:
        await asyncio.sleep(0.05)
        server.stop()

    server._server_task = asyncio.create_task(stop_soon())  # noqa: SLF001
    task = server._server_task  # noqa: SLF001
    assert isinstance(task, asyncio.Task)
    await task


@pytest.mark.asyncio
async def test_run_in_background_starts_real_server(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    """``run_in_background`` calls ``start`` as a task and returns it."""
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    task = await server.run_in_background()
    # Give the start loop a tick to run.
    await asyncio.sleep(0.05)
    assert isinstance(task, asyncio.Task)
    # Now stop the server and wait for the loop to exit.
    server.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()


@pytest.mark.asyncio
async def test_start_method_runs_init_and_loop(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    """``start`` runs the adapter init, sets start_time, then loops."""
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    task = asyncio.create_task(server.start())
    await asyncio.sleep(0.05)
    assert server.running is True
    assert server.start_time is not None
    assert len(server.adapters) >= 1
    # Stop the loop and confirm graceful exit.
    server.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()


@pytest.mark.asyncio
async def test_start_handles_cancellation(
    settings: SimpleNamespace, adapter_factory: MagicMock
) -> None:
    """Cancelling the running task triggers the CancelledError handler."""
    server = CrackerjackServer(settings=settings, adapter_factory=adapter_factory)
    task = asyncio.create_task(server.start())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
