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

        self._save_task: asyncio.Task[None] | None = None
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
            for save_id, last_time in list[t.Any](self._last_save_time.items()):
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
            save_ids = list[t.Any](self._pending_saves.keys())

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

        self.resource_manager = ResourceManager()
        register_global_resource_manager(self.resource_manager)

        self.console: Console | None = None
        # TODO(Phase 3): Replace with Oneiric workflow integration
        self.cli_runner: object | None = None
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

        self._initialized = False
        self._startup_tasks: list[t.Callable[[], t.Awaitable[None]]] = []
        self._shutdown_tasks: list[t.Callable[[], t.Awaitable[None]]] = []

    async def _auto_setup_git_working_directory(self) -> None:
        """Auto-detect and setup git working directory for enhanced DX."""
        try:
            git_root = await self._detect_git_repository()
            if git_root:
                await self._log_git_detection(git_root)

        except Exception as e:
            self._handle_git_setup_failure(e)

    async def _detect_git_repository(self) -> Path | None:
        """Detect if we're in a git repository and return the root path."""

        current_dir = Path.cwd()

        # Check if we're in a git repository
        if not self._is_git_repository(current_dir):
            return None

        return self._get_git_root_directory(current_dir)

    def _is_git_repository(self, current_dir: Path) -> bool:
        """Check if the current directory is within a git repository."""

        git_check = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            cwd=current_dir,
        )
        return git_check.returncode == 0

    def _get_git_root_directory(self, current_dir: Path) -> Path | None:
        """Get the git repository root directory."""

        git_root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=current_dir,
        )

        if git_root_result.returncode == 0:
            git_root = Path(git_root_result.stdout.strip())
            return git_root if git_root.exists() else None
        return None

    async def _log_git_detection(self, git_root: Path) -> None:
        """Log git repository detection to stderr and console."""

        # Log to stderr for Claude to see
        self._log_to_stderr(git_root)

        # Log to console if available
        self._log_to_console(git_root)

    def _log_to_stderr(self, git_root: Path) -> None:
        """Log git detection messages to stderr."""
        import sys

        print(
            f"📍 Crackerjack MCP: Git repository detected at {git_root}",
            file=sys.stderr,
        )
        print(
            f"💡 Tip: Auto-setup git working directory with: git_set_working_dir('{git_root}')",
            file=sys.stderr,
        )

    def _log_to_console(self, git_root: Path) -> None:
        """Log git detection messages to console if available."""
        if self.console:
            self.console.print(f"🔧 Auto-detected git repository: {git_root}")
            self.console.print(
                f"💡 Recommend: Use `mcp__git__git_set_working_dir` with path='{git_root}'"
            )

    def _handle_git_setup_failure(self, error: Exception) -> None:
        """Handle git setup failure with graceful fallback."""
        if self.console:
            self.console.print(
                f"[dim]Git auto-setup failed (non-critical): {error}[/dim]"
            )

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            await self._perform_initialization_sequence()
            self._initialized = True

        except Exception as e:
            self._handle_initialization_failure(e)

    async def _perform_initialization_sequence(self) -> None:
        """Perform the complete initialization sequence."""
        self._setup_console()
        self._setup_directories()
        await self._initialize_components()
        await self._finalize_initialization()

    def _handle_initialization_failure(self, error: Exception) -> None:
        """Handle initialization failure with cleanup and error propagation."""
        self._cleanup_failed_initialization()
        msg = f"Failed to initialize MCP server context: {error}"
        raise RuntimeError(msg) from error

    def _setup_console(self) -> None:
        """Setup console based on configuration mode."""
        if self.config.stdio_mode:
            io.StringIO()
            self.console = Console()
        else:
            self.console = Console()

    def _setup_directories(self) -> None:
        """Setup required directories."""
        self.progress_dir.mkdir(exist_ok=True)

    async def _initialize_components(self) -> None:
        """Initialize all service components."""
        # TODO(Phase 3): Replace with Oneiric workflow integration
        self.cli_runner = None

        self.state_manager = StateManager(
            self.config.state_dir or Path.home() / ".cache" / "crackerjack-mcp",
            self.batched_saver,
        )

        self.error_cache = ErrorCache(
            self.config.cache_dir or Path.home() / ".cache" / "crackerjack-mcp",
        )

        self.rate_limiter = RateLimitMiddleware(self.config.rate_limit_config)
        await self.batched_saver.start()

    async def _finalize_initialization(self) -> None:
        """Complete initialization with optional setup and startup tasks."""
        # Auto-setup git working directory for enhanced DX
        await self._auto_setup_git_working_directory()

        for task in self._startup_tasks:
            await task()

    def _cleanup_failed_initialization(self) -> None:
        """Cleanup components after failed initialization."""
        self.cli_runner = None
        self.state_manager = None
        self.error_cache = None
        self.rate_limiter = None

    async def shutdown(self) -> None:
        if not self._initialized:
            return

        for task in reversed(self._shutdown_tasks):
            try:
                await task()
            except Exception as e:
                if self.console:
                    self.console.print(f"[red]Error during shutdown: {e}[/red]")

        if self.rate_limiter:
            await self.rate_limiter.stop()

        await self.batched_saver.stop()

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

        return os.path.basename(job_id) == job_id

    def safe_print(self, *args: t.Any, **kwargs: t.Any) -> None:
        if not self.config.stdio_mode and self.console:
            self.console.print(*args, **kwargs)

    def create_progress_file_path(self, job_id: str) -> Path:
        if not self.validate_job_id(job_id):
            msg = f"Invalid job_id: {job_id}"
            raise ValueError(msg)

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


def safe_print(*args: t.Any, **kwargs: t.Any) -> None:
    get_context().safe_print(*args, **kwargs)


def validate_job_id(job_id: str) -> bool:
    return get_context().validate_job_id(job_id)
