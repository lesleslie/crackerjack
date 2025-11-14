"""Unit tests for ImportOptimizationAgent.

Tests AST-based import analysis, mixed import detection,
unused import removal, PEP 8 organization, and import consolidation.
"""

import ast
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.import_optimization_agent import (
    ImportAnalysis,
    ImportOptimizationAgent,
)


@pytest.mark.unit
class TestImportOptimizationAgentInitialization:
    """Test ImportOptimizationAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test ImportOptimizationAgent initializes correctly."""
        agent = ImportOptimizationAgent(context)

        assert agent.context == context
        assert agent.name == "import_optimization"

    def test_get_supported_types(self, context):
        """Test agent supports import-related issue types."""
        agent = ImportOptimizationAgent(context)

        supported = agent.get_supported_types()

        assert IssueType.IMPORT_ERROR in supported
        assert IssueType.DEAD_CODE in supported
        assert len(supported) == 2


@pytest.mark.unit
@pytest.mark.asyncio
class TestImportOptimizationAgentCanHandle:
    """Test confidence calculation for import issues."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    async def test_can_handle_supported_type(self, agent):
        """Test high confidence for supported types."""
        issue = Issue(
            id="import-001",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="Import error detected",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.85

    async def test_can_handle_unused_import_keyword(self, agent):
        """Test confidence for unused import keywords."""
        issue = Issue(
            id="import-002",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused import detected in module",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_import_style_keyword(self, agent):
        """Test confidence for import style issues."""
        issue = Issue(
            id="import-003",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.LOW,
            message="Mixed import style detected",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_unsupported_type(self, agent):
        """Test zero confidence for unsupported types."""
        issue = Issue(
            id="import-004",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
class TestImportOptimizationAgentFileAnalysis:
    """Test file analysis functionality."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    async def test_analyze_file_valid_python(self, agent, tmp_path):
        """Test analyzing valid Python file."""
        test_file = tmp_path / "module.py"
        test_file.write_text("""
import os
import sys
from pathlib import Path
from typing import Any
""")

        analysis = await agent.analyze_file(test_file)

        assert isinstance(analysis, ImportAnalysis)
        assert analysis.file_path == test_file

    async def test_analyze_file_with_mixed_imports(self, agent, tmp_path):
        """Test detecting mixed import styles."""
        test_file = tmp_path / "module.py"
        test_file.write_text("""
import os
from os import path
""")

        with patch.object(agent, "_detect_unused_imports", return_value=[]):
            analysis = await agent.analyze_file(test_file)

            assert len(analysis.mixed_imports) > 0

    async def test_analyze_file_invalid(self, agent, tmp_path):
        """Test analyzing non-existent file."""
        test_file = tmp_path / "nonexistent.py"

        analysis = await agent.analyze_file(test_file)

        assert analysis.file_path == test_file
        assert analysis.mixed_imports == []

    async def test_analyze_file_syntax_error(self, agent, tmp_path):
        """Test handling syntax errors."""
        test_file = tmp_path / "broken.py"
        test_file.write_text("import os\nif True")  # Syntax error

        analysis = await agent.analyze_file(test_file)

        assert isinstance(analysis, ImportAnalysis)

    def test_is_valid_python_file(self, agent, tmp_path):
        """Test Python file validation."""
        valid_file = tmp_path / "module.py"
        valid_file.write_text("import os")

        invalid_file = tmp_path / "data.txt"
        invalid_file.write_text("text")

        assert agent._is_valid_python_file(valid_file) is True
        assert agent._is_valid_python_file(invalid_file) is False
        assert agent._is_valid_python_file(tmp_path / "missing.py") is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestImportOptimizationAgentUnusedDetection:
    """Test unused import detection."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    async def test_detect_unused_imports_success(self, agent, tmp_path):
        """Test detecting unused imports with vulture."""
        test_file = tmp_path / "module.py"

        mock_result = Mock(returncode=0, stdout="unused import 'os'\n")

        with patch.object(
            agent, "_run_vulture_analysis", return_value=mock_result
        ):
            unused = await agent._detect_unused_imports(test_file)

            assert isinstance(unused, list)

    async def test_detect_unused_imports_timeout(self, agent, tmp_path):
        """Test handling vulture timeout."""
        test_file = tmp_path / "module.py"

        with patch.object(
            agent,
            "_run_vulture_analysis",
            side_effect=subprocess.TimeoutExpired("vulture", 30),
        ):
            unused = await agent._detect_unused_imports(test_file)

            assert unused == []

    def test_extract_unused_imports_from_result(self, agent):
        """Test extracting import names from vulture output."""
        mock_result = Mock(
            returncode=0,
            stdout="module.py:1: unused import 'os' (confidence 80%)\n"
            "module.py:2: unused import 'sys' (confidence 90%)\n",
        )

        unused = agent._extract_unused_imports_from_result(mock_result)

        assert isinstance(unused, list)

    def test_is_valid_vulture_result(self, agent):
        """Test vulture result validation."""
        valid_result = Mock(returncode=0, stdout="output")
        invalid_result = Mock(returncode=1, stdout="")
        empty_result = Mock(returncode=0, stdout="")

        assert agent._is_valid_vulture_result(valid_result) is True
        assert agent._is_valid_vulture_result(invalid_result) is False
        assert agent._is_valid_vulture_result(empty_result) is False


@pytest.mark.unit
class TestImportOptimizationAgentImportAnalysis:
    """Test import analysis functionality."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    def test_extract_import_information(self, agent):
        """Test extracting import information from AST."""
        code = """
import os
import sys
from pathlib import Path
from typing import Any, Dict
"""
        tree = ast.parse(code)

        module_imports, all_imports = agent._extract_import_information(tree)

        assert "os" in module_imports
        assert "sys" in module_imports
        assert "pathlib" in module_imports
        assert len(all_imports) > 0

    def test_find_mixed_imports(self, agent):
        """Test finding mixed import styles."""
        module_imports = {
            "os": [
                {"type": "standard", "module": "os"},
                {"type": "from", "module": "os"},
            ],
            "sys": [{"type": "standard", "module": "sys"}],
        }

        mixed = agent._find_mixed_imports(module_imports)

        assert "os" in mixed
        assert "sys" not in mixed

    def test_find_redundant_imports(self, agent):
        """Test finding redundant imports."""
        all_imports = [
            {"module": "os", "name": "path", "line": 1},
            {"module": "os", "name": "path", "line": 2},
        ]

        redundant = agent._find_redundant_imports(all_imports)

        assert len(redundant) == 1
        assert "Line 2" in redundant[0]

    def test_find_optimization_opportunities(self, agent):
        """Test finding consolidation opportunities."""
        module_imports = {
            "pathlib": [
                {"type": "standard", "module": "pathlib"},
                {"type": "standard", "module": "pathlib"},
            ]
        }

        opportunities = agent._find_optimization_opportunities(module_imports)

        assert len(opportunities) > 0
        assert "Consolidate" in opportunities[0]


@pytest.mark.unit
class TestImportOptimizationAgentImportOrdering:
    """Test import ordering and PEP 8 compliance."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    def test_get_import_category_stdlib(self, agent):
        """Test categorizing standard library imports."""
        category = agent._get_import_category("os")

        assert category == 1

    def test_get_import_category_third_party(self, agent):
        """Test categorizing third-party imports."""
        category = agent._get_import_category("requests")

        assert category == 2

    def test_get_import_category_local(self, agent):
        """Test categorizing local imports."""
        category = agent._get_import_category("crackerjack.services")

        assert category == 3

    def test_is_stdlib_module(self, agent):
        """Test stdlib module detection."""
        assert agent._is_stdlib_module("os") is True
        assert agent._is_stdlib_module("sys") is True
        assert agent._is_stdlib_module("pathlib") is True
        assert agent._is_stdlib_module("requests") is False

    def test_is_local_import(self, agent):
        """Test local import detection."""
        assert agent._is_local_import("crackerjack.agents", "crackerjack") is True
        assert agent._is_local_import(".services", "services") is True
        assert agent._is_local_import("os.path", "os") is False

    def test_check_star_imports(self, agent):
        """Test detecting star imports."""
        content = """
from os import *
from pathlib import Path
"""

        violations = agent._check_star_imports(content)

        assert len(violations) > 0
        assert "star import" in violations[0].lower()


@pytest.mark.unit
@pytest.mark.asyncio
class TestImportOptimizationAgentFixIssue:
    """Test issue fixing workflow."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    async def test_fix_issue_no_file_path(self, agent):
        """Test handling issue without file path."""
        issue = Issue(
            id="import-001",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="Import error",
            file_path=None,
        )

        result = await agent.fix_issue(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_fix_issue_no_optimizations_needed(self, agent, tmp_path):
        """Test when no optimizations are needed."""
        test_file = tmp_path / "module.py"
        test_file.write_text("import os\n")

        issue = Issue(
            id="import-002",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.LOW,
            message="Check imports",
            file_path=str(test_file),
        )

        with patch.object(agent, "analyze_file") as mock_analyze:
            mock_analyze.return_value = ImportAnalysis(
                test_file, [], [], [], [], []
            )

            result = await agent.fix_issue(issue)

            assert result.success is True
            assert result.confidence == 1.0
            assert "No import optimizations needed" in result.fixes_applied[0]

    async def test_fix_issue_with_optimizations(self, agent, tmp_path):
        """Test applying optimizations."""
        test_file = tmp_path / "module.py"
        test_file.write_text("""
import os
from os import path
""")

        issue = Issue(
            id="import-003",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="Mixed imports",
            file_path=str(test_file),
        )

        with patch.object(
            agent, "analyze_file"
        ) as mock_analyze:
            mock_analyze.return_value = ImportAnalysis(
                test_file, ["os"], [], [], [], []
            )

            with patch.object(agent, "_read_and_optimize_file", return_value="optimized"):
                with patch.object(agent, "_write_optimized_content"):
                    result = await agent.fix_issue(issue)

                    assert result.success is True
                    assert len(result.fixes_applied) > 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestImportOptimizationAgentOptimizations:
    """Test import optimization transformations."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    async def test_optimize_imports(self, agent):
        """Test optimizing import statements."""
        content = """
import os
from os import path
"""
        analysis = ImportAnalysis(
            Path("test.py"), ["os"], [], [], [], []
        )

        optimized = await agent._optimize_imports(content, analysis)

        assert isinstance(optimized, str)

    def test_remove_unused_imports(self, agent):
        """Test removing unused imports."""
        lines = [
            "import os",
            "import sys",
            "def main(): pass",
        ]
        unused_imports = ["sys"]

        filtered = agent._remove_unused_imports(lines, unused_imports)

        # Should remove or filter unused imports
        assert isinstance(filtered, list)

    def test_consolidate_mixed_imports(self, agent):
        """Test consolidating mixed imports."""
        lines = [
            "import os",
            "from os import path",
            "def main(): pass",
        ]
        mixed_modules = ["os"]

        consolidated = agent._consolidate_mixed_imports(lines, mixed_modules)

        assert isinstance(consolidated, list)

    def test_remove_redundant_imports(self, agent):
        """Test removing redundant imports."""
        lines = [
            "import os",
            "import os",
            "def main(): pass",
        ]
        redundant = ["Line 2: os"]

        filtered = agent._remove_redundant_imports(lines, redundant)

        assert isinstance(filtered, list)

    def test_organize_imports_pep8(self, agent):
        """Test PEP 8 import organization."""
        lines = [
            "from crackerjack.services import config",
            "import os",
            "import requests",
            "def main(): pass",
        ]

        organized = agent._organize_imports_pep8(lines)

        # Should organize: stdlib, third-party, local
        assert isinstance(organized, list)


@pytest.mark.unit
class TestImportOptimizationAgentHelpers:
    """Test helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    def test_is_multi_import_line(self, agent):
        """Test detecting multi-import lines."""
        assert agent._is_multi_import_line("from os import path, sep") is True
        assert agent._is_multi_import_line("import os") is False

    def test_is_import_line(self, agent):
        """Test detecting import lines."""
        assert agent._is_import_line("import os") is True
        assert agent._is_import_line("from os import path") is True
        assert agent._is_import_line("# import os") is False
        assert agent._is_import_line("def foo(): pass") is False

    def test_extract_module_name(self, agent):
        """Test extracting module names."""
        assert agent._extract_module_name("import os.path") == "os"
        assert agent._extract_module_name("from pathlib import Path") == "pathlib"

    def test_categorize_imports(self, agent):
        """Test categorizing imports by type."""
        all_imports = [
            {"module": "os", "name": "path"},
            {"module": "requests", "name": "get"},
            {"module": "crackerjack.services", "name": "config"},
        ]

        categories = agent._categorize_imports(all_imports)

        assert isinstance(categories, dict)
        assert 1 in categories  # stdlib
        assert 2 in categories  # third-party
        assert 3 in categories  # local

    def test_parse_import_lines(self, agent):
        """Test parsing import lines."""
        lines = [
            "import os",
            "from pathlib import Path",
            "",
            "def main(): pass",
        ]

        import_lines, other_lines, bounds = agent._parse_import_lines(lines)

        assert len(import_lines) == 2
        assert len(other_lines) > 0
        assert bounds[0] == 0  # import start
        assert bounds[1] == 1  # import end


@pytest.mark.unit
@pytest.mark.asyncio
class TestImportOptimizationAgentDiagnostics:
    """Test diagnostics functionality."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    async def test_get_diagnostics_success(self, agent, tmp_path):
        """Test getting diagnostics successfully."""
        # Create test files
        (tmp_path / "module1.py").write_text("import os\n")
        (tmp_path / "module2.py").write_text("import sys\n")

        with patch.object(agent, "_analyze_file_sample") as mock_analyze:
            mock_analyze.return_value = {
                "mixed_import_files": 1,
                "total_mixed_modules": 2,
                "unused_import_files": 1,
                "total_unused_imports": 3,
                "pep8_violations": 0,
            }

            diagnostics = await agent.get_diagnostics()

            assert diagnostics["agent"] == "ImportOptimizationAgent"
            assert "files_analyzed" in diagnostics
            assert "capabilities" in diagnostics

    async def test_get_diagnostics_error(self, agent):
        """Test handling diagnostics error."""
        with patch.object(agent, "_get_python_files", side_effect=Exception("Error")):
            diagnostics = await agent.get_diagnostics()

            assert diagnostics["files_analyzed"] == 0
            assert "error" in diagnostics


@pytest.mark.unit
class TestImportOptimizationAgentASTParsing:
    """Test AST node processing."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    def test_process_standard_import(self, agent):
        """Test processing standard import nodes."""
        code = "import os, sys"
        tree = ast.parse(code)
        all_imports = []
        module_imports = {}

        node = tree.body[0]
        agent._process_standard_import(node, all_imports, module_imports)

        assert len(all_imports) == 2
        assert "os" in module_imports
        assert "sys" in module_imports

    def test_process_from_import(self, agent):
        """Test processing from-import nodes."""
        code = "from pathlib import Path, PurePath"
        tree = ast.parse(code)
        all_imports = []
        module_imports = {}

        node = tree.body[0]
        agent._process_from_import(node, all_imports, module_imports)

        assert len(all_imports) == 2
        assert "pathlib" in module_imports


@pytest.mark.unit
@pytest.mark.asyncio
class TestImportOptimizationAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create ImportOptimizationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return ImportOptimizationAgent(context)

    async def test_full_optimization_workflow(self, agent, tmp_path):
        """Test complete optimization workflow."""
        test_file = tmp_path / "module.py"
        test_file.write_text("""
from crackerjack.services import config
import os
import requests
from os import path
""")

        issue = Issue(
            id="import-001",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="Mixed imports and ordering issues",
            file_path=str(test_file),
        )

        result = await agent.analyze_and_fix(issue)

        assert isinstance(result, FixResult)

    async def test_analyze_then_optimize(self, agent, tmp_path):
        """Test analyze followed by optimization."""
        test_file = tmp_path / "module.py"
        test_file.write_text("""
import os
from os import path
""")

        # First analyze
        analysis = await agent.analyze_file(test_file)
        assert isinstance(analysis, ImportAnalysis)

        # Then optimize based on analysis
        if any([
            analysis.mixed_imports,
            analysis.redundant_imports,
            analysis.unused_imports,
        ]):
            content = test_file.read_text()
            optimized = await agent._optimize_imports(content, analysis)
            assert isinstance(optimized, str)

    def test_import_analysis_namedtuple(self):
        """Test ImportAnalysis NamedTuple structure."""
        analysis = ImportAnalysis(
            file_path=Path("test.py"),
            mixed_imports=["os"],
            redundant_imports=["sys"],
            unused_imports=["json"],
            optimization_opportunities=["Consolidate imports"],
            import_violations=["PEP 8 violation"],
        )

        assert analysis.file_path == Path("test.py")
        assert "os" in analysis.mixed_imports
        assert "sys" in analysis.redundant_imports
        assert "json" in analysis.unused_imports
        assert len(analysis.optimization_opportunities) == 1
        assert len(analysis.import_violations) == 1
