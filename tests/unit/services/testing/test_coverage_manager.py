"""Unit tests for CoverageManager.

Tests the CoverageManager class which handles test coverage data management
and reporting. All tests use mocked CoverageRatchet and CoverageBadgeService
to verify behavior without actual file I/O or external dependencies.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from dataclasses import dataclass

from crackerjack.services.testing.coverage_manager import CoverageManager
from crackerjack.models.protocols import (
    CoverageRatchetProtocol,
    CoverageBadgeServiceProtocol,
    ConsoleInterface,
)


@pytest.fixture
def mock_console() -> Mock:
    """Create a mock console."""
    console = Mock(spec=ConsoleInterface)
    return console


@pytest.fixture
def mock_ratchet() -> Mock:
    """Create a mock coverage ratchet."""
    ratchet = Mock(spec=CoverageRatchetProtocol)
    return ratchet


@pytest.fixture
def mock_badge() -> Mock:
    """Create a mock coverage badge service."""
    badge = Mock(spec=CoverageBadgeServiceProtocol)
    return badge


@pytest.fixture
def mock_pkg_path() -> Path:
    """Create a mock package path."""
    return Path("/mock/project/path")


@pytest.fixture
def manager(
    mock_console: Mock,
    mock_pkg_path: Path,
    mock_ratchet: Mock,
    mock_badge: Mock,
) -> CoverageManager:
    """Create a CoverageManager instance with mocked dependencies."""
    return CoverageManager(
        console=mock_console,
        pkg_path=mock_pkg_path,
        coverage_ratchet=mock_ratchet,
        coverage_badge=mock_badge,
    )


@dataclass
class MockRatchetResult:
    """Mock ratchet result for testing."""
    current_coverage: float
    passed: bool
    previous_coverage: float | None = None
    message: str = ""


class TestCoverageManager:
    """Test suite for CoverageManager class."""

    def test_init(self, mock_console: Mock, mock_pkg_path: Path, mock_ratchet: Mock, mock_badge: Mock):
        """Test manager initialization with dependencies."""
        manager = CoverageManager(
            console=mock_console,
            pkg_path=mock_pkg_path,
            coverage_ratchet=mock_ratchet,
            coverage_badge=mock_badge,
        )

        assert manager.console == mock_console
        assert manager.pkg_path == mock_pkg_path
        assert manager.coverage_ratchet == mock_ratchet
        assert manager.coverage_badge == mock_badge

    def test_init_without_badge(self, mock_console: Mock, mock_pkg_path: Path, mock_ratchet: Mock):
        """Test manager initialization without badge service."""
        manager = CoverageManager(
            console=mock_console,
            pkg_path=mock_pkg_path,
            coverage_ratchet=mock_ratchet,
            coverage_badge=None,
        )

        assert manager.coverage_ratchet == mock_ratchet
        assert manager.coverage_badge is None

    def test_init_without_ratchet(self, mock_console: Mock, mock_pkg_path: Path):
        """Test manager initialization without ratchet (no coverage checking)."""
        manager = CoverageManager(
            console=mock_console,
            pkg_path=mock_pkg_path,
            coverage_ratchet=None,
            coverage_badge=None,
        )

        assert manager.coverage_ratchet is None
        assert manager.coverage_badge is None

    def test_process_coverage_ratchet_passed(self, manager: CoverageManager, mock_ratchet: Mock, mock_badge: Mock):
        """Test processing coverage ratchet when coverage passes."""
        ratchet_result = MockRatchetResult(
            current_coverage=85.5,
            passed=True,
            previous_coverage=80.0,
            message="Coverage improved",
        )
        mock_ratchet.check_and_update_coverage.return_value = ratchet_result

        result = manager.process_coverage_ratchet()

        # Verify ratchet was checked
        mock_ratchet.check_and_update_coverage.assert_called_once()

        # Verify badge was updated
        mock_badge.update_badge.assert_called_once_with(85.5)

        # Verify result is True (passed)
        assert result is True

    def test_process_coverage_ratchet_failed(self, manager: CoverageManager, mock_ratchet: Mock, mock_badge: Mock):
        """Test processing coverage ratchet when coverage fails."""
        ratchet_result = MockRatchetResult(
            current_coverage=75.0,
            passed=False,
            previous_coverage=80.0,
            message="Coverage regression",
        )
        mock_ratchet.check_and_update_coverage.return_value = ratchet_result

        result = manager.process_coverage_ratchet()

        # Verify ratchet was checked
        mock_ratchet.check_and_update_coverage.assert_called_once()

        # Verify badge was still updated with current coverage
        mock_badge.update_badge.assert_called_once_with(75.0)

        # Verify result is False (failed)
        assert result is False

    def test_process_coverage_ratchet_no_ratchet(self, mock_console: Mock, mock_pkg_path: Path, mock_badge: Mock):
        """Test processing when ratchet is None (no coverage checking)."""
        manager = CoverageManager(
            console=mock_console,
            pkg_path=mock_pkg_path,
            coverage_ratchet=None,
            coverage_badge=mock_badge,
        )

        result = manager.process_coverage_ratchet()

        # Verify returns True (no coverage check means pass)
        assert result is True

        # Verify badge was not called
        mock_badge.update_badge.assert_not_called()

    def test_process_coverage_ratchet_no_badge(self, mock_console: Mock, mock_pkg_path: Path, mock_ratchet: Mock):
        """Test processing when badge service is None."""
        manager = CoverageManager(
            console=mock_console,
            pkg_path=mock_pkg_path,
            coverage_ratchet=mock_ratchet,
            coverage_badge=None,
        )

        ratchet_result = MockRatchetResult(
            current_coverage=90.0,
            passed=True,
        )
        mock_ratchet.check_and_update_coverage.return_value = ratchet_result

        result = manager.process_coverage_ratchet()

        # Verify ratchet was checked
        mock_ratchet.check_and_update_coverage.assert_called_once()

        # Verify returns True
        assert result is True

    def test_attempt_coverage_extraction_success(self, manager: CoverageManager):
        """Test successful coverage extraction from coverage.json."""
        # Mock Path operations
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = '{"totals": {"percent_covered": 85.5}}'

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Verify coverage was extracted
        assert coverage == 85.5

    def test_attempt_coverage_extraction_file_not_found(self, manager: CoverageManager):
        """Test coverage extraction when coverage.json doesn't exist."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = False

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Verify returns None
        assert coverage is None

    def test_attempt_coverage_extraction_invalid_json(self, manager: CoverageManager):
        """Test coverage extraction with invalid JSON in coverage.json."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = 'invalid json'

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Verify returns None on error
        assert coverage is None

    def test_attempt_coverage_extraction_missing_coverage_key(self, manager: CoverageManager):
        """Test coverage extraction when coverage key is missing from JSON."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = '{"other_key": "value"}'

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Verify returns None
        assert coverage is None

    def test_update_coverage_badge_with_badge_service(self, manager: CoverageManager, mock_badge: Mock):
        """Test updating coverage badge when badge service is available."""
        ratchet_result = MockRatchetResult(current_coverage=85.5, passed=True)

        manager.update_coverage_badge(ratchet_result)

        # Verify badge was updated
        mock_badge.update_badge.assert_called_once_with(85.5)

    def test_update_coverage_badge_without_badge_service(self, manager: CoverageManager, mock_badge: Mock):
        """Test updating coverage badge when badge service is None."""
        manager.coverage_badge = None
        ratchet_result = MockRatchetResult(current_coverage=85.5, passed=True)

        manager.update_coverage_badge(ratchet_result)

        # Verify badge was not called
        mock_badge.update_badge.assert_not_called()

    def test_handle_ratchet_result_passed(self, manager: CoverageManager):
        """Test handling ratchet result when coverage passes."""
        ratchet_result = MockRatchetResult(
            current_coverage=85.5,
            passed=True,
            previous_coverage=80.0,
            message="Coverage improved",
        )

        result = manager.handle_ratchet_result(ratchet_result)

        # Verify returns True
        assert result is True

    def test_handle_ratchet_result_failed(self, manager: CoverageManager):
        """Test handling ratchet result when coverage fails."""
        ratchet_result = MockRatchetResult(
            current_coverage=75.0,
            passed=False,
            previous_coverage=80.0,
            message="Coverage regression",
        )

        result = manager.handle_ratchet_result(ratchet_result)

        # Verify returns False
        assert result is False

    def test_handle_ratchet_result_with_improvement(self, manager: CoverageManager):
        """Test handling ratchet result shows improvement message."""
        ratchet_result = MockRatchetResult(
            current_coverage=90.0,
            passed=True,
            previous_coverage=85.0,
            message="Coverage improved by 5%",
        )

        result = manager.handle_ratchet_result(ratchet_result)

        # Verify returns True
        assert result is True


class TestCoverageManagerEdgeCases:
    """Test edge cases and error conditions for CoverageManager."""

    def test_coverage_extraction_zero_coverage(self, manager: CoverageManager):
        """Test coverage extraction with 0% coverage."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = '{"totals": {"percent_covered": 0.0}}'

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Should return 0.0, not None
        assert coverage == 0.0

    def test_coverage_extraction_full_coverage(self, manager: CoverageManager):
        """Test coverage extraction with 100% coverage."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = '{"totals": {"percent_covered": 100.0}}'

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Should return 100.0
        assert coverage == 100.0

    def test_coverage_extraction_with_totals_percent(self, manager: CoverageManager):
        """Test coverage extraction with alternative JSON structure."""
        # Some coverage.py versions use different structure
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = '{"totals": {"percent_covered": 78.5}}'

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Should extract coverage correctly
        assert coverage == 78.5

    def test_coverage_extraction_io_error(self, manager: CoverageManager):
        """Test coverage extraction when I/O error occurs."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.side_effect = IOError("Permission denied")

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Should return None on error
        assert coverage is None

    def test_coverage_extraction_empty_file(self, manager: CoverageManager):
        """Test coverage extraction with empty coverage.json."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = ''

        with patch('crackerjack.services.testing.coverage_manager.Path', return_value=mock_path):
            coverage = manager.attempt_coverage_extraction()

        # Should return None (invalid JSON)
        assert coverage is None

    def test_process_ratchet_with_both_dependencies_none(self, mock_console: Mock, mock_pkg_path: Path):
        """Test processing when both ratchet and badge are None."""
        manager = CoverageManager(
            console=mock_console,
            pkg_path=mock_pkg_path,
            coverage_ratchet=None,
            coverage_badge=None,
        )

        result = manager.process_coverage_ratchet()

        # Should return True (no coverage check)
        assert result is True

    def test_handle_ratchet_result_no_previous_coverage(self, manager: CoverageManager):
        """Test handling ratchet result when there's no previous coverage."""
        ratchet_result = MockRatchetResult(
            current_coverage=85.0,
            passed=True,
            previous_coverage=None,
            message="Initial coverage measurement",
        )

        result = manager.handle_ratchet_result(ratchet_result)

        # Should still return True
        assert result is True

    def test_handle_ratchet_result_exact_match(self, manager: CoverageManager):
        """Test handling ratchet result when coverage matches exactly."""
        ratchet_result = MockRatchetResult(
            current_coverage=80.0,
            passed=True,
            previous_coverage=80.0,
            message="Coverage unchanged",
        )

        result = manager.handle_ratchet_result(ratchet_result)

        # Should return True (exact match passes)
        assert result is True


class TestCoverageManagerIntegration:
    """Integration-style tests for CoverageManager."""

    def test_full_workflow_with_coverage_improvement(self, manager: CoverageManager, mock_ratchet: Mock, mock_badge: Mock):
        """Test full workflow: coverage improves, badge updated."""
        ratchet_result = MockRatchetResult(
            current_coverage=88.5,
            passed=True,
            previous_coverage=82.0,
            message="Coverage improved",
        )
        mock_ratchet.check_and_update_coverage.return_value = ratchet_result

        # Process ratchet
        result = manager.process_coverage_ratchet()

        # Verify complete workflow
        mock_ratchet.check_and_update_coverage.assert_called_once()
        mock_badge.update_badge.assert_called_once_with(88.5)
        assert result is True

    def test_full_workflow_with_coverage_regression(self, manager: CoverageManager, mock_ratchet: Mock, mock_badge: Mock):
        """Test full workflow: coverage regresses, badge still updated."""
        ratchet_result = MockRatchetResult(
            current_coverage=72.0,
            passed=False,
            previous_coverage=78.0,
            message="Coverage regression",
        )
        mock_ratchet.check_and_update_coverage.return_value = ratchet_result

        # Process ratchet
        result = manager.process_coverage_ratchet()

        # Verify complete workflow
        mock_ratchet.check_and_update_coverage.assert_called_once()
        mock_badge.update_badge.assert_called_once_with(72.0)
        assert result is False
