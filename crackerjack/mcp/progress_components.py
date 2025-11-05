import asyncio
import json
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import aiohttp
from acb.console import Console
from acb.depends import depends

from crackerjack.core.timeout_manager import get_timeout_manager


class JobDataCollector:
    def __init__(self, progress_dir: Path, websocket_url: str) -> None:
        self.progress_dir = progress_dir
        self.websocket_url = websocket_url
        self.console = depends.get_sync(Console)

    async def discover_jobs(self) -> dict[str, Any]:
        jobs_data = self._init_jobs_data()

        websocket_jobs = await self._discover_jobs_websocket()
        if websocket_jobs and websocket_jobs["total"] > 0:
            return {"method": "WebSocket", "data": websocket_jobs}

        filesystem_jobs = await self._discover_jobs_filesystem(jobs_data)
        return {"method": "File", "data": filesystem_jobs}

    def _init_jobs_data(self) -> dict[str, Any]:
        return {
            "active": 0,
            "completed": 0,
            "failed": 0,
            "total": 0,
            "individual_jobs": [],
            "total_issues": 0,
            "errors_fixed": 0,
            "errors_failed": 0,
            "current_errors": 0,
        }

    async def _discover_jobs_filesystem(
        self,
        jobs_data: dict[str, Any],
    ) -> dict[str, Any]:
        with suppress(Exception):
            if not self.progress_dir.exists():
                return jobs_data

            for progress_file in self.progress_dir.glob("job-* .json"):
                self._process_progress_file(progress_file, jobs_data)

        return jobs_data

    def _process_progress_file(
        self,
        progress_file: Path,
        jobs_data: dict[str, Any],
    ) -> None:
        with suppress(json.JSONDecodeError, OSError):
            with progress_file.open() as f:
                data = json.load(f)

            job_id = progress_file.stem.replace("job-", "")
            self._update_job_counters(data, jobs_data)
            self._aggregate_error_metrics(data, jobs_data)
            self._add_individual_job(job_id, data, jobs_data)

    def _update_job_counters(
        self,
        data: dict[str, Any],
        jobs_data: dict[str, Any],
    ) -> None:
        status = data.get("status", "unknown")
        if status == "running":
            jobs_data["active"] += 1
        elif status == "completed":
            jobs_data["completed"] += 1
        elif status == "failed":
            jobs_data["failed"] += 1
        jobs_data["total"] += 1

    def _aggregate_error_metrics(
        self,
        data: dict[str, Any],
        jobs_data: dict[str, Any],
    ) -> None:
        jobs_data["total_issues"] += data.get("total_issues", 0)
        jobs_data["errors_fixed"] += data.get("errors_fixed", 0)
        jobs_data["errors_failed"] += data.get("errors_failed", 0)

        current_errors_data = data.get("current_errors", {})
        current_errors = (
            current_errors_data.get("total", 0)
            if isinstance(current_errors_data, dict)
            else 0
        )
        jobs_data["current_errors"] += current_errors

    def _add_individual_job(
        self,
        job_id: str,
        data: dict[str, Any],
        jobs_data: dict[str, Any],
    ) -> None:
        status = data.get("status", "unknown")
        stage = data.get("current_stage", "Unknown")
        iteration = data.get("iteration", 0)
        max_iterations = data.get("max_iterations", 5)

        status_emoji = {
            "running": "🚀 Running",
            "completed": "✅ Done",
        }.get(status, "❌ Error")

        jobs_data["individual_jobs"].append(
            {
                "job_id": job_id[:8],
                "full_job_id": job_id,
                "project": data.get("project_name", "crackerjack"),
                "stage": stage,
                "progress": f"{iteration} / {max_iterations}",
                "status": status_emoji,
                "iteration": iteration,
                "max_iterations": max_iterations,
                "message": data.get("message", "Processing job..."),
                "errors": data.get("errors", []),
                "hook_failures": data.get("hook_failures", []),
                "test_failures": data.get("test_failures", []),
                "total_issues": data.get("total_issues", 0),
                "errors_fixed": data.get("errors_fixed", 0),
                "errors_failed": data.get("errors_failed", 0),
                "current_errors": data.get("current_errors", {}),
            },
        )

    async def _discover_jobs_websocket(self) -> dict[str, Any]:
        jobs_data: dict[str, Any] = {
            "active": 0,
            "completed": 0,
            "failed": 0,
            "total": 0,
            "individual_jobs": [],
            "total_issues": 0,
            "errors_fixed": 0,
            "errors_failed": 0,
            "current_errors": 0,
        }

        timeout_manager = get_timeout_manager()

        with suppress(Exception):
            async with timeout_manager.timeout_context(
                "network_operations",
                timeout=5.0,
            ):
                websocket_base = self.websocket_url.replace("ws://", "http://").replace(
                    "wss://",
                    "https://",
                )

                async with (
                    aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as session,
                    session.get(f"{websocket_base}/") as response,
                ):
                    if response.status == 200:
                        data = await response.json()

                        active_jobs = data.get("active_jobs_detailed", [])

                        for job in active_jobs:
                            job_id = job.get("job_id", "unknown")
                            status = job.get("status", "unknown")

                            if status == "running":
                                jobs_data["active"] += 1
                            elif status == "completed":
                                jobs_data["completed"] += 1
                            elif status == "failed":
                                jobs_data["failed"] += 1

                            jobs_data["total"] += 1

                            job_entry = {
                                "job_id": job_id,
                                "status": status,
                                "iteration": job.get("iteration", 1),
                                "max_iterations": job.get("max_iterations", 10),
                                "current_stage": job.get("current_stage", "unknown"),
                                "message": job.get("message", "Processing..."),
                                "project": job.get("project", "crackerjack"),
                                "total_issues": job.get("total_issues", 0),
                                "errors_fixed": job.get("errors_fixed", 0),
                                "errors_failed": job.get("errors_failed", 0),
                                "current_errors": job.get("current_errors", 0),
                                "overall_progress": job.get("overall_progress", 0.0),
                                "stage_progress": job.get("stage_progress", 0.0),
                            }
                            jobs_data["individual_jobs"].append(job_entry)

                            jobs_data["total_issues"] += job.get("total_issues", 0)
                            jobs_data["errors_fixed"] += job.get("errors_fixed", 0)
                            jobs_data["errors_failed"] += job.get("errors_failed", 0)

        return jobs_data


class ServiceHealthChecker:
    def __init__(self) -> None:
        self.console = depends.get_sync(Console)

    async def collect_services_data(self) -> list[tuple[str, str, str]]:
        services = []

        services.extend(
            (
                await self._check_websocket_server(),
                self._check_mcp_server(),
            ),
        )

        services.extend(
            (
                self._check_service_watchdog(),
                ("File Monitor", "🟢 Watching", "0"),
            ),
        )

        return services

    async def _check_websocket_server(self) -> tuple[str, str, str]:
        timeout_manager = get_timeout_manager()

        try:
            async with timeout_manager.timeout_context(
                "network_operations",
                timeout=3.0,
            ):
                async with (
                    aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=2),
                    ) as session,
                    session.get("http: //localhost: 8675/") as response,
                ):
                    if response.status == 200:
                        data = await response.json()
                        connections = data.get("total_connections", 0)
                        len(data.get("active_jobs", []))
                        return (
                            "WebSocket Server",
                            f"🟢 Active ({connections} conn)",
                            "0",
                        )
                    return ("WebSocket Server", "🔴 HTTP Error", "1")
        except Exception:
            return ("WebSocket Server", "🔴 Connection Failed", "1")

    def _check_mcp_server(self) -> tuple[str, str, str]:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "crackerjack.*mcp"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                return ("MCP Server", "🟢 Process Active", "0")
            return ("MCP Server", "🔴 No Process", "0")
        except subprocess.TimeoutExpired:
            return ("MCP Server", "🔴 Process Check Timeout", "0")
        except Exception:
            return ("MCP Server", "🔴 Check Failed", "0")

    def _check_service_watchdog(self) -> tuple[str, str, str]:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "crackerjack.*watchdog"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                return ("Service Watchdog", "🟢 Active", "0")
            return ("Service Watchdog", "🔴 Inactive", "0")
        except subprocess.TimeoutExpired:
            return ("Service Watchdog", "🔴 Process Check Timeout", "0")
        except Exception:
            return ("Service Watchdog", "🔴 Check Failed", "0")


class ErrorCollector:
    def __init__(self) -> None:
        self.console = depends.get_sync(Console)

    async def collect_recent_errors(self) -> list[tuple[str, str, str, str]]:
        errors: list[tuple[str, str, str, str]] = []

        errors.extend(self._check_debug_logs())

        errors.extend(self._check_crackerjack_logs())

        if not errors:
            errors = [
                (
                    time.strftime(" % H: % M: % S"),
                    "system",
                    "No recent errors found",
                    "Clean",
                ),
                (" - - : - - : --", "monitor", "System monitoring active", "Status"),
            ]

        return errors[-5:]

    def _check_debug_logs(self) -> list[tuple[str, str, str, str]]:
        errors: list[tuple[str, str, str, str]] = []

        with suppress(Exception):
            debug_log = Path(tempfile.gettempdir()) / "tui_debug.log"
            if debug_log.exists():
                errors = self._extract_debug_log_errors(debug_log)

        return errors

    def _extract_debug_log_errors(
        self,
        debug_log: Path,
    ) -> list[tuple[str, str, str, str]]:
        errors: list[tuple[str, str, str, str]] = []

        with debug_log.open() as f:
            lines = f.readlines()[-10:]

        for line in lines:
            if self._is_debug_error_line(line):
                error_entry = self._parse_debug_error_line(line)
                if error_entry:
                    errors.append(error_entry)

        return errors

    def _is_debug_error_line(self, line: str) -> bool:
        return any(indicator in line for indicator in ("ERROR", "Exception", "Failed"))

    def _parse_debug_error_line(self, line: str) -> tuple[str, str, str, str] | None:
        parts = line.strip().split(" ", 2)
        if len(parts) < 3:
            return None

        timestamp = parts[0]
        error_msg = self._truncate_debug_message(parts[2])
        return (timestamp, "debug", error_msg, "System")

    def _truncate_debug_message(self, message: str) -> str:
        return message[:40] + "..." if len(message) > 40 else message

    def _check_crackerjack_logs(self) -> list[tuple[str, str, str, str]]:
        errors: list[tuple[str, str, str, str]] = []

        with suppress(Exception):
            for log_file in Path(tempfile.gettempdir()).glob(
                "crackerjack - debug-*.log"
            ):
                if self._is_log_file_recent(log_file):
                    errors.extend(self._extract_errors_from_log_file(log_file))

        return errors

    def _is_log_file_recent(self, log_file: Path) -> bool:
        return time.time() - log_file.stat().st_mtime < 3600

    def _extract_errors_from_log_file(
        self,
        log_file: Path,
    ) -> list[tuple[str, str, str, str]]:
        errors: list[tuple[str, str, str, str]] = []

        with log_file.open() as f:
            lines = f.readlines()[-5:]

        for line in lines:
            if self._is_error_line(line):
                error_entry = self._create_error_entry(line, log_file)
                errors.append(error_entry)

        return errors

    def _is_error_line(self, line: str) -> bool:
        return any(
            keyword in line.lower() for keyword in ("error", "failed", "exception")
        )

    def _create_error_entry(
        self,
        line: str,
        log_file: Path,
    ) -> tuple[str, str, str, str]:
        timestamp = time.strftime(
            " % H: % M: % S",
            time.localtime(log_file.stat().st_mtime),
        )
        error_msg = self._truncate_error_message(line.strip())
        return (timestamp, "job", error_msg, "Crackerjack")

    def _truncate_error_message(self, message: str) -> str:
        return message[:50] + "..." if len(message) > 50 else message


class ServiceManager:
    def __init__(self) -> None:
        self.started_services: list[tuple[str, subprocess.Popen[bytes]]] = []
        self.console = depends.get_sync(Console)

    async def ensure_services_running(self) -> None:
        with suppress(Exception):
            websocket_running = await self._check_websocket_server()
            mcp_running = self._check_mcp_server()

            self._cleanup_dead_services()

            if not websocket_running:
                await self._start_websocket_server()

            if not mcp_running:
                await self._start_mcp_server()

            await self._start_service_watchdog()

    def _cleanup_dead_services(self) -> None:
        self.started_services = [
            (service_name, process)
            for service_name, process in self.started_services
            if process.poll() is None
        ]

    async def _check_websocket_server(self) -> bool:
        timeout_manager = get_timeout_manager()

        with suppress(Exception):
            async with timeout_manager.timeout_context(
                "network_operations",
                timeout=3.0,
            ):
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as session:
                    async with session.get("http: //localhost: 8675/") as response:
                        return response.status == 200
        return False

    def _check_mcp_server(self) -> bool:
        with suppress(Exception):
            result = subprocess.run(
                ["pgrep", "-f", "crackerjack.*mcp"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            return result.returncode == 0
        return False

    def collect_services_data(self) -> list[tuple[str, str, str]]:
        """Check all services and return their status information."""
        mcp_status = "running" if self._check_mcp_server() else "stopped"
        return [
            ("mcp_server", mcp_status, "localhost:8675"),
            ("websocket_server", "unknown", "localhost:8676"),
        ]

    async def _start_websocket_server(self) -> None:
        with suppress(Exception):
            process = subprocess.Popen(
                ["python", "-m", "crackerjack", "--start-websocket-server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self.started_services.append(("websocket", process))
            await asyncio.sleep(2)

    async def _start_mcp_server(self) -> None:
        with suppress(Exception):
            process = subprocess.Popen(
                ["python", "-m", "crackerjack", "--start-mcp-server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self.started_services.append(("mcp", process))
            await asyncio.sleep(2)

    async def _start_service_watchdog(self) -> None:
        with suppress(Exception):
            result = subprocess.run(
                ["pgrep", "-f", "crackerjack.*watchdog"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                return

            process = subprocess.Popen(
                ["python", "-m", "crackerjack", "--watchdog"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self.started_services.append(("watchdog", process))

    def cleanup_services(self) -> None:
        for _service_name, process in self.started_services:
            self._cleanup_single_service(process)
        self.started_services.clear()

    def _cleanup_single_service(self, process: subprocess.Popen[bytes]) -> None:
        with suppress(Exception):
            if process.poll() is not None:
                return

            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    import os

                    os.kill(process.pid, 9)


class TerminalRestorer:
    @staticmethod
    def restore_terminal() -> None:
        try:
            import subprocess
            import sys

            restoration_sequences = [
                "\033[?1049l",
                "\033[?1000l",
                "\033[?1003l",
                "\033[?1015l",
                "\033[?1006l",
                "\033[?25h",
                "\033[?1004l",
                "\033[?2004l",
                "\033[?7h",
                "\033[0m",
                "\r",
            ]

            for sequence in restoration_sequences:
                sys.stdout.write(sequence)
            sys.stdout.flush()

            subprocess.run(
                ["stty", "echo", "icanon", "icrnl", "ixon"],
                check=False,
                capture_output=True,
                timeout=1,
            )

        except Exception:
            with suppress(Exception):
                import subprocess
                import sys

                critical_sequences = [
                    "\033[?1049l",
                    "\033[?25h",
                    "\033[0m",
                    "\r",
                ]

                for sequence in critical_sequences:
                    sys.stdout.write(sequence)
                sys.stdout.flush()

                subprocess.run(
                    ["stty", "sane"],
                    check=False,
                    capture_output=True,
                    timeout=1,
                )
