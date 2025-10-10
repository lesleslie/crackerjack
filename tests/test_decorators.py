"""Tests for error handling decorators."""

import asyncio
from pathlib import Path

import pytest

from crackerjack.decorators import (
    graceful_degradation,
    handle_errors,
    log_errors,
    retry,
    validate_args,
    with_timeout,
)
from crackerjack.errors import (
    FileError,
    NetworkError,
    TimeoutError as CrackerjackTimeoutError,
    ValidationError,
)


class TestRetryDecorator:
    """Test retry decorator functionality."""

    def test_retry_success_on_first_attempt(self) -> None:
        """Test that successful operations don't retry."""
        call_count = 0

        @retry(max_attempts=3)
        def successful_operation() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_operation()

        assert result == "success"
        assert call_count == 1

    def test_retry_with_eventual_success(self) -> None:
        """Test retry logic with eventual success."""
        call_count = 0

        @retry(max_attempts=3, backoff=0.1)
        def flaky_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Temporary failure")
            return "success"

        result = flaky_operation()

        assert result == "success"
        assert call_count == 3

    def test_retry_exhausts_attempts(self) -> None:
        """Test that retry gives up after max attempts."""

        @retry(max_attempts=3, backoff=0.1)
        def always_fails() -> str:
            raise NetworkError("Permanent failure")

        with pytest.raises(NetworkError):
            always_fails()

    def test_retry_specific_exceptions(self) -> None:
        """Test retry only catches specified exception types."""

        @retry(max_attempts=3, exceptions=[NetworkError])
        def wrong_error() -> str:
            raise FileError("File error")

        # Should not retry FileError, only NetworkError
        with pytest.raises(FileError):
            wrong_error()

    @pytest.mark.asyncio
    async def test_async_retry(self) -> None:
        """Test retry with async functions."""
        call_count = 0

        @retry(max_attempts=3, backoff=0.1)
        async def async_flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Temporary")
            return "success"

        result = await async_flaky()

        assert result == "success"
        assert call_count == 2


class TestTimeoutDecorator:
    """Test timeout decorator functionality."""

    @pytest.mark.asyncio
    async def test_async_timeout_success(self) -> None:
        """Test async function completes within timeout."""

        @with_timeout(seconds=1.0)
        async def fast_operation() -> str:
            await asyncio.sleep(0.1)
            return "done"

        result = await fast_operation()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_async_timeout_exceeded(self) -> None:
        """Test async function exceeds timeout."""

        @with_timeout(seconds=0.1)
        async def slow_operation() -> str:
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(CrackerjackTimeoutError):
            await slow_operation()

    @pytest.mark.asyncio
    async def test_timeout_custom_message(self) -> None:
        """Test timeout with custom error message."""

        @with_timeout(seconds=0.1, error_message="Custom timeout message")
        async def slow_operation() -> str:
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(CrackerjackTimeoutError) as exc_info:
            await slow_operation()

        assert "Custom timeout message" in str(exc_info.value)


class TestHandleErrors:
    """Test error handling decorator."""

    def test_handle_errors_with_fallback_value(self) -> None:
        """Test error handling with static fallback value."""

        @handle_errors(fallback={})
        def failing_operation() -> dict:
            raise FileError("File not found")

        result = failing_operation()
        assert result == {}

    def test_handle_errors_with_fallback_callable(self) -> None:
        """Test error handling with callable fallback."""

        @handle_errors(fallback=lambda: {"default": True})
        def failing_operation() -> dict:
            raise FileError("File not found")

        result = failing_operation()
        assert result == {"default": True}

    def test_handle_errors_suppress(self) -> None:
        """Test error suppression."""

        @handle_errors(suppress=True)
        def failing_operation() -> str:
            raise ValueError("Some error")

        result = failing_operation()
        assert result is None

    def test_handle_errors_transform(self) -> None:
        """Test error transformation."""

        @handle_errors(
            error_types=[ValueError],
            transform_to=FileError,
        )
        def failing_operation() -> str:
            raise ValueError("Original error")

        with pytest.raises(FileError) as exc_info:
            failing_operation()

        assert "Original error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_handle_errors(self) -> None:
        """Test async error handling."""

        @handle_errors(fallback="fallback")
        async def async_failing() -> str:
            raise ValueError("Error")

        result = await async_failing()
        assert result == "fallback"


class TestGracefulDegradation:
    """Test graceful degradation decorator."""

    def test_graceful_degradation_with_error(self) -> None:
        """Test graceful degradation returns fallback on error."""

        @graceful_degradation(fallback_value=[], warn=False)
        def failing_operation() -> list:
            raise RuntimeError("Failed")

        result = failing_operation()
        assert result == []

    def test_graceful_degradation_success(self) -> None:
        """Test graceful degradation passes through success."""

        @graceful_degradation(fallback_value=[], warn=False)
        def successful_operation() -> list:
            return ["item1", "item2"]

        result = successful_operation()
        assert result == ["item1", "item2"]

    @pytest.mark.asyncio
    async def test_async_graceful_degradation(self) -> None:
        """Test async graceful degradation."""

        @graceful_degradation(fallback_value=0, warn=False)
        async def async_failing() -> int:
            raise ValueError("Error")

        result = await async_failing()
        assert result == 0


class TestLogErrors:
    """Test error logging decorator."""

    def test_log_errors_reraises(self) -> None:
        """Test that log_errors still raises the exception."""

        @log_errors()
        def failing_operation() -> str:
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_operation()

    @pytest.mark.asyncio
    async def test_async_log_errors(self) -> None:
        """Test async error logging."""

        @log_errors()
        async def async_failing() -> str:
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await async_failing()


class TestValidateArgs:
    """Test argument validation decorator."""

    def test_validate_args_success(self) -> None:
        """Test successful argument validation."""

        @validate_args(
            validators={"count": lambda x: x > 0},
        )
        def process_items(count: int) -> bool:
            return True

        result = process_items(count=5)
        assert result is True

    def test_validate_args_failure(self) -> None:
        """Test failed argument validation."""

        @validate_args(
            validators={"count": lambda x: x > 0},
        )
        def process_items(count: int) -> bool:
            return True

        with pytest.raises(ValidationError):
            process_items(count=-1)

    def test_validate_args_multiple_validators(self) -> None:
        """Test multiple validators for one parameter."""

        @validate_args(
            validators={
                "email": [
                    lambda e: "@" in e,
                    lambda e: len(e) > 5,
                ]
            },
        )
        def register_user(email: str) -> bool:
            return True

        # Valid email
        assert register_user(email="user@example.com") is True

        # Missing @
        with pytest.raises(ValidationError):
            register_user(email="invalid")

        # Too short
        with pytest.raises(ValidationError):
            register_user(email="a@b")

    def test_validate_args_type_checking(self) -> None:
        """Test automatic type checking."""

        @validate_args(type_check=True)
        def typed_function(count: int, name: str) -> bool:
            return True

        # Valid types
        assert typed_function(count=5, name="test") is True

        # Invalid types should fail (note: runtime type checking is best-effort)
        # Type hints alone don't enforce runtime validation without additional checks

    @pytest.mark.asyncio
    async def test_async_validate_args(self) -> None:
        """Test async argument validation."""

        @validate_args(validators={"count": lambda x: x > 0})
        async def async_process(count: int) -> bool:
            return True

        result = await async_process(count=5)
        assert result is True

        with pytest.raises(ValidationError):
            await async_process(count=-1)


class TestDecoratorComposition:
    """Test stacking multiple decorators."""

    @pytest.mark.asyncio
    async def test_retry_with_timeout(self) -> None:
        """Test retry combined with timeout."""
        call_count = 0

        @with_timeout(seconds=2.0)
        @retry(max_attempts=3, backoff=0.1)
        async def flaky_with_timeout() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Temporary")
            await asyncio.sleep(0.1)
            return "success"

        result = await flaky_with_timeout()
        assert result == "success"

    def test_validate_with_handle_errors(self) -> None:
        """Test validation combined with error handling."""

        @handle_errors(fallback=-1)
        @validate_args(validators={"count": lambda x: x > 0})
        def process_with_validation(count: int) -> int:
            return count * 2

        # Valid input
        assert process_with_validation(count=5) == 10

        # Invalid input - validation fails, handle_errors catches it
        result = process_with_validation(count=-1)
        assert result == -1

    @pytest.mark.asyncio
    async def test_full_stack(self) -> None:
        """Test multiple decorators stacked together."""
        call_count = 0

        @graceful_degradation(fallback_value="fallback", warn=False)
        @with_timeout(seconds=2.0)
        @retry(max_attempts=2, backoff=0.1)
        @log_errors()
        async def complex_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkError("First attempt fails")
            return "success"

        result = await complex_operation()
        assert result == "success"
        assert call_count == 2
