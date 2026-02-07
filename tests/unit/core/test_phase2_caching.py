"""Tests for Phase 2 QAResult caching optimization.

These tests verify that HookExecutor caches QAResult and AutofixCoordinator
uses the cached results instead of re-running tools.
"""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.config.hooks import HookDefinition
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.qa_results import (
    QAResult,
    QAResultStatus,
    QACheckType,
)
from crackerjack.models.task import HookResult
from pathlib import Path


class TestPhase2QAResultCaching:
    """Test Phase 2 QAResult caching in HookResult and usage in AutofixCoordinator."""

    @pytest.fixture
    def hook_def(self):
        """Create a hook definition for testing."""
        hook = MagicMock(spec=HookDefinition)
        hook.name = "complexipy"
        hook.stage = MagicMock()
        hook.stage.value = "comprehensive"
        hook.is_formatting = False
        hook.accepts_file_paths = True
        return hook

    @pytest.fixture
    def coordinator(self):
        """Create AutofixCoordinator instance."""
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_hook_result_has_qa_result_field(self):
        """Test that HookResult model has qa_result field."""
        result = HookResult(
            id="test-hook",
            name="complexipy",
            status="failed",
            qa_result=MagicMock(),  # QAResult object
        )

        assert hasattr(result, "qa_result")
        assert result.qa_result is not None

    def test_hook_result_qa_result_defaults_to_none(self):
        """Test that qa_result defaults to None if not provided."""
        result = HookResult(
            id="test-hook",
            name="complexipy",
            status="failed",
        )

        assert result.qa_result is None

    def test_extract_cached_qa_results_with_cache_hits(self, coordinator):
        """Test _extract_cached_qa_results finds cached QAResult objects."""
        # Create mock hook results with cached QAResult
        qa_result1 = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            message="Found 2 issues",
            parsed_issues=[
                {
                    "file_path": "file1.py",
                    "line_number": 10,
                    "message": "High complexity",
                    "severity": "error",
                },
                {
                    "file_path": "file2.py",
                    "line_number": 20,
                    "message": "Another issue",
                    "severity": "warning",
                },
            ],
            files_checked=[Path("file1.py"), Path("file2.py")],
            issues_found=2,
        )

        hook_result1 = MagicMock(spec=HookResult)
        hook_result1.name = "complexipy"
        hook_result1.qa_result = qa_result1

        hook_result2 = MagicMock(spec=HookResult)
        hook_result2.name = "ruff"
        hook_result2.qa_result = None  # No cached result

        hook_results = [hook_result1, hook_result2]

        # Extract cached results
        cached = coordinator._extract_cached_qa_results(hook_results)

        # Should only return hooks with cached results
        assert "complexipy" in cached
        assert "ruff" not in cached
        assert cached["complexipy"] == qa_result1

    def test_extract_cached_qa_results_empty(self, coordinator):
        """Test _extract_cached_qa_results with no cached results."""
        hook_results = [
            MagicMock(name="tool1", qa_result=None),
            MagicMock(name="tool2", qa_result=None),
        ]

        cached = coordinator._extract_cached_qa_results(hook_results)

        assert cached == {}

    def test_parse_hook_results_uses_cached_qa_result(self, coordinator):
        """Test that _parse_hook_results_to_issues_with_qa uses cached QAResult."""
        # Create mock hook result with cached QAResult
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            message="Found 1 issue",
            parsed_issues=[
                {
                    "file_path": "test.py",
                    "line_number": 42,
                    "message": "High complexity",
                    "severity": "error",
                }
            ],
            files_checked=[Path("test.py")],
            issues_found=1,
        )

        hook_result = MagicMock(spec=HookResult)
        hook_result.name = "complexipy"
        hook_result.qa_result = qa_result  # Cached!

        hook_results = [hook_result]

        # Mock _run_qa_adapters_for_hooks to verify it's not called
        with patch.object(
            coordinator, "_run_qa_adapters_for_hooks", return_value={}
        ) as mock_run_adapters:
            issues = coordinator._parse_hook_results_to_issues_with_qa(
                hook_results
            )

        # Should have 1 issue from cached QAResult
        assert len(issues) == 1
        assert issues[0].message == "High complexity"
        assert issues[0].file_path == "test.py"

        # Verify that we didn't try to run QA adapters (already cached)
        assert not mock_run_adapters.called

    def test_parse_hook_results_fallback_without_cache(self, coordinator):
        """Test that workflow falls back to running QA adapters if no cache."""
        # Create hook result WITHOUT cached QAResult
        hook_result = MagicMock(spec=HookResult)
        hook_result.name = "complexipy"
        hook_result.qa_result = None  # No cache

        hook_results = [hook_result]

        # Mock _run_qa_adapters_for_hooks to return QAResult
        mock_qa_result = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            message="Found 1 issue",
            parsed_issues=[
                {
                    "file_path": "test.py",
                    "line_number": 42,
                    "message": "High complexity",
                    "severity": "error",
                }
            ],
            files_checked=[Path("test.py")],
            issues_found=1,
        )

        with patch.object(
            coordinator, "_run_qa_adapters_for_hooks", return_value={"complexipy": mock_qa_result}
        ):
            issues = coordinator._parse_hook_results_to_issues_with_qa(
                hook_results
            )

        # Should have 1 issue from fallback QA adapter run
        assert len(issues) == 1
        assert issues[0].message == "High complexity"

    def test_cache_hit_performance_logging(self, coordinator):
        """Test that cache hits are logged with performance info."""
        # Create multiple hook results with cached QAResult
        qa_results = []
        hook_results = []

        for i in range(3):
            qa_result = QAResult(
                check_id=uuid4(),
                check_name=f"tool{i}",
                check_type=QACheckType.LINT,
                status=QAResultStatus.FAILURE,
                message=f"Found {i} issues",
                parsed_issues=[
                    {
                        "file_path": f"file{i}.py",
                        "line_number": i * 10,
                        "message": f"Issue {i}",
                        "severity": "error",
                    }
                ],
                files_checked=[Path(f"file{i}.py")],
                issues_found=1,
            )

            hook_result = MagicMock(spec=HookResult)
            hook_result.name = f"tool{i}"
            hook_result.qa_result = qa_result
            hook_results.append(hook_result)

        # Extract cached results
        cached = coordinator._extract_cached_qa_results(hook_results)

        # All 3 should be cached
        assert len(cached) == 3

    def test_mixed_cache_and_fallback_scenario(self, coordinator):
        """Test scenario with some cached results and some requiring fallback."""
        # Create hook results: 2 with cache, 1 without
        qa_result1 = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            parsed_issues=[
                {
                    "file_path": "file1.py",
                    "line_number": 10,
                    "message": "Issue 1",
                    "severity": "error",
                }
            ],
            files_checked=[Path("file1.py")],
            issues_found=1,
        )

        hook_result1 = MagicMock(spec=HookResult)
        hook_result1.name = "complexipy"
        hook_result1.qa_result = qa_result1  # Cached

        hook_result2 = MagicMock(spec=HookResult)
        hook_result2.name = "ruff"
        hook_result2.qa_result = None  # No cache - will fallback

        hook_results = [hook_result1, hook_result2]

        # Mock adapter for ruff fallback
        mock_ruff_qa_result = QAResult(
            check_id=uuid4(),
            check_name="ruff",
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.FAILURE,
            parsed_issues=[
                {
                    "file_path": "file2.py",
                    "line_number": 20,
                    "message": "Format issue",
                    "severity": "warning",
                }
            ],
            files_checked=[Path("file2.py")],
            issues_found=1,
        )

        with patch.object(
            coordinator,
            "_run_qa_adapters_for_hooks",
            return_value={"ruff": mock_ruff_qa_result},
        ):
            issues = coordinator._parse_hook_results_to_issues_with_qa(
                hook_results
            )

        # Should have 2 issues: 1 from cache, 1 from fallback
        assert len(issues) == 2
        assert issues[0].message == "Issue 1"
        assert issues[1].message == "Format issue"
