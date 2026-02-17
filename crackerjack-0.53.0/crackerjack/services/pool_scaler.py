"""Pool Scaler for auto-scaling Mahavishnu worker pools.

This module monitors pool metrics and automatically scales workers up or down
based on load to maintain optimal resource utilization.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from rich.console import Console

logger = logging.getLogger(__name__)


class PoolScaler:
    """Auto-scale Mahavishnu pools based on load metrics.

    Monitors pending tasks and idle time to scale workers:
    - Scale UP when pending tasks > threshold
    - Scale DOWN when idle time > threshold
    """

    def __init__(
        self,
        console: Console | None = None,
        scale_up_threshold: int = 10,
        scale_down_threshold: int = 300,  # 5 minutes
        check_interval: int = 30,  # Check every 30 seconds
    ) -> None:
        """Initialize the pool scaler.

        Args:
            console: Optional console for output
            scale_up_threshold: Pending tasks threshold for scaling up
            scale_down_threshold: Idle seconds threshold for scaling down
            check_interval: Seconds between scaling checks
        """
        self.console = console or Console()
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.check_interval = check_interval
        self._running = False
        self._scale_task: asyncio.Task[None] | None = None
        self._worker_count = 0

    async def start_monitoring(
        self,
        pool_client: Any,
    ) -> None:
        """Start monitoring pool metrics and auto-scaling.

        Args:
            pool_client: Pool client with get_pool_health() method
        """
        if self._running:
            self.console.print("[yellow]⚠️ Scaler already running[/yellow]")
            return

        self._running = True
        self._scale_task = asyncio.create_task(self._monitor_loop(pool_client))
        self.console.print("[green]✅ Pool scaler started[/green]")

    async def stop_monitoring(self) -> None:
        """Stop monitoring and cleanup resources.

        Scales down to minimum workers before stopping.
        """
        if not self._running:
            return

        self._running = False

        if self._scale_task:
            self._scale_task.cancel()
            self.console.print("[dim]Scaling task cancelled[/dim]")

        self.console.print("[yellow]⚠️ Scaling down to minimum workers...[/yellow]")

        # TODO: Call pool_client.scale(pool_id, worker_count=min_workers)
        # This requires pool_client to have scale() method

        self.console.print("[green]✅ Pool scaler stopped[/green]")

    async def _monitor_loop(
        self,
        pool_client: Any,
    ) -> None:
        """Main monitoring loop - checks metrics and scales as needed.

        Args:
            pool_client: Pool client to query for metrics
        """
        try:
            while self._running:
                try:
                    # Get pool health metrics
                    # TODO: Replace with actual pool_client.get_pool_metrics() call
                    # For now, simulate metrics
                    metrics = await self._get_mock_metrics()

                    should_scale_up = (
                        metrics.get("pending_tasks", 0) > self.scale_up_threshold
                    )
                    should_scale_down = (
                        metrics.get("idle_seconds", 0) > self.scale_down_threshold
                    )

                    if should_scale_up:
                        await self._scale_up(pool_client, metrics)
                    elif should_scale_down:
                        await self._scale_down(pool_client, metrics)

                    # Update worker count
                    self._worker_count = metrics.get(
                        "current_workers", self._worker_count
                    )

                    # Wait before next check
                    await asyncio.sleep(self.check_interval)

                except asyncio.CancelledError:
                    logger.debug("Monitoring loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    # Continue running despite errors
                    await asyncio.sleep(self.check_interval)

        finally:
            self._running = False

    async def _scale_up(
        self,
        pool_client: Any,
        metrics: dict[str, Any],
    ) -> None:
        """Scale up pool workers.

        Args:
            pool_client: Pool client
            metrics: Current pool metrics
        """
        current_workers = metrics.get("current_workers", 2)
        new_worker_count = min(current_workers + 2, 16)  # Add 2 workers, max 16

        self.console.print(
            f"[cyan]⬆️ Scaling UP: {current_workers} → {new_worker_count} workers[/cyan]"
        )

        # TODO: Call pool_client.scale(pool_id, worker_count=new_worker_count)
        # await pool_client.scale(pool_id, worker_count=new_worker_count)
        self.console.print(
            f"[dim]  Scale up command queued (workers: {new_worker_count})[/dim]"
        )

    async def _scale_down(
        self,
        pool_client: Any,
        metrics: dict[str, Any],
    ) -> None:
        """Scale down pool workers.

        Args:
            pool_client: Pool client
            metrics: Current pool metrics
        """
        current_workers = metrics.get("current_workers", 8)
        new_worker_count = max(current_workers - 2, 2)  # Reduce by 2, min 2

        # Check if we'd go below minimum
        if new_worker_count < 2:
            self.console.print("[yellow]⚠️ Already at minimum workers (2)[/yellow]")
            return

        self.console.print(
            f"[yellow]⬇️ Scaling DOWN: {current_workers} → {new_worker_count} workers[/yellow]"
        )

        # TODO: Call pool_client.scale(pool_id, worker_count=new_worker_count)
        # await pool_client.scale(pool_id, worker_count=new_worker_count)
        self.console.print(
            f"[dim]  Scale down command queued (workers: {new_worker_count})[/dim]"
        )

    async def _get_mock_metrics(self) -> dict[str, Any]:
        """Get mock pool metrics for testing.

        Returns:
            Dictionary with simulated pool metrics
        """
        import random

        # Simulate varying load
        pending_tasks = random.randint(0, 20)
        idle_seconds = random.randint(0, 600)

        return {
            "pool_id": "mock-pool",
            "status": "healthy",
            "pending_tasks": pending_tasks,
            "idle_seconds": idle_seconds,
            "current_workers": self._worker_count,
            "max_workers": 16,
            "min_workers": 2,
        }

    def get_status(self) -> dict[str, Any]:
        """Get current scaler status.

        Returns:
            Dictionary with status information
        """
        return {
            "running": self._running,
            "worker_count": self._worker_count,
            "scale_up_threshold": self.scale_up_threshold,
            "scale_down_threshold": self.scale_down_threshold,
            "check_interval": self.check_interval,
        }
