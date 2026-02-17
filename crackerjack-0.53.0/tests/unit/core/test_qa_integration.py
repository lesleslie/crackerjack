"""Tests for QAResult integration with AI-fix workflow.

Tests the conversion from ToolIssue dicts (from QAResult.parsed_issues) to Issue objects,
ensuring single-source-of-truth for issue data instead of duplicate parsing.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.models.qa_results import QAResult, QAResultStatus, QACheckType
from crackerjack.core.autofix_coordinator import AutofixCoordinator


class TestQAResultIssueConversion:
    """Test conversion of ToolIssue dicts to Issue objects."""

    @pytest.fixture
    def coordinator(self):
        """Create AutofixCoordinator instance."""
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_convert_parsed_issues_to_issues_basic(self, coordinator):
        """Test basic conversion of ToolIssue dict to Issue."""
        tool_issues = [
            {
                "file_path": "/path/to/file.py",
                "line_number": 42,
                "column_number": 10,
                "message": "Code style violation",
                "code": "TEST001",
                "severity": "error",
                "suggestion": "Fix it this way",
            }
        ]

        issues = coordinator._convert_parsed_issues_to_issues("test-tool", tool_issues)

        assert len(issues) == 1
        issue = issues[0]

        assert issue.type == IssueType.FORMATTING  # Default fallback
        assert issue.severity == Priority.HIGH
        assert issue.message == "Code style violation"
        assert issue.file_path == "/path/to/file.py"
        assert issue.line_number == 42
        assert issue.stage == "test-tool"

        # Check details
        assert "code: TEST001" in issue.details
        assert "suggestion: Fix it this way" in issue.details
        assert "severity: error" in issue.details
        assert "column: 10" in issue.details

    def test_convert_severity_mapping(self, coordinator):
        """Test severity string to Priority enum mapping."""
        test_cases = [
            ("error", Priority.HIGH),
            ("warning", Priority.MEDIUM),
            ("info", Priority.LOW),
            ("note", Priority.LOW),
            ("unknown", Priority.MEDIUM),  # Fallback
        ]

        for severity_str, expected_priority in test_cases:
            tool_issues = [
                {
                    "file_path": "/path/to/file.py",
                    "line_number": 1,
                    "message": "Test message",
                    "severity": severity_str,
                }
            ]

            issues = coordinator._convert_parsed_issues_to_issues("unknown-tool", tool_issues)

            assert len(issues) == 1
            assert issues[0].severity == expected_priority

    def test_determine_issue_type_by_tool_name(self, coordinator):
        """Test IssueType determination based on tool name."""
        tool_type_tests = [
            ("ruff", IssueType.FORMATTING),
            ("ruff-format", IssueType.FORMATTING),
            ("mypy", IssueType.TYPE_ERROR),
            ("zuban", IssueType.TYPE_ERROR),
            ("bandit", IssueType.SECURITY),
            ("complexipy", IssueType.COMPLEXITY),
            ("skylos", IssueType.DEAD_CODE),
            ("pytest", IssueType.TEST_FAILURE),
        ]

        for tool_name, expected_type in tool_type_tests:
            tool_issues = [
                {
                    "file_path": "/path/to/file.py",
                    "line_number": 1,
                    "message": "Test issue",
                    "severity": "error",
                }
            ]

            issues = coordinator._convert_parsed_issues_to_issues(tool_name, tool_issues)

            assert len(issues) == 1
            assert issues[0].type == expected_type
            assert issues[0].stage == tool_name

    def test_determine_issue_type_fallback(self, coordinator):
        """Test IssueType fallback based on message content."""
        test_cases = [
            ("Test failed in module", IssueType.TEST_FAILURE),
            ("Function has high complexity", IssueType.COMPLEXITY),
            ("Unused variable detected", IssueType.DEAD_CODE),
            ("Security vulnerability found", IssueType.SECURITY),
            ("Import error for module", IssueType.IMPORT_ERROR),
            ("Type error: incompatible types", IssueType.TYPE_ERROR),
        ]

        for message, expected_type in test_cases:
            tool_issues = [
                {
                    "file_path": "/path/to/file.py",
                    "line_number": 1,
                    "message": message,
                    "severity": "error",
                }
            ]

            issues = coordinator._convert_parsed_issues_to_issues("unknown-tool", tool_issues)

            assert len(issues) == 1
            assert issues[0].type == expected_type

    def test_build_issue_details(self, coordinator):
        """Test details list building."""
        tool_issues = [
            {
                "file_path": "/path/to/file.py",
                "line_number": 42,
                "column_number": 10,
                "message": "Test error",
                "code": "TEST001",
                "severity": "error",
                "suggestion": "Fix it",
            }
        ]

        issues = coordinator._convert_parsed_issues_to_issues("test", tool_issues)

        assert len(issues) == 1
        details = issues[0].details

        assert "code: TEST001" in details
        assert "suggestion: Fix it" in details
        assert "column: 10" in details
        assert "severity: error" in details

    def test_convert_handles_missing_fields(self, coordinator):
        """Test conversion handles missing optional fields gracefully."""
        minimal_tool_issues = [
            {
                "file_path": "/path/to/file.py",
                "message": "Minimal issue",
                # Missing: line_number, column_number, code, suggestion
            }
        ]

        issues = coordinator._convert_parsed_issues_to_issues("test", minimal_tool_issues)

        assert len(issues) == 1
        assert issues[0].line_number is None
        assert issues[0].message == "Minimal issue"

    def test_convert_filters_invalid_issues(self, coordinator):
        """Test that conversion filters out problematic issues gracefully."""
        # This should be logged but not crash
        invalid_issues = [
            {"message": "No file path"}  # Missing required field
        ]

        issues = coordinator._convert_parsed_issues_to_issues("test", invalid_issues)

        # Should handle gracefully (log warning but return what it can)
        assert isinstance(issues, list)

    def test_convert_multiple_issues(self, coordinator):
        """Test converting multiple issues at once."""
        tool_issues = [
            {
                "file_path": "/path/to/file1.py",
                "line_number": 10,
                "message": "Error 1",
                "severity": "error",
            },
            {
                "file_path": "/path/to/file2.py",
                "line_number": 20,
                "message": "Warning 1",
                "severity": "warning",
            },
            {
                "file_path": "/path/to/file3.py",
                "line_number": 30,
                "message": "Error 2",
                "severity": "error",
            },
        ]

        issues = coordinator._convert_parsed_issues_to_issues("test", tool_issues)

        assert len(issues) == 3
        assert issues[0].severity == Priority.HIGH
        assert issues[1].severity == Priority.MEDIUM
        assert issues[2].severity == Priority.HIGH


class TestQAResultIntegration:
    """Integration tests for QAResult usage in AI-fix workflow."""

    @pytest.fixture
    def mock_qa_result(self):
        """Create a mock QAResult with parsed issues."""
        return QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            message="Found 14 complexity issues",
            parsed_issues=[
                {
                    "file_path": "/path/to/file1.py",
                    "line_number": 42,
                    "column_number": 10,
                    "message": "Function 'test_func' has complexity 20",
                    "code": "C001",
                    "severity": "error",
                    "suggestion": "Refactor function",
                },
                {
                    "file_path": "/path/to/file2.py",
                    "line_number": 100,
                    "message": "Function 'complex_func' has complexity 25",
                    "severity": "error",
                },
            ],
            files_checked=[Path("/path/to/file1.py"), Path("/path/to/file2.py")],
            issues_found=2,
            execution_time_ms=1000.0,
        )

    @pytest.fixture
    def coordinator(self):
        """Create AutofixCoordinator instance."""
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_parse_hook_to_issues_uses_qa_result(self, coordinator, mock_qa_result):
        """Test that _parse_hook_to_issues uses QAResult when available."""
        hook_name = "complexipy"
        raw_output = "Some output"

        # Call with qa_result
        issues = coordinator._parse_hook_to_issues(
            hook_name, raw_output, qa_result=mock_qa_result
        )

        assert len(issues) == 2
        assert issues[0].message == "Function 'test_func' has complexity 20"
        assert issues[0].file_path == "/path/to/file1.py"
        assert issues[0].line_number == 42
        assert issues[0].type == IssueType.COMPLEXITY

    def test_parse_hook_to_issues_fallback_without_qa_result(self, coordinator):
        """Test that _parse_hook_to_issues falls back to raw parsing without QAResult."""
        hook_name = "complexipy"
        raw_output = """
Results saved at
/tmp/complexipy_results.json
"""

        # Call without qa_result
        with patch.object(
            coordinator, "_parser_factory"
        ) as mock_factory:
            mock_parser = MagicMock()
            mock_parser.parse_with_validation.return_value = [
                Issue(
                    type=IssueType.COMPLEXITY,
                    severity=Priority.HIGH,
                    message="Fallback issue",
                    file_path="/path/to/file.py",
                    stage="complexipy",
                )
            ]
            mock_factory.parse_with_validation.return_value = mock_parser.parse_with_validation(
                tool_name="complexipy",
                output=raw_output,
                expected_count=None,
            )

            issues = coordinator._parse_hook_to_issues(hook_name, raw_output, qa_result=None)

        assert len(issues) == 1
        assert issues[0].message == "Fallback issue"

    def test_convert_preserves_all_data(self, coordinator, mock_qa_result):
        """Test that conversion preserves all important data from ToolIssue."""
        issues = coordinator._convert_parsed_issues_to_issues(
            "complexipy", mock_qa_result.parsed_issues
        )

        assert len(issues) == 2

        # Check first issue
        assert issues[0].file_path == "/path/to/file1.py"
        assert issues[0].line_number == 42
        assert issues[0].message == "Function 'test_func' has complexity 20"
        assert issues[0].details[0] == "code: C001"
        assert issues[0].details[1] == "suggestion: Refactor function"
        assert issues[0].stage == "complexipy"

        # Check second issue
        assert issues[1].file_path == "/path/to/file2.py"
        assert issues[1].line_number == 100
        assert issues[1].message == "Function 'complex_func' has complexity 25"

    def test_tool_has_qa_adapter(self, coordinator):
        """Test _tool_has_qa_adapter returns correct values."""
        # Tools with adapters
        assert coordinator._tool_has_qa_adapter("complexipy")
        assert coordinator._tool_has_qa_adapter("skylos")
        assert coordinator._tool_has_qa_adapter("ruff")
        assert coordinator._tool_has_qa_adapter("mypy")

        # Tools without adapters (hypothetically)
        assert not coordinator._tool_has_qa_adapter("nonexistent-tool")


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def coordinator(self):
        """Create AutofixCoordinator instance."""
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_convert_empty_list(self, coordinator):
        """Test converting empty issue list."""
        issues = coordinator._convert_parsed_issues_to_issues("test", [])
        assert issues == []

    def test_convert_with_none_values(self, coordinator):
        """Test handling of None values in ToolIssue fields."""
        tool_issues = [
            {
                "file_path": "/path/to/file.py",
                "line_number": None,
                "column_number": None,
                "message": "Test",
                "code": None,
                "suggestion": None,
            }
        ]

        issues = coordinator._convert_parsed_issues_to_issues("test", tool_issues)

        assert len(issues) == 1
        assert issues[0].line_number is None
        # None values should be filtered from details
        assert not any("None" in detail for detail in issues[0].details)

    def test_integration_with_real_qa_result(self, coordinator):
        """Test full integration with realistic QAResult from complexipy."""
        # Simulate QAResult from complexipy adapter
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            message="Found 14 complexity issues",
            parsed_issues=[
                {
                    "file_path": "crackerjack/adapters/ai/base.py",
                    "line_number": 42,
                    "message": "Function '_fix_code_issue_with_retry' has complexity 18",
                    "severity": "error",
                    "code": "C001",
                }
            ],
            files_checked=[Path("crackerjack/adapters/ai/base.py")],
            issues_found=1,
            execution_time_ms=500.0,
        )

        # Convert using the integrated method
        issues = coordinator._convert_parsed_issues_to_issues(
            "complexipy", qa_result.parsed_issues
        )

        assert len(issues) == 1
        assert issues[0].type == IssueType.COMPLEXITY
        assert issues[0].severity == Priority.HIGH
        assert issues[0].stage == "complexipy"
        assert "_fix_code_issue_with_retry" in issues[0].message


class TestPriority1Improvements:
    """Priority 1 improvements from 5-agent review."""

    @pytest.fixture
    def coordinator(self):
        """Create AutofixCoordinator instance."""
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_file_path_validation_skips_issues_without_path(self, coordinator):
        """Test that issues without file_path are skipped."""
        tool_issues = [
            {
                "message": "Error without file path",
                "severity": "error",
                # Missing file_path - should be skipped
            }
        ]

        issues = coordinator._convert_parsed_issues_to_issues("test", tool_issues)

        # Issue should be skipped (logged but not added)
        assert len(issues) == 0

    def test_file_path_validation_allows_valid_issues(self, coordinator):
        """Test that issues with file_path are processed normally."""
        tool_issues = [
            {
                "file_path": "/path/to/file.py",
                "message": "Valid issue",
                "severity": "error",
            }
        ]

        issues = coordinator._convert_parsed_issues_to_issues("test", tool_issues)

        # Issue should be processed
        assert len(issues) == 1
        assert issues[0].file_path == "/path/to/file.py"

    def test_mixed_qa_raw_parsing_scenario(self, coordinator):
        """Test workflow with some hooks using QAResult and others using raw parsing."""
        from crackerjack.parsers.factory import ParserFactory

        # Create QAResult with parsed issues
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            message="Found 1 complexity issue",
            parsed_issues=[
                {
                    "file_path": "/path/to/file1.py",
                    "line_number": 42,
                    "message": "Function has high complexity",
                    "severity": "error",
                }
            ],
            files_checked=[Path("/path/to/file1.py")],
            issues_found=1,
        )

        # Scenario 1: Use QAResult (complexipy)
        qa_issues = coordinator._parse_hook_to_issues(
            "complexipy", "raw output", qa_result=qa_result
        )

        # Scenario 2: Fall back to raw parsing (hypothetical tool without adapter)
        with patch.object(ParserFactory, "parse_with_validation") as mock_parse:
            mock_parse.return_value = [
                Issue(
                    type=IssueType.FORMATTING,
                    severity=Priority.HIGH,
                    message="Raw parsed issue",
                    file_path="/path/to/file2.py",
                    stage="unknown-tool",
                )
            ]

            raw_issues = coordinator._parse_hook_to_issues(
                "unknown-tool", "raw output", qa_result=None
            )

        # Verify both paths work
        assert len(qa_issues) == 1
        assert qa_issues[0].message == "Function has high complexity"
        assert qa_issues[0].file_path == "/path/to/file1.py"

        assert len(raw_issues) == 1
        assert raw_issues[0].message == "Raw parsed issue"
        assert raw_issues[0].file_path == "/path/to/file2.py"

    def test_empty_parsed_issues_edge_case(self, coordinator):
        """Test behavior when QAResult has empty parsed_issues list."""
        # Create QAResult with empty parsed_issues
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.SUCCESS,
            message="No issues found",
            parsed_issues=[],  # Empty list
            files_checked=[],
            issues_found=0,
        )

        # Should return empty list without errors
        issues = coordinator._parse_hook_to_issues(
            "complexipy", "No issues", qa_result=qa_result
        )

        assert issues == []
        assert len(issues) == 0

    def test_adapter_failure_falls_back_to_raw_parsing(self, coordinator):
        """Test that adapter failures fall back to raw parsing gracefully."""
        from crackerjack.parsers.factory import ParserFactory

        # Simulate QAResult with no parsed_issues (adapter failure scenario)
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            message="Adapter ran but found no issues",
            parsed_issues=[],  # Empty - should trigger fallback
            files_checked=[],
            issues_found=0,
        )

        # Mock the parser factory to provide fallback
        with patch.object(ParserFactory, "parse_with_validation") as mock_parse:
            mock_parse.return_value = [
                Issue(
                    type=IssueType.COMPLEXITY,
                    severity=Priority.HIGH,
                    message="Fallback parsed issue",
                    file_path="/path/to/file.py",
                    stage="complexipy",
                )
            ]

            # Should fall back to raw parsing when parsed_issues is empty
            issues = coordinator._parse_hook_to_issues(
                "complexipy", "raw output for parsing", qa_result=qa_result
            )

        # Verify fallback worked
        assert len(issues) == 1
        assert issues[0].message == "Fallback parsed issue"

    def test_run_qa_adapters_handles_missing_adapter_gracefully(self, coordinator):
        """Test that _run_qa_adapters_for_hooks handles missing adapters gracefully."""
        # Create mock hook result for a tool without an adapter
        mock_hook_result = MagicMock()
        mock_hook_result.status = "failed"
        mock_hook_result.name = "nonexistent-tool"

        # Should return empty dict (tool not in adapters list)
        qa_results = coordinator._run_qa_adapters_for_hooks([mock_hook_result])

        # Verify graceful handling
        assert qa_results == {}
        assert len(qa_results) == 0

    def test_run_qa_adapters_filters_non_failed_hooks(self, coordinator):
        """Test that _run_qa_adapters_for_hooks only processes failed hooks."""
        # Create mock hook results with different statuses
        passed_hook = MagicMock()
        passed_hook.status = "passed"
        passed_hook.name = "complexipy"

        failed_hook = MagicMock()
        failed_hook.status = "failed"
        failed_hook.name = "skylos"

        # Should return empty dict (passed hooks are skipped, skylos has no QA adapter in test)
        qa_results = coordinator._run_qa_adapters_for_hooks([passed_hook, failed_hook])

        # Verify that passed hook was skipped
        assert "complexipy" not in qa_results  # Not run (status: passed)
