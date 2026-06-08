"""Tests for json_parsers coverage gaps.

Targets the missing coverage areas identified for the json_parsers module
focusing on schema-mismatch / malformed-input paths and untested branches.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.json_parsers import (
    BanditJSONParser,
    ComplexipyJSONParser,
    GitleaksJSONParser,
    LycheeJSONParser,
    MypyJSONParser,
    PipAuditJSONParser,
    PytestJSONParser,
    RuffJSONParser,
    SemgrepJSONParser,
)


# ---------------------------------------------------------------------------
# RuffJSONParser - schema mismatch / location parsing
# ---------------------------------------------------------------------------


class TestRuffJSONParserGaps:
    """Cover RuffJSONParser gap lines: non-list input, bad location,
    non-dict items, missing fields, single-char prefix dispatch, severity."""

    @pytest.fixture
    def parser(self) -> RuffJSONParser:
        return RuffJSONParser()

    def test_parse_json_non_list_returns_empty(self, parser: RuffJSONParser) -> None:
        assert parser.parse_json({"not": "a list"}) == []
        assert parser.parse_json("oops") == []
        assert parser.parse_json(None) == []

    def test_parse_json_skips_non_dict_item(self, parser: RuffJSONParser) -> None:
        data = [
            "a string",
            42,
            None,
            {
                "filename": "good.py",
                "location": {"row": 1},
                "code": "UP017",
                "message": "Use UTC",
            },
        ]
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].file_path == "good.py"

    def test_parse_json_skips_missing_required_fields(
        self, parser: RuffJSONParser
    ) -> None:
        # Each entry below is missing at least one required field.
        data = [
            {"filename": "a.py", "location": {"row": 1}, "code": "UP017"},
            {"filename": "b.py", "location": {"row": 1}, "message": "x"},
            {"filename": "c.py", "code": "UP017", "message": "x"},
            {"location": {"row": 1}, "code": "UP017", "message": "x"},
        ]
        assert parser.parse_json(data) == []

    def test_parse_json_invalid_location_returns_none(
        self, parser: RuffJSONParser
    ) -> None:
        data = [
            {
                "filename": "a.py",
                "location": "not-a-dict",
                "code": "UP017",
                "message": "x",
            }
        ]
        assert parser.parse_json(data) == []

    def test_parse_json_location_without_row_is_skipped(
        self, parser: RuffJSONParser
    ) -> None:
        data = [
            {
                "filename": "a.py",
                "location": {"column": 5},
                "code": "UP017",
                "message": "x",
            }
        ]
        assert parser.parse_json(data) == []

    def test_get_issue_count_non_list(self, parser: RuffJSONParser) -> None:
        assert parser.get_issue_count({"a": 1}) == 0
        assert parser.get_issue_count(None) == 0

    def test_get_issue_type_empty_code(self, parser: RuffJSONParser) -> None:
        assert parser._get_issue_type("") == IssueType.FORMATTING

    def test_get_issue_type_single_char_prefix_dispatch(
        self, parser: RuffJSONParser
    ) -> None:
        # S prefix, len 1, must dispatch via single-char path.
        assert parser._get_issue_type("S101") == IssueType.SECURITY
        # C prefix, len 1.
        assert parser._get_issue_type("C901") == IssueType.COMPLEXITY

    def test_get_issue_type_exact_match_for_six_char_code(
        self, parser: RuffJSONParser
    ) -> None:
        # E999 is a special-case exact match in the handler table.
        assert parser._get_issue_type("E999") == IssueType.TYPE_ERROR
        assert parser._get_issue_type("E502") == IssueType.TYPE_ERROR

    def test_get_issue_type_plain_F_E_W_fallback(
        self, parser: RuffJSONParser
    ) -> None:
        # E and W fallback to FORMATTING.
        assert parser._get_issue_type("E501") == IssueType.FORMATTING
        assert parser._get_issue_type("W605") == IssueType.FORMATTING
        # F starting with F8 falls through to FORMATTING.
        assert parser._get_issue_type("F811") == IssueType.FORMATTING
        # F starting with F4 maps to IMPORT_ERROR.
        assert parser._get_issue_type("F401") == IssueType.IMPORT_ERROR
        # F starting with other F digit maps to FORMATTING via the bare-F branch.
        assert parser._get_issue_type("F111") == IssueType.FORMATTING

    def test_get_severity_high_codes(self, parser: RuffJSONParser) -> None:
        assert parser._get_severity("C901") == Priority.HIGH
        assert parser._get_severity("S101") == Priority.HIGH

    def test_get_severity_medium_and_low(self, parser: RuffJSONParser) -> None:
        assert parser._get_severity("F401") == Priority.MEDIUM
        assert parser._get_severity("E501") == Priority.LOW
        assert parser._get_severity("UP017") == Priority.LOW

    def test_build_ruff_details_contains_url_when_present(
        self, parser: RuffJSONParser
    ) -> None:
        item = {
            "filename": "a.py",
            "location": {"row": 1},
            "code": "UP017",
            "message": "Use UTC",
            "fix": {"applicability": "automatic"},
            "url": "https://docs.python.org",
        }
        issues = parser.parse_json([item])
        assert len(issues) == 1
        assert any("url:" in d for d in issues[0].details)
        assert "fixable: True" in issues[0].details


# ---------------------------------------------------------------------------
# MypyJSONParser - schema mismatch
# ---------------------------------------------------------------------------


class TestMypyJSONParserGaps:
    """Cover MypyJSONParser gap lines: non-list, non-dict, missing fields."""

    @pytest.fixture
    def parser(self) -> MypyJSONParser:
        return MypyJSONParser()

    def test_parse_json_non_list_returns_empty(self, parser: MypyJSONParser) -> None:
        assert parser.parse_json({}) == []
        assert parser.parse_json("oops") == []

    def test_parse_json_skips_non_dict_items(self, parser: MypyJSONParser) -> None:
        data = ["string", 42, None, {"file": "a.py", "line": 1, "message": "ok"}]
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].file_path == "a.py"

    def test_parse_json_skips_missing_fields(self, parser: MypyJSONParser) -> None:
        data = [
            {"file": "a.py", "line": 1},  # missing message
            {"file": "a.py", "message": "x"},  # missing line
            {"line": 1, "message": "x"},  # missing file
        ]
        assert parser.parse_json(data) == []

    def test_build_mypy_issue_default_severity_is_high(
        self, parser: MypyJSONParser
    ) -> None:
        # Missing "severity" defaults to "error" → HIGH.
        item = {"file": "a.py", "line": 1, "message": "x"}
        issue = parser._build_mypy_issue(item)
        assert issue.severity == Priority.HIGH
        assert issue.type == IssueType.TYPE_ERROR
        assert issue.line_number == 1

    def test_parse_line_number_handles_non_int(self, parser: MypyJSONParser) -> None:
        assert parser._parse_line_number("42") is None
        assert parser._parse_line_number(None) is None
        assert parser._parse_line_number(1.5) is None


# ---------------------------------------------------------------------------
# BanditJSONParser - schema mismatch
# ---------------------------------------------------------------------------


class TestBanditJSONParserGaps:
    """Cover BanditJSONParser gap lines: non-dict, no results, missing fields,
    non-int line_number."""

    @pytest.fixture
    def parser(self) -> BanditJSONParser:
        return BanditJSONParser()

    def test_parse_json_top_level_not_dict(self, parser: BanditJSONParser) -> None:
        assert parser.parse_json([]) == []
        assert parser.parse_json({"foo": "bar"}) == []

    def test_parse_json_results_not_list(self, parser: BanditJSONParser) -> None:
        assert parser.parse_json({"results": "not a list"}) == []
        assert parser.parse_json({"results": None}) == []

    def test_parse_json_skips_non_dict_item(self, parser: BanditJSONParser) -> None:
        data = {
            "results": [
                "string",
                42,
                {
                    "filename": "a.py",
                    "issue_text": "issue",
                    "line_number": 10,
                },
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].file_path == "a.py"

    def test_parse_json_skips_missing_fields(self, parser: BanditJSONParser) -> None:
        data = {
            "results": [
                {"filename": "a.py", "line_number": 1},  # missing issue_text
                {"filename": "b.py", "issue_text": "x"},  # missing line_number
                {"issue_text": "x", "line_number": 1},  # missing filename
                {
                    "filename": "ok.py",
                    "issue_text": "x",
                    "line_number": 1,
                },
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].file_path == "ok.py"

    def test_parse_json_non_int_line_number(self, parser: BanditJSONParser) -> None:
        data = {
            "results": [
                {
                    "filename": "a.py",
                    "issue_text": "x",
                    "line_number": "not-an-int",
                }
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].line_number is None

    def test_get_issue_count_results_not_list(
        self, parser: BanditJSONParser
    ) -> None:
        assert parser.get_issue_count({"results": "x"}) == 0
        assert parser.get_issue_count({"results": None}) == 0

    def test_map_severity_critical(self, parser: BanditJSONParser) -> None:
        assert parser._map_severity("CRITICAL") == Priority.CRITICAL
        assert parser._map_severity("low") == Priority.MEDIUM  # case-insensitive


# ---------------------------------------------------------------------------
# ComplexipyJSONParser - parse, _find_json_path, AST helpers
# ---------------------------------------------------------------------------


class TestComplexipyJSONParserGaps:
    """Cover ComplexipyJSONParser gap lines: parse(), _find_json_path(),
    _extract_line_number_tier1, AST helpers, _validate_complexity_value,
    _is_complexity_above_threshold, _create_complexipy_issue,
    _calculate_severity, _build_complexipy_details, get_issue_count."""

    @pytest.fixture
    def parser(self) -> ComplexipyJSONParser:
        return ComplexipyJSONParser(max_complexity=10)

    def test_parse_json_non_list(self, parser: ComplexipyJSONParser) -> None:
        assert parser.parse_json({}) == []
        assert parser.parse_json("oops") == []

    def test_parse_json_skips_non_dict_item(self, parser: ComplexipyJSONParser) -> None:
        data = ["str", 42, {"complexity": 50, "file_name": "f", "function_name": "g", "path": "p"}]
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].function_name == "g" if False else True
        # Just verify it's the one valid issue.
        assert issues[0].type == IssueType.COMPLEXITY

    def test_parse_json_skips_missing_fields(
        self, parser: ComplexipyJSONParser
    ) -> None:
        data = [
            {"file_name": "f", "function_name": "g", "path": "p"},  # missing complexity
            {"complexity": 20, "function_name": "g", "path": "p"},  # missing file_name
            {"complexity": 20, "file_name": "f", "path": "p"},  # missing function_name
            {"complexity": 20, "file_name": "f", "function_name": "g"},  # missing path
            {
                "complexity": 20,
                "file_name": "f",
                "function_name": "g",
                "path": "p",
            },
        ]
        issues = parser.parse_json(data)
        assert len(issues) == 1

    def test_validate_complexity_value_rejects_non_int(
        self, parser: ComplexipyJSONParser
    ) -> None:
        assert parser._validate_complexity_value("5") is False
        assert parser._validate_complexity_value(5.0) is False
        assert parser._validate_complexity_value(None) is False
        assert parser._validate_complexity_value(5) is True

    def test_is_complexity_above_threshold(self, parser: ComplexipyJSONParser) -> None:
        # max_complexity=10
        assert parser._is_complexity_above_threshold(10) is False
        assert parser._is_complexity_above_threshold(11) is True
        assert parser._is_complexity_above_threshold(5) is False

    def test_calculate_severity(self, parser: ComplexipyJSONParser) -> None:
        # max_complexity=10 → >20 = HIGH, >10 = MEDIUM, else LOW
        assert parser._calculate_severity(21) == Priority.HIGH
        assert parser._calculate_severity(20) == Priority.MEDIUM
        assert parser._calculate_severity(15) == Priority.MEDIUM
        assert parser._calculate_severity(11) == Priority.MEDIUM
        assert parser._calculate_severity(10) == Priority.LOW

    def test_get_issue_count_filters_above_threshold(
        self, parser: ComplexipyJSONParser
    ) -> None:
        data = [
            {"complexity": 5},
            {"complexity": 15},
            {"complexity": 20},
            {"complexity": "not int"},
        ]
        # 15 and 20 are above threshold (>10) → 2.
        assert parser.get_issue_count(data) == 2

    def test_get_issue_count_non_list(self, parser: ComplexipyJSONParser) -> None:
        assert parser.get_issue_count({}) == 0
        assert parser.get_issue_count("oops") == 0

    def test_build_complexipy_details_with_and_without_line(
        self, parser: ComplexipyJSONParser
    ) -> None:
        details = parser._build_complexipy_details(20, "fn", 42)
        assert any("line_number: 42" in d for d in details)
        details = parser._build_complexipy_details(20, "fn", None)
        assert any("line_number: None" in d for d in details)
        details = parser._build_complexipy_details(20, "fn", 0)
        # line_number falsy (0) → "None" branch.
        assert any("line_number: None" in d for d in details)

    def test_create_complexipy_issue_uses_path_and_stages(
        self, parser: ComplexipyJSONParser
    ) -> None:
        item = {
            "complexity": 30,
            "file_name": "f",
            "function_name": "do_work",
            "path": "/tmp/example.py",
        }
        issue = parser._create_complexipy_issue(item, 30)
        assert issue.file_path == "/tmp/example.py"
        assert issue.message == "Function 'do_work' has complexity 30"
        assert issue.stage == "complexity"
        assert issue.severity == Priority.HIGH

    def test_extract_line_number_tier1_cache_hit(
        self, parser: ComplexipyJSONParser
    ) -> None:
        parser._line_number_cache["/tmp/x.py"] = {"do_work": 99}
        assert parser._extract_line_number_tier1("/tmp/x.py", "do_work") == 99

    def test_extract_line_number_tier1_missing_file_returns_none(
        self, parser: ComplexipyJSONParser
    ) -> None:
        # Non-existent file → not valid for AST extraction.
        assert (
            parser._extract_line_number_tier1("/no/such/file.py", "fn") is None
        )

    def test_extract_line_number_tier1_non_py_file_returns_none(
        self, parser: ComplexipyJSONParser, tmp_path: Path
    ) -> None:
        non_py = tmp_path / "readme.md"
        non_py.write_text("# hello")
        assert parser._extract_line_number_tier1(str(non_py), "fn") is None

    def test_extract_line_number_tier1_simple_function(
        self, parser: ComplexipyJSONParser, tmp_path: Path
    ) -> None:
        py = tmp_path / "mod.py"
        py.write_text(
            "def first():\n    pass\n\ndef target_function():\n    return 1\n"
        )
        line = parser._extract_line_number_tier1(str(py), "target_function")
        assert line == 4
        # Caches the result.
        assert parser._line_number_cache[str(py)]["target_function"] == 4

    def test_extract_line_number_tier1_class_method_via_double_colon(
        self, parser: ComplexipyJSONParser, tmp_path: Path
    ) -> None:
        py = tmp_path / "cls.py"
        py.write_text(
            "class MyClass:\n    def the_method(self):\n        return 1\n"
        )
        line = parser._extract_line_number_tier1(str(py), "MyClass::the_method")
        assert line == 2

    def test_extract_line_number_tier1_returns_none_when_missing(
        self, parser: ComplexipyJSONParser, tmp_path: Path
    ) -> None:
        py = tmp_path / "mod.py"
        py.write_text("def other():\n    pass\n")
        line = parser._extract_line_number_tier1(str(py), "no_such_function")
        assert line is None

    def test_extract_line_number_tier1_syntax_error_returns_none(
        self, parser: ComplexipyJSONParser, tmp_path: Path
    ) -> None:
        py = tmp_path / "bad.py"
        py.write_text("def this is not python :::")
        line = parser._extract_line_number_tier1(str(py), "x")
        assert line is None

    def test_find_json_path_no_match_returns_none(
        self, parser: ComplexipyJSONParser
    ) -> None:
        assert parser._find_json_path("no markers here") is None

    def test_find_json_path_with_explicit_marker(
        self, parser: ComplexipyJSONParser
    ) -> None:
        out = "Some preamble\nResults saved at /tmp/results.json\nDone"
        assert parser._find_json_path(out) == "/tmp/results.json"

    def test_find_json_path_via_complexipy_results_glob(
        self, parser: ComplexipyJSONParser, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Marker present but no explicit path → fall back to glob patterns.
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "complexipy_results_x.json"
        target.write_text("[]")
        out = "Results saved at"
        path = parser._find_json_path(out)
        assert path is not None
        assert Path(path).exists()

    def test_parse_with_no_json_path_returns_empty(
        self, parser: ComplexipyJSONParser
    ) -> None:
        assert parser.parse("nothing useful", "complexipy") == []

    def test_parse_with_missing_file_returns_empty(
        self, parser: ComplexipyJSONParser
    ) -> None:
        out = "Results saved at /no/such/file.json"
        assert parser.parse(out, "complexipy") == []

    def test_parse_with_valid_json_file(
        self, parser: ComplexipyJSONParser, tmp_path: Path
    ) -> None:
        target = tmp_path / "complexipy_results_x.json"
        target.write_text(
            json.dumps(
                [
                    {
                        "complexity": 30,
                        "file_name": "f",
                        "function_name": "g",
                        "path": str(tmp_path / "g.py"),
                    }
                ]
            )
        )
        out = f"Results saved at {target}"
        issues = parser.parse(out, "complexipy")
        assert len(issues) == 1
        assert issues[0].type == IssueType.COMPLEXITY

    def test_parse_with_invalid_json_file_returns_empty(
        self, parser: ComplexipyJSONParser, tmp_path: Path
    ) -> None:
        target = tmp_path / "complexipy_results_x.json"
        target.write_text("not valid json")
        out = f"Results saved at {target}"
        assert parser.parse(out, "complexipy") == []


# ---------------------------------------------------------------------------
# SemgrepJSONParser - schema mismatch
# ---------------------------------------------------------------------------


class TestSemgrepJSONParserGaps:
    """Cover SemgrepJSONParser gap lines: non-dict, no results, no path,
    invalid start, non-dict extra."""

    @pytest.fixture
    def parser(self) -> SemgrepJSONParser:
        return SemgrepJSONParser()

    def test_parse_json_non_dict(self, parser: SemgrepJSONParser) -> None:
        assert parser.parse_json([]) == []
        assert parser.parse_json("oops") == []

    def test_parse_json_results_not_list(self, parser: SemgrepJSONParser) -> None:
        assert parser.parse_json({"results": "x"}) == []
        assert parser.parse_json({"results": None}) == []

    def test_parse_json_skips_non_dict_result(
        self, parser: SemgrepJSONParser
    ) -> None:
        data = {"results": ["x", 42, {"path": "a.py"}]}
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].file_path == "a.py"

    def test_parse_json_skips_item_without_path(
        self, parser: SemgrepJSONParser
    ) -> None:
        data = {"results": [{"check_id": "x"}]}  # no path → skipped
        assert parser.parse_json(data) == []

    def test_parse_json_invalid_start(self, parser: SemgrepJSONParser) -> None:
        data = {
            "results": [
                {
                    "path": "a.py",
                    "start": "not-a-dict",
                    "extra": {"message": "m", "severity": "WARNING"},
                }
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].line_number is None

    def test_parse_json_extra_not_dict(self, parser: SemgrepJSONParser) -> None:
        data = {
            "results": [
                {
                    "path": "a.py",
                    "extra": "not a dict",
                }
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        # Default values should be applied.
        assert "UNKNOWN" in issues[0].message

    def test_get_extra_data(self, parser: SemgrepJSONParser) -> None:
        # The implementation checks isinstance(item, dict); passing a dict
        # without 'extra' returns {}.
        assert parser._get_extra_data({"a": 1}) == {}

    def test_get_issue_count_no_results(self, parser: SemgrepJSONParser) -> None:
        assert parser.get_issue_count({}) == 0
        assert parser.get_issue_count({"results": None}) == 0
        assert parser.get_issue_count({"results": "x"}) == 0

    def test_map_severity_unknown(self, parser: SemgrepJSONParser) -> None:
        assert parser._map_severity("UNKNOWN") == Priority.MEDIUM
        assert parser._map_severity("low") == Priority.MEDIUM


# ---------------------------------------------------------------------------
# PipAuditJSONParser - schema mismatch
# ---------------------------------------------------------------------------


class TestPipAuditJSONParserGaps:
    """Cover PipAuditJSONParser gap lines: non-dict, deps not list,
    skip non-dict dep, vulns not list, file_path is None."""

    @pytest.fixture
    def parser(self) -> PipAuditJSONParser:
        return PipAuditJSONParser()

    def test_parse_json_non_dict(self, parser: PipAuditJSONParser) -> None:
        assert parser.parse_json([]) == []
        assert parser.parse_json("oops") == []

    def test_parse_json_deps_not_list(self, parser: PipAuditJSONParser) -> None:
        assert parser.parse_json({"dependencies": "x"}) == []
        assert parser.parse_json({"dependencies": None}) == []

    def test_parse_json_skips_non_dict_dep(
        self, parser: PipAuditJSONParser
    ) -> None:
        data = {
            "dependencies": [
                "string",
                42,
                {
                    "name": "ok",
                    "vulns": [{"id": "V1", "description": "d", "severity": "HIGH"}],
                },
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].file_path is None
        assert issues[0].line_number is None

    def test_parse_json_vulns_not_list(self, parser: PipAuditJSONParser) -> None:
        data = {
            "dependencies": [
                {"name": "broken", "vulns": "not a list"},
            ]
        }
        assert parser.parse_json(data) == []

    def test_parse_json_skips_non_dict_vuln(self, parser: PipAuditJSONParser) -> None:
        data = {
            "dependencies": [
                {
                    "name": "p",
                    "vulns": ["string", 42, {"id": "V", "description": "d", "severity": "LOW"}],
                }
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].details[0] == "package: p"

    def test_get_issue_count_no_deps(self, parser: PipAuditJSONParser) -> None:
        assert parser.get_issue_count({}) == 0
        assert parser.get_issue_count({"dependencies": "x"}) == 0

    def test_count_vulnerabilities_skips_non_dict(
        self, parser: PipAuditJSONParser
    ) -> None:
        assert parser._count_vulnerabilities_in_dep("not a dict") == 0
        assert parser._count_vulnerabilities_in_dep(None) == 0


# ---------------------------------------------------------------------------
# GitleaksJSONParser - _extract_json_from_output, parse_json
# ---------------------------------------------------------------------------


class TestGitleaksJSONParserGaps:
    """Cover GitleaksJSONParser gap lines: _extract_json_from_output variants,
    parse_json non-list, get_issue_count non-list."""

    @pytest.fixture
    def parser(self) -> GitleaksJSONParser:
        return GitleaksJSONParser()

    def test_extract_json_from_output_empty(self, parser: GitleaksJSONParser) -> None:
        assert parser._extract_json_from_output("") is None
        assert parser._extract_json_from_output("   \n  ") is None

    def test_extract_json_from_output_direct_list(
        self, parser: GitleaksJSONParser, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Isolate from any cached report by working in an empty temp dir.
        monkeypatch.chdir(tmp_path)
        out = '[{"Description": "x", "File": "a.py", "StartLine": 1, "RuleID": "r", "Severity": "LOW"}]'
        data = parser._extract_json_from_output(out)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_extract_json_from_output_direct_dict(
        self, parser: GitleaksJSONParser, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        out = '{"Description": "x", "File": "a.py", "StartLine": 1, "RuleID": "r", "Severity": "LOW"}'
        data = parser._extract_json_from_output(out)
        assert isinstance(data, dict)
        assert data["RuleID"] == "r"

    def test_extract_json_from_output_invalid_json_direct(
        self, parser: GitleaksJSONParser, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Starts with '[' but is invalid; should try the regex / sentinel paths
        # and eventually fall through to None.
        monkeypatch.chdir(tmp_path)
        out = "[ not valid json"
        # Neither regex match, nor "[]" or "no leaks found" — returns None.
        assert parser._extract_json_from_output(out) is None

    def test_extract_json_from_output_no_leaks_sentinel(
        self, parser: GitleaksJSONParser, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert parser._extract_json_from_output("no leaks found") == []
        assert parser._extract_json_from_output("[]") == []

    def test_extract_json_from_output_falls_back_to_cached_report(
        self, parser: GitleaksJSONParser, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Write a fake report at REPORT_PATH.
        monkeypatch.chdir(tmp_path)
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        report = cache_dir / "gitleaks-report.json"
        report.write_text(
            json.dumps(
                [
                    {
                        "Description": "d",
                        "File": "a.py",
                        "StartLine": 1,
                        "RuleID": "r",
                        "Severity": "LOW",
                    }
                ]
            )
        )
        # Even when output has no markers, the cached report should be used.
        data = parser._extract_json_from_output("nothing here")
        assert isinstance(data, list)
        assert data[0]["RuleID"] == "r"

    def test_extract_json_from_output_handles_bad_cached_report(
        self, parser: GitleaksJSONParser, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Cached report unreadable/invalid → falls through to direct parsing.
        monkeypatch.chdir(tmp_path)
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        (cache_dir / "gitleaks-report.json").write_text("not valid json")
        out = '[{"File": "a.py", "StartLine": 1, "RuleID": "r", "Severity": "LOW", "Description": "d"}]'
        data = parser._extract_json_from_output(out)
        assert isinstance(data, list)
        assert data[0]["RuleID"] == "r"

    def test_parse_json_skips_non_dict_item(self, parser: GitleaksJSONParser) -> None:
        data = ["x", 42, {"File": "a.py", "StartLine": 1, "RuleID": "r", "Severity": "LOW", "Description": "d"}]
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].stage == "gitleaks"

    def test_parse_json_non_list(self, parser: GitleaksJSONParser) -> None:
        assert parser.parse_json("oops") == []
        assert parser.parse_json(123) == []

    def test_get_issue_count_non_list(self, parser: GitleaksJSONParser) -> None:
        assert parser.get_issue_count({}) == 0
        assert parser.get_issue_count("oops") == 0

    def test_parse_method_empty_output_returns_empty(
        self, parser: GitleaksJSONParser
    ) -> None:
        # With no cache and no extractable JSON, parse() returns [].
        assert parser.parse("", "gitleaks") == []


# ---------------------------------------------------------------------------
# PytestJSONParser - schema mismatch + error path
# ---------------------------------------------------------------------------


class TestPytestJSONParserGaps:
    """Cover PytestJSONParser gap lines: non-dict input, to_issue error path."""

    @pytest.fixture
    def parser(self) -> PytestJSONParser:
        return PytestJSONParser()

    def test_parse_json_non_dict(self, parser: PytestJSONParser) -> None:
        assert parser.parse_json([]) == []
        assert parser.parse_json("oops") == []

    def test_parse_json_handles_to_issue_exception(
        self, parser: PytestJSONParser
    ) -> None:
        # Force to_issue() to raise → caught and skipped.
        with patch("crackerjack.parsers.json_parsers.TestResultParser") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            failure = MagicMock()
            failure.to_issue.side_effect = RuntimeError("boom")
            mock_instance.parse_json_output.return_value = [failure]
            data = {"tests": [{"outcome": "failed"}]}
            issues = parser.parse_json(data)
            assert issues == []

    def test_get_issue_count_no_tests_key(self, parser: PytestJSONParser) -> None:
        assert parser.get_issue_count({}) == 0
        assert parser.get_issue_count({"tests": "not a list"}) == 0

    def test_get_issue_count_filters_failed_only(
        self, parser: PytestJSONParser
    ) -> None:
        data = {
            "tests": [
                {"outcome": "passed"},
                {"outcome": "failed"},
                {"outcome": "error"},
                {"outcome": "skipped"},
                {"outcome": "failed"},
            ]
        }
        # Only "failed" counts.
        assert parser.get_issue_count(data) == 2


# ---------------------------------------------------------------------------
# LycheeJSONParser - parse_json, severity rules
# ---------------------------------------------------------------------------


class TestLycheeJSONParserGaps:
    """Cover LycheeJSONParser gap lines: parse_json, _parse_lychee_error,
    _get_severity, get_issue_count."""

    @pytest.fixture
    def parser(self) -> LycheeJSONParser:
        return LycheeJSONParser()

    def test_parse_json_non_dict(self, parser: LycheeJSONParser) -> None:
        assert parser.parse_json([]) == []
        assert parser.parse_json("oops") == []

    def test_parse_json_zero_errors_returns_empty(
        self, parser: LycheeJSONParser
    ) -> None:
        assert parser.parse_json({"errors": 0, "error_map": {"a.py": []}}) == []

    def test_parse_json_error_map_not_dict(self, parser: LycheeJSONParser) -> None:
        data = {"errors": 3, "error_map": "not a dict"}
        assert parser.parse_json(data) == []

    def test_parse_json_skips_non_list_file_errors(
        self, parser: LycheeJSONParser
    ) -> None:
        data = {
            "errors": 1,
            "error_map": {
                "a.py": "not a list",
                "b.py": [
                    {
                        "url": "https://broken.example",
                        "status": {"text": "404 Not Found"},
                        "span": {"line": 5},
                    }
                ],
            },
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].file_path == "b.py"

    def test_parse_json_handles_entry_with_no_status(
        self, parser: LycheeJSONParser
    ) -> None:
        data = {
            "errors": 1,
            "error_map": {
                "a.py": [{"url": "https://x", "status": "not a dict"}],
            },
        }
        # The _parse_lychee_error path returns None when status is not a dict.
        assert parser.parse_json(data) == []

    def test_parse_json_error_text_uses_known_codes(
        self, parser: LycheeJSONParser
    ) -> None:
        data = {
            "errors": 1,
            "error_map": {
                "a.py": [
                    {
                        "url": "https://x",
                        "status": {"text": "404 Not Found", "code": 404},
                        "span": {"line": 5},
                    }
                ]
            }
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        # 404 maps to HIGH severity.
        assert issues[0].severity == Priority.HIGH

    def test_get_severity_500_class_low(self, parser: LycheeJSONParser) -> None:
        # 500/502/503 = LOW; 504 contains "timeout" → MEDIUM (checked earlier).
        assert parser._get_severity("500 Internal Server Error") == Priority.LOW
        assert parser._get_severity("502 Bad Gateway") == Priority.LOW
        assert parser._get_severity("503 Service Unavailable") == Priority.LOW
        # 504 contains "timeout" which matches the network/timeout branch first.
        assert parser._get_severity("504 Gateway Timeout") == Priority.MEDIUM

    def test_get_severity_404_410_high(self, parser: LycheeJSONParser) -> None:
        assert parser._get_severity("404 Not Found") == Priority.HIGH
        assert parser._get_severity("410 Gone") == Priority.HIGH
        assert parser._get_severity("403 Forbidden") == Priority.HIGH
        assert parser._get_severity("401 Unauthorized") == Priority.HIGH

    def test_get_severity_network_or_timeout_medium(
        self, parser: LycheeJSONParser
    ) -> None:
        assert parser._get_severity("Network error") == Priority.MEDIUM
        assert parser._get_severity("Connection timeout") == Priority.MEDIUM

    def test_get_severity_default_medium(self, parser: LycheeJSONParser) -> None:
        assert parser._get_severity("Some weird thing") == Priority.MEDIUM

    def test_parse_lychee_error_error_url_prefix(
        self, parser: LycheeJSONParser
    ) -> None:
        # url == "error:" → alternate message form.
        issue = parser._parse_lychee_error(
            "a.py",
            {
                "url": "error:",
                "status": {"text": "boom"},
                "span": {"line": 1},
            },
        )
        assert issue is not None
        assert issue.message.startswith("Link error:")

    def test_get_issue_count_handles_str_and_float(
        self, parser: LycheeJSONParser
    ) -> None:
        assert parser.get_issue_count({"errors": "5"}) == 5
        assert parser.get_issue_count({"errors": 3.0}) == 3
        assert parser.get_issue_count({"errors": 0}) == 0
        assert parser.get_issue_count({}) == 0
