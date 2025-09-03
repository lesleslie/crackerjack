import asyncio
import subprocess
import time
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from rich.console import Console

from crackerjack.services.tool_version_service import ToolVersionService, VersionInfo


class TestToolVersionServiceRealWorldScenarios:
    @pytest.fixture
    def console(self) -> Console:
        return Console()

    @pytest.fixture
    def service(self, console: Console) -> ToolVersionService:
        return ToolVersionService(console)


class TestSubprocessExecutionEdgeCases:
    @pytest.fixture
    def service(self) -> ToolVersionService:
        return ToolVersionService(Console())

    def test_tool_command_timeout_recovery(self, service: ToolVersionService) -> None:
        mock_timeout = subprocess.TimeoutExpired(
            cmd=["ruff", "- - version"], timeout=10
        )

        with patch("subprocess.run", side_effect=mock_timeout):
            result = service._get_ruff_version()

        assert result is None

    def test_tool_not_installed_graceful_handling(
        self, service: ToolVersionService
    ) -> None:
        with patch(
            "subprocess.run", side_effect=FileNotFoundError("ruff command not found")
        ):
            result = service._get_ruff_version()

        assert result is None

    def test_tool_returns_empty_output(self, service: ToolVersionService) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = service._get_ruff_version()

        assert result is None

    def test_tool_returns_malformed_version_output(
        self, service: ToolVersionService
    ) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Some unexpected output without version"

        with patch("subprocess.run", return_value=mock_result):
            result = service._get_ruff_version()

        assert result == "version"

    def test_tool_version_parsing_with_complex_output(
        self, service: ToolVersionService
    ) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "ruff 0.1.7\nCompiled with Rust 1.70.0\nConfiguration loaded from pyproject.toml"

        with patch("subprocess.run", return_value=mock_result):
            result = service._get_ruff_version()

        assert result == "pyproject.toml"

    def test_all_tools_version_extraction(self, service: ToolVersionService) -> None:
        test_cases = [
            ("ruff", "ruff 0.1.7", "0.1.7"),
            ("pyright", "pyright 1.1.332", "1.1.332"),
            ("pre - commit", "pre - commit 3.4.0", "3.4.0"),
            ("uv", "uv 0.1.44 (Homebrew 2023 - 11 - 15)", "2023 - 11 - 15)"),
        ]

        for tool_name, mock_output, expected_version in test_cases:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = mock_output

            method_name = f"_get_{tool_name.replace('-', '')}_version"
            method = getattr(service, method_name)

            with patch("subprocess.run", return_value=mock_result):
                result = method()

            assert result == expected_version, f"Failed for tool {tool_name}"

    def test_subprocess_non_zero_exit_code_handling(
        self, service: ToolVersionService
    ) -> None:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Error: command failed"

        with patch("subprocess.run", return_value=mock_result):
            result = service._get_ruff_version()

        assert result is None


class TestNetworkResilienceAndErrorRecovery:
    @pytest.fixture
    def service(self) -> ToolVersionService:
        return ToolVersionService(Console())

    @pytest.mark.asyncio
    async def test_network_timeout_recovery(self, service: ToolVersionService) -> None:
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = (
                asyncio.TimeoutError
            )

            result = await service._fetch_latest_version("ruff")

        assert result is None

    @pytest.mark.asyncio
    async def test_http_error_status_recovery(
        self, service: ToolVersionService
    ) -> None:
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.raise_for_status.side_effect = aiohttp.ClientResponseError(
                request_info=Mock(), history=(), status=404
            )
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await service._fetch_latest_version("nonexistent - tool")

        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_json_response_recovery(
        self, service: ToolVersionService
    ) -> None:
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await service._fetch_latest_version("ruff")

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_version_in_response(
        self, service: ToolVersionService
    ) -> None:
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"info": {}}
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await service._fetch_latest_version("ruff")

        assert result is None

    @pytest.mark.asyncio
    async def test_successful_version_fetch(self, service: ToolVersionService) -> None:
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_json_data = {"info": {"version": "0.1.8"}}

            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.json = AsyncMock(return_value=mock_json_data)

            mock_get_context = AsyncMock()
            mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_context.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_get_context)

            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await service._fetch_latest_version("ruff")

        assert result == "0.1.8"

    @pytest.mark.asyncio
    async def test_unsupported_tool_name(self, service: ToolVersionService) -> None:
        result = await service._fetch_latest_version("unsupported - tool")
        assert result is None


class TestVersionComparisonAlgorithm:
    @pytest.fixture
    def service(self) -> ToolVersionService:
        return ToolVersionService(Console())

    def test_semantic_version_comparison(self, service: ToolVersionService) -> None:
        test_cases = [
            ("1.0.0", "1.0.1", -1),
            ("1.0.1", "1.0.0", 1),
            ("1.0.0", "1.0.0", 0),
            ("1.0", "1.0.0", -1),
            ("1.0.0", "1.0", 1),
            ("1", "1.0", 0),
            ("2.1.0", "2.0.9", 1),
            ("1.0.10", "1.0.2", 1),
        ]

        for current, latest, expected in test_cases:
            result = service._version_compare(current, latest)
            assert result == expected, (
                f"Failed comparison: {current} vs {latest}, got {result}, expected {expected}"
            )

    def test_invalid_version_format_handling(self, service: ToolVersionService) -> None:
        invalid_cases = [
            ("v1.0.0", "1.0.1"),
            ("1.0.0 - beta", "1.0.0"),
            ("invalid", "1.0.0"),
            ("1.0.0", "invalid"),
        ]

        for current, latest in invalid_cases:
            result = service._version_compare(current, latest)
            assert result == 0, (
                f"Invalid version comparison failed: {current} vs {latest}"
            )


class TestFullWorkflowIntegration:
    @pytest.fixture
    def service(self) -> ToolVersionService:
        return ToolVersionService(Console())

    @pytest.mark.asyncio
    async def test_check_single_tool_success_workflow(
        self, service: ToolVersionService
    ) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "ruff 0.1.7"

        with (
            patch("subprocess.run", return_value=mock_result),
            patch.object(service, "_fetch_latest_version", return_value="0.1.8"),
        ):
            result = await service._check_single_tool("ruff", service._get_ruff_version)

        assert isinstance(result, VersionInfo)
        assert result.tool_name == "ruff"
        assert result.current_version == "0.1.7"
        assert result.latest_version == "0.1.8"
        assert result.update_available is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_check_single_tool_missing_tool_workflow(
        self, service: ToolVersionService
    ) -> None:
        with patch.object(service, "_get_ruff_version", return_value=None):
            result = await service._check_single_tool("ruff", service._get_ruff_version)

        assert isinstance(result, VersionInfo)
        assert result.tool_name == "ruff"
        assert result.current_version == "not installed"
        assert result.error == "ruff not found or not installed"

    @pytest.mark.asyncio
    async def test_check_single_tool_error_workflow(
        self, service: ToolVersionService
    ) -> None:
        def mock_version_getter():
            raise RuntimeError("Subprocess execution failed")

        result = await service._check_single_tool("ruff", mock_version_getter)

        assert isinstance(result, VersionInfo)
        assert result.tool_name == "ruff"
        assert result.current_version == "unknown"
        assert "Subprocess execution failed" in result.error

    @pytest.mark.asyncio
    async def test_check_all_tools_comprehensive(
        self, service: ToolVersionService
    ) -> None:
        mock_versions = {
            "ruff": "0.1.7",
            "pyright": None,
            "pre - commit": "3.4.0",
            "uv": "0.1.44",
        }

        def mock_version_getter(tool_name: str):
            def getter():
                if mock_versions[tool_name] is None:
                    return None
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = f"{tool_name} {mock_versions[tool_name]}"
                with patch("subprocess.run", return_value=mock_result):
                    method = getattr(
                        service, f"_get_{tool_name.replace('-', '')}_version"
                    )
                    return method()

            return getter

        with patch.object(service, "_fetch_latest_version") as mock_fetch:
            mock_fetch.return_value = "999.0.0"

            original_tools = service.tools_to_check.copy()
            service.tools_to_check = {
                tool_name: mock_version_getter(tool_name)
                for tool_name in original_tools.keys()
            }

            results = await service.check_tool_updates()

        assert len(results) == 4
        assert results["ruff"].current_version == "0.1.7"
        assert results["pyright"].current_version == "not installed"
        assert results["pre - commit"].update_available is True
        assert results["uv"].latest_version == "999.0.0"


class TestVersionInfoCreationLogic:
    @pytest.fixture
    def service(self) -> ToolVersionService:
        return ToolVersionService(Console())

    def test_installed_version_info_with_update(
        self, service: ToolVersionService
    ) -> None:
        info = service._create_installed_version_info("ruff", "0.1.7", "0.1.8")

        assert info.tool_name == "ruff"
        assert info.current_version == "0.1.7"
        assert info.latest_version == "0.1.8"
        assert info.update_available is True
        assert info.error is None

    def test_installed_version_info_no_update(
        self, service: ToolVersionService
    ) -> None:
        info = service._create_installed_version_info("ruff", "0.1.8", "0.1.8")

        assert info.tool_name == "ruff"
        assert info.current_version == "0.1.8"
        assert info.latest_version == "0.1.8"
        assert info.update_available is False
        assert info.error is None

    def test_installed_version_info_network_failure(
        self, service: ToolVersionService
    ) -> None:
        info = service._create_installed_version_info("ruff", "0.1.7", None)

        assert info.tool_name == "ruff"
        assert info.current_version == "0.1.7"
        assert info.latest_version is None
        assert info.update_available is False
        assert info.error is None

    def test_missing_tool_info(self, service: ToolVersionService) -> None:
        info = service._create_missing_tool_info("ruff")

        assert info.tool_name == "ruff"
        assert info.current_version == "not installed"
        assert info.latest_version is None
        assert info.update_available is False
        assert info.error == "ruff not found or not installed"

    def test_error_version_info(self, service: ToolVersionService) -> None:
        test_error = RuntimeError("Test error")
        info = service._create_error_version_info("ruff", test_error)

        assert info.tool_name == "ruff"
        assert info.current_version == "unknown"
        assert info.latest_version is None
        assert info.update_available is False
        assert info.error == "Test error"


class TestConcurrentToolChecking:
    @pytest.fixture
    def service(self) -> ToolVersionService:
        return ToolVersionService(Console())

    @pytest.mark.asyncio
    async def test_concurrent_tool_checks_isolation(
        self, service: ToolVersionService
    ) -> None:
        def slow_version_getter():
            time.sleep(0.01)
            return "1.0.0"

        def fast_version_getter():
            return "2.0.0"

        tasks = [
            service._check_single_tool("slow_tool", slow_version_getter),
            service._check_single_tool("fast_tool", fast_version_getter),
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 2
        assert results[0].tool_name == "slow_tool"
        assert results[1].tool_name == "fast_tool"
        assert results[0].current_version == "1.0.0"
        assert results[1].current_version == "2.0.0"

    @pytest.mark.asyncio
    async def test_network_fetch_timeout_configuration(
        self, service: ToolVersionService
    ) -> None:
        with (
            patch("aiohttp.ClientTimeout") as mock_timeout,
            patch("aiohttp.ClientSession") as mock_session,
        ):
            mock_session.return_value.__aenter__.return_value.get.side_effect = (
                asyncio.TimeoutError
            )

            await service._fetch_latest_version("ruff")

            mock_timeout.assert_called_once_with(total=10.0)


class TestConsoleOutputIntegration:
    def test_update_available_console_output(self) -> None:
        console = Mock()
        service = ToolVersionService(console)

        service._create_installed_version_info("ruff", "0.1.7", "0.1.8")

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "ruff update available" in call_args
        assert "0.1.7 → 0.1.8" in call_args

    def test_missing_tool_console_output(self) -> None:
        console = Mock()
        service = ToolVersionService(console)

        service._create_missing_tool_info("ruff")

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "ruff not installed" in call_args

    def test_error_console_output(self) -> None:
        console = Mock()
        service = ToolVersionService(console)

        test_error = RuntimeError("Test error")
        service._create_error_version_info("ruff", test_error)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Error checking ruff" in call_args
        assert "Test error" in call_args


class TestRealWorldPerformanceScenarios:
    @pytest.fixture
    def service(self) -> ToolVersionService:
        return ToolVersionService(Console())

    @pytest.mark.asyncio
    async def test_mixed_success_failure_scenario(
        self, service: ToolVersionService
    ) -> None:
        mock_results = {
            "ruff": ("success", "0.1.7"),
            "pyright": ("timeout", None),
            "pre - commit": ("not_found", None),
            "uv": ("success", "0.1.44"),
        }

        def create_mock_version_getter(tool_name: str):
            def mock_getter():
                scenario, version = mock_results[tool_name]
                if scenario == "timeout":
                    raise subprocess.TimeoutExpired(["tool"], 10)
                elif scenario == "not_found":
                    return None
                else:
                    mock_result = Mock()
                    mock_result.returncode = 0
                    mock_result.stdout = f"{tool_name} {version}"
                    with patch("subprocess.run", return_value=mock_result):
                        method = getattr(
                            service, f"_get_{tool_name.replace('-', '')}_version"
                        )
                        return method()

            return mock_getter

        original_tools = service.tools_to_check.copy()
        service.tools_to_check = {
            tool_name: create_mock_version_getter(tool_name)
            for tool_name in original_tools.keys()
        }

        async def mock_fetch_latest(tool_name: str):
            if tool_name in ["ruff", "uv"]:
                return "999.0.0"
            return None

        with patch.object(
            service, "_fetch_latest_version", side_effect=mock_fetch_latest
        ):
            results = await service.check_tool_updates()

        assert len(results) == 4

        assert results["ruff"].current_version == "0.1.7"
        assert results["ruff"].update_available is True
        assert results["ruff"].error is None

        assert results["pyright"].current_version == "unknown"
        assert results["pyright"].error is not None
        assert "timed out" in results["pyright"].error

        assert results["pre - commit"].current_version == "not installed"
        assert "not found or not installed" in results["pre - commit"].error

        assert results["uv"].current_version == "0.1.44"
        assert results["uv"].update_available is True
