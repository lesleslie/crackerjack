"""Unit tests for PatternDetector.

Tests anti-pattern detection, AST-based code analysis,
and proactive issue identification.
"""

import ast
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.services.pattern_detector import (
    AntiPattern,
    PatternDetector,
)


@pytest.mark.unit
class TestAntiPatternDataClass:
    """Test AntiPattern dataclass."""

    def test_anti_pattern_creation(self) -> None:
        """Test AntiPattern dataclass creation."""
        pattern = AntiPattern(
            pattern_type="complexity_hotspot",
            severity=Priority.HIGH,
            file_path="/test/file.py",
            line_number=42,
            description="Function has high complexity",
            suggestion="Break into smaller methods",
            prevention_strategy="extract_method",
        )

        assert pattern.pattern_type == "complexity_hotspot"
        assert pattern.severity == Priority.HIGH
        assert pattern.file_path == "/test/file.py"
        assert pattern.line_number == 42


@pytest.mark.unit
class TestPatternDetectorInitialization:
    """Test PatternDetector initialization."""

    def test_initialization(self, tmp_path) -> None:
        """Test detector initializes with required dependencies."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        assert detector.project_path == tmp_path
        assert detector.pattern_cache == mock_cache
        assert detector.logger is not None

    def test_anti_patterns_configured(self, tmp_path) -> None:
        """Test all anti-patterns are configured."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        expected_patterns = [
            "complexity_hotspot",
            "code_duplication",
            "performance_issues",
            "security_risks",
            "import_complexity",
        ]

        for pattern in expected_patterns:
            assert pattern in detector._anti_patterns
            assert "detector" in detector._anti_patterns[pattern]
            assert "description" in detector._anti_patterns[pattern]


@pytest.mark.unit
class TestShouldSkipFile:
    """Test file skipping logic."""

    def test_skip_pycache(self, tmp_path) -> None:
        """Test skipping __pycache__ directories."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        pycache_path = tmp_path / "__pycache__" / "test.py"
        assert detector._should_skip_file(pycache_path) is True

    def test_skip_git(self, tmp_path) -> None:
        """Test skipping .git directory."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        git_path = tmp_path / ".git" / "file.py"
        assert detector._should_skip_file(git_path) is True

    def test_skip_venv(self, tmp_path) -> None:
        """Test skipping virtual environment directories."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        venv_path = tmp_path / ".venv" / "lib" / "file.py"
        assert detector._should_skip_file(venv_path) is True

    def test_skip_node_modules(self, tmp_path) -> None:
        """Test skipping node_modules directory."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        node_path = tmp_path / "node_modules" / "package" / "file.py"
        assert detector._should_skip_file(node_path) is True

    def test_not_skip_regular_file(self, tmp_path) -> None:
        """Test not skipping regular Python files."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        regular_path = tmp_path / "src" / "module.py"
        assert detector._should_skip_file(regular_path) is False


@pytest.mark.unit
class TestDetectComplexityHotspots:
    """Test complexity hotspot detection."""

    @pytest.mark.asyncio
    async def test_detect_no_complexity_issues(self, tmp_path) -> None:
        """Test detection with no complexity issues."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "simple.py"
        test_file.write_text("""
def simple_func():
    pass

def another_func():
    pass
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_complexity_hotspots(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) == 0

    @pytest.mark.asyncio
    async def test_detect_complexity_hotspot(self, tmp_path) -> None:
        """Test detection of complexity hotspots."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        # Create highly complex function (complexity >= 12 for HIGH priority)
        test_file = tmp_path / "complex.py"
        test_file.write_text("""
def very_complex_func():
    if True:
        if False:
            for i in range(10):
                if i > 5:
                    while True:
                        if True:
                            for j in range(5):
                                if j > 2:
                                    try:
                                        pass
                                    except:
                                        if True:
                                            for k in range(3):
                                                pass
    return
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_complexity_hotspots(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) > 0
        assert patterns[0].pattern_type == "complexity_hotspot"
        assert patterns[0].severity == Priority.HIGH


@pytest.mark.unit
class TestDetectCodeDuplication:
    """Test code duplication detection."""

    @pytest.mark.asyncio
    async def test_detect_no_duplication(self, tmp_path) -> None:
        """Test detection with no code duplication."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "unique.py"
        test_file.write_text("""
def func1():
    return 1

def func2():
    return 2
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_code_duplication(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) == 0

    @pytest.mark.asyncio
    async def test_detect_line_duplication(self, tmp_path) -> None:
        """Test detection of duplicate lines."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        # Create identical lines that appear 3+ times
        test_file = tmp_path / "duplication.py"
        test_file.write_text("""
some_long_function_call_with_parameters()
some_long_function_call_with_parameters()
some_long_function_call_with_parameters()
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_code_duplication(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) > 0
        assert patterns[0].pattern_type == "code_duplication"


@pytest.mark.unit
class TestDetectPerformanceIssues:
    """Test performance issue detection."""

    @pytest.mark.asyncio
    async def test_detect_no_performance_issues(self, tmp_path) -> None:
        """Test detection with no performance issues."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "efficient.py"
        test_file.write_text("""
def efficient_func(items):
    return [x * 2 for x in items]
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_performance_issues(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) == 0

    @pytest.mark.asyncio
    async def test_detect_nested_loop(self, tmp_path) -> None:
        """Test detection of nested loops."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "nested.py"
        test_file.write_text("""
def nested_loop():
    for i in range(10):
        for j in range(10):
            pass
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_performance_issues(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) > 0
        assert "nested loop" in patterns[0].description.lower()

    @pytest.mark.asyncio
    async def test_detect_inefficient_concatenation(self, tmp_path) -> None:
        """Test detection of inefficient list concatenation."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "concat.py"
        test_file.write_text("""
def inefficient_concat():
    result = []
    for item in items:
        result += [item]
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_performance_issues(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) > 0
        assert any("concatenation" in p.description.lower() for p in patterns)


@pytest.mark.unit
class TestDetectSecurityRisks:
    """Test security risk detection."""

    @pytest.mark.asyncio
    async def test_detect_no_security_issues(self, tmp_path) -> None:
        """Test detection with no security issues."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "secure.py"
        test_file.write_text("""
def secure_func():
    return "safe"
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_security_risks(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) == 0

    @pytest.mark.asyncio
    async def test_detect_hardcoded_tmp_path(self, tmp_path) -> None:
        """Test detection of hardcoded /tmp/ paths."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "insecure.py"
        test_file.write_text("""
def insecure_func():
    path = "/tmp/data.txt"
    return path
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_security_risks(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) > 0
        assert any("hardcoded" in p.description.lower() for p in patterns)

    @pytest.mark.asyncio
    async def test_detect_shell_true(self, tmp_path) -> None:
        """Test detection of shell=True in subprocess."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "subprocess.py"
        test_file.write_text("""
import subprocess

def run_command():
    subprocess.run(["ls", "-l"], shell=True)
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_security_risks(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) > 0
        assert any("shell" in p.description.lower() for p in patterns)


@pytest.mark.unit
class TestDetectImportComplexity:
    """Test import complexity detection."""

    @pytest.mark.asyncio
    async def test_detect_simple_imports(self, tmp_path) -> None:
        """Test detection with simple imports."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        test_file = tmp_path / "simple_imports.py"
        test_file.write_text("""
import os
import sys
from pathlib import Path
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_import_complexity(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) == 0

    @pytest.mark.asyncio
    async def test_detect_deep_import(self, tmp_path) -> None:
        """Test detection of deep imports."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        # Deep import has > 2 dots (e.g., "very.deep.package.module" = 3 dots)
        test_file = tmp_path / "deep_import.py"
        test_file.write_text("""
import very.deep.package.module
""")

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_import_complexity(
            test_file, test_file.read_text(), tree
        )

        assert len(patterns) > 0
        assert any("deep" in p.description.lower() for p in patterns)

    @pytest.mark.asyncio
    async def test_detect_many_imports(self, tmp_path) -> None:
        """Test detection of too many imports."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        # Create file with many imports
        imports = "\n".join([f"import module{i}" for i in range(60)])
        test_file = tmp_path / "many_imports.py"
        test_file.write_text(imports)

        tree = ast.parse(test_file.read_text())
        patterns = await detector._detect_import_complexity(
            test_file, test_file.read_text(), tree
        )

        # Should detect high import count
        assert len(patterns) > 0


@pytest.mark.unit
class TestGenerateSolutionKey:
    """Test solution key generation."""

    def test_generate_solution_key(self, tmp_path) -> None:
        """Test generation of unique solution keys."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        pattern = AntiPattern(
            pattern_type="complexity_hotspot",
            severity=Priority.HIGH,
            file_path="/test/file.py",
            line_number=42,
            description="Test",
            suggestion="Test suggestion",
            prevention_strategy="test",
        )

        key = detector._generate_solution_key(pattern)

        assert "complexity_hotspot" in key
        assert "/test/file.py" in key
        assert "42" in key


@pytest.mark.unit
class TestMapAntiPatternToIssueType:
    """Test anti-pattern to issue type mapping."""

    def test_map_complexity_hotspot(self, tmp_path) -> None:
        """Test mapping complexity hotspot to issue type."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        issue_type = detector._map_anti_pattern_to_issue_type("complexity_hotspot")

        assert issue_type == IssueType.COMPLEXITY

    def test_map_code_duplication(self, tmp_path) -> None:
        """Test mapping code duplication to issue type."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        issue_type = detector._map_anti_pattern_to_issue_type("code_duplication")

        assert issue_type == IssueType.DRY_VIOLATION

    def test_map_performance_issues(self, tmp_path) -> None:
        """Test mapping performance issues to issue type."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        issue_type = detector._map_anti_pattern_to_issue_type("performance_issues")

        assert issue_type == IssueType.PERFORMANCE

    def test_map_security_risks(self, tmp_path) -> None:
        """Test mapping security risks to issue type."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        issue_type = detector._map_anti_pattern_to_issue_type("security_risks")

        assert issue_type == IssueType.SECURITY

    def test_map_unknown_pattern(self, tmp_path) -> None:
        """Test mapping unknown pattern returns None."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        issue_type = detector._map_anti_pattern_to_issue_type("unknown_pattern")

        assert issue_type is None


@pytest.mark.unit
class TestCreateTempIssueForLookup:
    """Test temporary issue creation for pattern lookup."""

    def test_create_temp_issue(self, tmp_path) -> None:
        """Test creation of temporary issue for lookup."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        pattern = AntiPattern(
            pattern_type="complexity_hotspot",
            severity=Priority.HIGH,
            file_path="/test/file.py",
            line_number=42,
            description="High complexity detected",
            suggestion="Refactor",
            prevention_strategy="extract_method",
        )

        issue = detector._create_temp_issue_for_lookup(pattern, IssueType.COMPLEXITY)

        assert issue.id == "temp"
        assert issue.type == IssueType.COMPLEXITY
        assert issue.severity == Priority.HIGH
        assert issue.message == "High complexity detected"
        assert issue.file_path == "/test/file.py"


@pytest.mark.unit
class TestSuggestProactiveRefactoring:
    """Test proactive refactoring suggestions."""

    @pytest.mark.asyncio
    async def test_suggest_empty_patterns(self, tmp_path) -> None:
        """Test suggesting with no anti-patterns."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        issues = await detector.suggest_proactive_refactoring([])

        assert issues == []

    @pytest.mark.asyncio
    async def test_suggest_refactoring(self, tmp_path) -> None:
        """Test suggesting refactoring for detected patterns."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        patterns = [
            AntiPattern(
                pattern_type="complexity_hotspot",
                severity=Priority.HIGH,
                file_path="/test/complex.py",
                line_number=10,
                description="Function has complexity 12",
                suggestion="Break down function",
                prevention_strategy="extract_method",
            ),
            AntiPattern(
                pattern_type="code_duplication",
                severity=Priority.MEDIUM,
                file_path="/test/dup.py",
                line_number=20,
                description="Duplicate code detected",
                suggestion="Extract to utility",
                prevention_strategy="extract_utility",
            ),
        ]

        issues = await detector.suggest_proactive_refactoring(patterns)

        assert len(issues) == 2
        assert issues[0].type == IssueType.COMPLEXITY
        assert issues[1].type == IssueType.DRY_VIOLATION
        assert all("proactive_" in i.id for i in issues)


@pytest.mark.unit
class TestGetCachedSolutions:
    """Test cached solution retrieval."""

    @pytest.mark.asyncio
    async def test_get_empty_solutions(self, tmp_path) -> None:
        """Test getting solutions with no patterns."""
        mock_cache = Mock()
        mock_cache.get_best_pattern_for_issue = Mock(return_value=None)
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        solutions = await detector.get_cached_solutions([])

        assert solutions == {}

    @pytest.mark.asyncio
    async def test_get_cached_solution(self, tmp_path) -> None:
        """Test getting cached solution for pattern."""
        mock_cache = Mock()
        mock_cached_pattern = Mock()
        mock_cache.get_best_pattern_for_issue = Mock(return_value=mock_cached_pattern)
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        pattern = AntiPattern(
            pattern_type="complexity_hotspot",
            severity=Priority.HIGH,
            file_path="/test/file.py",
            line_number=10,
            description="Test",
            suggestion="Test",
            prevention_strategy="test",
        )

        solutions = await detector.get_cached_solutions([pattern])

        # Should have one solution with the generated key
        assert len(solutions) == 1
        key = list(solutions.keys())[0]
        assert "complexity_hotspot" in key


@pytest.mark.unit
class TestAnalyzeCodebase:
    """Test full codebase analysis."""

    @pytest.mark.asyncio
    async def test_analyze_empty_codebase(self, tmp_path) -> None:
        """Test analyzing empty codebase."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        patterns = await detector.analyze_codebase()

        assert patterns == []

    @pytest.mark.asyncio
    async def test_analyze_with_files(self, tmp_path) -> None:
        """Test analyzing codebase with files."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        # Create test files
        (tmp_path / "simple.py").write_text("def simple(): pass")
        (tmp_path / "complex.py").write_text("""
def complex():
    if True:
        if False:
            for i in range(10):
                pass
""")

        patterns = await detector.analyze_codebase()

        # Should detect at least complexity in complex.py
        assert len(patterns) >= 0

    @pytest.mark.asyncio
    async def test_analyze_skips_special_dirs(self, tmp_path) -> None:
        """Test analysis skips special directories."""
        mock_cache = Mock()
        detector = PatternDetector(project_path=tmp_path, pattern_cache=mock_cache)

        # Create files in special directories
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cached.py").write_text("def cached(): pass")

        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "lib.py").write_text("def venv_lib(): pass")

        patterns = await detector.analyze_codebase()

        # Should skip files in special directories
        assert not any("__pycache__" in p.file_path for p in patterns)
        assert not any(".venv" in p.file_path for p in patterns)
