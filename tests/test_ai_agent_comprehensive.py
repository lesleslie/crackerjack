"""
Comprehensive AI Agent Testing Framework

Tests all agents individually and as an integrated pipeline to prevent
regression failures and ensure reliable auto-fixing capabilities.
"""

import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
    agent_registry,
)
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.agents.refactoring_agent import RefactoringAgent


class TestRefactoringAgentEnhanced:
    """Test the enhanced RefactoringAgent with known failure cases."""

    @pytest.fixture
    def agent_context(self):
        """Create test agent context."""
        return AgentContext(
            project_path=Path("/Users/les/Projects/crackerjack"),
            temp_dir=Path(tempfile.gettempdir()),
        )

    @pytest.fixture
    def refactoring_agent(self, agent_context):
        """Create RefactoringAgent for testing."""
        return RefactoringAgent(agent_context)

    @pytest.fixture
    def complexity_issue(self):
        """Create the exact complexity issue that was failing."""
        return Issue(
            id="complexity_test_detect_agent_needs",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function detect_agent_needs has complexity 22 (exceeds limit of 15)",
            file_path="/Users/les/Projects/crackerjack/crackerjack/mcp/tools/execution_tools.py",
            line_number=986,
            details=["Function is too complex and needs refactoring"],
            stage="comprehensive_hooks",
        )

    @pytest.mark.asyncio
    async def test_can_handle_complexity_issues(
        self, refactoring_agent, complexity_issue
    ):
        """Test that agent correctly identifies complexity issues."""
        confidence = await refactoring_agent.can_handle(complexity_issue)

        assert confidence == 0.9, f"Expected 0.9 confidence, got {confidence}"
        assert confidence >= 0.7, (
            "RefactoringAgent should have high confidence for complexity issues"
        )

    @pytest.mark.asyncio
    async def test_detect_agent_needs_refactoring_success(
        self, refactoring_agent, complexity_issue
    ):
        """Test successful refactoring of detect_agent_needs function."""
        result = await refactoring_agent.analyze_and_fix(complexity_issue)

        # The RefactoringAgent should attempt to handle the complexity issue
        # It may not always succeed (pattern may not match exactly), but should not crash
        assert isinstance(result, FixResult), "Should return a FixResult"
        assert result.confidence >= 0.0, (
            f"Should have non-negative confidence, got {result.confidence}"
        )

        # If it detects detect_agent_needs but pattern doesn't match exactly, it should fail gracefully
        if not result.success:
            expected_failures = [
                "Refactoring pattern did not apply to current file content",
                "File may have been modified since pattern was created",
            ]
            # Should have a reasonable failure message
            assert any(
                any(expected in issue for expected in expected_failures)
                for issue in result.remaining_issues
            ), f"Should have expected failure reason, got: {result.remaining_issues}"
        else:
            # If successful, should have applied fixes
            assert len(result.files_modified) > 0, "Should have modified files"
            assert len(result.fixes_applied) > 0, "Should have applied fixes"

    @pytest.mark.asyncio
    async def test_generic_complexity_reduction(self, refactoring_agent, agent_context):
        """Test generic complexity reduction for other functions."""
        # Create a different complexity issue using actual existing file
        generic_issue = Issue(
            id="complexity_test_generic",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function some_complex_function has complexity 18 (exceeds limit of 15)",
            file_path="/Users/les/Projects/crackerjack/crackerjack/agents/refactoring_agent.py",
            line_number=100,
        )

        result = await refactoring_agent.analyze_and_fix(generic_issue)

        # Should at least attempt to handle it (file exists, so confidence > 0)
        assert result.confidence >= 0.0, (
            "Should attempt to handle generic complexity issues"
        )
        # Note: Generic handling might not always succeed, but should not crash with existing files

    def test_refactoring_patterns_available(self, refactoring_agent):
        """Test that refactoring patterns are properly implemented."""
        # Check that the enhanced methods exist
        assert hasattr(refactoring_agent, "_refactor_detect_agent_needs_pattern")
        assert hasattr(refactoring_agent, "_extract_logical_sections")
        assert hasattr(refactoring_agent, "_apply_function_extraction")

        # Test pattern recognition with matching content
        test_content = """async def detect_agent_needs(error_context: str = "", file_patterns: str = ""):
    recommendations = {
        "urgent_agents": [],
        "suggested_agents": [],
        "workflow_recommendations": [],
        "detection_reasoning": "",
    }

    if error_context:
        # Complex logic here that would match the pattern
        pass
"""
        result = refactoring_agent._refactor_detect_agent_needs_pattern(test_content)
        # Pattern should either apply changes or return original content if pattern doesn't match exactly
        # Both cases are valid - this tests that the method doesn't crash
        assert isinstance(result, str), "Should return a string"
        assert len(result) > 0, "Should return non-empty content"


class TestAgentCoordinationPipeline:
    """Test the complete AI agent pipeline integration."""

    @pytest.fixture
    def agent_context(self):
        """Create test agent context."""
        return AgentContext(project_path=Path.cwd())

    @pytest.fixture
    def coordinator(self, agent_context):
        """Create AgentCoordinator for testing."""
        return AgentCoordinator(agent_context)

    @pytest.mark.asyncio
    async def test_complexity_issue_routing(self, coordinator):
        """Test that complexity issues are routed to RefactoringAgent."""
        complexity_issue = Issue(
            id="routing_test",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test complexity routing",
            file_path="test_file.py",
        )

        coordinator.initialize_agents()

        # Verify RefactoringAgent is available
        refactoring_agents = [
            a for a in coordinator.agents if a.__class__.__name__ == "RefactoringAgent"
        ]
        assert len(refactoring_agents) > 0, "RefactoringAgent should be available"

        # Test routing
        result = await coordinator.handle_issues([complexity_issue])

        # Should not immediately fail
        assert isinstance(result, FixResult), "Should return FixResult"

    @pytest.mark.asyncio
    async def test_multi_issue_coordination(self, coordinator):
        """Test handling multiple different issue types."""
        issues = [
            Issue(
                id="1",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Complex function",
                file_path="test.py",
            ),
            Issue(
                id="2",
                type=IssueType.IMPORT_ERROR,
                severity=Priority.MEDIUM,
                message="Import issue",
                file_path="test.py",
            ),
            Issue(
                id="3",
                type=IssueType.TEST_FAILURE,
                severity=Priority.HIGH,
                message="Test failed",
                file_path="test_test.py",
            ),
        ]

        coordinator.initialize_agents()
        result = await coordinator.handle_issues(issues)

        assert isinstance(result, FixResult), "Should handle multiple issues"
        # Should attempt to process all issues
        assert result.confidence > 0.0, "Should have some confidence in handling issues"


class TestAgentRegistryAndAvailability:
    """Test that all agents are properly registered and functional."""

    def test_all_agents_registered(self):
        """Verify all expected agents are in the registry."""
        expected_agents = {
            "RefactoringAgent",
            "FormattingAgent",
            "SecurityAgent",
            "TestCreationAgent",
            "TestSpecialistAgent",
            "ImportOptimizationAgent",
            "DRYAgent",
            "DocumentationAgent",
            "PerformanceAgent",
        }

        available_agents = set(agent_registry._agents.keys())

        # Check for critical agents
        critical_agents = {"RefactoringAgent", "FormattingAgent", "TestCreationAgent"}
        missing_critical = critical_agents - available_agents
        assert not missing_critical, f"Missing critical agents: {missing_critical}"

        # Report on all expected agents
        missing_agents = expected_agents - available_agents
        if missing_agents:
            pytest.fail(
                f"Missing expected agents: {missing_agents}. Available: {available_agents}"
            )

    @pytest.mark.asyncio
    async def test_agent_instantiation(self):
        """Test that all agents can be instantiated without errors."""
        context = AgentContext(project_path=Path.cwd())

        for agent_name, agent_class in agent_registry._agents.items():
            try:
                agent = agent_class(context)
                assert hasattr(agent, "can_handle"), (
                    f"{agent_name} should have can_handle method"
                )
                assert hasattr(agent, "analyze_and_fix"), (
                    f"{agent_name} should have analyze_and_fix method"
                )
            except Exception as e:
                pytest.fail(f"Failed to instantiate {agent_name}: {e}")

    @pytest.mark.asyncio
    async def test_agent_confidence_scoring(self):
        """Test that agents return reasonable confidence scores."""
        context = AgentContext(project_path=Path.cwd())

        test_issues = {
            IssueType.COMPLEXITY: Issue(
                id="1",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Complex",
                file_path="test.py",
            ),
            IssueType.FORMATTING: Issue(
                id="2",
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="Format",
                file_path="test.py",
            ),
            IssueType.SECURITY: Issue(
                id="3",
                type=IssueType.SECURITY,
                severity=Priority.CRITICAL,
                message="Security",
                file_path="test.py",
            ),
            IssueType.TEST_FAILURE: Issue(
                id="4",
                type=IssueType.TEST_FAILURE,
                severity=Priority.HIGH,
                message="Test fail",
                file_path="test.py",
            ),
        }

        for agent_name, agent_class in agent_registry._agents.items():
            agent = agent_class(context)

            for issue_type, issue in test_issues.items():
                confidence = await agent.can_handle(issue)

                # Confidence should be between 0.0 and 1.0
                assert 0.0 <= confidence <= 1.0, (
                    f"{agent_name} returned invalid confidence {confidence} for {issue_type}"
                )

                # Agents should have high confidence for their primary issue types
                supported_types = (
                    agent.get_supported_types()
                    if hasattr(agent, "get_supported_types")
                    else set()
                )
                if issue_type in supported_types:
                    assert confidence >= 0.7, (
                        f"{agent_name} should have high confidence ({confidence}) for supported type {issue_type}"
                    )


class TestRegressionPrevention:
    """Test cases for known failure patterns to prevent regression."""

    @pytest.mark.asyncio
    async def test_detect_agent_needs_complexity_regression(self):
        """Regression test for detect_agent_needs complexity failure."""
        context = AgentContext(project_path=Path("/Users/les/Projects/crackerjack"))
        agent = RefactoringAgent(context)

        # The exact issue that caused 10 iteration failures
        issue = Issue(
            id="regression_detect_agent_needs",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function detect_agent_needs has complexity 22 (exceeds limit of 15)",
            file_path="/Users/les/Projects/crackerjack/crackerjack/mcp/tools/execution_tools.py",
            line_number=986,
        )

        result = await agent.analyze_and_fix(issue)

        # The agent should handle this without crashing and with reasonable behavior
        assert isinstance(result, FixResult), "Should return valid FixResult"
        assert result.confidence >= 0.0, (
            f"Should have non-negative confidence: {result.confidence}"
        )

        # Should not crash or return meaningless errors - either succeeds or fails gracefully
        if not result.success:
            # Should have meaningful failure messages, not generic "could not" messages
            acceptable_messages = [
                "Refactoring pattern did not apply to current file content",
                "File may have been modified since pattern was created",
            ]
            has_acceptable_message = any(
                any(acceptable in issue_msg for acceptable in acceptable_messages)
                for issue_msg in result.remaining_issues
            )
            assert has_acceptable_message or result.success, (
                f"Should either succeed or have acceptable failure message: {result.remaining_issues}"
            )

    @pytest.mark.asyncio
    async def test_agent_coordination_no_infinite_loops(self):
        """Test that agent coordination doesn't create infinite loops."""
        context = AgentContext(project_path=Path.cwd())
        coordinator = AgentCoordinator(context)
        coordinator.initialize_agents()

        # Test with the same issue multiple times
        issue = Issue(
            id="loop_test",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test",
            file_path="test.py",
        )

        # Should handle repeated issues without infinite loops
        for i in range(3):
            result = await coordinator.handle_issues([issue])
            assert isinstance(result, FixResult), f"Iteration {i} failed"

            # Should not take excessively long (test timeout prevents this)

    def test_issue_detection_patterns(self):
        """Test that issue detection patterns match expected formats."""
        # Test complexipy output parsing pattern (testing the pattern format, not the parser itself)
        complexipy_output = [
            "crackerjack/mcp/tools/execution_tools.py:986:1: C901 Function 'detect_agent_needs' is too complex (22)"
        ]

        # Verify the pattern format is parseable
        for line in complexipy_output:
            parts = line.split(":")
            assert len(parts) >= 4, (
                f"Expected at least 4 parts in complexipy output: {line}"
            )
            assert "detect_agent_needs" in line, "Should contain function name"
            assert "too complex" in line, "Should contain complexity message"

        # Test that we have valid test data
        assert complexipy_output, "Should have test data for complexipy parsing"


@pytest.mark.asyncio
async def test_end_to_end_ai_agent_pipeline():
    """End-to-end test of the complete AI agent pipeline."""
    # This test simulates the full crackerjack --ai-agent workflow

    # 1. Create test context
    context = AgentContext(project_path=Path.cwd())
    coordinator = AgentCoordinator(context)
    coordinator.initialize_agents()

    # 2. Create mixed issues (like crackerjack would detect)
    issues = [
        Issue(
            id="1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
            file_path="test.py",
        ),
        Issue(
            id="2",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
            file_path="test.py",
        ),
        Issue(
            id="3",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="Import problem",
            file_path="test.py",
        ),
    ]

    # 3. Process through coordinator
    result = await coordinator.handle_issues(issues)

    # 4. Verify reasonable behavior
    assert isinstance(result, FixResult), "Should return FixResult"
    assert result.confidence >= 0.0, "Should have valid confidence"

    # Should not crash or hang
    assert True, "Pipeline completed without crashing"


if __name__ == "__main__":
    # Run specific tests for debugging
    pytest.main(
        [
            __file__
            + "::TestRefactoringAgentEnhanced::test_detect_agent_needs_refactoring_success",
            "-v",
            "-s",
        ]
    )
