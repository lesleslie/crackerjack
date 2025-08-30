"""Strategic test file for contextual_ai_assistant.py - targeting 60-80% of 241 statements.

This file provides comprehensive test coverage for the ContextualAIAssistant module,
focusing on core AI assistant functionality, context analysis, and recommendation generation.

Target: 150-200 statements covered for ~3-4% overall coverage boost.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.services.contextual_ai_assistant import (
    AIRecommendation,
    ContextualAIAssistant,
    ProjectContext,
)


@pytest.fixture
def mock_filesystem():
    """Mock filesystem interface for testing."""
    filesystem = Mock()
    filesystem.read_file.return_value = "test content"
    filesystem.write_file.return_value = None
    filesystem.exists.return_value = True
    filesystem.mkdir.return_value = None
    return filesystem


@pytest.fixture
def mock_console():
    """Mock Rich console for testing."""
    return Mock(spec=Console)


@pytest.fixture
def ai_assistant(mock_filesystem, mock_console):
    """Create ContextualAIAssistant instance with mocked dependencies."""
    return ContextualAIAssistant(filesystem=mock_filesystem, console=mock_console)


@pytest.fixture
def sample_project_context():
    """Create sample project context for testing."""
    return ProjectContext(
        has_tests=True,
        test_coverage=35.0,
        lint_errors_count=15,
        security_issues=["B101: hardcoded_password", "B102: shell_injection"],
        outdated_dependencies=["requests==1.0.0", "flask==0.12.0"],
        last_commit_days=5,
        project_size="medium",
        main_languages=["python"],
        has_ci_cd=False,
        has_documentation=True,
        project_type="library",
    )


@pytest.fixture
def sample_recommendations():
    """Create sample AI recommendations for testing."""
    return [
        AIRecommendation(
            category="testing",
            priority="high",
            title="Improve Test Coverage",
            description="Current coverage is 35.0%, below minimum requirement",
            action_command="python -m crackerjack -t",
            reasoning="Low coverage indicates untested code paths",
            confidence=0.85,
        ),
        AIRecommendation(
            category="security",
            priority="high",
            title="Address Security Issues",
            description="Found 2 security issues in dependencies",
            action_command="python -m crackerjack --check-dependencies",
            reasoning="Security vulnerabilities can expose application",
            confidence=0.95,
        ),
    ]


class TestAIRecommendation:
    """Test AIRecommendation dataclass functionality."""

    def test_ai_recommendation_creation(self):
        """Test creating AIRecommendation with all fields."""
        rec = AIRecommendation(
            category="testing",
            priority="high",
            title="Add Tests",
            description="No tests found",
            action_command="python -m crackerjack -t",
            reasoning="Tests improve reliability",
            confidence=0.9,
        )

        assert rec.category == "testing"
        assert rec.priority == "high"
        assert rec.title == "Add Tests"
        assert rec.description == "No tests found"
        assert rec.action_command == "python -m crackerjack -t"
        assert rec.reasoning == "Tests improve reliability"
        assert rec.confidence == 0.9

    def test_ai_recommendation_defaults(self):
        """Test AIRecommendation with default values."""
        rec = AIRecommendation(
            category="code_quality",
            priority="medium",
            title="Refactor Code",
            description="Complex functions found",
        )

        assert rec.action_command is None
        assert rec.reasoning == ""
        assert rec.confidence == 0.0


class TestProjectContext:
    """Test ProjectContext dataclass functionality."""

    def test_project_context_creation(self):
        """Test creating ProjectContext with all fields."""
        context = ProjectContext(
            has_tests=True,
            test_coverage=75.5,
            lint_errors_count=3,
            security_issues=["B101"],
            outdated_dependencies=["requests"],
            last_commit_days=10,
            project_size="large",
            main_languages=["python", "javascript"],
            has_ci_cd=True,
            has_documentation=False,
            project_type="api",
        )

        assert context.has_tests is True
        assert context.test_coverage == 75.5
        assert context.lint_errors_count == 3
        assert context.security_issues == ["B101"]
        assert context.outdated_dependencies == ["requests"]
        assert context.last_commit_days == 10
        assert context.project_size == "large"
        assert context.main_languages == ["python", "javascript"]
        assert context.has_ci_cd is True
        assert context.has_documentation is False
        assert context.project_type == "api"

    def test_project_context_defaults(self):
        """Test ProjectContext with default values."""
        context = ProjectContext()

        assert context.has_tests is False
        assert context.test_coverage == 0.0
        assert context.lint_errors_count == 0
        assert context.security_issues == []
        assert context.outdated_dependencies == []
        assert context.last_commit_days == 0
        assert context.project_size == "small"
        assert context.main_languages == []
        assert context.has_ci_cd is False
        assert context.has_documentation is False
        assert context.project_type == "library"


class TestContextualAIAssistantInit:
    """Test ContextualAIAssistant initialization."""

    def test_init_with_filesystem_and_console(self, mock_filesystem, mock_console):
        """Test initialization with provided filesystem and console."""
        assistant = ContextualAIAssistant(
            filesystem=mock_filesystem, console=mock_console
        )

        assert assistant.filesystem is mock_filesystem
        assert assistant.console is mock_console
        assert isinstance(assistant.project_root, Path)
        assert assistant.pyproject_path.name == "pyproject.toml"
        assert assistant.cache_file.parts[-2:] == (".crackerjack", "ai_context.json")

    def test_init_with_filesystem_only(self, mock_filesystem):
        """Test initialization with only filesystem provided."""
        assistant = ContextualAIAssistant(filesystem=mock_filesystem)

        assert assistant.filesystem is mock_filesystem
        assert isinstance(assistant.console, Console)

    @patch("crackerjack.services.contextual_ai_assistant.Path.cwd")
    def test_init_sets_correct_paths(self, mock_cwd, mock_filesystem):
        """Test that initialization sets correct file paths."""
        mock_project_root = Path("/test/project")
        mock_cwd.return_value = mock_project_root

        assistant = ContextualAIAssistant(filesystem=mock_filesystem)

        assert assistant.project_root == mock_project_root
        assert assistant.pyproject_path == mock_project_root / "pyproject.toml"
        assert (
            assistant.cache_file
            == mock_project_root / ".crackerjack" / "ai_context.json"
        )


class TestGetContextualRecommendations:
    """Test get_contextual_recommendations method."""

    @patch.object(ContextualAIAssistant, "_analyze_project_context")
    @patch.object(ContextualAIAssistant, "_generate_recommendations")
    def test_get_contextual_recommendations_sorting(
        self, mock_generate, mock_analyze, ai_assistant
    ):
        """Test that recommendations are properly sorted by priority and confidence."""
        mock_context = ProjectContext()
        mock_analyze.return_value = mock_context

        recommendations = [
            AIRecommendation("test", "low", "Low Priority", "desc", confidence=0.9),
            AIRecommendation("test", "high", "High Priority", "desc", confidence=0.8),
            AIRecommendation(
                "test", "medium", "Medium Priority", "desc", confidence=0.7
            ),
            AIRecommendation("test", "high", "High Priority 2", "desc", confidence=0.9),
        ]
        mock_generate.return_value = recommendations

        result = ai_assistant.get_contextual_recommendations(max_recommendations=5)

        # Should be sorted by priority (high=3, medium=2, low=1) then confidence
        assert len(result) == 4
        assert result[0].title == "High Priority 2"  # high priority, 0.9 confidence
        assert result[1].title == "High Priority"  # high priority, 0.8 confidence
        assert result[2].title == "Medium Priority"  # medium priority, 0.7 confidence
        assert result[3].title == "Low Priority"  # low priority, 0.9 confidence

    @patch.object(ContextualAIAssistant, "_analyze_project_context")
    @patch.object(ContextualAIAssistant, "_generate_recommendations")
    def test_get_contextual_recommendations_max_limit(
        self, mock_generate, mock_analyze, ai_assistant
    ):
        """Test that max_recommendations parameter limits results."""
        mock_context = ProjectContext()
        mock_analyze.return_value = mock_context

        recommendations = [
            AIRecommendation("test", "high", f"Rec {i}", "desc", confidence=0.9)
            for i in range(10)
        ]
        mock_generate.return_value = recommendations

        result = ai_assistant.get_contextual_recommendations(max_recommendations=3)

        assert len(result) == 3
        mock_analyze.assert_called_once()
        mock_generate.assert_called_once_with(mock_context)


class TestAnalyzeProjectContext:
    """Test _analyze_project_context method."""

    @patch.object(ContextualAIAssistant, "_has_test_directory")
    @patch.object(ContextualAIAssistant, "_get_current_coverage")
    @patch.object(ContextualAIAssistant, "_count_current_lint_errors")
    @patch.object(ContextualAIAssistant, "_determine_project_size")
    @patch.object(ContextualAIAssistant, "_detect_main_languages")
    @patch.object(ContextualAIAssistant, "_has_ci_cd_config")
    @patch.object(ContextualAIAssistant, "_has_documentation")
    @patch.object(ContextualAIAssistant, "_determine_project_type")
    @patch.object(ContextualAIAssistant, "_days_since_last_commit")
    @patch.object(ContextualAIAssistant, "_detect_security_issues")
    @patch.object(ContextualAIAssistant, "_get_outdated_dependencies")
    def test_analyze_project_context_integration(
        self,
        mock_outdated,
        mock_security,
        mock_days,
        mock_type,
        mock_docs,
        mock_ci,
        mock_languages,
        mock_size,
        mock_lint,
        mock_coverage,
        mock_tests,
        ai_assistant,
    ):
        """Test that _analyze_project_context calls all analysis methods."""
        # Setup mocks
        mock_tests.return_value = True
        mock_coverage.return_value = 85.5
        mock_lint.return_value = 12
        mock_size.return_value = "large"
        mock_languages.return_value = ["python", "rust"]
        mock_ci.return_value = True
        mock_docs.return_value = False
        mock_type.return_value = "api"
        mock_days.return_value = 7
        mock_security.return_value = ["B101"]
        mock_outdated.return_value = ["flask==0.12"]

        context = ai_assistant._analyze_project_context()

        # Verify all methods were called
        mock_tests.assert_called_once()
        mock_coverage.assert_called_once()
        mock_lint.assert_called_once()
        mock_size.assert_called_once()
        mock_languages.assert_called_once()
        mock_ci.assert_called_once()
        mock_docs.assert_called_once()
        mock_type.assert_called_once()
        mock_days.assert_called_once()
        mock_security.assert_called_once()
        mock_outdated.assert_called_once()

        # Verify context was populated correctly
        assert context.has_tests is True
        assert context.test_coverage == 85.5
        assert context.lint_errors_count == 12
        assert context.project_size == "large"
        assert context.main_languages == ["python", "rust"]
        assert context.has_ci_cd is True
        assert context.has_documentation is False
        assert context.project_type == "api"
        assert context.last_commit_days == 7
        assert context.security_issues == ["B101"]
        assert context.outdated_dependencies == ["flask==0.12"]


class TestGenerateRecommendations:
    """Test _generate_recommendations method."""

    @patch.object(ContextualAIAssistant, "_get_testing_recommendations")
    @patch.object(ContextualAIAssistant, "_get_code_quality_recommendations")
    @patch.object(ContextualAIAssistant, "_get_security_recommendations")
    @patch.object(ContextualAIAssistant, "_get_maintenance_recommendations")
    @patch.object(ContextualAIAssistant, "_get_workflow_recommendations")
    @patch.object(ContextualAIAssistant, "_get_documentation_recommendations")
    def test_generate_recommendations_calls_all_categories(
        self,
        mock_docs,
        mock_workflow,
        mock_maintenance,
        mock_security,
        mock_quality,
        mock_testing,
        ai_assistant,
        sample_project_context,
    ):
        """Test that _generate_recommendations calls all category methods."""
        # Setup mocks to return specific recommendations
        mock_testing.return_value = [
            AIRecommendation("testing", "high", "Test 1", "desc")
        ]
        mock_quality.return_value = [
            AIRecommendation("code_quality", "medium", "Quality 1", "desc")
        ]
        mock_security.return_value = [
            AIRecommendation("security", "high", "Security 1", "desc")
        ]
        mock_maintenance.return_value = [
            AIRecommendation("maintenance", "low", "Maintenance 1", "desc")
        ]
        mock_workflow.return_value = [
            AIRecommendation("workflow", "medium", "Workflow 1", "desc")
        ]
        mock_docs.return_value = [
            AIRecommendation("documentation", "low", "Docs 1", "desc")
        ]

        recommendations = ai_assistant._generate_recommendations(sample_project_context)

        # Verify all methods were called with context
        mock_testing.assert_called_once_with(sample_project_context)
        mock_quality.assert_called_once_with(sample_project_context)
        mock_security.assert_called_once_with(sample_project_context)
        mock_maintenance.assert_called_once_with(sample_project_context)
        mock_workflow.assert_called_once_with(sample_project_context)
        mock_docs.assert_called_once_with(sample_project_context)

        # Verify all recommendations were aggregated
        assert len(recommendations) == 6
        categories = [rec.category for rec in recommendations]
        assert "testing" in categories
        assert "code_quality" in categories
        assert "security" in categories
        assert "maintenance" in categories
        assert "workflow" in categories
        assert "documentation" in categories


class TestTestingRecommendations:
    """Test _get_testing_recommendations method."""

    def test_no_tests_recommendation(self, ai_assistant):
        """Test recommendation when no tests are present."""
        context = ProjectContext(has_tests=False)

        recommendations = ai_assistant._get_testing_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "testing"
        assert rec.priority == "high"
        assert rec.title == "Add Test Suite"
        assert "No test directory found" in rec.description
        assert rec.action_command == "python -m crackerjack -t"
        assert rec.confidence == 0.9

    def test_low_coverage_recommendation(self, ai_assistant):
        """Test recommendation for low test coverage."""
        context = ProjectContext(has_tests=True, test_coverage=35.0)

        recommendations = ai_assistant._get_testing_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "testing"
        assert rec.priority == "medium"
        assert rec.title == "Progress Toward 100% Coverage"
        assert "35.0%" in rec.description
        assert "40% on the journey to 100%" in rec.description
        assert rec.confidence == 0.85

    def test_adequate_coverage_no_recommendation(self, ai_assistant):
        """Test no recommendation when coverage is adequate."""
        context = ProjectContext(has_tests=True, test_coverage=75.0)

        recommendations = ai_assistant._get_testing_recommendations(context)

        assert len(recommendations) == 0


class TestCodeQualityRecommendations:
    """Test _get_code_quality_recommendations method."""

    def test_high_lint_errors_recommendation(self, ai_assistant):
        """Test recommendation for high lint error count."""
        context = ProjectContext(lint_errors_count=25)

        recommendations = ai_assistant._get_code_quality_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "code_quality"
        assert rec.priority == "high"
        assert rec.title == "Fix Lint Errors"
        assert "25 lint errors" in rec.description
        assert rec.action_command == "python -m crackerjack --ai-agent"
        assert rec.confidence == 0.95

    def test_medium_lint_errors_recommendation(self, ai_assistant):
        """Test recommendation for medium lint error count."""
        context = ProjectContext(lint_errors_count=10)

        recommendations = ai_assistant._get_code_quality_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "code_quality"
        assert rec.priority == "medium"
        assert rec.title == "Clean Up Code Style"
        assert "10 minor lint issues" in rec.description
        assert rec.action_command == "python -m crackerjack"
        assert rec.confidence == 0.8

    def test_low_lint_errors_no_recommendation(self, ai_assistant):
        """Test no recommendation for low lint error count."""
        context = ProjectContext(lint_errors_count=3)

        recommendations = ai_assistant._get_code_quality_recommendations(context)

        assert len(recommendations) == 0


class TestSecurityRecommendations:
    """Test _get_security_recommendations method."""

    def test_security_issues_recommendation(self, ai_assistant):
        """Test recommendation when security issues are found."""
        context = ProjectContext(security_issues=["B101", "B102", "B103"])

        recommendations = ai_assistant._get_security_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "security"
        assert rec.priority == "high"
        assert rec.title == "Address Security Vulnerabilities"
        assert "3 security issues" in rec.description
        assert rec.action_command == "python -m crackerjack --check-dependencies"
        assert rec.confidence == 0.95

    def test_no_security_issues_no_recommendation(self, ai_assistant):
        """Test no recommendation when no security issues found."""
        context = ProjectContext(security_issues=[])

        recommendations = ai_assistant._get_security_recommendations(context)

        assert len(recommendations) == 0


class TestMaintenanceRecommendations:
    """Test _get_maintenance_recommendations method."""

    def test_many_outdated_dependencies_recommendation(self, ai_assistant):
        """Test recommendation for many outdated dependencies."""
        outdated_deps = [f"package{i}==1.0.0" for i in range(15)]
        context = ProjectContext(outdated_dependencies=outdated_deps)

        recommendations = ai_assistant._get_maintenance_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "maintenance"
        assert rec.priority == "medium"
        assert rec.title == "Update Dependencies"
        assert "15 outdated dependencies" in rec.description
        assert rec.confidence == 0.75

    def test_few_outdated_dependencies_no_recommendation(self, ai_assistant):
        """Test no recommendation for few outdated dependencies."""
        context = ProjectContext(outdated_dependencies=["package1==1.0.0"])

        recommendations = ai_assistant._get_maintenance_recommendations(context)

        assert len(recommendations) == 0


class TestWorkflowRecommendations:
    """Test _get_workflow_recommendations method."""

    def test_no_cicd_medium_project_recommendation(self, ai_assistant):
        """Test CI/CD recommendation for medium+ projects without CI/CD."""
        context = ProjectContext(has_ci_cd=False, project_size="medium")

        recommendations = ai_assistant._get_workflow_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "workflow"
        assert rec.priority == "medium"
        assert rec.title == "Set Up CI / CD Pipeline"
        assert "No CI/CD configuration found" in rec.description
        assert rec.confidence == 0.8

    def test_no_cicd_small_project_no_recommendation(self, ai_assistant):
        """Test no CI/CD recommendation for small projects."""
        context = ProjectContext(has_ci_cd=False, project_size="small")

        recommendations = ai_assistant._get_workflow_recommendations(context)

        assert len(recommendations) == 0

    def test_has_cicd_no_recommendation(self, ai_assistant):
        """Test no recommendation when CI/CD already exists."""
        context = ProjectContext(has_ci_cd=True, project_size="large")

        recommendations = ai_assistant._get_workflow_recommendations(context)

        assert len(recommendations) == 0


class TestDocumentationRecommendations:
    """Test _get_documentation_recommendations method."""

    def test_library_no_docs_recommendation(self, ai_assistant):
        """Test documentation recommendation for libraries without docs."""
        context = ProjectContext(has_documentation=False, project_type="library")

        recommendations = ai_assistant._get_documentation_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "documentation"
        assert rec.priority == "medium"
        assert rec.title == "Add Documentation"
        assert rec.confidence == 0.7

    def test_api_no_docs_recommendation(self, ai_assistant):
        """Test documentation recommendation for APIs without docs."""
        context = ProjectContext(has_documentation=False, project_type="api")

        recommendations = ai_assistant._get_documentation_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "documentation"
        assert rec.title == "Add Documentation"

    def test_cli_no_docs_no_recommendation(self, ai_assistant):
        """Test no documentation recommendation for CLI tools."""
        context = ProjectContext(has_documentation=False, project_type="cli")

        recommendations = ai_assistant._get_documentation_recommendations(context)

        assert len(recommendations) == 0


class TestHasTestDirectory:
    """Test _has_test_directory method."""

    def test_has_test_directory_tests_folder(self, ai_assistant):
        """Test detection of 'tests' directory."""
        with patch.object(Path, "__truediv__") as mock_div:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_div.return_value = mock_path

            result = ai_assistant._has_test_directory()
            assert result is True

    def test_has_test_directory_test_folder(self, ai_assistant):
        """Test detection of 'test' directory."""
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(dirname):
                mock_path = Mock()
                # Return True only for 'test' directory
                mock_path.exists.return_value = dirname == "test"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_test_directory()
            assert result is True

    def test_has_test_directory_testing_folder(self, ai_assistant):
        """Test detection of 'testing' directory."""
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(dirname):
                mock_path = Mock()
                # Return True only for 'testing' directory
                mock_path.exists.return_value = dirname == "testing"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_test_directory()
            assert result is True

    def test_has_test_directory_none_exist(self, ai_assistant):
        """Test when no test directories exist."""
        with patch.object(Path, "__truediv__") as mock_div:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_div.return_value = mock_path

            result = ai_assistant._has_test_directory()
            assert result is False


class TestGetCurrentCoverage:
    """Test _get_current_coverage method."""

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_current_coverage_success(self, mock_run, mock_exists, ai_assistant):
        """Test successful coverage retrieval."""
        mock_exists.return_value = True

        # Mock successful coverage command
        coverage_data = {"totals": {"percent_covered": 85.5}}
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(coverage_data)
        mock_run.return_value = mock_result

        result = ai_assistant._get_current_coverage()

        assert result == 85.5
        mock_run.assert_called_once_with(
            ["uv", "run", "coverage", "report", "--format=json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=ai_assistant.project_root,
        )

    @patch("pathlib.Path.exists")
    def test_get_current_coverage_no_coverage_file(self, mock_exists, ai_assistant):
        """Test when no .coverage file exists."""
        mock_exists.return_value = False

        result = ai_assistant._get_current_coverage()

        assert result == 0.0

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_current_coverage_command_fails(
        self, mock_run, mock_exists, ai_assistant
    ):
        """Test when coverage command fails."""
        mock_exists.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired("coverage", 10)

        result = ai_assistant._get_current_coverage()

        assert result == 0.0

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_current_coverage_invalid_json(
        self, mock_run, mock_exists, ai_assistant
    ):
        """Test handling of invalid JSON from coverage command."""
        mock_exists.return_value = True

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid json"
        mock_run.return_value = mock_result

        result = ai_assistant._get_current_coverage()

        assert result == 0.0


class TestCountCurrentLintErrors:
    """Test _count_current_lint_errors method."""

    @patch("subprocess.run")
    def test_count_lint_errors_json_output(self, mock_run, ai_assistant):
        """Test counting lint errors from JSON output."""
        lint_data = [
            {"file": "test1.py", "message": "Error 1"},
            {"file": "test2.py", "message": "Error 2"},
            {"file": "test3.py", "message": "Error 3"},
        ]

        mock_result = Mock()
        mock_result.returncode = 1  # ruff returns 1 when errors found
        mock_result.stdout = json.dumps(lint_data)
        mock_run.return_value = mock_result

        result = ai_assistant._count_current_lint_errors()

        assert result == 3

    @patch("subprocess.run")
    def test_count_lint_errors_text_output(self, mock_run, ai_assistant):
        """Test counting lint errors from text output."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "error1\nerror2\nerror3\nerror4\n"
        mock_run.return_value = mock_result

        result = ai_assistant._count_current_lint_errors()

        assert result == 4

    @patch("subprocess.run")
    def test_count_lint_errors_no_errors(self, mock_run, ai_assistant):
        """Test when no lint errors are found."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        result = ai_assistant._count_current_lint_errors()

        assert result == 0

    @patch("subprocess.run")
    def test_count_lint_errors_timeout(self, mock_run, ai_assistant):
        """Test timeout handling in lint error counting."""
        mock_run.side_effect = subprocess.TimeoutExpired("ruff", 30)

        result = ai_assistant._count_current_lint_errors()

        assert result == 0


class TestDetermineProjectSize:
    """Test _determine_project_size method."""

    @patch("pathlib.Path.rglob")
    def test_determine_project_size_small(self, mock_rglob, ai_assistant):
        """Test small project size detection."""
        # Mock 5 Python files
        mock_rglob.return_value = [Path(f"file{i}.py") for i in range(5)]

        result = ai_assistant._determine_project_size()

        assert result == "small"

    @patch("pathlib.Path.rglob")
    def test_determine_project_size_medium(self, mock_rglob, ai_assistant):
        """Test medium project size detection."""
        # Mock 25 Python files
        mock_rglob.return_value = [Path(f"file{i}.py") for i in range(25)]

        result = ai_assistant._determine_project_size()

        assert result == "medium"

    @patch("pathlib.Path.rglob")
    def test_determine_project_size_large(self, mock_rglob, ai_assistant):
        """Test large project size detection."""
        # Mock 75 Python files
        mock_rglob.return_value = [Path(f"file{i}.py") for i in range(75)]

        result = ai_assistant._determine_project_size()

        assert result == "large"

    @patch("pathlib.Path.rglob")
    def test_determine_project_size_exception(self, mock_rglob, ai_assistant):
        """Test exception handling in project size determination."""
        mock_rglob.side_effect = OSError("Permission denied")

        result = ai_assistant._determine_project_size()

        assert result == "small"


class TestDetectMainLanguages:
    """Test _detect_main_languages method."""

    def test_detect_python_only(self, ai_assistant):
        """Test detection of Python-only project."""
        with (
            patch.object(Path, "__truediv__") as mock_div,
            patch.object(Path, "glob") as mock_glob,
        ):

            def path_side_effect(filename):
                mock_path = Mock()
                # Return True only for pyproject.toml
                mock_path.exists.return_value = filename == "pyproject.toml"
                return mock_path

            mock_div.side_effect = path_side_effect
            mock_glob.return_value = []  # No TypeScript files

            result = ai_assistant._detect_main_languages()
            assert result == ["python"]

    def test_detect_multiple_languages(self, ai_assistant):
        """Test detection of multiple languages."""
        with (
            patch.object(Path, "__truediv__") as mock_div,
            patch.object(Path, "glob") as mock_glob,
        ):

            def path_side_effect(filename):
                mock_path = Mock()
                # Return True for multiple config files
                mock_path.exists.return_value = filename in [
                    "pyproject.toml",
                    "package.json",
                    "Cargo.toml",
                ]
                return mock_path

            mock_div.side_effect = path_side_effect
            mock_glob.return_value = [Path("app.ts"), Path("utils.ts")]

            result = ai_assistant._detect_main_languages()
            expected = ["python", "javascript", "typescript", "rust"]
            assert set(result) == set(expected)

    def test_detect_no_known_languages(self, ai_assistant):
        """Test fallback when no known languages detected."""
        with (
            patch.object(Path, "__truediv__") as mock_div,
            patch.object(Path, "glob") as mock_glob,
        ):
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_div.return_value = mock_path
            mock_glob.return_value = []

            result = ai_assistant._detect_main_languages()
            assert result == ["python"]  # Default fallback


class TestHasCICDConfig:
    """Test _has_ci_cd_config method."""

    def test_has_github_workflow(self, ai_assistant):
        """Test detection of GitHub Actions workflow."""
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(path_str):
                mock_path = Mock()
                # Return True only for .github/workflows
                mock_path.exists.return_value = path_str == ".github/workflows"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_ci_cd_config()
            assert result is True

    def test_has_gitlab_ci(self, ai_assistant):
        """Test detection of GitLab CI."""
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(path_str):
                mock_path = Mock()
                # Return True only for .gitlab-ci.yml
                mock_path.exists.return_value = path_str == ".gitlab-ci.yml"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_ci_cd_config()
            assert result is True

    def test_no_cicd_config(self, ai_assistant):
        """Test when no CI/CD configuration exists."""
        with patch.object(Path, "__truediv__") as mock_div:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_div.return_value = mock_path

            result = ai_assistant._has_ci_cd_config()
            assert result is False


class TestHasDocumentation:
    """Test _has_documentation method."""

    def test_has_readme_md(self, ai_assistant):
        """Test detection of README.md."""
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(path_str):
                mock_path = Mock()
                # Return True only for README.md
                mock_path.exists.return_value = path_str == "README.md"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_documentation()
            assert result is True

    def test_has_docs_directory(self, ai_assistant):
        """Test detection of docs directory."""
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(path_str):
                mock_path = Mock()
                # Return True only for docs directory
                mock_path.exists.return_value = path_str == "docs"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_documentation()
            assert result is True

    def test_no_documentation(self, ai_assistant):
        """Test when no documentation exists."""
        with patch.object(Path, "__truediv__") as mock_div:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_div.return_value = mock_path

            result = ai_assistant._has_documentation()
            assert result is False


class TestQuickHelp:
    """Test get_quick_help method."""

    def test_quick_help_test_query(self, ai_assistant):
        """Test quick help for test-related queries."""
        result = ai_assistant.get_quick_help("how do I run tests?")

        assert "python -m crackerjack -t" in result
        assert "ai-agent" in result

    def test_quick_help_lint_query(self, ai_assistant):
        """Test quick help for lint-related queries."""
        result = ai_assistant.get_quick_help("fix formatting issues")

        assert "python -m crackerjack" in result
        assert "ai-agent" in result

    def test_quick_help_security_query(self, ai_assistant):
        """Test quick help for security-related queries."""
        result = ai_assistant.get_quick_help("check for vulnerabilities")

        assert "--check-dependencies" in result
        assert "bandit" in result

    def test_quick_help_coverage_query(self, ai_assistant):
        """Test quick help for coverage-related queries."""
        result = ai_assistant.get_quick_help("test coverage report")

        assert "python -m crackerjack -t" in result
        assert "uv run coverage html" in result

    def test_quick_help_publish_query(self, ai_assistant):
        """Test quick help for publish-related queries."""
        result = ai_assistant.get_quick_help("how to release?")

        assert "python -m crackerjack -p patch" in result
        assert "python -m crackerjack -b patch" in result

    def test_quick_help_clean_query(self, ai_assistant):
        """Test quick help for clean-related queries."""
        result = ai_assistant.get_quick_help("clean up code")

        assert "python -m crackerjack -x" in result
        assert "TODOs" in result

    def test_quick_help_dashboard_query(self, ai_assistant):
        """Test quick help for dashboard-related queries."""
        result = ai_assistant.get_quick_help("start monitoring")

        assert "--dashboard" in result
        assert "--start-websocket-server" in result

    def test_quick_help_unknown_query(self, ai_assistant):
        """Test quick help for unknown queries."""
        result = ai_assistant.get_quick_help("unknown command")

        assert "python -m crackerjack --help" in result
        assert "ai-agent" in result


class TestDisplayRecommendations:
    """Test display_recommendations method."""

    def test_display_no_recommendations(self, ai_assistant, mock_console):
        """Test displaying when no recommendations exist."""
        ai_assistant.display_recommendations([])

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Great job! No immediate recommendations" in call_args

    def test_display_single_recommendation(self, ai_assistant, mock_console):
        """Test displaying a single recommendation."""
        rec = AIRecommendation(
            category="testing",
            priority="high",
            title="Add Tests",
            description="No tests found",
            action_command="python -m crackerjack -t",
            reasoning="Tests prevent bugs",
            confidence=0.9,
        )

        ai_assistant.display_recommendations([rec])

        # Should print header, recommendation, and confidence bar
        assert mock_console.print.call_count >= 5

        # Check that key information was printed
        printed_content = " ".join(
            str(call.args[0]) for call in mock_console.print.call_args_list
        )
        assert "Add Tests" in printed_content
        assert "high" in printed_content
        assert "python -m crackerjack -t" in printed_content
        assert "Tests prevent bugs" in printed_content

    def test_display_multiple_recommendations(
        self, ai_assistant, mock_console, sample_recommendations
    ):
        """Test displaying multiple recommendations."""
        ai_assistant.display_recommendations(sample_recommendations)

        # Should print header + multiple recommendations
        assert mock_console.print.call_count > len(sample_recommendations) * 3

        # Verify both recommendations appear in output
        printed_content = " ".join(
            str(call.args[0]) for call in mock_console.print.call_args_list if call.args
        )
        assert "Improve Test Coverage" in printed_content
        assert (
            "Address Security" in printed_content
        )  # Partial match for "Address Security Issues"


# Integration tests for complex workflows
class TestIntegrationWorkflows:
    """Integration tests for complete AI assistant workflows."""

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.rglob")
    def test_full_recommendation_workflow(
        self, mock_rglob, mock_exists, mock_run, ai_assistant
    ):
        """Test complete workflow from analysis to recommendations."""
        # Setup mocks for project analysis
        mock_exists.return_value = True
        mock_rglob.return_value = [
            Path(f"file{i}.py") for i in range(15)
        ]  # medium project

        # Mock coverage command
        coverage_result = Mock()
        coverage_result.returncode = 0
        coverage_result.stdout = json.dumps({"totals": {"percent_covered": 25.0}})

        # Mock lint command
        lint_result = Mock()
        lint_result.returncode = 1
        lint_result.stdout = json.dumps([{"error": f"lint{i}"} for i in range(8)])

        # Mock other commands to return empty/success
        default_result = Mock()
        default_result.returncode = 0
        default_result.stdout = ""

        def run_side_effect(cmd, **kwargs):
            if "coverage" in cmd:
                return coverage_result
            elif "ruff" in cmd:
                return lint_result
            else:
                return default_result

        mock_run.side_effect = run_side_effect

        # Get recommendations
        recommendations = ai_assistant.get_contextual_recommendations()

        # Should get recommendations for low coverage and lint errors
        assert len(recommendations) > 0
        categories = [rec.category for rec in recommendations]
        assert "testing" in categories
        assert "code_quality" in categories

        # Verify recommendations are properly prioritized
        priorities = [rec.priority for rec in recommendations]
        assert "high" in priorities or "medium" in priorities
