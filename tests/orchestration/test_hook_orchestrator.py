"""Unit tests for HookOrchestratorAdapter (Phase 3.1).

Tests the core orchestration adapter including:
- Initialization and dependency graph building
- Dual execution modes (legacy vs ACB)
- Dependency resolution via topological sort
- Cache integration
- Statistics tracking
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.config.hooks import HookDefinition, HookStage, HookStrategy, SecurityLevel
from crackerjack.executors.hook_executor import HookExecutionResult
from crackerjack.models.task import HookResult
from crackerjack.orchestration.cache.memory_cache import MemoryCacheAdapter
from crackerjack.orchestration.hook_orchestrator import (
    HookOrchestratorAdapter,
    HookOrchestratorSettings,
)


@pytest.fixture
def sample_hooks() -> list[HookDefinition]:
    """Create sample hook definitions for testing."""
    return [
        HookDefinition(
            name="ruff-format",
            command=["uv", "run", "ruff", "format"],
            timeout=60,
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
            use_precommit_legacy=False,
        ),
        HookDefinition(
            name="ruff-check",
            command=["uv", "run", "ruff", "check"],
            timeout=60,
            stage=HookStage.FAST,
            security_level=SecurityLevel.MEDIUM,
            use_precommit_legacy=False,
        ),
        HookDefinition(
            name="bandit",
            command=["uv", "run", "bandit", "-c", "pyproject.toml", "-r", "crackerjack"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.HIGH,
            use_precommit_legacy=False,
        ),
    ]


@pytest.fixture
def dependent_hooks() -> list[HookDefinition]:
    """Create hooks with dependencies for testing resolution."""
    return [
        HookDefinition(
            name="gitleaks",
            command=["uv", "run", "gitleaks", "detect"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.CRITICAL,
            use_precommit_legacy=False,
        ),
        HookDefinition(
            name="bandit",
            command=["uv", "run", "bandit", "-c", "pyproject.toml", "-r", "crackerjack"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.HIGH,
            use_precommit_legacy=False,
        ),
        HookDefinition(
            name="zuban",
            command=["uv", "run", "zuban"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.MEDIUM,
            use_precommit_legacy=False,
        ),
        HookDefinition(
            name="refurb",
            command=["uv", "run", "refurb", "."],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.LOW,
            use_precommit_legacy=False,
        ),
    ]


@pytest.fixture
def fast_strategy(sample_hooks: list[HookDefinition]) -> HookStrategy:
    """Create fast hook strategy for testing."""
    return HookStrategy(
        name="fast",
        hooks=[sample_hooks[0], sample_hooks[1]],  # ruff-format, ruff-check
        parallel=True,
        max_workers=2,
    )


@pytest.fixture
def comprehensive_strategy(sample_hooks: list[HookDefinition]) -> HookStrategy:
    """Create comprehensive strategy for testing."""
    return HookStrategy(
        name="comprehensive",
        hooks=sample_hooks,
        parallel=False,
        max_workers=1,
    )


@pytest.fixture
def mock_hook_executor():
    """Create mock HookExecutor for testing legacy mode."""
    executor = MagicMock()
    executor.execute_strategy.return_value = HookExecutionResult(
        strategy_name="fast",
        results=[
            HookResult(
                id="ruff-format",
                name="ruff-format",
                status="passed",
                duration=1.0,
            ),
            HookResult(
                id="ruff-check",
                name="ruff-check",
                status="passed",
                duration=2.0,
            ),
        ],
        total_duration=3.0,
        success=True,
    )
    return executor


class TestHookOrchestratorInitialization:
    """Test orchestrator initialization."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test basic initialization."""
        settings = HookOrchestratorSettings(
            max_parallel_hooks=5,
            enable_caching=True,
            cache_backend="memory",
        )

        orchestrator = HookOrchestratorAdapter(settings=settings)

        assert orchestrator.settings.max_parallel_hooks == 5
        assert orchestrator.settings.enable_caching is True
        assert not orchestrator._initialized

    @pytest.mark.asyncio
    async def test_init_builds_dependency_graph(self):
        """Test that init builds dependency graph."""
        orchestrator = HookOrchestratorAdapter()

        await orchestrator.init()

        assert orchestrator._initialized
        assert len(orchestrator._dependency_graph) > 0

        # Verify some known dependencies
        assert "bandit" in orchestrator._dependency_graph
        assert "gitleaks" in orchestrator._dependency_graph["bandit"]
        assert "refurb" in orchestrator._dependency_graph
        assert "zuban" in orchestrator._dependency_graph["refurb"]

    @pytest.mark.asyncio
    async def test_init_initializes_cache(self):
        """Test that init initializes cache adapter."""
        settings = HookOrchestratorSettings(
            enable_caching=True,
            cache_backend="memory",
        )

        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        assert orchestrator._cache_adapter is not None
        assert orchestrator._cache_adapter._initialized

    @pytest.mark.asyncio
    async def test_init_with_provided_cache(self):
        """Test initialization with externally provided cache."""
        cache = MemoryCacheAdapter()
        await cache.init()

        orchestrator = HookOrchestratorAdapter(cache_adapter=cache)

        await orchestrator.init()

        assert orchestrator._cache_adapter is cache

    @pytest.mark.asyncio
    async def test_double_init_is_safe(self):
        """Test that calling init twice doesn't cause issues."""
        orchestrator = HookOrchestratorAdapter()

        await orchestrator.init()
        await orchestrator.init()  # Should be no-op

        assert orchestrator._initialized


class TestHookOrchestratorLegacyMode:
    """Test legacy execution mode."""

    @pytest.mark.asyncio
    async def test_legacy_mode_delegates_to_executor(
        self, fast_strategy: HookStrategy, mock_hook_executor
    ):
        """Test that legacy mode delegates to HookExecutor."""
        settings = HookOrchestratorSettings(execution_mode="legacy")
        orchestrator = HookOrchestratorAdapter(
            settings=settings,
            hook_executor=mock_hook_executor,
        )

        await orchestrator.init()

        results = await orchestrator.execute_strategy(fast_strategy)

        # Verify executor was called
        mock_hook_executor.execute_strategy.assert_called_once_with(fast_strategy)

        # Verify results were returned
        assert len(results) == 2
        assert results[0].name == "ruff-format"
        assert results[1].name == "ruff-check"

    @pytest.mark.asyncio
    async def test_legacy_mode_without_executor_raises(self, fast_strategy: HookStrategy):
        """Test that legacy mode without executor raises error."""
        settings = HookOrchestratorSettings(execution_mode="legacy")
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        with pytest.raises(RuntimeError, match="Legacy mode requires HookExecutor"):
            await orchestrator.execute_strategy(fast_strategy)


class TestHookOrchestratorACBMode:
    """Test ACB execution mode."""

    @pytest.mark.asyncio
    async def test_acb_mode_placeholder_execution(self, fast_strategy: HookStrategy):
        """Test ACB mode placeholder execution (Phase 3-7)."""
        settings = HookOrchestratorSettings(execution_mode="acb", enable_caching=False)
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        results = await orchestrator.execute_strategy(fast_strategy)

        # Should return placeholder results
        assert len(results) == 2
        assert all(r.status == "passed" for r in results)
        # Placeholder results have no issues_found
        assert all((r.issues_found is None or len(r.issues_found) == 0) for r in results)

    @pytest.mark.asyncio
    async def test_acb_mode_with_caching(self, fast_strategy: HookStrategy):
        """Test ACB mode with caching enabled."""
        settings = HookOrchestratorSettings(
            execution_mode="acb",
            enable_caching=True,
            cache_backend="memory",
        )
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        # First execution - should miss cache
        results1 = await orchestrator.execute_strategy(fast_strategy)
        assert orchestrator._cache_misses == 2
        assert orchestrator._cache_hits == 0

        # Second execution - should hit cache
        results2 = await orchestrator.execute_strategy(fast_strategy)
        assert orchestrator._cache_hits == 2
        assert orchestrator._cache_misses == 2

        # Results should be identical
        assert len(results1) == len(results2)


class TestDependencyResolution:
    """Test dependency resolution logic."""

    @pytest.mark.asyncio
    async def test_dependency_resolution(self, dependent_hooks: list[HookDefinition]):
        """Test topological sort of dependencies."""
        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        # Original order: gitleaks, bandit, zuban, refurb
        # Expected order: gitleaks, zuban, bandit, refurb
        # (gitleaks first, zuban before refurb, bandit after gitleaks)

        ordered = orchestrator._resolve_dependencies(dependent_hooks)

        names = [h.name for h in ordered]

        # gitleaks must come before bandit
        assert names.index("gitleaks") < names.index("bandit")

        # zuban must come before refurb
        assert names.index("zuban") < names.index("refurb")

    @pytest.mark.asyncio
    async def test_hooks_without_dependencies_maintain_order(self, sample_hooks: list[HookDefinition]):
        """Test that hooks without dependencies maintain original order."""
        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        ordered = orchestrator._resolve_dependencies(sample_hooks)

        # None of these hooks have dependencies, so order should be preserved
        assert [h.name for h in ordered] == [h.name for h in sample_hooks]


class TestCacheIntegration:
    """Test cache integration."""

    @pytest.mark.asyncio
    async def test_cache_statistics(self, fast_strategy: HookStrategy):
        """Test cache statistics tracking."""
        settings = HookOrchestratorSettings(
            execution_mode="acb",
            enable_caching=True,
            cache_backend="memory",
        )
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        # Execute twice
        await orchestrator.execute_strategy(fast_strategy)
        await orchestrator.execute_strategy(fast_strategy)

        stats = await orchestrator.get_cache_stats()

        assert stats["caching_enabled"] is True
        assert stats["cache_backend"] == "memory"
        assert stats["cache_hits"] == 2
        assert stats["cache_misses"] == 2
        assert stats["total_requests"] == 4
        assert stats["hit_ratio"] == 0.5

    @pytest.mark.asyncio
    async def test_cache_disabled(self, fast_strategy: HookStrategy):
        """Test behavior when caching is disabled."""
        settings = HookOrchestratorSettings(
            execution_mode="acb",
            enable_caching=False,
        )
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        await orchestrator.execute_strategy(fast_strategy)

        stats = await orchestrator.get_cache_stats()

        assert stats["caching_enabled"] is False
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0


class TestExecutionModes:
    """Test different execution modes."""

    @pytest.mark.asyncio
    async def test_parallel_execution(self, fast_strategy: HookStrategy):
        """Test parallel execution mode."""
        orchestrator = HookOrchestratorAdapter(
            settings=HookOrchestratorSettings(execution_mode="acb")
        )

        await orchestrator.init()

        # Fast strategy has parallel=True
        results = await orchestrator.execute_strategy(fast_strategy)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_sequential_execution(self, comprehensive_strategy: HookStrategy):
        """Test sequential execution mode."""
        orchestrator = HookOrchestratorAdapter(
            settings=HookOrchestratorSettings(execution_mode="acb")
        )

        await orchestrator.init()

        # Comprehensive strategy has parallel=False
        results = await orchestrator.execute_strategy(comprehensive_strategy)

        assert len(results) == 3


class TestModuleProperties:
    """Test MODULE_ID and adapter properties."""

    @pytest.mark.asyncio
    async def test_module_id(self):
        """Test MODULE_ID property."""
        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        assert orchestrator.module_id is not None
        assert str(orchestrator.module_id).startswith("01937d86-ace0-7000")

    @pytest.mark.asyncio
    async def test_adapter_name(self):
        """Test adapter name property."""
        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        assert orchestrator.adapter_name == "Hook Orchestrator"


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_execute_before_init_raises(self, fast_strategy: HookStrategy):
        """Test that executing before init raises error."""
        orchestrator = HookOrchestratorAdapter()

        with pytest.raises(RuntimeError, match="not initialized"):
            await orchestrator.execute_strategy(fast_strategy)

    @pytest.mark.asyncio
    async def test_invalid_execution_mode_raises(self, fast_strategy: HookStrategy):
        """Test that invalid execution mode raises error."""
        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        with pytest.raises(ValueError, match="Invalid execution mode"):
            await orchestrator.execute_strategy(fast_strategy, execution_mode="invalid")
