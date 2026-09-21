from __future__ import annotations

from pathlib import Path
from unittest import mock

from crackerjack.adapters.base import LifecycleOptions
from crackerjack.adapters.python.lifecycle import PythonLifecycle
from crackerjack.adapters.python.version_source import PyprojectVersionSource


def _write_pyproject(tmp_path: Path, version: str = "1.0.0") -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\nversion = "{version}"\n',
    )
    return tmp_path


def test_lifecycle_run_dry_run_does_not_mutate(tmp_path: Path) -> None:
    root = _write_pyproject(tmp_path, version="1.0.0")
    lifecycle = PythonLifecycle(PyprojectVersionSource(root))
    result = lifecycle.run(LifecycleOptions(level="minor", dry_run=True))

    assert result.new_version == "1.1.0"
    assert "dry_run" in result.skipped_steps
    assert result.commit_sha is None
    assert result.tag_name is None
    # Source file unchanged.
    assert 'version = "1.0.0"' in (root / "pyproject.toml").read_text()


def test_lifecycle_run_minor_bumps(tmp_path: Path) -> None:
    """Integration test: bumps minor and reports commit/tag.

    This test MOCKS publish_manager / git operations so it runs offline.
    The end-to-end flow (real git) is exercised by existing crackerjack
    smoke tests.
    """
    root = _write_pyproject(tmp_path, version="1.0.0")
    lifecycle = PythonLifecycle(PyprojectVersionSource(root))

    with (
        mock.patch.object(lifecycle, "_commit", return_value="abc123"),
        mock.patch.object(lifecycle, "_tag", return_value="v1.1.0"),
        mock.patch.object(lifecycle, "_push", return_value=None),
    ):
        result = lifecycle.run(LifecycleOptions(level="minor"))

    assert result.new_version == "1.1.0"
    assert result.commit_sha == "abc123"
    assert result.tag_name == "v1.1.0"


def test_lifecycle_publish_threads_publish_url_from_settings(tmp_path: Path) -> None:
    """Regression: PythonLifecycle._publish_pypi must thread
    ``settings.publishing.publish_url`` to ``PublishManagerImpl``.

    Same mdincident class as the PhaseCoordinator regression (2026-09-19
    mdinject 0.2.0 ended up on public PyPI). Without this, the lifecycle
    adapter instantiated ``PublishManagerImpl(pkg_path=...)`` with no
    ``publish_url``, falling through to the default ``uv publish`` branch
    and hitting public PyPI.

    Locked here so any future refactor of ``_publish_pypi`` preserves
    the threading.
    """
    from crackerjack.config import CrackerjackSettings

    root = _write_pyproject(tmp_path, version="1.0.0")
    # Materialize a settings/local.yaml under root/settings/ so the
    # loader picks it up.
    settings_dir = root / "settings"
    settings_dir.mkdir()
    gitlab_url = (
        "https://gitlab.example/api/v4/projects/1/packages/pypi"
    )
    (settings_dir / "local.yaml").write_text(
        f"publishing:\n  publish_url: '{gitlab_url}'\n",
    )

    lifecycle = PythonLifecycle(PyprojectVersionSource(root))

    captured_kwargs: dict[str, object] = {}

    class _FakePublishManager:
        def __init__(self, **kwargs: object) -> None:
            captured_kwargs.update(kwargs)

        def publish_package(self) -> bool:
            return True

        def _get_package_name(self) -> str | None:
            # _publish_pypi reads this on the success path to build
            # project_url. We don't assert on it, but the call needs
            # to succeed so the function doesn't blow up before
            # capturing the kwargs we care about.
            return "demo"

    # Patch the symbol on its SOURCE module — _publish_pypi imports
    # PublishManagerImpl inside the function body (line 201), so the
    # binding lives in the function's local namespace at call time.
    # Patching the importer module would not intercept. This is the
    # ``monkeypatch-inline-import-target`` pattern.
    with mock.patch(
        "crackerjack.managers.publish_manager.PublishManagerImpl",
        _FakePublishManager,
    ):
        lifecycle._publish_pypi("v1.1.0")

    assert captured_kwargs.get("publish_url") == gitlab_url, (
        "_publish_pypi must pass settings.publishing.publish_url to "
        "PublishManagerImpl — otherwise private repos silently fall "
        "through to public PyPI."
    )


def test_lifecycle_publish_publish_url_none_when_settings_unset(
    tmp_path: Path,
) -> None:
    """Counterpart: when settings.publishing.publish_url is unset, the
    lifecycle adapter must NOT inject a publish_url (so the default
    public-PyPI branch is taken). Locks in the priority documented in
    ``crackerjack/config/ecosystem_synthesis.py:17-23``.
    """
    root = _write_pyproject(tmp_path, version="1.0.0")
    # No settings/local.yaml — publish_url should remain None.
    lifecycle = PythonLifecycle(PyprojectVersionSource(root))

    captured_kwargs: dict[str, object] = {}

    class _FakePublishManager:
        def __init__(self, **kwargs: object) -> None:
            captured_kwargs.update(kwargs)

        def publish_package(self) -> bool:
            return True

        def _get_package_name(self) -> str | None:
            return "demo"

    with mock.patch(
        "crackerjack.managers.publish_manager.PublishManagerImpl",
        _FakePublishManager,
    ):
        lifecycle._publish_pypi("v1.1.0")

    assert captured_kwargs.get("publish_url") is None
