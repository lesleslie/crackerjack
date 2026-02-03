"""Health check mixin for QA adapters.

This module provides a mixin class that adds health check functionality
to QA adapters, enabling them to report their status.
"""

from __future__ import annotations

import logging
import shutil
import typing as t
from pathlib import Path

from crackerjack.models.health_check import HealthCheckResult

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


logger = logging.getLogger(__name__)


class HealthCheckMixin:
    """Mixin class adding health check functionality to adapters.

    This mixin provides a standard health_check() implementation that
    can be used by any QA adapter. It checks:
    - Tool availability (is the tool installed?)
    - Configuration validity
    - Required dependencies

    Usage:
        ```python
        class MyAdapter(QAAdapterBase, HealthCheckMixin):
            def __init__(self, config: QACheckConfig, ...):
                super().__init__(config, ...)
                self.tool_name = "mytool"

            # health_check() is inherited from HealthCheckMixin
        ```
    """

    tool_name: str = ""
    """Name of the tool this adapter wraps."""

    config: QACheckConfig | None = None
    """Configuration for this adapter."""

    pkg_path: Path | None = None
    """Package path for the project."""

    def health_check(self) -> HealthCheckResult:
        """Perform health check for this adapter.

        Returns:
            HealthCheckResult: Health status of the adapter

        Checks performed:
        1. Tool availability (is tool installed?)
        2. Configuration validity
        3. Package path accessibility (if set)
        """
        import time

        start_time = time.time()
        component_name = self.__class__.__name__
        issues = []

        # Check 1: Tool availability
        tool_available = self._check_tool_available()
        if not tool_available:
            issues.append(f"Tool '{self.tool_name}' not found in PATH")

        # Check 2: Configuration
        config_valid = self._check_configuration()
        if not config_valid:
            issues.append("Configuration is invalid or missing")

        # Check 3: Package path (if set)
        if self.pkg_path:
            path_accessible = self._check_package_path()
            if not path_accessible:
                issues.append(f"Package path not accessible: {self.pkg_path}")

        # Determine status
        check_duration_ms = (time.time() - start_time) * 1000

        if not issues:
            return HealthCheckResult.healthy(
                message=f"Adapter '{component_name}' is healthy",
                component_name=component_name,
                details={
                    "tool_name": self.tool_name,
                    "tool_available": True,
                    "config_valid": True,
                    "pkg_path": str(self.pkg_path) if self.pkg_path else None,
                },
                check_duration_ms=check_duration_ms,
            )
        elif not tool_available:
            # Tool not available is critical
            return HealthCheckResult.unhealthy(
                message=f"Adapter '{component_name}' is unhealthy: {'; '.join(issues)}",
                component_name=component_name,
                details={
                    "tool_name": self.tool_name,
                    "tool_available": False,
                    "issues": issues,
                },
                check_duration_ms=check_duration_ms,
            )
        else:
            # Other issues are degraded
            return HealthCheckResult.degraded(
                message=f"Adapter '{component_name}' is degraded: {'; '.join(issues)}",
                component_name=component_name,
                details={
                    "tool_name": self.tool_name,
                    "tool_available": tool_available,
                    "config_valid": config_valid,
                    "issues": issues,
                },
                check_duration_ms=check_duration_ms,
            )

    def is_healthy(self) -> bool:
        """Quick check if adapter is healthy.

        Returns:
            bool: True if healthy, False otherwise
        """
        result = self.health_check()
        return result.status == "healthy"

    def _check_tool_available(self) -> bool:
        """Check if the tool is available in PATH.

        Returns:
            bool: True if tool is available, False otherwise
        """
        if not self.tool_name:
            return True  # No tool to check

        return shutil.which(self.tool_name) is not None

    def _check_configuration(self) -> bool:
        """Check if configuration is valid.

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        # If no config is set, that's okay (use defaults)
        if self.config is None:
            return True

        # Check if config has required attributes
        try:
            _ = self.config.name
            _ = self.config.enabled
            return True
        except (AttributeError, TypeError):
            return False

    def _check_package_path(self) -> bool:
        """Check if package path is accessible.

        Returns:
            bool: True if path exists and is accessible, False otherwise
        """
        if self.pkg_path is None:
            return True

        return self.pkg_path.exists() and self.pkg_path.is_dir()

    def get_tool_version(self) -> str | None:
        """Get the version of the tool this adapter wraps.

        Returns:
            Tool version string, or None if not available

        Subclasses can override this to provide actual version info.
        """
        return None


__all__ = ["HealthCheckMixin"]
