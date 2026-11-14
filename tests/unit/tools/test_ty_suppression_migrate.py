"""Unit tests for ``crackerjack.tools.ty_suppression_migrate``.

The tool rewrites mypy-syntax ignore directives into ty's syntax by removing
each directive, asking ty what it now reports, and writing the answer back.
Two properties matter most and are pinned here:

* only real COMMENT tokens are touched — the same text inside a string or a
  docstring is user-visible content, not a directive;
* the column arithmetic is composed correctly — a match offset is relative to
  the comment token's own string, not to the file line, and getting it wrong
  silently eats the code that precedes a trailing comment.
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.tools.ty_suppression_migrate import (
    convert_blanket,
    find_comments,
    find_directives,
    migrate,
    strip_directives,
)


class TestFindDirectives:
    def test_finds_a_bare_directive(self) -> None:
        directives = find_directives("x = 1  # type: ignore\n")
        assert len(directives) == 1
        assert directives[0].kind == "bare"
        assert directives[0].line == 1

    def test_finds_a_bracketed_directive(self) -> None:
        directives = find_directives("x = 1  # type: ignore[assignment]\n")
        assert len(directives) == 1
        assert directives[0].kind == "bracketed"
        assert directives[0].codes == "assignment"

    def test_ignores_text_inside_a_docstring(self) -> None:
        """A docstring that mentions a directive is content, not a directive."""
        text = '"""Docs mentioning # type: ignore[assignment] for context."""\n'
        assert find_directives(text) == []

    def test_ignores_text_inside_a_string_literal(self) -> None:
        text = 'message = "use # type: ignore[assignment] here"\n'
        assert find_directives(text) == []

    def test_ignores_a_ty_syntax_directive(self) -> None:
        assert find_directives("x = 1  # ty: ignore[missing-attribute]\n") == []

    def test_reports_the_column_of_a_trailing_directive(self) -> None:
        text = "value = compute()  # type: ignore[assignment]\n"
        directives = find_directives(text)
        assert directives[0].col == len("value = compute()  ")
        assert text[directives[0].col : directives[0].end_col] == (
            "# type: ignore[assignment]"
        )


class TestStripDirectives:
    def test_removes_only_the_directive_text(self) -> None:
        """The code before a trailing comment must survive intact."""
        text = "value = compute()  # type: ignore[assignment]\n"
        directives = find_directives(text)
        stripped = strip_directives(text, {(directives[0].line, directives[0].col)})
        assert stripped == "value = compute()\n"

    def test_preserves_the_line_count(self) -> None:
        text = "a = 1  # type: ignore[assignment]\nb = 2\nc = 3\n"
        directives = find_directives(text)
        stripped = strip_directives(text, {(directives[0].line, directives[0].col)})
        assert len(stripped.splitlines()) == len(text.splitlines())

    def test_leaves_untargeted_directives_alone(self) -> None:
        text = "a = 1  # type: ignore\nb = 2  # type: ignore[assignment]\n"
        comments = find_comments(text)
        stripped = strip_directives(
            text, {(comments[0].line, comments[0].col)}, kinds=("bare",)
        )
        assert "# type: ignore[assignment]" in stripped
        assert stripped.splitlines()[0] == "a = 1"


class TestConvertBlanket:
    def test_replaces_with_a_single_rule(self) -> None:
        text = "x = 1  # type: ignore\n"
        directives = find_directives(text)
        converted = convert_blanket(
            text,
            {
                (
                    directives[0].line,
                    directives[0].col,
                ): "# ty: ignore[invalid-argument-type]"
            },
        )
        assert converted == "x = 1  # ty: ignore[invalid-argument-type]\n"

    def test_replaces_with_several_rules(self) -> None:
        text = "x = 1  # type: ignore\n"
        directives = find_directives(text)
        converted = convert_blanket(
            text,
            {(directives[0].line, directives[0].col): "# ty: ignore[a-rule, b-rule]"},
        )
        assert converted == "x = 1  # ty: ignore[a-rule, b-rule]\n"

    def test_preserves_the_code_before_the_directive(self) -> None:
        text = "value = compute()  # type: ignore\n"
        directives = find_directives(text)
        converted = convert_blanket(
            text,
            {
                (
                    directives[0].line,
                    directives[0].col,
                ): "# ty: ignore[missing-attribute]"
            },
        )
        assert converted.startswith("value = compute()  ")


class TestMigrateDeleteBracketed:
    def test_removes_bracketed_and_keeps_bare(self, tmp_path: Path) -> None:
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "mod.py").write_text(
            "a = 1  # type: ignore[assignment]\nb = 2  # type: ignore\n",
            encoding="utf-8",
        )
        report = migrate(tmp_path, mode="delete-bracketed", dry_run=False)
        assert report["deleted"] == 1
        text = (tmp_path / "pkg" / "mod.py").read_text(encoding="utf-8")
        assert "# type: ignore[assignment]" not in text
        assert "# type: ignore\n" in text

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "pkg").mkdir()
        original = "a = 1  # type: ignore[assignment]\n"
        (tmp_path / "pkg" / "mod.py").write_text(original, encoding="utf-8")
        migrate(tmp_path, mode="delete-bracketed", dry_run=True)
        assert (tmp_path / "pkg" / "mod.py").read_text(encoding="utf-8") == original


class TestMigrateConvertBlanket:
    def test_deletes_a_directive_that_hides_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "mod.py").write_text(
            "a = 1  # type: ignore\n", encoding="utf-8"
        )
        report = migrate(
            tmp_path,
            mode="convert-blanket",
            prod_dir="pkg",
            python=str(
                Path(__file__).resolve().parents[3] / ".venv" / "bin" / "python"
            ),
        )
        assert report["deleted"] == 1
        assert "# type: ignore" not in (tmp_path / "pkg" / "mod.py").read_text(
            encoding="utf-8"
        )

    def test_leaves_the_tree_parseable(self, tmp_path: Path) -> None:
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "mod.py").write_text(
            "try:\n    import optional\nexcept ImportError:\n"
            "    optional = None  # type: ignore\n",
            encoding="utf-8",
        )
        migrate(tmp_path, mode="convert-blanket", prod_dir="pkg")
        compile(
            (tmp_path / "pkg" / "mod.py").read_text(encoding="utf-8"), "mod.py", "exec"
        )


class TestProseSurvivesDirectiveRemoval:
    """A directive can be followed by prose in the same comment segment.

    ``# type: ignore[attr-defined] dynamically attached`` is one comment
    token. Removing only the directive text leaves ``dynamically attached``
    as bare code, which is a syntax error. The comment must be rebuilt from
    its parts so the prose stays a comment.
    """

    def test_trailing_prose_is_preserved_as_a_comment(self) -> None:
        text = "adapter.client = client  # type: ignore[attr-defined] dynamically attached\n"
        directives = find_directives(text)
        stripped = strip_directives(text, {(directives[0].line, directives[0].col)})
        assert stripped == "adapter.client = client  # dynamically attached\n"

    def test_trailing_prose_still_parses(self) -> None:
        text = "adapter.client = client  # type: ignore[attr-defined] dynamically attached\n"
        directives = find_directives(text)
        stripped = strip_directives(text, {(directives[0].line, directives[0].col)})
        compile(stripped, "x.py", "exec")

    def test_both_forms_keep_the_ty_directive(self) -> None:
        text = "x = 1  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]\n"
        directives = find_directives(text)
        stripped = strip_directives(text, {(directives[0].line, directives[0].col)})
        assert stripped == "x = 1  # ty: ignore[missing-attribute]\n"

    def test_stripping_bracketed_keeps_a_bare_directive(self) -> None:
        text = "x = 1  # type: ignore\n"
        comments = find_comments(text)
        stripped = strip_directives(text, {(comments[0].line, comments[0].col)})
        assert stripped == "x = 1  # type: ignore\n"


class TestNoTrailingWhitespace:
    """Removing a comment must not leave the line padded with spaces."""

    def test_trailing_comment_removal_strips_the_whitespace_before_it(self) -> None:
        text = "value = compute()  # type: ignore[assignment]\n"
        directives = find_directives(text)
        stripped = strip_directives(text, {(directives[0].line, directives[0].col)})
        assert stripped == "value = compute()\n"

    def test_kept_comment_keeps_its_leading_whitespace(self) -> None:
        text = "value = compute()  # ty: ignore[missing-attribute]\n"
        assert strip_directives(text, set()) == text


class TestDocumentedDirectivesAreNotDirectives:
    """A comment can write about a directive instead of using one.

    ``# ``# type: ignore[import-not-found]`` directive covers Mypy/Pyright``
    is prose about a directive. Rewriting it would mangle the documentation,
    so a directive inside a backtick-quoted run is not a directive.
    """

    def test_a_directive_in_backticks_is_not_found(self) -> None:
        text = "# ``# type: ignore[import-not-found]`` directive covers Mypy/Pyright\n"
        assert find_directives(text) == []

    def test_a_directive_in_backticks_is_not_rewritten(self) -> None:
        text = "# ``# type: ignore[import-not-found]`` directive covers Mypy/Pyright\n"
        comments = find_comments(text)
        assert comments[0].mypy == ()
        stripped = strip_directives(text, {(comments[0].line, comments[0].col)})
        assert stripped == text

    def test_a_real_directive_next_to_backticked_text_is_still_found(self) -> None:
        text = "x = 1  # type: ignore[assignment]  # see ``# type: ignore`` docs\n"
        directives = find_directives(text)
        assert len(directives) == 1
        assert directives[0].kind == "bracketed"
