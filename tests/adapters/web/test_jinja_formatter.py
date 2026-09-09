"""Jinja formatter: lex-as-validation + Tier 1 raw-source string ops.

Phase 4 ships Tier 1 only. Tier 2 normalization is deferred to a future phase
that can afford golden-master-driven design.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.web.jinja_formatter import (
    DEFAULT_DELIMITERS,
    JINJA_SUFFIXES,
    _apply_tier1,
    _env,
    _load_jinja_config,
    format_template,
)


class TestApplyTier1:
    def test_adds_trailing_newline(self) -> None:
        assert _apply_tier1("hello").endswith("\n")

    def test_idempotent_when_already_canonical(self) -> None:
        assert _apply_tier1("hello\n") == "hello\n"

    def test_strips_trailing_whitespace_per_line(self) -> None:
        assert _apply_tier1("a   \nb\n").splitlines() == ["a", "b"]

    def test_preserves_marker_surrounding_text(self) -> None:
        # Tier 1 must NOT touch text adjacent to {%- / -%} markers.
        src = "A {%- if x -%} B\n"
        assert _apply_tier1(src) == "A {%- if x -%} B\n"

    def test_normalizes_crlf_to_lf(self) -> None:
        # Phase 4 normalizes CRLF → LF (Python's splitlines() strips line
        # terminators; we rejoin with LF only). CRLF preservation is out of
        # scope for Phase 4 (deferred; see Spec Revision Notes #8).
        assert _apply_tier1("hello\r\n") == "hello\n"


class TestFormatTemplate:
    def test_lex_failure_returns_source_unchanged(self) -> None:
        """Mismatched delimiters raise TemplateSyntaxError; format_template catches and returns src."""
        src = "{% if x %}A{% endif %}"
        custom_delims = {
            "block_start": "[%", "block_end": "%]",
            "variable_start": "[[", "variable_end": "]]",
            "comment_start": "[#", "comment_end": "#]",
        }
        # Source uses `{%` but env expects `[%`. env.lex() raises TemplateSyntaxError;
        # format_template catches and returns src unchanged.
        assert format_template(src, delimiters=custom_delims) == src

    def test_default_delimiters_round_trip(self) -> None:
        src = "{# c #}\n{% if x %}\nA\n{% else %}\nB\n{% endif %}\n"
        once = format_template(src)
        twice = format_template(once)
        assert once == twice
        assert once.endswith("\n")

    def test_unknown_tag_is_tolerated(self) -> None:
        # `{% trans %}` is valid Jinja but not configured; lex returns text tokens.
        # Tier 1 must not corrupt surrounding content.
        src = "before {% trans %}hello{% endtrans %} after\n"
        once = format_template(src)
        assert "before" in once and "after" in once


class TestLoadJinjaConfig:
    def test_missing_pyproject_returns_defaults(self, tmp_path: Path) -> None:
        delims, normalize = _load_jinja_config(tmp_path)
        assert delims == DEFAULT_DELIMITERS

    def test_writes_delimiters_from_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.crackerjack.jinja]\n"
            'block_start = "[%"\n'
            'block_end = "%]"\n'
            'variable_start = "[["\n'
            'variable_end = "]]"\n'
            'comment_start = "[#"\n'
            'comment_end = "#]"\n'
        )
        delims, _ = _load_jinja_config(tmp_path)
        assert delims["block_start"] == "[%"

    def test_malformed_pyproject_returns_defaults(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("not valid toml {{{")
        delims, _ = _load_jinja_config(tmp_path)
        assert delims == DEFAULT_DELIMITERS


class TestJinjaSuffixes:
    def test_suffixes_match_policy(self) -> None:
        assert JINJA_SUFFIXES == frozenset({".html", ".j2", ".jinja"})


@pytest.mark.parametrize(
    "fixture_name",
    ["basic.html.j2", "custom_delimiters.html.j2", "whitespace.html.j2"],
)
class TestGoldenMaster:
    CORPUS = Path(__file__).parent.parent.parent / "fixtures" / "jinja-templates"

    def test_format_matches_golden_master(self, fixture_name: str) -> None:
        """Per spec Testing F9: round-trip + golden-master expected output."""
        src = (self.CORPUS / fixture_name).read_text()
        expected = (self.CORPUS / f"{fixture_name}.expected").read_text()
        actual = format_template(src)
        assert actual == expected
        # Round-trip: golden output is its own fixed point.
        assert format_template(actual) == actual
