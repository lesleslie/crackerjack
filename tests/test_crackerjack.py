import os
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from crackerjack.crackerjack import (
    CodeCleaner,
    ConfigManager,
    Crackerjack,
    ProjectManager,
)


class BumpOption(str, Enum):
    micro = "micro"
    minor = "minor"
    major = "major"

    def __str__(self) -> str:
        return self.value


@dataclass
class OptionsForTesting:
    commit: bool = False
    interactive: bool = False
    doc: bool = False
    no_config_updates: bool = False
    publish: BumpOption | None = None
    bump: BumpOption | None = None
    verbose: bool = False
    update_precommit: bool = False
    clean: bool = False
    test: bool = False
    all: BumpOption | None = None
    ai_agent: bool = False
    create_pr: bool = False


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
            if "all" in kwargs and isinstance(kwargs["all"], str):
                kwargs["all"] = BumpOption(kwargs["all"])
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
            all="minor",
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
        with (
            patch.object(Crackerjack, "_update_project") as mock_update_project,
            patch.object(Crackerjack, "_run_tests") as mock_run_tests,
        ):
            mock_update_project.side_effect = lambda opts: mock_console_print(
                "Skipping config updates."
            )
            mock_run_tests.side_effect = lambda opts: mock_console_print(
                "\n\nRunning tests...\n"
            )
            cj = Crackerjack(dry_run=True)
            cj.process(options)
            mock_run_tests.assert_called_once_with(options)
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

    def test_process_with_all_option(
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
        options = options_factory(all="micro", publish="micro")
        with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
            mock_cj_execute.return_value = MagicMock(returncode=0, stdout="Success")
            with patch.object(Crackerjack, "_update_project"):
                with patch.object(Crackerjack, "_clean_project") as mock_clean:
                    with patch.object(Crackerjack, "_run_tests") as mock_tests:
                        with patch.object(
                            Crackerjack, "_publish_project"
                        ) as mock_publish:
                            with patch.object(
                                Crackerjack, "_commit_and_push"
                            ) as mock_commit:
                                cj = Crackerjack(dry_run=True)
                                cj.process(options)
                                mock_clean.assert_called_once()
                                mock_tests.assert_called_once()
                                mock_publish.assert_called_once()
                                mock_commit.assert_called_once()
        mock_console_print.assert_any_call("\n🍺 Crackerjack complete!\n")

    def test_process_with_all_option_sets_flags(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(all=BumpOption.micro)
        cj = Crackerjack(dry_run=True)
        with patch.object(cj, "_setup_package"):
            with patch.object(cj, "_update_project"):
                with patch.object(cj, "_update_precommit"):
                    with patch.object(cj, "_run_interactive_hooks"):
                        with patch.object(cj, "_clean_project") as mock_clean:
                            with patch.object(cj, "_run_tests") as mock_tests:
                                with patch.object(cj, "_bump_version"):
                                    with patch.object(
                                        cj, "_publish_project"
                                    ) as mock_publish:
                                        with patch.object(
                                            cj, "_commit_and_push"
                                        ) as mock_commit:
                                            cj.process(options)
                                            assert options.clean
                                            assert options.test
                                            assert options.publish == options.all
                                            assert options.commit
                                            mock_clean.assert_called_once_with(options)
                                            mock_tests.assert_called_once_with(options)
                                            mock_publish.assert_called_once_with(
                                                options
                                            )
                                            mock_commit.assert_called_once_with(options)

    def test_process_with_all_option_invalid_value(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        with pytest.raises(ValueError):
            options = options_factory(all="invalid_value")
        options = options_factory(all=None)
        cj = Crackerjack(dry_run=True)
        with patch.object(cj, "_setup_package"):
            with patch.object(cj, "_update_project"):
                cj.process(options)
        assert not options.clean
        assert not options.test
        assert not options.commit
        assert options.publish is None

    def test_process_with_all_option_precedence(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(
            all=BumpOption.major,
            publish=BumpOption.micro,
            clean=False,
            test=False,
            commit=False,
        )
        cj = Crackerjack(dry_run=True)
        with patch.object(cj, "_setup_package"):
            with patch.object(cj, "_update_project"):
                with patch.object(cj, "_update_precommit"):
                    with patch.object(cj, "_run_interactive_hooks"):
                        with patch.object(cj, "_clean_project") as mock_clean:
                            with patch.object(cj, "project_manager"):
                                with patch.object(cj, "_run_tests") as mock_tests:
                                    with patch.object(cj, "_bump_version"):
                                        with patch.object(
                                            cj, "_publish_project"
                                        ) as mock_publish:
                                            with patch.object(
                                                cj, "_commit_and_push"
                                            ) as mock_commit:
                                                cj.process(options)
                                                assert options.clean
                                                assert options.test
                                                assert (
                                                    options.publish == BumpOption.major
                                                )
                                                assert options.commit
                                                mock_clean.assert_called_once_with(
                                                    options
                                                )
                                                mock_tests.assert_called_once_with(
                                                    options
                                                )
                                                mock_publish.assert_called_once_with(
                                                    options
                                                )
                                                mock_commit.assert_called_once_with(
                                                    options
                                                )

    def test_process_with_all_option_bump_conflict(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(all=BumpOption.major, bump=BumpOption.minor)
        cj = Crackerjack(dry_run=True)
        with patch.object(cj, "_setup_package"):
            with patch.object(cj, "_update_project"):
                with patch.object(cj, "_update_precommit"):
                    with patch.object(cj, "_run_interactive_hooks"):
                        with patch.object(cj, "_clean_project"):
                            with patch.object(cj, "project_manager"):
                                with patch.object(cj, "_run_tests"):
                                    with patch.object(cj, "_bump_version") as mock_bump:
                                        with patch.object(cj, "_publish_project"):
                                            with patch.object(cj, "_commit_and_push"):
                                                cj.process(options)
                                                assert options.bump == BumpOption.minor
                                                assert (
                                                    options.publish == BumpOption.major
                                                )
                                                mock_bump.assert_called_once_with(
                                                    options
                                                )

    def test_process_implementation_of_all_option(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        cj = Crackerjack(dry_run=True)
        options = MagicMock()
        options.all = BumpOption.micro
        options.clean = False
        options.test = False
        options.publish = None
        options.commit = False
        with patch.object(cj, "_setup_package"):
            with patch.object(cj, "_update_project"):
                with patch.object(cj, "_update_precommit"):
                    with patch.object(cj, "_run_interactive_hooks"):
                        with patch.object(cj, "_clean_project"):
                            with patch.object(cj, "project_manager"):
                                with patch.object(cj, "_run_tests"):
                                    with patch.object(cj, "_bump_version"):
                                        with patch.object(cj, "_publish_project"):
                                            with patch.object(cj, "_commit_and_push"):
                                                cj.process(options)
                                                assert options.clean is True
                                                assert options.test is True
                                                assert (
                                                    options.publish == BumpOption.micro
                                                )
                                                assert options.commit is True

    def test_process_with_failed_tests(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(test=True, no_config_updates=True)
        failed_result = MagicMock(
            returncode=1, stdout="Test failed", stderr="Error in test"
        )
        with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
            mock_cj_execute.return_value = failed_result
            with patch.object(Crackerjack, "_update_project"):
                cj = Crackerjack(dry_run=True)
                with suppress(SystemExit):
                    cj.process(options)
        mock_console_print.assert_any_call("\n\n❌ Tests failed. Please fix errors.\n")

    def test_process_with_failed_build(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(publish="micro", no_config_updates=True)
        with patch("platform.system", return_value="Linux"):
            with patch.object(Crackerjack, "execute_command") as mock_cj_execute:

                def mock_execute_side_effect(*args: t.Any, **kwargs: t.Any):
                    cmd = args[0][0]
                    if cmd == "pdm" and "build" in args[0]:
                        return MagicMock(returncode=1, stdout="", stderr="Build failed")
                    return MagicMock(returncode=0, stdout="Success")

                mock_cj_execute.side_effect = mock_execute_side_effect
                with patch.object(Crackerjack, "_update_project"):
                    with pytest.raises(SystemExit) as excinfo:
                        cj = Crackerjack(dry_run=True)
                        cj.process(options)
                    assert excinfo.value.code == 1
        build_failed_printed = False
        for call in mock_console_print.call_args_list:
            args = call[0]
            if args and isinstance(args[0], str) and ("Build failed" in args[0]):
                build_failed_printed = True
                break
        assert build_failed_printed, "Expected 'Build failed' message was not printed"

    def test_process_with_darwin_platform(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(publish="micro", no_config_updates=True)
        with patch("platform.system", return_value="Darwin"):
            with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
                mock_cj_execute.side_effect = [
                    MagicMock(returncode=0, stdout="Success"),
                    MagicMock(returncode=0, stdout="Success"),
                    MagicMock(returncode=0, stdout="Success"),
                    MagicMock(returncode=0, stdout="Success"),
                ]
                with patch.object(Crackerjack, "_update_project"):
                    cj = Crackerjack(dry_run=True)
                    cj.process(options)
                    mock_cj_execute.assert_any_call(
                        ["pdm", "self", "add", "keyring"],
                        capture_output=True,
                        text=True,
                    )

    def test_process_with_darwin_platform_keyring_failure(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(publish="micro", no_config_updates=True)
        with patch("platform.system", return_value="Darwin"):
            with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
                mock_cj_execute.return_value = MagicMock(
                    returncode=1, stdout="", stderr="Authorization failed"
                )
                with patch.object(Crackerjack, "_update_project"):
                    with pytest.raises(SystemExit) as excinfo:
                        cj = Crackerjack(dry_run=True)
                        cj.process(options)
                    assert excinfo.value.code == 1
        mock_console_print.assert_any_call(
            "\n\nAuthorization failed. Please add your keyring credentials to PDM. Run `pdm self add keyring` and try again.\n\n"
        )

    def test_process_with_commit_input(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(commit=True, no_config_updates=True)
        with patch("builtins.input", return_value="Test commit message"):
            with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
                mock_cj_execute.return_value = MagicMock(returncode=0, stdout="Success")
                with patch.object(Crackerjack, "_update_project"):
                    cj = Crackerjack(dry_run=True)
                    cj.process(options)
                    mock_cj_execute.assert_any_call(
                        [
                            "git",
                            "commit",
                            "-m",
                            "Test commit message",
                            "--no-verify",
                            "--",
                            ".",
                        ]
                    )
                    mock_cj_execute.assert_any_call(["git", "push", "origin", "main"])

    def test_process_with_pdm_install_failure(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(no_config_updates=False)
        with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
            mock_cj_execute.return_value = MagicMock(
                returncode=1, stdout="", stderr="PDM installation failed"
            )
            with patch.object(ProjectManager, "update_pkg_configs"):
                cj = Crackerjack(dry_run=True)
                cj.process(options)
        mock_console_print.assert_any_call(
            "\n\n❌ PDM installation failed. Is PDM is installed? Run `pipx install pdm` and try again.\n\n"
        )

    def test_process_with_crackerjack_project(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        crackerjack_path = tmp_path / "crackerjack"
        crackerjack_path.mkdir(exist_ok=True)
        options = options_factory(update_precommit=True)
        with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
            mock_cj_execute.return_value = MagicMock(returncode=0, stdout="Success")
            cj = Crackerjack(pkg_path=crackerjack_path, dry_run=True)
            with patch.object(cj, "_setup_package"):
                with patch.object(cj, "_update_project"):
                    cj.process(options)
                    mock_cj_execute.assert_any_call(["pre-commit", "autoupdate"])

    def test_process_with_precommit_failure(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(no_config_updates=True)
        with patch.object(ProjectManager, "run_pre_commit") as mock_run_precommit:
            mock_run_precommit.side_effect = SystemExit(1)
            with patch.object(Crackerjack, "_update_project"):
                with pytest.raises(SystemExit) as excinfo:
                    cj = Crackerjack(dry_run=True)
                    cj.process(options)
                assert excinfo.value.code == 1
                mock_run_precommit.assert_called_once()

    def test_process_with_interactive_hooks(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(interactive=True, no_config_updates=True)
        with patch.object(Crackerjack, "_run_interactive_hooks") as mock_run_hooks:
            with patch.object(Crackerjack, "_update_project"):
                cj = Crackerjack(dry_run=True)
                cj.process(options)
                mock_run_hooks.assert_called_once_with(options)

    def test_run_interactive_hooks(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        with patch("crackerjack.crackerjack.interactive_hooks", ["black", "isort"]):
            with patch.object(
                ProjectManager, "run_interactive"
            ) as mock_run_interactive:
                cj = Crackerjack(dry_run=True)
                options = MagicMock()
                options.interactive = True
                cj._run_interactive_hooks(options)
                assert mock_run_interactive.call_count == 2
                mock_run_interactive.assert_any_call("black")
                mock_run_interactive.assert_any_call("isort")

    def test_project_manager_run_interactive_success(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        with patch.object(ProjectManager, "execute_command") as mock_pm_execute:
            mock_pm_execute.return_value = MagicMock(returncode=0, stdout="Success")
            code_cleaner = CodeCleaner(console=Console())
            config_manager = ConfigManager(
                our_path=Path(),
                pkg_path=Path(),
                pkg_name="test",
                console=Console(),
                python_version="3.9",
                dry_run=True,
            )
            pm = ProjectManager(
                our_path=Path(),
                pkg_path=Path(),
                pkg_dir=Path(),
                pkg_name="test",
                console=Console(),
                code_cleaner=code_cleaner,
                config_manager=config_manager,
                dry_run=True,
            )
            pm.run_interactive("black")
            mock_pm_execute.assert_called_once_with(
                ["pre-commit", "run", "black", "--all-files"]
            )

    def test_project_manager_run_interactive_failure_retry(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        with patch.object(ProjectManager, "execute_command") as mock_pm_execute:
            mock_pm_execute.side_effect = [
                MagicMock(returncode=1, stdout="", stderr="Failed"),
                MagicMock(returncode=0, stdout="Success"),
            ]
            with patch("builtins.input", return_value="y"):
                code_cleaner = CodeCleaner(console=Console())
                config_manager = ConfigManager(
                    our_path=Path(),
                    pkg_path=Path(),
                    pkg_name="test",
                    console=Console(),
                    python_version="3.9",
                    dry_run=True,
                )
                pm = ProjectManager(
                    our_path=Path(),
                    pkg_path=Path(),
                    pkg_dir=Path(),
                    pkg_name="test",
                    console=Console(),
                    code_cleaner=code_cleaner,
                    config_manager=config_manager,
                    dry_run=True,
                )
                pm.run_interactive("black")
                assert mock_pm_execute.call_count == 2
                mock_pm_execute.assert_called_with(
                    ["pre-commit", "run", "black", "--all-files"]
                )

    def test_project_manager_run_interactive_failure_exit(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        with patch.object(ProjectManager, "execute_command") as mock_pm_execute:
            mock_pm_execute.return_value = MagicMock(
                returncode=1, stdout="", stderr="Failed"
            )
            with patch("builtins.input", return_value="n"):
                code_cleaner = CodeCleaner(console=Console())
                config_manager = ConfigManager(
                    our_path=Path(),
                    pkg_path=Path(),
                    pkg_name="test",
                    console=Console(),
                    python_version="3.9",
                    dry_run=True,
                )
                pm = ProjectManager(
                    our_path=Path(),
                    pkg_path=Path(),
                    pkg_dir=Path(),
                    pkg_name="test",
                    console=Console(),
                    code_cleaner=code_cleaner,
                    config_manager=config_manager,
                    dry_run=True,
                )
                with pytest.raises(SystemExit) as excinfo:
                    pm.run_interactive("black")
                assert excinfo.value.code == 1
                mock_pm_execute.assert_called_once_with(
                    ["pre-commit", "run", "black", "--all-files"]
                )

    def test_config_manager_swap_package_name(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        config_manager = ConfigManager(
            our_path=Path(),
            pkg_path=Path(),
            pkg_name="test_package",
            console=Console(),
            python_version="3.9",
            dry_run=True,
        )
        result_str = config_manager.swap_package_name(
            "replace crackerjack with test_package"
        )
        assert result_str == "replace test_package with test_package"
        result_list = config_manager.swap_package_name(
            ["item1", "crackerjack", "item3"]
        )
        assert "crackerjack" not in result_list
        assert "test_package" in result_list
        assert len(result_list) == 3

    def test_config_manager_update_python_version(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        config_manager = ConfigManager(
            our_path=Path(),
            pkg_path=Path(),
            pkg_name="test_package",
            console=Console(),
            python_version="3.9",
            dry_run=True,
        )
        our_toml = {"project": {"requires-python": ">=3.8"}}
        pkg_toml = {
            "project": {
                "classifiers": [
                    "Programming Language :: Python :: 3.8",
                    "Programming Language :: Python :: 3.7",
                ]
            }
        }
        config_manager._update_python_version(our_toml, pkg_toml)
        assert (
            "Programming Language :: Python :: 3.9"
            in pkg_toml["project"]["classifiers"]
        )
        assert (
            "Programming Language :: Python :: 3.8"
            not in pkg_toml["project"]["classifiers"]
        )
        assert (
            "Programming Language :: Python :: 3.7"
            not in pkg_toml["project"]["classifiers"]
        )
        assert pkg_toml["project"]["requires-python"] == ">=3.8"

    def test_code_cleaner_clean_files(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        py_file = test_dir / "test.py"
        py_file.write_text("def test_func():\n    pass\n")
        non_py_file = test_dir / "test.txt"
        non_py_file.write_text("This is a text file")
        with patch("crackerjack.crackerjack.CodeCleaner.clean_file") as mock_clean_file:
            code_cleaner = CodeCleaner(console=Console())
            code_cleaner.clean_files(test_dir)
            mock_clean_file.assert_called_once_with(py_file)

    def test_code_cleaner_remove_docstrings(self) -> None:
        from rich.console import Console
        from crackerjack.crackerjack import CodeCleaner

        code_cleaner = CodeCleaner(console=Console())
        code_with_docstrings = (
            Path(__file__).parent / "data" / "docstrings_sample.txt"
        ).read_text()
        cleaned_code = code_cleaner.remove_docstrings(code_with_docstrings)
        print(cleaned_code)
        assert '"""This is a docstring."""' not in cleaned_code, (
            f"Got: {cleaned_code!r}"
        )
        assert '"""Class docstring."""' not in cleaned_code, f"Got: {cleaned_code!r}"
        assert "'''Method docstring.'''" not in cleaned_code, f"Got: {cleaned_code!r}"
        assert "This is a multi-line docstring." not in cleaned_code, (
            f"Got: {cleaned_code!r}"
        )

    def test_code_cleaner_remove_line_comments(self) -> None:
        from pathlib import Path

        from rich.console import Console
        from crackerjack.crackerjack import CodeCleaner

        code_cleaner = CodeCleaner(console=Console())
        code_with_comments = (
            (Path(__file__).parent / "data" / "comments_sample.txt")
            .read_text()
            .rstrip()
        )
        cleaned_code = code_cleaner.remove_line_comments(code_with_comments)
        expected_cleaned = (
            (Path(__file__).parent / "data" / "expected_comments_sample.txt")
            .read_text()
            .rstrip()
        )
        assert cleaned_code == expected_cleaned, (
            f"Cleaned code does not match expected.\nExpected:\n{expected_cleaned}\nGot:\n{cleaned_code}"
        )

    def test_code_cleaner_remove_extra_whitespace(self) -> None:
        from rich.console import Console
        from crackerjack.crackerjack import CodeCleaner

        code_cleaner = CodeCleaner(console=Console())
        code_with_whitespace = (
            "def test_func():\n        return True\n    \n    \n    x = 1\n    "
        )
        cleaned_code = code_cleaner.remove_extra_whitespace(code_with_whitespace)
        assert "def test_func():" in cleaned_code, f"Got: {cleaned_code!r}"
        assert "return True" in cleaned_code, f"Got: {cleaned_code!r}"
        assert "x = 1" in cleaned_code, f"Got: {cleaned_code!r}"

    def test_code_cleaner_reformat_code_success(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        code_cleaner = CodeCleaner(console=Console())
        code_to_format = "def test_func():\n    return True\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch("pathlib.Path.write_text"):
                with patch(
                    "pathlib.Path.read_text",
                    return_value="def test_func():\n    return True\n",
                ):
                    formatted_code = code_cleaner.reformat_code(code_to_format)
                    assert formatted_code == "def test_func():\n    return True\n"
                    mock_run.assert_called_once()

    def test_code_cleaner_reformat_code_failure(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        from rich.console import Console

        console = Console()

        code_cleaner = CodeCleaner(console=console)
        code_to_format = "def test_func():\n    return True\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Formatting error")

            with patch("pathlib.Path.write_text"):
                with patch.object(console, "print") as mock_console_print_method:
                    formatted_code = code_cleaner.reformat_code(code_to_format)

                    assert formatted_code == code_to_format

                    mock_run.assert_called_once()

                    mock_console_print_method.assert_any_call(
                        "Ruff formatting failed: Formatting error"
                    )

    def test_config_manager_is_crackerjack_project(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        crackerjack_path = tmp_path / "crackerjack"
        crackerjack_path.mkdir(exist_ok=True)
        config_manager = ConfigManager(
            our_path=Path(),
            pkg_path=crackerjack_path,
            pkg_name="crackerjack",
            console=Console(),
            python_version="3.9",
            dry_run=True,
        )
        assert config_manager._is_crackerjack_project()
        other_path = tmp_path / "other_project"
        other_path.mkdir(exist_ok=True)
        config_manager = ConfigManager(
            our_path=Path(),
            pkg_path=other_path,
            pkg_name="other_project",
            console=Console(),
            python_version="3.9",
            dry_run=True,
        )
        assert not config_manager._is_crackerjack_project()

    def test_config_manager_handle_crackerjack_project(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        our_toml_path = tmp_path / "our_pyproject.toml"
        pkg_toml_path = tmp_path / "pkg_pyproject.toml"
        our_toml_path.write_text("[project]\nname = 'our_project'")
        pkg_toml_path.write_text("[project]\nname = 'pkg_project'")
        config_manager = ConfigManager(
            our_path=Path(),
            pkg_path=tmp_path / "crackerjack",
            pkg_name="crackerjack",
            console=Console(),
            python_version="3.9",
            dry_run=True,
        )
        config_manager.our_toml_path = our_toml_path
        config_manager.pkg_toml_path = pkg_toml_path
        config_manager._handle_crackerjack_project()
        assert our_toml_path.read_text() == "[project]\nname = 'pkg_project'"

    def test_config_manager_update_tool_settings(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        config_manager = ConfigManager(
            our_path=Path(),
            pkg_path=Path(),
            pkg_name="test_package",
            console=Console(),
            python_version="3.9",
            dry_run=True,
        )
        our_toml = {
            "tool": {
                "ruff": {
                    "target-version": "py39",
                    "exclude": ["crackerjack/excluded.py", "crackerjack"],
                    "nested": {"option": "crackerjack value"},
                },
                "pytest": {"testpaths": ["tests", "crackerjack/tests", "crackerjack"]},
            }
        }
        pkg_toml = {"tool": {"ruff": {"exclude": ["existing.py"]}}}
        config_manager._update_tool_settings(our_toml, pkg_toml)
        assert pkg_toml["tool"]["ruff"]["target-version"] == "py39"
        nested = pkg_toml["tool"]["ruff"].get("nested")
        from typing import cast

        nested_dict = cast(dict[str, t.Any], nested)
        assert "option" in nested_dict, "option key not found in nested"
        assert nested_dict["option"] == "test_package value"
        assert "pytest" in pkg_toml["tool"], "pytest key not found in pkg_toml['tool']"
        assert "testpaths" in pkg_toml["tool"]["pytest"], (
            "testpaths key not found in pytest section"
        )
        assert "tests" in pkg_toml["tool"]["pytest"]["testpaths"]

    def test_config_manager_copy_configs(
        self, mock_execute: MagicMock, mock_console_print: MagicMock, tmp_path: Path
    ) -> None:
        our_path = tmp_path / "our_path"
        pkg_path = tmp_path / "pkg_path"
        our_path.mkdir()
        pkg_path.mkdir()
        config_files = [".gitignore", ".pre-commit-config.yaml"]
        for config in config_files:
            (our_path / config).write_text(f"content for {config} with crackerjack")
        config_manager = ConfigManager(
            our_path=our_path,
            pkg_path=pkg_path,
            pkg_name="test_package",
            console=Console(),
            python_version="3.9",
            dry_run=True,
        )
        with patch.object(ConfigManager, "execute_command") as mock_cm_execute:
            with patch("crackerjack.crackerjack.config_files", config_files):
                config_manager.copy_configs()
                for config in config_files:
                    assert (pkg_path / config).exists()
                    if config != ".gitignore":
                        assert "crackerjack" not in (pkg_path / config).read_text()
                        assert "test_package" in (pkg_path / config).read_text()
                    mock_cm_execute.assert_any_call(["git", "add", config])
