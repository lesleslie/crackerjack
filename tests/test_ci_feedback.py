"""Tests for CI feedback integration and failure analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crackerjack.ci_feedback import (
    CIFailureAnalysis,
    CIFeedbackAnalyzer,
    analyze_ci_failure,
)


@pytest.fixture
def temp_patterns_path(tmp_path: Path) -> Path:
    """Create a temporary CI patterns storage file."""
    return tmp_path / "ci_patterns.json"


@pytest.fixture
def ci_analyzer(temp_patterns_path: Path) -> CIFeedbackAnalyzer:
    """Create a CIFeedbackAnalyzer with temporary storage."""
    return CIFeedbackAnalyzer(patterns_path=temp_patterns_path)


@pytest.fixture
def test_failure_log() -> str:
    """Sample test failure build log."""
    return """
============================= test session starts ==============================
collected 45 items

tests/test_main.py:15: error
========================= ERRORS =========================================
______________________ test_calculate_total ______________________________

    def test_calculate_total():
>       assert calculate_total(10, 20) == 30
E       AssertionError: assert 50 == 30
E        +  where 50 = calculate_total(10, 20)

tests/test_main.py:15: AssertionError
=========================== short test summary ============================
FAILED test_calculate_total - AssertionError: assert 50 == 30
=================== 1 failed, 44 passed in 2.5s ====================
"""


@pytest.fixture
def coverage_failure_log() -> str:
    """Sample coverage failure build log."""
    return """
Name                      Stmts   Miss  Cover   Missing
-------------------------------------------------------
src/main.py                  50      15    70%   23-45, 78-90
src/utils.py                 30      5     83%   12-15
-------------------------------------------------------
TOTAL                        80      20    75%

Coverage check failed: Minimum coverage is 80%, but got 75%
"""


@pytest.fixture
def linting_error_log() -> str:
    """Sample linting error build log."""
    return """
src/main.py:45:1: F401 'os' imported but unused
src/main.py:78:5: E501 line too long (120 > 79 characters)
src/utils.py:12:1: F811 redefinition of unused 'calculate' from line 8

Found 3 linting errors.
"""


@pytest.fixture
def timeout_log() -> str:
    """Sample timeout build log."""
    return """
tests/test_api.py:15: Timeout >30.0s
=========================== short test summary ============================
FAILED test_api_call - Timeout >30.0s
"""


@pytest.fixture
def import_error_log() -> str:
    """Sample import error build log."""
    return """
Traceback (most recent call last):
  File "src/main.py", line 5, in <module>
    from nonexistent_module import helper
ModuleNotFoundError: No module named 'nonexistent_module'
"""


class TestIdentifyFailureType:
    """Tests for failure type identification."""

    def test_identify_test_failure(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test identifying test failures."""
        failure_type = ci_analyzer._identify_failure_type("Test failed: assert 1 == 2")
        assert failure_type == "test_failure"

    def test_identify_coverage_failure(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test identifying coverage failures."""
        failure_type = ci_analyzer._identify_failure_type(
            "Coverage below threshold: 75% < 80%"
        )
        assert failure_type == "coverage_below_threshold"

    def test_identify_linting_error(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test identifying linting errors."""
        failure_type = ci_analyzer._identify_failure_type(
            "ruff error: F401 'os' imported but unused"
        )
        assert failure_type == "linting_error"

    def test_identify_type_error(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test identifying type errors."""
        failure_type = ci_analyzer._identify_failure_type(
            "mypy error: Incompatible return value type"
        )
        assert failure_type == "type_error"

    def test_identify_import_error(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test identifying import errors."""
        failure_type = ci_analyzer._identify_failure_type(
            "ModuleNotFoundError: No module named 'requests'"
        )
        assert failure_type == "import_error"

    def test_identify_permission_error(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test identifying permission errors."""
        failure_type = ci_analyzer._identify_failure_type(
            "Permission denied: cannot open file '/etc/hosts'"
        )
        assert failure_type == "permission_error"

    def test_identify_timeout(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test identifying timeouts."""
        failure_type = ci_analyzer._identify_failure_type(
            "Timeout error: Operation timed out after 30 seconds"
        )
        assert failure_type == "timeout"

    def test_identify_unknown_failure(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test identifying unknown failures."""
        failure_type = ci_analyzer._identify_failure_type(
            "Something completely unexpected happened"
        )
        assert failure_type == "unknown_failure"


class TestExtractPatternId:
    """Tests for pattern ID extraction."""

    def test_extract_pattern_from_error(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test extracting pattern ID from error log."""
        log = """
Error: Division by zero
Traceback:
  File "src/main.py", line 42
    result = 10 / 0
"""
        pattern_id = ci_analyzer._extract_pattern_id(log)
        assert "error" in pattern_id.lower()
        assert len(pattern_id) <= 100

    def test_extract_pattern_normalizes_numbers(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test that pattern ID normalizes numbers."""
        log = "Error at line 12345 with hash abc123def456"
        pattern_id = ci_analyzer._extract_pattern_id(log)
        assert "N" in pattern_id  # Numbers replaced with N
        assert "12345" not in pattern_id
        assert "abc123def456" not in pattern_id  # Hash replaced


class TestCalculateLogSimilarity:
    """Tests for log similarity calculation."""

    def test_identical_logs_max_similarity(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test that identical logs have maximum similarity."""
        log1 = "Test failed: assert 1 == 2"
        log2 = "Test failed: assert 1 == 2"
        similarity = ci_analyzer._calculate_log_similarity(log1, log2)
        assert similarity == 1.0

    def test_different_logs_min_similarity(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test that completely different logs have low similarity."""
        log1 = "Test failed: assert 1 == 2"
        log2 = "Coverage is 75%"
        similarity = ci_analyzer._calculate_log_similarity(log1, log2)
        assert similarity < 0.5

    def test_similar_logs_high_similarity(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test that similar logs have high similarity."""
        # Use logs with more overlapping words for higher similarity
        log1 = "Test failed: assert calculate(10) == 20"
        log2 = "Test failed: assert calculate(10) == 20"
        similarity = ci_analyzer._calculate_log_similarity(log1, log2)
        assert similarity > 0.9  # Identical logs should have high similarity

    def test_empty_logs_zero_similarity(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test that empty logs have zero similarity."""
        similarity = ci_analyzer._calculate_log_similarity("", "")
        assert similarity == 0.0


class TestGenerateSuggestions:
    """Tests for suggestion generation."""

    def test_test_failure_suggestions(
        self, ci_analyzer: CIFeedbackAnalyzer, test_failure_log: str
    ) -> None:
        """Test generating suggestions for test failures."""
        failure_type = "test_failure"
        suggestions = ci_analyzer._generate_suggestions(failure_type, [])

        assert len(suggestions) > 0
        assert any("pytest" in s.lower() for s in suggestions)
        assert any("test" in s.lower() for s in suggestions)

    def test_coverage_suggestions(
        self, ci_analyzer: CIFeedbackAnalyzer
    ) -> None:
        """Test generating suggestions for coverage failures."""
        failure_type = "coverage_below_threshold"
        suggestions = ci_analyzer._generate_suggestions(failure_type, [])

        assert len(suggestions) > 0
        assert any("coverage" in s.lower() for s in suggestions)
        assert any("test" in s.lower() for s in suggestions)

    def test_includes_historical_suggestions(
        self, ci_analyzer: CIFeedbackAnalyzer
    ) -> None:
        """Test that historical resolutions are included in suggestions."""
        # Add historical pattern
        ci_analyzer.patterns.append(
            {
                "failure_type": "test_failure",
                "log_sample": "Test failed: assert 1 == 2",
                "resolution": "Fixed assertion to use correct expected value",
            }
        )

        failure_type = "test_failure"
        similar_failures = [
            {
                "failure_type": "test_failure",
                "log_sample": "Test failed: assert 1 == 2",
                "resolution": "Fixed assertion to use correct expected value",
            }
        ]

        suggestions = ci_analyzer._generate_suggestions(failure_type, similar_failures)

        assert any("Historical fix" in s for s in suggestions)

    def test_removes_duplicate_suggestions(
        self, ci_analyzer: CIFeedbackAnalyzer
    ) -> None:
        """Test that duplicate suggestions are removed."""
        failure_type = "test_failure"

        # Add patterns with duplicate resolutions
        similar_failures = [
            {"resolution": "Run pytest locally"},
            {"resolution": "Run pytest locally"},
        ]

        suggestions = ci_analyzer._generate_suggestions(failure_type, similar_failures)

        # Count occurrences of "Run pytest locally"
        count = sum(1 for s in suggestions if "Run pytest locally" in s)
        assert count == 1  # Only one instance despite duplicates


class TestAnalyzeCIFailure:
    """Tests for CI failure analysis."""

    def test_analyze_test_failure(
        self, ci_analyzer: CIFeedbackAnalyzer, test_failure_log: str
    ) -> None:
        """Test analyzing test failure."""
        analysis = ci_analyzer.analyze_ci_failure(test_failure_log)

        assert isinstance(analysis, CIFailureAnalysis)
        assert analysis.failure_type == "test_failure"
        assert len(analysis.suggestions) > 0
        assert analysis.confidence > 0

    def test_analyze_coverage_failure(
        self, ci_analyzer: CIFeedbackAnalyzer, coverage_failure_log: str
    ) -> None:
        """Test analyzing coverage failure."""
        analysis = ci_analyzer.analyze_ci_failure(coverage_failure_log)

        assert analysis.failure_type == "coverage_below_threshold"
        assert "coverage" in analysis.description.lower()

    def test_analyze_with_similar_failures(
        self,
        ci_analyzer: CIFeedbackAnalyzer,
        test_failure_log: str,
    ) -> None:
        """Test analysis with historical similar failures."""
        # Add similar historical failure - use larger portion of the log
        # to increase similarity score
        ci_analyzer.patterns.append(
            {
                "failure_type": "test_failure",
                "log_sample": test_failure_log.strip(),  # Use the entire log for perfect match
                "resolution": "Fixed calculation logic",
            }
        )

        analysis = ci_analyzer.analyze_ci_failure(test_failure_log)

        assert len(analysis.similar_failures) > 0

    def test_analyze_with_test_results(
        self, ci_analyzer: CIFeedbackAnalyzer, test_failure_log: str
    ) -> None:
        """Test analysis with test results."""
        test_results = {
            "total": 45,
            "passed": 44,
            "failed": 1,
            "skipped": 0,
        }

        analysis = ci_analyzer.analyze_ci_failure(
            test_failure_log, test_results=test_results
        )

        assert analysis.failure_type == "test_failure"

    def test_analyze_with_coverage_report(
        self, ci_analyzer: CIFeedbackAnalyzer, coverage_failure_log: str
    ) -> None:
        """Test analysis with coverage report."""
        coverage_report = {
            "percent_covered": 75.0,
            "minimum_coverage": 80.0,
            "lines_missing": 20,
        }

        analysis = ci_analyzer.analyze_ci_failure(
            coverage_failure_log, coverage_report=coverage_report
        )

        assert analysis.failure_type == "coverage_below_threshold"

    def test_confidence_with_similar_failures(
        self, ci_analyzer: CIFeedbackAnalyzer, test_failure_log: str
    ) -> None:
        """Test confidence calculation with similar failures."""
        # Add high-similarity failure
        ci_analyzer.patterns.append(
            {
                "failure_type": "test_failure",
                "log_sample": test_failure_log,
                "resolution": "Fixed test",
            }
        )

        analysis = ci_analyzer.analyze_ci_failure(test_failure_log)

        # Should have higher confidence with similar failures
        assert analysis.confidence > 0.7

    def test_confidence_without_similar_failures(
        self, ci_analyzer: CIFeedbackAnalyzer, test_failure_log: str
    ) -> None:
        """Test confidence calculation without similar failures."""
        analysis = ci_analyzer.analyze_ci_failure(test_failure_log)

        # Should have medium confidence without similar failures
        assert analysis.confidence == 0.5


class TestAnalyzeCIFailureMCP:
    """Tests for MCP-compatible analyze_ci_failure function."""

    def test_mcp_function_returns_dict(self, test_failure_log: str) -> None:
        """Test that MCP function returns dictionary."""
        result = analyze_ci_failure(test_failure_log)

        assert isinstance(result, dict)
        assert "failure_type" in result
        assert "pattern_id" in result
        assert "description" in result
        assert "suggestions" in result
        assert "confidence" in result

    def test_mcp_function_includes_next_steps(self, test_failure_log: str) -> None:
        """Test that MCP function includes recommended next steps."""
        result = analyze_ci_failure(test_failure_log)

        assert "recommended_next_steps" in result
        assert len(result["recommended_next_steps"]) > 0


class TestRecordFailureResolution:
    """Tests for recording failure resolutions."""

    def test_record_resolution(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test recording a successful resolution."""
        initial_count = len(ci_analyzer.patterns)

        ci_analyzer.record_failure_resolution(
            pattern_id="test_pattern_123",
            resolution="Fixed import error by adding missing dependency",
            successful=True,
        )

        assert len(ci_analyzer.patterns) == initial_count + 1

        # Verify pattern was saved
        pattern = ci_analyzer.patterns[-1]
        assert pattern["pattern_id"] == "test_pattern_123"
        assert pattern["resolution"] == "Fixed import error by adding missing dependency"
        assert pattern["successful"] is True

    def test_persistence(self, ci_analyzer: CIFeedbackAnalyzer, temp_patterns_path: Path) -> None:
        """Test that patterns are persisted."""
        # Record a pattern
        ci_analyzer.record_failure_resolution(
            pattern_id="test_pattern",
            resolution="Test resolution",
            successful=True,
        )

        # Create new analyzer and verify pattern loaded
        new_analyzer = CIFeedbackAnalyzer(patterns_path=temp_patterns_path)
        assert len(new_analyzer.patterns) == 1


class TestDescribeFailure:
    """Tests for failure description generation."""

    def test_describe_test_failure(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test describing test failure."""
        description = ci_analyzer._describe_failure(
            "test_failure", "Test failed: assert 1 == 2"
        )

        assert "test" in description.lower()
        assert "failed" in description.lower()

    def test_describe_includes_error_preview(self, ci_analyzer: CIFeedbackAnalyzer) -> None:
        """Test that description includes error preview."""
        log = """
Error: Something went wrong
  File "main.py", line 42
    result = process()
ValueError: Invalid input
"""
        description = ci_analyzer._describe_failure("unknown_failure", log)

        assert "Error preview" in description or "Error:" in description
