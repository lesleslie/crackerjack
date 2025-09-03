import pytest


@pytest.mark.unit
class TestMCPServerCore:
    def test_mcp_server_core_import(self) -> None:
        from crackerjack.mcp.server_core import create_mcp_server

        assert create_mcp_server is not None


@pytest.mark.unit
class TestMCPServiceWatchdog:
    def test_service_watchdog_import(self) -> None:
        from crackerjack.mcp.service_watchdog import ServiceConfig, ServiceWatchdog

        assert ServiceWatchdog is not None
        assert ServiceConfig is not None


@pytest.mark.unit
class TestMCPState:
    def test_mcp_state_import(self) -> None:
        from crackerjack.mcp.state import Issue, SessionState, StageStatus

        assert SessionState is not None
        assert StageStatus is not None
        assert Issue is not None

    def test_stage_status_enum(self) -> None:
        from crackerjack.mcp.state import StageStatus

        assert hasattr(StageStatus, "__members__")
        assert len(list(StageStatus)) > 0


@pytest.mark.unit
class TestMCPTaskManager:
    def test_task_manager_import(self) -> None:
        from crackerjack.mcp.task_manager import AsyncTaskManager, TaskInfo

        assert AsyncTaskManager is not None
        assert TaskInfo is not None


@pytest.mark.unit
class TestMCPCoreTools:
    def test_core_tools_import(self) -> None:
        import crackerjack.mcp.tools.core_tools

        assert crackerjack.mcp.tools.core_tools is not None


@pytest.mark.unit
class TestMCPExecutionTools:
    def test_execution_tools_import(self) -> None:
        import crackerjack.mcp.tools.execution_tools

        assert crackerjack.mcp.tools.execution_tools is not None


@pytest.mark.unit
class TestMCPMonitoringTools:
    def test_monitoring_tools_import(self) -> None:
        import crackerjack.mcp.tools.monitoring_tools

        assert crackerjack.mcp.tools.monitoring_tools is not None


@pytest.mark.unit
class TestMCPProgressTools:
    def test_progress_tools_import(self) -> None:
        import crackerjack.mcp.tools.progress_tools

        assert crackerjack.mcp.tools.progress_tools is not None


@pytest.mark.unit
class TestMCPWebSocketApp:
    def test_websocket_app_import(self) -> None:
        import crackerjack.mcp.websocket.app

        assert crackerjack.mcp.websocket.app is not None


@pytest.mark.unit
class TestMCPWebSocketEndpoints:
    def test_endpoints_import(self) -> None:
        import crackerjack.mcp.websocket.endpoints

        assert crackerjack.mcp.websocket.endpoints is not None


@pytest.mark.unit
class TestMCPWebSocketJobs:
    def test_jobs_import(self) -> None:
        from crackerjack.mcp.websocket.jobs import JobManager

        assert JobManager is not None


@pytest.mark.unit
class TestMCPWebSocketServer:
    def test_websocket_server_import(self) -> None:
        from crackerjack.mcp.websocket.server import WebSocketServer

        assert WebSocketServer is not None


@pytest.mark.unit
class TestMCPWebSocketHandler:
    def test_websocket_handler_import(self) -> None:
        import crackerjack.mcp.websocket.websocket_handler

        assert crackerjack.mcp.websocket.websocket_handler is not None
