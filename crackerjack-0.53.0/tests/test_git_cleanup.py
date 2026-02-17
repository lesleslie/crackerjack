"""Unit tests for GitCleanupService.

This test suite verifies the git cleanup feature:
- Detection of .gitignore patterns
- Identification of tracked files matching patterns
- Three-tiered cleanup strategy (config files, cache dirs, filter-branch)
- Dry-run mode
- Working tree validation
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.config.settings import CrackerjackSettings, GitCleanupSettings
from crackerjack.models.protocols import GitInterface
from crackerjack.services.git_cleanup_service import (
    GitCleanupResult,
    GitCleanupService,
)


@pytest.fixture
def temp_pkg_path(tmp_path: Path):
    """Create a temporary package path for testing."""
    yield tmp_path


@pytest.fixture
def mock_console():
    """Create a mock console for testing."""
    return Mock(spec=Console)


@pytest.fixture
def mock_git_service():
    """Create a mock git service for testing."""
    git_service = Mock(spec=GitInterface)

    # Mock run_git_command to return GitResult
    mock_result = Mock()
    mock_result.success = True
    mock_result.stdout = ""
    git_service.run_git_command = Mock(return_value=mock_result)

    # Mock get_changed_files for working tree validation
    git_service.get_changed_files = Mock(return_value=[])

    return git_service


@pytest.fixture
def git_cleanup_settings():
    """Create default git cleanup settings for testing."""
    return GitCleanupSettings(
        enabled=True,
        smart_approach=True,
        filter_branch_threshold=100,
        require_clean_working_tree=True,
    )


@pytest.fixture
def git_cleanup_service(
    temp_pkg_path: Path,
    mock_console: Mock,
    mock_git_service: Mock,
    git_cleanup_settings: GitCleanupSettings,
):
    """Create a GitCleanupService instance for testing."""
    settings = CrackerjackSettings()
    settings.git_cleanup = git_cleanup_settings

    return GitCleanupService(
        console=mock_console,
        pkg_path=temp_pkg_path,
        git_service=mock_git_service,
        settings=settings,
    )


class TestLoadGitignorePatterns:
    """Test .gitignore pattern loading."""

    def test_load_gitignore_patterns_file_exists(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test loading patterns from existing .gitignore."""
        gitignore = temp_pkg_path / ".gitignore"
        gitignore.write_text(
            """# Comment line
*.pyc
.pytest_cache/
__pycache__/

.mypy_cache/
.ruff_cache/
"""
        )

        patterns = git_cleanup_service._load_gitignore_patterns()

        # Should have 5 patterns (comment and empty lines filtered out)
        assert len(patterns) == 5
        assert "*.pyc" in patterns
        assert ".pytest_cache/" in patterns
        assert "__pycache__/" in patterns
        assert ".mypy_cache/" in patterns
        assert ".ruff_cache/" in patterns
        assert "# Comment line" not in patterns

    def test_load_gitignore_patterns_no_file(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test behavior when .gitignore doesn't exist."""
        patterns = git_cleanup_service._load_gitignore_patterns()

        assert patterns == []

    def test_load_gitignore_patterns_caching(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test that patterns are cached after first load."""
        gitignore = temp_pkg_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        # First call loads from file
        patterns1 = git_cleanup_service._load_gitignore_patterns()

        # Modify file
        gitignore.write_text("*.pyc\n__pycache__\n")

        # Second call should use cached value
        patterns2 = git_cleanup_service._load_gitignore_patterns()

        assert patterns1 == patterns2
        assert len(patterns2) == 1


class TestGetGitignoreChanges:
    """Test detection of tracked files matching .gitignore patterns."""

    def test_get_gitignore_changes_no_patterns(
        self,
        git_cleanup_service: GitCleanupService,
    ):
        """Test behavior with no .gitignore patterns."""
        changes = git_cleanup_service._get_gitignore_changes([])

        assert changes == []

    def test_get_gitignore_changes_no_tracked_files(
        self,
        git_cleanup_service: GitCleanupService,
    ):
        """Test behavior when no tracked files."""
        # Mock the service's _run_git_command method
        mock_result = Mock()
        mock_result.success = True
        mock_result.stdout = ""
        git_cleanup_service._run_git_command = Mock(return_value=mock_result)

        changes = git_cleanup_service._get_gitignore_changes(["*.pyc"])

        assert changes == []

    def test_get_gitignore_changes_with_matches(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test detection of matching files."""
        # Mock git ls-files output
        mock_result = Mock()
        mock_result.success = True
        mock_result.stdout = "test.pyc\n__pycache__/module.pyc\nsrc.py\n"
        git_cleanup_service._run_git_command = Mock(return_value=mock_result)

        patterns = ["*.pyc"]
        changes = git_cleanup_service._get_gitignore_changes(patterns)

        # Should find .pyc files
        assert len(changes) == 2
        assert all(f.name in ("test.pyc", "module.pyc") for f in changes)


class TestCategorizeFiles:
    """Test file categorization into config files and cache directories."""

    def test_categorize_config_files(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test identification of config files."""
        files = [
            temp_pkg_path / "mypy.ini",
            temp_pkg_path / ".ruffignore",
            temp_pkg_path / "pyrightconfig.json",
        ]

        config_files, cache_dirs = git_cleanup_service._categorize_files(files)

        assert len(config_files) == 3
        assert len(cache_dirs) == 0

    def test_categorize_cache_directories(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test identification of cache directories."""
        files = [
            temp_pkg_path / "__pycache__",
            temp_pkg_path / ".pytest_cache",
            temp_pkg_path / ".ruff_cache",
        ]

        config_files, cache_dirs = git_cleanup_service._categorize_files(files)

        assert len(config_files) == 0
        assert len(cache_dirs) == 3

    def test_categorize_mixed_files(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test categorization of mixed file types."""
        files = [
            temp_pkg_path / "mypy.ini",
            temp_pkg_path / "__pycache__",
            temp_pkg_path / ".ruffignore",
            temp_pkg_path / ".pytest_cache",
        ]

        config_files, cache_dirs = git_cleanup_service._categorize_files(files)

        assert len(config_files) == 2
        assert len(cache_dirs) == 2
        assert (temp_pkg_path / "mypy.ini") in config_files
        assert (temp_pkg_path / "__pycache__") in cache_dirs


class TestRemoveFromIndexCached:
    """Test removal of config files from git index (keeping local)."""

    def test_remove_from_index_cached_success(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test successful removal of config files."""
        # Mock _run_git_command to succeed
        mock_result = Mock()
        mock_result.success = True
        git_cleanup_service._run_git_command = Mock(return_value=mock_result)

        config_files = [temp_pkg_path / "mypy.ini", temp_pkg_path / ".ruffignore"]

        removed = git_cleanup_service._remove_from_index_cached(config_files)

        assert removed == 2
        assert git_cleanup_service._run_git_command.call_count == 2

    def test_remove_from_index_cached_empty_list(
        self,
        git_cleanup_service: GitCleanupService,
    ):
        """Test behavior with empty file list."""
        removed = git_cleanup_service._remove_from_index_cached([])

        assert removed == 0
        # No git commands should be executed for empty list
        # If _run_git_command was mocked, call_count should be 0
        # If not mocked, it's still the original function
        if hasattr(git_cleanup_service._run_git_command, "call_count"):
            assert git_cleanup_service._run_git_command.call_count == 0

    def test_remove_from_index_cached_partial_failure(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test behavior when some removals fail."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            mock_result = Mock()
            call_count[0] += 1
            # First call succeeds, second fails
            if call_count[0] == 1:
                mock_result.success = True
            else:
                mock_result.success = False
            return mock_result

        git_cleanup_service._run_git_command = Mock(side_effect=side_effect)

        config_files = [temp_pkg_path / "mypy.ini", temp_pkg_path / ".ruffignore"]

        removed = git_cleanup_service._remove_from_index_cached(config_files)

        # Should return count of successful removals
        assert removed == 1


class TestRemoveFromIndexHard:
    """Test hard removal of cache directories from git and filesystem."""

    def test_remove_from_index_hard_success(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test successful removal of cache directories."""
        mock_result = Mock()
        mock_result.success = True
        git_cleanup_service._run_git_command = Mock(return_value=mock_result)

        cache_dirs = [
            temp_pkg_path / "__pycache__",
            temp_pkg_path / ".pytest_cache",
        ]

        removed = git_cleanup_service._remove_from_index_hard(cache_dirs)

        assert removed == 2
        assert git_cleanup_service._run_git_command.call_count == 2

    def test_remove_from_index_hard_empty_list(
        self,
        git_cleanup_service: GitCleanupService,
    ):
        """Test behavior with empty directory list."""
        removed = git_cleanup_service._remove_from_index_hard([])

        assert removed == 0
        # No git commands should be executed for empty list
        # If _run_git_command was mocked, call_count should be 0
        # If not mocked, it's still the original function
        if hasattr(git_cleanup_service._run_git_command, "call_count"):
            assert git_cleanup_service._run_git_command.call_count == 0


class TestValidateWorkingTreeClean:
    """Test working tree validation before git operations."""

    def test_validate_working_tree_clean_success(
        self,
        git_cleanup_service: GitCleanupService,
        mock_git_service: Mock,
    ):
        """Test validation with clean working tree."""
        mock_git_service.get_changed_files = Mock(return_value=[])

        is_clean, error_msg = git_cleanup_service._validate_working_tree_clean()

        assert is_clean
        assert error_msg is None

    def test_validate_working_tree_clean_dirty(
        self,
        git_cleanup_service: GitCleanupService,
        mock_git_service: Mock,
    ):
        """Test validation with dirty working tree."""
        mock_git_service.get_changed_files = Mock(return_value=["modified.txt"])

        is_clean, error_msg = git_cleanup_service._validate_working_tree_clean()

        assert not is_clean
        assert "uncommitted changes" in error_msg.lower()

    def test_validate_working_tree_clean_disabled(
        self,
        git_cleanup_service: GitCleanupService,
        mock_git_service: Mock,
    ):
        """Test that validation can be disabled via settings."""
        # Modify the settings object directly (service stores full CrackerjackSettings)
        git_cleanup_service._settings.git_cleanup.require_clean_working_tree = False

        mock_git_service.get_changed_files = Mock(return_value=["modified.txt"])

        # Call cleanup_git_deleted_files instead of _validate_working_tree_clean directly
        # This tests the actual behavior where validation is skipped when disabled
        result = git_cleanup_service.cleanup_git_deleted_files(dry_run=False)

        # Should succeed even with dirty tree when validation is disabled
        # (though it will fail at git ls-files since .gitignore doesn't exist in tmp_path)
        # The key is that it doesn't fail at the working tree validation step
        assert "No .gitignore patterns found" in result.summary or result.success


class TestCleanupGitDeletedFiles:
    """Test main cleanup orchestration."""

    def test_cleanup_git_deleted_files_no_gitignore(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test cleanup when .gitignore doesn't exist."""
        result = git_cleanup_service.cleanup_git_deleted_files(dry_run=False)

        assert result.success
        assert "No .gitignore patterns found" in result.summary

    def test_cleanup_git_deleted_files_no_matches(
        self,
        git_cleanup_service: GitCleanupService,
        mock_git_service: Mock,
        temp_pkg_path: Path,
    ):
        """Test cleanup when no tracked files match patterns."""
        # Create .gitignore
        gitignore = temp_pkg_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        # Mock git ls-files to return no matches
        mock_result = Mock()
        mock_result.success = True
        mock_result.stdout = "src.py\nREADME.md\n"
        mock_git_service.run_git_command = Mock(return_value=mock_result)

        result = git_cleanup_service.cleanup_git_deleted_files(dry_run=False)

        assert result.success
        assert "No tracked files match" in result.summary

    def test_cleanup_git_deleted_files_dry_run(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test dry-run mode doesn't modify files."""
        # Create .gitignore
        gitignore = temp_pkg_path / ".gitignore"
        gitignore.write_text("mypy.ini\n.pytest_cache/\n")

        # Mock git ls-files
        mock_result = Mock()
        mock_result.success = True
        mock_result.stdout = "mypy.ini\n"
        git_cleanup_service._run_git_command = Mock(return_value=mock_result)

        result = git_cleanup_service.cleanup_git_deleted_files(dry_run=True)

        assert result.success
        assert result.dry_run
        assert "Dry Run" in result.summary
        # Verify no git commands were executed (only ls-files for detection)
        assert git_cleanup_service._run_git_command.call_count == 1


class TestGenerateSummaries:
    """Test summary generation for various scenarios."""

    def test_generate_dry_run_summary(
        self,
        git_cleanup_service: GitCleanupService,
        temp_pkg_path: Path,
    ):
        """Test dry-run summary generation."""
        config_files = [
            temp_pkg_path / "mypy.ini",
            temp_pkg_path / ".ruffignore",
        ]
        cache_dirs = [
            temp_pkg_path / "__pycache__",
        ]

        summary = git_cleanup_service._generate_dry_run_summary(
            config_files=config_files,
            cache_dirs=cache_dirs,
        )

        assert "Dry Run" in summary
        assert "Config files to remove" in summary
        assert "Cache dirs to remove" in summary
        assert "2" in summary  # 2 config files
        assert "1" in summary  # 1 cache dir

    def test_generate_cleanup_summary(
        self,
        git_cleanup_service: GitCleanupService,
    ):
        """Test cleanup summary generation."""
        summary = git_cleanup_service._generate_cleanup_summary(
            removed_cached=2,
            removed_hard=1,
            config_files=[],
            cache_dirs=[],
            suggest_filter_branch=False,
        )

        assert "Cleanup Complete" in summary
        assert "2" in summary
        assert "1" in summary

    def test_generate_summary_with_filter_branch_suggestion(
        self,
        git_cleanup_service: GitCleanupService,
    ):
        """Test summary includes filter-branch suggestion."""
        summary = git_cleanup_service._generate_cleanup_summary(
            removed_cached=150,
            removed_hard=0,
            config_files=[],
            cache_dirs=[],
            suggest_filter_branch=True,
        )

        assert "filter-branch" in summary
