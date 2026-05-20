"""Focused coverage tests for small helper modules."""

import tomllib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.cli.formatting import separator
from crackerjack.cli.handlers.config_handlers import handle_config_updates
from crackerjack.cli.handlers.coverage import (
    display_coverage_info,
    display_coverage_report,
    display_ratchet_status,
    handle_coverage_status,
)
from crackerjack.cli.version import get_package_version
from crackerjack.services.import_resolution import (
    SAFE_IMPORT_SPECS,
    get_safe_import_spec,
)
from crackerjack.services.tool_version_service import ToolVersionService
from crackerjack.websocket.tls_config import (
    get_websocket_tls_config,
    load_ssl_context,
)


class TestCliFormatting:
    def test_separator_uses_console_width_when_width_is_invalid(self) -> None:
        with patch("crackerjack.cli.formatting.get_console_width", return_value=12):
            assert separator(width=0) == "-" * 12

    def test_separator_uses_explicit_width(self) -> None:
        assert separator(char="=", width=3) == "==="

    def test_separator_falls_back_to_console_width_for_non_int(self) -> None:
        with patch("crackerjack.cli.formatting.get_console_width", return_value=7):
            assert separator(char="*", width=None) == "*" * 7


class TestImportResolution:
    @pytest.mark.parametrize(
        ("undefined_name", "expected_module", "expected_symbol"),
        [
            ("Any", "typing", "Any"),
            ("Path", "pathlib", "Path"),
            ("operator", "operator", None),
            ("suppress", "contextlib", "suppress"),
        ],
    )
    def test_get_safe_import_spec_known_names(
        self,
        undefined_name: str,
        expected_module: str,
        expected_symbol: str | None,
    ) -> None:
        spec = get_safe_import_spec(undefined_name)

        assert spec is not None
        assert spec.module_name == expected_module
        assert spec.symbol_name == expected_symbol
        assert spec.import_line == SAFE_IMPORT_SPECS[undefined_name].import_line

    def test_get_safe_import_spec_unknown_name(self) -> None:
        assert get_safe_import_spec("not_known") is None


class TestPackageVersion:
    def test_get_package_version_uses_importlib_metadata(self) -> None:
        with patch("importlib.metadata.version", return_value="1.2.3"):
            assert get_package_version() == "1.2.3"

    def test_get_package_version_falls_back_to_pyproject(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            pyproject = tomllib.load(f)

        expected_version = str(pyproject["project"]["version"])

        with patch(
            "importlib.metadata.version",
            side_effect=ModuleNotFoundError,
        ):
            assert get_package_version() == expected_version

    def test_get_package_version_returns_unknown_when_fallback_fails(self) -> None:
        with patch(
            "importlib.metadata.version",
            side_effect=ModuleNotFoundError,
        ), patch("tomllib.load", side_effect=ValueError("bad toml")):
            assert get_package_version() == "unknown"


class TestTlsConfig:
    def test_get_websocket_tls_config_delegates_to_env(self) -> None:
        expected = {
            "tls_enabled": False,
            "cert_file": None,
            "key_file": None,
            "ca_file": None,
        }

        with patch(
            "crackerjack.websocket.tls_config.get_tls_config_from_env",
            return_value=expected,
        ) as mock_get_env:
            assert get_websocket_tls_config() == expected

        mock_get_env.assert_called_once_with("CRACKERJACK_WS")

    def test_load_ssl_context_uses_env_config_when_tls_enabled(self) -> None:
        created_context = Mock(name="ssl_context")
        env_config = {
            "tls_enabled": True,
            "cert_file": "cert.pem",
            "key_file": "key.pem",
            "ca_file": Path("ca.pem"),
        }

        with patch(
            "crackerjack.websocket.tls_config.get_websocket_tls_config",
            return_value=env_config,
        ) as mock_get_env, patch(
            "crackerjack.websocket.tls_config.create_ssl_context",
            return_value=created_context,
        ) as mock_create:
            result = load_ssl_context()

        mock_get_env.assert_called_once_with()
        mock_create.assert_called_once_with(
            cert_file="cert.pem",
            key_file="key.pem",
            ca_file="ca.pem",
            verify_client=False,
        )
        assert result == {
            "ssl_context": created_context,
            "cert_file": "cert.pem",
            "key_file": "key.pem",
            "ca_file": "ca.pem",
            "verify_client": False,
        }

    def test_load_ssl_context_skips_env_when_cert_and_key_are_explicit(self) -> None:
        created_context = Mock(name="ssl_context")

        with patch(
            "crackerjack.websocket.tls_config.get_websocket_tls_config",
        ) as mock_get_env, patch(
            "crackerjack.websocket.tls_config.create_ssl_context",
            return_value=created_context,
        ) as mock_create:
            result = load_ssl_context(
                cert_file="explicit-cert.pem",
                key_file="explicit-key.pem",
                verify_client=True,
            )

        mock_get_env.assert_not_called()
        mock_create.assert_called_once_with(
            cert_file="explicit-cert.pem",
            key_file="explicit-key.pem",
            ca_file=None,
            verify_client=True,
        )
        assert result["ssl_context"] is created_context
        assert result["verify_client"] is True

    def test_load_ssl_context_propagates_ssl_errors(self) -> None:
        with patch(
            "crackerjack.websocket.tls_config.create_ssl_context",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                load_ssl_context(cert_file="cert.pem", key_file="key.pem")


class TestConfigHandlers:
    def test_handle_config_updates_raises_not_implemented(self) -> None:
        with pytest.raises(
            NotImplementedError,
            match="handle_config_updates needs to be properly implemented",
        ):
            handle_config_updates(options=Mock(), console=Mock())


class TestCoverageHandlers:
    def test_display_coverage_info_with_percent_and_message(self) -> None:
        console = Mock()

        display_coverage_info(
            {
                "coverage_percent": 87.5,
                "source": "unit",
                "message": "build succeeded",
            },
            console,
        )

        console.print.assert_any_call(
            "[green]Current Coverage:[/green] 87.50% (from unit)",
        )
        console.print.assert_any_call("[dim]build succeeded[/dim]")

    def test_display_coverage_info_without_percent(self) -> None:
        console = Mock()

        display_coverage_info({}, console)

        console.print.assert_called_once_with(
            "[yellow]Current Coverage:[/yellow] No coverage data available",
        )

    def test_display_coverage_report_when_report_exists(self) -> None:
        console = Mock()
        test_manager = Mock()
        test_manager.get_coverage_report.return_value = "coverage details"

        display_coverage_report(test_manager, console)

        console.print.assert_called_once_with(
            "[cyan]Details:[/cyan] coverage details",
        )

    def test_display_coverage_report_when_report_missing(self) -> None:
        console = Mock()
        test_manager = Mock()
        test_manager.get_coverage_report.return_value = ""

        display_coverage_report(test_manager, console)

        console.print.assert_not_called()

    def test_display_ratchet_status_with_data(self) -> None:
        console = Mock()
        test_manager = Mock()
        test_manager.get_coverage_ratchet_status.return_value = {
            "next_milestone": 91.2,
            "milestones_achieved": ["80%", "90%"],
        }

        display_ratchet_status(test_manager, console)

        console.print.assert_any_call("[cyan]Next Milestone:[/cyan] 91%")
        console.print.assert_any_call("[green]Milestones Achieved:[/green] 2")

    def test_display_ratchet_status_swallows_exceptions(self) -> None:
        console = Mock()
        test_manager = Mock()
        test_manager.get_coverage_ratchet_status.side_effect = RuntimeError("boom")

        display_ratchet_status(test_manager, console)

        console.print.assert_not_called()

    def test_handle_coverage_status_false_short_circuits(self) -> None:
        console = Mock()

        assert handle_coverage_status(False, options=Mock(), console=console) is True
        console.print.assert_not_called()

    def test_handle_coverage_status_success(self) -> None:
        console = Mock()
        test_manager = Mock()
        test_manager.get_coverage.return_value = {
            "coverage_percent": 75.0,
            "source": "unit",
        }
        test_manager.get_coverage_report.return_value = "details"
        test_manager.get_coverage_ratchet_status.return_value = {
            "next_milestone": 80,
            "milestones_achieved": ["70%"],
        }

        with patch(
            "crackerjack.managers.test_manager.TestManager",
            return_value=test_manager,
        ) as mock_cls:
            result = handle_coverage_status(True, options=Mock(), console=console)

        assert result is False
        mock_cls.assert_called_once()
        console.print.assert_any_call("[cyan]📊[/cyan] Coverage Status Report")
        console.print.assert_any_call("=" * 50)
        console.print.assert_any_call("[green]Current Coverage:[/green] 75.00% (from unit)")
        console.print.assert_any_call("[cyan]Details:[/cyan] details")
        console.print.assert_any_call("[cyan]Next Milestone:[/cyan] 80%")
        console.print.assert_any_call("[green]Milestones Achieved:[/green] 1")

    def test_handle_coverage_status_error(self) -> None:
        console = Mock()

        with patch(
            "crackerjack.managers.test_manager.TestManager",
            side_effect=RuntimeError("fail"),
        ):
            result = handle_coverage_status(True, options=Mock(), console=console)

        assert result is False
        console.print.assert_any_call(
            "[red]❌[/red] Failed to get coverage status: fail",
        )


class TestToolVersionService:
    def test_constructor_uses_defaults(self) -> None:
        console = Mock()

        with patch(
            "crackerjack.services.tool_version_service.Console",
            return_value=console,
        ), patch(
            "crackerjack.services.tool_version_service.Path.cwd",
            return_value=Path("/tmp/default-project"),
        ), patch(
            "crackerjack.services.tool_version_service.VersionChecker",
        ) as mock_checker, patch(
            "crackerjack.services.tool_version_service.ConfigIntegrityService",
        ) as mock_integrity, patch(
            "crackerjack.services.tool_version_service.SmartSchedulingService",
        ) as mock_scheduling:
            service = ToolVersionService()

        assert service.console is console
        assert service.project_path == Path("/tmp/default-project")
        mock_checker.assert_called_once_with()
        mock_integrity.assert_called_once_with(Path("/tmp/default-project"))
        mock_scheduling.assert_called_once_with(Path("/tmp/default-project"))
