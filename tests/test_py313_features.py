from pathlib import Path

from crackerjack.py313 import (
    CommandResult,
    HookResult,
    HookStatus,
    ModernConfigManager,
    analyze_hook_result,
    categorize_file,
    clean_python_code,
    process_command_output,
)


class TestPy313Features:
    def test_pattern_matching_categorize_file(self) -> None:
        py_file = Path("/some/path/module.py")
        init_file = Path("/some/path/__init__.py")
        test_file = Path("/some/path/tests/test_module.py")
        md_file = Path("/some/path/README.md")
        config_file = Path("/some/path/.gitignore")
        unknown_file = Path("/some/path/unknown.xyz")
        assert "Python Source File" == categorize_file(py_file)
        assert "Python Module Init" == categorize_file(init_file)
        assert "Python Test File" == categorize_file(test_file)
        assert "Documentation File" == categorize_file(md_file)
        assert "Configuration File" == categorize_file(config_file)
        assert "Unknown File Type" == categorize_file(unknown_file)

    def test_clean_python_code(self) -> None:
        code = "import os\nimport sys\n\n# This is a comment\ndef hello():\n    '''This is a docstring'''\n    print(\"Hello\")  # type: ignore\n    # This is another comment\n\n\n"
        cleaned = clean_python_code(code)
        assert "import os" in cleaned
        assert "import sys" in cleaned
        assert "# This is a comment" not in cleaned
        assert "# This is another comment" not in cleaned
        assert "'''This is a docstring'''" not in cleaned
        assert 'print("Hello")' in cleaned
        assert "# type: ignore" in cleaned
        assert "\n\n\n" not in cleaned

    def test_hook_result_pattern_matching(self) -> None:
        success_result: HookResult = {
            "status": HookStatus.SUCCESS,
            "hook_id": "ruff",
            "output": "All files passed",
            "files": ["file1.py", "file2.py"],
        }
        failure_result: HookResult = {
            "status": HookStatus.FAILURE,
            "hook_id": "black",
            "output": "Formatting issues found",
            "files": ["file1.py"],
        }
        fixable_failure: HookResult = {
            "status": HookStatus.FAILURE,
            "hook_id": "black",
            "output": "Formatting issues found (fixable)",
            "files": ["file1.py"],
        }
        skipped_result: HookResult = {
            "status": HookStatus.SKIPPED,
            "hook_id": "mypy",
            "output": "Hook skipped",
            "files": [],
        }
        error_result: HookResult = {
            "status": HookStatus.ERROR,
            "hook_id": "pytest",
            "output": "Hook crashed",
            "files": ["file1.py"],
        }
        assert "✅ Hook ruff passed successfully" == analyze_hook_result(success_result)
        assert "❌ Hook black failed" == analyze_hook_result(failure_result)
        assert "🔧 Hook black failed with fixable issues" == analyze_hook_result(
            fixable_failure
        )
        assert "⏩ Hook mypy was skipped" == analyze_hook_result(skipped_result)
        assert (
            "💥 Hook pytest encountered an error: Hook crashed"
            == analyze_hook_result(error_result)
        )

    def test_command_result_pattern_matching(self) -> None:
        success_result: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "Command completed successfully",
            "stderr": "",
            "command": ["echo", "hello"],
            "duration_ms": 10.5,
        }
        success_no_output: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "command": ["touch", "file.txt"],
            "duration_ms": 5.2,
        }
        command_not_found: CommandResult = {
            "success": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": "Command not found: unknown_command",
            "command": ["unknown_command"],
            "duration_ms": 1.0,
        }
        command_failed: CommandResult = {
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "Error: file not found",
            "command": ["cat", "nonexistent.txt"],
            "duration_ms": 3.0,
        }
        success, message = process_command_output(success_result)
        assert success
        assert "Command completed successfully" == message
        success, message = process_command_output(success_no_output)
        assert success
        assert "Command completed successfully with no output" == message
        success, message = process_command_output(command_not_found)
        assert not success
        assert "Command not found" in message
        success, message = process_command_output(command_failed)
        assert not success
        assert "Command failed with exit code 1" in message

    def test_self_type_method_chaining(self) -> None:
        config_manager = ModernConfigManager(Path("/fake/config.json"))
        result = config_manager.load().update("key", "value").save()
        assert result is config_manager
