from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.pypi_auth._keyring import _keyring_get_raw


class TestKeyringGetRawHappyPath:
    def test_returns_stdout_stripped(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["keyring", "get", "url", "user"],
            returncode=0,
            stdout="pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA\n",
            stderr="",
        )
        with patch(
            "crackerjack.services.pypi_auth._keyring.subprocess.run",
            return_value=completed,
        ):
            result = _keyring_get_raw("url", "user")
        assert result == "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"

    def test_returns_token_with_long_body_unchanged(self) -> None:
        # Regression: mask_generic_long_token would have mangled this.
        long_token = "pypi-AgEIcHlwaS5vcmcC" + "deadbeef" * 8
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=long_token + "\n", stderr="",
        )
        with patch(
            "crackerjack.services.pypi_auth._keyring.subprocess.run",
            return_value=completed,
        ):
            result = _keyring_get_raw("url", "user")
        assert result == long_token
        assert "****" not in result


class TestKeyringGetRawFailureModes:
    def test_file_not_found_returns_none(self) -> None:
        with patch(
            "crackerjack.services.pypi_auth._keyring.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = _keyring_get_raw("url", "user")
        assert result is None

    def test_timeout_returns_none(self) -> None:
        with patch(
            "crackerjack.services.pypi_auth._keyring.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="keyring", timeout=10),
        ):
            result = _keyring_get_raw("url", "user")
        assert result is None

    def test_nonzero_exit_returns_none(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="backend unavailable",
        )
        with patch(
            "crackerjack.services.pypi_auth._keyring.subprocess.run",
            return_value=completed,
        ):
            result = _keyring_get_raw("url", "user")
        assert result is None

    def test_empty_stdout_returns_none(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="  \n  ", stderr="",
        )
        with patch(
            "crackerjack.services.pypi_auth._keyring.subprocess.run",
            return_value=completed,
        ):
            result = _keyring_get_raw("url", "user")
        assert result is None


class TestKeyringGetRawInvocation:
    def test_calls_keyring_cli_with_correct_args(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="",
        )
        with patch(
            "crackerjack.services.pypi_auth._keyring.subprocess.run",
            return_value=completed,
        ) as mock_run:
            _keyring_get_raw("https://upload.pypi.org/legacy/", "__token__")
        args = mock_run.call_args.args[0]
        assert args == ["keyring", "get", "https://upload.pypi.org/legacy/", "__token__"]