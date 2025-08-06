from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from crackerjack.managers.async_hook_manager import AsyncHookManager
from crackerjack.models.task import HookResult


@pytest.fixture
def console():
    return Console()


@pytest.fixture
def pkg_path(tmp_path):
    return tmp_path


@pytest.fixture
def async_hook_manager(console, pkg_path):
    return AsyncHookManager(console, pkg_path, max_concurrent=2)


class TestAsyncHookManager:
    def test_init(self, async_hook_manager, console, pkg_path) -> None:
        assert async_hook_manager.console == console
        assert async_hook_manager.pkg_path == pkg_path
        assert async_hook_manager.async_executor is not None
        assert async_hook_manager.config_loader is not None

    @patch("crackerjack.managers.async_hook_manager.HookConfigLoader")
    @patch("crackerjack.managers.async_hook_manager.AsyncHookExecutor")
    def test_init_with_mocks(
        self, mock_executor_class, mock_loader_class, console, pkg_path
    ) -> None:
        AsyncHookManager(console, pkg_path, max_concurrent=3)

        mock_executor_class.assert_called_once_with(console, pkg_path, max_concurrent=3)
        mock_loader_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_fast_hooks_async(self, async_hook_manager) -> None:
        mock_strategy = Mock()
        mock_result = Mock()
        mock_result.results = [
            HookResult(id="test", name="test hook", status="passed", duration=1.0)
        ]

        async_hook_manager.config_loader.load_strategy = Mock(
            return_value=mock_strategy
        )
        async_hook_manager.async_executor.execute_strategy = AsyncMock(
            return_value=mock_result
        )

        results = await async_hook_manager.run_fast_hooks_async()

        assert len(results) == 1
        assert results[0].status == "passed"
        assert mock_strategy.parallel is False

    @pytest.mark.asyncio
    async def test_run_comprehensive_hooks_async(self, async_hook_manager) -> None:
        mock_strategy = Mock()
        mock_result = Mock()
        mock_result.results = [
            HookResult(id="test1", name="test hook 1", status="passed", duration=1.0),
            HookResult(id="test2", name="test hook 2", status="failed", duration=2.0),
        ]

        async_hook_manager.config_loader.load_strategy = Mock(
            return_value=mock_strategy
        )
        async_hook_manager.async_executor.execute_strategy = AsyncMock(
            return_value=mock_result
        )

        results = await async_hook_manager.run_comprehensive_hooks_async()

        assert len(results) == 2
        assert mock_strategy.parallel is True
        assert mock_strategy.max_workers == 3

    def test_run_fast_hooks_sync(self, async_hook_manager) -> None:
        with patch.object(async_hook_manager, "run_fast_hooks_async") as mock_async:
            mock_async.return_value = [
                HookResult(id="test", name="test hook", status="passed", duration=1.0)
            ]

            results = async_hook_manager.run_fast_hooks()

            assert len(results) == 1
            assert results[0].status == "passed"

    def test_run_comprehensive_hooks_sync(self, async_hook_manager) -> None:
        with patch.object(
            async_hook_manager, "run_comprehensive_hooks_async"
        ) as mock_async:
            mock_async.return_value = [
                HookResult(id="test", name="test hook", status="passed", duration=1.0)
            ]

            results = async_hook_manager.run_comprehensive_hooks()

            assert len(results) == 1
            assert results[0].status == "passed"

    @pytest.mark.asyncio
    async def test_install_hooks_async_success(self, async_hook_manager) -> None:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", return_value=(b"", b"")):
                result = await async_hook_manager.install_hooks_async()

                assert result is True

    @pytest.mark.asyncio
    async def test_install_hooks_async_failure(self, async_hook_manager) -> None:
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error message"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", return_value=(b"", b"Error message")):
                result = await async_hook_manager.install_hooks_async()

                assert result is False

    @pytest.mark.asyncio
    async def test_install_hooks_async_timeout(self, async_hook_manager) -> None:
        with patch("asyncio.create_subprocess_exec"):
            with patch("asyncio.wait_for", side_effect=TimeoutError):
                result = await async_hook_manager.install_hooks_async()

                assert result is False

    def test_install_hooks_sync(self, async_hook_manager) -> None:
        with patch.object(async_hook_manager, "install_hooks_async", return_value=True):
            result = async_hook_manager.install_hooks()
            assert result is True

    @pytest.mark.asyncio
    async def test_update_hooks_async_success(self, async_hook_manager) -> None:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", return_value=(b"", b"")):
                result = await async_hook_manager.update_hooks_async()

                assert result is True

    def test_update_hooks_sync(self, async_hook_manager) -> None:
        with patch.object(async_hook_manager, "update_hooks_async", return_value=True):
            result = async_hook_manager.update_hooks()
            assert result is True

    def test_get_hook_summary_empty(self, async_hook_manager) -> None:
        summary = async_hook_manager.get_hook_summary([])

        expected = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "total_duration": 0,
            "success_rate": 0,
        }
        assert summary == expected

    def test_get_hook_summary_with_results(self, async_hook_manager) -> None:
        results = [
            HookResult(id="test1", name="test hook 1", status="passed", duration=1.0),
            HookResult(id="test2", name="test hook 2", status="failed", duration=2.0),
            HookResult(id="test3", name="test hook 3", status="timeout", duration=3.0),
            HookResult(id="test4", name="test hook 4", status="passed", duration=1.5),
        ]

        summary = async_hook_manager.get_hook_summary(results)

        assert summary["total"] == 4
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["errors"] == 1
        assert summary["total_duration"] == 7.5
        assert summary["success_rate"] == 50.0
