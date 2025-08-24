import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.py313 import (
    CommandResult,
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


class TestProcessCommandOutput:
    def test_successful_command_with_output(self) -> None:
        result: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "Command output here\n",
            "stderr": "",
            "command": ["echo", "test"],
            "duration_ms": 100.0,
        }

        success, message = process_command_output(result)

        assert success is True
        assert message == "Command output here\n"

    def test_successful_command_no_output(self) -> None:
        result: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "command": ["true"],
            "duration_ms": 50.0,
        }

        success, message = process_command_output(result)

        assert success is True
        assert message == "Command completed successfully with no output"

    def test_failed_command_not_found(self) -> None:
        result: CommandResult = {
            "success": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": "command not found",
            "command": ["nonexistent"],
            "duration_ms": 10.0,
        }

        success, message = process_command_output(result)

        assert success is False
        assert message == "Command not found: command not found"

    def test_failed_command_general_error(self) -> None:
        result: CommandResult = {
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "Permission denied",
            "command": ["cat", " / root / secret"],
            "duration_ms": 25.0,
        }

        success, message = process_command_output(result)

        assert success is False
        assert message == "Command failed with exit code 1: Permission denied"

    def test_unknown_pattern(self) -> None:
        result: CommandResult = {
            "success": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "command": ["weird"],
            "duration_ms": 0.0,
        }

        success, message = process_command_output(result)

        assert success is False
        assert message == "Unknown command result pattern"


class TestHookStatus:
    def test_hook_status_values(self) -> None:
        assert HookStatus.SUCCESS
        assert HookStatus.FAILURE
        assert HookStatus.SKIPPED
        assert HookStatus.ERROR

        statuses = {
            HookStatus.SUCCESS,
            HookStatus.FAILURE,
            HookStatus.SKIPPED,
            HookStatus.ERROR,
        }
        assert len(statuses) == 4


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
            "hook_id": "black",
            "output": "File formatting issues detected, fixable automatically",
            "files": ["src / main.py"],
        }

        message = analyze_hook_result(result)

        assert message == "🔧 Hook black failed with fixable issues"

    def test_failed_hook_general(self) -> None:
        result: HookResult = {
            "status": HookStatus.FAILURE,
            "hook_id": "mypy",
            "output": "Type errors found",
            "files": ["src / main.py"],
        }

        message = analyze_hook_result(result)

        assert message == "❌ Hook mypy failed"

    def test_skipped_hook(self) -> None:
        result: HookResult = {
            "status": HookStatus.SKIPPED,
            "hook_id": "pylint",
            "output": "Skipped due to configuration",
            "files": [],
        }

        message = analyze_hook_result(result)

        assert message == "⏩ Hook pylint was skipped"

    def test_error_hook(self) -> None:
        result: HookResult = {
            "status": HookStatus.ERROR,
            "hook_id": "pytest",
            "output": "ImportError: No module named 'nonexistent'",
            "files": ["tests / test_main.py"],
        }

        message = analyze_hook_result(result)

        assert (
            message
            == "💥 Hook pytest encountered an error: ImportError: No module named 'nonexistent'"
        )

    def test_unknown_hook_pattern(self) -> None:
        result: HookResult = {
            "status": "INVALID_STATUS",
            "hook_id": "test",
            "output": "",
            "files": [],
        }

        message = analyze_hook_result(result)

        assert message == "Unknown hook result pattern"


class TestModernConfigManager:
    @pytest.fixture
    def temp_config_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            yield Path(f.name)

    def test_config_manager_initialization(self, temp_config_file) -> None:
        manager = ModernConfigManager(temp_config_file)

        assert manager.config_path == temp_config_file
        assert manager.config == {}

    def test_config_manager_chaining(self, temp_config_file) -> None:
        manager = ModernConfigManager(temp_config_file)

        result = manager.load().update("key1", "value1").update("key2", "value2").save()

        assert result is manager
        assert manager.config["key1"] == "value1"
        assert manager.config["key2"] == "value2"

    def test_config_manager_individual_methods(self, temp_config_file) -> None:
        manager = ModernConfigManager(temp_config_file)

        load_result = manager.load()
        assert load_result is manager

        update_result = manager.update("test_key", "test_value")
        assert update_result is manager
        assert manager.config["test_key"] == "test_value"

        save_result = manager.save()
        assert save_result is manager


class TestCategorizeFile:
    def test_python_test_file(self) -> None:
        test_file = Path("/project / tests / test_main.py")

        category = categorize_file(test_file)

        assert category == "Python Test File"

    def test_python_init_file(self) -> None:
        init_file = Path("/project / src / package / __init__.py")

        category = categorize_file(init_file)

        assert category == "Python Module Init"

    def test_python_source_file(self) -> None:
        source_file = Path("/project / src / main.py")

        category = categorize_file(source_file)

        assert category == "Python Source File"

    def test_documentation_files(self) -> None:
        md_file = Path("/project / README.md")
        rst_file = Path("/project / docs / index.rst")
        txt_file = Path("/project / CHANGELOG.txt")

        assert categorize_file(md_file) == "Documentation File"
        assert categorize_file(rst_file) == "Documentation File"
        assert categorize_file(txt_file) == "Documentation File"

    def test_configuration_files(self) -> None:
        gitignore = Path("/project / .gitignore")
        precommit = Path("/project / .pre - commit - config.yaml")
        hidden_file = Path("/project / .env")

        assert categorize_file(gitignore) == "Configuration File"
        assert categorize_file(precommit) == "Configuration File"
        assert categorize_file(hidden_file) == "Configuration File"

    def test_unknown_file_type(self) -> None:
        binary_file = Path("/project / image.png")

        category = categorize_file(binary_file)

        assert category == "Unknown File Type"


class TestProcessHookResults:
    def test_process_hook_results_success(self) -> None:
        def success_handler(result) -> str:
            return f"SUCCESS: {result['hook_id']}"

        def failure_handler(result) -> str:
            return f"FAILURE: {result.get('hook_id', 'unknown')}"

        results = [
            {"status": HookStatus.SUCCESS, "hook_id": "ruff"},
            {"status": HookStatus.FAILURE, "hook_id": "mypy"},
            {"status": HookStatus.SUCCESS, "hook_id": "black"},
        ]

        processed = process_hook_results(results, success_handler, failure_handler)

        assert processed == ["SUCCESS: ruff", "FAILURE: mypy", "SUCCESS: black"]

    def test_process_hook_results_non_dict(self) -> None:
        def success_handler(result) -> str:
            return "success"

        def failure_handler(result) -> str:
            return f"failure: {result}"

        results = [
            "string_result",
            123,
            {"status": HookStatus.SUCCESS, "hook_id": "test"},
        ]

        processed = process_hook_results(results, success_handler, failure_handler)

        assert processed == ["failure: string_result", "failure: 123", "success"]

    def test_process_hook_results_empty(self) -> None:
        def success_handler(result) -> str:
            return "success"

        def failure_handler(result) -> str:
            return "failure"

        results = []

        processed = process_hook_results(results, success_handler, failure_handler)

        assert processed == []


class TestEnhancedCommandRunner:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_command_runner_initialization(self, temp_dir) -> None:
        runner = EnhancedCommandRunner(temp_dir)

        assert runner.working_dir == temp_dir

    def test_command_runner_initialization_no_dir(self) -> None:
        runner = EnhancedCommandRunner()

        assert runner.working_dir is None

    def test_run_successful_command(self, temp_dir) -> None:
        runner = EnhancedCommandRunner(temp_dir)

        with patch("subprocess.run") as mock_run:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = "Command output"
            mock_process.stderr = ""
            mock_run.return_value = mock_process

            result = runner.run(["echo", "test"])

            assert result["success"] is True
            assert result["exit_code"] == 0
            assert result["stdout"] == "Command output"
            assert result["stderr"] == ""
            assert result["command"] == ["echo", "test"]
            assert result["duration_ms"] > 0

    def test_run_failed_command(self, temp_dir) -> None:
        runner = EnhancedCommandRunner(temp_dir)

        with patch("subprocess.run") as mock_run:
            mock_process = Mock()
            mock_process.returncode = 1
            mock_process.stdout = ""
            mock_process.stderr = "Command failed"
            mock_run.return_value = mock_process

            result = runner.run(["false"])

            assert result["success"] is False
            assert result["exit_code"] == 1
            assert result["stderr"] == "Command failed"

    def test_run_command_subprocess_error(self, temp_dir) -> None:
        runner = EnhancedCommandRunner(temp_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Process error")

            result = runner.run(["nonexistent"])

            assert result["success"] is False
            assert result["exit_code"] == -1
            assert result["stdout"] == ""
            assert result["stderr"] == "Process error"
            assert result["command"] == ["nonexistent"]

    def test_handle_result(self, temp_dir) -> None:
        runner = EnhancedCommandRunner(temp_dir)

        test_result: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "Success output",
            "stderr": "",
            "command": ["test"],
            "duration_ms": 100.0,
        }

        success, message = runner.handle_result(test_result)

        assert success is True
        assert message == "Success output"


class TestCleanPythonCode:
    def test_clean_python_code_basic(self) -> None:
        code = '''import os
from pathlib import Path


def hello():
    """This is a docstring"""
    print("Hello")

def world():
    print("World")
'''

        cleaned = clean_python_code(code)

        assert "import os" in cleaned
        assert "from pathlib import Path" in cleaned
        assert "# This is a comment" not in cleaned
        assert '"""This is a docstring"""' not in cleaned
        assert 'print("Hello")' in cleaned
        assert "# inline comment" not in cleaned
        assert 'print("World")' in cleaned

    def test_clean_python_code_special_comments(self) -> None:
        code = """def test():
    x = 1
    y = 2
    z = 3
    w = 4
    a = 5
"""

        cleaned = clean_python_code(code)

        assert "# noqa: E701" in cleaned
        assert "# type: int" in cleaned
        assert "# pragma: no cover" in cleaned
        assert "# skip this" in cleaned
        assert "# regular comment" not in cleaned

    def test_clean_python_code_empty_lines(self) -> None:
        code = """import os


def hello():
    print("Hello")


    print("World")
"""

        cleaned = clean_python_code(code)

        lines = cleaned.split("\n")

        max_consecutive_empty = 0
        current_consecutive = 0
        for line in lines:
            if line.strip() == "":
                current_consecutive += 1
                max_consecutive_empty = max(max_consecutive_empty, current_consecutive)
            else:
                current_consecutive = 0

        assert max_consecutive_empty <= 1

    def test_clean_python_code_docstrings(self) -> None:
        code = '''def test1():
    """Single line docstring"""
    pass

def test2():
    \'\'\'Triple single quote docstring\'\'\'
    pass

def test3():
    pass
'''

        cleaned = clean_python_code(code)

        assert '"""Single line docstring"""' not in cleaned
        assert "'''Triple single quote docstring'''" not in cleaned
        assert "def test1(): " in cleaned
        assert "def test2(): " in cleaned
        assert "def test3(): " in cleaned


class TestPy313Integration:
    def test_full_workflow_example(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            manager = ModernConfigManager(config_path)

            manager.load().update("project", "test").save()

            runner = EnhancedCommandRunner(Path(temp_dir))

            with patch("subprocess.run") as mock_run:
                mock_process = Mock()
                mock_process.returncode = 0
                mock_process.stdout = "Success"
                mock_process.stderr = ""
                mock_run.return_value = mock_process

                result = runner.run(["echo", "test"])
                success, message = runner.handle_result(result)

                assert success is True
                assert message == "Success"

            test_file = Path(temp_dir) / "test.py"
            category = categorize_file(test_file)
            assert category == "Python Source File"

            hook_result: HookResult = {
                "status": HookStatus.SUCCESS,
                "hook_id": "integration - test",
                "output": "All good",
                "files": [str(test_file)],
            }

            analysis = analyze_hook_result(hook_result)
            assert analysis == "✅ Hook integration - test passed successfully"
