"""Tool version service - unified facade for version and configuration management.

This module provides a unified interface to various tool and configuration services.
The implementation has been split into focused modules following single responsibility principle.

REFACTORING NOTE: This file was reduced from 1353 lines to ~50 lines by splitting into:
- version_checker.py: Core version checking and comparison
- config_integrity.py: Configuration file integrity checking
- smart_scheduling.py: Intelligent scheduling for automated initialization
- (Additional services extracted into separate files)
"""

from pathlib import Path

from rich.console import Console

from .config_integrity import ConfigIntegrityService
from .smart_scheduling import SmartSchedulingService
from .version_checker import VersionChecker, VersionInfo

# Re-export for backward compatibility
__all__ = [
    "VersionInfo",
    "ToolVersionService",
    "ConfigIntegrityService",
    "SmartSchedulingService",
]


class ToolVersionService:
    """Facade for tool version management services."""

    def __init__(self, console: Console, project_path: Path | None = None) -> None:
        self.console = console
        self.project_path = project_path or Path.cwd()

        # Initialize component services
        self._version_checker = VersionChecker(console)
        self._config_integrity = ConfigIntegrityService(console, self.project_path)
        self._scheduling = SmartSchedulingService(console, self.project_path)

    async def check_tool_updates(self) -> dict[str, VersionInfo]:
        """Check for tool updates using the version checker service."""
        return await self._version_checker.check_tool_updates()

    def check_config_integrity(self) -> bool:
        """Check configuration integrity using the config integrity service."""
        return self._config_integrity.check_config_integrity()

    def should_scheduled_init(self) -> bool:
        """Check if scheduled initialization should run."""
        return self._scheduling.should_scheduled_init()

    def record_init_timestamp(self) -> None:
        """Record initialization timestamp."""
        self._scheduling.record_init_timestamp()


# For backward compatibility, maintain the other services here if needed
# They are primarily accessed through the facade now
ToolManager = ToolVersionService  # Alias for compatibility
