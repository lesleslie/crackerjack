from __future__ import annotations

import sys
import pytest

SECRET = "crackerjack-test-secret-at-least-32-chars-ok"


@pytest.fixture
def _reload_auth_module(monkeypatch):
    """Fixture that reloads websocket.auth module before and after each test.

    This ensures that module initialization respects environment variable changes
    made by monkeypatch, while also cleaning up module state to prevent
    contamination of subsequent tests.
    """
    # Store the original module state
    original_module = sys.modules.pop("crackerjack.websocket.auth", None)

    yield

    # Cleanup after test: remove the module again to prevent state leakage
    sys.modules.pop("crackerjack.websocket.auth", None)
    # Restore original module if it existed
    if original_module is not None:
        sys.modules["crackerjack.websocket.auth"] = original_module


def test_auth_disabled_when_no_secret(monkeypatch, _reload_auth_module):
    monkeypatch.delenv("CRACKERJACK_JWT_SECRET", raising=False)
    monkeypatch.delenv("BODAI_SHARED_SECRET", raising=False)

    from crackerjack.websocket.auth import get_auth_config

    cfg = get_auth_config()
    assert cfg.enabled is False


def test_auth_enabled_when_secret_set(monkeypatch, _reload_auth_module):
    monkeypatch.setenv("CRACKERJACK_JWT_SECRET", SECRET)

    from crackerjack.websocket.auth import get_auth_config

    cfg = get_auth_config()
    assert cfg.enabled is True


def test_generate_and_verify_round_trip(monkeypatch, _reload_auth_module):
    monkeypatch.setenv("CRACKERJACK_JWT_SECRET", SECRET)

    from crackerjack.websocket.auth import generate_token, verify_token

    token = generate_token(user_id="system", permissions=["read"])
    result = verify_token(token)
    assert result is not None
    assert result.get("iss") == "crackerjack"
    assert result.get("aud") == "crackerjack"
    assert "read" in result.get("scopes", [])
