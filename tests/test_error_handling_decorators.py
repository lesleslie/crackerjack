"""Tests for error handling decorators."""

import json
import subprocess
import tempfile
from pathlib import Path
import pytest
from crackerjack.decorators.error_handling_decorators import (
    handle_file_errors,
    handle_json_errors,
    handle_subprocess_errors,
    handle_validation_errors,
    handle_network_errors,
    handle_all_errors,
    retry_on_error
)


class TestErrorHandlingDecorators:
    """Test cases for error handling decorators."""

    def test_handle_file_errors_decorator(self):
        """Test the handle_file_errors decorator."""

        @handle_file_errors(default_return="default_value", log_error=False)
        def failing_file_function():
            raise FileNotFoundError("Test file error")

        result = failing_file_function()
        assert result == "default_value"

    def test_handle_file_errors_reraise(self):
        """Test that handle_file_errors reraises by default."""

        @handle_file_errors(log_error=False)
        def failing_file_function():
            raise FileNotFoundError("Test file error")

        with pytest.raises(FileNotFoundError):
            failing_file_function()

    def test_handle_json_errors_decorator(self):
        """Test the handle_json_errors decorator."""

        @handle_json_errors(default_return="default_value", log_error=False)
        def failing_json_function():
            raise json.JSONDecodeError("Test JSON error", "{}", 0)

        result = failing_json_function()
        assert result == "default_value"

    def test_handle_subprocess_errors_decorator(self):
        """Test the handle_subprocess_errors decorator."""

        @handle_subprocess_errors(default_return="default_value", log_error=False)
        def failing_subprocess_function():
            raise subprocess.CalledProcessError(1, "test_command")

        result = failing_subprocess_function()
        assert result == "default_value"

    def test_handle_validation_errors_decorator(self):
        """Test the handle_validation_errors decorator."""

        @handle_validation_errors(default_return="default_value", log_error=False)
        def failing_validation_function():
            raise ValueError("Test validation error")

        result = failing_validation_function()
        assert result == "default_value"

    def test_handle_network_errors_decorator(self):
        """Test the handle_network_errors decorator."""

        @handle_network_errors(default_return="default_value", log_error=False)
        def failing_network_function():
            raise ConnectionError("Test network error")

        result = failing_network_function()
        assert result == "default_value"

    def test_handle_all_errors_decorator(self):
        """Test the handle_all_errors decorator."""

        @handle_all_errors(default_return="default_value", log_error=False)
        def failing_function():
            raise RuntimeError("Test runtime error")

        result = failing_function()
        assert result == "default_value"

    def test_handle_all_errors_excludes_system_exceptions(self):
        """Test that handle_all_errors excludes system exceptions."""

        @handle_all_errors(log_error=False)
        def keyboard_interrupt_function():
            raise KeyboardInterrupt("Test keyboard interrupt")

        with pytest.raises(KeyboardInterrupt):
            keyboard_interrupt_function()

    def test_success_case_no_error(self):
        """Test that decorators don't interfere with successful functions."""

        @handle_file_errors(default_return="default_value", log_error=False)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_retry_on_error_success(self):
        """Test retry_on_error decorator succeeds after retries."""
        attempt_count = 0
        max_fails = 2

        @retry_on_error(max_attempts=3, delay=0.01, log_retry=False)
        def sometimes_failing_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= max_fails:
                raise ValueError(f"Attempt {attempt_count} failed")
            return "success"

        result = sometimes_failing_function()
        assert result == "success"
        assert attempt_count == 3  # Should succeed on 3rd attempt

    def test_retry_on_error_fails_after_max_attempts(self):
        """Test retry_on_error decorator fails after max attempts."""

        @retry_on_error(max_attempts=2, delay=0.01, log_retry=False)
        def always_failing_function():
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_failing_function()

    def test_retry_on_error_different_exception_types(self):
        """Test retry_on_error decorator with different exception types."""

        @retry_on_error(max_attempts=2, delay=0.01, exceptions=(ValueError, TypeError), log_retry=False)
        def failing_with_different_errors():
            raise TypeError("Test type error")

        with pytest.raises(TypeError):
            failing_with_different_errors()
