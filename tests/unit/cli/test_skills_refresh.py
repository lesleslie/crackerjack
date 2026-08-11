from __future__ import annotations

import httpx
import pytest
from typer.testing import CliRunner

from crackerjack.cli.skills_cli import app


runner = CliRunner()


class _Transport(httpx.AsyncBaseTransport):
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=self.payload)


@pytest.mark.unit
def test_skills_refresh_succeeds_when_session_buddy_acks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_post(url: str, *, json: dict, timeout: float) -> httpx.Response:
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "result": {
                    "content": [{"text": '{"distilled": 7}'}],
                }
            },
        )

    monkeypatch.setattr(
        "crackerjack.cli.skills_cli._post_json", _fake_post
    )
    result = runner.invoke(app, ["refresh"])
    assert result.exit_code == 0


@pytest.mark.unit
def test_skills_refresh_exits_1_when_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_post(url: str, *, json: dict, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("test", request=httpx.Request("POST", url))

    monkeypatch.setattr(
        "crackerjack.cli.skills_cli._post_json", _fake_post
    )
    result = runner.invoke(app, ["refresh"])
    assert result.exit_code == 1
