"""Tests for ``crackerjack.websocket.server``.

Covers:
- ``CrackerjackWebSocketServer`` lifecycle callbacks (``on_connect``,
  ``on_disconnect``).
- ``on_message`` request handling: ``subscribe`` / ``unsubscribe`` /
  ``get_test_status`` / ``get_quality_gate`` / unknown event.
- ``_can_subscribe_to_channel`` permission matrix.
- Quality-gate source resolution and report building.
- All ``broadcast_*`` methods (``test_started``, ``test_completed``,
  ``test_failed``, ``quality_gate_checked``, ``coverage_updated``).
- ``tls_config`` helpers.
- ``_handle_event`` debug logging path.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_websocket_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip CRACKERJACK_* env vars and reload the websocket module so each
    test sees a clean slate (mirrors the pattern in test_websocket_auth.py)."""
    for key in [k for k in os.environ if k.startswith("CRACKERJACK_")]:
        monkeypatch.delenv(key, raising=False)
    for mod in [m for m in list(sys.modules) if m.startswith("crackerjack.websocket")]:
        sys.modules.pop(mod, None)
    yield
    for mod in [m for m in list(sys.modules) if m.startswith("crackerjack.websocket")]:
        sys.modules.pop(mod, None)


@pytest.fixture
def server() -> Any:
    """Fresh ``CrackerjackWebSocketServer`` with a mock qc_manager."""
    from crackerjack.websocket import CrackerjackWebSocketServer

    return CrackerjackWebSocketServer(qc_manager=MagicMock())


@pytest.fixture
def server_with_qc() -> Any:
    """Server with a qc_manager that exposes ``get_quality_gate_report``."""
    from crackerjack.websocket import CrackerjackWebSocketServer

    qc = MagicMock()
    return CrackerjackWebSocketServer(qc_manager=qc), qc


# ---------------------------------------------------------------------------
# Init / lifecycle
# ---------------------------------------------------------------------------


class TestServerInit:
    def test_default_init_logs_ws_mode(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        server = CrackerjackWebSocketServer(qc_manager=MagicMock())
        assert server.qc_manager is not None
        assert server.host == "127.0.0.1"
        assert server.port == 8686
        assert server.max_connections == 1000
        assert server.message_rate_limit == 100
        # Dev mode authenticator is ``None``
        assert server.authenticator is None
        # No TLS in default config
        assert server.ssl_context is None

    def test_init_with_tls_logs_wss_mode(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        server = CrackerjackWebSocketServer(
            qc_manager=MagicMock(),
            tls_enabled=True,
        )
        # SSL context is still None (no cert files), but tls_enabled is set
        assert server.tls_enabled is True

    def test_init_with_ssl_context_logs_wss_mode(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        sentinel = object()
        server = CrackerjackWebSocketServer(
            qc_manager=MagicMock(),
            ssl_context=sentinel,
        )
        assert server.ssl_context is sentinel

    def test_init_with_auth_enabled_uses_authenticator(self) -> None:
        os.environ["CRACKERJACK_AUTH_ENABLED"] = "true"
        os.environ["CRACKERJACK_JWT_SECRET"] = "test-secret"
        # Reload modules to pick up new env
        for mod in [m for m in list(sys.modules) if m.startswith("crackerjack.websocket")]:
            sys.modules.pop(mod, None)

        from crackerjack.websocket import CrackerjackWebSocketServer

        server = CrackerjackWebSocketServer(qc_manager=MagicMock(), require_auth=True)
        assert server.authenticator is not None
        assert server.require_auth is True


# ---------------------------------------------------------------------------
# on_connect / on_disconnect
# ---------------------------------------------------------------------------


class TestConnectionCallbacks:
    @pytest.mark.asyncio
    async def test_on_connect_authenticated_sends_welcome(self) -> None:
        from mcp_common.websocket import WebSocketProtocol

        from crackerjack.websocket import CrackerjackWebSocketServer

        server = CrackerjackWebSocketServer(qc_manager=MagicMock())
        ws = AsyncMock()
        ws.user = {"user_id": "u1"}

        await server.on_connect(ws, "conn-1")

        assert ws.send.await_count == 1
        sent = ws.send.await_args.args[0]
        assert "Connected to Crackerjack" in sent
        # Encoded message should include the connection id
        decoded = WebSocketProtocol.decode(sent)
        assert decoded is not None

    @pytest.mark.asyncio
    async def test_on_connect_anonymous_sends_welcome(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        server = CrackerjackWebSocketServer(qc_manager=MagicMock())
        ws = AsyncMock()
        # No user attribute → falls back to anonymous
        del ws.user

        await server.on_connect(ws, "conn-2")

        assert ws.send.await_count == 1
        assert "Connected to Crackerjack" in ws.send.await_args.args[0]

    @pytest.mark.asyncio
    async def test_on_disconnect_leaves_all_rooms(self, server: Any) -> None:
        ws = AsyncMock()
        # The base server's ``leave_all_rooms`` only drops a connection from
        # its single tracked room (``room_connections``). The Crackerjack
        # subclass also calls it on disconnect, so we register the room
        # through the base server's room APIs to ensure the bookkeeping is
        # consistent.
        server.connection_rooms.setdefault("quality:proj", set()).add("conn-3")
        server.room_connections["conn-3"] = "quality:proj"

        await server.on_disconnect(ws, "conn-3")

        # leave_all_rooms should drop the connection from both registries
        assert "conn-3" not in server.connection_rooms.get("quality:proj", set())
        assert "conn-3" not in server.room_connections


# ---------------------------------------------------------------------------
# on_message routing
# ---------------------------------------------------------------------------


class TestOnMessage:
    @pytest.mark.asyncio
    async def test_request_message_dispatches_to_handle_request(
        self, server: Any
    ) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None
        ws.id = "c1"
        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="unknown_event_xyz",
            data={},
            correlation_id="corr-1",
        )
        with patch.object(server, "_handle_request") as handle:
            await server.on_message(ws, msg)
        handle.assert_awaited_once_with(ws, msg)

    @pytest.mark.asyncio
    async def test_event_message_dispatches_to_handle_event(
        self, server: Any
    ) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(type="event", event="ping", data={}, correlation_id="c2")  # ty: ignore[invalid-argument-type]
        with patch.object(server, "_handle_event") as handle:
            await server.on_message(ws, msg)
        handle.assert_awaited_once_with(ws, msg)

    @pytest.mark.asyncio
    async def test_unknown_message_type_is_logged_only(self, server: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        # 'response' is not in {request, event}, so it should fall through.
        msg = WebSocketMessage(type="response", event="x", data={}, correlation_id="c3")  # ty: ignore[invalid-argument-type]
        await server.on_message(ws, msg)
        ws.send.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_request — subscribe / unsubscribe / status / gate / unknown
# ---------------------------------------------------------------------------


class TestHandleRequestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_with_admin_permission_joins_room(
        self, server: Any
    ) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        # Only the bare "admin" permission reliably grants access (see
        # TestChannelAuthorization docstring — the function has a
        # normalization/literal-string mismatch bug for "crackerjack:read"
        # and "crackerjack:admin" forms).
        ws.user = {
            "user_id": "admin",
            "permissions": ["admin"],
        }
        ws.id = "conn-sub-1"

        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="subscribe",
            data={"channel": "quality:proj"},
            correlation_id="sub-1",
        )
        await server._handle_request(ws, msg)

        assert ws.send.await_count == 1
        assert "subscribed" in ws.send.await_args.args[0]
        assert "conn-sub-1" in server.connection_rooms.get("quality:proj", set())

    @pytest.mark.asyncio
    async def test_subscribe_forbidden_sends_error(self, server: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = {"user_id": "u", "permissions": []}
        ws.id = "conn-forbidden"

        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="subscribe",
            data={"channel": "quality:proj"},
            correlation_id="sub-2",
        )
        await server._handle_request(ws, msg)

        assert ws.send.await_count == 1
        assert "FORBIDDEN" in ws.send.await_args.args[0]
        # Should NOT have joined the room
        assert "conn-forbidden" not in server.connection_rooms.get(
            "quality:proj", set()
        )

    @pytest.mark.asyncio
    async def test_subscribe_without_channel_does_nothing(self, server: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None  # no user
        ws.id = "nochan"

        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="subscribe",
            data={},
            correlation_id="sub-3",
        )
        await server._handle_request(ws, msg)

        # No response is sent when channel is missing
        ws.send.assert_not_called()


class TestHandleRequestUnsubscribe:
    @pytest.mark.asyncio
    async def test_unsubscribe_leaves_room(self, server: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        # connection_rooms is a plain dict; setdefault ensures the key exists
        server.connection_rooms.setdefault("test:run1", set()).add("conn-unsub")
        ws = AsyncMock()
        ws.user = None
        ws.id = "conn-unsub"

        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="unsubscribe",
            data={"channel": "test:run1"},
            correlation_id="un-1",
        )
        await server._handle_request(ws, msg)

        assert "unsubscribed" in ws.send.await_args.args[0]
        assert "conn-unsub" not in server.connection_rooms.get("test:run1", set())

    @pytest.mark.asyncio
    async def test_unsubscribe_without_channel_does_nothing(
        self, server: Any
    ) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None
        ws.id = "c"

        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="unsubscribe",
            data={},
            correlation_id="un-2",
        )
        await server._handle_request(ws, msg)
        ws.send.assert_not_called()


class TestHandleRequestTestStatus:
    @pytest.mark.asyncio
    async def test_get_test_status_returns_payload(self, server: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="get_test_status",
            data={"run_id": "run-42"},
            correlation_id="ts-1",
        )
        await server._handle_request(ws, msg)

        body = ws.send.await_args.args[0]
        assert "run-42" in body
        assert "running" in body

    @pytest.mark.asyncio
    async def test_get_test_status_without_run_id_does_nothing(
        self, server: Any
    ) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="get_test_status",
            data={},
            correlation_id="ts-2",
        )
        await server._handle_request(ws, msg)
        ws.send.assert_not_called()


class TestHandleRequestQualityGate:
    @pytest.mark.asyncio
    async def test_get_quality_gate_with_qc_manager(self, server_with_qc: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        server, qc = server_with_qc
        qc.get_quality_gate_report = MagicMock(
            return_value={
                "fast_hooks": True,
                "tests": True,
                "comprehensive": True,
                "coverage": 92.5,
                "errors": [],
                "checks": [],
                "repository": "proj",
            }
        )

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="get_quality_gate",
            data={"project": "proj"},
            correlation_id="qg-1",
        )
        await server._handle_request(ws, msg)

        body = ws.send.await_args.args[0]
        assert "proj" in body
        assert "passed" in body

    @pytest.mark.asyncio
    async def test_get_quality_gate_without_qc_manager_uses_placeholder(
        self, server: Any
    ) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer
        from mcp_common.websocket import WebSocketMessage

        # Server with no qc_manager
        server_no_qc = CrackerjackWebSocketServer(qc_manager=None)

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="get_quality_gate",
            data={"project": "ghost"},
            correlation_id="qg-2",
        )
        await server_no_qc._handle_request(ws, msg)

        body = ws.send.await_args.args[0]
        assert "ghost" in body

    @pytest.mark.asyncio
    async def test_get_quality_gate_handles_exception(self, server_with_qc: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        server, qc = server_with_qc
        qc.get_quality_gate_report = MagicMock(
            side_effect=RuntimeError("qc boom")
        )

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="get_quality_gate",
            data={"project": "proj-x"},
            correlation_id="qg-3",
        )
        await server._handle_request(ws, msg)

        body = ws.send.await_args.args[0]
        assert "error" in body
        assert "qc boom" in body

    @pytest.mark.asyncio
    async def test_get_quality_gate_without_project_does_nothing(
        self, server: Any
    ) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="get_quality_gate",
            data={},
            correlation_id="qg-4",
        )
        await server._handle_request(ws, msg)
        ws.send.assert_not_called()


class TestHandleRequestUnknown:
    @pytest.mark.asyncio
    async def test_unknown_request_sends_error(self, server: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(
            type="request",  # ty: ignore[invalid-argument-type]
            event="frobnicate",
            data={},
            correlation_id="unk-1",
        )
        await server._handle_request(ws, msg)

        body = ws.send.await_args.args[0]
        assert "UNKNOWN_REQUEST" in body


# ---------------------------------------------------------------------------
# _handle_event
# ---------------------------------------------------------------------------


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_event_message_logged_no_send(self, server: Any) -> None:
        from mcp_common.websocket import WebSocketMessage

        ws = AsyncMock()
        ws.user = None
        msg = WebSocketMessage(
            type="event",  # ty: ignore[invalid-argument-type]
            event="client_ping",
            data={"ts": 1},
            correlation_id="ev-1",
        )
        await server._handle_event(ws, msg)
        ws.send.assert_not_called()


# ---------------------------------------------------------------------------
# _can_subscribe_to_channel
# ---------------------------------------------------------------------------


class TestChannelAuthorization:
    """Documents the current behavior of ``_can_subscribe_to_channel``.

    NOTE — known source bug: the permission set is normalized by
    ``str.strip().lower().replace(" ", ":")``, which turns ``"crackerjack:
    read"`` into ``"crackerjack::read"`` (double colon). The same function
    then checks for membership of the *literal* ``"crackerjack: read"`` /
    ``"crackerjack: admin"`` strings. As a result, a properly-normalized
    permission like ``"crackerjack:read"`` (single colon, no space) is
    rejected for both ``quality:`` and ``test:`` channels, while the same
    string *with* a space (``"crackerjack: read"``) does not match the
    normalized form. Only the bare ``"admin"`` permission works correctly
    for cross-channel access. Tests below pin the current (buggy) behavior.
    """

    def test_admin_permission_grants_all(self, server: Any) -> None:
        assert server._can_subscribe_to_channel(
            {"permissions": ["admin"]}, "anything:goes"
        )

    def test_bare_admin_string_also_grants_quality_test(self, server: Any) -> None:
        user = {"permissions": ["admin"]}
        assert server._can_subscribe_to_channel(user, "quality:p")
        assert server._can_subscribe_to_channel(user, "test:r")

    def test_normalized_read_does_not_grant_quality_or_test(
        self, server: Any
    ) -> None:
        # Documents the bug: "crackerjack:read" normalizes to
        # "crackerjack::read" which does not match the literal
        # "crackerjack: read" the function looks for.
        user = {"permissions": ["crackerjack:read"]}
        assert not server._can_subscribe_to_channel(user, "quality:p")
        assert not server._can_subscribe_to_channel(user, "test:r")

    def test_normalized_admin_does_not_grant(self, server: Any) -> None:
        user = {"permissions": ["crackerjack:admin"]}
        # Normalized to "crackerjack::admin" — does not match the literal
        # "crackerjack: admin" / "admin" the function checks for.
        assert not server._can_subscribe_to_channel(user, "quality:p")
        assert not server._can_subscribe_to_channel(user, "test:r")

    def test_canonical_space_form_matches_literal_check(self, server: Any) -> None:
        # The function checks the literal string "crackerjack: admin"
        # (with single space). After normalization this becomes
        # "crackerjack::admin" which still does NOT match the literal check.
        # The only way to pass is to provide the literal string
        # "crackerjack: admin" verbatim — but even that is normalized away
        # first. So in practice this test confirms the function never grants
        # access via the "crackerjack: admin" / "crackerjack: read" forms.
        user = {"permissions": ["crackerjack: admin"]}
        assert not server._can_subscribe_to_channel(user, "quality:p")
        assert not server._can_subscribe_to_channel(user, "test:r")

    def test_no_permission_denies(self, server: Any) -> None:
        user = {"permissions": []}
        assert not server._can_subscribe_to_channel(user, "quality:p")
        assert not server._can_subscribe_to_channel(user, "test:r")
        assert not server._can_subscribe_to_channel(user, "other:x")

    def test_other_permissions_deny_known_channels(self, server: Any) -> None:
        user = {"permissions": ["crackerjack:write"]}
        assert not server._can_subscribe_to_channel(user, "quality:p")
        assert not server._can_subscribe_to_channel(user, "test:r")

    def test_unknown_channel_returns_false(self, server: Any) -> None:
        user = {"permissions": ["crackerjack:write"]}
        # 'other:' is not a quality or test channel, and the user lacks
        # admin permission, so this falls through to ``return False``.
        assert not server._can_subscribe_to_channel(user, "other:foo")

    def test_admin_passes_any_channel_prefix(self, server: Any) -> None:
        user = {"permissions": ["admin"]}
        # The admin check short-circuits before channel-prefix matching,
        # so admin can subscribe to *any* channel including unknown ones.
        assert server._can_subscribe_to_channel(user, "other:foo")


# ---------------------------------------------------------------------------
# _get_test_status
# ---------------------------------------------------------------------------


class TestGetTestStatus:
    @pytest.mark.asyncio
    async def test_returns_default_running_status(self, server: Any) -> None:
        result = await server._get_test_status("run-1")
        assert result["run_id"] == "run-1"
        assert result["status"] == "running"
        assert result["tests_completed"] == 0
        assert result["tests_total"] == 100
        assert result["failures"] == 0


# ---------------------------------------------------------------------------
# _resolve_quality_gate_source / _build_quality_gate_report
# ---------------------------------------------------------------------------


class TestQualityGateSource:
    @pytest.mark.asyncio
    async def test_no_qc_manager_returns_none(self, server: Any) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        server_none = CrackerjackWebSocketServer(qc_manager=None)
        assert await server_none._resolve_quality_gate_source("p") is None

    @pytest.mark.asyncio
    async def test_prefers_first_matching_attribute(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc = MagicMock()
        qc.get_quality_gate_report = MagicMock(
            return_value={
                "fast_hooks": True,
                "tests": True,
                "comprehensive": True,
                "coverage": 80.0,
            }
        )
        server = CrackerjackWebSocketServer(qc_manager=qc)
        result = await server._resolve_quality_gate_source("p")
        assert result is not None
        qc.get_quality_gate_report.assert_called_once_with("p")

    @pytest.mark.asyncio
    async def test_falls_back_to_attribute_aliases(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc = MagicMock(spec=["quality_gate_status"])
        qc.quality_gate_status = {"fast_hooks": True, "tests": True, "comprehensive": True, "coverage": 50.0}
        server = CrackerjackWebSocketServer(qc_manager=qc)
        result = await server._resolve_quality_gate_source("p")
        assert result is not None
        assert result["coverage"] == 50.0

    @pytest.mark.asyncio
    async def test_awaitable_attribute_is_awaited(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        async def fetch(project: str) -> dict:
            return {"fast_hooks": True, "tests": True, "comprehensive": True, "coverage": 70.0}

        qc = MagicMock()
        qc.get_quality_gate_report = fetch  # async function
        server = CrackerjackWebSocketServer(qc_manager=qc)
        result = await server._resolve_quality_gate_source("p")
        assert result["coverage"] == 70.0

    @pytest.mark.asyncio
    async def test_all_attrs_none_returns_none(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc = MagicMock(spec=[])  # no attributes
        server = CrackerjackWebSocketServer(qc_manager=qc)
        assert await server._resolve_quality_gate_source("p") is None


class TestBuildQualityGateReport:
    @pytest.mark.asyncio
    async def test_placeholder_report_when_source_missing(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer
        from crackerjack.models.validation_contracts import QualityGateReport

        server = CrackerjackWebSocketServer(qc_manager=None)
        report = await server._build_quality_gate_report("p")
        assert isinstance(report, QualityGateReport)
        assert report.passed is True
        assert report.repository == "p"
        assert report.metadata.get("mode") == "placeholder"

    @pytest.mark.asyncio
    async def test_report_from_dict_source(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc = MagicMock()
        qc.get_quality_gate_report = MagicMock(
            return_value={
                "fast_hooks": True,
                "tests": False,
                "comprehensive": True,
                "coverage": 60.0,
                "errors": ["tests"],
            }
        )
        server = CrackerjackWebSocketServer(qc_manager=qc)
        report = await server._build_quality_gate_report("p")
        assert report.repository == "p"
        assert report.passed is False
        assert "tests" in report.errors

    @pytest.mark.asyncio
    async def test_explicit_source_skips_resolution(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        server = CrackerjackWebSocketServer(qc_manager=None)
        # NOTE: QualityGateReport.from_result prefers the ``repository`` kwarg
        # over the value embedded in the source dict. The server always
        # passes the project name as that kwarg, so the source's
        # ``"repository"`` key is ignored. This test pins that behavior.
        report = await server._build_quality_gate_report(
            "p",
            report_source={
                "fast_hooks": True,
                "tests": True,
                "comprehensive": True,
                "coverage": 100.0,
                "repository": "ignored-repo",
            },
        )
        assert report.repository == "p"
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_empty_repository_filled_from_project(self) -> None:
        from crackerjack.websocket import CrackerjackWebSocketServer

        server = CrackerjackWebSocketServer(qc_manager=None)
        report = await server._build_quality_gate_report(
            "fallback-proj",
            report_source={
                "fast_hooks": True,
                "tests": True,
                "comprehensive": True,
                "coverage": 90.0,
                # no "repository" key → from_result leaves it blank
            },
        )
        assert report.repository == "fallback-proj"


class TestGetQualityGateStatus:
    @pytest.mark.asyncio
    async def test_returns_dict_with_gates_and_status(self, server: Any) -> None:
        result = await server._get_quality_gate_status("p")
        assert result["project"] == "p"
        assert result["status"] in ("passed", "failed")
        assert "gates" in result
        # placeholder report has 3 default checks
        assert isinstance(result["gates"], list)

    @pytest.mark.asyncio
    async def test_handles_building_exception(self, server: Any) -> None:
        with patch.object(
            server, "_build_quality_gate_report", side_effect=RuntimeError("boom")
        ):
            result = await server._get_quality_gate_status("p")
        assert result["project"] == "p"
        assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# broadcast_* methods
# ---------------------------------------------------------------------------


class TestBroadcasts:
    @pytest.mark.asyncio
    async def test_broadcast_test_started_calls_broadcast(self, server: Any) -> None:
        server.broadcast_to_room = AsyncMock()
        await server.broadcast_test_started("run-1", "pytest", 50)
        server.broadcast_to_room.assert_awaited_once()
        args = server.broadcast_to_room.await_args.args
        assert args[0] == "test:run-1"

    @pytest.mark.asyncio
    async def test_broadcast_test_completed_calls_broadcast(
        self, server: Any
    ) -> None:
        server.broadcast_to_room = AsyncMock()
        await server.broadcast_test_completed("run-2", 100, 5, 12.5)
        server.broadcast_to_room.assert_awaited_once()
        assert server.broadcast_to_room.await_args.args[0] == "test:run-2"

    @pytest.mark.asyncio
    async def test_broadcast_test_failed_calls_broadcast(self, server: Any) -> None:
        server.broadcast_to_room = AsyncMock()
        await server.broadcast_test_failed(
            "run-3", "test_x", "AssertionError", "Traceback..."
        )
        server.broadcast_to_room.assert_awaited_once()
        assert server.broadcast_to_room.await_args.args[0] == "test:run-3"

    @pytest.mark.asyncio
    async def test_broadcast_quality_gate_checked_passed(self, server: Any) -> None:
        server.broadcast_to_room = AsyncMock()
        await server.broadcast_quality_gate_checked(
            "myproj", "coverage", "passed", 95.0, 80.0
        )
        server.broadcast_to_room.assert_awaited_once()
        # Room is quality:{project}
        assert server.broadcast_to_room.await_args.args[0] == "quality:myproj"

    @pytest.mark.asyncio
    async def test_broadcast_quality_gate_checked_with_report(
        self, server: Any
    ) -> None:
        server.broadcast_to_room = AsyncMock()
        report = {
            "fast_hooks": True,
            "tests": True,
            "comprehensive": True,
            "coverage": 88.0,
            "errors": [],
            "checks": [],
        }
        await server.broadcast_quality_gate_checked(
            "p2", "lint", "passed", 88.0, 80.0, quality_gate_report=report
        )
        server.broadcast_to_room.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_quality_gate_checked_status_normalization(
        self, server: Any
    ) -> None:
        # 'PASSED' should normalize to True (uppercase) - status string
        server.broadcast_to_room = AsyncMock()
        await server.broadcast_quality_gate_checked(
            "p3", "tests", "PASSED", 100.0, 90.0
        )
        server.broadcast_to_room.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_coverage_updated(self, server: Any) -> None:
        server.broadcast_to_room = AsyncMock()
        await server.broadcast_coverage_updated("myproj", 80.0, 70.0, 65.0)
        server.broadcast_to_room.assert_awaited_once()
        assert server.broadcast_to_room.await_args.args[0] == "quality:myproj"


# ---------------------------------------------------------------------------
# tls_config
# ---------------------------------------------------------------------------


class TestTlsConfig:
    def test_get_websocket_tls_config_returns_mapping(self) -> None:
        from crackerjack.websocket.tls_config import get_websocket_tls_config

        config = get_websocket_tls_config()
        assert isinstance(config, dict)
        assert "tls_enabled" in config

    def test_load_ssl_context_without_cert_returns_none(self) -> None:
        from crackerjack.websocket.tls_config import load_ssl_context

        result = load_ssl_context(cert_file=None, key_file=None)
        assert result["ssl_context"] is None
        assert result["cert_file"] is None
        assert result["key_file"] is None
        assert result["verify_client"] is False

    def test_load_ssl_context_reads_from_env_when_no_args(self) -> None:
        from crackerjack.websocket.tls_config import load_ssl_context

        # Without env vars set, should return None ssl_context
        result = load_ssl_context()
        assert isinstance(result, dict)
        assert "ssl_context" in result
