
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

    tool_name: str = ""
    """Name of the tool this adapter wraps."""

    config: QACheckConfig | None = None
    """Configuration for this adapter."""

    pkg_path: Path | None = None
    """Package path for the project."""

    def health_check(self) -> HealthCheckResult:
        import time

        start_time = time.time()
        component_name = self.__class__.__name__
        issues = []


        tool_available = self._check_tool_available()
        if not tool_available:
            issues.append(f"Tool '{self.tool_name}' not found in PATH")


        config_valid = self._check_configuration()
        if not config_valid:
            issues.append("Configuration is invalid or missing")


        if self.pkg_path:
            path_accessible = self._check_package_path()
            if not path_accessible:
                issues.append(f"Package path not accessible: {self.pkg_path}")


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
        result = self.health_check()
        return result.status == "healthy"

    def _check_tool_available(self) -> bool:
        if not self.tool_name:
            return True

        return shutil.which(self.tool_name) is not None

    def _check_configuration(self) -> bool:

        if self.config is None:
            return True


        try:
            _ = self.config.name
            _ = self.config.enabled
            return True
        except (AttributeError, TypeError):
            return False

    def _check_package_path(self) -> bool:
        if self.pkg_path is None:
            return True

        return self.pkg_path.exists() and self.pkg_path.is_dir()

    def get_tool_version(self) -> str | None:
        return None


__all__ = ["HealthCheckMixin"]
