"""Unit tests for tool version service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.services.tool_version_service import ToolManager, ToolVersionService
from crackerjack.services.version_checker import VersionInfo


@pytest.fixture
def console() -> MagicMock:
    return MagicMock()


@pytest.fixture
def dependencies() -> tuple[MagicMock, MagicMock, MagicMock]:
    checker = MagicMock()
    integrity = MagicMock()
    scheduling = MagicMock()
    return checker, integrity, scheduling


def test_constructor_wires_dependencies(
    console: MagicMock,
    dependencies: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    checker, integrity, scheduling = dependencies

    with patch(
        "crackerjack.services.tool_version_service.Console",
        return_value=console,
    ), patch(
        "crackerjack.services.tool_version_service.VersionChecker",
        return_value=checker,
    ), patch(
        "crackerjack.services.tool_version_service.ConfigIntegrityService",
        return_value=integrity,
    ) as mock_integrity_cls, patch(
        "crackerjack.services.tool_version_service.SmartSchedulingService",
        return_value=scheduling,
    ) as mock_scheduling_cls:
        service = ToolVersionService(console=None, project_path=Path("/tmp/project"))

    assert service.console is console
    assert service.project_path == Path("/tmp/project")
    assert service._version_checker is checker
    assert service._config_integrity is integrity
    assert service._scheduling is scheduling
    mock_integrity_cls.assert_called_once_with(Path("/tmp/project"))
    mock_scheduling_cls.assert_called_once_with(Path("/tmp/project"))


@pytest.mark.asyncio
async def test_forwarding_methods(
    console: MagicMock,
    dependencies: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    checker, integrity, scheduling = dependencies
    checker.check_tool_updates = AsyncMock(
        return_value={
            "ruff": VersionInfo(
                tool_name="ruff",
                current_version="1.0.0",
                latest_version="1.1.0",
                update_available=True,
            ),
        },
    )
    integrity.check_config_integrity.return_value = True
    scheduling.should_scheduled_init.return_value = True

    with patch(
        "crackerjack.services.tool_version_service.Console",
        return_value=console,
    ), patch(
        "crackerjack.services.tool_version_service.VersionChecker",
        return_value=checker,
    ), patch(
        "crackerjack.services.tool_version_service.ConfigIntegrityService",
        return_value=integrity,
    ), patch(
        "crackerjack.services.tool_version_service.SmartSchedulingService",
        return_value=scheduling,
    ):
        service = ToolVersionService(project_path=Path("/tmp/project"))

    updates = await service.check_tool_updates()
    assert updates["ruff"].update_available is True
    assert service.check_config_integrity() is True
    assert service.should_scheduled_init() is True

    service.record_init_timestamp()

    checker.check_tool_updates.assert_awaited_once()
    integrity.check_config_integrity.assert_called_once()
    scheduling.should_scheduled_init.assert_called_once()
    scheduling.record_init_timestamp.assert_called_once()


def test_tool_manager_alias_points_to_service() -> None:
    assert ToolManager is ToolVersionService
