"""Smart file filter combining incremental scanning and hash markers.

This is the main entry point for HookExecutor integration.
"""

import logging
import typing as t
from pathlib import Path

from crackerjack.models.protocols import ServiceProtocol

from .incremental_scanner import IncrementalScanner
from .marker_tracker import MarkerTracker

logger = logging.getLogger(__name__)


class SmartFileFilterV2(ServiceProtocol):
    """Intelligent file filtering combining multiple strategies.

    Combines:
    - Git-diff based incremental scanning
    - Hash-based marker tracking
    - Periodic full scans
    - Graceful fallback
    """

    def __init__(
        self,
        repo_path: Path,
        use_incremental: bool = True,
        full_scan_interval_days: int = 7,
    ) -> None:
        """Initialize filter.

        Args:
            repo_path: Repository root path
            use_incremental: Enable incremental scanning (default: True)
            full_scan_interval_days: Days between forced full scans (default: 7)
        """
        self.repo_path = Path(repo_path)
        self.use_incremental = use_incremental

        self.scanner = IncrementalScanner(
            repo_path=repo_path,
            full_scan_interval_days=full_scan_interval_days,
        )
        self.marker_tracker = MarkerTracker(repo_path=repo_path)

    # ServiceProtocol implementation
    def initialize(self) -> None:
        """Initialize service."""
        logger.debug("SmartFileFilterV2 initialized")

    def cleanup(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> bool:
        """Check service health."""
        return True

    def shutdown(self) -> None:
        """Shutdown service."""
        pass

    def metrics(self) -> dict[str, t.Any]:
        """Get service metrics."""
        return {}

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return True

    def register_resource(self, resource: t.Any) -> None:
        """Register resource."""
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        """Cleanup resource."""
        pass

    def record_error(self, error: Exception) -> None:
        """Record error."""
        pass

    def increment_requests(self) -> None:
        """Increment request counter."""
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        """Get custom metric."""
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        """Set custom metric."""
        pass

    # Core API
    def get_files_for_scan(
        self,
        tool_name: str,
        force_incremental: bool = False,
    ) -> list[Path]:
        """Get files that need scanning for a tool.

        This is the main entry point used by HookExecutor.

        Args:
            tool_name: Name of the quality tool
            force_incremental: Force incremental mode (default: False)

        Returns:
            List of files that need scanning
        """
        if not self.use_incremental:
            # Incremental mode disabled - scan all files
            logger.debug(f"Incremental disabled, full scan for {tool_name}")
            return self.scanner._get_all_python_files()

        # Use incremental scanning
        strategy, files = self.scanner.get_scan_strategy(
            tool_name=tool_name,
            force_full=force_incremental,
        )

        if strategy == "full":
            # Full scan - use all files
            return files

        if strategy == "incremental":
            # Incremental scan - use markers to filter further
            all_files = self.scanner._get_all_python_files()
            files_needing_scan = self.marker_tracker.get_files_needing_scan(
                tool_name,
                all_files,
            )

            # If marker tracker returns nothing, use git files
            if not files_needing_scan:
                return files

            return files_needing_scan

        return files

    def mark_scan_complete(
        self,
        tool_name: str,
        files: list[Path],
        was_full_scan: bool,
    ) -> None:
        """Mark scan as complete in tracking system.

        Args:
            tool_name: Name of the tool
            files: Files that were scanned
            was_full_scan: Whether this was a full scan
        """
        if was_full_scan:
            # Update full scan marker
            self.marker_tracker.mark_full_scan_complete(tool_name)
        else:
            # Update file markers
            self.marker_tracker.mark_scanned(tool_name, files)
