"""Coverage management for test results.

This module handles coverage extraction, ratchet system integration,
and badge updates for test coverage reporting.

The CoverageManager class encapsulates all coverage-related logic,
providing a clean separation from test orchestration. It handles
multiple data sources for coverage information and integrates with
both the coverage ratchet system (for enforcement) and badge services
(for reporting).

Coverage Data Flow:
    1. Extract from coverage.json (primary source)
    2. Fallback to ratchet service (secondary source)
    3. Update badge with current coverage
    4. Report coverage improvements/regressions

Typical usage:
    >>> from crackerjack.services.testing.coverage_manager import CoverageManager
    >>> manager = CoverageManager(console, pkg_path, ratchet, badge_service)
    >>> success = manager.process_coverage_ratchet()
    >>> if not success:
    ...     # Coverage regression detected
    ...     pass

The manager is designed to be fault-tolerant, gracefully handling
missing coverage files or service unavailability.
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

    This class encapsulates all coverage-related operations, providing a
    single point of responsibility for coverage data management. It handles
    extraction from multiple sources, ratchet system integration, and badge
    updates with proper error handling and fallback mechanisms.

    Core Responsibilities:
        - Extract coverage from coverage.json file
        - Integrate with coverage ratchet system for enforcement
        - Update coverage badges in README
        - Provide fallback coverage retrieval when primary sources fail
        - Report coverage improvements and regressions

    Design Patterns:
        - Dependency Injection: All services injected via __init__
        - Fault Tolerance: Graceful degradation when sources unavailable
        - Multi-Source Fallback: Tries multiple coverage data sources
        - Protocol-Based: Works with any Console/CoverageRatchet/CoverageBadge

    Attributes:
        console: Console interface for user feedback
        pkg_path: Package path for locating coverage files
        coverage_ratchet: Coverage ratchet service (optional)
        _coverage_badge_service: Badge update service (optional)

    Example:
        >>> from crackerjack.services.testing.coverage_manager import CoverageManager
        >>> manager = CoverageManager(console, Path("/project"), ratchet, badge)
        >>> # Process ratchet check and update badge
        >>> success = manager.process_coverage_ratchet()
        >>> if not success:
        ...     print("Coverage regression detected!")
    """

    def __init__(
        self,
        console: ConsoleInterface,
        pkg_path: Path,
        coverage_ratchet: CoverageRatchetProtocol | None = None,
        coverage_badge: CoverageBadgeServiceProtocol | None = None,
    ) -> None:
        """Initialize the coverage manager with dependencies.

        Args:
            console: Console interface for output and user feedback
            pkg_path: Package path for locating coverage.json and ratchet files
            coverage_ratchet: Coverage ratchet service for enforcement (optional)
            coverage_badge: Coverage badge service for README updates (optional)

        The manager accepts optional services to support different usage scenarios:
            - With ratchet: Enforces coverage minimums and detects regressions
            - With badge: Updates README badges with current coverage
            - Without services: Basic coverage extraction only

        All services are protocol-based, enabling easy testing with mocks.
        """
        self.console = console
        self.pkg_path = pkg_path
        self.coverage_ratchet = coverage_ratchet
        self._coverage_badge_service = coverage_badge

    def process_coverage_ratchet(self) -> bool:
        """Process coverage ratchet check and update.

        Orchestrates the complete coverage ratchet workflow:
            1. Check coverage against ratchet baseline
            2. Update ratchet state if coverage improved
            3. Update README badge with new coverage
            4. Report results to console

        Returns:
            True if coverage passed ratchet check (no regression),
            False if coverage regressed below baseline

        Example:
            >>> manager = CoverageManager(console, pkg_path, ratchet, badge)
            >>> success = manager.process_coverage_ratchet()
            >>> if success:
            ...     print("Coverage check passed!")
            >>> else:
            ...     print("Coverage regression detected!")

        Note:
            If no ratchet service is configured, this method returns True
            (coverage check is effectively skipped).
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
