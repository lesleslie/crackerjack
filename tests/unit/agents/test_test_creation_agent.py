"""Unit tests for TestCreationAgent.

Tests coverage analysis, test generation, AST parsing,
and automated test creation for uncovered modules.
"""

import ast
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.test_creation_agent import TestCreationAgent


@pytest.mark.unit
class TestTestCreationAgentInitialization:
    """Test TestCreationAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test TestCreationAgent initializes correctly."""
        agent = TestCreationAgent(context)

        assert agent.context == context

    def test_get_supported_types(self, context):
        """Test agent supports test-related issue types."""
        agent = TestCreationAgent(context)

        supported = agent.get_supported_types()

        assert IssueType.TEST_FAILURE in supported
        assert IssueType.DEPENDENCY in supported
        assert IssueType.TEST_ORGANIZATION in supported
        assert IssueType.COVERAGE_IMPROVEMENT in supported
        assert len(supported) == 4


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentCanHandle:
    """Test confidence calculation for different issue types."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    async def test_can_handle_coverage_below_threshold(self, agent):
        """Test perfect confidence for coverage below threshold."""
        issue = Issue(
            id="test-001",
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Coverage below 80% threshold",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.95

    async def test_can_handle_missing_tests(self, agent):
        """Test perfect confidence for missing tests."""
        issue = Issue(
            id="test-002",
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.MEDIUM,
            message="Missing tests for critical module",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.95

    async def test_can_handle_generic_coverage(self, agent):
        """Test high confidence for generic coverage issues."""
        issue = Issue(
            id="test-003",
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.MEDIUM,
            message="Coverage improvement needed",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_test_organization_redundant(self, agent):
        """Test confidence for test organization issues."""
        issue = Issue(
            id="test-004",
            type=IssueType.TEST_ORGANIZATION,
            severity=Priority.LOW,
            message="Redundant tests detected",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_test_organization_generic(self, agent):
        """Test default test organization confidence."""
        issue = Issue(
            id="test-005",
            type=IssueType.TEST_ORGANIZATION,
            severity=Priority.LOW,
            message="Test organization issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.7

    async def test_can_handle_untested_functions(self, agent):
        """Test confidence for untested function messages."""
        issue = Issue(
            id="test-006",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="Function not tested",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.85

    async def test_can_handle_unsupported_type(self, agent):
        """Test zero confidence for unsupported types."""
        issue = Issue(
            id="test-007",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.0

    async def test_can_handle_file_path_indicators(self, agent, tmp_path):
        """Test confidence based on file path indicators."""
        test_file = tmp_path / "crackerjack" / "managers" / "test_manager.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def process(): pass")

        issue = Issue(
            id="test-008",
            type=IssueType.TEST_FAILURE,
            severity=Priority.MEDIUM,
            message="Test failure",
            file_path=str(test_file),
        )

        with patch.object(agent, "_has_corresponding_test", return_value=False):
            confidence = await agent.can_handle(issue)

            assert confidence == 0.8


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentAnalyzeAndFix:
    """Test test creation and fix application."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    async def test_analyze_and_fix_success(self, agent):
        """Test successful test creation."""
        issue = Issue(
            id="test-001",
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Missing tests",
        )

        with patch.object(
            agent,
            "_apply_test_creation_fixes",
            return_value=(["Created test file"], ["test_module.py"]),
        ):
            result = await agent.analyze_and_fix(issue)

            assert result.success is True
            assert len(result.fixes_applied) == 1
            assert len(result.files_modified) == 1

    async def test_analyze_and_fix_error_handling(self, agent):
        """Test error handling in analyze_and_fix."""
        issue = Issue(
            id="test-002",
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Missing tests",
        )

        with patch.object(
            agent,
            "_apply_test_creation_fixes",
            side_effect=Exception("Test creation failed"),
        ):
            result = await agent.analyze_and_fix(issue)

            assert result.success is False
            assert result.confidence == 0.0
            assert "Failed to create tests" in result.remaining_issues[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentCoverageAnalysis:
    """Test coverage analysis functionality."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    async def test_analyze_coverage_with_json(self, agent, tmp_path):
        """Test coverage analysis with existing coverage.json."""
        coverage_json = {
            "totals": {
                "percent_covered": 65.5,
                "num_statements": 1000,
                "covered_lines": 655,
            },
            "files": {
                str(tmp_path / "module1.py"): {
                    "summary": {"percent_covered": 50}
                },
                str(tmp_path / "module2.py"): {
                    "summary": {"percent_covered": 75}
                },
            },
        }

        json_path = tmp_path / "coverage.json"
        json_path.write_text(json.dumps(coverage_json))

        agent.context.get_file_content = Mock(return_value=json.dumps(coverage_json))

        result = await agent._analyze_coverage()

        assert result["below_threshold"] is True
        assert result["current_coverage"] == 0.655
        assert len(result["uncovered_modules"]) > 0

    async def test_analyze_coverage_no_existing_data(self, agent):
        """Test coverage analysis with no existing data."""
        with patch.object(agent, "_run_coverage_command", return_value=(1, "", "Error")):
            result = await agent._analyze_coverage()

            assert result["below_threshold"] is True
            assert result["current_coverage"] == 0.0

    async def test_parse_coverage_json(self, agent, tmp_path):
        """Test parsing coverage JSON data."""
        coverage_json = {
            "totals": {
                "percent_covered": 75.0,
                "num_statements": 500,
                "covered_lines": 375,
            },
            "files": {
                str(tmp_path / "low_coverage.py"): {
                    "summary": {"percent_covered": 60}
                }
            },
        }

        result = agent._parse_coverage_json(coverage_json)

        assert result["below_threshold"] is True
        assert result["current_coverage"] == 0.75
        assert result["missing_lines"] == 125

    async def test_estimate_current_coverage(self, agent, tmp_path):
        """Test coverage estimation from file counts."""
        source_dir = tmp_path / "crackerjack"
        source_dir.mkdir()
        (source_dir / "module1.py").write_text("def foo(): pass")
        (source_dir / "module2.py").write_text("def bar(): pass")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module1.py").write_text("def test_foo(): pass")

        coverage = await agent._estimate_current_coverage()

        assert isinstance(coverage, float)
        assert 0.0 <= coverage <= 0.9


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentModuleDiscovery:
    """Test uncovered module discovery."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    async def test_find_uncovered_modules_enhanced(self, agent, tmp_path):
        """Test finding uncovered modules with priority scoring."""
        package_dir = tmp_path / "crackerjack" / "services"
        package_dir.mkdir(parents=True)

        module_file = package_dir / "config_service.py"
        module_file.write_text("""
def load_config(): pass
def save_config(): pass

class ConfigManager:
    def get(self): pass
    def set(self): pass
""")

        agent.context.get_file_content = Mock(return_value=module_file.read_text())

        with patch.object(agent, "_has_corresponding_test", return_value=False):
            uncovered = await agent._find_uncovered_modules_enhanced()

            assert len(uncovered) > 0
            assert all("priority_score" in m for m in uncovered)
            assert all("function_count" in m for m in uncovered)

    async def test_analyze_module_priority(self, agent, tmp_path):
        """Test module priority scoring."""
        module_file = tmp_path / "crackerjack" / "managers" / "hook_manager.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text("""
def public_function(): pass
def _private_function(): pass

class HookManager:
    def execute(self): pass
    def _internal(self): pass
""")

        agent.context.get_file_content = Mock(return_value=module_file.read_text())

        priority_info = await agent._analyze_module_priority(module_file)

        assert priority_info["priority_score"] > 0
        assert priority_info["function_count"] == 2
        assert priority_info["class_count"] == 1
        assert priority_info["public_function_count"] == 1
        assert priority_info["category"] == "manager"

    def test_categorize_module(self, agent):
        """Test module categorization."""
        assert agent._categorize_module("crackerjack/managers/test.py") == "manager"
        assert agent._categorize_module("crackerjack/services/test.py") == "service"
        assert agent._categorize_module("crackerjack/core/test.py") == "core"
        assert agent._categorize_module("crackerjack/agents/test.py") == "agent"
        assert agent._categorize_module("crackerjack/models/test.py") == "model"
        assert agent._categorize_module("crackerjack/utils/test.py") == "utility"


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentFunctionDiscovery:
    """Test untested function discovery."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    async def test_extract_functions_from_file(self, agent, tmp_path):
        """Test extracting functions from Python file."""
        test_file = tmp_path / "module.py"
        test_file.write_text("""
def public_function(arg1, arg2):
    pass

def _private_function():
    pass

async def async_function():
    pass

def test_something():
    pass
""")

        agent.context.get_file_content = Mock(return_value=test_file.read_text())

        functions = await agent._extract_functions_from_file(test_file)

        # Should find public and async functions, but not private or test functions
        function_names = [f["name"] for f in functions]
        assert "public_function" in function_names
        assert "async_function" in function_names
        assert "_private_function" not in function_names
        assert "test_something" not in function_names

    async def test_extract_classes_from_file(self, agent, tmp_path):
        """Test extracting classes from Python file."""
        test_file = tmp_path / "module.py"
        test_file.write_text("""
class PublicClass:
    def method1(self): pass
    def method2(self): pass
    def _private_method(self): pass

class _PrivateClass:
    pass
""")

        agent.context.get_file_content = Mock(return_value=test_file.read_text())

        classes = await agent._extract_classes_from_file(test_file)

        # Should find public class with public methods
        assert len(classes) == 1
        assert classes[0]["name"] == "PublicClass"
        assert "method1" in classes[0]["methods"]
        assert "method2" in classes[0]["methods"]
        assert "_private_method" not in classes[0]["methods"]

    async def test_analyze_function_testability(self, agent, tmp_path):
        """Test function testability analysis."""
        func_info = {
            "name": "process_data",
            "args": ["self", "data", "options", "config", "flags"],
            "is_async": True,
        }

        test_file = tmp_path / "crackerjack" / "services" / "processor.py"
        test_file.parent.mkdir(parents=True)

        result = await agent._analyze_function_testability(func_info, test_file)

        assert result["testing_priority"] > 0
        assert result["complexity"] == "complex"
        assert result["test_strategy"] == "async"

    async def test_find_untested_functions_in_file(self, agent, tmp_path):
        """Test finding untested functions in a file."""
        test_file = tmp_path / "module.py"
        test_file.write_text("""
def tested_function(): pass
def untested_function(): pass
""")

        agent.context.get_file_content = Mock(return_value=test_file.read_text())

        with patch.object(
            agent, "_function_has_test", side_effect=[True, False]
        ):
            untested = await agent._find_untested_functions_in_file(test_file)

            # Should find only untested_function
            assert len(untested) == 1


@pytest.mark.unit
class TestTestCreationAgentHelpers:
    """Test helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    def test_has_corresponding_test(self, agent, tmp_path):
        """Test checking for corresponding test files."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module.py").write_text("test content")

        module_path = str(tmp_path / "crackerjack" / "module.py")

        # Should find test file
        assert agent._has_corresponding_test(module_path) is True

    def test_has_corresponding_test_not_found(self, agent, tmp_path):
        """Test when no corresponding test exists."""
        module_path = str(tmp_path / "crackerjack" / "no_test_module.py")

        assert agent._has_corresponding_test(module_path) is False

    def test_should_skip_module_for_coverage(self, agent, tmp_path):
        """Test module skipping logic."""
        assert agent._should_skip_module_for_coverage(tmp_path / "test_module.py") is True
        assert agent._should_skip_module_for_coverage(tmp_path / "__init__.py") is True
        assert agent._should_skip_module_for_coverage(tmp_path / "module.py") is False

    def test_should_skip_file_for_testing(self, agent, tmp_path):
        """Test file skipping for testing."""
        assert agent._should_skip_file_for_testing(tmp_path / "test_module.py") is True
        assert agent._should_skip_file_for_testing(tmp_path / "module.py") is False

    def test_calculate_confidence_no_fixes(self, agent):
        """Test confidence calculation with no fixes."""
        confidence = agent._calculate_confidence(False, [], [])

        assert confidence == 0.0

    def test_calculate_confidence_with_fixes(self, agent):
        """Test confidence calculation with various fix types."""
        fixes = [
            "Created test file for module",
            "Added test for function process_data",
            "Coverage increased to 85%",
        ]
        files = ["test_module1.py", "test_module2.py"]

        confidence = agent._calculate_confidence(True, fixes, files)

        assert confidence > 0.5
        assert confidence <= 0.95

    def test_generate_recommendations_success(self, agent):
        """Test generating recommendations on success."""
        recommendations = agent._generate_recommendations(True)

        assert "Generated comprehensive test suite" in recommendations[0]
        assert any("pytest" in r for r in recommendations)

    def test_generate_recommendations_failure(self, agent):
        """Test generating recommendations on failure."""
        recommendations = agent._generate_recommendations(False)

        assert "No test creation opportunities" in recommendations[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentTestGeneration:
    """Test test content generation."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    async def test_generate_test_file_path(self, agent, tmp_path):
        """Test generating test file path."""
        source_file = tmp_path / "crackerjack" / "services" / "config.py"
        source_file.parent.mkdir(parents=True)

        test_path = await agent._generate_test_file_path(source_file)

        assert test_path.name == "test_config.py"
        assert "tests" in str(test_path)

    def test_get_module_import_path(self, agent, tmp_path):
        """Test getting module import path."""
        module_file = tmp_path / "crackerjack" / "services" / "config.py"

        import_path = agent._get_module_import_path(module_file)

        assert import_path == "crackerjack.services.config"

    def test_generate_smart_default_args(self, agent):
        """Test generating smart default arguments."""
        # Path argument
        assert 'Path("test_file.txt")' in agent._generate_smart_default_args(["file_path"])

        # String argument
        assert '"test_name"' in agent._generate_smart_default_args(["name"])

        # Numeric argument
        assert "10" in agent._generate_smart_default_args(["count"])

        # Boolean argument
        assert "True" in agent._generate_smart_default_args(["is_enabled"])

    def test_generate_invalid_args(self, agent):
        """Test generating invalid arguments for error testing."""
        args = agent._generate_invalid_args(["arg1", "arg2", "arg3"])

        assert args == "None, None, None"

    def test_generate_edge_case_args_empty(self, agent):
        """Test generating empty edge case arguments."""
        args = agent._generate_edge_case_args(["name", "data", "config"], "empty")

        assert '""' in args
        assert "[]" in args or "{}" in args

    def test_generate_edge_case_args_boundary(self, agent):
        """Test generating boundary edge case arguments."""
        args = agent._generate_edge_case_args(["count", "name"], "boundary")

        assert "0" in args
        assert '"x" * 1000' in args


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentCoverageGaps:
    """Test coverage gap identification."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    async def test_identify_coverage_gaps(self, agent, tmp_path):
        """Test identifying coverage gaps."""
        package_dir = tmp_path / "crackerjack"
        package_dir.mkdir()
        module_file = package_dir / "module.py"
        module_file.write_text("def process(): pass")

        with patch.object(
            agent,
            "_analyze_existing_test_coverage",
            return_value={
                "source_file": "module.py",
                "has_gaps": True,
                "missing_test_types": ["basic", "edge_cases"],
            },
        ):
            gaps = await agent._identify_coverage_gaps()

            assert isinstance(gaps, list)

    async def test_analyze_existing_test_coverage_no_test(self, agent, tmp_path):
        """Test analyzing coverage when no test file exists."""
        module_file = tmp_path / "crackerjack" / "module.py"
        module_file.parent.mkdir(parents=True)

        with patch.object(
            agent,
            "_generate_test_file_path",
            return_value=tmp_path / "tests" / "test_module.py",
        ):
            coverage_info = await agent._analyze_existing_test_coverage(module_file)

            assert coverage_info["has_gaps"] is True
            assert "basic" in coverage_info["missing_test_types"]

    async def test_analyze_existing_test_coverage_with_test(self, agent, tmp_path):
        """Test analyzing coverage with existing test file."""
        module_file = tmp_path / "crackerjack" / "module.py"
        test_file = tmp_path / "tests" / "test_module.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
def test_basic(): pass
@pytest.mark.parametrize("x", [1, 2])
def test_parametrized(x): pass
""")

        agent.context.get_file_content = Mock(return_value=test_file.read_text())

        with patch.object(agent, "_generate_test_file_path", return_value=test_file):
            coverage_info = await agent._analyze_existing_test_coverage(module_file)

            assert coverage_info["has_gaps"] is True
            assert "error_handling" in coverage_info["missing_test_types"]
            assert coverage_info["coverage_score"] > 0

    def test_calculate_improvement_potential(self, agent):
        """Test calculating improvement potential."""
        # High potential
        potential = agent._calculate_improvement_potential(10, 20)
        assert potential["priority"] == "high"
        assert potential["percentage_points"] > 15

        # Medium potential
        potential = agent._calculate_improvement_potential(3, 5)
        assert potential["priority"] == "medium"

        # Low potential
        potential = agent._calculate_improvement_potential(1, 0)
        assert potential["priority"] == "low"


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentASTOperations:
    """Test AST parsing and analysis."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    def test_parse_function_nodes(self, agent):
        """Test parsing function nodes from AST."""
        code = """
def regular_function(arg1, arg2):
    pass

async def async_function():
    pass

def _private_function():
    pass
"""
        tree = ast.parse(code)
        functions = agent._parse_function_nodes(tree)

        # Should find public functions only
        assert len(functions) == 2
        assert any(f["name"] == "regular_function" for f in functions)
        assert any(f["name"] == "async_function" for f in functions)
        assert any(f["is_async"] for f in functions)

    def test_is_valid_function_node(self, agent):
        """Test function node validation."""
        # Valid public function
        code = "def public_func(): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert agent._is_valid_function_node(func_node) is True

        # Invalid private function
        code = "def _private_func(): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert agent._is_valid_function_node(func_node) is False

        # Invalid test function
        code = "def test_something(): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert agent._is_valid_function_node(func_node) is False

    def test_create_function_info(self, agent):
        """Test creating function info from AST node."""
        code = """
async def process_data(input_data, config):
    \"\"\"Process data with config.\"\"\"
    return result
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        func_info = agent._create_function_info(func_node)

        assert func_info["name"] == "process_data"
        assert func_info["args"] == ["input_data", "config"]
        assert func_info["is_async"] is True
        assert func_info["docstring"] == "Process data with config."

    def test_get_function_signature(self, agent):
        """Test getting function signature."""
        code = "async def process(data, options): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]

        signature = agent._get_function_signature(func_node)

        assert "async" in signature
        assert "process" in signature
        assert "data, options" in signature


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestCreationAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestCreationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestCreationAgent(context)

    async def test_full_test_creation_workflow(self, agent, tmp_path):
        """Test complete test creation workflow."""
        # Create source module
        module_file = tmp_path / "crackerjack" / "services" / "config.py"
        module_file.parent.mkdir(parents=True)
        module_file.write_text("""
def load_config(path):
    pass

def save_config(path, data):
    pass
""")

        issue = Issue(
            id="test-001",
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Missing tests for config service",
            file_path=str(module_file),
        )

        agent.context.get_file_content = Mock(return_value=module_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        with patch.object(agent, "_has_corresponding_test", return_value=False):
            with patch.object(agent, "_analyze_coverage", return_value={
                "below_threshold": True,
                "current_coverage": 0.5,
                "uncovered_modules": [],
            }):
                result = await agent.analyze_and_fix(issue)

                # Should attempt test creation
                assert isinstance(result, FixResult)

    def test_comprehensive_pattern_detection(self, agent):
        """Test comprehensive pattern detection methods."""
        # Test all pattern detection methods
        assert agent._is_path_arg("file_path") is True
        assert agent._is_url_arg("api_url") is True
        assert agent._is_email_arg("user_email") is True
        assert agent._is_id_arg("user_id") is True
        assert agent._is_name_arg("username") is True
        assert agent._is_numeric_arg("count") is True
        assert agent._is_boolean_arg("is_enabled") is True
        assert agent._is_text_arg("text_content") is True
        assert agent._is_list_arg("items") is True
        assert agent._is_dict_arg("config") is True
