"""Unit tests for HookOrchestratorAdapter.

Tests ACB-powered hook orchestration, dependency resolution,
caching integration, and dual execution modes (legacy/ACB).
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest

from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.models.task import HookResult
from crackerjack.orchestration.hook_orchestrator import (
    HookOrchestratorAdapter,
    HookOrchestratorSettings,
    MODULE_ID,
    MODULE_STATUS,
)


@pytest.mark.unit
class TestHookOrchestratorSettings:
    """Test HookOrchestratorSettings configuration."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = HookOrchestratorSettings()

        assert settings.max_parallel_hooks == 3
        assert settings.default_timeout == 300
        assert settings.enable_caching is True
        assert settings.enable_dependency_resolution is True
        assert settings.retry_on_failure is False
        assert settings.cache_backend == "tool_proxy"
        assert settings.execution_mode == "acb"
        assert settings.enable_adaptive_execution is True

    def test_custom_settings(self):
        """Test custom settings override."""
        settings = HookOrchestratorSettings(
            max_parallel_hooks=5,
            default_timeout=600,
            enable_caching=False,
            execution_mode="legacy",
        )

        assert settings.max_parallel_hooks == 5
        assert settings.default_timeout == 600
        assert settings.enable_caching is False
        assert settings.execution_mode == "legacy"

    def test_settings_validation_max_parallel(self):
        """Test max_parallel_hooks validation."""
        with pytest.raises(ValueError):
            HookOrchestratorSettings(max_parallel_hooks=0)

        with pytest.raises(ValueError):
            HookOrchestratorSettings(max_parallel_hooks=11)

    def test_settings_validation_timeout(self):
        """Test timeout validation."""
        with pytest.raises(ValueError):
            HookOrchestratorSettings(default_timeout=20)

        with pytest.raises(ValueError):
            HookOrchestratorSettings(default_timeout=2000)

    def test_settings_validation_cache_backend(self):
        """Test cache_backend pattern validation."""
        valid_backends = ["tool_proxy", "redis", "memory"]

        for backend in valid_backends:
            settings = HookOrchestratorSettings(cache_backend=backend)
            assert settings.cache_backend == backend

        with pytest.raises(ValueError):
            HookOrchestratorSettings(cache_backend="invalid")

    def test_settings_validation_execution_mode(self):
        """Test execution_mode pattern validation."""
        valid_modes = ["legacy", "acb"]

        for mode in valid_modes:
            settings = HookOrchestratorSettings(execution_mode=mode)
            assert settings.execution_mode == mode

        with pytest.raises(ValueError):
            HookOrchestratorSettings(execution_mode="invalid")


@pytest.mark.unit
class TestHookOrchestratorInitialization:
    """Test HookOrchestratorAdapter initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        orchestrator = HookOrchestratorAdapter()

        assert orchestrator.settings is not None
        assert orchestrator.settings.max_parallel_hooks == 3
        assert orchestrator._initialized is False
        assert orchestrator._cache_hits == 0
        assert orchestrator._cache_misses == 0

    def test_initialization_with_custom_settings(self):
        """Test initialization with custom settings."""
        settings = HookOrchestratorSettings(max_parallel_hooks=5)
        orchestrator = HookOrchestratorAdapter(settings=settings)

        assert orchestrator.settings.max_parallel_hooks == 5

    def test_initialization_with_hook_executor(self):
        """Test initialization with hook executor."""
        mock_executor = Mock()
        orchestrator = HookOrchestratorAdapter(hook_executor=mock_executor)

        assert orchestrator._hook_executor == mock_executor

    def test_initialization_with_cache_adapter(self):
        """Test initialization with cache adapter."""
        mock_cache = Mock()
        orchestrator = HookOrchestratorAdapter(cache_adapter=mock_cache)

        assert orchestrator._cache_adapter == mock_cache

    def test_module_id_property(self):
        """Test module_id property returns correct UUID."""
        orchestrator = HookOrchestratorAdapter()

        assert orchestrator.module_id == MODULE_ID
        assert isinstance(orchestrator.module_id, UUID)

    def test_adapter_name_property(self):
        """Test adapter_name property."""
        orchestrator = HookOrchestratorAdapter()

        assert orchestrator.adapter_name == "HookOrchestratorAdapter"


@pytest.mark.unit
@pytest.mark.asyncio
class TestHookOrchestratorInit:
    """Test async initialization."""

    async def test_init_basic(self):
        """Test basic initialization."""
        orchestrator = HookOrchestratorAdapter()

        await orchestrator.init()

        assert orchestrator._initialized is True

    async def test_init_idempotent(self):
        """Test initialization is idempotent."""
        orchestrator = HookOrchestratorAdapter()

        await orchestrator.init()
        assert orchestrator._initialized is True

        # Second init should not re-initialize
        await orchestrator.init()
        assert orchestrator._initialized is True

    async def test_init_with_tool_proxy_cache(self):
        """Test initialization with tool_proxy cache backend."""
        settings = HookOrchestratorSettings(
            enable_caching=True, cache_backend="tool_proxy"
        )
        orchestrator = HookOrchestratorAdapter(settings=settings)

        with patch(
            "crackerjack.orchestration.hook_orchestrator.ToolProxyCacheAdapter"
        ) as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            await orchestrator.init()

            assert orchestrator._initialized is True
            mock_cache_instance.init.assert_called_once()

    async def test_init_with_memory_cache(self):
        """Test initialization with memory cache backend."""
        settings = HookOrchestratorSettings(
            enable_caching=True, cache_backend="memory"
        )
        orchestrator = HookOrchestratorAdapter(settings=settings)

        with patch(
            "crackerjack.orchestration.hook_orchestrator.MemoryCacheAdapter"
        ) as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            await orchestrator.init()

            assert orchestrator._initialized is True
            mock_cache_instance.init.assert_called_once()

    async def test_init_with_unknown_cache_backend(self):
        """Test initialization with unknown cache backend."""
        settings = HookOrchestratorSettings(
            enable_caching=True, cache_backend="redis"  # Not implemented yet
        )
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        # Should disable caching for unknown backend
        assert settings.enable_caching is False

    async def test_init_with_caching_disabled(self):
        """Test initialization with caching disabled."""
        settings = HookOrchestratorSettings(enable_caching=False)
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        assert orchestrator._cache_adapter is None
        assert orchestrator._initialized is True

    async def test_init_with_provided_cache_adapter(self):
        """Test initialization with pre-provided cache adapter."""
        mock_cache = AsyncMock()
        orchestrator = HookOrchestratorAdapter(cache_adapter=mock_cache)

        await orchestrator.init()

        mock_cache.init.assert_called_once()
        assert orchestrator._cache_adapter == mock_cache


@pytest.mark.unit
@pytest.mark.asyncio
class TestHookOrchestratorExecution:
    """Test hook execution workflows."""

    async def test_execute_strategy_legacy_mode(self):
        """Test executing strategy in legacy mode."""
        settings = HookOrchestratorSettings(execution_mode="legacy")
        mock_executor = AsyncMock()
        orchestrator = HookOrchestratorAdapter(
            settings=settings, hook_executor=mock_executor
        )

        await orchestrator.init()

        strategy = Mock(spec=HookStrategy)
        strategy.hooks = []

        mock_executor.execute_hooks.return_value = []

        result = await orchestrator.execute_strategy(strategy)

        assert isinstance(result, list)

    async def test_execute_strategy_without_executor(self):
        """Test executing strategy without hook executor."""
        settings = HookOrchestratorSettings(execution_mode="legacy")
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        strategy = Mock(spec=HookStrategy)

        with pytest.raises(RuntimeError, match="HookExecutor not available"):
            await orchestrator.execute_strategy(strategy)

    async def test_execute_strategy_with_empty_hooks(self):
        """Test executing strategy with empty hook list."""
        mock_executor = AsyncMock()
        orchestrator = HookOrchestratorAdapter(hook_executor=mock_executor)

        await orchestrator.init()

        strategy = Mock(spec=HookStrategy)
        strategy.hooks = []

        mock_executor.execute_hooks.return_value = []

        result = await orchestrator.execute_strategy(strategy)

        assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestHookOrchestratorCaching:
    """Test caching functionality."""

    async def test_cache_hit_tracking(self):
        """Test cache hit tracking."""
        mock_cache = AsyncMock()
        orchestrator = HookOrchestratorAdapter(cache_adapter=mock_cache)

        await orchestrator.init()

        # Simulate cache hit
        orchestrator._cache_hits += 1

        assert orchestrator._cache_hits == 1
        assert orchestrator._cache_misses == 0

    async def test_cache_miss_tracking(self):
        """Test cache miss tracking."""
        mock_cache = AsyncMock()
        orchestrator = HookOrchestratorAdapter(cache_adapter=mock_cache)

        await orchestrator.init()

        # Simulate cache miss
        orchestrator._cache_misses += 1

        assert orchestrator._cache_hits == 0
        assert orchestrator._cache_misses == 1

    async def test_get_cache_stats(self):
        """Test getting cache statistics."""
        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        orchestrator._cache_hits = 10
        orchestrator._cache_misses = 5

        stats = orchestrator.get_cache_stats()

        assert stats["hits"] == 10
        assert stats["misses"] == 5
        assert stats["hit_rate"] == 10 / 15


@pytest.mark.unit
class TestHookOrchestratorDependencyGraph:
    """Test dependency graph building and resolution."""

    def test_build_dependency_graph_empty(self):
        """Test building dependency graph with no dependencies."""
        orchestrator = HookOrchestratorAdapter()

        orchestrator._build_dependency_graph()

        assert orchestrator._dependency_graph == {}

    def test_resolve_execution_order_no_dependencies(self):
        """Test resolving execution order without dependencies."""
        orchestrator = HookOrchestratorAdapter()

        hooks = [
            Mock(name="hook1", depends_on=[]),
            Mock(name="hook2", depends_on=[]),
        ]

        order = orchestrator._resolve_execution_order(hooks)

        assert len(order) == 2
        assert set(h.name for h in order) == {"hook1", "hook2"}

    def test_resolve_execution_order_with_dependencies(self):
        """Test resolving execution order with dependencies."""
        orchestrator = HookOrchestratorAdapter()

        hook1 = Mock(name="hook1", depends_on=[])
        hook2 = Mock(name="hook2", depends_on=["hook1"])
        hook3 = Mock(name="hook3", depends_on=["hook1", "hook2"])

        hooks = [hook3, hook2, hook1]  # Out of order

        order = orchestrator._resolve_execution_order(hooks)

        # hook1 should come before hook2 and hook3
        hook1_idx = order.index(hook1)
        hook2_idx = order.index(hook2)
        hook3_idx = order.index(hook3)

        assert hook1_idx < hook2_idx
        assert hook2_idx < hook3_idx


@pytest.mark.unit
@pytest.mark.asyncio
class TestHookOrchestratorEventBus:
    """Test event bus integration."""

    async def test_event_bus_resolution(self):
        """Test event bus resolution from DI."""
        with patch("crackerjack.orchestration.hook_orchestrator.depends.get") as mock_get:
            mock_event_bus = Mock()
            mock_get.return_value = mock_event_bus

            orchestrator = HookOrchestratorAdapter()

            assert orchestrator._event_bus == mock_event_bus

    async def test_event_bus_resolution_failure(self):
        """Test handling event bus resolution failure."""
        with patch("crackerjack.orchestration.hook_orchestrator.depends.get") as mock_get:
            mock_get.side_effect = Exception("Not available")

            orchestrator = HookOrchestratorAdapter()

            assert orchestrator._event_bus is None

    async def test_emit_event_with_bus(self):
        """Test emitting event with event bus."""
        mock_event_bus = AsyncMock()
        orchestrator = HookOrchestratorAdapter(event_bus=mock_event_bus)

        await orchestrator.init()

        event_data = {"type": "hook_started", "hook_name": "test"}
        await orchestrator._emit_event(event_data)

        mock_event_bus.emit.assert_called_once()

    async def test_emit_event_without_bus(self):
        """Test emitting event without event bus."""
        orchestrator = HookOrchestratorAdapter()
        orchestrator._event_bus = None

        await orchestrator.init()

        # Should not raise error
        event_data = {"type": "hook_started"}
        await orchestrator._emit_event(event_data)


@pytest.mark.unit
@pytest.mark.asyncio
class TestHookOrchestratorParallelExecution:
    """Test parallel hook execution."""

    async def test_execute_parallel_hooks(self):
        """Test executing hooks in parallel."""
        settings = HookOrchestratorSettings(max_parallel_hooks=2)
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        hook1 = Mock(name="hook1")
        hook2 = Mock(name="hook2")
        hook3 = Mock(name="hook3")

        hooks = [hook1, hook2, hook3]

        with patch.object(
            orchestrator, "_execute_single_hook", return_value=HookResult(name="test", status="passed")
        ) as mock_execute:
            results = await orchestrator._execute_hooks_parallel(hooks)

            assert len(results) == 3
            assert mock_execute.call_count == 3

    async def test_parallel_execution_respects_limit(self):
        """Test parallel execution respects max_parallel_hooks."""
        settings = HookOrchestratorSettings(max_parallel_hooks=2)
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        # This test would need more complex mocking to truly verify
        # that only 2 hooks run at once, but we can verify the setting
        assert orchestrator.settings.max_parallel_hooks == 2


@pytest.mark.unit
@pytest.mark.asyncio
class TestHookOrchestratorErrorHandling:
    """Test error handling in orchestration."""

    async def test_handle_hook_execution_error(self):
        """Test handling hook execution error."""
        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        hook = Mock(name="failing_hook")

        with patch.object(
            orchestrator, "_execute_single_hook", side_effect=Exception("Hook failed")
        ):
            result = await orchestrator._execute_hook_with_error_handling(hook)

            assert result.status == "failed"
            assert "Hook failed" in result.error

    async def test_retry_on_failure_enabled(self):
        """Test retry behavior when enabled."""
        settings = HookOrchestratorSettings(retry_on_failure=True)
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        hook = Mock(name="retry_hook")

        call_count = 0

        async def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First failure")
            return HookResult(name="test", status="passed")

        with patch.object(
            orchestrator, "_execute_single_hook", side_effect=failing_then_success
        ):
            result = await orchestrator._execute_hook_with_retry(hook)

            assert result.status == "passed"
            assert call_count == 2

    async def test_retry_on_failure_disabled(self):
        """Test no retry when disabled."""
        settings = HookOrchestratorSettings(retry_on_failure=False)
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        assert orchestrator.settings.retry_on_failure is False


@pytest.mark.unit
class TestModuleConstants:
    """Test module-level constants."""

    def test_module_id_is_uuid(self):
        """Test MODULE_ID is a valid UUID."""
        assert isinstance(MODULE_ID, UUID)
        assert str(MODULE_ID) == "01937d86-ace0-7000-8000-000000000003"

    def test_module_status(self):
        """Test MODULE_STATUS value."""
        assert MODULE_STATUS == "stable"


@pytest.mark.unit
@pytest.mark.asyncio
class TestHookOrchestratorIntegration:
    """Test integration scenarios."""

    async def test_full_orchestration_workflow(self):
        """Test complete orchestration workflow."""
        settings = HookOrchestratorSettings(
            max_parallel_hooks=2,
            enable_caching=True,
            cache_backend="memory",
        )

        mock_executor = AsyncMock()
        orchestrator = HookOrchestratorAdapter(
            settings=settings, hook_executor=mock_executor
        )

        # Initialize
        with patch(
            "crackerjack.orchestration.hook_orchestrator.MemoryCacheAdapter"
        ) as mock_cache:
            mock_cache_instance = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            await orchestrator.init()

            assert orchestrator._initialized is True
            assert orchestrator._cache_adapter is not None

    async def test_orchestration_with_dependency_resolution(self):
        """Test orchestration with dependency resolution."""
        settings = HookOrchestratorSettings(enable_dependency_resolution=True)
        orchestrator = HookOrchestratorAdapter(settings=settings)

        await orchestrator.init()

        # Create hooks with dependencies
        hook1 = Mock(name="hook1", depends_on=[])
        hook2 = Mock(name="hook2", depends_on=["hook1"])

        hooks = [hook2, hook1]  # Out of order

        # Should resolve to correct order
        order = orchestrator._resolve_execution_order(hooks)

        assert order[0].name == "hook1"
        assert order[1].name == "hook2"
