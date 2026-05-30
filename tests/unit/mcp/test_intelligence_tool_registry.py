from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock


def _load_registry_module() -> types.ModuleType:
    fake_package = types.ModuleType("fakepkg")
    fake_package.__path__ = []  # type: ignore[attr-defined]
    fake_tools = types.ModuleType("fakepkg.tools")
    fake_tools.__path__ = []  # type: ignore[attr-defined]
    fake_intelligence_tools = types.ModuleType("fakepkg.tools.intelligence_tools")

    fake_intelligence_tools.execute_smart_agent_task = AsyncMock(
        return_value={"tool": "execute"},
    )
    fake_intelligence_tools.get_smart_agent_recommendation = AsyncMock(
        return_value={"tool": "recommend"},
    )
    fake_intelligence_tools.get_intelligence_system_status = AsyncMock(
        return_value={"tool": "status"},
    )
    fake_intelligence_tools.analyze_agent_performance = AsyncMock(
        return_value={"tool": "analysis"},
    )

    sys.modules["fakepkg"] = fake_package
    sys.modules["fakepkg.tools"] = fake_tools
    sys.modules["fakepkg.tools.intelligence_tools"] = fake_intelligence_tools

    module_path = (
        Path(__file__).resolve().parents[3]
        / "crackerjack"
        / "mcp"
        / "tools"
        / "intelligence_tool_registry.py"
    )
    spec = importlib.util.spec_from_file_location(
        "fakepkg.tools.intelligence_tool_registry",
        module_path,
    )
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["fakepkg.tools.intelligence_tool_registry"] = module
    spec.loader.exec_module(module)
    return module


def test_register_intelligence_tools_registers_expected_tools() -> None:
    module = _load_registry_module()

    class FakeApp:
        def __init__(self) -> None:
            self.registered: dict[str, object] = {}

        def tool(self):
            def decorator(func):
                self.registered[func.__name__] = func
                return func

            return decorator

    app = FakeApp()
    module.register_intelligence_tools(app)

    assert set(app.registered) == {
        "execute_smart_task",
        "get_agent_recommendation",
        "intelligence_system_status",
        "agent_performance_analysis",
    }


def test_registered_tools_delegate_to_underlying_helpers() -> None:
    module = _load_registry_module()

    class FakeApp:
        def __init__(self) -> None:
            self.registered: dict[str, object] = {}

        def tool(self):
            def decorator(func):
                self.registered[func.__name__] = func
                return func

            return decorator

    app = FakeApp()
    module.register_intelligence_tools(app)

    execute = app.registered["execute_smart_task"]
    recommendation = app.registered["get_agent_recommendation"]
    status = app.registered["intelligence_system_status"]
    analysis = app.registered["agent_performance_analysis"]

    result = asyncio.run(
        execute(
            "task",
            context_type="code",
            strategy="multi",
            max_agents=5,
            use_learning=False,
        ),
    )
    assert result == {"tool": "execute"}
    module.execute_smart_agent_task.assert_awaited_once_with(
        "task",
        "code",
        "multi",
        5,
        False,
    )

    result = asyncio.run(
        recommendation(
            "task",
            context_type="docs",
            include_analysis=False,
        ),
    )
    assert result == {"tool": "recommend"}
    module.get_smart_agent_recommendation.assert_awaited_once_with(
        "task",
        "docs",
        False,
    )

    assert asyncio.run(status()) == {"tool": "status"}
    assert asyncio.run(analysis()) == {"tool": "analysis"}
    module.get_intelligence_system_status.assert_awaited_once_with()
    module.analyze_agent_performance.assert_awaited_once_with()
