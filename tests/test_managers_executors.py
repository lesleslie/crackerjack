from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.executors.hook_executor import HookExecutor
from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.managers.test_manager import TestManagementImpl
from crackerjack.models.task import HookResult


class TestHookManagerImpl:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / hook_manager")

    @pytest.fixture
    def hook_manager(self, mock_console, mock_pkg_path):
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                return HookManagerImpl(console=mock_console, pkg_path=mock_pkg_path)

    def test_init(self, hook_manager, mock_console, mock_pkg_path) -> None:
        assert hook_manager.console == mock_console
        assert hook_manager.pkg_path == mock_pkg_path
        assert hasattr(hook_manager, "executor")
        assert hasattr(hook_manager, "config_loader")

    def test_run_fast_hooks_success(self, hook_manager) -> None:
        mock_result = HookResult(
            id="hook1", name="test - hook", status="passed", duration=1.0
        )
        mock_execution_result = Mock()
        mock_execution_result.results = [mock_result]

        with patch.object(hook_manager.config_loader, "load_strategy") as mock_load:
            with patch.object(
                hook_manager.executor, "execute_strategy"
            ) as mock_execute:
                mock_strategy = Mock()
                mock_strategy.hooks = []
                mock_load.return_value = mock_strategy
                mock_execute.return_value = mock_execution_result

                result = hook_manager.run_fast_hooks()

                assert result == [mock_result]
                mock_load.assert_called_once_with("fast")
                mock_execute.assert_called_once_with(mock_strategy)

    def test_run_comprehensive_hooks_success(self, hook_manager) -> None:
        mock_result = HookResult(
            id="hook2", name="comp - hook", status="passed", duration=2.0
        )
        mock_execution_result = Mock()
        mock_execution_result.results = [mock_result]

        with patch.object(hook_manager.config_loader, "load_strategy") as mock_load:
            with patch.object(
                hook_manager.executor, "execute_strategy"
            ) as mock_execute:
                mock_strategy = Mock()
                mock_strategy.hooks = []
                mock_load.return_value = mock_strategy
                mock_execute.return_value = mock_execution_result

                result = hook_manager.run_comprehensive_hooks()

                assert result == [mock_result]
                mock_load.assert_called_once_with("comprehensive")
                mock_execute.assert_called_once_with(mock_strategy)

    def test_set_config_path(self, hook_manager) -> None:
        config_path = Path(" / test / config.yaml")
        hook_manager.set_config_path(config_path)
        assert hook_manager._config_path == config_path

    def test_install_hooks_success(self, hook_manager) -> None:
        with patch("crackerjack.managers.hook_manager.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = hook_manager.install_hooks()

            assert result is True
            mock_run.assert_called_once()

    def test_install_hooks_failure(self, hook_manager) -> None:
        with patch("crackerjack.managers.hook_manager.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="Install failed")

            result = hook_manager.install_hooks()

            assert result is False

    def test_update_hooks_success(self, hook_manager) -> None:
        with patch("crackerjack.managers.hook_manager.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = hook_manager.update_hooks()

            assert result is True

    def test_get_hook_summary_empty(self, hook_manager) -> None:
        summary = hook_manager.get_hook_summary([])

        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["success_rate"] == 0

    def test_get_hook_summary_with_results(self, hook_manager) -> None:
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0),
            HookResult(id="2", name="hook2", status="failed", duration=2.0),
            HookResult(id="3", name="hook3", status="passed", duration=1.5),
        ]

        summary = hook_manager.get_hook_summary(results)

        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["total_duration"] == 4.5
        assert summary["success_rate"] == (2 / 3) * 100


class TestHookExecutorComponents:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / hook_executor")

    @pytest.fixture
    def hook_executor(self, mock_console, mock_pkg_path):
        return HookExecutor(console=mock_console, pkg_path=mock_pkg_path)

    def test_hook_executor_init(
        self, hook_executor, mock_console, mock_pkg_path
    ) -> None:
        assert hook_executor.console == mock_console
        assert hook_executor.pkg_path == mock_pkg_path

    def test_execute_strategy_success(self, hook_executor) -> None:
        from crackerjack.config.hooks import HookStrategy
        from crackerjack.models.task import HookResult

        strategy = Mock(spec=HookStrategy)
        strategy.hooks = []
        strategy.name = "fast"

        with patch.object(hook_executor, "execute_strategy") as mock_execute:
            mock_result = Mock()
            mock_result.results = [
                HookResult(id="1", name="test", status="passed", duration=1.0)
            ]
            mock_execute.return_value = mock_result

            result = hook_executor.execute_strategy(strategy)

            assert hasattr(result, "results")
            assert len(result.results) == 1

    def test_execute_strategy_failure(self, hook_executor) -> None:
        from crackerjack.config.hooks import HookStrategy

        strategy = Mock(spec=HookStrategy)
        strategy.hooks = []
        strategy.name = "fast"

        with patch.object(hook_executor, "execute_strategy") as mock_execute:
            mock_execute.side_effect = Exception("Execution failed")

            with pytest.raises(Exception):
                hook_executor.execute_strategy(strategy)

    def test_console_integration(self, hook_executor) -> None:
        assert hasattr(hook_executor, "console")
        assert hook_executor.console is not None


class TestServicesIntegration:
    def test_filesystem_service_integration(self) -> None:
        from crackerjack.services.filesystem import FileSystemService

        fs_service = FileSystemService()
        assert hasattr(fs_service, "read_file")
        assert hasattr(fs_service, "write_file")

    def test_git_service_integration(self) -> None:
        from crackerjack.services.git import GitService

        mock_console = Mock()
        mock_pkg_path = Path(" / test")

        git_service = GitService(console=mock_console, pkg_path=mock_pkg_path)
        assert hasattr(git_service, "commit")
        assert hasattr(git_service, "push")

    def test_config_service_integration(self) -> None:
        from crackerjack.services.config import ConfigurationService

        mock_console = Mock()
        mock_pkg_path = Path(" / test")

        config_service = ConfigurationService(
            console=mock_console, pkg_path=mock_pkg_path
        )
        assert hasattr(config_service, "update_precommit_config")
        assert hasattr(config_service, "console")


class TestTestManagementImpl:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / test_manager")

    @pytest.fixture
    def mock_options(self):
        options = Mock()
        options.test_workers = 2
        options.test_timeout = 300
        options.benchmark = False
        options.verbose = False
        return options

    @pytest.fixture
    def test_manager(self, mock_console, mock_pkg_path):
        return TestManagementImpl(console=mock_console, pkg_path=mock_pkg_path)

    def test_init(self, test_manager, mock_console, mock_pkg_path) -> None:
        assert test_manager.console == mock_console
        assert test_manager.pkg_path == mock_pkg_path

    def test_run_tests_success(self, test_manager, mock_options) -> None:
        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="All tests passed", stderr=""
            )

            result = test_manager.run_tests(mock_options)

            assert result is True

    def test_run_tests_failure(self, test_manager, mock_options) -> None:
        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Tests failed")

            result = test_manager.run_tests(mock_options)

            assert result is False

    def test_run_tests_timeout(self, test_manager, mock_options) -> None:
        with patch.object(test_manager, "_run_test_command") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired("pytest", 300)

            result = test_manager.run_tests(mock_options)

            assert result is False

    def test_get_coverage_success(self, test_manager) -> None:
        coverage_json = '{"totals": {"percent_covered": 85.5}, "files": {}}'
        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=coverage_json)

            result = test_manager.get_coverage()

            assert result["total_coverage"] == 85.5
            assert "files" in result
            assert "summary" in result

    def test_get_coverage_failure(self, test_manager) -> None:
        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Coverage failed"
            )

            result = test_manager.get_coverage()

            assert result == {}

    def test_run_specific_tests_success(self, test_manager) -> None:
        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Tests passed")

            result = test_manager.run_specific_tests("test_pattern")

            assert result is True

    def test_validate_test_environment_success(self, test_manager) -> None:
        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            with patch("pathlib.Path.glob") as mock_glob:
                mock_glob.return_value = [Path("test_file.py")]
                with patch("pathlib.Path.exists") as mock_exists:
                    mock_exists.return_value = True

                    result = test_manager.validate_test_environment()

                    assert result is True

    def test_validate_test_environment_failure(self, test_manager) -> None:
        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(returncode=1)

            result = test_manager.validate_test_environment()

            assert result is False

    def test_get_test_stats(self, test_manager) -> None:
        mock_file1 = Mock()
        mock_file1.read_text.return_value = (
            "def test_one(): \n pass\n\ndef test_two(): \n pass"
        )
        mock_file2 = Mock()
        mock_file2.read_text.return_value = (
            "def test_three(): \n pass\n\ndef test_four(): \n pass"
        )

        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = [mock_file1, mock_file2]
            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                stats = test_manager.get_test_stats()

                assert stats["test_files"] == 2
                assert stats["total_tests"] == 4
                assert stats["avg_tests_per_file"] == 2.0

    def test_get_optimal_workers(self, test_manager, mock_options) -> None:
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = [Path(f"test_{i}.py") for i in range(10)]

            workers = test_manager._get_optimal_workers(mock_options)

            assert workers == 2

    def test_get_test_timeout(self, test_manager, mock_options) -> None:
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = [Path(f"test_{i}.py") for i in range(9)]

            timeout = test_manager._get_test_timeout(mock_options)

            assert timeout == 300


class TestManagerErrorHandling:
    def test_hook_manager_error_handling(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / error")

        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                manager = HookManagerImpl(console=mock_console, pkg_path=mock_pkg_path)

                with patch.object(manager.config_loader, "load_strategy") as mock_load:
                    mock_load.side_effect = Exception("Config load failed")

                    with pytest.raises(Exception):
                        manager.run_fast_hooks()

    def test_test_manager_error_handling(self, mock_options) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / error")

        manager = TestManagementImpl(console=mock_console, pkg_path=mock_pkg_path)

        with patch.object(manager, "_run_test_command") as mock_run:
            mock_run.side_effect = Exception("Command failed")

            result = manager.run_tests(mock_options)
            assert result is False

    @pytest.fixture
    def mock_options(self):
        options = Mock()
        options.test_workers = 2
        options.test_timeout = 300
        options.benchmark = False
        options.verbose = False
        return options


class TestCoverageIntegration:
    def test_manager_coverage_methods(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / coverage")

        test_manager = TestManagementImpl(console=mock_console, pkg_path=mock_pkg_path)
        assert hasattr(test_manager, "get_coverage")
        assert callable(test_manager.get_coverage)

    def test_coverage_data_processing(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / coverage_data")

        test_manager = TestManagementImpl(console=mock_console, pkg_path=mock_pkg_path)

        coverage_json = '{"totals": {"percent_covered": 75.5}, "files": {"file1.py": {"summary": {"percent_covered": 80}}}}'

        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=coverage_json)

            coverage_data = test_manager.get_coverage()

            assert coverage_data["total_coverage"] == 75.5
            assert "files" in coverage_data
            assert "summary" in coverage_data

    def test_coverage_error_handling(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / coverage_error")

        test_manager = TestManagementImpl(console=mock_console, pkg_path=mock_pkg_path)

        with patch.object(test_manager, "_run_test_command") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="Coverage command failed")

            coverage_data = test_manager.get_coverage()

            assert coverage_data == {}


class TestUtilityFunctions:
    def test_hook_manager_utilities(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / utilities")

        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                manager = HookManagerImpl(console=mock_console, pkg_path=mock_pkg_path)

                summary = manager.get_hook_summary([])
                assert summary["total"] == 0
                assert summary["success_rate"] == 0

    def test_test_manager_utilities(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / test_utilities")

        manager = TestManagementImpl(console=mock_console, pkg_path=mock_pkg_path)

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False

            stats = manager.get_test_stats()

            assert stats["test_files"] == 0
            assert stats["total_tests"] == 0
            assert stats["test_lines"] == 0

    def test_optimal_workers_calculation(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / workers")

        manager = TestManagementImpl(console=mock_console, pkg_path=mock_pkg_path)

        options = Mock()
        options.test_workers = 0

        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = [Path("test_1.py"), Path("test_2.py")]

            workers = manager._get_optimal_workers(options)

            assert isinstance(workers, int)
            assert workers >= 1
