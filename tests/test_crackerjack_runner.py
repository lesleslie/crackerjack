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
        self.doc = kwargs.get("doc", False)
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
        console = MagicMock(spec=Console)

        with (
            patch("crackerjack.crackerjack.CodeCleaner") as mock_cleaner,
            patch("crackerjack.crackerjack.ConfigManager") as mock_config,
            patch("crackerjack.crackerjack.ProjectManager") as mock_project,
        ):
            mock_cleaner_instance = mock_cleaner.return_value
            mock_config_instance = mock_config.return_value
            mock_project_instance = mock_project.return_value

            crackerjack = Crackerjack(
                our_path=tmp_path,
                pkg_path=tmp_path,
                console=console,
                code_cleaner=mock_cleaner_instance,
                config_manager=mock_config_instance,
                project_manager=mock_project_instance,
            )

            yield (
                crackerjack,
                {
                    "console": console,
                    "code_cleaner": mock_cleaner_instance,
                    "config_manager": mock_config_instance,
                    "project_manager": mock_project_instance,
                },
            )


def test_process_with_all_option(
    mock_crackerjack: tuple[Crackerjack, dict[str, MagicMock]],
) -> None:
    crackerjack, mocks = mock_crackerjack

    options = MockOptions(all="minor")

    crackerjack.execute_command = MagicMock(return_value=MagicMock(returncode=0))

    with patch("builtins.input", return_value="Test commit message"):
        with patch.object(Crackerjack, "_run_tests"):
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

    crackerjack.execute_command = MagicMock(return_value=MagicMock(returncode=0))

    with patch("builtins.input", return_value="Test commit message"):
        crackerjack.process(options)

    mocks["code_cleaner"].clean_files.assert_called_with(crackerjack.pkg_dir)


def test_process_with_test_option(
    mock_crackerjack: tuple[Crackerjack, dict[str, MagicMock]],
) -> None:
    crackerjack, _ = mock_crackerjack

    options = MockOptions(test=True)

    crackerjack.execute_command = MagicMock(
        return_value=MagicMock(returncode=0, stdout="All tests passed", stderr="")
    )

    with patch("builtins.input", return_value="Test commit message"):
        with patch.object(Crackerjack, "_run_tests"):
            crackerjack.process(options)
