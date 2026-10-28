"""Tests for ``crackerjack.utils.path_redaction.redact_path``.

Covers the home-directory redaction applied to user-facing path output:
paths under the home directory are rendered with a leading ``~`` so
console lines and logs do not disclose the OS account name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.utils.path_redaction import redact_path


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``Path.home()`` at a temporary directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def test_path_under_home_is_rewritten_with_tilde(fake_home: Path) -> None:
    """A path inside the home directory keeps its tail, loses the prefix."""
    assert redact_path(fake_home / "Projects" / "oneiric") == "~/Projects/oneiric"


def test_home_itself_renders_as_bare_tilde(fake_home: Path) -> None:
    """The home directory itself renders as ``~``, not ``~/.``."""
    assert redact_path(fake_home) == "~"


def test_path_outside_home_is_unchanged(fake_home: Path) -> None:
    """Paths outside the home directory carry no account information."""
    outside = Path("/opt/tools")
    assert redact_path(outside) == str(outside)


def test_relative_path_is_unchanged() -> None:
    """A relative path has no home prefix to strip."""
    assert redact_path(Path("relative/path")) == "relative/path"


def test_sibling_prefix_does_not_match_home(fake_home: Path) -> None:
    """A path sharing only a textual prefix with home is not redacted."""
    sibling = fake_home.parent / f"{fake_home.name}-backup" / "repo"
    assert redact_path(sibling) == str(sibling)


def test_accepts_string_input(fake_home: Path) -> None:
    """Strings are accepted, not just ``Path`` instances."""
    target = fake_home / "Projects" / "oneiric"
    assert redact_path(str(target)) == "~/Projects/oneiric"


def test_none_renders_verbatim() -> None:
    """A None path renders as ``None`` — the f-string's own behavior."""
    assert redact_path(None) == "None"


def test_non_path_renders_verbatim() -> None:
    """A non-path value renders as its own string form, never raising."""
    assert redact_path(42) == "42"


def test_unresolvable_home_returns_path_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no resolvable home there is nothing to redact against."""

    def _raise(cls: type[Path]) -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", classmethod(_raise))
    target = Path("/Users/someone/Projects/oneiric")
    assert redact_path(target) == str(target)
