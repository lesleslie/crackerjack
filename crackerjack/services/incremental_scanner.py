"""Hybrid incremental scanner using git-diff + markers.

Features:
- Git-diff based detection (fast, good for daily workflow)
- Configurable full-scan interval (default: 7 days)
- Graceful fallback to full scan if git unavailable
- Type-safe with Protocol-based dependencies
"""

import logging
import subprocess
import typing as t
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ScanStrategy = t.Literal["incremental", "full"]


class IncrementalScanner:
    """Hybrid incremental scanner using git-diff + markers."""

    def __init__(
        self,
        repo_path: Path,
        full_scan_interval_days: int = 7,
    ) -> None:
        """Initialize scanner.

        Args:
            repo_path: Repository root path
            full_scan_interval_days: Days between forced full scans (default: 7)
        """
        self.repo_path = Path(repo_path)
        self.full_scan_interval_days = full_scan_interval_days

    def get_scan_strategy(
        self,
        tool_name: str,
        force_full: bool = False,
    ) -> tuple[ScanStrategy, list[Path]]:
        """Determine scan strategy and files to scan.

        Args:
            tool_name: Name of tool being run
            force_full: Force full scan regardless of heuristics

        Returns:
            Tuple of (strategy_type, files_to_scan)
        """
        if force_full or self._should_force_full_scan(tool_name):
            logger.debug(f"Full scan required for {tool_name}")
            return "full", self._get_all_python_files()

        # Try git-diff approach
        git_files = self._get_changed_files_git()
        if git_files:
            logger.debug(
                f"Git-diff incremental scan: {len(git_files)} files for {tool_name}"
            )
            return "incremental", git_files

        # Fallback to full scan
        logger.debug(f"Fallback to full scan for {tool_name}")
        return "full", self._get_all_python_files()

    def _get_changed_files_git(self) -> list[Path] | None:
        """Get files changed since last commit using git-diff.

        Returns:
            List of changed Python files, or None if git unavailable
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.repo_path,
                check=False,
            )

            if result.returncode != 0:
                logger.debug(f"Git diff failed: {result.stderr.strip()}")
                return None

            changed_files = [
                self.repo_path / f
                for f in result.stdout.strip().split("\n")
                if f and f.endswith(".py")
            ]

            return changed_files if changed_files else None

        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.debug(f"Git unavailable: {e}")
            return None

    def _should_force_full_scan(self, tool_name: str) -> bool:
        """Check if we should force a full scan.

        Forces full scan if:
        - Last scan was >7 days ago
        - Marker file doesn't exist

        Args:
            tool_name: Name of tool

        Returns:
            True if full scan required
        """
        marker_file = self.repo_path / ".crackerjack" / f"{tool_name}_last_full.txt"

        if not marker_file.exists():
            logger.debug(f"No full scan marker for {tool_name}")
            return True

        try:
            mtime = datetime.fromtimestamp(marker_file.stat().st_mtime)
            days_since_scan = (datetime.now() - mtime).days

            if days_since_scan >= self.full_scan_interval_days:
                logger.debug(
                    f"Last full scan {days_since_scan} days ago for {tool_name}"
                )
                return True

        except OSError as e:
            logger.warning(f"Failed to read marker file: {e}")
            return True

        return False

    def _get_all_python_files(self) -> list[Path]:
        """Get all Python files in repository.

        Returns:
            List of all .py files
        """
        try:
            return list(self.repo_path.rglob("*.py"))
        except OSError as e:
            logger.error(f"Failed to scan repository: {e}")
            return []
