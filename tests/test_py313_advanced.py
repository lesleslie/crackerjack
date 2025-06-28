import subprocess
from pathlib import Path
from typing import Any
from unittest import mock

from crackerjack.py313 import (
    CommandResult,
    CommandRunner,
    EnhancedCommandRunner,
    HookResult,
    HookStatus,
    analyze_hook_result,
    process_command_output,
    process_hook_results,
)


class TestPy313Advanced:
    def test_command_runner_type_parameters(self) -> None:
        runner_str = CommandRunner[str]()
        with mock.patch.object(
            CommandRunner, "run_command", return_value="test output"
        ):
            result = runner_str.run_command(["echo", "test"])
            assert result == "test output"
            assert isinstance(result, str)
        runner_result = CommandRunner[CommandResult]()
        mock_result: CommandResult = {
            "success": True,
            "exit_code": 0,
            "stdout": "test output",
            "stderr": "",
            "command": ["echo", "test"],
            "duration_ms": 10.0,
        }
        with mock.patch.object(CommandRunner, "run_command", return_value=mock_result):
            result = runner_result.run_command(["echo", "test"])
            assert result["success"]
            assert result["stdout"] == "test output"

    def test_process_command_output_unknown_case(self) -> None:
        weird_result: CommandResult = {
            "success": False,
            "exit_code": -999,
            "stdout": "",
            "stderr": "",
            "command": ["unknown"],
            "duration_ms": 0.0,
        }
        success, message = process_command_output(weird_result)
        assert not success
        assert message == "Unknown command result pattern"

    def test_analyze_hook_result_unknown_case(self) -> None:
        weird_result: HookResult = {
            "status": HookStatus.ERROR,
            "hook_id": "custom",
            "output": "some error",
            "files": [],
        }
        result = analyze_hook_result(weird_result)
        assert result == "💥 Hook custom encountered an error: some error"

    def test_process_hook_results(self) -> None:
        hook_results: list[HookResult] = [
            {
                "status": HookStatus.SUCCESS,
                "hook_id": "test1",
                "output": "success",
                "files": ["file1.py"],
            },
            {
                "status": HookStatus.FAILURE,
                "hook_id": "test2",
                "output": "failure",
                "files": ["file2.py"],
            },
        ]

        def success_handler(result: HookResult) -> str:
            return f"Success: {result['hook_id']}"

        def failure_handler(result: HookResult) -> str:
            return f"Failure: {result['hook_id']}"

        processed = process_hook_results(hook_results, success_handler, failure_handler)
        assert processed[0] == "Success: test1"
        assert processed[1] == "Failure: test2"
        non_dict_results = ["not a dict", 123, None]

        def alt_success_handler(result: Any) -> str:
            return f"Success object: {result}"

        def alt_failure_handler(result: Any) -> str:
            return f"Failure object: {result}"

        processed = process_hook_results(
            non_dict_results, alt_success_handler, alt_failure_handler
        )
        assert processed[0] == "Failure object: not a dict"
        assert processed[1] == "Failure object: 123"
        assert processed[2] == "Failure object: None"

    def test_enhanced_command_runner(self) -> None:
        test_dir = Path.home() / ".cache" / "crackerjack-tests"
        test_dir.mkdir(parents=True, exist_ok=True)
        runner = EnhancedCommandRunner(test_dir)
        with mock.patch("subprocess.run") as mock_run:
            mock_process = mock.MagicMock()
            mock_process.returncode = 0
            mock_process.stdout = "test output"
            mock_process.stderr = ""
            mock_run.return_value = mock_process
            result = runner.run(["echo", "test"])
            assert result["success"]
            assert result["exit_code"] == 0
            assert result["stdout"] == "test output"
            assert result["stderr"] == ""
            assert result["command"] == ["echo", "test"]
            assert isinstance(result["duration_ms"], float)
            success, message = runner.handle_result(result)
            assert success
            assert message == "test output"
        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Command failed")
            result = runner.run(["failing", "command"])
            assert not result["success"]
            assert result["exit_code"] == -1
            assert result["stdout"] == ""
            assert result["stderr"] == "Command failed"
            assert result["command"] == ["failing", "command"]
            assert isinstance(result["duration_ms"], float)
            success, message = runner.handle_result(result)
            assert not success
            assert "Unknown command result pattern" == message
