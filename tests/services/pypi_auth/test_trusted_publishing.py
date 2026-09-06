"""Tests for ``crackerjack.services.pypi_auth._trusted_publishing``.

Covers the Trusted Publishing (OIDC) provider's availability check and
credential resolution. The provider returns a sentinel when both
``GITHUB_ACTIONS`` and ``ACTIONS_ID_TOKEN_REQUEST_TOKEN`` are set.
"""

from __future__ import annotations

import pytest

from crackerjack.services.pypi_auth._trusted_publishing import (
    TrustedPublishingProvider,
)


@pytest.fixture
def provider() -> TrustedPublishingProvider:
    return TrustedPublishingProvider()


def test_provider_name_is_descriptive(provider: TrustedPublishingProvider) -> None:
    assert provider.name == "Trusted Publishing (OIDC)"


def test_is_available_returns_false_when_github_actions_unset(
    monkeypatch: pytest.MonkeyPatch, provider: TrustedPublishingProvider
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
    assert provider.is_available() is False


def test_is_available_returns_false_when_only_github_actions_set(
    monkeypatch: pytest.MonkeyPatch, provider: TrustedPublishingProvider
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
    assert provider.is_available() is False


def test_is_available_returns_false_when_only_token_set(
    monkeypatch: pytest.MonkeyPatch, provider: TrustedPublishingProvider
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "some-token")
    assert provider.is_available() is False


def test_is_available_returns_true_when_both_set(
    monkeypatch: pytest.MonkeyPatch, provider: TrustedPublishingProvider
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ghs_token")
    assert provider.is_available() is True


def test_is_available_requires_exact_github_actions_value(
    monkeypatch: pytest.MonkeyPatch, provider: TrustedPublishingProvider
) -> None:
    """``GITHUB_ACTIONS`` must literally be ``"true"`` (string), not truthy."""
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "x")
    assert provider.is_available() is False


def test_resolve_returns_none_when_unavailable(
    monkeypatch: pytest.MonkeyPatch, provider: TrustedPublishingProvider
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
    assert provider.resolve() is None


def test_resolve_returns_sentinel_when_available(
    monkeypatch: pytest.MonkeyPatch, provider: TrustedPublishingProvider
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ghs_token")
    sentinel = provider.resolve()
    assert sentinel is not None
    # The sentinel is the module-level singleton used by the auth resolver.
    from crackerjack.services.pypi_auth._auth import _TrustedPublishingSentinel

    assert isinstance(sentinel, _TrustedPublishingSentinel)
