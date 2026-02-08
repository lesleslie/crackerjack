"""Coverage management for test results.

This module handles coverage extraction, ratchet system integration,
and badge updates for test coverage reporting.
"""

import json
import typing as t
from pathlib import Path

from crackerjack.models.protocols import (
    ConsoleInterface,
    CoverageBadgeServiceProtocol,
    CoverageRatchetProtocol,
)


class CoverageManager:
    """Manage test coverage data and reporting.

    This class handles:
    - Coverage extraction from coverage.json
    - Coverage ratchet system integration
    - Badge updates
    - Fallback coverage retrieval
    """

    def __init__(
        self,
        console: ConsoleInterface,
        pkg_path: Path,
        coverage_ratchet: CoverageRatchetProtocol | None = None,
        coverage_badge: CoverageBadgeServiceProtocol | None = None,
    ) -> None:
        """Initialize the coverage manager.

        Args:
            console: Console interface for output
            pkg_path: Package path for coverage files
            coverage_ratchet: Coverage ratchet service (optional)
            coverage_badge: Coverage badge service (optional)
        """
        self.console = console
        self.pkg_path = pkg_path
        self.coverage_ratchet = coverage_ratchet
        self._coverage_badge_service = coverage_badge

    def process_coverage_ratchet(self) -> bool:
        """Process coverage ratchet check and update.

        Returns:
            True if coverage passed ratchet check, False otherwise
        """
        if self.coverage_ratchet is None:
            return True

        ratchet_result = self.coverage_ratchet.check_and_update_coverage()
        self.update_coverage_badge(ratchet_result)
        return self.handle_ratchet_result(ratchet_result)

    def attempt_coverage_extraction(self) -> float | None:
        """Attempt to extract coverage from coverage.json.

        Returns:
            Coverage percentage or None if not found
        """
        current_coverage = self._get_coverage_from_file()
        if current_coverage is not None:
            return current_coverage
        return None

    def handle_coverage_extraction_result(
        self, current_coverage: float | None,
    ) -> float | None:
        """Handle coverage extraction result with console output.

        Args:
            current_coverage: Extracted coverage percentage

        Returns:
            The coverage percentage (unchanged)
        """
        if current_coverage is not None:
            self.console.print(
                f"[dim]📊 Coverage extracted from coverage.json: {current_coverage:.2f}%[/dim]",
            )
        return current_coverage

    def update_coverage_badge(self, ratchet_result: dict[str, t.Any]) -> None:
        """Update coverage badge based on current coverage.

        Args:
            ratchet_result: Result from ratchet check
        """
        if self._coverage_badge_service is None:
            return

        try:
            coverage_json_path = self.pkg_path / "coverage.json"
            ratchet_path = self.pkg_path / ".coverage-ratchet.json"

            if not coverage_json_path.exists():
                self.console.print(
                    "[yellow]ℹ️[/yellow] Coverage file doesn't exist yet, will be created after test run",
                )
            if not ratchet_path.exists():
                self.console.print(
                    "[yellow]ℹ️[/yellow] Coverage ratchet file doesn't exist yet, initializing...",
                )

            # Extract coverage
            current_coverage = self.attempt_coverage_extraction()
            current_coverage = self.handle_coverage_extraction_result(current_coverage)

            # Try fallback methods
            current_coverage = self._get_fallback_coverage(ratchet_result, current_coverage)

            # Update badge if we have valid coverage
            if current_coverage is not None and current_coverage >= 0:
                if self._coverage_badge_service.should_update_badge(current_coverage):
                    self._coverage_badge_service.update_readme_coverage_badge(
                        current_coverage,
                    )
                    self.console.print(
                        f"[green]✅[/green] Badge updated to {current_coverage:.2f}%",
                    )
                else:
                    self.console.print(
                        f"[dim]📊 Badge unchanged (current: {current_coverage:.2f}%)[/dim]",
                    )
            else:
                self.console.print(
                    "[yellow]⚠️[/yellow] No valid coverage data found for badge update",
                )

        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Badge update failed: {e}")

    def handle_ratchet_result(self, ratchet_result: dict[str, t.Any]) -> bool:
        """Handle ratchet check result with console output.

        Args:
            ratchet_result: Result from ratchet check

        Returns:
            True if ratchet check passed, False otherwise
        """
        if ratchet_result.get("success", False):
            if ratchet_result.get("improved", False):
                self._handle_coverage_improvement(ratchet_result)
            return True

        # Ratchet check failed
        if "message" in ratchet_result:
            self.console.print(f"[red]📉[/red] {ratchet_result['message']}")
        else:
            current = ratchet_result.get("current_coverage", 0)
            previous = ratchet_result.get("previous_coverage", 0)
            self.console.print(
                f"[red]📉[/red] Coverage regression: "
                f"{current:.2f}% < {previous:.2f}%",
            )
        return False

    def _get_coverage_from_file(self) -> float | None:
        """Extract coverage from coverage.json file.

        Returns:
            Coverage percentage or None if file doesn't exist
        """
        coverage_json_path = self.pkg_path / "coverage.json"

        if not coverage_json_path.exists():
            return None

        try:
            with open(coverage_json_path) as f:
                data = json.load(f)
                return data.get("totals", {}).get("percent_covered")
        except (json.JSONDecodeError, IOError, KeyError):
            return None

    def _try_service_coverage(self) -> float | None:
        """Try to get coverage from ratchet service as fallback.

        Returns:
            Coverage percentage or None if unavailable
        """
        if self.coverage_ratchet is None:
            return None

        try:
            current_coverage = self.coverage_ratchet.get_baseline_coverage()
            if current_coverage is not None and current_coverage > 0:
                self.console.print(
                    f"[dim]📊 Coverage from service fallback: {current_coverage:.2f}%[/dim]",
                )
                return current_coverage
            return None
        except (AttributeError, Exception):
            return None

    def _handle_zero_coverage_fallback(self, current_coverage: float | None) -> None:
        """Handle zero coverage fallback case.

        Args:
            current_coverage: Current coverage value
        """
        coverage_json_path = self.pkg_path / "coverage.json"
        if current_coverage is None and coverage_json_path.exists():
            self.console.print(
                "[yellow]⚠️[/yellow] Skipping 0.0% fallback when coverage.json exists",
            )

    def _get_fallback_coverage(
        self, ratchet_result: dict[str, t.Any], current_coverage: float | None,
    ) -> float | None:
        """Get fallback coverage from various sources.

        Args:
            ratchet_result: Result from ratchet check
            current_coverage: Current coverage value

        Returns:
            Coverage percentage or None
        """
        if current_coverage is None and ratchet_result:
            if "current_coverage" in ratchet_result:
                current_coverage = ratchet_result["current_coverage"]
                if current_coverage is not None and current_coverage > 0:
                    self.console.print(
                        f"[dim]📊 Coverage from ratchet result: {current_coverage:.2f}%[/dim]",
                    )

        if current_coverage is None:
            current_coverage = self._try_service_coverage()
            if current_coverage is None:
                self._handle_zero_coverage_fallback(current_coverage)

        return current_coverage

    def _handle_coverage_improvement(self, ratchet_result: dict[str, t.Any]) -> None:
        """Handle coverage improvement with console output.

        Args:
            ratchet_result: Result from ratchet check with improvement info
        """
        improvement = ratchet_result.get("improvement", 0)
        current = ratchet_result.get("current_coverage", 0)

        self.console.print(
            f"[green]📈[/green] Coverage improved by {improvement:.2f}% "
            f"to {current:.2f}%",
        )
