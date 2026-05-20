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
