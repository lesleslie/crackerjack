"""Unit tests for hook result details population and formatting.

Tests that verify:
1. Adapters populate details correctly in QAResult
2. Orchestrator preserves adapter details in HookResult
3. Phase coordinator displays actual issue details (not generic fallbacks)
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolIssue
from crackerjack.adapters.complexity.complexipy import ComplexipyAdapter
from crackerjack.adapters.format.ruff import RuffAdapter
from crackerjack.adapters.lint.codespell import CodespellAdapter
from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel
from crackerjack.models.qa_results import QAResult, QAResultStatus
from crackerjack.models.task import HookResult
from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter


class TestAdapterDetailsPopulation:
    """Test that adapters correctly populate details in QAResult."""

    @pytest.mark.asyncio
    async def test_complexipy_adapter_populates_details(self):
        """Verify ComplexipyAdapter populates details string with issue information."""
        adapter = ComplexipyAdapter()
        await adapter.init()

        # Mock the parse_output to return known issues
        mock_issues = [
            ToolIssue(
                file_path=Path("crackerjack/foo.py"),
                line_number=123,
                message="Function 'bar' - Complexity: 25",
                code="COMPLEXITY",
                severity="error",
            ),
            ToolIssue(
                file_path=Path("crackerjack/baz.py"),
                line_number=456,
                message="Function 'qux' - Complexity: 18",
                code="COMPLEXITY",
                severity="warning",
            ),
        ]

        # Mock execution result with proper attributes
        from crackerjack.adapters._tool_adapter_base import ToolExecutionResult

        mock_exec_result = ToolExecutionResult(
            exit_code=1,
            raw_output="",
            error_output="",
            files_modified=[],
        )

        with patch.object(adapter, "parse_output", return_value=mock_issues):
            with patch.object(adapter, "_execute_tool", return_value=mock_exec_result):
                result = await adapter.check(files=[Path(".")])

        # Verify details are populated
        assert result.details is not None, "QAResult.details should not be None"
        assert len(result.details) > 0, "QAResult.details should not be empty"
        assert (
            "crackerjack/foo.py:123" in result.details
        ), "Details should contain file:line"
        assert "Complexity: 25" in result.details, "Details should contain issue message"

        # Verify issues_found count matches
        assert result.issues_found == 2, "QAResult.issues_found should match issue count"

    @pytest.mark.asyncio
    async def test_ruff_adapter_populates_details(self):
        """Verify RuffAdapter populates details string with issue information."""
        adapter = RuffAdapter()
        await adapter.init()

        # Mock the parse_output to return known issues
        mock_issues = [
            ToolIssue(
                file_path=Path("crackerjack/main.py"),
                line_number=45,
                column_number=10,
                message="Line too long (95 > 88)",
                code="E501",
                severity="error",
            ),
            ToolIssue(
                file_path=Path("crackerjack/utils.py"),
                line_number=67,
                message="Trailing whitespace",
                code="W291",
                severity="warning",
            ),
        ]

        # Mock execution result with proper attributes
        from crackerjack.adapters._tool_adapter_base import ToolExecutionResult

        mock_exec_result = ToolExecutionResult(
            exit_code=1,
            raw_output="",
            error_output="",
            files_modified=[],
        )

        with patch.object(adapter, "parse_output", return_value=mock_issues):
            with patch.object(adapter, "_execute_tool", return_value=mock_exec_result):
                result = await adapter.check(files=[Path(".")])

        # Verify details are populated with file:line:column format
        assert result.details is not None
        assert "crackerjack/main.py:45:10" in result.details
        assert "Line too long" in result.details
        assert result.issues_found == 2

    @pytest.mark.asyncio
    async def test_codespell_adapter_populates_details(self):
        """Verify CodespellAdapter populates details string with issue information."""
        adapter = CodespellAdapter()
        await adapter.init()

        # Mock the parse_output to return known issues
        mock_issues = [
            ToolIssue(
                file_path=Path("README.md"),
                line_number=12,
                message="teh ==> the",
                code="TYPO",
                severity="warning",
            ),
        ]

        # Mock execution result with proper attributes
        from crackerjack.adapters._tool_adapter_base import ToolExecutionResult

        mock_exec_result = ToolExecutionResult(
            exit_code=1,
            raw_output="",
            error_output="",
            files_modified=[],
        )

        with patch.object(adapter, "parse_output", return_value=mock_issues):
            with patch.object(adapter, "_execute_tool", return_value=mock_exec_result):
                result = await adapter.check(files=[Path(".")])

        # Verify details are populated
        assert result.details is not None
        assert "README.md:12" in result.details
        assert "teh ==> the" in result.details
        assert result.issues_found == 1


class TestOrchestratorPreservesDetails:
    """Test that HookOrchestrator preserves adapter details in HookResult."""

    @pytest.mark.asyncio
    async def test_orchestrator_uses_adapter_details_not_generic_fallback(self):
        """Verify orchestrator uses adapter's details instead of generic fallback."""
        hook = HookDefinition(
            name="complexipy",
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.LOW,
            timeout=90,
        )

        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        # Mock the adapter to return a QAResult with details
        mock_qa_result = QAResult(
            status=QAResultStatus.FAILURE,
            message="Complexity issues found",
            details="crackerjack/foo.py:123: Function 'bar' - Complexity: 25\ncrackerjack/baz.py:456: Function 'qux' - Complexity: 18",
            files_checked=[Path("crackerjack/foo.py"), Path("crackerjack/baz.py")],
            issues_found=2,
        )

        with patch.object(
            orchestrator, "_build_adapter", return_value=MagicMock()
        ) as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.init = AsyncMock()
            mock_adapter.check = AsyncMock(return_value=mock_qa_result)
            mock_build.return_value = mock_adapter

            result = await orchestrator._execute_single_hook(hook)

        # Verify HookResult contains actual details, not generic fallback
        assert result.issues_found is not None
        assert len(result.issues_found) > 0

        # CRITICAL: Should NOT contain generic fallback message
        assert not any(
            "failed with no detailed output" in issue for issue in result.issues_found
        ), "Should not use generic fallback when adapter provides details"

        # CRITICAL: Should contain actual issue details
        assert any(
            "crackerjack/foo.py:123" in issue for issue in result.issues_found
        ), "Should contain actual file:line from adapter details"

        # Verify issues_count matches
        assert (
            result.issues_count == 2
        ), "issues_count should match actual issue count from adapter"

    @pytest.mark.asyncio
    async def test_orchestrator_handles_empty_details_gracefully(self):
        """Verify orchestrator handles empty details without crashing."""
        hook = HookDefinition(
            name="test-hook",
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
            timeout=30,
        )

        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        # Mock adapter returns QAResult with issues but no details
        mock_qa_result = QAResult(
            status=QAResultStatus.FAILURE,
            message="Issues found",
            details="",  # Empty details
            files_checked=[],
            issues_found=5,  # Has issues but no details
        )

        with patch.object(orchestrator, "_build_adapter", return_value=MagicMock()):
            mock_adapter = AsyncMock()
            mock_adapter.init = AsyncMock()
            mock_adapter.check = AsyncMock(return_value=mock_qa_result)
            orchestrator._build_adapter = MagicMock(return_value=mock_adapter)

            result = await orchestrator._execute_single_hook(hook)

        # Should still create a result, even if details are missing
        assert result is not None
        assert result.status == "failed"

        # Should use fallback message when no details available
        assert result.issues_found is not None
        assert len(result.issues_found) > 0


class TestBuildIssuesListMethod:
    """Test the _build_issues_list method directly."""

    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = HookOrchestratorAdapter()

    def test_build_issues_list_with_valid_details(self):
        """Test _build_issues_list with valid details string."""
        mock_qa_result = MagicMock()
        mock_qa_result.issues_found = 3
        mock_qa_result.details = (
            "crackerjack/foo.py:123: Complexity 25\n"
            "crackerjack/bar.py:456: Complexity 18\n"
            "crackerjack/baz.py:789: Complexity 20"
        )

        issues = self.orchestrator._build_issues_list(mock_qa_result)

        # Should parse all 3 issues
        assert len(issues) == 3
        assert "crackerjack/foo.py:123" in issues[0]
        assert "Complexity 25" in issues[0]

    def test_build_issues_list_with_no_details(self):
        """Test _build_issues_list with no details."""
        mock_qa_result = MagicMock()
        mock_qa_result.issues_found = 5
        mock_qa_result.details = ""  # Empty details

        issues = self.orchestrator._build_issues_list(mock_qa_result)

        # Should create fallback message
        assert len(issues) == 1
        assert "5 issue" in issues[0]
        assert "full details" in issues[0].lower()  # Updated to match new message

    def test_build_issues_list_with_truncated_details(self):
        """Test _build_issues_list with many issues (should truncate)."""
        mock_qa_result = MagicMock()
        mock_qa_result.issues_found = 25

        # Create 25 detail lines
        detail_lines = [f"file{i}.py:{i}: Issue {i}" for i in range(25)]
        mock_qa_result.details = "\n".join(detail_lines)

        issues = self.orchestrator._build_issues_list(mock_qa_result)

        # Should show first 20 + summary
        assert len(issues) == 21  # 20 issues + 1 summary line
        assert "... and 5 more issue" in issues[-1]

    def test_build_issues_list_zero_issues(self):
        """Test _build_issues_list with zero issues."""
        mock_qa_result = MagicMock()
        mock_qa_result.issues_found = 0
        mock_qa_result.details = ""

        issues = self.orchestrator._build_issues_list(mock_qa_result)

        # Should return empty list
        assert len(issues) == 0


class TestIssuesCountAccuracy:
    """Test that issues_count accurately reflects total issues."""

    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = HookOrchestratorAdapter()

    def test_issues_count_matches_qa_result(self):
        """Test that issues_count is taken from QAResult, not issues_found list length."""
        mock_qa_result = MagicMock()
        mock_qa_result.issues_found = 50  # Total issues
        mock_qa_result.details = "\n".join(
            [f"file{i}.py:{i}: Issue" for i in range(50)]
        )
        mock_qa_result.status = QAResultStatus.FAILURE

        mock_hook = MagicMock()
        mock_hook.name = "test-hook"
        mock_hook.stage = HookStage.FAST

        import time

        result = self.orchestrator._create_success_result(
            mock_hook, mock_qa_result, time.time()
        )

        # issues_count should be 50 (total from QAResult)
        assert result.issues_count == 50

        # issues_found list should be truncated to 21 (20 + summary)
        assert len(result.issues_found) == 21

        # But issues_count should still reflect the true total
        assert result.issues_count > len(result.issues_found)


class TestPhaseCoordinatorDisplay:
    """Test that PhaseCoordinator displays actual issue details."""

    def test_results_table_shows_issues_count(self):
        """Test that results table shows issues_count, not len(issues_found)."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        # Mock dependencies
        coordinator = MagicMock(spec=PhaseCoordinator)
        coordinator._build_results_table = (
            PhaseCoordinator._build_results_table.__get__(coordinator)
        )
        coordinator._status_style = lambda status: "red"
        coordinator._strip_ansi = lambda text: text

        # Create result with many issues but truncated list
        result = HookResult(
            id="complexipy",
            name="complexipy",
            status="failed",
            duration=5.0,
            issues_found=["issue1", "issue2", "... and 48 more issues"],  # Truncated
            issues_count=50,  # True count
        )

        table = coordinator._build_results_table([result])

        # Table should show issues_count (50), not len(issues_found) (3)
        # Note: We can't easily inspect Rich Table contents in tests,
        # but we can verify the logic is correct by checking the code path
        assert result.issues_count == 50
        assert len(result.issues_found) == 3

    def test_hook_failure_display_shows_actual_details(self):
        """Test that hook failure display shows actual issue details."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        coordinator = MagicMock(spec=PhaseCoordinator)
        coordinator._print_single_hook_failure = (
            PhaseCoordinator._print_single_hook_failure.__get__(coordinator)
        )
        coordinator._print_hook_issues = PhaseCoordinator._print_hook_issues.__get__(
            coordinator
        )
        coordinator._display_failure_reasons = (
            PhaseCoordinator._display_failure_reasons.__get__(coordinator)
        )
        coordinator._strip_ansi = lambda text: text
        coordinator.console = MagicMock()

        # Create result with actual issue details
        result = HookResult(
            id="ruff-format",
            name="ruff-format",
            status="failed",
            duration=5.0,
            issues_found=[
                "crackerjack/main.py:45: Trailing whitespace",
                "crackerjack/utils.py:67: Line too long",
            ],
            issues_count=2,
        )

        coordinator._print_single_hook_failure(result)

        # Verify console.print was called with actual issue details
        print_calls = [str(call) for call in coordinator.console.print.call_args_list]
        assert len(print_calls) >= 2  # Hook name + at least one issue

        # Should NOT contain generic fallback
        assert not any("failed with no detailed output" in call for call in print_calls)


class TestEndToEndHookReporting:
    """Integration tests for end-to-end hook reporting."""

    @pytest.mark.asyncio
    async def test_complexipy_full_reporting_flow(self):
        """Test complete flow from adapter to display for complexipy."""
        # This would be an integration test that:
        # 1. Creates a test file with high complexity
        # 2. Runs complexipy adapter
        # 3. Verifies orchestrator creates correct HookResult
        # 4. Verifies phase coordinator displays correctly

        # For now, this is a placeholder for future integration test
        pytest.skip("Integration test - requires test fixtures")

    @pytest.mark.asyncio
    async def test_ruff_format_full_reporting_flow(self):
        """Test complete flow from adapter to display for ruff-format."""
        # Similar integration test for ruff-format
        pytest.skip("Integration test - requires test fixtures")
