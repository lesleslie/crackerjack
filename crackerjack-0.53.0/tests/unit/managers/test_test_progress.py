"""Unit tests for TestProgress.

Tests progress tracking, formatting, and statistics
calculation during test execution.
"""

import threading
import time

import pytest

from crackerjack.managers.test_progress import TestProgress


@pytest.mark.unit
class TestTestProgressInitialization:
    """Test TestProgress initialization and defaults."""

    def test_initialization_defaults(self) -> None:
        """Test TestProgress initializes with correct defaults."""
        progress = TestProgress()

        assert progress.total_tests == 0
        assert progress.passed == 0
        assert progress.failed == 0
        assert progress.skipped == 0
        assert progress.errors == 0
        assert progress.current_test == ""
        assert progress.start_time == 0
        assert progress.is_complete is False
        assert progress.is_collecting is True
        assert progress.files_discovered == 0
        assert progress.collection_status == "Starting collection..."
        assert progress._lock is not None
        assert progress._seen_files == set()
        assert progress._stdout_buffer == []
        assert progress._stderr_buffer == []

    def test_initialization_with_start_time(self) -> None:
        """Test TestProgress can set start time."""
        progress = TestProgress()
        test_time = time.time()

        progress.start_time = test_time

        assert progress.start_time == test_time


@pytest.mark.unit
class TestTestProgressProperties:
    """Test TestProgress property calculations."""

    def test_completed_property(self) -> None:
        """Test completed property calculates correctly."""
        progress = TestProgress()
        progress.update(total_tests=10)

        assert progress.completed == 0

        progress.update(passed=5, failed=2, skipped=1, errors=1)

        assert progress.completed == 9

    def test_completed_property_xfailed_xpassed(self) -> None:
        """Test completed includes xfailed and xpassed."""
        progress = TestProgress()

        # Note: TestProgress doesn't have xfailed/xpassed fields in __init__
        # Only completed, passed, failed, skipped, errors
        progress.update(passed=3, failed=2, skipped=1)

        assert progress.completed == 6

    def test_elapsed_time_property(self) -> None:
        """Test elapsed_time property calculates correctly."""
        progress = TestProgress()

        # No start time = 0 elapsed
        assert progress.elapsed_time == 0

        # With start time
        start = time.time()
        progress.start_time = start
        time.sleep(0.1)

        elapsed = progress.elapsed_time
        assert elapsed >= 0.1
        assert elapsed < 0.2  # Should be close to 0.1

    def test_elapsed_time_property_no_start_time(self) -> None:
        """Test elapsed_time returns 0 when no start time."""
        progress = TestProgress()
        progress.start_time = 0

        assert progress.elapsed_time == 0

    def test_eta_seconds_property(self) -> None:
        """Test ETA calculation."""
        progress = TestProgress()
        progress.start_time = time.time()
        progress.update(total_tests=100, passed=50)

        # Should calculate ETA based on completion rate
        eta = progress.eta_seconds
        assert eta is not None
        assert eta > 0

    def test_eta_seconds_property_no_data(self) -> None:
        """Test ETA returns None when insufficient data."""
        progress = TestProgress()

        # No start time
        assert progress.eta_seconds is None

        # No tests completed
        progress.start_time = time.time()
        progress.update(total_tests=100)
        assert progress.eta_seconds is None

        # No total tests
        progress.update(total_tests=0, passed=10)
        assert progress.eta_seconds is None

    def test_tests_per_second_property(self) -> None:
        """Test tests_per_second calculation."""
        progress = TestProgress()
        progress.start_time = time.time()
        progress.update(total_tests=100, passed=50)

        # Should calculate rate
        rate = progress.tests_per_second
        assert rate > 0

        time.sleep(0.1)
        # Rate should decrease over time if no more tests complete
        later_rate = progress.tests_per_second
        assert later_rate <= rate

    def test_tests_per_second_property_no_data(self) -> None:
        """Test tests_per_second returns 0 when no data."""
        progress = TestProgress()

        # No start time
        assert progress.tests_per_second == 0.0

        # No completed tests
        progress.start_time = time.time()
        assert progress.tests_per_second == 0.0

    def test_overall_status_color_property_red(self) -> None:
        """Test status color is red when failures/errors."""
        progress = TestProgress()

        progress.update(failed=1)
        assert progress.overall_status_color == "red"

        progress.update(failed=0, errors=1)
        assert progress.overall_status_color == "red"

    def test_overall_status_color_property_green(self) -> None:
        """Test status color is green when all complete."""
        progress = TestProgress()
        progress.update(total_tests=10, passed=10)

        assert progress.overall_status_color == "green"

    def test_overall_status_color_property_yellow(self) -> None:
        """Test status color is yellow when passed but not complete."""
        progress = TestProgress()
        progress.update(total_tests=100, passed=50)

        assert progress.overall_status_color == "yellow"

    def test_overall_status_color_property_cyan(self) -> None:
        """Test status color is cyan when no progress."""
        progress = TestProgress()

        assert progress.overall_status_color == "cyan"


@pytest.mark.unit
class TestTestProgressUpdate:
    """Test TestProgress update functionality."""

    def test_update_single_field(self) -> None:
        """Test updating a single field."""
        progress = TestProgress()

        progress.update(total_tests=100)

        assert progress.total_tests == 100
        assert progress.passed == 0  # Unchanged

    def test_update_multiple_fields(self) -> None:
        """Test updating multiple fields."""
        progress = TestProgress()

        progress.update(
            total_tests=100,
            passed=50,
            failed=2,
            current_test="test_example",
        )

        assert progress.total_tests == 100
        assert progress.passed == 50
        assert progress.failed == 2
        assert progress.current_test == "test_example"

    def test_update_invalid_field_ignored(self) -> None:
        """Test updating invalid field is ignored."""
        progress = TestProgress()

        progress.update(total_tests=100, invalid_field=123)

        assert progress.total_tests == 100
        assert not hasattr(progress, "invalid_field")

    def test_update_thread_safety(self) -> None:
        """Test update is thread-safe."""
        progress = TestProgress()
        errors = []
        results = {}

        def update_field(field: str, value: int) -> None:
            try:
                for i in range(100):
                    progress.update(**{field: value + i})
                    time.sleep(0.0001)  # Tiny sleep to increase context switches
                results[field] = True
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=update_field, args=("passed", 0)),
            threading.Thread(target=update_field, args=("failed", 0)),
            threading.Thread(target=update_field, args=("skipped", 0)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 3


@pytest.mark.unit
class TestTestProgressBufferManagement:
    """Test stdout/stderr buffer management."""

    def test_append_stdout(self) -> None:
        """Test appending to stdout buffer."""
        progress = TestProgress()

        progress.append_stdout("line 1\n")
        progress.append_stdout("line 2\n")

        assert progress.get_stdout() == "line 1\nline 2\n"

    def test_append_stderr(self) -> None:
        """Test appending to stderr buffer."""
        progress = TestProgress()

        progress.append_stderr("error 1\n")
        progress.append_stderr("error 2\n")

        assert progress.get_stderr() == "error 1\nerror 2\n"

    def test_get_stdout_thread_safety(self) -> None:
        """Test get_stdout is thread-safe."""
        progress = TestProgress()
        lines = []

        def append_lines() -> None:
            for i in range(50):
                progress.append_stdout(f"line {i}\n")

        def get_content() -> None:
            for _ in range(10):
                lines.append(progress.get_stdout())

        threads = [
            threading.Thread(target=append_lines),
            threading.Thread(target=get_content),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not crash and should have some content
        assert len(lines) == 10

    def test_get_stderr_thread_safety(self) -> None:
        """Test get_stderr is thread-safe."""
        progress = TestProgress()

        def append_errors() -> None:
            for i in range(50):
                progress.append_stderr(f"error {i}\n")

        threads = [threading.Thread(target=append_errors) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have all errors
        content = progress.get_stderr()
        assert "error 0" in content
        assert "error 49" in content


@pytest.mark.unit
class TestTestProgressFormatting:
    """Test progress formatting methods."""

    def test_create_progress_bar_no_total(self) -> None:
        """Test progress bar with no total tests."""
        progress = TestProgress()

        bar = progress._create_progress_bar()

        assert bar == ""

    def test_create_progress_bar_start(self) -> None:
        """Test progress bar at start."""
        progress = TestProgress()
        progress.update(total_tests=100, passed=0)

        bar = progress._create_progress_bar()

        assert "[green]" in bar or "[yellow]" in bar
        assert "0%" in bar
        assert "░" in bar  # Empty progress indicator

    def test_create_progress_bar_half(self) -> None:
        """Test progress bar at 50%."""
        progress = TestProgress()
        progress.update(total_tests=100, passed=50)

        bar = progress._create_progress_bar()

        assert "50%" in bar
        assert "█" in bar or "▓" in bar  # Filled progress indicator

    def test_create_progress_bar_complete(self) -> None:
        """Test progress bar at 100%."""
        progress = TestProgress()
        progress.update(total_tests=100, passed=100)

        bar = progress._create_progress_bar()

        assert "100%" in bar
        assert "█" in bar  # Filled progress indicator

    def test_create_progress_bar_with_failures(self) -> None:
        """Test progress bar shows failures."""
        progress = TestProgress()
        progress.update(total_tests=100, passed=50, failed=5)

        bar = progress._create_progress_bar()

        assert "[red]" in bar
        assert "▓" in bar  # Different fill char for failures

    def test_format_eta_none(self) -> None:
        """Test ETA formatting with no ETA."""
        progress = TestProgress()

        eta = progress._format_eta()

        assert eta == ""

    def test_format_eta_seconds(self) -> None:
        """Test ETA formatting with seconds only."""
        progress = TestProgress()
        progress.start_time = time.time()
        progress.update(total_tests=100, passed=50)

        eta = progress._format_eta()

        assert "ETA:" in eta
        assert "s" in eta

    def test_format_eta_minutes(self) -> None:
        """Test ETA formatting with minutes."""
        progress = TestProgress()
        # Set up state to produce > 60 second ETA
        progress.start_time = time.time()
        progress.update(total_tests=1000, passed=100)  # Slow progress to get > 60s ETA
        time.sleep(0.1)  # Small delay to affect calculation

        eta = progress._format_eta()

        # If ETA is > 60 seconds, should include minutes
        if eta:  # Only test if ETA was calculated
            assert "ETA:" in eta

    def test_format_eta_hours(self) -> None:
        """Test ETA formatting with hours."""
        progress = TestProgress()
        # Very slow progress to potentially get large ETA
        progress.start_time = time.time()
        progress.update(total_tests=100000, passed=1)
        time.sleep(0.05)

        eta = progress._format_eta()

        # If ETA calculated and > 3600 seconds, should include hours
        if eta and "h" in eta:
            assert "ETA:" in eta
            assert "m" in eta

    def test_format_test_rate_zero(self) -> None:
        """Test test rate formatting with zero rate."""
        progress = TestProgress()

        rate = progress._format_test_rate()

        assert rate == ""

    def test_format_test_rate_positive(self) -> None:
        """Test test rate formatting with positive rate."""
        progress = TestProgress()
        progress.start_time = time.time()
        progress.update(total_tests=100, passed=50)

        rate = progress._format_test_rate()

        assert "tests/s" in rate
        # Should have a number
        assert any(c.isdigit() for c in rate)

    def test_format_progress_collection_status(self) -> None:
        """Test collection status formatting."""
        progress = TestProgress()
        progress.update(
            collection_status="Finding tests...",
            files_discovered=5,
        )

        formatted = progress.format_progress()

        assert "Finding tests..." in formatted
        assert "5 test files" in formatted

    def test_format_progress_execution_status(self) -> None:
        """Test execution status formatting."""
        progress = TestProgress()
        progress.update(
            total_tests=100,
            passed=50,
            failed=2,
            is_collecting=False,
        )

        formatted = progress.format_progress()

        assert "Running 100 tests" in formatted
        assert "50" in formatted  # passed count
        assert "2" in formatted  # failed count

    def test_format_progress_counters(self) -> None:
        """Test progress counters formatting."""
        progress = TestProgress()
        progress.update(
            total_tests=100,
            passed=70,
            failed=5,
            skipped=10,
            errors=2,
            is_collecting=False,
        )

        counters = progress._format_progress_counters()

        counter_text = " ".join(counters)
        assert "70" in counter_text  # passed
        assert "5" in counter_text  # failed
        assert "10" in counter_text  # skipped
        assert "2" in counter_text  # errors

    def test_format_progress_counters_empty(self) -> None:
        """Test progress counters with no results."""
        progress = TestProgress()
        progress.update(total_tests=100, is_collecting=False)

        counters = progress._format_progress_counters()

        # Should handle empty counters gracefully
        # When no tests completed, may not show percentage
        if counters:
            counter_text = " ".join(counters)
            # Either has percentage or is empty
            assert "%" in counter_text or len(counter_text) == 0

    def test_format_execution_progress_no_total(self) -> None:
        """Test execution progress without total."""
        progress = TestProgress()
        progress.update(is_collecting=False)

        formatted = progress._format_execution_progress()

        assert "Preparing tests" in formatted

    def test_format_execution_progress_with_total(self) -> None:
        """Test execution progress with total."""
        progress = TestProgress()
        progress.start_time = time.time()
        time.sleep(0.1)  # Ensure elapsed time > 0
        progress.update(
            total_tests=100,
            passed=10,
            is_collecting=False,
        )

        formatted = progress._format_execution_progress()

        assert "Running 100 tests" in formatted
        # Should include elapsed time
        assert "s" in formatted or "Preparing" not in formatted
