"""Tests for the log manager."""

from crackerjack.services.log_manager import LogManager


def test_log_manager_prefers_project_local_logs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    log_manager = LogManager()

    assert log_manager.log_dir == tmp_path / ".crackerjack" / "logs"
    assert log_manager.debug_dir.exists()
    assert log_manager.error_dir.exists()
    assert log_manager.audit_dir.exists()


def test_create_debug_log_file_sanitizes_session_id(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    log_manager = LogManager()
    debug_log = log_manager.create_debug_log_file("ai-agent -debug 1776381655")

    assert debug_log.parent == log_manager.debug_dir
    assert debug_log.name.startswith("debug-")
    assert " " not in debug_log.name
    assert debug_log.suffix == ".log"
