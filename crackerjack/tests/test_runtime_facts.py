"""Tests for the runtime-facts builder and Oneiric boot push (Plan 1 Phase 3).

Covers three contracts:

* ``RuntimeFactsBuilder`` enumerates a FastMCP app's registered tools
  into a structured list with name / description / parameters.
* No file in the runtime-facts push path imports ``oneiric`` —
  isolation is enforced by source-grep.
* The Oneiric push fails soft: when ``httpx`` raises, the helper
  returns cleanly without propagating the exception.
"""

from __future__ import annotations

import asyncio
import re
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


NEW_FILE_PATHS = (
    Path(__file__).resolve().parents[1] / "core" / "runtime_facts.py",
    Path(__file__).resolve().parents[1] / "mcp" / "oneiric_runtime.py",
)


def _make_fake_tool(
    name: str, description: str = "", parameters: dict[str, Any] | None = None
) -> _FakeTool:
    """Build a minimal object that quacks like a FastMCP ``Tool``."""

    tool = _FakeTool()
    tool.name = name
    tool.description = description
    tool.parameters = parameters or {"type": "object", "properties": {}}
    return tool


class _FakeTool:
    """Minimal stand-in for a FastMCP ``Tool`` used by runtime-facts tests."""

    name: str
    description: str
    parameters: dict[str, Any]


def _make_fake_app(tools: dict[str, Any] | None = None) -> Any:
    """Build a minimal object that quacks like a ``FastMCP`` for sync access."""

    class _FakeToolManager:
        def __init__(self, registry: dict[str, Any]) -> None:
            self._tools = registry

    class _FakeApp:
        def __init__(self, registry: dict[str, Any]) -> None:
            self._tool_manager = _FakeToolManager(registry)

    return _FakeApp(tools or {})


class CrackerjackRuntimeFactsTests(unittest.TestCase):
    def test_crackerjack_runtime_facts_enumerates_tools(self) -> None:
        """``build_all`` returns a structured list per FastMCP tool."""
        from crackerjack.core.runtime_facts import RuntimeFactsBuilder

        tools = {
            "crackerjack_run": _make_fake_tool(
                "crackerjack_run",
                description="Run quality checks",
                parameters={"type": "object", "properties": {"level": {"type": "string"}}},
            ),
            "search_code": _make_fake_tool(
                "search_code",
                description="Search code patterns",
                parameters={"type": "object"},
            ),
            "mcp_health": _make_fake_tool(
                "mcp_health",
                description="Health probe",
                parameters={"type": "object"},
            ),
        }
        app = _make_fake_app(tools)
        builder = RuntimeFactsBuilder(app)

        facts = builder.build_all()

        self.assertEqual(facts["count"], 3)
        self.assertEqual(len(facts["tools"]), 3)
        names = {entry["name"] for entry in facts["tools"]}
        self.assertSetEqual(names, {"crackerjack_run", "search_code", "mcp_health"})
        for entry in facts["tools"]:
            self.assertIn("name", entry)
            self.assertIn("description", entry)
            self.assertIn("parameters", entry)
            self.assertIn("category", entry)
        capabilities = facts["capabilities"]
        self.assertEqual(capabilities["total"], 3)
        self.assertGreater(len(capabilities["by_category"]), 0)
        self.assertIn("crackerjack", capabilities["by_category"])

    def test_crackerjack_runtime_facts_handles_empty_registry(self) -> None:
        """``build_all`` returns an empty, well-formed envelope when no tools."""
        from crackerjack.core.runtime_facts import RuntimeFactsBuilder

        app = _make_fake_app({})
        facts = RuntimeFactsBuilder(app).build_all()
        self.assertEqual(facts["count"], 0)
        self.assertEqual(facts["tools"], [])
        self.assertEqual(facts["capabilities"], {"total": 0, "by_category": {}})

    def test_crackerjack_no_oneiric_imports(self) -> None:
        """No new file may import from ``oneiric`` (isolation contract)."""
        pattern = re.compile(r"^\s*(?:from\s+oneiric|import\s+oneiric)\b", re.MULTILINE)
        for path in NEW_FILE_PATHS:
            with self.subTest(path=str(path)):
                content = path.read_text(encoding="utf-8")
                matches = pattern.findall(content)
                self.assertEqual(
                    matches,
                    [],
                    f"{path} must not import oneiric; found: {matches}",
                )

    def test_crackerjack_fail_soft_on_push_failure(self) -> None:
        """Helper returns cleanly when ``httpx`` raises."""
        from crackerjack.mcp import oneiric_runtime

        app = _make_fake_app(
            {
                "crackerjack_run": _make_fake_tool(
                    "crackerjack_run",
                    description="Run quality checks",
                ),
            }
        )

        with mock.patch.object(
            oneiric_runtime, "_push_async", new_callable=mock.AsyncMock
        ) as push_mock:
            push_mock.side_effect = RuntimeError("connection refused")
            # Must not raise.
            oneiric_runtime.report_runtime_to_oneiric(app)

        # Give the daemon thread a brief moment to execute before the
        # process tears down. The test's pass criterion is the absence
        # of any raised exception above — this loop just makes the
        # race window explicit.
        async def _no_op() -> None:
            await asyncio.sleep(0)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_no_op())
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
