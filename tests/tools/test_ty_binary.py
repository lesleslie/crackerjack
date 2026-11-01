"""Tests for ``crackerjack.tools._ty_binary``.

``resolve_ty_binary`` decides which ``ty`` build the quality gates run.
That decision is load-bearing: a stale ty does not fail loudly, it
changes what the gate reports. On 2026-10-31 a five-month-old ``ty``
reported seven phantom errors across session-buddy against code that was
correct, because it resolved SQLModel's ``Session.exec`` overloads
differently.

The resolution order is:

1. ``<sys.executable>/ty`` -- the virtualenv crackerjack is running in.
2. ``PATH``.

Two properties are pinned here:

* The interpreter path is **not** resolved. ``sys.executable`` is a
  symlink inside a virtualenv pointing at the base interpreter, so
  resolving it lands in a directory that holds no ``ty`` at all.
* The repository's contents never decide the answer. An earlier draft
  preferred ``<git-root>/.venv/bin/ty`` -- an uncontrolled search path
  (CWE-427), since a checkout's files are attacker-controllable in a CI
  run over a fork's pull request.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

from crackerjack.tools import _ty_binary
from crackerjack.tools._ty_binary import resolve_ty_binary


def _make_executable(path: Path) -> Path:
    """Create an executable regular file at ``path`` and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _isolate_interpreter(monkeypatch, tmp_path: Path) -> Path:
    """Point ``sys.executable`` at a scratch ``bin`` directory.

    Without this, the interpreter running the tests is the crackerjack
    virtualenv, whose ``bin`` directory really does contain a ``ty`` --
    which would satisfy the candidate in every test.
    """
    scripts = tmp_path / "venv" / "bin"
    scripts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "executable", str(scripts / "python"))
    return scripts


def test_prefers_the_interpreters_own_directory(tmp_path: Path, monkeypatch) -> None:
    """The ty beside the running interpreter wins over PATH."""
    scripts = _isolate_interpreter(monkeypatch, tmp_path)
    expected = _make_executable(scripts / "ty")

    with patch.object(_ty_binary.shutil, "which", return_value="/usr/bin/ty"):
        assert resolve_ty_binary() == str(expected)


def test_does_not_resolve_the_interpreter_symlink(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The interpreter is not resolved; only its directory is used.

    ``sys.executable`` is a symlink to the base interpreter. Resolving
    it would land in the base interpreter's ``bin`` directory, which
    holds no ``ty`` -- so the resolution would silently fall through to
    PATH. The virtualenv's own ``bin`` is the correct anchor.
    """
    scripts = _isolate_interpreter(monkeypatch, tmp_path)
    expected = _make_executable(scripts / "ty")

    # A symlink standing in for the base interpreter, whose directory
    # has no ty at all.
    base = tmp_path / "base" / "bin"
    base.mkdir(parents=True)
    (scripts / "python").symlink_to(base / "python3.14")

    with patch.object(_ty_binary.shutil, "which", return_value="/usr/bin/ty"):
        assert resolve_ty_binary() == str(expected)
    assert not (base / "ty").exists()


def test_ignores_a_repository_local_binary(tmp_path: Path, monkeypatch) -> None:
    """A ``.venv/bin/ty`` in the checkout is never selected.

    This is the CWE-427 boundary: the contents of a checkout are
    attacker-controllable in a CI run over a fork's pull request, so
    they must not decide which binary the gate executes.
    """
    _isolate_interpreter(monkeypatch, tmp_path)
    _make_executable(tmp_path / "repo" / ".venv" / "bin" / "ty")
    monkeypatch.chdir(tmp_path / "repo")

    with patch.object(_ty_binary.shutil, "which", return_value="/usr/bin/ty"):
        assert resolve_ty_binary() == "/usr/bin/ty"


def test_rejects_a_non_executable_file(tmp_path: Path, monkeypatch) -> None:
    """A file that is not executable is not run."""
    scripts = _isolate_interpreter(monkeypatch, tmp_path)
    candidate = scripts / "ty"
    candidate.write_text("not a program\n", encoding="utf-8")
    candidate.chmod(0o644)

    with patch.object(_ty_binary.shutil, "which", return_value="/usr/bin/ty"):
        assert resolve_ty_binary() == "/usr/bin/ty"
    assert not os.access(candidate, os.X_OK)


def test_rejects_a_directory(tmp_path: Path, monkeypatch) -> None:
    """A directory named ``ty`` is not a program."""
    scripts = _isolate_interpreter(monkeypatch, tmp_path)
    (scripts / "ty").mkdir()

    with patch.object(_ty_binary.shutil, "which", return_value="/usr/bin/ty"):
        assert resolve_ty_binary() == "/usr/bin/ty"


def test_falls_back_to_path_when_the_virtualenv_has_no_ty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Without a build beside the interpreter, PATH decides."""
    _isolate_interpreter(monkeypatch, tmp_path)

    with patch.object(_ty_binary.shutil, "which", return_value="/usr/local/bin/ty"):
        assert resolve_ty_binary() == "/usr/local/bin/ty"


def test_returns_the_bare_name_when_ty_is_nowhere_to_be_found(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A missing binary must not silently skip the check.

    Returning the bare name lets the caller's ``subprocess.run`` raise
    its own ``FileNotFoundError``, which the gates already handle by
    reporting that ty was unavailable.
    """
    _isolate_interpreter(monkeypatch, tmp_path)

    with patch.object(_ty_binary.shutil, "which", return_value=None):
        assert resolve_ty_binary() == "ty"
