"""Tests for ``crackerjack.utils.xdg_paths`` and the legacy data-path guard.

Runtime data used to live under ``~/.claude/data`` — a Claude-Code-specific
directory.  The resolver module points those paths at the XDG Base Directory
locations instead, and the guard test below fails if anybody reintroduces a
hardcoded legacy data path in executable code.

The default app name is ``crackerjack``: Crackerjack owns the files it
resolves by default, and names the Session-Buddy-owned files explicitly
(``data_dir("session-buddy")``) at the call sites that touch them.

Docstrings and comments may still *name* the legacy path (they document the
migration); code may not *contain* it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from crackerjack.utils.xdg_paths import (
    cache_dir,
    config_dir,
    data_dir,
    state_dir,
)

#: The legacy, Claude-Code-specific data directory.
LEGACY_DATA_SUBSTRING = ".claude/data"

#: The same legacy location spelled as a ``Path`` join, e.g.
#: ``Path.home() / ".claude" / "data"`` — the literal substring above does
#: not appear in that form, so it needs its own pattern.
LEGACY_DATA_JOIN_PATTERN = re.compile(r"""["']\.claude["']\s*/\s*["']data["']""")

#: The package root, resolved relative to this file so the guard always
#: scans the checkout under test rather than an installed copy.
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "crackerjack"


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """Blank out every docstring in *tree*, in place."""
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = node.body
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            first.value.value = ""
    return tree


def _executable_source(path: Path) -> str:
    """Return *path*'s source with comments and docstrings removed.

    Args:
        path: The Python file to read.

    Returns:
        The normalised source of the file.  Comments never reach the AST,
        and docstrings are blanked out, so only executable code remains.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return ast.unparse(_strip_docstrings(tree))


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the home directory at a temporary directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def test_data_dir_honours_xdg_data_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``$XDG_DATA_HOME`` selects the root the app name is joined onto."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    assert data_dir() == tmp_path / "xdg-data" / "crackerjack"


def test_state_dir_honours_xdg_state_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``$XDG_STATE_HOME`` selects the root the app name is joined onto."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))

    assert state_dir() == tmp_path / "xdg-state" / "crackerjack"


def test_cache_dir_honours_xdg_cache_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``$XDG_CACHE_HOME`` selects the root the app name is joined onto."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))

    assert cache_dir() == tmp_path / "xdg-cache" / "crackerjack"


def test_config_dir_honours_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``$XDG_CONFIG_HOME`` selects the root the app name is joined onto."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    assert config_dir() == tmp_path / "xdg-config" / "crackerjack"


def test_directories_fall_back_to_xdg_defaults(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the ``XDG_*`` variables the spec defaults apply."""
    for variable in (
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
    ):
        monkeypatch.delenv(variable, raising=False)

    assert data_dir() == fake_home / ".local" / "share" / "crackerjack"
    assert state_dir() == fake_home / ".local" / "state" / "crackerjack"
    assert cache_dir() == fake_home / ".cache" / "crackerjack"
    assert config_dir() == fake_home / ".config" / "crackerjack"


def test_app_name_is_configurable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app name is a parameter, not a hardcoded constant."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    assert data_dir("some-other-app") == tmp_path / "some-other-app"


def test_session_buddy_files_are_named_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Session-Buddy-owned files keep their own namespace.

    Crackerjack reads and writes two Session-Buddy-owned databases
    (``workflow_metrics.db`` and ``correlation_insights.db``). Those must
    resolve under ``session-buddy``; Crackerjack's own files resolve under
    ``crackerjack``. The two used to share one directory, so the two
    components wrote their tables into one file.
    """
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    assert data_dir() == tmp_path / "crackerjack"
    assert data_dir("session-buddy") == tmp_path / "session-buddy"


def test_resolver_creates_no_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolving a path must not create it — the caller owns creation."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    resolved = data_dir()

    assert not resolved.exists()


def test_package_contains_no_legacy_data_path() -> None:
    """No executable code in the package may hardcode the legacy path."""
    offenders: list[str] = []

    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        source = _executable_source(path)
        if LEGACY_DATA_SUBSTRING in source:
            offenders.append(f"{path}: contains {LEGACY_DATA_SUBSTRING!r}")
        if LEGACY_DATA_JOIN_PATTERN.search(source):
            offenders.append(f"{path}: joins '.claude' and 'data'")

    assert not offenders, "legacy data paths found:\n" + "\n".join(offenders)
