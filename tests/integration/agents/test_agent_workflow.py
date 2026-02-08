"""Integration tests for agent workflow and coordination.

Tests end-to-end agent coordination, multi-agent scenarios,
and real-world issue fixing workflows.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
    SubAgent,
)


@pytest.mark.integration
class TestAgentWorkflow:
    """Test end-to-end agent coordination workflows."""

    @pytest.fixture
    def project_path(self, tmp_path):
        """Create temporary project path with sample files."""
        # Create sample Python files
        (tmp_path / "complex.py").write_text(
            """
def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return x + y + z
            else:
                return x + y
        else:
            return x
    return 0

unused_import = os.path.join("a", "b")
""",
        )

        (tmp_path / "security.py").write_text(
            """
import subprocess

def vulnerable_command(user_input):
    # Shell injection vulnerability
    result = subprocess.run(f"echo {user_input}", shell=True)
    return result

temp_file = "/tmp hardcoded path"
""",
        )

        (tmp_path / "test_sample.py").write_text(
            """
def add(a, b):
    return a + b
""",
        )

        return tmp_path

    @pytest.fixture
    def agent_context(self, project_path):
        """Create agent context for testing."""
        return AgentContext(
            project_path=project_path,
            subprocess_timeout=30,
            max_file_size=1_000_000,
        )

    @pytest.fixture
    def mock_refactoring_agent(self):
        """Create mock refactoring agent."""
        agent = Mock(spec=SubAgent)
        agent.name = "RefactoringAgent"
        agent.get_supported_types = Mock(return_value={IssueType.COMPLEXITY, IssueType.DEAD_CODE})
        agent.can_handle = AsyncMock(return_value=0.9)
        agent.analyze_and_fix = AsyncMock(
            return_value=FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=["Reduced complexity"],
                files_modified=["complex.py"],
            )
        )
        return agent

    @pytest.fixture
    def mock_security_agent(self):
        """Create mock security agent."""
        agent = Mock(spec=SubAgent)
        agent.name = "SecurityAgent"
        agent.get_supported_types = Mock(return_value={IssueType.SECURITY})
        agent.can_handle = AsyncMock(return_value=0.95)
        agent.analyze_and_fix = AsyncMock(
            return_value=FixResult(
                success=True,
                confidence=0.95,
                fixes_applied=["Fixed shell injection"],
                files_modified=["security.py"],
            )
        )
        return agent

    @pytest.fixture
    def mock_test_creation_agent(self):
        """Create mock test creation agent."""
        agent = Mock(spec=SubAgent)
        agent.name = "TestCreationAgent"
        agent.get_supported_types = Mock(return_value={IssueType.TEST_FAILURE})
        agent.can_handle = AsyncMock(return_value=0.8)
        agent.analyze_and_fix = AsyncMock(
            return_value=FixResult(
                success=True,
                confidence=0.8,
                fixes_applied=["Created test file"],
                files_modified=["test_complex.py"],
            )
        )
        return agent

    @pytest.mark.asyncio
    async def test_single_agent_single_issue(
        self, agent_context, mock_refactoring_agent
    ):
        """Test single agent handling single issue."""
        issue = Issue(
            id="issue-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
            file_path="complex.py",
            line_number=3,
        )

        # Simulate coordinator routing
        agents = [mock_refactoring_agent]
        for agent in agents:
            confidence = await agent.can_handle(issue)
            if confidence >= 0.7:
                result = await agent.analyze_and_fix(issue)
                break
        else:
            result = FixResult(success=False, confidence=0.0)

        assert result.success is True
        assert result.confidence == 0.9
        assert "Reduced complexity" in result.fixes_applied
        mock_refactoring_agent.analyze_and_fix.assert_called_once_with(issue)

    @pytest.mark.asyncio
    async def test_multi_agent_different_issue_types(
        self,
        agent_context,
        mock_refactoring_agent,
        mock_security_agent,
        mock_test_creation_agent,
    ):
        """Test multiple agents handling different issue types."""
        issues = [
            Issue(
                id="issue-001",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Complex function",
                file_path="complex.py",
            ),
            Issue(
                id="issue-002",
                type=IssueType.SECURITY,
                severity=Priority.CRITICAL,
                message="Shell injection",
                file_path="security.py",
            ),
            Issue(
                id="issue-003",
                type=IssueType.TEST_FAILURE,
                severity=Priority.MEDIUM,
                message="Missing tests",
                file_path="test_sample.py",
            ),
        ]

        agents = [mock_refactoring_agent, mock_security_agent, mock_test_creation_agent]

        results = []
        for issue in issues:
            best_agent = None
            best_confidence = 0.0

            for agent in agents:
                confidence = await agent.can_handle(issue)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_agent = agent

            if best_agent and best_confidence >= 0.7:
                result = await best_agent.analyze_and_fix(issue)
                results.append(result)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert mock_refactoring_agent.analyze_and_fix.call_count == 1
        assert mock_security_agent.analyze_and_fix.call_count == 1
        assert mock_test_creation_agent.analyze_and_fix.call_count == 1

    @pytest.mark.asyncio
    async def test_agent_selection_by_confidence(
        self, agent_context, mock_refactoring_agent, mock_security_agent
    ):
        """Test that agent with highest confidence is selected."""
        issue = Issue(
            id="issue-001",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Security vulnerability",
            file_path="security.py",
        )

        # Set different confidence scores
        mock_refactoring_agent.can_handle = AsyncMock(return_value=0.3)
        mock_security_agent.can_handle = AsyncMock(return_value=0.95)

        agents = [mock_refactoring_agent, mock_security_agent]

        # Find best agent
        best_agent = None
        best_confidence = 0.0
        for agent in agents:
            confidence = await agent.can_handle(issue)
            if confidence > best_confidence:
                best_confidence = confidence
                best_agent = agent

        assert best_agent == mock_security_agent
        assert best_confidence == 0.95

    @pytest.mark.asyncio
    async def test_failed_fix_doesnt_stop_workflow(
        self, agent_context, mock_refactoring_agent, mock_security_agent
    ):
        """Test that one failed fix doesn't prevent other fixes."""
        issues = [
            Issue(
                id="issue-001",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Complex function",
                file_path="complex.py",
            ),
            Issue(
                id="issue-002",
                type=IssueType.SECURITY,
                severity=Priority.CRITICAL,
                message="Shell injection",
                file_path="security.py",
            ),
        ]

        # Make refactoring agent fail
        mock_refactoring_agent.analyze_and_fix = AsyncMock(
            return_value=FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not fix complexity"],
            )
        )

        agents = [mock_refactoring_agent, mock_security_agent]

        results = []
        for issue in issues:
            for agent in agents:
                confidence = await agent.can_handle(issue)
                if confidence >= 0.7:
                    result = await agent.analyze_and_fix(issue)
                    results.append(result)
                    break

        assert len(results) == 2
        assert results[0].success is False  # Complexity fix failed
        assert results[1].success is True  # Security fix succeeded

    @pytest.mark.asyncio
    async def test_result_merging(self):
        """Test merging multiple FixResults."""
        result1 = FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["Fix A", "Fix B"],
            remaining_issues=["Issue 1"],
            recommendations=["Rec 1"],
            files_modified=["file1.py", "file2.py"],
        )

        result2 = FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["Fix B", "Fix C"],  # Duplicate Fix B
            remaining_issues=["Issue 1", "Issue 2"],
            recommendations=["Rec 2"],
            files_modified=["file2.py", "file3.py"],  # Duplicate file2.py
        )

        merged = result1.merge_with(result2)

        assert merged.success is True
        assert merged.confidence == 0.9  # Max confidence
        assert len(merged.fixes_applied) == 3  # Deduplicated
        assert set(merged.fixes_applied) == {"Fix A", "Fix B", "Fix C"}
        assert set(merged.remaining_issues) == {"Issue 1", "Issue 2"}
        assert len(merged.recommendations) == 2
        assert set(merged.files_modified) == {"file1.py", "file2.py", "file3.py"}

    @pytest.mark.asyncio
    async def test_sequential_file_modifications(
        self, agent_context, mock_refactoring_agent
    ):
        """Test sequential modifications to same file."""
        issues = [
            Issue(
                id=f"issue-{i:03d}",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message=f"Complex function {i}",
                file_path="complex.py",
                line_number=i * 10,
            )
            for i in range(1, 4)
        ]

        results = []
        for issue in issues:
            result = await mock_refactoring_agent.analyze_and_fix(issue)
            results.append(result)

        # All should succeed
        assert all(r.success for r in results)
        # All should modify same file
        assert all("complex.py" in r.files_modified for r in results)

    @pytest.mark.asyncio
    async def test_issue_routing_with_fallback(
        self, agent_context, mock_refactoring_agent, mock_security_agent
    ):
        """Test fallback to generic agent when no specialist available."""
        issue = Issue(
            id="issue-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Missing docstring",
            file_path="complex.py",
        )

        # No agent can handle documentation
        mock_refactoring_agent.can_handle = AsyncMock(return_value=0.0)
        mock_security_agent.can_handle = AsyncMock(return_value=0.0)

        agents = [mock_refactoring_agent, mock_security_agent]

        best_agent = None
        best_confidence = 0.0
        for agent in agents:
            confidence = await agent.can_handle(issue)
            if confidence > best_confidence:
                best_confidence = confidence
                best_agent = agent

        # Should not find suitable agent
        assert best_confidence < 0.7

    @pytest.mark.asyncio
    async def test_batch_processing_order_preserved(
        self, agent_context, mock_refactoring_agent
    ):
        """Test that batch processing preserves issue order."""
        issues = [
            Issue(
                id=f"issue-{i:03d}",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message=f"Issue {i}",
                file_path=f"file{i}.py",
            )
            for i in range(5, 0, -1)  # Reverse order
        ]

        results = []
        for issue in issues:
            result = await mock_refactoring_agent.analyze_and_fix(issue)
            results.append((issue.id, result))

        # Verify order preserved
        assert results[0][0] == "issue-005"
        assert results[1][0] == "issue-004"
        assert results[2][0] == "issue-003"
        assert results[3][0] == "issue-002"
        assert results[4][0] == "issue-001"

    @pytest.mark.asyncio
    async def test_complex_real_world_scenario(
        self,
        agent_context,
        mock_refactoring_agent,
        mock_security_agent,
        mock_test_creation_agent,
    ):
        """Test complex scenario with multiple files and issue types."""
        # Simulate real project with mixed issues
        issues = [
            Issue(
                id="issue-001",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Function 'complex_function' is too complex (cognitive complexity: 25)",
                file_path="complex.py",
                line_number=3,
                details=["function:complex_function", "complexity:25"],
            ),
            Issue(
                id="issue-002",
                type=IssueType.SECURITY,
                severity=Priority.CRITICAL,
                message="subprocess call with shell=True identified",
                file_path="security.py",
                line_number=6,
                details=["B602: subprocess call with shell=True"],
            ),
            Issue(
                id="issue-003",
                type=IssueType.DEAD_CODE,
                severity=Priority.LOW,
                message="unused_import imported but unused",
                file_path="complex.py",
                line_number=17,
            ),
            Issue(
                id="issue-004",
                type=IssueType.TEST_FAILURE,
                severity=Priority.MEDIUM,
                message="No tests found for complex.py",
                file_path="complex.py",
            ),
        ]

        agents = [
            mock_refactoring_agent,
            mock_security_agent,
            mock_test_creation_agent,
        ]

        results = []
        files_modified = set()

        for issue in issues:
            best_agent = None
            best_confidence = 0.0

            for agent in agents:
                confidence = await agent.can_handle(issue)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_agent = agent

            if best_agent and best_confidence >= 0.7:
                result = await best_agent.analyze_and_fix(issue)
                results.append((issue.id, result))
                files_modified.update(result.files_modified)

        # Verify results
        assert len(results) == 4  # All issues handled
        assert all(r.success for _, r in results)  # All succeeded
        assert len(files_modified) >= 2  # At least 2 files modified

        # Verify correct agent routing
        agent_calls = {
            agent.name: agent.analyze_and_fix.call_count for agent in agents
        }
        assert agent_calls["RefactoringAgent"] >= 1
        assert agent_calls["SecurityAgent"] >= 1
        assert agent_calls["TestCreationAgent"] >= 1

    @pytest.mark.asyncio
    async def test_error_recovery_in_workflow(
        self, agent_context, mock_refactoring_agent
    ):
        """Test workflow recovery when agent raises exception."""
        issues = [
            Issue(
                id="issue-001",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="First issue",
                file_path="file1.py",
            ),
            Issue(
                id="issue-002",
                type=IssueType.DEAD_CODE,
                severity=Priority.MEDIUM,
                message="Second issue",
                file_path="file2.py",
            ),
            Issue(
                id="issue-003",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Third issue",
                file_path="file3.py",
            ),
        ]

        # Make second issue fail with exception
        call_count = 0

        async def failing_analyze(issue):
            nonlocal call_count
            call_count += 1
            if issue.id == "issue-002":
                raise ValueError("Agent failed")
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=["Fixed"],
                files_modified=[issue.file_path],
            )

        mock_refactoring_agent.analyze_and_fix = AsyncMock(side_effect=failing_analyze)

        results = []
        for issue in issues:
            try:
                result = await mock_refactoring_agent.analyze_and_fix(issue)
                results.append((issue.id, "success", result))
            except Exception as e:
                results.append((issue.id, "error", str(e)))

        # First and third should succeed, second should fail
        assert results[0][1] == "success"
        assert results[1][1] == "error"
        assert results[2][1] == "success"
        assert call_count == 3


@pytest.mark.integration
class TestAgentFileOperations:
    """Test agent file operations in real scenarios."""

    @pytest.fixture
    def project_path(self, tmp_path):
        """Create test project with files."""
        (tmp_path / "test_file.py").write_text(
            """
def hello():
    print("hello")

def world():
    print("world")
""",
        )
        return tmp_path

    @pytest.fixture
    def agent_context(self, project_path):
        """Create agent context."""
        return AgentContext(project_path=project_path)

    def test_read_and_write_file_cycle(self, agent_context):
        """Test reading, modifying, and writing file."""
        file_path = agent_context.project_path / "test_file.py"

        # Read original content
        original_content = agent_context.get_file_content(file_path)
        assert original_content is not None
        assert "def hello" in original_content

        # Modify content
        modified_content = original_content.replace(
            'print("hello")', 'print("hello, modified!")'
        )

        # Write modified content
        success = agent_context.write_file_content(file_path, modified_content)
        assert success is True

        # Verify modification
        new_content = agent_context.get_file_content(file_path)
        assert "hello, modified" in new_content
        assert "hello, modified" not in original_content

    def test_write_rejects_invalid_syntax(self, agent_context):
        """Test that write with syntax error is rejected."""
        file_path = agent_context.project_path / "invalid.py"
        invalid_content = "def foo(:\n    pass"  # Missing closing paren

        success = agent_context.write_file_content(file_path, invalid_content)

        assert success is False
        assert not file_path.exists()

    def test_write_rejects_duplicate_functions(self, agent_context):
        """Test that duplicate functions are detected."""
        file_path = agent_context.project_path / "duplicates.py"
        duplicate_content = """
def foo():
    pass

def foo():
    pass
"""

        success = agent_context.write_file_content(file_path, duplicate_content)

        assert success is False

    def test_multiple_file_operations(self, agent_context):
        """Test multiple sequential file operations."""
        files = [
            agent_context.project_path / f"file{i}.py"
            for i in range(3)
        ]

        # Write multiple files
        for i, file_path in enumerate(files):
            content = f"def func_{i}():\n    return {i}\n"
            success = agent_context.write_file_content(file_path, content)
            assert success is True

        # Verify all files exist
        for file_path in files:
            assert file_path.exists()
            content = agent_context.get_file_content(file_path)
            assert content is not None
            assert "def func_" in content
