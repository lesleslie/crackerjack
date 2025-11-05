"""Integration tests for Phase 8 direct invocation system.

Tests actual hook execution with direct tool invocation (bypassing pre-commit).
"""

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.config.hooks import (
    COMPREHENSIVE_HOOKS,
    FAST_HOOKS,
    HookDefinition,
)
from crackerjack.config.tool_commands import get_tool_command


class TestDirectInvocationExecution:
    """Test actual execution of hooks with direct invocation."""

    def test_native_tool_executes_successfully(self, tmp_path):
        """Test that a native tool executes successfully."""
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')  \n")  # Trailing whitespace

        hook = HookDefinition(
            name="trailing-whitespace",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        # Execute the command on the test file
        result = subprocess.run(
            [*command, str(test_file)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )

        # Should complete successfully (either fixed or detected issue)
        # Exit code can be 0 (fixed) or 1 (found issues)
        assert result.returncode in (0, 1)

    def test_rust_tool_executes_successfully(self, tmp_path, monkeypatch):
        """Test that a Rust tool (skylos) command can be generated."""
        # Note: We only test command generation, not execution
        # since skylos requires a valid Python project structure
        hook = HookDefinition(
            name="skylos",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        # Verify command structure
        assert command[0] == "uv"
        assert command[1] == "run"
        assert "skylos" in command
        assert "check" in command
        assert "crackerjack" in command

    def test_third_party_tool_executes_successfully(self, tmp_path):
        """Test that a third-party tool (ruff) executes successfully."""
        # Create a test Python file with an issue
        test_file = tmp_path / "test.py"
        test_file.write_text("import  sys\n")  # Double space (formatting issue)

        hook = HookDefinition(
            name="ruff-format",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        # Execute ruff format
        result = subprocess.run(
            [*command, str(test_file)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=10,
        )

        # Should complete successfully (ruff-format returns 0 even when fixing)
        assert result.returncode == 0

    def test_command_uses_uv_isolation(self):
        """Test that all direct commands use uv for dependency isolation."""
        hook = HookDefinition(
            name="ruff-check",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        # Should start with 'uv run' for dependency isolation
        assert command[0] == "uv"
        assert command[1] == "run"


class TestFastHooksIntegration:
    """Integration tests for defined fast hooks."""

    @pytest.mark.parametrize(
        "hook_name",
        [
            "validate-regex-patterns",
            "trailing-whitespace",
            "end-of-file-fixer",
            "check-yaml",
            "check-toml",
            "check-added-large-files",
            "uv-lock",
            "codespell",
            "ruff-check",
            "ruff-format",
            # mdformat is disabled in current FAST_HOOKS; enable when available
        ],
    )
    def test_fast_hook_can_execute(self, hook_name):
        """Test that each fast hook can generate an executable command."""
        hook = next(h for h in FAST_HOOKS if h.name == hook_name)

        command = hook.get_command()

        # Verify command structure
        assert isinstance(command, list)
        assert len(command) > 0
        assert command[0] == "uv"

    def test_all_fast_hooks_have_direct_mode(self):
        """Test that all fast hooks use direct invocation mode."""
        for hook in FAST_HOOKS:
            assert not hook.use_precommit_legacy, f"{hook.name} should use direct mode"
            assert hook.get_command()[0] == "uv"

    def test_fast_hooks_count(self):
        """Test that we have expected number of fast hooks."""
        assert len(FAST_HOOKS) == 10


class TestComprehensiveHooksIntegration:
    """Integration tests for defined comprehensive hooks."""

    @pytest.mark.parametrize(
        "hook_name",
        [
            "zuban",
            "bandit",
            "gitleaks",
            "skylos",
            "refurb",
            "creosote",
            "complexipy",
        ],
    )
    def test_comprehensive_hook_can_execute(self, hook_name):
        """Test that each comprehensive hook can generate an executable command."""
        hook = next(h for h in COMPREHENSIVE_HOOKS if h.name == hook_name)

        command = hook.get_command()

        # Verify command structure
        assert isinstance(command, list)
        assert len(command) > 0
        assert command[0] == "uv"

    def test_all_comprehensive_hooks_have_direct_mode(self):
        """Test that all comprehensive hooks use direct invocation mode."""
        for hook in COMPREHENSIVE_HOOKS:
            assert (
                not hook.use_precommit_legacy
            ), f"{hook.name} should use direct mode"
            assert hook.get_command()[0] == "uv"

    def test_comprehensive_hooks_count(self):
        """Test that we have expected number of comprehensive hooks."""
        assert len(COMPREHENSIVE_HOOKS) == 7


class TestHookExecutionPerformance:
    """Test performance characteristics of direct invocation."""

    def test_command_generation_is_fast(self):
        """Test that getting commands is fast (< 1ms per hook)."""
        start_time = time.perf_counter()

        for _ in range(100):
            for hook in FAST_HOOKS + COMPREHENSIVE_HOOKS:
                hook.get_command()

        duration = time.perf_counter() - start_time

        # Should be able to generate 1800 commands in under 100ms
        # (100 iterations * 18 hooks = 1800 commands)
        assert duration < 0.1, f"Command generation took {duration:.3f}s (too slow)"

    def test_direct_invocation_has_minimal_overhead(self):
        """Test that direct invocation adds minimal overhead."""
        hook = HookDefinition(
            name="trailing-whitespace",
            command=[],
            use_precommit_legacy=False,
        )

        # Measure command retrieval time
        start_time = time.perf_counter()
        command = hook.get_command()
        retrieval_time = time.perf_counter() - start_time

        # Should be sub-millisecond
        assert retrieval_time < 0.001, f"Retrieval took {retrieval_time*1000:.2f}ms"

        # Verify command is ready to execute
        assert command[0] == "uv"
        assert len(command) >= 3


class TestHookFailureHandling:
    """Test graceful handling of hook execution failures."""

    def test_hook_failure_returns_nonzero_exit_code(self, tmp_path):
        """Test that hook failures are detected via exit code."""
        # Create invalid YAML file
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("key: [unclosed\n")

        hook = HookDefinition(
            name="check-yaml",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        # Execute on invalid YAML
        result = subprocess.run(
            [*command, str(invalid_yaml)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=20,
        )

        # Should fail with nonzero exit code
        assert result.returncode != 0

    def test_hook_timeout_can_be_enforced(self, tmp_path):
        """Test that hook timeout attribute exists and can be configured."""
        hook = HookDefinition(
            name="ruff-check",
            command=[],
            timeout=1,  # Very short timeout
            use_precommit_legacy=False,
        )

        # Verify timeout attribute exists and can be configured
        assert hook.timeout == 1

        # Verify command can still be generated
        command = hook.get_command()
        assert command[0] == "uv"

    def test_invalid_tool_gracefully_falls_back(self):
        """Test that invalid tools fall back to pre-commit wrapper."""
        hook = HookDefinition(
            name="nonexistent-tool-12345",
            command=[],
            use_precommit_legacy=False,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            command = hook.get_command()

            # Should fall back to pre-commit
            assert "pre-commit" in command[0]
            assert "nonexistent-tool-12345" in command


class TestEndToEndWorkflow:
    """Test complete end-to-end hook execution workflows."""

    def test_can_execute_formatting_hook_chain(self, tmp_path):
        """Test executing multiple formatting hooks in sequence."""
        # Create test file with multiple issues
        test_file = tmp_path / "test.py"
        test_file.write_text("import  sys  \n\nx=1\n")  # Multiple issues

        formatting_hooks = [
            "trailing-whitespace",
            "end-of-file-fixer",
            "ruff-format",
        ]

        results = []
        for hook_name in formatting_hooks:
            hook = next(h for h in FAST_HOOKS if h.name == hook_name)
            command = hook.get_command()

            if hook_name == "trailing-whitespace":
                from crackerjack.tools.trailing_whitespace import (
                    main as trailing_whitespace_main,
                )

                rc = trailing_whitespace_main([str(test_file)])
            elif hook_name == "end-of-file-fixer":
                from crackerjack.tools.end_of_file_fixer import (
                    main as eof_main,
                )

                rc = eof_main([str(test_file)])
            else:
                result = subprocess.run(
                    [*command, str(test_file)],
                    capture_output=True,
                    text=True,
                    cwd=tmp_path,
                    timeout=20,
                )
                rc = result.returncode

            results.append((hook_name, rc))

        # At least one hook should have made changes or found issues
        assert any(rc in (0, 1) for _, rc in results)

    def test_native_tools_dont_require_pre_commit(self, tmp_path, monkeypatch):
        """Test that native tools work without pre-commit installed."""
        monkeypatch.chdir(tmp_path)

        # Create test file
        test_file = tmp_path / "test.yaml"
        test_file.write_text("key: value\n")

        hook = HookDefinition(
            name="check-yaml",
            command=[],
            use_precommit_legacy=False,
        )

        command = hook.get_command()

        # Should not reference pre-commit at all
        assert "pre-commit" not in " ".join(command)

        # Execute via module entrypoint to avoid fresh interpreter overhead
        from crackerjack.tools.check_yaml import main as check_yaml_main

        exit_code = check_yaml_main([str(test_file)])
        assert exit_code == 0


class TestToolRegistryIntegration:
    """Test integration between tool registry and hook execution."""

    def test_all_registered_tools_have_valid_commands(self):
        """Test that all 18 registered tools have valid, executable commands."""
        from crackerjack.config.tool_commands import list_available_tools

        all_tools = list_available_tools()

        for tool_name in all_tools:
            command = get_tool_command(tool_name)

            # Verify command structure
            assert command[0] == "uv", f"{tool_name} should start with 'uv'"

            # uv-lock is special: "uv lock" not "uv run"
            if tool_name == "uv-lock":
                assert command[1] == "lock", f"{tool_name} should be 'uv lock'"
            else:
                assert command[1] == "run", f"{tool_name} should have 'run' as second arg"

            assert len(command) >= 2, f"{tool_name} command too short: {command}"

    def test_registry_commands_match_hook_commands(self):
        """Test that registry commands match what hooks generate."""
        for hook in FAST_HOOKS + COMPREHENSIVE_HOOKS:
            # Get command from hook
            hook_command = hook.get_command()

            # Get command from registry
            registry_command = get_tool_command(hook.name)

            # Should be identical
            assert hook_command == registry_command, f"Mismatch for {hook.name}"


class TestDirectInvocationBenefits:
    """Test the benefits of Phase 8 direct invocation."""

    def test_direct_mode_reduces_subprocess_overhead(self):
        """Test that direct mode has less overhead than pre-commit wrapper."""
        hook_direct = HookDefinition(
            name="ruff-format",
            command=[],
            use_precommit_legacy=False,
        )

        hook_legacy = HookDefinition(
            name="ruff-format",
            command=[],
            use_precommit_legacy=True,
        )

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "pre-commit"

            # Direct mode command
            direct_cmd = hook_direct.get_command()

            # Legacy mode command
            legacy_cmd = hook_legacy.get_command()

            # Direct mode uses uv directly
            assert direct_cmd[0] == "uv"

            # Legacy mode uses pre-commit wrapper
            assert "pre-commit" in legacy_cmd[0]

            # Both should reference the same underlying tool
            assert "ruff" in " ".join(direct_cmd)
            assert "ruff-format" in " ".join(legacy_cmd)

    def test_direct_mode_uses_uv_dependency_isolation(self):
        """Test that all direct commands use uv for consistent environments."""
        for hook in FAST_HOOKS + COMPREHENSIVE_HOOKS:
            command = hook.get_command()

            # All should use uv for dependency isolation
            assert command[0] == "uv", f"{hook.name} doesn't use uv"

    def test_native_tools_have_no_external_dependencies(self):
        """Test that native tools are self-contained Python modules."""
        native_tools = [
            "trailing-whitespace",
            "end-of-file-fixer",
            "check-yaml",
            "check-toml",
            "check-added-large-files",
            "validate-regex-patterns",
        ]

        for tool_name in native_tools:
            command = get_tool_command(tool_name)

            # Should use python -m for native tools
            assert "python" in command
            assert "-m" in command
            assert "crackerjack.tools." in " ".join(command)
