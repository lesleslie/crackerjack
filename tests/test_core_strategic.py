import pytest


@pytest.mark.unit
class TestAutofixCoordinator:
    def test_autofix_coordinator_import(self) -> None:
        import crackerjack.core.autofix_coordinator

        assert crackerjack.core.autofix_coordinator is not None


@pytest.mark.unit
class TestServerManager:
    def test_server_manager_import(self) -> None:
        import crackerjack.services.server_manager

        assert crackerjack.services.server_manager is not None
