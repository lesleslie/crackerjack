"""Tests for ``crackerjack.mcp.service_watchdog``.

The watchdog spawns a subprocess for each ``ServiceConfig``, periodically
health-checks the URL (if any), and restarts the process when it dies or
fails health. Subprocess.Popen is mocked via ``crackerjack.mcp.service_watchdog.subprocess.Popen``
so we exercise the orchestration logic without spawning real processes.

The HTTP pool is mocked via the ``get_http_pool`` symbol imported by the
module — both for the initial ``await get_http_pool()`` in ``start()`` and
for ``_health_check``. We patch it via a fixture that injects a fake pool
that yields a session whose ``get()`` returns a status-controlled response.

The watchdog runs in tight ``while self.is_running`` loops; for unit tests
we set ``is_running = False`` after the first iteration or use a
``task.cancel()`` to short-circuit, since ``start()`` is meant to run
forever.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from crackerjack.mcp import service_watchdog
from crackerjack.mcp.service_watchdog import (
    ServiceConfig,
    ServiceWatchdog,
    create_default_watchdog,
    watchdog_event_queue,
)


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def console() -> MagicMock:
    return MagicMock()


def _fake_popen_factory() -> Any:
    """Return a fake Popen class with ``poll()`` returning None (still running)."""

    class _FakeProcess:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.pid = 12345
            self.stdout = None
            self.stderr = None
            self._exit_code: int | None = None
            self.communicate_called = False

        def poll(self) -> int | None:
            return self._exit_code

        def communicate(self) -> tuple[str, str]:
            self.communicate_called = True
            return ("", "boom stderr")

        def terminate(self) -> None:
            self._exit_code = -15

        def kill(self) -> None:
            self._exit_code = -9

        def wait(self, timeout: float | None = None) -> int:
            return -1

    return _FakeProcess


def _make_fake_pool(status: int = 200) -> Any:
    """Build a fake httpx pool that yields a session yielding ``status``."""
    pool = MagicMock()

    @asynccontextmanager
    async def _session_ctx() -> Any:
        session = MagicMock()

        @asynccontextmanager
        async def _response_ctx() -> Any:
            yield SimpleNamespace(status=status)

        session.get = lambda url: _response_ctx()
        yield session

    pool.get_session_context = _session_ctx
    return pool


# ---------------------------------------------------------------------------
# ServiceConfig
# ---------------------------------------------------------------------------


def test_service_config_defaults() -> None:
    config = ServiceConfig(name="x", command=["echo"])
    assert config.health_check_url is None
    assert config.health_check_interval == 30.0
    assert config.restart_delay == 5.0
    assert config.max_restarts == 10
    assert config.restart_window == 300.0
    assert config.process is None
    assert config.restart_count == 0
    assert config.restart_timestamps == []
    assert config.last_health_check == 0.0
    assert config.is_healthy is False
    assert config._port_acknowledged is False
    assert config.last_error is None


def test_service_config_explicit_values() -> None:
    config = ServiceConfig(
        name="mcp",
        command=["python", "-m", "crackerjack"],
        health_check_url="http://127.0.0.1:8676/mcp",
        health_check_interval=10.0,
        restart_delay=2.0,
        max_restarts=3,
        restart_window=60.0,
    )
    assert config.name == "mcp"
    assert config.health_check_url == "http://127.0.0.1:8676/mcp"
    assert config.health_check_interval == 10.0


# ---------------------------------------------------------------------------
# ServiceWatchdog.__init__
# ---------------------------------------------------------------------------


def test_watchdog_init_default_console(console: MagicMock) -> None:
    watchdog = ServiceWatchdog(services=[], console=console)
    assert watchdog.services == []
    assert watchdog.console is console
    assert watchdog.is_running is True
    assert watchdog.event_queue is None


def test_watchdog_init_creates_default_console() -> None:
    watchdog = ServiceWatchdog(services=[])
    assert watchdog.console is not None


def test_watchdog_init_sets_module_event_queue() -> None:
    """The constructor rebinds the module-level ``watchdog_event_queue``
    when an explicit queue is provided.

    Access the global via ``service_watchdog.watchdog_event_queue`` so we
    read the actual module binding rather than the import-time cached
    reference held by this test module.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    ServiceWatchdog(services=[], event_queue=queue)
    assert service_watchdog.watchdog_event_queue is queue


def test_watchdog_init_does_not_set_event_queue_when_none() -> None:
    saved = service_watchdog.watchdog_event_queue
    service_watchdog.watchdog_event_queue = None
    try:
        ServiceWatchdog(services=[], event_queue=None)
        assert service_watchdog.watchdog_event_queue is None
    finally:
        service_watchdog.watchdog_event_queue = saved


# ---------------------------------------------------------------------------
# _is_port_in_use
# ---------------------------------------------------------------------------


def test_is_port_in_use_unused_returns_false() -> None:
    """An unused high port (close 0) is not in use."""
    s = ServiceWatchdog(services=[])
    # Bind to a random free port first, then check that the SAME port is in use.
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serv:
        serv.bind(("127.0.0.1", 0))
        port = serv.getsockname()[1]
        # While the socket is bound, the port is in use.
        assert s._is_port_in_use(port) is True
        # And a fresh unused port is not in use (use a different probe).
    # Use a high random port that we know is free by binding to 0 then closing.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    probe.close()
    # Race-prone but usually works — small chance the OS reassigns.
    assert s._is_port_in_use(free_port) is False


# ---------------------------------------------------------------------------
# _check_process_startup_success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_process_startup_success_no_process_returns_false() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = None
    assert await s._check_process_startup_success(config) is False


@pytest.mark.asyncio
async def test_check_process_startup_success_running_returns_true() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = SimpleNamespace(poll=lambda: None)
    assert await s._check_process_startup_success(config) is True


@pytest.mark.asyncio
async def test_check_process_startup_success_died_calls_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    fake_proc = SimpleNamespace(
        poll=lambda: 1,
        communicate=lambda: ("", "boom"),
    )
    config.process = fake_proc

    async def fake_emit(event_type: str, name: str, msg: str) -> None:
        pass

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    assert await s._check_process_startup_success(config) is False
    assert "Process died" in (config.last_error or "")


# ---------------------------------------------------------------------------
# _handle_process_died
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_process_died_no_process_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = None

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    assert await s._handle_process_died(config, 1) is False


@pytest.mark.asyncio
async def test_handle_process_died_with_stderr(
    monkeypatch: pytest.MonkeyPatch,
    console: MagicMock,
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])
    config.process = SimpleNamespace(communicate=lambda: ("", "err"))

    async def fake_emit(event_type: str, name: str, msg: str) -> None:
        pass

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    assert await s._handle_process_died(config, 1) is False
    assert "Process died" in (config.last_error or "")
    assert "err" in (config.last_error or "")


# ---------------------------------------------------------------------------
# _finalize_service_startup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_service_startup_no_health_check_is_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.health_check_url = None

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    assert await s._finalize_service_startup(config) is True
    assert config.is_healthy is True


@pytest.mark.asyncio
async def test_finalize_service_startup_health_check_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(
        name="x", command=["echo"], health_check_url="http://x"
    )

    async def fake_health(_service: ServiceConfig) -> bool:
        return True

    async def fake_emit(event_type: str, name: str, msg: str) -> None:
        pass

    monkeypatch.setattr(s, "_health_check", fake_health)
    monkeypatch.setattr(s, "_emit_event", fake_emit)
    assert await s._finalize_service_startup(config) is True


@pytest.mark.asyncio
async def test_finalize_service_startup_health_check_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(
        name="x", command=["echo"], health_check_url="http://x"
    )

    async def fake_health(_service: ServiceConfig) -> bool:
        return False

    async def fake_emit(event_type: str, name: str, msg: str) -> None:
        pass

    monkeypatch.setattr(s, "_health_check", fake_health)
    monkeypatch.setattr(s, "_emit_event", fake_emit)
    assert await s._finalize_service_startup(config) is False


# ---------------------------------------------------------------------------
# _handle_service_start_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_service_start_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    assert await s._handle_service_start_error(config, RuntimeError("nope")) is False
    assert config.last_error == "nope"


@pytest.mark.asyncio
async def test_start_service_returns_false_when_launch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``_launch_service_process`` returns False, ``_start_service``
    also returns False without invoking ``_finalize_service_startup``."""
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])

    async def fake_launch(_service: ServiceConfig) -> bool:
        return False

    async def fake_finalize(_service: ServiceConfig) -> bool:
        raise AssertionError("should not be called")

    monkeypatch.setattr(s, "_launch_service_process", fake_launch)
    monkeypatch.setattr(s, "_finalize_service_startup", fake_finalize)
    assert await s._start_service(config) is False


@pytest.mark.asyncio
async def test_start_service_calls_finalize_on_launch_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When launch succeeds, ``_start_service`` calls ``_finalize_service_startup``."""
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])

    async def fake_launch(_service: ServiceConfig) -> bool:
        return True

    async def fake_finalize(_service: ServiceConfig) -> bool:
        return True

    monkeypatch.setattr(s, "_launch_service_process", fake_launch)
    monkeypatch.setattr(s, "_finalize_service_startup", fake_finalize)
    assert await s._start_service(config) is True


@pytest.mark.asyncio
async def test_start_service_handles_launch_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exception in ``_launch_service_process`` is caught and routed
    through ``_handle_service_start_error``."""
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])

    async def fake_launch(_service: ServiceConfig) -> bool:
        raise RuntimeError("launch boom")

    async def fake_handle(service: ServiceConfig, error: Exception) -> bool:
        return False

    monkeypatch.setattr(s, "_launch_service_process", fake_launch)
    monkeypatch.setattr(s, "_handle_service_start_error", fake_handle)
    assert await s._start_service(config) is False


@pytest.mark.asyncio
async def test_launch_service_process_runs(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    """``_launch_service_process`` calls subprocess.Popen, sleeps, then checks."""
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])

    fake_proc = SimpleNamespace(
        pid=12345,
        poll=lambda: None,
        communicate=lambda: ("", ""),
    )

    class _FakePopen:
        """Supports ``Popen[str]`` generic-subscript syntax."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            for attr, value in vars(fake_proc).items():
                setattr(self, attr, value)

        def __class_getitem__(cls, _item: Any) -> type:
            return cls

    monkeypatch.setattr(service_watchdog.subprocess, "Popen", _FakePopen)

    async def fake_check(_service: ServiceConfig) -> bool:
        return True

    async def fake_sleep(_secs: float) -> None:
        pass

    monkeypatch.setattr(s, "_check_process_startup_success", fake_check)
    monkeypatch.setattr(service_watchdog.asyncio, "sleep", fake_sleep)
    assert await s._launch_service_process(config) is True
    assert config.process is fake_proc or config.process.pid == 12345


@pytest.mark.asyncio
async def test_launch_service_process_returns_false_when_check_fails(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])

    fake_proc = SimpleNamespace(
        pid=12345,
        poll=lambda: None,
        communicate=lambda: ("", ""),
    )

    class _FakePopen:
        def __init__(self, *args: object, **kwargs: object) -> None:
            for attr, value in vars(fake_proc).items():
                setattr(self, attr, value)

        def __class_getitem__(cls, _item: Any) -> type:
            return cls

    monkeypatch.setattr(service_watchdog.subprocess, "Popen", _FakePopen)

    async def fake_check(_service: ServiceConfig) -> bool:
        return False

    async def fake_sleep(_secs: float) -> None:
        pass

    monkeypatch.setattr(s, "_check_process_startup_success", fake_check)
    monkeypatch.setattr(service_watchdog.asyncio, "sleep", fake_sleep)
    assert await s._launch_service_process(config) is False


@pytest.mark.asyncio
async def test_execute_monitoring_cycle_continue_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``_check_process_health`` returns False, the cycle returns False
    without invoking ``_perform_health_check_if_needed``."""
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])

    async def fake_check(_service: ServiceConfig) -> bool:
        return False

    async def fake_health_check_if_needed(_service: ServiceConfig) -> bool:
        raise AssertionError("should not be called")

    monkeypatch.setattr(s, "_check_process_health", fake_check)
    monkeypatch.setattr(
        s, "_perform_health_check_if_needed", fake_health_check_if_needed
    )
    assert await s._execute_monitoring_cycle(config) is False


@pytest.mark.asyncio
async def test_execute_monitoring_cycle_passes_through_health_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``_check_process_health`` returns True, the cycle delegates
    to ``_perform_health_check_if_needed`` and returns its result."""
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])

    async def fake_check(_service: ServiceConfig) -> bool:
        return True

    async def fake_health_check_if_needed(_service: ServiceConfig) -> bool:
        return False

    monkeypatch.setattr(s, "_check_process_health", fake_check)
    monkeypatch.setattr(
        s, "_perform_health_check_if_needed", fake_health_check_if_needed
    )
    assert await s._execute_monitoring_cycle(config) is False


@pytest.mark.asyncio
async def test_main_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    """``main()`` constructs a default watchdog and runs until interrupted."""
    captured: dict[str, object] = {}

    async def fake_start() -> None:
        raise KeyboardInterrupt()

    async def fake_stop() -> None:
        captured["stopped"] = True

    class _FakeWatchdog:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def start(self) -> None:
            raise KeyboardInterrupt()

        async def stop(self) -> None:
            captured["stopped"] = True

    async def fake_create(*args: object, **kwargs: object) -> Any:
        return _FakeWatchdog()

    monkeypatch.setattr(service_watchdog, "create_default_watchdog", fake_create)
    await service_watchdog.main()
    assert captured.get("stopped") is True


# ---------------------------------------------------------------------------
# _check_process_health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_process_health_running_returns_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = SimpleNamespace(poll=lambda: None)
    assert await s._check_process_health(config) is True


@pytest.mark.asyncio
async def test_check_process_health_died_triggers_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = SimpleNamespace(poll=lambda: 1)

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    async def fake_restart(_service: ServiceConfig) -> None:
        pass

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    monkeypatch.setattr(s, "_restart_service", fake_restart)
    assert await s._check_process_health(config) is False


@pytest.mark.asyncio
async def test_check_process_health_no_process_triggers_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = None

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    async def fake_restart(_service: ServiceConfig) -> None:
        pass

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    monkeypatch.setattr(s, "_restart_service", fake_restart)
    assert await s._check_process_health(config) is False


# ---------------------------------------------------------------------------
# _perform_health_check_if_needed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_perform_health_check_if_needed_no_url_returns_true() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.health_check_url = None
    assert await s._perform_health_check_if_needed(config) is True


@pytest.mark.asyncio
async def test_perform_health_check_if_needed_skips_when_recent() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(
        name="x", command=["echo"],
        health_check_url="http://x",
        health_check_interval=300.0,
    )
    config.last_health_check = time.time()
    assert await s._perform_health_check_if_needed(config) is True


@pytest.mark.asyncio
async def test_perform_health_check_if_needed_fails_triggers_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(
        name="x", command=["echo"], health_check_url="http://x",
    )
    config.last_health_check = 0.0

    async def fake_health(_service: ServiceConfig) -> bool:
        return False

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    async def fake_restart(_service: ServiceConfig) -> None:
        pass

    monkeypatch.setattr(s, "_health_check", fake_health)
    monkeypatch.setattr(s, "_emit_event", fake_emit)
    monkeypatch.setattr(s, "_restart_service", fake_restart)
    assert await s._perform_health_check_if_needed(config) is False


@pytest.mark.asyncio
async def test_perform_health_check_if_needed_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(
        name="x", command=["echo"], health_check_url="http://x",
    )
    config.last_health_check = 0.0

    async def fake_health(_service: ServiceConfig) -> bool:
        return True

    monkeypatch.setattr(s, "_health_check", fake_health)
    assert await s._perform_health_check_if_needed(config) is True
    assert config.is_healthy is True


# ---------------------------------------------------------------------------
# _monitor_service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monitor_service_exits_when_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    s.is_running = False
    config = ServiceConfig(name="x", command=["echo"])
    # Should return immediately without error.
    await s._monitor_service(config)


@pytest.mark.asyncio
async def test_monitor_service_handles_cycle_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    call_count = {"n": 0}

    async def fake_execute(_service: ServiceConfig) -> bool:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("boom")
        s.is_running = False
        return True

    async def fake_handle_error(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(s, "_execute_monitoring_cycle", fake_execute)
    monkeypatch.setattr(s, "_handle_monitoring_error", fake_handle_error)
    await s._monitor_service(config)


# ---------------------------------------------------------------------------
# _handle_monitoring_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_monitoring_error_sets_last_error(
    console: MagicMock,
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])
    config.last_error = None
    await s._handle_monitoring_error(config, RuntimeError("oops"))
    assert config.last_error == "oops"


# ---------------------------------------------------------------------------
# _health_check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_no_url_returns_true() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.health_check_url = None
    assert await s._health_check(config) is True


@pytest.mark.asyncio
async def test_health_check_status_200(monkeypatch: pytest.MonkeyPatch) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(
        name="x", command=["echo"], health_check_url="http://x"
    )

    async def fake_get_pool() -> Any:
        return _make_fake_pool(status=200)

    monkeypatch.setattr(service_watchdog, "get_http_pool", fake_get_pool)
    assert await s._health_check(config) is True


@pytest.mark.asyncio
async def test_health_check_status_500(monkeypatch: pytest.MonkeyPatch) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(
        name="x", command=["echo"], health_check_url="http://x"
    )

    async def fake_get_pool() -> Any:
        return _make_fake_pool(status=500)

    monkeypatch.setattr(service_watchdog, "get_http_pool", fake_get_pool)
    assert await s._health_check(config) is False


@pytest.mark.asyncio
async def test_health_check_exception_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(
        name="x", command=["echo"], health_check_url="http://x"
    )

    async def fake_get_pool() -> Any:
        raise RuntimeError("net fail")

    monkeypatch.setattr(service_watchdog, "get_http_pool", fake_get_pool)
    assert await s._health_check(config) is False


# ---------------------------------------------------------------------------
# _restart_service / _determine_restart_reason
# ---------------------------------------------------------------------------


def test_determine_restart_reason_process_died() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = None
    assert s._determine_restart_reason(config) == "Process died"


def test_determine_restart_reason_health_failed() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = SimpleNamespace(poll=lambda: None)
    assert s._determine_restart_reason(config) == "Health failed"


@pytest.mark.asyncio
async def test_restart_service_calls_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"], restart_delay=0.0)
    called: list[str] = []

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    async def fake_check_rate(*args: object, **kwargs: object) -> bool:
        called.append("rate")
        return True

    async def fake_terminate(*args: object, **kwargs: object) -> None:
        called.append("terminate")

    async def fake_wait(*args: object, **kwargs: object) -> None:
        called.append("wait")

    async def fake_execute(*args: object, **kwargs: object) -> None:
        called.append("execute")

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    monkeypatch.setattr(s, "_check_restart_rate_limit", fake_check_rate)
    monkeypatch.setattr(s, "_terminate_existing_process", fake_terminate)
    monkeypatch.setattr(s, "_wait_before_restart", fake_wait)
    monkeypatch.setattr(s, "_execute_service_restart", fake_execute)
    await s._restart_service(config)
    assert called == ["rate", "terminate", "wait", "execute"]


@pytest.mark.asyncio
async def test_restart_service_returns_when_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    called: list[str] = []

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    async def fake_check_rate(*args: object, **kwargs: object) -> bool:
        called.append("rate")
        return False

    async def fake_terminate(*args: object, **kwargs: object) -> None:
        called.append("terminate")

    monkeypatch.setattr(s, "_emit_event", fake_emit)
    monkeypatch.setattr(s, "_check_restart_rate_limit", fake_check_rate)
    monkeypatch.setattr(s, "_terminate_existing_process", fake_terminate)
    await s._restart_service(config)
    assert called == ["rate"]


# ---------------------------------------------------------------------------
# _check_restart_rate_limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_restart_rate_limit_under_threshold(
    console: MagicMock,
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(
        name="x", command=["echo"], max_restarts=3, restart_window=300.0,
    )
    now = time.time()
    config.restart_timestamps = [now - 10, now - 5]
    assert await s._check_restart_rate_limit(config, now) is True


@pytest.mark.asyncio
async def test_check_restart_rate_limit_at_threshold(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(
        name="x", command=["echo"], max_restarts=2, restart_window=300.0,
    )
    now = time.time()
    config.restart_timestamps = [now - 10, now - 5]

    async def fake_sleep(_secs: float) -> None:
        pass

    monkeypatch.setattr(service_watchdog.asyncio, "sleep", fake_sleep)
    assert await s._check_restart_rate_limit(config, now) is False
    assert config.last_error == "Restart rate limit exceeded"


@pytest.mark.asyncio
async def test_check_restart_rate_limit_drops_old_timestamps(
    console: MagicMock,
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(
        name="x", command=["echo"], max_restarts=2, restart_window=300.0,
    )
    now = time.time()
    # Old timestamps beyond the window are dropped.
    config.restart_timestamps = [now - 1000, now - 1000, now - 5]
    assert await s._check_restart_rate_limit(config, now) is True
    assert len(config.restart_timestamps) == 1


# ---------------------------------------------------------------------------
# _terminate_existing_process
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_terminate_no_process_returns(
    console: MagicMock,
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])
    config.process = None
    # No-op.
    await s._terminate_existing_process(config)


@pytest.mark.asyncio
async def test_terminate_timeout_expired_force_kills(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])
    killed: list[str] = []

    class _Proc:
        pid = 12345

        def terminate(self) -> None:
            killed.append("term")

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired(cmd="x", timeout=timeout or 0)

        def kill(self) -> None:
            killed.append("kill")

    config.process = _Proc()
    await s._terminate_existing_process(config)
    assert killed == ["term", "kill"]


@pytest.mark.asyncio
async def test_terminate_generic_exception_swallowed(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])

    class _Proc:
        def terminate(self) -> None:
            raise RuntimeError("boom")

        def wait(self, timeout: float | None = None) -> int:
            return -1

    config.process = _Proc()
    # Should not raise.
    await s._terminate_existing_process(config)


# ---------------------------------------------------------------------------
# _wait_before_restart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_before_restart_sleeps(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"], restart_delay=1.5)
    slept: list[float] = []

    async def fake_sleep(secs: float) -> None:
        slept.append(secs)

    monkeypatch.setattr(service_watchdog.asyncio, "sleep", fake_sleep)
    await s._wait_before_restart(config)
    assert slept == [1.5]


# ---------------------------------------------------------------------------
# _execute_service_restart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_service_restart_increments_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.restart_count = 0
    config.restart_timestamps = []

    async def fake_start(_service: ServiceConfig) -> bool:
        return True

    monkeypatch.setattr(s, "_start_service", fake_start)
    await s._execute_service_restart(config, time.time())
    assert config.restart_count == 1
    assert len(config.restart_timestamps) == 1


@pytest.mark.asyncio
async def test_execute_service_restart_failure_emits_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])

    async def fake_start(_service: ServiceConfig) -> bool:
        return False

    async def fake_emit(*args: object, **kwargs: object) -> None:
        pass

    captured: list[tuple[str, str, str]] = []

    async def fake_emit_capture(event_type: str, name: str, msg: str) -> None:
        captured.append((event_type, name, msg))

    monkeypatch.setattr(s, "_start_service", fake_start)
    monkeypatch.setattr(s, "_emit_event", fake_emit_capture)
    await s._execute_service_restart(config, time.time())
    assert captured == [("restart_failed", "x", "Restart failed")]


# ---------------------------------------------------------------------------
# _display_status / _update_status_display
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_display_status_breaks_when_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = ServiceWatchdog(services=[])
    s.is_running = False
    await s._display_status()  # no-op


@pytest.mark.asyncio
async def test_display_status_continues_when_running(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    s.is_running = True
    call_count = {"n": 0}

    async def fake_update() -> None:
        call_count["n"] += 1
        if call_count["n"] >= 1:
            s.is_running = False

    async def fake_sleep(secs: float) -> None:
        pass

    monkeypatch.setattr(s, "_update_status_display", fake_update)
    monkeypatch.setattr(service_watchdog.asyncio, "sleep", fake_sleep)
    await s._display_status()
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_display_status_handles_update_exception(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    s = ServiceWatchdog(services=[], console=console)
    s.is_running = True
    call_count = {"n": 0}

    async def fake_update() -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("display boom")
        s.is_running = False

    async def fake_sleep(secs: float) -> None:
        pass

    monkeypatch.setattr(s, "_update_status_display", fake_update)
    monkeypatch.setattr(service_watchdog.asyncio, "sleep", fake_sleep)
    await s._display_status()
    assert call_count["n"] >= 1


@pytest.mark.asyncio
async def test_update_status_display_runs(console: MagicMock) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])
    config.process = SimpleNamespace(poll=lambda: None)
    config.is_healthy = True
    s.services = [config]
    await s._update_status_display()
    console.print.assert_called()


def test_create_status_table_columns() -> None:
    s = ServiceWatchdog(services=[])
    table = s._create_status_table()
    assert table is not None
    column_styles = [c.style for c in table.columns]
    assert "cyan" in column_styles


def test_get_service_status_running() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = SimpleNamespace(poll=lambda: None)
    assert "Running" in s._get_service_status(config)


def test_get_service_status_stopped() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.process = None
    assert "Stopped" in s._get_service_status(config)


def test_get_service_health_no_url() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"])
    config.health_check_url = None
    assert "N / A" in s._get_service_health(config)


def test_get_service_health_healthy() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"], health_check_url="http://x")
    config.is_healthy = True
    assert "Healthy" in s._get_service_health(config)


def test_get_service_health_unhealthy() -> None:
    s = ServiceWatchdog(services=[])
    config = ServiceConfig(name="x", command=["echo"], health_check_url="http://x")
    config.is_healthy = False
    assert "Unhealthy" in s._get_service_health(config)


def test_format_error_message_none() -> None:
    s = ServiceWatchdog(services=[])
    assert "None" in s._format_error_message(None)


def test_format_error_message_short() -> None:
    s = ServiceWatchdog(services=[])
    assert s._format_error_message("boom") == "boom"


def test_format_error_message_long_truncated() -> None:
    s = ServiceWatchdog(services=[])
    long = "x" * 100
    formatted = s._format_error_message(long)
    assert formatted.endswith("...")
    assert len(formatted) < 50


# ---------------------------------------------------------------------------
# _emit_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_event_no_queue() -> None:
    s = ServiceWatchdog(services=[])
    await s._emit_event("started", "x", "msg")  # no-op


@pytest.mark.asyncio
async def test_emit_event_with_queue() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    s = ServiceWatchdog(services=[], event_queue=queue)
    await s._emit_event("started", "x", "msg")
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["type"] == "started"
    assert event["service"] == "x"
    assert event["message"] == "msg"


@pytest.mark.asyncio
async def test_emit_event_swallows_queue_put_exception() -> None:
    """A failing queue.put is swallowed silently."""
    queue = MagicMock()
    queue.put = MagicMock(side_effect=RuntimeError("queue down"))

    class _QueueProxy:
        @staticmethod
        async def put(_event: dict[str, Any]) -> None:
            raise RuntimeError("queue down")

    s = ServiceWatchdog(services=[], event_queue=_QueueProxy())  # type: ignore[arg-type]
    await s._emit_event("started", "x", "msg")  # no raise


# ---------------------------------------------------------------------------
# _cleanup / stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_is_noop() -> None:
    s = ServiceWatchdog(services=[])
    await s._cleanup()


@pytest.mark.asyncio
async def test_stop_no_process() -> None:
    s = ServiceWatchdog(services=[])
    s.is_running = True
    config = ServiceConfig(name="x", command=["echo"])
    s.services = [config]
    await s.stop()
    assert s.is_running is False


@pytest.mark.asyncio
async def test_stop_with_running_process(console: MagicMock) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])

    class _Proc:
        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: float | None = None) -> int:
            return -1

        def kill(self) -> None:
            self.killed = True

    config.process = _Proc()
    s.services = [config]
    s.is_running = True
    await s.stop()
    assert config.process.terminated is True
    assert s.is_running is False


@pytest.mark.asyncio
async def test_stop_timeout_expired_force_kills(console: MagicMock) -> None:
    s = ServiceWatchdog(services=[], console=console)
    config = ServiceConfig(name="x", command=["echo"])

    class _Proc:
        def __init__(self) -> None:
            self.killed = False

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired(cmd="x", timeout=timeout or 0)

        def kill(self) -> None:
            self.killed = True

    config.process = _Proc()
    s.services = [config]
    s.is_running = True
    await s.stop()
    assert config.process.killed is True


# ---------------------------------------------------------------------------
# create_default_watchdog
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_default_watchdog_returns_watchdog() -> None:
    watchdog = await create_default_watchdog()
    assert isinstance(watchdog, ServiceWatchdog)
    assert len(watchdog.services) == 1
    assert watchdog.services[0].name == "MCP Server"
    # The command is the python interpreter + module entry.
    assert "crackerjack" in " ".join(watchdog.services[0].command)


@pytest.mark.asyncio
async def test_create_default_watchdog_with_queue() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    watchdog = await create_default_watchdog(event_queue=queue)
    assert watchdog.event_queue is queue
    assert service_watchdog.watchdog_event_queue is queue


# ---------------------------------------------------------------------------
# start (integration-ish)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_runs_full_pipeline(
    monkeypatch: pytest.MonkeyPatch, console: MagicMock
) -> None:
    """A complete ``start()`` invocation that gets cancelled after one cycle."""
    config = ServiceConfig(name="x", command=["echo"], restart_delay=0.0)

    async def fake_get_pool() -> Any:
        return _make_fake_pool(status=200)

    monkeypatch.setattr(service_watchdog, "get_http_pool", fake_get_pool)
    monkeypatch.setattr(service_watchdog, "subprocess_popen_factory", None, raising=False)

    # Patch subprocess.Popen inside the watchdog module.
    monkeypatch.setattr(
        service_watchdog.subprocess, "Popen",
        lambda *a, **kw: SimpleNamespace(
            pid=12345, poll=lambda: None, communicate=lambda: ("", ""),
            wait=lambda timeout=None: 0, terminate=lambda: None, kill=lambda: None,
        ),
    )

    watchdog = ServiceWatchdog(services=[config], console=console)

    # Run start() and cancel after one monitoring cycle.
    task = asyncio.create_task(watchdog.start())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
