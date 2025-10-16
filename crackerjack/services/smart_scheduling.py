import os
import subprocess
import typing as t
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.models.protocols import ServiceProtocol, SmartSchedulingServiceProtocol


class SmartSchedulingService(SmartSchedulingServiceProtocol, ServiceProtocol):
    @depends.inject
    def __init__(self, console: Inject[Console], project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.cache_dir = Path.home() / ".cache" / "crackerjack"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    def should_scheduled_init(self) -> bool:
        init_schedule = os.environ.get("CRACKERJACK_INIT_SCHEDULE", "weekly")

        if init_schedule == "disabled":
            return False

        if init_schedule == "weekly":
            return self._check_weekly_schedule()
        if init_schedule == "commit-based":
            return self._check_commit_based_schedule()
        if init_schedule == "activity-based":
            return self._check_activity_based_schedule()

        return self._check_weekly_schedule()

    def record_init_timestamp(self) -> None:
        timestamp_file = self.cache_dir / f"{self.project_path.name}.init_timestamp"
        try:
            timestamp_file.write_text(datetime.now().isoformat())
        except OSError as e:
            self.console.print(
                f"[yellow]⚠️ Could not record init timestamp: {e}[/ yellow]",
            )

    def _check_weekly_schedule(self) -> bool:
        init_day = os.environ.get("CRACKERJACK_INIT_DAY", "monday")
        today = datetime.now().strftime("% A").lower()

        if today == init_day.lower():
            last_init = self._get_last_init_timestamp()
            if datetime.now() - last_init > timedelta(days=6):
                self.console.print(
                    f"[blue]📅 Weekly initialization scheduled for {init_day}[/ blue]",
                )
                return True

        return False

    def _check_commit_based_schedule(self) -> bool:
        commits_since_init = self._count_commits_since_init()
        threshold = int(os.environ.get("CRACKERJACK_INIT_COMMITS", "50"))

        if commits_since_init >= threshold:
            self.console.print(
                f"[blue]📊 {commits_since_init} commits since last init "
                f"(threshold: {threshold})[/ blue]",
            )
            return True

        return False

    def _check_activity_based_schedule(self) -> bool:
        if self._has_recent_activity() and self._days_since_init() >= 7:
            self.console.print(
                "[blue]⚡ Recent activity detected, initialization recommended[/ blue]",
            )
            return True

        return False

    def _get_last_init_timestamp(self) -> datetime:
        timestamp_file = self.cache_dir / f"{self.project_path.name}.init_timestamp"

        if timestamp_file.exists():
            with suppress(OSError, ValueError):
                timestamp_str = timestamp_file.read_text().strip()
                return datetime.fromisoformat(timestamp_str)

        return datetime.now() - timedelta(days=30)

    def _count_commits_since_init(self) -> int:
        since_date = self._get_last_init_timestamp().strftime("% Y - % m - % d")

        try:
            result = subprocess.run(
                ["git", "log", f"--since ={since_date}", "--oneline"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode == 0:
                return len([line for line in result.stdout.strip().split("\n") if line])

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return 0

    def _has_recent_activity(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--since=24.hours", "--oneline"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            return result.returncode == 0 and bool(result.stdout.strip())

        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _days_since_init(self) -> int:
        last_init = self._get_last_init_timestamp()
        return (datetime.now() - last_init).days
