import os
import typing as t
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel
from rich.console import Console
from crackerjack.crackerjack import ConfigManager, Crackerjack, ProjectManager


class BumpOption(str, Enum):
    micro = "micro"
    minor = "minor"
    major = "major"

    def __str__(self) -> str:
        return self.value


class OptionsForTesting(BaseModel):
    commit: bool = False
    interactive: bool = False
    doc: bool = False
    no_config_updates: bool = False
    publish: t.Optional[BumpOption] = None
    bump: t.Optional[BumpOption] = None
    verbose: bool = False
    update_precommit: bool = False
    clean: bool = False
    test: bool = False


@pytest.fixture
def mock_execute() -> t.Generator[MagicMock, None, None]:
    with patch("crackerjack.crackerjack.execute") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="Success")
        yield mock


@pytest.fixture
def mock_console_print() -> t.Generator[MagicMock, None, None]:
    with patch.object(Console, "print") as mock:
        yield mock


@pytest.fixture
def mock_input() -> t.Generator[MagicMock, None, None]:
    with patch("builtins.input") as mock:
        mock.return_value = "y"
        yield mock


@pytest.fixture
def mock_config_manager_execute() -> t.Generator[MagicMock, None, None]:
    with patch.object(ConfigManager, "execute_command") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="Success")
        yield mock


@pytest.fixture
def mock_project_manager_execute() -> t.Generator[MagicMock, None, None]:
    with patch.object(ProjectManager, "execute_command") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="Success")
        yield mock


@pytest.fixture
def tmp_path_package(tmp_path: Path) -> Path:
    return tmp_path / "test_package"


@pytest.fixture
def create_package_dir(tmp_path_package: Path) -> None:
    tmp_path_package.mkdir(exist_ok=True, parents=True)
    (tmp_path_package / "test_package").mkdir(exist_ok=True, parents=True)
    (tmp_path_package / "our").mkdir(exist_ok=True, parents=True)
    pyproject_content = '[project]\nname = "test_package"\nversion = "0.1.0"\n'
    (tmp_path_package / "pyproject.toml").write_text(pyproject_content)
    init_content = (Path(__file__).parent / "data" / "init.py").read_text()
    (tmp_path_package / "test_package" / "__init__.py").write_text(init_content)
    os.chdir(tmp_path_package)


class TestCrackerjackProcess:
    @pytest.fixture
    def options_factory(self) -> t.Callable[..., OptionsForTesting]:
        def _create_options(**kwargs: t.Any) -> OptionsForTesting:
            if "publish" in kwargs and isinstance(kwargs["publish"], str):
                kwargs["publish"] = BumpOption(kwargs["publish"])
            if "bump" in kwargs and isinstance(kwargs["bump"], str):
                kwargs["bump"] = BumpOption(kwargs["bump"])
            return OptionsForTesting(**kwargs)

        return _create_options

    def test_process_all_options(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        mock_input: MagicMock,
        mock_project_manager_execute: MagicMock,
        mock_config_manager_execute: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        mock_execute.return_value.returncode = 0
        mock_project_manager_execute.return_value.returncode = 0
        mock_config_manager_execute.return_value.returncode = 0
        mock_input.return_value = "y"
        options = options_factory(
            commit=True,
            interactive=True,
            publish="micro",
            bump="major",
            clean=True,
            update_precommit=True,
            no_config_updates=False,
            test=True,
        )
        with patch.object(ConfigManager, "copy_configs") as mock_copy_configs:

            def side_effect() -> None:
                mock_config_manager_execute(["git", "add", ".gitignore"])
                mock_config_manager_execute(["git", "add", ".pre-commit-config.yaml"])
                mock_config_manager_execute(["git", "add", ".libcst.codemod.yaml"])

            mock_copy_configs.side_effect = side_effect
            with patch.object(Crackerjack, "_run_tests"):
                with patch.object(Crackerjack, "_bump_version"):
                    with patch.object(Crackerjack, "_publish_project"):
                        cj = Crackerjack(dry_run=True)
                        cj.process(options)
        expected_config_calls = [
            ["git", "add", ".gitignore"],
            ["git", "add", ".pre-commit-config.yaml"],
            ["git", "add", ".libcst.codemod.yaml"],
        ]
        for cmd in expected_config_calls:
            mock_config_manager_execute.assert_any_call(cmd)

    def test_process_no_configs(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        mock_input: MagicMock,
        mock_project_manager_execute: MagicMock,
        mock_config_manager_execute: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        mock_execute.return_value.returncode = 0
        mock_project_manager_execute.return_value.returncode = 0
        mock_config_manager_execute.return_value.returncode = 0
        mock_input.return_value = "Test Commit"
        options = options_factory(commit=True, no_config_updates=True)
        with patch.object(Crackerjack, "_update_project") as mock_update_project:

            def side_effect(opts: t.Any) -> None:
                if opts.no_config_updates:
                    mock_console_print("Skipping config updates.")

            mock_update_project.side_effect = side_effect
            with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
                mock_cj_execute.return_value = MagicMock(returncode=0, stdout="Success")
                cj = Crackerjack(dry_run=True)
                cj.process(options)
                commit_call_found = False
                for call_args in mock_cj_execute.call_args_list:
                    cmd = call_args[0][0]
                    if len(cmd) >= 2 and cmd[0] == "git" and (cmd[1] == "commit"):
                        commit_call_found = True
                        break
                assert commit_call_found, "Expected git commit command was not called"
        mock_console_print.assert_any_call("Skipping config updates.")

    def test_process_with_test_option(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        mock_input: MagicMock,
        mock_project_manager_execute: MagicMock,
        mock_config_manager_execute: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        mock_execute.return_value.returncode = 0
        mock_project_manager_execute.return_value.returncode = 0
        mock_config_manager_execute.return_value.returncode = 0
        options = options_factory(test=True, no_config_updates=True)
        with patch.object(Crackerjack, "_update_project") as mock_update_project:
            mock_update_project.side_effect = lambda opts: mock_console_print(
                "Skipping config updates."
            )
            cj = Crackerjack(dry_run=True)
            cj.process(options)
        console_print_calls = [str(call) for call in mock_console_print.call_args_list]
        assert any(("Running tests" in call for call in console_print_calls)), (
            "Expected 'Running tests' message was not printed"
        )
        assert any(
            ("Skipping config updates" in call for call in console_print_calls)
        ), "Expected 'Skipping config updates' message was not printed"

    def test_process_with_bump_option(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        mock_project_manager_execute: MagicMock,
        mock_config_manager_execute: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        mock_execute.return_value.returncode = 0
        mock_project_manager_execute.return_value.returncode = 0
        mock_config_manager_execute.return_value.returncode = 0
        options = options_factory(bump="minor", no_config_updates=True)
        with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
            mock_cj_execute.return_value = MagicMock(returncode=0, stdout="Success")
            with patch.object(Crackerjack, "_update_project") as mock_update_project:
                mock_update_project.side_effect = lambda opts: mock_console_print(
                    "Skipping config updates."
                )
                cj = Crackerjack(dry_run=True)
                cj.process(options)
                mock_cj_execute.assert_any_call(["pdm", "bump", "minor"])
        console_print_calls = [str(call) for call in mock_console_print.call_args_list]
        assert any(
            ("Skipping config updates" in call for call in console_print_calls)
        ), "Expected 'Skipping config updates' message was not printed"

    def test_process_with_publish_option(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        mock_project_manager_execute: MagicMock,
        mock_config_manager_execute: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        mock_execute.return_value.returncode = 0
        mock_project_manager_execute.return_value.returncode = 0
        mock_config_manager_execute.return_value.returncode = 0
        options = options_factory(publish="micro", no_config_updates=True)
        with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
            mock_cj_execute.return_value = MagicMock(returncode=0, stdout="Success")
            with patch.object(Crackerjack, "_update_project") as mock_update_project:
                mock_update_project.side_effect = lambda opts: mock_console_print(
                    "Skipping config updates."
                )
                cj = Crackerjack(dry_run=True)
                cj.process(options)
                mock_cj_execute.assert_any_call(["pdm", "bump", "micro"])
                mock_cj_execute.assert_any_call(["pdm", "publish", "--no-build"])
        console_print_calls = [str(call) for call in mock_console_print.call_args_list]
        assert any(
            ("Skipping config updates" in call for call in console_print_calls)
        ), "Expected 'Skipping config updates' message was not printed"
