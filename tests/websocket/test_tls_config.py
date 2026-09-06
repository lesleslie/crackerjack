"""Tests for ``crackerjack.websocket.tls_config``.

Covers the thin wrappers around ``mcp_common.websocket.tls``. The functions
forward to the upstream helpers without adding logic, so the tests verify
the delegation produces the expected dict shape and respects environment
overrides.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from crackerjack.websocket.tls_config import (
    get_websocket_tls_config,
    load_ssl_context,
)


def test_get_websocket_tls_config_returns_dict() -> None:
    config = get_websocket_tls_config()
    assert isinstance(config, dict)


def test_get_websocket_tls_config_reads_crackjack_ws_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The helper should look up ``CRACKERJACK_WS_*`` env vars."""
    sentinel = {
        "tls_enabled": True,
        "cert_file": "/tmp/cert.pem",
        "key_file": "/tmp/key.pem",
        "ca_file": None,
    }
    with patch(
        "crackerjack.websocket.tls_config.get_tls_config_from_env",
        return_value=sentinel,
    ) as mocked:
        result = get_websocket_tls_config()
    mocked.assert_called_once_with("CRACKERJACK_WS")
    assert result is sentinel


def test_load_ssl_context_returns_dict_with_expected_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The return dict always contains ``ssl_context`` and friends."""
    monkeypatch.setattr(
        "crackerjack.websocket.tls_config.get_websocket_tls_config",
        lambda: {
            "tls_enabled": False,
            "cert_file": None,
            "key_file": None,
            "ca_file": None,
        },
    )
    result = load_ssl_context(cert_file=None, key_file=None)
    assert set(result.keys()) == {
        "ssl_context",
        "cert_file",
        "key_file",
        "ca_file",
        "verify_client",
    }


def test_load_ssl_context_disabled_when_no_certs_and_env_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If neither cert_file nor env-var TLS is set, ``ssl_context`` is None."""
    monkeypatch.setattr(
        "crackerjack.websocket.tls_config.get_websocket_tls_config",
        lambda: {
            "tls_enabled": False,
            "cert_file": None,
            "key_file": None,
            "ca_file": None,
        },
    )
    result = load_ssl_context(cert_file=None, key_file=None)
    assert result["ssl_context"] is None
    assert result["cert_file"] is None
    assert result["key_file"] is None


def test_load_ssl_context_passes_verify_client() -> None:
    """The ``verify_client`` arg flows through to the context builder."""
    with patch(
        "crackerjack.websocket.tls_config.create_ssl_context"
    ) as mocked_create:
        with patch(
            "crackerjack.websocket.tls_config.get_websocket_tls_config",
            return_value={
                "tls_enabled": False,
                "cert_file": None,
                "key_file": None,
                "ca_file": None,
            },
        ):
            load_ssl_context(
                cert_file="/x/cert.pem",
                key_file="/x/key.pem",
                verify_client=True,
            )
        mocked_create.assert_called_once()
        kwargs = mocked_create.call_args.kwargs
        assert kwargs["verify_client"] is True


def test_load_ssl_context_propagates_create_ssl_context_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``create_ssl_context`` raises, the error propagates (logged upstream)."""
    monkeypatch.setattr(
        "crackerjack.websocket.tls_config.get_websocket_tls_config",
        lambda: {
            "tls_enabled": False,
            "cert_file": None,
            "key_file": None,
            "ca_file": None,
        },
    )
    with patch(
        "crackerjack.websocket.tls_config.create_ssl_context",
        side_effect=OSError("bad cert"),
    ):
        with pytest.raises(OSError, match="bad cert"):
            load_ssl_context(cert_file="/x/cert.pem", key_file="/x/key.pem")


def test_load_ssl_context_falls_back_to_env_when_no_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When cert/key args are omitted, env-config is consulted."""
    monkeypatch.setattr(
        "crackerjack.websocket.tls_config.get_websocket_tls_config",
        lambda: {
            "tls_enabled": True,
            "cert_file": "/env/cert.pem",
            "key_file": "/env/key.pem",
            "ca_file": "/env/ca.pem",
        },
    )
    with patch(
        "crackerjack.websocket.tls_config.create_ssl_context",
        return_value="fake-context",
    ) as mocked:
        result = load_ssl_context(cert_file=None, key_file=None)
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
    with patch(
        "crackerjack.websocket.tls_config.get_websocket_tls_config",
        return_value={
            "tls_enabled": True,
            "cert_file": "/x/cert.pem",
            "key_file": "/x/key.pem",
            "ca_file": "/x/ca.pem",
        },
    ):
        with patch(
            "crackerjack.websocket.tls_config.create_ssl_context",
            return_value="ctx",
        ) as mocked:
            result = load_ssl_context(cert_file=None, key_file=None)
    assert result["ca_file"] == "/x/ca.pem"
    assert mocked.call_args.kwargs["ca_file"] == "/x/ca.pem"
