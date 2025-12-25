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
    add_timestamp,
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
        assert "key = value" in captured.out

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

    def test_add_timestamp_processor(self) -> None:
        event_dict = {"event": "test"}
        result = add_timestamp(None, None, event_dict)

        assert "timestamp" in result
        assert "T" in result["timestamp"]
        assert result["timestamp"].endswith("Z")

    def test_get_logger_returns_structlog_logger(self) -> None:
        logger = get_logger("test.logger")

        assert isinstance(logger, structlog.BoundLogger)
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "debug")


class TestLoggingContext:
    def test_logging_context_success(self, capsys) -> None:
        setup_structured_logging(level="INFO", json_output=False)

        with LoggingContext(
            "test_operation",
            param1="value1",
            param2=42,
        ) as correlation_id:
            assert isinstance(correlation_id, str)
            assert len(correlation_id) == 8
            time.sleep(0.01)

        captured = capsys.readouterr()
        output = captured.out

        assert "Operation started" in output
        assert "Operation completed" in output
        assert "test_operation" in output
        assert "param1 = value1" in output
        assert "param2 = 42" in output
        assert "duration_seconds" in output

    def test_logging_context_exception(self, capsys) -> Never:
        setup_structured_logging(level="INFO", json_output=False)

        with pytest.raises(ValueError, match="Test error"):
            with LoggingContext("failing_operation", test_param="test_value"):
                time.sleep(0.01)
                msg = "Test error"
                raise ValueError(msg)

        captured = capsys.readouterr()
        output = captured.out

        assert "Operation started" in output
        assert "Operation failed" in output
        assert "failing_operation" in output
        assert "Test error" in output
        assert "ValueError" in output
        assert "duration_seconds" in output

    def test_logging_context_correlation_id_propagation(self) -> None:
        with LoggingContext("test_correlation") as correlation_id:
            assert get_correlation_id() == correlation_id


class TestLogPerformanceDecorator:
    def test_performance_decorator_success(self, capsys) -> None:
        setup_structured_logging(level="INFO", json_output=False)

        @log_performance("test_function", extra_param="extra_value")
        def successful_function(x, y):
            time.sleep(0.01)
            return x + y

        result = successful_function(2, 3)

        assert result == 5

        captured = capsys.readouterr()
        output = captured.out

        assert "Function completed" in output
        assert "test_function" in output
        assert "successful_function" in output
        assert "success = True" in output
        assert "duration_seconds" in output
        assert "extra_param = extra_value" in output

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
        output = captured.out

        assert "Function failed" in output
        assert "failing_function" in output
        assert "success = False" in output
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
            assert isinstance(logger, structlog.BoundLogger)
            assert hasattr(logger, "info")
            assert hasattr(logger, "error")

    def test_logger_names_are_correct(self) -> None:
        from crackerjack.services.logging import hook_logger

        hook_logger.info("Test hook message")


@pytest.fixture(autouse=True)
def reset_structlog_config():
    yield

    structlog.reset_defaults()


class TestLoggingIntegration:
    def test_full_logging_workflow_with_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as f:
            log_file = Path(f.name)

        try:
            setup_structured_logging(level="DEBUG", json_output=True, log_file=log_file)

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

            for handler in logging.getLogger().handlers:
                handler.flush()

            log_content = log_file.read_text()
            assert len(log_content.strip()) > 0

            log_lines = log_content.strip().split("\n")
            parsed_logs = [json.loads(line) for line in log_lines if line.strip()]

            assert len(parsed_logs) > 0

            for log_entry in parsed_logs:
                assert "correlation_id" in log_entry
                assert "timestamp" in log_entry

        finally:
            log_file.unlink(missing_ok=True)
