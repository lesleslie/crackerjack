import shutil
import typing as t
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from crackerjack.crackerjack import Crackerjack


@pytest.fixture
def crackerjack_instance(tmp_path: Path) -> t.Generator[Crackerjack, None, None]:
    """Fixture to create a Crackerjack instance in a temporary directory."""
    # Create a temporary directory for the package
    pkg_path = tmp_path / "test_package"
    pkg_path.mkdir()
    # create the package directory
    pkg_dir = pkg_path / "test_package"
    pkg_dir.mkdir()
    # Create a dummy pyproject.toml
    pyproject_content = """
[project]
name = "test_package"
version = "0.1.0"
classifiers = [
    "Programming Language :: Python :: 3.10",
]
requires-python = ">=3.10"

[tool.ruff.lint]
ignore = [
    "F821",
]
[tool.vulture]
min_confidence = 84
paths = ["test_package",]
"""
    (pkg_path / "pyproject.toml").write_text(pyproject_content)

    # Create a dummy .gitignore
    (pkg_path / ".gitignore").write_text("*.pyc\n__pycache__/\n")

    # Create dummy config file
    (pkg_path / ".pre-commit-config.yaml").write_text("dummy pre-commit config")

    # Create a dummy our_pyproject.toml
    our_pyproject_content = """
[project]
name = "crackerjack"
version = "0.1.0"
requires-python = ">=3.13"
classifiers = [
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

[tool.ruff.lint]
ignore = [
    "F821",
    "D100",
]
[tool.vulture]
min_confidence = 84
paths = ["crackerjack",]
"""

    our_path = tmp_path / "our_crackerjack"
    our_path.mkdir()
    (our_path / "pyproject.toml").write_text(our_pyproject_content)
    (our_path / ".gitignore").write_text("*.pyc\n__pycache__/\n")
    (our_path / ".pre-commit-config.yaml").write_text(
        "dummy our pre-commit config crackerjack"
    )
    (our_path / ".libcst.codemod.yaml").write_text("dummy our libcst")

    # Create a Crackerjack instance
    instance = Crackerjack(
        our_path=our_path,
        pkg_path=pkg_path,
        pkg_name="test_package",
        pkg_dir=pkg_dir,
        python_version="3.12",
    )
    yield instance
    # Teardown (cleanup the temporary directory)
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_update_pyproject_configs(crackerjack_instance: Crackerjack) -> None:
    """Test that pyproject.toml is correctly updated."""
    crackerjack_instance.update_pyproject_configs()
    pkg_pyproject = crackerjack_instance.pkg_toml_path.read_text()
    assert "test_package" in pkg_pyproject
    assert "Programming Language :: Python :: 3.12" in pkg_pyproject
    assert '"F821", "D100"' in pkg_pyproject
    assert 'paths = ["test_package"]' in pkg_pyproject


def test_copy_configs(crackerjack_instance: Crackerjack) -> None:
    """Test that the config files are copied correctly."""
    crackerjack_instance.copy_configs()
    assert (crackerjack_instance.pkg_path / ".gitignore").exists()
    assert (crackerjack_instance.pkg_path / ".pre-commit-config.yaml").exists()
    assert (crackerjack_instance.pkg_path / ".libcst.codemod.yaml").exists()
    assert (
        "test_package"
        in crackerjack_instance.pkg_path.joinpath(".pre-commit-config.yaml").read_text()
    )


@patch("subprocess.run")
def test_run_interactive_success(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test run_interactive with successful pre-commit run."""
    mock_run.return_value.returncode = 0
    crackerjack_instance.run_interactive("refurb")
    mock_run.assert_called_once_with(
        ["pre-commit", "run", "refurb", "--all-files"],
        check=True,
    )


@patch("subprocess.run")
def test_run_interactive_failure(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test run_interactive with a failing pre-commit run."""
    mock_run.return_value.returncode = 1
    with pytest.raises(SystemExit):
        with patch("builtins.input", return_value="N"):
            crackerjack_instance.run_interactive("refurb")
    mock_run.assert_called_once_with(
        ["pre-commit", "run", "refurb", "--all-files"], check=True
    )


@patch("subprocess.run")
def test_run_interactive_retry(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test run_interactive with a failing pre-commit run, then retry."""
    mock_run.side_effect = [
        type("", (), {"returncode": 1})(),
        type("", (), {"returncode": 0})(),
    ]
    with patch("builtins.input", side_effect=["y", "N"]):
        crackerjack_instance.run_interactive("refurb")
    assert mock_run.call_count == 2


@patch("subprocess.run")
def test_update_pkg_configs_new(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test update_pkg_configs when pre-commit is not found."""
    mock_run.return_value.stdout = ""
    crackerjack_instance.update_pkg_configs()
    assert mock_run.call_count >= 8


@patch("subprocess.run")
def test_update_pkg_configs_exists(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test update_pkg_configs when pre-commit is found."""
    mock_run.return_value.stdout = "pre-commit 3.6.0\n"
    crackerjack_instance.update_pkg_configs()
    mock_run.assert_called_with(
        ["pdm", "list", "--freeze"],
        capture_output=True,
        text=True,
        check=True,
    )


@patch("subprocess.run")
def test_run_pre_commit_success(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test run_pre_commit with a successful pre-commit run."""
    mock_run.return_value.returncode = 0
    crackerjack_instance.run_pre_commit()
    mock_run.assert_called_once_with(["pre-commit", "run", "--all-files"], check=True)


@patch("subprocess.run")
def test_run_pre_commit_failure(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test run_pre_commit with a failing pre-commit run."""
    mock_run.side_effect = [
        type("", (), {"returncode": 1})(),
        type("", (), {"returncode": 1})(),
    ]
    with pytest.raises(SystemExit):
        crackerjack_instance.run_pre_commit()
    assert mock_run.call_count == 2


@patch("subprocess.run")
def test_process_no_update(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test process with do_not_update_configs=True."""
    options = type(
        "",
        (),
        {
            "do_not_update_configs": True,
            "interactive": False,
            "publish": False,
            "bump": False,
            "update_precommit": False,
            "commit": False,
        },
    )()
    crackerjack_instance.process(options)
    mock_run.assert_called_with(["pre-commit", "run", "--all-files"], check=True)


@patch("subprocess.run")
def test_process_update(mock_run: MagicMock, crackerjack_instance: Crackerjack) -> None:
    """Test process with do_not_update_configs=False."""
    options = type(
        "",
        (),
        {
            "do_not_update_configs": False,
            "interactive": False,
            "publish": False,
            "bump": False,
            "update_precommit": False,
            "commit": False,
        },
    )()
    crackerjack_instance.process(options)
    mock_run.assert_called_with(["pre-commit", "run", "--all-files"], check=True)


@patch("subprocess.run")
def test_process_update_precommit(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test process with do_not_update_configs=False and update_precommit=True."""
    crackerjack_instance.pkg_path = crackerjack_instance.our_path
    options = type(
        "",
        (),
        {
            "do_not_update_configs": False,
            "interactive": False,
            "publish": False,
            "bump": False,
            "update_precommit": True,
            "commit": False,
        },
    )()
    crackerjack_instance.process(options)
    mock_run.assert_called_with(["pre-commit", "autoupdate"], check=True)


@patch("subprocess.run")
def test_process_interactive(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test process with interactive=True."""
    mock_run.return_value.returncode = 0
    options = type(
        "",
        (),
        {
            "do_not_update_configs": False,
            "interactive": True,
            "publish": False,
            "bump": False,
            "update_precommit": False,
            "commit": False,
        },
    )()
    crackerjack_instance.process(options)
    assert mock_run.call_count >= 5


@patch("subprocess.run")
def test_process_bump(mock_run: MagicMock, crackerjack_instance: Crackerjack) -> None:
    """Test process with bump."""
    options = type(
        "",
        (),
        {
            "do_not_update_configs": False,
            "interactive": False,
            "publish": False,
            "bump": "micro",
            "update_precommit": False,
            "commit": False,
        },
    )()
    crackerjack_instance.process(options)
    mock_run.assert_called_with(["pdm", "bump", "micro"], check=True)


@patch("subprocess.run")
def test_process_publish(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test process with publish."""
    options = type(
        "",
        (),
        {
            "do_not_update_configs": False,
            "interactive": False,
            "publish": "major",
            "bump": False,
            "update_precommit": False,
            "commit": False,
        },
    )()
    crackerjack_instance.process(options)
    assert mock_run.call_args_list[-1][0][0] == ["pdm", "publish", "--no-build"]


@patch("subprocess.run")
def test_process_publish_fail(
    mock_run: MagicMock, crackerjack_instance: Crackerjack
) -> None:
    """Test process with publish failure."""
    mock_run.side_effect = [
        type("", (), {"returncode": 1, "stdout": "", "stderr": "build failed"})(),
    ]
    options = type(
        "",
        (),
        {
            "do_not_update_configs": False,
            "interactive": False,
            "publish": "major",
            "bump": False,
            "update_precommit": False,
            "commit": False,
        },
    )()
    with pytest.raises(SystemExit):
        crackerjack_instance.process(options)
    assert mock_run.call_args_list[0][0][0] == ["pdm", "build"]


@patch("subprocess.run")
def test_process_commit(mock_run: MagicMock, crackerjack_instance: Crackerjack) -> None:
    """Test process with commit."""
    mock_run.return_value.returncode = 0
    with patch("builtins.input", return_value="test commit"):
        options = type(
            "",
            (),
            {
                "do_not_update_configs": False,
                "interactive": False,
                "publish": False,
                "bump": False,
                "update_precommit": False,
                "commit": True,
            },
        )()
        crackerjack_instance.process(options)
    assert mock_run.call_args_list[-1][0][0] == ["git", "push", "origin", "main"]
