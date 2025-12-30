from pathlib import Path

from .config_integrity import ConfigIntegrityService
from .smart_scheduling import SmartSchedulingService
from .version_checker import VersionChecker, VersionInfo

__all__ = [
    "VersionInfo",
    "ToolVersionService",
    "ConfigIntegrityService",
    "SmartSchedulingService",
]


class ToolVersionService:
    def __init__(self, project_path: Path | None = None) -> None:
        self.console = console
        self.project_path = project_path or Path.cwd()

        self._version_checker = VersionChecker()
        self._config_integrity = ConfigIntegrityService(self.project_path)
        self._scheduling = SmartSchedulingService(self.project_path)

    async def check_tool_updates(self) -> dict[str, VersionInfo]:
        return await self._version_checker.check_tool_updates()

    def check_config_integrity(self) -> bool:
        return self._config_integrity.check_config_integrity()

    def should_scheduled_init(self) -> bool:
        return self._scheduling.should_scheduled_init()

    def record_init_timestamp(self) -> None:
        self._scheduling.record_init_timestamp()


ToolManager = ToolVersionService
