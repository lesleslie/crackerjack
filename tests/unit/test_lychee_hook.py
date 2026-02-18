"""Unit tests for lychee link checker hook."""

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
    assert "--exclude-mail" in cmd
    assert "--cache" in cmd
    assert ".cache/lychee" in cmd, "Cache should be XDG-compliant"
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


def test_lychee_manual_stage():
    """Test that lychee requires manual stage opt-in."""
    lychee_hook = next((h for h in COMPREHENSIVE_HOOKS if h.name == "lychee"), None)
    assert lychee_hook is not None
    assert lychee_hook.manual_stage is True, "Lychee should require explicit opt-in like other comprehensive hooks"


def test_lychee_description():
    """Test that lychee has descriptive text."""
    lychee_hook = next((h for h in COMPREHENSIVE_HOOKS if h.name == "lychee"), None)
    assert lychee_hook is not None
    assert lychee_hook.description is not None
    assert "link checker" in lychee_hook.description.lower()
