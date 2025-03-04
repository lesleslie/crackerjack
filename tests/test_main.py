import typing as t

import pytest
from click.testing import CliRunner
from crackerjack.__main__ import crackerjack, options
from crackerjack.crackerjack import Crackerjack


@pytest.fixture(autouse=True)
def mock_crackerjack_it(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_process(self: Crackerjack, options: t.Any) -> None:
        pass

    monkeypatch.setattr(Crackerjack, "process", mock_process)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def reset_options() -> None:
    options.commit = False
    options.interactive = False
    options.doc = False
    options.update_precommit = False
    options.do_not_update_configs = False
    options.publish = False
    options.bump = False
    options.verbose = False


def test_no_options(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack)
    assert result.exit_code == 0
    assert not options.commit
    assert not options.interactive
    assert not options.doc
    assert not options.update_precommit
    assert not options.do_not_update_configs
    assert options.publish is False
    assert options.bump is False
    assert not options.verbose


def test_commit_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-c"])
    assert result.exit_code == 1
    assert options.commit


def test_interactive_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-i"])
    assert result.exit_code == 0
    assert options.interactive


def test_doc_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-d"])
    assert result.exit_code == 0
    assert options.doc


def test_update_precommit_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-u"])
    assert result.exit_code == 0
    assert options.update_precommit


def test_do_not_update_configs_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-x"])
    assert result.exit_code == 0
    assert options.do_not_update_configs


# def test_publish_micro_option(runner: CliRunner) -> None:
#     result = runner.invoke(crackerjack, ["-p", "micro"])
#     assert result.exit_code == 0
#     assert options.publish == "micro"
#
#
# def test_publish_minor_option(runner: CliRunner) -> None:
#     result = runner.invoke(crackerjack, ["-p", "minor"])
#     assert result.exit_code == 0
#     assert options.publish == "minor"
#
#
# def test_publish_major_option(runner: CliRunner) -> None:
#     result = runner.invoke(crackerjack, ["-p", "major"])
#     assert result.exit_code == 0
#     assert options.publish == "major"
#
#
# def test_bump_micro_option(runner: CliRunner) -> None:
#     result = runner.invoke(crackerjack, ["-b", "micro"])
#     assert result.exit_code == 0
#     assert options.bump == "micro"
#
#
# def test_bump_minor_option(runner: CliRunner) -> None:
#     result = runner.invoke(crackerjack, ["-b", "minor"])
#     assert result.exit_code == 0
#     assert options.bump == "minor"
#
#
# def test_bump_major_option(runner: CliRunner) -> None:
#     result = runner.invoke(crackerjack, ["-b", "major"])
#     assert result.exit_code == 0
#     assert options.bump == "major"


def test_verbose_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-v"])
    assert result.exit_code == 0
    assert options.verbose
    assert "-v not currently implemented" in result.output


def test_multiple_options(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-c", "-i"])
    assert result.exit_code == 1
    assert options.commit
    assert options.interactive


def test_help_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-h"])
    assert result.exit_code == 0
    assert "Usage: " in result.output


def test_invalid_publish_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-p", "invalid"])
    assert result.exit_code == 0
    assert options.publish is False


def test_invalid_bump_option(runner: CliRunner) -> None:
    result = runner.invoke(crackerjack, ["-b", "invalid"])
    assert result.exit_code == 0
    assert options.bump is False
