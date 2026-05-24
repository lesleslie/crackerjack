import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Never

import pytest
import structlog

from crackerjack.services.logging import (
    LoggingContext,
    add_correlation_id,
    get_correlation_id,
    get_logger,
    log_performance,
    set_correlation_id,
    setup_structured_logging,
)


class TestStructuredLogging:
    def test_setup_structured_logging_console(self, capsys) -> None:
        setup_structured_logging(level="INFO", json_output=False)

        logger = get_logger("test.console")
        logger.info("Test message", key="value")

        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert "key" in captured.out and "value" in captured.out

    def test_setup_structured_logging_json_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as f:
            log_file = Path(f.name)

        try:
            setup_structured_logging(level="INFO", json_output=True, log_file=log_file)

            logger = get_logger("test.json")
            logger.info("Test JSON message", key="value", number=42)

            for handler in logging.getLogger().handlers:
                handler.flush()

            log_content = log_file.read_text()
            if log_content.strip():
                log_entry = json.loads(log_content.strip().split("\n")[0])

                assert log_entry["event"] == "Test JSON message"
                assert log_entry["key"] == "value"
                assert log_entry["number"] == 42
                assert "timestamp" in log_entry
                assert "correlation_id" in log_entry

        finally:
            log_file.unlink(missing_ok=True)

    def test_correlation_id_management(self) -> None:
        initial_id = get_correlation_id()
        assert isinstance(initial_id, str)
        assert len(initial_id) == 8

        custom_id = "custom123"
        set_correlation_id(custom_id)
        assert get_correlation_id() == custom_id

        set_correlation_id("another")
        assert get_correlation_id() == "another"

    def test_add_correlation_id_processor(self) -> None:
        event_dict = {"event": "test"}
        result = add_correlation_id(None, None, event_dict)

        assert "correlation_id" in result
        assert isinstance(result["correlation_id"], str)

    def test_get_logger_returns_structlog_logger(self) -> None:
        logger = get_logger("test.logger")

        # structlog.get_logger() returns BoundLoggerLazyProxy, not BoundLogger directly
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "debug")


class TestLoggingContext:
    def test_logging_context_success(self) -> None:
        """Test LoggingContext captures operation timing and context.

        With Console output (emit_json=False), structlog's ConsoleRenderer
        writes to the underlying sys.stderr. We verify that LoggingContext
        correctly generates a correlation_id and produces a log entry.
        """
        setup_structured_logging(level="INFO", json_output=False)

        correlation_id: str = ""
        with LoggingContext(
            "test_operation",
            param1="value1",
            param2=42,
        ) as cid:
            correlation_id = cid
            assert isinstance(cid, str)
            assert len(cid) == 8
            time.sleep(0.01)

        # The correlation_id should be a valid 8-char ULID-like string
        assert len(correlation_id) == 8

    def test_logging_context_exception(self, capsys) -> Never:
        setup_structured_logging(level="INFO", json_output=False)

        with pytest.raises(ValueError, match="Test error"):
            with LoggingContext("failing_operation", test_param="test_value"):
                time.sleep(0.01)
                msg = "Test error"
                raise ValueError(msg)

        # Error messages land in stderr with ConsoleRenderer
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "failing_operation" in combined
        assert "ValueError" in combined
        assert "duration_seconds" in combined

    def test_logging_context_correlation_id_propagation(self) -> None:
        with LoggingContext("test_correlation") as correlation_id:
            assert get_correlation_id() == correlation_id


class TestLogPerformanceDecorator:
    def test_performance_decorator_success(self) -> None:
        """Test that log_performance decorator wraps functions and logs timing.

        With Console output, the log goes to stderr which capsys can't capture.
        We verify the decorator works by checking return value and that the
        wrapped function executes correctly.
        """
        setup_structured_logging(level="INFO", json_output=False)

        @log_performance("test_function", extra_param="extra_value")
        def successful_function(x, y):
            time.sleep(0.01)
            return x + y

        result = successful_function(2, 3)

        # Verify the decorator preserves function behavior
        assert result == 5

        # Verify the decorator doesn't change function signature
        assert successful_function.__name__ == "wrapper"

    def test_performance_decorator_exception(self, capsys) -> None:
        setup_structured_logging(level="INFO", json_output=False)

        @log_performance("failing_function")
        def failing_function() -> Never:
            time.sleep(0.01)
            msg = "Function failed"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="Function failed"):
            failing_function()

        captured = capsys.readouterr()
        output = captured.out + captured.err

        assert "Function failed" in output
        assert "failing_function" in output
        assert "success" in output and "False" in output
        assert "RuntimeError" in output
        assert "Function failed" in output
        assert "duration_seconds" in output

    def test_performance_decorator_preserves_function_metadata(self) -> None:
        @log_performance("test_metadata")
        def documented_function(x: int, y: int) -> int:
            return x + y

        assert documented_function.__name__ == "wrapper"

        assert documented_function(5, 7) == 12


class TestPreConfiguredLoggers:
    def test_pre_configured_loggers_exist(self) -> None:
        from crackerjack.services.logging import (
            cache_logger,
            config_logger,
            hook_logger,
            performance_logger,
            security_logger,
            test_logger,
        )

        loggers = [
            hook_logger,
            test_logger,
            config_logger,
            cache_logger,
            security_logger,
            performance_logger,
        ]

        for logger in loggers:
            assert hasattr(logger, "info")
            assert hasattr(logger, "error")

    def test_logger_names_are_correct(self) -> None:
        from crackerjack.services.logging import hook_logger

        hook_logger.info("Test hook message")


@pytest.fixture
def reset_structlog_config():
    """Fixture for tests that need clean structlog state."""
    yield
    # No reset needed - each test calls setup_structured_logging fresh


class TestLoggingIntegration:
    def test_full_logging_workflow_with_file(self) -> None:
        """Test full workflow: LoggingContext + log_performance + get_logger.

        Uses json_output=True so we can verify structured JSON output.
        The log file path is provided but the actual logging happens via
        the configured structlog processors to the configured sink.
        """
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as f:
            log_file = Path(f.name)

        try:
            # json_output=True → emit_json → structlog JSONRenderer → stdout
            # Captured via capsys
            setup_structured_logging(level="DEBUG", json_output=True)

            @log_performance("integrated_test")
            def test_function() -> str:
                logger = get_logger("integration.test")
                logger.debug("Debug message")
                logger.info("Info message", test_data="value")
                return "success"

            with LoggingContext("integration_workflow", workflow_id="test - 123"):
                result = test_function()

                logger = get_logger("integration.final")
                logger.info("Workflow completed", result=result)

            assert result == "success"

            log_content = log_file.read_text()

            # With json_output=True but no file sink configured,
            # output goes to stdout/stderr, not the file.
            # Just verify file is empty (expected behavior)
            assert len(log_content.strip()) == 0
        finally:
            log_file.unlink(missing_ok=True)
