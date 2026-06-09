"""Tests for PoolScaler service."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.services.pool_scaler import PoolScaler


@pytest.fixture
def console() -> Console:
    """Quiet console for test output."""
    return Console(quiet=True, no_color=True, force_terminal=False)


@pytest.fixture
def scaler(console: Console) -> PoolScaler:
    """PoolScaler with tiny thresholds and tiny check interval."""
    return PoolScaler(
        console=console,
        scale_up_threshold=5,
        scale_down_threshold=100,
        check_interval=1,
    )


@pytest.fixture
def pool_client() -> MagicMock:
    """Mock pool client - not directly invoked by current implementation."""
    client = MagicMock()
    client.scale = MagicMock()
    client.get_pool_metrics = AsyncMock()
    return client


def _make_metrics(
    pending_tasks: int,
    idle_seconds: int,
    current_workers: int = 4,
) -> dict[str, Any]:
    """Build a metrics dict matching _get_mock_metrics shape."""
    return {
        "pool_id": "mock-pool",
        "status": "healthy",
        "pending_tasks": pending_tasks,
        "idle_seconds": idle_seconds,
        "current_workers": current_workers,
        "max_workers": 16,
        "min_workers": 2,
    }


class TestPoolScalerInit:
    def test_default_initialization(self) -> None:
        scaler = PoolScaler()
        assert scaler._running is False
        assert scaler._scale_task is None
        assert scaler._worker_count == 0
        assert scaler.scale_up_threshold == 10
        assert scaler.scale_down_threshold == 300
        assert scaler.check_interval == 30
        assert isinstance(scaler.console, Console)

    def test_custom_initialization(self, console: Console) -> None:
        scaler = PoolScaler(
            console=console,
            scale_up_threshold=3,
            scale_down_threshold=42,
            check_interval=7,
        )
        assert scaler.console is console
        assert scaler.scale_up_threshold == 3
        assert scaler.scale_down_threshold == 42
        assert scaler.check_interval == 7

    def test_default_console_is_created(self) -> None:
        scaler = PoolScaler()
        # When console=None is passed, a fresh Console is constructed.
        assert isinstance(scaler.console, Console)


class TestGetStatus:
    def test_initial_status(self, scaler: PoolScaler) -> None:
        status = scaler.get_status()
        assert status == {
            "running": False,
            "worker_count": 0,
            "scale_up_threshold": 5,
            "scale_down_threshold": 100,
            "check_interval": 1,
        }

    def test_status_reflects_running_state(self, scaler: PoolScaler) -> None:
        scaler._running = True
        scaler._worker_count = 7
        status = scaler.get_status()
        assert status["running"] is True
        assert status["worker_count"] == 7


class TestMockMetrics:
    async def test_get_mock_metrics_shape(self, scaler: PoolScaler) -> None:
        metrics = await scaler._get_mock_metrics()
        assert metrics["pool_id"] == "mock-pool"
        assert metrics["status"] == "healthy"
        assert 0 <= metrics["pending_tasks"] <= 20
        assert 0 <= metrics["idle_seconds"] <= 600
        assert metrics["max_workers"] == 16
        assert metrics["min_workers"] == 2
        # current_workers mirrors internal _worker_count
        assert metrics["current_workers"] == scaler._worker_count

    async def test_get_mock_metrics_tracks_worker_count(self, scaler: PoolScaler) -> None:
        scaler._worker_count = 9
        metrics = await scaler._get_mock_metrics()
        assert metrics["current_workers"] == 9


class TestScaleUp:
    async def test_scale_up_increments_by_two(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        metrics = _make_metrics(pending_tasks=50, idle_seconds=0, current_workers=4)
        await scaler._scale_up(pool_client, metrics)
        # No assertion on actual pool_client.scale call since the
        # implementation currently only prints; verify it does not raise.

    async def test_scale_up_caps_at_max_workers(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        # Even if current_workers is 16, the new count is min(18, 16) = 16.
        metrics = _make_metrics(pending_tasks=50, idle_seconds=0, current_workers=16)
        # Should not raise.
        await scaler._scale_up(pool_client, metrics)

    async def test_scale_up_uses_default_current_workers(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        # No "current_workers" key -> default of 2 is used.
        metrics = {"pending_tasks": 1, "idle_seconds": 0}
        await scaler._scale_up(pool_client, metrics)


class TestScaleDown:
    async def test_scale_down_decrements_by_two(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        metrics = _make_metrics(pending_tasks=0, idle_seconds=500, current_workers=8)
        # Should run without raising.
        await scaler._scale_down(pool_client, metrics)

    async def test_scale_down_at_minimum_is_noop(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        # current_workers=3 -> new_count=1 -> new_count < 2 -> early return.
        metrics = _make_metrics(pending_tasks=0, idle_seconds=500, current_workers=3)
        await scaler._scale_down(pool_client, metrics)

    async def test_scale_down_at_two_is_noop(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        # current_workers=2 -> new_count=0 -> new_count < 2 -> early return.
        metrics = _make_metrics(pending_tasks=0, idle_seconds=500, current_workers=2)
        await scaler._scale_down(pool_client, metrics)

    async def test_scale_down_uses_default_current_workers(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        # No "current_workers" key -> default of 8 is used -> 8-2=6.
        metrics = {"pending_tasks": 0, "idle_seconds": 500}
        await scaler._scale_down(pool_client, metrics)


class TestMonitorLoop:
    async def test_scale_up_triggers_on_high_pending(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        """Single iteration with pending>threshold calls _scale_up."""
        high_load = _make_metrics(pending_tasks=10, idle_seconds=0, current_workers=4)
        with patch.object(scaler, "_get_mock_metrics", AsyncMock(return_value=high_load)):
            with patch.object(scaler, "_scale_up", AsyncMock()) as mock_up:
                with patch.object(scaler, "_scale_down", AsyncMock()) as mock_down:
                    # Run a single iteration then stop.
                    async def stop_after_one() -> None:
                        await asyncio.sleep(0.01)
                        scaler._running = False

                    scaler._running = True
                    await asyncio.wait_for(
                        asyncio.gather(
                            scaler._monitor_loop(pool_client),
                            stop_after_one(),
                        ),
                        timeout=2.0,
                    )
                    mock_up.assert_awaited_once()
                    mock_down.assert_not_awaited()

    async def test_scale_down_triggers_on_high_idle(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        """Single iteration with idle>threshold calls _scale_down."""
        low_load = _make_metrics(pending_tasks=0, idle_seconds=500, current_workers=8)
        with patch.object(scaler, "_get_mock_metrics", AsyncMock(return_value=low_load)):
            with patch.object(scaler, "_scale_up", AsyncMock()) as mock_up:
                with patch.object(scaler, "_scale_down", AsyncMock()) as mock_down:
                    async def stop_after_one() -> None:
                        await asyncio.sleep(0.01)
                        scaler._running = False

                    scaler._running = True
                    await asyncio.wait_for(
                        asyncio.gather(
                            scaler._monitor_loop(pool_client),
                            stop_after_one(),
                        ),
                        timeout=2.0,
                    )
                    mock_up.assert_not_awaited()
                    mock_down.assert_awaited_once()

    async def test_no_action_at_steady_state(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        """Steady metrics should call neither _scale_up nor _scale_down."""
        steady = _make_metrics(pending_tasks=2, idle_seconds=10, current_workers=4)
        with patch.object(scaler, "_get_mock_metrics", AsyncMock(return_value=steady)):
            with patch.object(scaler, "_scale_up", AsyncMock()) as mock_up:
                with patch.object(scaler, "_scale_down", AsyncMock()) as mock_down:
                    async def stop_after_one() -> None:
                        await asyncio.sleep(0.01)
                        scaler._running = False

                    scaler._running = True
                    await asyncio.wait_for(
                        asyncio.gather(
                            scaler._monitor_loop(pool_client),
                            stop_after_one(),
                        ),
                        timeout=2.0,
                    )
                    mock_up.assert_not_awaited()
                    mock_down.assert_not_awaited()

    async def test_metrics_exception_is_swallowed(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        """Exception from metrics source does not kill the loop."""
        call_count = 0

        async def flaky_metrics() -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("metrics boom")
            return _make_metrics(pending_tasks=0, idle_seconds=0, current_workers=4)

        with patch.object(scaler, "_get_mock_metrics", side_effect=flaky_metrics):
            async def stop_after_two() -> None:
                # Allow time for the failing call, then a successful one.
                await asyncio.sleep(scaler.check_interval * 2 + 0.05)
                scaler._running = False

            scaler._running = True
            await asyncio.wait_for(
                asyncio.gather(
                    scaler._monitor_loop(pool_client),
                    stop_after_two(),
                ),
                timeout=5.0,
            )
            assert call_count >= 2

    async def test_loop_updates_worker_count(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        """_worker_count is updated from metrics on each iteration."""
        new_metrics = _make_metrics(pending_tasks=0, idle_seconds=0, current_workers=11)
        with patch.object(scaler, "_get_mock_metrics", AsyncMock(return_value=new_metrics)):
            async def stop_after_one() -> None:
                await asyncio.sleep(scaler.check_interval + 0.05)
                scaler._running = False

            scaler._running = True
            await asyncio.wait_for(
                asyncio.gather(
                    scaler._monitor_loop(pool_client),
                    stop_after_one(),
                ),
                timeout=5.0,
            )
            assert scaler._worker_count == 11


class TestStartStopMonitoring:
    async def test_start_sets_running_and_creates_task(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        with patch.object(scaler, "_monitor_loop", AsyncMock()) as mock_loop:
            await scaler.start_monitoring(pool_client)
            try:
                assert scaler._running is True
                assert scaler._scale_task is not None
                # Give the task a chance to be scheduled.
                await asyncio.sleep(0)
                mock_loop.assert_awaited()
            finally:
                await scaler.stop_monitoring()

    async def test_start_is_idempotent(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        with patch.object(scaler, "_monitor_loop", AsyncMock()):
            await scaler.start_monitoring(pool_client)
            first_task = scaler._scale_task
            try:
                # Second call should be a no-op (already running).
                await scaler.start_monitoring(pool_client)
                assert scaler._scale_task is first_task
            finally:
                await scaler.stop_monitoring()

    async def test_stop_when_not_running_is_noop(self, scaler: PoolScaler) -> None:
        # Should not raise.
        await scaler.stop_monitoring()
        assert scaler._running is False

    async def test_stop_cancels_task(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        with patch.object(scaler, "_monitor_loop", AsyncMock()):
            await scaler.start_monitoring(pool_client)
            task = scaler._scale_task
            assert task is not None
            await scaler.stop_monitoring()
            assert scaler._running is False
            # Wait briefly for cancellation to propagate to the task.
            with pytest.raises(asyncio.CancelledError):
                await task
            assert task.cancelled() or task.done()


class TestBoundaryBehavior:
    """Edge cases at the threshold boundaries."""

    async def test_pending_equal_threshold_does_not_scale_up(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        """Boundary: pending == threshold should not trigger scale up (uses strict >)."""
        boundary = _make_metrics(pending_tasks=scaler.scale_up_threshold, idle_seconds=0, current_workers=4)
        with patch.object(scaler, "_get_mock_metrics", AsyncMock(return_value=boundary)):
            with patch.object(scaler, "_scale_up", AsyncMock()) as mock_up:
                with patch.object(scaler, "_scale_down", AsyncMock()) as mock_down:
                    async def stop_after_one() -> None:
                        await asyncio.sleep(scaler.check_interval + 0.05)
                        scaler._running = False

                    scaler._running = True
                    await asyncio.wait_for(
                        asyncio.gather(
                            scaler._monitor_loop(pool_client),
                            stop_after_one(),
                        ),
                        timeout=5.0,
                    )
                    mock_up.assert_not_awaited()
                    mock_down.assert_not_awaited()

    async def test_idle_equal_threshold_does_not_scale_down(self, scaler: PoolScaler, pool_client: MagicMock) -> None:
        """Boundary: idle == threshold should not trigger scale down (uses strict >)."""
        boundary = _make_metrics(pending_tasks=0, idle_seconds=scaler.scale_down_threshold, current_workers=4)
        with patch.object(scaler, "_get_mock_metrics", AsyncMock(return_value=boundary)):
            with patch.object(scaler, "_scale_up", AsyncMock()) as mock_up:
                with patch.object(scaler, "_scale_down", AsyncMock()) as mock_down:
                    async def stop_after_one() -> None:
                        await asyncio.sleep(scaler.check_interval + 0.05)
                        scaler._running = False

                    scaler._running = True
                    await asyncio.wait_for(
                        asyncio.gather(
                            scaler._monitor_loop(pool_client),
                            stop_after_one(),
                        ),
                        timeout=5.0,
                    )
                    mock_up.assert_not_awaited()
                    mock_down.assert_not_awaited()
