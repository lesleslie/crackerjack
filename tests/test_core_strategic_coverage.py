from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowOrchestrator
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.core.enhanced_container import EnhancedDependencyContainer
from crackerjack.core.performance import PerformanceMonitor


class TestEnhancedDependencyContainer:
    @pytest.fixture
    def enhanced_container(self):
        return EnhancedDependencyContainer()

    def test_init(self, enhanced_container) -> None:
        assert enhanced_container is not None
        assert hasattr(enhanced_container, "_services")
        assert hasattr(enhanced_container, "_singletons")

    def test_register_service(self, enhanced_container) -> None:
        mock_service = Mock()

        enhanced_container.register_singleton(str, instance=mock_service)

        assert enhanced_container.is_registered(str)

    def test_get_service(self, enhanced_container) -> None:
        mock_service = Mock()
        enhanced_container.register_singleton(str, instance=mock_service)

        retrieved = enhanced_container.get(str)

        assert retrieved == mock_service

    def test_get_service_not_found(self, enhanced_container) -> None:
        with pytest.raises(ValueError):
            enhanced_container.get(int)

    def test_has_service(self, enhanced_container) -> None:
        assert not enhanced_container.is_registered(str)

        enhanced_container.register_singleton(str, instance=Mock())

        assert enhanced_container.is_registered(str)

    def test_register_factory(self, enhanced_container) -> None:
        def factory():
            return Mock()

        enhanced_container.register_singleton(str, factory=factory)

        assert enhanced_container.is_registered(str)

    def test_get_from_factory(self, enhanced_container) -> None:
        def factory():
            mock_service = Mock()
            mock_service.name = "from_factory"
            return mock_service

        enhanced_container.register_singleton(str, factory=factory)

        service = enhanced_container.get(str)

        assert service.name == "from_factory"

    def test_singleton_factory(self, enhanced_container) -> None:
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return Mock(call_count=call_count)

        enhanced_container.register_singleton(dict, factory=factory)

        service1 = enhanced_container.get(dict)

        service2 = enhanced_container.get(dict)

        assert service1 is service2
        assert call_count == 1

    def test_dispose_services(self, enhanced_container) -> None:
        enhanced_container.register_singleton(int, instance=Mock())
        enhanced_container.register_singleton(float, instance=Mock())

        assert enhanced_container.is_registered(int)
        assert enhanced_container.is_registered(float)

        enhanced_container.dispose()

        assert enhanced_container.is_registered(int)
        assert enhanced_container.is_registered(float)

    def test_service_info(self, enhanced_container) -> None:
        info = enhanced_container.get_service_info()
        assert isinstance(info, dict)
        assert len(info) == 0

        enhanced_container.register_singleton(int, instance=Mock())
        enhanced_container.register_singleton(float, instance=Mock())

        info = enhanced_container.get_service_info()
        assert len(info) == 2
        assert "builtins.int" in info
        assert "builtins.float" in info

    def test_get_optional(self, enhanced_container) -> None:
        service = enhanced_container.get_optional(int)
        assert service is None

        default_service = Mock()
        service = enhanced_container.get_optional(int, default=default_service)
        assert service is default_service

        registered_service = Mock()
        enhanced_container.register_singleton(int, instance=registered_service)
        service = enhanced_container.get_optional(int)
        assert service is registered_service


class TestPerformanceMonitor:
    @pytest.fixture
    def performance_monitor(self):
        return PerformanceMonitor()

    def test_init(self, performance_monitor) -> None:
        assert performance_monitor is not None
        assert hasattr(performance_monitor, "metrics")
        assert isinstance(performance_monitor.metrics, dict)
        assert len(performance_monitor.metrics) == 0

    def test_time_operation_decorator(self, performance_monitor) -> None:
        @performance_monitor.time_operation("test_operation")
        def test_function() -> str:
            return "result"

        result = test_function()

        assert result == "result"
        assert "test_operation" in performance_monitor.metrics
        assert len(performance_monitor.metrics["test_operation"]) == 1
        assert performance_monitor.metrics["test_operation"][0] >= 0

    def test_record_metric(self, performance_monitor) -> None:
        performance_monitor.record_metric("test_metric", 42.5)

        assert "test_metric" in performance_monitor.metrics
        assert len(performance_monitor.metrics["test_metric"]) == 1
        assert performance_monitor.metrics["test_metric"][0] == 42.5

    def test_get_stats(self, performance_monitor) -> None:
        stats = performance_monitor.get_stats("nonexistent")
        assert stats == {}

        performance_monitor.record_metric("test_metric", 10.0)
        performance_monitor.record_metric("test_metric", 20.0)
        performance_monitor.record_metric("test_metric", 30.0)

        stats = performance_monitor.get_stats("test_metric")
        assert stats["count"] == 3
        assert stats["total"] == 60.0
        assert stats["avg"] == 20.0
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0

    def test_print_stats_no_console(self, performance_monitor) -> None:
        performance_monitor.record_metric("test_metric", 15.0)

        performance_monitor.print_stats("test_metric")
        performance_monitor.print_stats()

    def test_print_stats_with_console(self, performance_monitor) -> None:
        from unittest.mock import Mock

        mock_console = Mock()
        performance_monitor.console = mock_console
        performance_monitor.record_metric("test_metric", 15.0)

        performance_monitor.print_stats("test_metric")

        mock_console.print.assert_called_once()

    def test_multiple_metrics(self, performance_monitor) -> None:
        performance_monitor.record_metric("metric1", 10.0)
        performance_monitor.record_metric("metric1", 15.0)
        performance_monitor.record_metric("metric2", 20.0)

        assert len(performance_monitor.metrics) == 2
        assert len(performance_monitor.metrics["metric1"]) == 2
        assert len(performance_monitor.metrics["metric2"]) == 1

        stats1 = performance_monitor.get_stats("metric1")
        assert stats1["count"] == 2
        assert stats1["avg"] == 12.5

        stats2 = performance_monitor.get_stats("metric2")
        assert stats2["count"] == 1
        assert stats2["avg"] == 20.0


class TestAsyncWorkflowOrchestrator:
    @pytest.fixture
    def mock_container(self):
        container = Mock()
        container.get_console.return_value = Mock()
        container.get_filesystem.return_value = Mock()
        container.get_config_service.return_value = Mock()
        container.get_hook_manager.return_value = Mock()
        container.get_test_manager.return_value = Mock()
        return container

    @pytest.fixture
    def async_orchestrator(self):
        from unittest.mock import Mock

        console = Mock()
        return AsyncWorkflowOrchestrator(console=console, pkg_path=Path("/ tmp / test"))

    def test_basic_attributes(self) -> None:
        from crackerjack.core.async_workflow_orchestrator import (
            AsyncWorkflowOrchestrator,
        )

        assert hasattr(AsyncWorkflowOrchestrator, "__init__")
        assert (
            AsyncWorkflowOrchestrator.__module__
            == "crackerjack.core.async_workflow_orchestrator"
        )

    def test_module_constants(self) -> None:
        from crackerjack.core import async_workflow_orchestrator

        assert hasattr(async_workflow_orchestrator, "AsyncWorkflowOrchestrator")

        import inspect

        source = inspect.getsource(async_workflow_orchestrator)
        assert "from pathlib import Path" in source
        assert "from rich.console import Console" in source

    def test_constructor_signature(self) -> None:
        import inspect

        from crackerjack.core.async_workflow_orchestrator import (
            AsyncWorkflowOrchestrator,
        )

        signature = inspect.signature(AsyncWorkflowOrchestrator.__init__)
        params = list(signature.parameters.keys())

        assert "self" in params
        assert "console" in params
        assert "pkg_path" in params
        assert "dry_run" in params
        assert "web_job_id" in params


class TestAutofixCoordinator:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Mock(),
            "pkg_path": Path("/ tmp / test"),
        }

    @pytest.fixture
    def autofix_coordinator(self, mock_dependencies):
        return AutofixCoordinator(**mock_dependencies)

    def test_init(self, autofix_coordinator, mock_dependencies) -> None:
        assert autofix_coordinator.console == mock_dependencies["console"]
        assert autofix_coordinator.pkg_path == mock_dependencies["pkg_path"]
        assert hasattr(autofix_coordinator, "logger")

    def test_apply_fast_stage_fixes(self, autofix_coordinator) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "fixed 2 files"

            result = autofix_coordinator.apply_fast_stage_fixes()

            assert isinstance(result, bool)

    def test_apply_comprehensive_stage_fixes(self, autofix_coordinator) -> None:
        mock_hook_result = Mock()
        mock_hook_result.name = "ruff"
        mock_hook_result.status = "Failed"
        hook_results = [mock_hook_result]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "fixed"

            result = autofix_coordinator.apply_comprehensive_stage_fixes(hook_results)

            assert isinstance(result, bool)

    def test_validate_fix_command(self, autofix_coordinator) -> None:
        valid_cmd = ["uv", "run", "ruff", "check", "."]
        assert autofix_coordinator.validate_fix_command(valid_cmd) is True

        invalid_cmd = ["python", "script.py"]
        assert autofix_coordinator.validate_fix_command(invalid_cmd) is False

    def test_should_skip_autofix(self, autofix_coordinator) -> None:
        mock_hook_result = Mock()
        mock_hook_result.raw_output = "ModuleNotFoundError: No module named 'test'"

        hook_results = [mock_hook_result]

        result = autofix_coordinator.should_skip_autofix(hook_results)
        assert result is True

        mock_hook_result.raw_output = "Some other error"
        result = autofix_coordinator.should_skip_autofix(hook_results)
        assert result is False

    def test_validate_hook_result(self, autofix_coordinator) -> None:
        valid_result = Mock()
        valid_result.name = "ruff"
        valid_result.status = "Failed"

        assert autofix_coordinator.validate_hook_result(valid_result) is True

        invalid_result = Mock()

        if hasattr(invalid_result, "name"):
            delattr(invalid_result, "name")

        assert autofix_coordinator.validate_hook_result(invalid_result) is False
