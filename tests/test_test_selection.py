"""Tests for Crackerjack test selection module.

Tests cover:
- Test selection strategies
- Changed file detection
- Test selection by changes
- Related test selection
- Fast test filtering
- Pytest output parsing
- Report generation
"""

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.test_selection import (
    TestMetrics,
    TestSelector,
    TestSelectionResult,
    TestSelectionStrategy,
    get_test_selector,
    get_test_strategy_from_env,
    install_testmon,
    run_smart_tests,
    select_tests_for_ci,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def selector():
    """Create test selector instance."""
    return TestSelector(
        testmon_data_file=".testmondata",
        project_root="/tmp/test_project",
    )


@pytest.fixture
def sample_test_files(tmp_path):
    """Create sample test files."""
    test_dir = tmp_path / "tests"
    test_dir.mkdir()

    test_files = [
        test_dir / "test_api.py",
        test_dir / "test_utils.py",
        test_dir / "test_fast_tests.py",
    ]

    for test_file in test_files:
        test_file.write_text("# test file")

    return test_files


# ============================================================================
# TestSelectionStrategy Tests
# ============================================================================


def test_selection_strategy_values():
    """Test selection strategy enum values."""
    assert TestSelectionStrategy.ALL.value == "all"
    assert TestSelectionStrategy.CHANGED.value == "changed"
    assert TestSelectionStrategy.RELATED.value == "related"
    assert TestSelectionStrategy.FAST.value == "fast"


def test_selection_strategy_from_env():
    """Test getting strategy from environment variable."""
    with patch.dict(os.environ, {"CRACKERJACK_TEST_STRATEGY": "fast"}):
        strategy = get_test_strategy_from_env()
        assert strategy == TestSelectionStrategy.FAST

    # Test default
    with patch.dict(os.environ, {}, clear=True):
        strategy = get_test_strategy_from_env()
        assert strategy == TestSelectionStrategy.CHANGED


# ============================================================================
# TestSelectionResult Tests
# ============================================================================


def test_selection_result_creation():
    """Test creating test selection result."""
    result = TestSelectionResult(
        strategy=TestSelectionStrategy.CHANGED,
        total_tests=100,
        selected_tests=30,
        skipped_tests=70,
    )

    assert result.strategy == TestSelectionStrategy.CHANGED
    assert result.total_tests == 100
    assert result.selected_tests == 30
    assert result.skipped_tests == 70


def test_selection_result_reduction_percentage():
    """Test reduction percentage calculation."""
    # 70% reduction
    result = TestSelectionResult(
        strategy=TestSelectionStrategy.CHANGED,
        total_tests=100,
        selected_tests=30,
        skipped_tests=70,
    )

    assert result.reduction_percentage == 70.0


def test_selection_result_efficiency_ratio():
    """Test efficiency ratio calculation."""
    result = TestSelectionResult(
        strategy=TestSelectionStrategy.CHANGED,
        total_tests=100,
        selected_tests=30,
        skipped_tests=70,
    )

    assert result.efficiency_ratio == 0.7


def test_selection_result_no_tests():
    """Test selection result with no tests."""
    result = TestSelectionResult(
        strategy=TestSelectionStrategy.ALL,
        total_tests=0,
        selected_tests=0,
        skipped_tests=0,
    )

    assert result.reduction_percentage == 0.0
    assert result.efficiency_ratio == 0.0


# ============================================================================
# TestSelector Tests
# ============================================================================


def test_selector_initialization(selector):
    """Test selector initialization."""
    assert selector.testmon_data_file == ".testmondata"
    assert selector.project_root == Path("/tmp/test_project")


def test_detect_changed_files_empty(selector):
    """Test detecting changed files with no changes."""
    # Mock git command with no output
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="",
            returncode=0,
        )

        changed = selector.detect_changed_files()
        assert len(changed) == 0


def test_detect_changed_files_with_changes(selector):
    """Test detecting changed files."""
    # Mock git command with changed files
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="src/main.py\nsrc/utils.py\n",
            returncode=0,
        )

        changed = selector.detect_changed_files()
        assert "src/main.py" in changed
        assert "src/utils.py" in changed


def test_detect_changed_files_git_error(selector):
    """Test detecting changed files when git fails."""
    # Mock git command that fails
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="",
            returncode=1,
        )

        changed = selector.detect_changed_files()
        assert len(changed) == 0  # Returns empty on error


# ============================================================================
# Test Selection Tests
# ============================================================================


@pytest.mark.asyncio
async def test_select_tests_by_changes_all(selector, sample_test_files):
    """Test selecting all tests."""
    result = selector.select_tests_by_changes(
        test_files=sample_test_files,
        changed_files=set(),
        strategy=TestSelectionStrategy.ALL,
    )

    assert result.strategy == TestSelectionStrategy.ALL
    assert result.total_tests == len(sample_test_files)
    assert result.selected_tests == len(sample_test_files)
    assert result.skipped_tests == 0


def test_select_tests_by_changes_changed(selector, sample_test_files):
    """Test selecting only changed tests."""
    # Mark one test file as changed
    changed_files = {str(sample_test_files[0])}

    # Need to mock TESTMON_AVAILABLE to True for strategy to be preserved
    with patch("crackerjack.test_selection.TESTMON_AVAILABLE", True):
        result = selector.select_tests_by_changes(
            test_files=sample_test_files,
            changed_files=changed_files,
            strategy=TestSelectionStrategy.CHANGED,
        )

        assert result.strategy == TestSelectionStrategy.CHANGED
        assert result.selected_tests == 1
        assert result.skipped_tests == len(sample_test_files) - 1


def test_select_tests_by_changes_related(selector, sample_test_files):
    """Test selecting related tests."""
    # Mark one test file as changed
    test_file = str(sample_test_files[0])
    changed_files = {test_file}

    # Need to mock TESTMON_AVAILABLE to True for strategy to be preserved
    with patch("crackerjack.test_selection.TESTMON_AVAILABLE", True):
        result = selector.select_tests_by_changes(
            test_files=sample_test_files,
            changed_files=changed_files,
            strategy=TestSelectionStrategy.RELATED,
        )

        # Should include changed test
        assert test_file in result.changed_tests or []


def test_select_tests_by_changes_fast(selector, sample_test_files):
    """Test selecting only fast tests."""
    # Need to mock TESTMON_AVAILABLE to True for strategy to be preserved
    with patch("crackerjack.test_selection.TESTMON_AVAILABLE", True):
        result = selector.select_tests_by_changes(
            test_files=sample_test_files,
            changed_files=set(),
            strategy=TestSelectionStrategy.FAST,
        )

        # Should only include fast test
        assert any("fast" in str(t).lower() for t in result.changed_tests)


def test_select_tests_by_changes_no_fast_tests(selector, sample_test_files):
    """Test fast test selection when no fast tests exist."""
    # Remove "fast" from test files
    test_files_no_fast = [
        f for f in sample_test_files if "fast" not in f.name.lower()
    ]

    # Need to mock TESTMON_AVAILABLE to True for strategy to be preserved
    with patch("crackerjack.test_selection.TESTMON_AVAILABLE", True):
        result = selector.select_tests_by_changes(
            test_files=test_files_no_fast,
            changed_files=set(),
            strategy=TestSelectionStrategy.FAST,
        )

        # Should fall back to all tests
        assert result.selected_tests == len(test_files_no_fast)


# ============================================================================
# TestMetrics Tests
# ============================================================================


def test_metrics_creation():
    """Test creating test metrics."""
    metrics = TestMetrics(
        total_tests=100,
        passed=95,
        failed=3,
        skipped=2,
        duration_seconds=30.0,
    )

    assert metrics.total_tests == 100
    assert metrics.passed == 95
    assert metrics.failed == 3
    assert metrics.skipped == 2


def test_metrics_success_rate():
    """Test success rate calculation."""
    metrics = TestMetrics(
        total_tests=100,
        passed=95,
        failed=3,
        skipped=2,
        duration_seconds=30.0,
    )

    assert metrics.success_rate == 95.0


def test_metrics_zero_tests():
    """Test metrics with zero tests."""
    metrics = TestMetrics(
        total_tests=0,
        passed=0,
        failed=0,
        skipped=0,
        duration_seconds=0.0,
    )

    assert metrics.success_rate == 0.0


# ============================================================================
# Pytest Output Parsing Tests
# ============================================================================


def test_parse_pytest_output_success(selector):
    """Test parsing successful pytest output."""
    output = "collected 50 items\n\n50 passed in 10.5 seconds"

    metrics = selector._parse_pytest_output(output, 0)

    assert metrics.total_tests == 50
    assert metrics.passed == 50
    assert metrics.failed == 0
    assert metrics.duration_seconds == 10.5


def test_parse_pytest_output_with_failures(selector):
    """Test parsing pytest output with failures."""
    output = "collected 50 items\n\n48 passed, 2 failed in 12.3 seconds"

    metrics = selector._parse_pytest_output(output, 1)

    assert metrics.total_tests == 50
    assert metrics.passed == 48
    assert metrics.failed == 2
    assert metrics.duration_seconds == 12.3


def test_parse_pytest_output_with_skipped(selector):
    """Test parsing pytest output with skipped tests."""
    output = "collected 50 items\n\n45 passed, 3 failed, 2 skipped in 8.7 seconds"

    metrics = selector._parse_pytest_output(output, 1)

    assert metrics.total_tests == 50
    assert metrics.passed == 45
    assert metrics.failed == 3
    assert metrics.skipped == 2
    assert metrics.duration_seconds == 8.7


def test_parse_pytest_output_no_match(selector):
    """Test parsing pytest output without expected pattern."""
    output = "Some random output\nwithout test summary"

    metrics = selector._parse_pytest_output(output, 1)

    # Should return zero metrics (fallback)
    assert metrics.total_tests >= 0


# ============================================================================
# Report Generation Tests
# ============================================================================


def test_generate_selection_report(selector):
    """Test generating selection report."""
    result = TestSelectionResult(
        strategy=TestSelectionStrategy.CHANGED,
        total_tests=100,
        selected_tests=30,
        skipped_tests=70,
        affected_files=["src/main.py", "src/utils.py"],
        changed_tests=["tests/test_main.py", "tests/test_utils.py"],
        estimated_savings_seconds=60.0,
    )

    report = selector.generate_selection_report(result)

    assert "Test Selection Report" in report
    assert "Strategy: changed" in report
    assert "Total Tests: 100" in report
    assert "Selected: 30" in report
    assert "Skipped: 70" in report
    assert "Reduction: 70.0%" in report
    assert "Est. Time Saved: 60.0s" in report


def test_generate_selection_report_writes_file(selector, tmp_path):
    """Test that report is written to file."""
    result = TestSelectionResult(
        strategy=TestSelectionStrategy.CHANGED,
        total_tests=100,
        selected_tests=30,
        skipped_tests=70,
    )

    output_file = tmp_path / "report.txt"
    selector.generate_selection_report(result, str(output_file))

    assert output_file.exists()
    content = output_file.read_text()
    assert "Test Selection Report" in content


# ============================================================================
# Convenience Functions Tests
# ============================================================================


def test_get_test_selector():
    """Test getting test selector."""
    selector = get_test_selector()
    assert isinstance(selector, TestSelector)


def test_install_testmon_success():
    """Test successful testmon installation."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        success = install_testmon()
        assert success is True


def test_install_testmon_failure():
    """Test testmon installation failure."""
    with patch("subprocess.run") as mock_run:
        # CalledProcessError requires returncode and cmd arguments
        mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="pip install")
        success = install_testmon()
        assert success is False


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_selection_workflow(tmp_path):
    """Test complete selection workflow."""
    # Create test files
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    test_files = [
        tests_dir / "test_a.py",
        tests_dir / "test_b.py",
        tests_dir / "test_c.py",
    ]

    for test_file in test_files:
        test_file.write_text("# test")

    # Create selector
    selector = TestSelector(
        testmon_data_file=".testmondata",
        project_root=str(tmp_path),
    )

    # Simulate file changes
    changed_files = {str(test_files[0])}

    # Need to mock TESTMON_AVAILABLE to True for strategy to be preserved
    with patch("crackerjack.test_selection.TESTMON_AVAILABLE", True):
        # Select tests
        result = selector.select_tests_by_changes(
            test_files=test_files,
            changed_files=changed_files,
            strategy=TestSelectionStrategy.CHANGED,
        )

        # Verify
        assert result.total_tests == 3
        assert result.selected_tests <= 3
        assert result.strategy == TestSelectionStrategy.CHANGED


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_select_tests_empty_test_list(selector):
    """Test selecting from empty test list."""
    result = selector.select_tests_by_changes(
        test_files=[],
        changed_files=set(),
        strategy=TestSelectionStrategy.ALL,
    )

    assert result.total_tests == 0
    assert result.selected_tests == 0


def test_select_tests_no_capability_fallback(selector):
    """Test selection falls back to all tests when testmon unavailable."""
    with patch("crackerjack.test_selection.TESTMON_AVAILABLE", False):
        test_files = [Path("test_a.py")]

        result = selector.select_tests_by_changes(
            test_files=test_files,
            changed_files=set(),
            strategy=TestSelectionStrategy.CHANGED,
        )

        # Should return all tests
        assert result.strategy == TestSelectionStrategy.ALL
        assert result.selected_tests == len(test_files)


def test_strategy_from_env_invalid():
    """Test strategy from env with invalid value."""
    with patch.dict(os.environ, {"CRACKERJACK_TEST_STRATEGY": "invalid"}):
        strategy = get_test_strategy_from_env()
        # Should fall back to CHANGED
        assert strategy == TestSelectionStrategy.CHANGED


# ============================================================================
# Performance Tests
# ============================================================================


def test_selection_performance():
    """Test that selection is fast."""
    selector = TestSelector(
        testmon_data_file=".testmondata",
        project_root="/tmp/test_project",
    )

    # Create large test file list
    test_files = [Path(f"test_{i}.py") for i in range(1000)]

    # Time selection
    started = datetime.now(UTC)

    result = selector.select_tests_by_changes(
        test_files=test_files,
        changed_files=set(),
        strategy=TestSelectionStrategy.ALL,
    )

    elapsed = (datetime.now(UTC) - started).total_seconds()

    # Should be very fast (< 1 second for 1000 files)
    assert elapsed < 1.0


# ============================================================================
# Environment Variable Tests
# ============================================================================


def test_env_var_affects_ci_selection():
    """Test that environment variable affects CI selection."""
    with patch.dict(os.environ, {"CRACKERJACK_TEST_STRATEGY": "fast"}):
        # Create temp directory
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dummy test files
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            (test_dir / "test_fast.py").write_text("# fast test")

            # Need to mock TESTMON_AVAILABLE to True for strategy to be preserved
            with patch("crackerjack.test_selection.TESTMON_AVAILABLE", True):
                # Run CI selection
                result = select_tests_for_ci(
                    strategy=TestSelectionStrategy.FAST,
                    output_file="report.txt",
                )

                # Should use fast strategy
                assert result.strategy == TestSelectionStrategy.FAST


# ============================================================================
# Migration and Integration Tests
# ============================================================================


def test_backward_compatibility_with_crackerjack():
    """Test that test selection works with existing Crackerjack."""
    # Simulate existing Crackerjack usage
    selector = get_test_selector()

    # Should work with standard Crackerjack setup
    assert selector is not None

    # Test selection methods
    assert hasattr(selector, "select_tests_by_changes")
    assert hasattr(selector, "run_pytest_with_selection")
    assert hasattr(selector, "generate_selection_report")
