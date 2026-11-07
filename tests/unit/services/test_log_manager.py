"""Tests for the log manager."""

from crackerjack.services.log_manager import LogManager


def test_log_manager_prefers_the_xdg_state_home(tmp_path, monkeypatch) -> None:
    """Logs live under XDG state, not in the project tree.

    The project-local directory is gitignored, so `git clean -fd`
    destroyed the logs. The decision record puts them under
    `$XDG_STATE_HOME/crackerjack/logs`.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    log_manager = LogManager()

    assert log_manager.log_dir == tmp_path / "state" / "crackerjack" / "logs"
    assert log_manager.debug_dir.exists()
    assert log_manager.error_dir.exists()
    assert log_manager.audit_dir.exists()


def test_log_manager_falls_back_to_the_project_local_logs(
    tmp_path, monkeypatch
) -> None:
    """A checkout that cannot write to the state directory still logs."""
    monkeypatch.chdir(tmp_path)
    unwritable = tmp_path / "state"
    unwritable.mkdir()
    unwritable.chmod(0o500)
    monkeypatch.setenv("XDG_STATE_HOME", str(unwritable))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    try:
        log_manager = LogManager()
    finally:
        unwritable.chmod(0o700)

    assert log_manager.log_dir == tmp_path / ".crackerjack" / "logs"


def test_create_debug_log_file_sanitizes_session_id(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    log_manager = LogManager()
    debug_log = log_manager.create_debug_log_file("ai-agent -debug 1776381655")

    assert debug_log.parent == log_manager.debug_dir
    assert debug_log.name.startswith("debug-")
    assert " " not in debug_log.name
    assert debug_log.suffix == ".log"
