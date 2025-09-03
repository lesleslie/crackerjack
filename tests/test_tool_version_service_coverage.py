import tempfile

import pytest

from crackerjack.services.tool_version_service import (
    ToolVersionService,
    VersionInfo,
)


class TestVersionInfo:
    def test_version_info_basic_creation(self):
        version_info = VersionInfo(tool_name="pytest", current_version="7.4.0")
        assert version_info.tool_name == "pytest"
        assert version_info.current_version == "7.4.0"
        assert version_info.latest_version is None
        assert version_info.update_available is False
        assert version_info.error is None

    def test_version_info_with_update_available(self):
        version_info = VersionInfo(
            tool_name="ruff",
            current_version="0.1.0",
            latest_version="0.2.0",
            update_available=True,
        )
        assert version_info.tool_name == "ruff"
        assert version_info.current_version == "0.1.0"
        assert version_info.latest_version == "0.2.0"
        assert version_info.update_available is True

    def test_version_info_with_error(self):
        version_info = VersionInfo(
            tool_name="broken_tool",
            current_version="unknown",
            error="Command not found",
        )
        assert version_info.tool_name == "broken_tool"
        assert version_info.current_version == "unknown"
        assert version_info.error == "Command not found"


class TestToolVersionServiceInitialization:
    def test_service_initialization(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)
        assert service is not None
        assert hasattr(service, "tools_to_check")
        assert hasattr(service, "console")

    def test_service_default_tools_to_check(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)
        assert service.tools_to_check is not None
        assert isinstance(service.tools_to_check, dict)

    def test_service_console_initialization(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)
        assert service.console is not None

    def test_service_has_required_attributes(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)

        required_attrs = [
            "tools_to_check",
            "console",
        ]

        for attr in required_attrs:
            assert hasattr(service, attr), f"Missing attribute: {attr}"

    def test_service_tools_configuration(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)

        assert "ruff" in service.tools_to_check
        assert "pyright" in service.tools_to_check
        assert "pre - commit" in service.tools_to_check
        assert "uv" in service.tools_to_check

    def test_version_info_creation_methods(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)

        version_info = service._create_installed_version_info(
            "test_tool", "1.0.0", "1.1.0"
        )
        assert version_info.tool_name == "test_tool"
        assert version_info.current_version == "1.0.0"
        assert version_info.latest_version == "1.1.0"
        assert version_info.update_available is True

    def test_missing_tool_info_creation(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)

        version_info = service._create_missing_tool_info("missing_tool")
        assert version_info.tool_name == "missing_tool"
        assert version_info.current_version == "not installed"
        assert version_info.error is not None

    def test_error_version_info_creation(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)

        test_error = Exception("Test error")
        version_info = service._create_error_version_info("error_tool", test_error)
        assert version_info.tool_name == "error_tool"
        assert version_info.current_version == "unknown"
        assert version_info.error == "Test error"


class TestToolVersionServiceAsync:
    @pytest.mark.asyncio
    async def test_async_version_info_creation(self):
        async def create_version_info():
            return VersionInfo(tool_name="async_tool", current_version="1.0.0")

        version_info = await create_version_info()
        assert version_info.tool_name == "async_tool"

    @pytest.mark.asyncio
    async def test_async_service_usage(self):
        async def use_service():
            from rich.console import Console

            console = Console()
            service = ToolVersionService(console)
            return service.tools_to_check

        tools = await use_service()
        assert tools is not None


class TestToolVersionServiceEdgeCases:
    def test_service_with_temp_directory(self):
        from rich.console import Console

        with tempfile.TemporaryDirectory():
            console = Console()
            service = ToolVersionService(console)
            assert service.console is not None

    def test_version_info_equality_basic(self):
        v1 = VersionInfo("tool", "1.0.0")
        v2 = VersionInfo("tool", "1.0.0")

        assert v1.tool_name == v2.tool_name
        assert v1.current_version == v2.current_version

    def test_service_method_existence(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)

        expected_methods = [
            "_create_installed_version_info",
            "_create_missing_tool_info",
            "_create_error_version_info",
        ]

        for method in expected_methods:
            assert hasattr(service, method)
            assert callable(getattr(service, method))

    def test_multiple_service_instances(self):
        from rich.console import Console

        console1 = Console()
        console2 = Console()

        service1 = ToolVersionService(console1)
        service2 = ToolVersionService(console2)

        assert service1 is not service2
        assert service1.console is console1
        assert service2.console is console2

    def test_version_info_with_no_update_available(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)

        version_info = service._create_installed_version_info(
            "test_tool", "1.0.0", "1.0.0"
        )
        assert version_info.update_available is False

    def test_version_info_with_none_latest_version(self):
        from rich.console import Console

        console = Console()
        service = ToolVersionService(console)

        version_info = service._create_installed_version_info(
            "test_tool", "1.0.0", None
        )
        assert version_info.latest_version is None
        assert version_info.update_available is False
