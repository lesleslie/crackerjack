"""Unit tests for agent base classes.

Tests core agent infrastructure including AgentContext, Issue,
FixResult, Priority, IssueType, and SubAgent base class.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import (
    AgentContext,
    AgentRegistry,
    FixResult,
    Issue,
    IssueType,
    Priority,
    SubAgent,
)


@pytest.mark.unit
class TestPriorityEnum:
    """Test Priority enumeration."""

    def test_priority_values(self):
        """Test all priority levels are defined."""
        assert Priority.LOW.value == "low"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.HIGH.value == "high"
        assert Priority.CRITICAL.value == "critical"

    def test_priority_ordering(self):
        """Test priority enum members exist in expected order."""
        priorities = list(Priority)
        assert len(priorities) == 4
        assert Priority.LOW in priorities
        assert Priority.CRITICAL in priorities


@pytest.mark.unit
class TestIssueTypeEnum:
    """Test IssueType enumeration."""

    def test_issue_type_values(self):
        """Test all issue types are defined."""
        assert IssueType.FORMATTING.value == "formatting"
        assert IssueType.TYPE_ERROR.value == "type_error"
        assert IssueType.SECURITY.value == "security"
        assert IssueType.TEST_FAILURE.value == "test_failure"
        assert IssueType.COMPLEXITY.value == "complexity"
        assert IssueType.DEAD_CODE.value == "dead_code"
        assert IssueType.DRY_VIOLATION.value == "dry_violation"
        assert IssueType.PERFORMANCE.value == "performance"

    def test_issue_type_count(self):
        """Test expected number of issue types."""
        issue_types = list(IssueType)
        # Should have at least 12 issue types
        assert len(issue_types) >= 12


@pytest.mark.unit
class TestIssueDataclass:
    """Test Issue dataclass."""

    def test_issue_creation_minimal(self):
        """Test creating issue with minimal required fields."""
        issue = Issue(
            id="test-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Test issue",
        )

        assert issue.id == "test-001"
        assert issue.type == IssueType.FORMATTING
        assert issue.severity == Priority.LOW
        assert issue.message == "Test issue"
        assert issue.file_path is None
        assert issue.line_number is None
        assert issue.details == []
        assert issue.stage == "unknown"

    def test_issue_creation_full(self):
        """Test creating issue with all fields."""
        issue = Issue(
            id="test-002",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Security vulnerability",
            file_path="/path/to/file.py",
            line_number=42,
            details=["Detail 1", "Detail 2"],
            stage="analysis",
        )

        assert issue.id == "test-002"
        assert issue.type == IssueType.SECURITY
        assert issue.severity == Priority.CRITICAL
        assert issue.file_path == "/path/to/file.py"
        assert issue.line_number == 42
        assert len(issue.details) == 2
        assert issue.stage == "analysis"

    def test_issue_defaults(self):
        """Test issue default values."""
        issue = Issue(
            id="test-003",
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="Complex function",
        )

        assert issue.details == []
        assert issue.stage == "unknown"


@pytest.mark.unit
class TestFixResultDataclass:
    """Test FixResult dataclass."""

    def test_fix_result_creation_minimal(self):
        """Test creating fix result with minimal fields."""
        result = FixResult(success=True, confidence=0.9)

        assert result.success is True
        assert result.confidence == 0.9
        assert result.fixes_applied == []
        assert result.remaining_issues == []
        assert result.recommendations == []
        assert result.files_modified == []

    def test_fix_result_creation_full(self):
        """Test creating fix result with all fields."""
        result = FixResult(
            success=True,
            confidence=0.85,
            fixes_applied=["Fix 1", "Fix 2"],
            remaining_issues=["Issue 1"],
            recommendations=["Rec 1", "Rec 2"],
            files_modified=["file1.py", "file2.py"],
        )

        assert result.success is True
        assert result.confidence == 0.85
        assert len(result.fixes_applied) == 2
        assert len(result.remaining_issues) == 1
        assert len(result.recommendations) == 2
        assert len(result.files_modified) == 2

    def test_fix_result_merge_with(self):
        """Test merging two fix results."""
        result1 = FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["Fix A"],
            remaining_issues=["Issue 1"],
            recommendations=["Rec A"],
            files_modified=["file1.py"],
        )

        result2 = FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["Fix B"],
            remaining_issues=["Issue 2"],
            recommendations=["Rec B"],
            files_modified=["file2.py"],
        )

        merged = result1.merge_with(result2)

        assert merged.success is True
        assert merged.confidence == 0.9  # max of both
        assert "Fix A" in merged.fixes_applied
        assert "Fix B" in merged.fixes_applied
        assert "Issue 1" in merged.remaining_issues
        assert "Issue 2" in merged.remaining_issues
        assert "Rec A" in merged.recommendations
        assert "Rec B" in merged.recommendations
        assert "file1.py" in merged.files_modified
        assert "file2.py" in merged.files_modified

    def test_fix_result_merge_deduplicates_issues(self):
        """Test merging deduplicates remaining issues."""
        result1 = FixResult(
            success=True,
            confidence=0.8,
            remaining_issues=["Issue 1", "Issue 2"],
        )

        result2 = FixResult(
            success=True,
            confidence=0.9,
            remaining_issues=["Issue 2", "Issue 3"],
        )

        merged = result1.merge_with(result2)

        # Should deduplicate Issue 2
        assert len(merged.remaining_issues) == 3
        assert set(merged.remaining_issues) == {"Issue 1", "Issue 2", "Issue 3"}

    def test_fix_result_merge_deduplicates_files(self):
        """Test merging deduplicates modified files."""
        result1 = FixResult(
            success=True,
            confidence=0.8,
            files_modified=["file1.py", "file2.py"],
        )

        result2 = FixResult(
            success=True,
            confidence=0.9,
            files_modified=["file2.py", "file3.py"],
        )

        merged = result1.merge_with(result2)

        # Should deduplicate file2.py
        assert len(merged.files_modified) == 3
        assert set(merged.files_modified) == {"file1.py", "file2.py", "file3.py"}

    def test_fix_result_merge_failure_propagates(self):
        """Test merge with failure propagates failure."""
        result1 = FixResult(success=True, confidence=0.9)
        result2 = FixResult(success=False, confidence=0.5)

        merged = result1.merge_with(result2)

        assert merged.success is False


@pytest.mark.unit
class TestAgentContext:
    """Test AgentContext dataclass."""

    def test_agent_context_creation_minimal(self, tmp_path):
        """Test creating agent context with minimal fields."""
        context = AgentContext(project_path=tmp_path)

        assert context.project_path == tmp_path
        assert context.temp_dir is None
        assert context.config == {}
        assert context.session_id is None
        assert context.subprocess_timeout == 300
        assert context.max_file_size == 10_000_000

    def test_agent_context_creation_full(self, tmp_path):
        """Test creating agent context with all fields."""
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        context = AgentContext(
            project_path=tmp_path,
            temp_dir=temp_dir,
            config={"debug": True},
            session_id="session-123",
            subprocess_timeout=600,
            max_file_size=5_000_000,
        )

        assert context.project_path == tmp_path
        assert context.temp_dir == temp_dir
        assert context.config["debug"] is True
        assert context.session_id == "session-123"
        assert context.subprocess_timeout == 600
        assert context.max_file_size == 5_000_000

    def test_get_file_content_success(self, tmp_path):
        """Test getting file content."""
        context = AgentContext(project_path=tmp_path)
        test_file = tmp_path / "test.py"
        content = "print('hello')"
        test_file.write_text(content)

        result = context.get_file_content(test_file)

        assert result == content

    def test_get_file_content_string_path(self, tmp_path):
        """Test getting file content with string path."""
        context = AgentContext(project_path=tmp_path)
        test_file = tmp_path / "test.py"
        content = "print('hello')"
        test_file.write_text(content)

        result = context.get_file_content(str(test_file))

        assert result == content

    def test_get_file_content_nonexistent(self, tmp_path):
        """Test getting content of non-existent file."""
        context = AgentContext(project_path=tmp_path)
        nonexistent = tmp_path / "nonexistent.py"

        result = context.get_file_content(nonexistent)

        assert result is None

    def test_get_file_content_directory(self, tmp_path):
        """Test getting content of directory returns None."""
        context = AgentContext(project_path=tmp_path)
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        result = context.get_file_content(test_dir)

        assert result is None

    def test_get_file_content_too_large(self, tmp_path):
        """Test getting content of file exceeding max size."""
        context = AgentContext(project_path=tmp_path, max_file_size=100)
        test_file = tmp_path / "large.py"
        # Write file larger than max_file_size
        test_file.write_text("x" * 200)

        result = context.get_file_content(test_file)

        assert result is None

    def test_write_file_content_success(self, tmp_path):
        """Test writing file content."""
        context = AgentContext(project_path=tmp_path)
        test_file = tmp_path / "output.py"
        content = "print('world')"

        result = context.write_file_content(test_file, content)

        assert result is True
        assert test_file.read_text() == content

    def test_write_file_content_string_path(self, tmp_path):
        """Test writing file with string path."""
        context = AgentContext(project_path=tmp_path)
        test_file = tmp_path / "output.py"
        content = "print('world')"

        result = context.write_file_content(str(test_file), content)

        assert result is True
        assert test_file.read_text() == content

    def test_write_file_content_failure(self, tmp_path):
        """Test writing file content handles errors."""
        context = AgentContext(project_path=tmp_path)
        # Try to write to directory instead of file
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        result = context.write_file_content(test_dir, "content")

        assert result is False


@pytest.mark.unit
class TestSubAgentBase:
    """Test SubAgent base class."""

    class TestAgent(SubAgent):
        """Concrete test agent for testing."""

        async def can_handle(self, issue: Issue) -> float:
            return 0.9

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return FixResult(success=True, confidence=0.9)

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.FORMATTING, IssueType.COMPLEXITY}

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    @pytest.fixture
    def agent(self, context):
        """Create test agent instance."""
        return self.TestAgent(context)

    def test_agent_initialization(self, agent, context):
        """Test agent initializes correctly."""
        assert agent.context == context
        assert agent.name == "TestAgent"

    def test_agent_get_supported_types(self, agent):
        """Test agent returns supported issue types."""
        supported = agent.get_supported_types()

        assert IssueType.FORMATTING in supported
        assert IssueType.COMPLEXITY in supported
        assert len(supported) == 2

    @pytest.mark.asyncio
    async def test_agent_can_handle(self, agent):
        """Test agent can_handle returns confidence score."""
        issue = Issue(
            id="test-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Test",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    @pytest.mark.asyncio
    async def test_agent_analyze_and_fix(self, agent):
        """Test agent analyze_and_fix returns fix result."""
        issue = Issue(
            id="test-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Test",
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is True
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_run_command_success(self, agent):
        """Test running command successfully."""
        returncode, stdout, stderr = await agent.run_command(["echo", "hello"])

        assert returncode == 0
        assert "hello" in stdout
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_run_command_with_cwd(self, agent, tmp_path):
        """Test running command with custom working directory."""
        test_dir = tmp_path / "subdir"
        test_dir.mkdir()

        returncode, stdout, stderr = await agent.run_command(["pwd"], cwd=test_dir)

        assert returncode == 0
        assert str(test_dir) in stdout

    @pytest.mark.asyncio
    async def test_run_command_timeout(self, agent):
        """Test command timeout handling."""
        # Use a command that would take longer than timeout
        returncode, stdout, stderr = await agent.run_command(
            ["sleep", "10"],
            timeout=0.1,
        )

        assert returncode == -1
        assert "timed out" in stderr.lower()

    def test_log_method(self, agent):
        """Test log method doesn't raise errors."""
        # Should not raise
        agent.log("Test message", level="INFO")
        agent.log("Warning message", level="WARN")

    @pytest.mark.asyncio
    async def test_plan_before_action(self, agent):
        """Test plan_before_action returns default strategy."""
        issue = Issue(
            id="test-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Test",
        )

        plan = await agent.plan_before_action(issue)

        assert "strategy" in plan
        assert plan["strategy"] == "default"
        assert "confidence" in plan
        assert plan["confidence"] == 0.5

    def test_get_cached_patterns(self, agent):
        """Test get_cached_patterns returns empty dict by default."""
        patterns = agent.get_cached_patterns()

        assert patterns == {}
        assert isinstance(patterns, dict)


@pytest.mark.unit
class TestAgentRegistry:
    """Test AgentRegistry class."""

    class MockAgent1(SubAgent):
        """First mock agent."""

        async def can_handle(self, issue: Issue) -> float:
            return 0.8

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return FixResult(success=True, confidence=0.8)

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.FORMATTING}

    class MockAgent2(SubAgent):
        """Second mock agent."""

        async def can_handle(self, issue: Issue) -> float:
            return 0.9

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return FixResult(success=True, confidence=0.9)

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.SECURITY}

    def test_registry_initialization(self):
        """Test registry initializes empty."""
        registry = AgentRegistry()

        assert registry._agents == {}

    def test_registry_register_agent(self):
        """Test registering an agent."""
        registry = AgentRegistry()

        registry.register(self.MockAgent1)

        assert "MockAgent1" in registry._agents
        assert registry._agents["MockAgent1"] == self.MockAgent1

    def test_registry_register_multiple_agents(self):
        """Test registering multiple agents."""
        registry = AgentRegistry()

        registry.register(self.MockAgent1)
        registry.register(self.MockAgent2)

        assert len(registry._agents) == 2
        assert "MockAgent1" in registry._agents
        assert "MockAgent2" in registry._agents

    def test_registry_create_all(self, tmp_path):
        """Test creating all registered agents."""
        registry = AgentRegistry()
        registry.register(self.MockAgent1)
        registry.register(self.MockAgent2)

        context = AgentContext(project_path=tmp_path)
        agents = registry.create_all(context)

        assert len(agents) == 2
        assert all(isinstance(agent, SubAgent) for agent in agents)
        assert any(agent.name == "MockAgent1" for agent in agents)
        assert any(agent.name == "MockAgent2" for agent in agents)

    def test_registry_create_all_with_empty_registry(self, tmp_path):
        """Test creating agents from empty registry."""
        registry = AgentRegistry()
        context = AgentContext(project_path=tmp_path)

        agents = registry.create_all(context)

        assert agents == []


@pytest.mark.unit
class TestGlobalAgentRegistry:
    """Test global agent_registry instance."""

    def test_global_registry_exists(self):
        """Test global agent_registry instance exists."""
        from crackerjack.agents.base import agent_registry

        assert isinstance(agent_registry, AgentRegistry)

    def test_global_registry_is_singleton(self):
        """Test global agent_registry is singleton."""
        from crackerjack.agents.base import agent_registry as registry1
        from crackerjack.agents.base import agent_registry as registry2

        assert registry1 is registry2
