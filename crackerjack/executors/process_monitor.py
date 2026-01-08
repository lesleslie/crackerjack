import logging
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessMetrics:
    pid: int
    cpu_percent: float
    memory_mb: float
    elapsed_seconds: float
    is_responsive: bool
    last_activity_time: float


class ProcessMonitor:
    def __init__(
        self,
        check_interval: float = 30.0,
        cpu_threshold: float = 0.1,
        stall_timeout: float = 180.0,
    ) -> None:
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
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(process, hook_name, timeout, on_stall),
            daemon=True,
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
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
        start_time = time.time()
        last_cpu_check = start_time
        consecutive_zero_cpu = 0

        while not self._stop_event.is_set():
            elapsed = time.time() - start_time

            if self._should_stop_monitoring(process, hook_name, elapsed, timeout):
                return

            if time.time() - last_cpu_check >= self.check_interval:
                consecutive_zero_cpu = self._perform_health_check(
                    process.pid,
                    hook_name,
                    elapsed,
                    consecutive_zero_cpu,
                    on_stall,
                )
                last_cpu_check = time.time()

            time.sleep(min(5.0, self.check_interval / 6))

    def _should_stop_monitoring(
        self,
        process: subprocess.Popen[str],
        hook_name: str,
        elapsed: float,
        timeout: int,
    ) -> bool:
        if process.poll() is not None:
            logger.debug(f"{hook_name}: Process completed, stopping monitor")
            return True

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
        metrics = self._get_process_metrics(pid, elapsed)

        if not metrics:
            return consecutive_zero_cpu

        self._log_metrics(hook_name, metrics)

        return self._check_cpu_activity(
            hook_name, metrics, consecutive_zero_cpu, on_stall
        )

    def _log_metrics(self, hook_name: str, metrics: ProcessMetrics) -> None:
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
        if metrics.cpu_percent < self.cpu_threshold:
            consecutive_zero_cpu += 1
            return self._handle_potential_stall(
                hook_name, metrics, consecutive_zero_cpu, on_stall
            )

        return 0

    def _handle_potential_stall(
        self,
        hook_name: str,
        metrics: ProcessMetrics,
        consecutive_zero_cpu: int,
        on_stall: Callable[[str, ProcessMetrics], None] | None,
    ) -> int:
        stall_duration = consecutive_zero_cpu * self.check_interval

        if stall_duration >= self.stall_timeout:
            if on_stall:
                on_stall(hook_name, metrics)

            return 0

        return consecutive_zero_cpu

    def _get_process_metrics(self, pid: int, elapsed: float) -> ProcessMetrics | None:
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "%cpu, %mem"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )

            if result.returncode != 0:
                return None

            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return None

            values = lines[1].split()
            if len(values) < 2:
                return None

            cpu_percent = float(values[0])
            mem_percent = float(values[1])

            memory_mb = mem_percent * 16384 / 100

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
