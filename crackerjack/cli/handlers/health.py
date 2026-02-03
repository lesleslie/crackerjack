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
from rich.table import Table

from crackerjack.models.health_check import (
    ComponentHealth,
    HealthCheckResult,
    SystemHealthReport,
    health_check_wrapper,
)

if t.TYPE_CHECKING:
    from collections.abc import Sequence


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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        from crackerjack.config import load_settings
        from crackerjack.models.qa_config import QAOrchestratorConfig

        settings = load_settings(pkg_path)
        config = QAOrchestratorConfig.from_settings(settings)

        # Get all enabled adapters
        enabled_checks = config.get_enabled_checks()

        for check_name in enabled_checks:
            try:
                # Create adapter instance
                adapter = QAAdapterBase.create_adapter(check_name, config, pkg_path)

                # Check if adapter has health_check method
                if hasattr(adapter, "health_check"):
                    result = health_check_wrapper(
                        component_name=check_name,
                        check_func=adapter.health_check,
                    )
                    results[check_name] = result
                else:
                    # Adapter doesn't implement health check
                    results[check_name] = HealthCheckResult.degraded(
                        message=f"Adapter '{check_name}' does not implement health_check",
                        component_name=check_name,
                    )
            except Exception as e:
                logger.exception("Failed to check adapter %s", check_name)
                results[check_name] = HealthCheckResult.unhealthy(
                    message=f"Failed to check adapter: {e!s}",
                    component_name=check_name,
                    details={"error_type": type(e).__name__},
                )

    except Exception as e:
        logger.exception("Failed to load adapters")
        # Return unhealthy for entire category
        return ComponentHealth(
            category="adapters",
            overall_status="unhealthy",
            total=0,
            healthy=0,
            degraded=0,
            unhealthy=1,
            components={
                "adapters": HealthCheckResult.unhealthy(
                    message=f"Failed to load adapters: {e!s}",
                    component_name="adapters",
                )
            },
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

        def check_hook_manager() -> HealthCheckResult:
            from crackerjack.config import load_settings
            from crackerjack.core.console import CrackerjackConsole

            settings = load_settings(pkg_path)
            console = CrackerjackConsole()

            manager = HookManagerImpl(
                pkg_path=pkg_path,
                settings=settings,
                console=console,
                verbose=False,
                quiet=True,
                debug=False,
            )

            if hasattr(manager, "health_check"):
                return manager.health_check()
            else:
                return HealthCheckResult.degraded(
                    message="HookManager does not implement health_check",
                    component_name="HookManager",
                )

        results["hook_manager"] = health_check_wrapper("HookManager", check_hook_manager)
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

        def check_test_manager() -> HealthCheckResult:
            from crackerjack.config import load_settings
            from crackerjack.core.console import CrackerjackConsole

            settings = load_settings(pkg_path)
            console = CrackerjackConsole()

            manager = TestManager(
                pkg_path=pkg_path,
                settings=settings,
                console=console,
            )

            if hasattr(manager, "health_check"):
                return manager.health_check()
            else:
                return HealthCheckResult.degraded(
                    message="TestManager does not implement health_check",
                    component_name="TestManager",
                )

        results["test_manager"] = health_check_wrapper("TestManager", check_test_manager)
    except Exception as e:
        logger.exception("Failed to check TestManager")
        results["test_manager"] = HealthCheckResult.unhealthy(
            message=f"Failed to check TestManager: {e!s}",
            component_name="TestManager",
            details={"error_type": type(e).__name__},
        )

    # Check PublishManager
    try:
        from crackerjack.managers.publish_manager import PublishManager

        def check_publish_manager() -> HealthCheckResult:
            from crackerjack.config import load_settings
            from crackerjack.core.console import CrackerjackConsole

            settings = load_settings(pkg_path)
            console = CrackerjackConsole()

            manager = PublishManager(
                pkg_path=pkg_path,
                settings=settings,
                console=console,
            )

            if hasattr(manager, "health_check"):
                return manager.health_check()
            else:
                return HealthCheckResult.degraded(
                    message="PublishManager does not implement health_check",
                    component_name="PublishManager",
                )

        results["publish_manager"] = health_check_wrapper(
            "PublishManager", check_publish_manager
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

        def check_git_service() -> HealthCheckResult:
            service = GitService(pkg_path=pkg_path)

            if hasattr(service, "health_check"):
                return service.health_check()
            else:
                # Basic check
                is_repo = service.is_git_repo()
                if is_repo:
                    return HealthCheckResult.healthy(
                        message="Git repository detected",
                        component_name="GitService",
                        details={"is_git_repo": True},
                    )
                else:
                    return HealthCheckResult.degraded(
                        message="Not a git repository",
                        component_name="GitService",
                        details={"is_git_repo": False},
                    )

        results["git_service"] = health_check_wrapper("GitService", check_git_service)
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

        def check_filesystem_service() -> HealthCheckResult:
            service = EnhancedFileSystemService()

            if hasattr(service, "health_check"):
                return service.health_check()
            else:
                # Basic check
                can_read = pkg_path.exists() and pkg_path.is_dir()
                if can_read:
                    return HealthCheckResult.healthy(
                        message="Filesystem is accessible",
                        component_name="EnhancedFileSystemService",
                        details={"pkg_path": str(pkg_path)},
                    )
                else:
                    return HealthCheckResult.unhealthy(
                        message=f"Cannot access package path: {pkg_path}",
                        component_name="EnhancedFileSystemService",
                        details={"pkg_path": str(pkg_path)},
                    )

        results["filesystem_service"] = health_check_wrapper(
            "EnhancedFileSystemService", check_filesystem_service
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
    console.print(f"🕒 Checked at: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")


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
