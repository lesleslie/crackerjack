from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from crackerjack.adapters.base import (
    VersionNotFoundError,
    VersionWriteError,
)
from crackerjack.adapters.python.version_source import PyprojectVersionSource


def _write_pyproject(tmp_path: Path, version: str | None = "1.2.3") -> Path:
    body = '[project]\nname = "demo"\n'
    if version is not None:
        body += f'version = "{version}"\n'
    (tmp_path / "pyproject.toml").write_text(body)
    return tmp_path


def test_read_returns_project_version() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_pyproject(Path(td))
        src = PyprojectVersionSource(root)
        assert src.read() == "1.2.3"


def test_read_raises_version_not_found_when_version_missing() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_pyproject(Path(td), version=None)
        src = PyprojectVersionSource(root)
        with pytest.raises(VersionNotFoundError):
            src.read()


def test_write_updates_version_and_verifies() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_pyproject(Path(td), version="1.2.3")
        src = PyprojectVersionSource(root)
        src.write("1.2.4")
        assert src.read() == "1.2.4"


class _BrokenReadPyprojectVersionSource(PyprojectVersionSource):
    """Subclass that lies about reads.

    Simulates a write-then-read-back failure (e.g. disk corruption,
    fsync loss, or a buggy read parser) by always returning a stale
    value regardless of what ``write()`` persisted.
    """

    def read(self) -> str:  # type: ignore[override]
        return "9.9.9"


def test_write_raises_version_write_error_on_read_back_mismatch() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_pyproject(Path(td), version="1.2.3")
        src = _BrokenReadPyprojectVersionSource(root)
        with pytest.raises(VersionWriteError):
            src.write("1.2.4")