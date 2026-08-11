from __future__ import annotations

import httpx
import pytest

from crackerjack.skills.health import (
    DEFAULT_SESSION_BUDDY_URL,
    DEFAULT_TIMEOUT_SECONDS,
    SkillHealthReport,
    fetch_skill_health,
)


class _Transport(httpx.AsyncBaseTransport):
    def __init__(self, *, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.payload = payload or {}
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(self.status_code, json=self.payload)


def _make_client(transport: httpx.AsyncBaseTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS, transport=transport)


@pytest.mark.unit
async def test_fetch_skill_health_returns_fresh_when_zero_stale() -> None:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {"text": '[{"name": "foo", "status": "fresh"}]'},
            ],
        },
    }
    transport = _Transport(payload=body)

    def factory(timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=transport)

    report = await fetch_skill_health(http_client_factory=factory)
    assert report.status == "fresh"
    assert report.stale_count == 0


@pytest.mark.unit
async def test_fetch_skill_health_returns_stale_when_any_stale() -> None:
    body = {
        "result": {
            "content": [
                {"text": '[{"name": "a", "status": "stale"}, {"name": "b", "status": "fresh"}]'},
            ],
        },
    }
    transport = _Transport(payload=body)

    def factory(timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=transport)

    report = await fetch_skill_health(http_client_factory=factory)
    assert report.status == "stale"
    assert report.stale_count == 1


@pytest.mark.unit
async def test_fetch_skill_health_treats_unreachable_as_fresh() -> None:
    """Service down is NOT the same as stale data — return fresh-but-unavailable."""

    def factory(timeout: float) -> httpx.AsyncClient:
        # ConnectError to simulate unreachable host.
        return httpx.AsyncClient(timeout=timeout, transport=_BrokenTransport())

    report = await fetch_skill_health(http_client_factory=factory)
    assert report.status == "unavailable"
    assert report.stale_count == 0


class _BrokenTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("test-induced", request=request)


def test_default_url_constant_matches_existing_hook() -> None:
    assert DEFAULT_SESSION_BUDDY_URL == "http://localhost:8678/mcp"
    assert DEFAULT_TIMEOUT_SECONDS == 5.0
