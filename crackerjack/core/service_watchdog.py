"""
Service watchdog with timeout protection and automatic recovery.

This module provides comprehensive monitoring of crackerjack services
with automatic restart capabilities and hanging prevention.
"""

import asyncio
import contextlib
import logging
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.table import Table

from ..services.security_logger import get_security_logger
from .timeout_manager import TimeoutStrategy, get_timeout_manager

logger = logging.getLogger("crackerjack.service_watchdog")


class ServiceState(Enum):
    """Service states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ServiceConfig:
    """Configuration for a monitored service."""

    name: str
    command: list[str]
    health_check_url: str | None = None
    health_check_timeout: float = 5.0
    startup_timeout: float = 30.0
    shutdown_timeout: float = 10.0
    max_restarts: int = 5
    restart_delay: float = 5.0
    restart_backoff_multiplier: float = 2.0
    max_restart_delay: float = 300.0


@dataclass
class ServiceStatus:
    """Status of a monitored service."""

    config: ServiceConfig
    state: ServiceState = ServiceState.STOPPED
    process: subprocess.Popen[bytes] | None = None
    last_start_time: float = 0.0
    last_health_check: float = 0.0
    restart_count: int = 0
    consecutive_failures: int = 0
    last_error: str = ""
    health_check_failures: int = 0

    @property
    def uptime(self) -> float:
        """Get service uptime in seconds."""
        if self.state == ServiceState.RUNNING and self.last_start_time > 0:
            return time.time() - self.last_start_time
        return 0.0

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return (
            self.state == ServiceState.RUNNING
            and self.process is not None
            and self.process.poll() is None
            and self.health_check_failures < 3
        )


class ServiceWatchdog:
    """Watchdog for monitoring and managing services with timeout protection."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.timeout_manager = get_timeout_manager()
        self.services: dict[str, ServiceStatus] = {}
        self.is_running = False
        self.monitor_task: asyncio.Task[None] | None = None

        # Default service configurations
        self.default_configs = {
            "mcp_server": ServiceConfig(
                name="MCP Server",
                command=["python", "-m", "crackerjack", "--start-mcp-server"],
                startup_timeout=30.0,
                shutdown_timeout=15.0,
            ),
            "websocket_server": ServiceConfig(
                name="WebSocket Server",
                command=["python", "-m", "crackerjack", "--start-websocket-server"],
                health_check_url="http://localhost:8675/",
                health_check_timeout=3.0,
                startup_timeout=20.0,
                shutdown_timeout=10.0,
            ),
        }

    def add_service(self, service_id: str, config: ServiceConfig) -> None:
        """Add a service to monitor."""
        self.services[service_id] = ServiceStatus(config=config)
        logger.info(f"Added service {service_id} to watchdog")

    def remove_service(self, service_id: str) -> None:
        """Remove a service from monitoring."""
        if service_id in self.services:
            asyncio.create_task(self.stop_service(service_id))
            del self.services[service_id]
            logger.info(f"Removed service {service_id} from watchdog")

    async def start_watchdog(self) -> None:
        """Start the watchdog monitoring."""
        if self.is_running:
            return

        self.is_running = True

        # Add default services
        for service_id, config in self.default_configs.items():
            self.add_service(service_id, config)

        # Start monitoring task with timeout protection
        self.monitor_task = asyncio.create_task(self._monitor_services())

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        self.console.print("[green]🐕 Service Watchdog started[/green]")
        logger.info("Service watchdog started")

    async def stop_watchdog(self) -> None:
        """Stop the watchdog and all monitored services."""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel monitoring task
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        # Stop all services
        stop_tasks = [
            self.stop_service(service_id) for service_id in self.services.keys()
        ]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        self.console.print("[yellow]🐕 Service Watchdog stopped[/yellow]")
        logger.info("Service watchdog stopped")

    async def start_service(self, service_id: str) -> bool:
        """Start a specific service with timeout protection."""
        if not self._validate_service_start_request(service_id):
            return False

        service = self.services[service_id]

        try:
            return await self._execute_service_startup(service_id, service)
        except Exception as e:
            return self._handle_service_start_failure(service, service_id, e)

    def _validate_service_start_request(self, service_id: str) -> bool:
        """Validate if service can be started."""
        if service_id not in self.services:
            return False

        service = self.services[service_id]
        return service.state not in (ServiceState.RUNNING, ServiceState.STARTING)

    async def _execute_service_startup(
        self, service_id: str, service: ServiceStatus
    ) -> bool:
        """Execute the service startup process with timeout protection."""
        async with self.timeout_manager.timeout_context(
            f"start_service_{service_id}",
            timeout=service.config.startup_timeout,
            strategy=TimeoutStrategy.FAIL_FAST,
        ):
            self._prepare_service_startup(service)

            if not await self._start_service_process(service):
                return False

            if not await self._verify_service_health(service):
                return False

            self._finalize_successful_startup(service, service_id)
            return True

    def _prepare_service_startup(self, service: ServiceStatus) -> None:
        """Prepare service for startup."""
        service.state = ServiceState.STARTING
        service.last_start_time = time.time()

    async def _start_service_process(self, service: ServiceStatus) -> bool:
        """Start the service process and verify it's running."""
        # Start the service process with security logging
        security_logger = get_security_logger()
        security_logger.log_subprocess_execution(
            command=service.config.command,
            purpose="service_watchdog_start",
        )

        service.process = subprocess.Popen(
            service.config.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        # Wait for process to stabilize
        await asyncio.sleep(2)

        # Check if process is still running
        if service.process.poll() is not None:
            service.state = ServiceState.FAILED
            service.last_error = "Process exited immediately"
            return False

        return True

    async def _verify_service_health(self, service: ServiceStatus) -> bool:
        """Verify service health if health check is configured."""
        if not service.config.health_check_url:
            return True

        health_ok = await self._perform_health_check(service)
        if not health_ok:
            await self._terminate_process(service)
            service.state = ServiceState.FAILED
            service.last_error = "Health check failed"
            return False

        return True

    def _finalize_successful_startup(
        self, service: ServiceStatus, service_id: str
    ) -> None:
        """Finalize successful service startup."""
        service.state = ServiceState.RUNNING
        service.consecutive_failures = 0
        service.health_check_failures = 0

        self.console.print(f"[green]✅ Started {service.config.name}[/green]")
        logger.info(f"Started service {service_id}")

    def _handle_service_start_failure(
        self, service: ServiceStatus, service_id: str, error: Exception
    ) -> bool:
        """Handle service startup failure."""
        service.state = ServiceState.FAILED
        service.last_error = str(error)
        service.consecutive_failures += 1

        if service.process:
            asyncio.create_task(self._terminate_process(service))

        self.console.print(
            f"[red]❌ Failed to start {service.config.name}: {error}[/red]"
        )
        logger.error(f"Failed to start service {service_id}: {error}")
        return False

    async def stop_service(self, service_id: str) -> bool:
        """Stop a specific service with timeout protection."""
        if service_id not in self.services:
            return False

        service = self.services[service_id]

        if service.state == ServiceState.STOPPED:
            return True

        try:
            async with self.timeout_manager.timeout_context(
                f"stop_service_{service_id}",
                timeout=service.config.shutdown_timeout,
                strategy=TimeoutStrategy.FAIL_FAST,
            ):
                service.state = ServiceState.STOPPING

                if service.process:
                    await self._terminate_process(service)

                service.state = ServiceState.STOPPED
                service.process = None

                self.console.print(f"[yellow]⏹️ Stopped {service.config.name}[/yellow]")
                logger.info(f"Stopped service {service_id}")
                return True

        except Exception as e:
            service.state = ServiceState.FAILED
            service.last_error = str(e)

            self.console.print(
                f"[red]❌ Failed to stop {service.config.name}: {e}[/red]"
            )
            logger.error(f"Failed to stop service {service_id}: {e}")
            return False

    async def _monitor_services(self) -> None:
        """Main monitoring loop with timeout protection."""
        while self.is_running:
            try:
                async with self.timeout_manager.timeout_context(
                    "monitor_services",
                    timeout=30.0,  # Monitor cycle timeout
                    strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
                ):
                    # Check each service
                    for service_id, service in self.services.items():
                        if not self.is_running:  # Check if shutdown requested
                            break

                        try:
                            await self._check_service_health(service_id, service)
                        except Exception as e:
                            logger.error(f"Error checking service {service_id}: {e}")

                # Wait before next check cycle
                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Monitor services error: {e}")
                await asyncio.sleep(30)  # Longer delay on error

    async def _check_service_health(
        self, service_id: str, service: ServiceStatus
    ) -> None:
        """Check health of a single service."""
        if service.state == ServiceState.RUNNING:
            # Check if process is still alive
            if service.process and service.process.poll() is not None:
                service.state = ServiceState.FAILED
                service.last_error = (
                    f"Process died with exit code {service.process.returncode}"
                )
                service.consecutive_failures += 1

                self.console.print(f"[red]💀 {service.config.name} process died[/red]")
                return

    async def _perform_health_check(self, service: ServiceStatus) -> bool:
        """Perform HTTP health check with timeout protection."""
        if not service.config.health_check_url:
            return True

        try:
            import aiohttp

            async with self.timeout_manager.timeout_context(
                "health_check",
                timeout=service.config.health_check_timeout,
                strategy=TimeoutStrategy.FAIL_FAST,
            ):
                async with aiohttp.ClientSession() as session:
                    async with session.get(service.config.health_check_url) as response:
                        return response.status == 200

        except Exception:
            return False

    async def _terminate_process(self, service: ServiceStatus) -> None:
        """Terminate service process gracefully with timeout."""
        if not service.process:
            return

        try:
            # Try graceful termination first
            service.process.terminate()

            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(
                    self._wait_for_process_exit(service.process), timeout=5.0
                )
            except TimeoutError:
                # Force kill if graceful shutdown fails
                service.process.kill()
                await asyncio.wait_for(
                    self._wait_for_process_exit(service.process), timeout=2.0
                )

        except Exception as e:
            logger.warning(f"Error terminating process: {e}")
            # Last resort: force kill
            with contextlib.suppress(Exception):
                service.process.kill()

    async def _wait_for_process_exit(self, process: subprocess.Popen[bytes]) -> None:
        """Wait for process to exit."""
        while process.poll() is None:
            await asyncio.sleep(0.1)

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: object) -> None:  # noqa: ARG001
            """Handle termination signals."""
            _ = frame  # Signal handler frame - required by signal API
            logger.info(f"Received signal {signum}, stopping watchdog...")
            asyncio.create_task(self.stop_watchdog())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def get_service_status(self, service_id: str) -> ServiceStatus | None:
        """Get status of a specific service."""
        return self.services.get(service_id)

    def get_all_services_status(self) -> dict[str, ServiceStatus]:
        """Get status of all services."""
        return self.services.copy()

    def print_status_report(self) -> None:
        """Print formatted status report."""
        self.console.print("\n[bold blue]🐕 Service Watchdog Status[/bold blue]")
        self.console.print("=" * 50)

        if not self.services:
            self.console.print("[dim]No services configured[/dim]")
            return

        table = Table()
        table.add_column("Service")
        table.add_column("Status")
        table.add_column("Uptime")

        for service in self.services.values():
            # Status emoji and color
            if service.state == ServiceState.RUNNING and service.is_healthy:
                status = "[green]🟢 Running[/green]"
            elif service.state == ServiceState.STARTING:
                status = "[yellow]🟡 Starting[/yellow]"
            elif service.state == ServiceState.STOPPING:
                status = "[yellow]🟡 Stopping[/yellow]"
            elif service.state == ServiceState.FAILED:
                status = "[red]🔴 Failed[/red]"
            elif service.state == ServiceState.TIMEOUT:
                status = "[red]⏰ Timeout[/red]"
            else:
                status = "[dim]⚫ Stopped[/dim]"

            # Format uptime
            uptime = service.uptime
            if uptime > 3600:
                uptime_str = f"{uptime / 3600:.1f}h"
            elif uptime > 60:
                uptime_str = f"{uptime / 60:.1f}m"
            elif uptime > 0:
                uptime_str = f"{uptime:.0f}s"
            else:
                uptime_str = "-"

            table.add_row(service.config.name, status, uptime_str)

        self.console.print(table)


# Global service watchdog instance
_global_watchdog: ServiceWatchdog | None = None


def get_service_watchdog(console: Console | None = None) -> ServiceWatchdog:
    """Get global service watchdog instance."""
    global _global_watchdog
    if _global_watchdog is None:
        _global_watchdog = ServiceWatchdog(console)
    return _global_watchdog
