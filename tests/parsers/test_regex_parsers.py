"""Tests for regex_parsers module - comprehensive coverage for all regex parsers."""

import pytest
from unittest.mock import patch, MagicMock

from crackerjack.parsers.regex_parsers import (
    CodespellRegexParser,
    RefurbRegexParser,
    PyscnRegexParser,
    RuffFormatRegexParser,
    ComplexityRegexParser,
    GenericRegexParser,
    StructuredDataParser,
    MypyRegexParser,
    CreosoteRegexParser,
    LocalLinkCheckerRegexParser,
    LinkcheckmdRegexParser,
    JsonSchemaRegexParser,
    SkylosRegexParser,
    ValidateRegexPatternsParser,
    TrailingWhitespaceParser,
    EndOfFileFixerParser,
    FormatJsonParser,
    MdformatParser,
    UvLockParser,
    CheckAddedLargeFilesParser,
    CheckAstParser,
    RuffRegexParser,
    register_regex_parsers,
)
from crackerjack.agents.base import Issue, IssueType, Priority


class TestCodespellRegexParser:
    """Tests for CodespellRegexParser."""

    @pytest.fixture
    def parser(self):
        return CodespellRegexParser()

    def test_parse_basic_codespell_output(self, parser):
        """Test parsing basic codespell output with ==> format."""
        output = """src/file.py:42:1:佊  ==> expected"""
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING
        assert issues[0].severity == Priority.LOW
        assert "佊" in issues[0].message
        assert "expected" in issues[0].message

    def test_parse_codespell_without_suggestion(self, parser):
        """Test parsing codespell output without suggestion."""
        output = "src/utils.py:10: some_typo"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "src/utils.py"

    def test_parse_codespell_empty_output(self, parser):
        """Test parsing empty output."""
        assert parser.parse_text("") == []
        assert parser.parse_text("   ") == []

    def test_should_parse_codespell_line_with_arrow(self, parser):
        """Test that lines with ==> are parsed."""
        assert parser._should_parse_codespell_line("file.py:10:佊 ==> expected") is True

    def test_should_parse_codespell_line_with_multiple_colons(self, parser):
        """Test that lines with multiple colons are parsed."""
        assert parser._should_parse_codespell_line("file.py:10:20:message") is True

    def test_should_not_parse_empty_line(self, parser):
        """Test that empty lines are skipped."""
        assert parser._should_parse_codespell_line("") is False
        assert parser._should_parse_codespell_line("   ") is False


class TestRefurbRegexParser:
    """Tests for RefurbRegexParser."""

    @pytest.fixture
    def parser(self):
        return RefurbRegexParser()

    def test_parse_basic_refurb_output(self, parser):
        """Test parsing basic refurb output."""
        output = "src/myfile.py:42:10: [FURB123]: Use dict comprehension instead of loop"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.REFURB
        assert issues[0].severity == Priority.MEDIUM
        assert "FURB123" in issues[0].details[0]

    def test_parse_refurb_without_message_part(self, parser):
        """Test parsing refurb output with minimal message."""
        output = "src/myfile.py:5:10:Some message"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "src/myfile.py"

    def test_should_not_parse_summary_lines(self, parser):
        """Test that summary lines are skipped."""
        assert parser._should_parse_refurb_line("Found 5 issues") is False
        assert parser._should_parse_refurb_line("Checked 100 files") is False
        assert parser._should_parse_refurb_line("Success!") is False

    def test_should_not_parse_emoji_lines(self, parser):
        """Test that emoji-prefixed lines are skipped."""
        assert parser._should_parse_refurb_line("🔍 Scanning...") is False
        assert parser._should_parse_refurb_line("✅ Done") is False

    def test_parse_refurb_extracts_furb_code(self, parser):
        """Test that FURB code is extracted from message."""
        output = "src/file.py:10:5: [FURB456] Some message"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "FURB456" in issues[0].details[0]


class TestPyscnRegexParser:
    """Tests for PyscnRegexParser."""

    @pytest.fixture
    def parser(self):
        return PyscnRegexParser()

    def test_parse_basic_pyscn_output(self, parser):
        """Test parsing basic pyscn output."""
        output = "src/complex.py:42:10: Function is too complex (complexity 15)"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.COMPLEXITY
        assert issues[0].severity == Priority.HIGH  # "too complex"

    def test_parse_pyscn_with_clone_message(self, parser):
        """Test parsing pyscn output with clone message."""
        output = "src/duplicates.py:10:5: DUPLICATE CODE: found clone"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].severity == Priority.LOW  # clone

    def test_should_not_parse_emoji_lines(self, parser):
        """Test that emoji-prefixed lines are skipped."""
        assert parser._should_parse_pyscn_line("🔍 Analyzing...") is False
        assert parser._should_parse_pyscn_line("❌ Error occurred") is False
        assert parser._should_parse_pyscn_line("✅ Complete") is False

    def test_should_not_parse_usage_lines(self, parser):
        """Test that usage/help lines are skipped."""
        assert parser._should_parse_pyscn_line("Usage: pyscn [options]") is False
        assert parser._should_parse_pyscn_line("Available Commands:") is False

    def test_parse_pyscn_empty_output(self, parser):
        """Test parsing empty output."""
        assert parser.parse_text("") == []


class TestRuffFormatRegexParser:
    """Tests for RuffFormatRegexParser."""

    @pytest.fixture
    def parser(self):
        return RuffFormatRegexParser()

    def test_parse_would_be_reformatted(self, parser):
        """Test parsing 'would be reformatted' output."""
        output = "2 files would be reformatted"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING
        assert "2 file(s)" in issues[0].message

    def test_parse_failed_to_format(self, parser):
        """Test parsing 'Failed to format' output."""
        output = "Failed to format src/broken.py: syntax error"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "Formatting error" in issues[0].message

    def test_parse_no_issues(self, parser):
        """Test parsing output with no formatting issues."""
        assert parser.parse_text("") == []
        assert parser.parse_text("Everything is fine") == []


class TestComplexityRegexParser:
    """Tests for ComplexityRegexParser."""

    @pytest.fixture
    def parser(self):
        return ComplexityRegexParser()

    def test_parse_basic_complexity_output(self, parser):
        """Test parsing basic complexity output."""
        output = "src/file.py some_function 15"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.COMPLEXITY

    def test_parse_with_module_prefix(self, parser):
        """Test parsing with module::function format."""
        output = "src/module.py module::ClassName::method 20"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "method" in issues[0].message
        assert "20" in issues[0].message

    def test_should_not_parse_success_lines(self, parser):
        """Test that success indicator lines are skipped."""
        assert parser._parse_complexity_line("✓ All checks passed") is None
        assert parser._parse_complexity_line("✔ OK") is None
        assert parser._parse_complexity_line("PASS: 100 files") is None

    def test_should_not_parse_header_lines(self, parser):
        """Test that header/separator lines are skipped."""
        assert parser._parse_complexity_line("---") is None
        assert parser._parse_complexity_line("Checking...") is None

    def test_parse_invalid_line_with_few_parts(self, parser):
        """Test that lines with fewer than 3 parts are ignored."""
        assert parser._parse_complexity_line("only two") is None
        assert parser._parse_complexity_line("one") is None

    def test_parse_invalid_line_without_number(self, parser):
        """Test that lines without numeric complexity are ignored."""
        assert parser._parse_complexity_line("file.py function not_a_number") is None


class TestGenericRegexParser:
    """Tests for GenericRegexParser."""

    def test_constructor_sets_tool_name_and_issue_type(self):
        """Test that constructor properly sets tool_name and issue_type."""
        parser = GenericRegexParser("test-tool", IssueType.SECURITY)
        assert parser.tool_name == "test-tool"
        assert parser.issue_type == IssueType.SECURITY

    def test_parse_success_indicators(self):
        """Test parsing output with success indicators."""
        parser = GenericRegexParser("test-tool", IssueType.FORMATTING)
        for indicator in ("✓", "passed", "valid", "ok", "success", "no issues"):
            output = f"Tool ran and {indicator}!"
            assert parser.parse_text(output) == [], f"Failed for: {indicator}"

    def test_parse_failure_indicators(self):
        """Test parsing output with failure indicators."""
        parser = GenericRegexParser("test-tool", IssueType.FORMATTING)
        output = "Tool failed with error"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING

    def test_parse_unclear_output_treated_as_success(self):
        """Test that unclear output is treated as success (no issues)."""
        parser = GenericRegexParser("test-tool", IssueType.FORMATTING)
        assert parser.parse_text("Some random output") == []

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        parser = GenericRegexParser("test-tool")
        assert parser.parse_text("") == []
        assert parser.parse_text("   ") == []


class TestStructuredDataParser:
    """Tests for StructuredDataParser."""

    @pytest.fixture
    def parser(self):
        return StructuredDataParser()

    def test_parse_basic_structured_data(self, parser):
        """Test parsing basic structured data with ✗ prefix."""
        output = "✗ src/file.py: error message"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING
        assert issues[0].file_path == "src/file.py"

    def test_should_parse_only_lines_starting_with_x(self, parser):
        """Test that only ✗ prefixed lines are parsed."""
        assert parser._should_parse_structured_data_line("✗ some error") is True
        assert parser._should_parse_structured_data_line("not an error") is False
        assert parser._should_parse_structured_data_line("") is False

    def test_parse_without_x_prefix(self, parser):
        """Test parsing structured data after removing ✗."""
        output = "✗ config.yaml: missing field"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "missing field" in issues[0].message


class TestMypyRegexParser:
    """Tests for MypyRegexParser."""

    @pytest.fixture
    def parser(self):
        return MypyRegexParser()

    def test_parse_basic_mypy_output(self, parser):
        """Test parsing basic mypy output."""
        output = "src/file.py:42: error: Type mismatch"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.TYPE_ERROR
        assert issues[0].severity == Priority.HIGH
        assert issues[0].file_path == "src/file.py"

    def test_parse_mypy_with_warning(self, parser):
        """Test parsing mypy output with warning."""
        output = "src/file.py:10: warning: Unused import"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].severity == Priority.MEDIUM

    def test_should_not_parse_summary_lines(self, parser):
        """Test that summary lines are skipped."""
        assert parser._should_parse_mypy_line("Found 5 errors") is False
        assert parser._should_parse_mypy_line("Checked 100 files") is False
        assert parser._should_parse_mypy_line("Success") is False

    def test_should_not_parse_empty_lines(self, parser):
        """Test that empty lines are skipped."""
        assert parser._should_parse_mypy_line("") is False

    def test_extract_mypy_line_number(self, parser):
        """Test line number extraction from parts."""
        parts = ["file.py", "42", "error", "message"]
        assert parser._extract_mypy_line_number(parts) == 42

    def test_extract_mypy_line_number_invalid(self, parser):
        """Test line number extraction with invalid parts."""
        parts = ["file.py", "not_a_number", "error", "message"]
        assert parser._extract_mypy_line_number(parts) is None


class TestCreosoteRegexParser:
    """Tests for CreosoteRegexParser."""

    @pytest.fixture
    def parser(self):
        return CreosoteRegexParser()

    def test_parse_unused_dependencies_list(self, parser):
        """Test parsing 'Found unused dependencies:' line."""
        output = "Found unused dependencies: dep1, dep2, dep3"
        issues = parser.parse_text(output)
        assert len(issues) == 3
        assert all(i.type == IssueType.DEPENDENCY for i in issues)

    def test_parse_bulleted_dependencies(self, parser):
        """Test parsing bulleted dependency list."""
        output = "- requests\n- flask\n- django"
        issues = parser.parse_text(output)
        assert len(issues) == 3

    def test_parse_inline_unused_dependency(self, parser):
        """Test parsing inline unused dependency."""
        output = "src/file.py: unused-dependency (requests)"
        issues = parser.parse_text(output)
        assert len(issues) >= 1

    def test_should_not_parse_summary_lines(self, parser):
        """Test that summary lines are skipped."""
        assert parser._should_parse_creosote_line("Checked 100 dependencies") is False
        assert parser._should_parse_creosote_line("All dependencies are used") is False

    def test_should_parse_found_unused_deps(self, parser):
        """Test that 'Found unused dependencies' is parsed."""
        assert parser._should_parse_creosote_line("Found unused dependencies: foo") is True

    def test_parse_no_unused_dependencies(self, parser):
        """Test parsing output with no unused dependencies."""
        output = "No unused dependencies found"
        issues = parser.parse_text(output)
        # Should not create issues for this line
        assert not any("unused-dependency" in i.message.lower() for i in issues)

    def test_parse_redundant_and_excluded_not_found(self, parser):
        """Parse 'Redundant exclusion' and 'Excluded dependencies not found' lines."""
        output = (
            "Redundant exclusion 'pip-audit': import detected in source code\n"
            "Redundant exclusion 'pyright': not found in pyproject.toml\n"
            "Excluded dependencies not found in virtual environment: ty, pyrefly, pyright\n"
        )
        issues = parser.parse_text(output)

        # 2 redundant lines + 3 deps from the comma-split line = 5 issues
        assert len(issues) == 5
        assert all(i.stage == "creosote" for i in issues)
        assert all(i.type == IssueType.DEPENDENCY for i in issues)
        assert all(i.file_path == "pyproject.toml" for i in issues)
        # Each Issue carries a message the DependencyAgent can match.
        dep_names = {
            msg.split("'")[1]
            for msg in (i.message for i in issues)
            if msg.startswith("Redundant exclusion '") and "'" in msg
        }
        assert dep_names == {"pip-audit", "pyright", "ty", "pyrefly", "pyright"}


class TestLocalLinkCheckerRegexParser:
    """Tests for LocalLinkCheckerRegexParser."""

    @pytest.fixture
    def parser(self):
        return LocalLinkCheckerRegexParser()

    def test_parse_basic_link_output(self, parser):
        """Test parsing basic local link checker output."""
        output = "docs/guide.md:42 - ../readme.md - Target not found"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.DOCUMENTATION
        assert issues[0].file_path == "docs/guide.md"
        assert issues[0].line_number == 42

    def test_parse_without_message(self, parser):
        """Test parsing link output without extra message."""
        output = "file.md:10 - target.md"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "Broken link" in issues[0].message

    def test_should_not_parse_lines_without_dash(self, parser):
        """Test that lines without ' - ' are skipped."""
        assert parser._should_parse_local_link_line("no dash here") is False

    def test_parse_non_digit_line_number(self, parser):
        """Test parsing with non-numeric line number."""
        output = "file.md:abc - target.md - Error"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].line_number is None


class TestLinkcheckmdRegexParser:
    """Tests for LinkcheckmdRegexParser."""

    @pytest.fixture
    def parser(self):
        return LinkcheckmdRegexParser()

    def test_parse_basic_linkcheckmd_output(self, parser):
        """Test parsing basic linkcheckmd output."""
        output = "docs/guide.md:42 ERROR: broken link"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.DOCUMENTATION
        assert "broken link" in issues[0].message

    def test_parse_with_404(self, parser):
        """Test parsing linkcheckmd output with 404."""
        output = "README.md:10 404 not found"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "README.md"

    def test_should_not_parse_success_lines(self, parser):
        """Test that success lines are skipped."""
        assert parser._should_parse_linkcheckmd_line("✓ All links valid") is False
        assert parser._should_parse_linkcheckmd_line("PASS: Checked 100 links") is False

    def test_should_not_parse_checking_lines(self, parser):
        """Test that checking progress lines are skipped."""
        assert parser._should_parse_linkcheckmd_line("Checking links...") is False


class TestJsonSchemaRegexParser:
    """Tests for JsonSchemaRegexParser."""

    @pytest.fixture
    def parser(self):
        return JsonSchemaRegexParser()

    def test_parse_basic_jsonschema_output(self, parser):
        """Test parsing basic check-jsonschema output."""
        output = "schema.json:10 ERROR: validation failed"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING
        assert issues[0].file_path == "schema.json"

    def test_parse_yaml_file(self, parser):
        """Test parsing YAML schema file."""
        output = "config.yaml:5 FAIL: invalid schema"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "config.yaml"

    def test_should_not_parse_success_lines(self, parser):
        """Test that success lines are skipped."""
        assert parser._should_parse_jsonschema_line("OK: Schema valid") is False
        assert parser._should_parse_jsonschema_line("PASS: All schemas valid") is False

    def test_should_not_parse_checking_lines(self, parser):
        """Test that checking lines are skipped."""
        assert parser._should_parse_jsonschema_line("Checking schema.json...") is False


class TestSkylosRegexParser:
    """Tests for SkylosRegexParser."""

    @pytest.fixture
    def parser(self):
        return SkylosRegexParser()

    def test_parse_basic_skylos_output(self, parser):
        """Test parsing basic skylos output."""
        output = "src/dead_code.py - ERROR - line 42: unused import"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.DEAD_CODE
        assert issues[0].file_path == "src/dead_code.py"
        assert issues[0].line_number == 42

    def test_should_parse_only_error_lines(self, parser):
        """Test that only ERROR lines are parsed."""
        assert parser._should_parse_skylos_line("some file - ERROR - message") is True
        assert parser._should_parse_skylos_line("some file - WARNING - message") is False

    def test_parse_without_line_in_message(self, parser):
        """Test parsing skylos output without 'line' in message."""
        output = "src/file.py - ERROR - some error message"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].line_number is None


class TestGenericParserSubclasses:
    """Tests for GenericRegexParser subclasses."""

    def test_validate_regex_patterns_parser(self):
        """Test ValidateRegexPatternsParser."""
        parser = ValidateRegexPatternsParser()
        assert parser.tool_name == "validate-regex-patterns"
        assert parser.issue_type == IssueType.FORMATTING

    def test_trailing_whitespace_parser(self):
        """Test TrailingWhitespaceParser."""
        parser = TrailingWhitespaceParser()
        assert parser.tool_name == "trailing-whitespace"
        assert parser.issue_type == IssueType.FORMATTING

    def test_end_of_file_fixer_parser(self):
        """Test EndOfFileFixerParser."""
        parser = EndOfFileFixerParser()
        assert parser.tool_name == "end-of-file-fixer"
        assert parser.issue_type == IssueType.FORMATTING

    def test_format_json_parser(self):
        """Test FormatJsonParser."""
        parser = FormatJsonParser()
        assert parser.tool_name == "format-json"
        assert parser.issue_type == IssueType.FORMATTING

    def test_mdformat_parser(self):
        """Test MdformatParser."""
        parser = MdformatParser()
        assert parser.tool_name == "mdformat"
        assert parser.issue_type == IssueType.FORMATTING

    def test_uv_lock_parser(self):
        """Test UvLockParser."""
        parser = UvLockParser()
        assert parser.tool_name == "uv-lock"
        assert parser.issue_type == IssueType.DEPENDENCY

    def test_check_ast_parser(self):
        """Test CheckAstParser."""
        parser = CheckAstParser()
        assert parser.tool_name == "check-ast"
        assert parser.issue_type == IssueType.FORMATTING


class TestCheckAddedLargeFilesParser:
    """Tests for CheckAddedLargeFilesParser."""

    @pytest.fixture
    def parser(self):
        return CheckAddedLargeFilesParser()

    def test_parse_large_files_detected(self, parser):
        """Test parsing 'Large files detected' output."""
        output = """Large files detected:
src/large_file.bin: 50 MB
docs/video.mp4: 100 MB"""
        issues = parser.parse_text(output)
        assert len(issues) == 2
        assert all(i.type == IssueType.FORMATTING for i in issues)
        assert any("50 MB" in i.message for i in issues)

    def test_parse_no_large_files(self, parser):
        """Test parsing output without large files."""
        output = "No large files detected"
        issues = parser.parse_text(output)
        assert issues == []

    def test_parse_empty_output(self, parser):
        """Test parsing empty output."""
        assert parser.parse_text("") == []
        assert parser.parse_text("   ") == []


class TestRuffRegexParser:
    """Tests for RuffRegexParser."""

    @pytest.fixture
    def parser(self):
        return RuffRegexParser()

    def test_parse_concise_format(self, parser):
        """Test parsing concise ruff format."""
        # Format: file:line:column code message
        output = "src/file.py:42:10:F401 unused import"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.IMPORT_ERROR
        assert issues[0].file_path == "src/file.py"
        assert issues[0].line_number == 42
        assert "F401" in issues[0].message

    def test_parse_diagnostic_format(self, parser):
        """Test parsing diagnostic format with --> arrow."""
        # Diagnostic format: code message on one line, --> path:line:col on next
        output = "F401 unused import\n--> src/file.py:42:10"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type == IssueType.IMPORT_ERROR
        assert issues[0].file_path == "src/file.py"
        assert issues[0].line_number == 42

    def test_parse_multiline_context(self, parser):
        """Test parsing diagnostic format with context lines."""
        output = """F401 unused import 'os'
--> src/app.py:15:5
| import os"""
        issues = parser.parse_text(output)
        assert len(issues) == 1

    def test_should_skip_context_lines(self, parser):
        """Test that context lines are skipped."""
        assert parser._is_context_line("| some code") is True
        assert parser._is_context_line("") is True
        assert parser._is_context_line("not context") is False

    def test_is_concise_format_line(self, parser):
        """Test concise format detection."""
        assert parser._is_concise_format_line("file.py:10:5 F401 message") is True
        assert parser._is_concise_format_line("not:enough:colons") is False

    def test_issue_type_for_code_complexity(self, parser):
        """Test issue type mapping for C9 (complexity) codes."""
        assert parser._issue_type_for_code("C901") == IssueType.COMPLEXITY

    def test_issue_type_for_code_dead_code(self, parser):
        """Test issue type mapping for F4 (dead code) codes."""
        assert parser._issue_type_for_code("F401") == IssueType.IMPORT_ERROR
        assert parser._issue_type_for_code("F841") == IssueType.DEAD_CODE

    def test_issue_type_for_code_security(self, parser):
        """Test issue type mapping for S (security) codes."""
        assert parser._issue_type_for_code("S101") == IssueType.SECURITY

    def test_severity_for_code(self, parser):
        """Test severity mapping."""
        assert parser._severity_for_code("C901") == Priority.HIGH
        assert parser._severity_for_code("S101") == Priority.HIGH
        assert parser._severity_for_code("E741") == Priority.HIGH
        assert parser._severity_for_code("F401") == Priority.MEDIUM

    def test_extract_code_and_message(self, parser):
        """Test code and message extraction."""
        code, message = parser._extract_code_and_message("F401 unused import")
        assert code == "F401"
        assert message == "unused import"

    def test_extract_code_and_message_no_code(self, parser):
        """Test extraction when no code prefix."""
        code, message = parser._extract_code_and_message("just a message")
        assert code is None
        assert message == "just a message"


class TestRegisterRegexParsers:
    """Tests for register_regex_parsers function."""

    def test_register_regex_parsers_adds_parsers(self):
        """Test that register_regex_parsers adds all expected parsers."""
        factory = MagicMock()
        register_regex_parsers(factory)

        # Check that multiple register_regex_parser calls were made
        calls = factory.register_regex_parser.call_args_list
        tool_names = [call[0][0] for call in calls]

        expected_tools = [
            "codespell", "refurb", "pyscn", "ruff", "ruff-format",
            "complexipy", "complexity", "creosote", "mypy", "zuban",
            "skylos", "check-local-links", "lychee", "linkcheckmd",
            "check-jsonschema", "check-yaml", "check-toml", "check-json"
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Missing parser for {tool}"


class TestRegexParserEdgeCases:
    """Edge case tests for regex parsers."""

    def test_empty_output_all_parsers(self):
        """Test that all parsers handle empty output gracefully."""
        parsers = [
            CodespellRegexParser(),
            RefurbRegexParser(),
            PyscnRegexParser(),
            RuffFormatRegexParser(),
            ComplexityRegexParser(),
            MypyRegexParser(),
            CreosoteRegexParser(),
            LocalLinkCheckerRegexParser(),
            LinkcheckmdRegexParser(),
            JsonSchemaRegexParser(),
            SkylosRegexParser(),
            RuffRegexParser(),
        ]

        for parser in parsers:
            result = parser.parse_text("")
            assert result == [], f"{parser.__class__.__name__} failed on empty input"

    def test_whitespace_only_output(self):
        """Test parsers with whitespace-only output."""
        parser = CodespellRegexParser()
        assert parser.parse_text("   \n\t  \n") == []
