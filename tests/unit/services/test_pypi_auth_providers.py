from __future__ import annotations

import pytest

from crackerjack.services.pypi_auth._auth import PyPIAuth
from crackerjack.services.pypi_auth._providers import (
    EnvVarAuthProvider,
    KeyringAuthProvider,
)


class TestEnvVarAuthProvider:
    def test_unavailable_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UV_PUBLISH_TOKEN", raising=False)
        provider = EnvVarAuthProvider()
        assert provider.is_available() is False
        assert provider.resolve() is None

    def test_resolves_valid_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        monkeypatch.setenv("UV_PUBLISH_TOKEN", token)
        provider = EnvVarAuthProvider()
        assert provider.is_available() is True
        auth = provider.resolve()
        assert isinstance(auth, PyPIAuth)
        assert auth.as_uv_publish_token() == token
        assert auth.source() == "env:UV_PUBLISH_TOKEN"

    def test_malformed_env_var_falls_through(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UV_PUBLISH_TOKEN", "not-pypi-format")
        provider = EnvVarAuthProvider()
        assert provider.is_available() is True
        assert provider.resolve() is None

    def test_name_is_stable(self) -> None:
        provider = EnvVarAuthProvider()
        assert provider.name == "UV_PUBLISH_TOKEN env var"


class TestKeyringAuthProvider:
    def test_unavailable_when_keyring_returns_none(self) -> None:
        from unittest.mock import patch
        with patch(
            "crackerjack.services.pypi_auth._providers._keyring_get_raw",
            return_value=None,
        ):
            provider = KeyringAuthProvider()
            assert provider.resolve() is None

    def test_resolves_valid_keyring_token(self) -> None:
        from unittest.mock import patch
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        with patch(
            "crackerjack.services.pypi_auth._providers._keyring_get_raw",
            return_value=token,
        ):
            provider = KeyringAuthProvider()
            auth = provider.resolve()
        assert isinstance(auth, PyPIAuth)
        assert auth.as_uv_publish_token() == token
        assert auth.source() == "keyring"

    def test_malformed_keyring_token_returns_none(self) -> None:
        from unittest.mock import patch
        with patch(
            "crackerjack.services.pypi_auth._providers._keyring_get_raw",
            return_value="not-pypi-format",
        ):
            provider = KeyringAuthProvider()
            assert provider.resolve() is None

    def test_name_is_stable(self) -> None:
        provider = KeyringAuthProvider()
        assert provider.name == "Keyring storage"
