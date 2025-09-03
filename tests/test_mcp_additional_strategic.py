import pytest


@pytest.mark.unit
class TestMCPServiceWatchdog:
    def test_service_watchdog_import(self) -> None:
        import crackerjack.mcp.service_watchdog

        assert crackerjack.mcp.service_watchdog is not None


@pytest.mark.unit
class TestMCPTaskManager:
    def test_task_manager_import(self) -> None:
        import crackerjack.mcp.task_manager

        assert crackerjack.mcp.task_manager is not None
