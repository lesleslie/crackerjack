from __future__ import annotations

import sys

import pytest

SECRET = "crackerjack-test-secret-at-least-32-chars-ok"


def test_auth_disabled_when_no_secret(monkeypatch):
    monkeypatch.delenv("CRACKERJACK_JWT_SECRET", raising=False)
    monkeypatch.delenv("BODAI_SHARED_SECRET", raising=False)
    sys.modules.pop("crackerjack.websocket.auth", None)

    from crackerjack.websocket.auth import get_auth_config

    cfg = get_auth_config()
    assert cfg.enabled is False


def test_auth_enabled_when_secret_set(monkeypatch):
    monkeypatch.setenv("CRACKERJACK_JWT_SECRET", SECRET)
    sys.modules.pop("crackerjack.websocket.auth", None)

    from crackerjack.websocket.auth import get_auth_config

    cfg = get_auth_config()
    assert cfg.enabled is True


def test_generate_and_verify_round_trip(monkeypatch):
    monkeypatch.setenv("CRACKERJACK_JWT_SECRET", SECRET)
    sys.modules.pop("crackerjack.websocket.auth", None)

    from crackerjack.websocket.auth import generate_token, verify_token

    token = generate_token(user_id="system", permissions=["read"])
    result = verify_token(token)
    assert result is not None
    assert result.get("iss") == "crackerjack"
    assert result.get("aud") == "crackerjack"
    assert "read" in result.get("scopes", [])
