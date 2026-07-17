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


class TestTrustedPublishingProvider:
    def test_unavailable_outside_ci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
        from crackerjack.services.pypi_auth._trusted_publishing import (
            TrustedPublishingProvider,
        )

        provider = TrustedPublishingProvider()
        assert provider.is_available() is False
        assert provider.resolve() is None

    def test_available_in_github_actions_with_oidc_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "some-token")
        from crackerjack.services.pypi_auth._trusted_publishing import (
            TrustedPublishingProvider,
        )

        provider = TrustedPublishingProvider()
        assert provider.is_available() is True
        auth = provider.resolve()
        assert auth is not None
        assert auth.is_trusted_publishing() is True
        # Source label, not the literal sentinel — for safe logging.
        assert "trusted" in auth.source().lower()

    def test_unavailable_if_github_actions_but_no_oidc_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
        from crackerjack.services.pypi_auth._trusted_publishing import (
            TrustedPublishingProvider,
        )

        provider = TrustedPublishingProvider()
        assert provider.is_available() is False

    def test_unavailable_if_oidc_token_but_not_github_actions(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "some-token")
        from crackerjack.services.pypi_auth._trusted_publishing import (
            TrustedPublishingProvider,
        )

        provider = TrustedPublishingProvider()
        assert provider.is_available() is False

    def test_name_is_stable(self) -> None:
        from crackerjack.services.pypi_auth._trusted_publishing import (
            TrustedPublishingProvider,
        )

        provider = TrustedPublishingProvider()
        assert provider.name == "Trusted Publishing (OIDC)"
