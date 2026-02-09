"""Unit tests for TestResultRenderer.

Tests the TestResultRenderer class which handles UI rendering for test results
using Rich console formatting. All tests use mocked ConsoleInterface to
verify rendering behavior without actual console output.
"""

import pytest
from unittest.mock import Mock, MagicMock, call
from rich.panel import Panel
from rich.table import Table

from crackerjack.services.testing.test_result_renderer import TestResultRenderer
from crackerjack.models.protocols import ConsoleInterface


@pytest.fixture
def mock_console() -> Mock:
    """Create a mock console for testing."""
    console = Mock(spec=ConsoleInterface)
    return console


@pytest.fixture
def renderer(mock_console: Mock) -> TestResultRenderer:
    """Create a TestResultRenderer instance with mock console."""
    return TestResultRenderer(mock_console)


class TestTestResultRenderer:
    """Test suite for TestResultRenderer class."""

    def test_init(self, mock_console: Mock):
        """Test renderer initialization with console."""
        test_renderer = TestResultRenderer(mock_console)
        assert test_renderer.console == mock_console

    def test_render_test_results_panel_success(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering test results panel with all tests passed."""
        stats = {
            "total": 100,
            "passed": 95,
            "failed": 5,
            "skipped": 0,
            "errors": 0,
            "duration": 12.3,
            "coverage": 85.5,
        }

        renderer.render_test_results_panel(stats, workers=4, success=True)

        # Verify console.print was called
        assert mock_console.print.called
        # Get the Panel that was printed
        call_args = mock_console.print.call_args
        panel = call_args[0][0]
        assert isinstance(panel, Panel)

    def test_render_test_results_panel_failure(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering test results panel with test failures."""
        stats = {
            "total": 50,
            "passed": 40,
            "failed": 10,
            "skipped": 0,
            "errors": 0,
            "duration": 8.5,
        }

        renderer.render_test_results_panel(stats, workers="auto", success=False)

        # Verify console.print was called
        assert mock_console.print.called
        call_args = mock_console.print.call_args
        panel = call_args[0][0]
        assert isinstance(panel, Panel)

    def test_render_test_results_panel_with_optional_metrics(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering panel with xfailed and xpassed metrics."""
        stats = {
            "total": 100,
            "passed": 90,
            "failed": 5,
            "skipped": 0,
            "errors": 0,
            "xfailed": 3,
            "xpassed": 2,
            "duration": 15.7,
        }

        renderer.render_test_results_panel(stats, workers=2, success=True)

        # Verify panel was rendered
        assert mock_console.print.called
        call_args = mock_console.print.call_args
        panel = call_args[0][0]
        assert isinstance(panel, Panel)

    def test_render_test_results_panel_zero_tests(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering panel with zero tests collected."""
        stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0.0,
        }

        renderer.render_test_results_panel(stats, workers=1, success=True)

        # Should still render panel even with zero tests
        assert mock_console.print.called

    def test_render_test_results_panel_without_coverage(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering panel without coverage data."""
        stats = {
            "total": 75,
            "passed": 70,
            "failed": 5,
            "skipped": 0,
            "errors": 0,
            "duration": 10.2,
            # No coverage field
        }

        renderer.render_test_results_panel(stats, workers=4, success=True)

        # Verify console.print was called
        assert mock_console.print.called

    def test_render_banner_default_style(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering banner with default styling."""
        renderer.render_banner("Test Banner")

        # Verify console.print was called 5 times (padding, line, title, line, padding)
        # Default padding=True adds 2 extra calls
        assert mock_console.print.call_count == 5

    def test_render_banner_custom_style(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering banner with custom styling."""
        renderer.render_banner(
            "Custom Banner",
            line_style="cyan",
            title_style="bold cyan",
            char="═",
            padding=False,
        )

        # Verify console.print was called 3 times
        assert mock_console.print.call_count == 3

    def test_render_banner_with_padding(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering banner with padding."""
        renderer.render_banner("Padded Banner", padding=True)

        # Should have 5 calls: padding, line, title, line, padding
        assert mock_console.print.call_count == 5

    def test_render_banner_without_padding(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering banner without padding."""
        renderer.render_banner("No Padding Banner", padding=False)

        # Should have 3 calls: line, title, line
        assert mock_console.print.call_count == 3

    def test_should_render_test_panel_with_data(self, renderer: TestResultRenderer):
        """Test should_render_test_panel returns True when there's test data."""
        stats = {
            "total": 100,
            "passed": 95,
            "failed": 5,
        }

        result = renderer.should_render_test_panel(stats)
        assert result is True

    def test_should_render_test_panel_all_zeros(self, renderer: TestResultRenderer):
        """Test should_render_test_panel returns False when all values are zero."""
        stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0.0,
        }

        result = renderer.should_render_test_panel(stats)
        assert result is False

    def test_should_render_test_panel_with_coverage_only(self, renderer: TestResultRenderer):
        """Test should_render_test_panel returns True when only coverage is present."""
        stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0.0,
            "coverage": 75.5,
        }

        result = renderer.should_render_test_panel(stats)
        assert result is True

    def test_should_render_test_panel_with_duration_only(self, renderer: TestResultRenderer):
        """Test should_render_test_panel returns True when only duration is present."""
        stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 12.3,
        }

        result = renderer.should_render_test_panel(stats)
        assert result is True

    def test_render_parsing_error_message(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering parsing error message."""
        error = ValueError("Invalid JSON format")

        renderer.render_parsing_error_message(error)

        # Verify console.print was called twice
        assert mock_console.print.call_count == 2

        # Check the error messages contain expected text
        calls = mock_console.print.call_args_list
        assert "Structured parsing failed" in str(calls[0])
        assert "Falling back to standard formatting" in str(calls[1])

    def test_render_test_results_panel_table_structure(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test that the rendered panel contains a properly structured table."""
        stats = {
            "total": 10,
            "passed": 8,
            "failed": 2,
            "skipped": 0,
            "errors": 0,
            "duration": 1.5,
        }

        renderer.render_test_results_panel(stats, workers=4, success=False)

        # Get the panel
        call_args = mock_console.print.call_args
        panel = call_args[0][0]

        # Verify it's a Panel
        assert isinstance(panel, Panel)

        # Verify title contains failure indication
        assert "Failed" in panel.title or "❌" in panel.title

    def test_render_test_results_panel_with_various_worker_counts(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering panel with different worker configurations."""
        stats = {
            "total": 100,
            "passed": 100,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 10.0,
        }

        # Test with integer workers
        renderer.render_test_results_panel(stats, workers=4, success=True)
        assert mock_console.print.called

        mock_console.reset_mock()

        # Test with "auto" workers
        renderer.render_test_results_panel(stats, workers="auto", success=True)
        assert mock_console.print.called

        mock_console.reset_mock()

        # Test with fractional workers
        renderer.render_test_results_panel(stats, workers=-2, success=True)
        assert mock_console.print.called


class TestTestResultRendererEdgeCases:
    """Test edge cases and error conditions for TestResultRenderer."""

    def test_render_with_empty_stats(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering panel with empty stats dictionary."""
        stats = {}

        # Empty dict causes KeyError - this is expected behavior
        # The renderer requires at minimum: total, passed, failed, skipped, errors
        with pytest.raises(KeyError):
            renderer.render_test_results_panel(stats, workers=1, success=True)

    def test_render_with_missing_optional_fields(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering panel with missing optional fields."""
        # Provide minimal required fields (duration is required)
        stats = {
            "total": 10,
            "passed": 8,
            "failed": 2,
            "skipped": 0,  # Required
            "errors": 0,   # Required
            "duration": 5.0,  # Required
            # Missing: xfailed, xpassed, coverage (optional)
        }

        renderer.render_test_results_panel(stats, workers=2, success=False)

        # Should render without errors
        assert mock_console.print.called

    def test_render_banner_empty_title(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test rendering banner with empty title."""
        renderer.render_banner("", padding=False)

        # Should render 3 times (line, empty title, line)
        assert mock_console.print.call_count == 3

    def test_render_parsing_error_with_exception_message(self, renderer: TestResultRenderer, mock_console: Mock):
        """Test parsing error message includes exception details."""
        error = RuntimeError("Unexpected token at line 42")

        renderer.render_parsing_error_message(error)

        # Verify error message is included
        calls = mock_console.print.call_args_list
        error_message = str(calls[0])
        assert "Unexpected token at line 42" in error_message or "RuntimeError" in error_message
