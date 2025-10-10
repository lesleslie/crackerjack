"""Unit tests for execution strategies (Phase 3.2).

Tests both ParallelExecutionStrategy and SequentialExecutionStrategy to ensure:
- Parallel execution with semaphore resource limiting
- Sequential execution with early exit on critical failures
- Timeout handling
- Exception isolation
- Execution ordering
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel
from crackerjack.models.task import HookResult
from crackerjack.orchestration.strategies.parallel_strategy import ParallelExecutionStrategy
from crackerjack.orchestration.strategies.sequential_strategy import SequentialExecutionStrategy


@pytest.fixture
def sample_hooks() -> list[HookDefinition]:
    """Create sample hook definitions for testing."""
    return [
        HookDefinition(
            name="hook1",
            command=["python", "-m", "hook1"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.LOW,
            use_precommit_legacy=False,
        ),
        HookDefinition(
            name="hook2",
            command=["python", "-m", "hook2"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.MEDIUM,
            use_precommit_legacy=False,
        ),
        HookDefinition(
            name="hook3",
            command=["python", "-m", "hook3"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.HIGH,
            use_precommit_legacy=False,
        ),
    ]


@pytest.fixture
def critical_hook() -> HookDefinition:
    """Create critical security hook for testing early exit."""
    return HookDefinition(
        name="critical_hook",
        command=["python", "-m", "critical_hook"],
        timeout=60,
        stage=HookStage.COMPREHENSIVE,
        security_level=SecurityLevel.CRITICAL,
        use_precommit_legacy=False,
    )


class TestParallelExecutionStrategy:
    """Test ParallelExecutionStrategy functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test strategy initialization."""
        strategy = ParallelExecutionStrategy(max_parallel=5, default_timeout=600)

        assert strategy.max_parallel == 5
        assert strategy.default_timeout == 600

    @pytest.mark.asyncio
    async def test_empty_hooks_list(self):
        """Test execution with empty hooks list."""
        strategy = ParallelExecutionStrategy()

        results = await strategy.execute(hooks=[])

        assert results == []

    @pytest.mark.asyncio
    async def test_successful_execution(self, sample_hooks: list[HookDefinition]):
        """Test successful parallel execution."""
        strategy = ParallelExecutionStrategy(max_parallel=3)

        # Mock executor that returns success
        async def mock_executor(hook: HookDefinition) -> HookResult:
            await asyncio.sleep(0.1)  # Simulate work
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.1,
            )

        results = await strategy.execute(
            hooks=sample_hooks,
            executor_callable=mock_executor,
        )

        assert len(results) == 3
        assert all(r.status == "passed" for r in results)
        assert [r.name for r in results] == ["hook1", "hook2", "hook3"]

    @pytest.mark.asyncio
    async def test_timeout_handling(self, sample_hooks: list[HookDefinition]):
        """Test timeout handling in parallel execution."""
        strategy = ParallelExecutionStrategy(default_timeout=1)

        # Mock executor that times out
        async def slow_executor(hook: HookDefinition) -> HookResult:
            await asyncio.sleep(10)  # This will timeout
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=10.0,
            )

        # Override timeout for specific hook
        sample_hooks[0].timeout = 0.1

        results = await strategy.execute(
            hooks=[sample_hooks[0]],
            executor_callable=slow_executor,
        )

        assert len(results) == 1
        assert results[0].status == "timeout"
        assert results[0].issues_found and any("timed out" in issue.lower() for issue in results[0].issues_found)

    @pytest.mark.asyncio
    async def test_exception_isolation(self, sample_hooks: list[HookDefinition]):
        """Test that exception in one hook doesn't stop others."""
        strategy = ParallelExecutionStrategy()

        call_count = 0

        async def mixed_executor(hook: HookDefinition) -> HookResult:
            nonlocal call_count
            call_count += 1

            if hook.name == "hook2":
                raise ValueError("Simulated error")

            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.1,
            )

        results = await strategy.execute(
            hooks=sample_hooks,
            executor_callable=mixed_executor,
        )

        # All hooks should have been attempted
        assert call_count == 3
        assert len(results) == 3

        # hook2 should have error, others should pass
        assert results[0].status == "passed"  # hook1
        assert results[1].status == "error"  # hook2
        assert results[2].status == "passed"  # hook3

    @pytest.mark.asyncio
    async def test_semaphore_limiting(self):
        """Test that semaphore limits concurrent executions."""
        strategy = ParallelExecutionStrategy(max_parallel=2)

        max_concurrent = 0
        current_concurrent = 0

        async def tracking_executor(hook: HookDefinition) -> HookResult:
            nonlocal max_concurrent, current_concurrent
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)

            await asyncio.sleep(0.1)

            current_concurrent -= 1

            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.1,
            )

        # Create 5 hooks
        hooks = [
            HookDefinition(
                name=f"hook{i}",
                command=["python", "-m", f"hook{i}"],
                timeout=60,
                stage=HookStage.COMPREHENSIVE,
                security_level=SecurityLevel.LOW,
                use_precommit_legacy=False,
            )
            for i in range(5)
        ]

        await strategy.execute(
            hooks=hooks,
            max_parallel=2,
            executor_callable=tracking_executor,
        )

        # Max concurrent should never exceed semaphore limit
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_get_execution_order(self, sample_hooks: list[HookDefinition]):
        """Test execution order batching."""
        strategy = ParallelExecutionStrategy()

        batches = strategy.get_execution_order(sample_hooks)

        # Parallel strategy should return all hooks in single batch
        assert len(batches) == 1
        assert len(batches[0]) == 3


class TestSequentialExecutionStrategy:
    """Test SequentialExecutionStrategy functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test strategy initialization."""
        strategy = SequentialExecutionStrategy(
            default_timeout=600,
            stop_on_critical_failure=True,
        )

        assert strategy.default_timeout == 600
        assert strategy.stop_on_critical_failure is True

    @pytest.mark.asyncio
    async def test_empty_hooks_list(self):
        """Test execution with empty hooks list."""
        strategy = SequentialExecutionStrategy()

        results = await strategy.execute(hooks=[])

        assert results == []

    @pytest.mark.asyncio
    async def test_successful_execution(self, sample_hooks: list[HookDefinition]):
        """Test successful sequential execution."""
        strategy = SequentialExecutionStrategy()

        execution_order = []

        async def mock_executor(hook: HookDefinition) -> HookResult:
            execution_order.append(hook.name)
            await asyncio.sleep(0.05)
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.05,
            )

        results = await strategy.execute(
            hooks=sample_hooks,
            executor_callable=mock_executor,
        )

        assert len(results) == 3
        assert all(r.status == "passed" for r in results)

        # Verify sequential execution order
        assert execution_order == ["hook1", "hook2", "hook3"]

    @pytest.mark.asyncio
    async def test_early_exit_on_critical_failure(
        self, sample_hooks: list[HookDefinition], critical_hook: HookDefinition
    ):
        """Test early exit when critical hook fails."""
        strategy = SequentialExecutionStrategy(stop_on_critical_failure=True)

        # Insert critical hook in the middle
        hooks = [sample_hooks[0], critical_hook, sample_hooks[1], sample_hooks[2]]

        execution_order = []

        async def mock_executor(hook: HookDefinition) -> HookResult:
            execution_order.append(hook.name)

            if hook.name == "critical_hook":
                return HookResult(
                    id=hook.name,
                    name=hook.name,
                    status="failed",
                    duration=0.1,
                )

            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.1,
            )

        results = await strategy.execute(
            hooks=hooks,
            executor_callable=mock_executor,
        )

        # Should stop after critical hook fails
        assert len(results) == 2  # hook1 + critical_hook only
        assert execution_order == ["hook1", "critical_hook"]

        assert results[0].status == "passed"
        assert results[1].status == "failed"

    @pytest.mark.asyncio
    async def test_no_early_exit_when_disabled(
        self, sample_hooks: list[HookDefinition], critical_hook: HookDefinition
    ):
        """Test no early exit when stop_on_critical_failure=False."""
        strategy = SequentialExecutionStrategy(stop_on_critical_failure=False)

        hooks = [sample_hooks[0], critical_hook, sample_hooks[1]]

        async def mock_executor(hook: HookDefinition) -> HookResult:
            if hook.name == "critical_hook":
                return HookResult(
                    id=hook.name,
                    name=hook.name,
                    status="failed",
                    duration=0.1,
                )

            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.1,
            )

        results = await strategy.execute(
            hooks=hooks,
            executor_callable=mock_executor,
        )

        # Should execute all hooks despite critical failure
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_timeout_handling(self, sample_hooks: list[HookDefinition]):
        """Test timeout handling in sequential execution."""
        strategy = SequentialExecutionStrategy(default_timeout=1)

        async def slow_executor(hook: HookDefinition) -> HookResult:
            await asyncio.sleep(10)
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=10.0,
            )

        sample_hooks[0].timeout = 0.1

        results = await strategy.execute(
            hooks=[sample_hooks[0]],
            executor_callable=slow_executor,
        )

        assert len(results) == 1
        assert results[0].status == "timeout"

    @pytest.mark.asyncio
    async def test_exception_handling(self, sample_hooks: list[HookDefinition]):
        """Test exception handling in sequential execution."""
        strategy = SequentialExecutionStrategy(stop_on_critical_failure=False)

        async def failing_executor(hook: HookDefinition) -> HookResult:
            if hook.name == "hook2":
                raise RuntimeError("Simulated error")

            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.1,
            )

        results = await strategy.execute(
            hooks=sample_hooks,
            executor_callable=failing_executor,
        )

        assert len(results) == 3
        assert results[0].status == "passed"
        assert results[1].status == "error"
        assert results[2].status == "passed"

    @pytest.mark.asyncio
    async def test_get_execution_order(self, sample_hooks: list[HookDefinition]):
        """Test execution order batching."""
        strategy = SequentialExecutionStrategy()

        batches = strategy.get_execution_order(sample_hooks)

        # Sequential strategy should return one hook per batch
        assert len(batches) == 3
        assert all(len(batch) == 1 for batch in batches)
