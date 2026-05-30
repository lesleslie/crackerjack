from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


def _load_tool_version_module() -> types.ModuleType:
    fake_package = types.ModuleType("fakepkg")
    fake_package.__path__ = []  # type: ignore[attr-defined]
    fake_services = types.ModuleType("fakepkg.services")
    fake_services.__path__ = []  # type: ignore[attr-defined]

    fake_config_integrity = types.ModuleType("fakepkg.services.config_integrity")
    fake_smart_scheduling = types.ModuleType("fakepkg.services.smart_scheduling")
    fake_version_checker = types.ModuleType("fakepkg.services.version_checker")

    class FakeConfigIntegrityService:
        def __init__(self, project_path: Path) -> None:
            self.project_path = project_path
            self.calls = 0

        def check_config_integrity(self) -> bool:
            self.calls += 1
            return True

    class FakeSmartSchedulingService:
        def __init__(self, project_path: Path) -> None:
            self.project_path = project_path
            self.calls = 0

        def should_scheduled_init(self) -> bool:
            self.calls += 1
            return True

        def record_init_timestamp(self) -> None:
            self.calls += 1

    class FakeVersionChecker:
        def __init__(self) -> None:
            self.check_tool_updates = AsyncMock(
                return_value={"ruff": {"update_available": True}},
            )

    fake_config_integrity.ConfigIntegrityService = FakeConfigIntegrityService
    fake_smart_scheduling.SmartSchedulingService = FakeSmartSchedulingService
    fake_version_checker.VersionChecker = FakeVersionChecker
    fake_version_checker.VersionInfo = dict

    sys.modules["fakepkg"] = fake_package
    sys.modules["fakepkg.services"] = fake_services
    sys.modules["fakepkg.services.config_integrity"] = fake_config_integrity
    sys.modules["fakepkg.services.smart_scheduling"] = fake_smart_scheduling
    sys.modules["fakepkg.services.version_checker"] = fake_version_checker

    module_path = (
        Path(__file__).resolve().parents[3]
        / "crackerjack"
        / "services"
        / "tool_version_service.py"
    )
    spec = importlib.util.spec_from_file_location(
        "fakepkg.services.tool_version_service",
        module_path,
    )
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["fakepkg.services.tool_version_service"] = module
    spec.loader.exec_module(module)
    return module


def test_tool_version_service_wires_dependencies_and_forwards_calls() -> None:
    module = _load_tool_version_module()

    console = MagicMock()
    service = module.ToolVersionService(
        console=console,
        project_path=Path("/tmp/project"),
    )

    assert service.console is console
    assert service.project_path == Path("/tmp/project")
    assert asyncio.run(service.check_tool_updates()) == {"ruff": {"update_available": True}}
    assert service.check_config_integrity() is True
    assert service.should_scheduled_init() is True
    service.record_init_timestamp()
    assert module.ToolManager is module.ToolVersionService


def test_tool_version_service_uses_default_paths() -> None:
    module = _load_tool_version_module()

    original_cwd = Path.cwd()
    service = module.ToolVersionService()

    assert service.project_path == original_cwd
    assert service.console is not None
