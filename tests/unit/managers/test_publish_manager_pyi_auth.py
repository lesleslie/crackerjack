"""Unit tests for PyPIAuth abstraction wiring in PublishManagerImpl.

Task 5: verify that PublishManagerImpl delegates auth discovery to
``crackerjack.services.pypi_auth.discover_auth`` and that the publish
command is built correctly for both keyring-token and trusted-publishing
auth sources.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.managers.publish_manager import PublishManagerImpl
from crackerjack.services.pypi_auth._auth import PyPIAuth


@pytest.fixture
def manager(tmp_path: Path) -> PublishManagerImpl:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
    )
    return PublishManagerImpl(pkg_path=tmp_path)


@pytest.fixture(autouse=True)
def _isolate_pypi_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no ambient PyPI auth leaks into the tests.

    The host shell may have ``UV_PUBLISH_TOKEN`` set; ``discover_auth``
    prefers it over keyring. These tests target keyring/TP paths
    specifically, so clear it (and the TP env vars) before each test.
    """
    monkeypatch.delenv("UV_PUBLISH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)


class TestResolvePypiAuth:
    def test_returns_none_when_no_provider_succeeds(self, manager: PublishManagerImpl) -> None:
        with patch(
            "crackerjack.services.pypi_auth._providers._keyring_get_raw",
            return_value=None,
        ):
            assert manager._resolve_pypi_auth() is None

    def test_returns_pypi_auth_when_keyring_succeeds(self, manager: PublishManagerImpl) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        with patch(
            "crackerjack.services.pypi_auth._providers._keyring_get_raw",
            return_value=token,
        ):
            auth = manager._resolve_pypi_auth()
        assert isinstance(auth, PyPIAuth)
        assert auth.as_uv_publish_token() == token


class TestExecutePublishInjectsToken:
    def test_injects_uv_publish_token_for_keyring_auth(
        self, manager: PublishManagerImpl,
    ) -> None:
        token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        # Stub build_package and _run_command to capture the env
        with patch.object(manager, "build_package", return_value=True), \
             patch.object(manager, "_run_command") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Successfully uploaded",
                stderr="",
            )
            with patch(
                "crackerjack.services.pypi_auth._providers._keyring_get_raw",
                return_value=token,
            ):
                result = manager._execute_publish()
        assert result is True
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["additional_env"] == {"UV_PUBLISH_TOKEN": token}
        assert mock_run.call_args.args[0] == ["uv", "publish"]

    def test_uses_trusted_publishing_flag_when_sentinel(
        self, manager: PublishManagerImpl, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "token")
        with patch.object(manager, "build_package", return_value=True), \
             patch.object(manager, "_run_command") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Successfully uploaded",
                stderr="",
            )
            result = manager._execute_publish()
        assert result is True
        cmd = mock_run.call_args.args[0]
        assert cmd == ["uv", "publish", "--trusted-publishing"]
        # When using TP, additional_env should NOT contain UV_PUBLISH_TOKEN
        env = mock_run.call_args.kwargs.get("additional_env") or {}
        assert "UV_PUBLISH_TOKEN" not in env

    def test_returns_false_when_no_auth(self, manager: PublishManagerImpl) -> None:
        with patch(
            "crackerjack.services.pypi_auth._providers._keyring_get_raw",
            return_value=None,
        ), patch.object(manager, "_run_command") as mock_run:
            result = manager._execute_publish()
        assert result is False
        mock_run.assert_not_called()
