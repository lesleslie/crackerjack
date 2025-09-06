"""Global hook lock management to prevent concurrent execution of specific hooks.

This module provides a lock manager that ensures certain hooks
(like complexipy) run sequentially rather than concurrently to prevent
resource contention and hanging processes.

This implements the HookLockManagerProtocol for dependency injection compatibility.

Phase 2 implementation provides enhanced file-based global lock coordination
across multiple crackerjack sessions with atomic operations, heartbeat monitoring,
and comprehensive stale lock cleanup.
"""

import asyncio
import json
import logging
import os
import time
import typing as t
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from ..config.global_lock_config import GlobalLockConfig


class HookLockManager:
    """Manager for hook-specific locks to prevent concurrent execution.

    Implements HookLockManagerProtocol for dependency injection compatibility.
    Provides async locking with timeout protection and comprehensive monitoring.
    """

    _instance: t.Optional["HookLockManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "HookLockManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._hooks_requiring_locks = {
            "complexipy",  # Prevent multiple complexipy processes
            # Add other hooks that should run sequentially
        }

        # Per-hook locks for sequential execution
        self._hook_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Global lock configuration and state
        self._global_config = GlobalLockConfig()
        self._global_lock_enabled = self._global_config.enabled
        self._active_global_locks: set[str] = set()
        self._heartbeat_tasks: dict[str, asyncio.Task[None]] = {}

        # Lock usage tracking for monitoring
        self._lock_usage: dict[str, list[float]] = defaultdict(list)
        self._lock_wait_times: dict[str, list[float]] = defaultdict(list)
        self._lock_execution_times: dict[str, list[float]] = defaultdict(list)
        self._max_history = 50  # Keep last 50 lock acquisitions

        # Global lock statistics tracking
        self._global_lock_attempts: dict[str, int] = defaultdict(int)
        self._global_lock_successes: dict[str, int] = defaultdict(int)
        self._global_lock_failures: dict[str, int] = defaultdict(int)
        self._stale_locks_cleaned: dict[str, int] = defaultdict(int)
        self._heartbeat_failures: dict[str, int] = defaultdict(int)

        # Timeout protection
        self._default_lock_timeout = 300.0  # 5 minutes default timeout
        self._lock_timeouts: dict[str, float] = {}

        # Error tracking
        self._lock_failures: dict[str, int] = defaultdict(int)
        self._timeout_failures: dict[str, int] = defaultdict(int)

        self.logger = logging.getLogger(__name__)
        self._initialized = True

    def requires_lock(self, hook_name: str) -> bool:
        """Check if a hook requires sequential execution."""
        return hook_name in self._hooks_requiring_locks

    @asynccontextmanager
    async def acquire_hook_lock(self, hook_name: str) -> t.AsyncIterator[None]:
        """Unified lock acquisition handling both hook-specific and global locks.

        Args:
            hook_name: Name of the hook to lock

        Yields:
            None when lock is acquired (or hook doesn't require lock)

        Raises:
            asyncio.TimeoutError: If lock acquisition times out

        Example:
            async with lock_manager.acquire_hook_lock("complexipy"):
                # Only one complexipy process will run at a time
                result = await execute_hook(hook)
        """
        if not self.requires_lock(hook_name):
            # Hook doesn't require locking, proceed immediately
            yield
            return

        if not self._global_lock_enabled:
            # Use existing hook-specific locking only (legacy behavior)
            async with self._acquire_existing_hook_lock(hook_name):
                yield
            return

        # Global locking: coordinate across all crackerjack sessions
        async with self._acquire_global_coordination_lock(hook_name):
            # Then acquire hook-specific lock within global coordination
            async with self._acquire_existing_hook_lock(hook_name):
                yield

    @asynccontextmanager
    async def _acquire_existing_hook_lock(
        self, hook_name: str
    ) -> t.AsyncIterator[None]:
        """Acquire hook-specific asyncio lock (original behavior)."""
        lock = self._hook_locks[hook_name]
        timeout = self._lock_timeouts.get(hook_name, self._default_lock_timeout)
        start_time = time.time()

        self.logger.debug(
            f"Acquiring hook-specific lock: {hook_name} (timeout: {timeout}s)"
        )

        try:
            # Use asyncio.wait_for to implement timeout for lock acquisition
            await asyncio.wait_for(lock.acquire(), timeout=timeout)

            try:
                acquisition_time = time.time() - start_time
                self.logger.info(
                    f"Hook-specific lock acquired for {hook_name} after"
                    f" {acquisition_time:.2f}s"
                )

                # Track lock usage for monitoring
                self._track_lock_usage(hook_name, acquisition_time)

                execution_start = time.time()
                try:
                    yield
                finally:
                    execution_time = time.time() - execution_start
                    total_time = time.time() - start_time

                    self._track_lock_execution(hook_name, execution_time, total_time)
                    self.logger.debug(
                        f"Hook-specific lock released for {hook_name} after"
                        f" {total_time:.2f}s total"
                    )

            finally:
                # Always release the lock, even if an exception occurred
                lock.release()

        except TimeoutError:
            self._timeout_failures[hook_name] += 1
            wait_time = time.time() - start_time
            self.logger.error(
                f"Hook-specific lock acquisition timeout for {hook_name} after"
                f" {wait_time:.2f}s "
                f"(timeout: {timeout}s, total failures: "
                f"{self._timeout_failures[hook_name]})"
            )
            raise

        except Exception as e:
            self._lock_failures[hook_name] += 1
            self.logger.error(
                f"Hook-specific lock acquisition failed for {hook_name}: {e} "
                f"(total failures: {self._lock_failures[hook_name]})"
            )
            raise

    @asynccontextmanager
    async def _acquire_global_coordination_lock(
        self, hook_name: str
    ) -> t.AsyncIterator[None]:
        """Acquire global file-based coordination lock across crackerjack sessions."""
        lock_path = self._global_config.get_lock_path(hook_name)
        start_time = time.time()

        self._global_lock_attempts[hook_name] += 1
        self.logger.debug(
            f"Attempting global lock acquisition for {hook_name}: {lock_path}"
        )

        # Clean up stale locks first
        await self._cleanup_stale_lock_if_needed(hook_name)

        try:
            # Atomic lock acquisition with retry logic
            await self._acquire_global_lock_file(hook_name, lock_path)
            self._global_lock_successes[hook_name] += 1
            self._active_global_locks.add(hook_name)

            # Start heartbeat to keep lock alive
            heartbeat_task = asyncio.create_task(self._maintain_heartbeat(hook_name))
            self._heartbeat_tasks[hook_name] = heartbeat_task

            acquisition_time = time.time() - start_time
            self.logger.info(
                f"Global lock acquired for {hook_name} after {acquisition_time:.2f}s"
            )

            try:
                yield
            finally:
                # Cleanup: cancel heartbeat and remove lock file
                await self._cleanup_global_lock(hook_name, heartbeat_task)

        except Exception as e:
            self._global_lock_failures[hook_name] += 1
            self.logger.error(f"Global lock acquisition failed for {hook_name}: {e}")
            raise

    def _track_lock_usage(self, hook_name: str, acquisition_time: float) -> None:
        """Track lock acquisition times for monitoring."""
        usage_list = self._lock_usage[hook_name]
        wait_list = self._lock_wait_times[hook_name]

        usage_list.append(acquisition_time)
        wait_list.append(acquisition_time)

        # Keep only recent history
        if len(usage_list) > self._max_history:
            usage_list.pop(0)
        if len(wait_list) > self._max_history:
            wait_list.pop(0)

    def _track_lock_execution(
        self, hook_name: str, execution_time: float, total_time: float
    ) -> None:
        """Track lock execution times for monitoring."""
        exec_list = self._lock_execution_times[hook_name]
        exec_list.append(execution_time)

        # Keep only recent history
        if len(exec_list) > self._max_history:
            exec_list.pop(0)

        self.logger.debug(
            f"Hook {hook_name} execution: {execution_time:.2f}s "
            f"(total with lock: {total_time:.2f}s)"
        )

    async def _acquire_global_lock_file(self, hook_name: str, lock_path: Path) -> None:
        """Atomic acquisition of global lock file with retry logic."""
        for attempt in range(self._global_config.max_retry_attempts):
            try:
                await self._attempt_lock_acquisition(hook_name, lock_path)
                return
            except FileExistsError:
                if attempt < self._global_config.max_retry_attempts - 1:
                    # Exponential backoff with jitter
                    delay = self._global_config.retry_delay_seconds * (2**attempt)
                    jitter = delay * 0.1  # Add 10% jitter
                    wait_time = delay + (jitter * (0.5 - os.urandom(1)[0] / 255))

                    self.logger.debug(
                        f"Global lock exists for {hook_name}, retrying in "
                        f"{wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise TimeoutError(
                        f"Failed to acquire global lock for {hook_name} after"
                        f" {self._global_config.max_retry_attempts} attempts"
                    )

    async def _attempt_lock_acquisition(self, hook_name: str, lock_path: Path) -> None:
        """Single atomic lock acquisition attempt using temp file + rename pattern."""
        temp_path = lock_path.with_suffix(".tmp")

        lock_data = {
            "session_id": self._global_config.session_id,
            "hostname": self._global_config.hostname,
            "pid": os.getpid(),
            "hook_name": hook_name,
            "acquired_at": time.time(),
            "last_heartbeat": time.time(),
            "crackerjack_version": "0.30.3",  # Could be made configurable
        }

        try:
            # Use exclusive creation for atomic operation
            with temp_path.open("x", encoding="utf-8") as f:
                json.dump(lock_data, f, indent=2)

            # Set restrictive permissions (owner only)
            temp_path.chmod(0o600)

            # Atomic rename - this is the critical section
            try:
                temp_path.rename(lock_path)
                self.logger.debug(f"Successfully created global lock file: {lock_path}")
            except FileExistsError:
                # Another process won the race, clean up our temp file
                with suppress(OSError):
                    temp_path.unlink()
                raise

        except FileExistsError:
            # Lock file already exists - convert to proper exception type
            raise FileExistsError(f"Global lock already exists for {hook_name}")
        except Exception as e:
            # Clean up temp file on any error
            with suppress(OSError):
                temp_path.unlink()
            self.logger.error(f"Failed to create global lock for {hook_name}: {e}")
            raise

    async def _maintain_heartbeat(self, hook_name: str) -> None:
        """Maintain heartbeat updates to prevent stale lock detection."""
        lock_path = self._global_config.get_lock_path(hook_name)
        interval = self._global_config.session_heartbeat_interval

        self.logger.debug(f"Starting heartbeat for {hook_name} every {interval}s")

        while hook_name in self._active_global_locks:
            try:
                await asyncio.sleep(interval)

                if hook_name not in self._active_global_locks:
                    break

                # Update heartbeat timestamp in lock file
                await self._update_heartbeat_timestamp(hook_name, lock_path)

            except asyncio.CancelledError:
                self.logger.debug(f"Heartbeat cancelled for {hook_name}")
                break
            except Exception as e:
                self._heartbeat_failures[hook_name] += 1
                self.logger.warning(f"Heartbeat update failed for {hook_name}: {e}")

                # If too many heartbeat failures, consider the lock compromised
                if self._heartbeat_failures[hook_name] > 3:
                    self.logger.error(
                        f"Too many heartbeat failures for {hook_name},"
                        f" stopping heartbeat"
                    )
                    break

    async def _update_heartbeat_timestamp(
        self, hook_name: str, lock_path: Path
    ) -> None:
        """Atomic update of heartbeat timestamp in existing lock file."""
        if not lock_path.exists():
            self.logger.warning(
                f"Lock file disappeared for {hook_name}, stopping heartbeat"
            )
            self._active_global_locks.discard(hook_name)
            return

        temp_path = lock_path.with_suffix(".heartbeat_tmp")

        try:
            # Read existing lock data
            with lock_path.open(encoding="utf-8") as f:
                lock_data = json.load(f)

            # Verify we still own this lock
            if lock_data.get("session_id") != self._global_config.session_id:
                self.logger.warning(
                    f"Lock ownership changed for {hook_name}, stopping heartbeat"
                )
                self._active_global_locks.discard(hook_name)
                return

            # Update heartbeat timestamp
            lock_data["last_heartbeat"] = time.time()

            # Write updated data atomically
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(lock_data, f, indent=2)

            temp_path.chmod(0o600)
            temp_path.rename(lock_path)

        except Exception as e:
            with suppress(OSError):
                temp_path.unlink()
            raise RuntimeError(f"Failed to update heartbeat for {hook_name}: {e}")

    async def _cleanup_global_lock(
        self, hook_name: str, heartbeat_task: asyncio.Task[None] | None = None
    ) -> None:
        """Clean up global lock resources and remove lock file."""
        self.logger.debug(f"Cleaning up global lock for {hook_name}")

        # Stop tracking this lock
        self._active_global_locks.discard(hook_name)

        # Cancel heartbeat task
        if heartbeat_task is None:
            heartbeat_task = self._heartbeat_tasks.pop(hook_name, None)
        else:
            # Remove from task tracking
            self._heartbeat_tasks.pop(hook_name, None)

        if heartbeat_task:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

        # Remove lock file
        lock_path = self._global_config.get_lock_path(hook_name)
        with suppress(OSError):
            if lock_path.exists():
                # Verify we still own the lock before deleting
                try:
                    with lock_path.open(encoding="utf-8") as f:
                        lock_data = json.load(f)

                    if lock_data.get("session_id") == self._global_config.session_id:
                        lock_path.unlink()
                        self.logger.debug(f"Removed global lock file: {lock_path}")
                    else:
                        self.logger.warning(
                            f"Lock ownership changed, not removing file: {lock_path}"
                        )

                except Exception as e:
                    self.logger.warning(
                        f"Could not verify lock ownership for cleanup: {e}"
                    )

    async def _cleanup_stale_lock_if_needed(self, hook_name: str) -> None:
        """Check for and remove stale lock if detected."""
        lock_path = self._global_config.get_lock_path(hook_name)

        if not lock_path.exists():
            return

        try:
            # Check if lock is stale
            with lock_path.open(encoding="utf-8") as f:
                lock_data = json.load(f)

            last_heartbeat = lock_data.get(
                "last_heartbeat", lock_data.get("acquired_at", 0)
            )
            age_hours = (time.time() - last_heartbeat) / 3600

            if age_hours > self._global_config.stale_lock_hours:
                self.logger.warning(
                    f"Removing stale lock for {hook_name} (age: {age_hours:.2f}h)"
                )
                lock_path.unlink()
                self._stale_locks_cleaned[hook_name] += 1
            else:
                # Lock is not stale, someone else has it
                owner = lock_data.get("session_id", "unknown")
                self.logger.debug(
                    f"Active lock exists for {hook_name} owned by {owner}"
                )

        except Exception as e:
            self.logger.warning(f"Could not check lock staleness for {hook_name}: {e}")
            # If we can't read the lock file, it might be corrupted - remove it
            with suppress(OSError):
                lock_path.unlink()
                self._stale_locks_cleaned[hook_name] += 1

    def get_lock_stats(self) -> dict[str, t.Any]:
        """Get comprehensive statistics about lock usage for monitoring."""
        stats = {}

        for hook_name in self._hooks_requiring_locks:
            wait_times = self._lock_wait_times[hook_name]
            exec_times = self._lock_execution_times[hook_name]
            usage_list = self._lock_usage[hook_name]

            if not usage_list:
                stats[hook_name] = {
                    "total_acquisitions": 0,
                    "avg_wait_time": 0.0,
                    "max_wait_time": 0.0,
                    "min_wait_time": 0.0,
                    "avg_execution_time": 0.0,
                    "max_execution_time": 0.0,
                    "min_execution_time": 0.0,
                    "currently_locked": self._hook_locks[hook_name].locked(),
                    "lock_failures": self._lock_failures[hook_name],
                    "timeout_failures": self._timeout_failures[hook_name],
                    "success_rate": 1.0,
                    "lock_timeout": self._lock_timeouts.get(
                        hook_name, self._default_lock_timeout
                    ),
                }
            else:
                total_attempts = len(usage_list) + self._lock_failures[hook_name]
                success_rate = (
                    len(usage_list) / total_attempts if total_attempts > 0 else 1.0
                )

                base_stats = {
                    "total_acquisitions": len(usage_list),
                    "total_attempts": total_attempts,
                    "currently_locked": self._hook_locks[hook_name].locked(),
                    "lock_failures": self._lock_failures[hook_name],
                    "timeout_failures": self._timeout_failures[hook_name],
                    "success_rate": success_rate,
                    "lock_timeout": self._lock_timeouts.get(
                        hook_name, self._default_lock_timeout
                    ),
                }

                # Wait time statistics
                if wait_times:
                    base_stats.update(
                        {
                            "avg_wait_time": sum(wait_times) / len(wait_times),
                            "max_wait_time": max(wait_times),
                            "min_wait_time": min(wait_times),
                        }
                    )
                else:
                    base_stats.update(
                        {
                            "avg_wait_time": 0.0,
                            "max_wait_time": 0.0,
                            "min_wait_time": 0.0,
                        }
                    )

                # Execution time statistics
                if exec_times:
                    base_stats.update(
                        {
                            "avg_execution_time": sum(exec_times) / len(exec_times),
                            "max_execution_time": max(exec_times),
                            "min_execution_time": min(exec_times),
                        }
                    )
                else:
                    base_stats.update(
                        {
                            "avg_execution_time": 0.0,
                            "max_execution_time": 0.0,
                            "min_execution_time": 0.0,
                        }
                    )

                stats[hook_name] = base_stats

        return stats

    def add_hook_to_lock_list(self, hook_name: str) -> None:
        """Add a hook to the list requiring sequential execution."""
        self._hooks_requiring_locks.add(hook_name)
        self.logger.info(f"Added {hook_name} to hooks requiring locks")

    def remove_hook_from_lock_list(self, hook_name: str) -> None:
        """Remove a hook from the list requiring sequential execution."""
        self._hooks_requiring_locks.discard(hook_name)
        if hook_name in self._hook_locks:
            del self._hook_locks[hook_name]
        if hook_name in self._lock_usage:
            del self._lock_usage[hook_name]
        self.logger.info(f"Removed {hook_name} from hooks requiring locks")

    def is_hook_currently_locked(self, hook_name: str) -> bool:
        """Check if a hook is currently locked."""
        if not self.requires_lock(hook_name):
            return False
        return self._hook_locks[hook_name].locked()

    def set_hook_timeout(self, hook_name: str, timeout: float) -> None:
        """Set custom timeout for a specific hook.

        Args:
            hook_name: Name of the hook
            timeout: Timeout in seconds
        """
        self._lock_timeouts[hook_name] = timeout
        self.logger.info(f"Set custom timeout for {hook_name}: {timeout}s")

    def get_hook_timeout(self, hook_name: str) -> float:
        """Get timeout for a specific hook.

        Args:
            hook_name: Name of the hook

        Returns:
            Timeout in seconds
        """
        return self._lock_timeouts.get(hook_name, self._default_lock_timeout)

    # New protocol methods for global lock functionality

    def enable_global_lock(self, enabled: bool = True) -> None:
        """Enable or disable global lock functionality.

        Args:
            enabled: Whether to enable global locking
        """
        self._global_lock_enabled = enabled
        self._global_config.enabled = enabled
        self.logger.info(
            f"Global lock functionality {'enabled' if enabled else 'disabled'}"
        )

    def is_global_lock_enabled(self) -> bool:
        """Check if global lock functionality is enabled.

        Returns:
            True if global locking is enabled
        """
        return self._global_lock_enabled

    def get_global_lock_path(self, hook_name: str) -> Path:
        """Get the filesystem path for a hook's global lock file.

        Args:
            hook_name: Name of the hook

        Returns:
            Path to the lock file for the hook
        """
        return self._global_config.get_lock_path(hook_name)

    def cleanup_stale_locks(self, max_age_hours: float = 2.0) -> int:
        """Clean up stale lock files older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before a lock is considered stale

        Returns:
            Number of stale locks cleaned up
        """
        locks_dir = self._global_config.lock_directory
        if not locks_dir.exists():
            return 0

        cleaned_count = 0
        current_time = time.time()

        try:
            for lock_file in locks_dir.glob("*.lock"):
                cleaned_count += self._process_lock_file(
                    lock_file, max_age_hours, current_time
                )

        except OSError as e:
            self.logger.error(f"Could not access locks directory {locks_dir}: {e}")

        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} stale lock files")

        return cleaned_count

    def _process_lock_file(
        self, lock_file: Path, max_age_hours: float, current_time: float
    ) -> int:
        """Process a single lock file and return number of files cleaned."""
        try:
            # Check file age
            file_age_hours = (current_time - lock_file.stat().st_mtime) / 3600

            if file_age_hours > max_age_hours:
                return self._cleanup_stale_lock_file(
                    lock_file, max_age_hours, current_time
                )
            return 0

        except OSError as e:
            self.logger.warning(f"Could not process lock file {lock_file}: {e}")
            return 0

    def _cleanup_stale_lock_file(
        self, lock_file: Path, max_age_hours: float, current_time: float
    ) -> int:
        """Clean up a stale lock file and return 1 if successful."""
        try:
            with lock_file.open(encoding="utf-8") as f:
                lock_data = json.load(f)

            last_heartbeat = lock_data.get(
                "last_heartbeat", lock_data.get("acquired_at", 0)
            )
            heartbeat_age_hours = (current_time - last_heartbeat) / 3600

            if heartbeat_age_hours > max_age_hours:
                lock_file.unlink()
                hook_name = lock_file.stem
                self._stale_locks_cleaned[hook_name] += 1
                self.logger.info(
                    f"Cleaned stale lock: {lock_file} (age: {heartbeat_age_hours:.2f}h)"
                )
                return 1

        except (json.JSONDecodeError, KeyError):
            # Corrupted lock file, remove it
            lock_file.unlink()
            self.logger.warning(f"Cleaned corrupted lock file: {lock_file}")
            return 1

        return 0

    def get_global_lock_stats(self) -> dict[str, t.Any]:
        """Get comprehensive statistics about global lock usage.

        Returns:
            Dictionary containing global lock statistics and metrics
        """
        stats: dict[str, t.Any] = {
            "global_lock_enabled": self._global_lock_enabled,
            "lock_directory": str(self._global_config.lock_directory),
            "session_id": self._global_config.session_id,
            "hostname": self._global_config.hostname,
            "active_global_locks": list(self._active_global_locks),
            "active_heartbeat_tasks": len(self._heartbeat_tasks),
            "configuration": {
                "timeout_seconds": self._global_config.timeout_seconds,
                "stale_lock_hours": self._global_config.stale_lock_hours,
                "heartbeat_interval": self._global_config.session_heartbeat_interval,
                "max_retry_attempts": self._global_config.max_retry_attempts,
                "retry_delay_seconds": self._global_config.retry_delay_seconds,
                "enable_lock_monitoring": self._global_config.enable_lock_monitoring,
            },
            "statistics": {},
        }

        # Per-hook global lock statistics
        all_hooks = (
            set(self._global_lock_attempts.keys())
            | set(self._global_lock_successes.keys())
            | set(self._global_lock_failures.keys())
        )

        for hook_name in all_hooks:
            attempts = self._global_lock_attempts[hook_name]
            successes = self._global_lock_successes[hook_name]
            failures = self._global_lock_failures[hook_name]
            stale_cleaned = self._stale_locks_cleaned[hook_name]
            heartbeat_failures = self._heartbeat_failures[hook_name]

            success_rate = (successes / attempts) if attempts > 0 else 0.0

            stats["statistics"][hook_name] = {
                "attempts": attempts,
                "successes": successes,
                "failures": failures,
                "success_rate": success_rate,
                "stale_locks_cleaned": stale_cleaned,
                "heartbeat_failures": heartbeat_failures,
                "currently_locked": hook_name in self._active_global_locks,
                "has_heartbeat_task": hook_name in self._heartbeat_tasks,
            }

        # Overall statistics
        total_attempts = sum(self._global_lock_attempts.values())
        total_successes = sum(self._global_lock_successes.values())
        total_failures = sum(self._global_lock_failures.values())
        total_stale_cleaned = sum(self._stale_locks_cleaned.values())
        total_heartbeat_failures = sum(self._heartbeat_failures.values())

        stats["totals"] = {
            "total_attempts": total_attempts,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_success_rate": (total_successes / total_attempts)
            if total_attempts > 0
            else 0.0,
            "total_stale_locks_cleaned": total_stale_cleaned,
            "total_heartbeat_failures": total_heartbeat_failures,
        }

        return stats

    def configure_from_options(self, options: t.Any) -> None:
        """Configure the lock manager from CLI options.

        Args:
            options: Options object containing CLI arguments
        """
        self._global_config = GlobalLockConfig.from_options(options)
        self._global_lock_enabled = self._global_config.enabled

        # Apply stale lock cleanup if requested
        if hasattr(options, "global_lock_cleanup") and options.global_lock_cleanup:
            self.cleanup_stale_locks()

        self.logger.info(
            f"Configured lock manager: global_locks={
                'enabled' if self._global_lock_enabled else 'disabled'
            },"
            f" timeout={self._global_config.timeout_seconds}s, "
            f"lock_dir={self._global_config.lock_directory}"
        )

    def reset_hook_stats(self, hook_name: str | None = None) -> None:
        """Reset statistics for a specific hook or all hooks.

        Args:
            hook_name: Name of the hook to reset, or None for all hooks
        """
        if hook_name:
            self._lock_usage[hook_name].clear()
            self._lock_wait_times[hook_name].clear()
            self._lock_execution_times[hook_name].clear()
            self._lock_failures[hook_name] = 0
            self._timeout_failures[hook_name] = 0
            self.logger.info(f"Reset statistics for hook: {hook_name}")
        else:
            self._lock_usage.clear()
            self._lock_wait_times.clear()
            self._lock_execution_times.clear()
            self._lock_failures.clear()
            self._timeout_failures.clear()
            self.logger.info("Reset statistics for all hooks")

    def get_comprehensive_status(self) -> dict[str, t.Any]:
        """Get comprehensive status including configuration and health."""
        status = {
            "hooks_requiring_locks": list(self._hooks_requiring_locks),
            "default_timeout": self._default_lock_timeout,
            "custom_timeouts": self._lock_timeouts.copy(),
            "max_history": self._max_history,
            "lock_statistics": self.get_lock_stats(),
            "currently_locked_hooks": [
                hook
                for hook in self._hooks_requiring_locks
                if self.is_hook_currently_locked(hook)
            ],
            "total_lock_failures": sum(self._lock_failures.values()),
            "total_timeout_failures": sum(self._timeout_failures.values()),
        }

        # Add global lock information if enabled
        if self._global_lock_enabled:
            status["global_lock_stats"] = self.get_global_lock_stats()
        else:
            status["global_lock_stats"] = {
                "global_lock_enabled": False,
                "message": "Global locking is disabled",
            }

        return status


# Singleton instance
hook_lock_manager = HookLockManager()
