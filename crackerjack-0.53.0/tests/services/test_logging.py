import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from crackerjack.services.logging import (
    add_correlation_id,
    add_timestamp,
    setup_structured_logging,
    get_logger,
    get_correlation_id,
    set_correlation_id,
    LoggingContext,
    log_performance,
)


def test_add_correlation_id():
    """Test the add_correlation_id processor."""
    event_dict = {"event": "test_event"}

    # Initially, no correlation ID is set
    result = add_correlation_id(None, None, event_dict)

    # The correlation_id should be added with a generated value
    assert "correlation_id" in result
    assert isinstance(result["correlation_id"], str)
    assert len(result["correlation_id"]) == 8  # UUID hex[:8] gives 8 chars


def test_add_timestamp():
    """Test the add_timestamp processor."""
    event_dict = {"event": "test_event"}

    result = add_timestamp(None, None, event_dict)

    assert "timestamp" in result
    assert isinstance(result["timestamp"], str)
    # Timestamp should be in ISO format ending with Z
    assert result["timestamp"].endswith("Z")


def test_setup_structured_logging_defaults():
    """Test setup_structured_logging with default parameters."""
    # This should not raise an exception
    setup_structured_logging()

    # Verify that we can get a logger
    logger = get_logger("test_logger")
    assert logger is not None


def test_setup_structured_logging_with_params():
    """Test setup_structured_logging with custom parameters."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        # This should not raise an exception
        setup_structured_logging(level="DEBUG", json_output=True, log_file=tmp_path)

        # Verify that we can get a logger
        logger = get_logger("test_logger_json")
        assert logger is not None
    finally:
        # Clean up the temp file
        tmp_path.unlink(missing_ok=True)


def test_get_logger():
    """Test getting a logger."""
    logger = get_logger("test.module")

    assert logger is not None
    # Verify that the logger is cached
    cached_logger = get_logger("test.module")
    assert logger is cached_logger


def test_get_correlation_id():
    """Test getting correlation ID."""
    # Initially, no correlation ID is set
    corr_id = get_correlation_id()

    assert isinstance(corr_id, str)
    assert len(corr_id) == 8  # UUID hex[:8] gives 8 chars


def test_set_correlation_id():
    """Test setting correlation ID."""
    test_id = "test1234"
    set_correlation_id(test_id)

    retrieved_id = get_correlation_id()

    assert retrieved_id == test_id


def test_logging_context():
    """Test LoggingContext context manager."""
    with LoggingContext("test_operation", param="value") as corr_id:
        # Inside the context, we should have a correlation ID
        assert corr_id is not None
        assert len(corr_id) == 8

    # The context manager should complete without errors


def test_logging_context_with_exception():
    """Test LoggingContext context manager with an exception."""
    try:
        with LoggingContext("test_operation_with_error", param="value"):
            raise ValueError("Test error")
    except ValueError:
        pass  # Expected

    # The context manager should handle the exception gracefully


def test_log_performance_decorator():
    """Test the log_performance decorator."""
    @log_performance(operation="test_operation", param="value")
    def sample_function():
        return "result"

    # Call the decorated function
    result = sample_function()

    assert result == "result"


def test_log_performance_decorator_with_exception():
    """Test the log_performance decorator with an exception."""
    @log_performance(operation="test_operation_with_error", param="value")
    def sample_function_that_fails():
        raise ValueError("Test error")

    # Call the decorated function and expect the exception
    with pytest.raises(ValueError):
        sample_function_that_fails()


def test_log_performance_decorator_with_args():
    """Test the log_performance decorator with arguments."""
    @log_performance(operation="test_operation_args", param="value")
    def sample_function_with_args(x, y):
        return x + y

    # Call the decorated function with arguments
    result = sample_function_with_args(5, 3)

    assert result == 8


def test_global_loggers_exist():
    """Test that global loggers are created."""
    from crackerjack.services.logging import (
        hook_logger,
        test_logger,
        config_logger,
        cache_logger,
        security_logger,
        performance_logger,
    )

    # All global loggers should exist and not be None
    assert hook_logger is not None
    assert test_logger is not None
    assert config_logger is not None
    assert cache_logger is not None
    assert security_logger is not None
    assert performance_logger is not None
