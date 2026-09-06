"""Tests for ``crackerjack.websocket.tls_config``.

Covers the thin wrappers around ``mcp_common.websocket.tls``. The functions
forward to the upstream helpers without adding logic, so the tests verify
the delegation produces the expected dict shape and respects environment
overrides.

Note on imports: ``tests/websocket/test_server.py`` has an autouse fixture
that deletes ``crackerjack.websocket.*`` from ``sys.modules`` between tests.
Top-level imports would therefore bind stale references. Imports are placed
inside each test function so they re-resolve against the current module.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_get_websocket_tls_config_returns_dict() -> None:
    from crackerjack.websocket.tls_config import get_websocket_tls_config

    config = get_websocket_tls_config()
    assert isinstance(config, dict)


def test_get_websocket_tls_config_reads_crackjack_ws_prefix() -> None:
    """The helper should look up ``CRACKERJACK_WS_*`` env vars."""
    from crackerjack.websocket import tls_config

    sentinel = {
        "tls_enabled": True,
        "cert_file": "/tmp/cert.pem",
        "key_file": "/tmp/key.pem",
        "ca_file": None,
    }
    with patch.object(
        tls_config,
        "get_tls_config_from_env",
        return_value=sentinel,
    ) as mocked:
        result = tls_config.get_websocket_tls_config()
    mocked.assert_called_once_with("CRACKERJACK_WS")
    assert result is sentinel


def test_load_ssl_context_returns_dict_with_expected_keys() -> None:
    """The return dict always contains ``ssl_context`` and friends."""
    from crackerjack.websocket import tls_config

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            tls_config,
            "get_websocket_tls_config",
            lambda: {
                "tls_enabled": False,
                "cert_file": None,
                "key_file": None,
                "ca_file": None,
            },
        )
        result = tls_config.load_ssl_context(cert_file=None, key_file=None)
    finally:
        monkeypatch.undo()

    assert set(result.keys()) == {
        "ssl_context",
        "cert_file",
        "key_file",
        "ca_file",
        "verify_client",
    }


def test_load_ssl_context_disabled_when_no_certs_and_env_disabled() -> None:
    """If neither cert_file nor env-var TLS is set, ``ssl_context`` is None."""
    from crackerjack.websocket import tls_config

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            tls_config,
            "get_websocket_tls_config",
            lambda: {
                "tls_enabled": False,
                "cert_file": None,
                "key_file": None,
                "ca_file": None,
            },
        )
        result = tls_config.load_ssl_context(cert_file=None, key_file=None)
    finally:
        monkeypatch.undo()

    assert result["ssl_context"] is None
    assert result["cert_file"] is None
    assert result["key_file"] is None


def test_load_ssl_context_passes_verify_client() -> None:
    """The ``verify_client`` arg flows through to the context builder."""
    from crackerjack.websocket import tls_config

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            tls_config,
            "get_websocket_tls_config",
            lambda: {
                "tls_enabled": False,
                "cert_file": None,
                "key_file": None,
                "ca_file": None,
            },
        )
        with patch.object(
            tls_config, "create_ssl_context"
        ) as mocked_create:
            tls_config.load_ssl_context(
                cert_file="/x/cert.pem",
                key_file="/x/key.pem",
                verify_client=True,
            )
        mocked_create.assert_called_once()
        kwargs = mocked_create.call_args.kwargs
        assert kwargs["verify_client"] is True
    finally:
        monkeypatch.undo()


def test_load_ssl_context_propagates_create_ssl_context_errors() -> None:
    """If ``create_ssl_context`` raises, the error propagates (logged upstream)."""
    from crackerjack.websocket import tls_config

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            tls_config,
            "get_websocket_tls_config",
            lambda: {
                "tls_enabled": False,
                "cert_file": None,
                "key_file": None,
                "ca_file": None,
            },
        )
        with patch.object(
            tls_config,
            "create_ssl_context",
            side_effect=OSError("bad cert"),
        ):
            with pytest.raises(OSError, match="bad cert"):
                tls_config.load_ssl_context(
                    cert_file="/x/cert.pem", key_file="/x/key.pem"
                )
    finally:
        monkeypatch.undo()


def test_load_ssl_context_falls_back_to_env_when_no_args() -> None:
    """When cert/key args are omitted, env-config is consulted."""
    from crackerjack.websocket import tls_config

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            tls_config,
            "get_websocket_tls_config",
            lambda: {
                "tls_enabled": True,
                "cert_file": "/env/cert.pem",
                "key_file": "/env/key.pem",
                "ca_file": "/env/ca.pem",
            },
        )
        with patch.object(
            tls_config, "create_ssl_context", return_value="fake-context"
        ) as mocked:
            result = tls_config.load_ssl_context(cert_file=None, key_file=None)
    finally:
        monkeypatch.undo()

    mocked.assert_called_once_with(
        cert_file="/env/cert.pem",
        key_file="/env/key.pem",
        ca_file="/env/ca.pem",
        verify_client=False,
    )
    assert result["ssl_context"] == "fake-context"
    assert result["cert_file"] == "/env/cert.pem"


def test_load_ssl_context_converts_string_ca_file_to_str() -> None:
    """When ``ca_file`` is a string it stays a string."""
    from crackerjack.websocket import tls_config

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            tls_config,
            "get_websocket_tls_config",
            lambda: {
                "tls_enabled": True,
                "cert_file": "/x/cert.pem",
                "key_file": "/x/key.pem",
                "ca_file": "/x/ca.pem",
            },
        )
        with patch.object(
            tls_config, "create_ssl_context", return_value="ctx"
        ) as mocked:
            result = tls_config.load_ssl_context(cert_file=None, key_file=None)
    finally:
        monkeypatch.undo()

    assert result["ca_file"] == "/x/ca.pem"
    assert mocked.call_args.kwargs["ca_file"] == "/x/ca.pem"
