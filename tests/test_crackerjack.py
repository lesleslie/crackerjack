import typing as t
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from crackerjack.__main__ import options
from crackerjack.crackerjack import Crackerjack


@pytest.fixture
def mock_execute() -> t.Generator[t.Any, t.Any, t.Any]:
    with patch("crackerjack.crackerjack.execute") as mock:
        yield mock


@pytest.fixture
def mock_subprocess_run() -> t.Generator[t.Any, t.Any, t.Any]:
    with patch("subprocess.run") as mock:
        yield mock


@pytest.fixture
def mock_print() -> t.Generator[t.Any, t.Any, t.Any]:
    with patch("builtins.print") as mock:
        yield mock


@pytest.fixture
def mock_input() -> t.Generator[t.Any, t.Any, t.Any]:
    with patch("builtins.input") as mock:
        yield mock


@pytest.fixture(autouse=True)
def reset_options() -> None:
    """Resets the options before each test."""
    options.commit = False
    options.interactive = False
    options.doc = False
    options.update_precommit = False
    options.do_not_update_configs = False
    options.publish = False
    options.bump = False
    options.verbose = False


@pytest.fixture
def tmp_path_package(tmp_path: Path) -> Path:
    return tmp_path / "my-package"


@pytest.fixture
def create_package_dir(tmp_path_package: Path) -> None:
    (tmp_path_package / "my_package").mkdir(parents=True)
    (tmp_path_package / "pyproject.toml").touch()
    (tmp_path_package / ".gitignore").touch()
    (tmp_path_package / ".pre-commit-config.yaml").touch()
    (tmp_path_package / ".libcst.codemod.yaml").touch()


class TestCrackerjackProcess:
    def test_process_all_options(
        self,
        mock_execute: MagicMock,
        mock_print: MagicMock,
        mock_input: MagicMock,
        mock_subprocess_run: MagicMock,
        tmp_path: Path,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        mock_input.return_value = "Test Commit"
        mock_execute.return_value.returncode = 0
        mock_execute.return_value.stdout = "Mock Build Output"
        mock_subprocess_run.return_value.returncode = 0
        mock_execute.return_value.stderr = ""
        mock_subprocess_run.return_value.stdout = ""
        mock_subprocess_run.return_value.stderr = ""
        crackerjack_instance = Crackerjack(pkg_path=tmp_path_package)
        options_mock = MagicMock()
        options_mock.do_not_update_configs = False
        options_mock.update_precommit = True
        options_mock.interactive = True
        options_mock.commit = False
        options_mock.publish = None
        options_mock.bump = None
        crackerjack_instance.process(options_mock)

        assert crackerjack_instance.pkg_name == "my_package"
        (tmp_path_package / "my_package").exists()
        mock_execute.assert_has_calls(
            [
                call(["pdm", "self", "add", "keyring"]),
                call(["pdm", "config", "python.use_uv", "true"]),
                call(["git", "init"]),
                call(["git", "branch", "-m", "main"]),
                call(["git", "add", "pyproject.toml"]),
                call(["git", "add", "pdm.lock"]),
                call(["pre-commit", "install"]),
                call(["git", "config", "advice.addIgnoredFile", "false"]),
                call(["pdm", "install"]),
                call(["pre-commit", "run", "refurb", "--all-files"]),
                call(["pre-commit", "run", "bandit", "--all-files"]),
                call(["pre-commit", "run", "pyright", "--all-files"]),
                call(["pre-commit", "run", "--all-files"]),
                call(["git", "add", ".gitignore"]),
                call(["git", "add", ".pre-commit-config.yaml"]),
                call(["git", "add", ".libcst.codemod.yaml"]),
            ],
            any_order=True,
        )

    def test_process_no_options(
        self,
        mock_execute: MagicMock,
        mock_print: MagicMock,
        mock_subprocess_run: MagicMock,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        mock_execute.return_value.returncode = 0
        mock_subprocess_run.return_value.returncode = 0
        crackerjack_instance = Crackerjack(pkg_path=tmp_path_package)
        options_mock = MagicMock()
        options_mock.do_not_update_configs = True
        options_mock.update_precommit = False
        options_mock.interactive = False
        options_mock.publish = None
        options_mock.bump = None
        options_mock.commit = False

        crackerjack_instance.process(options_mock)

        assert crackerjack_instance.pkg_name == "my_package"
        (tmp_path_package / "my_package").exists()
        mock_execute.assert_has_calls(
            [
                call(["pre-commit", "run", "--all-files"]),
            ]
        )

    def test_process_interactive_hooks(
        self,
        mock_execute: MagicMock,
        mock_print: MagicMock,
        mock_subprocess_run: MagicMock,
        tmp_path_package: Path,
        create_package_dir: None,
    ) -> None:
        mock_execute.return_value.returncode = 0
        mock_subprocess_run.return_value.returncode = 0

        crackerjack_instance = Crackerjack(pkg_path=tmp_path_package)
        options_mock = MagicMock()
        options_mock.do_not_update_configs = False
        options_mock.update_precommit = False
        options_mock.interactive = True
        options_mock.publish = None
        options_mock.bump = None
        options_mock.commit = False

        crackerjack_instance.process(options_mock)

        assert crackerjack_instance.pkg_name == "my_package"
        (tmp_path_package / "my_package").exists()

        mock_execute.assert_has_calls(
            [
                call(["pre-commit", "run", "refurb", "--all-files"]),
                call(["pre-commit", "run", "bandit", "--all-files"]),
                call(["pre-commit", "run", "pyright", "--all-files"]),
                call(["pre-commit", "run", "--all-files"]),
            ]
        )
