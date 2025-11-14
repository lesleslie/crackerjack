"""Unit tests for ArchitectAgent.

Tests multi-issue type handling, external specialist planning,
pattern recommendation, and proactive architecture guidance.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.architect_agent import ArchitectAgent
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority


@pytest.mark.unit
class TestArchitectAgentInitialization:
    """Test ArchitectAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test ArchitectAgent initializes correctly."""
        agent = ArchitectAgent(context)

        assert agent.context == context

    def test_get_supported_types(self, context):
        """Test agent supports comprehensive issue types."""
        agent = ArchitectAgent(context)

        supported = agent.get_supported_types()

        # Should support 12 issue types
        assert IssueType.COMPLEXITY in supported
        assert IssueType.DRY_VIOLATION in supported
        assert IssueType.PERFORMANCE in supported
        assert IssueType.SECURITY in supported
        assert IssueType.DEAD_CODE in supported
        assert IssueType.IMPORT_ERROR in supported
        assert IssueType.TYPE_ERROR in supported
        assert IssueType.TEST_FAILURE in supported
        assert IssueType.FORMATTING in supported
        assert IssueType.DEPENDENCY in supported
        assert IssueType.DOCUMENTATION in supported
        assert IssueType.TEST_ORGANIZATION in supported
        assert len(supported) == 12


@pytest.mark.unit
@pytest.mark.asyncio
class TestArchitectAgentCanHandle:
    """Test issue handling confidence."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ArchitectAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ArchitectAgent(context)

    async def test_can_handle_complexity_high_confidence(self, agent):
        """Test high confidence for complexity issues."""
        issue = Issue(
            id="arch-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="High complexity",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_dry_violation(self, agent):
        """Test confidence for DRY violations."""
        issue = Issue(
            id="arch-002",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="Code duplication",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.85

    async def test_can_handle_performance(self, agent):
        """Test confidence for performance issues."""
        issue = Issue(
            id="arch-003",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance bottleneck",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_security(self, agent):
        """Test confidence for security issues."""
        issue = Issue(
            id="arch-004",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Security vulnerability",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.75

    async def test_can_handle_formatting_low_confidence(self, agent):
        """Test low confidence for formatting issues."""
        issue = Issue(
            id="arch-005",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.4

    async def test_can_handle_import_error(self, agent):
        """Test low confidence for import errors."""
        issue = Issue(
            id="arch-006",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="Import error",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.4

    async def test_can_handle_default_confidence(self, agent):
        """Test default confidence for other issue types."""
        issue = Issue(
            id="arch-007",
            type=IssueType.TEST_FAILURE,
            severity=Priority.MEDIUM,
            message="Test failure",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.6


@pytest.mark.unit
@pytest.mark.asyncio
class TestArchitectAgentPlanning:
    """Test planning logic with external specialist support."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ArchitectAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ArchitectAgent(context)

    async def test_plan_before_action_external_specialist(self, agent):
        """Test planning with external specialist for complexity."""
        issue = Issue(
            id="arch-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex method",
        )

        plan = await agent.plan_before_action(issue)

        assert plan["strategy"] == "external_specialist_guided"
        assert plan["specialist"] == "crackerjack-architect"
        assert "patterns" in plan
        assert "dependencies" in plan
        assert "risks" in plan
        assert "validation" in plan

    async def test_plan_before_action_dry_violation_external(self, agent):
        """Test external specialist plan for DRY violations."""
        issue = Issue(
            id="arch-002",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="Code duplication",
        )

        plan = await agent.plan_before_action(issue)

        assert plan["strategy"] == "external_specialist_guided"
        assert plan["approach"] == "extract_common_patterns"

    async def test_plan_before_action_internal_strategy(self, agent):
        """Test internal planning for simpler issues."""
        issue = Issue(
            id="arch-003",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        plan = await agent.plan_before_action(issue)

        assert plan["strategy"] == "internal_pattern_based"
        assert "patterns" in plan
        assert plan["risks"] == ["minimal"]

    async def test_needs_external_specialist_complexity(self, agent):
        """Test external specialist detection for complexity."""
        issue = Issue(
            id="test",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex",
        )

        needs_external = await agent._needs_external_specialist(issue)

        assert needs_external is True

    async def test_needs_external_specialist_dry_violation(self, agent):
        """Test external specialist detection for DRY."""
        issue = Issue(
            id="test",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="Duplication",
        )

        needs_external = await agent._needs_external_specialist(issue)

        assert needs_external is True

    async def test_needs_external_specialist_other_types(self, agent):
        """Test no external specialist for other types."""
        issue = Issue(
            id="test",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format",
        )

        needs_external = await agent._needs_external_specialist(issue)

        assert needs_external is False


@pytest.mark.unit
class TestArchitectAgentPatternRecommendations:
    """Test pattern recommendation logic."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ArchitectAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ArchitectAgent(context)

    def test_get_specialist_approach_complexity(self, agent):
        """Test specialist approach for complexity."""
        issue = Issue(type=IssueType.COMPLEXITY, message="Complex", severity=Priority.HIGH)

        approach = agent._get_specialist_approach(issue)

        assert approach == "break_into_helper_methods"

    def test_get_specialist_approach_dry_violation(self, agent):
        """Test specialist approach for DRY violations."""
        issue = Issue(type=IssueType.DRY_VIOLATION, message="DRY", severity=Priority.MEDIUM)

        approach = agent._get_specialist_approach(issue)

        assert approach == "extract_common_patterns"

    def test_get_specialist_approach_performance(self, agent):
        """Test specialist approach for performance."""
        issue = Issue(type=IssueType.PERFORMANCE, message="Slow", severity=Priority.HIGH)

        approach = agent._get_specialist_approach(issue)

        assert approach == "optimize_algorithms"

    def test_get_specialist_approach_security(self, agent):
        """Test specialist approach for security."""
        issue = Issue(type=IssueType.SECURITY, message="Vulnerable", severity=Priority.CRITICAL)

        approach = agent._get_specialist_approach(issue)

        assert approach == "apply_secure_patterns"

    def test_get_specialist_approach_default(self, agent):
        """Test default specialist approach."""
        issue = Issue(type=IssueType.FORMATTING, message="Format", severity=Priority.LOW)

        approach = agent._get_specialist_approach(issue)

        assert approach == "apply_clean_code_principles"

    def test_get_internal_approach_formatting(self, agent):
        """Test internal approach for formatting."""
        issue = Issue(type=IssueType.FORMATTING, message="Format", severity=Priority.LOW)

        approach = agent._get_internal_approach(issue)

        assert approach == "apply_standard_formatting"

    def test_get_internal_approach_import_error(self, agent):
        """Test internal approach for import errors."""
        issue = Issue(type=IssueType.IMPORT_ERROR, message="Import", severity=Priority.MEDIUM)

        approach = agent._get_internal_approach(issue)

        assert approach == "optimize_imports"

    def test_get_internal_approach_type_error(self, agent):
        """Test internal approach for type errors."""
        issue = Issue(type=IssueType.TYPE_ERROR, message="Type", severity=Priority.MEDIUM)

        approach = agent._get_internal_approach(issue)

        assert approach == "add_type_annotations"

    def test_get_internal_approach_test_failure(self, agent):
        """Test internal approach for test failures."""
        issue = Issue(type=IssueType.TEST_FAILURE, message="Test", severity=Priority.HIGH)

        approach = agent._get_internal_approach(issue)

        assert approach == "fix_test_patterns"

    def test_get_internal_approach_default(self, agent):
        """Test default internal approach."""
        issue = Issue(type=IssueType.DEPENDENCY, message="Dep", severity=Priority.MEDIUM)

        approach = agent._get_internal_approach(issue)

        assert approach == "apply_standard_fix"

    def test_get_recommended_patterns_complexity(self, agent):
        """Test pattern recommendations for complexity."""
        issue = Issue(type=IssueType.COMPLEXITY, message="Complex", severity=Priority.HIGH)

        patterns = agent._get_recommended_patterns(issue)

        assert "extract_method" in patterns
        assert "dependency_injection" in patterns
        assert "protocol_interfaces" in patterns
        assert "helper_methods" in patterns

    def test_get_recommended_patterns_dry_violation(self, agent):
        """Test pattern recommendations for DRY violations."""
        issue = Issue(type=IssueType.DRY_VIOLATION, message="DRY", severity=Priority.MEDIUM)

        patterns = agent._get_recommended_patterns(issue)

        assert "common_base_class" in patterns
        assert "utility_functions" in patterns
        assert "protocol_pattern" in patterns
        assert "composition" in patterns

    def test_get_recommended_patterns_performance(self, agent):
        """Test pattern recommendations for performance."""
        issue = Issue(type=IssueType.PERFORMANCE, message="Slow", severity=Priority.HIGH)

        patterns = agent._get_recommended_patterns(issue)

        assert "list_comprehension" in patterns
        assert "generator_pattern" in patterns
        assert "caching" in patterns
        assert "algorithm_optimization" in patterns

    def test_get_recommended_patterns_security(self, agent):
        """Test pattern recommendations for security."""
        issue = Issue(type=IssueType.SECURITY, message="Vulnerable", severity=Priority.CRITICAL)

        patterns = agent._get_recommended_patterns(issue)

        assert "secure_temp_files" in patterns
        assert "input_validation" in patterns
        assert "safe_subprocess" in patterns
        assert "token_handling" in patterns

    def test_get_recommended_patterns_default(self, agent):
        """Test default pattern recommendations."""
        issue = Issue(type=IssueType.FORMATTING, message="Format", severity=Priority.LOW)

        patterns = agent._get_recommended_patterns(issue)

        assert patterns == ["standard_patterns"]


@pytest.mark.unit
class TestArchitectAgentDependenciesAndRisks:
    """Test dependency and risk analysis."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ArchitectAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ArchitectAgent(context)

    def test_analyze_dependencies_complexity(self, agent):
        """Test dependency analysis for complexity issues."""
        issue = Issue(type=IssueType.COMPLEXITY, message="Complex", severity=Priority.HIGH)

        dependencies = agent._analyze_dependencies(issue)

        assert "update_tests_for_extracted_methods" in dependencies
        assert "update_type_annotations" in dependencies
        assert "verify_imports" in dependencies

    def test_analyze_dependencies_dry_violation(self, agent):
        """Test dependency analysis for DRY violations."""
        issue = Issue(type=IssueType.DRY_VIOLATION, message="DRY", severity=Priority.MEDIUM)

        dependencies = agent._analyze_dependencies(issue)

        assert "update_all_usage_sites" in dependencies
        assert "ensure_backward_compatibility" in dependencies

    def test_analyze_dependencies_default(self, agent):
        """Test default dependency analysis."""
        issue = Issue(type=IssueType.FORMATTING, message="Format", severity=Priority.LOW)

        dependencies = agent._analyze_dependencies(issue)

        assert dependencies == []

    def test_identify_risks_complexity(self, agent):
        """Test risk identification for complexity issues."""
        issue = Issue(type=IssueType.COMPLEXITY, message="Complex", severity=Priority.HIGH)

        risks = agent._identify_risks(issue)

        assert "breaking_existing_functionality" in risks
        assert "changing_method_signatures" in risks
        assert "test_failures" in risks

    def test_identify_risks_dry_violation(self, agent):
        """Test risk identification for DRY violations."""
        issue = Issue(type=IssueType.DRY_VIOLATION, message="DRY", severity=Priority.MEDIUM)

        risks = agent._identify_risks(issue)

        assert "breaking_dependent_code" in risks
        assert "performance_impact" in risks

    def test_identify_risks_default(self, agent):
        """Test default risk identification."""
        issue = Issue(type=IssueType.FORMATTING, message="Format", severity=Priority.LOW)

        risks = agent._identify_risks(issue)

        assert risks == []

    def test_get_validation_steps(self, agent):
        """Test validation step generation."""
        issue = Issue(type=IssueType.COMPLEXITY, message="Complex", severity=Priority.HIGH)

        steps = agent._get_validation_steps(issue)

        assert "run_fast_hooks" in steps
        assert "run_full_tests" in steps
        assert "run_comprehensive_hooks" in steps
        assert "validate_complexity_reduction" in steps
        assert "check_pattern_compliance" in steps


@pytest.mark.unit
class TestArchitectAgentCachedPatterns:
    """Test cached pattern retrieval."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ArchitectAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ArchitectAgent(context)

    def test_get_cached_patterns_for_issue(self, agent):
        """Test retrieving cached patterns for issue."""
        issue = Issue(type=IssueType.COMPLEXITY, message="Complex", severity=Priority.HIGH)

        # Mock cached patterns
        with patch.object(agent, "get_cached_patterns", return_value={}):
            patterns = agent._get_cached_patterns_for_issue(issue)

            # Should return default when no cached patterns
            assert patterns == ["default_pattern"]

    def test_get_cached_patterns_with_matching_patterns(self, agent):
        """Test retrieving matching cached patterns."""
        issue = Issue(type=IssueType.COMPLEXITY, message="Complex", severity=Priority.HIGH)

        cached = {
            "complexity_issue_1": {
                "plan": {"patterns": ["extract_method", "helper_functions"]}
            },
            "complexity_issue_2": {"plan": {"patterns": ["simplify_logic"]}},
            "performance_issue": {"plan": {"patterns": ["optimize_loop"]}},
        }

        with patch.object(agent, "get_cached_patterns", return_value=cached):
            patterns = agent._get_cached_patterns_for_issue(issue)

            # Should find complexity patterns
            assert "extract_method" in patterns
            assert "helper_functions" in patterns
            assert "simplify_logic" in patterns


@pytest.mark.unit
@pytest.mark.asyncio
class TestArchitectAgentExecution:
    """Test execution with different strategies."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ArchitectAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ArchitectAgent(context)

    async def test_analyze_and_fix(self, agent):
        """Test analyze_and_fix delegates to proactive workflow."""
        issue = Issue(
            id="arch-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex method",
        )

        with patch.object(
            agent, "analyze_and_fix_proactively", return_value=FixResult(success=True)
        ) as mock_proactive:
            result = await agent.analyze_and_fix(issue)

            mock_proactive.assert_called_once_with(issue)
            assert result.success is True

    async def test_execute_with_plan_external_specialist(self, agent):
        """Test execution with external specialist strategy."""
        issue = Issue(
            id="arch-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex method",
            file_path="/test/file.py",
        )

        plan = {
            "strategy": "external_specialist_guided",
            "approach": "break_into_helper_methods",
            "patterns": ["extract_method", "dependency_injection"],
            "validation": ["run_tests", "check_complexity"],
        }

        result = await agent._execute_with_plan(issue, plan)

        assert result.success is True
        assert result.confidence == 0.9
        assert "break_into_helper_methods" in result.fixes_applied[0]
        assert "extract_method" in result.fixes_applied[1]
        assert "crackerjack-architect" in result.fixes_applied[2]
        assert len(result.files_modified) == 1

    async def test_execute_with_plan_pattern_based(self, agent):
        """Test execution with pattern-based strategy."""
        issue = Issue(
            id="arch-002",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format issue",
            file_path="/test/file.py",
        )

        plan = {
            "strategy": "internal_pattern_based",
            "approach": "apply_standard_formatting",
            "patterns": ["ruff_format", "import_sort"],
        }

        result = await agent._execute_with_plan(issue, plan)

        assert result.success is True
        assert result.confidence == 0.75
        assert "apply_standard_formatting" in result.fixes_applied[0]
        assert "ruff_format" in result.fixes_applied[1]
        assert len(result.files_modified) == 1

    async def test_execute_specialist_guided_fix(self, agent):
        """Test specialist-guided fix execution."""
        issue = Issue(
            id="arch-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex",
            file_path="/test/file.py",
        )

        plan = {
            "approach": "break_into_helper_methods",
            "patterns": ["extract_method", "helper_functions"],
            "validation": ["run_tests"],
        }

        result = await agent._execute_specialist_guided_fix(issue, plan)

        assert result.success is True
        assert result.confidence == 0.9
        assert len(result.fixes_applied) == 3
        assert len(result.recommendations) == 2
        assert "run_tests" in result.recommendations[0]

    async def test_execute_pattern_based_fix(self, agent):
        """Test pattern-based fix execution."""
        issue = Issue(
            id="arch-002",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format",
            file_path="/test/file.py",
        )

        plan = {
            "approach": "apply_formatting",
            "patterns": ["ruff_format"],
        }

        result = await agent._execute_pattern_based_fix(issue, plan)

        assert result.success is True
        assert result.confidence == 0.75
        assert "apply_formatting" in result.fixes_applied[0]
        assert "ruff_format" in result.fixes_applied[1]

    async def test_execute_with_plan_no_file_path(self, agent):
        """Test execution when issue has no file path."""
        issue = Issue(
            id="arch-003",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex",
            file_path=None,
        )

        plan = {"strategy": "external_specialist_guided", "approach": "refactor"}

        result = await agent._execute_with_plan(issue, plan)

        assert result.success is True
        assert len(result.files_modified) == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestArchitectAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ArchitectAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ArchitectAgent(context)

    async def test_full_workflow_external_specialist(self, agent):
        """Test complete workflow with external specialist."""
        issue = Issue(
            id="arch-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex method with high cyclomatic complexity",
            file_path="/test/complex.py",
        )

        # Plan should require external specialist
        plan = await agent.plan_before_action(issue)
        assert plan["strategy"] == "external_specialist_guided"

        # Execute with plan
        result = await agent._execute_with_plan(issue, plan)
        assert result.success is True
        assert result.confidence == 0.9

    async def test_full_workflow_internal_pattern(self, agent):
        """Test complete workflow with internal patterns."""
        issue = Issue(
            id="arch-002",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting inconsistency",
            file_path="/test/format.py",
        )

        # Plan should use internal strategy
        plan = await agent.plan_before_action(issue)
        assert plan["strategy"] == "internal_pattern_based"

        # Execute with plan
        result = await agent._execute_with_plan(issue, plan)
        assert result.success is True
        assert result.confidence == 0.75

    def test_comprehensive_issue_type_support(self, agent):
        """Test agent supports all expected issue types."""
        supported = agent.get_supported_types()

        # Verify comprehensive coverage
        expected_types = {
            IssueType.COMPLEXITY,
            IssueType.DRY_VIOLATION,
            IssueType.PERFORMANCE,
            IssueType.SECURITY,
            IssueType.DEAD_CODE,
            IssueType.IMPORT_ERROR,
            IssueType.TYPE_ERROR,
            IssueType.TEST_FAILURE,
            IssueType.FORMATTING,
            IssueType.DEPENDENCY,
            IssueType.DOCUMENTATION,
            IssueType.TEST_ORGANIZATION,
        }

        assert supported == expected_types
