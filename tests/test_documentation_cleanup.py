"""Unit tests for DocumentationCleanup service.

This test suite verifies the automatic documentation cleanup feature:
- File detection using whitelist + patterns + configuration
- Backup creation and rollback functionality
- Dry-run mode preservation of files
- Archive subdirectory categorization
- Configuration override behavior
"""

from __future__ import annotations

import ast
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.config.settings import CrackerjackSettings, DocumentationSettings
from crackerjack.services import documentation_cleanup
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

    def test_legacy_detection_path_respects_the_lifecycle_gate(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """The fallback detector must not become a gate bypass.

        ``_detect_archivable_files`` falls back to the legacy pattern
        matcher when the categorizer raises. That fallback matches by
        filename alone, so without the gate it would sweep a governed
        document — exactly the failure the gate exists to prevent.
        """
        governed = temp_pkg_path / "SPRINT1_PLAN.md"
        governed.write_text(
            "---\nstatus: complete\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

        def _categorizer_unavailable() -> list[Path]:
            raise RuntimeError("categorizer unavailable")

        monkeypatch.setattr(
            documentation_cleanup_service.categorizer,
            "get_archival_candidates",
            _categorizer_unavailable,
        )

        archivable = documentation_cleanup_service._detect_archivable_files()

        assert "SPRINT1_PLAN.md" not in {f.name for f in archivable}

    def test_legacy_detection_path_still_archives_ungoverned_files(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A file with no lifecycle is still swept by the fallback path."""

        def _categorizer_unavailable() -> list[Path]:
            raise RuntimeError("categorizer unavailable")

        monkeypatch.setattr(
            documentation_cleanup_service.categorizer,
            "get_archival_candidates",
            _categorizer_unavailable,
        )
        (temp_pkg_path / "SPRINT1_PLAN.md").write_text("# Scratch\n", encoding="utf-8")

        archivable = documentation_cleanup_service._detect_archivable_files()

        assert "SPRINT1_PLAN.md" in {f.name for f in archivable}

    def test_detection_applies_the_gate_to_the_categorizer_path(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """The primary detection path is gated too — this is the contract.

        The two OTel substrate plans in mahavishnu matched the
        ``implementation_reports`` name pattern and were swept three
        times because nothing read their frontmatter.
        """
        governed = temp_pkg_path / "2026-10-19-example-implementation.md"
        governed.write_text(
            "---\nstatus: complete\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )
        shipped = temp_pkg_path / "2026-10-20-example-implementation.md"
        shipped.write_text(
            "---\nstatus: shipped\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

        archivable = documentation_cleanup_service._detect_archivable_files()

        names = {f.name for f in archivable}
        assert "2026-10-19-example-implementation.md" not in names
        assert "2026-10-20-example-implementation.md" in names

    def test_a_backup_of_a_document_is_gated_too(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """``foo.md.backup`` holds a document's content, so it is gated.

        The gate keys on the name rather than the suffix: a backup of a
        governed document carries that document's frontmatter, and a
        sweep must not decide a live document's fate — not even by way
        of a copy of it.
        """
        (temp_pkg_path / "2026-10-19-example.md.backup").write_text(
            "---\nstatus: active\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

        archivable = documentation_cleanup_service._detect_archivable_files()

        assert "2026-10-19-example.md.backup" not in {f.name for f in archivable}

    def test_non_markdown_artifacts_are_not_lifecycle_gated(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """A non-markdown root artifact has no lifecycle — it is still swept.

        Only markdown carries a frontmatter lifecycle. The loose
        ``.py`` / ``.json`` / ``.txt`` / ``.backup`` files the archiver
        also sweeps have none, and a binary ``.backup`` cannot even be
        read as UTF-8 — gating them would make them unarchivable.
        """
        (temp_pkg_path / "pyproject.toml.backup").write_bytes(b"\x00\x01\x02binary")

        archivable = documentation_cleanup_service._detect_archivable_files()

        assert "pyproject.toml.backup" in {f.name for f in archivable}


class TestEndToEndSurvival:
    """A governed document survives a real cleanup run.

    The unit tests exercise the detector in isolation. This one runs the
    whole phase — detect, back up, move — and checks that the document
    is still on disk afterwards, which is the property the mahavishnu
    incident was about: a plan that was "archived" into a gitignored
    directory was simply gone from the repository.
    """

    def test_a_complete_plan_survives_a_real_cleanup(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        plan = temp_pkg_path / "2026-10-19-example-implementation.md"
        plan.write_text(
            "---\nstatus: complete\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

        result = documentation_cleanup_service.cleanup_documentation()

        assert result.success
        assert plan.exists(), "a governed document must not be moved"
        assert result.files_moved == 0

    def test_a_shipped_plan_is_archived_by_a_real_cleanup(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        plan = temp_pkg_path / "2026-10-19-example-implementation.md"
        plan.write_text(
            "---\nstatus: shipped\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

        result = documentation_cleanup_service.cleanup_documentation()

        assert result.success
        assert result.files_moved == 1
        assert not plan.exists()


class TestSingleChokePoint:
    """Pin the shape that makes the gate unbypassable.

    The lifecycle gate is applied at exactly one place. That property is
    what makes it safe: a path added outside it would bypass the rule
    silently, and no test of behaviour would notice until a governed
    document vanished from the repository.
    """

    @staticmethod
    def _module_source() -> str:
        from crackerjack.services import documentation_cleanup

        return Path(documentation_cleanup.__file__).read_text(encoding="utf-8")

    @staticmethod
    def _callers(source: str, attribute: str) -> dict[str, list[int]]:
        """Map each function name to the lines where it calls ``attribute``."""
        tree = ast.parse(source)
        callers: dict[str, list[int]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == attribute
                ):
                    callers.setdefault(node.name, []).append(child.lineno)
        return callers

    def test_only_the_cleanup_moves_files(self) -> None:
        """``_move_files_to_archive`` has exactly one caller."""
        callers = self._callers(self._module_source(), "_move_files_to_archive")

        assert set(callers) == {"cleanup_documentation"}
        assert len(callers["cleanup_documentation"]) == 1

    def test_the_mover_takes_its_list_from_the_gated_detector(self) -> None:
        """The mover's file list comes from the gated detector."""
        callers = self._callers(self._module_source(), "_detect_archivable_files")

        assert set(callers) == {"cleanup_documentation"}

    def test_the_candidate_list_has_one_consumer(self) -> None:
        """Only the gated detector reads the candidate list.

        A second consumer of ``get_archival_candidates`` would be a
        second path to the archive, and therefore a second way to skip
        the gate.
        """
        callers = self._callers(self._module_source(), "get_archival_candidates")

        assert set(callers) == {"_detect_archivable_files"}

    def test_the_legacy_fallback_has_one_caller(self) -> None:
        """Only the gated detector reads the legacy fallback's candidates.

        The fallback returns candidates with no gate of its own. A second
        caller would take that ungated list straight to the archive.
        """
        callers = self._callers(
            self._module_source(), "_detect_archivable_files_legacy"
        )

        assert set(callers) == {"_detect_archivable_files"}

    def test_no_other_module_reaches_the_archive(self) -> None:
        """Nothing outside the cleanup service can move a document.

        The gate protects a governed document only if every path to the
        archive passes through it. A new module that asked the
        categorizer for candidates, or composed an archive path itself,
        would bypass the rule without failing any test above.
        """
        package_root = Path(documentation_cleanup.__file__).resolve().parent.parent
        offenders: dict[str, set[str]] = {}

        for source_path in package_root.rglob("*.py"):
            if "test" in source_path.parts:
                continue
            source = source_path.read_text(encoding="utf-8")
            for attribute in ("get_archival_candidates", "archive_target_path"):
                if f".{attribute}" not in source:
                    continue
                callers = self._callers(source, attribute)
                if not callers:
                    continue
                expected = (
                    {"_detect_archivable_files"}
                    if attribute == "get_archival_candidates"
                    else {"_move_files_to_archive"}
                )
                if set(callers) != expected:
                    offenders.setdefault(
                        str(source_path.relative_to(package_root)), set()
                    ).add(f"{attribute}: {sorted(callers)}")

        assert offenders == {}


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
        assert documentation_cleanup_service._matches_archive_patterns(
            "SPRINT1_PLAN.md"
        )
        assert documentation_cleanup_service._matches_archive_patterns(
            "PHASE2_SUMMARY.md"
        )
        assert documentation_cleanup_service._matches_archive_patterns("SPRINT3.md")

    def test_matches_archive_patterns_case_sensitive(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test that pattern matching is case-sensitive."""
        assert documentation_cleanup_service._matches_archive_patterns(
            "SPRINT1_PLAN.md"
        )
        assert not documentation_cleanup_service._matches_archive_patterns(
            "sprint1_plan.md"
        )
        assert not documentation_cleanup_service._matches_archive_patterns(
            "Sprint1_Plan.md"
        )

    def test_matches_archive_patterns_no_match(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """Test files that don't match any pattern."""
        assert not documentation_cleanup_service._matches_archive_patterns("README.md")
        assert not documentation_cleanup_service._matches_archive_patterns(
            "RANDOM_FILE.md"
        )


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


class TestDisplayCompletion:
    """Test completion output formatting."""

    def test_display_completion_success_omits_separator_bars(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        mock_console: Mock,
    ):
        """Test successful completion output without horizontal separators."""
        result = DocumentationCleanupResult(
            success=True,
            files_moved=5,
            files_preserved=3,
            summary="Files moved: 5\nFiles preserved: 3 (essential)",
        )

        documentation_cleanup_service._display_completion(result)

        printed = [call.args[0] for call in mock_console.print.call_args_list]
        assert "[green]✅ Documentation cleanup completed[/green]" in printed
        assert "\nFiles moved: 5\nFiles preserved: 3 (essential)" in printed
        assert not any("━" in message for message in printed)

    def test_display_completion_failure_omits_separator_bars(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        mock_console: Mock,
    ):
        """Test failure output without horizontal separators."""
        result = DocumentationCleanupResult(
            success=False,
            error_message="Permission denied",
        )

        documentation_cleanup_service._display_completion(result)

        printed = [call.args[0] for call in mock_console.print.call_args_list]
        assert "[red]❌ Documentation cleanup failed[/red]" in printed
        assert "Error: Permission denied" in printed
        assert not any("━" in message for message in printed)


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

    def test_validate_preconditions_allows_unrelated_git_changes(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        mock_git_service: Mock,
        temp_pkg_path: Path,
    ):
        """Test unrelated git changes do not block cleanup."""
        # Create archive directory
        archive_dir = temp_pkg_path / "docs" / "archive"
        archive_dir.mkdir(parents=True)

        # Create a file that should be archived
        plan_file = temp_pkg_path / "SPRINT1_PLAN.md"
        plan_file.touch()

        # Mock git service to return unrelated changes
        mock_git_service.get_changed_files = Mock(
            return_value=["crackerjack/services/patterns/formatting.py"]
        )

        is_valid, error_msg = documentation_cleanup_service._validate_preconditions()

        assert is_valid
        assert error_msg is None

    def test_validate_preconditions_allows_existing_archive_targets(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test validation still succeeds when an archive target already exists."""
        archive_dir = temp_pkg_path / "docs" / "archive"
        target_dir = archive_dir / "implementation-plans"
        target_dir.mkdir(parents=True)

        (temp_pkg_path / "SPRINT1_PLAN.md").touch()
        (target_dir / "SPRINT1_PLAN.md").touch()

        is_valid, error_msg = documentation_cleanup_service._validate_preconditions()

        assert is_valid
        assert error_msg is None

    def test_cleanup_renames_existing_archive_targets(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """Test cleanup archives duplicates without clobbering existing files."""
        # Per-area scheme: root files archive to `docs/.archive/<sub>/`.
        archive_dir = temp_pkg_path / "docs" / ".archive"
        target_dir = archive_dir / "implementation-plans"
        target_dir.mkdir(parents=True)

        source_file = temp_pkg_path / "SPRINT1_PLAN.md"
        source_file.write_text("new plan content")

        existing_target = target_dir / "SPRINT1_PLAN.md"
        existing_target.write_text("old archived content")

        result = documentation_cleanup_service.cleanup_documentation(dry_run=False)

        assert result.success
        assert result.files_moved == 1
        assert not source_file.exists()
        assert existing_target.exists()

        archived_matches = list(target_dir.glob("SPRINT1_PLAN*.md"))
        assert len(archived_matches) == 2
        assert any(path.name != "SPRINT1_PLAN.md" for path in archived_matches)


class TestGitIndexSync:
    """Regression tests for git-index sync after the disk move. The cleanup
    uses ``Path.replace`` (not ``git mv``) to physically move each file into
    its archive subdirectory. After the move, ``git rm`` must be called on
    the OLD/source path — the only one still tracked by git. Passing the
    new archive path makes git reply ``did not match any files`` because
    the archive path is untracked until the next ``git add``.
    """

    def test_rm_files_called_with_source_path_not_destination(
        self,
        temp_pkg_path: Path,
        mock_console: Mock,
        documentation_settings: DocumentationSettings,
    ):
        """Cleanup must pass ``file_path`` (source) to ``rm_files``, not the
        new archive target path. ``git rm`` only operates on tracked paths,
        so passing the untracked archive path is a no-op that surfaces as
        ``fatal: pathspec ... did not match any files``.
        """
        settings = CrackerjackSettings()
        settings.documentation = documentation_settings
        mock_git_service = Mock()

        service = DocumentationCleanup(
            console=mock_console,
            pkg_path=temp_pkg_path,
            git_service=mock_git_service,
            settings=settings,
        )

        source_file = temp_pkg_path / "SPRINT1_PLAN.md"
        source_file.write_text("plan content")

        result = service.cleanup_documentation(dry_run=False)

        assert result.success
        assert result.files_moved == 1

        # The git index sync must reference the source path (relative to
        # pkg_path), NOT the destination archive path. ``git rm`` can only
        # act on tracked paths, and the source is what was tracked.
        assert mock_git_service.rm_files.called
        rm_calls = mock_git_service.rm_files.call_args_list
        assert len(rm_calls) == 1
        rm_paths = rm_calls[0].args[0]
        assert rm_paths == ["SPRINT1_PLAN.md"]

        # Sanity-check: the archive destination must NOT have been passed.
        for call in rm_calls:
            for path in call.args[0]:
                assert ".archive" not in path, (
                    f"rm_files was passed the archive destination "
                    f"({path}); git rm cannot act on untracked paths"
                )

    def test_rm_files_called_for_per_area_source_path(
        self,
        temp_pkg_path: Path,
        mock_console: Mock,
        documentation_settings: DocumentationSettings,
    ):
        """Per-area archive scheme: a file in ``docs/plans/`` archives to
        ``docs/plans/.archive/<subdir>/``. ``rm_files`` must still receive
        the source (``docs/plans/...``), never the new archive path.
        """
        settings = CrackerjackSettings()
        settings.documentation = documentation_settings
        mock_git_service = Mock()

        service = DocumentationCleanup(
            console=mock_console,
            pkg_path=temp_pkg_path,
            git_service=mock_git_service,
            settings=settings,
        )

        # File living in a per-area scan root.
        plans_dir = temp_pkg_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        source_file = plans_dir / "PROTOCOL_DOCUMENTATION_PLAN.md"
        source_file.write_text("plan content")

        result = service.cleanup_documentation(dry_run=False)

        assert result.success
        assert result.files_moved == 1

        rm_calls = mock_git_service.rm_files.call_args_list
        assert len(rm_calls) == 1
        rm_paths = rm_calls[0].args[0]
        assert rm_paths == ["docs/plans/PROTOCOL_DOCUMENTATION_PLAN.md"]

        for call in rm_calls:
            for path in call.args[0]:
                assert ".archive" not in path, (
                    f"rm_files was passed the archive destination "
                    f"({path}); git rm cannot act on untracked paths"
                )


class TestTheGateHoldBacksAreVisible:
    """A held file must read as *held*, not as never found.

    The gate's whole job is to leave a governed document in the tree.
    When it did that silently, the cleanup reported "no files to
    cleanup - all files are essential" — which is false for a file
    that matched an archival category and was held. The operator
    could not tell a mis-declared lifecycle from "there was nothing
    to do", and the plan's observability contract asked for the
    declined files to be reported.
    """

    @staticmethod
    def _write_held(path: Path) -> None:
        path.write_text(
            "---\nstatus: complete\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

    def test_a_held_file_is_named_in_the_summary(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        self._write_held(temp_pkg_path / "2026-10-19-example-implementation.md")

        result = documentation_cleanup_service.cleanup_documentation(dry_run=True)

        assert result.success is True
        assert result.gated_files == ["2026-10-19-example-implementation.md"]
        assert "held by the lifecycle gate" in result.summary
        assert "2026-10-19-example-implementation.md" in result.summary
        assert "all files are essential" not in result.summary

    def test_nothing_gated_keeps_the_plain_summary(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        result = documentation_cleanup_service.cleanup_documentation(dry_run=True)

        assert result.gated_files == []
        assert result.summary == "No files to cleanup - all files are essential"

    def test_the_held_files_are_displayed(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
        mock_console: Mock,
    ):
        self._write_held(temp_pkg_path / "2026-10-19-example-implementation.md")

        documentation_cleanup_service.cleanup_documentation(dry_run=True)

        printed = "\n".join(
            call.args[0] for call in mock_console.print.call_args_list
        )
        assert "held by the lifecycle gate" in printed
        assert "2026-10-19-example-implementation.md" in printed

    def test_a_run_that_moves_files_still_reports_the_held_ones(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """The count belongs in the summary of a run that did move things."""
        self._write_held(temp_pkg_path / "2026-10-19-example-implementation.md")
        (temp_pkg_path / "2026-10-20-example-implementation.md").write_text(
            "---\nstatus: shipped\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

        result = documentation_cleanup_service.cleanup_documentation(dry_run=True)

        assert result.success is True
        assert result.gated_files == ["2026-10-19-example-implementation.md"]
        assert "Files held by the lifecycle gate: 1" in result.summary


class TestTheGateMessageNamesTheConfiguredCriterion:
    """The message has to name the criterion the gate actually applies.

    The gate's vocabulary is configurable: a repo with a different
    lifecycle overrides ``archivable_statuses``. A message that names
    one status is then false, and it is false in the way that costs
    the most: it names the status to *set*, so an operator who sets
    ``status: shipped`` in a repo whose criterion is ``complete`` finds
    the document still not archivable.
    """

    @staticmethod
    def _write_held(path: Path) -> None:
        path.write_text(
            "---\nstatus: draft\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_status(path: Path, status: str) -> None:
        path.write_text(
            f"---\nstatus: {status}\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

    @staticmethod
    def _service_with_statuses(
        base: DocumentationCleanup,
        statuses: list[str],
    ) -> DocumentationCleanup:
        """A service whose categorizer *applies* ``statuses``.

        The vocabulary is snapshotted when the categorizer is built, so
        the settings have to carry the override **before** construction.
        A service built with the default criterion and then mutated still
        applies the default -- so a message that read the live settings
        would name a criterion the gate never used.
        """
        base.settings.documentation.archivable_statuses = statuses
        return DocumentationCleanup(
            console=base.console,
            pkg_path=base.pkg_path,
            git_service=base.git_service,
            settings=base.settings,
        )

    def test_the_default_criterion_names_the_default_status(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        self._write_held(temp_pkg_path / "2026-10-19-example-implementation.md")

        result = documentation_cleanup_service.cleanup_documentation(dry_run=True)

        assert "status is not 'shipped'" in result.summary

    def test_the_message_names_the_criterion_the_gate_applied(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """A criterion changed after construction must not change the message.

        The categorizer snapshots the configured vocabulary when the
        cleanup is built, so a later mutation changes the settings but
        not the gate. A message that read the live settings would then
        name a criterion the gate never applied -- which is the exact
        false statement this gate exists to avoid, and it points the
        operator at the wrong status to set.
        """
        documentation_cleanup_service.settings.documentation.archivable_statuses = [
            "complete"
        ]
        self._write_held(temp_pkg_path / "2026-10-19-example-implementation.md")

        result = documentation_cleanup_service.cleanup_documentation(dry_run=True)

        assert "status is not 'shipped'" in result.summary
        assert "complete" not in result.summary

    def test_an_overridden_criterion_names_the_override(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """The override has to reach the gate, not only the message.

        The document declares ``status: shipped``. Under the default
        criterion it would be archived, so holding it proves the gate
        really applied the override rather than the default.
        """
        service = self._service_with_statuses(
            documentation_cleanup_service, ["complete"]
        )
        self._write_status(
            temp_pkg_path / "2026-10-19-example-implementation.md", "shipped"
        )

        result = service.cleanup_documentation(dry_run=True)

        assert result.gated_files, "the gate held nothing - it never applied"
        assert "status is not 'complete'" in result.summary
        assert "shipped" not in result.summary

    def test_several_configured_statuses_are_all_named(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        service = self._service_with_statuses(
            documentation_cleanup_service, ["complete", "shipped"]
        )
        self._write_held(temp_pkg_path / "2026-10-19-example-implementation.md")

        result = service.cleanup_documentation(dry_run=True)

        assert "status is not one of 'complete', 'shipped'" in result.summary

    def test_the_named_criterion_is_normalised_like_the_gate(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """The message names the status the gate actually compares against.

        The categorizer normalises the configured vocabulary the same way
        it normalises a document's status, so a configuration written as
        ``"Shipped"`` matches a ``status: shipped`` document. A message
        naming the un-normalised spelling would send the operator to
        write a status the gate does not accept.
        """
        service = self._service_with_statuses(
            documentation_cleanup_service, ["Shipped"]
        )
        self._write_held(temp_pkg_path / "2026-10-19-example-implementation.md")

        result = service.cleanup_documentation(dry_run=True)

        assert "status is not 'shipped'" in result.summary

    def test_an_empty_criterion_says_so_without_naming_a_status(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        """An empty vocabulary must not produce a message naming a status.

        With nothing archivable, the gate holds every governed document.
        The message has to say the criterion is empty rather than name
        some status -- there is no status to set that would help.
        """
        service = self._service_with_statuses(documentation_cleanup_service, [])
        self._write_held(temp_pkg_path / "2026-10-19-example-implementation.md")

        result = service.cleanup_documentation(dry_run=True)

        assert "status is not archivable" in result.summary


class TestTheHeldFileIsNamedForTheOperator:
    """A held file is named so the operator can find it.

    Two documents with the same name in different directories are two
    files, so the name alone is ambiguous -- the label has to carry the
    path relative to the package root.
    """

    def test_a_held_file_is_named_by_its_path_under_the_package(
        self,
        documentation_cleanup_service: DocumentationCleanup,
        temp_pkg_path: Path,
    ):
        nested = temp_pkg_path / "docs" / "plans"
        nested.mkdir(parents=True)
        (nested / "2026-10-19-example-implementation.md").write_text(
            "---\nstatus: draft\nrole: implementation\n---\n\n# Plan\n",
            encoding="utf-8",
        )

        result = documentation_cleanup_service.cleanup_documentation(dry_run=True)

        assert "docs/plans/2026-10-19-example-implementation.md" in result.summary

    def test_a_file_outside_the_package_is_named_by_its_name_alone(
        self,
        documentation_cleanup_service: DocumentationCleanup,
    ):
        """A path outside the package root has no relative form.

        ``relative_to`` raises for such a path, and the label falls back
        to the file's name -- a degraded label is better than a report
        that raises while naming what it held back.
        """
        outside = Path("/tmp/elsewhere/2026-10-19-example-implementation.md")

        label = documentation_cleanup_service._gated_label(outside)

        assert label == "2026-10-19-example-implementation.md"
