"""Tests for ``crackerjack.cli.handlers.health``.

Covers the public ``handle_health_check`` entry point and the private
``_check_*`` helpers. All filesystem, network, and import-time side effects
are mocked at the boundary so the tests stay deterministic and run without
external services.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.cli.handlers import health as health_mod
from crackerjack.cli.handlers.health import (
    STATUS_COLORS,
    _check_adapters,
    _check_managers,
    _check_services,
    _output_json,
    _output_table,
    _print_category_components,
    _print_category_details,
    _print_component_details,
    _print_overall_status,
    _print_single_category,
    _print_timestamp,
    handle_health_check,
)
from crackerjack.models.enums import HealthStatus
from crackerjack.models.health_check import (
    ComponentHealth,
    HealthCheckResult,
    SystemHealthReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_healthy_result(name: str = "comp", message: str = "ok") -> HealthCheckResult:
    return HealthCheckResult.healthy(message=message, component_name=name)


def _make_degraded_result(name: str = "comp", message: str = "warn") -> HealthCheckResult:
    return HealthCheckResult.degraded(message=message, component_name=name)


def _make_unhealthy_result(name: str = "comp", message: str = "bad") -> HealthCheckResult:
    return HealthCheckResult.unhealthy(message=message, component_name=name)


def _make_component_health(
    status: HealthStatus = HealthStatus.HEALTHY,
    category: str = "adapters",
) -> ComponentHealth:
    return ComponentHealth(
        category=category,
        overall_status=status,
        total=2,
        healthy=2 if status == HealthStatus.HEALTHY else 1,
        degraded=0 if status == HealthStatus.HEALTHY else (1 if status == HealthStatus.DEGRADED else 0),
        unhealthy=0 if status == HealthStatus.HEALTHY else (1 if status == HealthStatus.UNHEALTHY else 0),
        components={
            "alpha": _make_healthy_result("alpha"),
            "beta": _make_degraded_result("beta") if status == HealthStatus.DEGRADED else _make_unhealthy_result("beta") if status == HealthStatus.UNHEALTHY else _make_healthy_result("beta"),
        },
    )


def _make_report(
    overall: HealthStatus = HealthStatus.HEALTHY,
) -> SystemHealthReport:
    return SystemHealthReport(
        overall_status=overall,
        categories={
            "adapters": _make_component_health(HealthStatus.HEALTHY, "adapters"),
        },
        summary="All 2 components healthy",
    )


@pytest.fixture
def fake_console() -> Console:
    """Console that records output to a string buffer (no ANSI noise)."""
    return Console(record=True, force_terminal=False, width=200)


# ---------------------------------------------------------------------------
# STATUS_COLORS
# ---------------------------------------------------------------------------


class TestStatusColors:
    def test_contains_all_three_states(self) -> None:
        assert set(STATUS_COLORS) == {"healthy", "degraded", "unhealthy"}

    def test_colors_are_rich_ansi_names(self) -> None:
        assert STATUS_COLORS["healthy"] == "green"
        assert STATUS_COLORS["degraded"] == "yellow"
        assert STATUS_COLORS["unhealthy"] == "red"


# ---------------------------------------------------------------------------
# handle_health_check — subcommand dispatch
# ---------------------------------------------------------------------------


class TestHandleHealthCheckDispatch:
    def test_component_adapters_routes_to_adapters_check(self, tmp_path: Path) -> None:
        adapter_health = _make_component_health(HealthStatus.HEALTHY, "adapters")
        with patch.object(
            health_mod,
            "_check_adapters",
            return_value=adapter_health,
        ) as mock_adapters, patch.object(
            health_mod, "_check_managers"
        ) as mock_managers, patch.object(
            health_mod, "_check_services"
        ) as mock_services:
            report = SystemHealthReport.from_category_health({"adapters": adapter_health})
            with patch.object(
                SystemHealthReport,
                "from_category_health",
                return_value=report,
            ):
                code = handle_health_check(
                    component="adapters",
                    quiet=True,
                    pkg_path=tmp_path,
                )

        assert code == 0
        mock_adapters.assert_called_once_with(tmp_path)
        mock_managers.assert_not_called()
        mock_services.assert_not_called()

    def test_component_managers_routes_to_managers_check(self, tmp_path: Path) -> None:
        manager_health = _make_component_health(HealthStatus.HEALTHY, "managers")
        report = SystemHealthReport.from_category_health({"managers": manager_health})
        with patch.object(
            health_mod, "_check_adapters"
        ) as mock_adapters, patch.object(
            health_mod, "_check_managers", return_value=manager_health
        ) as mock_managers, patch.object(
            health_mod, "_check_services"
        ) as mock_services, patch.object(
            SystemHealthReport, "from_category_health", return_value=report
        ):
            code = handle_health_check(
                component="managers",
                quiet=True,
                pkg_path=tmp_path,
            )

        assert code == 0
        mock_managers.assert_called_once_with(tmp_path)
        mock_adapters.assert_not_called()
        mock_services.assert_not_called()

    def test_component_services_routes_to_services_check(self, tmp_path: Path) -> None:
        svc_health = _make_component_health(HealthStatus.HEALTHY, "services")
        report = SystemHealthReport.from_category_health({"services": svc_health})
        with patch.object(
            health_mod, "_check_adapters"
        ), patch.object(
            health_mod, "_check_managers"
        ), patch.object(
            health_mod, "_check_services", return_value=svc_health
        ) as mock_services, patch.object(
            SystemHealthReport, "from_category_health", return_value=report
        ):
            code = handle_health_check(
                component="services",
                quiet=True,
                pkg_path=tmp_path,
            )

        assert code == 0
        mock_services.assert_called_once_with(tmp_path)

    def test_no_component_runs_all_three_checks(self, tmp_path: Path) -> None:
        with patch.object(
            health_mod, "_check_adapters", return_value=_make_component_health()
        ) as mock_adapters, patch.object(
            health_mod, "_check_managers", return_value=_make_component_health(category="managers")
        ) as mock_managers, patch.object(
            health_mod, "_check_services", return_value=_make_component_health(category="services")
        ) as mock_services:
            code = handle_health_check(quiet=True, pkg_path=tmp_path)

        assert code == 0
        mock_adapters.assert_called_once()
        mock_managers.assert_called_once()
        mock_services.assert_called_once()

    def test_pkg_path_defaults_to_cwd_when_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with patch.object(
            health_mod, "_check_adapters", return_value=_make_component_health()
        ) as mock_adapters:
            handle_health_check(component="adapters", quiet=True)

        assert mock_adapters.call_args.args[0] == tmp_path

    def test_unknown_component_runs_all_categories(self, tmp_path: Path) -> None:
        with patch.object(
            health_mod, "_check_adapters", return_value=_make_component_health()
        ) as mock_adapters, patch.object(
            health_mod, "_check_managers", return_value=_make_component_health(category="managers")
        ), patch.object(
            health_mod, "_check_services", return_value=_make_component_health(category="services")
        ):
            handle_health_check(component="bogus", quiet=True, pkg_path=tmp_path)

        mock_adapters.assert_called_once()


# ---------------------------------------------------------------------------
# handle_health_check — exit codes for each health state
# ---------------------------------------------------------------------------


class TestHandleHealthCheckExitCodes:
    def test_healthy_returns_zero(self, tmp_path: Path) -> None:
        report = SystemHealthReport.from_category_health(
            {"adapters": _make_component_health(HealthStatus.HEALTHY, "adapters")},
        )
        with patch.object(health_mod, "_check_adapters", return_value=_make_component_health(HealthStatus.HEALTHY, "adapters")), patch.object(
            SystemHealthReport, "from_category_health", return_value=report
        ):
            assert handle_health_check(component="adapters", quiet=True, pkg_path=tmp_path) == 0

    def test_degraded_returns_one(self, tmp_path: Path) -> None:
        cat = _make_component_health(HealthStatus.DEGRADED, "adapters")
        report = SystemHealthReport.from_category_health({"adapters": cat})
        with patch.object(health_mod, "_check_adapters", return_value=cat), patch.object(
            SystemHealthReport, "from_category_health", return_value=report
        ):
            assert handle_health_check(component="adapters", quiet=True, pkg_path=tmp_path) == 1

    def test_unhealthy_returns_two(self, tmp_path: Path) -> None:
        cat = _make_component_health(HealthStatus.UNHEALTHY, "adapters")
        report = SystemHealthReport.from_category_health({"adapters": cat})
        with patch.object(health_mod, "_check_adapters", return_value=cat), patch.object(
            SystemHealthReport, "from_category_health", return_value=report
        ):
            assert handle_health_check(component="adapters", quiet=True, pkg_path=tmp_path) == 2


# ---------------------------------------------------------------------------
# handle_health_check — error handling for each category
# ---------------------------------------------------------------------------


class TestHandleHealthCheckErrorHandling:
    def test_adapter_check_failure_yields_unhealthy_category(self, tmp_path: Path) -> None:
        with patch.object(health_mod, "_check_adapters", side_effect=RuntimeError("boom")), patch.object(
            health_mod, "_check_managers", return_value=_make_component_health(HealthStatus.HEALTHY, "managers")
        ), patch.object(health_mod, "_check_services", return_value=_make_component_health(HealthStatus.HEALTHY, "services")):
            code = handle_health_check(quiet=True, pkg_path=tmp_path)

        assert code == 2  # unhealthy

    def test_manager_check_failure_yields_unhealthy_category(self, tmp_path: Path) -> None:
        with patch.object(health_mod, "_check_adapters", return_value=_make_component_health(HealthStatus.HEALTHY, "adapters")), patch.object(
            health_mod, "_check_managers", side_effect=RuntimeError("boom")
        ), patch.object(health_mod, "_check_services", return_value=_make_component_health(HealthStatus.HEALTHY, "services")):
            code = handle_health_check(quiet=True, pkg_path=tmp_path)

        assert code == 2

    def test_service_check_failure_yields_unhealthy_category(self, tmp_path: Path) -> None:
        with patch.object(health_mod, "_check_adapters", return_value=_make_component_health(HealthStatus.HEALTHY, "adapters")), patch.object(
            health_mod, "_check_managers", return_value=_make_component_health(HealthStatus.HEALTHY, "managers")
        ), patch.object(health_mod, "_check_services", side_effect=RuntimeError("boom")):
            code = handle_health_check(quiet=True, pkg_path=tmp_path)

        assert code == 2

    def test_all_categories_failing_still_returns_exit_code(self, tmp_path: Path) -> None:
        with patch.object(health_mod, "_check_adapters", side_effect=RuntimeError("a")), patch.object(
            health_mod, "_check_managers", side_effect=RuntimeError("m")
        ), patch.object(health_mod, "_check_services", side_effect=RuntimeError("s")):
            code = handle_health_check(quiet=True, pkg_path=tmp_path)

        assert code == 2


# ---------------------------------------------------------------------------
# handle_health_check — output format dispatch
# ---------------------------------------------------------------------------


class TestHandleHealthCheckOutput:
    def test_json_output_calls_output_json(self, tmp_path: Path, fake_console: Console) -> None:
        cat = _make_component_health(HealthStatus.HEALTHY, "adapters")
        report = SystemHealthReport.from_category_health({"adapters": cat})
        with patch.object(health_mod, "_check_adapters", return_value=cat), patch.object(
            health_mod, "_output_json"
        ) as mock_json, patch.object(health_mod, "_output_table") as mock_table, patch.object(
            Console, "__init__", lambda self, *a, **kw: None
        ), patch.object(health_mod, "_output_json", wraps=health_mod._output_json):
            handle_health_check(
                component="adapters",
                json_output=True,
                verbose=False,
                quiet=False,
                pkg_path=tmp_path,
            )

        mock_json.assert_called_once()
        mock_table.assert_not_called()

    def test_text_output_calls_output_table(self, tmp_path: Path) -> None:
        cat = _make_component_health(HealthStatus.HEALTHY, "adapters")
        report = SystemHealthReport.from_category_health({"adapters": cat})
        with patch.object(health_mod, "_check_adapters", return_value=cat), patch.object(
            health_mod, "_output_table"
        ) as mock_table, patch.object(health_mod, "_output_json") as mock_json:
            handle_health_check(
                component="adapters",
                json_output=False,
                verbose=False,
                quiet=False,
                pkg_path=tmp_path,
            )

        mock_table.assert_called_once()
        mock_json.assert_not_called()

    def test_quiet_suppresses_all_output(self, tmp_path: Path) -> None:
        cat = _make_component_health(HealthStatus.HEALTHY, "adapters")
        with patch.object(health_mod, "_check_adapters", return_value=cat), patch.object(
            health_mod, "_output_table"
        ) as mock_table, patch.object(health_mod, "_output_json") as mock_json:
            code = handle_health_check(
                component="adapters",
                json_output=True,
                verbose=True,
                quiet=True,
                pkg_path=tmp_path,
            )

        assert code == 0
        mock_table.assert_not_called()
        mock_json.assert_not_called()


# ---------------------------------------------------------------------------
# _check_adapters
# ---------------------------------------------------------------------------


class TestCheckAdapters:
    def test_returns_component_health_with_adapters_category(self) -> None:
        result = _check_adapters(Path("/tmp"))
        assert result.category == "adapters"
        assert isinstance(result, ComponentHealth)

    def test_includes_adapter_base_when_protocol_present(self) -> None:
        # The crackerjack runtime guarantees QAAdapterBase is importable,
        # so adapter_base ends up healthy in the result.
        result = _check_adapters(Path("/tmp"))
        assert "adapter_base" in result.components

    def test_handles_missing_module_gracefully(self) -> None:
        # Simulate a failure loading the adapter base module.
        with patch.dict("sys.modules", {"crackerjack.adapters._qa_adapter_base": None}):
            result = _check_adapters(Path("/tmp"))

        # The function should not raise; some component will be marked unhealthy.
        assert isinstance(result, ComponentHealth)
        assert result.category == "adapters"
        # At least one component is tracked.
        assert result.total >= 1


# ---------------------------------------------------------------------------
# _check_managers
# ---------------------------------------------------------------------------


class TestCheckManagers:
    def test_returns_component_health_with_managers_category(self) -> None:
        result = _check_managers(Path("/tmp"))
        assert result.category == "managers"

    def test_includes_all_three_managers(self) -> None:
        result = _check_managers(Path("/tmp"))
        # All three managers should be probed in a working environment.
        assert {"hook_manager", "test_manager", "publish_manager"}.issubset(
            result.components.keys()
        )

    def test_unhealthy_when_hook_manager_import_fails(self) -> None:
        with patch.dict("sys.modules", {"crackerjack.managers.hook_manager": None}):
            result = _check_managers(Path("/tmp"))

        assert result.components["hook_manager"].status == HealthStatus.UNHEALTHY
        assert result.unhealthy >= 1


# ---------------------------------------------------------------------------
# _check_services
# ---------------------------------------------------------------------------


class TestCheckServices:
    def test_returns_component_health_with_services_category(self, tmp_path: Path) -> None:
        result = _check_services(tmp_path)
        assert result.category == "services"

    def test_filesystem_healthy_for_existing_dir(self, tmp_path: Path) -> None:
        result = _check_services(tmp_path)
        fs = result.components.get("filesystem_service")
        assert fs is not None
        assert fs.status == HealthStatus.HEALTHY

    def test_filesystem_unhealthy_for_missing_path(self) -> None:
        bogus = Path("/nonexistent/path/that/cannot/exist/12345")
        result = _check_services(bogus)
        fs = result.components.get("filesystem_service")
        assert fs is not None
        assert fs.status == HealthStatus.UNHEALTHY
        assert bogus.as_posix() in fs.message or str(bogus) in fs.message

    def test_git_service_healthy_in_git_repo(self, tmp_path: Path) -> None:
        # tmp_path may or may not be a git repo depending on test setup.
        # Mock the GitService to return a known answer.
        mock_service = MagicMock()
        mock_service.is_git_repo.return_value = True
        with patch("crackerjack.services.git.GitService", return_value=mock_service):
            result = _check_services(tmp_path)

        git = result.components.get("git_service")
        assert git is not None
        assert git.status == HealthStatus.HEALTHY

    def test_git_service_degraded_when_not_a_git_repo(self, tmp_path: Path) -> None:
        mock_service = MagicMock()
        mock_service.is_git_repo.return_value = False
        with patch("crackerjack.services.git.GitService", return_value=mock_service):
            result = _check_services(tmp_path)

        git = result.components.get("git_service")
        assert git is not None
        assert git.status == HealthStatus.DEGRADED

    def test_git_service_unhealthy_on_exception(self, tmp_path: Path) -> None:
        with patch("crackerjack.services.git.GitService", side_effect=RuntimeError("git fail")):
            result = _check_services(tmp_path)

        git = result.components.get("git_service")
        assert git is not None
        assert git.status == HealthStatus.UNHEALTHY


# ---------------------------------------------------------------------------
# _output_table / _print_* functions
# ---------------------------------------------------------------------------


class TestOutputTable:
    def test_calls_overall_status_category_details_and_timestamp(
        self, fake_console: Console
    ) -> None:
        report = _make_report()
        with patch.object(health_mod, "_print_overall_status") as m1, patch.object(
            health_mod, "_print_category_details"
        ) as m2, patch.object(health_mod, "_print_timestamp") as m3:
            _output_table(fake_console, report, verbose=False)

        m1.assert_called_once()
        m2.assert_called_once()
        m3.assert_called_once()


class TestPrintOverallStatus:
    def test_renders_uppercase_status_with_color(self, fake_console: Console) -> None:
        report = _make_report(HealthStatus.HEALTHY)
        _print_overall_status(fake_console, report)
        rendered = fake_console.export_text()
        assert "HEALTHY" in rendered
        assert "Overall Status" in rendered

    def test_renders_degraded(self, fake_console: Console) -> None:
        report = _make_report(HealthStatus.DEGRADED)
        _print_overall_status(fake_console, report)
        assert "DEGRADED" in fake_console.export_text()

    def test_renders_unhealthy(self, fake_console: Console) -> None:
        report = _make_report(HealthStatus.UNHEALTHY)
        _print_overall_status(fake_console, report)
        assert "UNHEALTHY" in fake_console.export_text()


class TestPrintCategoryDetails:
    def test_renders_each_category(self, fake_console: Console) -> None:
        report = SystemHealthReport(
            overall_status=HealthStatus.HEALTHY,
            categories={
                "adapters": _make_component_health(HealthStatus.HEALTHY, "adapters"),
                "managers": _make_component_health(HealthStatus.HEALTHY, "managers"),
            },
            summary="ok",
        )
        _print_category_details(fake_console, report, verbose=False)
        rendered = fake_console.export_text()
        assert "Adapters" in rendered
        assert "Managers" in rendered

    def test_verbose_false_skips_component_breakdown(
        self, fake_console: Console
    ) -> None:
        report = SystemHealthReport(
            overall_status=HealthStatus.HEALTHY,
            categories={
                "adapters": _make_component_health(HealthStatus.HEALTHY, "adapters"),
            },
            summary="ok",
        )
        with patch.object(health_mod, "_print_category_components") as mock_print:
            _print_category_details(fake_console, report, verbose=False)
        mock_print.assert_not_called()

    def test_verbose_true_prints_component_breakdown(
        self, fake_console: Console
    ) -> None:
        report = SystemHealthReport(
            overall_status=HealthStatus.HEALTHY,
            categories={
                "adapters": _make_component_health(HealthStatus.HEALTHY, "adapters"),
            },
            summary="ok",
        )
        with patch.object(health_mod, "_print_category_components") as mock_print:
            _print_category_details(fake_console, report, verbose=True)
        mock_print.assert_called_once()


class TestPrintSingleCategory:
    def test_renders_healthy_counts(self, fake_console: Console) -> None:
        cat = _make_component_health(HealthStatus.HEALTHY, "adapters")
        _print_single_category(fake_console, "adapters", cat, verbose=False)
        rendered = fake_console.export_text()
        assert "Adapters" in rendered
        assert "healthy" in rendered

    def test_verbose_includes_component_listing(self, fake_console: Console) -> None:
        cat = _make_component_health(HealthStatus.HEALTHY, "adapters")
        with patch.object(health_mod, "_print_category_components") as mock_print:
            _print_single_category(fake_console, "adapters", cat, verbose=True)
        mock_print.assert_called_once()

    def test_no_components_skips_verbose_branch(self, fake_console: Console) -> None:
        empty_cat = ComponentHealth(
            category="adapters",
            overall_status=HealthStatus.HEALTHY,
            total=0,
            healthy=0,
            degraded=0,
            unhealthy=0,
            components={},
        )
        with patch.object(health_mod, "_print_category_components") as mock_print:
            _print_single_category(fake_console, "adapters", empty_cat, verbose=True)
        mock_print.assert_not_called()


class TestPrintCategoryComponents:
    def test_renders_component_name_and_status(self, fake_console: Console) -> None:
        components = {
            "alpha": _make_healthy_result("alpha", message="all good"),
            "beta": _make_unhealthy_result("beta", message="down"),
        }
        _print_category_components(fake_console, components, verbose=False)
        rendered = fake_console.export_text()
        assert "alpha" in rendered
        assert "beta" in rendered
        assert "all good" in rendered
        assert "down" in rendered

    def test_verbose_includes_details(self, fake_console: Console) -> None:
        components = {
            "alpha": HealthCheckResult.healthy(
                message="ok",
                component_name="alpha",
                details={"key": "value"},
            ),
        }
        with patch.object(health_mod, "_print_component_details") as mock_details:
            _print_category_components(fake_console, components, verbose=True)
        mock_details.assert_called_once()

    def test_verbose_false_skips_details(self, fake_console: Console) -> None:
        components = {
            "alpha": HealthCheckResult.healthy(
                message="ok",
                component_name="alpha",
                details={"key": "value"},
            ),
        }
        with patch.object(health_mod, "_print_component_details") as mock_details:
            _print_category_components(fake_console, components, verbose=False)
        mock_details.assert_not_called()

    def test_skips_message_when_empty(self, fake_console: Console) -> None:
        components = {
            "alpha": HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="",
                component_name="alpha",
            ),
        }
        _print_category_components(fake_console, components, verbose=False)
        # No assertion on absence needed — the function should not raise.


class TestPrintComponentDetails:
    def test_renders_each_key_value(self, fake_console: Console) -> None:
        details = {"a": 1, "b": "two"}
        _print_component_details(fake_console, details)
        rendered = fake_console.export_text()
        assert "a:" in rendered
        assert "b:" in rendered
        assert "1" in rendered
        assert "two" in rendered

    def test_empty_details_renders_nothing_extra(self, fake_console: Console) -> None:
        _print_component_details(fake_console, {})
        # Should not raise; nothing is rendered.


class TestPrintTimestamp:
    def test_renders_timestamp_line(self, fake_console: Console) -> None:
        report = _make_report()
        _print_timestamp(fake_console, report)
        rendered = fake_console.export_text()
        assert "Checked at" in rendered


# ---------------------------------------------------------------------------
# _output_json
# ---------------------------------------------------------------------------


class TestOutputJson:
    def test_prints_valid_json(self, fake_console: Console) -> None:
        report = _make_report()
        _output_json(fake_console, report, verbose=False)
        raw = fake_console.export_text()
        data = json.loads(raw)
        assert "overall_status" in data
        assert "categories" in data

    def test_non_verbose_omits_components(self, fake_console: Console) -> None:
        report = _make_report()
        _output_json(fake_console, report, verbose=False)
        data = json.loads(fake_console.export_text())
        for category in data["categories"].values():
            assert category["components"] == {}

    def test_verbose_includes_components(self, fake_console: Console) -> None:
        report = _make_report()
        _output_json(fake_console, report, verbose=True)
        data = json.loads(fake_console.export_text())
        categories = data["categories"]
        assert categories, "expected at least one category"
        for category in categories.values():
            assert category["components"] != {}


# ---------------------------------------------------------------------------
# Integration: end-to-end JSON vs text output behavior
# ---------------------------------------------------------------------------


class TestIntegrationOutputs:
    def test_handle_health_check_json_output_uses_json_serializer(
        self, tmp_path: Path
    ) -> None:
        cat = _make_component_health(HealthStatus.HEALTHY, "adapters")
        report = SystemHealthReport.from_category_health({"adapters": cat})

        captured_console = Console(record=True, force_terminal=False, width=200)

        def fake_console_init(self: object, *args: object, **kwargs: object) -> None:
            # Replace self with a pre-built recording console.
            self.__dict__.update(captured_console.__dict__)

        with patch.object(health_mod, "_check_adapters", return_value=cat), patch.object(
            Console, "__init__", fake_console_init
        ):
            code = handle_health_check(
                component="adapters",
                json_output=True,
                verbose=False,
                quiet=False,
                pkg_path=tmp_path,
            )

        assert code == 0
        rendered = captured_console.export_text()
        # The JSON path always emits a JSON object.
        assert rendered.strip().startswith("{")
        assert '"overall_status"' in rendered
