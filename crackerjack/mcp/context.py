import asyncio
import contextlib
import io
import os
import subprocess
import tempfile
import time
import typing as t
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from rich.console import Console

from crackerjack.core.resource_manager import (
    ResourceManager,
    register_global_resource_manager,
)
from crackerjack.core.websocket_lifecycle import NetworkResourceManager
from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.services.secure_path_utils import SecurePathValidator

from .cache import ErrorCache
from .rate_limiter import RateLimitConfig, RateLimitMiddleware
from .state import StateManager


class BatchedStateSaver:
    def __init__(self, debounce_delay: float = 1.0, max_batch_size: int = 10) -> None:
        self.debounce_delay = debounce_delay
        self.max_batch_size = max_batch_size

        self._pending_saves: dict[str, t.Callable[[], None]] = {}
        self._last_save_time: dict[str, float] = {}

        self._save_task: asyncio.Task | None = None
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._save_task = asyncio.create_task(self._save_loop())

    async def stop(self) -> None:
        self._running = False

        if self._save_task:
            self._save_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._save_task

        await self._flush_saves()

    async def schedule_save(
        self,
        save_id: str,
        save_func: t.Callable[[], None],
    ) -> None:
        async with self._lock:
            self._pending_saves[save_id] = save_func
            self._last_save_time[save_id] = time.time()

            if len(self._pending_saves) >= self.max_batch_size:
                await self._flush_saves()

    async def _save_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.debounce_delay)
                ready_saves = await self._get_ready_saves()

                if ready_saves:
                    await self._execute_saves(ready_saves)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def _get_ready_saves(self) -> list[str]:
        now = time.time()
        ready_saves = []

        async with self._lock:
            for save_id, last_time in list(self._last_save_time.items()):
                if now - last_time >= self.debounce_delay:
                    ready_saves.append(save_id)

        return ready_saves

    async def _execute_saves(self, save_ids: list[str]) -> None:
        async with self._lock:
            saves_to_execute = []

            for save_id in save_ids:
                if save_id in self._pending_saves:
                    saves_to_execute.append((save_id, self._pending_saves.pop(save_id)))
                    self._last_save_time.pop(save_id, None)

        for save_id, save_func in saves_to_execute:
            with contextlib.suppress(Exception):
                save_func()

    async def _flush_saves(self) -> None:
        async with self._lock:
            save_ids = list(self._pending_saves.keys())

        if save_ids:
            await self._execute_saves(save_ids)

    def get_stats(self) -> dict[str, t.Any]:
        return {
            "running": self._running,
            "pending_saves": len(self._pending_saves),
            "debounce_delay": self.debounce_delay,
            "max_batch_size": self.max_batch_size,
        }


@dataclass
class MCPServerConfig:
    project_path: Path
    progress_dir: Path | None = None
    rate_limit_config: RateLimitConfig | None = None
    stdio_mode: bool = True
    state_dir: Path | None = None
    cache_dir: Path | None = None

    def __post_init__(self) -> None:
        # Validate all paths using secure path validation
        self.project_path = SecurePathValidator.validate_safe_path(self.project_path)

        if self.progress_dir:
            self.progress_dir = SecurePathValidator.validate_safe_path(
                self.progress_dir
            )

        if self.state_dir:
            self.state_dir = SecurePathValidator.validate_safe_path(self.state_dir)

        if self.cache_dir:
            self.cache_dir = SecurePathValidator.validate_safe_path(self.cache_dir)


class MCPServerContext:
    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config

        # Resource management
        self.resource_manager = ResourceManager()
        self.network_manager = NetworkResourceManager()
        register_global_resource_manager(self.resource_manager)

        self.console: Console | None = None
        self.cli_runner = None
        self.state_manager: StateManager | None = None
        self.error_cache: ErrorCache | None = None
        self.rate_limiter: RateLimitMiddleware | None = None
        self.batched_saver: BatchedStateSaver = BatchedStateSaver()

        self.progress_dir = config.progress_dir or (
            Path(tempfile.gettempdir()) / "crackerjack-mcp-progress"
        )
        self.progress_queue: asyncio.Queue[dict[str, t.Any]] = asyncio.Queue(
            maxsize=1000,
        )

        self.websocket_server_process: subprocess.Popen[bytes] | None = None
        self.websocket_server_port: int = int(
            os.environ.get("CRACKERJACK_WEBSOCKET_PORT", "8675"),
        )
        self._websocket_process_lock = asyncio.Lock()
        self._websocket_cleanup_registered = False
        self._websocket_health_check_task: asyncio.Task | None = None

        self._initialized = False
        self._startup_tasks: list[t.Callable[[], t.Awaitable[None]]] = []
        self._shutdown_tasks: list[t.Callable[[], t.Awaitable[None]]] = []

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            if self.config.stdio_mode:
                null_file = io.StringIO()
                self.console = Console(file=null_file, force_terminal=False)
            else:
                self.console = Console(force_terminal=True)

            self.progress_dir.mkdir(exist_ok=True)

            self.cli_runner = WorkflowOrchestrator(
                console=self.console,
                pkg_path=self.config.project_path,
            )

            self.state_manager = StateManager(
                self.config.state_dir or Path.home() / ".cache" / "crackerjack-mcp",
                self.batched_saver,
            )

            self.error_cache = ErrorCache(
                self.config.cache_dir or Path.home() / ".cache" / "crackerjack-mcp",
            )

            self.rate_limiter = RateLimitMiddleware(self.config.rate_limit_config)

            await self.batched_saver.start()

            for task in self._startup_tasks:
                await task()

            self._initialized = True

        except Exception as e:
            self.cli_runner = None
            self.state_manager = None
            self.error_cache = None
            self.rate_limiter = None
            msg = f"Failed to initialize MCP server context: {e}"
            raise RuntimeError(msg) from e

    async def shutdown(self) -> None:
        if not self._initialized:
            return

        # Run custom shutdown tasks first
        for task in reversed(self._shutdown_tasks):
            try:
                await task()
            except Exception as e:
                if self.console:
                    self.console.print(f"[red]Error during shutdown: {e}[/red]")

        # Cancel health check task
        if self._websocket_health_check_task:
            self._websocket_health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._websocket_health_check_task
            self._websocket_health_check_task = None

        # Stop WebSocket server
        await self._stop_websocket_server()

        # Stop rate limiter
        if self.rate_limiter:
            await self.rate_limiter.stop()

        # Stop batched saver
        await self.batched_saver.stop()

        # Clean up all managed resources
        try:
            await self.network_manager.cleanup_all()
        except Exception as e:
            if self.console:
                self.console.print(
                    f"[yellow]Warning: Network resource cleanup error: {e}[/yellow]"
                )

        try:
            await self.resource_manager.cleanup_all()
        except Exception as e:
            if self.console:
                self.console.print(
                    f"[yellow]Warning: Resource cleanup error: {e}[/yellow]"
                )

        self._initialized = False

    def add_startup_task(self, task: t.Callable[[], t.Awaitable[None]]) -> None:
        self._startup_tasks.append(task)

    def add_shutdown_task(self, task: t.Callable[[], t.Awaitable[None]]) -> None:
        self._shutdown_tasks.append(task)

    def validate_job_id(self, job_id: str) -> bool:
        if not job_id:
            return False

        import uuid
        from contextlib import suppress

        with suppress(ValueError):
            uuid.UUID(job_id)
            return True

        from crackerjack.services.regex_patterns import is_valid_job_id

        if not is_valid_job_id(job_id):
            return False

        if ".." in job_id or "/" in job_id or "\\" in job_id:
            return False

        import os

        return os.path.basename(job_id) == job_id

    async def check_websocket_server_running(self) -> bool:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            result = sock.connect_ex(("localhost", self.websocket_server_port))
            return result == 0

    async def start_websocket_server(self) -> bool:
        async with self._websocket_process_lock:
            if await self._check_existing_websocket_server():
                return True

            if self.console:
                self.console.print(
                    f"🚀 Starting WebSocket server on localhost: {self.websocket_server_port}...",
                )

            try:
                await self._spawn_websocket_process()
                await self._register_websocket_cleanup()
                return await self._wait_for_websocket_startup()

            except Exception as e:
                if self.console:
                    self.console.print(f"❌ Failed to start WebSocket server: {e}")
                await self._cleanup_dead_websocket_process()
                return False

    async def _check_existing_websocket_server(self) -> bool:
        if (
            self.websocket_server_process
            and self.websocket_server_process.poll() is None
        ):
            if await self.check_websocket_server_running():
                if self.console:
                    self.console.print(
                        f"✅ WebSocket server already running on port {self.websocket_server_port}",
                    )
                return True
            await self._cleanup_dead_websocket_process()

        if await self.check_websocket_server_running():
            if self.console:
                self.console.print(
                    f"⚠️ Port {self.websocket_server_port} already in use by another process",
                )
            return True

        return False

    async def _spawn_websocket_process(self) -> None:
        import sys

        self.websocket_server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "crackerjack",
                "--start-websocket-server",
                "--websocket-port",
                str(self.websocket_server_port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Register the process with the network resource manager for automatic cleanup
        if self.websocket_server_process:
            managed_process = self.network_manager.create_subprocess(
                self.websocket_server_process, timeout=30.0
            )
            await managed_process.start_monitoring()

    async def _register_websocket_cleanup(self) -> None:
        if not self._websocket_cleanup_registered:
            self.add_shutdown_task(self._stop_websocket_server)
            self._websocket_cleanup_registered = True

        if not self._websocket_health_check_task:
            self._websocket_health_check_task = asyncio.create_task(
                self._websocket_health_monitor(),
            )

    async def _wait_for_websocket_startup(self) -> bool:
        max_attempts = 10
        for _attempt in range(max_attempts):
            await asyncio.sleep(0.5)

            if self.websocket_server_process.poll() is not None:
                return_code = self.websocket_server_process.returncode
                if self.console:
                    self.console.print(
                        f"❌ WebSocket server process died during startup (exit code: {return_code})",
                    )
                self.websocket_server_process = None
                return False

            if await self.check_websocket_server_running():
                if self.console:
                    self.console.print(
                        f"✅ WebSocket server started successfully on port {self.websocket_server_port}",
                    )
                    self.console.print(
                        f"📊 Progress available at: ws: / / localhost: {self.websocket_server_port}/ ws / progress /{{job_id}}",
                    )
                return True

        if self.console:
            self.console.print(
                f"❌ WebSocket server failed to start within {max_attempts * 0.5}s",
            )
        await self._cleanup_dead_websocket_process()
        return False

    async def _cleanup_dead_websocket_process(self) -> None:
        if self.websocket_server_process:
            try:
                if self.websocket_server_process.poll() is None:
                    self.websocket_server_process.terminate()
                    try:
                        self.websocket_server_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.websocket_server_process.kill()
                        self.websocket_server_process.wait(timeout=1)

                if self.console:
                    self.console.print("🧹 Cleaned up dead WebSocket server process")
            except Exception as e:
                if self.console:
                    self.console.print(f"⚠️ Error cleaning up WebSocket process: {e}")
            finally:
                self.websocket_server_process = None

    async def _stop_websocket_server(self) -> None:
        async with self._websocket_process_lock:
            if not self.websocket_server_process:
                return

            try:
                if self.websocket_server_process.poll() is None:
                    await self._terminate_live_websocket_process()
                else:
                    await self._handle_dead_websocket_process_cleanup()

            except Exception as e:
                if self.console:
                    self.console.print(f"⚠️ Error stopping WebSocket server: {e}")
            finally:
                self.websocket_server_process = None

    async def _terminate_live_websocket_process(self) -> None:
        if self.console:
            self.console.print("🛑 Stopping WebSocket server...")

        self.websocket_server_process.terminate()

        if await self._wait_for_graceful_termination():
            return

        await self._force_kill_websocket_process()

    async def _wait_for_graceful_termination(self) -> bool:
        try:
            self.websocket_server_process.wait(timeout=5)
            if self.console:
                self.console.print("✅ WebSocket server stopped gracefully")
            return True
        except subprocess.TimeoutExpired:
            return False

    async def _force_kill_websocket_process(self) -> None:
        if self.console:
            self.console.print("⚡ Force killing unresponsive WebSocket server...")

        self.websocket_server_process.kill()

        try:
            self.websocket_server_process.wait(timeout=2)
            if self.console:
                self.console.print("💀 WebSocket server force killed")
        except subprocess.TimeoutExpired:
            if self.console:
                self.console.print("⚠️ WebSocket server process may be zombified")

    async def _handle_dead_websocket_process_cleanup(self) -> None:
        if self.console:
            self.console.print("💀 WebSocket server process was already dead")

    async def get_websocket_server_status(self) -> dict[str, t.Any]:
        async with self._websocket_process_lock:
            status = {
                "port": self.websocket_server_port,
                "process_exists": self.websocket_server_process is not None,
                "process_alive": False,
                "server_responding": False,
                "process_id": None,
                "return_code": None,
            }

            if self.websocket_server_process:
                status["process_id"] = self.websocket_server_process.pid
                poll_result = self.websocket_server_process.poll()
                status["process_alive"] = poll_result is None
                if poll_result is not None:
                    status["return_code"] = poll_result

            status["server_responding"] = await self.check_websocket_server_running()

            return status

    async def _websocket_health_monitor(self) -> None:
        while True:
            try:
                await asyncio.sleep(30)
                await self._check_and_restart_websocket()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.console:
                    self.console.print(f"⚠️ Error in WebSocket health monitor: {e}")
                await asyncio.sleep(60)

    async def _check_and_restart_websocket(self) -> None:
        async with self._websocket_process_lock:
            if not self.websocket_server_process:
                return

            if self.websocket_server_process.poll() is not None:
                await self._handle_dead_websocket_process()
                return

            if not await self.check_websocket_server_running():
                await self._handle_unresponsive_websocket_server()

    async def _handle_dead_websocket_process(self) -> None:
        return_code = self.websocket_server_process.returncode
        if self.console:
            self.console.print(
                f"⚠️ WebSocket server process died (exit code: {return_code}), attempting restart...",
            )
        self.websocket_server_process = None
        await self._restart_websocket_server()

    async def _handle_unresponsive_websocket_server(self) -> None:
        if self.console:
            self.console.print("⚠️ WebSocket server not responding, restarting...")
        await self._cleanup_dead_websocket_process()
        await self._restart_websocket_server()

    async def _restart_websocket_server(self) -> None:
        if await self.start_websocket_server():
            if self.console:
                self.console.print("✅ WebSocket server restarted successfully")
        elif self.console:
            self.console.print("❌ Failed to restart WebSocket server")

    def safe_print(self, *args, **kwargs) -> None:
        if not self.config.stdio_mode and self.console:
            self.console.print(*args, **kwargs)

    def create_progress_file_path(self, job_id: str) -> Path:
        if not self.validate_job_id(job_id):
            msg = f"Invalid job_id: {job_id}"
            raise ValueError(msg)

        # Use secure path joining to prevent directory traversal
        return SecurePathValidator.secure_path_join(
            self.progress_dir, f"job-{job_id}.json"
        )

    async def schedule_state_save(
        self,
        save_id: str,
        save_func: t.Callable[[], None],
    ) -> None:
        await self.batched_saver.schedule_save(save_id, save_func)

    def get_current_time(self) -> str:
        import datetime

        return datetime.datetime.now().isoformat()

    def get_context_stats(self) -> dict[str, t.Any]:
        return {
            "initialized": self._initialized,
            "stdio_mode": self.config.stdio_mode,
            "project_path": str(self.config.project_path),
            "progress_dir": str(self.progress_dir),
            "components": {
                "cli_runner": self.cli_runner is not None,
                "state_manager": self.state_manager is not None,
                "error_cache": self.error_cache is not None,
                "rate_limiter": self.rate_limiter is not None,
                "batched_saver": self.batched_saver is not None,
            },
            "websocket_server": {
                "port": self.websocket_server_port,
                "process_exists": self.websocket_server_process is not None,
                "health_monitor_running": self._websocket_health_check_task is not None
                and not self._websocket_health_check_task.done(),
                "cleanup_registered": self._websocket_cleanup_registered,
            },
            "progress_queue": {
                "maxsize": self.progress_queue.maxsize,
                "current_size": self.progress_queue.qsize(),
                "full": self.progress_queue.full(),
            },
            "startup_tasks": len(self._startup_tasks),
            "shutdown_tasks": len(self._shutdown_tasks),
            "batched_saving": self.batched_saver.get_stats(),
        }


class MCPContextManager:
    def __init__(self, config: MCPServerConfig) -> None:
        self.context = MCPServerContext(config)

    async def __aenter__(self) -> MCPServerContext:
        await self.context.initialize()
        return self.context

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        await self.context.shutdown()


_global_context: MCPServerContext | None = None


def get_context() -> MCPServerContext:
    if _global_context is None:
        msg = "MCP server context not initialized. Call set_context() first."
        raise RuntimeError(
            msg,
        )
    return _global_context


def set_context(context: MCPServerContext) -> None:
    global _global_context
    _global_context = context


def clear_context() -> None:
    global _global_context
    _global_context = None


def get_console() -> Console:
    return get_context().console or Console()


def get_state_manager() -> StateManager | None:
    return get_context().state_manager


def get_error_cache() -> ErrorCache | None:
    return get_context().error_cache


def get_rate_limiter() -> RateLimitMiddleware | None:
    return get_context().rate_limiter


def safe_print(*args, **kwargs) -> None:
    get_context().safe_print(*args, **kwargs)


def validate_job_id(job_id: str) -> bool:
    return get_context().validate_job_id(job_id)
