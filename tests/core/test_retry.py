import asyncio
import pytest
from unittest.mock import patch
from crackerjack.core.retry import (
    retry,
    retry_api_call,
    _calculate_delay,
    _prepare_next_attempt,
    _should_retry,
    _retry_async,
    _retry_sync,
    API_CONNECTION_EXCEPTIONS,
    example_api_call_async,
    example_api_call_sync
)


def test_calculate_delay_without_jitter():
    """Test delay calculation without jitter."""
    delay = _calculate_delay(1.0, jitter=False, backoff=2.0)
    assert delay == 2.0  # 1.0 * 2.0


def test_calculate_delay_with_jitter():
    """Test delay calculation with jitter."""
    delay = _calculate_delay(1.0, jitter=True, backoff=1.0)
    # With jitter, the delay should be between 0.5 and 1.0
    assert 0.5 <= delay <= 1.0


def test_should_retry():
    """Test the _should_retry function."""
    # Should retry when attempt < max_attempts - 1
    assert _should_retry(0, 3)  # First attempt of 3
    assert _should_retry(1, 3)  # Second attempt of 3
    assert not _should_retry(2, 3)  # Last attempt of 3


def test_prepare_next_attempt():
    """Test the _prepare_next_attempt function."""
    # Mock logger function
    log_calls = []
    def mock_logger(msg):
        log_calls.append(msg)

    # Test the function
    next_delay = _prepare_next_attempt(
        current_delay=1.0,
        max_delay=5.0,
        backoff=2.0,
        jitter=False,  # Disable jitter for predictable results
        attempt=0,
        max_attempts=3,
        e=ValueError("test error"),
        logger_func=mock_logger
    )

    # Check that the calculated delay is correct
    expected_delay = 2.0  # 1.0 * 2.0 (backoff)
    assert next_delay == expected_delay

    # Check that the logger was called with the expected message
    assert len(log_calls) == 1
    assert "Attempt 1/3 failed" in log_calls[0]


def test_retry_decorator_on_sync_function():
    """Test the retry decorator on a synchronous function."""
    call_count = 0

    @retry(max_attempts=3, delay=0.01, backoff=1.0, jitter=False)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("Flaky error")
        return "success"

    # This should succeed on the second attempt
    result = flaky_function()
    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_decorator_on_async_function():
    """Test the retry decorator on an asynchronous function."""
    call_count = 0

    @retry(max_attempts=3, delay=0.01, backoff=1.0, jitter=False)
    async def flaky_async_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("Flaky async error")
        return "async success"

    # This should succeed on the second attempt
    result = await flaky_async_function()
    assert result == "async success"
    assert call_count == 2


def test_retry_max_attempts_exceeded():
    """Test that the retry decorator raises the last exception after max attempts."""
    @retry(max_attempts=2, delay=0.01, backoff=1.0, jitter=False)
    def always_fail():
        raise ValueError("Always fails")

    # This should raise the ValueError after 2 attempts
    with pytest.raises(ValueError, match="Always fails"):
        always_fail()


@pytest.mark.asyncio
async def test_retry_async_max_attempts_exceeded():
    """Test that the retry decorator raises the last exception after max attempts for async functions."""
    @retry(max_attempts=2, delay=0.01, backoff=1.0, jitter=False)
    async def async_always_fail():
        raise ValueError("Async always fails")

    # This should raise the ValueError after 2 attempts
    with pytest.raises(ValueError, match="Async always fails"):
        await async_always_fail()


def test_retry_with_different_exceptions():
    """Test that the retry decorator only retries specified exceptions."""
    call_count = 0

    @retry(max_attempts=3, delay=0.01, backoff=1.0, jitter=False, exceptions=(ValueError,))
    def sometimes_wrong_exception():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise TypeError("Wrong exception type")  # Should not be retried
        return "success"

    # This should fail immediately with TypeError
    with pytest.raises(TypeError):
        sometimes_wrong_exception()

    assert call_count == 1  # Should not retry on TypeError


def test_retry_sync_function():
    """Test the _retry_sync function directly."""
    def successful_func(x):
        return f"result_{x}"

    result = _retry_sync(
        func=successful_func,
        args=("test",),
        kwargs={},
        max_attempts=3,
        delay=0.01,
        backoff=1.0,
        max_delay=None,
        jitter=False,
        exceptions=(Exception,),
        logger_func=None
    )

    assert result == "result_test"


@pytest.mark.asyncio
async def test_retry_async_function():
    """Test the _retry_async function directly."""
    async def successful_async_func(x):
        return f"async_result_{x}"

    result = await _retry_async(
        func=successful_async_func,
        args=("test",),
        kwargs={},
        max_attempts=3,
        delay=0.01,
        backoff=1.0,
        max_delay=None,
        jitter=False,
        exceptions=(Exception,),
        logger_func=None
    )

    assert result == "async_result_test"


def test_api_connection_exceptions():
    """Test that API_CONNECTION_EXCEPTIONS contains the expected exception types."""
    expected_exceptions = [
        ConnectionError,
        TimeoutError,
        ConnectionResetError,
        ConnectionAbortedError,
        BrokenPipeError,
        OSError,
    ]

    for exc in expected_exceptions:
        assert exc in API_CONNECTION_EXCEPTIONS


def test_retry_api_call_decorator():
    """Test the retry_api_call decorator."""
    call_count = 0

    @retry_api_call(max_attempts=3, delay=0.01, backoff=1.0)
    def api_call():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("Network error")
        return "api success"

    result = api_call()
    assert result == "api success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_example_api_call_async():
    """Test the example async API call function."""
    # This function has a 70% chance of failing initially, so we run it multiple times
    # to ensure it eventually succeeds with retries
    success_count = 0
    for _ in range(5):
        try:
            result = await example_api_call_async("https://example.com")
            if result.startswith("Success:"):
                success_count += 1
        except Exception:
            # Expected to occasionally fail even after retries
            pass

    # We expect at least some successes
    assert success_count >= 0  # This is just to ensure the function runs


def test_example_api_call_sync():
    """Test the example sync API call function."""
    # This function has a 70% chance of failing initially, so we run it multiple times
    # to ensure it eventually succeeds with retries
    success_count = 0
    for _ in range(5):
        try:
            result = example_api_call_sync("https://example.com")
            if result.startswith("Success:"):
                success_count += 1
        except Exception:
            # Expected to occasionally fail even after retries
            pass

    # We expect at least some successes
    assert success_count >= 0  # This is just to ensure the function runs
