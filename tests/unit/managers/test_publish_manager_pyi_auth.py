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
        # --trusted-publishing is a value-taking flag; we pin "always" because
        # OIDC has already been verified to be configured.
        assert cmd == ["uv", "publish", "--trusted-publishing", "always"]
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


VALID_TOKEN_RE = r"pypi-[A-Za-z0-9_\-]+"


class TestTokenBodySurvives:
    """Regression: prior to PyPIAuth, ``mask_generic_long_token`` corrupted
    PyPI tokens by replacing their body with ``****``, surfacing as
    "Keyring token format appears invalid" in the publish flow.

    Only the keyring provider ever pipes token bytes through a subprocess
    whose stdout could be auto-masked -- the env-var and trusted-publishing
    flows read credentials via ``os.getenv`` and were never affected.
    Parametrizing all three documents the contract for any future provider
    added to ``discover_auth`` so a re-introduction of masking cannot pass
    silently.
    """

    @pytest.mark.parametrize(
        "provider_setup",
        ["env", "keyring", "trusted_publishing"],
    )
    def test_token_reaches_uv_publish_unmodified(
        self,
        manager: PublishManagerImpl,
        monkeypatch: pytest.MonkeyPatch,
        provider_setup: str,
    ) -> None:
        # Body contains a 64-char hex run -- mask_generic_long_token
        # masks any 32+ char run of [a-zA-Z0-9_-].
        sentinel_body = "deadbeef" * 8  # 64-char hex run
        sentinel_token = f"pypi-AgEIcHlwaS5vcmcC{sentinel_body}"

        expected_cmd: list[str]
        expected_token_in_env: str | None
        if provider_setup == "env":
            monkeypatch.setenv("UV_PUBLISH_TOKEN", sentinel_token)
            expected_cmd = ["uv", "publish"]
            expected_token_in_env = sentinel_token
        elif provider_setup == "keyring":
            expected_cmd = ["uv", "publish"]
            expected_token_in_env = sentinel_token
        else:  # trusted_publishing
            monkeypatch.setenv("GITHUB_ACTIONS", "true")
            monkeypatch.setenv(
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "any-oidc-token",
            )
            expected_cmd = ["uv", "publish", "--trusted-publishing", "always"]
            expected_token_in_env = None

        # The keyring patch MUST wrap ``_execute_publish()`` -- discover_auth
        # invokes ``_keyring_get_raw`` inside that call, so teardown before
        # the call would probe the host's real (typically absent) keyring
        # and flake the test. Mirror the layout of the existing
        # ``test_injects_uv_publish_token_for_keyring_auth``.
        build_patch = patch.object(manager, "build_package", return_value=True)
        run_patch = patch.object(manager, "_run_command")
        keyring_patch = patch(
            "crackerjack.services.pypi_auth._providers._keyring_get_raw",
            return_value=sentinel_token,
        )

        with build_patch, run_patch as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Successfully uploaded",
                stderr="",
            )
            if provider_setup == "keyring":
                with keyring_patch:
                    result = manager._execute_publish()
            else:
                result = manager._execute_publish()

        assert result is True
        cmd = mock_run.call_args.args[0]
        assert cmd == expected_cmd

        env = mock_run.call_args.kwargs.get("additional_env") or {}
        if expected_token_in_env is not None:
            assert env.get("UV_PUBLISH_TOKEN") == expected_token_in_env
            # Belt-and-suspenders: token body has zero ``****`` corruption.
            assert "****" not in env["UV_PUBLISH_TOKEN"]
            assert sentinel_body in env["UV_PUBLISH_TOKEN"]
        else:
            assert "UV_PUBLISH_TOKEN" not in env
