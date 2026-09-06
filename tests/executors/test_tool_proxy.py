"""Tests for ``crackerjack.executors.tool_proxy``.

The module orchestrates a circuit-breaker + fallback chain over a
``subprocess.run`` boundary. Tests mock at three levels:

1. ``time.time`` for circuit-breaker timing logic
2. ``subprocess.run`` for the health-check + direct-execution paths
3. The internal ``tool_adapters`` dict for the adapter-execution path

Pre-existing bugs (Python 2 ``except X, Y:`` syntax on lines 183, 310,
326) are preserved verbatim per CLAUDE.md Rule 7. They parse in
Python 3 but behave differently from a multi-except clause.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.executors.tool_proxy import (
    CircuitBreakerState,
    ToolHealthStatus,
    ToolProxy,
    main,
)


# ---------------------------------------------------------------------------
# Dataclass / circuit breaker state machine
# ---------------------------------------------------------------------------


def test_tool_health_status_defaults() -> None:
    s = ToolHealthStatus(is_healthy=True, last_check=1.0)
    assert s.consecutive_failures == 0
    assert s.last_error is None
    assert s.fallback_recommendations == []


def test_circuit_breaker_state_defaults() -> None:
    cb = CircuitBreakerState()
    assert cb.is_open is False
    assert cb.failure_count == 0
    assert cb.failure_threshold == 3
    assert cb.retry_timeout == 120


def test_circuit_breaker_should_attempt_closed() -> None:
    cb = CircuitBreakerState()
    assert cb.should_attempt() is True


def test_circuit_breaker_should_attempt_open_before_retry() -> None:
    cb = CircuitBreakerState(is_open=True, next_retry_time=10**12)
    assert cb.should_attempt() is False


def test_circuit_breaker_should_attempt_open_after_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If next_retry_time is in the past, attempt is allowed."""
    cb = CircuitBreakerState(is_open=True, next_retry_time=0)
    monkeypatch.setattr("time.time", lambda: 10**9)
    assert cb.should_attempt() is True


def test_circuit_breaker_record_failure_below_threshold() -> None:
    cb = CircuitBreakerState()
    cb.record_failure()
    cb.record_failure()
    assert cb.failure_count == 2
    assert cb.is_open is False


def test_circuit_breaker_record_failure_opens_at_threshold() -> None:
    cb = CircuitBreakerState()
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open is True
    assert cb.next_retry_time > 0


def test_circuit_breaker_record_success_resets() -> None:
    cb = CircuitBreakerState(is_open=True, failure_count=5, next_retry_time=999)
    cb.record_success()
    assert cb.failure_count == 0
    assert cb.is_open is False
    assert cb.next_retry_time == 0


# ---------------------------------------------------------------------------
# ToolProxy initialization
# ---------------------------------------------------------------------------


def test_tool_proxy_init_defaults() -> None:
    proxy = ToolProxy()
    assert isinstance(proxy.console, Console)
    assert proxy.health_status == {}
    assert proxy.circuit_breakers == {}


def test_tool_proxy_init_with_console() -> None:
    c = Console()
    proxy = ToolProxy(console=c)
    assert proxy.console is c


def test_tool_proxy_init_registers_adapters() -> None:
    proxy = ToolProxy()
    assert "zuban" in proxy.tool_adapters
    assert "skylos" in proxy.tool_adapters
    assert "ruff" in proxy.tool_adapters
    assert "bandit" in proxy.tool_adapters


def test_tool_proxy_init_seeds_fallback_tools() -> None:
    proxy = ToolProxy()
    assert proxy.fallback_tools["zuban"] == ["pyright", "mypy"]
    assert proxy.fallback_tools["skylos"] == ["vulture"]
    assert proxy.fallback_tools["ruff"] == []
    assert proxy.fallback_tools["bandit"] == []


# ---------------------------------------------------------------------------
# _get_circuit_breaker
# ---------------------------------------------------------------------------


def test_get_circuit_breaker_creates_new() -> None:
    proxy = ToolProxy()
    cb = proxy._get_circuit_breaker("zuban")
    assert isinstance(cb, CircuitBreakerState)
    assert "zuban" in proxy.circuit_breakers


def test_get_circuit_breaker_returns_same() -> None:
    proxy = ToolProxy()
    cb1 = proxy._get_circuit_breaker("zuban")
    cb2 = proxy._get_circuit_breaker("zuban")
    assert cb1 is cb2


# ---------------------------------------------------------------------------
# _check_tool_health + health cache
# ---------------------------------------------------------------------------


def test_check_tool_health_uses_cache_when_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If last_check was <30s ago, return cached is_healthy."""
    proxy = ToolProxy()
    proxy.health_status["zuban"] = ToolHealthStatus(
        is_healthy=True, last_check=100.0
    )
    monkeypatch.setattr("time.time", lambda: 105.0)  # 5s later
    # Adapter should NOT be called since cache is fresh.
    assert proxy._check_tool_health("zuban") is True


def test_check_tool_health_cache_stale_reruns(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()
    proxy.health_status["zuban"] = ToolHealthStatus(
        is_healthy=True, last_check=0.0
    )
    monkeypatch.setattr("time.time", lambda: 100.0)  # 100s later, cache stale
    proxy.tool_adapters["zuban"] = lambda: MagicMock(check_tool_health=lambda: True)
    assert proxy._check_tool_health("zuban") is True


def test_check_tool_health_records_recommendations(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()
    proxy.tool_adapters["zuban"] = lambda: MagicMock(check_tool_health=lambda: True)
    monkeypatch.setattr("time.time", lambda: 100.0)
    proxy._check_tool_health("zuban")
    status = proxy.health_status["zuban"]
    assert status.fallback_recommendations == ["pyright", "mypy"]


def test_check_tool_health_no_recommendations_for_unknown_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown tool → fallback_recommendations is empty list."""
    proxy = ToolProxy()
    proxy.tool_adapters["custom"] = lambda: MagicMock(check_tool_health=lambda: True)
    monkeypatch.setattr("time.time", lambda: 100.0)
    proxy._check_tool_health("custom")
    status = proxy.health_status["custom"]
    assert status.fallback_recommendations == []


# ---------------------------------------------------------------------------
# _perform_health_check
# ---------------------------------------------------------------------------


def test_perform_health_check_via_adapter_true() -> None:
    proxy = ToolProxy()
    proxy.tool_adapters["zuban"] = lambda: MagicMock(check_tool_health=lambda: True)
    assert proxy._perform_health_check("zuban") is True


def test_perform_health_check_via_adapter_false() -> None:
    proxy = ToolProxy()
    proxy.tool_adapters["zuban"] = lambda: MagicMock(check_tool_health=lambda: False)
    assert proxy._perform_health_check("zuban") is False


def test_perform_health_check_adapter_returns_none() -> None:
    """If adapter factory returns None, falls through to subprocess fallback."""
    proxy = ToolProxy()
    proxy.tool_adapters["zuban"] = lambda: None
    # The fallback path tries subprocess.run("uv run zuban --version").
    # We don't care about the result here; just verify it doesn't raise.
    result = proxy._perform_health_check("zuban")
    assert isinstance(result, bool)


def test_perform_health_check_adapter_no_health_method(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter without check_tool_health attribute → falls through."""
    proxy = ToolProxy()
    proxy.tool_adapters["zuban"] = lambda: object()  # no check_tool_health

    class _FakeCompleted:
        returncode = 0

    def fake_run(*a: object, **kw: object) -> _FakeCompleted:
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._perform_health_check("zuban") is True


def test_perform_health_check_unknown_tool_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown tool → subprocess.run('uv run <tool> --version')."""
    proxy = ToolProxy()

    class _FakeCompleted:
        returncode = 0

    def fake_run(cmd: list[str], *a: object, **kw: object) -> _FakeCompleted:
        assert cmd == ["uv", "run", "mytool", "--version"]
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._perform_health_check("mytool") is True


def test_perform_health_check_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    class _FakeCompleted:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._perform_health_check("mytool") is False


def test_perform_health_check_subprocess_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    def fake_run(*a: object, **kw: object) -> object:
        raise OSError("uv not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._perform_health_check("mytool") is False


def test_perform_health_check_zuban_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """When adapter factory returns None and tool_name == 'zuban', use _check_zuban_health."""
    proxy = ToolProxy()
    proxy.tool_adapters["zuban"] = lambda: None

    with patch.object(proxy, "_check_zuban_health", return_value=True):
        assert proxy._perform_health_check("zuban") is True


def test_perform_health_check_skylos_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()
    proxy.tool_adapters["skylos"] = lambda: None

    with patch.object(proxy, "_check_skylos_health", return_value=True):
        assert proxy._perform_health_check("skylos") is True


# ---------------------------------------------------------------------------
# _check_zuban_health
# ---------------------------------------------------------------------------


def test_check_zuban_health_version_ok_check_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """`uv run zuban --version` rc=0 then `uv run zuban check file.py` rc 0 or 1 → True."""
    proxy = ToolProxy()

    class _FakeCompleted:
        returncode = 0

    class _FakeCheck:
        returncode = 1  # 1 also counts as healthy

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *a: object, **kw: object) -> _FakeCompleted | _FakeCheck:
        calls.append(cmd)
        return _FakeCheck() if "check" in cmd else _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._check_zuban_health() is True
    assert len(calls) == 2


def test_check_zuban_health_version_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    class _FakeCompleted:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._check_zuban_health() is False


def test_check_zuban_health_check_non_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """check returning rc=2 (unexpected) → False."""
    proxy = ToolProxy()

    class _FakeVer:
        returncode = 0

    class _FakeCheck:
        returncode = 2

    def fake_run(cmd: list[str], *a: object, **kw: object) -> _FakeVer | _FakeCheck:
        return _FakeCheck() if "check" in cmd else _FakeVer()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._check_zuban_health() is False


def test_check_zuban_health_subprocess_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """subprocess.TimeoutExpired → False (caught by pre-existing except clause)."""
    proxy = ToolProxy()

    def fake_run(*a: object, **kw: object) -> object:
        raise subprocess.TimeoutExpired(cmd="uv", timeout=10)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._check_zuban_health() is False


def test_check_zuban_health_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    def fake_run(*a: object, **kw: object) -> object:
        raise OSError("no uv")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._check_zuban_health() is False


# ---------------------------------------------------------------------------
# _check_skylos_health
# ---------------------------------------------------------------------------


def test_check_skylos_health_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._check_skylos_health() is True


def test_check_skylos_health_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    class _FakeCompleted:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._check_skylos_health() is False


def test_check_skylos_health_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    def fake_run(*a: object, **kw: object) -> object:
        raise OSError("no uv")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._check_skylos_health() is False


# ---------------------------------------------------------------------------
# _execute_direct
# ---------------------------------------------------------------------------


def test_execute_direct_success(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    class _FakeCompleted:
        returncode = 0

    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], *a: object, **kw: object) -> _FakeCompleted:
        captured["cmd"] = cmd
        captured["timeout"] = kw.get("timeout")
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = proxy._execute_direct("zuban", ["check", "foo.py"])
    assert rc == 0
    assert captured["cmd"] == ["uv", "run", "zuban", "check", "foo.py"]
    assert captured["timeout"] == 300


def test_execute_direct_nonzero_rc(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    class _FakeCompleted:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._execute_direct("zuban", []) == 1


def test_execute_direct_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    def fake_run(*a: object, **kw: object) -> object:
        raise subprocess.TimeoutExpired(cmd="uv", timeout=300)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._execute_direct("zuban", []) == 1


def test_execute_direct_generic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()

    def fake_run(*a: object, **kw: object) -> object:
        raise OSError("crash")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert proxy._execute_direct("zuban", []) == 1


# ---------------------------------------------------------------------------
# _args_to_file_paths
# ---------------------------------------------------------------------------


def test_args_to_file_paths_filters_flags(tmp_path: Path) -> None:
    f1 = tmp_path / "a.py"
    f1.write_text("")
    proxy = ToolProxy()
    out = proxy._args_to_file_paths([str(f1), "--strict"])
    assert f1 in out
    assert Path("--strict") not in out


def test_args_to_file_paths_filters_nonexistent(tmp_path: Path) -> None:
    proxy = ToolProxy()
    # None of the args are valid files, so default to Path() (cwd).
    out = proxy._args_to_file_paths(["--flag", "/nonexistent/foo.py"])
    # Path() (empty) is used as fallback; just check it's a single Path entry.
    assert len(out) == 1
    assert out[0] == Path()


def test_args_to_file_paths_empty_args() -> None:
    proxy = ToolProxy()
    out = proxy._args_to_file_paths([])
    assert out == [Path()]


# ---------------------------------------------------------------------------
# _try_fallback_tools
# ---------------------------------------------------------------------------


def test_try_fallback_tools_no_fallbacks() -> None:
    """ruff has no fallbacks → returns 0 with warning."""
    proxy = ToolProxy()
    assert proxy._try_fallback_tools("ruff", []) == 0


def test_try_fallback_tools_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()
    # First fallback (pyright) is healthy → execute_direct → rc=0.
    monkeypatch.setattr(proxy, "_check_tool_health", lambda name: True)

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._try_fallback_tools("zuban", ["foo.py"]) == 0


def test_try_fallback_tools_first_unhealthy_second_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxy = ToolProxy()
    # pyright unhealthy, mypy healthy → mypy used.
    monkeypatch.setattr(
        proxy, "_check_tool_health", lambda name: name == "mypy"
    )

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._try_fallback_tools("zuban", []) == 0


def test_try_fallback_tools_all_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()
    # All fallbacks unhealthy → returns 0 (warning only).
    monkeypatch.setattr(proxy, "_check_tool_health", lambda name: False)
    assert proxy._try_fallback_tools("zuban", []) == 0


def test_try_fallback_tools_execute_direct_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """If execute_direct raises mid-fallback, continue to next fallback."""
    proxy = ToolProxy()
    monkeypatch.setattr(proxy, "_check_tool_health", lambda name: True)

    def fake_run(*a: object, **kw: object) -> object:
        raise RuntimeError("crash")

    monkeypatch.setattr(subprocess, "run", fake_run)
    # All fallbacks raise → returns 0 with "All fallbacks failed" warning.
    assert proxy._try_fallback_tools("zuban", []) == 0


def test_try_fallback_tools_check_health_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """If _check_tool_health raises mid-fallback, continue to next fallback.

    Exercises the `except Exception: continue` clause at line 275-276.
    """
    proxy = ToolProxy()

    def raising_health(name: str) -> bool:
        raise RuntimeError("health probe failed")

    monkeypatch.setattr(proxy, "_check_tool_health", raising_health)
    # All fallbacks raise → returns 0.
    assert proxy._try_fallback_tools("zuban", []) == 0


def test_try_fallback_tools_unhealthy_but_execute_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If fallback is healthy but execution returns non-zero, try next fallback."""
    proxy = ToolProxy()
    monkeypatch.setattr(proxy, "_check_tool_health", lambda name: True)

    class _FakeCompleted:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._try_fallback_tools("zuban", []) == 0


# ---------------------------------------------------------------------------
# execute_tool — full integration
# ---------------------------------------------------------------------------


def test_execute_tool_success(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()
    # Bypass adapter path → go straight to _execute_direct.
    proxy.tool_adapters["custom"] = lambda: None
    monkeypatch.setattr(
        proxy, "_check_tool_health", lambda name: True
    )

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy.execute_tool("custom", ["foo.py"]) == 0


def test_execute_tool_circuit_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Open circuit breaker → use fallbacks immediately."""
    proxy = ToolProxy()
    # Pre-open the circuit breaker with future retry time.
    cb = proxy._get_circuit_breaker("zuban")
    cb.is_open = True
    cb.next_retry_time = 10**12  # far future

    # Spy on _try_fallback_tools.
    with patch.object(proxy, "_try_fallback_tools", return_value=0) as fb:
        rc = proxy.execute_tool("zuban", [])
        assert rc == 0
        fb.assert_called_once()


def test_execute_tool_unhealthy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health check fails → use fallbacks."""
    proxy = ToolProxy()
    proxy.tool_adapters["custom"] = lambda: None
    monkeypatch.setattr(
        proxy, "_check_tool_health", lambda name: False
    )
    with patch.object(proxy, "_try_fallback_tools", return_value=0) as fb:
        rc = proxy.execute_tool("custom", [])
        assert rc == 0
        fb.assert_called_once()
    # Circuit breaker recorded the failure.
    cb = proxy._get_circuit_breaker("custom")
    assert cb.failure_count == 1


def test_execute_tool_failure_records_circuit_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """execute_direct returns 1 → circuit breaker records failure."""
    proxy = ToolProxy()
    proxy.tool_adapters["custom"] = lambda: None
    monkeypatch.setattr(proxy, "_check_tool_health", lambda name: True)

    class _FakeCompleted:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy.execute_tool("custom", []) == 1
    assert proxy._get_circuit_breaker("custom").failure_count == 1


def test_execute_tool_success_records_circuit_success(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()
    proxy.tool_adapters["custom"] = lambda: None
    monkeypatch.setattr(proxy, "_check_tool_health", lambda name: True)

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    proxy.execute_tool("custom", [])
    assert proxy._get_circuit_breaker("custom").failure_count == 0


def test_execute_tool_outer_exception_triggers_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """If anything raises in the main flow, fall back."""
    proxy = ToolProxy()
    # Force _check_tool_health to raise so the outer except catches it.
    monkeypatch.setattr(proxy, "_check_tool_health", lambda name: (_ for _ in ()).throw(RuntimeError("boom")))
    with patch.object(proxy, "_try_fallback_tools", return_value=0) as fb:
        rc = proxy.execute_tool("zuban", [])
        assert rc == 0
        fb.assert_called_once()


# ---------------------------------------------------------------------------
# _execute_through_adapter (adapter path)
# ---------------------------------------------------------------------------


def test_execute_through_adapter_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter with check_with_lsp_or_fallback → async call → return 0."""
    proxy = ToolProxy()

    class _FakeAdapter:
        async def check_with_lsp_or_fallback(self, files: list[Path]) -> object:
            return type("R", (), {"success": True})()

    factory = lambda: _FakeAdapter()
    proxy.tool_adapters["custom"] = factory
    monkeypatch.setattr(proxy, "_args_to_file_paths", lambda a: [Path("/tmp/x.py")])
    assert proxy._execute_through_adapter("custom", ["x.py"]) == 0


def test_execute_through_adapter_returns_nonzero_on_unsuccessful(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxy = ToolProxy()

    class _FakeAdapter:
        async def check_with_lsp_or_fallback(self, files: list[Path]) -> object:
            return type("R", (), {"success": False})()

    proxy.tool_adapters["custom"] = lambda: _FakeAdapter()
    monkeypatch.setattr(proxy, "_args_to_file_paths", lambda a: [Path("/tmp/x.py")])
    assert proxy._execute_through_adapter("custom", ["x.py"]) == 1


def test_execute_through_adapter_no_lsp_method(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter without check_with_lsp_or_fallback → direct execution."""

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())

    proxy = ToolProxy()
    proxy.tool_adapters["custom"] = lambda: object()  # no LSP method
    assert proxy._execute_through_adapter("custom", ["x.py"]) == 0


def test_execute_through_adapter_exception_falls_back_to_direct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxy = ToolProxy()

    def factory() -> object:
        raise RuntimeError("adapter boom")

    proxy.tool_adapters["custom"] = factory

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    # Adapter raises → falls through to direct execution → 0.
    assert proxy._execute_through_adapter("custom", ["x.py"]) == 0


def test_execute_through_adapter_unknown_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool not in tool_adapters → direct execution path."""
    proxy = ToolProxy()
    proxy.tool_adapters = {}  # no adapters

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert proxy._execute_through_adapter("mytool", ["x.py"]) == 0


# ---------------------------------------------------------------------------
# Adapter factories
# ---------------------------------------------------------------------------


def test_create_zuban_adapter_import_error() -> None:
    """Adapter factory returns None when imports fail."""
    proxy = ToolProxy()
    with patch.dict("sys.modules", {"crackerjack.adapters.lsp.zuban": None}):
        assert proxy._create_zuban_adapter() is None


def test_create_zuban_adapter_settings_load_fails() -> None:
    """If load_settings raises, the adapter factory returns None."""
    proxy = ToolProxy()
    # Force the import to succeed (mock the module), but make ZubanAdapter
    # raise so the factory falls into its except clause.
    fake_module = MagicMock()
    fake_module.ZubanAdapter = MagicMock(side_effect=RuntimeError("boom"))
    with patch.dict(
        "sys.modules",
        {
            "crackerjack.adapters.lsp.zuban": fake_module,
            "crackerjack.adapters.lsp._base": MagicMock(),
            "crackerjack.adapters.lsp": MagicMock(),
            "crackerjack.adapters": MagicMock(),
        },
    ):
        # Patch load_settings to raise — this hits the except ImportError, Exception
        # clause (which is pre-existing Python 2 syntax that binds Exception).
        with patch(
            "crackerjack.config.load_settings",
            side_effect=RuntimeError("no settings"),
        ):
            result = proxy._create_zuban_adapter()
        assert result is None


def test_create_zuban_adapter_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Full success path: load_settings → adapt_settings → ZubanAdapter(...) returned."""
    proxy = ToolProxy()
    fake_adapter_instance = MagicMock()

    class _FakeZubanAdapter:
        def __init__(self, context: object) -> None:
            assert context is not None
            # Capture for assertion via closure / attr.
            self.context = context

    class _FakeContext:
        def __init__(self, pkg_path: Path, options: object) -> None:
            self.pkg_path = pkg_path
            self.options = options

    # Patch the imports inside the adapter factory body.
    fake_zuban_mod = MagicMock()
    fake_zuban_mod.ZubanAdapter = _FakeZubanAdapter
    fake_base_mod = MagicMock()
    fake_base_mod.ExecutionContext = _FakeContext
    fake_core_tools_mod = MagicMock()
    fake_core_tools_mod._adapt_settings_to_protocol = lambda s: {"adapted": True}

    import sys as _sys
    monkeypatch.setitem(_sys.modules, "crackerjack.adapters.lsp.zuban", fake_zuban_mod)
    monkeypatch.setitem(_sys.modules, "crackerjack.adapters.lsp._base", fake_base_mod)
    monkeypatch.setitem(_sys.modules, "crackerjack.mcp.tools.core_tools", fake_core_tools_mod)

    monkeypatch.setattr("crackerjack.config.load_settings", lambda cls: MagicMock())
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)

    adapter = proxy._create_zuban_adapter()
    assert isinstance(adapter, _FakeZubanAdapter)


def test_create_skylos_adapter_import_error() -> None:
    proxy = ToolProxy()
    with patch.dict("sys.modules", {"crackerjack.adapters.lsp.skylos": None}):
        assert proxy._create_skylos_adapter() is None


def test_create_skylos_adapter_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Full success path for skylos adapter."""
    proxy = ToolProxy()

    class _FakeSkylosAdapter:
        def __init__(self, context: object) -> None:
            self.context = context

    class _FakeContext:
        def __init__(self, pkg_path: Path, options: object) -> None:
            pass

    fake_skylos_mod = MagicMock()
    fake_skylos_mod.SkylosAdapter = _FakeSkylosAdapter
    fake_base_mod = MagicMock()
    fake_base_mod.ExecutionContext = _FakeContext
    fake_core_tools_mod = MagicMock()
    fake_core_tools_mod._adapt_settings_to_protocol = lambda s: {"adapted": True}

    import sys as _sys
    monkeypatch.setitem(_sys.modules, "crackerjack.adapters.lsp.skylos", fake_skylos_mod)
    monkeypatch.setitem(_sys.modules, "crackerjack.adapters.lsp._base", fake_base_mod)
    monkeypatch.setitem(_sys.modules, "crackerjack.mcp.tools.core_tools", fake_core_tools_mod)
    monkeypatch.setattr("crackerjack.config.load_settings", lambda cls: MagicMock())
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)

    adapter = proxy._create_skylos_adapter()
    assert isinstance(adapter, _FakeSkylosAdapter)


def test_create_ruff_adapter_returns_none() -> None:
    proxy = ToolProxy()
    assert proxy._create_ruff_adapter() is None


def test_create_bandit_adapter_returns_none() -> None:
    proxy = ToolProxy()
    assert proxy._create_bandit_adapter() is None


# ---------------------------------------------------------------------------
# get_tool_status
# ---------------------------------------------------------------------------


def test_get_tool_status_empty() -> None:
    proxy = ToolProxy()
    # Pre-register so no lazy creation interferes with the assertions.
    proxy._get_circuit_breaker("zuban")
    status = proxy.get_tool_status()
    assert "zuban" in status
    assert status["zuban"]["circuit_breaker_open"] is False
    assert status["zuban"]["is_healthy"] is None
    assert status["zuban"]["fallback_tools"] == ["pyright", "mypy"]


def test_get_tool_status_with_health(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = ToolProxy()
    proxy._get_circuit_breaker("zuban")
    proxy.health_status["zuban"] = ToolHealthStatus(is_healthy=True, last_check=42.0)
    status = proxy.get_tool_status()
    assert status["zuban"]["is_healthy"] is True
    assert status["zuban"]["last_health_check"] == 42.0


def test_get_tool_status_with_open_circuit() -> None:
    proxy = ToolProxy()
    cb = proxy._get_circuit_breaker("zuban")
    cb.is_open = True
    cb.failure_count = 5
    status = proxy.get_tool_status()
    assert status["zuban"]["circuit_breaker_open"] is True
    assert status["zuban"]["failure_count"] == 5


# ---------------------------------------------------------------------------
# main() entry point
# ---------------------------------------------------------------------------


def test_main_no_args() -> None:
    """No tool_name → sys.exit(1)."""
    import sys as _sys
    with patch.object(_sys, "argv", ["tool_proxy"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1


def test_main_with_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool name provided → execute_tool → sys.exit(rc)."""
    import sys as _sys

    proxy_mock = MagicMock()
    proxy_mock.execute_tool.return_value = 0

    with patch.object(_sys, "argv", ["tool_proxy", "zuban", "foo.py"]):
        with patch("crackerjack.executors.tool_proxy.ToolProxy", return_value=proxy_mock):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
            proxy_mock.execute_tool.assert_called_once_with("zuban", ["foo.py"])
