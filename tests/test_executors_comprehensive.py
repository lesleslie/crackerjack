import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.executors.async_hook_executor import AsyncHookExecutor
from crackerjack.executors.cached_hook_executor import CachedHookExecutor
from crackerjack.executors.hook_executor import HookExecutor
from crackerjack.models.task import HookResult


class TestHookExecutorCore:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / executor")

    @pytest.fixture
    def hook_executor(self, mock_console, mock_pkg_path):
        return HookExecutor(console=mock_console, pkg_path=mock_pkg_path)

    def test_executor_initialization(
        self, hook_executor, mock_console, mock_pkg_path,
    ) -> None:
        assert hook_executor.console == mock_console
        assert hook_executor.pkg_path == mock_pkg_path

    def test_execute_strategy_with_hooks(self, hook_executor) -> None:
        from crackerjack.config.hooks import HookDefinition

        strategy = Mock()
        strategy.hooks = [
            HookDefinition(name="test - hook - 1", command=["echo", "test1"]),
            HookDefinition(name="test - hook - 2", command=["echo", "test2"]),
        ]
        strategy.stage = "fast"
        strategy.max_workers = 2
        strategy.timeout = 30

        with patch.object(hook_executor, "execute_single_hook") as mock_execute_hook:
            mock_result1 = HookResult(
                id="hook1", name="test - hook - 1", status="passed", duration=1.0,
            )
            mock_result2 = HookResult(
                id="hook2", name="test - hook - 2", status="passed", duration=1.5,
            )
            mock_execute_hook.side_effect = [mock_result1, mock_result2]

            result = hook_executor.execute_strategy(strategy)

            assert hasattr(result, "results")
            assert len(result.results) == 2
            assert mock_execute_hook.call_count == 2

    def test_execute_strategy_with_failure(self, hook_executor) -> None:
        strategy = Mock()
        strategy.hooks = [Mock(id="hook1", name="failing - hook", command=["false"])]
        strategy.stage = "fast"

        with patch.object(hook_executor, "execute_single_hook") as mock_execute_hook:
            mock_result = HookResult(
                id="hook1", name="failing - hook", status="failed", duration=1.0,
            )
            mock_execute_hook.return_value = mock_result

            result = hook_executor.execute_strategy(strategy)

            assert len(result.results) == 1
            assert result.results[0].status == "failed"

    def test_execute_single_hook_success(self, hook_executor) -> None:
        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(
            name="test - hook", command=["echo", "success"], timeout=10,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="success\n", stderr="", check=True,
            )

            result = hook_executor.execute_single_hook(hook_config)

            assert result.status == "passed"
            assert result.name == "test - hook"
            assert result.duration > 0

    def test_execute_single_hook_failure(self, hook_executor) -> None:
        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(name="fail - hook", command=["false"], timeout=10)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Command failed", check=False,
            )

            result = hook_executor.execute_single_hook(hook_config)

            assert result.status == "failed"
            assert result.name == "fail - hook"

    def test_execute_hook_timeout(self, hook_executor) -> None:
        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(
            name="timeout - hook", command=["sleep", "100"], timeout=1,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["sleep", "100"], 1)

            result = hook_executor.execute_single_hook(hook_config)

            assert result.status == "timeout"
            assert result.name == "timeout - hook"

    def test_parallel_execution(self, hook_executor) -> None:
        from crackerjack.config.hooks import HookDefinition

        hooks = [
            HookDefinition(name="parallel - 1", command=["echo", "1"]),
            HookDefinition(name="parallel - 2", command=["echo", "2"]),
            HookDefinition(name="parallel - 3", command=["echo", "3"]),
        ]

        strategy = Mock()
        strategy.hooks = hooks
        strategy.stage = "fast"
        strategy.max_workers = 3

        with patch.object(hook_executor, "execute_single_hook") as mock_execute:
            mock_results = [
                HookResult(id="p1", name="parallel - 1", status="passed", duration=0.1),
                HookResult(id="p2", name="parallel - 2", status="passed", duration=0.1),
                HookResult(id="p3", name="parallel - 3", status="passed", duration=0.1),
            ]
            mock_execute.side_effect = mock_results

            result = hook_executor.execute_strategy(strategy)

            assert len(result.results) == 3
            assert all(r.status == "passed" for r in result.results)


class TestAsyncHookExecutorCore:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / async_executor")

    @pytest.fixture
    def async_executor(self, mock_console, mock_pkg_path):
        return AsyncHookExecutor(console=mock_console, pkg_path=mock_pkg_path)

    def test_async_executor_initialization(
        self, async_executor, mock_console, mock_pkg_path,
    ) -> None:
        assert async_executor.console == mock_console
        assert async_executor.pkg_path == mock_pkg_path

    @pytest.mark.asyncio
    async def test_execute_strategy_async(self, async_executor) -> None:
        strategy = Mock()
        strategy.hooks = [
            Mock(
                id="async1",
                name="async - hook - 1",
                command=["echo", "async1"],
                timeout=10,
            ),
            Mock(
                id="async2",
                name="async - hook - 2",
                command=["echo", "async2"],
                timeout=10,
            ),
        ]
        strategy.stage = "fast"
        strategy.timeout = 30

        with patch.object(async_executor, "_execute_single_hook") as mock_execute:
            mock_results = [
                HookResult(
                    id="async1", name="async - hook - 1", status="passed", duration=0.5,
                ),
                HookResult(
                    id="async2", name="async - hook - 2", status="passed", duration=0.7,
                ),
            ]
            mock_execute.side_effect = mock_results

            result = await async_executor.execute_strategy(strategy)

            assert hasattr(result, "results")
            assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_execute_single_hook_async(self, async_executor) -> None:
        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(
            name="async - test", command=["echo", "async - success"],
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"async - success\n", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await async_executor._execute_single_hook(hook_config)

            assert result.status == "passed"
            assert result.name == "async - test"

    @pytest.mark.asyncio
    async def test_execute_hook_async_failure(self, async_executor) -> None:
        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(name="async - fail", command=["false"])

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Command failed")
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process

            result = await async_executor._execute_single_hook(hook_config)

            assert result.status == "failed"
            assert result.name == "async - fail"

    @pytest.mark.asyncio
    async def test_concurrent_hook_execution(self, async_executor) -> None:
        hooks = [
            Mock(id="c1", command=["echo", "1"], timeout=10),
            Mock(id="c2", command=["echo", "2"], timeout=10),
            Mock(id="c3", command=["echo", "3"], timeout=10),
        ]
        hooks[0].name = "concurrent - 1"
        hooks[1].name = "concurrent - 2"
        hooks[2].name = "concurrent - 3"

        strategy = Mock()
        strategy.hooks = hooks
        strategy.stage = "fast"
        strategy.max_workers = 3
        strategy.timeout = 30

        with patch.object(async_executor, "_execute_single_hook") as mock_execute:

            async def mock_hook_execution(hook):
                await asyncio.sleep(0.01)
                return HookResult(
                    id=hook.id, name=hook.name, status="passed", duration=0.01,
                )

            mock_execute.side_effect = mock_hook_execution

            result = await async_executor.execute_strategy(strategy)

            assert len(result.results) == 3
            assert all(r.status == "passed" for r in result.results)


class TestCachedHookExecutorCore:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / cached_executor")

    @pytest.fixture
    def cached_executor(self, mock_console, mock_pkg_path):
        return CachedHookExecutor(console=mock_console, pkg_path=mock_pkg_path)

    def test_cached_executor_initialization(
        self, cached_executor, mock_console, mock_pkg_path,
    ) -> None:
        assert cached_executor.console == mock_console
        assert cached_executor.pkg_path == mock_pkg_path
        assert hasattr(cached_executor, "cache")

    def test_cache_storage_and_retrieval(self, cached_executor) -> None:
        cache_key = "test_cache_key"
        result = HookResult(id="test", name="test", status="passed", duration=1.0)

        cached_executor.cache.set_hook_result(cache_key, [], result)

        cached_result = cached_executor.cache.get_hook_result(cache_key, [])

        assert cached_result is not None
        assert cached_result.id == result.id
        assert cached_result.status == result.status

    def test_cache_expiration(self, cached_executor) -> None:
        cache_key = "expiring_key"
        result = HookResult(id="test", name="test", status="passed", duration=1.0)

        cached_executor.cache.set_hook_result(cache_key, [], result)

        assert cached_executor.cache.get_hook_result(cache_key, []) is not None

        cache_entry_key = cached_executor.cache._get_hook_cache_key(cache_key, [])
        cache_entry = cached_executor.cache.hook_results_cache._cache[cache_entry_key]

        import time

        cache_entry.created_at = time.time() - 3600
        cache_entry.ttl_seconds = 1

        assert cached_executor.cache.get_hook_result(cache_key, []) is None

    def test_cache_invalidation_on_file_change(self, cached_executor) -> None:
        cache_key = "file_change_key"
        result = HookResult(id="test", name="test", status="passed", duration=1.0)

        initial_file_hashes = ["hash1", "hash2"]
        modified_file_hashes = ["hash1", "hash3"]

        cached_executor.cache.set_hook_result(cache_key, initial_file_hashes, result)
        assert (
            cached_executor.cache.get_hook_result(cache_key, initial_file_hashes)
            is not None
        )

        assert (
            cached_executor.cache.get_hook_result(cache_key, modified_file_hashes)
            is None
        )

    def test_execute_with_cache_hit(self, cached_executor) -> None:
        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(name="cached - hook", command=["echo", "cached"])

        cached_result = HookResult(
            id="cached - hook", name="cached - hook", status="passed", duration=1.0,
        )

        with patch.object(
            cached_executor, "_get_relevant_files_for_strategy", return_value=[],
        ):
            file_hashes = []
        cached_executor.cache.set_hook_result(
            hook_config.name, file_hashes, cached_result,
        )

        with (
            patch.object(
                cached_executor, "_get_relevant_files_for_strategy", return_value=[],
            ),
            patch.object(
                cached_executor.cache, "get_hook_result", return_value=cached_result,
            ) as mock_get_cache,
        ):
            result = cached_executor.execute_strategy(
                Mock(hooks=[hook_config], name="test_strategy"),
            )
            mock_get_cache.assert_called_once_with(hook_config.name, file_hashes)
            assert result.results[0].id == cached_result.id
            assert result.results[0].status == cached_result.status
            assert result.success
            assert result.cache_hits == 1
            assert result.cache_misses == 0

    def test_execute_with_cache_miss(self, cached_executor) -> None:
        from crackerjack.config.hooks import HookDefinition, HookStrategy

        hook_config = HookDefinition(
            name="uncached - hook", command=["echo", "uncached"],
        )
        strategy = HookStrategy(name="test - cache - miss", hooks=[hook_config])

        with patch.object(
            cached_executor.base_executor, "execute_single_hook",
        ) as mock_execute:
            mock_result = HookResult(
                id="uncached - hook",
                name="uncached - hook",
                status="passed",
                duration=1.0,
            )
            mock_execute.return_value = mock_result

            with patch.object(
                cached_executor.cache, "get_hook_result", return_value=None,
            ):
                result = cached_executor.execute_strategy(strategy)

                assert result.success
                assert len(result.results) == 1
                assert result.results[0].id == mock_result.id
                assert result.results[0].status == mock_result.status
                mock_execute.assert_called_once_with(hook_config)

    def test_cache_statistics(self, cached_executor) -> None:
        stats = cached_executor.get_cache_stats()

        assert "hook_results" in stats
        assert "file_hashes" in stats
        assert "config" in stats

        hook_stats = stats["hook_results"]
        assert "hits" in hook_stats
        assert "misses" in hook_stats
        assert "hit_rate_percent" in hook_stats
        assert "total_entries" in hook_stats

    def test_cache_cleanup(self, cached_executor) -> None:
        cached_executor.invalidate_hook_cache("test_hook")

        cleanup_stats = cached_executor.cleanup_cache()
        assert isinstance(cleanup_stats, dict)

        stats = cached_executor.get_cache_stats()
        assert isinstance(stats, dict)

        expected_categories = {"config", "disk_cache", "file_hashes", "hook_results"}
        assert any(category in stats for category in expected_categories)

        for category in stats.values():
            if isinstance(category, dict):
                assert "hits" in category
                assert "misses" in category
                assert "hit_rate_percent" in category


class TestExecutorErrorHandling:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / error_handling")

    def test_hook_executor_subprocess_error(self, mock_console, mock_pkg_path) -> None:
        executor = HookExecutor(console=mock_console, pkg_path=mock_pkg_path)

        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(
            name="error - hook", command=["nonexistent - command"],
        )

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("Command not found")

            result = executor.execute_single_hook(hook_config)

            assert result.status == "error"
            assert result.name == "error - hook"

    @pytest.mark.asyncio
    async def test_async_executor_subprocess_error(
        self, mock_console, mock_pkg_path,
    ) -> None:
        executor = AsyncHookExecutor(console=mock_console, pkg_path=mock_pkg_path)

        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(
            name="async - error - hook",
            command=["nonexistent - command"],
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_subprocess.side_effect = FileNotFoundError("Command not found")

            result = await executor._execute_single_hook(hook_config)

            assert result.status == "error"
            assert result.name == "async - error - hook"

    def test_cached_executor_cache_corruption(
        self, mock_console, mock_pkg_path,
    ) -> None:
        executor = CachedHookExecutor(console=mock_console, pkg_path=mock_pkg_path)

        with patch.object(executor.cache, "get_hook_result") as mock_get_cache:
            mock_get_cache.side_effect = Exception("Cache corruption")

            from crackerjack.config.hooks import HookDefinition, HookStrategy

            hook_config = HookDefinition(
                name="cache - corruption - hook",
                command=["echo", "test"],
            )
            strategy = HookStrategy(name="test - corruption", hooks=[hook_config])

            with patch.object(
                executor.base_executor, "execute_single_hook",
            ) as mock_execute:
                mock_result = HookResult(
                    id="cache - corruption - hook",
                    name="cache - corruption - hook",
                    status="passed",
                    duration=1.0,
                )
                mock_execute.return_value = mock_result

                result = executor.execute_strategy(strategy)

                assert result.success
                assert len(result.results) == 1
                assert result.results[0].status == "passed"
                mock_execute.assert_called_once()

    def test_executor_resource_cleanup(self, mock_console, mock_pkg_path) -> None:
        executor = HookExecutor(console=mock_console, pkg_path=mock_pkg_path)

        assert hasattr(executor, "_cleanup_resources")

        executor._cleanup_resources()


class TestExecutorPerformance:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / performance")

    def test_hook_executor_timing(self, mock_console, mock_pkg_path) -> None:
        executor = HookExecutor(console=mock_console, pkg_path=mock_pkg_path)

        from crackerjack.config.hooks import HookDefinition

        hook_config = HookDefinition(name="timing - hook", command=["echo", "timing"])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="timing\n", stderr="")

            result = executor.execute_single_hook(hook_config)

            assert result.duration >= 0
            assert isinstance(result.duration, float)

    @pytest.mark.asyncio
    async def test_async_executor_concurrency(
        self, mock_console, mock_pkg_path,
    ) -> None:
        executor = AsyncHookExecutor(console=mock_console, pkg_path=mock_pkg_path)

        hooks = [
            Mock(
                id=f"perf - {i}",
                name=f"perf - hook - {i}",
                command=["echo", str(i)],
                timeout=10,
            )
            for i in range(10)
        ]

        from crackerjack.config.hooks import RetryPolicy

        strategy = Mock()
        strategy.hooks = hooks
        strategy.stage = "performance"
        strategy.max_workers = 5
        strategy.timeout = 30
        strategy.name = "performance"
        strategy.parallel = True
        strategy.retry_policy = RetryPolicy.NONE

        with patch.object(executor, "_execute_single_hook") as mock_execute:

            async def mock_hook_execution(hook):
                await asyncio.sleep(0.001)
                return HookResult(
                    id=str(hook.id),
                    name=str(hook.name),
                    status="passed",
                    duration=0.001,
                )

            mock_execute.side_effect = mock_hook_execution

            import time

            start_time = time.time()
            result = await executor.execute_strategy(strategy)
            end_time = time.time()

            execution_time = end_time - start_time
            assert execution_time < 1.0
            assert len(result.results) == 10

    def test_cached_executor_performance_improvement(
        self, mock_console, mock_pkg_path,
    ) -> None:
        executor = CachedHookExecutor(console=mock_console, pkg_path=mock_pkg_path)

        from crackerjack.config.hooks import HookDefinition, HookStrategy

        hook_config = HookDefinition(
            name="perf - cached - hook",
            command=["echo", "performance"],
        )

        strategy = HookStrategy(name="test - perf", hooks=[hook_config])

        with patch.object(
            executor.base_executor, "execute_single_hook",
        ) as mock_execute:
            mock_result = HookResult(
                id="perf - cached - hook",
                name="perf - cached - hook",
                status="passed",
                duration=1.0,
            )
            mock_execute.return_value = mock_result

            import time

            start_time = time.time()
            result1 = executor.execute_strategy(strategy)
            first_execution_time = time.time() - start_time

            with patch.object(
                executor.cache, "get_hook_result", return_value=mock_result,
            ), patch.object(executor, "_is_cache_valid", return_value=True):
                start_time = time.time()
                result2 = executor.execute_strategy(strategy)
                second_execution_time = time.time() - start_time

                assert second_execution_time < first_execution_time
                assert result1.success == result2.success
                assert len(result1.results) == len(result2.results)
