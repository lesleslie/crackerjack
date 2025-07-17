import os
import subprocess
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
    OptionsProtocol,
    ProjectManager,
    SessionTracker,
    TaskStatus,
)


class BumpOption(str, Enum):
    patch = "patch"
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
    update_docs: bool = False
    force_update_docs: bool = False
    clean: bool = False
    test: bool = False
    benchmark: bool = False
    benchmark_regression: bool = False
    benchmark_regression_threshold: float = 5.0
    test_workers: int = 0
    test_timeout: int = 0
    all: BumpOption | None = None
    ai_agent: bool = False
    create_pr: bool = False
    skip_hooks: bool = False
    comprehensive: bool = False
    async_mode: bool = False
    track_progress: bool = False
    resume_from: str | None = None
    progress_file: str | None = None
    compress_docs: bool = False


@pytest.fixture
def mock_execute() -> t.Generator[MagicMock]:
    with patch("crackerjack.crackerjack.execute") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="Success")
        yield mock


@pytest.fixture
def mock_console_print() -> t.Generator[MagicMock]:
    with patch.object(Console, "print") as mock:
        yield mock


@pytest.fixture
def mock_input() -> t.Generator[MagicMock]:
    with patch("builtins.input") as mock:
        mock.return_value = "y"
        yield mock


@pytest.fixture
def mock_config_manager_execute() -> t.Generator[MagicMock]:
    with patch.object(ConfigManager, "execute_command") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="Success")
        yield mock


@pytest.fixture
def mock_project_manager_execute() -> t.Generator[MagicMock]:
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
            publish="patch",
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

            def side_effect(opts: OptionsProtocol) -> None:
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
        assert any("Running tests" in call for call in console_print_calls), (
            "Expected 'Running tests' message was not printed"
        )
        assert any("Skipping config updates" in call for call in console_print_calls), (
            "Expected 'Skipping config updates' message was not printed"
        )

    def test_process_with_skip_hooks_option(
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
        options = options_factory(test=True, skip_hooks=True)
        with (
            patch.object(Crackerjack, "_run_tests") as mock_run_tests,
            patch.object(ProjectManager, "run_pre_commit") as mock_run_pre_commit,
        ):
            mock_run_tests.side_effect = lambda opts: mock_console_print(
                "\n\nRunning tests...\n"
            )
            cj = Crackerjack(dry_run=True)
            cj.process(options)
            mock_run_pre_commit.assert_not_called()
            mock_run_tests.assert_called_once_with(options)
        console_print_calls = [str(call) for call in mock_console_print.call_args_list]
        assert any("Running tests" in call for call in console_print_calls), (
            "Expected 'Running tests' message was not printed"
        )
        assert any(
            "Skipping pre-commit hooks" in call for call in console_print_calls
        ), "Expected 'Skipping pre-commit hooks' message was not printed"

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
        with patch("rich.prompt.Confirm.ask", return_value=True):
            with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
                mock_cj_execute.return_value = MagicMock(returncode=0, stdout="Success")
                with patch.object(
                    Crackerjack, "_update_project"
                ) as mock_update_project:
                    mock_update_project.side_effect = lambda opts: mock_console_print(
                        "Skipping config updates."
                    )
                    cj = Crackerjack(dry_run=True)
                    cj.process(options)
                    mock_cj_execute.assert_any_call(
                        ["uv", "version", "--bump", "minor"]
                    )
            console_print_calls = [
                str(call) for call in mock_console_print.call_args_list
            ]
        assert any("Skipping config updates" in call for call in console_print_calls), (
            "Expected 'Skipping config updates' message was not printed"
        )

    def test_bump_version_confirmation_minor_accepted(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(bump="minor", no_config_updates=True)
        cj = Crackerjack(dry_run=True)
        with patch("rich.prompt.Confirm.ask", return_value=True) as mock_confirm:
            with patch.object(Crackerjack, "execute_command") as mock_exec:
                mock_exec.return_value = MagicMock(returncode=0)
                cj._bump_version(options)
                mock_confirm.assert_called_once_with(
                    "Are you sure you want to bump the minor version?", default=False
                )
                mock_exec.assert_called_once_with(["uv", "version", "--bump", "minor"])

    def test_bump_version_confirmation_minor_declined(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(bump="minor", no_config_updates=True)
        cj = Crackerjack(dry_run=True)
        with patch("rich.prompt.Confirm.ask", return_value=False) as mock_confirm:
            with patch.object(Crackerjack, "execute_command") as mock_exec:
                mock_exec.return_value = MagicMock(returncode=0)
                cj._bump_version(options)
                mock_confirm.assert_called_once_with(
                    "Are you sure you want to bump the minor version?", default=False
                )
                mock_exec.assert_not_called()

    def test_bump_version_confirmation_major(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(bump="major", no_config_updates=True)
        cj = Crackerjack(dry_run=True)
        with patch("rich.prompt.Confirm.ask", return_value=True) as mock_confirm:
            with patch.object(Crackerjack, "execute_command") as mock_exec:
                mock_exec.return_value = MagicMock(returncode=0)
                cj._bump_version(options)
                mock_confirm.assert_called_once_with(
                    "Are you sure you want to bump the major version?", default=False
                )
                mock_exec.assert_called_once_with(["uv", "version", "--bump", "major"])

    def test_bump_version_no_confirmation_patch(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(bump="patch", no_config_updates=True)
        cj = Crackerjack(dry_run=True)
        with patch("rich.prompt.Confirm.ask") as mock_confirm:
            with patch.object(Crackerjack, "execute_command") as mock_exec:
                mock_exec.return_value = MagicMock(returncode=0)
                cj._bump_version(options)
                mock_confirm.assert_not_called()
                mock_exec.assert_called_once_with(["uv", "version", "--bump", "patch"])

    def test_prepare_pytest_command_ai_agent_mode(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(test=True, ai_agent=True, no_config_updates=True)
        pytest_command = (_cj := Crackerjack(dry_run=True))._prepare_pytest_command(
            options
        )
        assert "--junitxml=test-results.xml" in pytest_command
        assert "--cov-report=json:coverage.json" in pytest_command
        assert "--quiet" in pytest_command
        assert "--tb=short" in pytest_command
        assert "--no-header" in pytest_command

    def test_prepare_pytest_command_ai_agent_with_benchmark(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(
            test=True, ai_agent=True, benchmark=True, no_config_updates=True
        )
        pytest_command = (_cj := Crackerjack(dry_run=True))._prepare_pytest_command(
            options
        )
        assert "--junitxml=test-results.xml" in pytest_command
        assert "--cov-report=json:coverage.json" in pytest_command
        assert "--benchmark-json=benchmark.json" in pytest_command
        assert "--benchmark" in pytest_command
        assert "--benchmark-autosave" in pytest_command

    def test_prepare_pytest_command_normal_mode(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(test=True, ai_agent=False, no_config_updates=True)
        pytest_command = (_cj := Crackerjack(dry_run=True))._prepare_pytest_command(
            options
        )
        assert "--junitxml=test-results.xml" not in pytest_command
        assert "--cov-report=json:coverage.json" not in pytest_command
        assert "--benchmark-json=benchmark.json" not in pytest_command
        assert "--quiet" not in pytest_command
        assert "--capture=fd" in pytest_command
        assert "--disable-warnings" in pytest_command
        assert "--durations=0" in pytest_command

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
        options = options_factory(publish="patch", no_config_updates=True)
        with (
            patch.object(Crackerjack, "_bump_version") as mock_bump,
            patch.object(Crackerjack, "_publish_project") as mock_publish,
            patch.object(Crackerjack, "_update_project") as mock_update,
        ):
            cj = Crackerjack(dry_run=True)
            cj.process(options)
            mock_bump.assert_called_once_with(options)
            mock_publish.assert_called_once_with(options)
            mock_update.assert_called_once_with(options)

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
        options = options_factory(all="patch", publish="patch")
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
        mock_console_print.assert_any_call("-" * 80 + "\n")

    def test_process_with_all_option_sets_flags(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(all=BumpOption.patch)
        cj = Crackerjack(dry_run=True)
        with patch.object(cj, "_setup_package"):
            with patch.object(cj, "_update_project"):
                with patch.object(cj, "_update_precommit"):
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
                                        mock_publish.assert_called_once_with(options)
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
            publish=BumpOption.patch,
            clean=False,
            test=False,
            commit=False,
        )
        cj = Crackerjack(dry_run=True)
        with patch.object(cj, "_setup_package"):
            with patch.object(cj, "_update_project"):
                with patch.object(cj, "_update_precommit"):
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
                                            assert options.publish == BumpOption.major
                                            assert options.commit
                                            mock_clean.assert_called_once_with(options)
                                            mock_tests.assert_called_once_with(options)
                                            mock_publish.assert_called_once_with(
                                                options
                                            )
                                            mock_commit.assert_called_once_with(options)

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
                    with patch.object(cj, "_clean_project"):
                        with patch.object(cj, "project_manager"):
                            with patch.object(cj, "_run_tests"):
                                with patch.object(cj, "_bump_version") as mock_bump:
                                    with patch.object(cj, "_publish_project"):
                                        with patch.object(cj, "_commit_and_push"):
                                            cj.process(options)
                                            assert options.bump == BumpOption.minor
                                            assert options.publish == BumpOption.major
                                            mock_bump.assert_called_once_with(options)

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
        options.all = BumpOption.patch
        options.clean = False
        options.test = False
        options.publish = None
        options.commit = False
        with patch.object(cj, "_setup_package"):
            with patch.object(cj, "_update_project"):
                with patch.object(cj, "_update_precommit"):
                    with patch.object(cj, "_clean_project"):
                        with patch.object(cj, "project_manager"):
                            with patch.object(cj, "_run_tests"):
                                with patch.object(cj, "_bump_version"):
                                    with patch.object(cj, "_publish_project"):
                                        with patch.object(cj, "_commit_and_push"):
                                            cj.process(options)
                                            assert options.clean is True
                                            assert options.test is True
                                            assert options.publish == BumpOption.patch
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
        mock_console_print.assert_any_call(
            "\n\n[bold bright_red]❌ Tests failed. Please fix errors.[/bold bright_red]\n"
        )
        mock_cj_execute.assert_called_once()

    def test_process_with_failed_build(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(publish="patch", no_config_updates=True)
        with patch("platform.system", return_value="Linux"):
            with patch.object(Crackerjack, "execute_command") as mock_cj_execute:

                def mock_execute_side_effect(
                    *args: t.Any, **kwargs: t.Any
                ) -> subprocess.CompletedProcess[str]:
                    cmd = args[0][0]
                    if cmd == "uv" and "build" in args[0]:
                        return MagicMock(returncode=1, stdout="", stderr="Build failed")
                    return MagicMock(returncode=0, stdout="Success")

                mock_cj_execute.side_effect = mock_execute_side_effect
                with patch.object(Crackerjack, "_update_project"):
                    cj = Crackerjack(dry_run=True)
                    with suppress(SystemExit):
                        cj.process(options)
        mock_console_print.assert_any_call(
            "[bold bright_red]❌ Build failed. Please fix errors.[/bold bright_red]"
        )

    def test_publish_project_darwin(self) -> None:
        options = OptionsForTesting(publish=BumpOption.patch)
        actual_calls: list[list[str]] = []

        def mock_execute_side_effect(
            self: Crackerjack, cmd: list[str], **kwargs: t.Any
        ) -> subprocess.CompletedProcess[str]:
            actual_calls.append(cmd)
            if cmd == ["uv", "build"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="build output", stderr=""
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with patch("platform.system", return_value="Darwin"):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(
                    Crackerjack,
                    "execute_command",
                    side_effect=mock_execute_side_effect,
                    autospec=True,
                ):
                    crackerjack = Crackerjack(dry_run=False)
                    with patch.object(crackerjack.console, "print"):
                        crackerjack._publish_project(options)
        assert ["uv", "build"] in actual_calls
        assert any(cmd[:2] == ["uv", "publish"] for cmd in actual_calls)

    def test_publish_with_authentication(self) -> None:
        options = OptionsForTesting(publish=BumpOption.patch)
        actual_calls: list[list[str]] = []

        def mock_execute_side_effect(
            self: Crackerjack, cmd: list[str], **kwargs: t.Any
        ) -> subprocess.CompletedProcess[str]:
            actual_calls.append(cmd)
            if cmd == ["uv", "build"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="build output", stderr=""
                )
            elif cmd[:2] == ["uv", "publish"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="publish output", stderr=""
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with patch("platform.system", return_value="Darwin"):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(
                    Crackerjack,
                    "execute_command",
                    side_effect=mock_execute_side_effect,
                    autospec=True,
                ):
                    crackerjack = Crackerjack(dry_run=False)
                    with patch.object(crackerjack.console, "print"):
                        crackerjack._publish_project(options)
        assert ["uv", "build"] in actual_calls
        any_publish_command = any(cmd[:2] == ["uv", "publish"] for cmd in actual_calls)
        assert any_publish_command

    def test_publish_with_uv_token_environment_variable(self) -> None:
        options = OptionsForTesting(publish=BumpOption.patch)
        actual_calls: list[list[str]] = []

        def mock_execute_side_effect(
            self: Crackerjack, cmd: list[str], **kwargs: t.Any
        ) -> subprocess.CompletedProcess[str]:
            actual_calls.append(cmd)
            if cmd == ["uv", "build"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="build output", stderr=""
                )
            elif cmd[:2] == ["uv", "publish"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="publish output", stderr=""
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with patch("platform.system", return_value="Darwin"):
            with patch.dict(
                "os.environ", {"UV_PUBLISH_TOKEN": "pypi-test-token"}, clear=True
            ):
                with patch.object(
                    Crackerjack,
                    "execute_command",
                    side_effect=mock_execute_side_effect,
                    autospec=True,
                ):
                    crackerjack = Crackerjack(dry_run=False)
                    with patch.object(crackerjack.console, "print"):
                        crackerjack._publish_project(options)

        assert ["uv", "build"] in actual_calls
        assert any(
            cmd[:4] == ["uv", "publish", "--token", "pypi-test-token"]
            for cmd in actual_calls
        )

    def test_publish_with_keyring_provider_configuration(self) -> None:
        options = OptionsForTesting(publish=BumpOption.patch)
        actual_calls: list[list[str]] = []

        def mock_execute_side_effect(
            self: Crackerjack, cmd: list[str], **kwargs: t.Any
        ) -> subprocess.CompletedProcess[str]:
            actual_calls.append(cmd)
            if cmd == ["uv", "build"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="build output", stderr=""
                )
            elif cmd[:2] == ["uv", "publish"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="publish output", stderr=""
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with patch("platform.system", return_value="Darwin"):
            with patch.dict(
                "os.environ", {"UV_KEYRING_PROVIDER": "subprocess"}, clear=True
            ):
                with patch.object(
                    Crackerjack,
                    "execute_command",
                    side_effect=mock_execute_side_effect,
                    autospec=True,
                ):
                    crackerjack = Crackerjack(dry_run=False)
                    with patch.object(crackerjack.console, "print"):
                        crackerjack._publish_project(options)

        assert ["uv", "build"] in actual_calls
        publish_with_keyring = ["uv", "publish", "--keyring-provider", "subprocess"]
        assert publish_with_keyring in actual_calls

    def test_authentication_validation_with_token(self) -> None:
        with patch("platform.system", return_value="Darwin"):
            with patch.dict(
                "os.environ", {"UV_PUBLISH_TOKEN": "pypi-test-token"}, clear=True
            ):
                crackerjack = Crackerjack(dry_run=False)
                with patch.object(crackerjack.console, "print") as mock_print:
                    crackerjack._validate_authentication_setup()
                mock_print.assert_any_call(
                    "[dim]🔐 Validating authentication setup...[/dim]"
                )
                mock_print.assert_any_call(
                    "[dim]  ✅ UV_PUBLISH_TOKEN environment variable found[/dim]"
                )

    def test_authentication_validation_with_keyring(self) -> None:
        def mock_execute_side_effect(
            self: Crackerjack, cmd: list[str], **kwargs: t.Any
        ) -> subprocess.CompletedProcess[str]:
            if cmd == [
                "keyring",
                "get",
                "https://upload.pypi.org/legacy/",
                "__token__",
            ]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="pypi-test-token", stderr=""
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with patch("platform.system", return_value="Darwin"):
            with patch.dict("os.environ", {}, clear=True):
                with patch("shutil.which", return_value="/usr/local/bin/keyring"):
                    with patch.object(
                        Crackerjack, "_get_keyring_provider", return_value="subprocess"
                    ):
                        with patch.object(
                            Crackerjack,
                            "execute_command",
                            side_effect=mock_execute_side_effect,
                            autospec=True,
                        ):
                            crackerjack = Crackerjack(dry_run=False)
                            with patch.object(
                                crackerjack.console, "print"
                            ) as mock_print:
                                crackerjack._validate_authentication_setup()

                            mock_print.assert_any_call(
                                "[dim]🔐 Validating authentication setup...[/dim]"
                            )
                            mock_print.assert_any_call(
                                "[dim]  ✅ Keyring provider configured and keyring executable found[/dim]"
                            )
                            mock_print.assert_any_call(
                                "[dim]  ✅ PyPI token found in keyring[/dim]"
                            )

    def test_get_keyring_provider_from_environment(self) -> None:
        with patch.dict(
            "os.environ", {"UV_KEYRING_PROVIDER": "subprocess"}, clear=True
        ):
            crackerjack = Crackerjack(dry_run=False)
            provider = crackerjack._get_keyring_provider()
            assert provider == "subprocess"

    def test_get_keyring_provider_from_pyproject_toml(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject_path = Path(temp_dir) / "pyproject.toml"
            pyproject_content = """
[tool.uv]
keyring-provider = "subprocess"
"""
            pyproject_path.write_text(pyproject_content)

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch("pathlib.Path.open") as mock_open:
                            mock_open.return_value.__enter__.return_value.read.return_value = pyproject_content.encode()
                            crackerjack = Crackerjack(dry_run=False)

                            with patch("tomllib.load") as mock_load:
                                mock_load.return_value = {
                                    "tool": {"uv": {"keyring-provider": "subprocess"}}
                                }
                                provider = crackerjack._get_keyring_provider()
                                assert provider == "subprocess"

    def test_build_failure(self) -> None:
        options = OptionsForTesting(publish=BumpOption.patch)
        actual_calls: list[list[str]] = []

        def mock_execute_side_effect(
            self: Crackerjack, cmd: list[str], **kwargs: t.Any
        ) -> subprocess.CompletedProcess[str]:
            actual_calls.append(cmd)
            if cmd == ["uv", "build"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr="Build failed"
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with patch("platform.system", return_value="Darwin"):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(
                    Crackerjack,
                    "execute_command",
                    side_effect=mock_execute_side_effect,
                    autospec=True,
                ):
                    crackerjack = Crackerjack(dry_run=False)
                    with patch.object(crackerjack.console, "print"):
                        with pytest.raises(SystemExit) as exc_info:
                            crackerjack._publish_project(options)
        assert exc_info.value.code == 1
        assert ["uv", "build"] in actual_calls
        assert ["uv", "publish"] not in actual_calls

    def test_publish_failure(self) -> None:
        options = OptionsForTesting(publish=BumpOption.patch)
        actual_calls: list[list[str]] = []

        def mock_execute_side_effect(
            self: Crackerjack, cmd: list[str], **kwargs: t.Any
        ) -> subprocess.CompletedProcess[str]:
            actual_calls.append(cmd)
            if cmd == ["uv", "build"]:
                return MagicMock(returncode=0, stdout="build output")
            elif cmd == ["uv", "publish"]:
                return MagicMock(
                    returncode=1, stdout="publish output", stderr="Publish failed"
                )
            return MagicMock(returncode=0, stdout="")

        with patch("platform.system", return_value="Linux"):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(
                    Crackerjack,
                    "execute_command",
                    side_effect=mock_execute_side_effect,
                    autospec=True,
                ):
                    crackerjack = Crackerjack(dry_run=False)
                    with patch.object(crackerjack.console, "print") as mock_print:
                        crackerjack._publish_project(options)
                        assert ["uv", "build"] in actual_calls
                        assert any(cmd[:2] == ["uv", "publish"] for cmd in actual_calls)
                        assert any(
                            "build output" in str(call)
                            for call in mock_print.mock_calls
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
                    mock_cj_execute.assert_any_call(
                        ["git", "push", "origin", "main", "--no-verify"]
                    )

    def test_process_with_uv_sync_failure(
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
                returncode=1, stdout="", stderr="UV sync failed"
            )
            with patch.object(
                ProjectManager, "update_pkg_configs"
            ) as mock_update_configs:
                cj = Crackerjack(dry_run=True)
                cj.process(options)
                mock_update_configs.assert_called_once()
                assert any(
                    "UV sync failed" in str(call)
                    for call in mock_console_print.mock_calls
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
                    mock_cj_execute.assert_any_call(
                        ["uv", "run", "pre-commit", "autoupdate"]
                    )

    def test_update_precommit_ai_agent(
        self,
        mock_console_print: MagicMock,
        tmp_path: Path,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        crackerjack_path = tmp_path / "crackerjack"
        crackerjack_path.mkdir(exist_ok=True)
        options = options_factory(update_precommit=True, ai_agent=True)
        with patch.object(Crackerjack, "execute_command") as mock_cj_execute:
            mock_cj_execute.return_value = MagicMock(returncode=0, stdout="Success")
            cj = Crackerjack(pkg_path=crackerjack_path, dry_run=True)
            with patch.object(cj, "_setup_package"):
                with patch.object(cj, "_update_project"):
                    cj.process(options)
                    mock_cj_execute.assert_any_call(
                        [
                            "uv",
                            "run",
                            "pre-commit",
                            "autoupdate",
                            "-c",
                            ".pre-commit-config-ai.yaml",
                        ]
                    )

    def test_run_pre_commit_ai_agent(
        self,
        mock_console_print: MagicMock,
        tmp_path: Path,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        mock_project = MagicMock()
        options = options_factory(ai_agent=True)
        mock_project.options = options
        mock_project.console = MagicMock()
        mock_project.execute_command.return_value = MagicMock(returncode=0)
        mock_project._select_precommit_config.return_value = (
            ".pre-commit-config-ai.yaml"
        )
        mock_project._analyze_precommit_workload.return_value = {
            "total_files": 10,
            "complexity": "low",
        }
        mock_project._optimize_precommit_execution.return_value = {
            "PRE_COMMIT_CONCURRENCY": "4"
        }
        ProjectManager.run_pre_commit(mock_project)
        call_args = mock_project.execute_command.call_args
        assert call_args[0][0] == [
            "uv",
            "run",
            "pre-commit",
            "run",
            "--all-files",
            "-c",
            ".pre-commit-config-ai.yaml",
        ]

    def test_pre_commit_install_ai_agent(
        self,
        mock_console_print: MagicMock,
        tmp_path: Path,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        mock_project = MagicMock(spec=ProjectManager)
        options = options_factory(ai_agent=True)
        mock_project.options = options
        mock_project.console = MagicMock()
        mock_project.config_manager = MagicMock()
        with patch.object(mock_project, "execute_command") as mock_execute:
            mock_execute.return_value = MagicMock(
                returncode=0,
                stdout="package1\npackage2\n",
            )
            original_method = ProjectManager.update_pkg_configs
            original_method(mock_project)
            mock_execute.assert_any_call(
                [
                    "uv",
                    "run",
                    "pre-commit",
                    "install",
                    "-c",
                    ".pre-commit-config-ai.yaml",
                ]
            )

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

    def test_process_with_interactive_option(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(interactive=True, no_config_updates=True)
        with patch.object(Crackerjack, "_update_project"):
            cj = Crackerjack(dry_run=True)
            cj.process(options)

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
        import ast

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
        try:
            ast.parse(cleaned_code)
        except SyntaxError as e:
            raise AssertionError(
                f"Cleaned code is not valid Python syntax: {e}\nCode: {cleaned_code!r}"
            )

    def test_code_cleaner_remove_docstrings_empty_functions(self) -> None:
        import ast

        from rich.console import Console
        from crackerjack.crackerjack import CodeCleaner

        code_cleaner = CodeCleaner(console=Console())
        test_code = """
def empty_function():
    pass
class TestClass:
    def method_with_docstring_only(self):
        pass
    def method_with_code(self):
        return True
"""
        cleaned_code = code_cleaner.remove_docstrings(test_code)
        print(f"Cleaned code: {cleaned_code!r}")
        assert '"""This function has only a docstring."""' not in cleaned_code
        assert '"""Class docstring."""' not in cleaned_code
        assert '"""Method with only docstring."""' not in cleaned_code
        assert '"""This method has code after docstring."""' not in cleaned_code
        assert "def empty_function():\n    pass" in cleaned_code
        assert "def method_with_docstring_only(self):\n        pass" in cleaned_code
        assert "def method_with_code(self):\n        return True" in cleaned_code
        try:
            ast.parse(cleaned_code)
        except SyntaxError as e:
            raise AssertionError(
                f"Cleaned code is not valid Python syntax: {e}\nCode: {cleaned_code!r}"
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

    def test_code_cleaner_preserve_special_comments(self) -> None:
        from rich.console import Console
        from crackerjack.crackerjack import CodeCleaner

        code_cleaner = CodeCleaner(console=Console())
        test_code = "def test_func():\n    x = 1  # type: ignore\n    y = 2  # noqa\n    z = 3  # nosec\n    a = 4  # type: ignore[arg-type]\n    b = 5  # noqa: E501\n    c = 6  # nosec: B101\n    d = 7  # pragma: no cover\n    e = 8  # pylint: disable=line-too-long\n    f = 9  # mypy: ignore\n    g = 10  # regular comment that should be removed\n    h = 11 #type:ignore\n    i = 12#noqa\n    j = 13 #nosec\n    return x + y + z"
        expected_code = "def test_func():\n    x = 1  # type: ignore\n    y = 2  # noqa\n    z = 3  # nosec\n    a = 4  # type: ignore[arg-type]\n    b = 5  # noqa: E501\n    c = 6  # nosec: B101\n    d = 7  # pragma: no cover\n    e = 8  # pylint: disable=line-too-long\n    f = 9  # mypy: ignore\n    g = 10\n    h = 11 #type:ignore\n    i = 12#noqa\n    j = 13 #nosec\n    return x + y + z"
        cleaned_code = code_cleaner.remove_line_comments(test_code)
        assert cleaned_code == expected_code, (
            f"Special comments not preserved correctly.\nExpected:\n{expected_code}\nGot:\n{cleaned_code}"
        )

    def test_code_cleaner_special_comments_in_strings(self) -> None:
        from rich.console import Console
        from crackerjack.crackerjack import CodeCleaner

        code_cleaner = CodeCleaner(console=Console())
        test_code = 'def test_func():\n    s1 = "# type: ignore"  # should keep comment outside string but preserve string\n    s2 = \'# noqa\'  # type: ignore\n    s3 = "test"  # regular comment should be removed\n    return s1 + s2'
        expected_code = 'def test_func():\n    s1 = "# type: ignore"\n    s2 = \'# noqa\'  # type: ignore\n    s3 = "test"\n    return s1 + s2'
        cleaned_code = code_cleaner.remove_line_comments(test_code)
        assert cleaned_code == expected_code, (
            f"String handling with special comments failed.\nExpected:\n{expected_code}\nGot:\n{cleaned_code}"
        )

    def test_code_cleaner_remove_extra_whitespace(self) -> None:
        from rich.console import Console
        from crackerjack.crackerjack import CodeCleaner

        code_cleaner = CodeCleaner(console=Console())
        code_with_whitespace = (
            "def test_func():\n    x = 1\n\n\n    y = 2\n\n    return x + y\n\n\n"
        )
        cleaned_code = code_cleaner.remove_extra_whitespace(code_with_whitespace)
        assert "def test_func():" in cleaned_code, f"Got: {cleaned_code!r}"
        assert "x = 1" in cleaned_code, f"Got: {cleaned_code!r}"
        assert "y = 2" in cleaned_code, f"Got: {cleaned_code!r}"
        assert "\n\n\n" not in cleaned_code, (
            f"Triple newlines should be removed: {cleaned_code!r}"
        )
        assert "y = 2\n\n    return x + y" in cleaned_code, (
            f"Should keep blank before return: {cleaned_code!r}"
        )
        code_with_classes = "class TestClass:\n\n\n    def method1(self):\n        pass\n\n\n    def method2(self):\n        return True\n\n"
        cleaned_class_code = code_cleaner.remove_extra_whitespace(code_with_classes)
        assert "class TestClass:" in cleaned_class_code
        assert "def method1(self):" in cleaned_class_code
        assert "def method2(self):" in cleaned_class_code

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

        with patch("crackerjack.errors.handle_error") as mock_handle_error:
            console = Console()
            code_cleaner = CodeCleaner(console=console)
            code_to_format = "def test_func():\n    return True\n"
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1, stderr="Formatting error"
                )
                with patch("pathlib.Path.write_text"):
                    formatted_code = code_cleaner.reformat_code(code_to_format)
                    assert formatted_code == code_to_format
                    mock_run.assert_called_once()
                    mock_handle_error.assert_called()

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

                configs_to_add = [
                    config for config in config_files if config != ".gitignore"
                ]
                if configs_to_add:
                    mock_cm_execute.assert_any_call(["git", "add"] + configs_to_add)

    def test_prepare_pytest_command_with_benchmark(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        crackerjack = Crackerjack(
            pkg_path=tmp_path_package, console=Console(force_terminal=True)
        )
        options = options_factory(
            test=True, benchmark=False, benchmark_regression=False
        )
        test_command = crackerjack._prepare_pytest_command(options)
        assert "--benchmark" not in test_command
        assert "--benchmark-regression" not in test_command
        assert "-xvs" in test_command
        options = options_factory(test=True, benchmark=True, benchmark_regression=False)
        test_command = crackerjack._prepare_pytest_command(options)
        assert "--benchmark" in test_command
        assert "--benchmark-regression" not in test_command
        assert "-xvs" not in test_command
        options = options_factory(
            test=True,
            benchmark=False,
            benchmark_regression=True,
            benchmark_regression_threshold=5.0,
        )
        test_command = crackerjack._prepare_pytest_command(options)
        assert "--benchmark" not in test_command
        assert "--benchmark-regression" in test_command
        assert "--benchmark-regression-threshold=5.0" in test_command
        assert "-xvs" not in test_command
        options = options_factory(
            test=True,
            benchmark=True,
            benchmark_regression=True,
            benchmark_regression_threshold=10.0,
        )
        test_command = crackerjack._prepare_pytest_command(options)
        assert "--benchmark" in test_command
        assert "--benchmark-regression" in test_command
        assert "--benchmark-regression-threshold=10.0" in test_command
        assert "-xvs" not in test_command

    def test_analyze_git_changes(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        with patch.object(Crackerjack, "execute_command") as mock_execute:
            mock_execute.return_value = MagicMock(
                returncode=0,
                stdout="A\tcrackerjack/new_feature.py\nM\tREADME.md\nD\toldfile.py\nR100\told_name.py\tnew_name.py",
            )
            cj = Crackerjack(dry_run=False)
            changes = cj._analyze_git_changes()

            assert changes["added"] == ["crackerjack/new_feature.py"]
            assert changes["modified"] == ["README.md"]
            assert changes["deleted"] == ["oldfile.py"]
            assert changes["renamed"] == [("old_name.py", "new_name.py")]
            assert changes["total_changes"] == 4

    def test_categorize_changes(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        cj = Crackerjack(dry_run=False)
        changes = {
            "added": ["README.md", "tests/test_new.py", "src/core.py"],
            "modified": ["pyproject.toml", ".pre-commit-config.yaml"],
            "deleted": ["old_test.py"],
        }

        categories = cj._categorize_changes(changes)

        assert "README.md" in categories["docs"]
        assert "tests/test_new.py" in categories["tests"]
        assert "src/core.py" in categories["core"]
        assert (
            "pyproject.toml" in categories["config"]
            or "pyproject.toml" in categories["deps"]
        )
        assert ".pre-commit-config.yaml" in categories["config"]

    def test_generate_commit_message(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        cj = Crackerjack(dry_run=False)

        changes = {
            "added": ["src/new_feature.py", "tests/test_feature.py"],
            "modified": ["README.md"],
            "deleted": [],
            "renamed": [],
            "total_changes": 3,
            "stats": "",
        }

        message = cj._generate_commit_message(changes)
        assert message.startswith("Add")
        assert "core functionality" in message or "tests" in message
        assert "Added 2 file(s)" in message

        changes = {
            "added": [],
            "modified": ["README.md", "CLAUDE.md", "docs/guide.md"],
            "deleted": [],
            "renamed": [],
            "total_changes": 3,
            "stats": "",
        }

        message = cj._generate_commit_message(changes)
        assert message.startswith("Update")
        assert "documentation" in message

        changes = {
            "added": [],
            "modified": [],
            "deleted": ["old_file.py", "deprecated.py"],
            "renamed": [],
            "total_changes": 2,
            "stats": "",
        }

        message = cj._generate_commit_message(changes)
        assert message.startswith("Remove")

    def test_commit_with_suggested_message(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
        options_factory: t.Callable[..., OptionsForTesting],
    ) -> None:
        options = options_factory(commit=True, no_config_updates=True)

        with patch.object(Crackerjack, "execute_command") as mock_execute_cmd:
            mock_execute_cmd.side_effect = [
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=0, stdout="M\tREADME.md\nA\ttests/test_new.py"),
                MagicMock(returncode=0, stdout=""),
                MagicMock(
                    returncode=0,
                    stdout=" README.md | 10 ++++\n tests/test_new.py | 50 ++++\n 2 files changed, 60 insertions(+)",
                ),
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=0, stdout=""),
            ]

            with patch("builtins.input", return_value="y"):
                with patch.object(Crackerjack, "_update_project"):
                    cj = Crackerjack(dry_run=False)
                    cj.process(options)

                    commit_call = None
                    for call in mock_execute_cmd.call_args_list:
                        if call[0][0][0:2] == ["git", "commit"]:
                            commit_call = call
                            break

                    assert commit_call is not None
                    commit_msg = commit_call[0][0][3]
                    assert "Update" in commit_msg or "Add" in commit_msg
                    assert any(
                        keyword in commit_msg
                        for keyword in ("documentation", "tests", "core functionality")
                    )

    def test_claude_md_compression(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        config_manager = ConfigManager(
            our_path=tmp_path / "source",
            pkg_path=tmp_path_package,
            pkg_name="test_package",
            console=Console(),
            dry_run=True,
        )

        large_content = (
            """# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

A detailed project overview with lots of information that will be compressed.

```bash
pipx install uv

uv sync

uv run pytest
uv run pyright
uv run ruff check
uv run pre-commit run --all-files
```

```bash
python -m crackerjack

python -m crackerjack -x -t -c

python -m crackerjack -i
```

This is a very long section with detailed development guidelines that would normally be quite verbose and contain many examples and explanations that could be compressed while retaining the essential information.

- Use static typing throughout
- Follow PEP 8 style guidelines
- Write comprehensive tests
- Document public APIs
- Use modern Python features

This section contains detailed information about recent bug fixes and improvements that is useful but not essential for basic operation.

Detailed explanation of a bug fix with lots of technical details that could be summarized.

Another detailed explanation with implementation details.

Essential information for AI assistants that should be preserved during compression.

- Always use type hints
- Follow project conventions
- Write clean, readable code
- Test thoroughly
- Document important decisions

Critical information that must be preserved:

- Run quality checks before completion
- Verify all tests pass
- Update documentation as needed
- Follow project standards

Very detailed section about self-maintenance that could be compressed significantly while preserving key points.
"""
            * 3
        )

        compressed = config_manager._compress_claude_md(large_content, target_size=3000)

        assert len(compressed) < len(large_content)
        assert "automatically compressed by Crackerjack" in compressed
        assert len(compressed) <= 3000

    def test_claude_md_customization_with_compression(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        config_manager = ConfigManager(
            our_path=tmp_path / "source",
            pkg_path=tmp_path_package,
            pkg_name="test_package",
            console=Console(),
            dry_run=True,
        )

        content = """# CLAUDE.md

This file provides guidance to Claude Code.

Essential development guidelines for the project.

Important quality standards that must be preserved.
"""

        result = config_manager._customize_claude_md(content, compress=True)

        assert "TEST_PACKAGE.md" in result
        assert "Test_Package" in result
        assert "automatically generated by Crackerjack" in result
        assert "Essential development guidelines" in result

    def test_claude_md_no_compression_when_small(
        self,
        mock_execute: MagicMock,
        mock_console_print: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        config_manager = ConfigManager(
            our_path=tmp_path / "source",
            pkg_path=tmp_path_package,
            pkg_name="test_package",
            console=Console(),
            dry_run=True,
        )

        small_content = """# CLAUDE.md

Short content that doesn't need compression.

Brief overview.
"""

        result = config_manager._compress_claude_md(small_content)

        assert result == small_content
        assert "automatically compressed" not in result


class TestSessionTracker:
    def test_task_status_initialization(self) -> None:
        task = TaskStatus(
            id="test-task",
            name="Test Task",
            status="pending",
        )
        assert task.id == "test-task"
        assert task.name == "Test Task"
        assert task.status == "pending"
        assert task.files_changed == []
        assert task.duration is None

    def test_task_status_duration_calculation(self) -> None:
        import time

        start_time = time.time()
        end_time = start_time + 2.5
        task = TaskStatus(
            id="test-task",
            name="Test Task",
            status="completed",
            start_time=start_time,
            end_time=end_time,
        )
        assert task.duration == 2.5

    def test_session_tracker_creation(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        progress_file = tmp_path / "test-progress.md"
        tracker = SessionTracker.create_session(
            console=console,
            session_id="test-session",
            progress_file=progress_file,
            metadata={"test": "data"},
        )
        assert tracker.session_id == "test-session"
        assert tracker.progress_file == progress_file
        assert tracker.metadata == {"test": "data"}
        assert progress_file.exists()
        content = progress_file.read_text(encoding="utf-8")
        assert "test-session" in content
        assert "Session Progress" in content

    def test_session_tracker_start_task(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        progress_file = tmp_path / "test-progress.md"
        tracker = SessionTracker.create_session(
            console=console,
            progress_file=progress_file,
        )
        tracker.start_task("setup", "Initialize project", "Setting up structure")
        assert "setup" in tracker.tasks
        task = tracker.tasks["setup"]
        assert task.name == "Initialize project"
        assert task.status == "in_progress"
        assert task.details == "Setting up structure"
        assert task.start_time is not None
        assert tracker.current_task == "setup"

    def test_session_tracker_complete_task(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        progress_file = tmp_path / "test-progress.md"
        tracker = SessionTracker.create_session(
            console=console,
            progress_file=progress_file,
        )
        tracker.start_task("setup", "Initialize project")
        tracker.complete_task("setup", "Project initialized", ["file1.py", "file2.py"])
        task = tracker.tasks["setup"]
        assert task.status == "completed"
        assert task.details == "Project initialized"
        assert task.files_changed == ["file1.py", "file2.py"]
        assert task.end_time is not None
        assert task.duration is not None
        assert tracker.current_task is None

    def test_session_tracker_fail_task(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        progress_file = tmp_path / "test-progress.md"
        tracker = SessionTracker.create_session(
            console=console,
            progress_file=progress_file,
        )
        tracker.start_task("setup", "Initialize project")
        tracker.fail_task("setup", "Setup failed", "Permission denied")
        task = tracker.tasks["setup"]
        assert task.status == "failed"
        assert task.error_message == "Setup failed"
        assert task.details == "Permission denied"
        assert task.end_time is not None
        assert tracker.current_task is None

    def test_session_tracker_skip_task(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        progress_file = tmp_path / "test-progress.md"
        tracker = SessionTracker.create_session(
            console=console,
            progress_file=progress_file,
        )
        tracker.start_task("setup", "Initialize project")
        tracker.skip_task("setup", "User requested skip")
        task = tracker.tasks["setup"]
        assert task.status == "skipped"
        assert task.details == "Skipped: User requested skip"
        assert task.end_time is not None
        assert tracker.current_task is None

    def test_session_tracker_resume_session(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        progress_file = tmp_path / "test-progress.md"
        SessionTracker.create_session(
            console=console,
            session_id="original-session",
            progress_file=progress_file,
        )
        resumed_tracker = SessionTracker.resume_session(
            console=console,
            progress_file=progress_file,
        )
        assert resumed_tracker.progress_file == progress_file
        assert resumed_tracker.session_id == "original-session"

    def test_session_tracker_markdown_generation(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        progress_file = tmp_path / "test-progress.md"
        tracker = SessionTracker.create_session(
            console=console,
            session_id="test-session",
            progress_file=progress_file,
            metadata={"working_dir": "/test/dir"},
        )
        tracker.start_task("setup", "Initialize project")
        tracker.complete_task("setup", "Project initialized", ["file1.py"])
        tracker.start_task("test", "Run tests")
        tracker.fail_task("test", "Test failed", "Syntax error")
        content = progress_file.read_text(encoding="utf-8")
        assert "test-session" in content
        assert "2/2 tasks completed" in content or "1/2 tasks completed" in content
        assert "Initialize project" in content
        assert "✅ Initialize project - COMPLETED" in content
        assert "❌ Run tests - FAILED" in content
        assert "file1.py" in content
        assert "Test failed" in content

    def test_find_recent_progress_files(self, tmp_path: Path) -> None:
        file1 = tmp_path / "SESSION-PROGRESS-20240101-120000.md"
        file2 = tmp_path / "SESSION-PROGRESS-20240102-120000.md"
        file3 = tmp_path / "other-file.md"
        file1.write_text("test content 1")
        file2.write_text("test content 2")
        file3.write_text("not a progress file")
        import time

        time.sleep(0.1)
        file2.touch()
        files = SessionTracker.find_recent_progress_files(tmp_path)
        assert len(files) == 2
        assert files[0] == file2
        assert files[1] == file1

    def test_is_session_incomplete(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        complete_file = tmp_path / "complete-session.md"
        complete_tracker = SessionTracker.create_session(
            console=console,
            progress_file=complete_file,
        )
        complete_tracker.start_task("setup", "Setup")
        complete_tracker.complete_task("setup", "Setup done")
        incomplete_file = tmp_path / "incomplete-session.md"
        incomplete_tracker = SessionTracker.create_session(
            console=console,
            progress_file=incomplete_file,
        )
        incomplete_tracker.start_task("setup", "Setup")
        assert not SessionTracker.is_session_incomplete(complete_file)
        assert SessionTracker.is_session_incomplete(incomplete_file)
        failed_file = tmp_path / "failed-session.md"
        failed_tracker = SessionTracker.create_session(
            console=console,
            progress_file=failed_file,
        )
        failed_tracker.start_task("setup", "Setup")
        failed_tracker.fail_task("setup", "Setup failed")
        assert SessionTracker.is_session_incomplete(failed_file)

    def test_find_incomplete_session(self, tmp_path: Path) -> None:
        console = Console(force_terminal=True)
        complete_file = tmp_path / "SESSION-PROGRESS-20240101-120000.md"
        complete_tracker = SessionTracker.create_session(
            console=console,
            progress_file=complete_file,
        )
        complete_tracker.start_task("setup", "Setup")
        complete_tracker.complete_task("setup", "Setup done")
        incomplete_file = tmp_path / "SESSION-PROGRESS-20240102-120000.md"
        incomplete_tracker = SessionTracker.create_session(
            console=console,
            progress_file=incomplete_file,
        )
        incomplete_tracker.start_task("setup", "Setup")
        import time

        time.sleep(0.1)
        incomplete_file.touch()
        found_session = SessionTracker.find_incomplete_session(tmp_path)
        assert found_session == incomplete_file
        complete_tracker2 = SessionTracker.create_session(
            console=console,
            progress_file=incomplete_file,
        )
        complete_tracker2.start_task("setup", "Setup")
        complete_tracker2.complete_task("setup", "Setup done")
        found_session = SessionTracker.find_incomplete_session(tmp_path)
        assert found_session is None
