import tempfile
import typing as t
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from crackerjack import create_crackerjack_runner
from crackerjack.crackerjack import Crackerjack


class MockOptions:
    def __init__(self, **kwargs: t.Any) -> None:
        self.commit = kwargs.get("commit", False)
        self.interactive = kwargs.get("interactive", False)
        self.no_config_updates = kwargs.get("no_config_updates", False)
        self.verbose = kwargs.get("verbose", False)
        self.update_precommit = kwargs.get("update_precommit", False)
        self.clean = kwargs.get("clean", False)
        self.test = kwargs.get("test", False)
        self.publish = kwargs.get("publish")
        self.bump = kwargs.get("bump")
        self.all = kwargs.get("all")
        self.ai_agent = kwargs.get("ai_agent", False)
        self.create_pr = kwargs.get("create_pr", False)
        self.skip_hooks = kwargs.get("skip_hooks", False)
        self.benchmark = kwargs.get("benchmark", False)
        self.benchmark_regression = kwargs.get("benchmark_regression", False)
        self.benchmark_regression_threshold = kwargs.get(
            "benchmark_regression_threshold", 5.0
        )
        self.test_workers = kwargs.get("test_workers", 0)
        self.test_timeout = kwargs.get("test_timeout", 0)


def test_create_crackerjack_runner() -> None:
    console = Console(force_terminal=False)
    runner = create_crackerjack_runner(console=console)
    assert isinstance(runner, Crackerjack)
    assert runner.console == console
    assert runner.our_path == Path(__file__).parent.parent / "crackerjack"
    assert runner.pkg_path == Path.cwd()
    assert not runner.dry_run


@pytest.fixture
def mock_crackerjack():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        mock_console = MagicMock(spec=Console)
        mock_console.print = MagicMock()
        with (
            patch("crackerjack.crackerjack.CodeCleaner") as mock_cleaner_cls,
            patch("crackerjack.crackerjack.ConfigManager") as mock_config_cls,
            patch("crackerjack.crackerjack.ProjectManager") as mock_project_cls,
            patch.object(Crackerjack, "execute_command") as mock_execute_command,
        ):
            mock_cleaner = MagicMock()
            mock_config = MagicMock()
            mock_project = MagicMock()
            mock_cleaner_cls.return_value = mock_cleaner
            mock_config_cls.return_value = mock_config
            mock_project_cls.return_value = mock_project
            mock_execute_command.return_value = MagicMock(returncode=0)
            crackerjack = Crackerjack(
                our_path=tmp_path, pkg_path=tmp_path, console=mock_console
            )
            mock_cleaner.console = mock_console
            mock_config.console = mock_console
            mock_project.console = mock_console
            mock_project.run_pre_commit.return_value = None
            yield (
                crackerjack,
                {
                    "console": mock_console,
                    "code_cleaner": mock_cleaner,
                    "config_manager": mock_config,
                    "project_manager": mock_project,
                    "execute_command": mock_execute_command,
                },
            )


def test_process_with_all_option(
    mock_crackerjack: tuple[Crackerjack, dict[str, MagicMock]],
) -> None:
    crackerjack, mocks = mock_crackerjack
    options = MockOptions(all="minor")
    with patch.object(Crackerjack, "_run_tests"):
        with patch("rich.prompt.Confirm.ask", return_value=True):
            with patch("builtins.input", return_value="Test commit message"):
                crackerjack.process(options)
    assert options.clean is True
    assert options.test is True
    assert options.publish == "minor"
    assert options.commit is True
    mocks["project_manager"].run_pre_commit.assert_called_once()


def test_process_with_clean_option(
    mock_crackerjack: tuple[Crackerjack, dict[str, MagicMock]],
) -> None:
    crackerjack, mocks = mock_crackerjack
    options = MockOptions(clean=True)
    crackerjack.pkg_dir = crackerjack.pkg_path / "test_pkg"
    with patch("builtins.input", return_value="Test commit message"):
        crackerjack.process(options)
    mocks["code_cleaner"].clean_files.assert_called_with(crackerjack.pkg_dir)


def test_process_with_test_option(
    mock_crackerjack: tuple[Crackerjack, dict[str, MagicMock]],
) -> None:
    crackerjack, _ = mock_crackerjack
    options = MockOptions(test=True)
    with patch.object(Crackerjack, "_run_tests") as mock_run_tests:
        with patch("builtins.input", return_value="Test commit message"):
            crackerjack.process(options)
    mock_run_tests.assert_called_once_with(options)


def test_process_with_test_and_skip_hooks_options(
    mock_crackerjack: tuple[Crackerjack, dict[str, MagicMock]],
) -> None:
    crackerjack, mocks = mock_crackerjack
    options = MockOptions(test=True, skip_hooks=True)
    with patch.object(Crackerjack, "_run_tests") as mock_run_tests:
        with patch("builtins.input", return_value="Test commit message"):
            crackerjack.process(options)
    mock_run_tests.assert_called_once_with(options)
    mocks["project_manager"].run_pre_commit.assert_not_called()
    assert any(
        "Skipping pre-commit hooks" in str(call)
        for call in mocks["console"].print.call_args_list
    )
