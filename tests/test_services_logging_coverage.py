import logging
import tempfile
import uuid
from contextvars import copy_context
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import structlog

from crackerjack.services.logging import (
    LoggingContext,
    add_correlation_id,
    add_timestamp,
    cache_logger,
    config_logger,
    correlation_id,
    get_correlation_id,
    get_logger,
    hook_logger,
    log_performance,
    performance_logger,
    security_logger,
    set_correlation_id,
    setup_structured_logging,
    test_logger,
)


class TestCorrelationIdFunctions:
    def test_set_and_get_correlation_id(self) -> None:
        test_id = "test - correlation - 123"

        ctx = copy_context()

        def test_in_context() -> None:
            set_correlation_id(test_id)
            retrieved_id = get_correlation_id()
            assert retrieved_id == test_id

        ctx.run(test_in_context)

    def test_get_correlation_id_generates_new(self) -> None:
        ctx = copy_context()

        def test_in_context() -> None:
            correlation_id.set(None)

            with patch.object(uuid, "uuid4") as mock_uuid:
                mock_uuid.return_value.hex = "generated - uuid - id"
                mock_uuid.return_value.__str__ = lambda self: "generated - uuid - id"
                mock_uuid.return_value.__getitem__ = (
                    lambda self, slice_obj: "generated - uuid - id"[: slice_obj.stop]
                    if isinstance(slice_obj, slice)
                    else "generated - uuid - id"[slice_obj]
                )

                generated_id = get_correlation_id()

                assert generated_id == "generate"
                mock_uuid.assert_called_once()

        ctx.run(test_in_context)

    def test_get_correlation_id_returns_existing(self) -> None:
        ctx = copy_context()

        def test_in_context() -> None:
            existing_id = "existing - 123"
            correlation_id.set(existing_id)

            retrieved_id = get_correlation_id()
            assert retrieved_id == existing_id

        ctx.run(test_in_context)


class TestLogProcessors:
    def test_add_correlation_id_processor(self) -> None:
        ctx = copy_context()

        def test_in_context() -> None:
            test_id = "processor - test - 123"
            set_correlation_id(test_id)

            event_dict = {"event": "test"}
            result = add_correlation_id(None, None, event_dict)

            assert result["correlation_id"] == test_id
            assert result["event"] == "test"

        ctx.run(test_in_context)

    def test_add_correlation_id_generates_if_none(self) -> None:
        ctx = copy_context()

        def test_in_context() -> None:
            correlation_id.set(None)

            event_dict = {"event": "test"}
            result = add_correlation_id(None, None, event_dict)

            assert "correlation_id" in result
            assert len(result["correlation_id"]) == 8

        ctx.run(test_in_context)

    def test_add_timestamp_processor(self) -> None:
        event_dict = {"event": "test"}

        with patch("time.strftime") as mock_strftime:
            mock_strftime.return_value = "2024 - 01 - 15T10: 30: 45.123456"

            result = add_timestamp(None, None, event_dict)

            assert result["timestamp"] == "2024 - 01 - 15T10: 30: 45.123Z"
            assert result["event"] == "test"
            mock_strftime.assert_called_once_with(" % Y -% m -% dT % H: % M: % S. % f")


class TestStructuredLoggingSetup:
    @pytest.fixture
    def temp_log_file(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            yield Path(f.name)

    def test_setup_structured_logging_defaults(self) -> None:
        with (
            patch("structlog.configure") as mock_configure,
            patch("logging.basicConfig") as mock_basic_config,
        ):
            setup_structured_logging()

            mock_configure.assert_called_once()
            call_args = mock_configure.call_args[1]
            assert call_args["wrapper_class"] == structlog.stdlib.BoundLogger
            assert call_args["cache_logger_on_first_use"] is True

            processors = call_args["processors"]
            [p.__name__ if hasattr(p, "__name__") else str(p) for p in processors]

            assert len(processors) > 5

            mock_basic_config.assert_called_once()
            basic_call_args = mock_basic_config.call_args[1]
            assert basic_call_args["level"] == logging.INFO
            assert basic_call_args["format"] == "%(message)s"

    def test_setup_structured_logging_custom_level(self) -> None:
        with (
            patch("structlog.configure"),
            patch("logging.basicConfig") as mock_basic_config,
        ):
            setup_structured_logging(level="DEBUG")

            mock_basic_config.assert_called_once()
            basic_call_args = mock_basic_config.call_args[1]
            assert basic_call_args["level"] == logging.DEBUG

    def test_setup_structured_logging_with_file(self, temp_log_file) -> None:
        with (
            patch("structlog.configure"),
            patch("logging.basicConfig") as mock_basic_config,
        ):
            setup_structured_logging(log_file=temp_log_file)

            mock_basic_config.assert_called_once()
            basic_call_args = mock_basic_config.call_args[1]

            handlers = basic_call_args["handlers"]
            assert len(handlers) == 2

            assert temp_log_file.parent.exists()

    def test_setup_structured_logging_json_output_false(self) -> None:
        with (
            patch("structlog.configure") as mock_configure,
            patch("logging.basicConfig"),
        ):
            setup_structured_logging(json_output=False)

            mock_configure.assert_called_once()
            call_args = mock_configure.call_args[1]
            processors = call_args["processors"]

            assert len(processors) > 0

    def test_setup_structured_logging_creates_log_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "nested" / "dir" / "test.log"

            with patch("structlog.configure"), patch("logging.basicConfig"):
                setup_structured_logging(log_file=log_file)

                assert log_file.parent.exists()


class TestGetLogger:
    def test_get_logger_returns_bound_logger(self) -> None:
        logger = get_logger("test.logger")

        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")


class TestLoggingContext:
    def test_logging_context_successful_operation(self) -> None:
        ctx = copy_context()

        def test_in_context() -> None:
            mock_logger = Mock()

            with (
                patch(
                    "crackerjack.services.logging.get_logger", return_value=mock_logger
                ),
                patch("time.time", side_effect=[1000.0, 1005.5]),
            ):
                with LoggingContext(
                    "test_operation", param1="value1"
                ) as correlation_id:
                    assert isinstance(correlation_id, str)
                    assert len(correlation_id) == 8

                assert mock_logger.info.call_count == 2
                start_call = mock_logger.info.call_args_list[0]
                assert start_call[0][0] == "Operation started"
                assert start_call[1]["operation"] == "test_operation"
                assert start_call[1]["param1"] == "value1"

                end_call = mock_logger.info.call_args_list[1]
                assert end_call[0][0] == "Operation completed"
                assert end_call[1]["operation"] == "test_operation"
                assert end_call[1]["duration_seconds"] == 5.5
                assert end_call[1]["param1"] == "value1"

        ctx.run(test_in_context)

    def test_logging_context_failed_operation(self) -> None:
        ctx = copy_context()

        def test_in_context():
            mock_logger = Mock()

            with (
                patch(
                    "crackerjack.services.logging.get_logger", return_value=mock_logger
                ),
                patch("time.time", side_effect=[1000.0, 1003.2]),
            ):
                with pytest.raises(ValueError):
                    with LoggingContext("failing_operation", param1="value1"):
                        raise ValueError("Test error")

                start_call = mock_logger.info.call_args_list[0]
                assert start_call[0][0] == "Operation started"

                mock_logger.error.assert_called_once()
                error_call = mock_logger.error.call_args
                assert error_call[0][0] == "Operation failed"
                assert error_call[1]["operation"] == "failing_operation"
                assert error_call[1]["duration_seconds"] == 3.2
                assert error_call[1]["error"] == "Test error"
                assert error_call[1]["error_type"] == "ValueError"
                assert error_call[1]["param1"] == "value1"

        ctx.run(test_in_context)

    def test_logging_context_initialization(self) -> None:
        with (
            patch("crackerjack.services.logging.get_logger") as mock_get_logger,
            patch("time.time", return_value=1000.0),
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            context = LoggingContext("init_test", key="value")

            assert context.operation == "init_test"
            assert context.kwargs == {"key": "value"}
            assert len(context.correlation_id) == 8
            assert context.logger == mock_logger
            assert context.start_time == 1000.0

            mock_get_logger.assert_called_once_with("crackerjack.context")


class TestLogPerformanceDecorator:
    def test_log_performance_successful_function(self) -> None:
        mock_logger = Mock()

        with (
            patch("crackerjack.services.logging.get_logger", return_value=mock_logger),
            patch("time.time", side_effect=[1000.0, 1002.5]),
        ):

            @log_performance("test_operation", param="value")
            def test_function(arg1, arg2=None) -> str:
                return f"result_{arg1}_{arg2}"

            result = test_function("hello", arg2="world")

            assert result == "result_hello_world"

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "Function completed"
            assert call_args[1]["operation"] == "test_operation"
            assert call_args[1]["function"] == "test_function"
            assert call_args[1]["duration_seconds"] == 2.5
            assert call_args[1]["success"] is True
            assert call_args[1]["param"] == "value"

    def test_log_performance_failed_function(self) -> None:
        mock_logger = Mock()

        with (
            patch("crackerjack.services.logging.get_logger", return_value=mock_logger),
            patch("time.time", side_effect=[1000.0, 1001.8]),
        ):

            @log_performance("failing_operation", param="value")
            def failing_function():
                raise RuntimeError("Function failed")

            with pytest.raises(RuntimeError):
                failing_function()

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "Function failed"
            assert call_args[1]["operation"] == "failing_operation"
            assert call_args[1]["function"] == "failing_function"
            assert call_args[1]["duration_seconds"] == 1.8
            assert call_args[1]["success"] is False
            assert call_args[1]["error"] == "Function failed"
            assert call_args[1]["error_type"] == "RuntimeError"
            assert call_args[1]["param"] == "value"

    def test_log_performance_logger_name_generation(self) -> None:
        with patch("crackerjack.services.logging.get_logger") as mock_get_logger:
            mock_get_logger.return_value = Mock()

            @log_performance("test_op")
            def my_test_function() -> str:
                return "result"

            my_test_function()

            mock_get_logger.assert_called_with("crackerjack.perf.my_test_function")


class TestPreconfiguredLoggers:
    def test_preconfigured_loggers_exist(self) -> None:
        assert hook_logger is not None
        assert test_logger is not None
        assert config_logger is not None
        assert cache_logger is not None
        assert security_logger is not None
        assert performance_logger is not None

        for logger in [
            hook_logger,
            test_logger,
            config_logger,
            cache_logger,
            security_logger,
            performance_logger,
        ]:
            assert hasattr(logger, "info")
            assert hasattr(logger, "error")
            assert hasattr(logger, "debug")
            assert hasattr(logger, "warning")

    def test_preconfigured_logger_names(self) -> None:
        assert callable(hook_logger.info)
        assert callable(test_logger.error)
        assert callable(config_logger.debug)
        assert callable(cache_logger.warning)
        assert callable(security_logger.info)
        assert callable(performance_logger.error)


class TestLoggingIntegration:
    def test_full_logging_workflow(self) -> None:
        ctx = copy_context()

        def test_in_context() -> None:
            with patch("crackerjack.services.logging.get_logger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                with LoggingContext("integration_test", component="test") as cid:

                    @log_performance("decorated_operation")
                    def test_operation():
                        event_dict = {"message": "test event"}
                        processed = add_correlation_id(None, None, event_dict)
                        return processed

                    result = test_operation()

                    assert result["correlation_id"] == cid

                assert mock_get_logger.call_count >= 2
                assert mock_logger.info.call_count >= 2

        ctx.run(test_in_context)

    def test_correlation_id_propagation(self) -> None:
        ctx = copy_context()

        def test_in_context() -> None:
            test_id = "propagation - test - 123"
            set_correlation_id(test_id)

            event1 = add_correlation_id(None, None, {"event": "first"})
            event2 = add_correlation_id(None, None, {"event": "second"})
            current_id = get_correlation_id()

            assert event1["correlation_id"] == test_id
            assert event2["correlation_id"] == test_id
            assert current_id == test_id

        ctx.run(test_in_context)

    def test_logging_with_file_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            setup_structured_logging(level="DEBUG", json_output=True, log_file=log_file)

            logger = get_logger("integration.test")

            assert logger is not None
