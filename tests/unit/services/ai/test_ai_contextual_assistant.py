"""Unit tests for ``crackerjack.services.ai.contextual_ai_assistant``.

The ``ContextualAIAssistant`` shells out to ``git``/``uv``/``bandit``/``ruff``
during project analysis. All subprocess calls are mocked at the
``subprocess.run`` boundary to keep these tests hermetic.

Focus: each public/private recommendation branch, the display routine, and
the quick-help mapping.
"""

from __future__ import annotations

import json
import subprocess
import time
import tomllib
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.services.ai.contextual_ai_assistant import (
    AIRecommendation,
    ContextualAIAssistant,
    ProjectContext,
)
from crackerjack.models.protocols import FileSystemInterface


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FSStub:
    """Minimal FileSystemInterface stub: only the methods used by the assistant
    (which currently is none — it relies on ``Path`` and ``subprocess``)."""

    def read_file(self, path: object) -> str:  # pragma: no cover
        return ""

    def write_file(self, path: object, content: str) -> None:  # pragma: no cover
        pass

    def exists(self, path: object) -> bool:  # pragma: no cover
        return False

    def mkdir(self, path: object, parents: bool = False) -> None:  # pragma: no cover
        pass


@pytest.fixture
def fs() -> FileSystemInterface:
    return _FSStub()  # type: ignore[return-value]


@pytest.fixture
def console() -> Console:
    return Console(file=MagicMock(), force_terminal=False, no_color=True, width=200)


@pytest.fixture
def assistant(fs: FileSystemInterface, console: Console) -> ContextualAIAssistant:
    return ContextualAIAssistant(filesystem=fs, console=console)


# ---------------------------------------------------------------------------
# Recommendation generation — direct unit tests
# ---------------------------------------------------------------------------


class TestGetTestingRecommendations:
    def test_no_tests_recommends_suite(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(has_tests=False)
        recs = assistant._get_testing_recommendations(ctx)
        assert len(recs) == 1
        rec = recs[0]
        assert rec.category == "testing"
        assert rec.priority == "high"
        assert "Add Test Suite" in rec.title
        assert rec.action_command == "python -m crackerjack -t"
        assert rec.confidence > 0.8

    def test_low_coverage_recommends_progress(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(has_tests=True, test_coverage=42.0)
        recs = assistant._get_testing_recommendations(ctx)
        assert len(recs) == 1
        assert recs[0].category == "testing"
        assert "Progress" in recs[0].title
        assert "42.0%" in recs[0].description
        # Next milestone > 42 -> 50
        assert "50%" in recs[0].description

    def test_high_coverage_no_recommendation(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(has_tests=True, test_coverage=85.0)
        assert assistant._get_testing_recommendations(ctx) == []

    def test_coverage_above_100_uses_default_milestone(
        self, assistant: ContextualAIAssistant
    ) -> None:
        # Edge case: coverage 100+ -> next(...) falls back to 100.
        ctx = ProjectContext(has_tests=True, test_coverage=100.0)
        recs = assistant._get_testing_recommendations(ctx)
        # 100 is not < 75, so no recommendation.
        assert recs == []


class TestGetCodeQualityRecommendations:
    def test_high_lint_errors_high_priority(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(lint_errors_count=42)
        recs = assistant._get_code_quality_recommendations(ctx)
        assert len(recs) == 1
        assert recs[0].priority == "high"
        assert "42" in recs[0].description
        assert recs[0].action_command == "python -m crackerjack --ai-fix"

    def test_medium_lint_errors_medium_priority(
        self, assistant: ContextualAIAssistant
    ) -> None:
        ctx = ProjectContext(lint_errors_count=10)
        recs = assistant._get_code_quality_recommendations(ctx)
        assert len(recs) == 1
        assert recs[0].priority == "medium"
        assert recs[0].action_command == "python -m crackerjack"

    def test_low_lint_errors_no_recommendation(
        self, assistant: ContextualAIAssistant
    ) -> None:
        ctx = ProjectContext(lint_errors_count=3)
        assert assistant._get_code_quality_recommendations(ctx) == []


class TestGetSecurityRecommendations:
    def test_with_issues(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(security_issues=["X1", "X2", "X3"])
        recs = assistant._get_security_recommendations(ctx)
        assert len(recs) == 1
        assert recs[0].priority == "high"
        assert "3" in recs[0].description

    def test_without_issues(self, assistant: ContextualAIAssistant) -> None:
        assert assistant._get_security_recommendations(ProjectContext()) == []


class TestGetMaintenanceRecommendations:
    def test_many_outdated_deps(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(outdated_dependencies=[f"dep{i}" for i in range(15)])
        recs = assistant._get_maintenance_recommendations(ctx)
        assert len(recs) == 1
        assert "15" in recs[0].description
        assert recs[0].action_command == "python -m crackerjack --check-dependencies"

    def test_few_outdated_deps(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(outdated_dependencies=["a", "b"])
        assert assistant._get_maintenance_recommendations(ctx) == []


class TestGetWorkflowRecommendations:
    def test_no_cicd_medium_project(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(has_ci_cd=False, project_size="medium")
        recs = assistant._get_workflow_recommendations(ctx)
        assert len(recs) == 1
        assert "CI" in recs[0].title

    def test_no_cicd_small_project_no_recommendation(
        self, assistant: ContextualAIAssistant
    ) -> None:
        ctx = ProjectContext(has_ci_cd=False, project_size="small")
        assert assistant._get_workflow_recommendations(ctx) == []

    def test_with_cicd_no_recommendation(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(has_ci_cd=True, project_size="large")
        assert assistant._get_workflow_recommendations(ctx) == []


class TestGetDocumentationRecommendations:
    def test_library_no_docs(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(project_type="library", has_documentation=False)
        recs = assistant._get_documentation_recommendations(ctx)
        assert len(recs) == 1
        assert "Documentation" in recs[0].title

    def test_api_no_docs(self, assistant: ContextualAIAssistant) -> None:
        ctx = ProjectContext(project_type="api", has_documentation=False)
        assert len(assistant._get_documentation_recommendations(ctx)) == 1

    def test_application_no_docs_no_recommendation(
        self, assistant: ContextualAIAssistant
    ) -> None:
        ctx = ProjectContext(project_type="application", has_documentation=False)
        assert assistant._get_documentation_recommendations(ctx) == []

    def test_library_with_docs_no_recommendation(
        self, assistant: ContextualAIAssistant
    ) -> None:
        ctx = ProjectContext(project_type="library", has_documentation=True)
        assert assistant._get_documentation_recommendations(ctx) == []


# ---------------------------------------------------------------------------
# Public API — get_contextual_recommendations (sorting/limit)
# ---------------------------------------------------------------------------


class TestGetContextualRecommendations:
    def test_sorts_by_priority_then_confidence(
        self, assistant: ContextualAIAssistant
    ) -> None:
        """Three recommendations across priority levels. Higher priority
        must come first; ties broken by descending confidence."""
        recs = [
            AIRecommendation("x", "low", "L1", "d", confidence=0.9),
            AIRecommendation("x", "high", "H1", "d", confidence=0.5),
            AIRecommendation("x", "medium", "M1", "d", confidence=0.95),
            AIRecommendation("x", "high", "H2", "d", confidence=0.7),
        ]
        # Drive _generate_recommendations to return these.
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(assistant, "_generate_recommendations", lambda _ctx: recs)
            result = assistant.get_contextual_recommendations()

        assert [r.priority for r in result] == ["high", "high", "medium", "low"]
        # H2 (high, conf 0.7) > H1 (high, conf 0.5) — same priority, higher
        # confidence wins.
        assert result[0].title == "H2"
        assert result[1].title == "H1"

    def test_limits_max_recommendations(self, assistant: ContextualAIAssistant) -> None:
        recs = [
            AIRecommendation("x", "high", f"T{i}", "d", confidence=0.5)
            for i in range(20)
        ]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(assistant, "_generate_recommendations", lambda _ctx: recs)
            result = assistant.get_contextual_recommendations(max_recommendations=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Quick help
# ---------------------------------------------------------------------------


class TestGetQuickHelp:
    def test_coverage_query(self, assistant: ContextualAIAssistant) -> None:
        result = assistant.get_quick_help("how to check coverage?")
        assert "coverage" in result.lower()
        assert "python -m crackerjack" in result

    def test_security_query(self, assistant: ContextualAIAssistant) -> None:
        result = assistant.get_quick_help("any security issues?")
        assert "bandit" in result

    def test_lint_query(self, assistant: ContextualAIAssistant) -> None:
        result = assistant.get_quick_help("how to fix lint?")
        # The keyword mapping has "lint" mapped to a fix-format response.
        assert "fix code style" in result.lower() or "ai-fix" in result

    def test_test_query(self, assistant: ContextualAIAssistant) -> None:
        result = assistant.get_quick_help("how do I run tests?")
        assert "test" in result.lower()

    def test_publish_query(self, assistant: ContextualAIAssistant) -> None:
        result = assistant.get_quick_help("how to publish?")
        assert "publish" in result.lower() or "release" in result.lower()
        assert "-p patch" in result

    def test_clean_query(self, assistant: ContextualAIAssistant) -> None:
        result = assistant.get_quick_help("how to clean code?")
        assert "clean" in result.lower() or "TODO" in result

    def test_dashboard_query(self, assistant: ContextualAIAssistant) -> None:
        result = assistant.get_quick_help("how to start dashboard?")
        assert "dashboard" in result.lower() or "monitor" in result.lower()

    def test_unknown_query_returns_default(self, assistant: ContextualAIAssistant) -> None:
        result = assistant.get_quick_help("xyzzy nothing matches")
        assert "--help" in result
        assert "--ai-fix" in result


# ---------------------------------------------------------------------------
# Project analysis methods (subprocess mocked)
# ---------------------------------------------------------------------------


def _ok(stdout: str = "", returncode: int = 0) -> MagicMock:
    m = MagicMock(returncode=returncode, stdout=stdout, stderr="")
    return m


class TestProjectAnalysisHelpers:
    def test_has_test_directory_true(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / "tests").mkdir()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._has_test_directory() is True

    def test_has_test_directory_false(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._has_test_directory() is False

    def test_detect_main_languages_python_only(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / "pyproject.toml").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._detect_main_languages() == ["python"]

    def test_detect_main_languages_python_and_ts(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / "main.ts").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        langs = assistant._detect_main_languages()
        assert "python" in langs
        assert "typescript" in langs

    def test_detect_main_languages_no_project_files_defaults_to_python(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._detect_main_languages() == ["python"]

    def test_has_ci_cd_github_workflows(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        """The source's first entry is the literal string ``" .github / workflows"``
        (with spaces) — which can never match a real path. The GitHub
        workflows case is therefore dead code; pin that the other
        (correctly-spelled) entry, ``.gitlab-ci.yml``, still detects CI."""
        # The literal `" .github / workflows"` cannot exist on macOS/Linux
        # (leading space) so the GitHub detection is unreachable. We pin
        # this by using a gitlab config instead.
        (tmp_path / ".gitlab-ci.yml").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._has_ci_cd_config() is True

    def test_has_ci_cd_github_workflows_unreachable(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        """Even creating a directory at the exact buggy path doesn't
        match — file systems strip the leading space, so the GitHub
        workflows case is unreachable. The path entry returns False."""
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "workflows").mkdir()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        # Pinned: the correctly-named path does NOT match because the
        # source's entry has spaces in it.
        assert assistant._has_ci_cd_config() is False

    def test_has_ci_cd_gitlab(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / ".gitlab-ci.yml").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._has_ci_cd_config() is True

    def test_has_ci_cd_no_config(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._has_ci_cd_config() is False

    def test_has_documentation_readme(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / "README.md").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._has_documentation() is True

    def test_has_documentation_dir(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / "docs").mkdir()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._has_documentation() is True

    def test_has_documentation_no_indicator(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._has_documentation() is False

    def test_determine_project_size_small(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / "a.py").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._determine_project_size() == "small"

    def test_determine_project_size_medium(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        for i in range(20):
            (tmp_path / f"f{i}.py").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._determine_project_size() == "medium"

    def test_determine_project_size_large(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        for i in range(60):
            (tmp_path / f"f{i}.py").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        assert assistant._determine_project_size() == "large"

    def test_determine_project_type_no_pyproject_is_library(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        monkeypatch.setattr(assistant, "pyproject_path", tmp_path / "pyproject.toml")
        assert assistant._determine_project_type() == "library"

    def test_determine_project_type_cli_via_scripts(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_bytes(
            tomllib.dumps(
                {
                    "project": {
                        "name": "x",
                        "scripts": {"my-cli": "x.cli:main"},
                    }
                }
            )
            if hasattr(tomllib, "dumps")
            else b"[project]\nname='x'\n[project.scripts]\nmy-cli='x.cli:main'\n"
        )
        # The source uses tomllib.load(f) — write a TOML string instead.
        pyproject.write_text(
            "[project]\nname='x'\n[project.scripts]\nmy-cli='x.cli:main'\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        monkeypatch.setattr(assistant, "pyproject_path", pyproject)
        assert assistant._determine_project_type() == "cli"

    def test_determine_project_type_api_via_fastapi(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\nname='x'\ndependencies=['fastapi>=0.100']\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        monkeypatch.setattr(assistant, "pyproject_path", pyproject)
        assert assistant._determine_project_type() == "api"

    def test_determine_project_type_application_via_main(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname='x'\n", encoding="utf-8")
        (tmp_path / "__main__.py").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        monkeypatch.setattr(assistant, "pyproject_path", pyproject)
        assert assistant._determine_project_type() == "application"

    def test_determine_project_type_invalid_toml_returns_library(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("not = valid = toml = ", encoding="utf-8")
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        monkeypatch.setattr(assistant, "pyproject_path", pyproject)
        # The try/except returns "library" on parse error.
        assert assistant._determine_project_type() == "library"

    def test_get_outdated_dependencies_empty(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\nname='x'\ndependencies=['rich>=15.0.0']\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(assistant, "pyproject_path", pyproject)
        assert assistant._get_outdated_dependencies() == []

    def test_get_outdated_dependencies_picks_old_pinned(
        self, assistant: ContextualAIAssistant, tmp_path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        # The source pattern is the literal string " == 1." (with a
        # leading space and a dot). Build the dep string to match.
        pyproject.write_text(
            "[project]\nname='x'\n"
            "dependencies=['requests == 1.0.0', 'flask>=15.0.0']\n",
            encoding="utf-8",
        )
        assistant.pyproject_path = pyproject
        deps = assistant._get_outdated_dependencies()
        # Only `requests == 1.0.0` matches the literal pattern.
        assert "requests" in deps
        # flask has no " == 1." substring.
        assert "flask" not in deps

    def test_get_outdated_dependencies_no_pyproject(
        self, assistant: ContextualAIAssistant, tmp_path
    ) -> None:
        # No pyproject -> returns empty.
        assistant.pyproject_path = tmp_path / "pyproject.toml"
        assert assistant._get_outdated_dependencies() == []


class TestSubprocessBackedHelpers:
    """Helpers that shell out to subprocess. We mock subprocess.run."""

    def test_get_current_coverage_no_file_returns_zero(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        # No .coverage file -> short-circuits to 0.0 without spawning a process.
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        with patch("crackerjack.services.ai.contextual_ai_assistant.subprocess.run") as run:
            result = assistant._get_current_coverage()
        assert result == 0.0
        run.assert_not_called()

    def test_get_current_coverage_with_file(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / ".coverage").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok(json.dumps({"totals": {"percent_covered": 87.3}})),
        ):
            result = assistant._get_current_coverage()
        assert result == pytest.approx(87.3)

    def test_get_current_coverage_nonzero_exit(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        (tmp_path / ".coverage").touch()
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok("", returncode=1),
        ):
            assert assistant._get_current_coverage() == 0.0

    def test_count_current_lint_errors_uses_subprocess(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok(
                json.dumps([{"code": "E501"}, {"code": "F401"}]),
                returncode=1,
            ),
        ):
            assert assistant._count_current_lint_errors() == 2

    def test_count_current_lint_errors_invalid_json_falls_back_to_lines(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok("line1\nline2\nline3", returncode=1),
        ):
            assert assistant._count_current_lint_errors() == 3

    def test_count_current_lint_errors_success_returns_zero(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok("", returncode=0),
        ):
            assert assistant._count_current_lint_errors() == 0

    def test_days_since_last_commit(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        # Pretend the last commit was 100 seconds ago.
        now_minus_100 = int(__import__("time").time()) - 100
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok(str(now_minus_100), returncode=0),
        ):
            assert assistant._days_since_last_commit() == 0
        # 2 days ago
        two_days = int(__import__("time").time()) - 2 * 86400
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok(str(two_days), returncode=0),
        ):
            assert assistant._days_since_last_commit() == 2

    def test_days_since_last_commit_nonzero_exit(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok("", returncode=128),
        ):
            assert assistant._days_since_last_commit() == 0

    def test_detect_security_issues_parses_bandit_json(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        bandit = {
            "results": [
                {"test_id": "B101"},
                {"test_id": "B102"},
                {"test_id": "B103"},
                {"test_id": "B104"},
                {"test_id": "B105"},
                {"test_id": "B106"},
                {"test_id": "B107"},
            ]
        }
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok(json.dumps(bandit), returncode=1),
        ):
            issues = assistant._detect_security_issues()
        # Capped at 5 per source
        assert len(issues) == 5
        assert all("B10" in i for i in issues)

    def test_detect_security_issues_nonzero_exit_no_stdout(
        self, assistant: ContextualAIAssistant, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(assistant, "project_root", tmp_path)
        with patch(
            "crackerjack.services.ai.contextual_ai_assistant.subprocess.run",
            return_value=_ok("", returncode=1),
        ):
            assert assistant._detect_security_issues() == []


# ---------------------------------------------------------------------------
# Display routine
# ---------------------------------------------------------------------------


class TestDisplayRecommendations:
    def test_empty_list_prints_great_job(
        self, assistant: ContextualAIAssistant, console: Console
    ) -> None:
        assistant.display_recommendations([])
        rendered = "".join(
            str(call.args[0])
            for call in console.file.write.call_args_list  # type: ignore[attr-defined]
        )
        assert "No immediate recommendations" in rendered

    def test_with_recommendations_renders_each(
        self, assistant: ContextualAIAssistant, console: Console
    ) -> None:
        recs = [
            AIRecommendation(
                category="testing",
                priority="high",
                title="Test title",
                description="A description",
                action_command="run me",
                reasoning="because",
                confidence=0.7,
            )
        ]
        assistant.display_recommendations(recs)
        rendered = "".join(
            str(call.args[0])
            for call in console.file.write.call_args_list  # type: ignore[attr-defined]
        )
        assert "AI Assistant Recommendations" in rendered
        assert "Test title" in rendered
        assert "A description" in rendered
        assert "run me" in rendered
        assert "because" in rendered
        assert "70.0%" in rendered

    def test_without_optional_fields(
        self, assistant: ContextualAIAssistant, console: Console
    ) -> None:
        recs = [
            AIRecommendation(
                category="other", priority="low", title="Plain", description="d"
            )
        ]
        assistant.display_recommendations(recs)
        rendered = "".join(
            str(call.args[0])
            for call in console.file.write.call_args_list  # type: ignore[attr-defined]
        )
        # No action_command or reasoning -> the Run/Reasoning lines are
        # absent, but the title is still rendered.
        assert "Plain" in rendered


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class TestProjectContextDefaults:
    def test_defaults(self) -> None:
        ctx = ProjectContext()
        assert ctx.has_tests is False
        assert ctx.test_coverage == 0.0
        assert ctx.lint_errors_count == 0
        assert ctx.security_issues == []
        assert ctx.outdated_dependencies == []
        assert ctx.last_commit_days == 0
        assert ctx.project_size == "small"
        assert ctx.main_languages == []
        assert ctx.has_ci_cd is False
        assert ctx.has_documentation is False
        assert ctx.project_type == "library"

    def test_security_issues_independent_defaults(self) -> None:
        """The two mutable defaults must not share a list."""
        a = ProjectContext()
        b = ProjectContext()
        a.security_issues.append("x")
        assert b.security_issues == []
        a.outdated_dependencies.append("y")
        assert b.outdated_dependencies == []
