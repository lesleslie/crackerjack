import pytest


@pytest.mark.unit
class TestMCPProgressMonitor:
    def test_progress_monitor_import(self) -> None:
        import crackerjack.mcp.progress_monitor

        assert crackerjack.mcp.progress_monitor is not None


@pytest.mark.unit
class TestMCPDashboard:
    def test_dashboard_import(self) -> None:
        import crackerjack.mcp.dashboard

        assert crackerjack.mcp.dashboard is not None


@pytest.mark.unit
class TestMCPProgressComponents:
    def test_progress_components_import(self) -> None:
        import crackerjack.mcp.progress_components

        assert crackerjack.mcp.progress_components is not None


@pytest.mark.unit
class TestMCPEnhancedProgressMonitor:
    def test_enhanced_progress_monitor_import(self) -> None:
        import crackerjack.mcp.enhanced_progress_monitor

        assert crackerjack.mcp.enhanced_progress_monitor is not None


@pytest.mark.unit
class TestMCPFileMonitor:
    def test_file_monitor_import(self) -> None:
        import crackerjack.mcp.file_monitor

        assert crackerjack.mcp.file_monitor is not None


@pytest.mark.unit
class TestMCPWebSocketServer:
    def test_websocket_server_import(self) -> None:
        import crackerjack.mcp.websocket_server

        assert crackerjack.mcp.websocket_server is not None


@pytest.mark.unit
class TestMCPServer:
    def test_mcp_server_import(self) -> None:
        import crackerjack.mcp.server

        assert crackerjack.mcp.server is not None
