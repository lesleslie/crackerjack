from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.dynamic_config import DynamicConfigGenerator
from crackerjack.errors import (
    ConfigError,
    CrackerjackError,
    ErrorCode,
    ExecutionError,
    GitError,
    handle_error,
)
from crackerjack.services.initialization import InitializationService


class TestErrorClasses:
    def test_crackerjack_error_with_code(self) -> None:
        error = CrackerjackError("Test error", ErrorCode.CONFIG_FILE_NOT_FOUND)

        assert str(error) == "Test error"
        assert error.error_code == ErrorCode.CONFIG_FILE_NOT_FOUND

    def test_config_error(self) -> None:
        error = ConfigError("Config failed")

        assert isinstance(error, CrackerjackError)
        assert error.error_code == ErrorCode.CONFIG_PARSE_ERROR

    def test_execution_error(self) -> None:
        error = ExecutionError("Execution failed", ErrorCode.COMMAND_EXECUTION_ERROR)

        assert isinstance(error, CrackerjackError)
        assert error.error_code == ErrorCode.COMMAND_EXECUTION_ERROR

    @patch("crackerjack.errors.Console")
    def test_handle_error(self, mock_console_class) -> None:
        mock_console = mock_console_class.return_value

        error = GitError("Git command failed", ErrorCode.GIT_COMMAND_ERROR)

        handle_error(error, console=mock_console, exit_on_error=False)

        mock_console.print.assert_called()

    def test_error_code_enum(self) -> None:
        assert ErrorCode.CONFIG_FILE_NOT_FOUND.value == 1001
        assert ErrorCode.COMMAND_EXECUTION_ERROR.value == 2001
        assert ErrorCode.TEST_FAILURE.value == 3002
        assert ErrorCode.PUBLISH_ERROR.value == 4002
        assert ErrorCode.GIT_COMMAND_ERROR.value == 5001


class TestDynamicConfigGenerator:
    @pytest.fixture
    def config_generator(self):
        return DynamicConfigGenerator()

    def test_init(self, config_generator) -> None:
        assert config_generator.template is not None

    def test_filter_hooks_for_mode(self, config_generator) -> None:
        hooks = config_generator.filter_hooks_for_mode("fast")

        assert len(hooks) > 0

        for hook in hooks:
            assert hook["tier"] in [1, 2]

    def test_group_hooks_by_repo(self, config_generator) -> None:
        hooks = config_generator.filter_hooks_for_mode("fast")
        grouped = config_generator.group_hooks_by_repo(hooks)

        assert isinstance(grouped, dict)
        assert len(grouped) > 0

    def test_generate_config(self, config_generator) -> None:
        config_content = config_generator.generate_config("fast")

        assert "repos: " in config_content
        assert "trailing - whitespace" in config_content
        assert "end - of - file - fixer" in config_content

    def test_create_temp_config(self, config_generator) -> None:
        temp_path = config_generator.create_temp_config("fast")

        assert temp_path.exists()
        assert temp_path.suffix == ".yaml"

        temp_path.unlink(missing_ok=True)


class TestInitializationService:
    @pytest.fixture
    def init_service(self):
        from unittest.mock import Mock

        from rich.console import Console

        from crackerjack.services.filesystem import FileSystemService
        from crackerjack.services.git import GitService

        return InitializationService(
            Console(),
            filesystem=Mock(spec=FileSystemService),
            git_service=Mock(spec=GitService),
            pkg_path=Path(" / test / project"),
        )

    def test_init(self, init_service) -> None:
        assert init_service.pkg_path == Path(" / test / project")
        assert init_service.console is not None

    @patch("subprocess.run")
    def test_check_uv_installed(self, mock_run, init_service) -> None:
        mock_run.return_value = Mock(returncode=0)

        result = init_service.check_uv_installed()

        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_check_uv_not_installed(self, mock_run, init_service) -> None:
        mock_run.side_effect = FileNotFoundError()

        result = init_service.check_uv_installed()

        assert result is False

    @patch("pathlib.Path.exists")
    def test_validate_project_structure(self, mock_exists, init_service) -> None:
        mock_exists.return_value = True

        result = init_service.validate_project_structure()

        assert result is True

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_initialize_project(self, mock_exists, mock_run, init_service) -> None:
        mock_exists.return_value = True
        mock_run.return_value = Mock(returncode=0)

        with patch.object(init_service, "check_uv_installed", return_value=True):
            with patch.object(
                init_service, "validate_project_structure", return_value=True
            ):
                result = init_service.initialize_project()

        assert isinstance(result, dict)
        assert result["success"] is True
