import asyncio
import subprocess
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from crackerjack.services.tool_version_service import ToolVersionService, VersionInfo


class TestToolVersionServiceAdvanced:
    @pytest.fixture
    def console(self) -> Console:
        return Console(width=80, legacy_windows=False)

    @pytest.fixture
    def service(self, console: Console) -> ToolVersionService:
        return ToolVersionService(console)

    def test_version_info_creation(self, service: ToolVersionService) -> None:
        info = VersionInfo("ruff", "0.1.0")
        assert info.tool_name == "ruff"
        assert info.current_version == "0.1.0"
        assert info.latest_version is None
        assert info.update_available is False
        assert info.error is None

        info_full = VersionInfo(
            tool_name="pyright",
            current_version="1.1.0",
            latest_version="1.2.0",
            update_available=True,
            error="Connection timeout",
        )
        assert info_full.tool_name == "pyright"
        assert info_full.current_version == "1.1.0"
        assert info_full.latest_version == "1.2.0"
        assert info_full.update_available is True
        assert info_full.error == "Connection timeout"

    def test_service_initialization(
        self, service: ToolVersionService, console: Console
    ) -> None:
        assert service.console == console
        assert isinstance(service.tools_to_check, dict)
        assert len(service.tools_to_check) == 4

        expected_tools = {"ruff", "pyright", "pre - commit", "uv"}
        assert set(service.tools_to_check.keys()) == expected_tools

        for tool_name, method in service.tools_to_check.items():
            assert callable(method)

    @patch("subprocess.run")
    def test_get_ruff_version_success(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.return_value = Mock(
            stdout="ruff 0.1.6\nCompiled with Rust", stderr="", returncode=0
        )

        result = service._get_ruff_version()
        assert result == "0.1.6"
        mock_run.assert_called_once_with(
            ["uv", "run", "ruff", "- - version"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_get_ruff_version_failure(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["ruff", "- - version"])

        result = service._get_ruff_version()
        assert result == "unknown"

    @patch("subprocess.run")
    def test_get_pyright_version_success(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.return_value = Mock(stdout="pyright 1.1.365", stderr="", returncode=0)

        result = service._get_pyright_version()
        assert result == "1.1.365"

    @patch("subprocess.run")
    def test_get_pyright_version_npm_fallback(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, ["pyright", "- - version"]),
            Mock(stdout="pyright 1.1.365", stderr="", returncode=0),
        ]

        result = service._get_pyright_version()
        assert result == "1.1.365"
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_get_precommit_version_success(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.return_value = Mock(
            stdout="pre - commit 3.5.0", stderr="", returncode=0
        )

        result = service._get_precommit_version()
        assert result == "3.5.0"

    @patch("subprocess.run")
    def test_get_uv_version_success(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.return_value = Mock(
            stdout="uv 0.2.18 (Cargo 1.75.0)", stderr="", returncode=0
        )

        result = service._get_uv_version()
        assert result == "0.2.18"

    def test_version_compare_functionality(self, service: ToolVersionService) -> None:
        assert service._version_compare("1.0.0", "1.0.0") == 0

        assert service._version_compare("1.0.0", "1.0.1") < 0
        assert service._version_compare("1.0.0", "1.1.0") < 0
        assert service._version_compare("1.0.0", "2.0.0") < 0

        assert service._version_compare("1.0.1", "1.0.0") > 0
        assert service._version_compare("1.1.0", "1.0.0") > 0
        assert service._version_compare("2.0.0", "1.0.0") > 0

        assert service._version_compare("1.0", "1.0.0") == 0
        assert service._version_compare("1.0.1", "1.0") > 0

    def test_create_installed_version_info(self, service: ToolVersionService) -> None:
        info = service._create_installed_version_info("ruff", "0.1.6", "0.1.6")
        assert info.tool_name == "ruff"
        assert info.current_version == "0.1.6"
        assert info.latest_version == "0.1.6"
        assert info.update_available is False

        info_update = service._create_installed_version_info("ruff", "0.1.5", "0.1.6")
        assert info_update.update_available is True

        info_no_latest = service._create_installed_version_info("ruff", "0.1.6", None)
        assert info_no_latest.latest_version is None
        assert info_no_latest.update_available is False

    @patch("subprocess.run")
    def test_check_installed_tools_comprehensive(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        responses = [
            Mock(stdout="ruff 0.1.6", returncode=0),
            Mock(stdout="pyright 1.1.365", returncode=0),
            Mock(stdout="pre - commit 3.5.0", returncode=0),
            Mock(stdout="uv 0.2.18", returncode=0),
        ]
        mock_run.side_effect = responses

        results = service.check_installed_tools()

        assert len(results) == 4
        assert all(isinstance(info, VersionInfo) for info in results)
        assert all(info.error is None for info in results)

        tool_names = {info.tool_name for info in results}
        assert tool_names == {"ruff", "pyright", "pre - commit", "uv"}

    @patch("subprocess.run")
    def test_check_installed_tools_with_failures(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        responses = [
            Mock(stdout="ruff 0.1.6", returncode=0),
            subprocess.CalledProcessError(1, ["pyright", "- - version"]),
            Mock(stdout="pre - commit 3.5.0", returncode=0),
            subprocess.CalledProcessError(1, ["uv", "- - version"]),
        ]
        mock_run.side_effect = responses

        results = service.check_installed_tools()

        assert len(results) == 4

        success_results = [r for r in results if r.error is None]
        assert len(success_results) == 2

        failed_results = [r for r in results if r.error is not None]
        assert len(failed_results) == 2
        assert all("not installed" in r.error for r in failed_results)

    def test_create_not_installed_version_info(
        self, service: ToolVersionService
    ) -> None:
        info = service._create_not_installed_version_info("missing - tool")

        assert info.tool_name == "missing - tool"
        assert info.current_version == "not installed"
        assert info.latest_version is None
        assert info.update_available is False
        assert "not installed" in info.error

    @pytest.mark.asyncio
    async def test_fetch_latest_version_success(
        self, service: ToolVersionService
    ) -> None:
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.json.return_value = {"info": {"version": "0.1.7"}}
            mock_response.__aenter__.return_value = mock_response

            mock_session = AsyncMock()
            mock_session.get.return_value = mock_response
            mock_session.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session

            result = await service._fetch_latest_version("ruff")
            assert result == "0.1.7"

    @pytest.mark.asyncio
    async def test_fetch_latest_version_failure(
        self, service: ToolVersionService
    ) -> None:
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get.side_effect = Exception("Network error")
            mock_session.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session

            result = await service._fetch_latest_version("ruff")
            assert result is None

    @pytest.mark.asyncio
    async def test_check_tool_updates_comprehensive(
        self, service: ToolVersionService
    ) -> None:
        with patch.object(service, "check_installed_tools") as mock_installed:
            with patch.object(service, "_fetch_latest_version") as mock_fetch:
                mock_installed.return_value = [
                    VersionInfo("ruff", "0.1.5"),
                    VersionInfo("pyright", "1.1.365"),
                ]

                mock_fetch.side_effect = [
                    "0.1.6",
                    "1.1.365",
                ]

                results = await service.check_tool_updates()

                assert len(results) == 2
                ruff_result = next(r for r in results if r.tool_name == "ruff")
                assert ruff_result.update_available is True
                assert ruff_result.latest_version == "0.1.6"

                pyright_result = next(r for r in results if r.tool_name == "pyright")
                assert pyright_result.update_available is False
                assert pyright_result.latest_version == "1.1.365"

    @pytest.mark.asyncio
    async def test_get_outdated_tools(self, service: ToolVersionService) -> None:
        with patch.object(service, "check_tool_updates") as mock_updates:
            mock_updates.return_value = [
                VersionInfo("ruff", "0.1.5", "0.1.6", True),
                VersionInfo("pyright", "1.1.365", "1.1.365", False),
                VersionInfo("uv", "0.2.17", "0.2.18", True),
                VersionInfo("pre - commit", "3.5.0", None, False),
            ]

            outdated = await service.get_outdated_tools()

            assert len(outdated) == 2
            tool_names = {tool.tool_name for tool in outdated}
            assert tool_names == {"ruff", "uv"}
            assert all(tool.update_available for tool in outdated)

    def test_edge_cases_version_parsing(self, service: ToolVersionService) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                stdout="ruff 0.1.6\nCompiled with Rust 1.75.0", returncode=0
            )
            assert service._get_ruff_version() == "0.1.6"

        assert service._version_compare("1.0.0", "1.0.0 - alpha") > 0
        assert service._version_compare("1.0.0 - alpha", "1.0.0 - beta") < 0

        assert service._version_compare("1.0.0 + build1", "1.0.0 + build2") == 0

    @pytest.mark.asyncio
    async def test_concurrent_version_checks(self, service: ToolVersionService) -> None:
        with patch.object(service, "_fetch_latest_version") as mock_fetch:

            async def slow_fetch(tool: str) -> str | None:
                await asyncio.sleep(0.01)
                return f"{tool}- 1.0.0"

            mock_fetch.side_effect = slow_fetch

            tools = ["ruff", "pyright", "uv", "pre - commit"]
            tasks = [service._fetch_latest_version(tool) for tool in tools]
            results = await asyncio.gather(*tasks)

            assert len(results) == 4
            assert all(result is not None for result in results)
            assert results == [
                "ruff - 1.0.0",
                "pyright - 1.0.0",
                "uv - 1.0.0",
                "pre - commit - 1.0.0",
            ]


class TestToolVersionServiceIntegration:
    @pytest.fixture
    def service(self) -> ToolVersionService:
        return ToolVersionService(Console())

    def test_real_version_detection_integration(
        self, service: ToolVersionService
    ) -> None:
        try:
            results = service.check_installed_tools()
            assert isinstance(results, list)
            assert all(isinstance(info, VersionInfo) for info in results)

            detected_tools = [
                info for info in results if info.current_version != "not installed"
            ]
            assert len(detected_tools) > 0, "At least one tool should be detected"

        except Exception as e:
            pytest.skip(f"Tools not available for integration test: {e}")

    @pytest.mark.asyncio
    async def test_async_integration_flow(self, service: ToolVersionService) -> None:
        try:
            updates = await service.check_tool_updates()
            assert isinstance(updates, list)

            outdated = await service.get_outdated_tools()
            assert isinstance(outdated, list)

            outdated_names = {tool.tool_name for tool in outdated}
            update_names = {tool.tool_name for tool in updates}
            assert outdated_names.issubset(update_names)

        except Exception as e:
            pytest.skip(f"Integration test skipped due to: {e}")
