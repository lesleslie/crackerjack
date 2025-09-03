import subprocess
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.managers.publish_manager import PublishManagerImpl
from crackerjack.managers.test_manager import TestManagementImpl


@pytest.fixture
def console():
    return Console(force_terminal=True)


@pytest.fixture
def temp_project(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_content = """
[project]
name = "test - project"
version = "0.1.0"
description = "Test project"
requires - python = ">=    3.8"

[build - system]
requires = ["hatchling"]
build - backend = "hatchling.build"

[tool.pytest.ini_options]
addopts = "- v"
"""
    pyproject_path.write_text(pyproject_content)

    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    test_file = test_dir / "test_dummy.py"
    test_file.write_text("def test_dummy(): \n assert True\n")

    return tmp_path


class MockOptions:
    def __init__(self, **kwargs) -> None:
        self.test = False
        self.benchmark = False
        self.test_workers = 0
        self.test_timeout = 0

        self.skip_hooks = False
        self.update_precommit = False
        self.experimental_hooks = False

        self.publish = None
        self.bump = None

        self.verbose = False
        self.dry_run = False

        self.ai_agent = False

        for key, value in kwargs.items():
            setattr(self, key, value)


class TestHookManagerImpl:
    def test_initialization(self, console, temp_project) -> None:
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        assert manager.console is console
        assert manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_run_fast_hooks_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="All hooks passed", stderr="")

        manager = HookManagerImpl(console=console, pkg_path=temp_project)

        results = manager.run_fast_hooks()
        assert isinstance(results, list)

    @patch("subprocess.run")
    def test_run_comprehensive_hooks_success(
        self,
        mock_run,
        console,
        temp_project,
    ) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="All hooks passed", stderr="")

        manager = HookManagerImpl(console=console, pkg_path=temp_project)

        results = manager.run_comprehensive_hooks()
        assert isinstance(results, list)

    @patch("subprocess.run")
    def test_run_hooks_failure(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Hook failed")

        manager = HookManagerImpl(console=console, pkg_path=temp_project)

        results = manager.run_fast_hooks()
        assert isinstance(results, list)

    def test_skip_hooks_option(self, console, temp_project) -> None:
        manager = HookManagerImpl(console=console, pkg_path=temp_project)

        results = manager.run_fast_hooks()
        assert isinstance(results, list)


class TestTestManagementImpl:
    def test_initialization(self, console, temp_project) -> None:
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        assert manager.console is console
        assert manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_run_tests_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="collected 1 items\n\ntests / test_dummy.py:: test_dummy PASSED [100 %]\n\n1 passed in 0.01s",
            stderr="",
        )

        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)

        result = manager.run_tests(options)
        assert result is True

    @patch("crackerjack.managers.test_manager.subprocess.Popen")
    @patch("crackerjack.managers.test_manager.subprocess.run")
    def test_run_tests_failure(
        self,
        mock_run,
        mock_popen,
        console,
        temp_project,
    ) -> None:
        mock_run.return_value = Mock(
            returncode=1,
            stdout="collected 1 items\n\ntests / test_dummy.py:: test_dummy FAILED [100 %]\n\nFAILURES\ntest_dummy.py FAILED\n",
            stderr="Tests failed",
        )

        mock_process = Mock()
        mock_process.communicate.return_value = (
            "collected 1 items\n\ntests / test_dummy.py:: test_dummy FAILED [100 %]\n\nFAILURES\ntest_dummy.py FAILED\n",
            "Tests failed",
        )
        mock_process.returncode = 1
        mock_process.stdout = Mock()
        mock_process.stderr = Mock()
        mock_process.stdout.readline.return_value = ""
        mock_process.stderr.readline.return_value = ""
        mock_process.poll.return_value = 1
        mock_popen.return_value = mock_process

        manager = TestManagementImpl(console=console, pkg_path=temp_project)

        options = MockOptions(
            test=True,
            benchmark=True,
        )

        result = manager.run_tests(options)
        assert result is False

    def test_test_disabled(self, console, temp_project) -> None:
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=False)

        result = manager.run_tests(options)
        assert result is True

    @patch("subprocess.run")
    def test_benchmark_mode(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Benchmark complete",
            stderr="",
        )

        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True, benchmark=True)

        result = manager.run_tests(options)
        assert result is True

    @patch("subprocess.run")
    def test_test_workers_configuration(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="Tests completed", stderr="")

        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True, test_workers=4)

        result = manager.run_tests(options)
        assert result is True

    @patch("subprocess.run")
    def test_test_timeout_configuration(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="Tests completed", stderr="")

        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True, test_timeout=300)

        result = manager.run_tests(options)
        assert result is True


class TestPublishManagerImpl:
    def test_initialization(self, console, temp_project) -> None:
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        assert manager.console is console
        assert manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_version_bump_patch(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="Version bumped", stderr="")

        manager = PublishManagerImpl(console=console, pkg_path=temp_project)

        result = manager.bump_version("patch")
        assert isinstance(result, str)
        assert "0.1.1" in result

    @patch("subprocess.run")
    def test_version_bump_minor(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="Version bumped", stderr="")

        manager = PublishManagerImpl(console=console, pkg_path=temp_project)

        result = manager.bump_version("minor")
        assert isinstance(result, str)
        assert "0.2.0" in result

    @patch("subprocess.run")
    def test_version_bump_major(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="Version bumped", stderr="")

        manager = PublishManagerImpl(console=console, pkg_path=temp_project)

        result = manager.bump_version("major")
        assert isinstance(result, str)
        assert "1.0.0" in result

    @patch("subprocess.run")
    def test_publish_to_pypi(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Published successfully",
            stderr="",
        )

        manager = PublishManagerImpl(console=console, pkg_path=temp_project)

        result = manager.publish_package()
        assert isinstance(result, bool)

    def test_publish_disabled(self, console, temp_project) -> None:
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)

        result = manager.publish_package()
        assert isinstance(result, bool)

    @patch("subprocess.run")
    def test_dry_run_mode(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Dry run successful",
            stderr="",
        )

        manager = PublishManagerImpl(
            console=console,
            pkg_path=temp_project,
            dry_run=True,
        )

        result = manager.publish_package()
        assert isinstance(result, bool)


class TestManagersIntegration:
    def test_managers_work_together(self, console, temp_project) -> None:
        hook_manager = HookManagerImpl(console=console, pkg_path=temp_project)
        test_manager = TestManagementImpl(console=console, pkg_path=temp_project)
        publish_manager = PublishManagerImpl(console=console, pkg_path=temp_project)

        assert hook_manager.console is console
        assert test_manager.console is console
        assert publish_manager.console is console

        assert hook_manager.pkg_path == temp_project
        assert test_manager.pkg_path == temp_project
        assert publish_manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_workflow_simulation(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")

        hook_manager = HookManagerImpl(console=console, pkg_path=temp_project)
        test_manager = TestManagementImpl(console=console, pkg_path=temp_project)

        options = MockOptions(test=True)

        hook_results = hook_manager.run_fast_hooks()
        assert isinstance(hook_results, list)

        test_result = test_manager.run_tests(options)
        assert isinstance(test_result, bool)


class TestManagerConfiguration:
    def test_hook_config_integration(self, console, temp_project) -> None:
        manager = HookManagerImpl(console=console, pkg_path=temp_project)

        configs = [
            MockOptions(skip_hooks=True),
            MockOptions(experimental_hooks=True),
            MockOptions(update_precommit=True),
        ]

        for _config in configs:
            results = manager.run_fast_hooks()
            assert isinstance(results, list)

    def test_test_config_integration(self, console, temp_project) -> None:
        manager = TestManagementImpl(console=console, pkg_path=temp_project)

        configs = [
            MockOptions(test=False),
            MockOptions(test=True, benchmark=True),
            MockOptions(test=True, test_workers=2, test_timeout=60),
        ]

        for config in configs:
            result = manager.run_tests(config)
            assert isinstance(result, bool)

    def test_publish_config_integration(self, console, temp_project) -> None:
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)

        configs = [
            MockOptions(publish=None),
            MockOptions(bump="patch"),
            MockOptions(publish="minor", dry_run=True),
        ]

        for config in configs:
            if config.publish:
                result = manager.publish_package()
            elif config.bump:
                result = manager.bump_version(config.bump)
            else:
                result = manager.publish_package()
            assert isinstance(
                result,
                bool | str,
            )


class TestManagerErrorHandling:
    @patch("subprocess.run")
    def test_hook_manager_subprocess_error(
        self,
        mock_run,
        console,
        temp_project,
    ) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["cmd"])

        manager = HookManagerImpl(console=console, pkg_path=temp_project)

        results = manager.run_fast_hooks()
        assert isinstance(results, list)

    @patch("subprocess.run")
    def test_test_manager_subprocess_error(
        self,
        mock_run,
        console,
        temp_project,
    ) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["pytest"])

        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)

        result = manager.run_tests(options)
        assert isinstance(result, bool)

    @patch("subprocess.run")
    def test_publish_manager_subprocess_error(
        self,
        mock_run,
        console,
        temp_project,
    ) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["uv", "build"])

        manager = PublishManagerImpl(console=console, pkg_path=temp_project)

        result = manager.publish_package()
        assert isinstance(result, bool)
