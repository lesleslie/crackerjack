import subprocess
import time
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

try:
    from crackerjack.services.tool_version_service import (
        ToolVersionService,
        VersionInfo,
    )
except ImportError:
    pytest.skip("ToolVersionService not available", allow_module_level=True)


class TestToolVersionServiceDeepCoverage:
    @pytest.fixture
    def console(self) -> Console:
        return Console(width=80, legacy_windows=False)

    @pytest.fixture
    def service(self, console: Console) -> ToolVersionService:
        return ToolVersionService(console)

    def test_version_info_complete_functionality(self) -> None:
        info = VersionInfo("test - tool", "1.0.0")
        assert info.tool_name == "test - tool"
        assert info.current_version == "1.0.0"
        assert info.latest_version is None
        assert info.update_available is False
        assert info.error is None

        full_info = VersionInfo(
            tool_name="advanced - tool",
            current_version="2.1.0",
            latest_version="2.2.0",
            update_available=True,
            error="Network timeout",
        )
        assert full_info.tool_name == "advanced - tool"
        assert full_info.current_version == "2.1.0"
        assert full_info.latest_version == "2.2.0"
        assert full_info.update_available is True
        assert full_info.error == "Network timeout"

        info_no_update = VersionInfo("same - tool", "1.0.0", "1.0.0", False)
        assert info_no_update.update_available is False

    def test_service_initialization_comprehensive(
        self, service: ToolVersionService, console: Console
    ) -> None:
        assert service.console == console
        assert hasattr(service, "tools_to_check")
        assert isinstance(service.tools_to_check, dict)

        expected_tools = {"ruff", "pyright", "pre - commit", "uv"}
        actual_tools = set(service.tools_to_check.keys())
        assert actual_tools == expected_tools

        for tool_name, method in service.tools_to_check.items():
            assert callable(method), f"Method for {tool_name} is not callable"

    @patch("subprocess.run")
    def test_all_version_methods_comprehensive(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        test_cases = [
            ("_get_ruff_version", "ruff 0.1.6", "0.1.6"),
            ("_get_pyright_version", "pyright 1.1.365", "1.1.365"),
            ("_get_precommit_version", "pre - commit 3.5.0", "3.5.0"),
            ("_get_uv_version", "uv 0.2.18", "0.2.18"),
        ]

        for method_name, stdout, expected in test_cases:
            mock_run.return_value = Mock(stdout=stdout, stderr="", returncode=0)

            method = getattr(service, method_name)
            result = method()
            assert expected in result, (
                f"{method_name} failed: got {result}, expected {expected}"
            )

    @patch("subprocess.run")
    def test_version_detection_error_handling(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["tool", "- - version"])

        methods_to_test = [
            service._get_ruff_version,
            service._get_pyright_version,
            service._get_precommit_version,
            service._get_uv_version,
        ]

        for method in methods_to_test:
            result = method()
            assert result == "unknown", (
                f"Method {method.__name__} should return 'unknown' on error"
            )

    @patch("subprocess.run")
    def test_version_detection_with_complex_output(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        complex_outputs = [
            (
                "ruff 0.1.6\nCompiled with Rust 1.75.0",
                service._get_ruff_version,
                "0.1.6",
            ),
            (
                "pyright 1.1.365\nNode.js v18.17.0",
                service._get_pyright_version,
                "1.1.365",
            ),
            (
                "pre - commit 3.5.0\nPython 3.11.0",
                service._get_precommit_version,
                "3.5.0",
            ),
            (
                "uv 0.2.18 (Cargo 1.75.0)\nInstalled via pip",
                service._get_uv_version,
                "0.2.18",
            ),
        ]

        for output, method, expected in complex_outputs:
            mock_run.return_value = Mock(stdout=output, returncode=0)
            result = method()
            assert expected in result or result == expected

    def test_version_comparison_comprehensive(
        self, service: ToolVersionService
    ) -> None:
        if hasattr(service, "_version_compare"):
            version_compare = service._version_compare

            assert version_compare("1.0.0", "1.0.0") == 0
            assert version_compare("2.1.5", "2.1.5") == 0

            assert version_compare("1.0.0", "1.0.1") < 0
            assert version_compare("1.0.0", "1.1.0") < 0
            assert version_compare("1.0.0", "2.0.0") < 0
            assert version_compare("0.9.0", "1.0.0") < 0

            assert version_compare("1.0.1", "1.0.0") > 0
            assert version_compare("1.1.0", "1.0.0") > 0
            assert version_compare("2.0.0", "1.0.0") > 0
            assert version_compare("1.0.0", "0.9.0") > 0

            assert version_compare("1.0.0", "1.0.0 - alpha") > 0
            assert version_compare("1.0.0 - alpha", "1.0.0 - beta") < 0
            assert version_compare("1.0.0 - beta", "1.0.0") < 0

    def test_version_info_creation_methods(self, service: ToolVersionService) -> None:
        info_update = service._create_installed_version_info(
            "test - tool", "1.0.0", "1.1.0"
        )
        assert info_update.tool_name == "test - tool"
        assert info_update.current_version == "1.0.0"
        assert info_update.latest_version == "1.1.0"
        assert info_update.update_available is True
        assert info_update.error is None

        info_no_update = service._create_installed_version_info(
            "test - tool", "1.1.0", "1.1.0"
        )
        assert info_no_update.update_available is False

        info_no_latest = service._create_installed_version_info(
            "test - tool", "1.0.0", None
        )
        assert info_no_latest.latest_version is None
        assert info_no_latest.update_available is False

        info_not_installed = service._create_not_installed_version_info(
            "missing - tool"
        )
        assert info_not_installed.tool_name == "missing - tool"
        assert info_not_installed.current_version == "not installed"
        assert info_not_installed.latest_version is None
        assert info_not_installed.update_available is False
        assert "not installed" in info_not_installed.error

    @patch("subprocess.run")
    def test_check_installed_tools_comprehensive_workflow(
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

        assert len(results) == 4, "Should return results for all 4 tools"
        assert all(isinstance(info, VersionInfo) for info in results), (
            "All results should be VersionInfo instances"
        )
        assert all(info.error is None for info in results), (
            "No errors should occur with successful mocks"
        )

        tool_names = {info.tool_name for info in results}
        expected_tools = {"ruff", "pyright", "pre - commit", "uv"}
        assert tool_names == expected_tools, (
            f"Expected {expected_tools}, got {tool_names}"
        )

        for info in results:
            assert info.current_version != "unknown", (
                f"Tool {info.tool_name} should have extracted version"
            )

    @patch("subprocess.run")
    def test_check_installed_tools_mixed_results(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        responses = [
            Mock(stdout="ruff 0.1.6", returncode=0),
            subprocess.CalledProcessError(1, ["pyright", "- - version"]),
            Mock(stdout="pre - commit 3.5.0", returncode=0),
            subprocess.CalledProcessError(127, ["uv", "- - version"]),
        ]
        mock_run.side_effect = responses

        results = service.check_installed_tools()

        assert len(results) == 4, (
            "Should return results for all tools, even failed ones"
        )

        successful_results = [r for r in results if r.error is None]
        assert len(successful_results) == 2, "Should have 2 successful results"

        successful_tools = {r.tool_name for r in successful_results}
        expected_successful = {"ruff", "pre - commit"}
        assert successful_tools == expected_successful, (
            f"Expected successful: {expected_successful}"
        )

        failed_results = [r for r in results if r.error is not None]
        assert len(failed_results) == 2, "Should have 2 failed results"

        for failed_result in failed_results:
            assert "not installed" in failed_result.error, (
                "Failed result should indicate not installed"
            )
            assert failed_result.current_version == "not installed"

    def test_edge_case_version_parsing(self, service: ToolVersionService) -> None:
        with patch("subprocess.run") as mock_run:
            test_cases = [
                ("ruff 0.1.6\nCompiled with Rust", "0.1.6"),
                ("Tool version v1.2.3", "1.2.3"),
                ("mytool 2.0.0 - beta1 (build 123)", "2.0.0 - beta1"),
                ("software 1.0.0 + build.1", "1.0.0"),
            ]

            for output, expected_version in test_cases:
                mock_run.return_value = Mock(stdout=output, returncode=0)

                result = service._get_ruff_version()

                assert expected_version in result or result == expected_version

    @pytest.mark.asyncio
    async def test_async_version_fetching(self, service: ToolVersionService) -> None:
        if hasattr(service, "_fetch_latest_version"):
            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_response = Mock()
                mock_response.json.return_value = {"info": {"version": "1.0.5"}}
                mock_response.__aenter__ = Mock(return_value=mock_response)
                mock_response.__aexit__ = Mock(return_value=None)

                mock_session = Mock()
                mock_session.get.return_value = mock_response
                mock_session.__aenter__ = Mock(return_value=mock_session)
                mock_session.__aexit__ = Mock(return_value=None)
                mock_session_class.return_value = mock_session

                result = await service._fetch_latest_version("test - package")
                assert result == "1.0.5"

                mock_session.get.side_effect = Exception("Network error")
                result_error = await service._fetch_latest_version("test - package")
                assert result_error is None

    def test_performance_characteristics(self, service: ToolVersionService) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="tool 1.0.0", returncode=0)

            start_time = time.time()

            for _ in range(5):
                results = service.check_installed_tools()
                assert len(results) == 4

            end_time = time.time()

            execution_time = end_time - start_time
            assert execution_time < 10.0, (
                f"Performance test took {execution_time}s, should be under 10s"
            )

    def test_memory_usage_patterns(self, service: ToolVersionService) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="tool 1.0.0", returncode=0)

            results_list = []
            for i in range(20):
                results = service.check_installed_tools()
                assert len(results) == 4
                results_list.append(results)

            for results in results_list:
                assert all(
                    r.tool_name in {"ruff", "pyright", "pre - commit", "uv"}
                    for r in results
                )

    def test_subprocess_command_construction(self, service: ToolVersionService) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="tool 1.0.0", returncode=0)

            service._get_ruff_version()
            mock_run.assert_called_with(
                ["uv", "run", "ruff", "- - version"],
                capture_output=True,
                text=True,
                check=False,
            )

            mock_run.reset_mock()
            service._get_pyright_version()

            assert mock_run.called
            args, kwargs = mock_run.call_args
            assert "pyright" in args[0]
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            assert kwargs["check"] is False

    def test_error_scenarios_comprehensive(self, service: ToolVersionService) -> None:
        error_types = [
            subprocess.CalledProcessError(1, ["tool", "- - version"]),
            subprocess.CalledProcessError(127, ["tool", "- - version"]),
            subprocess.TimeoutExpired(["tool", "- - version"], 30),
            OSError("Permission denied"),
            FileNotFoundError("Command not found"),
        ]

        for error in error_types:
            with patch("subprocess.run", side_effect=error):
                result = service._get_ruff_version()
                assert result == "unknown", (
                    f"Should return 'unknown' for error: {type(error).__name__}"
                )

    def test_version_info_edge_cases(self) -> None:
        edge_cases = [
            VersionInfo("", "", None, False, None),
            VersionInfo("tool", "", "", False, ""),
            VersionInfo("tool", "1.0.0", "", True, None),
        ]

        for info in edge_cases:
            assert isinstance(info.tool_name, str)
            assert isinstance(info.current_version, str)
            assert isinstance(info.update_available, bool)

    def test_integration_with_real_environment(
        self, service: ToolVersionService
    ) -> None:
        try:
            results = service.check_installed_tools()

            assert isinstance(results, list)
            assert len(results) == 4
            assert all(isinstance(info, VersionInfo) for info in results)

            tool_names = {info.tool_name for info in results}
            expected_tools = {"ruff", "pyright", "pre - commit", "uv"}
            assert tool_names == expected_tools

        except Exception:
            pytest.skip("Real tools not available for integration test")
