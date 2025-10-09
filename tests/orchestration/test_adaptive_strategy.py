"""Unit tests for AdaptiveExecutionStrategy (Phase 5-7).

Tests dependency-aware batching, wave computation, parallel execution within waves,
and early exit on critical failures.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel
from crackerjack.models.task import HookResult
from crackerjack.orchestration.strategies.adaptive_strategy import AdaptiveExecutionStrategy


@pytest.fixture
def simple_hooks() -> list[HookDefinition]:
    """Create hooks with no dependencies."""
    return [
        HookDefinition(
            name="hook1",
            command=["hook1"],
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
        ),
        HookDefinition(
            name="hook2",
            command=["hook2"],
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
        ),
        HookDefinition(
            name="hook3",
            command=["hook3"],
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
        ),
    ]


@pytest.fixture
def dependent_hooks() -> list[HookDefinition]:
    """Create hooks with simple dependencies.

    Dependency graph:
    gitleaks → bandit
    zuban → refurb
    """
    return [
        HookDefinition(
            name="gitleaks",
            command=["gitleaks"],
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.CRITICAL,
        ),
        HookDefinition(
            name="bandit",
            command=["bandit"],
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.HIGH,
        ),
        HookDefinition(
            name="zuban",
            command=["zuban"],
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.MEDIUM,
        ),
        HookDefinition(
            name="refurb",
            command=["refurb"],
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.LOW,
        ),
    ]


@pytest.fixture
def diamond_hooks() -> list[HookDefinition]:
    """Create hooks with diamond dependency pattern.

    Dependency graph:
         A
        / \\
       B   C
        \\ /
         D

    Execution order: Wave 1: [A], Wave 2: [B, C], Wave 3: [D]
    """
    return [
        HookDefinition(
            name="A",
            command=["A"],
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
        ),
        HookDefinition(
            name="B",
            command=["B"],
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
        ),
        HookDefinition(
            name="C",
            command=["C"],
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
        ),
        HookDefinition(
            name="D",
            command=["D"],
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
        ),
    ]


class TestAdaptiveStrategyInitialization:
    """Test adaptive strategy initialization."""

    def test_initialization_with_defaults(self):
        """Test initialization with default parameters."""
        strategy = AdaptiveExecutionStrategy(dependency_graph={})

        assert strategy.dependency_graph == {}
        assert strategy.max_parallel == 4
        assert strategy.default_timeout == 300
        assert strategy.stop_on_critical_failure is True

    def test_initialization_with_custom_params(self):
        """Test initialization with custom parameters."""
        dependency_graph = {"bandit": ["gitleaks"]}
        strategy = AdaptiveExecutionStrategy(
            dependency_graph=dependency_graph,
            max_parallel=8,
            default_timeout=600,
            stop_on_critical_failure=False,
        )

        assert strategy.dependency_graph == dependency_graph
        assert strategy.max_parallel == 8
        assert strategy.default_timeout == 600
        assert strategy.stop_on_critical_failure is False


class TestWaveComputation:
    """Test topological sort and wave computation."""

    def test_zero_dependencies_single_wave(self, simple_hooks: list[HookDefinition]):
        """Test that hooks with no dependencies all go in wave 1."""
        strategy = AdaptiveExecutionStrategy(dependency_graph={})

        waves = strategy._compute_execution_waves(simple_hooks)

        assert len(waves) == 1
        assert len(waves[0]) == 3
        assert set(h.name for h in waves[0]) == {"hook1", "hook2", "hook3"}

    def test_simple_dependencies_two_waves(self, dependent_hooks: list[HookDefinition]):
        """Test simple dependencies create correct waves."""
        dependency_graph = {
            "bandit": ["gitleaks"],
            "refurb": ["zuban"],
        }
        strategy = AdaptiveExecutionStrategy(dependency_graph=dependency_graph)

        waves = strategy._compute_execution_waves(dependent_hooks)

        # Wave 1: gitleaks, zuban (no dependencies)
        # Wave 2: bandit, refurb (depend on wave 1)
        assert len(waves) == 2

        wave1_names = {h.name for h in waves[0]}
        wave2_names = {h.name for h in waves[1]}

        assert wave1_names == {"gitleaks", "zuban"}
        assert wave2_names == {"bandit", "refurb"}

    def test_diamond_dependencies_three_waves(self, diamond_hooks: list[HookDefinition]):
        """Test diamond dependency pattern creates 3 waves."""
        dependency_graph = {
            "B": ["A"],
            "C": ["A"],
            "D": ["B", "C"],
        }
        strategy = AdaptiveExecutionStrategy(dependency_graph=dependency_graph)

        waves = strategy._compute_execution_waves(diamond_hooks)

        # Wave 1: [A]
        # Wave 2: [B, C]
        # Wave 3: [D]
        assert len(waves) == 3

        assert [h.name for h in waves[0]] == ["A"]
        assert set(h.name for h in waves[1]) == {"B", "C"}
        assert [h.name for h in waves[2]] == ["D"]

    def test_linear_dependencies_sequential_waves(self):
        """Test linear dependencies create N waves for N hooks."""
        hooks = [
            HookDefinition(
                name=f"hook{i}",
                command=[f"hook{i}"],
                stage=HookStage.FAST,
                security_level=SecurityLevel.LOW,
            )
            for i in range(1, 5)
        ]

        # Linear chain: hook1 → hook2 → hook3 → hook4
        dependency_graph = {
            "hook2": ["hook1"],
            "hook3": ["hook2"],
            "hook4": ["hook3"],
        }
        strategy = AdaptiveExecutionStrategy(dependency_graph=dependency_graph)

        waves = strategy._compute_execution_waves(hooks)

        # Should create 4 waves, each with one hook
        assert len(waves) == 4
        assert all(len(wave) == 1 for wave in waves)
        assert [w[0].name for w in waves] == ["hook1", "hook2", "hook3", "hook4"]

    def test_circular_dependency_raises_error(self):
        """Test that circular dependencies raise ValueError."""
        hooks = [
            HookDefinition(
                # id removed
                name="A",
                command=["A"],
                # language removed
                stage=HookStage.FAST,
                security_level=SecurityLevel.LOW,
            ),
            HookDefinition(
                # id removed
                name="B",
                command=["B"],
                # language removed
                stage=HookStage.FAST,
                security_level=SecurityLevel.LOW,
            ),
        ]

        # Circular dependency: A → B → A
        dependency_graph = {
            "A": ["B"],
            "B": ["A"],
        }
        strategy = AdaptiveExecutionStrategy(dependency_graph=dependency_graph)

        with pytest.raises(ValueError, match="Circular dependency"):
            strategy._compute_execution_waves(hooks)

    def test_dependency_on_missing_hook_ignored(self, simple_hooks: list[HookDefinition]):
        """Test that dependencies on missing hooks are ignored."""
        # hook1 depends on "missing_hook" which isn't in the hook list
        dependency_graph = {
            "hook1": ["missing_hook"],
        }
        strategy = AdaptiveExecutionStrategy(dependency_graph=dependency_graph)

        waves = strategy._compute_execution_waves(simple_hooks)

        # Should treat hook1 as having no dependencies (missing_hook ignored)
        assert len(waves) == 1
        assert len(waves[0]) == 3


class TestAdaptiveExecution:
    """Test adaptive execution with waves."""

    @pytest.mark.asyncio
    async def test_execute_empty_hooks(self):
        """Test execution with empty hook list."""
        strategy = AdaptiveExecutionStrategy(dependency_graph={})

        results = await strategy.execute(hooks=[])

        assert results == []

    @pytest.mark.asyncio
    async def test_execute_single_wave(self, simple_hooks: list[HookDefinition]):
        """Test execution of single wave (all parallel)."""
        strategy = AdaptiveExecutionStrategy(dependency_graph={})

        # Mock executor that returns success
        async def mock_executor(hook: HookDefinition) -> HookResult:
            await asyncio.sleep(0.01)  # Simulate work
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=0.01,
                # output removed: "Mock success",
            )

        results = await strategy.execute(
            hooks=simple_hooks,
            executor_callable=mock_executor,
        )

        assert len(results) == 3
        assert all(r.status == "passed" for r in results)
        assert set(r.name for r in results) == {"hook1", "hook2", "hook3"}

    @pytest.mark.asyncio
    async def test_execute_multiple_waves(self, dependent_hooks: list[HookDefinition]):
        """Test execution across multiple waves."""
        dependency_graph = {
            "bandit": ["gitleaks"],
            "refurb": ["zuban"],
        }
        strategy = AdaptiveExecutionStrategy(dependency_graph=dependency_graph)

        # Track execution order
        execution_order = []

        async def mock_executor(hook: HookDefinition) -> HookResult:
            execution_order.append(hook.name)
            await asyncio.sleep(0.01)
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=0.01,
                # output removed: "Mock success",
            )

        results = await strategy.execute(
            hooks=dependent_hooks,
            executor_callable=mock_executor,
        )

        assert len(results) == 4
        assert all(r.status == "passed" for r in results)

        # Verify dependency ordering: gitleaks before bandit, zuban before refurb
        assert execution_order.index("gitleaks") < execution_order.index("bandit")
        assert execution_order.index("zuban") < execution_order.index("refurb")

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling for slow hooks."""
        # Create hook with short timeout
        hook = HookDefinition(
            name="slow_hook",
            command=["slow_hook"],
            timeout=1,  # 1 second timeout
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
        )

        strategy = AdaptiveExecutionStrategy(dependency_graph={})

        async def slow_executor(hook: HookDefinition) -> HookResult:
            await asyncio.sleep(10)  # Will timeout (10s > 1s timeout)
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=10.0,
                # output removed: "Should not reach here",
            )

        # Execute with hook that has 1s timeout
        results = await strategy.execute(
            hooks=[hook],
            executor_callable=slow_executor,
        )

        assert len(results) == 1
        assert results[0].status == "timeout"
        # Timeout result created, no output field to check

    @pytest.mark.asyncio
    async def test_exception_handling(self, simple_hooks: list[HookDefinition]):
        """Test exception handling during hook execution."""
        strategy = AdaptiveExecutionStrategy(dependency_graph={})

        async def failing_executor(hook: HookDefinition) -> HookResult:
            if hook.name == "hook2":
                raise ValueError("Mock error")
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=0.0,
                # output removed: "Success",
            )

        results = await strategy.execute(
            hooks=simple_hooks,
            executor_callable=failing_executor,
        )

        assert len(results) == 3
        # hook1 and hook3 should pass
        assert sum(1 for r in results if r.status == "passed") == 2
        # hook2 should have error
        assert sum(1 for r in results if r.status == "error") == 1

        error_result = next(r for r in results if r.status == "error")
        assert error_result.name == "hook2"
        assert error_result.name == "hook2"


class TestCriticalFailureHandling:
    """Test early exit on critical failures."""

    @pytest.mark.asyncio
    async def test_critical_failure_stops_execution(self):
        """Test that critical hook failure stops subsequent waves."""
        hooks = [
            HookDefinition(
                # id removed
                name="gitleaks",
                command=["gitleaks"],
                # language removed
                stage=HookStage.COMPREHENSIVE,
                security_level=SecurityLevel.CRITICAL,
            ),
            HookDefinition(
                # id removed
                name="bandit",
                command=["bandit"],
                # language removed
                stage=HookStage.COMPREHENSIVE,
                security_level=SecurityLevel.HIGH,
            ),
        ]

        dependency_graph = {"bandit": ["gitleaks"]}
        strategy = AdaptiveExecutionStrategy(
            dependency_graph=dependency_graph,
            stop_on_critical_failure=True,
        )

        async def mock_executor(hook: HookDefinition) -> HookResult:
            if hook.name == "gitleaks":
                # Critical hook fails
                return HookResult(
                    id=hook.name, name=hook.name,
                    status="failed",
                    duration=0.0,
                    # output removed: "Critical failure",
                )
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=0.0,
                # output removed: "Success",
            )

        results = await strategy.execute(
            hooks=hooks,
            executor_callable=mock_executor,
        )

        # Only gitleaks should execute, bandit should be skipped
        assert len(results) == 1
        assert results[0].name == "gitleaks"
        assert results[0].status == "failed"

    @pytest.mark.asyncio
    async def test_non_critical_failure_continues(self):
        """Test that non-critical failure does not stop execution."""
        hooks = [
            HookDefinition(
                # id removed
                name="hook1",
                command=["hook1"],
                # language removed
                stage=HookStage.FAST,
                security_level=SecurityLevel.LOW,  # Not critical
            ),
            HookDefinition(
                # id removed
                name="hook2",
                command=["hook2"],
                # language removed
                stage=HookStage.FAST,
                security_level=SecurityLevel.LOW,
            ),
        ]

        dependency_graph = {"hook2": ["hook1"]}
        strategy = AdaptiveExecutionStrategy(
            dependency_graph=dependency_graph,
            stop_on_critical_failure=True,
        )

        async def mock_executor(hook: HookDefinition) -> HookResult:
            if hook.name == "hook1":
                # Non-critical hook fails
                return HookResult(
                    id=hook.name, name=hook.name,
                    status="failed",
                    duration=0.0,
                    # output removed: "Non-critical failure",
                )
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=0.0,
                # output removed: "Success",
            )

        results = await strategy.execute(
            hooks=hooks,
            executor_callable=mock_executor,
        )

        # Both hooks should execute
        assert len(results) == 2
        assert results[0].name == "hook1"
        assert results[0].status == "failed"
        assert results[1].name == "hook2"
        assert results[1].status == "passed"

    @pytest.mark.asyncio
    async def test_stop_on_critical_failure_disabled(self):
        """Test execution continues when stop_on_critical_failure is False."""
        hooks = [
            HookDefinition(
                # id removed
                name="gitleaks",
                command=["gitleaks"],
                # language removed
                stage=HookStage.COMPREHENSIVE,
                security_level=SecurityLevel.CRITICAL,
            ),
            HookDefinition(
                # id removed
                name="bandit",
                command=["bandit"],
                # language removed
                stage=HookStage.COMPREHENSIVE,
                security_level=SecurityLevel.HIGH,
            ),
        ]

        dependency_graph = {"bandit": ["gitleaks"]}
        strategy = AdaptiveExecutionStrategy(
            dependency_graph=dependency_graph,
            stop_on_critical_failure=False,  # Disabled
        )

        async def mock_executor(hook: HookDefinition) -> HookResult:
            if hook.name == "gitleaks":
                # Critical hook fails
                return HookResult(
                    id=hook.name, name=hook.name,
                    status="failed",
                    duration=0.0,
                    # output removed: "Critical failure",
                )
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=0.0,
                # output removed: "Success",
            )

        results = await strategy.execute(
            hooks=hooks,
            executor_callable=mock_executor,
        )

        # Both hooks should execute
        assert len(results) == 2
        assert results[0].name == "gitleaks"
        assert results[0].status == "failed"
        assert results[1].name == "bandit"
        assert results[1].status == "passed"


class TestResourceLimiting:
    """Test resource limiting with semaphore."""

    @pytest.mark.asyncio
    async def test_max_parallel_enforced(self, simple_hooks: list[HookDefinition]):
        """Test that max_parallel limits concurrent executions."""
        strategy = AdaptiveExecutionStrategy(
            dependency_graph={},
            max_parallel=1,  # Only 1 concurrent execution
        )

        concurrent_count = 0
        max_concurrent = 0

        async def tracking_executor(hook: HookDefinition) -> HookResult:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)  # Simulate work
            concurrent_count -= 1
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=0.01,
                # output removed: "Success",
            )

        await strategy.execute(
            hooks=simple_hooks,
            executor_callable=tracking_executor,
        )

        # With max_parallel=1, should never have more than 1 concurrent
        assert max_concurrent == 1

    @pytest.mark.asyncio
    async def test_max_parallel_override(self, simple_hooks: list[HookDefinition]):
        """Test that execute() can override max_parallel."""
        strategy = AdaptiveExecutionStrategy(
            dependency_graph={},
            max_parallel=1,  # Default is 1
        )

        concurrent_count = 0
        max_concurrent = 0

        async def tracking_executor(hook: HookDefinition) -> HookResult:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)
            concurrent_count -= 1
            return HookResult(
                id=hook.name, name=hook.name,
                status="passed",
                duration=0.01,
                # output removed: "Success",
            )

        await strategy.execute(
            hooks=simple_hooks,
            max_parallel=3,  # Override to 3
            executor_callable=tracking_executor,
        )

        # Should allow up to 3 concurrent executions
        assert max_concurrent <= 3
        assert max_concurrent >= 2  # With 3 hooks, should reach at least 2


class TestExecutionOrder:
    """Test get_execution_order method."""

    def test_get_execution_order_single_wave(self, simple_hooks: list[HookDefinition]):
        """Test execution order for hooks with no dependencies."""
        strategy = AdaptiveExecutionStrategy(dependency_graph={})

        order = strategy.get_execution_order(simple_hooks)

        assert len(order) == 1
        assert len(order[0]) == 3

    def test_get_execution_order_multiple_waves(self, dependent_hooks: list[HookDefinition]):
        """Test execution order for hooks with dependencies."""
        dependency_graph = {
            "bandit": ["gitleaks"],
            "refurb": ["zuban"],
        }
        strategy = AdaptiveExecutionStrategy(dependency_graph=dependency_graph)

        order = strategy.get_execution_order(dependent_hooks)

        assert len(order) == 2
        assert len(order[0]) == 2  # gitleaks, zuban
        assert len(order[1]) == 2  # bandit, refurb

    def test_get_execution_order_circular_dependency_fallback(self):
        """Test fallback to sequential for circular dependencies."""
        hooks = [
            HookDefinition(
                # id removed
                name="A",
                command=["A"],
                # language removed
                stage=HookStage.FAST,
                security_level=SecurityLevel.LOW,
            ),
            HookDefinition(
                # id removed
                name="B",
                command=["B"],
                # language removed
                stage=HookStage.FAST,
                security_level=SecurityLevel.LOW,
            ),
        ]

        dependency_graph = {"A": ["B"], "B": ["A"]}
        strategy = AdaptiveExecutionStrategy(dependency_graph=dependency_graph)

        order = strategy.get_execution_order(hooks)

        # Should fall back to sequential (one hook per batch)
        assert len(order) == 2
        assert all(len(batch) == 1 for batch in order)
