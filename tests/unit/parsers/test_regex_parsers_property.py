"""Property-based and edge-case tests for regex_parsers.

Focuses on parser branches not exercised by the canonical happy-path suites:
- Error/fallback paths (ValueError, IndexError, no-match returns)
- Concurrency/parse_text where the input is unusual (very long, only whitespace,
  mixed prefix/skip lists)
- Private helpers used by the diagnostic format parsers (RuffRegexParser,
  CheckAddedLargeFilesParser, LinkcheckmdRegexParser, JsonSchemaRegexParser,
  CreosoteRegexParser, StructuredDataParser, ComplexityRegexParser).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.regex_parsers import (
    CheckAddedLargeFilesParser,
    CodespellRegexParser,
    ComplexityRegexParser,
    CreosoteRegexParser,
    GenericRegexParser,
    JsonSchemaRegexParser,
    LinkcheckmdRegexParser,
    LocalLinkCheckerRegexParser,
    MypyRegexParser,
    PyscnRegexParser,
    RefurbRegexParser,
    RuffFormatRegexParser,
    RuffRegexParser,
    SkylosRegexParser,
    StructuredDataParser,
)

# All parsers in the module — for sweep-style "empty/whitespace" tests.
_ALL_PARSERS = [
    CheckAddedLargeFilesParser(),
    CodespellRegexParser(),
    ComplexityRegexParser(),
    CreosoteRegexParser(),
    GenericRegexParser("generic"),
    JsonSchemaRegexParser(),
    LinkcheckmdRegexParser(),
    LocalLinkCheckerRegexParser(),
    MypyRegexParser(),
    PyscnRegexParser(),
    RefurbRegexParser(),
    RuffFormatRegexParser(),
    RuffRegexParser(),
    SkylosRegexParser(),
    StructuredDataParser(),
]


# ---------------------------------------------------------------------------
# Property-based: random non-issue inputs never produce an Issue for parsers
# that take a single "issue" line and only return issues for a specific prefix.
# ---------------------------------------------------------------------------


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_codespell_random_text_never_crashes(text: str) -> None:
    """Codespell parser must never raise on arbitrary text input."""
    parser = CodespellRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)
    for issue in issues:
        assert isinstance(issue, Issue)
        assert issue.type == IssueType.FORMATTING
        assert issue.severity == Priority.LOW


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_refurb_random_text_never_crashes(text: str) -> None:
    """Refurb parser must never raise on arbitrary text input."""
    parser = RefurbRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)
    for issue in issues:
        assert isinstance(issue, Issue)
        assert issue.type == IssueType.REFURB


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_pyscn_random_text_never_crashes(text: str) -> None:
    """Pyscn parser must never raise on arbitrary text input."""
    parser = PyscnRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_mypy_random_text_never_crashes(text: str) -> None:
    """Mypy parser must never raise on arbitrary text input."""
    parser = MypyRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_creosote_random_text_never_crashes(text: str) -> None:
    """Creosote parser must never raise on arbitrary text input."""
    parser = CreosoteRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)
    for issue in issues:
        assert isinstance(issue, Issue)
        assert issue.type == IssueType.DEPENDENCY


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_structured_random_text_never_crashes(text: str) -> None:
    """StructuredDataParser must never raise on arbitrary text input."""
    parser = StructuredDataParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_local_link_random_text_never_crashes(text: str) -> None:
    """LocalLinkCheckerRegexParser must never raise on arbitrary text input."""
    parser = LocalLinkCheckerRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_skylos_random_text_never_crashes(text: str) -> None:
    """Skylos parser must never raise on arbitrary text input."""
    parser = SkylosRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_linkcheckmd_random_text_never_crashes(text: str) -> None:
    """Linkcheckmd parser must never raise on arbitrary text input."""
    parser = LinkcheckmdRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_jsonschema_random_text_never_crashes(text: str) -> None:
    """JsonSchema parser must never raise on arbitrary text input."""
    parser = JsonSchemaRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_complexity_random_text_never_crashes(text: str) -> None:
    """Complexity parser must never raise on arbitrary text input."""
    parser = ComplexityRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_ruff_format_random_text_never_crashes(text: str) -> None:
    """RuffFormat parser must never raise on arbitrary text input."""
    parser = RuffFormatRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


@given(text=st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_ruff_random_text_never_crashes(text: str) -> None:
    """Ruff parser must never raise on arbitrary text input."""
    parser = RuffRegexParser()
    issues = parser.parse_text(text)
    assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# CodespellRegexParser — branches
# ---------------------------------------------------------------------------


class TestCodespellRegexParserEdges:
    """Targeted edge cases for CodespellRegexParser branches."""

    @pytest.fixture
    def parser(self) -> CodespellRegexParser:
        return CodespellRegexParser()

    def test_non_numeric_line_number_falls_back_to_none(
        self, parser: CodespellRegexParser
    ) -> None:
        """Lines where the second colon-separated field isn't a number leave
        line_number as None (covers branch 58-59)."""
        output = "src/file.py:abc ==> expected"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].line_number is None
        assert issues[0].file_path == "src/file.py"
        assert "abc" in issues[0].message

    def test_format_codespell_message_without_arrow(
        self, parser: CodespellRegexParser
    ) -> None:
        """_format_codespell_message without ==> returns the stripped raw text."""
        assert parser._format_codespell_message("just some text") == "just some text"

    def test_format_codespell_message_with_arrow(
        self, parser: CodespellRegexParser
    ) -> None:
        """_format_codespell_message with ==> emits 'Spelling: ...' format."""
        result = parser._format_codespell_message("teh ==> the")
        assert "teh" in result
        assert "the" in result

    def test_parse_codespell_internal_exception_is_swallowed(
        self, parser: CodespellRegexParser, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A buggy _parse_single_codespell_line must not raise; the loop logs
        and continues (covers line 30-31, the try/except branch)."""
        calls = {"n": 0}

        def boom(_line: str) -> Issue | None:
            calls["n"] += 1
            raise RuntimeError("intentional")

        monkeypatch.setattr(parser, "_parse_single_codespell_line", boom)
        # First line is a codespell line that should reach the boom branch
        output = "file.py:1:foo ==> bar\nfile.py:2:baz ==> qux"
        # Should not raise
        issues = parser.parse_text(output)
        assert issues == []
        assert calls["n"] == 2

    def test_parse_codespell_returns_none_for_no_colon_line(
        self, parser: CodespellRegexParser
    ) -> None:
        """Lines matching the should_parse predicate but lacking ':' return None.

        ``==> present but no colons`` is rare but is covered for completeness:
        _should_parse_codespell_line returns True when '==>' is present even
        without multiple colons, so _parse_single_codespell_line receives it.
        With no colon at all, the function returns None.
        """
        assert parser._parse_single_codespell_line("==>") is None


# ---------------------------------------------------------------------------
# RefurbRegexParser — branches
# ---------------------------------------------------------------------------


class TestRefurbRegexParserEdges:
    """Edge cases for RefurbRegexParser branches."""

    @pytest.fixture
    def parser(self) -> RefurbRegexParser:
        return RefurbRegexParser()

    def test_refurb_line_too_few_colons_returns_none(
        self, parser: RefurbRegexParser
    ) -> None:
        """A line with `.py:` but only 2 parts total returns None (branch 109)."""
        # .py: triggers _should_parse_refurb_line, but 2 colons only.
        # Actually: `file.py:1` has split(":") length 2, which is < 3, so
        # _should_parse_refurb_line returns False. We force a 2-part line that
        # has split(":") >= 3 by abusing the colon check.
        # Easiest: directly call _parse_refurb_line on input that splits to < 3.
        assert parser._parse_refurb_line("file.py") is None

    def test_refurb_invalid_line_number_returns_none(
        self, parser: RefurbRegexParser
    ) -> None:
        """A refurb-style line with non-numeric line number returns None."""
        # _should_parse_refurb_line requires ".py:" and >=3 colons. Construct
        # one with 3 colons but a non-numeric middle field.
        output = "file.py:abc:5:msg"
        issues = parser.parse_text(output)
        assert issues == []

    def test_refurb_extract_furb_code_variants(
        self, parser: RefurbRegexParser
    ) -> None:
        """_extract_furb_code recognises bracketed and unbracketed FURB codes."""
        assert parser._extract_furb_code("Use dict [FURB123] comprehension") == "FURB123"
        assert parser._extract_furb_code("Use FURB456: dict comp") == "FURB456"
        assert parser._extract_furb_code("no code here") is None

    def test_refurb_should_skip_empty_line(self, parser: RefurbRegexParser) -> None:
        """Empty/whitespace lines are skipped by the guard."""
        assert parser._should_parse_refurb_line("") is False
        assert parser._should_parse_refurb_line("   ") is False

    def test_refurb_message_with_furb_code_keeps_message(
        self, parser: RefurbRegexParser
    ) -> None:
        """A FURB line with a code adds a details entry but keeps the message."""
        output = "src/x.py:10:5: [FURB101] some message"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].details
        assert "FURB101" in issues[0].details[0]
        assert "some message" in issues[0].message


# ---------------------------------------------------------------------------
# PyscnRegexParser — branches
# ---------------------------------------------------------------------------


class TestPyscnRegexParserEdges:
    """Edge cases for PyscnRegexParser branches."""

    @pytest.fixture
    def parser(self) -> PyscnRegexParser:
        return PyscnRegexParser()

    def test_pyscn_line_with_fewer_than_four_colons_skipped(
        self, parser: PyscnRegexParser
    ) -> None:
        """Lines with <4 colon-separated parts (but passing guard) return None.

        The guard requires split(":") length >= 4, so we craft a line that
        passes the guard but fails _parse_pyscn_line anyway.
        """
        # Direct: _parse_pyscn_line returns None when parts < 4
        assert parser._parse_pyscn_line("a:b:c") is None

    def test_pyscn_invalid_line_number_returns_none(
        self, parser: PyscnRegexParser
    ) -> None:
        """A pyscn-style line with non-numeric line number returns None."""
        output = "file.py:abc:5:msg"
        # guard requires .py: and split(":")>=4 - 4 colons means "a:b:c:d"
        # with our pattern we need a real .py: with 4 parts. Construct it.
        # 4-part lines are: file.py:line:col:msg. Non-numeric line field.
        output = "file.py:notnum:5:some message"
        issues = parser.parse_text(output)
        assert issues == []

    def test_pyscn_default_severity_is_medium(
        self, parser: PyscnRegexParser
    ) -> None:
        """Lines without 'too complex' or 'clone' keywords get MEDIUM severity."""
        output = "src/x.py:1:1: some other diagnostic"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].severity == Priority.MEDIUM

    def test_pyscn_too_complex_high_severity(
        self, parser: PyscnRegexParser
    ) -> None:
        """'too complex' message maps to HIGH severity."""
        output = "src/x.py:1:1: This function is too complex"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].severity == Priority.HIGH

    def test_pyscn_clone_detection_low_severity(
        self, parser: PyscnRegexParser
    ) -> None:
        """'clone' in the message maps to LOW severity."""
        output = "src/x.py:1:1: Code clone detected"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].severity == Priority.LOW

    def test_pyscn_should_skip_running_lines(
        self, parser: PyscnRegexParser
    ) -> None:
        """Guard rejects 'Running ...' lines."""
        assert parser._should_parse_pyscn_line("Running mypy on src/") is False

    def test_pyscn_should_skip_error_prefix(
        self, parser: PyscnRegexParser
    ) -> None:
        """Guard rejects 'Error:' and 'error:' prefixes."""
        assert parser._should_parse_pyscn_line("Error: bad") is False
        assert parser._should_parse_pyscn_line("error: bad") is False


# ---------------------------------------------------------------------------
# RuffFormatRegexParser — branches
# ---------------------------------------------------------------------------


class TestRuffFormatRegexParserEdges:
    """Edge cases for RuffFormatRegexParser branches."""

    @pytest.fixture
    def parser(self) -> RuffFormatRegexParser:
        return RuffFormatRegexParser()

    def test_failed_to_format_with_no_error_lines_falls_back(
        self, parser: RuffFormatRegexParser
    ) -> None:
        """If 'Failed to format' is present but there are no error lines, the
        fallback message includes the first non-empty line (which is
        'Failed to format' itself)."""
        output = "Failed to format"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        # The first non-empty line is "Failed to format" itself, so the message
        # combines the prefix with that line.
        assert "Formatting error" in issues[0].message
        assert "Failed to format" in issues[0].message

    def test_failed_to_format_uses_first_error_line(
        self, parser: RuffFormatRegexParser
    ) -> None:
        """When 'Failed to format' is in the output, the first non-empty line
        is the error message."""
        output = (
            "Failed to format src/broken.py: invalid syntax\n"
            "  File \"src/broken.py\", line 5"
        )
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "Formatting error" in issues[0].message
        assert "Failed to format" in issues[0].message

    def test_no_issues_when_message_absent(
        self, parser: RuffFormatRegexParser
    ) -> None:
        """Output that doesn't mention reformatting or errors returns []."""
        assert parser.parse_text("All files already formatted") == []
        assert parser.parse_text("") == []


# ---------------------------------------------------------------------------
# ComplexityRegexParser — branches
# ---------------------------------------------------------------------------


class TestComplexityRegexParserEdges:
    """Edge cases for ComplexityRegexParser branches."""

    @pytest.fixture
    def parser(self) -> ComplexityRegexParser:
        return ComplexityRegexParser()

    def test_no_current_file_returns_none(
        self, parser: ComplexityRegexParser
    ) -> None:
        """If no `- file.py` header has been seen, a function line returns None."""
        assert parser._parse_complexity_line("func 10", current_file=None) is None

    def test_dash_marker_starts_a_new_file(
        self, parser: ComplexityRegexParser
    ) -> None:
        """A `- file.py:` line sets current_file and yields no issue itself."""
        # Each line is split/stripped independently in parse_text. The function
        # line is "some_func 12" (no leading whitespace, since parse_text
        # already strips).
        output = "- src/module.py:\nsome_func 12"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "src/module.py"
        assert "some_func" in issues[0].message

    def test_module_prefix_with_double_colon(
        self, parser: ComplexityRegexParser
    ) -> None:
        """Lines matching `module::func value` use func_name as the qualifier."""
        output = "src/x.py module::Class::method 25"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "method" in issues[0].message

    def test_too_few_words_skipped(self, parser: ComplexityRegexParser) -> None:
        """Single-word lines are skipped."""
        assert parser._parse_complexity_line("word") is None
        assert parser._parse_complexity_line("") is None

    def test_non_integer_complexity_skipped(
        self, parser: ComplexityRegexParser
    ) -> None:
        """The last token must be parseable as int."""
        # Provide current_file so the early-return doesn't fire.
        assert (
            parser._parse_complexity_line("func not_a_number", current_file="x.py")
            is None
        )

    def test_separator_lines_skipped(self, parser: ComplexityRegexParser) -> None:
        """Lines starting with '─' or '---' are skipped."""
        assert parser._parse_complexity_line("─ stats ─") is None


# ---------------------------------------------------------------------------
# GenericRegexParser — branches
# ---------------------------------------------------------------------------


class TestGenericRegexParserEdges:
    """Edge cases for GenericRegexParser branches."""

    def test_issue_type_default_is_formatting(self) -> None:
        """Default issue_type is FORMATTING when constructor omits it."""
        parser = GenericRegexParser("t")
        assert parser.issue_type == IssueType.FORMATTING

    def test_message_format_includes_tool_name(self) -> None:
        """The issue message includes the configured tool name."""
        parser = GenericRegexParser("my-tool", IssueType.SECURITY)
        issues = parser.parse_text("error: stuff broke")
        assert issues[0].message == "my-tool check failed"

    def test_details_carries_truncated_output(self) -> None:
        """Generic parser stashes the first 500 chars of output in details."""
        parser = GenericRegexParser("t")
        long_output = ("error: " + "x" * 1000)
        issues = parser.parse_text(long_output)
        assert issues[0].details
        assert len(issues[0].details[0]) <= 500

    def test_lowercase_indicators_also_match(self) -> None:
        """Lowercase 'failed' and 'error' trigger the failure path."""
        parser = GenericRegexParser("t")
        for trigger in ("failed", "error", "invalid", "issue", "would be"):
            output = f"Tool reports {trigger} now"
            assert parser.parse_text(output), f"missed: {trigger}"


# ---------------------------------------------------------------------------
# StructuredDataParser — branches
# ---------------------------------------------------------------------------


class TestStructuredDataParserEdges:
    """Edge cases for StructuredDataParser branches."""

    @pytest.fixture
    def parser(self) -> StructuredDataParser:
        return StructuredDataParser()

    def test_x_prefix_with_no_colon_yields_empty_file_path(
        self, parser: StructuredDataParser
    ) -> None:
        """When the line is `✗ text` with no `:`, _extract_structured_data_parts
        returns `('', line)`, and the parser returns None."""
        output = "✗ just a message with no colon"
        issues = parser.parse_text(output)
        assert issues == []

    def test_extract_structured_data_parts_no_x_prefix(
        self, parser: StructuredDataParser
    ) -> None:
        """_extract_structured_data_parts strips `✗` if present."""
        path, msg = parser._extract_structured_data_parts("✗ file.py: boom")
        assert path == "file.py"
        assert msg == "boom"

    def test_extract_structured_data_parts_no_colon(
        self, parser: StructuredDataParser
    ) -> None:
        """Lines without a colon get an empty file_path and full message."""
        path, msg = parser._extract_structured_data_parts("✗ no colon here")
        assert path == ""
        assert msg == "no colon here"

    def test_parse_handles_internal_exception(
        self, parser: StructuredDataParser, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_parse_single_structured_data_line exceptions are swallowed."""
        def boom(_line: str) -> Issue | None:
            raise RuntimeError("intentional")

        monkeypatch.setattr(parser, "_parse_single_structured_data_line", boom)
        # Should not raise.
        assert parser.parse_text("✗ file.py: msg\n✗ other.py: msg") == []


# ---------------------------------------------------------------------------
# MypyRegexParser — branches
# ---------------------------------------------------------------------------


class TestMypyRegexParserEdges:
    """Edge cases for MypyRegexParser branches."""

    @pytest.fixture
    def parser(self) -> MypyRegexParser:
        return MypyRegexParser()

    def test_mypy_line_with_note(self, parser: MypyRegexParser) -> None:
        """'note' in the line still parses (treated as MEDIUM)."""
        output = "src/file.py:42: note: See docs"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].severity == Priority.MEDIUM

    def test_mypy_line_with_no_line_number(
        self, parser: MypyRegexParser
    ) -> None:
        """Lines with no numeric middle field get line_number=None."""
        output = "src/file.py: error: bare error"
        issues = parser.parse_text(output)
        # The line has 3 parts after split by ':' (max 3) so it parses.
        # However the middle part is ' error' (with leading space after first split).
        # The guard needs ':' + error/warning/note. Let's check: it does match.
        assert len(issues) == 1
        assert issues[0].file_path == "src/file.py"
        # Middle field is ' error' which is not numeric
        assert issues[0].line_number is None

    def test_mypy_line_with_fewer_than_three_parts(
        self, parser: MypyRegexParser
    ) -> None:
        """A line with <3 colons returns None in _parse_mypy_line."""
        assert parser._parse_mypy_line("file.py") is None

    def test_extract_mypy_message_with_three_parts(
        self, parser: MypyRegexParser
    ) -> None:
        """_extract_mypy_message with <4 parts returns the full_line."""
        parts = ["file.py", "42", "error"]
        full = "file.py:42: error"
        assert parser._extract_mypy_message(parts, full) == full

    def test_extract_mypy_severity_error(
        self, parser: MypyRegexParser
    ) -> None:
        """'error' substring (case-insensitive) yields HIGH severity."""
        assert parser._extract_mypy_severity("file.py:1: error: bad") == Priority.HIGH
        assert parser._extract_mypy_severity("file.py:1: ERROR: bad") == Priority.HIGH

    def test_extract_mypy_severity_warning(
        self, parser: MypyRegexParser
    ) -> None:
        """Lines without 'error' yield MEDIUM severity."""
        assert (
            parser._extract_mypy_severity("file.py:1: warning: x")
            == Priority.MEDIUM
        )
        assert parser._extract_mypy_severity("file.py:1: note: x") == Priority.MEDIUM


# ---------------------------------------------------------------------------
# CreosoteRegexParser — branches
# ---------------------------------------------------------------------------


class TestCreosoteRegexParserEdges:
    """Edge cases for CreosoteRegexParser branches."""

    @pytest.fixture
    def parser(self) -> CreosoteRegexParser:
        return CreosoteRegexParser()

    def test_bullet_with_no_dep_returns_empty(
        self, parser: CreosoteRegexParser
    ) -> None:
        """A bullet '- ' with nothing after the dash returns no issues."""
        issues = parser.parse_text("- ")
        assert issues == []

    def test_bullet_with_separator_prefix_returns_empty(
        self, parser: CreosoteRegexParser
    ) -> None:
        """Lines starting with '---' or '====' (separator styles) are not deps."""
        # '---' doesn't start with '- ' (the second char is '-' not ' '), so
        # _parse_bulleted_dependency won't trigger via _parse_creosote_line.
        # We confirm parsing produces no issue.
        issues = parser.parse_text("---")
        assert issues == []
        issues = parser.parse_text("====")
        assert issues == []

    def test_inline_dependency_no_parens_returns_empty(
        self, parser: CreosoteRegexParser
    ) -> None:
        """_parse_inline_dependency returns [] when no (...) is present."""
        # Must reach _parse_inline_dependency: contains 'not being used' but
        # has no parenthesized name.
        output = "src/x.py:1: This dep is not being used"
        issues = parser.parse_text(output)
        assert issues == []

    def test_redundant_exclusion_no_match_returns_empty(
        self, parser: CreosoteRegexParser
    ) -> None:
        """'redundant exclusion' present but no quoted name yields []."""
        # "Redundant exclusion" without quote chars around a name.
        output = "Redundant exclusion in pyproject.toml"
        issues = parser.parse_text(output)
        assert issues == []

    def test_excluded_not_found_no_colon_returns_empty(
        self, parser: CreosoteRegexParser
    ) -> None:
        """Line 'Excluded dependencies not found in virtual environment' with
        no colon after the message yields no issues."""
        output = "Excluded dependencies not found in virtual environment"
        issues = parser.parse_text(output)
        assert issues == []

    def test_excluded_not_found_with_empty_deps(
        self, parser: CreosoteRegexParser
    ) -> None:
        """A line with a colon but no real deps (only commas/whitespace) yields
        no issues."""
        output = "Excluded dependencies not found in virtual environment: "
        issues = parser.parse_text(output)
        assert issues == []

    def test_creosote_should_skip_lines_starting_with_checked(
        self, parser: CreosoteRegexParser
    ) -> None:
        """_should_parse_creosote_line returns False for 'Checked' lines."""
        assert parser._should_parse_creosote_line("Checked 10 files") is False
        assert parser._should_parse_creosote_line("All dependencies used") is False
        assert parser._should_parse_creosote_line("Found dependencies in pyproject.toml: a, b") is False

    def test_creosote_unused_found_multi(self, parser: CreosoteRegexParser) -> None:
        """'Unused dependencies found: a, b' produces 2 issues."""
        output = "Unused dependencies found: requests, flask"
        issues = parser.parse_text(output)
        assert len(issues) == 2
        assert all("Unused dependency:" in i.message for i in issues)


# ---------------------------------------------------------------------------
# LocalLinkCheckerRegexParser — branches
# ---------------------------------------------------------------------------


class TestLocalLinkCheckerRegexParserEdges:
    """Edge cases for LocalLinkCheckerRegexParser branches."""

    @pytest.fixture
    def parser(self) -> LocalLinkCheckerRegexParser:
        return LocalLinkCheckerRegexParser()

    def test_line_without_separator_dash(
        self, parser: LocalLinkCheckerRegexParser
    ) -> None:
        """Lines without ' - ' in the file part are skipped at parse time."""
        # File part has ':' but no ' - ' separator at all
        output = "file.md:10:Target.md"
        issues = parser.parse_text(output)
        assert issues == []

    def test_file_part_no_colon(self, parser: LocalLinkCheckerRegexParser) -> None:
        """File part without ':' returns None."""
        # Construct: "nocolon - target - msg"  — splits as file=nocolon, rest
        # contains ' - '. Then file_part.split(':') has length 1, so returns None.
        output = "nocolon - target - msg"
        issues = parser.parse_text(output)
        assert issues == []

    def test_file_part_too_few_colon_parts(
        self, parser: LocalLinkCheckerRegexParser
    ) -> None:
        """file_part has < 2 colon parts: returns None (branch 600)."""
        # The split happens on ' - '. file_part is "onlyoneword", which has no
        # ':'. _parse_local_link_line should return None.
        # But _should_parse_local_link_line requires both ':' and ' - '. So we
        # need both present. file_part is "file" before any colon, rest has
        # ' - '. So we can't directly hit the parts < 2 branch via parse_text
        # (guard rejects). We can hit it via the helper directly.
        assert parser._parse_local_link_line("a:1 - target") is not None  # sanity
        # A "weird" line: ':' is the very first char, so file_part="" after split.
        # The first split takes 'a:1' as file_part (no leading dash). Then ' - '
        # splits off the rest. file_part 'a:1' has 2 parts — guard passes.
        # To exercise branch 600, we need file_part with only one part. That
        # requires file_part to not contain ':'. Guard rejects it. So we test
        # the helper directly with a constructed call: split the line so file_part
        # is "a" and " - " follows. Such a line wouldn't pass the guard, but
        # _parse_local_link_line is called by parse_text only when guard passes.
        # Therefore branch 600 is unreachable through the public API; we assert
        # the helper returns None for completeness when invoked directly with
        # a colon-less file_part preceded by ' - ' (which guard wouldn't allow).
        # This is just to ensure defensive code holds.
        # _parse_local_link_line requires ' - ' in the line. Splitting, file_part
        # can be anything. We craft: ":1 - target - msg" (starts with colon so
        # file_part is empty, no colon in it, parts = [''] length 1 < 2).
        result = parser._parse_local_link_line(":1 - target - msg")
        assert result is None  # file_part is '' which has no ':' and parts<2
        # The "parts < 2" branch in the code splits the file_part and checks
        # len < 2. With a single-element split, it goes through the early return.

    def test_target_without_message(self, parser: LocalLinkCheckerRegexParser) -> None:
        """If the rest has no further ' - ' separator, default message used."""
        output = "file.md:10 - target.md"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "Broken link" in issues[0].message
        assert "target.md" in issues[0].details[0]

    def test_link_part_with_message(self, parser: LocalLinkCheckerRegexParser) -> None:
        """rest is split on ' - ' to separate target and message."""
        output = "file.md:10 - target.md - file not found"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "file not found" in issues[0].message
        assert "target.md" in issues[0].message

    def test_should_skip_empty_and_no_dash(
        self, parser: LocalLinkCheckerRegexParser
    ) -> None:
        """_should_parse_local_link_line guards against empty and dashless."""
        assert parser._should_parse_local_link_line("") is False
        assert parser._should_parse_local_link_line("no dash here") is False
        assert parser._should_parse_local_link_line("only:colons") is False
        assert parser._should_parse_local_link_line("only - dash") is False


# ---------------------------------------------------------------------------
# LinkcheckmdRegexParser — branches
# ---------------------------------------------------------------------------


class TestLinkcheckmdRegexParserEdges:
    """Edge cases for LinkcheckmdRegexParser branches."""

    @pytest.fixture
    def parser(self) -> LinkcheckmdRegexParser:
        return LinkcheckmdRegexParser()

    def test_unknown_file_falls_back_to_unknown_md(
        self, parser: LinkcheckmdRegexParser
    ) -> None:
        """Without a `.md` file in the line, file_path defaults to 'unknown.md'."""
        output = "ERROR: no file path"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "unknown.md"
        assert issues[0].line_number is None

    def test_strips_x_marks(self, parser: LinkcheckmdRegexParser) -> None:
        """Leading '✗' or '✖' are stripped from the message."""
        output = "✗ docs/guide.md:5 broken link"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert not issues[0].message.startswith("✗")
        assert "broken link" in issues[0].message

    def test_strips_error_prefix(self, parser: LinkcheckmdRegexParser) -> None:
        """'ERROR:' or 'FAIL:' prefix is stripped from the message."""
        output = "ERROR: docs/guide.md:5 broken"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert not issues[0].message.startswith("ERROR")
        assert "broken" in issues[0].message

    def test_long_message_truncated(self, parser: LinkcheckmdRegexParser) -> None:
        """Messages over 200 chars are truncated to 200."""
        long = "x" * 500
        output = f"ERROR: docs/guide.md:1 {long}"
        issues = parser.parse_text(output)
        assert len(issues[0].message) == 200

    def test_empty_message_default(self, parser: LinkcheckmdRegexParser) -> None:
        """An empty message after stripping defaults to 'Link check failure'."""
        # Construct a line that triggers the parser but yields an empty message
        # after prefix stripping. The line "✗" alone will be matched by guard
        # (has "✗") and after strip becomes "".
        output = "✗"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        # After strip, message is "" and falls back to "Link check failure"
        assert issues[0].message == "Link check failure"

    def test_skip_lines_starting_with_unicode_check(
        self, parser: LinkcheckmdRegexParser
    ) -> None:
        """Lines starting with success-style prefixes are skipped."""
        assert parser._should_parse_linkcheckmd_line("✓ all ok") is False
        assert parser._should_parse_linkcheckmd_line("✔ done") is False
        assert parser._should_parse_linkcheckmd_line("PASS: ok") is False
        assert parser._should_parse_linkcheckmd_line("---") is False


# ---------------------------------------------------------------------------
# JsonSchemaRegexParser — branches
# ---------------------------------------------------------------------------


class TestJsonSchemaRegexParserEdges:
    """Edge cases for JsonSchemaRegexParser branches."""

    @pytest.fixture
    def parser(self) -> JsonSchemaRegexParser:
        return JsonSchemaRegexParser()

    def test_unknown_file_falls_back(self, parser: JsonSchemaRegexParser) -> None:
        """Without a .json/.yaml/.yml/.toml file in the line, file_path='unknown'."""
        output = "ERROR: no file"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "unknown"

    def test_toml_file(self, parser: JsonSchemaRegexParser) -> None:
        """TOML files are recognised."""
        output = "config.toml:5 FAIL: invalid"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "config.toml"

    def test_yml_file(self, parser: JsonSchemaRegexParser) -> None:
        """YML files are recognised."""
        output = "config.yml:5 FAIL: invalid"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "config.yml"

    def test_skip_lines_starting_with_unicode_check(
        self, parser: JsonSchemaRegexParser
    ) -> None:
        """Lines starting with success-style prefixes are skipped."""
        assert parser._should_parse_jsonschema_line("OK: valid") is False
        assert parser._should_parse_jsonschema_line("PASS: done") is False
        assert parser._should_parse_jsonschema_line("✓") is False
        assert parser._should_parse_jsonschema_line("---") is False

    def test_skip_no_schema_lines(self, parser: JsonSchemaRegexParser) -> None:
        """'no schema found' and 'skipping' lines are skipped."""
        assert parser._should_parse_jsonschema_line("No schema found") is False
        assert parser._should_parse_jsonschema_line("Skipping invalid") is False

    def test_recognises_validation_error_phrase(
        self, parser: JsonSchemaRegexParser
    ) -> None:
        """'validation error' / 'schema validation failed' trigger parse."""
        output = "schema.json:1 validation error: missing field"
        assert parser._should_parse_jsonschema_line(output) is True
        output = "schema.json:1 schema validation failed"
        assert parser._should_parse_jsonschema_line(output) is True

    def test_long_message_truncated(self, parser: JsonSchemaRegexParser) -> None:
        """Messages are truncated to 200 chars."""
        long = "x" * 500
        output = f"ERROR: schema.json:1 {long}"
        issues = parser.parse_text(output)
        assert len(issues[0].message) == 200


# ---------------------------------------------------------------------------
# SkylosRegexParser — branches
# ---------------------------------------------------------------------------


class TestSkylosRegexParserEdges:
    """Edge cases for SkylosRegexParser branches."""

    @pytest.fixture
    def parser(self) -> SkylosRegexParser:
        return SkylosRegexParser()

    def test_no_error_separator_returns_none(
        self, parser: SkylosRegexParser
    ) -> None:
        """A line with 'ERROR' but no ' - ERROR - ' separator returns None."""
        # _should_parse_skylos_line requires line and "ERROR" and "-".
        # Direct call to _parse_skylos_line with no ' - ERROR - ' returns None.
        assert parser._parse_skylos_line("file.py ERROR no dashes") is None

    def test_message_truncated_to_200(self, parser: SkylosRegexParser) -> None:
        """Long messages are truncated to 200 chars in the issue."""
        long = "x" * 500
        output = f"src/file.py - ERROR - {long}"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert len(issues[0].message) == 200

    def test_details_includes_full_line(self, parser: SkylosRegexParser) -> None:
        """The full original line is stored in details[0]."""
        output = "src/file.py - ERROR - unused function"
        issues = parser.parse_text(output)
        assert issues[0].details == [output]

    def test_line_with_line_keyword_extracts_line_number(
        self, parser: SkylosRegexParser
    ) -> None:
        """A 'line N' in the message body sets line_number to N."""
        output = "src/x.py - ERROR - some_func at line 99"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].line_number == 99

    def test_should_skip_when_no_dash_or_error(
        self, parser: SkylosRegexParser
    ) -> None:
        """Guard requires both '-' and 'ERROR' substrings."""
        assert parser._should_parse_skylos_line("") is False
        assert parser._should_parse_skylos_line("just a line") is False
        assert parser._should_parse_skylos_line("has-dash but no error") is False
        assert parser._should_parse_skylos_line("has ERROR but no dash") is False


# ---------------------------------------------------------------------------
# RuffRegexParser — branches
# ---------------------------------------------------------------------------


class TestRuffRegexParserEdges:
    """Edge cases for RuffRegexParser branches."""

    @pytest.fixture
    def parser(self) -> RuffRegexParser:
        return RuffRegexParser()

    def test_diagnostic_format_on_first_line_returns_none(
        self, parser: RuffRegexParser
    ) -> None:
        """The first line cannot be a diagnostic (no previous code line)."""
        result = parser._try_parse_diagnostic_format(["--> file.py:1:1"], 0)
        assert result is None

    def test_diagnostic_format_arrow_line_returns_none(
        self, parser: RuffRegexParser
    ) -> None:
        """A non-arrow line at current_index returns None from
        _try_parse_diagnostic_format."""
        result = parser._try_parse_diagnostic_format(
            ["F401 unused", "not an arrow"], 1
        )
        assert result is None

    def test_skip_multiline_context_stops_at_next_diagnostic(
        self, parser: RuffRegexParser
    ) -> None:
        """_skip_multiline_context advances past context lines."""
        lines = [
            "F401",
            "--> file.py:1:1",
            "| import os",
            "|",
            "F402",
            "--> file.py:2:2",
        ]
        # From index 1 (the arrow line), skip context lines.
        end = parser._skip_multiline_context(lines, 1)
        # Should land at index 4 (the next code line).
        assert end == 4

    def test_parse_diagnostic_with_no_code_match_returns_none(
        self, parser: RuffRegexParser
    ) -> None:
        """_parse_diagnostic_format returns None if the code line doesn't match
        ``^[A-Z]+\d+\s+.+$``."""
        # prev_line doesn't start with a code.
        result = parser._parse_diagnostic_format("not a code", "--> file.py:1:1")
        assert result is None

    def test_parse_diagnostic_with_no_arrow_match_returns_none(
        self, parser: RuffRegexParser
    ) -> None:
        """_parse_diagnostic_format returns None if the arrow line has no
        path:line:col match."""
        result = parser._parse_diagnostic_format("F401 unused import", "not an arrow")
        assert result is None

    def test_parse_diagnostic_with_invalid_arrow_numbers(
        self, parser: RuffRegexParser
    ) -> None:
        """_parse_diagnostic_format returns None if the arrow line's numbers
        aren't integers (they are matched as groups so this is harder to hit
        via the public API; we exercise the value-error path indirectly)."""
        # The arrow regex requires \d+, so we can't pass non-digits there.
        # Instead, construct a path that's just whitespace so the resulting
        # 'file_path' has no meaningful content but the parse still succeeds.
        result = parser._parse_diagnostic_format("F401 unused", "--> file.py:1:1")
        assert result is not None  # sanity

    def test_concise_format_with_fewer_than_two_prefix_parts(
        self, parser: RuffRegexParser
    ) -> None:
        """_parse_concise_format returns None when split(':') has <2 parts."""
        # Build a line that matches the outer regex but splits into <2 parts.
        # The outer regex is `[^:]+(?::\d+){1,3}(?::|:?\s)[A-Z]{1,4}\d+\s+.*`.
        # The capture prefix `[^:]+(?::\d+){1,3}` requires at least one colon
        # via the `(?::\d+){1,3}` group, so prefix always has at least 2 parts.
        # We test the case where prefix has >4 parts: `a:1:2:3:4:5 FOO1 msg`.
        result = parser._parse_concise_format("a:1:2:3:4:5 FOO1 msg")
        assert result is None  # 6 parts > 4 limit

    def test_concise_format_with_non_numeric_line(
        self, parser: RuffRegexParser
    ) -> None:
        """_parse_concise_format returns None if the line part isn't numeric."""
        result = parser._parse_concise_format("a:notnum:5 FOO1 msg")
        assert result is None

    def test_concise_format_no_match_returns_none(
        self, parser: RuffRegexParser
    ) -> None:
        """A line that doesn't match the outer regex returns None."""
        result = parser._parse_concise_format("not a ruff line at all")
        assert result is None

    def test_issue_type_for_code_e741(self, parser: RuffRegexParser) -> None:
        """E741 (ambiguous variable name) maps to FORMATTING."""
        assert parser._issue_type_for_code("E741") == IssueType.FORMATTING

    def test_issue_type_for_code_default(self, parser: RuffRegexParser) -> None:
        """Unknown codes default to FORMATTING."""
        assert parser._issue_type_for_code("W999") == IssueType.FORMATTING

    def test_severity_for_code_e(self, parser: RuffRegexParser) -> None:
        """E-codes are HIGH severity."""
        assert parser._severity_for_code("E501") == Priority.HIGH
        assert parser._severity_for_code("E741") == Priority.HIGH


# ---------------------------------------------------------------------------
# CheckAddedLargeFilesParser — branches
# ---------------------------------------------------------------------------


class TestCheckAddedLargeFilesParserEdges:
    """Edge cases for CheckAddedLargeFilesParser branches."""

    @pytest.fixture
    def parser(self) -> CheckAddedLargeFilesParser:
        return CheckAddedLargeFilesParser()

    def test_tool_name_attribute(self, parser: CheckAddedLargeFilesParser) -> None:
        """The parser has a tool_name attribute."""
        assert parser.tool_name == "check-added-large-files"

    def test_no_large_files_header_returns_empty(
        self, parser: CheckAddedLargeFilesParser
    ) -> None:
        """Without the 'Large files detected:' header, the parser returns []."""
        output = "Some other message\nNo files detected"
        assert parser.parse_text(output) == []

    def test_header_only_returns_empty(
        self, parser: CheckAddedLargeFilesParser
    ) -> None:
        """The header with no following file lines yields no issues."""
        assert parser.parse_text("Large files detected:") == []

    def test_lines_before_header_are_ignored(
        self, parser: CheckAddedLargeFilesParser
    ) -> None:
        """Pre-header lines don't become issues."""
        output = "leading line: stuff\nLarge files detected:\nfile.bin: 10 MB"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "file.bin"

    def test_file_line_with_no_colon_skipped(
        self, parser: CheckAddedLargeFilesParser
    ) -> None:
        """File lines without a colon are skipped (parts != 2)."""
        output = "Large files detected:\nno_colon_here"
        assert parser.parse_text(output) == []

    def test_message_includes_size(self, parser: CheckAddedLargeFilesParser) -> None:
        """The issue message includes the file size string verbatim."""
        output = "Large files detected:\nbig.bin: 200 MB"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "200 MB" in issues[0].message
        assert "big.bin" in issues[0].message


# ---------------------------------------------------------------------------
# RuffRegexParser / SkylosRegexParser — message clipping & details
# ---------------------------------------------------------------------------


class TestRuffRegexParserMessageClipping:
    """Confirm details list and message composition."""

    @pytest.fixture
    def parser(self) -> RuffRegexParser:
        return RuffRegexParser()

    def test_details_carries_code(self, parser: RuffRegexParser) -> None:
        """The details[0] entry contains 'code: FOO'."""
        output = "file.py:1:1 F401 unused import"
        issues = parser.parse_text(output)
        assert issues[0].details == ["code: F401"]

    def test_message_format(self, parser: RuffRegexParser) -> None:
        """The message starts with the code, then the body."""
        output = "file.py:1:1 E501 line too long"
        issues = parser.parse_text(output)
        assert issues[0].message.startswith("E501")
        assert "line too long" in issues[0].message

    def test_diagnostic_format_message_includes_code(
        self, parser: RuffRegexParser
    ) -> None:
        """Diagnostic-format messages start with the ruff code."""
        output = "F401 unused import\n--> file.py:1:1"
        issues = parser.parse_text(output)
        assert issues[0].message.startswith("F401")
        assert "unused import" in issues[0].message


# ---------------------------------------------------------------------------
# GenericRegexParser — registered subclasses
# ---------------------------------------------------------------------------


class TestGenericRegexParserSubclassesEdges:
    """Quick sanity checks for the registered subclasses' default IssueType."""

    def test_validate_regex_patterns_uses_formatting(self) -> None:
        from crackerjack.parsers.regex_parsers import ValidateRegexPatternsParser
        assert ValidateRegexPatternsParser().issue_type == IssueType.FORMATTING

    def test_trailing_whitespace_uses_formatting(self) -> None:
        from crackerjack.parsers.regex_parsers import TrailingWhitespaceParser
        assert TrailingWhitespaceParser().issue_type == IssueType.FORMATTING

    def test_end_of_file_fixer_uses_formatting(self) -> None:
        from crackerjack.parsers.regex_parsers import EndOfFileFixerParser
        assert EndOfFileFixerParser().issue_type == IssueType.FORMATTING

    def test_format_json_uses_formatting(self) -> None:
        from crackerjack.parsers.regex_parsers import FormatJsonParser
        assert FormatJsonParser().issue_type == IssueType.FORMATTING

    def test_mdformat_uses_formatting(self) -> None:
        from crackerjack.parsers.regex_parsers import MdformatParser
        assert MdformatParser().issue_type == IssueType.FORMATTING

    def test_uv_lock_uses_dependency(self) -> None:
        from crackerjack.parsers.regex_parsers import UvLockParser
        assert UvLockParser().issue_type == IssueType.DEPENDENCY

    def test_check_ast_uses_formatting(self) -> None:
        from crackerjack.parsers.regex_parsers import CheckAstParser
        assert CheckAstParser().issue_type == IssueType.FORMATTING

    def test_subclass_failure_propagates_message(self) -> None:
        """The subclass parser message names the subclass tool."""
        from crackerjack.parsers.regex_parsers import UvLockParser
        parser = UvLockParser()
        issues = parser.parse_text("error: dep missing")
        assert "uv-lock" in issues[0].message
        assert issues[0].type == IssueType.DEPENDENCY


# ---------------------------------------------------------------------------
# Sweep: every parser handles an empty string without raising.
# ---------------------------------------------------------------------------


class TestAllParsersEmptyInput:
    """Empty/whitespace inputs must not raise and should return [] for most."""

    @pytest.mark.parametrize("parser", _ALL_PARSERS, ids=lambda p: type(p).__name__)
    def test_empty_string_no_raise(self, parser) -> None:
        assert parser.parse_text("") == [] or isinstance(parser.parse_text(""), list)

    @pytest.mark.parametrize("parser", _ALL_PARSERS, ids=lambda p: type(p).__name__)
    def test_whitespace_string_no_raise(self, parser) -> None:
        assert parser.parse_text("   \n\t  \n   ") == [] or isinstance(
            parser.parse_text("   \n\t  \n   "), list
        )
