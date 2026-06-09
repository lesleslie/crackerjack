"""Tests for the pool_client service.

Covers ``CrackerjackPoolClient`` (the local HTTP-ish stub for talking to
a remote Mahavishnu pool): construction defaults, pool lifecycle
(spawn / list / health / close), tool-scan execution, command building
for supported tools, error and malformed-response handling, and the
``cleanup`` async-context helper.

The MCP transport is a TODO stub in the source — we patch
``_call_mcp_tool`` at the boundary to drive success, error, retry, and
malformed-response scenarios deterministically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.services.pool_client import CrackerjackPoolClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> CrackerjackPoolClient:
    """Return a client with a non-default URL so we can verify it's stored."""
    return CrackerjackPoolClient(
        mcp_server_url="http://example.test:9999/mcp",
        timeout=42,
    )


@pytest.fixture
def ok_call() -> AsyncMock:
    """Return an AsyncMock that behaves like a healthy MCP tool call."""
    return AsyncMock(
        return_value={
            "status": "created",
            "pool_id": "pool-abc",
        }
    )


# ---------------------------------------------------------------------------
# Construction & defaults
# ---------------------------------------------------------------------------


class TestConstruction:
    """Verify the constructor stores its inputs and defaults cleanly."""

    def test_default_url_and_timeout(self) -> None:
        c = CrackerjackPoolClient()
        # Default url contains the literal host string (with the
        # quirky space in the source — pinned here so future cleanup
        # is intentional, not accidental).
        assert "localhost" in c.mcp_server_url
        assert c.timeout == 300

    def test_custom_url_and_timeout(self, client: CrackerjackPoolClient) -> None:
        assert client.mcp_server_url == "http://example.test:9999/mcp"
        assert client.timeout == 42

    def test_initial_state(self, client: CrackerjackPoolClient) -> None:
        assert client.pool_id is None
        # The rich Console is constructed at __init__ time; verify the
        # attribute exists and is not None rather than asserting on
        # private internals.
        assert client.console is not None

    def test_timeout_zero_is_stored_verbatim(self) -> None:
        """``timeout=0`` is a valid (if pathological) value — must be kept."""
        c = CrackerjackPoolClient(timeout=0)
        assert c.timeout == 0


# ---------------------------------------------------------------------------
# spawn_scanner_pool
# ---------------------------------------------------------------------------


class TestSpawnScannerPool:
    """Cover the happy path and the failure path of pool spawning."""

    async def test_spawn_returns_pool_id_and_stores_it(
        self, client: CrackerjackPoolClient
    ) -> None:
        client._call_mcp_tool = AsyncMock(
            return_value={"status": "created", "pool_id": "pool-xyz"}
        )

        pool_id = await client.spawn_scanner_pool(
            min_workers=2,
            max_workers=4,
            pool_type="mahavishnu",
            worker_type="terminal-qwen",
            pool_name="scan",
        )

        assert pool_id == "pool-xyz"
        assert client.pool_id == "pool-xyz"
        client._call_mcp_tool.assert_awaited_once()
        # tool_name is passed positionally; the rest are kwargs.
        args, kwargs = client._call_mcp_tool.await_args
        assert args == ("pool_spawn",)
        assert kwargs["pool_type"] == "mahavishnu"
        assert kwargs["min_workers"] == 2
        assert kwargs["max_workers"] == 4
        assert kwargs["worker_type"] == "terminal-qwen"
        assert kwargs["name"] == "scan"

    async def test_spawn_uses_defaults(self, client: CrackerjackPoolClient) -> None:
        client._call_mcp_tool = AsyncMock(
            return_value={"status": "created", "pool_id": "pool-default"}
        )

        pool_id = await client.spawn_scanner_pool()

        assert pool_id == "pool-default"
        args, kwargs = client._call_mcp_tool.await_args
        assert args == ("pool_spawn",)
        assert kwargs["min_workers"] == 2
        assert kwargs["max_workers"] == 8
        assert kwargs["pool_type"] == "mahavishnu"
        assert kwargs["worker_type"] == "terminal-qwen"
        assert kwargs["name"] == "crackerjack-quality-scanners"

    async def test_spawn_failure_raises_runtime_error(
        self, client: CrackerjackPoolClient
    ) -> None:
        client._call_mcp_tool = AsyncMock(
            return_value={"status": "error", "error": "no quota"}
        )

        with pytest.raises(RuntimeError, match="Failed to spawn pool: no quota"):
            await client.spawn_scanner_pool()

        # Failure must not silently assign a pool_id.
        assert client.pool_id is None

    async def test_spawn_missing_error_field_falls_back_to_unknown(
        self, client: CrackerjackPoolClient
    ) -> None:
        """An error payload without an ``error`` key uses the default text."""
        client._call_mcp_tool = AsyncMock(return_value={"status": "error"})

        with pytest.raises(RuntimeError, match="Failed to spawn pool: Unknown error"):
            await client.spawn_scanner_pool()

    async def test_spawn_unexpected_status_does_not_assign_pool_id(
        self, client: CrackerjackPoolClient
    ) -> None:
        client._call_mcp_tool = AsyncMock(return_value={"status": "pending"})

        with pytest.raises(RuntimeError):
            await client.spawn_scanner_pool()
        assert client.pool_id is None


# ---------------------------------------------------------------------------
# execute_tool_scan
# ---------------------------------------------------------------------------


class TestExecuteToolScan:
    """Cover the tool-scan execution path: guards, command building, and
    parameter forwarding."""

    async def test_execute_requires_pool(
        self, client: CrackerjackPoolClient, tmp_path: Path
    ) -> None:
        target = tmp_path / "mod.py"
        target.write_text("x = 1\n")

        with pytest.raises(RuntimeError, match="Pool not spawned"):
            await client.execute_tool_scan("ruff", [target])

    async def test_execute_forwards_command_and_timeout(
        self, client: CrackerjackPoolClient, tmp_path: Path
    ) -> None:
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        client.pool_id = "pool-1"
        client._call_mcp_tool = AsyncMock(
            return_value={"status": "completed", "exit_code": 0}
        )

        result = await client.execute_tool_scan(
            "ruff", [f1, f2], timeout=120
        )

        assert result == {"status": "completed", "exit_code": 0}
        args, kwargs = client._call_mcp_tool.await_args
        assert args == ("pool_execute",)
        assert kwargs["pool_id"] == "pool-1"
        assert kwargs["timeout"] == 120
        # The prompt embeds the full CLI so the worker can replay it.
        prompt = kwargs["prompt"]
        assert "ruff" in prompt
        assert "check" in prompt
        assert str(f1) in prompt
        assert str(f2) in prompt

    async def test_execute_uses_client_default_timeout(
        self, client: CrackerjackPoolClient, tmp_path: Path
    ) -> None:
        client.pool_id = "pool-1"
        client._call_mcp_tool = AsyncMock(return_value={"ok": True})

        await client.execute_tool_scan("ruff", [tmp_path / "a.py"])

        args, kwargs = client._call_mcp_tool.await_args
        assert args == ("pool_execute",)
        assert kwargs["timeout"] == client.timeout

    async def test_execute_with_empty_file_list(
        self, client: CrackerjackPoolClient
    ) -> None:
        client.pool_id = "pool-1"
        client._call_mcp_tool = AsyncMock(return_value={"ok": True})

        result = await client.execute_tool_scan("ruff", [])

        assert result == {"ok": True}
        # No files means the embedded command is just "ruff check".
        args, kwargs = client._call_mcp_tool.await_args
        assert args == ("pool_execute",)
        assert "ruff check" in kwargs["prompt"]


# ---------------------------------------------------------------------------
# list_pools / get_pool_health / close_pool
# ---------------------------------------------------------------------------


class TestReadOperations:
    """Read-only MCP interactions — list, health, and close lifecycle."""

    async def test_list_pools_returns_payload(
        self, client: CrackerjackPoolClient
    ) -> None:
        client._call_mcp_tool = AsyncMock(
            return_value={
                "pools": [{"pool_id": "p1"}, {"pool_id": "p2"}],
            }
        )

        pools = await client.list_pools()

        assert len(pools) == 2
        assert pools[0]["pool_id"] == "p1"
        client._call_mcp_tool.assert_awaited_once_with("pool_list")

    async def test_list_pools_with_missing_key(
        self, client: CrackerjackPoolClient
    ) -> None:
        """A response without ``pools`` should yield an empty list, not raise."""
        client._call_mcp_tool = AsyncMock(return_value={})

        pools = await client.list_pools()

        assert pools == []

    async def test_get_pool_health_explicit_id(
        self, client: CrackerjackPoolClient
    ) -> None:
        client._call_mcp_tool = AsyncMock(
            return_value={"status": "healthy", "pools_active": 2}
        )

        result = await client.get_pool_health("pool-1")

        assert result["status"] == "healthy"
        client._call_mcp_tool.assert_awaited_once_with(
            "pool_health", pool_id="pool-1"
        )

    async def test_get_pool_health_default(
        self, client: CrackerjackPoolClient
    ) -> None:
        client._call_mcp_tool = AsyncMock(return_value={"status": "degraded"})

        result = await client.get_pool_health()

        assert result["status"] == "degraded"
        # No pool_id forwarded when none supplied.
        client._call_mcp_tool.assert_awaited_once_with("pool_health")


class TestClosePool:
    """close_pool + cleanup lifecycle."""

    async def test_close_specific_pool_clears_pool_id(
        self, client: CrackerjackPoolClient
    ) -> None:
        client.pool_id = "pool-1"
        client._call_mcp_tool = AsyncMock(return_value={"status": "closed"})

        await client.close_pool("pool-1")

        assert client.pool_id is None
        client._call_mcp_tool.assert_awaited_once_with(
            "pool_close", pool_id="pool-1"
        )

    async def test_close_default_uses_close_all(
        self, client: CrackerjackPoolClient
    ) -> None:
        client.pool_id = "pool-1"
        client._call_mcp_tool = AsyncMock(return_value={"status": "closed"})

        await client.close_pool()

        # pool_id is preserved when the explicit id path is *not* taken.
        assert client.pool_id == "pool-1"
        client._call_mcp_tool.assert_awaited_once_with("pool_close_all")

    async def test_close_non_closed_status_is_silent(
        self, client: CrackerjackPoolClient
    ) -> None:
        """A non-'closed' status must not raise — the operation is fire-and-forget."""
        client.pool_id = "pool-1"
        client._call_mcp_tool = AsyncMock(
            return_value={"status": "already_closed"}
        )

        # No exception expected.
        await client.close_pool("pool-1")
        # pool_id is NOT cleared when the status check fails.
        assert client.pool_id == "pool-1"

    async def test_cleanup_skips_when_no_pool(
        self, client: CrackerjackPoolClient
    ) -> None:
        client._call_mcp_tool = AsyncMock(return_value={"status": "closed"})

        await client.cleanup()

        client._call_mcp_tool.assert_not_called()

    async def test_cleanup_invokes_close_when_pool_active(
        self, client: CrackerjackPoolClient
    ) -> None:
        client.pool_id = "pool-1"
        client._call_mcp_tool = AsyncMock(return_value={"status": "closed"})

        await client.cleanup()

        # ``cleanup`` delegates to ``close_pool()`` (no arg) which uses
        # ``pool_close_all`` and intentionally does NOT clear
        # ``self.pool_id`` — only the explicit-id branch does. Pin that
        # current behaviour so a future cleanup refactor is intentional.
        client._call_mcp_tool.assert_awaited_once()
        args, kwargs = client._call_mcp_tool.await_args
        assert args == ("pool_close_all",)


# ---------------------------------------------------------------------------
# _build_tool_command
# ---------------------------------------------------------------------------


class TestBuildToolCommand:
    """The static command builder — one assertion per supported tool plus
    the unknown-tool fallback."""

    def test_supported_tools(self, tmp_path: Path) -> None:
        f = tmp_path / "x.py"
        # Each entry: (tool_name, expected_substrings)
        cases: list[tuple[str, list[str]]] = [
            ("refurb", ["refurb"]),
            ("complexipy", ["complexipy", "--path", "."]),
            ("skylos", ["skylos"]),
            ("vulture", ["vulture"]),
            ("ruff", ["ruff", "check"]),
            ("mypy", ["mypy"]),
            ("pylint", ["pylint"]),
            ("semgrep", ["semgrep", "--config", "auto"]),
            ("bandit", ["bandit", "-r"]),
        ]
        for tool, expected in cases:
            cmd = CrackerjackPoolClient()._build_tool_command(tool, [f])
            assert cmd, f"{tool} produced empty command"
            for needle in expected:
                assert needle in cmd, f"{needle} missing from {cmd}"
            assert str(f) in cmd

    def test_unknown_tool_returns_empty_list(
        self, tmp_path: Path
    ) -> None:
        cmd = CrackerjackPoolClient()._build_tool_command(
            "not-a-real-tool", [tmp_path / "x.py"]
        )
        assert cmd == []


# ---------------------------------------------------------------------------
# _call_mcp_tool — boundary stub
# ---------------------------------------------------------------------------


class TestCallMcpTool:
    """Drive the underlying stub directly. The source is a TODO
    implementation; this guards its observable contract so that any
    future JSON-RPC transport must remain backwards-compatible."""

    async def test_known_tools_return_mock_responses(
        self, client: CrackerjackPoolClient
    ) -> None:
        cases: dict[str, dict[str, Any]] = {
            "pool_spawn": {"status": "created", "pool_id": "test-pool-123"},
            "pool_execute": {
                "status": "completed",
                "output": "Mock execution output",
                "exit_code": 0,
            },
            "pool_list": {
                "pools": [
                    {
                        "pool_id": "test-pool-123",
                        "name": "test-pool",
                        "pool_type": "mahavishnu",
                        "workers": 8,
                    }
                ]
            },
            "pool_health": {"status": "healthy", "pools_active": 1},
            "pool_close": {"status": "closed"},
            "pool_close_all": {"status": "closed"},
        }
        for tool, expected in cases.items():
            result = await client._call_mcp_tool(tool)
            assert result == expected, f"{tool} returned {result}"

    async def test_unknown_tool_returns_error_envelope(
        self, client: CrackerjackPoolClient
    ) -> None:
        result = await client._call_mcp_tool("not_a_real_tool")
        assert result["status"] == "error"
        assert "Unknown tool" in result["error"]


# ---------------------------------------------------------------------------
# Retry / timeout / malformed-response — driven through the boundary
# ---------------------------------------------------------------------------


class TestResilience:
    """These tests don't change the source's behavior — they pin the
    *contract* callers can rely on. If the TODO transport is ever
    replaced, these describe what the new implementation should do."""

    async def test_transient_failure_is_propagated(
        self, client: CrackerjackPoolClient
    ) -> None:
        """The client does not silently swallow transport errors."""
        client._call_mcp_tool = AsyncMock(
            side_effect=ConnectionError("connection refused")
        )

        with pytest.raises(ConnectionError, match="connection refused"):
            await client.list_pools()

    async def test_timeout_is_propagated(
        self, client: CrackerjackPoolClient
    ) -> None:
        client._call_mcp_tool = AsyncMock(
            side_effect=TimeoutError("upstream timeout")
        )

        with pytest.raises(TimeoutError, match="upstream timeout"):
            await client.list_pools()

    async def test_malformed_response_is_propagated_as_is(
        self, client: CrackerjackPoolClient
    ) -> None:
        """When the server returns a non-dict (e.g. ``None`` or a bare
        string), the client should raise a ``TypeError`` from the
        ``.get`` access in the source. This pins that contract so a
        future transport change cannot silently regress to ``None``."""
        client._call_mcp_tool = AsyncMock(return_value=None)

        with pytest.raises(AttributeError):
            await client.list_pools()

    async def test_repeated_calls_use_independent_results(
        self, client: CrackerjackPoolClient
    ) -> None:
        """A retry loop can call the same tool twice and get two results."""
        responses = iter(
            [
                {"status": "created", "pool_id": "p1"},
                {"status": "closed"},
            ]
        )
        client._call_mcp_tool = AsyncMock(side_effect=lambda *_a, **_kw: next(responses))

        first = await client.spawn_scanner_pool()
        client.pool_id = first  # simulate the spawn having succeeded
        await client.close_pool(first)

        assert first == "p1"
        assert client._call_mcp_tool.await_count == 2

    async def test_console_output_does_not_raise(
        self, client: CrackerjackPoolClient
    ) -> None:
        """The rich Console must not raise even if it has no live terminal."""
        client._call_mcp_tool = AsyncMock(
            return_value={"status": "created", "pool_id": "p1"}
        )

        # No assertion on output — just that the call returns cleanly.
        pool_id = await client.spawn_scanner_pool()
        assert pool_id == "p1"


# ---------------------------------------------------------------------------
# Module-level smoke
# ---------------------------------------------------------------------------


class TestModuleSurface:
    """Confirm the public surface exposed by the module is unchanged."""

    def test_module_exposes_client_class(self) -> None:
        from crackerjack.services import pool_client

        assert hasattr(pool_client, "CrackerjackPoolClient")
        assert isinstance(pool_client.CrackerjackPoolClient, type)
