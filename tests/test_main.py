import typing as t
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner
from crackerjack.__main__ import BumpOption, Options, app, create_options


@pytest.fixture
def mock_crackerjack_process() -> t.Generator[MagicMock, None, None]:
    with patch("crackerjack.__main__.crackerjack_it") as mock_process:
        yield mock_process


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_no_options(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app)
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert isinstance(options, Options)
    assert not options.commit
    assert not options.interactive
    assert not options.doc
    assert not options.update_precommit
    assert not options.no_config_updates
    assert options.publish is None
    assert options.bump is None
    assert not options.verbose
    assert not options.clean
    assert not options.test


def test_commit_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-c"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.commit
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--commit"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.commit


def test_interactive_option(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-i"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.interactive
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--interactive"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.interactive


def test_doc_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-d"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.doc
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--doc"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.doc


def test_update_precommit_option(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-u"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.update_precommit
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--update-precommit"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.update_precommit


def test_verbose_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.verbose
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--verbose"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.verbose


def test_publish_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-p", "micro"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.publish == BumpOption.micro
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--publish", "minor"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.publish == BumpOption.minor
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--publish", "major"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.publish == BumpOption.major
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--publish", "MICRO"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.publish == BumpOption.micro


def test_bump_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-b", "micro"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.bump == BumpOption.micro
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--bump", "minor"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.bump == BumpOption.minor
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--bump", "major"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.bump == BumpOption.major
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--bump", "MICRO"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.bump == BumpOption.micro


def test_clean_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-x"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.clean
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--clean"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.clean


def test_no_config_updates(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-n"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.no_config_updates
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--no-config-updates"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.no_config_updates


def test_test_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-t"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.test
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--test"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.test


def test_multiple_options(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-c", "-i", "-d", "-t", "-x"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.commit
    assert options.interactive
    assert options.doc
    assert options.test
    assert options.clean


def test_create_options() -> None:
    test_options = create_options(
        commit=True,
        interactive=True,
        doc=True,
        no_config_updates=True,
        update_precommit=True,
        verbose=True,
        publish=BumpOption.micro,
        bump=BumpOption.major,
        clean=True,
        test=True,
        all=BumpOption.minor,
    )
    assert test_options.commit
    assert test_options.interactive
    assert test_options.doc
    assert test_options.no_config_updates
    assert test_options.update_precommit
    assert test_options.verbose
    assert test_options.publish == BumpOption.micro
    assert test_options.bump == BumpOption.major
    assert test_options.clean
    assert test_options.test
    assert test_options.all == BumpOption.minor


def test_conflicting_options(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-p", "micro", "-b", "minor"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.publish == BumpOption.micro
    assert options.bump == BumpOption.minor


def test_all_option(runner: CliRunner, mock_crackerjack_process: MagicMock) -> None:
    result = runner.invoke(app, ["-a", "micro"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.all == BumpOption.micro
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--all", "minor"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.all == BumpOption.minor
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--all", "major"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.all == BumpOption.major
    mock_crackerjack_process.reset_mock()
    result = runner.invoke(app, ["--all", "MICRO"])
    assert result.exit_code == 0
    options = mock_crackerjack_process.call_args[0][0]
    assert options.all == BumpOption.micro


def test_all_option_with_other_options(
    runner: CliRunner, mock_crackerjack_process: MagicMock
) -> None:
    result = runner.invoke(app, ["-a", "micro", "-c", "-t"])
    assert result.exit_code == 0
    mock_crackerjack_process.assert_called_once()
    options = mock_crackerjack_process.call_args[0][0]
    assert options.all == BumpOption.micro
    assert options.commit
    assert options.test
