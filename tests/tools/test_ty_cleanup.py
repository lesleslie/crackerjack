"""Tests for ``crackerjack.tools.ty_cleanup``.

The ty_cleanup module parses ``ty`` concise output for two mechanically
fixable error codes (``unused-type-ignore-comment``, ``redundant-cast``),
resolves the offending code spans, plans non-overlapping edits, and applies
them. CLI integration via ``main`` covers the dry-run / apply path.

The tests:

- ``run_ty`` subprocess boundary is mocked via ``subprocess.run`` patches
  (the module imports ``subprocess`` directly, so we patch at the module
  level).
- ``_collect_files`` calls ``get_git_tracked_files`` from ``_git_utils``,
  which we patch per-test for isolation.
- File-level helpers (``plan_edits``, ``apply_edits``, ``_restrict_to_scope``)
  are exercised against ``tmp_path`` with real file I/O.

Pre-existing Python-2 ``except UnicodeDecodeError, OSError:`` syntax on
line 282 is preserved verbatim per CLAUDE.md Rule 7 (no behavioral fixes
in test-writing waves).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from crackerjack.tools import _git_utils, ty_cleanup
from crackerjack.tools.ty_cleanup import (
    AUTO_FIX_CODES,
    FileEdits,
    FixSite,
    _apply_all_edits,
    _build_arg_parser,
    _collect_files,
    _describe_planned_edits,
    _find_cast_close_paren,
    _find_first_top_level_comma,
    _line_starts,
    _resolve_redundant_cast,
    _resolve_site,
    _resolve_unused_type_ignore,
    _restrict_to_scope,
    apply_edits,
    describe_site,
    main,
    plan_edits,
    run_ty,
)


# ---------------------------------------------------------------------------
# Dataclass surface
# ---------------------------------------------------------------------------


def test_fix_site_defaults() -> None:
    site = FixSite(
        file=Path("a.py"), line=1, col=1, code="x", message="y"
    )
    assert site.start == 0
    assert site.end == 0
    assert site.raw_match == ""


def test_file_edits_add_and_is_empty() -> None:
    fe = FileEdits(path=Path("a.py"))
    assert fe.is_empty()
    fe.add(0, 5, "hello", FixSite(file=Path("a.py"), line=1, col=1, code="x", message="y"))
    assert not fe.is_empty()
    assert len(fe.replacements) == 1
    assert fe.sites[0].code == "x"


def test_auto_fix_codes_frozenset() -> None:
    assert isinstance(AUTO_FIX_CODES, frozenset)
    assert "unused-type-ignore-comment" in AUTO_FIX_CODES
    assert "redundant-cast" in AUTO_FIX_CODES


# ---------------------------------------------------------------------------
# run_ty — subprocess boundary
# ---------------------------------------------------------------------------


def _fake_run_factory(stdout: str = "", returncode: int = 1) -> object:
    """Return a mock subprocess.run that yields ``stdout``."""

    def _fake_run(*args: object, **kwargs: object) -> object:
        return SimpleNamespace(
            stdout=stdout,
            stderr="",
            returncode=returncode,
            args=args[0] if args else [],
        )

    return _fake_run


def test_run_ty_returns_empty_on_file_not_found(
    tmp_path: Path,
) -> None:
    """If ``ty`` isn't installed, ``run_ty`` returns ``[]`` (no raise)."""
    pkg = tmp_path / "crackerjack"
    pkg.mkdir()

    def _raise_fnf(*a: object, **kw: object) -> object:
        raise FileNotFoundError("ty not installed")

    with patch.object(ty_cleanup.subprocess, "run", _raise_fnf):
        assert run_ty(pkg) == []


def test_run_ty_returns_empty_on_oserror(tmp_path: Path) -> None:
    """A generic ``OSError`` from the subprocess also yields ``[]``."""
    pkg = tmp_path / "crackerjack"
    pkg.mkdir()

    def _raise_os(*a: object, **kw: object) -> object:
        raise OSError("nope")

    with patch.object(ty_cleanup.subprocess, "run", _raise_os):
        assert run_ty(pkg) == []


def test_run_ty_parses_unused_type_ignore_site(tmp_path: Path) -> None:
    """A ty concise line with ``unused-type-ignore-comment`` becomes a FixSite."""
    pkg = tmp_path / "crackerjack"
    pkg.mkdir()
    (pkg / "foo.py").write_text("x = 1\n", encoding="utf-8")

    stdout = (
        "crackerjack/foo.py:10:5: warning[unused-type-ignore-comment] "
        "Unused blanket `type: ignore` directive"
    )
    fake = _fake_run_factory(stdout=stdout)
    with patch.object(ty_cleanup.subprocess, "run", fake):
        sites = run_ty(pkg)
    assert len(sites) == 1
    site = sites[0]
    assert site.line == 10
    assert site.col == 5
    assert site.code == "unused-type-ignore-comment"
    assert site.file == (pkg / "foo.py").resolve()


def test_run_ty_parses_redundant_cast_site(tmp_path: Path) -> None:
    pkg = tmp_path / "crackerjack"
    pkg.mkdir()
    (pkg / "foo.py").write_text("x = 1\n", encoding="utf-8")

    stdout = (
        "crackerjack/foo.py:20:9: warning[redundant-cast] "
        "Redundant cast to int"
    )
    fake = _fake_run_factory(stdout=stdout)
    with patch.object(ty_cleanup.subprocess, "run", fake):
        sites = run_ty(pkg)
    assert len(sites) == 1
    assert sites[0].code == "redundant-cast"


def test_run_ty_skips_unknown_codes(tmp_path: Path) -> None:
    """Lines with codes outside ``AUTO_FIX_CODES`` are skipped."""
    pkg = tmp_path / "crackerjack"
    pkg.mkdir()
    (pkg / "foo.py").write_text("x = 1\n", encoding="utf-8")

    stdout = (
        "crackerjack/foo.py:10:5: warning[unsupported-base] "
        "Some other warning\n"
        "crackerjack/foo.py:20:9: warning[unused-type-ignore-comment] "
        "Unused blanket directive"
    )
    fake = _fake_run_factory(stdout=stdout)
    with patch.object(ty_cleanup.subprocess, "run", fake):
        sites = run_ty(pkg)
    assert len(sites) == 1
    assert sites[0].code == "unused-type-ignore-comment"


def test_run_ty_skips_blank_and_malformed_lines(tmp_path: Path) -> None:
    pkg = tmp_path / "crackerjack"
    pkg.mkdir()
    (pkg / "foo.py").write_text("x = 1\n", encoding="utf-8")

    stdout = (
        "\n"
        "not a ty line at all\n"
        "crackerjack/foo.py:10:5: warning[unused-type-ignore-comment] "
        "Unused blanket directive\n"
    )
    fake = _fake_run_factory(stdout=stdout)
    with patch.object(ty_cleanup.subprocess, "run", fake):
        sites = run_ty(pkg)
    assert len(sites) == 1


def test_run_ty_passes_correct_cwd_and_args(tmp_path: Path) -> None:
    """The subprocess.run call gets the package-root parent as cwd and the
    right ty CLI args."""
    captured: dict[str, object] = {}

    def _capture(*args: object, **kwargs: object) -> object:
        captured["args"] = args[0] if args else None
        captured["cwd"] = kwargs.get("cwd")
        captured["check"] = kwargs.get("check")
        return SimpleNamespace(stdout="", stderr="", returncode=1, args=args[0])

    package_root = tmp_path / "crackerjack"
    package_root.mkdir()
    with patch.object(ty_cleanup.subprocess, "run", _capture):
        run_ty(package_root)
    cmd = captured["args"]
    assert isinstance(cmd, list)
    assert cmd[0] == "ty"
    assert "check" in cmd
    assert captured["cwd"] == tmp_path
    assert captured["check"] is False


# ---------------------------------------------------------------------------
# _line_starts
# ---------------------------------------------------------------------------


def test_line_starts_empty_string() -> None:
    assert _line_starts("") == [0]


def test_line_starts_no_newline() -> None:
    assert _line_starts("hello") == [0]


def test_line_starts_single_newline() -> None:
    assert _line_starts("hello\n") == [0, 6]


def test_line_starts_multiple_lines() -> None:
    content = "abc\nde\n\nf\n"
    assert _line_starts(content) == [0, 4, 7, 8, 10]


# ---------------------------------------------------------------------------
# _resolve_unused_type_ignore
# ---------------------------------------------------------------------------


def test_resolve_unused_type_ignore_with_code_specifier() -> None:
    """``# type: ignore[code]`` directive — directive span is replaced.

    The ``_TYPE_IGNORE_RE`` captures leading whitespace as part of ``lead``,
    so the replacement span includes the 2 spaces before ``#``.
    """
    content = "x = 1  # type: ignore[arg-type]\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=8, code="unused-type-ignore-comment", message="x")
    result = _resolve_unused_type_ignore(content, line_starts, site)
    assert result is not None
    start, end, new_text = result
    assert new_text == ""
    # The replacement span includes the leading whitespace + directive.
    assert content[start:end] == "  # type: ignore[arg-type]"
    # Applying the replacement leaves just the leading code.
    applied = content[:start] + new_text + content[end:]
    assert applied == "x = 1\n"


def test_resolve_unused_type_ignore_blank_line_only() -> None:
    """A line containing only ``# type: ignore`` (with newline) — the
    whole line is replaced, preserving the newline by clearing content."""
    content = "# type: ignore\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=1, code="unused-type-ignore-comment", message="x")
    result = _resolve_unused_type_ignore(content, line_starts, site)
    assert result is not None
    start, end, new_text = result
    assert new_text == ""
    assert start == 0
    assert end == len(content)


def test_resolve_unused_type_ignore_blank_line_no_newline() -> None:
    content = "# type: ignore"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=1, code="unused-type-ignore-comment", message="x")
    result = _resolve_unused_type_ignore(content, line_starts, site)
    assert result is not None
    start, end, new_text = result
    assert new_text == ""
    assert start == 0


def test_resolve_unused_type_ignore_inline() -> None:
    """``# type: ignore`` mid-line (after code) — only the directive span."""
    content = "x = 1  # type: ignore\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=8, code="unused-type-ignore-comment", message="x")
    result = _resolve_unused_type_ignore(content, line_starts, site)
    assert result is not None
    _start, _end, new_text = result
    assert new_text == ""
    # The replacement is only the directive, not the whole line.
    applied = content[:_start] + new_text + content[_end:]
    assert applied.startswith("x = 1")
    assert "type: ignore" not in applied


def test_resolve_unused_type_ignore_line_out_of_range() -> None:
    content = "x = 1\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=99, col=1, code="unused-type-ignore-comment", message="x")
    assert _resolve_unused_type_ignore(content, line_starts, site) is None


def test_resolve_unused_type_ignore_no_match() -> None:
    """Line without a type: ignore directive returns None."""
    content = "x = 1\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=1, code="unused-type-ignore-comment", message="x")
    assert _resolve_unused_type_ignore(content, line_starts, site) is None


# ---------------------------------------------------------------------------
# _find_cast_close_paren / _find_first_top_level_comma
# ---------------------------------------------------------------------------


def test_find_cast_close_paren_no_close() -> None:
    """If the open paren has no matching close, returns -1."""
    assert _find_cast_close_paren("cast(", 5) == -1


def test_find_cast_close_paren_basic() -> None:
    line = "x = cast(int, y)"
    open_idx = line.index("(")
    close_idx = _find_cast_close_paren(line, open_idx)
    assert close_idx == len(line)


def test_find_cast_close_paren_nested() -> None:
    line = "x = cast(dict[str, list[int]], value)"
    open_idx = line.index("(")
    close_idx = _find_cast_close_paren(line, open_idx)
    assert close_idx == len(line)


def test_find_cast_close_paren_inside_string() -> None:
    """A ``)`` inside a string literal does not close the paren."""
    line = 'x = cast("a)b", v)'
    open_idx = line.index("(")
    close_idx = _find_cast_close_paren(line, open_idx)
    assert close_idx == len(line)


def test_find_first_top_level_comma_basic() -> None:
    assert _find_first_top_level_comma("int, y") == 3


def test_find_first_top_level_comma_no_comma() -> None:
    assert _find_first_top_level_comma("int") == -1


def test_find_first_top_level_comma_nested() -> None:
    """Commas inside parens/brackets don't count."""
    assert _find_first_top_level_comma("list[int, str], y") == 14


def test_find_first_top_level_comma_inside_string() -> None:
    """A ``,`` inside a string literal is not a top-level comma."""
    # The ``,`` at position 5 is the top-level comma (after the closing quote);
    # the ``,`` inside the string is skipped.
    assert _find_first_top_level_comma('"a,b", y') == 5


def test_find_first_top_level_comma_escaped_quote_in_string() -> None:
    """An escaped quote inside a string is consumed with its partner.

    Exercises the ``if ch == "\\\\" and j + 1 < len(inner): continue`` branch
    (line 194). After ``"a\\"`` the parser is back out of the string, so the
    next ``,`` (at position 5) is the top-level comma.
    """
    assert _find_first_top_level_comma(r'"a\"b,c", d, e') == 5


def test_find_cast_close_paren_escaped_quote_in_string() -> None:
    """An escaped quote inside a string is consumed in pairs by the parser
    (line 170-172 branch: ``ch == "\\\\" and i + 1 < len(line)``)."""
    # The cast starts at index 4. The closing ``)`` is at the end.
    line = r'cast(int, "a\"b)")'
    open_idx = line.index("(")
    close_idx = _find_cast_close_paren(line, open_idx)
    assert close_idx == len(line)


# ---------------------------------------------------------------------------
# _resolve_redundant_cast
# ---------------------------------------------------------------------------


def test_resolve_redundant_cast_returns_expression() -> None:
    """The redundant ``cast(int, x)`` becomes ``x`` (just the expression)."""
    content = "y = cast(int, x)\n"
    line_starts = _line_starts(content)
    # The cast( starts at column 5 (1-indexed) — `cast(`.
    site = FixSite(
        file=Path("a.py"),
        line=1,
        col=5,
        code="redundant-cast",
        message="x",
    )
    result = _resolve_redundant_cast(content, line_starts, site)
    assert result is not None
    start, end, new_text = result
    assert new_text.strip() == "x"
    # The full cast(...) span is replaced.
    assert content[start:end].startswith("cast(")
    assert content[start:end].endswith(")")


def test_resolve_redundant_cast_line_out_of_range() -> None:
    content = "x = 1\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=99, col=1, code="redundant-cast", message="x")
    assert _resolve_redundant_cast(content, line_starts, site) is None


def test_resolve_redundant_cast_no_cast() -> None:
    """No ``cast(`` on the line → None."""
    content = "y = something(x)\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=5, code="redundant-cast", message="x")
    assert _resolve_redundant_cast(content, line_starts, site) is None


def test_resolve_redundant_cast_unbalanced_parens() -> None:
    """A ``cast(`` with no matching close paren returns None."""
    content = "y = cast(int, x\n"  # missing close paren
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=5, code="redundant-cast", message="x")
    assert _resolve_redundant_cast(content, line_starts, site) is None


def test_resolve_redundant_cast_no_comma() -> None:
    """``cast(x)`` (no comma) returns None — can't split type from value."""
    content = "y = cast(x)\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=5, code="redundant-cast", message="x")
    assert _resolve_redundant_cast(content, line_starts, site) is None


def test_resolve_redundant_cast_empty_expression_returns_none() -> None:
    """``cast(int, )`` — trailing whitespace after the comma → no value."""
    content = "y = cast(int,    )\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=5, code="redundant-cast", message="x")
    assert _resolve_redundant_cast(content, line_starts, site) is None


def test_resolve_redundant_cast_no_open_paren_returns_none() -> None:
    """When the matched cast text has no ``(`` after it, return None.

    (Hard to construct naturally; we patch ``_REDUNDANT_CAST_RE`` to a
    different anchor.)
    """
    import re

    import crackerjack.tools.ty_cleanup as mod

    class _FakeMatch:
        def start(self) -> int:
            return 0

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(
            mod, "_REDUNDANT_CAST_RE",
            re.compile(r"x"),
        )
        content = "y = cast(int, x)\n"
        line_starts = _line_starts(content)
        site = FixSite(file=Path("a.py"), line=1, col=1, code="redundant-cast", message="x")
        assert mod._resolve_redundant_cast(content, line_starts, site) is None
    finally:
        monkey.undo()


def test_plan_edits_overlapping_replacements_skip_second(
    tmp_path: Path,
) -> None:
    """Two sites on the same file with overlapping spans: the second is skipped
    (exercises the ``for/else`` overlap-check at 295->294)."""
    src = tmp_path / "a.py"
    # Two directives on the same line — site2's span overlaps site1's.
    src.write_text("# type: ignore  # type: ignore\n", encoding="utf-8")

    site1 = FixSite(
        file=src, line=1, col=1,
        code="unused-type-ignore-comment", message="x",
    )
    site2 = FixSite(
        file=src, line=1, col=20,
        code="unused-type-ignore-comment", message="x",
    )

    edits = plan_edits([site1, site2], tmp_path)
    assert src in edits
    # First site added, second skipped due to overlap.
    assert len(edits[src].replacements) == 1


# ---------------------------------------------------------------------------
# _resolve_site dispatch
# ---------------------------------------------------------------------------


def test_resolve_site_dispatches_unused_type_ignore() -> None:
    content = "# type: ignore\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=1, code="unused-type-ignore-comment", message="x")
    assert _resolve_site(content, line_starts, site) is not None


def test_resolve_site_dispatches_redundant_cast() -> None:
    content = "y = cast(int, x)\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=5, code="redundant-cast", message="x")
    assert _resolve_site(content, line_starts, site) is not None


def test_resolve_site_unknown_code_returns_none() -> None:
    content = "x = 1\n"
    line_starts = _line_starts(content)
    site = FixSite(file=Path("a.py"), line=1, col=1, code="some-other-code", message="x")
    assert _resolve_site(content, line_starts, site) is None


# ---------------------------------------------------------------------------
# plan_edits
# ---------------------------------------------------------------------------


def test_plan_edits_skips_missing_files(tmp_path: Path) -> None:
    """Sites pointing at non-existent files are silently skipped."""
    site = FixSite(
        file=tmp_path / "nope.py",
        line=1,
        col=1,
        code="unused-type-ignore-comment",
        message="x",
    )
    assert plan_edits([site], tmp_path) == {}


def test_plan_edits_resolves_unused_type_ignore(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("x = 1  # type: ignore\n", encoding="utf-8")
    site = FixSite(
        file=src,
        line=1,
        col=8,
        code="unused-type-ignore-comment",
        message="x",
    )
    edits = plan_edits([site], tmp_path)
    assert src in edits
    assert not edits[src].is_empty()
    assert edits[src].sites[0].code == "unused-type-ignore-comment"


def test_plan_edits_resolves_redundant_cast(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("y = cast(int, x)\n", encoding="utf-8")
    site = FixSite(
        file=src,
        line=1,
        col=5,
        code="redundant-cast",
        message="x",
    )
    edits = plan_edits([site], tmp_path)
    assert src in edits
    assert not edits[src].is_empty()


def test_plan_edits_skips_overlapping_replacements(tmp_path: Path) -> None:
    """Two sites on the same file with overlapping spans: only the first is kept."""
    src = tmp_path / "a.py"
    src.write_text("# type: ignore  # type: ignore\n", encoding="utf-8")
    line_starts = _line_starts(src.read_text(encoding="utf-8"))
    site1 = FixSite(
        file=src, line=1, col=1,
        code="unused-type-ignore-comment", message="x",
    )
    site2 = FixSite(
        file=src, line=1, col=20,
        code="unused-type-ignore-comment", message="x",
    )
    # Manually pre-populate edits.replacements to simulate an overlap.
    edits = plan_edits([site1, site2], tmp_path)
    # At minimum, both attempts run; overlap logic should keep site1 and
    # skip site2 because they both touch the same line.
    assert src in edits
    # The overlap-check keeps at most one of the two sites.
    assert len(edits[src].replacements) <= 1


def test_plan_edits_handles_unicode_decode_error(tmp_path: Path) -> None:
    """A file that fails to decode is silently skipped (the except branch)."""
    src = tmp_path / "a.py"
    src.write_bytes(b"\xff\xfe\x00invalid_utf8")
    site = FixSite(
        file=src, line=1, col=1,
        code="unused-type-ignore-comment", message="x",
    )
    edits = plan_edits([site], tmp_path)
    assert edits == {}


# ---------------------------------------------------------------------------
# apply_edits
# ---------------------------------------------------------------------------


def test_apply_edits_empty_returns_false(tmp_path: Path) -> None:
    fe = FileEdits(path=tmp_path / "a.py")
    assert apply_edits(fe) is False


def test_apply_edits_replaces_span(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("# type: ignore\n", encoding="utf-8")
    fe = FileEdits(path=src)
    # Replace just the directive, keep the newline.
    fe.add(
        start=0,
        end=len("# type: ignore"),
        new_text="",
        site=FixSite(file=src, line=1, col=1, code="x", message="y"),
    )
    assert apply_edits(fe) is True
    # The directive is gone; the trailing newline remains.
    assert src.read_text(encoding="utf-8") == "\n"


def test_apply_edits_read_oserror_returns_false(tmp_path: Path) -> None:
    src = tmp_path / "missing.py"
    fe = FileEdits(path=src)
    fe.add(
        start=0,
        end=5,
        new_text="hello",
        site=FixSite(file=src, line=1, col=1, code="x", message="y"),
    )
    assert apply_edits(fe) is False


def test_apply_edits_write_oserror_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write failure on the underlying Path is swallowed → ``False``."""
    src = tmp_path / "a.py"
    src.write_text("# type: ignore\n", encoding="utf-8")
    fe = FileEdits(path=src)
    fe.add(
        start=0,
        end=src.stat().st_size,
        new_text="",
        site=FixSite(file=src, line=1, col=1, code="x", message="y"),
    )

    import pathlib

    real_open = pathlib.Path.open

    def _boom_open(self, mode="r", *args, **kwargs):
        if "w" in mode:
            raise OSError("disk full")
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", _boom_open)
    assert apply_edits(fe) is False


# ---------------------------------------------------------------------------
# describe_site
# ---------------------------------------------------------------------------


def test_describe_site_short_snippet(tmp_path: Path) -> None:
    site = FixSite(
        file=tmp_path / "a.py", line=10, col=5,
        code="unused-type-ignore-comment", message="x",
    )
    site.raw_match = "# type: ignore"
    text = describe_site(site)
    assert "a.py:10:5" in text
    assert "unused-type-ignore-comment" in text
    assert "# type: ignore" in text


def test_describe_site_long_snippet_is_truncated(tmp_path: Path) -> None:
    site = FixSite(
        file=tmp_path / "a.py", line=10, col=5,
        code="x", message="y",
    )
    site.raw_match = "x" * 100
    text = describe_site(site)
    assert "..." in text


# ---------------------------------------------------------------------------
# _collect_files
# ---------------------------------------------------------------------------


def test_collect_files_filters_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Directories in the git-tracked set are filtered out."""
    (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "fake.py").mkdir()
    # ty_cleanup imported ``get_git_tracked_files`` directly, so we must
    # patch the symbol *in ty_cleanup*, not on ``_git_utils``.
    monkeypatch.setattr(
        ty_cleanup, "get_git_tracked_files",
        lambda pattern: [tmp_path / "real.py", tmp_path / "fake.py"],
    )
    result = _collect_files()
    assert tmp_path / "real.py" in result
    assert tmp_path / "fake.py" not in result


# ---------------------------------------------------------------------------
# _build_arg_parser
# ---------------------------------------------------------------------------


def test_build_arg_parser_defaults() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args([])
    assert args.package == Path("crackerjack")
    assert args.root == Path()
    assert args.dry_run is False
    assert args.files is None


def test_build_arg_parser_explicit() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(
        ["--package", "pkg", "--root", "/tmp", "--dry-run", "--files", "a.py", "b.py"]
    )
    assert args.package == Path("pkg")
    assert args.root == Path("/tmp")
    assert args.dry_run is True
    assert args.files == [Path("a.py"), Path("b.py")]


# ---------------------------------------------------------------------------
# _restrict_to_scope
# ---------------------------------------------------------------------------


def test_restrict_to_scope_explicit_files(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("x\n", encoding="utf-8")
    sites = [
        FixSite(file=a, line=1, col=1, code="x", message="y"),
        FixSite(
            file=tmp_path / "other.py", line=1, col=1, code="x", message="y"
        ),
    ]
    filtered = _restrict_to_scope(sites, [a])
    assert len(filtered) == 1
    assert filtered[0].file == a


def test_restrict_to_scope_no_files_arg_returns_all_when_tracked_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``files_arg`` is None and tracked is empty, sites are returned as-is."""
    monkeypatch.setattr(ty_cleanup, "get_git_tracked_files", lambda pattern: [])
    sites = [
        FixSite(file=tmp_path / "a.py", line=1, col=1, code="x", message="y"),
    ]
    assert _restrict_to_scope(sites, None) == sites


def test_restrict_to_scope_filters_to_tracked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = tmp_path / "tracked.py"
    tracked.write_text("x\n", encoding="utf-8")
    monkeypatch.setattr(
        ty_cleanup, "get_git_tracked_files", lambda pattern: [tracked]
    )
    sites = [
        FixSite(file=tracked, line=1, col=1, code="x", message="y"),
        FixSite(
            file=tmp_path / "untracked.py", line=1, col=1, code="x", message="y"
        ),
    ]
    filtered = _restrict_to_scope(sites, None)
    assert len(filtered) == 1
    assert filtered[0].file == tracked


# ---------------------------------------------------------------------------
# _describe_planned_edits / _apply_all_edits
# ---------------------------------------------------------------------------


def test_describe_planned_edits_prints_sites(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "a.py"
    fe = FileEdits(path=src)
    site = FixSite(file=src, line=1, col=1, code="x", message="y")
    site.raw_match = "snippet"
    fe.add(start=0, end=8, new_text="", site=site)
    total = _describe_planned_edits({src: fe})
    captured = capsys.readouterr()
    assert total == 1
    assert "snippet" in captured.out


def test_apply_all_edits_counts_changes(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("# type: ignore\n", encoding="utf-8")
    fe = FileEdits(path=src)
    fe.add(
        start=0,
        end=src.stat().st_size,
        new_text="",
        site=FixSite(file=src, line=1, col=1, code="x", message="y"),
    )
    assert _apply_all_edits({src: fe}) == 1


def test_apply_all_edits_skips_empty(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("x\n", encoding="utf-8")
    fe = FileEdits(path=src)
    assert _apply_all_edits({src: fe}) == 0


# ---------------------------------------------------------------------------
# main — CLI integration
# ---------------------------------------------------------------------------


def test_main_package_not_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--root", str(tmp_path), "--package", "nope"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "package not found" in captured.err


def test_main_no_sites_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No ty output → ``main`` prints the no-candidates message and exits 0."""
    (tmp_path / "crackerjack").mkdir()
    fake = _fake_run_factory(stdout="")
    with patch.object(ty_cleanup.subprocess, "run", fake):
        rc = main(["--root", str(tmp_path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "No ty cleanup candidates" in captured.out


def test_main_dry_run_with_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run path prints planned edits and exits ``1`` when there are any."""
    src = tmp_path / "crackerjack"
    src.mkdir(parents=True)
    src_file = src / "mod.py"
    src_file.write_text("# type: ignore\n", encoding="utf-8")

    stdout = (
        f"{src_file.relative_to(tmp_path)}:1:1: "
        "warning[unused-type-ignore-comment] Unused directive"
    )
    fake = _fake_run_factory(stdout=stdout)

    # Skip the git-tracked file check by passing --files explicitly.
    with patch.object(ty_cleanup.subprocess, "run", fake):
        rc = main(
            [
                "--root", str(tmp_path),
                "--package", "crackerjack",
                "--dry-run",
                "--files", str(src_file),
            ]
        )
    assert rc == 1
    captured = capsys.readouterr()
    assert "dry-run" in captured.out
    # File was NOT modified.
    assert src_file.read_text(encoding="utf-8") == "# type: ignore\n"


def test_main_apply_modifies_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The non-dry-run path applies the edits and reports counts."""
    pkg = tmp_path / "crackerjack"
    pkg.mkdir()
    src_file = pkg / "mod.py"
    src_file.write_text("# type: ignore\n", encoding="utf-8")

    stdout = (
        f"{src_file.relative_to(tmp_path)}:1:1: "
        "warning[unused-type-ignore-comment] Unused directive"
    )
    fake = _fake_run_factory(stdout=stdout)

    with patch.object(ty_cleanup.subprocess, "run", fake):
        rc = main(
            [
                "--root", str(tmp_path),
                "--package", "crackerjack",
                "--files", str(src_file),
            ]
        )
    assert rc == 1
    captured = capsys.readouterr()
    assert "Applied" in captured.out
    # The directive was removed.
    new_text = src_file.read_text(encoding="utf-8")
    assert "type: ignore" not in new_text


def test_main_dry_run_with_no_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run with no resolvable sites exits ``0`` after the dry-run summary."""
    pkg = tmp_path / "crackerjack"
    pkg.mkdir()
    src_file = pkg / "mod.py"
    src_file.write_text("x = 1\n", encoding="utf-8")

    # Site at line 1 column 1 — no type: ignore present, so plan_edits
    # returns no edits.
    stdout = (
        f"{src_file.relative_to(tmp_path)}:1:1: "
        "warning[unused-type-ignore-comment] Unused"
    )
    fake = _fake_run_factory(stdout=stdout)

    with patch.object(ty_cleanup.subprocess, "run", fake):
        rc = main(
            [
                "--root", str(tmp_path),
                "--package", "crackerjack",
                "--dry-run",
                "--files", str(src_file),
            ]
        )
    assert rc == 0
    captured = capsys.readouterr()
    assert "0 change(s) would be applied" in captured.out


def test_main_dry_run_path_with_no_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """When run_ty returns sites but they all filter out via _restrict_to_scope,
    main prints the in-scope message and exits 0."""
    src = tmp_path / "crackerjack"
    src.mkdir()
    src_file = src / "mod.py"
    src_file.write_text("x = 1\n", encoding="utf-8")

    stdout = (
        f"{src_file.relative_to(tmp_path)}:1:1: "
        "warning[unused-type-ignore-comment] Unused"
    )
    fake = _fake_run_factory(stdout=stdout)

    # Pass --files pointing at a DIFFERENT file so _restrict_to_scope
    # filters everything out.
    other_file = tmp_path / "other.py"
    other_file.write_text("y\n", encoding="utf-8")
    with patch.object(ty_cleanup.subprocess, "run", fake):
        rc = main(
            [
                "--root", str(tmp_path),
                "--package", "crackerjack",
                "--files", str(other_file),
            ]
        )
    assert rc == 0
    captured = capsys.readouterr()
    assert "No ty cleanup candidates in scope" in captured.out
