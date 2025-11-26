import subprocess
from unittest.mock import Mock, patch, MagicMock

import pytest
from acb.console import Console
from acb.config import root_path

from acb.depends import depends
from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.managers.publish_manager import PublishManagerImpl
from crackerjack.managers.test_command_builder import TestCommandBuilder
from crackerjack.managers.test_manager import TestManagementImpl
from crackerjack.models.protocols import CoverageRatchetProtocol, CoverageBadgeServiceProtocol


# Module-level DI context setup
@pytest.fixture
def mock_console_di() -> MagicMock:
    """Mock Console for DI context."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_coverage_ratchet() -> MagicMock:
    """Mock CoverageRatchetProtocol for DI context."""
    mock = MagicMock()
    # Make coverage ratchet always return True for tests
    mock.process_coverage_ratchet.return_value = True
    return mock


@pytest.fixture
def mock_coverage_badge() -> MagicMock:
    """Mock CoverageBadgeServiceProtocol for DI context."""
    return MagicMock(spec=CoverageBadgeServiceProtocol)


@pytest.fixture
def managers_di_context(
    mock_console_di: MagicMock,
    mock_coverage_ratchet: MagicMock,
    mock_coverage_badge: MagicMock,
    temp_project,
):
    """Set up DI context for managers testing."""
    injection_map = {
        Console: mock_console_di,
        CoverageRatchetProtocol: mock_coverage_ratchet,
        CoverageBadgeServiceProtocol: mock_coverage_badge,
        TestCommandBuilder: TestCommandBuilder(temp_project),
    }

    original_values = {}
    try:
        # Save original values
        for key in injection_map.keys():
            try:
                original_values[key] = depends.get_sync(key)
            except Exception:
                original_values[key] = None

        # Set mock values
        for key, value in injection_map.items():
            depends.set(key, value)

        yield injection_map
    finally:
        # Restore original values
        for key, value in original_values.items():
            if value is not None:
                depends.set(key, value)


@pytest.fixture
def console(mock_console_di):
    """Provide console mock for tests."""
    return mock_console_di


def create_test_manager_with_path(temp_project):
    """Helper to create TestManagementImpl with custom pkg_path.

    Since TestManager gets pkg_path from ACB's root_path via DI,
    we need to manually override it after instantiation for tests.
    """
    manager = TestManagementImpl()
    # Override the pkg_path that comes from root_path
    manager.pkg_path = temp_project
    # Recreate components with correct path
    from crackerjack.managers.test_executor import TestExecutor
    manager.executor = TestExecutor(manager.console, temp_project)
    manager.command_builder = TestCommandBuilder(temp_project)
    return manager


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
        manager = HookManagerImpl(pkg_path=temp_project)
        assert manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_run_fast_hooks_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="All hooks passed", stderr="")

        manager = HookManagerImpl(pkg_path=temp_project)

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

        manager = HookManagerImpl(pkg_path=temp_project)

        results = manager.run_comprehensive_hooks()
        assert isinstance(results, list)

    @patch("subprocess.run")
    def test_run_hooks_failure(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Hook failed")

        manager = HookManagerImpl(pkg_path=temp_project)

        results = manager.run_fast_hooks()
        assert isinstance(results, list)

    def test_skip_hooks_option(self, console, temp_project) -> None:
        manager = HookManagerImpl(pkg_path=temp_project)

        results = manager.run_fast_hooks()
        assert isinstance(results, list)


class TestTestManagementImpl:
    def test_initialization(self, managers_di_context, temp_project) -> None:
        manager = create_test_manager_with_path(temp_project)
        assert manager.pkg_path == temp_project

    def test_run_tests_success(self, managers_di_context, temp_project) -> None:
        manager = create_test_manager_with_path(temp_project)

        # Disable coverage ratchet for this test
        manager.set_coverage_ratchet_enabled(False)

        # Mock the executor's execute_with_progress method
        mock_result = Mock(
            returncode=0,
            stdout="collected 1 items\n\ntests/test_dummy.py::test_dummy PASSED [100%]\n\n1 passed in 0.01s",
            stderr="",
        )
        manager.executor.execute_with_progress = Mock(return_value=mock_result)

        options = MockOptions(test=True)
        result = manager.run_tests(options)
        assert result is True

    @patch("crackerjack.managers.test_manager.subprocess.Popen")
    @patch("crackerjack.managers.test_manager.subprocess.run")
    def test_run_tests_failure(
        self,
        mock_run,
        mock_popen,
        managers_di_context,
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

        manager = create_test_manager_with_path(temp_project)

        options = MockOptions(
            test=True,
            benchmark=True,
        )

        result = manager.run_tests(options)
        assert result is False

    def test_test_disabled(self, managers_di_context, temp_project) -> None:
        manager = create_test_manager_with_path(temp_project)

        # Mock the executor to verify it's not called when test=False
        manager.executor.execute_with_progress = Mock()

        options = MockOptions(test=False)
        result = manager.run_tests(options)

        # Should return True without running tests
        assert result is True
        # Executor should not be called
        manager.executor.execute_with_progress.assert_not_called()

    def test_benchmark_mode(self, managers_di_context, temp_project) -> None:
        manager = create_test_manager_with_path(temp_project)

        # Disable coverage ratchet for this test
        manager.set_coverage_ratchet_enabled(False)

        # Mock the executor's execute_with_progress method
        mock_result = Mock(
            returncode=0,
            stdout="Benchmark complete",
            stderr="",
        )
        manager.executor.execute_with_progress = Mock(return_value=mock_result)

        options = MockOptions(test=True, benchmark=True)
        result = manager.run_tests(options)
        assert result is True

    def test_test_workers_configuration(self, managers_di_context, temp_project) -> None:
        manager = create_test_manager_with_path(temp_project)

        # Disable coverage ratchet for this test
        manager.set_coverage_ratchet_enabled(False)

        # Mock the executor's execute_with_progress method
        mock_result = Mock(returncode=0, stdout="Tests completed", stderr="")
        manager.executor.execute_with_progress = Mock(return_value=mock_result)

        options = MockOptions(test=True, test_workers=4)
        result = manager.run_tests(options)
        assert result is True

    def test_test_timeout_configuration(self, managers_di_context, temp_project) -> None:
        manager = create_test_manager_with_path(temp_project)

        # Disable coverage ratchet for this test
        manager.set_coverage_ratchet_enabled(False)

        # Mock the executor's execute_with_progress method
        mock_result = Mock(returncode=0, stdout="Tests completed", stderr="")
        manager.executor.execute_with_progress = Mock(return_value=mock_result)

        options = MockOptions(test=True, test_timeout=300)
        result = manager.run_tests(options)
        assert result is True

    def test_parse_test_statistics_success(self, managers_di_context, temp_project) -> None:
        """Test parsing of successful pytest output."""
        manager = create_test_manager_with_path(temp_project)

        pytest_output = """
        ================================ test session starts =================================
        collected 10 items

        tests/test_foo.py ......                                                      [ 60%]
        tests/test_bar.py ....                                                        [100%]

        ============================== 10 passed in 5.23s ================================
        """

        stats = manager._parse_test_statistics(pytest_output)

        assert stats["total"] == 10
        assert stats["passed"] == 10
        assert stats["failed"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
        assert stats["duration"] == 5.23

    def test_parse_test_statistics_with_failures(self, managers_di_context, temp_project) -> None:
        """Test parsing of pytest output with failures."""
        manager = create_test_manager_with_path(temp_project)

        pytest_output = """
        ================================ test session starts =================================
        collected 15 items

        tests/test_foo.py .F.F.                                                       [ 33%]
        tests/test_bar.py ..s...                                                      [ 73%]
        tests/test_baz.py ....                                                        [100%]

        ========================== 11 passed, 2 failed, 2 skipped in 12.45s ==========================
        """

        stats = manager._parse_test_statistics(pytest_output)

        assert stats["total"] == 15
        assert stats["passed"] == 11
        assert stats["failed"] == 2
        assert stats["skipped"] == 2
        assert stats["errors"] == 0
        assert stats["duration"] == 12.45

    def test_parse_test_statistics_with_errors(self, managers_di_context, temp_project) -> None:
        """Test parsing of pytest output with errors."""
        manager = create_test_manager_with_path(temp_project)

        pytest_output = """
        ================================ test session starts =================================
        collected 8 items

        tests/test_foo.py EE                                                          [ 25%]
        tests/test_bar.py ..F.                                                        [ 75%]
        tests/test_baz.py ..                                                          [100%]

        ========================== 5 passed, 1 failed, 2 error in 3.12s ==========================
        """

        stats = manager._parse_test_statistics(pytest_output)

        assert stats["total"] == 8
        assert stats["passed"] == 5
        assert stats["failed"] == 1
        assert stats["errors"] == 2
        assert stats["duration"] == 3.12

    def test_parse_test_statistics_with_xfail_xpass(self, managers_di_context, temp_project) -> None:
        """Test parsing of pytest output with xfailed and xpassed tests."""
        manager = create_test_manager_with_path(temp_project)

        pytest_output = """
        ================================ test session starts =================================
        collected 12 items

        tests/test_foo.py .x.X                                                        [ 33%]
        tests/test_bar.py ........                                                    [100%]

        =================== 8 passed, 1 xfailed, 1 xpassed in 4.56s =====================
        """

        stats = manager._parse_test_statistics(pytest_output)

        assert stats["total"] == 10
        assert stats["passed"] == 8
        assert stats["xfailed"] == 1
        assert stats["xpassed"] == 1
        assert stats["duration"] == 4.56

    def test_parse_test_statistics_with_coverage(self, managers_di_context, temp_project) -> None:
        """Test parsing of pytest output with coverage information."""
        manager = create_test_manager_with_path(temp_project)

        pytest_output = """
        ================================ test session starts =================================
        collected 10 items

        tests/test_foo.py ......                                                      [ 60%]
        tests/test_bar.py ....                                                        [100%]

        ---------- coverage: platform darwin, python 3.13.0-final-0 -----------
        Name                     Stmts   Miss  Cover
        --------------------------------------------
        crackerjack/__init__.py     10      2    80%
        crackerjack/core.py        150     30    80%
        --------------------------------------------
        TOTAL                      160     32    80%

        ============================== 10 passed in 5.23s ================================
        """

        stats = manager._parse_test_statistics(pytest_output)

        assert stats["total"] == 10
        assert stats["passed"] == 10
        assert stats["coverage"] == 80.0

    def test_parse_test_statistics_with_ansi_codes(
        self, managers_di_context, temp_project
    ) -> None:
        """Ensure ANSI escape codes do not break parsing."""
        manager = create_test_manager_with_path(temp_project)

        pytest_output = (
            "\x1b[32m================== 2 passed, 1 skipped in 0.42s ==================\x1b[0m"
        )

        stats = manager._parse_test_statistics(pytest_output)

        assert stats["total"] == 3
        assert stats["passed"] == 2
        assert stats["skipped"] == 1
        assert stats["duration"] == 0.42

    def test_parse_test_statistics_fallback_counts(
        self, managers_di_context, temp_project
    ) -> None:
        """Fallback counting should handle verbose lines without summaries."""
        manager = create_test_manager_with_path(temp_project)

        pytest_output = """
        tests/test_alpha.py::test_pass PASSED
        tests/test_alpha.py::test_fail FAILED
        tests/test_alpha.py::test_skip SKIPPED
        tests/test_alpha.py::test_error ERROR
        tests/test_alpha.py::test_xpass XPASS
        tests/test_alpha.py::test_xfail XFAIL
        """

        stats = manager._parse_test_statistics(pytest_output)

        assert stats["total"] == 6
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["skipped"] == 1
        assert stats["errors"] == 1
        assert stats["xpassed"] == 1
        assert stats["xfailed"] == 1

    def test_parse_test_statistics_empty_output(self, managers_di_context, temp_project) -> None:
        """Test parsing of empty pytest output."""
        manager = create_test_manager_with_path(temp_project)

        stats = manager._parse_test_statistics("")

        assert stats["total"] == 0
        assert stats["passed"] == 0
        assert stats["failed"] == 0
        assert stats["duration"] == 0.0


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
    def test_managers_work_together(self, managers_di_context, console, temp_project) -> None:
        test_manager = create_test_manager_with_path(temp_project)
        publish_manager = PublishManagerImpl(pkg_path=temp_project)
        hook_manager = HookManagerImpl(pkg_path=temp_project)

        assert hook_manager.console is console
        assert test_manager.console is console
        assert publish_manager.console is console

        assert hook_manager.pkg_path == temp_project
        assert test_manager.pkg_path == temp_project
        assert publish_manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_workflow_simulation(self, mock_run, managers_di_context, console, temp_project) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")

        hook_manager = HookManagerImpl(console=console, pkg_path=temp_project)
        test_manager = create_test_manager_with_path(temp_project)

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
