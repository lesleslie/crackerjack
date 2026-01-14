"""Unit tests for DocumentationCleanup service.

This test suite verifies the automatic documentation cleanup feature:
- File detection using whitelist + patterns + configuration
- Backup creation and rollback functionality
- Dry-run mode preservation of files
- Archive subdirectory categorization
- Configuration override behavior
"""

from __future__ import annotations

import tarfile
import tempfile
import typing as t
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.config.settings import CrackerjackSettings, DocumentationSettings
from crackerjack.services.backup_service import BackupMetadata
from crackerjack.services.documentation_cleanup import (
    ArchiveMapping,
    DocumentationCleanup,
    DocumentationCleanupResult,
)


@pytest.fixture
def temp_pkg_path():
    """Create a temporary package path for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_console():
    """Create a mock console for testing."""
    return Mock(spec=Console)


@pytest.fixture
def mock_git_service():
    """Create a mock git service for testing."""
    git_service = Mock()
    git_service.get_changed_files = Mock(return_value=[])
    return git_service


@pytest.fixture
def documentation_settings():
    """Create default documentation settings for testing."""
    return DocumentationSettings(
        enabled=True,
        auto_cleanup_on_publish=True,
        dry_run_by_default=False,
        backup_before_cleanup=True,
        essential_files=[
            "README.md",
            "CLAUDE.md",
            "CHANGELOG.md",
            "LICENSE",
        ],
        archive_patterns=[
            "*PLAN*.md",
            "*SUMMARY*.md",
            "SPRINT*.md",
        ],
        archive_subdirectories={
            "*PLAN*.md": "implementation-plans",
            "*SUMMARY*.md": "summaries",
            "SPRINT*.md": "sprints",
        },
    )


@pytest.fixture
def documentation_cleanup_service(
    temp_pkg_path: Path,
    mock_console: Mock,
    mock_git_service: Mock,
    documentation_settings: DocumentationSettings,
):
    """Create a DocumentationCleanup service instance for testing."""
    settings = CrackerjackSettings()
    settings.documentation = documentation_settings

    return DocumentationCleanup(
        console=mock_console,
        pkg_path=temp_pkg_path,
        git_service=mock_git_service,
        settings=settings,
    )


class TestDetectArchivableFiles:
    """Test file detection logic with whitelist and pattern matching."""

    def test_detect_archivable_files_with_patterns(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test that files matching archive patterns are detected."""
        # Create test files
        (temp_pkg_path / "README.md").touch()
        (temp_pkg_path / "SPRINT1_PLAN.md").touch()
        (temp_pkg_path / "PHASE2_SUMMARY.md").touch()
        (temp_pkg_path / "SOME_OTHER_FILE.md").touch()

        # Run detection
        archivable = documentation_cleanup_service._detect_archivable_files()

        # Verify
        archivable_names = {f.name for f in archivable}
        assert "SPRINT1_PLAN.md" in archivable_names
        assert "PHASE2_SUMMARY.md" in archivable_names
        assert "README.md" not in archivable_names  # Essential file
        assert "SOME_OTHER_FILE.md" not in archivable_names  # No pattern match

    def test_detect_archivable_files_empty_directory(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test behavior with no markdown files."""
        # No files created

        archivable = documentation_cleanup_service._detect_archivable_files()

        assert archivable == []

    def test_detect_archivable_files_only_essential_files(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test that essential files are not archived."""
        (temp_pkg_path / "README.md").touch()
        (temp_pkg_path / "CLAUDE.md").touch()
        (temp_pkg_path / "CHANGELOG.md").touch()

        archivable = documentation_cleanup_service._detect_archivable_files()

        assert archivable == []


class TestEssentialFilesPreserved:
    """Test that essential files are never archived."""

    def test_is_essential_file_whitelist(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test essential file detection from whitelist."""
        assert documentation_cleanup_service._is_essential_file("README.md")
        assert documentation_cleanup_service._is_essential_file("CLAUDE.md")
        assert documentation_cleanup_service._is_essential_file("CHANGELOG.md")
        assert documentation_cleanup_service._is_essential_file("LICENSE")

    def test_is_essential_file_non_essential(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test non-essential files are not in whitelist."""
        assert not documentation_cleanup_service._is_essential_file("SPRINT1_PLAN.md")
        assert not documentation_cleanup_service._is_essential_file("PHASE2_SUMMARY.md")
        assert not documentation_cleanup_service._is_essential_file("RANDOM_FILE.md")


class TestArchivePatternMatching:
    """Test pattern matching for archive categorization."""

    def test_matches_archive_patterns_exact_match(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test exact pattern matching."""
        assert documentation_cleanup_service._matches_archive_patterns("SPRINT1_PLAN.md")
        assert documentation_cleanup_service._matches_archive_patterns("PHASE2_SUMMARY.md")
        assert documentation_cleanup_service._matches_archive_patterns("SPRINT3.md")

    def test_matches_archive_patterns_case_sensitive(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test that pattern matching is case-sensitive."""
        assert documentation_cleanup_service._matches_archive_patterns("SPRINT1_PLAN.md")
        assert not documentation_cleanup_service._matches_archive_patterns("sprint1_plan.md")
        assert not documentation_cleanup_service._matches_archive_patterns("Sprint1_Plan.md")

    def test_matches_archive_patterns_no_match(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test files that don't match any pattern."""
        assert not documentation_cleanup_service._matches_archive_patterns("README.md")
        assert not documentation_cleanup_service._matches_archive_patterns("RANDOM_FILE.md")


class TestArchiveSubdirectoryDetection:
    """Test correct categorization of files into archive subdirectories."""

    def test_determine_archive_subdirectory_plan_files(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test PLAN files go to implementation-plans."""
        subdir = documentation_cleanup_service._determine_archive_subdirectory(
            "SPRINT1_PLAN.md"
        )
        assert subdir == "implementation-plans"

    def test_determine_archive_subdirectory_summary_files(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test SUMMARY files go to summaries."""
        subdir = documentation_cleanup_service._determine_archive_subdirectory(
            "PHASE2_SUMMARY.md"
        )
        assert subdir == "summaries"

    def test_determine_archive_subdirectory_sprint_files(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test SPRINT files go to sprints."""
        subdir = documentation_cleanup_service._determine_archive_subdirectory(
            "SPRINT3.md"
        )
        assert subdir == "sprints"

    def test_determine_archive_subdirectory_no_match(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test files with no matching pattern return None."""
        subdir = documentation_cleanup_service._determine_archive_subdirectory(
            "RANDOM_FILE.md"
        )
        assert subdir is None


class TestArchiveMappings:
    """Test ArchiveMapping pattern-to-subdirectory mappings."""

    def test_build_archive_mappings(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test that archive mappings are built correctly from settings."""
        mappings = documentation_cleanup_service._archive_mappings

        assert len(mappings) == 3
        assert any(m.pattern == "*PLAN*.md" for m in mappings)
        assert any(m.pattern == "*SUMMARY*.md" for m in mappings)
        assert any(m.pattern == "SPRINT*.md" for m in mappings)

    def test_archive_mapping_structure(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test ArchiveMapping dataclass structure."""
        mapping = ArchiveMapping(
            pattern="*PLAN*.md",
            subdirectory="implementation-plans",
        )

        assert mapping.pattern == "*PLAN*.md"
        assert mapping.subdirectory == "implementation-plans"


class TestDryRunMode:
    """Test dry-run mode preserves files without modification."""

    def test_dry_run_does_not_modify_files(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test that dry-run mode doesn't move files."""
        # Create test files
        plan_file = temp_pkg_path / "SPRINT1_PLAN.md"
        plan_file.write_text("Plan content")

        summary_file = temp_pkg_path / "PHASE2_SUMMARY.md"
        summary_file.write_text("Summary content")

        # Run cleanup in dry-run mode
        result = documentation_cleanup_service.cleanup_documentation(dry_run=True)

        # Verify files still exist and unchanged
        assert plan_file.exists()
        assert plan_file.read_text() == "Plan content"
        assert summary_file.exists()
        assert summary_file.read_text() == "Summary content"

        # Verify result metadata
        assert result.success
        assert result.files_moved == 0  # No files moved in dry run
        # Note: Summary doesn't include "dry run" text, it just shows 0 files moved


class TestBackupCreation:
    """Test backup creation before file operations."""

    def test_backup_created_before_cleanup(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test that backup is created before file operations."""
        # Create test files
        plan_file = temp_pkg_path / "SPRINT1_PLAN.md"
        plan_file.write_text("Plan content")

        # Create archive directory
        archive_dir = temp_pkg_path / "docs" / "archive"
        archive_dir.mkdir(parents=True)

        # Run cleanup (not dry-run)
        result = documentation_cleanup_service.cleanup_documentation(dry_run=False)

        # Verify backup was created
        assert result.success
        assert result.backup_metadata is not None
        assert result.backup_metadata.backup_id is not None
        assert result.backup_metadata.total_files >= 1


class TestRollbackFunctionality:
    """Test rollback from backup restores files correctly."""

    def test_rollback_from_backup(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test that rollback restores files from backup."""
        from datetime import datetime

        # Create backup directory structure
        backup_dir = temp_pkg_path / "docs" / ".backups" / "20250113-120000"
        backup_dir.mkdir(parents=True)

        # Create a backup archive
        backup_archive = backup_dir / "backup.tar.gz"

        # Create original file in temp location
        with tempfile.TemporaryDirectory() as temp_extract_dir:
            temp_extract = Path(temp_extract_dir)
            original_file = temp_extract / "SPRINT1_PLAN.md"
            original_file.write_text("Restored content")

            # Create backup archive
            with tarfile.open(backup_archive, "w:gz") as tar:
                tar.add(original_file, arcname=original_file.name)

        # Create backup metadata with proper timestamp
        backup_metadata = BackupMetadata(
            backup_id="20250113-120000",
            timestamp=datetime.now(),
            package_directory=temp_pkg_path,
            backup_directory=backup_dir,
            total_files=1,
            total_size=100,
            checksum="abc123",
            file_checksums={},
        )

        # Run rollback
        success = documentation_cleanup_service.rollback_cleanup(backup_metadata)

        # Verify file was restored
        assert success
        restored_file = temp_pkg_path / "SPRINT1_PLAN.md"
        assert restored_file.exists()
        assert restored_file.read_text() == "Restored content"


class TestConfigurationOverride:
    """Test YAML configuration override behavior."""

    def test_configuration_override_essential_files(
        self,
        temp_pkg_path: Path,
        mock_console: Mock,
        mock_git_service: Mock,
    ):
        """Test that YAML configuration overrides default essential files."""
        # Create custom settings
        custom_settings = CrackerjackSettings()
        custom_settings.documentation.essential_files = [
            "CUSTOM_ESSENTIAL.md",
        ]

        service = DocumentationCleanup(
            console=mock_console,
            pkg_path=temp_pkg_path,
            git_service=mock_git_service,
            settings=custom_settings,
        )

        # Verify custom configuration
        assert service._is_essential_file("CUSTOM_ESSENTIAL.md")
        assert not service._is_essential_file("README.md")

    def test_configuration_override_archive_patterns(
        self,
        temp_pkg_path: Path,
        mock_console: Mock,
        mock_git_service: Mock,
    ):
        """Test that YAML configuration overrides default archive patterns."""
        custom_settings = CrackerjackSettings()
        custom_settings.documentation.archive_patterns = ["*CUSTOM*.md"]

        service = DocumentationCleanup(
            console=mock_console,
            pkg_path=temp_pkg_path,
            git_service=mock_git_service,
            settings=custom_settings,
        )

        # Verify custom pattern matching
        assert service._matches_archive_patterns("FILE_CUSTOM.md")
        assert not service._matches_archive_patterns("SPRINT1_PLAN.md")


class TestCountEssentialFiles:
    """Test counting essential files in project root."""

    def test_count_essential_files(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test counting essential markdown files."""
        # Create essential files
        (temp_pkg_path / "README.md").touch()
        (temp_pkg_path / "CLAUDE.md").touch()
        (temp_pkg_path / "CHANGELOG.md").touch()

        # Create non-essential files
        (temp_pkg_path / "SPRINT1_PLAN.md").touch()

        count = documentation_cleanup_service._count_essential_files()

        assert count == 3


class TestGenerateSummary:
    """Test summary generation for cleanup results."""

    def test_generate_summary_with_archived_files(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test summary generation with archived files."""
        result = DocumentationCleanupResult(
            success=True,
            files_moved=5,
            files_preserved=3,
            archived_files={
                "sprints": ["SPRINT1.md", "SPRINT2.md"],
                "summaries": ["PHASE1_SUMMARY.md"],
            },
        )

        summary = documentation_cleanup_service._generate_summary(result)

        assert "Files moved: 5" in summary
        assert "Files preserved: 3" in summary
        assert "sprints/" in summary
        assert "summaries/" in summary

    def test_generate_summary_no_files_moved(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test summary when no files were moved."""
        result = DocumentationCleanupResult(
            success=True,
            files_moved=0,
            files_preserved=7,
            archived_files={},
        )

        summary = documentation_cleanup_service._generate_summary(result)

        assert "Files moved: 0" in summary
        assert "Files preserved: 7" in summary


class TestGenerateBackupId:
    """Test backup ID generation."""

    def test_generate_backup_id_format(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test that backup ID follows expected format."""
        backup_id = documentation_cleanup_service._generate_backup_id()

        # Format: YYYYMMDD-HHMMSS (length may vary slightly based on time)
        assert len(backup_id) >= 15  # At minimum: 8 digits + 1 hyphen + 6 digits
        assert "-" in backup_id
        assert backup_id.count("-") == 1

        # Verify it's all digits except for the hyphen
        parts = backup_id.split("-")
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert parts[1].isdigit()


class TestValidatePreconditions:
    """Test preconditions validation before cleanup."""

    def test_validate_preconditions_success(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test successful validation when all preconditions met."""
        # Create archive directory
        archive_dir = temp_pkg_path / "docs" / "archive"
        archive_dir.mkdir(parents=True)

        is_valid, error_msg = documentation_cleanup_service._validate_preconditions()

        assert is_valid
        assert error_msg is None

    def test_validate_preconditions_git_dirty(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        mock_git_service: Mock,
        temp_pkg_path: Path,
    ):
        """Test validation fails with uncommitted git changes."""
        # Create archive directory
        archive_dir = temp_pkg_path / "docs" / "archive"
        archive_dir.mkdir(parents=True)

        # Mock git service to return changed files
        mock_git_service.get_changed_files = Mock(return_value=["modified_file.txt"])

        is_valid, error_msg = documentation_cleanup_service._validate_preconditions()

        assert not is_valid
        assert "uncommitted changes" in error_msg.lower()
