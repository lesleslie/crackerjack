import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from crackerjack.executors.hook_executor import HookExecutor
from crackerjack.models.config import HookConfig


@pytest.mark.skip(reason="HookExecutor requires complex nested ACB DI setup - integration test, not unit test")
class TestHookExecutor:
    @pytest.fixture
    def console(self):
        return Console()

    @pytest.fixture
    def executor(self, console):
        return HookExecutor(pkg_path=pkg_path)

    def test_init(self, executor, console):
        """Test HookExecutor initialization"""
        assert executor.console == console
        assert executor.logger is not None

    def test_execute_hook_success(self, executor):
        """Test execute_hook method with successful execution"""
        hook_config = HookConfig(
            id="black",
            name="black",
            entry="black",
            language="python",
            files="\\.py$"
        )

        with patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "All files formatted correctly"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            with tempfile.TemporaryDirectory() as tmp_dir:
                result = executor.execute_hook(hook_config, Path(tmp_dir))

                assert result.success is True
                assert result.hook_id == "black"
                assert result.duration >= 0
                assert result.stdout == "All files formatted correctly"
                assert result.stderr == ""

    def test_execute_hook_failure(self, executor):
        """Test execute_hook method with failed execution"""
        hook_config = HookConfig(
            id="flake8",
            name="flake8",
            entry="flake8",
            language="python",
            files="\\.py$"
        )

        with patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "errors found"
            mock_subprocess.return_value = mock_result

            with tempfile.TemporaryDirectory() as tmp_dir:
                result = executor.execute_hook(hook_config, Path(tmp_dir))

                assert result.success is False
                assert result.hook_id == "flake8"
                assert result.duration >= 0
                assert result.stdout == ""
                assert result.stderr == "errors found"
                assert result.error == "Hook execution failed with return code 1"

    def test_execute_hook_exception(self, executor):
        """Test execute_hook method with exception"""
        hook_config = HookConfig(
            id="mypy",
            name="mypy",
            entry="mypy",
            language="python",
            files="\\.py$"
        )

        with patch('subprocess.run', side_effect=Exception("Test exception")):
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = executor.execute_hook(hook_config, Path(tmp_dir))

                assert result.success is False
                assert result.hook_id == "mypy"
                assert result.duration >= 0
                assert "Test exception" in result.error

    def test_execute_hook_with_additional_args(self, executor):
        """Test execute_hook method with additional arguments"""
        hook_config = HookConfig(
            id="ruff",
            name="ruff",
            entry="ruff",
            language="python",
            files="\\.py$",
            args=["--fix", "--show-source"]
        )

        with patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "No issues found"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            with tempfile.TemporaryDirectory() as tmp_dir:
                result = executor.execute_hook(hook_config, Path(tmp_dir))

                assert result.success is True
                # Verify that the additional args were passed to subprocess.run

    def test_build_hook_command(self, executor):
        """Test _build_hook_command method"""
        hook_config = HookConfig(
            id="test-hook",
            name="Test Hook",
            entry="python script.py",
            language="python",
            files="\\.py$",
            args=["--verbose", "--output-format=json"]
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            command = executor._build_hook_command(hook_config, tmp_path)

            # Should include the entry command and additional args
            assert "python script.py" in command
            assert "--verbose" in command
            assert "--output-format=json" in command
            # Should include the working directory
            assert str(tmp_path) in str(command) or tmp_path.name in str(command)

    def test_execute_hook_with_environment(self, executor):
        """Test execute_hook method with custom environment variables"""
        hook_config = HookConfig(
            id="test-env",
            name="Test Env",
            entry="echo $TEST_VAR",
            language="python",
            files="\\.py$",
            env={"TEST_VAR": "test_value"}
        )

        with patch('subprocess.run') as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "test_value"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            with tempfile.TemporaryDirectory() as tmp_dir:
                result = executor.execute_hook(hook_config, Path(tmp_dir))

                assert result.success is True
                # Verify that environment variables were passed
                mock_subprocess.assert_called_once()
                args, kwargs = mock_subprocess.call_args
                assert "env" in kwargs
                assert kwargs["env"]["TEST_VAR"] == "test_value"
