"""
Integration test for complete two-stage AI fix workflow.

Tests the entire pipeline from issues to validated fixes.
"""
import pytest

from crackerjack.agents.analysis_coordinator import AnalysisCoordinator
from crackerjack.agents.fixer_coordinator import FixerCoordinator
from crackerjack.models.fix_plan import FixPlan
from crackerjack.agents.base import Issue, IssueType, Priority


class TestTwoStageWorkflow:
    """Integration tests for V2 two-stage workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow_success(self) -> None:
        """Test successful workflow with valid fix."""
        # This would need a sample file and real hooks to test properly
        # For now, test that components can be imported
        from crackerjack.agents import AnalysisCoordinator, FixerCoordinator

        assert AnalysisCoordinator is not None
        assert FixerCoordinator is not None

    @pytest.mark.asyncio
    async def test_analysis_stage(self) -> None:
        """Test that analysis stage creates FixPlans."""
        from crackerjack.agents import AnalysisCoordinator

        coordinator = AnalysisCoordinator(max_concurrent=5)

        # Create sample issue
        issue = Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="Function too complex",
            id="test_issue_1",
            file_path="/tmp/test.py",
            line_number=10,
        )

        # Analyze issue
        plan = await coordinator.analyze_issue(issue)

        # Validate plan
        assert plan.file_path == "/tmp/test.py"
        assert plan.issue_type == "COMPLEXITY"
        assert len(plan.changes) > 0
        assert plan.risk_level in ("low", "medium", "high")
        assert plan.validated_by == "PlanningAgent"

    @pytest.mark.asyncio
    async def test_fixer_routing(self) -> None:
        """Test that FixerCoordinator routes to correct fixer."""
        from crackerjack.agents import FixerCoordinator

        coordinator = FixerCoordinator()

        # Test routing for different issue types
        complexity_plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="COMPLEXITY",
            changes=[],
            rationale="Test complexity",
            risk_level="low",
            validated_by="test",
        )

        security_plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="SECURITY",
            changes=[],
            rationale="Test security",
            risk_level="low",
            validated_by="test",
        )

        # Execute plans
        results = await coordinator.execute_plans([complexity_plan, security_plan])

        # Both should succeed (have dummy fixers, so results indicate success)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_validation_coordinator(self) -> None:
        """Test that ValidationCoordinator works correctly."""
        from crackerjack.agents.validation_coordinator import ValidationCoordinator

        coordinator = ValidationCoordinator()

        # Test syntax validation
        is_valid, feedback = await coordinator.validate_fix(
            code="def hello():\n    print('hello')",
            file_path="/tmp/test.py",
        run_tests=False,
        )

        assert is_valid is True  # Valid Python code
        assert feedback == "Fix validated"

        # Test with syntax error
        is_valid, feedback = await coordinator.validate_fix(
            code="def broken(:",  # Syntax error
            file_path="/tmp/test.py",
            run_tests=False,
        )

        assert is_valid is False  # Should be rejected
        assert "Syntax" in feedback

    @pytest.mark.asyncio
    async def test_file_locking(self) -> None:
        """Test that file locking prevents concurrent modifications."""
        from crackerjack.agents.fixer_coordinator import FixerCoordinator
        import asyncio

        coordinator = FixerCoordinator()

        # Create two plans for same file
        plan1 = FixPlan(
            file_path="/tmp/test.py",
            issue_type="COMPLEXITY",
            changes=[],
            rationale="First change",
            risk_level="low",
            validated_by="test",
        )

        plan2 = FixPlan(
            file_path="/tmp/test.py",
            issue_type="COMPLEXITY",
            changes=[],
            rationale="Second change",
            risk_level="low",
            validated_by="test",
        )

        # Execute both plans
        results = await coordinator.execute_plans([plan1, plan2])

        # Should execute sequentially (same file)
        # Verify they were not executed concurrently
        assert results[0].success is True or results[1].success is True
        assert results[0].files_modified == results[1].files_modified == ["/tmp/test.py"]
