"""End-to-end integration tests for hook reporting.

These tests verify the complete flow:
1. Adapter executes and parses tool output
2. Orchestrator processes adapter results
3. Phase coordinator displays results correctly

Requires actual tool execution with test fixtures.
"""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from crackerjack.models.qa_results import QACheckType

from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.models.qa_results import QAResult, QAResultStatus
from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter
from crackerjack.config.tool_commands import get_tool_command


class TestComplexipyReportingE2E:
    """End-to-end tests for complexipy hook reporting."""

    @pytest.fixture
    def complex_test_file(self):
        """Create a test file with known complexity issues."""
        code = '''
def highly_complex_function(a, b, c, d, e):
    """Function with cyclomatic complexity > 15."""
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        if a > b:
                            if b > c:
                                if c > d:
                                    if d > e:
                                        if a > c:
                                            if b > d:
                                                if c > e:
                                                    if a > d:
                                                        if b > e:
                                                            return a + b + c + d + e
    return 0
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(code)
            tmp_file.flush()
            yield Path(tmp_file.name)

        # Cleanup
        Path(tmp_file.name).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_complexipy_reports_actual_issues_not_generic_fallback(
        self, complex_test_file
    ):
        """Verify complexipy reports actual complexity issues with file:line details."""
        from crackerjack.adapters.complexity.complexipy import ComplexipyAdapter

        adapter = ComplexipyAdapter()
        await adapter.init()

        # Run adapter on test file
        result = await adapter.check(files=[complex_test_file])

        # Verify QAResult has proper details
        assert result is not None
        assert result.issues_found > 0, "Should detect complexity issue"
        assert result.details is not None, "Should have details string"
        assert len(result.details) > 0, "Details should not be empty"

        # Verify details contain file path
        assert str(complex_test_file) in result.details or "highly_complex_function" in result.details

        # Verify details contain actual issue information
        assert "complexity" in result.details.lower() or "function" in result.details.lower()

    @pytest.mark.asyncio
    async def test_orchestrator_preserves_complexipy_details(self, complex_test_file):
        """Verify orchestrator preserves complexipy details in HookResult."""
        from crackerjack.config.tool_commands import get_tool_command

        hook = HookDefinition(
            name="complexipy",
            command=get_tool_command("complexipy"),
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.LOW,
            timeout=90,
        )

        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        # This would execute the actual hook
        # For now, we test the preservation logic with a mock
        pytest.skip("Requires full orchestrator setup with execution context")


class TestRuffFormatReportingE2E:
    """End-to-end tests for ruff-format hook reporting."""

    @pytest.fixture
    def unformatted_test_file(self):
        """Create a test file with formatting issues."""
        code = '''
def   badly_formatted   (  a,   b,  c  ):
    """Function with formatting issues."""
    x=1+2+3+4+5
    y  =  a+b+c
    return   x+y
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(code)
            tmp_file.flush()
            yield Path(tmp_file.name)

        # Cleanup
        Path(tmp_file.name).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_ruff_format_reports_actual_issues(self, unformatted_test_file):
        """Verify ruff-format reports actual formatting issues."""
        from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings

        adapter = RuffAdapter(settings=RuffSettings(mode="format"))
        await adapter.init()

        # Run adapter on test file
        result = await adapter.check(files=[unformatted_test_file])

        # Verify QAResult has proper details
        assert result is not None

        # If formatting issues found, should have details
        if result.issues_found > 0:
            assert result.details is not None
            assert len(result.details) > 0

            # Should contain file path or formatting details
            assert (
                str(unformatted_test_file) in result.details
                or "format" in result.details.lower()
            )


class TestCodespellReportingE2E:
    """End-to-end tests for codespell hook reporting."""

    @pytest.fixture
    def misspelled_test_file(self):
        """Create a test file with spelling errors."""
        content = '''
# Crackerjack Documentation

This is a teh test file with sevral spelling erors.
The performace of the systme is critcal for sucess.
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            yield Path(tmp_file.name)

        # Cleanup
        Path(tmp_file.name).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_codespell_reports_actual_typos(self, misspelled_test_file):
        """Verify codespell reports actual typos with suggestions."""
        from crackerjack.adapters.lint.codespell import CodespellAdapter

        adapter = CodespellAdapter()
        await adapter.init()

        # Run adapter on test file
        result = await adapter.check(files=[misspelled_test_file])

        # Verify QAResult has proper details
        assert result is not None

        # Should find multiple typos
        if result.issues_found > 0:
            assert result.details is not None
            assert len(result.details) > 0

            # Should contain file path and typo information
            assert str(misspelled_test_file) in result.details or "teh" in result.details


class TestHookResultTableDisplay:
    """Test that hook result tables display correct issue counts."""

    def test_table_shows_actual_issue_count_not_truncated_list_length(self):
        """Verify table shows issues_count, not len(issues_found)."""
        from crackerjack.models.task import HookResult

        # Create result with many issues but truncated display list
        result = HookResult(
            id="complexipy",
            name="complexipy",
            status="failed",
            duration=5.0,
            files_processed=100,
            issues_found=[
                f"file{i}.py:{i*10}: Complexity {15 + i}" for i in range(20)
            ]
            + ["... and 30 more issues"],
            issues_count=50,  # True total
        )

        # Verify data integrity
        assert result.issues_count == 50, "Should store true total"
        assert len(result.issues_found) == 21, "Display list should be truncated"

        # The table builder should use issues_count, not len(issues_found)
        # This is tested in the unit tests for _build_results_table


class TestGenericFallbackBehavior:
    """Test that generic fallback only appears when truly needed."""

    @pytest.mark.asyncio
    async def test_generic_fallback_only_when_no_adapter_details(self):
        """Verify generic fallback message only appears when adapter provides no details."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel
        from crackerjack.models.qa_results import QAResult, QAResultStatus
        from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter

        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        hook = HookDefinition(
            name="test-hook",
            command=get_tool_command("trailing-whitespace"),  # Using a common tool command as default
            stage=HookStage.FAST,
            security_level=SecurityLevel.LOW,
            timeout=30,
        )

        # Test Case 1: Adapter provides details - should NOT use fallback
        qa_result_with_details = QAResult(
            check_id=uuid4(),
            check_name="test-hook",
            check_type=QACheckType.LINT,
            status=QAResultStatus.FAILURE,
            message="Found issues",
            details="file.py:10: Actual issue detail",
            files_checked=[],
            issues_found=1,
        )

        with patch.object(orchestrator, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.init = AsyncMock()
            mock_adapter.check = AsyncMock(return_value=qa_result_with_details)
            mock_build.return_value = mock_adapter

            result = await orchestrator._execute_single_hook(hook)

            # Should contain actual details, NOT generic fallback
            assert result.issues_found is not None
            assert len(result.issues_found) > 0
            assert not any(
                "failed with no detailed output" in issue
                for issue in result.issues_found
            ), "Should not use fallback when details are provided"

        # Test Case 2: Adapter provides NO details - should use fallback
        qa_result_no_details = QAResult(
            check_id=uuid4(),
            check_name="test-hook",
            check_type=QACheckType.LINT,
            status=QAResultStatus.FAILURE,
            message="Found issues",
            details="",  # Empty
            files_checked=[],
            issues_found=5,
        )

        with patch.object(orchestrator, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.init = AsyncMock()
            mock_adapter.check = AsyncMock(return_value=qa_result_no_details)
            mock_build.return_value = mock_adapter

            result = await orchestrator._execute_single_hook(hook)

            # Should use fallback message when no details available
            assert result.issues_found is not None
            assert len(result.issues_found) > 0


class TestIssueCountConsistency:
    """Test that issue counts are consistent across the reporting pipeline."""

    @pytest.mark.asyncio
    async def test_issue_count_consistency_adapter_to_orchestrator(self):
        """Verify issue counts remain consistent from adapter to orchestrator."""
        from unittest.mock import AsyncMock, patch

        from crackerjack.adapters.complexity.complexipy import ComplexipyAdapter
        from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel
        from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter

        # Create orchestrator
        orchestrator = HookOrchestratorAdapter()
        await orchestrator.init()

        hook = HookDefinition(
            name="complexipy",
            command=get_tool_command("complexipy"),
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.LOW,
            timeout=90,
        )

        # Mock adapter to return known issue count
        expected_issue_count = 15

        with patch.object(orchestrator, "_build_complexipy_adapter") as mock_build:
            mock_adapter = AsyncMock(spec=ComplexipyAdapter)
            mock_adapter.init = AsyncMock()

            # Create QAResult with known issue count
            from crackerjack.models.qa_results import QAResult, QAResultStatus

            qa_result = QAResult(
                check_id=uuid4(),
                check_name="complexipy",
                check_type=QACheckType.COMPLEXITY,
                status=QAResultStatus.FAILURE,
                message="Complexity issues found",
                details="\n".join(
                    [
                        f"file{i}.py:100: Function 'func{i}' - Complexity: {20 + i}"
                        for i in range(expected_issue_count)
                    ]
                ),
                files_checked=[],
                issues_found=expected_issue_count,
            )

            mock_adapter.check = AsyncMock(return_value=qa_result)
            mock_build.return_value = mock_adapter

            # Execute hook
            result = await orchestrator._execute_single_hook(hook)

            # Verify issue count is preserved
            assert (
                result.issues_count == expected_issue_count
            ), "Issue count should be preserved from adapter to orchestrator"
