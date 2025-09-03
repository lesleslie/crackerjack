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
    filesystem = Mock()
    filesystem.read_file.return_value = "test content"
    filesystem.write_file.return_value = None
    filesystem.exists.return_value = True
    filesystem.mkdir.return_value = None
    return filesystem


@pytest.fixture
def mock_console():
    return Mock(spec=Console)


@pytest.fixture
def ai_assistant(mock_filesystem, mock_console):
    return ContextualAIAssistant(filesystem=mock_filesystem, console=mock_console)


@pytest.fixture
def sample_project_context():
    return ProjectContext(
        has_tests=True,
        test_coverage=35.0,
        lint_errors_count=15,
        security_issues=["B101: hardcoded_password", "B102: shell_injection"],
        outdated_dependencies=["requests == 1.0.0", "flask == 0.12.0"],
        last_commit_days=5,
        project_size="medium",
        main_languages=["python"],
        has_ci_cd=False,
        has_documentation=True,
        project_type="library",
    )


@pytest.fixture
def sample_recommendations():
    return [
        AIRecommendation(
            category="testing",
            priority="high",
            title="Improve Test Coverage",
            description="Current coverage is 35.0 %, below minimum requirement",
            action_command="python - m crackerjack - t",
            reasoning="Low coverage indicates untested code paths",
            confidence=0.85,
        ),
        AIRecommendation(
            category="security",
            priority="high",
            title="Address Security Issues",
            description="Found 2 security issues in dependencies",
            action_command="python - m crackerjack - - check - dependencies",
            reasoning="Security vulnerabilities can expose application",
            confidence=0.95,
        ),
    ]


class TestAIRecommendation:
    def test_ai_recommendation_creation(self):
        rec = AIRecommendation(
            category="testing",
            priority="high",
            title="Add Tests",
            description="No tests found",
            action_command="python - m crackerjack - t",
            reasoning="Tests improve reliability",
            confidence=0.9,
        )

        assert rec.category == "testing"
        assert rec.priority == "high"
        assert rec.title == "Add Tests"
        assert rec.description == "No tests found"
        assert rec.action_command == "python - m crackerjack - t"
        assert rec.reasoning == "Tests improve reliability"
        assert rec.confidence == 0.9

    def test_ai_recommendation_defaults(self):
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
    def test_project_context_creation(self):
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
    def test_init_with_filesystem_and_console(self, mock_filesystem, mock_console):
        assistant = ContextualAIAssistant(
            filesystem=mock_filesystem, console=mock_console
        )

        assert assistant.filesystem is mock_filesystem
        assert assistant.console is mock_console
        assert isinstance(assistant.project_root, Path)
        assert assistant.pyproject_path.name == "pyproject.toml"
        assert assistant.cache_file.parts[-2:] == (".crackerjack", "ai_context.json")

    def test_init_with_filesystem_only(self, mock_filesystem):
        assistant = ContextualAIAssistant(filesystem=mock_filesystem)

        assert assistant.filesystem is mock_filesystem
        assert isinstance(assistant.console, Console)

    @patch("crackerjack.services.contextual_ai_assistant.Path.cwd")
    def test_init_sets_correct_paths(self, mock_cwd, mock_filesystem):
        mock_project_root = Path("/ test / project")
        mock_cwd.return_value = mock_project_root

        assistant = ContextualAIAssistant(filesystem=mock_filesystem)

        assert assistant.project_root == mock_project_root
        assert assistant.pyproject_path == mock_project_root / "pyproject.toml"
        assert (
            assistant.cache_file
            == mock_project_root / ".crackerjack" / "ai_context.json"
        )


class TestGetContextualRecommendations:
    @patch.object(ContextualAIAssistant, "_analyze_project_context")
    @patch.object(ContextualAIAssistant, "_generate_recommendations")
    def test_get_contextual_recommendations_sorting(
        self, mock_generate, mock_analyze, ai_assistant
    ):
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

        assert len(result) == 4
        assert result[0].title == "High Priority 2"
        assert result[1].title == "High Priority"
        assert result[2].title == "Medium Priority"
        assert result[3].title == "Low Priority"

    @patch.object(ContextualAIAssistant, "_analyze_project_context")
    @patch.object(ContextualAIAssistant, "_generate_recommendations")
    def test_get_contextual_recommendations_max_limit(
        self, mock_generate, mock_analyze, ai_assistant
    ):
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
        mock_outdated.return_value = ["flask == 0.12"]

        context = ai_assistant._analyze_project_context()

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
        assert context.outdated_dependencies == ["flask == 0.12"]


class TestGenerateRecommendations:
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

        mock_testing.assert_called_once_with(sample_project_context)
        mock_quality.assert_called_once_with(sample_project_context)
        mock_security.assert_called_once_with(sample_project_context)
        mock_maintenance.assert_called_once_with(sample_project_context)
        mock_workflow.assert_called_once_with(sample_project_context)
        mock_docs.assert_called_once_with(sample_project_context)

        assert len(recommendations) == 6
        categories = [rec.category for rec in recommendations]
        assert "testing" in categories
        assert "code_quality" in categories
        assert "security" in categories
        assert "maintenance" in categories
        assert "workflow" in categories
        assert "documentation" in categories


class TestTestingRecommendations:
    def test_no_tests_recommendation(self, ai_assistant):
        context = ProjectContext(has_tests=False)

        recommendations = ai_assistant._get_testing_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "testing"
        assert rec.priority == "high"
        assert rec.title == "Add Test Suite"
        assert "No test directory found" in rec.description
        assert rec.action_command == "python - m crackerjack - t"
        assert rec.confidence == 0.9

    def test_low_coverage_recommendation(self, ai_assistant):
        context = ProjectContext(has_tests=True, test_coverage=35.0)

        recommendations = ai_assistant._get_testing_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "testing"
        assert rec.priority == "medium"
        assert rec.title == "Progress Toward 100 % Coverage"
        assert "35.0 %" in rec.description
        assert "40 % on the journey to 100 %" in rec.description
        assert rec.confidence == 0.85

    def test_adequate_coverage_no_recommendation(self, ai_assistant):
        context = ProjectContext(has_tests=True, test_coverage=75.0)

        recommendations = ai_assistant._get_testing_recommendations(context)

        assert len(recommendations) == 0


class TestCodeQualityRecommendations:
    def test_high_lint_errors_recommendation(self, ai_assistant):
        context = ProjectContext(lint_errors_count=25)

        recommendations = ai_assistant._get_code_quality_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "code_quality"
        assert rec.priority == "high"
        assert rec.title == "Fix Lint Errors"
        assert "25 lint errors" in rec.description
        assert rec.action_command == "python - m crackerjack - - ai - agent"
        assert rec.confidence == 0.95

    def test_medium_lint_errors_recommendation(self, ai_assistant):
        context = ProjectContext(lint_errors_count=10)

        recommendations = ai_assistant._get_code_quality_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "code_quality"
        assert rec.priority == "medium"
        assert rec.title == "Clean Up Code Style"
        assert "10 minor lint issues" in rec.description
        assert rec.action_command == "python - m crackerjack"
        assert rec.confidence == 0.8

    def test_low_lint_errors_no_recommendation(self, ai_assistant):
        context = ProjectContext(lint_errors_count=3)

        recommendations = ai_assistant._get_code_quality_recommendations(context)

        assert len(recommendations) == 0


class TestSecurityRecommendations:
    def test_security_issues_recommendation(self, ai_assistant):
        context = ProjectContext(security_issues=["B101", "B102", "B103"])

        recommendations = ai_assistant._get_security_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "security"
        assert rec.priority == "high"
        assert rec.title == "Address Security Vulnerabilities"
        assert "3 security issues" in rec.description
        assert rec.action_command == "python - m crackerjack - - check - dependencies"
        assert rec.confidence == 0.95

    def test_no_security_issues_no_recommendation(self, ai_assistant):
        context = ProjectContext(security_issues=[])

        recommendations = ai_assistant._get_security_recommendations(context)

        assert len(recommendations) == 0


class TestMaintenanceRecommendations:
    def test_many_outdated_dependencies_recommendation(self, ai_assistant):
        outdated_deps = [f"package{i}== 1.0.0" for i in range(15)]
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
        context = ProjectContext(outdated_dependencies=["package1 == 1.0.0"])

        recommendations = ai_assistant._get_maintenance_recommendations(context)

        assert len(recommendations) == 0


class TestWorkflowRecommendations:
    def test_no_cicd_medium_project_recommendation(self, ai_assistant):
        context = ProjectContext(has_ci_cd=False, project_size="medium")

        recommendations = ai_assistant._get_workflow_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "workflow"
        assert rec.priority == "medium"
        assert rec.title == "Set Up CI / CD Pipeline"
        assert "No CI / CD configuration found" in rec.description
        assert rec.confidence == 0.8

    def test_no_cicd_small_project_no_recommendation(self, ai_assistant):
        context = ProjectContext(has_ci_cd=False, project_size="small")

        recommendations = ai_assistant._get_workflow_recommendations(context)

        assert len(recommendations) == 0

    def test_has_cicd_no_recommendation(self, ai_assistant):
        context = ProjectContext(has_ci_cd=True, project_size="large")

        recommendations = ai_assistant._get_workflow_recommendations(context)

        assert len(recommendations) == 0


class TestDocumentationRecommendations:
    def test_library_no_docs_recommendation(self, ai_assistant):
        context = ProjectContext(has_documentation=False, project_type="library")

        recommendations = ai_assistant._get_documentation_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "documentation"
        assert rec.priority == "medium"
        assert rec.title == "Add Documentation"
        assert rec.confidence == 0.7

    def test_api_no_docs_recommendation(self, ai_assistant):
        context = ProjectContext(has_documentation=False, project_type="api")

        recommendations = ai_assistant._get_documentation_recommendations(context)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.category == "documentation"
        assert rec.title == "Add Documentation"

    def test_cli_no_docs_no_recommendation(self, ai_assistant):
        context = ProjectContext(has_documentation=False, project_type="cli")

        recommendations = ai_assistant._get_documentation_recommendations(context)

        assert len(recommendations) == 0


class TestHasTestDirectory:
    def test_has_test_directory_tests_folder(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_div.return_value = mock_path

            result = ai_assistant._has_test_directory()
            assert result is True

    def test_has_test_directory_test_folder(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(dirname):
                mock_path = Mock()

                mock_path.exists.return_value = dirname == "test"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_test_directory()
            assert result is True

    def test_has_test_directory_testing_folder(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(dirname):
                mock_path = Mock()

                mock_path.exists.return_value = dirname == "testing"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_test_directory()
            assert result is True

    def test_has_test_directory_none_exist(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_div.return_value = mock_path

            result = ai_assistant._has_test_directory()
            assert result is False


class TestGetCurrentCoverage:
    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_current_coverage_success(self, mock_run, mock_exists, ai_assistant):
        mock_exists.return_value = True

        coverage_data = {"totals": {"percent_covered": 85.5}}
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(coverage_data)
        mock_run.return_value = mock_result

        result = ai_assistant._get_current_coverage()

        assert result == 85.5
        mock_run.assert_called_once_with(
            ["uv", "run", "coverage", "report", "- - format = json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=ai_assistant.project_root,
        )

    @patch("pathlib.Path.exists")
    def test_get_current_coverage_no_coverage_file(self, mock_exists, ai_assistant):
        mock_exists.return_value = False

        result = ai_assistant._get_current_coverage()

        assert result == 0.0

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_current_coverage_command_fails(
        self, mock_run, mock_exists, ai_assistant
    ):
        mock_exists.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired("coverage", 10)

        result = ai_assistant._get_current_coverage()

        assert result == 0.0

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_current_coverage_invalid_json(
        self, mock_run, mock_exists, ai_assistant
    ):
        mock_exists.return_value = True

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid json"
        mock_run.return_value = mock_result

        result = ai_assistant._get_current_coverage()

        assert result == 0.0


class TestCountCurrentLintErrors:
    @patch("subprocess.run")
    def test_count_lint_errors_json_output(self, mock_run, ai_assistant):
        lint_data = [
            {"file": "test1.py", "message": "Error 1"},
            {"file": "test2.py", "message": "Error 2"},
            {"file": "test3.py", "message": "Error 3"},
        ]

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps(lint_data)
        mock_run.return_value = mock_result

        result = ai_assistant._count_current_lint_errors()

        assert result == 3

    @patch("subprocess.run")
    def test_count_lint_errors_text_output(self, mock_run, ai_assistant):
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "error1\nerror2\nerror3\nerror4\n"
        mock_run.return_value = mock_result

        result = ai_assistant._count_current_lint_errors()

        assert result == 4

    @patch("subprocess.run")
    def test_count_lint_errors_no_errors(self, mock_run, ai_assistant):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        result = ai_assistant._count_current_lint_errors()

        assert result == 0

    @patch("subprocess.run")
    def test_count_lint_errors_timeout(self, mock_run, ai_assistant):
        mock_run.side_effect = subprocess.TimeoutExpired("ruff", 30)

        result = ai_assistant._count_current_lint_errors()

        assert result == 0


class TestDetermineProjectSize:
    @patch("pathlib.Path.rglob")
    def test_determine_project_size_small(self, mock_rglob, ai_assistant):
        mock_rglob.return_value = [Path(f"file{i}.py") for i in range(5)]

        result = ai_assistant._determine_project_size()

        assert result == "small"

    @patch("pathlib.Path.rglob")
    def test_determine_project_size_medium(self, mock_rglob, ai_assistant):
        mock_rglob.return_value = [Path(f"file{i}.py") for i in range(25)]

        result = ai_assistant._determine_project_size()

        assert result == "medium"

    @patch("pathlib.Path.rglob")
    def test_determine_project_size_large(self, mock_rglob, ai_assistant):
        mock_rglob.return_value = [Path(f"file{i}.py") for i in range(75)]

        result = ai_assistant._determine_project_size()

        assert result == "large"

    @patch("pathlib.Path.rglob")
    def test_determine_project_size_exception(self, mock_rglob, ai_assistant):
        mock_rglob.side_effect = OSError("Permission denied")

        result = ai_assistant._determine_project_size()

        assert result == "small"


class TestDetectMainLanguages:
    def test_detect_python_only(self, ai_assistant):
        with (
            patch.object(Path, "__truediv__") as mock_div,
            patch.object(Path, "glob") as mock_glob,
        ):

            def path_side_effect(filename):
                mock_path = Mock()

                mock_path.exists.return_value = filename == "pyproject.toml"
                return mock_path

            mock_div.side_effect = path_side_effect
            mock_glob.return_value = []

            result = ai_assistant._detect_main_languages()
            assert result == ["python"]

    def test_detect_multiple_languages(self, ai_assistant):
        with (
            patch.object(Path, "__truediv__") as mock_div,
            patch.object(Path, "glob") as mock_glob,
        ):

            def path_side_effect(filename):
                mock_path = Mock()

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
        with (
            patch.object(Path, "__truediv__") as mock_div,
            patch.object(Path, "glob") as mock_glob,
        ):
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_div.return_value = mock_path
            mock_glob.return_value = []

            result = ai_assistant._detect_main_languages()
            assert result == ["python"]


class TestHasCICDConfig:
    def test_has_github_workflow(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(path_str):
                mock_path = Mock()

                mock_path.exists.return_value = path_str == ".github / workflows"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_ci_cd_config()
            assert result is True

    def test_has_gitlab_ci(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(path_str):
                mock_path = Mock()

                mock_path.exists.return_value = path_str == ".gitlab - ci.yml"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_ci_cd_config()
            assert result is True

    def test_no_cicd_config(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_div.return_value = mock_path

            result = ai_assistant._has_ci_cd_config()
            assert result is False


class TestHasDocumentation:
    def test_has_readme_md(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(path_str):
                mock_path = Mock()

                mock_path.exists.return_value = path_str == "README.md"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_documentation()
            assert result is True

    def test_has_docs_directory(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:

            def path_side_effect(path_str):
                mock_path = Mock()

                mock_path.exists.return_value = path_str == "docs"
                return mock_path

            mock_div.side_effect = path_side_effect

            result = ai_assistant._has_documentation()
            assert result is True

    def test_no_documentation(self, ai_assistant):
        with patch.object(Path, "__truediv__") as mock_div:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_div.return_value = mock_path

            result = ai_assistant._has_documentation()
            assert result is False


class TestQuickHelp:
    def test_quick_help_test_query(self, ai_assistant):
        result = ai_assistant.get_quick_help("how do I run tests?")

        assert "python - m crackerjack - t" in result
        assert "ai - agent" in result

    def test_quick_help_lint_query(self, ai_assistant):
        result = ai_assistant.get_quick_help("fix formatting issues")

        assert "python - m crackerjack" in result
        assert "ai - agent" in result

    def test_quick_help_security_query(self, ai_assistant):
        result = ai_assistant.get_quick_help("check for vulnerabilities")

        assert "- - check - dependencies" in result
        assert "bandit" in result

    def test_quick_help_coverage_query(self, ai_assistant):
        result = ai_assistant.get_quick_help("test coverage report")

        assert "python - m crackerjack - t" in result
        assert "uv run coverage html" in result

    def test_quick_help_publish_query(self, ai_assistant):
        result = ai_assistant.get_quick_help("how to release?")

        assert "python - m crackerjack - p patch" in result
        assert "python - m crackerjack - b patch" in result

    def test_quick_help_clean_query(self, ai_assistant):
        result = ai_assistant.get_quick_help("clean up code")

        assert "python - m crackerjack - x" in result
        assert "TODOs" in result

    def test_quick_help_dashboard_query(self, ai_assistant):
        result = ai_assistant.get_quick_help("start monitoring")

        assert "- - dashboard" in result
        assert "- - start - websocket - server" in result

    def test_quick_help_unknown_query(self, ai_assistant):
        result = ai_assistant.get_quick_help("unknown command")

        assert "python - m crackerjack - - help" in result
        assert "ai - agent" in result


class TestDisplayRecommendations:
    def test_display_no_recommendations(self, ai_assistant, mock_console):
        ai_assistant.display_recommendations([])

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Great job ! No immediate recommendations" in call_args

    def test_display_single_recommendation(self, ai_assistant, mock_console):
        rec = AIRecommendation(
            category="testing",
            priority="high",
            title="Add Tests",
            description="No tests found",
            action_command="python - m crackerjack - t",
            reasoning="Tests prevent bugs",
            confidence=0.9,
        )

        ai_assistant.display_recommendations([rec])

        assert mock_console.print.call_count >= 5

        printed_content = " ".join(
            str(call.args[0]) for call in mock_console.print.call_args_list
        )
        assert "Add Tests" in printed_content
        assert "high" in printed_content
        assert "python - m crackerjack - t" in printed_content
        assert "Tests prevent bugs" in printed_content

    def test_display_multiple_recommendations(
        self, ai_assistant, mock_console, sample_recommendations
    ):
        ai_assistant.display_recommendations(sample_recommendations)

        assert mock_console.print.call_count > len(sample_recommendations) * 3

        printed_content = " ".join(
            str(call.args[0]) for call in mock_console.print.call_args_list if call.args
        )
        assert "Improve Test Coverage" in printed_content
        assert "Address Security" in printed_content


class TestIntegrationWorkflows:
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.rglob")
    def test_full_recommendation_workflow(
        self, mock_rglob, mock_exists, mock_run, ai_assistant
    ):
        mock_exists.return_value = True
        mock_rglob.return_value = [Path(f"file{i}.py") for i in range(15)]

        coverage_result = Mock()
        coverage_result.returncode = 0
        coverage_result.stdout = json.dumps({"totals": {"percent_covered": 25.0}})

        lint_result = Mock()
        lint_result.returncode = 1
        lint_result.stdout = json.dumps([{"error": f"lint{i}"} for i in range(8)])

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

        recommendations = ai_assistant.get_contextual_recommendations()

        assert len(recommendations) > 0
        categories = [rec.category for rec in recommendations]
        assert "testing" in categories
        assert "code_quality" in categories

        priorities = [rec.priority for rec in recommendations]
        assert "high" in priorities or "medium" in priorities
