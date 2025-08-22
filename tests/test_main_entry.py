from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from crackerjack.__main__ import app
from crackerjack.cli.handlers import handle_mcp_server
from crackerjack.cli.options import BumpOption, Options


class TestBumpOption:
    def test_str_representation(self) -> None:
        assert str(BumpOption.patch) == "patch"
        assert str(BumpOption.minor) == "minor"
        assert str(BumpOption.major) == "major"
        assert str(BumpOption.interactive) == "interactive"

    def test_enum_values(self) -> None:
        assert BumpOption.patch.value == "patch"
        assert BumpOption.minor.value == "minor"
        assert BumpOption.major.value == "major"
        assert BumpOption.interactive.value == "interactive"


class TestOptions:
    def test_default_options(self) -> None:
        options = Options()
        assert options.commit is False
        assert options.interactive is False
        assert options.test is False
        assert options.verbose is False
        assert options.publish is None
        assert options.bump is None

    def test_create_options_with_valid_publish(self) -> None:
        options = Options(publish="patch")
        assert options.publish == BumpOption.patch

        options = Options(publish="interactive")
        assert options.publish == BumpOption.interactive

    def test_create_options_with_invalid_publish(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Options(publish="invalid")


class TestMCPServer:
    @patch("crackerjack.mcp.server.main")
    def testhandle_mcp_server(self, mock_start_mcp) -> None:
        handle_mcp_server()

        mock_start_mcp.assert_called_once()


class TestCLI:
    def test_app_exists(self) -> None:
        assert app is not None

    @patch("crackerjack.core.workflow_orchestrator.WorkflowOrchestrator")
    def test_basic_run(self, mock_orchestrator_class) -> None:
        mock_orchestrator = Mock()

        # Create an async function that returns True
        async def mock_workflow() -> bool:
            return True

        # Use side_effect to create a fresh coroutine each time
        mock_orchestrator.run_complete_workflow.side_effect = (
            lambda options: mock_workflow()
        )
        mock_orchestrator_class.return_value = mock_orchestrator

        runner = CliRunner()
        result = runner.invoke(app, [])

        assert result.exit_code == 0
        mock_orchestrator.run_complete_workflow.assert_called_once()

    @patch("crackerjack.__main__._handle_server_commands")
    def test_mcp_server_flag(self, mock_handle_server) -> None:
        mock_handle_server.return_value = (
            True  # Simulate successful server command handling
        )

        runner = CliRunner()
        result = runner.invoke(app, ["--start-mcp-server"])

        assert result.exit_code == 0
        mock_handle_server.assert_called_once()

    @patch("crackerjack.cli.interactive.launch_interactive_cli")
    def test_interactive_flag(self, mock_interactive) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--interactive"])

        assert result.exit_code == 0
        mock_interactive.assert_called_once()
