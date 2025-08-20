from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.managers.async_hook_manager import AsyncHookManager
from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.managers.publish_manager import PublishManagerImpl


@pytest.fixture
def console():
    return Console()


@pytest.fixture
def pkg_path(tmp_path):
    return tmp_path


class TestHookManagerImpl:
    @pytest.fixture
    def hook_manager(self, console, pkg_path):
        return HookManagerImpl(console, pkg_path)

    def test_init(self, hook_manager, console, pkg_path) -> None:
        assert hook_manager.console == console
        assert hook_manager.pkg_path == pkg_path

    def test_run_fast_hooks_success(self, hook_manager) -> None:
        with patch.object(hook_manager.executor, "execute_strategy") as mock_exec:
            mock_exec.return_value = Mock(results=[])

            results = hook_manager.run_fast_hooks()

            assert isinstance(results, list)
            mock_exec.assert_called_once()

    def test_run_fast_hooks_with_config_path(self, hook_manager) -> None:
        with patch.object(hook_manager.executor, "execute_strategy") as mock_exec:
            mock_exec.return_value = Mock(results=[])

            hook_manager.set_config_path(Path("/test/config.yaml"))
            results = hook_manager.run_fast_hooks()

            assert isinstance(results, list)
            mock_exec.assert_called_once()

    def test_run_comprehensive_hooks(self, hook_manager) -> None:
        with patch.object(hook_manager.executor, "execute_strategy") as mock_exec:
            mock_exec.return_value = Mock(results=[])

            results = hook_manager.run_comprehensive_hooks()

            assert isinstance(results, list)
            mock_exec.assert_called_once()

    @patch("subprocess.run")
    def test_install_hooks(self, mock_run, hook_manager) -> None:
        mock_run.return_value = Mock(returncode=0)

        result = hook_manager.install_hooks()

        assert result is True
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_install_hooks_failure(self, mock_run, hook_manager) -> None:
        mock_run.return_value = Mock(returncode=1)

        result = hook_manager.install_hooks()

        assert result is False

    def test_set_config_path(self, hook_manager) -> None:
        config_path = Path("/test/config.yaml")

        hook_manager.set_config_path(config_path)

        assert hook_manager._config_path == config_path


class TestAsyncHookManager:
    @pytest.fixture
    def async_hook_manager(self, console, pkg_path):
        return AsyncHookManager(console, pkg_path)

    def test_init(self, async_hook_manager, console, pkg_path) -> None:
        assert async_hook_manager.console == console
        assert async_hook_manager.pkg_path == pkg_path

    @pytest.mark.asyncio
    async def test_run_fast_hooks_async(self, async_hook_manager) -> None:
        with patch.object(
            async_hook_manager.async_executor, "execute_strategy"
        ) as mock_exec:
            mock_exec.return_value = Mock(results=[])

            results = await async_hook_manager.run_fast_hooks_async()

            assert isinstance(results, list)
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_comprehensive_hooks_async(self, async_hook_manager) -> None:
        with patch.object(
            async_hook_manager.async_executor, "execute_strategy"
        ) as mock_exec:
            mock_exec.return_value = Mock(results=[])

            results = await async_hook_manager.run_comprehensive_hooks_async()

            assert isinstance(results, list)
            mock_exec.assert_called_once()

    def test_max_concurrent_setting(self, console, pkg_path) -> None:
        manager = AsyncHookManager(console, pkg_path, max_concurrent=5)

        assert manager.async_executor.max_concurrent == 5

    def test_default_max_concurrent(self, async_hook_manager) -> None:
        assert async_hook_manager.async_executor.max_concurrent == 3


class TestPublishManagerImpl:
    @pytest.fixture
    def publish_manager(self, console, pkg_path):
        return PublishManagerImpl(console, pkg_path)

    def test_init(self, publish_manager, console, pkg_path) -> None:
        assert publish_manager.console == console
        assert publish_manager.pkg_path == pkg_path
        assert publish_manager.dry_run is False

    @patch("subprocess.run")
    def test_run_command(self, mock_run, publish_manager) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="output", stderr="")

        result = publish_manager._run_command(["echo", "test"])

        assert result.returncode == 0
        mock_run.assert_called_once()

    def test_get_current_version(self, publish_manager) -> None:
        with patch("pathlib.Path.exists", return_value=True):
            with patch.object(publish_manager.filesystem, "read_file") as mock_read:
                mock_read.return_value = """[project]
name = "test"
version = "1.0.0"
"""

                version = publish_manager._get_current_version()

                assert version == "1.0.0"

    def test_get_current_version_missing(self, publish_manager) -> None:
        with patch("pathlib.Path.exists", return_value=False):
            version = publish_manager._get_current_version()
            assert version is None

    @patch("subprocess.run")
    def test_build_package(self, mock_run, publish_manager) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="Built", stderr="")

        with patch.object(
            publish_manager, "_run_command", return_value=mock_run.return_value
        ) as mock_cmd:
            result = publish_manager.build_package()

            assert result is True
            mock_cmd.assert_called()

    def test_dry_run_mode(self, console, pkg_path) -> None:
        publish_manager = PublishManagerImpl(console, pkg_path, dry_run=True)

        assert publish_manager.dry_run is True

    def test_filesystem_and_security_services(self, publish_manager) -> None:
        assert publish_manager.filesystem is not None
        assert publish_manager.security is not None
