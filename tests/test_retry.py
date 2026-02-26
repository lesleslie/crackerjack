"""Tests for crackerjack.core.retry module."""

import pytest

from crackerjack.core.retry import (
    API_CONNECTION_EXCEPTIONS,
    _calculate_delay,
    _retry_async,
    _retry_sync,
    _should_retry,
    example_api_call_async,
    example_api_call_sync,
    retry,
    retry_api_call,
)


class TestCalculateDelay:
    """Tests for _calculate_delay function."""

    def test_calculate_delay_without_jitter(self) -> None:
        """Test delay calculation without jitter."""
        result = _calculate_delay(1.0, jitter=False, backoff=2.0)
        assert result == 2.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Test delay calculation with jitter adds randomness."""
        # With jitter, result should be between 0.5 * backoff and 1.0 * backoff
        # of current_delay
        result = _calculate_delay(1.0, jitter=True, backoff=2.0)
        assert 1.0 <= result <= 2.0  # 0.5 * 2.0 to 1.0 * 2.0


class TestShouldRetry:
    """Tests for _should_retry function."""

    def test_should_retry_returns_true_when_more_attempts(self) -> None:
        """Should return True when there are more attempts remaining."""
        assert _should_retry(attempt=0, max_attempts=3) is True
        assert _should_retry(attempt=1, max_attempts=3) is True

    def test_should_retry_returns_false_on_last_attempt(self) -> None:
        """Should return False on the last attempt."""
        assert _should_retry(attempt=2, max_attempts=3) is False


class TestRetryDecorator:
    """Tests for retry decorator."""

    def test_retry_decorator_returns_decorator(self) -> None:
        """Test that retry() returns a decorator function."""
        decorator = retry()
        assert callable(decorator)

    def test_retry_decorator_wraps_sync_function(self) -> None:
        """Test that retry decorator works with sync functions."""

        @retry(max_attempts=3, delay=0.01, jitter=False)
        def failing_func() -> str:
            failing_func.call_count += 1  # type: ignore[attr-defined]
            if failing_func.call_count < 3:  # type: ignore[attr-defined]
                msg = "Not yet"
                raise ValueError(msg)
            return "success"

        failing_func.call_count = 0
        result = failing_func()
        assert result == "success"
        assert failing_func.call_count == 3

    async def test_retry_decorator_wraps_async_function(self) -> None:
        """Test that retry decorator works with async functions."""

        @retry(max_attempts=3, delay=0.01, jitter=False)
        async def failing_async_func() -> str:
            failing_async_func.call_count += 1  # type: ignore[attr-defined]
            if failing_async_func.call_count < 2:  # type: ignore[attr-defined]
                msg = "Not yet"
                raise ValueError(msg)
            return "async success"

        failing_async_func.call_count = 0
        result = await failing_async_func()
        assert result == "async success"
        assert failing_async_func.call_count == 2

    def test_retry_raises_after_max_attempts(self) -> None:
        """Test that retry raises the last exception after max attempts."""

        @retry(max_attempts=2, delay=0.01, jitter=False)
        def always_failing() -> str:
            msg = "Always fails"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Always fails"):
            always_failing()

    def test_retry_respects_exception_types(self) -> None:
        """Test that retry only catches specified exception types."""

        @retry(
            max_attempts=3,
            delay=0.01,
            jitter=False,
            exceptions=(KeyError,),
        )
        def raises_value_error() -> str:
            msg = "Not a KeyError"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Not a KeyError"):
            raises_value_error()


class TestRetryApiCall:
    """Tests for retry_api_call decorator."""

    def test_retry_api_call_returns_decorator(self) -> None:
        """Test that retry_api_call() returns a decorator function."""
        decorator = retry_api_call()
        assert callable(decorator)

    def test_retry_api_call_uses_connection_exceptions(self) -> None:
        """Test that retry_api_call uses API_CONNECTION_EXCEPTIONS."""
        assert API_CONNECTION_EXCEPTIONS == (
            ConnectionError,
            TimeoutError,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            OSError,
        )


class TestExampleApiCallAsync:
    """Tests for example_api_call_async function."""

    async def test_example_api_call_async_eventually_succeeds(self) -> None:
        """Test that async API call eventually succeeds with retries."""
        # The function has 70% failure rate, but with retries should eventually succeed
        result = await example_api_call_async("http://example.com")
        assert result == "Success: http://example.com"


class TestExampleApiCallSync:
    """Tests for example_api_call_sync function."""

    def test_example_api_call_sync_eventually_succeeds(self) -> None:
        """Test that sync API call eventually succeeds with retries."""
        # The function has 70% failure rate, but with retries should eventually succeed
        result = example_api_call_sync("http://example.com")
        assert result == "Success: http://example.com"


class TestRetryAsync:
    """Tests for _retry_async internal function."""

    async def test_retry_async_succeeds_on_first_try(self) -> None:
        """Test _retry_async succeeds immediately when function works."""

        async def success_func() -> str:
            return "immediate success"

        result = await _retry_async(
            success_func,
            (),
            {},
            max_attempts=3,
            delay=0.01,
            backoff=2.0,
            max_delay=None,
            jitter=False,
            exceptions=(Exception,),
            logger_func=None,
        )
        assert result == "immediate success"

    async def test_retry_async_retries_on_failure(self) -> None:
        """Test _retry_async retries on failure."""
        call_count = 0

        async def eventually_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                msg = "Not yet"
                raise ValueError(msg)
            return "success"

        result = await _retry_async(
            eventually_succeeds,
            (),
            {},
            max_attempts=3,
            delay=0.01,
            backoff=2.0,
            max_delay=None,
            jitter=False,
            exceptions=(ValueError,),
            logger_func=None,
        )
        assert result == "success"
        assert call_count == 3


class TestRetrySync:
    """Tests for _retry_sync internal function."""

    def test_retry_sync_succeeds_on_first_try(self) -> None:
        """Test _retry_sync succeeds immediately when function works."""

        def success_func() -> str:
            return "immediate success"

        result = _retry_sync(
            success_func,
            (),
            {},
            max_attempts=3,
            delay=0.01,
            backoff=2.0,
            max_delay=None,
            jitter=False,
            exceptions=(Exception,),
            logger_func=None,
        )
        assert result == "immediate success"

    def test_retry_sync_retries_on_failure(self) -> None:
        """Test _retry_sync retries on failure."""
        call_count = 0

        def eventually_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                msg = "Not yet"
                raise ValueError(msg)
            return "success"

        result = _retry_sync(
            eventually_succeeds,
            (),
            {},
            max_attempts=3,
            delay=0.01,
            backoff=2.0,
            max_delay=None,
            jitter=False,
            exceptions=(ValueError,),
            logger_func=None,
        )
        assert result == "success"
        assert call_count == 3

    def test_retry_sync_respects_max_delay(self) -> None:
        """Test _retry_sync respects max_delay parameter."""
        call_count = 0
        delays: list[float] = []

        def track_delay(delay: float) -> None:
            delays.append(delay)

        def eventually_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                msg = "Not yet"
                raise ValueError(msg)
            return "success"

        result = _retry_sync(
            eventually_succeeds,
            (),
            {},
            max_attempts=3,
            delay=10.0,
            backoff=2.0,
            max_delay=0.05,  # Cap delay at 0.05 seconds
            jitter=False,
            exceptions=(ValueError,),
            logger_func=track_delay,
        )
        assert result == "success"
        # The delay should be capped at max_delay
        assert all(d <= 0.05 for d in delays)
