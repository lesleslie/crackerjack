"""Unit tests for lychee link checker hook."""

import json
from unittest.mock import MagicMock

import pytest

from crackerjack.config.hooks import HookConfigLoader, HookStage, COMPREHENSIVE_HOOKS


def test_lychee_hook_exists():
    """Test that lychee hook is registered."""
    strategy = HookConfigLoader.load_strategy("comprehensive")
    hook_names = [h.name for h in strategy.hooks]
    assert "lychee" in hook_names


def test_lychee_hook_is_comprehensive():
    """Test that lychee is in comprehensive stage."""
    strategy = HookConfigLoader.load_strategy("comprehensive")
    lychee_hook = next((h for h in strategy.hooks if h.name == "lychee"), None)
    assert lychee_hook is not None
    assert lychee_hook.stage == HookStage.COMPREHENSIVE


def test_lychee_command_structure():
    """Test that lychee command is properly structured."""
    from crackerjack.config.tool_commands import get_tool_command

    cmd = get_tool_command("lychee")

    assert "lychee" in cmd
    assert "--no-progress" in cmd
    assert "--cache" in cmd
    assert "--verbose" in cmd
    assert "." in cmd


def test_lychee_runs_with_comprehensive_hooks():
    """Test that lychee runs when using -c flag."""
    import subprocess
    from crackerjack.__main__ import app
    from typer.testing import CliRunner

    runner = CliRunner()
    # Test with short flag
    result = runner.invoke(app, ["run", "-c", "--help"])
    assert result.exit_code == 0
    # Test with long flag
    result = runner.invoke(app, ["run", "--comp", "--help"])
    assert result.exit_code == 0


def test_lychee_timeout_sufficient_for_network_ops():
    """Test that lychee timeout accounts for network I/O."""
    lychee_hook = next((h for h in COMPREHENSIVE_HOOKS if h.name == "lychee"), None)
    assert lychee_hook is not None
    assert lychee_hook.timeout >= 300, "Network operations need at least 5 minutes"


def test_lychee_accepts_no_file_paths():
    """Test that lychee scans entire directory, not specific files."""
    lychee_hook = next((h for h in COMPREHENSIVE_HOOKS if h.name == "lychee"), None)
    assert lychee_hook is not None
    assert lychee_hook.accepts_file_paths is False, "Lychee scans entire directory recursively"


def test_lychee_security_level():
    """Test that lychee has LOW security level (documentation quality)."""
    from crackerjack.config.hooks import SecurityLevel

    lychee_hook = next((h for h in COMPREHENSIVE_HOOKS if h.name == "lychee"), None)
    assert lychee_hook is not None
    assert lychee_hook.security_level == SecurityLevel.LOW


def test_lychee_auto_run():
    """Test that lychee is part of the default comprehensive stage.

    All comp hooks except opt-in type checkers (pyrefly) auto-run.
    """
    lychee_hook = next((h for h in COMPREHENSIVE_HOOKS if h.name == "lychee"), None)
    assert lychee_hook is not None
    assert lychee_hook.auto_run is True, "Lychee is a default comp hook"


def test_lychee_description():
    """Test that lychee has descriptive text."""
    lychee_hook = next((h for h in COMPREHENSIVE_HOOKS if h.name == "lychee"), None)
    assert lychee_hook is not None
    assert lychee_hook.description is not None
    assert "link checker" in lychee_hook.description.lower()


class TestParseLycheeIssues:
    """Pin the JSON issue parser so timeouts and unknown URLs surface as issues.

    Regression: lychee exits code 2 when ANY URL check fails, but the top-level
    `errors` counter only sums `error_map` entries. Timeouts (and unknown URLs)
    were silently dropped, leaving the user with 0 issues to act on.
    """

    def test_returns_timeouts_when_no_errors(self) -> None:
        """Timeouts must surface even when `errors` is 0."""
        from crackerjack.executors.hook_executor import HookExecutor

        executor = HookExecutor.__new__(HookExecutor)
        executor.console = MagicMock()

        output = json.dumps({
            "errors": 0,
            "timeouts": 1,
            "error_map": {},
            "timeout_map": {
                "./docs/example.md": [{
                    "url": "https://example.com/slow.pdf",
                    "status": {"text": "Timeout"},
                    "span": {"line": 42, "column": 1},
                }],
            },
        })

        issues = executor._parse_lychee_issues(output)

        assert len(issues) == 1
        assert "example.com/slow.pdf" in issues[0]
        assert ":42:" in issues[0]
        assert "Timeout" in issues[0]

    def test_returns_errors_normally(self) -> None:
        """The original error_map path still works."""
        from crackerjack.executors.hook_executor import HookExecutor

        executor = HookExecutor.__new__(HookExecutor)
        executor.console = MagicMock()

        output = json.dumps({
            "errors": 1,
            "error_map": {
                "./README.md": [{
                    "url": "https://broken.example.com",
                    "status": {"text": "404 Not Found"},
                    "span": {"line": 10, "column": 5},
                }],
            },
        })

        issues = executor._parse_lychee_issues(output)

        assert len(issues) == 1
        assert "broken.example.com" in issues[0]
        assert "404" in issues[0]

    def test_handles_string_status(self) -> None:
        """Lychee sometimes returns status as a plain string, not a dict."""
        from crackerjack.executors.hook_executor import HookExecutor

        executor = HookExecutor.__new__(HookExecutor)
        executor.console = MagicMock()

        output = json.dumps({
            "errors": 1,
            "error_map": {
                "./file.md": [{
                    "url": "https://x.example",
                    "status": "Connection refused",
                    "span": {"line": 7},
                }],
            },
        })

        issues = executor._parse_lychee_issues(output)

        assert "Connection refused" in issues[0]

    def test_empty_output_returns_empty_list(self) -> None:
        """No failures → no issues (legitimately passing case)."""
        from crackerjack.executors.hook_executor import HookExecutor

        executor = HookExecutor.__new__(HookExecutor)
        executor.console = MagicMock()

        output = json.dumps({
            "errors": 0,
            "timeouts": 0,
            "error_map": {},
            "timeout_map": {},
        })

        assert executor._parse_lychee_issues(output) == []

    def test_invalid_json_returns_empty_list(self) -> None:
        """Unparsable JSON shouldn't crash the parser."""
        from crackerjack.executors.hook_executor import HookExecutor

        executor = HookExecutor.__new__(HookExecutor)
        executor.console = MagicMock()

        assert executor._parse_lychee_issues("not json at all") == []

    def test_counter_present_but_map_empty(self) -> None:
        """Defensive: if `timeouts > 0` but the map is empty, still report it."""
        from crackerjack.executors.hook_executor import HookExecutor

        executor = HookExecutor.__new__(HookExecutor)
        executor.console = MagicMock()

        output = json.dumps({
            "errors": 0,
            "timeouts": 3,
            "error_map": {},
            "timeout_map": {},
        })

        issues = executor._parse_lychee_issues(output)

        assert len(issues) == 1
        assert "3 timeouts" in issues[0]
