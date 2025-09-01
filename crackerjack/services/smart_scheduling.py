"""Smart scheduling service for automated initialization.

This module handles intelligent scheduling of crackerjack initialization based on
various triggers like time, commits, or activity. Split from tool_version_service.py.
"""

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console


class SmartSchedulingService:
    """Service for intelligent scheduling of crackerjack operations."""

    def __init__(self, console: Console, project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.cache_dir = Path.home() / ".cache" / "crackerjack"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def should_scheduled_init(self) -> bool:
        """Check if initialization should run based on configured schedule."""
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
        """Record the current timestamp as the last initialization time."""
        timestamp_file = self.cache_dir / f"{self.project_path.name}.init_timestamp"
        try:
            timestamp_file.write_text(datetime.now().isoformat())
        except OSError as e:
            self.console.print(
                f"[yellow]⚠️ Could not record init timestamp: {e}[/yellow]",
            )

    def _check_weekly_schedule(self) -> bool:
        """Check if weekly initialization is due."""
        init_day = os.environ.get("CRACKERJACK_INIT_DAY", "monday")
        today = datetime.now().strftime("%A").lower()

        if today == init_day.lower():
            last_init = self._get_last_init_timestamp()
            if datetime.now() - last_init > timedelta(days=6):
                self.console.print(
                    f"[blue]📅 Weekly initialization scheduled for {init_day}[/blue]",
                )
                return True

        return False

    def _check_commit_based_schedule(self) -> bool:
        """Check if initialization is due based on commit count."""
        commits_since_init = self._count_commits_since_init()
        threshold = int(os.environ.get("CRACKERJACK_INIT_COMMITS", "50"))

        if commits_since_init >= threshold:
            self.console.print(
                f"[blue]📊 {commits_since_init} commits since last init "
                f"(threshold: {threshold})[/blue]",
            )
            return True

        return False

    def _check_activity_based_schedule(self) -> bool:
        """Check if initialization is due based on recent activity."""
        if self._has_recent_activity() and self._days_since_init() >= 7:
            self.console.print(
                "[blue]⚡ Recent activity detected, initialization recommended[/blue]",
            )
            return True

        return False

    def _get_last_init_timestamp(self) -> datetime:
        """Get the timestamp of the last initialization."""
        timestamp_file = self.cache_dir / f"{self.project_path.name}.init_timestamp"

        if timestamp_file.exists():
            from contextlib import suppress

            with suppress(OSError, ValueError):
                timestamp_str = timestamp_file.read_text().strip()
                return datetime.fromisoformat(timestamp_str)

        return datetime.now() - timedelta(days=30)

    def _count_commits_since_init(self) -> int:
        """Count git commits since last initialization."""
        since_date = self._get_last_init_timestamp().strftime("%Y-%m-%d")

        try:
            result = subprocess.run(
                ["git", "log", f"--since={since_date}", "--oneline"],
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
        """Check if there has been recent git activity."""
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
        """Calculate days since last initialization."""
        last_init = self._get_last_init_timestamp()
        return (datetime.now() - last_init).days
