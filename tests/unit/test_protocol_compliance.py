#!/usr/bin/env python3
"""Protocol compliance tests for CrackerjackIntegration.

These tests ensure that CrackerjackIntegration properly implements
external protocols and interfaces that other systems expect.
"""

import asyncio
import inspect
import subprocess
from pathlib import Path
from typing import get_type_hints
from unittest.mock import Mock, patch

import pytest
from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration


class TestCommandRunnerProtocol:
    """Test compliance with crackerjack's CommandRunner protocol."""

    def test_has_execute_command_method(self):
        """Test that execute_command method exists."""
        integration = CrackerjackIntegration()

        assert hasattr(integration, "execute_command"), "Missing execute_command method"
        assert callable(integration.execute_command), "execute_command is not callable"

    def test_execute_command_signature(self):
        """Test execute_command method signature matches protocol."""
        integration = CrackerjackIntegration()
        sig = inspect.signature(integration.execute_command)

        # Should have cmd parameter
        assert "cmd" in sig.parameters, "Missing 'cmd' parameter"

        # cmd should be annotated as list[str]
        cmd_param = sig.parameters["cmd"]
        assert cmd_param.annotation == list[str], (
            f"Wrong cmd annotation: {cmd_param.annotation}"
        )

        # Should accept **kwargs
        has_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
        assert has_kwargs, "Missing **kwargs parameter"

    def test_execute_command_return_type(self):
        """Test execute_command returns expected type."""
        integration = CrackerjackIntegration()

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "test output"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = integration.execute_command(["test"])

            # Should return dict-like object
            assert isinstance(result, dict), f"Wrong return type: {type(result)}"

            # Should have standard subprocess result keys
            expected_keys = {"stdout", "stderr", "returncode"}
            assert expected_keys.issubset(result.keys()), (
                f"Missing keys: {expected_keys - result.keys()}"
            )

    def test_execute_command_handles_subprocess_args(self):
        """Test execute_command properly handles subprocess arguments."""
        integration = CrackerjackIntegration()

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            # Test with various kwargs that subprocess.run accepts
            integration.execute_command(
                ["test"], cwd="/tmp", timeout=30, env={"TEST": "value"}
            )

            # Verify subprocess.run was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args

            # Should pass cmd as first argument
            assert call_args[0][0] == ["test"]

            # Should pass kwargs to subprocess.run
            assert call_args[1]["cwd"] == "/tmp"
            assert call_args[1]["timeout"] == 30

    def test_can_be_used_polymorphically_as_command_runner(self):
        """Test that integration can be used where CommandRunner is expected."""

        def function_expecting_command_runner(runner):
            """Simulates external code that expects CommandRunner protocol."""
            # This is the kind of call that might happen in crackerjack
            return runner.execute_command(["crackerjack", "--help"])

        integration = CrackerjackIntegration()

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "help text"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            # Should work without type errors or attribute errors
            result = function_expecting_command_runner(integration)
            assert isinstance(result, dict)

    def test_type_hints_compatibility(self):
        """Test that type hints are compatible with protocol."""
        integration = CrackerjackIntegration()

        # Get type hints for execute_command
        hints = get_type_hints(integration.execute_command)

        # Should have proper type annotations
        if "cmd" in hints:
            assert hints["cmd"] == list[str], f"Wrong cmd type hint: {hints['cmd']}"


class TestAsyncMethodCompatibility:
    """Test async method compatibility with expected interfaces."""

    def test_execute_crackerjack_command_is_async(self):
        """Test that execute_crackerjack_command is properly async."""
        integration = CrackerjackIntegration()

        import asyncio

        assert asyncio.iscoroutinefunction(integration.execute_crackerjack_command), (
            "execute_crackerjack_command is not async"
        )

    def test_execute_crackerjack_command_signature(self):
        """Test async method has expected signature."""
        integration = CrackerjackIntegration()
        sig = inspect.signature(integration.execute_crackerjack_command)

        # Should have expected parameters
        expected_params = {
            "command",
            "args",
            "working_directory",
            "timeout",
            "ai_agent_mode",
        }
        actual_params = set(sig.parameters.keys())

        assert expected_params.issubset(actual_params), (
            f"Missing parameters: {expected_params - actual_params}"
        )

    async def test_execute_crackerjack_command_return_type(self):
        """Test async method returns CrackerjackResult."""
        from session_mgmt_mcp.crackerjack_integration import CrackerjackResult

        integration = CrackerjackIntegration()

        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = Mock()
            mock_process.communicate = Mock(return_value=(b"output", b""))
            mock_process.returncode = 0
            mock_create.return_value = mock_process

            result = await integration.execute_crackerjack_command("test", [], ".")

            assert isinstance(result, CrackerjackResult), (
                f"Wrong return type: {type(result)}"
            )


class TestResultTypeCompatibility:
    """Test that result types are compatible with consumer expectations."""

    def test_sync_method_dict_compatibility(self):
        """Test sync method returns subprocess-compatible dict."""
        integration = CrackerjackIntegration()

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = "output"
            mock_result.stderr = "error"
            mock_run.return_value = mock_result

            result = integration.execute_command(["test"])

            # Should be compatible with subprocess.CompletedProcess attributes
            assert result["returncode"] == 1
            assert result["stdout"] == "output"
            assert result["stderr"] == "error"

            # Should have success flag for convenience
            assert "success" in result
            assert result["success"] is False  # returncode != 0

    async def test_async_method_dataclass_compatibility(self):
        """Test async method returns structured dataclass."""
        integration = CrackerjackIntegration()

        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = Mock()
            mock_process.communicate = Mock(return_value=(b"test", b""))
            mock_process.returncode = 0
            mock_create.return_value = mock_process

            result = await integration.execute_crackerjack_command("lint", [], ".")

            # Should have all expected CrackerjackResult fields
            expected_fields = {
                "command",
                "exit_code",
                "stdout",
                "stderr",
                "execution_time",
                "timestamp",
                "working_directory",
                "parsed_data",
                "quality_metrics",
                "test_results",
                "memory_insights",
            }

            actual_fields = set(result.__dict__.keys())
            assert expected_fields.issubset(actual_fields), (
                f"Missing fields: {expected_fields - actual_fields}"
            )


class TestMCPToolCompatibility:
    """Test compatibility with MCP tool system."""

    def test_can_be_imported_in_mcp_context(self):
        """Test that integration can be imported in MCP tools."""
        # This test catches import-time errors
        try:
            from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration

            integration = CrackerjackIntegration()
            assert integration is not None
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")

    def test_methods_dont_raise_attribute_errors(self):
        """Test critical methods exist and don't raise AttributeError."""
        from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration

        integration = CrackerjackIntegration()

        # These method calls should not raise AttributeError
        critical_methods = [
            "execute_command",
            "execute_crackerjack_command",
            "get_recent_results",
            "health_check",
        ]

        for method_name in critical_methods:
            try:
                method = getattr(integration, method_name)
                assert callable(method), f"{method_name} is not callable"
            except AttributeError:
                pytest.fail(f"Missing method: {method_name}")

    def test_mcp_tool_result_formatting(self):
        """Test that results can be formatted for MCP tools."""
        integration = CrackerjackIntegration()

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "success"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = integration.execute_command(["test"])

            # Should be able to format for display
            try:
                formatted = (
                    f"Exit code: {result['returncode']}\nOutput: {result['stdout']}"
                )
                assert "Exit code: 0" in formatted
                assert "Output: success" in formatted
            except KeyError as e:
                pytest.fail(f"Result missing key for formatting: {e}")


class TestErrorHandlingProtocol:
    """Test error handling matches expected protocols."""

    def test_sync_method_error_handling(self):
        """Test sync method handles errors according to protocol."""
        integration = CrackerjackIntegration()

        # Test subprocess timeout
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(["cmd"], 30)
        ):
            result = integration.execute_command(["test"], timeout=1)

            assert isinstance(result, dict), "Should return dict even on timeout"
            assert result["success"] is False, "Should indicate failure"
            assert result["returncode"] == -1, "Should use -1 for timeout"
            assert "timeout" in result["stderr"].lower(), (
                "Should indicate timeout in stderr"
            )

    def test_sync_method_exception_handling(self):
        """Test sync method handles general exceptions."""
        integration = CrackerjackIntegration()

        with patch("subprocess.run", side_effect=OSError("Command not found")):
            result = integration.execute_command(["nonexistent"])

            assert isinstance(result, dict), "Should return dict even on exception"
            assert result["success"] is False, "Should indicate failure"
            assert result["returncode"] == -2, "Should use -2 for general errors"
            assert "Command not found" in result["stderr"], (
                "Should include error message"
            )

    async def test_async_method_error_handling(self):
        """Test async method handles errors appropriately."""
        from session_mgmt_mcp.crackerjack_integration import CrackerjackResult

        integration = CrackerjackIntegration()

        # Test timeout error
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await integration.execute_crackerjack_command(
                "test", [], ".", timeout=1
            )

            assert isinstance(result, CrackerjackResult), (
                "Should return CrackerjackResult even on error"
            )
            assert result.exit_code == -1, "Should use -1 for timeout"
            assert "timeout" in result.stderr.lower(), "Should indicate timeout"

    async def test_async_method_general_exception_handling(self):
        """Test async method handles general exceptions."""
        from session_mgmt_mcp.crackerjack_integration import CrackerjackResult

        integration = CrackerjackIntegration()

        with patch(
            "asyncio.create_subprocess_exec", side_effect=OSError("Permission denied")
        ):
            result = await integration.execute_crackerjack_command("test", [], ".")

            assert isinstance(result, CrackerjackResult), (
                "Should return CrackerjackResult even on error"
            )
            assert result.exit_code == -2, "Should use -2 for general errors"
            assert "Permission denied" in result.stderr, "Should include error message"


class TestDatabaseProtocolCompliance:
    """Test database interaction follows expected patterns."""

    def test_database_path_handling(self):
        """Test database path can be customized."""
        custom_path = "/tmp/test.db"
        integration = CrackerjackIntegration(db_path=custom_path)

        assert integration.db_path == custom_path, "Should use custom database path"

    def test_database_initialization_doesnt_fail(self):
        """Test database initialization completes without errors."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            # Should initialize without raising exceptions
            integration = CrackerjackIntegration(db_path=db_path)
            assert integration is not None
        finally:
            # Cleanup
            try:
                Path(db_path).unlink()
            except OSError:
                pass

    async def test_result_storage_protocol(self):
        """Test that results are stored following expected protocol."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            integration = CrackerjackIntegration(db_path=db_path)

            with patch("asyncio.create_subprocess_exec") as mock_create:
                mock_process = Mock()
                mock_process.communicate = Mock(return_value=(b"test", b""))
                mock_process.returncode = 0
                mock_create.return_value = mock_process

                # Execute command (should store result)
                await integration.execute_crackerjack_command("test", [], ".")

                # Should be able to retrieve recent results
                recent = await integration.get_recent_results(hours=1)
                assert len(recent) > 0, "Result should be stored"
                assert recent[0]["command"] == "test", "Stored result should match"

        finally:
            try:
                Path(db_path).unlink()
            except OSError:
                pass


class TestRegressionPreventionTests:
    """Specific tests to prevent regression of the original issues."""

    def test_prevents_missing_execute_command_error(self):
        """Prevent 'execute_command' method missing error."""
        integration = CrackerjackIntegration()

        # This exact check would have caught the original error
        assert hasattr(integration, "execute_command"), (
            "'CrackerjackIntegration' object has no attribute 'execute_command'"
        )

    def test_prevents_command_structure_error(self):
        """Prevent crackerjack command structure errors."""
        integration = CrackerjackIntegration()

        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = Mock()
            mock_process.communicate = Mock(return_value=(b"", b""))
            mock_process.returncode = 0
            mock_create.return_value = mock_process

            # Execute lint command
            asyncio.run(integration.execute_crackerjack_command("lint", [], "."))

            # Verify command structure
            call_args = mock_create.call_args
            cmd = call_args[0]

            # Should NOT contain 'lint' as separate argument
            assert "lint" not in cmd, (
                "Command should not contain 'lint' as separate argument (would cause 'Got unexpected extra argument' error)"
            )

            # Should use proper flag mapping
            assert "--fast" in cmd or "--comp" in cmd or len(cmd) == 1, (
                f"Command should use proper flags, got: {cmd}"
            )

    def test_prevents_result_type_mismatch_error(self):
        """Prevent result type mismatch errors."""
        integration = CrackerjackIntegration()

        # Sync method should return dict
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            sync_result = integration.execute_command(["test"])
            assert isinstance(sync_result, dict), (
                f"Sync method should return dict, got {type(sync_result)}"
            )

        # Async method should return CrackerjackResult
        async def test_async():
            from session_mgmt_mcp.crackerjack_integration import CrackerjackResult

            with patch("asyncio.create_subprocess_exec") as mock_create:
                mock_process = Mock()
                mock_process.communicate = Mock(return_value=(b"", b""))
                mock_process.returncode = 0
                mock_create.return_value = mock_process

                async_result = await integration.execute_crackerjack_command(
                    "test", [], "."
                )
                assert isinstance(async_result, CrackerjackResult), (
                    f"Async method should return CrackerjackResult, got {type(async_result)}"
                )

        asyncio.run(test_async())


if __name__ == "__main__":
    pytest.main([__file__])
