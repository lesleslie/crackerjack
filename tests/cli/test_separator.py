"""Tests for ``crackerjack.cli.formatting``.

Covers the ``separator()`` helper which produces a horizontal rule of a
configurable character and width, falling back to the configured console
width when no explicit width is provided.
"""

from __future__ import annotations

import pytest

from crackerjack.cli import formatting
from crackerjack.cli.formatting import separator


def test_separator_default_returns_dashes_of_console_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(formatting, "get_console_width", lambda: 40)
    assert separator() == "-" * 40


def test_separator_uses_explicit_width() -> None:
    assert separator(char="=", width=10) == "=" * 10


def test_separator_uses_explicit_char() -> None:
    assert separator(char="#", width=5) == "#" * 5


def test_separator_ignores_non_positive_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Width must be a positive int; otherwise fall back to console width."""
    monkeypatch.setattr(formatting, "get_console_width", lambda: 25)
    assert separator(width=0) == "-" * 25
    assert separator(width=-5) == "-" * 25


def test_separator_ignores_non_int_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """String / float widths are not honored — fall back to console width."""
    monkeypatch.setattr(formatting, "get_console_width", lambda: 12)
    assert separator(width="10") == "-" * 12  # type: ignore[arg-type]
    assert separator(width=2.5) == "-" * 12  # type: ignore[arg-type]


def test_separator_with_empty_char_returns_empty_string() -> None:
    """An empty character produces an empty string regardless of width."""
    assert separator(char="", width=20) == ""
