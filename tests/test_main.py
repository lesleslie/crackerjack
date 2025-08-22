import typing as t
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from crackerjack.__main__ import app
from crackerjack.cli.options import BumpOption, Options


@pytest.fixture
def mock_crackerjack_process() -> t.Generator[MagicMock]:
    mock_orchestrator = MagicMock()

    # Create an async function that returns True
    async def mock_workflow() -> bool:
        return True

    # Use side_effect to create a fresh coroutine each time
    mock_orchestrator.run_complete_workflow.side_effect = (
        lambda options: mock_workflow()
    )
    with patch(
        "crackerjack.core.workflow_orchestrator.WorkflowOrchestrator",
        return_value=mock_orchestrator,
    ):
        yield mock_orchestrator


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_no_options(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app)
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert isinstance(options, Options)
    assert not options.commit
    assert not options.interactive
    assert not options.update_precommit
    assert not options.no_config_updates
    assert options.publish is None
    assert options.bump is None
    assert not options.verbose
    assert not options.clean
    assert not options.test
    assert not options.create_pr


def test_commit_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-c"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.commit
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--commit"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.commit


def test_interactive_option(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    with patch(
        "crackerjack.cli.interactive.launch_interactive_cli"
    ) as mock_interactive:
        result = runner.invoke(app, ["-i"])
        assert result.exit_code == 0
        mock_interactive.assert_called_once()
        mock_crackerjack_process.run_complete_workflow.assert_not_called()
        mock_interactive.reset_mock()
        result = runner.invoke(app, ["--interactive"])
        assert result.exit_code == 0
        mock_interactive.assert_called_once()
        mock_crackerjack_process.run_complete_workflow.assert_not_called()


def test_update_precommit_option(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-u"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.update_precommit
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--update-precommit"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.update_precommit


def test_verbose_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.verbose
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--verbose"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.verbose


def test_publish_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-p", "patch"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.publish == BumpOption.patch
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--publish", "minor"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.publish == BumpOption.minor
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--publish", "major"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.publish == BumpOption.major
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--publish", "PATCH"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.publish == BumpOption.patch


def test_bump_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-b", "patch"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.bump == BumpOption.patch
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--bump", "minor"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.bump == BumpOption.minor
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--bump", "major"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.bump == BumpOption.major
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--bump", "PATCH"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.bump == BumpOption.patch


def test_clean_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-x"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.clean
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--clean"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.clean


def test_no_config_updates(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-n"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.no_config_updates
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--no-config-updates"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.no_config_updates


def test_test_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-t"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.test
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--test"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.test


def test_multiple_options(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    with patch(
        "crackerjack.cli.interactive.launch_interactive_cli"
    ) as mock_interactive:
        result = runner.invoke(app, ["-c", "-i", "-t", "-x"])
        assert result.exit_code == 0
        mock_interactive.assert_called_once()
        mock_crackerjack_process.run_complete_workflow.assert_not_called()
    result = runner.invoke(app, ["-c", "-t", "-x"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.commit
    assert not options.interactive
    assert options.test
    assert options.clean


def test_create_options() -> None:
    test_options = Options(
        commit=True,
        interactive=True,
        no_config_updates=True,
        update_precommit=True,
        verbose=True,
        publish=BumpOption.patch,
        bump=BumpOption.major,
        clean=True,
        test=True,
        all=BumpOption.minor,
        create_pr=True,
        skip_hooks=True,
    )
    assert test_options.commit
    assert test_options.interactive
    assert test_options.no_config_updates
    assert test_options.update_precommit
    assert test_options.verbose
    assert test_options.publish == BumpOption.patch
    assert test_options.bump == BumpOption.major
    assert test_options.clean
    assert test_options.test
    assert test_options.all == BumpOption.minor
    assert test_options.create_pr
    assert test_options.skip_hooks


def test_conflicting_options(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-p", "patch", "-b", "minor"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.publish == BumpOption.patch
    assert options.bump == BumpOption.minor


def test_all_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-a", "patch"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.all == BumpOption.patch
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--all", "minor"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.all == BumpOption.minor
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--all", "major"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.all == BumpOption.major
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--all", "PATCH"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.all == BumpOption.patch


def test_all_option_with_other_options(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-a", "patch", "-c", "-t"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.all == BumpOption.patch
    assert options.commit
    assert options.test


def test_create_pr_option(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-r"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.create_pr
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--pr"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.create_pr


def test_skip_hooks_option(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-s"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.skip_hooks
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--skip-hooks"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.skip_hooks


def test_benchmark_option(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["--benchmark"])
    assert result.exit_code == 0
    mock_crackerjack_process.run_complete_workflow.assert_called_once()
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.benchmark
    mock_crackerjack_process.run_complete_workflow.reset_mock()
    result = runner.invoke(app, ["--benchmark"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.run_complete_workflow.call_args[0][0]
    assert options.benchmark


def test_options_validation_invalid_bump_option() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        Options(publish="invalid")
    error_msg = str(exc_info.value)
    assert "publish" in error_msg or "Invalid bump option: invalid" in error_msg
    with pytest.raises(ValidationError) as exc_info:
        Options(bump="not_a_valid_option")
    error_msg = str(exc_info.value)
    assert "bump" in error_msg or "Invalid bump option: not_a_valid_option" in error_msg


def test_options_validation_valid_bump_options() -> None:
    options = Options(publish=None, bump=None)
    assert options.publish is None
    assert options.bump is None
    options = Options(publish="patch")
    assert options.publish == BumpOption.patch
    options = Options(bump="minor")
    assert options.bump == BumpOption.minor
