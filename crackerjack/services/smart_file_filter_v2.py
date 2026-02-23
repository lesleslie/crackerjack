import logging
import typing as t
from pathlib import Path

from crackerjack.models.protocols import ServiceProtocol

from .incremental_scanner import IncrementalScanner
from .marker_tracker import MarkerTracker

logger = logging.getLogger(__name__)


class SmartFileFilterV2(ServiceProtocol):
    def __init__(
        self,
        repo_path: Path,
        use_incremental: bool = True,
        full_scan_interval_days: int = 7,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.use_incremental = use_incremental

        self.scanner = IncrementalScanner(
            repo_path=repo_path,
            full_scan_interval_days=full_scan_interval_days,
        )
        self.marker_tracker = MarkerTracker(repo_path=repo_path)

    def initialize(self) -> None:
        logger.debug("SmartFileFilterV2 initialized")

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

    def get_files_for_scan(
        self,
        tool_name: str,
        force_incremental: bool = False,
    ) -> list[Path]:
        if not self.use_incremental:
            logger.debug(f"Incremental disabled, full scan for {tool_name}")
            return self.scanner._get_all_python_files()

        strategy, files = self.scanner.get_scan_strategy(
            tool_name=tool_name,
            force_full=force_incremental,
        )

        if strategy == "full":
            return files

        if strategy == "incremental":
            all_files = self.scanner._get_all_python_files()
            files_needing_scan = self.marker_tracker.get_files_needing_scan(
                tool_name,
                all_files,
            )

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
        if was_full_scan:
            self.marker_tracker.mark_full_scan_complete(tool_name)
        else:
            self.marker_tracker.mark_scanned(tool_name, files)
