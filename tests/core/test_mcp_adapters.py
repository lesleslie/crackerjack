"""Tests for the production HTTP MCP client adapters.

Verifies that ``_HTTPMahavishnuClient`` and ``_HTTPSessionBuddyClient``
speak HTTP correctly to a Mahavishnu/Session-Buddy server. Uses
``respx``-style mocking via direct ``httpx.MockTransport`` (no extra
dependency) so we can assert request shape and simulate responses.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from crackerjack.core.tier3_factory import (
    _HTTPMahavishnuClient,
    _HTTPSessionBuddyClient,
)


def _mock_client(handler) -> httpx.Client:
    """Wrap a request handler in a mock-transport httpx.Client."""
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )


# ---------------------------------------------------------------------------
# _HTTPMahavishnuClient
# ---------------------------------------------------------------------------


class TestHTTPMahavishnuClient:
    def test_rejects_non_http_url(self) -> None:
        with pytest.raises(ValueError, match="must be http"):
            _HTTPMahavishnuClient(base_url="ftp://nope")

    def test_rejects_empty_url(self) -> None:
        with pytest.raises(ValueError, match="must be http"):
            _HTTPMahavishnuClient(base_url="")

    def test_strips_trailing_slash(self) -> None:
        # Constructor must accept both ``http://x`` and ``http://x/``.
        c1 = _HTTPMahavishnuClient(base_url="http://example.com")
        c2 = _HTTPMahavishnuClient(base_url="http://example.com/")
        assert c1._client.base_url == c2._client.base_url

    def test_dispatch_posts_to_pool_route_execute_endpoint(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["method"] = request.method
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": "fixed-by-mahavishnu",
                    "message": "ok",
                },
            )

        client = _HTTPMahavishnuClient(base_url="http://m.example.com")
        client._client = _mock_client(handler)
        result = client.pool_route_execute(
            prompt="fix this", pool_selector="least_loaded", timeout=300
        )
        assert captured["path"] == "/mcp/tools/pool_route_execute"
        assert captured["method"] == "POST"
        assert captured["body"] == {
            "prompt": "fix this",
            "pool_selector": "least_loaded",
            "timeout": 300,
        }
        assert result["success"] is True
        assert result["result"] == "fixed-by-mahavishnu"

    def test_dispatch_returns_failure_dict_on_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="service down")

        client = _HTTPMahavishnuClient(base_url="http://m.example.com")
        client._client = _mock_client(handler)
        result = client.pool_route_execute(prompt="x")
        assert result["success"] is False
        assert "HTTP dispatch failed" in result["message"] or "503" in result["message"]

    def test_dispatch_returns_failure_dict_on_connection_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = _HTTPMahavishnuClient(base_url="http://m.example.com")
        client._client = _mock_client(handler)
        result = client.pool_route_execute(prompt="x")
        assert result["success"] is False

    def test_dispatch_handles_dict_result(self) -> None:
        # The wire format may return a dict ``result`` (Mahavishnu may
        # want to return structured worker output). Our adapter should
        # pass it through (MahavishnuPool._parse_pool_route_result
        # handles the type).

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {"diff": "x", "files_modified": ["/foo.py"]},
                },
            )

        client = _HTTPMahavishnuClient(base_url="http://m.example.com")
        client._client = _mock_client(handler)
        result = client.pool_route_execute(prompt="x")
        assert result["success"] is True
        assert result["result"] == {"diff": "x", "files_modified": ["/foo.py"]}


# ---------------------------------------------------------------------------
# _HTTPSessionBuddyClient
# ---------------------------------------------------------------------------


class TestHTTPSessionBuddyClient:
    def test_rejects_non_http_url(self) -> None:
        with pytest.raises(ValueError, match="must be http"):
            _HTTPSessionBuddyClient(base_url="ftp://nope")

    def test_distill_skills_now_posts_correct_shape(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            captured["path"] = request.url.path
            return httpx.Response(200, json={"ok": True})

        client = _HTTPSessionBuddyClient(base_url="http://sb.example.com")
        client._client = _mock_client(handler)
        result = client.distill_skills_now(
            problem="unsupported-attribute:X",
            because="applied at /foo.py",
            approach="--- a/foo.py\n+++ b/foo.py\n",
            evidence_threshold=3,
        )
        assert captured["path"] == "/mcp/tools/distill_skills_now"
        assert captured["body"]["problem"] == "unsupported-attribute:X"
        assert captured["body"]["evidence_threshold"] == 3
        assert result["ok"] is True

    def test_distill_returns_false_on_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        client = _HTTPSessionBuddyClient(base_url="http://sb.example.com")
        client._client = _mock_client(handler)
        result = client.distill_skills_now(problem="x", because="y", approach="z")
        assert result["ok"] is False
        # httpx.raise_for_status() formats the error with the URL and
        # status code; we just need to confirm an error was reported.
        assert "500" in result["error"]

    def test_search_distilled_skills_returns_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "hits": [
                        {"diff": "--- a\n+++ b\n", "source_path": "/x.py"},
                        {"diff": "--- c\n+++ d\n", "source_path": "/y.py"},
                    ]
                },
            )

        client = _HTTPSessionBuddyClient(base_url="http://sb.example.com")
        client._client = _mock_client(handler)
        hits = client.search_distilled_skills(query="unsupported-attribute:X")
        assert len(hits) == 2
        assert hits[0]["source_path"] == "/x.py"

    def test_search_distilled_skills_returns_empty_on_connection_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("unreachable")

        client = _HTTPSessionBuddyClient(base_url="http://sb.example.com")
        client._client = _mock_client(handler)
        hits = client.search_distilled_skills(query="x")
        assert hits == []

    def test_search_distilled_skills_tolerates_missing_hits_key(self) -> None:
        # Server may return a payload without ``hits`` (e.g., error
        # wrapper). We must return [] in that case, not raise.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "error", "error": "no hits"})

        client = _HTTPSessionBuddyClient(base_url="http://sb.example.com")
        client._client = _mock_client(handler)
        hits = client.search_distilled_skills(query="x")
        assert hits == []


# ---------------------------------------------------------------------------
# Factory integration
# ---------------------------------------------------------------------------


class TestFactoryUsesHTTPClients:
    """Verify the factory actually instantiates the HTTP adapters."""

    def test_factory_uses_http_mahavishnu_client(self) -> None:
        from crackerjack.core.tier3_factory import _make_mahavishnu_client

        client = _make_mahavishnu_client("http://m.example.com")
        assert isinstance(client, _HTTPMahavishnuClient)

    def test_factory_uses_http_session_buddy_client(self) -> None:
        from crackerjack.core.tier3_factory import _make_session_buddy_client

        client = _make_session_buddy_client("http://sb.example.com")
        assert isinstance(client, _HTTPSessionBuddyClient)

    def test_factory_returns_none_for_invalid_url(self) -> None:
        from crackerjack.core.tier3_factory import (
            _make_mahavishnu_client,
            _make_session_buddy_client,
        )

        # Invalid URLs fail validation in the adapter constructor,
        # which the factory catches and returns None.
        assert _make_mahavishnu_client("ftp://nope") is None
        assert _make_session_buddy_client("ftp://nope") is None
        assert _make_mahavishnu_client("") is None
        assert _make_session_buddy_client("") is None
