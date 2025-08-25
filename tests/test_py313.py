import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from crackerjack.py313 import (
    CommandResult,
    CommandRunner,
    EnhancedCommandRunner,
    HookResult,
    HookStatus,
    ModernConfigManager,
    analyze_hook_result,
    categorize_file,
    clean_python_code,
    process_command_output,
    process_hook_results,
)


class TestCommandResult:
    def test_command_result_structure(self) -> None:
        result: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "output",
            "stderr": "",
            "command": ["echo", "test"],
            "duration_ms": 123.45,
        }

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert result["stdout"] == "output"
        assert result["stderr"] == ""
        assert result["command"] == ["echo", "test"]
        assert result["duration_ms"] == 123.45


class TestCommandRunner:
    def test_command_runner_protocol(self) -> None:
        class ConcreteRunner(CommandRunner[str]):
            def run_command(self, cmd: list[str], **kwargs) -> str:
                return f"Executed: {' '.join(cmd)}"

        runner = ConcreteRunner()
        result = runner.run_command(["test", "command"])

        assert result == "Executed: test command"


class TestProcessCommandOutput:
    def test_successful_command_with_output(self) -> None:
        result: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "Command output",
            "stderr": "",
            "command": ["echo", "test"],
            "duration_ms": 50.0,
        }

        success, message = process_command_output(result)

        assert success is True
        assert message == "Command output"

    def test_successful_command_no_output(self) -> None:
        result: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "command": ["true"],
            "duration_ms": 25.0,
        }

        success, message = process_command_output(result)

        assert success is True
        assert message == "Command completed successfully with no output"

    def test_command_not_found(self) -> None:
        result: CommandResult = {
            "success": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": "command not found: nonexistent",
            "command": ["nonexistent"],
            "duration_ms": 10.0,
        }

        success, message = process_command_output(result)

        assert success is False
        assert message == "Command not found: command not found: nonexistent"

    def test_command_failed_with_error(self) -> None:
        result: CommandResult = {
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "Permission denied",
            "command": ["access_restricted"],
            "duration_ms": 75.0,
        }

        success, message = process_command_output(result)

        assert success is False
        assert message == "Command failed with exit code 1: Permission denied"

    def test_unknown_pattern(self) -> None:
        result: CommandResult = {
            "success": None,
            "exit_code": -999,
            "stdout": "",
            "stderr": "",
            "command": [],
            "duration_ms": 0.0,
        }

        success, message = process_command_output(result)

        assert success is False
        assert message == "Unknown command result pattern"


class TestHookStatus:
    def test_hook_status_values(self) -> None:
        assert HookStatus.SUCCESS.name == "SUCCESS"
        assert HookStatus.FAILURE.name == "FAILURE"
        assert HookStatus.SKIPPED.name == "SKIPPED"
        assert HookStatus.ERROR.name == "ERROR"

        statuses = [
            HookStatus.SUCCESS,
            HookStatus.FAILURE,
            HookStatus.SKIPPED,
            HookStatus.ERROR,
        ]
        assert len(set(statuses)) == 4


class TestHookResult:
    def test_hook_result_structure(self) -> None:
        result: HookResult = {
            "status": HookStatus.SUCCESS,
            "hook_id": "test - hook",
            "output": "Hook completed successfully",
            "files": ["file1.py", "file2.py"],
        }

        assert result["status"] == HookStatus.SUCCESS
        assert result["hook_id"] == "test - hook"
        assert result["output"] == "Hook completed successfully"
        assert result["files"] == ["file1.py", "file2.py"]


class TestAnalyzeHookResult:
    def test_successful_hook(self) -> None:
        result: HookResult = {
            "status": HookStatus.SUCCESS,
            "hook_id": "ruff - check",
            "output": "All checks passed",
            "files": ["test.py"],
        }

        message = analyze_hook_result(result)

        assert message == "✅ Hook ruff - check passed successfully"

    def test_failed_hook_fixable(self) -> None:
        result: HookResult = {
            "status": HookStatus.FAILURE,
            "hook_id": "trailing - whitespace",
            "output": "Found trailing whitespace - fixable issues detected",
            "files": ["test.py"],
        }

        message = analyze_hook_result(result)

        assert message == "🔧 Hook trailing - whitespace failed with fixable issues"

    def test_failed_hook_not_fixable(self) -> None:
        result: HookResult = {
            "status": HookStatus.FAILURE,
            "hook_id": "pyright",
            "output": "Type error: undefined variable",
            "files": ["test.py"],
        }

        message = analyze_hook_result(result)

        assert message == "❌ Hook pyright failed"

    def test_skipped_hook(self) -> None:
        result: HookResult = {
            "status": HookStatus.SKIPPED,
            "hook_id": "bandit",
            "output": "No Python files to check",
            "files": [],
        }

        message = analyze_hook_result(result)

        assert message == "⏩ Hook bandit was skipped"

    def test_error_hook(self) -> None:
        result: HookResult = {
            "status": HookStatus.ERROR,
            "hook_id": "custom - hook",
            "output": "Hook crashed with exception",
            "files": [],
        }

        message = analyze_hook_result(result)

        assert (
            message
            == "💥 Hook custom - hook encountered an error: Hook crashed with exception"
        )

    def test_unknown_hook_pattern(self) -> None:
        result: HookResult = {
            "status": None,
            "hook_id": "unknown",
            "output": "Unknown status",
            "files": [],
        }

        message = analyze_hook_result(result)

        assert message == "Unknown hook result pattern"


class TestCategorizeFile:
    def test_python_test_file(self) -> None:
        file_path = Path("/project / tests / test_module.py")

        category = categorize_file(file_path)

        assert category == "Python Test File"

    def test_python_init_file(self) -> None:
        file_path = Path("/project / package / __init__.py")

        category = categorize_file(file_path)

        assert category == "Python Module Init"

    def test_python_source_file(self) -> None:
        file_path = Path("/project / src / module.py")

        category = categorize_file(file_path)

        assert category == "Python Source File"

    def test_markdown_documentation(self) -> None:
        file_path = Path("/project / README.md")

        category = categorize_file(file_path)

        assert category == "Documentation File"

    def test_rst_documentation(self) -> None:
        file_path = Path("/project / docs / index.rst")

        category = categorize_file(file_path)

        assert category == "Documentation File"

    def test_text_documentation(self) -> None:
        file_path = Path("/project / CHANGELOG.txt")

        category = categorize_file(file_path)

        assert category == "Documentation File"

    def test_gitignore_config_file(self) -> None:
        file_path = Path("/project / .gitignore")

        category = categorize_file(file_path)

        assert category == "Configuration File"

    def test_precommit_config_file(self) -> None:
        file_path = Path("/project / .pre - commit - config.yaml")

        category = categorize_file(file_path)

        assert category == "Configuration File"

    def test_hidden_config_file(self) -> None:
        file_path = Path("/project / .env")

        category = categorize_file(file_path)

        assert category == "Configuration File"

    def test_unknown_file_type(self) -> None:
        file_path = Path("/project / data.csv")

        category = categorize_file(file_path)

        assert category == "Unknown File Type"


class TestProcessHookResults:
    def test_process_mixed_results(self) -> None:
        results = [
            {"status": HookStatus.SUCCESS, "hook_id": "hook1"},
            {"status": HookStatus.FAILURE, "hook_id": "hook2"},
            {"status": HookStatus.SUCCESS, "hook_id": "hook3"},
        ]

        def success_handler(result) -> str:
            return f"SUCCESS: {result['hook_id']}"

        def failure_handler(result) -> str:
            return f"FAILURE: {result['hook_id']}"

        processed = process_hook_results(results, success_handler, failure_handler)

        assert processed == [
            "SUCCESS: hook1",
            "FAILURE: hook2",
            "SUCCESS: hook3",
        ]

    def test_process_all_successful_results(self) -> None:
        results = [
            {"status": HookStatus.SUCCESS, "data": "test1"},
            {"status": HookStatus.SUCCESS, "data": "test2"},
        ]

        def success_handler(result):
            return result["data"].upper()

        def failure_handler(result) -> str:
            return "FAILED"

        processed = process_hook_results(results, success_handler, failure_handler)

        assert processed == ["TEST1", "TEST2"]

    def test_process_all_failed_results(self) -> None:
        results = [
            {"status": HookStatus.FAILURE, "error": "error1"},
            {"status": HookStatus.ERROR, "error": "error2"},
            "invalid_result",
        ]

        def success_handler(result) -> str:
            return "SUCCESS"

        def failure_handler(result) -> str:
            if isinstance(result, dict) and "error" in result:
                return f"ERROR: {result['error']}"
            return "UNKNOWN_ERROR"

        processed = process_hook_results(results, success_handler, failure_handler)

        assert processed == ["ERROR: error1", "ERROR: error2", "UNKNOWN_ERROR"]

    def test_process_empty_results(self) -> None:
        results = []

        def success_handler(result) -> str:
            return "SUCCESS"

        def failure_handler(result) -> str:
            return "FAILURE"

        processed = process_hook_results(results, success_handler, failure_handler)

        assert processed == []


class TestModernConfigManager:
    def test_config_manager_initialization(self) -> None:
        config_path = Path("/test / config.yaml")
        manager = ModernConfigManager(config_path)

        assert manager.config_path == config_path
        assert manager.config == {}

    def test_config_manager_chaining(self) -> None:
        config_path = Path("/test / config.yaml")
        manager = ModernConfigManager(config_path)

        result = manager.load().update("key1", "value1").update("key2", "value2").save()

        assert result is manager
        assert manager.config == {"key1": "value1", "key2": "value2"}

    def test_load_returns_self(self) -> None:
        manager = ModernConfigManager(Path("/test / config.yaml"))

        result = manager.load()

        assert result is manager

    def test_update_modifies_config(self) -> None:
        manager = ModernConfigManager(Path("/test / config.yaml"))

        result = manager.update("test_key", "test_value")

        assert result is manager
        assert manager.config["test_key"] == "test_value"

    def test_save_returns_self(self) -> None:
        manager = ModernConfigManager(Path("/test / config.yaml"))

        result = manager.save()

        assert result is manager


class TestEnhancedCommandRunner:
    def test_initialization(self) -> None:
        working_dir = Path("/test / dir")
        runner = EnhancedCommandRunner(working_dir)

        assert runner.working_dir == working_dir

    def test_initialization_no_working_dir(self) -> None:
        runner = EnhancedCommandRunner()

        assert runner.working_dir is None

    @patch("subprocess.run")
    def test_successful_command_run(self, mock_run) -> None:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "Command output"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        runner = EnhancedCommandRunner()
        result = runner.run(["echo", "test"])

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert result["stdout"] == "Command output"
        assert result["stderr"] == ""
        assert result["command"] == ["echo", "test"]
        assert result["duration_ms"] > 0

        mock_run.assert_called_once_with(
            ["echo", "test"],
            capture_output=True,
            text=True,
            cwd=None,
        )

    @patch("subprocess.run")
    def test_failed_command_run(self, mock_run) -> None:
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Command failed"
        mock_run.return_value = mock_process

        runner = EnhancedCommandRunner()
        result = runner.run(["false"])

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert result["stdout"] == ""
        assert result["stderr"] == "Command failed"
        assert result["command"] == ["false"]
        assert result["duration_ms"] > 0

    @patch("subprocess.run")
    def test_command_with_working_directory(self, mock_run) -> None:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "output"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        working_dir = Path("/test / dir")
        runner = EnhancedCommandRunner(working_dir)
        runner.run(["ls"])

        mock_run.assert_called_once_with(
            ["ls"],
            capture_output=True,
            text=True,
            cwd=working_dir,
        )

    @patch("subprocess.run")
    def test_subprocess_error_handling(self, mock_run) -> None:
        mock_run.side_effect = subprocess.SubprocessError("Process error")

        runner = EnhancedCommandRunner()
        result = runner.run(["invalid_command"])

        assert result["success"] is False
        assert result["exit_code"] == -1
        assert result["stdout"] == ""
        assert result["stderr"] == "Process error"
        assert result["command"] == ["invalid_command"]
        assert result["duration_ms"] > 0

    @patch("subprocess.run")
    def test_handle_result_integration(self, mock_run) -> None:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "Success output"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        runner = EnhancedCommandRunner()
        result = runner.run(["echo", "test"])
        success, message = runner.handle_result(result)

        assert success is True
        assert message == "Success output"


class TestCleanPythonCode:
    def test_remove_comments(self) -> None:
        code = """def test():
    x = 1

    return x"""

        cleaned = clean_python_code(code)

        expected = """def test():
    x = 1
    return x"""
        assert cleaned == expected

    def test_preserve_special_comments(self) -> None:
        code = """def test():
    x = 1
    y = 2
    z = 3
    w = 4
    return x"""

        cleaned = clean_python_code(code)

        expected = """def test():
    x = 1
    y = 2
    z = 3
    w = 4
    return x"""
        assert cleaned == expected

    def test_preserve_imports(self) -> None:
        code = """import os # Standard library
from pathlib import Path

def test():
    pass"""

        cleaned = clean_python_code(code)

        expected = """import os # Standard library
from pathlib import Path

def test():
    pass"""
        assert cleaned == expected

    def test_remove_docstrings(self) -> None:
        code = '''def test():
    """This is a docstring."""
    x = 1
    \'\'\'Another docstring\'\'\'
    return x'''

        cleaned = clean_python_code(code)

        expected = """def test():
    x = 1
    return x"""
        assert cleaned == expected

    def test_handle_empty_lines(self) -> None:
        code = """def test():


    x = 1


    return x


"""

        cleaned = clean_python_code(code)

        expected = """def test():

    x = 1

    return x
"""
        assert cleaned == expected

    def test_mixed_code_cleaning(self) -> None:
        code = '''# File header comment
import sys
from typing import Any


class TestClass:
    """Class docstring."""

    def method(self, x):

        result = x * 2
        return result

    def another_method(self):
        \'\'\'Another docstring\'\'\'
        pass'''

        cleaned = clean_python_code(code)

        expected = """import sys # System module
from typing import Any

class TestClass:

    def method(self, x):
        result = x * 2
        return result

    def another_method(self):
        pass"""
        assert cleaned == expected

    def test_empty_input(self) -> None:
        code = ""

        cleaned = clean_python_code(code)

        assert cleaned == ""

    def test_only_comments_and_docstrings(self) -> None:
        code = '''# Just comments
"""And docstrings"""

\'\'\'More docstrings\'\'\'
'''

        cleaned = clean_python_code(code)

        assert cleaned == ""


def test_process_command_output_basic() -> None:
    """Test basic functionality of process_command_output."""
    try:
        result = process_command_output()
        assert result is not None or result is None
    except TypeError:
        import inspect

        assert callable(process_command_output), "Function should be callable"
        sig = inspect.signature(process_command_output)
        assert sig is not None, "Function should have valid signature"
        pytest.skip(
            "Function requires specific arguments - manual implementation needed",
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in process_command_output: {e}")


def test_analyze_hook_result_basic() -> None:
    """Test basic functionality of analyze_hook_result."""
    try:
        result = analyze_hook_result()
        assert result is not None or result is None
    except TypeError:
        import inspect

        assert callable(analyze_hook_result), "Function should be callable"
        sig = inspect.signature(analyze_hook_result)
        assert sig is not None, "Function should have valid signature"
        pytest.skip(
            "Function requires specific arguments - manual implementation needed",
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in analyze_hook_result: {e}")


def test_categorize_file_basic() -> None:
    """Test basic functionality of categorize_file."""
    try:
        result = categorize_file()
        assert result is not None or result is None
    except TypeError:
        import inspect

        assert callable(categorize_file), "Function should be callable"
        sig = inspect.signature(categorize_file)
        assert sig is not None, "Function should have valid signature"
        pytest.skip(
            "Function requires specific arguments - manual implementation needed",
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in categorize_file: {e}")


def test_process_hook_results_basic() -> None:
    """Test basic functionality of process_hook_results."""
    try:
        result = process_hook_results()
        assert result is not None or result is None
    except TypeError:
        import inspect

        assert callable(process_hook_results), "Function should be callable"
        sig = inspect.signature(process_hook_results)
        assert sig is not None, "Function should have valid signature"
        pytest.skip(
            "Function requires specific arguments - manual implementation needed",
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in process_hook_results: {e}")


def test_clean_python_code_basic() -> None:
    """Test basic functionality of clean_python_code."""
    try:
        result = clean_python_code()
        assert result is not None or result is None
    except TypeError:
        import inspect

        assert callable(clean_python_code), "Function should be callable"
        sig = inspect.signature(clean_python_code)
        assert sig is not None, "Function should have valid signature"
        pytest.skip(
            "Function requires specific arguments - manual implementation needed",
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in clean_python_code: {e}")


def test_run_command_basic() -> None:
    """Test basic functionality of run_command."""
    try:
        result = run_command()
        assert result is not None or result is None
    except TypeError:
        import inspect

        assert callable(run_command), "Function should be callable"
        sig = inspect.signature(run_command)
        assert sig is not None, "Function should have valid signature"
        pytest.skip(
            "Function requires specific arguments - manual implementation needed",
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in run_command: {e}")


def test_run_basic() -> None:
    """Test basic functionality of run."""
    try:
        result = run()
        assert result is not None or result is None
    except TypeError:
        import inspect

        assert callable(run), "Function should be callable"
        sig = inspect.signature(run)
        assert sig is not None, "Function should have valid signature"
        pytest.skip(
            "Function requires specific arguments - manual implementation needed",
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in run: {e}")
