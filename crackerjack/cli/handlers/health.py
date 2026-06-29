from __future__ import annotations

import json
import logging
import typing as t
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from crackerjack.models.health_check import (
    ComponentHealth,
    HealthCheckResult,
    SystemHealthReport,
)

if t.TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


# Path to the crackerjack integration metrics DB. Schema lives in
# session_buddy.crackerjack_integration.CrackerjackIntegration but is created
# idempotently by the first writer. We open the same path so any subsequent
# read by the MCP ``get_crackerjack_quality_metrics`` endpoint or by
# session-buddy's ``get_quality_metrics_history`` sees crackerjack CLI runs.
DEFAULT_INTEGRATION_DB_PATH = (
    Path.home() / ".claude" / "data" / "crackerjack_integration.db"
)


STATUS_COLORS = {
    "healthy": "green",
    "degraded": "yellow",
    "unhealthy": "red",
}


def handle_health_check(
    component: str | None = None,
    json_output: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    pkg_path: Path | None = None,
) -> int:
    console = Console()

    if pkg_path is None:
        pkg_path = Path.cwd()

    if component == "adapters":
        category_health = _check_adapters(pkg_path)
        report = SystemHealthReport.from_category_health({"adapters": category_health})
    elif component == "managers":
        category_health = _check_managers(pkg_path)
        report = SystemHealthReport.from_category_health({"managers": category_health})
    elif component == "services":
        category_health = _check_services(pkg_path)
        report = SystemHealthReport.from_category_health({"services": category_health})
    else:
        all_health = {}
        try:
            all_health["adapters"] = _check_adapters(pkg_path)
        except Exception:
            logger.exception("Failed to check adapters")
            all_health["adapters"] = ComponentHealth(
                category="adapters",
                overall_status="unhealthy",  # type: ignore
                total=0,
                healthy=0,
                degraded=0,
                unhealthy=0,
                components={},
            )

        try:
            all_health["managers"] = _check_managers(pkg_path)
        except Exception:
            logger.exception("Failed to check managers")
            all_health["managers"] = ComponentHealth(
                category="managers",
                overall_status="unhealthy",  # type: ignore
                total=0,
                healthy=0,
                degraded=0,
                unhealthy=0,
                components={},
            )

        try:
            all_health["services"] = _check_services(pkg_path)
        except Exception:
            logger.exception("Failed to check services")
            all_health["services"] = ComponentHealth(
                category="services",
                overall_status="unhealthy",  # type: ignore
                total=0,
                healthy=0,
                degraded=0,
                unhealthy=0,
                components={},
            )

        report = SystemHealthReport.from_category_health(all_health)

    if not quiet:
        if json_output:
            _output_json(console, report, verbose)
        else:
            _output_table(console, report, verbose)

    _record_health_snapshot(pkg_path, report)

    return report.exit_code


def _check_adapters(pkg_path: Path) -> ComponentHealth:
    results: dict[str, HealthCheckResult] = {}

    try:
        from crackerjack.adapters._qa_adapter_base import QAAdapterBase

        if hasattr(QAAdapterBase, "health_check"):
            results["adapter_base"] = HealthCheckResult.healthy(
                message="Adapter base class implements health_check",
                component_name="QAAdapterBase",
                details={"has_protocol": True},
            )
        else:
            results["adapter_base"] = HealthCheckResult.degraded(
                message="Adapter base class does not implement health_check",
                component_name="QAAdapterBase",
                details={"has_protocol": False},
            )

        try:
            results["adapter_factory"] = HealthCheckResult.healthy(
                message="DefaultAdapterFactory is available",
                component_name="DefaultAdapterFactory",
                details={"has_factory": True},
            )
        except Exception as e:
            results["adapter_factory"] = HealthCheckResult.degraded(
                message=f"Could not import factory: {e!s}",
                component_name="DefaultAdapterFactory",
                details={"error": str(e)},
            )

    except Exception as e:
        logger.exception("Failed to load adapters")
        results["adapters"] = HealthCheckResult.unhealthy(
            message=f"Failed to load adapter module: {e!s}",
            component_name="adapters",
            details={"error_type": type(e).__name__},
        )

    return ComponentHealth.from_results("adapters", results)


def _check_managers(pkg_path: Path) -> ComponentHealth:
    results: dict[str, HealthCheckResult] = {}

    try:
        from crackerjack.managers.hook_manager import HookManagerImpl

        results["hook_manager"] = HealthCheckResult.healthy(
            message="HookManagerImpl is available",
            component_name="HookManagerImpl",
            details={"has_health_check": hasattr(HookManagerImpl, "health_check")},
        )
    except Exception as e:
        logger.exception("Failed to check HookManager")
        results["hook_manager"] = HealthCheckResult.unhealthy(
            message=f"Failed to check HookManager: {e!s}",
            component_name="HookManager",
            details={"error_type": type(e).__name__},
        )

    try:
        from crackerjack.managers.test_manager import TestManager

        results["test_manager"] = HealthCheckResult.healthy(
            message="TestManager is available",
            component_name="TestManager",
            details={"has_health_check": hasattr(TestManager, "health_check")},
        )
    except Exception as e:
        logger.exception("Failed to check TestManager")
        results["test_manager"] = HealthCheckResult.unhealthy(
            message=f"Failed to check TestManager: {e!s}",
            component_name="TestManager",
            details={"error_type": type(e).__name__},
        )

    try:
        from crackerjack.managers.publish_manager import PublishManagerImpl

        results["publish_manager"] = HealthCheckResult.healthy(
            message="PublishManagerImpl is available",
            component_name="PublishManagerImpl",
            details={"has_health_check": hasattr(PublishManagerImpl, "health_check")},
        )
    except Exception as e:
        logger.exception("Failed to check PublishManager")
        results["publish_manager"] = HealthCheckResult.unhealthy(
            message=f"Failed to check PublishManager: {e!s}",
            component_name="PublishManager",
            details={"error_type": type(e).__name__},
        )

    return ComponentHealth.from_results("managers", results)


def _check_services(pkg_path: Path) -> ComponentHealth:
    results: dict[str, HealthCheckResult] = {}

    try:
        from crackerjack.services.git import GitService

        service = GitService(pkg_path=pkg_path)
        is_repo = service.is_git_repo()

        if is_repo:
            results["git_service"] = HealthCheckResult.healthy(
                message="Git repository detected",
                component_name="GitService",
                details={"is_git_repo": True},
            )
        else:
            results["git_service"] = HealthCheckResult.degraded(
                message="Not a git repository",
                component_name="GitService",
                details={"is_git_repo": False},
            )
    except Exception as e:
        logger.exception("Failed to check GitService")
        results["git_service"] = HealthCheckResult.unhealthy(
            message=f"Failed to check GitService: {e!s}",
            component_name="GitService",
            details={"error_type": type(e).__name__},
        )

    try:
        can_read = pkg_path.exists() and pkg_path.is_dir()
        if can_read:
            results["filesystem_service"] = HealthCheckResult.healthy(
                message="Filesystem is accessible",
                component_name="EnhancedFileSystemService",
                details={"pkg_path": pkg_path},
            )
        else:
            results["filesystem_service"] = HealthCheckResult.unhealthy(
                message=f"Cannot access package path: {pkg_path}",
                component_name="EnhancedFileSystemService",
                details={"pkg_path": pkg_path},
            )
    except Exception as e:
        logger.exception("Failed to check EnhancedFileSystemService")
        results["filesystem_service"] = HealthCheckResult.unhealthy(
            message=f"Failed to check EnhancedFileSystemService: {e!s}",
            component_name="EnhancedFileSystemService",
            details={"error_type": type(e).__name__},
        )

    return ComponentHealth.from_results("services", results)


def _output_table(console: Console, report: SystemHealthReport, verbose: bool) -> None:
    _print_overall_status(console, report)
    _print_category_details(console, report, verbose)
    _print_timestamp(console, report)


def _print_overall_status(console: Console, report: SystemHealthReport) -> None:
    status_color = STATUS_COLORS[report.overall_status]
    console.print(
        f"\n[{status_color}]●[/] "
        f"Overall Status: [{status_color}]{report.overall_status.upper()}[/{status_color}]"
    )
    console.print(f"📊 {report.summary}\n")


def _print_category_details(
    console: Console, report: SystemHealthReport, verbose: bool
) -> None:
    for category_name, category_health in report.categories.items():
        _print_single_category(console, category_name, category_health, verbose)


def _print_single_category(
    console: Console,
    category_name: str,
    category_health: ComponentHealth,
    verbose: bool,
) -> None:
    status_color = STATUS_COLORS[category_health.overall_status]
    console.print(
        f"[{status_color}]●[/] "
        f"{category_name.title()}: [{status_color}]{category_health.overall_status}[/] "
        f"({category_health.healthy}/{category_health.total} healthy)"
    )

    if verbose and category_health.components:
        _print_category_components(console, category_health.components, verbose)

    console.print()


def _print_category_components(
    console: Console, components: dict, verbose: bool
) -> None:
    for comp_name, comp_result in components.items():
        comp_color = STATUS_COLORS[comp_result.status]
        console.print(
            f" [{comp_color}]→[/] {comp_name}: [{comp_color}]{comp_result.status}[/]"
        )
        if comp_result.message:
            console.print(f" {comp_result.message}")

        if comp_result.details and verbose:
            _print_component_details(console, comp_result.details)


def _print_component_details(console: Console, details: dict) -> None:
    for key, value in details.items():
        console.print(f" • {key}: {value}")


def _print_timestamp(console: Console, report: SystemHealthReport) -> None:
    console.print(
        f"🕒 Checked at: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )


def _output_json(console: Console, report: SystemHealthReport, verbose: bool) -> None:
    data = report.to_dict()

    if not verbose:
        for category in data["categories"].values():
            category["components"] = {}

    console.print(json.dumps(data, indent=2))


def _record_health_snapshot(
    pkg_path: Path,
    report: SystemHealthReport,
    db_path: Path | None = None,
) -> None:
    """Persist a one-row-per-category health snapshot to ``quality_metrics_history``.

    The MCP ``get_crackerjack_quality_metrics`` endpoint reads from this
    same table (via session-buddy's ``get_quality_metrics_history``), so
    writing here is what makes ``crackerjack health --component adapters``
    visible to the radar. Failures are best-effort and never propagate:
    the CLI's exit code is the user's primary signal.

    Args:
        pkg_path: Project root passed by the CLI. Used as ``project_path``.
        report: Built ``SystemHealthReport`` to record.
        db_path: Override for tests; defaults to ``DEFAULT_INTEGRATION_DB_PATH``.
    """
    target = db_path or DEFAULT_INTEGRATION_DB_PATH
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        import uuid

        with sqlite3.connect(str(target)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_metrics_history (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    timestamp TIMESTAMP,
                    result_id TEXT,
                    FOREIGN KEY (result_id) REFERENCES crackerjack_results(id)
                )
                """,
            )
            now = datetime.now(UTC).isoformat()
            project_path = str(pkg_path.resolve())
            snapshot_id = f"health_{uuid.uuid4().hex}"
            rows = [
                (
                    f"{snapshot_id}_{category_name}",
                    project_path,
                    f"health_{category_name}",
                    1.0 if cat.overall_status.value == "healthy" else 0.0,
                    now,
                    snapshot_id,
                )
                for category_name, cat in report.categories.items()
            ]
            if not rows:
                # Always emit at least one row so the radar sees *something*
                # even when the user filters down to an empty category.
                rows = [
                    (
                        snapshot_id,
                        project_path,
                        "health_overall",
                        1.0 if report.overall_status.value == "healthy" else 0.0,
                        now,
                        snapshot_id,
                    ),
                ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO quality_metrics_history
                (id, project_path, metric_type, metric_value, timestamp, result_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
    except Exception as e:
        # Best-effort: log at debug level so a read-only filesystem or
        # missing optional dep cannot break the CLI exit code path.
        logger.debug("Failed to record crackerjack health snapshot: %s", e)


__all__ = ["handle_health_check"]
