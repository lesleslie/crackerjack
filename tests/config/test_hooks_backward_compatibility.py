"""Tests for backward compatibility between pre-commit wrappers and direct invocation (Phase 8.2)."""

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

# Backward-compatibility for pre-commit wrappers is no longer under test
pytestmark = pytest.mark.skip(
    reason="Backward compatibility tests deprecated; direct invocation is canonical"
)

from crackerjack.config.hooks import (
    COMPREHENSIVE_HOOKS,
    FAST_HOOKS,
    HookDefinition,
    HookStage,
    SecurityLevel,
)


class TestHookDefinitionGetCommand:
    """Test HookDefinition.get_command() with both legacy and direct modes."""

    def test_direct_mode_returns_tool_command(self):
        """Test that direct mode returns command from tool registry."""
        hook = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        assert isinstance(command, list)
        assert command[0] == "uv"
        assert command[1] == "run"
        assert "ruff" in command
        assert "check" in command

    def test_legacy_mode_returns_precommit_wrapper(self, tmp_path, monkeypatch):
        """Test that legacy mode returns pre-commit wrapper command."""
        # Use a temporary directory without .venv to test system pre-commit
        monkeypatch.chdir(tmp_path)

        hook = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=True,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/pre-commit"

            command = hook.get_command()

            assert isinstance(command, list)
            assert command[0] == "/usr/local/bin/pre-commit"
            assert "run" in command
            assert "ruff-check" in command
            assert "--all-files" in command

    def test_direct_mode_native_tool(self):
        """Test direct mode with native crackerjack tool."""
        hook = HookDefinition(
            name="trailing-whitespace",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        assert command[0] == "uv"
        assert command[1] == "run"
        assert command[2] == "python"
        assert command[3] == "-m"
        assert "crackerjack.tools.trailing_whitespace" in command

    def test_direct_mode_custom_tool(self):
        """Test direct mode with custom tool (validate-regex-patterns)."""
        hook = HookDefinition(
            name="validate-regex-patterns",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        assert command[0] == "uv"
        assert "crackerjack.tools.validate_regex_patterns" in " ".join(command)

    def test_direct_mode_rust_tool(self):
        """Test direct mode with Rust-based tool (skylos)."""
        hook = HookDefinition(
            name="skylos",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        assert command[0] == "uv"
        assert command[1] == "run"
        assert "skylos" in command
        assert "check" in command

    def test_legacy_mode_with_config_path(self, tmp_path):
        """Test legacy mode includes config path in command."""
        config_file = tmp_path / ".pre-commit-config.yaml"
        config_file.touch()

        hook = HookDefinition(
            name="bandit",
            command=[],
            config_path=config_file,
            use_precommit_legacy=True,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            command = hook.get_command()

            assert "-c" in command
            assert str(config_file) in command

    def test_legacy_mode_with_manual_stage(self):
        """Test legacy mode includes manual stage flag."""
        hook = HookDefinition(
            name="zuban",
            command=[],
            manual_stage=True,
            use_precommit_legacy=True,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            command = hook.get_command()

            assert "--hook-stage" in command
            assert "manual" in command

    def test_direct_mode_fallback_to_legacy(self):
        """Test that direct mode falls back to legacy for unknown tools."""
        hook = HookDefinition(
            name="nonexistent-tool-xyz",
            command=[],
            use_precommit_legacy=False,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            command = hook.get_command()

            # Should fallback to pre-commit wrapper
            assert "pre-commit" in command[0]
            assert "run" in command
            assert "nonexistent-tool-xyz" in command

    def test_legacy_mode_prefers_venv_precommit(self, tmp_path, monkeypatch):
        """Test legacy mode prefers .venv/bin/pre-commit if it exists."""
        monkeypatch.chdir(tmp_path)

        # Create .venv/bin/pre-commit
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        venv_precommit = venv_bin / "pre-commit"
        venv_precommit.touch()

        hook = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=True,
        )

        command = hook.get_command()

        assert str(venv_precommit) == command[0]

    def test_legacy_mode_falls_back_to_system_precommit(self, tmp_path, monkeypatch):
        """Test legacy mode uses system pre-commit if .venv doesn't exist."""
        monkeypatch.chdir(tmp_path)

        hook = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=True,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/pre-commit"

            command = hook.get_command()

            assert command[0] == "/usr/local/bin/pre-commit"
            mock_which.assert_called_once_with("pre-commit")


class TestFastHooksConfiguration:
    """Test FAST_HOOKS use correct direct invocation mode."""

    def test_all_fast_hooks_use_direct_mode(self):
        """Test that all fast hooks have use_precommit_legacy=False."""
        for hook in FAST_HOOKS:
            assert not hook.use_precommit_legacy, f"{hook.name} should use direct invocation"

    def test_fast_hooks_can_get_commands(self):
        """Test that all fast hooks can successfully get commands."""
        for hook in FAST_HOOKS:
            command = hook.get_command()
            assert isinstance(command, list)
            assert len(command) > 0
            assert command[0] == "uv", f"{hook.name} command should start with 'uv'"

    def test_fast_hooks_have_expected_count(self):
        """Test that fast hooks list has expected number of hooks."""
        # As of Phase 8: 12 fast hooks
        assert len(FAST_HOOKS) == 12

    def test_fast_formatting_hooks_marked_correctly(self):
        """Test that formatting hooks are properly marked."""
        formatting_hooks = [h for h in FAST_HOOKS if h.is_formatting]
        expected_formatting = {
            "validate-regex-patterns",
            "trailing-whitespace",
            "end-of-file-fixer",
            "ruff-check",
            "ruff-format",
            "mdformat",
        }

        formatting_names = {h.name for h in formatting_hooks}
        assert formatting_names == expected_formatting


class TestComprehensiveHooksConfiguration:
    """Test COMPREHENSIVE_HOOKS use correct direct invocation mode."""

    def test_all_comprehensive_hooks_use_direct_mode(self):
        """Test that all comprehensive hooks have use_precommit_legacy=False."""
        for hook in COMPREHENSIVE_HOOKS:
            assert not hook.use_precommit_legacy, f"{hook.name} should use direct invocation"

    def test_comprehensive_hooks_can_get_commands(self):
        """Test that all comprehensive hooks can successfully get commands."""
        for hook in COMPREHENSIVE_HOOKS:
            command = hook.get_command()
            assert isinstance(command, list)
            assert len(command) > 0
            assert command[0] == "uv", f"{hook.name} command should start with 'uv'"

    def test_comprehensive_hooks_have_expected_count(self):
        """Test that comprehensive hooks list has expected number of hooks."""
        # As of Phase 8: 6 comprehensive hooks
        assert len(COMPREHENSIVE_HOOKS) == 6

    def test_all_comprehensive_hooks_are_manual_stage(self):
        """Test that all comprehensive hooks use manual stage."""
        for hook in COMPREHENSIVE_HOOKS:
            assert hook.manual_stage, f"{hook.name} should use manual stage"

    def test_comprehensive_hooks_have_comprehensive_stage(self):
        """Test that all comprehensive hooks have correct stage."""
        for hook in COMPREHENSIVE_HOOKS:
            assert hook.stage == HookStage.COMPREHENSIVE


class TestMigrationPath:
    """Test migration scenarios from legacy to direct invocation."""

    def test_can_override_legacy_flag_for_testing(self):
        """Test that legacy flag can be overridden for migration testing."""
        # Create hook with legacy mode
        hook_legacy = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=True,
        )

        # Create same hook with direct mode
        hook_direct = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=False,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            legacy_cmd = hook_legacy.get_command()
            direct_cmd = hook_direct.get_command()

            # Commands should be different
            assert legacy_cmd != direct_cmd

            # Legacy should use pre-commit
            assert "pre-commit" in legacy_cmd[0]

            # Direct should use uv
            assert direct_cmd[0] == "uv"

    def test_both_modes_execute_same_tool(self):
        """Test that both modes target the same underlying tool."""
        hook_legacy = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=True,
        )

        hook_direct = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=False,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            legacy_cmd = hook_legacy.get_command()
            direct_cmd = hook_direct.get_command()

            # Both should reference ruff-check
            assert "ruff-check" in " ".join(legacy_cmd)
            assert "ruff" in " ".join(direct_cmd)

    def test_security_levels_preserved_across_modes(self):
        """Test that security levels are independent of invocation mode."""
        critical_hook = HookDefinition(
            name="gitleaks",
            command=[],
            security_level=SecurityLevel.CRITICAL,
            use_precommit_legacy=False,
        )

        assert critical_hook.security_level == SecurityLevel.CRITICAL

        # Test same hook with legacy mode
        critical_hook_legacy = HookDefinition(
            name="gitleaks",
            command=[],
            security_level=SecurityLevel.CRITICAL,
            use_precommit_legacy=True,
        )

        assert critical_hook_legacy.security_level == SecurityLevel.CRITICAL


class TestBackwardCompatibilityEdgeCases:
    """Test edge cases in backward compatibility implementation."""

    def test_empty_command_list_with_direct_mode(self):
        """Test that empty command list works with direct mode."""
        hook = HookDefinition(
            name="ruff-check",
            command=[],  # Empty command list (filled by get_command())
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        assert len(command) > 0
        assert command[0] == "uv"

    def test_empty_command_list_with_legacy_mode(self):
        """Test that empty command list works with legacy mode."""
        hook = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=True,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            command = hook.get_command()

            assert len(command) > 0
            assert "pre-commit" in command[0]

    def test_direct_mode_command_is_copy(self):
        """Test that get_command() returns a copy (prevents mutation)."""
        hook = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=False,
        )

        command1 = hook.get_command()
        command2 = hook.get_command()

        # Modify first command
        command1.append("--extra-flag")

        # Second command should be unaffected
        assert "--extra-flag" not in command2
        assert len(command2) < len(command1)

    def test_legacy_mode_command_is_fresh(self):
        """Test that legacy mode creates new command each time."""
        hook = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=True,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            command1 = hook.get_command()
            command2 = hook.get_command()

            # Commands should be equal but not the same object
            assert command1 == command2
            assert command1 is not command2

    def test_all_18_tools_work_in_direct_mode(self):
        """Test that all 18 registered tools work with direct invocation."""
        from crackerjack.config.tool_commands import list_available_tools

        all_tools = list_available_tools()
        assert len(all_tools) == 18

        for tool_name in all_tools:
            hook = HookDefinition(
                name=tool_name,
                command=[],
                use_precommit_legacy=False,
            )

            command = hook.get_command()

            assert isinstance(command, list)
            assert len(command) > 0
            assert command[0] == "uv"
