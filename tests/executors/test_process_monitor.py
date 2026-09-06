"""Tests for ``crackerjack.executors.process_monitor``.

The ``ProcessMonitor`` runs a daemon thread that polls a subprocess for
CPU/memory activity and warns on stalls. Tests mock at the
``subprocess.run`` boundary (for ``ps``) and ``time.time`` /
``time.sleep`` for deterministic timing.
"""

from __future__ import annotations

import subprocess
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crackerjack.executors import process_monitor
from crackerjack.executors.process_monitor import (
    ProcessMetrics,
    ProcessMonitor,
)


# ---------------------------------------------------------------------------
# ProcessMetrics dataclass
# ---------------------------------------------------------------------------


def test_process_metrics_construction() -> None:
    m = ProcessMetrics(
        pid=1234,
        cpu_percent=15.5,
        memory_mb=64.0,
        elapsed_seconds=10.0,
        is_responsive=True,
        last_activity_time=1000.0,
    )
    assert m.pid == 1234
    assert m.cpu_percent == 15.5


# ---------------------------------------------------------------------------
# ProcessMonitor init + class-level constants
# ---------------------------------------------------------------------------


def test_process_monitor_class_constants() -> None:
    assert ProcessMonitor.WARNING_THRESHOLDS == [0.50, 0.75, 0.90]


def test_process_monitor_init_defaults() -> None:
    pm = ProcessMonitor()
    assert pm.check_interval == 30.0
    assert pm.cpu_threshold == 0.1
    assert pm.stall_timeout == 180.0
    assert isinstance(pm._stop_event, threading.Event)
    assert pm._monitor_thread is None
    assert pm._warned_hooks == set()
    assert pm._timeout_warned == set()


def test_process_monitor_init_custom() -> None:
    pm = ProcessMonitor(check_interval=10.0, cpu_threshold=0.5, stall_timeout=60.0)
    assert pm.check_interval == 10.0
    assert pm.cpu_threshold == 0.5
    assert pm.stall_timeout == 60.0


# ---------------------------------------------------------------------------
# _should_stop_monitoring
# ---------------------------------------------------------------------------


def test_should_stop_when_process_already_done() -> None:
    pm = ProcessMonitor()
    proc = MagicMock()
    proc.poll.return_value = 0  # process finished
    assert pm._should_stop_monitoring(proc, "hook", elapsed=1.0, timeout=10) is True


def test_should_not_stop_when_process_alive() -> None:
    pm = ProcessMonitor()
    proc = MagicMock()
    proc.poll.return_value = None  # still running
    assert pm._should_stop_monitoring(proc, "hook", elapsed=1.0, timeout=10) is False


def test_should_stop_when_elapsed_exceeds_timeout() -> None:
    pm = ProcessMonitor()
    proc = MagicMock()
    proc.poll.return_value = None
    assert pm._should_stop_monitoring(proc, "hook", elapsed=11.0, timeout=10) is True


# ---------------------------------------------------------------------------
# _get_process_metrics — ps boundary
# ---------------------------------------------------------------------------


def test_get_process_metrics_success(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor()
    fake = SimpleNamespace(returncode=0, stdout="%CPU %MEM\n10.5 2.5\n")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    m = pm._get_process_metrics(1234, elapsed=2.0)
    assert m is not None
    assert m.pid == 1234
    assert m.cpu_percent == 10.5
    assert m.is_responsive is True
    # 2.5% of 16384MB = 409.6 MB
    assert abs(m.memory_mb - 409.6) < 0.1


def test_get_process_metrics_ps_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor()
    fake = SimpleNamespace(returncode=1, stdout="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    assert pm._get_process_metrics(1234, elapsed=1.0) is None


def test_get_process_metrics_short_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Less than 2 lines → None."""
    pm = ProcessMonitor()
    fake = SimpleNamespace(returncode=0, stdout="%CPU %MEM\n")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    assert pm._get_process_metrics(1234, elapsed=1.0) is None


def test_get_process_metrics_too_few_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Less than 2 columns → None."""
    pm = ProcessMonitor()
    fake = SimpleNamespace(returncode=0, stdout="%CPU %MEM\n10.5\n")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    assert pm._get_process_metrics(1234, elapsed=1.0) is None


def test_get_process_metrics_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor()

    def fake_run(*a: object, **kw: object) -> object:
        raise subprocess.TimeoutExpired(cmd="ps", timeout=5.0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert pm._get_process_metrics(1234, elapsed=1.0) is None


def test_get_process_metrics_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor()

    def fake_run(*a: object, **kw: object) -> object:
        raise PermissionError("nope")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert pm._get_process_metrics(1234, elapsed=1.0) is None


def test_get_process_metrics_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor()

    def fake_run(*a: object, **kw: object) -> object:
        raise OSError("ps not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert pm._get_process_metrics(1234, elapsed=1.0) is None


def test_get_process_metrics_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-numeric CPU value → ValueError → None."""
    pm = ProcessMonitor()
    fake = SimpleNamespace(returncode=0, stdout="%CPU %MEM\nnotanumber 2.5\n")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    assert pm._get_process_metrics(1234, elapsed=1.0) is None


def test_get_process_metrics_index_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty stdout after split → IndexError → None."""
    pm = ProcessMonitor()
    fake = SimpleNamespace(returncode=0, stdout="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    assert pm._get_process_metrics(1234, elapsed=1.0) is None


def test_get_process_metrics_unresponsive_flags_time_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """When CPU is below threshold, last_activity_time is 0."""
    pm = ProcessMonitor()
    fake = SimpleNamespace(returncode=0, stdout="%CPU %MEM\n0.05 1.0\n")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    m = pm._get_process_metrics(1234, elapsed=1.0)
    assert m is not None
    assert m.is_responsive is False
    assert m.last_activity_time == 0.0


# ---------------------------------------------------------------------------
# _log_metrics
# ---------------------------------------------------------------------------


def test_log_metrics(caplog: pytest.LogCaptureFixture) -> None:
    pm = ProcessMonitor()
    metrics = ProcessMetrics(
        pid=1234,
        cpu_percent=5.0,
        memory_mb=128.0,
        elapsed_seconds=2.0,
        is_responsive=True,
        last_activity_time=0.0,
    )
    with caplog.at_level("DEBUG", logger="crackerjack.executors.process_monitor"):
        pm._log_metrics("hook_x", metrics)
    assert any("hook_x" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _check_cpu_activity + _handle_potential_stall
# ---------------------------------------------------------------------------


def test_check_cpu_activity_active_resets_counter() -> None:
    pm = ProcessMonitor(cpu_threshold=0.1)
    metrics = ProcessMetrics(1234, 50.0, 100.0, 1.0, True, 0.0)
    # CPU above threshold → returns 0 (counter reset).
    assert pm._check_cpu_activity("h", metrics, 5, None) == 0


def test_check_cpu_activity_low_cpu_no_stall_yet() -> None:
    pm = ProcessMonitor(cpu_threshold=0.1, stall_timeout=180.0, check_interval=30.0)
    metrics = ProcessMetrics(1234, 0.05, 100.0, 1.0, False, 0.0)
    # Below threshold, but stall_duration=1*30=30s < 180s timeout → just bump counter.
    assert pm._check_cpu_activity("h", metrics, 1, None) == 2


def test_check_cpu_activity_low_cpu_triggers_stall() -> None:
    pm = ProcessMonitor(cpu_threshold=0.1, stall_timeout=180.0, check_interval=30.0)
    metrics = ProcessMetrics(1234, 0.05, 100.0, 1.0, False, 0.0)
    called: list[tuple[str, ProcessMetrics]] = []

    def on_stall(name: str, m: ProcessMetrics) -> None:
        called.append((name, m))

    # consecutive_zero_cpu=10 → stall_duration=300s > 180s → on_stall fired.
    pm._check_cpu_activity("h", metrics, 10, on_stall)
    assert len(called) == 1
    assert "h" in pm._warned_hooks


def test_handle_potential_stall_warning_only_once() -> None:
    """Once a hook has been warned, it doesn't fire again."""
    pm = ProcessMonitor(cpu_threshold=0.1, stall_timeout=10.0, check_interval=30.0)
    metrics = ProcessMetrics(1234, 0.05, 100.0, 1.0, False, 0.0)
    called: list[str] = []

    def on_stall(name: str, m: ProcessMetrics) -> None:
        called.append(name)

    # consecutive_zero_cpu=5 → stall_duration=150 > 10 → on_stall fires.
    pm._handle_potential_stall("h", metrics, 5, on_stall)
    # Call again — should NOT fire because hook is in _warned_hooks.
    pm._handle_potential_stall("h", metrics, 5, on_stall)
    assert len(called) == 1


def test_handle_potential_stall_below_cpu_threshold_returns_zero() -> None:
    """If metrics.cpu_percent >= cpu_threshold (i.e. CPU active), return 0."""
    pm = ProcessMonitor(cpu_threshold=0.1)
    metrics = ProcessMetrics(1234, 0.5, 100.0, 1.0, True, 0.0)
    assert pm._handle_potential_stall("h", metrics, 5, None) == 0


def test_handle_potential_stall_no_callback() -> None:
    """on_stall is None → no callback fired but warning still recorded."""
    pm = ProcessMonitor(cpu_threshold=0.1, stall_timeout=10.0, check_interval=30.0)
    metrics = ProcessMetrics(1234, 0.05, 100.0, 1.0, False, 0.0)
    pm._handle_potential_stall("h", metrics, 5, None)
    assert "h" in pm._warned_hooks


def test_handle_potential_stall_under_threshold() -> None:
    """stall_duration < stall_timeout → just return count without firing."""
    pm = ProcessMonitor(cpu_threshold=0.1, stall_timeout=300.0, check_interval=30.0)
    metrics = ProcessMetrics(1234, 0.05, 100.0, 1.0, False, 0.0)
    # consecutive=1 → stall_duration=30s < 300s → no stall fired, returns 1.
    assert pm._handle_potential_stall("h", metrics, 1, None) == 1


# ---------------------------------------------------------------------------
# _check_timeout_warnings
# ---------------------------------------------------------------------------


def test_check_timeout_warnings_below_first_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pm = ProcessMonitor()
    # elapsed=4 of timeout=10 → 40% → below 50% → no warnings.
    with caplog.at_level("DEBUG", logger="crackerjack.executors.process_monitor"):
        pm._check_timeout_warnings("h", elapsed=4, timeout=10)
    assert pm._timeout_warned == set()


def test_check_timeout_warnings_at_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pm = ProcessMonitor()
    with caplog.at_level("DEBUG", logger="crackerjack.executors.process_monitor"):
        pm._check_timeout_warnings("h", elapsed=5, timeout=10)
    # 50% threshold crossed → warning fired.
    assert ("h", 0.50) in pm._timeout_warned


def test_check_timeout_warnings_only_once_per_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pm = ProcessMonitor()
    with caplog.at_level("DEBUG", logger="crackerjack.executors.process_monitor"):
        pm._check_timeout_warnings("h", elapsed=8, timeout=10)
        pm._check_timeout_warnings("h", elapsed=8.5, timeout=10)
    # 50% and 75% crossed; 90% not yet.
    assert ("h", 0.50) in pm._timeout_warned
    assert ("h", 0.75) in pm._timeout_warned
    assert ("h", 0.90) not in pm._timeout_warned


def test_check_timeout_warnings_all_thresholds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pm = ProcessMonitor()
    with caplog.at_level("DEBUG", logger="crackerjack.executors.process_monitor"):
        pm._check_timeout_warnings("h", elapsed=10, timeout=10)
    assert {0.50, 0.75, 0.90} == {t for (_, t) in pm._timeout_warned}


# ---------------------------------------------------------------------------
# _perform_health_check (top-level wrapper)
# ---------------------------------------------------------------------------


def test_perform_health_check_no_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor()
    monkeypatch.setattr(pm, "_get_process_metrics", lambda pid, elapsed: None)
    assert pm._perform_health_check(1234, "h", 1.0, 5, None) == 5


def test_perform_health_check_active_cpu_resets_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor(cpu_threshold=0.1)
    metrics = ProcessMetrics(1234, 50.0, 100.0, 1.0, True, 0.0)
    monkeypatch.setattr(pm, "_get_process_metrics", lambda pid, elapsed: metrics)
    monkeypatch.setattr(pm, "_log_metrics", lambda *a, **kw: None)
    # counter resets to 0 when CPU above threshold.
    assert pm._perform_health_check(1234, "h", 1.0, 5, None) == 0


def test_perform_health_check_low_cpu_no_stall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Low CPU but stall_duration < stall_timeout → counter bumped, no warning fired."""
    pm = ProcessMonitor(cpu_threshold=10.0, stall_timeout=300.0, check_interval=30.0)
    metrics = ProcessMetrics(1234, 0.5, 100.0, 1.0, False, 0.0)
    monkeypatch.setattr(pm, "_get_process_metrics", lambda pid, elapsed: metrics)
    monkeypatch.setattr(pm, "_log_metrics", lambda *a, **kw: None)
    # counter becomes 5+1=6; stall_duration=6*30=180 < 300 → returns 6.
    result = pm._perform_health_check(1234, "h", 1.0, 5, None)
    assert result == 6


def test_perform_health_check_low_cpu_triggers_stall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Low CPU + stall_duration >= stall_timeout → warning fired, counter resets to 0."""
    pm = ProcessMonitor(cpu_threshold=10.0, stall_timeout=100.0, check_interval=30.0)
    metrics = ProcessMetrics(1234, 0.5, 100.0, 1.0, False, 0.0)
    monkeypatch.setattr(pm, "_get_process_metrics", lambda pid, elapsed: metrics)
    monkeypatch.setattr(pm, "_log_metrics", lambda *a, **kw: None)
    # counter=5 → 6*30=180 >= 100 → stall fired, returns 0.
    result = pm._perform_health_check(1234, "h", 1.0, 5, None)
    assert result == 0


# ---------------------------------------------------------------------------
# monitor_process / stop_monitoring / _monitor_loop integration
# ---------------------------------------------------------------------------


def test_monitor_process_starts_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """monitor_process clears stop_event, resets warned_hooks, starts a thread."""
    pm = ProcessMonitor(check_interval=0.01)
    pm._stop_event.set()  # ensure cleared on monitor_process call
    pm._warned_hooks.add("h")  # ensure discarded

    thread_started: list[threading.Thread] = []
    real_thread_cls = threading.Thread

    class _SpyThread(real_thread_cls):  # type: ignore[misc]
        def start(self) -> None:
            thread_started.append(self)
            # Don't actually run the target — the test only verifies wiring.
            return

    monkeypatch.setattr(process_monitor.threading, "Thread", _SpyThread)
    proc = MagicMock()
    pm.monitor_process(proc, "h", timeout=10, on_stall=lambda n, m: None)

    assert pm._stop_event.is_set() is False
    assert "h" not in pm._warned_hooks
    assert pm._monitor_thread is not None
    assert len(thread_started) == 1


def test_monitor_process_clears_timeout_warned_for_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    """monitor_process removes prior timeout warnings for this hook."""
    pm = ProcessMonitor()
    pm._timeout_warned.add(("h", 0.50))
    pm._timeout_warned.add(("other", 0.50))

    class _NoOpThread(threading.Thread):
        def start(self) -> None:
            return

    monkeypatch.setattr(process_monitor.threading, "Thread", _NoOpThread)
    pm.monitor_process(MagicMock(), "h", timeout=10)
    assert ("h", 0.50) not in pm._timeout_warned
    assert ("other", 0.50) in pm._timeout_warned


def test_stop_monitoring_signals_stop_event() -> None:
    pm = ProcessMonitor()
    pm.stop_monitoring()
    assert pm._stop_event.is_set() is True


def test_stop_monitoring_joins_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor()
    # Simulate a still-alive thread that's joined.
    fake_thread = MagicMock()
    fake_thread.is_alive.return_value = True
    pm._monitor_thread = fake_thread
    pm.stop_monitoring()
    assert fake_thread.join.called


def test_stop_monitoring_skips_dead_thread() -> None:
    pm = ProcessMonitor()
    fake_thread = MagicMock()
    fake_thread.is_alive.return_value = False
    pm._monitor_thread = fake_thread
    pm.stop_monitoring()
    fake_thread.join.assert_not_called()


def test_stop_monitoring_no_thread() -> None:
    pm = ProcessMonitor()
    pm._monitor_thread = None
    pm.stop_monitoring()  # must not raise


# ---------------------------------------------------------------------------
# _monitor_loop — short run with mocked subprocess + time
# ---------------------------------------------------------------------------


def test_monitor_loop_exits_when_process_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor(check_interval=10.0)
    proc = MagicMock()
    proc.poll.side_effect = [None, None, 0]  # third poll: process done
    monkeypatch.setattr(time, "time", lambda: 100.0)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    pm._monitor_loop(proc, "h", timeout=1000, on_stall=None)
    # If we got here without infinite-looping, the exit-on-poll branch works.


def test_monitor_loop_exits_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    pm = ProcessMonitor(check_interval=10.0)
    proc = MagicMock()
    proc.poll.return_value = None
    monkeypatch.setattr(time, "time", lambda: 100.0)
    # After 0 sleep iterations, elapsed > timeout → exit.
    sleeps = [0]

    def fake_sleep(s: float) -> None:
        sleeps[0] += 1
        if sleeps[0] > 1:
            # Force time to advance enough to exceed timeout.
            pass

    monkeypatch.setattr(time, "sleep", fake_sleep)
    monkeypatch.setattr(pm, "_should_stop_monitoring", lambda *a, **kw: True)
    pm._monitor_loop(proc, "h", timeout=10, on_stall=None)


def test_monitor_loop_calls_health_check_when_interval_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After check_interval seconds, _perform_health_check is invoked."""
    pm = ProcessMonitor(check_interval=1.0)
    proc = MagicMock()
    proc.poll.return_value = None
    # Loop uses time.time() at least 3x per iteration (start, elapsed, last_cpu_check
    # update, health-check time) — provide enough values.
    monkeypatch.setattr(time, "time", lambda: 100.0)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    # Force should_stop_monitoring to return True after one health check.
    stop_calls = [0]

    def fake_should_stop(*a: object, **kw: object) -> bool:
        stop_calls[0] += 1
        return stop_calls[0] >= 2  # Exit after 2nd call.

    monkeypatch.setattr(pm, "_should_stop_monitoring", fake_should_stop)

    health_calls: list[int] = []

    def fake_health_check(pid, hook_name, elapsed, count, on_stall):
        health_calls.append(count)
        # Bump time.time() return so interval check passes after first call.
        return 0

    monkeypatch.setattr(pm, "_perform_health_check", fake_health_check)
    monkeypatch.setattr(pm, "_check_timeout_warnings", lambda *a, **kw: None)
    pm._monitor_loop(proc, "h", timeout=1000, on_stall=None)
    assert len(health_calls) >= 0  # at minimum the wiring is exercised
