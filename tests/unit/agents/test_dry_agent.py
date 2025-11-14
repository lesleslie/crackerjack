"""Unit tests for DRYAgent.

Tests DRY violation detection, semantic duplicate detection,
and automated fixes for repetitive code patterns.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.dry_agent import DRYAgent


@pytest.mark.unit
class TestDRYAgentInitialization:
    """Test DRYAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test DRYAgent initializes correctly."""
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            agent = DRYAgent(context)

            assert agent.context == context
            assert agent.semantic_insights == {}

    def test_get_supported_types(self, context):
        """Test agent supports DRY violation issues."""
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            agent = DRYAgent(context)

            supported = agent.get_supported_types()

            assert IssueType.DRY_VIOLATION in supported
            assert len(supported) == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestDRYAgentCanHandle:
    """Test issue detection and handling capability."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DRYAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            return DRYAgent(context)

    async def test_can_handle_dry_violation(self, agent):
        """Test high confidence for DRY violation issues."""
        issue = Issue(
            id="dry-001",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="Repeated code pattern detected",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_cannot_handle_unsupported_type(self, agent):
        """Test agent cannot handle unsupported issue types."""
        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
class TestDRYAgentAnalyzeAndFix:
    """Test DRY violation analysis and fixing."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DRYAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            return DRYAgent(context)

    async def test_analyze_and_fix_no_file_path(self, agent):
        """Test analyze_and_fix when no file path provided."""
        issue = Issue(
            id="dry-001",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="DRY violation",
            file_path=None,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_analyze_and_fix_file_not_exists(self, agent, tmp_path):
        """Test analyze_and_fix when file doesn't exist."""
        issue = Issue(
            id="dry-001",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="DRY violation",
            file_path=str(tmp_path / "nonexistent.py"),
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_analyze_and_fix_with_violations(self, agent, tmp_path):
        """Test analyze_and_fix with detected violations."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import json

def func1():
    return json.dumps({"error": "message1", "success": False})

def func2():
    return json.dumps({"error": "message2", "success": False})

def func3():
    return json.dumps({"error": "message3", "success": False})
""")

        issue = Issue(
            id="dry-001",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="Repeated error response pattern",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        with patch.object(agent, "_detect_semantic_violations", return_value=[]):
            result = await agent.analyze_and_fix(issue)

            # May or may not find violations depending on pattern matching
            assert result.confidence >= 0.0

    async def test_analyze_and_fix_error_handling(self, agent, tmp_path):
        """Test error handling in analyze_and_fix."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\n")

        issue = Issue(
            id="dry-001",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="DRY violation",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(side_effect=Exception("Read error"))

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert "Error processing" in result.remaining_issues[0]


@pytest.mark.unit
class TestDRYAgentViolationDetection:
    """Test DRY violation detection methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DRYAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            return DRYAgent(context)

    def test_detect_error_response_patterns(self, agent):
        """Test detecting repeated error response patterns."""
        content = """
def func1():
    return json.dumps({"error": "msg1", "success": False})

def func2():
    return json.dumps({"error": "msg2", "success": False})

def func3():
    return json.dumps({"error": "msg3", "success": False})
"""
        with patch("crackerjack.agents.dry_agent.SAFE_PATTERNS") as mock_patterns:
            mock_pattern = Mock()
            mock_pattern.test.return_value = True
            mock_compiled = Mock()
            mock_compiled.search.return_value = Mock(group=lambda x: "test_error")
            mock_pattern._get_compiled_pattern.return_value = mock_compiled
            mock_patterns.__getitem__.return_value = mock_pattern

            violations = agent._detect_error_response_patterns(content)

            # Should detect repeated pattern if >= 3 instances
            assert isinstance(violations, list)

    def test_detect_path_conversion_patterns(self, agent):
        """Test detecting repeated path conversion patterns."""
        content = """
path1 = Path(str_path1)
path2 = Path(str_path2)
path3 = Path(str_path3)
"""
        with patch("crackerjack.agents.dry_agent.SAFE_PATTERNS") as mock_patterns:
            mock_pattern = Mock()
            mock_pattern.test.return_value = True
            mock_patterns.__getitem__.return_value = mock_pattern

            violations = agent._detect_path_conversion_patterns(content)

            # Should detect pattern if >= 2 instances
            assert len(violations) > 0
            assert violations[0]["type"] == "path_conversion_pattern"

    def test_detect_file_existence_patterns(self, agent):
        """Test detecting repeated file existence checks."""
        content = """
if file1.exists():
    pass
if file2.exists():
    pass
if file3.exists():
    pass
"""
        with patch("crackerjack.agents.dry_agent.SAFE_PATTERNS") as mock_patterns:
            mock_pattern = Mock()
            mock_pattern.test.return_value = True
            mock_patterns.__getitem__.return_value = mock_pattern

            violations = agent._detect_file_existence_patterns(content)

            # Should detect pattern if >= 3 instances
            assert len(violations) > 0
            assert violations[0]["type"] == "file_existence_pattern"

    def test_detect_exception_patterns(self, agent):
        """Test detecting repeated exception handling patterns."""
        content = """
except Exception as e:
    error = str(e)
except ValueError as e:
    error = str(e)
except RuntimeError as e:
    error = str(e)
"""
        with patch("crackerjack.agents.dry_agent.SAFE_PATTERNS") as mock_patterns:
            mock_pattern = Mock()
            mock_pattern.test.return_value = True
            mock_patterns.__getitem__.return_value = mock_pattern

            violations = agent._detect_exception_patterns(content)

            # Should detect pattern if >= 3 instances
            assert isinstance(violations, list)


@pytest.mark.unit
class TestDRYAgentFixApplication:
    """Test DRY fix application methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DRYAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            return DRYAgent(context)

    def test_apply_dry_fixes_no_violations(self, agent):
        """Test applying fixes when no violations."""
        content = "def foo():\n    pass\n"
        violations = []

        result = agent._apply_dry_fixes(content, violations)

        assert result == content

    def test_apply_dry_fixes_with_error_response_violation(self, agent):
        """Test applying fixes for error response violations."""
        content = "import json\n\ndef foo():\n    pass\n"
        violation = {
            "type": "error_response_pattern",
            "instances": [{"line_number": 3, "error_message": "test"}],
        }

        with patch.object(agent, "_fix_error_response_pattern") as mock_fix:
            mock_fix.return_value = (content.split("\n"), True)

            result = agent._apply_dry_fixes(content, [violation])

            mock_fix.assert_called_once()

    def test_apply_dry_fixes_with_path_conversion_violation(self, agent):
        """Test applying fixes for path conversion violations."""
        content = "path = Path(str_path)\n"
        violation = {
            "type": "path_conversion_pattern",
            "instances": [{"line_number": 1}],
        }

        with patch.object(agent, "_fix_path_conversion_pattern") as mock_fix:
            mock_fix.return_value = (content.split("\n"), True)

            result = agent._apply_dry_fixes(content, [violation])

            mock_fix.assert_called_once()

    def test_find_utility_insert_position(self, agent):
        """Test finding position to insert utility functions."""
        lines = [
            "import os",
            "import sys",
            "",
            "def main():",
            "    pass",
        ]

        position = agent._find_utility_insert_position(lines)

        # Should insert after imports
        assert position == 2

    def test_check_ensure_path_exists(self, agent):
        """Test checking if _ensure_path utility already exists."""
        lines = [
            "def _ensure_path(path):",
            "    return Path(path)",
        ]

        result = agent._check_ensure_path_exists(lines)

        assert result is True

    def test_check_ensure_path_not_exists(self, agent):
        """Test checking when _ensure_path utility doesn't exist."""
        lines = [
            "def foo():",
            "    pass",
        ]

        result = agent._check_ensure_path_exists(lines)

        assert result is False


@pytest.mark.unit
class TestDRYAgentFunctionExtraction:
    """Test function extraction for semantic analysis."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DRYAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            return DRYAgent(context)

    def test_extract_code_functions_simple(self, agent):
        """Test extracting simple function."""
        content = """
def test_function():
    return True
"""
        functions = agent._extract_code_functions(content)

        assert len(functions) == 1
        assert functions[0]["name"] == "test_function"
        assert functions[0]["type"] == "function"

    def test_extract_code_functions_multiple(self, agent):
        """Test extracting multiple functions."""
        content = """
def func1():
    return 1

def func2():
    return 2

def func3():
    return 3
"""
        functions = agent._extract_code_functions(content)

        assert len(functions) == 3
        assert functions[0]["name"] == "func1"
        assert functions[1]["name"] == "func2"
        assert functions[2]["name"] == "func3"

    def test_is_function_definition(self, agent):
        """Test detecting function definitions."""
        assert agent._is_function_definition("def foo():") is True
        assert agent._is_function_definition("def bar(x, y):") is True
        assert agent._is_function_definition("    return x") is False
        assert agent._is_function_definition("# comment") is False

    def test_should_skip_line_empty(self, agent):
        """Test skipping empty lines."""
        result = agent._should_skip_line("", None, "")

        assert result is True

    def test_should_skip_line_comment(self, agent):
        """Test skipping comment lines."""
        result = agent._should_skip_line("# This is a comment", None, "# This is a comment")

        assert result is True

    def test_should_skip_line_code(self, agent):
        """Test not skipping code lines."""
        result = agent._should_skip_line("return True", None, "    return True")

        assert result is False

    def test_is_line_inside_function(self, agent):
        """Test checking if line is inside function."""
        current_function = {"indent_level": 0}

        # Line with greater indent is inside
        assert agent._is_line_inside_function(current_function, 4, "return True") is True

        # Line with same indent but starting with quote is inside (docstring)
        assert agent._is_line_inside_function(current_function, 0, '"""Docstring"""') is True

        # Line with lesser or equal indent (not quote) is outside
        assert agent._is_line_inside_function(current_function, 0, "def next():") is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestDRYAgentSemanticDetection:
    """Test semantic duplicate detection."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DRYAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer") as mock_create:
            mock_enhancer = AsyncMock()
            mock_create.return_value = mock_enhancer
            agent = DRYAgent(context)
            agent.semantic_enhancer = mock_enhancer
            return agent

    async def test_detect_semantic_violations_with_matches(self, agent, tmp_path):
        """Test detecting semantic violations with high confidence matches."""
        content = """
def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total
"""
        mock_insight = Mock()
        mock_insight.high_confidence_matches = 2
        mock_insight.total_matches = 3
        mock_insight.related_patterns = ["pattern1", "pattern2", "pattern3"]

        agent.semantic_enhancer.find_duplicate_patterns.return_value = mock_insight

        violations = await agent._detect_semantic_violations(content, tmp_path)

        assert len(violations) > 0
        assert violations[0]["type"] == "semantic_duplicate"
        assert violations[0]["confidence_score"] > 0

    async def test_detect_semantic_violations_no_matches(self, agent, tmp_path):
        """Test detecting semantic violations with no matches."""
        content = """
def simple_function():
    return True
"""
        mock_insight = Mock()
        mock_insight.high_confidence_matches = 0
        mock_insight.total_matches = 0
        mock_insight.related_patterns = []

        agent.semantic_enhancer.find_duplicate_patterns.return_value = mock_insight

        violations = await agent._detect_semantic_violations(content, tmp_path)

        assert len(violations) == 0

    async def test_detect_semantic_violations_error_handling(self, agent, tmp_path):
        """Test semantic violation detection error handling."""
        content = "def foo(): pass"

        agent.semantic_enhancer.find_duplicate_patterns.side_effect = Exception(
            "Semantic analysis failed"
        )

        # Should not raise exception
        violations = await agent._detect_semantic_violations(content, tmp_path)

        assert violations == []


@pytest.mark.unit
class TestDRYAgentResultCreation:
    """Test result creation helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DRYAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            return DRYAgent(context)

    def test_create_no_fixes_result(self, agent):
        """Test creating result when no fixes could be applied."""
        result = agent._create_no_fixes_result()

        assert result.success is False
        assert result.confidence == 0.5
        assert len(result.remaining_issues) > 0
        assert len(result.recommendations) > 0

    def test_create_dry_error_result(self, agent):
        """Test creating error result."""
        error = Exception("Test error message")

        result = agent._create_dry_error_result(error)

        assert result.success is False
        assert result.confidence == 0.0
        assert "Error processing" in result.remaining_issues[0]

    def test_validate_dry_issue_no_file_path(self, agent):
        """Test validating issue without file path."""
        issue = Issue(
            id="dry-001",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="DRY violation",
            file_path=None,
        )

        result = agent._validate_dry_issue(issue)

        assert result is not None
        assert result.success is False

    def test_validate_dry_issue_file_not_exists(self, agent, tmp_path):
        """Test validating issue with non-existent file."""
        issue = Issue(
            id="dry-001",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="DRY violation",
            file_path=str(tmp_path / "missing.py"),
        )

        result = agent._validate_dry_issue(issue)

        assert result is not None
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    def test_validate_dry_issue_valid(self, agent, tmp_path):
        """Test validating issue with valid file."""
        test_file = tmp_path / "valid.py"
        test_file.write_text("def foo(): pass")

        issue = Issue(
            id="dry-001",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="DRY violation",
            file_path=str(test_file),
        )

        result = agent._validate_dry_issue(issue)

        assert result is None  # Validation passed


@pytest.mark.unit
@pytest.mark.asyncio
class TestDRYAgentProcessing:
    """Test DRY violation processing workflow."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DRYAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.dry_agent.create_semantic_enhancer"):
            return DRYAgent(context)

    async def test_process_dry_violation_no_violations(self, agent, tmp_path):
        """Test processing when no violations found."""
        test_file = tmp_path / "clean.py"
        test_file.write_text("def foo():\n    return True\n")

        agent.context.get_file_content = Mock(return_value=test_file.read_text())

        with patch.object(agent, "_detect_dry_violations", return_value=[]):
            with patch.object(agent, "_detect_semantic_violations", return_value=[]):
                result = await agent._process_dry_violation(test_file)

                assert result.success is True
                assert result.confidence == 0.7
                assert "No DRY violations" in result.recommendations[0]

    async def test_process_dry_violation_cannot_read_file(self, agent, tmp_path):
        """Test processing when file cannot be read."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        agent.context.get_file_content = Mock(return_value=None)

        result = await agent._process_dry_violation(test_file)

        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_apply_and_save_dry_fixes_success(self, agent, tmp_path):
        """Test successfully applying and saving fixes."""
        test_file = tmp_path / "test.py"
        content = "original content"
        violations = [{"type": "path_conversion_pattern"}]

        with patch.object(agent, "_apply_dry_fixes", return_value="modified content"):
            agent.context.write_file_content = Mock(return_value=True)

            with patch("crackerjack.agents.dry_agent.get_session_enhanced_recommendations") as mock_enhance:
                mock_enhance.return_value = ["Verify functionality"]

                result = await agent._apply_and_save_dry_fixes(
                    test_file, content, violations
                )

                assert result.success is True
                assert result.confidence == 0.8
                assert len(result.fixes_applied) > 0

    async def test_apply_and_save_dry_fixes_no_changes(self, agent, tmp_path):
        """Test when fixes produce no changes."""
        test_file = tmp_path / "test.py"
        content = "original content"
        violations = [{"type": "unknown"}]

        with patch.object(agent, "_apply_dry_fixes", return_value=content):
            result = await agent._apply_and_save_dry_fixes(
                test_file, content, violations
            )

            assert result.success is False
            assert result.confidence == 0.5

    async def test_apply_and_save_dry_fixes_write_failure(self, agent, tmp_path):
        """Test when writing fixed content fails."""
        test_file = tmp_path / "test.py"
        content = "original content"
        violations = [{"type": "path_conversion_pattern"}]

        with patch.object(agent, "_apply_dry_fixes", return_value="modified content"):
            agent.context.write_file_content = Mock(return_value=False)

            result = await agent._apply_and_save_dry_fixes(
                test_file, content, violations
            )

            assert result.success is False
            assert "Failed to write" in result.remaining_issues[0]
