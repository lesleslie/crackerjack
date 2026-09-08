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
