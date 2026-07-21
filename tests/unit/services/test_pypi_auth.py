from __future__ import annotations

import pickle
from typing import ClassVar

import pytest

from crackerjack.services.pypi_auth._auth import (
    PyPIAuth,
    PyPIAuthProvider,
    discover_auth,
)


# ----- PyPIAuth core -----


class TestPyPIAuthConstruction:
    def test_accepts_valid_pypi_token(self) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        auth = PyPIAuth(token)
        assert auth.as_uv_publish_token() == token

    def test_accepts_token_with_dashes_and_underscores(self) -> None:
        token = "pypi-AgEIcHlwaS5vcmcC-a_b-c_d-e_f"
        auth = PyPIAuth(token)
        assert auth.as_uv_publish_token() == token

    @pytest.mark.parametrize(
        "bad_token",
        [
            "",
            "pypi-",
            "pypi-short",  # length < 16
            "notpypi-AgEIcHlwaS5vcmcCAAAAAAAAAA",  # no pypi- prefix
            "pypi_AgEIcHlwaS5vcmcCAAAAAAAAAA",  # underscore instead of dash
            "AgEIcHlwaS5vcmcCAAAAAAAAAA",  # no prefix at all
        ],
    )
    def test_rejects_invalid_tokens(self, bad_token: str) -> None:
        with pytest.raises(ValueError, match="PyPI"):
            PyPIAuth(bad_token)

    def test_error_messages_do_not_echo_token_bytes(self) -> None:
        # The credential must never appear in a ValueError message —
        # Python tracebacks log those, which would leak the secret.
        with pytest.raises(ValueError) as exc_info:
            PyPIAuth("not-a-pypi-secret-credential-AAAA")
        assert "secret" not in str(exc_info.value)
        assert "AAAA" not in str(exc_info.value)


class TestPyPIAuthReprSafety:
    def test_repr_never_includes_token(self) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        auth = PyPIAuth(token)
        r = repr(auth)
        assert token not in r
        assert "source=" in r

    def test_repr_includes_source_label(self) -> None:
        auth = PyPIAuth("pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA")
        assert auth.source() in repr(auth)

    def test_str_never_includes_token(self) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        auth = PyPIAuth(token)
        s = str(auth)
        assert token not in s

    def test_format_string_never_leaks_token(self) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        auth = PyPIAuth(token)
        s = f"{auth}"
        assert token not in s


class TestPyPIAuthEquality:
    def test_equal_by_identity_not_value(self) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        auth1 = PyPIAuth(token)
        auth2 = PyPIAuth(token)
        assert auth1 != auth2
        assert hash(auth1) != hash(auth2)


class TestPyPIAuthIsTrustedPublishing:
    def test_default_is_false(self) -> None:
        auth = PyPIAuth("pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA")
        assert auth.is_trusted_publishing() is False


class TestPyPIAuthSource:
    def test_base_source_is_unknown(self) -> None:
        auth = PyPIAuth("pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA")
        assert auth.source() == "unknown"


class TestPyPIAuthPickling:
    def test_pickling_raises(self) -> None:
        auth = PyPIAuth("pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA")
        with pytest.raises((TypeError, AttributeError, pickle.PicklingError)):
            pickle.dumps(auth)


# ----- discover_auth() -----


class _FakeProvider:
    """A test-only PyPIAuthProvider that lets us script each branch."""

    instances: ClassVar[list[_FakeProvider]] = []

    def __init__(
        self,
        name: str,
        available: bool = True,
        auth: PyPIAuth | None = None,
        raises: bool = False,
    ) -> None:
        self.name = name
        self._available = available
        self._auth = auth
        self._raises = raises
        type(self).instances.append(self)

    def is_available(self) -> bool:
        return self._available

    def resolve(self) -> PyPIAuth | None:
        if self._raises:
            msg = f"boom from {self.name}"
            raise RuntimeError(msg)
        return self._auth


@pytest.fixture(autouse=True)
def _reset_fake_provider_state() -> None:
    _FakeProvider.instances = []


def _make_token() -> PyPIAuth:
    return PyPIAuth("pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA")


class TestDiscoverAuthFirstSuccessWins:
    def test_first_provider_success_short_circuits(self) -> None:
        winner = _FakeProvider("a", available=True, auth=_make_token())
        later = _FakeProvider("b", available=True, auth=_make_token())
        auth, checked = discover_auth([winner, later])
        assert auth is winner._auth
        assert checked == [winner]
        # The 'later' provider was constructed but its resolve() was never
        # called because 'winner' succeeded first. The `checked` list being
        # exactly `[winner]` is the contract assertion; we don't need a
        # second check.

    def test_only_checked_providers_are_returned(self) -> None:
        a = _FakeProvider("a", available=False)
        b = _FakeProvider("b", available=True, auth=_make_token())
        c = _FakeProvider("c", available=True, auth=_make_token())
        _auth, checked = discover_auth([a, b, c])
        # a (unavailable) IS checked; b (winner) IS checked; c (after winner) NOT.
        assert checked == [a, b]


class TestDiscoverAuthExhaustion:
    def test_all_unavailable_returns_none_with_all_checked(self) -> None:
        a = _FakeProvider("a", available=False)
        b = _FakeProvider("b", available=False)
        auth, checked = discover_auth([a, b])
        assert auth is None
        assert checked == [a, b]

    def test_resolve_returns_none_treated_as_unavailable(self) -> None:
        a = _FakeProvider("a", available=True, auth=None)
        b = _FakeProvider("b", available=True, auth=_make_token())
        auth, checked = discover_auth([a, b])
        assert auth is b._auth
        assert checked == [a, b]


class TestDiscoverAuthProviderExceptionIsolation:
    def test_provider_exception_does_not_break_discovery(self) -> None:
        a = _FakeProvider("a", available=True, raises=True)
        b = _FakeProvider("b", available=True, auth=_make_token())
        auth, checked = discover_auth([a, b])
        assert auth is b._auth
        assert checked == [a, b]


class TestDiscoverAuthPriorityOrdering:
    def test_priority_order_is_preserved(self) -> None:
        # Even if the second provider would succeed, the first should win.
        a = _FakeProvider("a", available=False)
        b = _FakeProvider("b", available=True, auth=_make_token())
        c = _FakeProvider("c", available=True, auth=_make_token())
        _auth, checked = discover_auth([a, b, c])
        assert checked == [a, b]  # c never queried because b succeeded


def test_protocol_is_structural() -> None:
    """A duck-typed class with the right members satisfies the protocol."""

    class DuckProvider:
        name = "duck"

        def is_available(self) -> bool:
            return True

        def resolve(self) -> PyPIAuth | None:
            return _make_token()

    auth, checked = discover_auth([DuckProvider()])
    assert auth is not None
    assert checked[0] is not None
    assert isinstance(checked[0], DuckProvider)
    # Pyright/mypy would catch this statically; runtime check is sanity only.
    assert isinstance(checked[0], object)  # Protocol is structural, not nominal.


# ----- TrustedPublishingSentinel defense-in-depth -----


class TestTrustedPublishingSentinelRaises:
    """Defense-in-depth: any future caller that forgets the
    ``is_trusted_publishing()`` check should fail loudly rather than silently
    send the placeholder token to PyPI. Exercises the public surface
    (TrustedPublishingProvider().resolve()) so we don't reach into private
    symbols."""

    def test_as_uv_publish_token_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from crackerjack.services.pypi_auth._trusted_publishing import (
            TrustedPublishingProvider,
        )

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "oidc-token")
        # Clear UV_PUBLISH_TOKEN so the env-var provider doesn't shadow TP.
        monkeypatch.delenv("UV_PUBLISH_TOKEN", raising=False)

        provider = TrustedPublishingProvider()
        assert provider.is_available() is True
        auth = provider.resolve()
        assert auth is not None
        assert auth.is_trusted_publishing() is True
        with pytest.raises(RuntimeError, match="TrustedPublishingSentinel"):
            auth.as_uv_publish_token()
