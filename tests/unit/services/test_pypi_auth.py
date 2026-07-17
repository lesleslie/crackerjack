from __future__ import annotations

import pickle

import pytest

from crackerjack.services.pypi_auth._auth import PyPIAuth


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


class TestPyPIAuthReprSafety:
    def test_repr_never_includes_token(self) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        auth = PyPIAuth(token)
        r = repr(auth)
        assert token not in r
        assert "source=" in r

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


class TestPyPIAuthPickling:
    def test_pickling_raises(self) -> None:
        auth = PyPIAuth("pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA")
        with pytest.raises((TypeError, AttributeError, pickle.PicklingError)):
            pickle.dumps(auth)
