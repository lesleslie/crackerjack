"""Additional edge case tests for agent base classes.

These tests extend the base test coverage for async operations,
encoding issues, and edge cases not covered in test_base.py.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

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
class TestAgentContextAsyncOperations:
    """Test AgentContext async file operations."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    @pytest.mark.asyncio
    async def test_async_get_file_content_success(self, context, tmp_path):
        """Test async file reading."""
        test_file = tmp_path / "test.py"
        content = "print('hello async')"
        test_file.write_text(content)

        result = await context.async_get_file_content(test_file)

        assert result == content

    @pytest.mark.asyncio
    async def test_async_get_file_content_nonexistent(self, context, tmp_path):
        """Test async reading of non-existent file."""
        nonexistent = tmp_path / "nonexistent.py"

        result = await context.async_get_file_content(nonexistent)

        assert result is None

    @pytest.mark.asyncio
    async def test_async_get_file_content_too_large(self, context, tmp_path):
        """Test async reading of file exceeding max size."""
        context.max_file_size = 100
        large_file = tmp_path / "large.py"
        large_file.write_text("x" * 200)

        result = await context.async_get_file_content(large_file)

        assert result is None

    @pytest.mark.asyncio
    async def test_async_write_file_content_success(self, context, tmp_path):
        """Test async file writing."""
        output_file = tmp_path / "output.py"
        content = "print('async write')"

        result = await context.async_write_file_content(output_file, content)

        assert result is True
        assert output_file.read_text() == content

    @pytest.mark.asyncio
    async def test_async_write_verification(self, context, tmp_path):
        """Test async write verification."""
        output_file = tmp_path / "verify.py"
        content = "x = 1"

        # Mock read to simulate verification failure
        with patch.object(
            context, "async_get_file_content", return_value="different content"
        ):
            result = await context.async_write_file_content(output_file, content)

        # Should fail verification
        assert result is False


@pytest.mark.unit
class TestAgentContextEncodingHandling:
    """Test AgentContext handling of different encodings."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context."""
        return AgentContext(project_path=tmp_path)

    def test_read_file_with_utf8_content(self, context, tmp_path):
        """Test reading file with UTF-8 content."""
        test_file = tmp_path / "utf8.py"
        content = "# -*- coding: utf-8 -*-\ndef hello():\n    print('Hello 世界')\n"
        test_file.write_text(content, encoding="utf-8")

        result = context.get_file_content(test_file)

        assert result is not None
        assert "世界" in result

    def test_read_file_with_ascii_content(self, context, tmp_path):
        """Test reading file with ASCII content."""
        test_file = tmp_path / "ascii.py"
        content = "def hello():\n    print('Hello')\n"
        test_file.write_text(content, encoding="ascii")

        result = context.get_file_content(test_file)

        assert result is not None
        assert "Hello" in result

    def test_read_file_with_special_characters(self, context, tmp_path):
        """Test reading file with special characters."""
        test_file = tmp_path / "special.py"
        content = "© 2024 Test™\n" + 'print("Quotes: \' \'")\n'
        test_file.write_text(content, encoding="utf-8")

        result = context.get_file_content(test_file)

        assert result is not None
        assert "©" in result
        assert "™" in result


@pytest.mark.unit
class TestAgentContextLineEndings:
    """Test AgentContext handling of different line endings."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context."""
        return AgentContext(project_path=tmp_path)

    def test_read_file_with_crlf_endings(self, context, tmp_path):
        """Test reading file with CRLF line endings."""
        test_file = tmp_path / "crlf.py"
        content = "line1\r\nline2\r\nline3\r\n"
        test_file.write_bytes(content.encode("utf-8"))

        result = context.get_file_content(test_file)

        assert result is not None
        assert "\r\n" in result

    def test_read_file_with_lf_endings(self, context, tmp_path):
        """Test reading file with LF line endings."""
        test_file = tmp_path / "lf.py"
        content = "line1\nline2\nline3\n"
        test_file.write_bytes(content.encode("utf-8"))

        result = context.get_file_content(test_file)

        assert result is not None
        assert "\n" in result

    def test_read_file_with_mixed_endings(self, context, tmp_path):
        """Test reading file with mixed line endings."""
        test_file = tmp_path / "mixed.py"
        content = "line1\nline2\r\nline3\n"
        test_file.write_bytes(content.encode("utf-8"))

        result = context.get_file_content(test_file)

        assert result is not None
        assert "\n" in result and "\r\n" in result

    def test_write_preserves_line_endings(self, context, tmp_path):
        """Test that write preserves line endings."""
        test_file = tmp_path / "endings.py"
        content = "line1\nline2\n"
        test_file.write_text(content)

        result = context.write_file_content(test_file, content)

        assert result is True
        # Read back and verify
        written = test_file.read_text()
        assert written == content


@pytest.mark.unit
class TestSubAgentCommandExecution:
    """Test SubAgent command execution edge cases."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context."""
        return AgentContext(project_path=tmp_path)

    @pytest.fixture
    def agent(self, context):
        """Create test agent."""
        class TestAgent(SubAgent):
            async def can_handle(self, issue: Issue) -> float:
                return 0.5

            async def analyze_and_fix(self, issue: Issue) -> FixResult:
                return FixResult(success=True, confidence=0.5)

            def get_supported_types(self) -> set[IssueType]:
                return {IssueType.FORMATTING}

        return TestAgent(context)

    @pytest.mark.asyncio
    async def test_run_command_with_environment_variables(self, agent, tmp_path):
        """Test running command with environment variables."""
        test_script = tmp_path / "test.sh"
        test_script.write_text("#!/bin/bash\necho $TEST_VAR\n")
        test_script.chmod(0o755)

        import os

        env = os.environ.copy()
        env["TEST_VAR"] = "test_value"

        returncode, stdout, stderr = await agent.run_command(
            ["bash", str(test_script)],
            env=env,
        )

        assert returncode == 0
        assert "test_value" in stdout

    @pytest.mark.asyncio
    async def test_run_command_custom_timeout(self, agent):
        """Test command with custom timeout."""
        # Use short timeout
        returncode, _stdout, stderr = await agent.run_command(
            ["sleep", "5"],
            timeout=0.5,
        )

        assert returncode == -1
        assert "timed out" in stderr.lower()

    @pytest.mark.asyncio
    async def test_run_command_stderr_capture(self, agent):
        """Test that stderr is captured separately."""
        returncode, stdout, stderr = await agent.run_command(
            ["python", "-c", "import sys; sys.stdout.write('out'); sys.stderr.write('err')"]
        )

        assert returncode == 0
        assert stdout == "out"
        assert stderr == "err"


@pytest.mark.unit
class TestFixResultMergeEdgeCases:
    """Test FixResult merge with edge cases."""

    def test_merge_with_empty_result(self):
        """Test merging with empty FixResult."""
        result1 = FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["Fix A"],
            files_modified=["file1.py"],
        )

        result2 = FixResult(success=True, confidence=0.0)

        merged = result1.merge_with(result2)

        assert merged.success is True
        assert merged.confidence == 0.9
        assert "Fix A" in merged.fixes_applied
        assert "file1.py" in merged.files_modified

    def test_merge_both_empty(self):
        """Test merging two empty results."""
        result1 = FixResult(success=True, confidence=0.0)
        result2 = FixResult(success=True, confidence=0.0)

        merged = result1.merge_with(result2)

        assert merged.success is True
        assert merged.confidence == 0.0
        assert merged.fixes_applied == []
        assert merged.files_modified == []

    def test_merge_with_all_duplicate_fixes(self):
        """Test merge when all fixes are duplicates."""
        result1 = FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["Fix A", "Fix B"],
            files_modified=["file1.py"],
        )

        result2 = FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["Fix A", "Fix B"],
            files_modified=["file1.py"],
        )

        merged = result1.merge_with(result2)

        # Should deduplicate
        assert len(merged.fixes_applied) == 2
        assert set(merged.fixes_applied) == {"Fix A", "Fix B"}
        assert len(merged.files_modified) == 1

    def test_merge_preserves_all_fields(self):
        """Test that merge preserves all result fields."""
        result1 = FixResult(
            success=True,
            confidence=0.7,
            fixes_applied=["Fix 1"],
            remaining_issues=["Issue 1"],
            recommendations=["Rec 1"],
            files_modified=["file1.py"],
        )

        result2 = FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["Fix 2"],
            remaining_issues=["Issue 2"],
            recommendations=["Rec 2"],
            files_modified=["file2.py"],
        )

        merged = result1.merge_with(result2)

        # Check all fields present and merged
        assert len(merged.fixes_applied) == 2
        assert len(merged.remaining_issues) == 2
        assert len(merged.recommendations) == 2
        assert len(merged.files_modified) == 2


@pytest.mark.unit
class TestAgentContextEdgeCases:
    """Test AgentContext edge cases and boundary conditions."""

    def test_get_file_content_zero_size(self, tmp_path):
        """Test reading empty file."""
        context = AgentContext(project_path=tmp_path)
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")

        result = context.get_file_content(empty_file)

        assert result == ""

    def test_get_file_content_exactly_max_size(self, tmp_path):
        """Test reading file exactly at max size limit."""
        context = AgentContext(project_path=tmp_path, max_file_size=100)
        test_file = tmp_path / "exact.py"
        test_file.write_text("x" * 100)

        result = context.get_file_content(test_file)

        # Should succeed (at limit, not exceeding)
        assert result == "x" * 100

    def test_get_file_content_one_byte_over_max(self, tmp_path):
        """Test reading file one byte over max size."""
        context = AgentContext(project_path=tmp_path, max_file_size=100)
        test_file = tmp_path / "over.py"
        test_file.write_text("x" * 101)

        result = context.get_file_content(test_file)

        # Should fail (exceeds limit)
        assert result is None

    def test_write_file_content_empty_file(self, tmp_path):
        """Test writing empty content to file."""
        context = AgentContext(project_path=tmp_path)
        output_file = tmp_path / "empty.py"

        result = context.write_file_content(output_file, "")

        assert result is True
        assert output_file.read_text() == ""

    def test_write_file_content_overwrites_existing(self, tmp_path):
        """Test that write overwrites existing file."""
        context = AgentContext(project_path=tmp_path)
        test_file = tmp_path / "overwrite.py"

        # Write initial content
        test_file.write_text("original content")

        # Overwrite with new content
        result = context.write_file_content(test_file, "new content")

        assert result is True
        assert test_file.read_text() == "new content"
        assert test_file.read_text() != "original content"

    def test_write_file_content_to_nested_directory(self, tmp_path):
        """Test writing to file in nested directory."""
        context = AgentContext(project_path=tmp_path)
        nested_dir = tmp_path / "nested" / "dir"
        nested_dir.mkdir(parents=True, exist_ok=True)
        output_file = nested_dir / "file.py"
        content = "x = 1"

        result = context.write_file_content(output_file, content)

        assert result is True
        assert output_file.read_text() == content


@pytest.mark.unit
class TestIssueDataclassEdgeCases:
    """Test Issue dataclass with edge cases."""

    def test_issue_with_empty_message(self):
        """Test issue with empty message."""
        issue = Issue(
            id="test-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="",
        )

        assert issue.message == ""

    def test_issue_with_very_long_message(self):
        """Test issue with very long message."""
        long_message = "x" * 10000
        issue = Issue(
            id="test-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message=long_message,
        )

        assert len(issue.message) == 10000

    def test_issue_with_special_characters_in_details(self):
        """Test issue with special characters in details."""
        issue = Issue(
            id="test-001",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Security issue",
            details=[
                "Detail with 'quotes'",
                'Detail with "double quotes"',
                "Detail with\nnewline",
                "Detail with\ttab",
            ],
        )

        assert len(issue.details) == 4
        assert "\n" in issue.details[2]
        assert "\t" in issue.details[3]

    def test_issue_with_unicode_in_fields(self):
        """Test issue with unicode characters in all fields."""
        issue = Issue(
            id="test-你好",
            type=IssueType.DOCUMENTATION,
            severity=Priority.MEDIUM,
            message="Message with emoji 🎉",
            file_path="/path/to/文件.py",
            details=["Detail with ©", "Detail with ™"],
        )

        assert "你好" in issue.id
        assert "🎉" in issue.message
        assert "文件" in issue.file_path
        assert "©" in issue.details[0]
        assert "™" in issue.details[1]


@pytest.mark.unit
class TestAgentRegistryConcurrency:
    """Test AgentRegistry with concurrent access."""

    def test_register_and_create_isolated(self, tmp_path):
        """Test that register and create operations are isolated."""

        class MockAgent1(SubAgent):
            async def can_handle(self, issue: Issue) -> float:
                return 0.5

            async def analyze_and_fix(self, issue: Issue) -> FixResult:
                return FixResult(success=True, confidence=0.5)

            def get_supported_types(self) -> set[IssueType]:
                return {IssueType.FORMATTING}

        class MockAgent2(SubAgent):
            async def can_handle(self, issue: Issue) -> float:
                return 0.6

            async def analyze_and_fix(self, issue: Issue) -> FixResult:
                return FixResult(success=True, confidence=0.6)

            def get_supported_types(self) -> set[IssueType]:
                return {IssueType.SECURITY}

        registry = AgentRegistry()
        context = AgentContext(project_path=tmp_path)

        # Register both agents
        registry.register(MockAgent1)
        registry.register(MockAgent2)

        # Create instances
        agents = registry.create_all(context)

        # Verify both created and isolated
        assert len(agents) == 2
        assert agents[0] is not agents[1]
        assert agents[0].context is agents[1].context

    def test_multiple_registries_independent(self, tmp_path):
        """Test that multiple registries are independent."""

        class MockAgent(SubAgent):
            async def can_handle(self, issue: Issue) -> float:
                return 0.5

            async def analyze_and_fix(self, issue: Issue) -> FixResult:
                return FixResult(success=True, confidence=0.5)

            def get_supported_types(self) -> set[IssueType]:
                return {IssueType.FORMATTING}

        registry1 = AgentRegistry()
        registry2 = AgentRegistry()

        # Register in different registries
        registry1.register(MockAgent)

        # registry2 should not have the agent
        context = AgentContext(project_path=tmp_path)
        agents1 = registry1.create_all(context)
        agents2 = registry2.create_all(context)

        assert len(agents1) == 1
        assert len(agents2) == 0
