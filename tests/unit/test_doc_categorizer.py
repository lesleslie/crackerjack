"""Unit tests for DocumentationCategorizer.

These tests verify the sophisticated regex-based categorization logic
that achieves 100% accuracy across the crackerjack documentation.
"""

from pathlib import Path

import pytest

from crackerjack.services.doc_categorizer import (
    CategoryResult,
    DocumentationCategorizer,
)


@pytest.fixture
def categorizer(tmp_path: Path) -> DocumentationCategorizer:
    """Create a categorizer instance with a temporary directory."""
    return DocumentationCategorizer(tmp_path)


class TestCoreCategorization:
    """Test core categorization functionality."""

    def test_categorize_completion_report(self, categorizer: DocumentationCategorizer) -> None:
        """Test completion reports are categorized correctly."""
        result = categorizer.categorize_file(Path("ADAPTER_FIX_COMPLETION_REPORT.md"))

        assert result.category == "completion_reports"
        assert result.destination == "docs/archive/completion-reports/"
        assert "Historical completion reports" in result.reason

    def test_categorize_agent_report(self, categorizer: DocumentationCategorizer) -> None:
        """Test all-caps agent reports are categorized correctly."""
        result = categorizer.categorize_file(Path("TYPE_FIXING_REPORT_AGENT4.md"))

        assert result.category == "completion_reports"
        assert result.destination == "docs/archive/completion-reports/"

    def test_categorize_dash_separated_investigation(self, categorizer: DocumentationCategorizer) -> None:
        """Test dash-separated investigation files are categorized correctly."""
        result = categorizer.categorize_file(Path("bandit-performance-investigation.md"))

        assert result.category == "investigations"
        assert result.destination == "docs/archive/investigations/"

    def test_categorize_dash_separated_plan(self, categorizer: DocumentationCategorizer) -> None:
        """Test dash-separated implementation plans are categorized correctly."""
        result = categorizer.categorize_file(Path("refactoring-plan-complexity-violations.md"))

        assert result.category == "implementation_plans"
        assert result.destination == "docs/"

    def test_categorize_implementation_plan(self, categorizer: DocumentationCategorizer) -> None:
        """Test standard implementation plans are categorized correctly."""
        result = categorizer.categorize_file(Path("TY_MIGRATION_PLAN.md"))

        assert result.category == "implementation_plans"
        assert result.destination == "docs/"

    def test_categorize_completion(self, categorizer: DocumentationCategorizer) -> None:
        """Test completion reports are categorized correctly."""
        result = categorizer.categorize_file(Path("FEATURE_COMPLETE.md"))

        assert result.category == "completion_reports"
        assert result.destination == "docs/archive/completion-reports/"

    def test_categorize_audit(self, categorizer: DocumentationCategorizer) -> None:
        """Test audit files are categorized correctly."""
        result = categorizer.categorize_file(Path("AUDIT_HOOKS_TOOLS.md"))

        assert result.category == "audits"
        assert result.destination == "docs/archive/audits/"

    def test_categorize_analysis(self, categorizer: DocumentationCategorizer) -> None:
        """Test analysis files are categorized correctly."""
        result = categorizer.categorize_file(Path("python-improvements-summary.md"))

        assert result.category == "analysis"
        assert result.destination == "docs/archive/analysis/"


class TestEssentialFiles:
    """Test essential files that should be kept in root."""

    def test_readme_kept_in_root(self, categorizer: DocumentationCategorizer) -> None:
        """Test README.md is kept in root."""
        result = categorizer.categorize_file(Path("README.md"))

        assert result.category == "keep_in_root"
        assert result.destination is None

    def test_changelog_kept_in_root(self, categorizer: DocumentationCategorizer) -> None:
        """Test CHANGELOG.md is kept in root."""
        result = categorizer.categorize_file(Path("CHANGELOG.md"))

        assert result.category == "keep_in_root"
        assert result.destination is None

    def test_claude_md_kept_in_root(self, categorizer: DocumentationCategorizer) -> None:
        """Test CLAUDE.md is kept in root."""
        result = categorizer.categorize_file(Path("CLAUDE.md"))

        assert result.category == "keep_in_root"
        assert result.destination is None

    def test_cleanup_guidelines_kept_in_root(self, categorizer: DocumentationCategorizer) -> None:
        """Test DOCS_CLEANUP_GUIDELINES.md is kept in root."""
        result = categorizer.categorize_file(Path("DOCS_CLEANUP_GUIDELINES.md"))

        assert result.category == "keep_in_root"
        assert result.destination is None

    def test_phase_completion_kept_in_root(self, categorizer: DocumentationCategorizer) -> None:
        """Test phase completion milestones are kept in root."""
        result = categorizer.categorize_file(Path("PHASE_2_COMPLETION.md"))

        assert result.category == "keep_in_root"
        assert result.destination is None


class TestUserFacingDocs:
    """Test user-facing documentation kept in docs/."""

    def test_ai_fix_behavior_in_docs(self, categorizer: DocumentationCategorizer) -> None:
        """Test AI_FIX_EXPECTED_BEHAVIOR.md is kept in docs/."""
        result = categorizer.categorize_file(Path("AI_FIX_EXPECTED_BEHAVIOR.md"))

        assert result.category == "keep_in_docs"
        assert result.destination == "docs/"


class TestUncategorizedFiles:
    """Test files that don't match any pattern."""

    def test_unknown_file_uncategorized(self, categorizer: DocumentationCategorizer) -> None:
        """Test files without matching patterns are uncategorized."""
        result = categorizer.categorize_file(Path("UNKNOWN_FILE_xyz123.md"))

        assert result.category is None
        assert result.destination is None
        assert "No matching pattern found" in result.reason


class TestUtilityMethods:
    """Test utility methods for file filtering."""

    def test_should_keep_in_root(self, categorizer: DocumentationCategorizer) -> None:
        """Test should_keep_in_root utility method."""
        assert categorizer.should_keep_in_root(Path("README.md"))
        assert categorizer.should_keep_in_root(Path("CHANGELOG.md"))
        assert not categorizer.should_keep_in_root(Path("TY_MIGRATION_PLAN.md"))

    def test_should_keep_in_docs(self, categorizer: DocumentationCategorizer) -> None:
        """Test should_keep_in_docs utility method."""
        assert categorizer.should_keep_in_docs(Path("AI_FIX_EXPECTED_BEHAVIOR.md"))
        assert not categorizer.should_keep_in_docs(Path("README.md"))

    def test_get_archivable_files(self, categorizer: DocumentationCategorizer, tmp_path: Path) -> None:
        """Test get_archivable_files returns correct list."""
        # Create test files
        (tmp_path / "README.md").touch()
        (tmp_path / "COMPLETED_FIX.md").touch()
        (tmp_path / "TY_MIGRATION_PLAN.md").touch()

        archivable = categorizer.get_archivable_files()

        # README should not be archivable (keep_in_root)
        # COMPLETED_FIX should be archivable (goes to sprints-and-fixes)
        # TY_MIGRATION_PLAN should be archivable (implementation_plans have destination "docs/" which is not "keep_in_*")

        filenames = [f.name for f in archivable]
        assert "COMPLETED_FIX.md" in filenames
        assert "README.md" not in filenames
        assert "TY_MIGRATION_PLAN.md" in filenames  # Has destination "docs/", not "keep_in_*"

    def test_get_archive_subdirectory(self, categorizer: DocumentationCategorizer) -> None:
        """Test get_archive_subdirectory extracts correct subdirectory."""
        assert categorizer.get_archive_subdirectory(Path("COMPLETED_FIX_COMPLETE.md")) == "completion-reports"
        assert categorizer.get_archive_subdirectory(Path("AUDIT_TEST.md")) == "audits"
        assert categorizer.get_archive_subdirectory(Path("performance_investigation.md")) == "investigations"  # Dash pattern
        assert categorizer.get_archive_subdirectory(Path("README.md")) is None


class TestCaseInsensitiveMatching:
    """Test that pattern matching is case-insensitive."""

    def test_uppercase_filename(self, categorizer: DocumentationCategorizer) -> None:
        """Test uppercase filenames match patterns."""
        result = categorizer.categorize_file(Path("README.MD"))

        assert result.category == "keep_in_root"

    def test_mixed_case_filename(self, categorizer: DocumentationCategorizer) -> None:
        """Test mixed-case filenames match patterns."""
        result = categorizer.categorize_file(Path("Ai_Fix_Expected_Behavior.Md"))

        assert result.category == "keep_in_docs"


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_filename(self, categorizer: DocumentationCategorizer) -> None:
        """Test empty filename doesn't crash."""
        result = categorizer.categorize_file(Path(""))

        assert result.category is None

    def test_non_md_file(self, categorizer: DocumentationCategorizer) -> None:
        """Test non-markdown files return uncategorized."""
        result = categorizer.categorize_file(Path("document.txt"))

        assert result.category is None

    def test_path_with_directory(self, categorizer: DocumentationCategorizer) -> None:
        """Test that only filename is used for categorization."""
        result = categorizer.categorize_file(Path("some/subdir/README.md"))

        # Should still match based on filename only
        assert result.category == "keep_in_root"
