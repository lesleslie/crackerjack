import asyncio
import contextlib
import logging
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum

from acb import console as acb_console
from acb.console import Console
from rich.panel import Panel
from rich.table import Table

from ..services.security_logger import get_security_logger
from .timeout_manager import TimeoutStrategy, get_timeout_manager

logger = logging.getLogger("crackerjack.service_watchdog")


class ServiceState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ServiceConfig:
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
        if self.state == ServiceState.RUNNING and self.last_start_time > 0:
            return time.time() - self.last_start_time
        return 0.0

    @property
    def is_healthy(self) -> bool:
        return (
            self.state == ServiceState.RUNNING
            and self.process is not None
            and self.process.poll() is None
            and self.health_check_failures < 3
        )


class ServiceWatchdog:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or acb_console
        self.timeout_manager = get_timeout_manager()
        self.services: dict[str, ServiceStatus] = {}
        self.is_running = False
        self.monitor_task: asyncio.Task[None] | None = None

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
                health_check_url="http: //localhost: 8675/",
                health_check_timeout=3.0,
                startup_timeout=20.0,
                shutdown_timeout=10.0,
            ),
            "zuban_lsp": ServiceConfig(
                name="Zuban LSP Server",
                command=["uv", "run", "zuban", "server"],
                startup_timeout=15.0,
                shutdown_timeout=10.0,
                max_restarts=5,
                restart_delay=5.0,
                restart_backoff_multiplier=2.0,
                max_restart_delay=300.0,
            ),
        }

    def add_service(self, service_id: str, config: ServiceConfig) -> None:
        self.services[service_id] = ServiceStatus(config=config)
        logger.info(f"Added service {service_id} to watchdog")

    def remove_service(self, service_id: str) -> None:
        if service_id in self.services:
            asyncio.create_task(self.stop_service(service_id))
            del self.services[service_id]
            logger.info(f"Removed service {service_id} from watchdog")

    async def start_watchdog(self) -> None:
        if self.is_running:
            return

        self.is_running = True

        for service_id, config in self.default_configs.items():
            self.add_service(service_id, config)

        self.monitor_task = asyncio.create_task(self._monitor_services())

        self._setup_signal_handlers()

        self.console.print("[green]🐕 Service Watchdog started[/green]")
        logger.info("Service watchdog started")

    async def stop_watchdog(self) -> None:
        if not self.is_running:
            return

        self.is_running = False

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        stop_tasks = [
            self.stop_service(service_id) for service_id in self.services.keys()
        ]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        self.console.print("[yellow]🐕 Service Watchdog stopped[/yellow]")
        logger.info("Service watchdog stopped")

    async def start_service(self, service_id: str) -> bool:
        if not self._validate_service_start_request(service_id):
            return False

        service = self.services[service_id]

        try:
            return await self._execute_service_startup(service_id, service)
        except Exception as e:
            return self._handle_service_start_failure(service, service_id, e)

    def _validate_service_start_request(self, service_id: str) -> bool:
        if service_id not in self.services:
            return False

        service = self.services[service_id]
        return service.state not in (ServiceState.RUNNING, ServiceState.STARTING)

    async def _execute_service_startup(
        self, service_id: str, service: ServiceStatus
    ) -> bool:
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
        service.state = ServiceState.STARTING
        service.last_start_time = time.time()

    async def _start_service_process(self, service: ServiceStatus) -> bool:
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

        await asyncio.sleep(2)

        if service.process.poll() is not None:
            service.state = ServiceState.FAILED
            service.last_error = "Process exited immediately"
            return False

        return True

    async def _verify_service_health(self, service: ServiceStatus) -> bool:
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
        service.state = ServiceState.RUNNING
        service.consecutive_failures = 0
        service.health_check_failures = 0

        self.console.print(f"[green]✅ Started {service.config.name}[/green]")
        logger.info(f"Started service {service_id}")

    def _handle_service_start_failure(
        self, service: ServiceStatus, service_id: str, error: Exception
    ) -> bool:
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
        while self.is_running:
            try:
                async with self.timeout_manager.timeout_context(
                    "monitor_services",
                    timeout=30.0,
                    strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
                ):
                    for service_id, service in self.services.items():
                        if not self.is_running:
                            break

                        try:
                            await self._check_service_health(service_id, service)
                        except Exception as e:
                            logger.error(f"Error checking service {service_id}: {e}")

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Monitor services error: {e}")
                await asyncio.sleep(30)

    async def _check_service_health(
        self, service_id: str, service: ServiceStatus
    ) -> None:
        if service.state == ServiceState.RUNNING:
            if service.process and service.process.poll() is not None:
                service.state = ServiceState.FAILED
                service.last_error = (
                    f"Process died with exit code {service.process.returncode}"
                )
                service.consecutive_failures += 1

                self.console.print(f"[red]💀 {service.config.name} process died[/red]")
                return

    async def _perform_health_check(self, service: ServiceStatus) -> bool:
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
        if not service.process:
            return

        try:
            service.process.terminate()

            try:
                await asyncio.wait_for(
                    self._wait_for_process_exit(service.process), timeout=5.0
                )
            except TimeoutError:
                service.process.kill()
                await asyncio.wait_for(
                    self._wait_for_process_exit(service.process), timeout=2.0
                )

        except Exception as e:
            logger.warning(f"Error terminating process: {e}")

            with contextlib.suppress(Exception):
                service.process.kill()

    async def _wait_for_process_exit(self, process: subprocess.Popen[bytes]) -> None:
        while process.poll() is None:
            await asyncio.sleep(0.1)

    def _setup_signal_handlers(self) -> None:
        def signal_handler(signum: int, frame: object) -> None:
            _ = frame
            logger.info(f"Received signal {signum}, stopping watchdog")
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.stop_watchdog())
            except RuntimeError:
                # No running loop; stop synchronously to avoid 'never awaited' warnings
                try:
                    asyncio.run(self.stop_watchdog())
                except RuntimeError:
                    # In case we're already within a running loop context where run() is invalid
                    with contextlib.suppress(Exception):
                        loop = asyncio.new_event_loop()
                        try:
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.stop_watchdog())
                        finally:
                            loop.close()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def get_service_status(self, service_id: str) -> ServiceStatus | None:
        return self.services.get(service_id)

    def get_all_services_status(self) -> dict[str, ServiceStatus]:
        return self.services.copy()

    def print_status_report(self) -> None:
        """Print detailed status report for all services."""
        self._print_report_header()

        if not self.services:
            self.console.print("[dim]No services configured[/dim]")
            return

        table = self._create_status_table()
        self.console.print(Panel(table, title="Service Status", border_style="blue"))

    def _print_report_header(self) -> None:
        """Print the status report header."""
        self.console.print("\n[bold blue]🐕 Service Watchdog Status[/bold blue]")
        self.console.print("=" * 50)

    def _create_status_table(self) -> Table:
        """Create and populate the status table."""
        table = Table()
        table.add_column("Service")
        table.add_column("Status")
        table.add_column("Uptime")

        for service in self.services.values():
            status_display = self._get_service_status_display(service)
            uptime_display = self._format_uptime(service.uptime)
            table.add_row(service.config.name, status_display, uptime_display)

        return table

    def _get_service_status_display(self, service: ServiceStatus) -> str:
        """Get formatted status display for a service."""
        status_map = {
            (ServiceState.RUNNING, True): "[green]🟢 Running[/green]",
            (ServiceState.STARTING, None): "[yellow]🟡 Starting[/yellow]",
            (ServiceState.STOPPING, None): "[yellow]🟡 Stopping[/yellow]",
            (ServiceState.FAILED, None): "[red]🔴 Failed[/red]",
            (ServiceState.TIMEOUT, None): "[red]⏰ Timeout[/red]",
        }

        # Check for running with healthy status first
        if service.state == ServiceState.RUNNING and service.is_healthy:
            return status_map[(ServiceState.RUNNING, True)]

        # Check other states
        status_key = (service.state, None)
        return status_map.get(status_key, "[dim]⚫ Stopped[/dim]")

    def _format_uptime(self, uptime: float) -> str:
        """Format uptime duration for display."""
        if uptime > 3600:
            return f"{uptime / 3600: .1f}h"
        elif uptime > 60:
            return f"{uptime / 60: .1f}m"
        elif uptime > 0:
            return f"{uptime: .0f}s"
        return "-"


_global_watchdog: ServiceWatchdog | None = None


def get_service_watchdog(console: Console | None = None) -> ServiceWatchdog:
    global _global_watchdog
    if _global_watchdog is None:
        _global_watchdog = ServiceWatchdog(console)
    return _global_watchdog
