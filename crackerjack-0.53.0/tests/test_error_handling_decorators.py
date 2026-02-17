"""Tests for error handling decorators."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Never

import pytest

from crackerjack.decorators.error_handling_decorators import (
    handle_all_errors,
    handle_file_errors,
    handle_json_errors,
    handle_network_errors,
    handle_subprocess_errors,
    handle_validation_errors,
    retry_on_error,
)


class TestErrorHandlingDecorators:
    """Test cases for error handling decorators."""

    def test_handle_file_errors_decorator(self) -> None:
        """Test the handle_file_errors decorator."""

        @handle_file_errors(default_return="default_value", log_error=False)
        def failing_file_function() -> Never:
            msg = "Test file error"
            raise FileNotFoundError(msg)

        result = failing_file_function()
        assert result == "default_value"

    def test_handle_file_errors_reraise(self) -> None:
        """Test that handle_file_errors reraises by default."""

        @handle_file_errors(log_error=False)
        def failing_file_function() -> Never:
            msg = "Test file error"
            raise FileNotFoundError(msg)

        with pytest.raises(FileNotFoundError):
            failing_file_function()

    def test_handle_json_errors_decorator(self) -> None:
        """Test the handle_json_errors decorator."""

        @handle_json_errors(default_return="default_value", log_error=False)
        def failing_json_function() -> Never:
            msg = "Test JSON error"
            raise json.JSONDecodeError(msg, "{}", 0)

        result = failing_json_function()
        assert result == "default_value"

    def test_handle_subprocess_errors_decorator(self) -> None:
        """Test the handle_subprocess_errors decorator."""

        @handle_subprocess_errors(default_return="default_value", log_error=False)
        def failing_subprocess_function() -> Never:
            raise subprocess.CalledProcessError(1, "test_command")

        result = failing_subprocess_function()
        assert result == "default_value"

    def test_handle_validation_errors_decorator(self) -> None:
        """Test the handle_validation_errors decorator."""

        @handle_validation_errors(default_return="default_value", log_error=False)
        def failing_validation_function() -> Never:
            msg = "Test validation error"
            raise ValueError(msg)

        result = failing_validation_function()
        assert result == "default_value"

    def test_handle_network_errors_decorator(self) -> None:
        """Test the handle_network_errors decorator."""

        @handle_network_errors(default_return="default_value", log_error=False)
        def failing_network_function() -> Never:
            msg = "Test network error"
            raise ConnectionError(msg)

        result = failing_network_function()
        assert result == "default_value"

    def test_handle_all_errors_decorator(self) -> None:
        """Test the handle_all_errors decorator."""

        @handle_all_errors(default_return="default_value", log_error=False)
        def failing_function() -> Never:
            msg = "Test runtime error"
            raise RuntimeError(msg)

        result = failing_function()
        assert result == "default_value"

    def test_handle_all_errors_excludes_system_exceptions(self) -> None:
        """Test that handle_all_errors excludes system exceptions."""

        @handle_all_errors(log_error=False)
        def keyboard_interrupt_function() -> Never:
            msg = "Test keyboard interrupt"
            raise KeyboardInterrupt(msg)

        with pytest.raises(KeyboardInterrupt):
            keyboard_interrupt_function()

    def test_success_case_no_error(self) -> None:
        """Test that decorators don't interfere with successful functions."""

        @handle_file_errors(default_return="default_value", log_error=False)
        def successful_function() -> str:
            return "success"

        result = successful_function()
        assert result == "success"

    def test_retry_on_error_success(self) -> None:
        """Test retry_on_error decorator succeeds after retries."""
        attempt_count = 0
        max_fails = 2

        @retry_on_error(max_attempts=3, delay=0.01, log_retry=False)
        def sometimes_failing_function() -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= max_fails:
                msg = f"Attempt {attempt_count} failed"
                raise ValueError(msg)
            return "success"

        result = sometimes_failing_function()
        assert result == "success"
        assert attempt_count == 3  # Should succeed on 3rd attempt

    def test_retry_on_error_fails_after_max_attempts(self) -> None:
        """Test retry_on_error decorator fails after max attempts."""

        @retry_on_error(max_attempts=2, delay=0.01, log_retry=False)
        def always_failing_function() -> Never:
            msg = "Always fails"
            raise ValueError(msg)

        with pytest.raises(ValueError):
            always_failing_function()

    def test_retry_on_error_different_exception_types(self) -> None:
        """Test retry_on_error decorator with different exception types."""

        @retry_on_error(max_attempts=2, delay=0.01, exceptions=(ValueError, TypeError), log_retry=False)
        def failing_with_different_errors() -> Never:
            msg = "Test type error"
            raise TypeError(msg)

        with pytest.raises(TypeError):
            failing_with_different_errors()
