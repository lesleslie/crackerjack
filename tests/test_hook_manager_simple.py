from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.models.task import HookResult


@pytest.fixture
def console():
    return Console()


@pytest.fixture
def pkg_path(tmp_path):
    return tmp_path


@pytest.fixture
def hook_manager(console, pkg_path):
    return HookManagerImpl(pkg_path)


class TestHookManager:
    def test_init(self, hook_manager, console, pkg_path) -> None:
        assert hook_manager.console == console
        assert hook_manager.pkg_path == pkg_path
        assert hook_manager.executor is not None
        assert hook_manager.config_loader is not None

    @patch("crackerjack.managers.hook_manager.HookConfigLoader")
    @patch("crackerjack.managers.hook_manager.HookExecutor")
    def test_init_with_mocks(
        self,
        mock_executor_class,
        mock_loader_class,
        console,
        pkg_path,
    ) -> None:
        HookManagerImpl(console, pkg_path)

        mock_executor_class.assert_called_once_with(console, pkg_path, False, False)
        mock_loader_class.assert_called_once()

    def test_get_hook_summary_empty(self, hook_manager) -> None:
        summary = hook_manager.get_hook_summary([])

        expected = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "total_duration": 0,
            "success_rate": 0,
        }
        assert summary == expected

    def test_get_hook_summary_with_results(self, hook_manager) -> None:
        results = [
            HookResult(id="test1", name="test hook 1", status="passed", duration=1.0),
            HookResult(id="test2", name="test hook 2", status="failed", duration=2.0),
            HookResult(id="test3", name="test hook 3", status="timeout", duration=3.0),
            HookResult(id="test4", name="test hook 4", status="passed", duration=1.5),
        ]

        summary = hook_manager.get_hook_summary(results)

        assert summary["total"] == 4
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["errors"] == 1
        assert summary["total_duration"] == 7.5
        assert summary["success_rate"] == 50.0

    def test_run_fast_hooks(self, hook_manager) -> None:
        mock_strategy = Mock()
        mock_result = Mock()
        mock_result.results = [
            HookResult(id="test", name="test hook", status="passed", duration=1.0),
        ]

        hook_manager.config_loader.load_strategy = Mock(return_value=mock_strategy)
        hook_manager.executor.execute_strategy = Mock(return_value=mock_result)

        results = hook_manager.run_fast_hooks()

        assert len(results) == 1
        assert results[0].status == "passed"
        hook_manager.config_loader.load_strategy.assert_called_once_with("fast")

    def test_run_comprehensive_hooks(self, hook_manager) -> None:
        mock_strategy = Mock()
        mock_result = Mock()
        mock_result.results = [
            HookResult(id="test1", name="test hook 1", status="passed", duration=1.0),
            HookResult(id="test2", name="test hook 2", status="failed", duration=2.0),
        ]

        hook_manager.config_loader.load_strategy = Mock(return_value=mock_strategy)
        hook_manager.executor.execute_strategy = Mock(return_value=mock_result)

        results = hook_manager.run_comprehensive_hooks()

        assert len(results) == 2
        hook_manager.config_loader.load_strategy.assert_called_once_with(
            "comprehensive",
        )

    def test_install_hooks(self, hook_manager) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = hook_manager.install_hooks()

            assert result is True
            mock_run.assert_called_once()

    def test_install_hooks_failure(self, hook_manager) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            result = hook_manager.install_hooks()

            assert result is False

    def test_update_hooks(self, hook_manager) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = hook_manager.update_hooks()

            assert result is True
            mock_run.assert_called_once()

    def test_update_hooks_failure(self, hook_manager) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            result = hook_manager.update_hooks()

            assert result is False
