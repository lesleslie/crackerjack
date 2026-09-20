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
    probe_publish_url,
)


def _fake_response(
    *,
    status_code: int = 200,
    json_payload: dict | None = None,
    text: str | None = None,
) -> SimpleNamespace:
    """Build a minimal httpx2.Response-shaped stub for the test seam.

    The seam ``_http_post`` is patched with this; tests assert on the
    request the seam received and the response the seam returned.
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
        raise_for_status=_raise_for_status,
        json=lambda: (json.loads(text_value) if text_value else None),
    )


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
    """Pin the request shape and soft-fallback behaviour."""

    def test_returns_url_on_success(self) -> None:
        url = "https://gitlab.com/api/v4/projects/77841268/packages/pypi/upload"
        response = _fake_response(
            json_payload={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": url}],
                    "isError": False,
                },
            },
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ) as spy:
            result = probe_publish_url("/Users/les/Projects/mdinject")

        assert result == url
        assert spy.call_args.args[0] == DEFAULT_MAHAVISHNU_MCP_URL

    def test_request_shape_is_mcp_compliant(self) -> None:
        """The probe must use the MCP JSON-RPC ``tools/call`` shape — Mahavishnu
        exposes its tools via FastMCP, which speaks JSON-RPC 2.0 only."""
        response = _fake_response(
            json_payload={
                "result": {"content": [{"type": "text", "text": "https://x"}]},
                "isError": False,
            },
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        body = spy.call_args.kwargs["json"]
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == PROBE_TOOL_NAME
        assert body["params"]["arguments"]["repo_path"] == "/Users/les/Projects/mdinject"

    def test_uses_short_timeout(self) -> None:
        """The probe budget must stay cheap — never block startup for long."""
        response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        assert spy.call_args.kwargs["timeout"] == PROBE_TIMEOUT_SECONDS
        assert PROBE_TIMEOUT_SECONDS <= 1.0

    def test_404_returns_none(self) -> None:
        response = _fake_response(status_code=404, text="not found")

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_500_returns_none(self) -> None:
        response = _fake_response(status_code=500, text="boom")

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_empty_url_string_returns_none(self) -> None:
        """Mahavishnu can legitimately return empty string for 'no URL'."""
        response = _fake_response(
            json_payload={
                "result": {"content": [{"type": "text", "text": ""}], "isError": False},
            },
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_malformed_json_returns_none(self) -> None:
        """Soft fallback on non-JSON body — must not raise."""
        response = _fake_response(text="not json at all")

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_is_error_in_result_returns_none(self) -> None:
        """MCP error responses carry ``isError: true`` INSIDE ``result``."""
        response = _fake_response(
            json_payload={
                "result": {
                    "content": [{"type": "text", "text": "Tool not found"}],
                    "isError": True,
                },
            },
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_connection_refused_returns_none(self) -> None:
        """Soft fallback: Mahavishnu down → ``None`` (caller falls through to PyPI)."""

        def _raise(*_args, **_kwargs):
            raise httpx.ConnectError("Connection refused")

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            side_effect=_raise,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None

    def test_timeout_returns_none(self) -> None:
        def _raise(*_args, **_kwargs):
            raise httpx.TimeoutException("read timed out")

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            side_effect=_raise,
        ):
            assert probe_publish_url("/Users/les/Projects/mdinject") is None


class TestEndpointUrlDiscovery:
    """The endpoint URL discovery respects $MAHAVISHNU_MCP_URL override."""

    def test_override_used_in_probe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An override must be passed through to the actual HTTP call."""
        monkeypatch.setenv(ENV_VAR_URL_OVERRIDE, "http://vish-internal:9999")

        response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "https://x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        assert spy.call_args.args[0] == "http://vish-internal:9999/mcp"

    def test_override_with_trailing_path_is_preserved(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(ENV_VAR_URL_OVERRIDE, "http://vish-internal:9999/mcp")

        response = _fake_response(
            json_payload={"result": {"content": [{"type": "text", "text": "https://x"}]}},
        )

        with patch(
            "crackerjack.services.mahavishnu_discovery._http_post",
            return_value=response,
        ) as spy:
            probe_publish_url("/Users/les/Projects/mdinject")

        # Already has /mcp — no double-append.
        assert spy.call_args.args[0] == "http://vish-internal:9999/mcp"
