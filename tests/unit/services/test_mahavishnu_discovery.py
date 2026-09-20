"""Unit tests for ``crackerjack.services.mahavishnu_discovery``.

The Mahavishnu MCP probe is the layered fallback that asks Mahavishnu
for the publish URL of the current cwd. These tests pin the contract:
soft fallback on every failure mode, correct request shape, correct
response parsing.

Test seam: tests patch ``mahavishnu_discovery._http_post`` directly.
We avoid respx because respx is pinned to upstream ``httpx`` and this
project uses ``httpx2`` (a fork); respx's ``isinstance(httpx.Response)``
check rejects ``httpx2.Response`` instances.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import httpx2 as httpx
import pytest

from crackerjack.services.mahavishnu_discovery import (
    DEFAULT_MAHAVISHNU_MCP_URL,
    ENV_VAR_URL_OVERRIDE,
    PROBE_TIMEOUT_SECONDS,
    PROBE_TOOL_NAME,
    _http_post,
    _mcp_endpoint_url,
    _parse_mcp_response,
    _post_mcp,
    probe_publish_url,
)


def _fake_response(
    *,
    status_code: int = 200,
    json_payload: dict | None = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a minimal httpx2.Response-shaped stub for the test seam.

    The seam ``_post_mcp`` (and the lower-level ``_http_post``) is
    patched with this; tests assert on the request the seam received
    and the response the seam returned.

    ``headers`` carries the FastMCP ``mcp-session-id`` set on the
    ``initialize`` response so the probe can echo it on subsequent
    calls. Defaults to an empty mapping.
    """
    payload = json_payload if json_payload is not None else None
    text_value = text if text is not None else (
        json.dumps(payload) if payload is not None else ""
    )

    def _raise_for_status() -> None:
        if status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{status_code} error",
                request=httpx.Request("POST", DEFAULT_MAHAVISHNU_MCP_URL),
                response=SimpleNamespace(status_code=status_code),
            )

    return SimpleNamespace(
        status_code=status_code,
        text=text_value,
        headers=headers or {},
        raise_for_status=_raise_for_status,
        json=lambda: (json.loads(text_value) if text_value else None),
    )


def _handshake_responses(
    call_response: SimpleNamespace,
    session_id: str = "test-session-123",
) -> list[SimpleNamespace]:
    """Build the 3-call handshake response sequence for ``_post_mcp``.

    Order matches the probe:

      1. ``initialize`` — carries the ``mcp-session-id`` response header
      2. ``notifications/initialized`` — empty 202 (FastMCP convention)
      3. ``tools/call`` — caller-supplied response (use ``call_response``)
    """
    init_response = _fake_response(
        json_payload={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": "test-server", "version": "0.0.0"},
            },
        },
        headers={"mcp-session-id": session_id},
    )
    notif_response = _fake_response(status_code=202, text="")
    return [init_response, notif_response, call_response]


class TestEndpointUrl:
    def test_default_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_VAR_URL_OVERRIDE, raising=False)
        assert _mcp_endpoint_url() == DEFAULT_MAHAVISHNU_MCP_URL

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_VAR_URL_OVERRIDE, "http://example.test:9000")
        assert _mcp_endpoint_url() == "http://example.test:9000/mcp"

    def test_env_var_with_trailing_mcp_path_is_preserved(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(ENV_VAR_URL_OVERRIDE, "http://example.test:9000/mcp")
        assert _mcp_endpoint_url() == "http://example.test:9000/mcp"

    def test_env_var_with_trailing_slash_normalized(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(ENV_VAR_URL_OVERRIDE, "http://example.test:9000/")
        assert _mcp_endpoint_url() == "http://example.test:9000/mcp"


class TestParseMcpResponse:
    """Pin the response parser so a Mahavishnu content-type change
    doesn't silently break crackerjack's URL discovery.
    """

    def test_text_content_shape(self) -> None:
        """Standard MCP ``tools/call`` response with a URL in content[0].text."""
        url = "https://gitlab.com/api/v4/projects/123/packages/pypi/upload"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": url}],
                "isError": False,
            },
        }
        assert _parse_mcp_response(payload) == url

    def test_structured_result_shape(self) -> None:
        """If Mahavishnu returns the URL directly as a string result."""
        url = "https://gitlab.com/api/v4/projects/123/packages/pypi/upload"
        payload = {"jsonrpc": "2.0", "id": 1, "result": url}
        assert _parse_mcp_response(payload) == url

    def test_fastmcp_structured_content_shape(self) -> None:
        """FastMCP 3.x default for ``str`` tool returns: the URL lands in
        ``structuredContent.result`` and ``content`` may be empty.

        Verified 2026-09-20 against running Mahavishnu — without this
        branch the probe returns ``None`` and crackerjack falls through
        to public PyPI.
        """
        url = "https://gitlab.com/api/v4/projects/123/packages/pypi/upload"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [],
                "isError": False,
                "structuredContent": {"result": url},
            },
        }
        assert _parse_mcp_response(payload) == url

    def test_fastmcp_structured_content_none(self) -> None:
        """When the tool returns ``None`` (no matching repo), the
        structuredContent.result lands as ``None`` in the wire format.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [],
                "isError": False,
                "structuredContent": {"result": None},
            },
        }
        assert _parse_mcp_response(payload) is None

    def test_is_error_returns_none(self) -> None:
        """``isError`` lives INSIDE ``result``, per MCP spec — not at top level."""
        payload = {
            "result": {"content": [{"type": "text", "text": "x"}], "isError": True},
        }
        assert _parse_mcp_response(payload) is None

    def test_non_dict_payload(self) -> None:
        """Robustness: garbage input must not raise."""
        assert _parse_mcp_response("not a dict") is None  # type: ignore[arg-type]
        assert _parse_mcp_response(None) is None  # type: ignore[arg-type]

    def test_empty_content_returns_none(self) -> None:
        payload = {"result": {"content": [], "isError": False}}
        assert _parse_mcp_response(payload) is None

    def test_non_text_content_returns_none(self) -> None:
        payload = {"result": {"content": [{"type": "image", "data": "x"}], "isError": False}}
        assert _parse_mcp_response(payload) is None


class TestProbePublishUrl:
    """Pin the request shape and soft-fallback behaviour.

    The probe performs the standard MCP three-call handshake
    (initialize → notifications/initialized → tools/call). Tests patch
    ``_post_mcp`` to feed canned responses in order; the response
    sequence helper ``_handshake_responses`` builds the boilerplate
    init + notification responses so each test only specifies the
    ``tools/call`` response it cares about.
    """

    def test_returns_url_on_success(self) -> None:
        url = "https://gitlab.com/api/v4/projects/77841268/packages/pypi/upload"
        call_response = _fake_response(
            json_payload={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [{"type": "text", "text": url}],
                    "isError": False,
                },
            },
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_handshake_responses(call_response),
        ) as spy:
            result = probe_publish_url("/Users/les/Projects/mdinject")

        assert result == url
        # All 3 calls hit the same endpoint.
        for call in spy.call_args_list:
            assert call.args[0] == DEFAULT_MAHAVISHNU_MCP_URL

    def test_request_shape_is_mcp_compliant(self) -> None:
        """The third call (tools/call) must use the MCP JSON-RPC shape.

        We assert on the LAST call's payload — that's the ``tools/call``
        that fetches the URL. The first call is ``initialize`` and the
        second is ``notifications/initialized``.
        """
        call_response = _fake_response(
            json_payload={
                "result": {"content": [{"type": "text", "text": "https://x"}]},
                "isError": False,
            },
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_handshake_responses(call_response),
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        # 3 calls in order: initialize, notifications/initialized, tools/call.
        assert len(spy.call_args_list) == 3
        body = spy.call_args_list[2].kwargs["json"]
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == PROBE_TOOL_NAME
        assert body["params"]["arguments"]["repo_path"] == "/Users/les/Projects/mdinject"

    def test_session_id_echoed_on_subsequent_calls(self) -> None:
        """After initialize, ``mcp-session-id`` must appear on the
        notifications/initialized AND tools/call request headers —
        FastMCP rejects subsequent calls without it.

        Inspects the underlying ``_http_post`` seam because
        ``mcp-session-id`` is added by ``_post_mcp`` itself.
        """
        call_response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            side_effect=_handshake_responses(call_response, session_id="abc123"),
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        # Call 1 (initialize): no session header yet.
        assert "mcp-session-id" not in (spy.call_args_list[0].kwargs.get("headers") or {})
        # Call 2 (notifications): session id is present.
        assert spy.call_args_list[1].kwargs["headers"]["mcp-session-id"] == "abc123"
        # Call 3 (tools/call): session id is present.
        assert spy.call_args_list[2].kwargs["headers"]["mcp-session-id"] == "abc123"

    def test_uses_short_timeout(self) -> None:
        """The probe budget must stay cheap — never block startup for long.

        Inspects the underlying ``_http_post`` seam because ``timeout``
        is set inside ``_post_mcp``. Bumped from 0.2 s to 5.0 s after
        verifying (2026-09-20) that FastMCP's SSE body reads need
        well over 200 ms even for a sub-second tools/call.
        """
        call_response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            side_effect=_handshake_responses(call_response),
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        # Every call uses the configured timeout.
        for call in spy.call_args_list:
            assert call.kwargs["timeout"] == PROBE_TIMEOUT_SECONDS
        # Total probe cost is at most 3 × timeout (3 calls in worst case).
        # Keep the ceiling generous enough to allow for SSE body reads.
        assert PROBE_TIMEOUT_SECONDS <= 10.0

    def test_uses_correct_accept_header(self) -> None:
        """FastMCP requires both ``application/json`` AND ``text/event-stream``
        in the Accept header. Sending only JSON returns HTTP 406.

        Inspects the underlying ``_http_post`` seam because the Accept
        header is set inside ``_post_mcp``.
        """
        call_response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            side_effect=_handshake_responses(call_response),
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        for call in spy.call_args_list:
            accept = call.kwargs["headers"]["Accept"]
            assert "application/json" in accept
            assert "text/event-stream" in accept

    def test_initialize_without_session_id_returns_none(self) -> None:
        """If the server's initialize response lacks ``mcp-session-id``,
        we can't proceed to tools/call — soft fallback to default.
        """
        # init response has no session id in headers
        init_response = _fake_response(
            json_payload={"result": {"protocolVersion": "2024-11-05"}},
            headers={},  # no mcp-session-id
        )
        call_response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=[init_response, _fake_response(), call_response],
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_initialize_404_returns_none(self) -> None:
        response = _fake_response(status_code=404, text="not found")

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            return_value=response,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_tools_call_500_returns_none(self) -> None:
        init_response = _fake_response(
            json_payload={"result": {"protocolVersion": "2024-11-05"}},
            headers={"mcp-session-id": "abc"},
        )
        notif_response = _fake_response(status_code=202, text="")
        call_response = _fake_response(status_code=500, text="boom")

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=[init_response, notif_response, call_response],
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_empty_url_string_returns_none(self) -> None:
        """Mahavishnu can legitimately return empty string for 'no URL'."""
        call_response = _fake_response(
            json_payload={
                "result": {"content": [{"type": "text", "text": ""}], "isError": False},
            },
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_handshake_responses(call_response),
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_malformed_json_returns_none(self) -> None:
        """Soft fallback on non-JSON body — must not raise."""
        call_response = _fake_response(text="not json at all")

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_handshake_responses(call_response),
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_sse_wrapped_response_is_parsed(self) -> None:
        """FastMCP returns SSE-formatted bodies even when JSON is accepted.
        The probe must extract the ``data:`` line and parse that as JSON.
        """
        url = "https://gitlab.com/api/v4/projects/77841268/packages/pypi/upload"
        sse_body = (
            "event: message\n"
            f"data: {{\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{{\"content\":[{{\"type\":\"text\",\"text\":\"{url}\"}}],\"isError\":false}}}}\n"
            "\n"
        )
        call_response = _fake_response(text=sse_body)

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_handshake_responses(call_response),
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") == url

    def test_is_error_in_result_returns_none(self) -> None:
        """MCP error responses carry ``isError: true`` INSIDE ``result``."""
        call_response = _fake_response(
            json_payload={
                "result": {
                    "content": [{"type": "text", "text": "Tool not found"}],
                    "isError": True,
                },
            },
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_handshake_responses(call_response),
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_connection_refused_returns_none(self) -> None:
        """Soft fallback: Mahavishnu down → ``None`` (caller falls through to PyPI)."""

        def _raise(*_args, **_kwargs):
            raise httpx.ConnectError("Connection refused")

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_raise,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_timeout_returns_none(self) -> None:
        def _raise(*_args, **_kwargs):
            raise httpx.TimeoutException("read timed out")

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_raise,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None


class TestEndpointUrlDiscovery:
    """The endpoint URL discovery respects $MAHAVISHNU_MCP_URL override."""

    def test_override_used_in_probe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An override must be passed through to the actual HTTP call."""
        monkeypatch.setenv(ENV_VAR_URL_OVERRIDE, "http://vish-internal:9999")

        call_response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "https://x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_handshake_responses(call_response),
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        # All 3 calls use the override endpoint.
        for call in spy.call_args_list:
            assert call.args[0] == "http://vish-internal:9999/mcp"

    def test_override_with_trailing_path_is_preserved(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(ENV_VAR_URL_OVERRIDE, "http://vish-internal:9999/mcp")

        call_response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "https://x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._post_mcp",
            side_effect=_handshake_responses(call_response),
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        # Already has /mcp — no double-append.
        for call in spy.call_args_list:
            assert call.args[0] == "http://vish-internal:9999/mcp"
