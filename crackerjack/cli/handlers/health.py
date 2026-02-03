"""Health check CLI handler for Crackerjack.

This module provides the CLI command for checking the health of all
Crackerjack components: adapters, managers, and services.
"""

from __future__ import annotations

import json
import logging
import typing as t
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


# Health check status colors
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
    """Handle the health check CLI command.

    Args:
        component: Specific component to check (adapters, managers, services, all)
        json_output: Output results as JSON
        verbose: Show detailed health information
        quiet: Only show exit code (no output)
        pkg_path: Package path to check

    Returns:
        int: Exit code (0=healthy, 1=degraded, 2=unhealthy)
    """
    console = Console()

    if pkg_path is None:
        pkg_path = Path.cwd()

    # Determine which components to check
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
        # Check all components
        all_health = {}
        try:
            all_health["adapters"] = _check_adapters(pkg_path)
        except Exception:
            logger.exception("Failed to check adapters")
            all_health["adapters"] = ComponentHealth(
                category="adapters",
                overall_status="unhealthy",
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
                overall_status="unhealthy",
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
                overall_status="unhealthy",
                total=0,
                healthy=0,
                degraded=0,
                unhealthy=0,
                components={},
            )

        report = SystemHealthReport.from_category_health(all_health)

    # Output results
    if not quiet:
        if json_output:
            _output_json(console, report, verbose)
        else:
            _output_table(console, report, verbose)

    return report.exit_code


def _check_adapters(pkg_path: Path) -> ComponentHealth:
    """Check health of all QA adapters.

    Args:
        pkg_path: Package path

    Returns:
        ComponentHealth: Aggregated adapter health
    """
    results: dict[str, HealthCheckResult] = {}

    # Import adapter registry
    try:
        from crackerjack.adapters._qa_adapter_base import QAAdapterBase

        # Check if adapter base class has health check protocol
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

        # Try to get list of available adapters
        try:
            from crackerjack.adapters.factory import AdapterFactory

            available_adapters = AdapterFactory.list_available()
            results["adapter_factory"] = HealthCheckResult.healthy(
                message=f"Found {len(available_adapters)} available adapters",
                component_name="AdapterFactory",
                details={"adapter_count": len(available_adapters)},
            )
        except Exception as e:
            results["adapter_factory"] = HealthCheckResult.degraded(
                message=f"Could not list adapters: {e!s}",
                component_name="AdapterFactory",
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
    """Check health of all managers.

    Args:
        pkg_path: Package path

    Returns:
        ComponentHealth: Aggregated manager health
    """
    results: dict[str, HealthCheckResult] = {}

    # Check HookManager
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

    # Check TestManager
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

    # Check PublishManager
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
    """Check health of all services.

    Args:
        pkg_path: Package path

    Returns:
        ComponentHealth: Aggregated service health
    """
    results: dict[str, HealthCheckResult] = {}

    # Check GitService
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

    # Check EnhancedFileSystemService
    try:
        from crackerjack.services.enhanced_filesystem import EnhancedFileSystemService

        can_read = pkg_path.exists() and pkg_path.is_dir()
        if can_read:
            results["filesystem_service"] = HealthCheckResult.healthy(
                message="Filesystem is accessible",
                component_name="EnhancedFileSystemService",
                details={"pkg_path": str(pkg_path)},
            )
        else:
            results["filesystem_service"] = HealthCheckResult.unhealthy(
                message=f"Cannot access package path: {pkg_path}",
                component_name="EnhancedFileSystemService",
                details={"pkg_path": str(pkg_path)},
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
    """Output health report as a formatted table.

    Args:
        console: Rich console instance
        report: Health report to display
        verbose: Show detailed information
    """
    # Overall status
    status_color = STATUS_COLORS[report.overall_status]
    console.print(
        f"\n[{status_color}]●[/] "
        f"Overall Status: [{status_color}]{report.overall_status.upper()}[/{status_color}]"
    )
    console.print(f"📊 {report.summary}\n")

    # Category breakdown
    for category_name, category_health in report.categories.items():
        status_color = STATUS_COLORS[category_health.overall_status]
        console.print(
            f"[{status_color}]●[/] "
            f"{category_name.title()}: [{status_color}]{category_health.overall_status}[/] "
            f"({category_health.healthy}/{category_health.total} healthy)"
        )

        if verbose and category_health.components:
            for comp_name, comp_result in category_health.components.items():
                comp_color = STATUS_COLORS[comp_result.status]
                console.print(
                    f"  [{comp_color}]→[/] {comp_name}: [{comp_color}]{comp_result.status}[/]"
                )
                if comp_result.message:
                    console.print(f"     {comp_result.message}")

                if comp_result.details and verbose:
                    for key, value in comp_result.details.items():
                        console.print(f"     • {key}: {value}")

        console.print()

    # Timestamp
    console.print(
        f"🕒 Checked at: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )


def _output_json(console: Console, report: SystemHealthReport, verbose: bool) -> None:
    """Output health report as JSON.

    Args:
        console: Rich console instance
        report: Health report to display
        verbose: Include detailed information
    """
    data = report.to_dict()

    if not verbose:
        # Remove component details in non-verbose mode
        for category in data["categories"].values():
            category["components"] = {}

    console.print(json.dumps(data, indent=2))


__all__ = ["handle_health_check"]
