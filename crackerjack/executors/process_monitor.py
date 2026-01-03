"""Process monitoring utilities to detect hung/stalled processes."""

import logging
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessMetrics:
    """Metrics for monitoring process health."""

    pid: int
    cpu_percent: float
    memory_mb: float
    elapsed_seconds: float
    is_responsive: bool
    last_activity_time: float


class ProcessMonitor:
    """Monitor subprocess execution to detect hung/stalled processes.

    Tracks CPU usage, memory consumption, and activity to detect when a process
    is hung (not making progress) vs legitimately slow.
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        cpu_threshold: float = 0.1,
        stall_timeout: float = 180.0,
    ) -> None:
        """Initialize process monitor.

        Args:
            check_interval: Seconds between health checks
            cpu_threshold: Minimum CPU % to consider process active
            stall_timeout: Seconds of inactivity before declaring hung
        """
        self.check_interval = check_interval
        self.cpu_threshold = cpu_threshold
        self.stall_timeout = stall_timeout
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None

    def monitor_process(
        self,
        process: subprocess.Popen[str],
        hook_name: str,
        timeout: int,
        on_stall: Callable[[str, ProcessMetrics], None] | None = None,
    ) -> None:
        """Monitor a running process for signs of hanging.

        Args:
            process: The subprocess to monitor
            hook_name: Name of the hook being executed
            timeout: Total timeout for the process
            on_stall: Optional callback when stall detected
        """
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(process, hook_name, timeout, on_stall),
            daemon=True,
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop the monitoring thread."""
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)

    def _monitor_loop(
        self,
        process: subprocess.Popen[str],
        hook_name: str,
        timeout: int,
        on_stall: Callable[[str, ProcessMetrics], None] | None,
    ) -> None:
        """Main monitoring loop that checks process health."""
        start_time = time.time()
        last_cpu_check = start_time
        consecutive_zero_cpu = 0

        while not self._stop_event.is_set():
            elapsed = time.time() - start_time

            # Check process status and timeout
            if self._should_stop_monitoring(process, hook_name, elapsed, timeout):
                return

            # Periodic health check
            if time.time() - last_cpu_check >= self.check_interval:
                consecutive_zero_cpu = self._perform_health_check(
                    process.pid,
                    hook_name,
                    elapsed,
                    consecutive_zero_cpu,
                    on_stall,
                )
                last_cpu_check = time.time()

            # Sleep briefly before next iteration
            time.sleep(min(5.0, self.check_interval / 6))

    def _should_stop_monitoring(
        self,
        process: subprocess.Popen[str],
        hook_name: str,
        elapsed: float,
        timeout: int,
    ) -> bool:
        """Check if monitoring should stop due to process completion or timeout."""
        # Check if process is still running
        if process.poll() is not None:
            logger.debug(f"{hook_name}: Process completed, stopping monitor")
            return True

        # Check if total timeout exceeded
        if elapsed > timeout:
            logger.warning(
                f"{hook_name}: Timeout of {timeout}s exceeded (elapsed: {elapsed:.1f}s)"
            )
            return True

        return False

    def _perform_health_check(
        self,
        pid: int,
        hook_name: str,
        elapsed: float,
        consecutive_zero_cpu: int,
        on_stall: Callable[[str, ProcessMetrics], None] | None,
    ) -> int:
        """Perform health check and return updated consecutive_zero_cpu counter."""
        metrics = self._get_process_metrics(pid, elapsed)

        if not metrics:
            return consecutive_zero_cpu

        self._log_metrics(hook_name, metrics)

        # Check CPU activity
        return self._check_cpu_activity(
            hook_name, metrics, consecutive_zero_cpu, on_stall
        )

    def _log_metrics(self, hook_name: str, metrics: ProcessMetrics) -> None:
        """Log process metrics for debugging."""
        logger.debug(
            f"{hook_name}: CPU={metrics.cpu_percent:.1f}%, "
            f"MEM={metrics.memory_mb:.1f}MB, "
            f"elapsed={metrics.elapsed_seconds:.1f}s"
        )

    def _check_cpu_activity(
        self,
        hook_name: str,
        metrics: ProcessMetrics,
        consecutive_zero_cpu: int,
        on_stall: Callable[[str, ProcessMetrics], None] | None,
    ) -> int:
        """Check CPU activity and handle stall detection."""
        # CPU below threshold - potential hang
        if metrics.cpu_percent < self.cpu_threshold:
            consecutive_zero_cpu += 1
            return self._handle_potential_stall(
                hook_name, metrics, consecutive_zero_cpu, on_stall
            )

        # CPU activity detected - reset counter
        return 0

    def _handle_potential_stall(
        self,
        hook_name: str,
        metrics: ProcessMetrics,
        consecutive_zero_cpu: int,
        on_stall: Callable[[str, ProcessMetrics], None] | None,
    ) -> int:
        """Handle potential process stall."""
        stall_duration = consecutive_zero_cpu * self.check_interval

        if stall_duration >= self.stall_timeout:
            logger.warning(
                f"\n{hook_name}: Process appears hung "
                f"(CPU < {self.cpu_threshold}% for {stall_duration:.1f}s)"
            )

            # Notify callback if provided
            if on_stall:
                on_stall(hook_name, metrics)

            # Reset counter after reporting
            return 0

        return consecutive_zero_cpu

    def _get_process_metrics(self, pid: int, elapsed: float) -> ProcessMetrics | None:
        """Get current metrics for a process using ps command.

        Args:
            pid: Process ID to check
            elapsed: Elapsed time since process start

        Returns:
            ProcessMetrics if process exists, None otherwise
        """
        try:
            # Use ps to get CPU and memory for the process
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "%cpu,%mem"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )

            if result.returncode != 0:
                return None

            # Parse ps output (skip header line)
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return None

            values = lines[1].split()
            if len(values) < 2:
                return None

            cpu_percent = float(values[0])
            mem_percent = float(values[1])

            # Estimate memory in MB (rough approximation)
            # This is % of total system memory
            memory_mb = mem_percent * 16384 / 100  # Assuming 16GB system

            is_responsive = cpu_percent >= self.cpu_threshold

            return ProcessMetrics(
                pid=pid,
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                elapsed_seconds=elapsed,
                is_responsive=is_responsive,
                last_activity_time=time.time() if is_responsive else 0.0,
            )

        except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
            logger.debug(f"Failed to get metrics for PID {pid}: {e}")
            return None
