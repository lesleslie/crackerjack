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
        monkeypatch.setenv("UV_PUBLISH_TOKEN", "ambient-token")
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
        # Explicitly override any ambient token so uv cannot prefer it over TP.
        assert mock_run.call_args.kwargs["additional_env"] == {
            "UV_PUBLISH_TOKEN": "",
        }

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
            assert env.get("UV_PUBLISH_TOKEN") == ""


class TestRealKeyringHelperUnmasked:
    """Regression: the existing ``TestTokenBodySurvives`` test mocks
    ``crackerjack.services.pypi_auth._providers._keyring_get_raw`` directly.
    That mock returns the sentinel token verbatim, so the test would still
    pass if a future regression added ``mask_tokens(result.stdout)`` INSIDE
    ``_keyring_get_raw`` itself (the mock short-circuits the real helper
    and the corruption would never run).

    This class patches one level lower — the ``subprocess.run`` that
    ``_keyring_get_raw`` actually invokes — and lets the real
    ``discover_auth()`` → ``KeyringAuthProvider.resolve()`` →
    ``_keyring_get_raw()`` chain execute. Any masking reintroduced
    inside ``_keyring_get_raw`` would now corrupt the token before the
    provider wraps it, and this test would catch it.
    """

    def test_real_keyring_helper_token_reaches_uv_publish_unmodified(
        self,
        manager: PublishManagerImpl,
    ) -> None:
        # Body contains a 64-char hex run -- mask_generic_long_token
        # masks any 32+ char run of [a-zA-Z0-9_-].
        sentinel_body = "deadbeef" * 8  # 64-char hex run
        sentinel_token = f"pypi-AgEIcHlwaS5vcmcC{sentinel_body}"

        completed = subprocess.CompletedProcess(
            args=["keyring", "get", "url", "user"],
            returncode=0,
            stdout=sentinel_token + "\n",
            stderr="",
        )

        build_patch = patch.object(manager, "build_package", return_value=True)
        run_patch = patch.object(manager, "_run_command")
        # Patch the lower-level subprocess.run that _keyring_get_raw calls.
        # We deliberately do NOT patch _keyring_get_raw itself.
        subprocess_patch = patch(
            "crackerjack.services.pypi_auth._keyring.subprocess.run",
            return_value=completed,
        )

        with build_patch, run_patch as mock_run, subprocess_patch:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Successfully uploaded",
                stderr="",
            )
            result = manager._execute_publish()

        assert result is True
        env = mock_run.call_args.kwargs.get("additional_env") or {}
        # Belt-and-suspenders: token body has zero ``****`` corruption.
        assert "****" not in env.get("UV_PUBLISH_TOKEN", "")
        assert sentinel_body in env["UV_PUBLISH_TOKEN"]
        assert env["UV_PUBLISH_TOKEN"] == sentinel_token
        assert mock_run.call_args.args[0] == ["uv", "publish"]


class TestExecutePublishWithPublishUrl:
    """Covers the third branch in PublishManagerImpl._execute_publish
    when publish_url is set: uv publish --publish-url <URL> with token auth
    (skipping OIDC trusted publishing)."""

    def test_injects_publish_url_and_uses_token_auth(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``uv publish --publish-url <URL>`` runs with a registry-issued
        token sourced from the configured env var — NOT a public-PyPI
        ``pypi-...`` token from the PyPI auth chain.

        Pre-fix: this test passed a ``pypi-...`` keyring token to a
        custom URL, which GitLab would 401 on. Post-fix, custom URLs
        pull the token from the registry's env var so gitlab.com gets
        the right token shape.
        """
        url = "https://gitlab.com/api/v4/projects/1/packages/pypi"
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        gitlab_pat = "glpat-EXAMPLE-do-not-use"
        # Even when a keyring has a stale pypi-... token, the
        # gitlab.com URL must bypass the PyPI auth chain and source
        # ``GITLAB_PERSONAL_ACCESS_TOKEN`` (the conventional default).
        monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", gitlab_pat)
        manager = PublishManagerImpl(pkg_path=tmp_path, publish_url=url)
        with patch.object(manager, "build_package", return_value=True), \
             patch.object(manager, "_run_command") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Successfully uploaded", stderr="",
            )
            result = manager._execute_publish()
        assert result is True
        cmd = mock_run.call_args.args[0]
        assert cmd == ["uv", "publish", "--publish-url", url]
        assert mock_run.call_args.kwargs["additional_env"] == {
            "UV_PUBLISH_TOKEN": gitlab_pat,
        }

    def test_publish_url_suppresses_trusted_publishing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When publish_url is set and only OIDC trusted publishing is
        available (no keyring token), _execute_publish must refuse with a
        clear error rather than crashing on the trusted-publishing sentinel.

        uv rejects --publish-url + --trusted-publishing; the manager must
        not silently fall through into the OIDC path. It returns False and
        prints a message explaining the user must configure a token.
        """
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        url = "https://gitlab.example/api/v4/projects/1/packages/pypi"
        manager = PublishManagerImpl(pkg_path=tmp_path, publish_url=url)
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "any-oidc-token")
        # No UV_PUBLISH_TOKEN, no keyring entry -- only OIDC is available.
        monkeypatch.delenv("UV_PUBLISH_TOKEN", raising=False)
        with patch.object(manager, "build_package", return_value=True), \
             patch.object(manager, "_run_command") as mock_run, \
             patch(
                 "crackerjack.services.pypi_auth._providers._keyring_get_raw",
                 return_value=None,
             ):
            result = manager._execute_publish()
        assert result is False
        # Critical: _run_command MUST NOT be called when only OIDC is
        # available -- that would feed uv --publish-url + --trusted-publishing
        # which uv rejects.
        mock_run.assert_not_called()

    def test_dry_run_includes_url(self, tmp_path: Path) -> None:
        """When publish_url is set, dry-run prints the URL."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        url = "https://gitlab.example/api/v4/projects/1/packages/pypi"
        manager = PublishManagerImpl(pkg_path=tmp_path, publish_url=url)
        # Capture console output via the manager's console.
        from io import StringIO
        from rich.console import Console as RichConsole

        buffer = StringIO()
        manager.console = RichConsole(file=buffer, force_terminal=False)
        result = manager._handle_dry_run_publish()
        assert result is True
        output = buffer.getvalue()
        assert url in output
        assert "to PyPI" not in output  # The default PyPI message must NOT appear.

    def test_dry_run_default_uses_pypi_message(self, manager: PublishManagerImpl) -> None:
        """When publish_url is NOT set, dry-run prints the original PyPI message."""
        from io import StringIO
        from rich.console import Console as RichConsole

        buffer = StringIO()
        manager.console = RichConsole(file=buffer, force_terminal=False)
        result = manager._handle_dry_run_publish()
        assert result is True
        output = buffer.getvalue()
        assert "to PyPI" in output
        assert "gitlab" not in output.lower()


class TestResolveCustomTokenEnvName:
    """Pins the precedence for resolving the env-var that holds a
    custom-registry publish token (``gitlab.com`` PyPI in particular)."""

    def test_explicit_publish_token_env_wins(self, tmp_path: Path) -> None:
        """Operator-set ``publish_token_env`` overrides the gitlab.com default."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        manager = PublishManagerImpl(
            pkg_path=tmp_path,
            publish_url="https://gitlab.com/api/v4/projects/1/packages/pypi",
            publish_token_env="CRACKERJACK_TEST_TOKEN",
        )
        assert (
            manager._resolve_custom_token_env_name() == "CRACKERJACK_TEST_TOKEN"
        )

    def test_gitlab_com_url_defaults_to_known_env(self, tmp_path: Path) -> None:
        """Without an explicit override, gitlab.com URLs default to
        ``GITLAB_PERSONAL_ACCESS_TOKEN`` — the canonical PAT env var name."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        manager = PublishManagerImpl(
            pkg_path=tmp_path,
            publish_url="https://gitlab.com/api/v4/projects/1/packages/pypi",
        )
        assert (
            manager._resolve_custom_token_env_name()
            == "GITLAB_PERSONAL_ACCESS_TOKEN"
        )

    def test_unknown_registry_returns_none_when_unset(self, tmp_path: Path) -> None:
        """A non-PyPI URL that we don't recognize as a known registry
        returns ``None`` so the caller errors out asking for an
        explicit ``--publish-token-env``, rather than silently picking
        the wrong env var."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        manager = PublishManagerImpl(
            pkg_path=tmp_path,
            publish_url="https://private.example.com/api/v4/....../packages/pypi",
        )
        assert manager._resolve_custom_token_env_name() is None


class TestExecutePublishToCustomRegistry:
    """Pins the auth wiring for publishing to a gitlab.com PyPI repo.

    The pre-fix code unconditionally pushed the PyPI ``pypi-...`` token
    through ``auth.as_uv_publish_token()``, which GitLab's PyPI registry
    rejects with 401. The post-fix code resolves the GitLab PAT from the
    configured env var instead of going through the PyPI auth chain.
    """

    def test_reads_token_from_configured_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        url = "https://gitlab.com/api/v4/projects/1/packages/pypi"
        manager = PublishManagerImpl(
            pkg_path=tmp_path,
            publish_url=url,
            publish_token_env="MY_GITLAB_TOKEN",
        )
        monkeypatch.setenv("MY_GITLAB_TOKEN", "glpat-EXAMPLE-do-not-use")
        monkeypatch.delenv("UV_PUBLISH_TOKEN", raising=False)

        with patch.object(manager, "build_package", return_value=True), \
             patch.object(manager, "_run_command") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Successfully uploaded", stderr="",
            )
            result = manager._execute_publish()
        assert result is True
        cmd = mock_run.call_args.args[0]
        assert cmd == ["uv", "publish", "--publish-url", url]
        assert mock_run.call_args.kwargs["additional_env"] == {
            "UV_PUBLISH_TOKEN": "glpat-EXAMPLE-do-not-use",
        }

    def test_does_not_use_pypi_auth_chain_for_gitlab(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Even when the public-PyPI token chain is available, a
        ``--publish-url`` publish must NOT pass the PyPI ``pypi-...``
        token through to GitLab — it must use the registry-side env var.

        This pins the regression that bit mdinject 2026-09-20 (the
        pre-fix code sent ``pypi-...`` tokens to gitlab.com and got 401).
        """
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        url = "https://gitlab.com/api/v4/projects/1/packages/pypi"
        pypi_token = "pypi-AgEIcHlwaS5vcmcCAAAAAAAAAAAA"
        monkeypatch.setenv("UV_PUBLISH_TOKEN", pypi_token)
        monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "glpat-real-token")

        manager = PublishManagerImpl(
            pkg_path=tmp_path,
            publish_url=url,
            # No explicit publish_token_env — must default to
            # GITLAB_PERSONAL_ACCESS_TOKEN for gitlab.com URLs.
        )
        with patch.object(manager, "build_package", return_value=True), \
             patch.object(manager, "_run_command") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Successfully uploaded", stderr="",
            )
            manager._execute_publish()
        # The pypi-... token must NOT leak through to the registry call.
        assert (
            mock_run.call_args.kwargs["additional_env"]["UV_PUBLISH_TOKEN"]
            != pypi_token
        )
        assert (
            mock_run.call_args.kwargs["additional_env"]["UV_PUBLISH_TOKEN"]
            == "glpat-real-token"
        )

    def test_refuses_when_token_env_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If neither ``publish_token_env`` nor the conventional
        registry default is set in the environment, ``_execute_publish``
        must return ``False`` and surface a clear error rather than
        crashing or sending an empty token."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )
        url = "https://gitlab.com/api/v4/projects/1/packages/pypi"
        monkeypatch.delenv("GITLAB_PERSONAL_ACCESS_TOKEN", raising=False)
        manager = PublishManagerImpl(pkg_path=tmp_path, publish_url=url)
        with patch.object(manager, "build_package", return_value=True), \
             patch.object(manager, "_run_command") as mock_run:
            result = manager._execute_publish()
        assert result is False
        mock_run.assert_not_called()
