"""Unit tests for security logger helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path, PurePosixPath
from unittest.mock import MagicMock, patch

import pytest

import crackerjack.services.security_logger as security_logger_module
from crackerjack.services.security_logger import (
    SecurityEvent,
    SecurityEventLevel,
    SecurityEventType,
    SecurityLogger,
    get_security_logger,
)


@pytest.fixture
def fake_logger() -> MagicMock:
    logger = MagicMock()
    logger.handlers = []
    return logger


def test_security_event_to_dict_serializes_nested_paths() -> None:
    event = SecurityEvent(
        timestamp=123.4,
        event_type=SecurityEventType.BACKUP_CREATED,
        level=SecurityEventLevel.INFO,
        message="backup created",
        file_path="/tmp/original.txt",
        user_id="user-1",
        session_id="session-1",
        additional_data={
            "path": Path("/tmp/example.txt"),
            "nested": {"inner": PurePosixPath("/tmp/inner.txt")},
            "items": [PurePosixPath("/tmp/one"), "plain"],
        },
    )

    data = event.to_dict()

    assert data["event_type"] == "backup_created"
    assert data["level"] == "info"
    assert data["additional_data"]["path"] == "/tmp/example.txt"
    assert data["additional_data"]["nested"]["inner"] == "/tmp/inner.txt"
    assert data["additional_data"]["items"] == ["/tmp/one", "plain"]


def test_security_logger_setup_with_debug_enabled(fake_logger: MagicMock) -> None:
    rich_handler = MagicMock()

    with patch(
        "crackerjack.services.security_logger.logging.getLogger",
        return_value=fake_logger,
    ), patch(
        "crackerjack.services.security_logger.Console",
    ) as mock_console, patch(
        "crackerjack.services.security_logger.RichHandler",
        return_value=rich_handler,
    ), patch.dict("os.environ", {"CRACKERJACK_DEBUG": "1"}, clear=False):
        logger = SecurityLogger("crackerjack.test.security")

    assert logger.logger is fake_logger
    fake_logger.setLevel.assert_called_with(logging.DEBUG)
    rich_handler.setLevel.assert_called_with(logging.DEBUG)
    fake_logger.addHandler.assert_called_once_with(rich_handler)
    mock_console.assert_called_once()


def test_security_logger_setup_without_adding_duplicate_handler(fake_logger: MagicMock) -> None:
    fake_logger.handlers = [MagicMock()]

    with patch(
        "crackerjack.services.security_logger.logging.getLogger",
        return_value=fake_logger,
    ), patch(
        "crackerjack.services.security_logger.Console",
    ) as mock_console, patch(
        "crackerjack.services.security_logger.RichHandler",
    ) as mock_handler, patch.dict("os.environ", {"CRACKERJACK_DEBUG": "0"}, clear=False):
        SecurityLogger("crackerjack.test.security")

    fake_logger.addHandler.assert_not_called()
    mock_console.assert_not_called()
    mock_handler.assert_not_called()


def test_log_security_event_and_helpers(fake_logger: MagicMock) -> None:
    with patch(
        "crackerjack.services.security_logger.logging.getLogger",
        return_value=fake_logger,
    ), patch(
        "crackerjack.services.security_logger.Console",
    ), patch(
        "crackerjack.services.security_logger.RichHandler",
    ), patch.dict("os.environ", {"CRACKERJACK_DEBUG": "0"}, clear=False):
        logger = SecurityLogger("crackerjack.test.security")

    logger.logger = fake_logger
    fake_logger.reset_mock()

    with patch("crackerjack.services.security_logger.time.time", return_value=100.0):
        logger.log_security_event(
            SecurityEventType.AUTH_SUCCESS,
            SecurityEventLevel.INFO,
            "ok",
            file_path=Path("/tmp/file.txt"),
            client_id="client-1",
        )

    fake_logger.log.assert_called_once()
    level, payload = fake_logger.log.call_args.args[:2]
    assert level == logging.INFO
    event_data = json.loads(payload)
    assert event_data["event_type"] == "auth_success"
    assert event_data["file_path"] == "/tmp/file.txt"
    assert event_data["additional_data"]["client_id"] == "client-1"

    fake_logger.reset_mock()
    logger.log_path_traversal_attempt(Path("/tmp/evil"), base_directory="/tmp")
    logger.log_file_size_exceeded("/tmp/file", 10, 5)
    logger.log_dangerous_path_detected("/tmp/danger", "node_modules")
    logger.log_backup_created("/tmp/original", "/tmp/backup")
    logger.log_file_cleaned("/tmp/clean", ["step-1", "step-2"])
    logger.log_atomic_operation("write", "/tmp/file", True)
    logger.log_atomic_operation("delete", "/tmp/file", False)
    logger.log_validation_failed("path", "/tmp/file", "bad path")
    logger.log_temp_file_created("/tmp/temp", "upload")
    logger.log_rate_limit_exceeded("client", 4, 3)
    logger.log_subprocess_execution(["git", "status", "--short", "extra"], cwd="/tmp", env_vars_count=2)
    logger.log_subprocess_environment_sanitized(10, 5, ["LD_PRELOAD", "PYTHONPATH"])
    logger.log_subprocess_command_validation(["git", "status", "--short"], True, ["none"])
    logger.log_subprocess_command_validation(["git", "status", "--short"], False, ["blocked"])
    logger.log_subprocess_timeout(["python", "-m", "pytest"], 3.0, 5.5)
    logger.log_subprocess_failure(["python", "-m", "pytest"], 1, "failed" * 100)
    logger.log_dangerous_command_blocked(["rm", "-rf", "/"], "blocked", ["rm"])
    logger.log_environment_variable_filtered("LD_PRELOAD", "dangerous", "x" * 100)
    logger.log_status_access_attempt("/status", "full", user_context="user-1", data_keys=["a", "b"])
    logger.log_sensitive_data_sanitized("token", 2, "low", ["token"])
    logger.log_status_information_disclosure("trace", "secret-value", "/status", severity="critical")
    logger.log_status_information_disclosure("trace", "secret-value", "/status", severity="unexpected")

    assert fake_logger.log.call_count >= 18


def test_get_security_logger_singleton(fake_logger: MagicMock) -> None:
    with patch(
        "crackerjack.services.security_logger.logging.getLogger",
        return_value=fake_logger,
    ), patch(
        "crackerjack.services.security_logger.Console",
    ), patch(
        "crackerjack.services.security_logger.RichHandler",
    ), patch.dict("os.environ", {"CRACKERJACK_DEBUG": "0"}, clear=False):
        security_logger_module._security_logger = None
        first = get_security_logger()
        second = get_security_logger()

    assert first is second


def _make_logger(caplog: pytest.LogCaptureFixture) -> SecurityLogger:
    """Build a SecurityLogger with real handlers suppressed and DEBUG level.

    Patches `SecurityLogger._setup_security_logger` so we exercise the
    *call sites* of `log_*` methods without instantiating RichHandler/Console.
    ``caplog`` captures records because the patched-out logger has no
    handlers and therefore still propagates to the root logger that caplog
    manages.
    """
    caplog.set_level(logging.DEBUG, logger="crackerjack.security.test")
    with patch.object(SecurityLogger, "_setup_security_logger"):
        logger = SecurityLogger("crackerjack.security.test")
    logger.logger.setLevel(logging.DEBUG)
    logger.logger.propagate = True
    return logger


def _last_event(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    """Return the parsed JSON payload of the most recent log record."""
    return json.loads(caplog.records[-1].getMessage())


# ---------------------------------------------------------------------------
# SecurityEvent model coverage
# ---------------------------------------------------------------------------


def test_security_event_to_dict_with_defaults() -> None:
    event = SecurityEvent(
        timestamp=1.0,
        event_type=SecurityEventType.AUTH_SUCCESS,
        level=SecurityEventLevel.INFO,
        message="ok",
    )

    data = event.to_dict()

    assert data == {
        "timestamp": 1.0,
        "event_type": "auth_success",
        "level": "info",
        "message": "ok",
        "file_path": None,
        "user_id": None,
        "session_id": None,
        "additional_data": {},
    }


def test_security_event_to_dict_with_plain_scalars_in_additional_data() -> None:
    event = SecurityEvent(
        timestamp=2.0,
        event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
        level=SecurityEventLevel.HIGH,
        message="limit",
        file_path="/tmp/x",
        user_id="u",
        session_id="s",
        additional_data={"count": 5, "ratio": 0.5, "flag": True},
    )

    data = event.to_dict()

    assert data["additional_data"] == {"count": 5, "ratio": 0.5, "flag": True}


def test_security_event_to_dict_serializes_deeply_nested_paths() -> None:
    event = SecurityEvent(
        timestamp=3.0,
        event_type=SecurityEventType.FILE_CLEANED,
        level=SecurityEventLevel.LOW,
        message="ok",
        additional_data={
            "outer": {
                "middle": {
                    "deep": PurePosixPath("/tmp/deep.txt"),
                },
                "list": [PurePosixPath("/a"), {"nested": PurePosixPath("/b")}],
            },
            "scalar": 42,
        },
    )

    data = event.to_dict()
    nested = data["additional_data"]
    assert nested["outer"]["middle"]["deep"] == "/tmp/deep.txt"
    assert nested["outer"]["list"] == ["/a", {"nested": "/b"}]
    assert nested["scalar"] == 42


def test_security_event_to_dict_keeps_non_path_values_unchanged() -> None:
    event = SecurityEvent(
        timestamp=4.0,
        event_type=SecurityEventType.BACKUP_CREATED,
        level=SecurityEventLevel.LOW,
        message="ok",
        additional_data={"note": "plain string", "items": (1, 2, 3)},
    )

    data = event.to_dict()

    assert data["additional_data"]["note"] == "plain string"
    assert data["additional_data"]["items"] == (1, 2, 3)


# ---------------------------------------------------------------------------
# SecurityLogger.__init__ / _setup_security_logger coverage
# ---------------------------------------------------------------------------


def test_security_logger_init_uses_default_logger_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch.object(SecurityLogger, "_setup_security_logger") as mock_setup, patch(
        "crackerjack.services.security_logger.logging.getLogger"
    ) as mock_get_logger:
        SecurityLogger()

    mock_get_logger.assert_called_once_with("crackerjack.security")
    mock_setup.assert_called_once_with()


def test_security_logger_init_uses_custom_logger_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch.object(SecurityLogger, "_setup_security_logger"), patch(
        "crackerjack.services.security_logger.logging.getLogger"
    ) as mock_get_logger:
        SecurityLogger("custom.security.logger")

    mock_get_logger.assert_called_once_with("custom.security.logger")


def test_setup_security_logger_with_debug_env_var_sets_debug_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_logger = MagicMock()
    fake_logger.handlers = []
    rich_handler = MagicMock()

    with patch(
        "crackerjack.services.security_logger.logging.getLogger",
        return_value=fake_logger,
    ), patch(
        "crackerjack.services.security_logger.Console",
    ) as mock_console, patch(
        "crackerjack.services.security_logger.RichHandler",
        return_value=rich_handler,
    ), patch.dict(
        "os.environ", {"CRACKERJACK_DEBUG": "1"}, clear=False
    ):
        SecurityLogger("crackerjack.security.debug")

    fake_logger.setLevel.assert_called_with(logging.DEBUG)
    rich_handler.setLevel.assert_called_with(logging.DEBUG)
    fake_logger.addHandler.assert_called_once_with(rich_handler)
    mock_console.assert_called_once()
    rich_handler.setFormatter.assert_called_once()
    assert isinstance(rich_handler.setFormatter.call_args.args[0], logging.Formatter)


def test_setup_security_logger_without_debug_env_var_uses_silent_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_logger = MagicMock()
    fake_logger.handlers = []
    rich_handler = MagicMock()
    silent_level = logging.CRITICAL + 10

    with patch(
        "crackerjack.services.security_logger.logging.getLogger",
        return_value=fake_logger,
    ), patch(
        "crackerjack.services.security_logger.Console",
    ), patch(
        "crackerjack.services.security_logger.RichHandler",
        return_value=rich_handler,
    ), patch.dict(
        "os.environ", {}, clear=True
    ):
        SecurityLogger("crackerjack.security.silent")

    fake_logger.setLevel.assert_called_with(silent_level)
    rich_handler.setLevel.assert_called_with(silent_level)
    fake_logger.addHandler.assert_called_once_with(rich_handler)


def test_setup_security_logger_skips_handler_when_already_present(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_logger = MagicMock()
    fake_logger.handlers = [MagicMock()]

    with patch(
        "crackerjack.services.security_logger.logging.getLogger",
        return_value=fake_logger,
    ), patch(
        "crackerjack.services.security_logger.Console"
    ) as mock_console, patch(
        "crackerjack.services.security_logger.RichHandler"
    ) as mock_handler:
        SecurityLogger("crackerjack.security.skip")

    fake_logger.addHandler.assert_not_called()
    mock_console.assert_not_called()
    mock_handler.assert_not_called()


# ---------------------------------------------------------------------------
# log_security_event + _get_logging_level coverage
# ---------------------------------------------------------------------------


def test_log_security_event_with_path_object(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    with patch("crackerjack.services.security_logger.time.time", return_value=10.0):
        logger.log_security_event(
            SecurityEventType.AUTH_SUCCESS,
            SecurityEventLevel.INFO,
            "ok",
            file_path=Path("/var/data/file.txt"),
        )

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    assert record.security_event is True  # type: ignore[attr-defined]
    assert record.getMessage().startswith("{")
    payload = _last_event(caplog)
    assert payload["timestamp"] == 10.0
    assert payload["file_path"] == "/var/data/file.txt"


def test_log_security_event_with_none_file_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_security_event(
        SecurityEventType.OPERATION_SUCCESS,
        SecurityEventLevel.LOW,
        "no path",
    )

    payload = _last_event(caplog)
    assert payload["file_path"] is None
    assert payload["additional_data"] == {}


def test_log_security_event_includes_user_id_and_session_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_security_event(
        SecurityEventType.AUTH_FAILURE,
        SecurityEventLevel.WARNING,
        "denied",
        user_id="user-42",
        session_id="sess-1",
    )

    payload = _last_event(caplog)
    assert payload["user_id"] == "user-42"
    assert payload["session_id"] == "sess-1"


def test_get_logging_level_maps_every_security_level() -> None:
    logger = SecurityLogger.__new__(SecurityLogger)
    logger.logger = logging.getLogger("crackerjack.security.level_map")

    assert logger._get_logging_level(SecurityEventLevel.LOW) == logging.DEBUG
    assert logger._get_logging_level(SecurityEventLevel.MEDIUM) == logging.INFO
    assert logger._get_logging_level(SecurityEventLevel.HIGH) == logging.WARNING
    assert logger._get_logging_level(SecurityEventLevel.CRITICAL) == logging.CRITICAL
    assert logger._get_logging_level(SecurityEventLevel.INFO) == logging.INFO
    assert logger._get_logging_level(SecurityEventLevel.WARNING) == logging.WARNING
    assert logger._get_logging_level(SecurityEventLevel.ERROR) == logging.ERROR


# ---------------------------------------------------------------------------
# log_* method payload coverage
# ---------------------------------------------------------------------------


def test_log_path_traversal_attempt_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_path_traversal_attempt(
        Path("/tmp/../etc/passwd"),
        base_directory="/tmp/safe",
        user_id="attacker",
    )

    record = caplog.records[-1]
    assert record.levelno == logging.CRITICAL
    payload = _last_event(caplog)
    assert payload["event_type"] == "path_traversal_attempt"
    assert payload["level"] == "critical"
    assert payload["file_path"] == "/tmp/../etc/passwd"
    assert payload["user_id"] == "attacker"
    assert "Path traversal attempt detected" in payload["message"]
    assert payload["additional_data"]["base_directory"] == "/tmp/safe"


def test_log_path_traversal_attempt_without_base_directory(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_path_traversal_attempt("/tmp/evil")

    payload = _last_event(caplog)
    assert payload["additional_data"]["base_directory"] is None


def test_log_file_size_exceeded_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_file_size_exceeded("/var/log/big.log", 1_000_000, 500_000)

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    payload = _last_event(caplog)
    assert payload["event_type"] == "file_size_exceeded"
    assert payload["level"] == "high"
    assert payload["file_path"] == "/var/log/big.log"
    assert payload["additional_data"]["file_size"] == 1_000_000
    assert payload["additional_data"]["max_size"] == 500_000


def test_log_dangerous_path_detected_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_dangerous_path_detected("/proj/node_modules", "node_modules")

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    payload = _last_event(caplog)
    assert payload["event_type"] == "dangerous_path_detected"
    assert payload["additional_data"]["dangerous_component"] == "node_modules"


def test_log_backup_created_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_backup_created("/tmp/original.txt", "/tmp/backup.txt")

    record = caplog.records[-1]
    assert record.levelno == logging.DEBUG
    payload = _last_event(caplog)
    assert payload["event_type"] == "backup_created"
    assert payload["level"] == "low"
    assert payload["file_path"] == "/tmp/original.txt"
    assert payload["additional_data"]["backup_path"] == "/tmp/backup.txt"


def test_log_file_cleaned_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_file_cleaned("/tmp/file", ["step-1", "step-2"])

    record = caplog.records[-1]
    assert record.levelno == logging.DEBUG
    payload = _last_event(caplog)
    assert payload["event_type"] == "file_cleaned"
    assert payload["additional_data"]["steps_completed"] == ["step-1", "step-2"]


def test_log_atomic_operation_success_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_atomic_operation("write", "/tmp/file", True)

    record = caplog.records[-1]
    assert record.levelno == logging.DEBUG
    payload = _last_event(caplog)
    assert payload["level"] == "low"
    assert payload["additional_data"]["operation"] == "write"
    assert payload["additional_data"]["success"] is True
    assert "successful" in payload["message"]


def test_log_atomic_operation_failure_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_atomic_operation("delete", "/tmp/file", False)

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    payload = _last_event(caplog)
    assert payload["level"] == "medium"
    assert payload["additional_data"]["success"] is False
    assert "failed" in payload["message"]


def test_log_validation_failed_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_validation_failed("schema", "/tmp/file.xml", "missing field")

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    payload = _last_event(caplog)
    assert payload["event_type"] == "validation_failed"
    assert payload["additional_data"]["validation_type"] == "schema"
    assert payload["additional_data"]["reason"] == "missing field"


def test_log_temp_file_created_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_temp_file_created("/tmp/upload-1234.tmp", "upload")

    record = caplog.records[-1]
    assert record.levelno == logging.DEBUG
    payload = _last_event(caplog)
    assert payload["event_type"] == "temp_file_created"
    assert payload["additional_data"]["purpose"] == "upload"


def test_log_rate_limit_exceeded_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_rate_limit_exceeded("client", 6, 5)

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    payload = _last_event(caplog)
    assert payload["event_type"] == "rate_limit_exceeded"
    assert payload["additional_data"]["limit_type"] == "client"
    assert payload["additional_data"]["current_count"] == 6
    assert payload["additional_data"]["max_allowed"] == 5


def test_log_subprocess_execution_truncates_long_command(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_subprocess_execution(
        ["git", "status", "--short", "--branch", "more"],
        cwd="/tmp",
        env_vars_count=2,
    )

    payload = _last_event(caplog)
    assert payload["event_type"] == "subprocess_execution"
    assert payload["level"] == "low"
    assert payload["additional_data"]["cwd"] == "/tmp"
    assert payload["additional_data"]["env_vars_count"] == 2
    # Truncated to first 10 entries; original has 5 so all preserved.
    assert payload["additional_data"]["command"] == [
        "git",
        "status",
        "--short",
        "--branch",
        "more",
    ]


def test_log_subprocess_environment_sanitized_truncates_filtered_vars(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    long_filtered = [f"VAR_{i}" for i in range(50)]
    logger.log_subprocess_environment_sanitized(60, 10, long_filtered)

    payload = _last_event(caplog)
    assert payload["event_type"] == "subprocess_environment_sanitized"
    assert payload["additional_data"]["original_count"] == 60
    assert payload["additional_data"]["sanitized_count"] == 10
    assert len(payload["additional_data"]["filtered_vars"]) == 20
    assert payload["additional_data"]["filtered_vars"][0] == "VAR_0"


def test_log_subprocess_command_validation_passed_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_subprocess_command_validation(["git", "status"], True, [])

    record = caplog.records[-1]
    assert record.levelno == logging.DEBUG
    payload = _last_event(caplog)
    assert payload["level"] == "low"
    assert payload["additional_data"]["validation_result"] is True
    assert payload["additional_data"]["issues"] == []
    assert "passed" in payload["message"]


def test_log_subprocess_command_validation_failed_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_subprocess_command_validation(
        ["git", "status", "--short"],
        False,
        ["blocked-pattern"],
    )

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    payload = _last_event(caplog)
    assert payload["level"] == "high"
    assert payload["additional_data"]["validation_result"] is False
    assert payload["additional_data"]["issues"] == ["blocked-pattern"]
    assert "failed" in payload["message"]


def test_log_subprocess_command_validation_with_default_issues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_subprocess_command_validation(["git", "status"], True)

    payload = _last_event(caplog)
    assert payload["additional_data"]["issues"] is None


def test_log_subprocess_timeout_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_subprocess_timeout(["pytest", "--long"], 5.0, 7.5)

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    payload = _last_event(caplog)
    assert payload["event_type"] == "subprocess_timeout"
    assert payload["additional_data"]["timeout_seconds"] == 5.0
    assert payload["additional_data"]["actual_duration"] == 7.5


def test_log_subprocess_failure_truncates_error_preview(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    long_error = "X" * 500
    logger.log_subprocess_failure(["pytest"], 1, long_error)

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    payload = _last_event(caplog)
    assert payload["event_type"] == "subprocess_failure"
    assert payload["additional_data"]["exit_code"] == 1
    assert len(payload["additional_data"]["error_preview"]) == 200


def test_log_dangerous_command_blocked_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_dangerous_command_blocked(
        ["rm", "-rf", "/"],
        "rm -rf blocked",
        ["rm -rf"],
    )

    record = caplog.records[-1]
    assert record.levelno == logging.CRITICAL
    payload = _last_event(caplog)
    assert payload["event_type"] == "dangerous_command_blocked"
    assert payload["additional_data"]["reason"] == "rm -rf blocked"
    assert payload["additional_data"]["dangerous_patterns"] == ["rm -rf"]


def test_log_environment_variable_filtered_truncates_value_preview(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_environment_variable_filtered(
        "SECRET",
        "looks like a credential",
        "x" * 200,
    )

    record = caplog.records[-1]
    assert record.levelno == logging.DEBUG
    payload = _last_event(caplog)
    assert payload["event_type"] == "environment_variable_filtered"
    assert payload["additional_data"]["variable_name"] == "SECRET"
    assert len(payload["additional_data"]["value_preview"]) == 50


def test_log_environment_variable_filtered_with_none_value_preview(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_environment_variable_filtered("SECRET", "sensitive")

    payload = _last_event(caplog)
    assert payload["additional_data"]["value_preview"] is None


def test_log_status_access_attempt_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_status_access_attempt(
        "/api/status",
        "full",
        user_context="user-1",
        data_keys=["cpu", "mem"],
    )

    record = caplog.records[-1]
    assert record.levelno == logging.DEBUG
    payload = _last_event(caplog)
    assert payload["event_type"] == "status_access_attempt"
    assert payload["user_id"] == "user-1"
    assert payload["additional_data"]["endpoint"] == "/api/status"
    assert payload["additional_data"]["verbosity_level"] == "full"
    assert payload["additional_data"]["data_keys"] == ["cpu", "mem"]


def test_log_status_access_attempt_defaults_data_keys(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_status_access_attempt("/api/status", "low")

    payload = _last_event(caplog)
    assert payload["additional_data"]["data_keys"] == []


def test_log_sensitive_data_sanitized_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_sensitive_data_sanitized("token", 7, "medium", ["regex-1", "regex-2"])

    record = caplog.records[-1]
    assert record.levelno == logging.DEBUG
    payload = _last_event(caplog)
    assert payload["event_type"] == "sensitive_data_sanitized"
    assert payload["additional_data"]["data_type"] == "token"
    assert payload["additional_data"]["sanitization_count"] == 7
    assert payload["additional_data"]["verbosity_level"] == "medium"
    assert payload["additional_data"]["patterns_matched"] == ["regex-1", "regex-2"]


def test_log_sensitive_data_sanitized_defaults_patterns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_sensitive_data_sanitized("token", 3, "low")

    payload = _last_event(caplog)
    assert payload["additional_data"]["patterns_matched"] == []


@pytest.mark.parametrize(
    "severity, expected_levelno",
    [
        ("low", logging.DEBUG),
        ("medium", logging.INFO),
        ("high", logging.WARNING),
        ("critical", logging.CRITICAL),
        ("unknown", logging.INFO),
    ],
)
def test_log_status_information_disclosure_severity_mapping(
    caplog: pytest.LogCaptureFixture,
    severity: str,
    expected_levelno: int,
) -> None:
    logger = _make_logger(caplog)

    logger.log_status_information_disclosure(
        "stacktrace",
        "secret-value",
        "/status",
        severity=severity,
    )

    record = caplog.records[-1]
    assert record.levelno == expected_levelno
    payload = _last_event(caplog)
    assert payload["event_type"] == "status_information_disclosure"
    assert payload["additional_data"]["disclosure_type"] == "stacktrace"
    assert payload["additional_data"]["severity"] == severity
    assert payload["additional_data"]["endpoint"] == "/status"
    assert payload["additional_data"]["sensitive_info_preview"] == "secret-value"


def test_log_status_information_disclosure_truncates_sensitive_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = _make_logger(caplog)

    logger.log_status_information_disclosure(
        "stacktrace",
        "Z" * 300,
        "/status",
    )

    payload = _last_event(caplog)
    assert len(payload["additional_data"]["sensitive_info_preview"]) == 100


# ---------------------------------------------------------------------------
# get_security_logger coverage (singleton initialization branch)
# ---------------------------------------------------------------------------


def test_get_security_logger_initializes_singleton_when_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch.object(SecurityLogger, "_setup_security_logger") as mock_setup, patch(
        "crackerjack.services.security_logger.logging.getLogger"
    ) as mock_get_logger:
        security_logger_module._security_logger = None
        instance = get_security_logger()

    assert isinstance(instance, SecurityLogger)
    mock_get_logger.assert_called_once_with("crackerjack.security")
    mock_setup.assert_called_once_with()


def test_get_security_logger_returns_existing_singleton(
    caplog: pytest.LogCaptureFixture,
) -> None:
    existing = SecurityLogger("pre-existing")
    security_logger_module._security_logger = existing

    with patch.object(SecurityLogger, "_setup_security_logger") as mock_setup, patch(
        "crackerjack.services.security_logger.logging.getLogger"
    ) as mock_get_logger:
        instance = get_security_logger()

    assert instance is existing
    mock_get_logger.assert_not_called()
    mock_setup.assert_not_called()
