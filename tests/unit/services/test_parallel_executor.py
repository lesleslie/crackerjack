"""Unit tests for parallel_executor.

Tests parallel hook execution, async command execution,
dependency analysis, and execution strategies.
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.config.hooks import HookDefinition, SecurityLevel
from crackerjack.models.results import ExecutionResult
from crackerjack.services.parallel_executor import (
    AsyncCommandExecutor,
    ExecutionStrategy,
    ParallelHookExecutor,
)


@pytest.mark.unit
class TestExecutionStrategyEnum:
    """Test ExecutionStrategy enum."""

    def test_execution_strategy_values(self):
        """Test ExecutionStrategy enum values."""
        assert ExecutionStrategy.SEQUENTIAL == "sequential"
        assert ExecutionStrategy.PARALLEL_SAFE == "parallel_safe"
        assert ExecutionStrategy.PARALLEL_AGGRESSIVE == "parallel_aggressive"


@pytest.mark.unit
class TestParallelHookExecutorInitialization:
    """Test ParallelHookExecutor initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        mock_logger = Mock()
        mock_cache = Mock()

        executor = ParallelHookExecutor(
            logger=mock_logger,
            cache=mock_cache,
        )

        assert executor.max_workers == 3
        assert executor.timeout_seconds == 300
        assert executor.strategy == ExecutionStrategy.PARALLEL_SAFE

    def test_initialization_custom_params(self):
        """Test initialization with custom parameters."""
        mock_logger = Mock()
        mock_cache = Mock()

        executor = ParallelHookExecutor(
            logger=mock_logger,
            cache=mock_cache,
            max_workers=5,
            timeout_seconds=600,
            strategy=ExecutionStrategy.SEQUENTIAL,
        )

        assert executor.max_workers == 5
        assert executor.timeout_seconds == 600
        assert executor.strategy == ExecutionStrategy.SEQUENTIAL


@pytest.mark.unit
class TestParallelHookExecutorDependencyAnalysis:
    """Test hook dependency analysis."""

    def test_analyze_hook_dependencies_empty(self):
        """Test analyzing empty hook list."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        groups = executor.analyze_hook_dependencies([])

        assert groups == {}

    def test_analyze_hook_dependencies_formatting(self):
        """Test analyzing formatting hooks."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook = Mock(spec=HookDefinition)
        hook.is_formatting = True
        hook.security_level = SecurityLevel.LOW

        groups = executor.analyze_hook_dependencies([hook])

        assert "formatting" in groups
        assert len(groups["formatting"]) == 1

    def test_analyze_hook_dependencies_security(self):
        """Test analyzing security hooks."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook = Mock(spec=HookDefinition)
        hook.is_formatting = False
        hook.security_level = SecurityLevel.CRITICAL

        groups = executor.analyze_hook_dependencies([hook])

        assert "security" in groups
        assert len(groups["security"]) == 1

    def test_analyze_hook_dependencies_validation(self):
        """Test analyzing validation hooks."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook = Mock(spec=HookDefinition)
        hook.is_formatting = False
        hook.name = "check-yaml"
        hook.security_level = SecurityLevel.MEDIUM

        groups = executor.analyze_hook_dependencies([hook])

        assert "validation" in groups
        assert len(groups["validation"]) == 1

    def test_analyze_hook_dependencies_comprehensive(self):
        """Test analyzing comprehensive hooks."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook = Mock(spec=HookDefinition)
        hook.is_formatting = False
        hook.name = "ruff"
        hook.security_level = SecurityLevel.MEDIUM

        groups = executor.analyze_hook_dependencies([hook])

        assert "comprehensive" in groups
        assert len(groups["comprehensive"]) == 1


@pytest.mark.unit
class TestParallelHookExecutorParallelizability:
    """Test can_execute_in_parallel logic."""

    def test_can_execute_in_parallel_different_security_levels(self):
        """Test hooks with different security levels cannot run in parallel."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook1 = Mock(spec=HookDefinition)
        hook1.security_level = SecurityLevel.LOW
        hook1.is_formatting = False

        hook2 = Mock(spec=HookDefinition)
        hook2.security_level = SecurityLevel.HIGH
        hook2.is_formatting = False

        result = executor.can_execute_in_parallel(hook1, hook2)

        assert result is False

    def test_can_execute_in_parallel_formatting_and_non_formatting(self):
        """Test formatting and non-formatting hooks cannot run in parallel."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook1 = Mock(spec=HookDefinition)
        hook1.security_level = SecurityLevel.LOW
        hook1.is_formatting = True
        hook1.name = "ruff-format"

        hook2 = Mock(spec=HookDefinition)
        hook2.security_level = SecurityLevel.LOW
        hook2.is_formatting = False
        hook2.name = "ruff-check"

        result = executor.can_execute_in_parallel(hook1, hook2)

        assert result is False

    def test_can_execute_in_parallel_both_formatting(self):
        """Test two formatting hooks can run in parallel."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook1 = Mock(spec=HookDefinition)
        hook1.security_level = SecurityLevel.LOW
        hook1.is_formatting = True
        hook1.name = "ruff-format"

        hook2 = Mock(spec=HookDefinition)
        hook2.security_level = SecurityLevel.LOW
        hook2.is_formatting = True
        hook2.name = "black"

        result = executor.can_execute_in_parallel(hook1, hook2)

        assert result is True

    def test_can_execute_in_parallel_validation_hooks(self):
        """Test validation hooks can run in parallel."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook1 = Mock(spec=HookDefinition)
        hook1.security_level = SecurityLevel.MEDIUM
        hook1.is_formatting = False
        hook1.name = "check-yaml"

        hook2 = Mock(spec=HookDefinition)
        hook2.security_level = SecurityLevel.MEDIUM
        hook2.is_formatting = False
        hook2.name = "check-json"

        result = executor.can_execute_in_parallel(hook1, hook2)

        assert result is True


@pytest.mark.unit
class TestParallelHookExecutorExecution:
    """Test hook execution."""

    @pytest.mark.asyncio
    async def test_execute_hooks_parallel_sequential_strategy(self):
        """Test executing hooks with sequential strategy."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
            strategy=ExecutionStrategy.SEQUENTIAL,
        )

        hook1 = Mock(spec=HookDefinition)
        hook1.name = "hook1"
        hook1.is_formatting = False
        hook1.security_level = SecurityLevel.MEDIUM

        async def mock_runner(hook):
            return ExecutionResult(
                operation_id=hook.name,
                success=True,
                duration_seconds=0.1,
            )

        result = await executor.execute_hooks_parallel([hook1], mock_runner)

        assert result.total_operations == 1
        assert result.successful_operations == 1
        assert result.failed_operations == 0

    @pytest.mark.asyncio
    async def test_execute_hooks_parallel_groups(self):
        """Test executing hooks in parallel groups."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
            strategy=ExecutionStrategy.PARALLEL_SAFE,
        )

        hook1 = Mock(spec=HookDefinition)
        hook1.name = "format1"
        hook1.is_formatting = True
        hook1.security_level = SecurityLevel.LOW

        hook2 = Mock(spec=HookDefinition)
        hook2.name = "format2"
        hook2.is_formatting = True
        hook2.security_level = SecurityLevel.LOW

        async def mock_runner(hook):
            await asyncio.sleep(0.01)
            return ExecutionResult(
                operation_id=hook.name,
                success=True,
                duration_seconds=0.01,
            )

        result = await executor.execute_hooks_parallel([hook1, hook2], mock_runner)

        assert result.total_operations == 2
        assert result.successful_operations == 2

    @pytest.mark.asyncio
    async def test_execute_hooks_parallel_with_failure(self):
        """Test executing hooks with failure."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        hook1 = Mock(spec=HookDefinition)
        hook1.name = "hook1"
        hook1.is_formatting = False
        hook1.security_level = SecurityLevel.MEDIUM

        hook2 = Mock(spec=HookDefinition)
        hook2.name = "hook2"
        hook2.is_formatting = False
        hook2.security_level = SecurityLevel.MEDIUM

        call_count = 0

        async def mock_runner(hook):
            nonlocal call_count
            call_count += 1
            return ExecutionResult(
                operation_id=hook.name,
                success=call_count == 1,
                duration_seconds=0.1,
                error="Error" if call_count == 2 else None,
            )

        result = await executor.execute_hooks_parallel([hook1, hook2], mock_runner)

        assert result.total_operations == 2
        assert result.successful_operations == 1
        assert result.failed_operations == 1


@pytest.mark.unit
class TestAsyncCommandExecutorInitialization:
    """Test AsyncCommandExecutor initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        mock_logger = Mock()
        mock_cache = Mock()

        executor = AsyncCommandExecutor(
            logger=mock_logger,
            cache=mock_cache,
        )

        assert executor.max_workers == 4
        assert executor.cache_results is True

    def test_initialization_custom_params(self):
        """Test initialization with custom parameters."""
        mock_logger = Mock()
        mock_cache = Mock()

        executor = AsyncCommandExecutor(
            logger=mock_logger,
            cache=mock_cache,
            max_workers=8,
            cache_results=False,
        )

        assert executor.max_workers == 8
        assert executor.cache_results is False


@pytest.mark.unit
class TestAsyncCommandExecutorCacheKey:
    """Test cache key generation."""

    def test_get_cache_key_command_only(self):
        """Test cache key with command only."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        key = executor._get_cache_key(["echo", "test"], None)

        assert key == "echo test"

    def test_get_cache_key_with_cwd(self):
        """Test cache key with cwd."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        cwd = Path("/test/dir")
        key = executor._get_cache_key(["echo", "test"], cwd)

        assert key == "echo test:/test/dir"


@pytest.mark.unit
class TestAsyncCommandExecutorExecution:
    """Test command execution."""

    @pytest.mark.asyncio
    async def test_execute_command_success(self):
        """Test successful command execution."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
            cache_results=False,
        )

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "output"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = await executor.execute_command(["echo", "test"])

            assert result.success is True
            assert result.output == "output"
            assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_command_failure(self):
        """Test failed command execution."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
            cache_results=False,
        )

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "error message"
            mock_run.return_value = mock_result

            result = await executor.execute_command(["false"])

            assert result.success is False
            assert result.error == "error message"
            assert result.exit_code == 1

    @pytest.mark.asyncio
    async def test_execute_command_with_cache_hit(self):
        """Test command execution with cache hit."""
        mock_cache = Mock()
        cached_result = ExecutionResult(
            operation_id="test",
            success=True,
            duration_seconds=0.1,
            output="cached",
        )
        mock_cache.get.return_value = cached_result

        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=mock_cache,
            cache_results=True,
        )

        result = await executor.execute_command(["echo", "test"])

        assert result.success is True
        assert result.output == "cached"

    @pytest.mark.asyncio
    async def test_execute_command_caches_on_success(self):
        """Test command result is cached on success."""
        mock_cache = Mock()
        mock_cache.get.return_value = None

        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=mock_cache,
            cache_results=True,
        )

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "output"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            await executor.execute_command(["echo", "test"])

            mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_commands_batch(self):
        """Test batch command execution."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
            cache_results=False,
        )

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "output"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            commands = [
                (["echo", "test1"], None),
                (["echo", "test2"], None),
            ]

            results = await executor.execute_commands_batch(commands)

            assert len(results) == 2
            assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_commands_batch_with_failure(self):
        """Test batch execution with one failure."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
            cache_results=False,
        )

        call_count = 0

        def mock_run_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = Mock()
            mock_result.returncode = 0 if call_count == 1 else 1
            mock_result.stdout = "output" if call_count == 1 else ""
            mock_result.stderr = "" if call_count == 1 else "error"
            return mock_result

        with patch("subprocess.run", side_effect=mock_run_side_effect):
            commands = [
                (["echo", "test1"], None),
                (["false"], None),
            ]

            results = await executor.execute_commands_batch(commands)

            assert len(results) == 2
            assert results[0].success is True
            assert results[1].success is False


@pytest.mark.unit
class TestParallelHookExecutorServiceMethods:
    """Test ServiceProtocol methods."""

    def test_health_check(self):
        """Test health_check method."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        assert executor.health_check() is True

    def test_is_healthy(self):
        """Test is_healthy method."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        assert executor.is_healthy() is True

    def test_metrics(self):
        """Test metrics method."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        metrics = executor.metrics()

        assert isinstance(metrics, dict)

    def test_shutdown(self):
        """Test shutdown method."""
        executor = ParallelHookExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        # Should not raise error
        executor.shutdown()


@pytest.mark.unit
class TestAsyncCommandExecutorServiceMethods:
    """Test AsyncCommandExecutor ServiceProtocol methods."""

    def test_is_healthy(self):
        """Test is_healthy method."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        assert executor.is_healthy() is True

    def test_metrics(self):
        """Test metrics method."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        metrics = executor.metrics()

        assert isinstance(metrics, dict)

    def test_shutdown(self):
        """Test shutdown method."""
        executor = AsyncCommandExecutor(
            logger=Mock(),
            cache=Mock(),
        )

        # Should not raise error
        executor.shutdown()
