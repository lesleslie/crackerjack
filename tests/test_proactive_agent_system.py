import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.architect_agent import ArchitectAgent
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.agents.proactive_agent import ProactiveAgent
from crackerjack.services.quality.pattern_cache import CachedPattern, PatternCache


class TestProactiveAgent:
    @pytest.fixture
    def agent_context(self):
        return AgentContext(project_path=Path.cwd())

    @pytest.fixture
    def test_issue(self):
        return Issue(
            id="test_complexity",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test complexity issue",
            file_path="test.py",
            line_number=10,
        )

    @pytest.fixture
    def mock_proactive_agent(self, agent_context):
        class MockProactiveAgent(ProactiveAgent):
            async def plan_before_action(self, issue):
                return {
                    "strategy": "test_strategy",
                    "patterns": ["test_pattern"],
                    "validation": ["test_validation"],
                }

            async def can_handle(self, issue):
                return 0.8

            async def analyze_and_fix(self, issue):
                return FixResult(success=True, confidence=0.8)

            def get_supported_types(self):
                return {IssueType.COMPLEXITY}

        return MockProactiveAgent(agent_context)

    @pytest.mark.asyncio
    async def test_proactive_fix_with_planning(self, mock_proactive_agent, test_issue):
        result = await mock_proactive_agent.analyze_and_fix_proactively(test_issue)

        assert isinstance(result, FixResult)
        assert result.success
        assert result.confidence == 0.8

        cache_key = mock_proactive_agent._get_planning_cache_key(test_issue)
        assert cache_key in mock_proactive_agent._planning_cache

    @pytest.mark.asyncio
    async def test_planning_cache(self, mock_proactive_agent, test_issue):
        result1 = await mock_proactive_agent.analyze_and_fix_proactively(test_issue)

        result2 = await mock_proactive_agent.analyze_and_fix_proactively(test_issue)

        assert result1.confidence == result2.confidence
        assert len(mock_proactive_agent._planning_cache) == 1

    def test_pattern_caching(self, mock_proactive_agent, test_issue):
        plan = {"strategy": "test", "patterns": ["pattern1"]}
        result = FixResult(success=True, confidence=0.9, fixes_applied=["fix1"])

        mock_proactive_agent._cache_successful_pattern(test_issue, plan, result)

        cached_patterns = mock_proactive_agent.get_cached_patterns()
        assert len(cached_patterns) == 1

        pattern_key = f"{test_issue.type.value}_test"
        assert pattern_key in cached_patterns
        assert cached_patterns[pattern_key]["confidence"] == 0.9

    def test_planning_confidence_scoring(self, mock_proactive_agent, test_issue):
        confidence = mock_proactive_agent.get_planning_confidence(test_issue)
        assert confidence == 0.5

        plan = {"strategy": "test", "patterns": ["pattern1"]}
        result = FixResult(success=True, confidence=0.9)
        mock_proactive_agent._cache_successful_pattern(test_issue, plan, result)

        confidence = mock_proactive_agent.get_planning_confidence(test_issue)
        assert confidence > 0.5


class TestArchitectAgent:
    @pytest.fixture
    def agent_context(self):
        return AgentContext(project_path=Path.cwd())

    @pytest.fixture
    def architect_agent(self, agent_context):
        return ArchitectAgent(agent_context)

    @pytest.fixture
    def complexity_issue(self):
        return Issue(
            id="arch_complexity",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function has complexity 20",
            file_path="complex.py",
            line_number=15,
        )

    @pytest.mark.asyncio
    async def test_can_handle_various_issues(self, architect_agent):
        complexity_issue = Issue(
            id="test", type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="test"
        )
        confidence = await architect_agent.can_handle(complexity_issue)
        assert confidence == 0.9

        dry_issue = Issue(
            id="test",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.HIGH,
            message="test",
        )
        confidence = await architect_agent.can_handle(dry_issue)
        assert confidence == 0.85

        format_issue = Issue(
            id="test", type=IssueType.FORMATTING, severity=Priority.LOW, message="test"
        )
        confidence = await architect_agent.can_handle(format_issue)
        assert confidence == 0.4

    @pytest.mark.asyncio
    async def test_planning_for_complex_issues(self, architect_agent, complexity_issue):
        plan = await architect_agent.plan_before_action(complexity_issue)

        assert isinstance(plan, dict)
        assert "strategy" in plan
        assert "patterns" in plan
        assert "approach" in plan

        assert plan["strategy"] == "external_specialist_guided"
        assert "break_into_helper_methods" in plan["approach"]
        assert len(plan["patterns"]) > 0

    @pytest.mark.asyncio
    async def test_planning_for_simple_issues(self, architect_agent):
        simple_issue = Issue(
            id="simple",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="format issue",
        )

        plan = await architect_agent.plan_before_action(simple_issue)

        assert plan["strategy"] == "internal_pattern_based"
        assert plan["approach"] == "apply_standard_formatting"

    @pytest.mark.asyncio
    async def test_fix_execution_with_plan(self, architect_agent, complexity_issue):
        result = await architect_agent.analyze_and_fix(complexity_issue)

        assert isinstance(result, FixResult)
        assert result.success
        assert result.confidence >= 0.7
        assert len(result.fixes_applied) > 0
        assert "crackerjack - architect" in " ".join(result.fixes_applied)

    def test_supported_types(self, architect_agent):
        supported = architect_agent.get_supported_types()

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


class TestProactiveAgentCoordination:
    @pytest.fixture
    def agent_context(self):
        return AgentContext(project_path=Path.cwd())

    @pytest.fixture
    def coordinator(self, agent_context):
        coordinator = AgentCoordinator(agent_context)
        coordinator.initialize_agents()
        return coordinator

    @pytest.fixture
    def test_issues(self):
        return [
            Issue(
                id="complex1",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Complex function",
                file_path="test1.py",
            ),
            Issue(
                id="dry1",
                type=IssueType.DRY_VIOLATION,
                severity=Priority.MEDIUM,
                message="Repeated code",
                file_path="test2.py",
            ),
            Issue(
                id="format1",
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="Format issue",
                file_path="test3.py",
            ),
        ]

    def test_proactive_mode_enabled_by_default(self, coordinator):
        assert coordinator.proactive_mode is True

    def test_set_proactive_mode(self, coordinator):
        coordinator.set_proactive_mode(False)
        assert coordinator.proactive_mode is False

        coordinator.set_proactive_mode(True)
        assert coordinator.proactive_mode is True

    @pytest.mark.asyncio
    async def test_proactive_planning_flow(self, coordinator, test_issues):
        mock_architect = MagicMock()
        mock_architect.plan_before_action = AsyncMock(
            return_value={
                "strategy": "test_strategy",
                "patterns": ["test_pattern"],
                "validation": ["test_validation"],
            }
        )

        with patch.object(
            coordinator, "_get_architect_agent", return_value=mock_architect
        ):
            result = await coordinator.handle_issues_proactively(test_issues)

        assert isinstance(result, FixResult)
        mock_architect.plan_before_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_reactive_mode(self, coordinator, test_issues):
        coordinator.set_proactive_mode(False)

        with patch.object(coordinator, "handle_issues") as mock_handle:
            mock_handle.return_value = FixResult(success=True, confidence=0.8)

            await coordinator.handle_issues_proactively(test_issues)

            mock_handle.assert_called_once_with(test_issues)

    @pytest.mark.asyncio
    async def test_architect_agent_availability(self, coordinator):
        architect = coordinator._get_architect_agent()

        assert architect is not None
        assert architect.__class__.__name__ == "ArchitectAgent"


class TestPatternCache:
    @pytest.fixture
    def temp_project_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def pattern_cache(self, temp_project_path):
        return PatternCache(temp_project_path)

    @pytest.fixture
    def test_issue(self):
        return Issue(
            id="cache_test",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test caching",
            file_path="cache_test.py",
        )

    @pytest.fixture
    def test_plan(self):
        return {
            "strategy": "cache_test_strategy",
            "patterns": ["cache_pattern1", "cache_pattern2"],
            "validation": ["cache_validation"],
        }

    @pytest.fixture
    def test_result(self):
        return FixResult(
            success=True,
            confidence=0.85,
            fixes_applied=["Applied cache pattern"],
            files_modified=["cache_test.py"],
        )

    def test_cache_initialization(self, pattern_cache, temp_project_path):
        assert pattern_cache.project_path == temp_project_path
        assert pattern_cache.cache_dir.exists()
        assert not pattern_cache._loaded

    def test_cache_successful_pattern(
        self, pattern_cache, test_issue, test_plan, test_result
    ):
        pattern_id = pattern_cache.cache_successful_pattern(
            test_issue, test_plan, test_result
        )

        assert pattern_id.startswith(f"{test_issue.type.value}_")
        assert pattern_cache.cache_file.exists()

        assert pattern_id in pattern_cache._patterns
        cached_pattern = pattern_cache._patterns[pattern_id]
        assert cached_pattern.issue_type == test_issue.type
        assert cached_pattern.strategy == test_plan["strategy"]
        assert cached_pattern.confidence == test_result.confidence

    def test_get_patterns_for_issue(
        self, pattern_cache, test_issue, test_plan, test_result
    ):
        pattern_cache.cache_successful_pattern(test_issue, test_plan, test_result)

        patterns = pattern_cache.get_patterns_for_issue(test_issue)

        assert len(patterns) == 1
        assert patterns[0].issue_type == test_issue.type
        assert patterns[0].strategy == test_plan["strategy"]

    def test_get_best_pattern(self, pattern_cache, test_issue, test_plan, test_result):
        pattern_cache.cache_successful_pattern(test_issue, test_plan, test_result)

        best_pattern = pattern_cache.get_best_pattern_for_issue(test_issue)

        assert best_pattern is not None
        assert best_pattern.issue_type == test_issue.type
        assert best_pattern.confidence == test_result.confidence

    def test_pattern_usage_tracking(
        self, pattern_cache, test_issue, test_plan, test_result
    ):
        pattern_id = pattern_cache.cache_successful_pattern(
            test_issue, test_plan, test_result
        )

        success = pattern_cache.use_pattern(pattern_id)
        assert success

        pattern = pattern_cache._patterns[pattern_id]
        assert pattern.usage_count == 1
        assert pattern.last_used > 0

    def test_success_rate_updates(
        self, pattern_cache, test_issue, test_plan, test_result
    ):
        pattern_id = pattern_cache.cache_successful_pattern(
            test_issue, test_plan, test_result
        )

        pattern_cache.use_pattern(pattern_id)
        pattern_cache.update_pattern_success_rate(pattern_id, True)

        pattern_cache.use_pattern(pattern_id)
        pattern_cache.update_pattern_success_rate(pattern_id, False)

        pattern = pattern_cache._patterns[pattern_id]
        assert pattern.success_rate == 0.5

    def test_pattern_statistics(
        self, pattern_cache, test_issue, test_plan, test_result
    ):
        pattern_cache.cache_successful_pattern(test_issue, test_plan, test_result)

        stats = pattern_cache.get_pattern_statistics()

        assert stats["total_patterns"] == 1
        assert stats["patterns_by_type"][test_issue.type.value] == 1
        assert stats["average_success_rate"] == 1.0
        assert len(stats["most_used_patterns"]) <= 5

    def test_cache_persistence(self, pattern_cache, test_issue, test_plan, test_result):
        pattern_id = pattern_cache.cache_successful_pattern(
            test_issue, test_plan, test_result
        )

        new_cache = PatternCache(pattern_cache.project_path)
        patterns = new_cache.get_patterns_for_issue(test_issue)

        assert len(patterns) == 1
        assert patterns[0].pattern_id == pattern_id

    def test_cleanup_old_patterns(self, pattern_cache):
        old_time = time.time() - (31 * 24 * 60 * 60)

        old_pattern = CachedPattern(
            pattern_id="old_pattern",
            issue_type=IssueType.COMPLEXITY,
            strategy="old_strategy",
            patterns=["old"],
            confidence=0.5,
            success_rate=0.1,
            usage_count=6,
            last_used=old_time,
            created_at=old_time,
            files_modified=[],
            fixes_applied=[],
            metadata={},
        )

        pattern_cache._patterns["old_pattern"] = old_pattern

        removed = pattern_cache.cleanup_old_patterns()
        assert removed == 1
        assert "old_pattern" not in pattern_cache._patterns


class TestPatternDetector:
    @pytest.fixture
    def temp_project_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)

            (project_path / "complex.py").write_text("""
def complex_function():
    if True:
        for i in range(10):
            if i % 2:
                try:
                    while True:
                        if i > 5:
                            break
                except:
                    pass
    return True

print("This line is duplicated")
print("Another line")
print("This line is duplicated")
print("This line is duplicated")

import subprocess
subprocess.run("ls", shell = True)
temp_file = "/ tmp / unsafe.txt"

def complex_function(a, b, c, d):
    if a:
        for i in range(b):
            if i % 2:
                try:
                    while c:
                        if d > i:
                            for j in range(d):
                                if j == i:
                                    return True
                except Exception:
                    pass
    return False


print("This line appears multiple times")
print("Another line")
print("This line appears multiple times")
print("This line appears multiple times")
""")
            yield project_path

    @pytest.mark.asyncio
    async def test_end_to_end_proactive_workflow(self, temp_project_path):
        agent_context = AgentContext(project_path=temp_project_path)
        coordinator = AgentCoordinator(agent_context)
        coordinator.initialize_agents()

        architect = coordinator._get_architect_agent()
        assert architect is not None

        issues = [
            Issue(
                id="e2e_complexity",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Complex function needs refactoring",
                file_path=str(temp_project_path / "test_file.py"),
                line_number=2,
            ),
            Issue(
                id="e2e_dry",
                type=IssueType.DRY_VIOLATION,
                severity=Priority.MEDIUM,
                message="Duplicate print statements",
                file_path=str(temp_project_path / "test_file.py"),
                line_number=15,
            ),
        ]

        result = await coordinator.handle_issues_proactively(issues)

        assert isinstance(result, FixResult)
        assert result.confidence > 0.0

        recommendations_text = " ".join(result.recommendations)
        assert any(
            keyword in recommendations_text.lower()
            for keyword in ["architect", "strategy", "pattern", "plan"]
        )


if __name__ == "__main__":
    pytest.main([__file__ + "::test_end_to_end_proactive_workflow", "-v", "-s"])
