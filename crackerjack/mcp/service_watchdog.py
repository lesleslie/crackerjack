import asyncio
import socket
import subprocess
import sys
import time
from contextlib import suppress
from typing import Any

import aiohttp
from acb import console
from rich.panel import Panel
from rich.table import Table

watchdog_event_queue: asyncio.Queue[dict[str, Any]] | None = None


class ServiceConfig:
    def __init__(
        self,
        name: str,
        command: list[str],
        health_check_url: str | None = None,
        health_check_interval: float = 30.0,
        restart_delay: float = 5.0,
        max_restarts: int = 10,
        restart_window: float = 300.0,
    ) -> None:
        self.name = name
        self.command = command
        self.health_check_url = health_check_url
        self.health_check_interval = health_check_interval
        self.restart_delay = restart_delay
        self.max_restarts = max_restarts
        self.restart_window = restart_window

        self.process: subprocess.Popen[str] | None = None
        self.restart_count = 0
        self.restart_timestamps: list[float] = []
        self.last_health_check = 0.0
        self.is_healthy = False
        self._port_acknowledged = False
        self.last_error: str | None = None


class ServiceWatchdog:
    def __init__(
        self,
        services: list[ServiceConfig],
        event_queue: asyncio.Queue[dict[str, Any]] | None = None,
    ) -> None:
        self.services = services
        self.is_running = True
        self.session: aiohttp.ClientSession | None = None
        self.event_queue = event_queue

        global watchdog_event_queue
        if event_queue:
            watchdog_event_queue = event_queue

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0))

        for service in self.services:
            await self._start_service(service)

        monitor_tasks = [
            asyncio.create_task(self._monitor_service(service))
            for service in self.services
        ]

        status_task = asyncio.create_task(self._display_status())

        try:
            await asyncio.gather(*monitor_tasks, status_task)
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        self.is_running = False

        for service in self.services:
            if service.process:
                console.print(f"[yellow]🛑 Stopping {service.name}...[/ yellow]")
                service.process.terminate()
                try:
                    service.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    service.process.kill()

        if self.session:
            await self.session.close()

    def _is_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except OSError:
                return True

    async def _start_service(self, service: ServiceConfig) -> bool:
        try:
            if await self._check_websocket_server_running(service):
                return True

            if not await self._launch_service_process(service):
                return False

            return await self._finalize_service_startup(service)

        except Exception as e:
            return await self._handle_service_start_error(service, e)

    async def _check_websocket_server_running(self, service: ServiceConfig) -> bool:
        if "websocket-server" in " ".join(service.command):
            if self._is_port_in_use(8675):
                await self._emit_event(
                    "port_in_use",
                    service.name,
                    "Port 8675 already in use (server already running)",
                )
                service.is_healthy = True
                return True
        return False

    async def _launch_service_process(self, service: ServiceConfig) -> bool:
        service.process = subprocess.Popen[str](
            service.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        service.last_error = None
        await asyncio.sleep(2)

        return await self._check_process_startup_success(service)

    async def _check_process_startup_success(self, service: ServiceConfig) -> bool:
        if service.process is None:
            return False
        exit_code = service.process.poll()
        if exit_code is not None:
            return await self._handle_process_died(service, exit_code)
        return True

    async def _handle_process_died(
        self,
        service: ServiceConfig,
        exit_code: int,
    ) -> bool:
        if service.process is None:
            return False
        stdout, stderr = service.process.communicate()
        error_msg = f"Process died (exit: {exit_code})"
        if stderr and stderr.strip():
            error_msg += f"-{stderr.strip()[:50]}"
        service.last_error = error_msg
        await self._emit_event("process_died", service.name, error_msg)
        return False

    async def _finalize_service_startup(self, service: ServiceConfig) -> bool:
        if service.health_check_url:
            service.is_healthy = await self._health_check(service)
        else:
            service.is_healthy = True

        if service.is_healthy:
            await self._emit_event("started", service.name, "Running")

        return service.is_healthy

    async def _handle_service_start_error(
        self,
        service: ServiceConfig,
        error: Exception,
    ) -> bool:
        service.last_error = str(error)
        await self._emit_event(
            "start_error",
            service.name,
            f"Failed: {str(error)[:30]}",
        )
        return False

    async def _handle_websocket_server_monitoring(self, service: ServiceConfig) -> bool:
        if "websocket-server" not in " ".join(service.command):
            return False

        if self._is_port_in_use(8675):
            if await self._verify_websocket_server_health():
                service.is_healthy = True
                if (
                    not hasattr(service, "_port_acknowledged")
                    or not service._port_acknowledged
                ):
                    service._port_acknowledged = True
                    await self._emit_event(
                        "port_healthy",
                        service.name,
                        "WebSocket server verified healthy",
                    )
                await asyncio.sleep(30)
                return True
            service.is_healthy = False
            await self._emit_event(
                "port_hijacked",
                service.name,
                "Port 8675 occupied by different service",
            )
            await self._restart_service(service)
            return False
        service._port_acknowledged = False
        if service.process and service.process.poll() is None:
            await self._emit_event(
                "port_unavailable",
                service.name,
                "Process running but port 8675 not available",
            )
            await self._restart_service(service)
        return False

    async def _check_process_health(self, service: ServiceConfig) -> bool:
        process_running = service.process and service.process.poll() is None
        if not process_running:
            if service.process:
                exit_code = service.process.poll()
                await self._emit_event(
                    "died",
                    service.name,
                    f"Process died (exit: {exit_code})",
                )
            else:
                await self._emit_event("not_started", service.name, "Not started")
            await self._restart_service(service)
            return False
        return True

    async def _perform_health_check_if_needed(self, service: ServiceConfig) -> bool:
        if not service.health_check_url:
            return True

        current_time = time.time()
        if current_time - service.last_health_check >= service.health_check_interval:
            service.is_healthy = await self._health_check(service)
            service.last_health_check = current_time

            if not service.is_healthy:
                await self._emit_event(
                    "health_fail",
                    service.name,
                    "Health check failed",
                )
                await self._restart_service(service)
                return False
        return True

    async def _monitor_service(self, service: ServiceConfig) -> None:
        while self.is_running:
            try:
                if await self._execute_monitoring_cycle(service):
                    await asyncio.sleep(5.0)
                else:
                    continue

            except Exception as e:
                await self._handle_monitoring_error(service, e)

    async def _execute_monitoring_cycle(self, service: ServiceConfig) -> bool:
        if await self._handle_websocket_server_monitoring(service):
            return True

        if not await self._check_process_health(service):
            return False

        return await self._perform_health_check_if_needed(service)

    async def _handle_monitoring_error(
        self,
        service: ServiceConfig,
        error: Exception,
    ) -> None:
        service.last_error = str(error)
        console.print(f"[red]❌ Error monitoring {service.name}: {error}[/ red]")
        await asyncio.sleep(10.0)

    async def _health_check(self, service: ServiceConfig) -> bool:
        if not service.health_check_url or not self.session:
            return True

        try:
            async with self.session.get(service.health_check_url) as response:
                return response.status == 200
        except Exception:
            return False

    async def _verify_websocket_server_health(self) -> bool:
        if not self.session:
            return False

        with suppress(Exception):
            async with self.session.get("http: / / localhost: 8675 / ") as response:
                if response.status == 200:
                    data = await response.json()

                    return (
                        "message" in data
                        and "Crackerjack" in data.get("message", "")
                        and "progress_dir" in data
                    )
        return False

    async def _restart_service(self, service: ServiceConfig) -> None:
        current_time = time.time()
        reason = self._determine_restart_reason(service)

        await self._emit_event("restarting", service.name, f"Restarting-{reason}")

        if not await self._check_restart_rate_limit(service, current_time):
            return

        await self._terminate_existing_process(service)
        await self._wait_before_restart(service)
        await self._execute_service_restart(service, current_time)

    def _determine_restart_reason(self, service: ServiceConfig) -> str:
        return (
            "Process died"
            if not service.process or service.process.poll() is not None
            else "Health failed"
        )

    async def _check_restart_rate_limit(
        self,
        service: ServiceConfig,
        current_time: float,
    ) -> bool:
        service.restart_timestamps = [
            ts
            for ts in service.restart_timestamps
            if current_time - ts < service.restart_window
        ]

        if len(service.restart_timestamps) >= service.max_restarts:
            console.print(
                f"[red]🚨 {service.name} exceeded restart limit ({service.max_restarts} in {service.restart_window}s)[/ red]",
            )
            service.last_error = "Restart rate limit exceeded"
            await asyncio.sleep(60)
            return False
        return True

    async def _terminate_existing_process(self, service: ServiceConfig) -> None:
        if not service.process:
            return

        try:
            console.print(
                f"[yellow]🔪 Terminating existing {service.name} process (PID: {service.process.pid})[/ yellow]",
            )
            service.process.terminate()
            service.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            console.print(f"[red]💀 Force killing {service.name} process[/ red]")
            service.process.kill()
        except Exception as e:
            console.print(f"[yellow]⚠️ Error terminating {service.name}: {e}[/ yellow]")

    async def _wait_before_restart(self, service: ServiceConfig) -> None:
        console.print(
            f"[yellow]⏳ Waiting {service.restart_delay}s before restarting {service.name}...[/ yellow]",
        )
        await asyncio.sleep(service.restart_delay)

    async def _execute_service_restart(
        self,
        service: ServiceConfig,
        current_time: float,
    ) -> None:
        service.restart_timestamps.append(current_time)
        service.restart_count += 1

        success = await self._start_service(service)
        if not success:
            await self._emit_event("restart_failed", service.name, "Restart failed")

    async def _display_status(self) -> None:
        while self.is_running:
            try:
                await self._update_status_display()
                await asyncio.sleep(10.0)

            except Exception as e:
                console.print(f"[red]Error updating display: {e}[/ red]")
                await asyncio.sleep(5.0)

    async def _update_status_display(self) -> None:
        console.clear()
        table = self._create_status_table()

        for service in self.services:
            status = self._get_service_status(service)
            health = self._get_service_health(service)
            restarts = str(service.restart_count)
            error = self._format_error_message(service.last_error)

            table.add_row(service.name, status, health, restarts, error)

        console.print(
            Panel(table, title="Crackerjack Service Watchdog", border_style="cyan")
        )
        console.print("\n[dim]Press Ctrl + C to stop monitoring[/ dim]")

    def _create_status_table(self) -> Table:
        table = Table(title="🔍 Crackerjack Service Watchdog")
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Status", style="white")
        table.add_column("Health", style="white")
        table.add_column("Restarts", style="white")
        table.add_column("Last Error", style="red")
        return table

    def _get_service_status(self, service: ServiceConfig) -> str:
        if service.process and service.process.poll() is None:
            return "[green]✅ Running[/ green]"
        return "[red]❌ Stopped[/ red]"

    def _get_service_health(self, service: ServiceConfig) -> str:
        if service.health_check_url:
            return (
                "[green]🟢 Healthy[/ green]"
                if service.is_healthy
                else "[red]🔴 Unhealthy[/ red]"
            )
        return "[dim]N / A[/ dim]"

    def _format_error_message(self, error_message: str | None) -> str:
        error = error_message or "[dim]None[/ dim]"
        if len(error) > 30:
            error = error[:27] + "..."
        return error

    async def _emit_event(
        self,
        event_type: str,
        service_name: str,
        message: str,
    ) -> None:
        if self.event_queue:
            with suppress(Exception):
                event = {
                    "type": event_type,
                    "service": service_name,
                    "message": message,
                    "timestamp": time.time(),
                }
                await self.event_queue.put(event)

    async def _cleanup(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()


async def create_default_watchdog(
    event_queue: asyncio.Queue[dict[str, Any]] | None = None,
) -> ServiceWatchdog:
    python_path = sys.executable

    services = [
        ServiceConfig(
            name="MCP Server",
            command=[
                python_path,
                "-m",
                "crackerjack",
                "--start-mcp-server",
            ],
        ),
        ServiceConfig(
            name="WebSocket Server",
            command=[
                python_path,
                "-m",
                "crackerjack",
                " - - websocket-server",
            ],
            health_check_url="http: / / localhost: 8675 / ",
        ),
    ]

    return ServiceWatchdog(services, event_queue)


async def main() -> None:
    watchdog = await create_default_watchdog()

    try:
        await watchdog.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Shutting down watchdog...[/ yellow]")
    finally:
        await watchdog.stop()


if __name__ == "__main__":
    asyncio.run(main())
