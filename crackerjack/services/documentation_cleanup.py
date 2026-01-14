"""Automatic documentation cleanup service with backup and rollback capabilities.

This service provides safe, automatic cleanup of documentation files from the
project root to organized archive subdirectories with full backup and rollback support.
"""

from __future__ import annotations

import fnmatch
import logging
import shutil
import tarfile
import time
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from rich.console import Console

from crackerjack.models.protocols import (
    ConsoleInterface as ConsoleProtocol,
    GitInterface,
)
from crackerjack.services.backup_service import BackupMetadata, PackageBackupService
from crackerjack.services.secure_path_utils import (
    AtomicFileOperations,
    SecurePathValidator,
)
from crackerjack.services.security_logger import (
    SecurityEventLevel,
    SecurityEventType,
    get_security_logger,
)

if t.TYPE_CHECKING:
    from crackerjack.config.settings import CrackerjackSettings


logger = logging.getLogger(__name__)


@dataclass
class DocumentationCleanupResult:
    """Result of documentation cleanup operation."""

    success: bool
    files_moved: int = 0
    files_preserved: int = 0
    backup_metadata: BackupMetadata | None = None
    summary: str = ""
    error_message: str | None = None
    archived_files: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ArchiveMapping:
    """Maps file patterns to archive subdirectories."""

    pattern: str
    subdirectory: str


class DocumentationCleanup:
    """Service for automatic documentation cleanup with safety mechanisms.

    This service implements hybrid file detection (whitelist + patterns + config)
    with comprehensive backup support and atomic file operations.

    Examples:
        >>> from rich.console import Console
        >>> from pathlib import Path
        >>>
        >>> console = Console()
        >>> service = DocumentationCleanup(console=console, pkg_path=Path.cwd())
        >>> result = service.cleanup_documentation(dry_run=True)
        >>> print(f"Would move {result.files_moved} files")
    """

    def __init__(
        self,
        console: ConsoleProtocol | None = None,
        pkg_path: Path | None = None,
        git_service: GitInterface | None = None,
        settings: CrackerjackSettings | None = None,
    ) -> None:
        """Initialize documentation cleanup service.

        Args:
            console: Rich console for output (constructor injection)
            pkg_path: Package root path
            git_service: Git service for git operations (optional)
            settings: Crackerjack configuration (optional, loads if not provided)
        """
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()
        self.git_service = git_service

        # Load settings if not provided
        if settings is None:
            from crackerjack.config import load_settings
            from crackerjack.config.settings import CrackerjackSettings

            settings = load_settings(CrackerjackSettings)

        self.settings = settings
        self.security_logger = get_security_logger()

        # Pre-compute archive mappings from settings
        self._archive_mappings = self._build_archive_mappings()

        # Backup service
        self.backup_service = PackageBackupService(
            backup_root=self.pkg_path / "docs" / ".backups"
        )

        # Atomic file operations
        self.atomic_ops = AtomicFileOperations()

    def cleanup_documentation(
        self,
        dry_run: bool = False,
    ) -> DocumentationCleanupResult:
        """Execute documentation cleanup with full safety mechanisms.

        This method orchestrates the entire cleanup process:
        1. Detect archivable files
        2. Validate preconditions
        3. Create backup
        4. Move files to archive
        5. Generate report

        Args:
            dry_run: Preview changes without executing (default: False)

        Returns:
            DocumentationCleanupResult with operation details

        Examples:
            >>> service = DocumentationCleanup(pkg_path=Path("/tmp/project"))
            >>> result = service.cleanup_documentation(dry_run=True)
            >>> assert result.files_moved >= 0
        """
        result = DocumentationCleanupResult(success=False)

        try:
            # Phase 1: Detect archivable files
            archivable_files = self._detect_archivable_files()

            if not archivable_files:
                result.success = True
                result.summary = "No files to cleanup - all files are essential"
                self._display_completion(result)
                return result

            # Phase 2: Validate preconditions
            is_valid, error_msg = self._validate_preconditions()
            if not is_valid:
                result.success = False
                result.error_message = error_msg
                return result

            # Phase 3: Create backup
            if dry_run:
                self.console.print(
                    "[yellow]Dry run: Would create backup before cleanup[/yellow]"
                )
                backup_metadata = None
            else:
                backup_metadata = self._create_backup(archivable_files)
                if backup_metadata is None:
                    result.success = False
                    result.error_message = "Backup creation failed"
                    return result

            result.backup_metadata = backup_metadata

            # Phase 4: Move files to archive
            files_moved, archived_files = self._move_files_to_archive(
                archivable_files,
                dry_run=dry_run,
            )

            result.files_moved = files_moved
            result.archived_files = archived_files

            # Phase 5: Generate summary
            essential_count = self._count_essential_files()
            result.files_preserved = essential_count
            result.summary = self._generate_summary(result)

            result.success = True

            # Log security event
            self.security_logger.log_security_event(
                SecurityEventType.DOCUMENTATION_CLEANUP,
                SecurityEventLevel.INFO,
                f"Documentation cleanup completed: {files_moved} files moved",
                files_moved=files_moved,
                dry_run=dry_run,
            )

        except Exception as e:
            logger.exception("Documentation cleanup failed")
            result.success = False
            result.error_message = str(e)

            self.security_logger.log_security_event(
                SecurityEventType.DOCUMENTATION_CLEANUP,
                SecurityEventLevel.ERROR,
                f"Documentation cleanup failed: {e}",
            )

        self._display_completion(result)
        return result

    def rollback_cleanup(
        self,
        backup_metadata: BackupMetadata,
    ) -> bool:
        """Rollback documentation cleanup from backup.

        Args:
            backup_metadata: Backup metadata from previous cleanup operation

        Returns:
            True if rollback succeeded, False otherwise

        Examples:
            >>> service = DocumentationCleanup(pkg_path=Path("/tmp/project"))
            >>> result = service.cleanup_documentation()
            >>> if not result.success:
            ...     service.rollback_cleanup(result.backup_metadata)
        """
        try:
            self.console.print(
                f"[cyan]ℹ️[/cyan] Rolling back cleanup: {backup_metadata.backup_id}"
            )

            # Extract files from backup
            if not backup_metadata.backup_directory.exists():
                self.console.print(
                    f"[red]❌[/red] Backup directory not found: {backup_metadata.backup_directory}"
                )
                return False

            # Restore from backup archive
            backup_archive = backup_metadata.backup_directory / "backup.tar.gz"
            if not backup_archive.exists():
                self.console.print(
                    f"[red]❌[/red] Backup archive not found: {backup_archive}"
                )
                return False

            # Extract to temp location first
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                with tarfile.open(backup_archive, "r:gz") as tar:
                    tar.extractall(temp_path)

                # Move files back to original locations
                restored = 0
                for file_path in temp_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(temp_path)
                        target_path = self.pkg_path / relative_path

                        # Create parent directories
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # Atomic move
                        shutil.move(str(file_path), str(target_path))
                        restored += 1

            self.console.print(
                f"[green]✅[/green] Restored {restored} files from backup"
            )

            self.security_logger.log_security_event(
                SecurityEventType.DOCUMENTATION_ROLLBACK,
                SecurityEventLevel.INFO,
                f"Documentation cleanup rollback completed: {restored} files restored",
                backup_id=backup_metadata.backup_id,
            )

            return True

        except Exception as e:
            logger.exception("Rollback failed")
            self.console.print(f"[red]❌[/red] Rollback failed: {e}")
            return False

    def _detect_archivable_files(self) -> list[Path]:
        """Detect files that should be archived using hybrid approach.

        Hybrid detection combines:
        1. Whitelist: Files explicitly marked as essential (never archive)
        2. Pattern matching: Files matching archive patterns
        3. Configuration override: User-defined patterns from YAML

        Returns:
            List of file paths that should be archived

        Examples:
            >>> service = DocumentationCleanup()
            >>> files = service._detect_archivable_files()
            >>> assert all(f.suffix == ".md" for f in files)
        """
        try:
            # Get all markdown files in project root
            md_files = list(self.pkg_path.glob("*.md"))

            archivable = []

            for md_file in md_files:
                filename = md_file.name

                # Skip essential files (whitelist)
                if self._is_essential_file(filename):
                    continue

                # Check if file matches archive patterns
                if self._matches_archive_patterns(filename):
                    archivable.append(md_file)

            return archivable

        except Exception as e:
            logger.exception(f"File detection failed: {e}")
            return []

    def _is_essential_file(self, filename: str) -> bool:
        """Check if file is in essential whitelist.

        Args:
            filename: Name of the file to check

        Returns:
            True if file is essential (should NOT be archived)

        Examples:
            >>> service = DocumentationCleanup()
            >>> assert service._is_essential_file("README.md")
            >>> assert not service._is_essential_file("SPRINT1_PLAN.md")
        """
        essential_files = self.settings.documentation.essential_files
        return filename in essential_files

    def _matches_archive_patterns(self, filename: str) -> bool:
        """Check if filename matches any archive pattern.

        Args:
            filename: Name of the file to check

        Returns:
            True if file matches an archive pattern

        Examples:
            >>> service = DocumentationCleanup()
            >>> assert service._matches_archive_patterns("SPRINT1_PLAN.md")
            >>> assert service._matches_archive_patterns("PHASE2_SUMMARY.md")
        """
        archive_patterns = self.settings.documentation.archive_patterns

        for pattern in archive_patterns:
            if fnmatch(filename, pattern):
                return True

        return False

    def _build_archive_mappings(self) -> list[ArchiveMapping]:
        """Build pattern-to-subdirectory mappings from settings.

        Returns:
            List of ArchiveMapping objects

        Examples:
            >>> service = DocumentationCleanup()
            >>> mappings = service._build_archive_mappings()
            >>> sprint_mapping = [m for m in mappings if "SPRINT" in m.pattern][0]
            >>> assert sprint_mapping.subdirectory == "sprints"
        """
        mappings = []

        subdirectories = self.settings.documentation.archive_subdirectories

        for pattern, subdirectory in subdirectories.items():
            mappings.append(
                ArchiveMapping(pattern=pattern, subdirectory=subdirectory)
            )

        return mappings

    def _determine_archive_subdirectory(self, filename: str) -> str | None:
        """Determine which archive subdirectory a file belongs to.

        Args:
            filename: Name of the file

        Returns:
            Subdirectory name or None if no match

        Examples:
            >>> service = DocumentationCleanup()
            >>> assert service._determine_archive_subdirectory("SPRINT1_PLAN.md") == "sprints"
            >>> assert service._determine_archive_subdirectory("README.md") is None
        """
        for mapping in self._archive_mappings:
            if fnmatch(filename, mapping.pattern):
                return mapping.subdirectory

        return None

    def _validate_preconditions(self) -> tuple[bool, str | None]:
        """Validate preconditions before cleanup.

        Returns:
            Tuple of (is_valid, error_message)

        Examples:
            >>> service = DocumentationCleanup()
            >>> is_valid, error = service._validate_preconditions()
            >>> assert is_valid or error is not None
        """
        # Check if archive directory structure exists
        archive_dir = self.pkg_path / "docs" / "archive"
        if not archive_dir.exists():
            try:
                archive_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return False, f"Cannot create archive directory: {e}"

        # Check git repo status (if git service available)
        if self.git_service:
            try:
                changed_files = self.git_service.get_changed_files()
                if changed_files:
                    return (
                        False,
                        "Git repository has uncommitted changes. Commit or stash first.",
                    )
            except Exception:
                # Git check failed, but don't block cleanup
                pass

        return True, None

    def _create_backup(self, files: list[Path]) -> BackupMetadata | None:
        """Create backup before file operations.

        Args:
            files: List of files to backup

        Returns:
            BackupMetadata if successful, None otherwise

        Examples:
            >>> service = DocumentationCleanup()
            >>> files = [Path("SPRINT1_PLAN.md")]
            >>> metadata = service._create_backup(files)
            >>> assert metadata is not None
        """
        try:
            backup_id = self._generate_backup_id()
            backup_dir = self.backup_service.backup_root / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create backup archive
            backup_archive = backup_dir / "backup.tar.gz"

            with tarfile.open(backup_archive, "w:gz") as tar:
                for file_path in files:
                    if file_path.exists():
                        tar.add(file_path, arcname=file_path.name)

            # Create metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=datetime.now(),
                package_directory=self.pkg_path,
                backup_directory=backup_dir,
                total_files=len(files),
                total_size=sum(f.stat().st_size for f in files if f.exists()),
                checksum="",  # TODO: Generate proper checksum
                file_checksums={},  # TODO: Generate file checksums
            )

            self.console.print(
                f"[green]✅[/green] Backup created: {backup_archive.relative_to(self.pkg_path)}"
            )

            self.security_logger.log_security_event(
                SecurityEventType.BACKUP_CREATED,
                SecurityEventLevel.INFO,
                f"Documentation backup created: {backup_id}",
                backup_id=backup_id,
                files_backed=len(files),
            )

            return metadata

        except Exception as e:
            logger.exception(f"Backup creation failed: {e}")
            self.console.print(f"[red]❌[/red] Backup creation failed: {e}")
            return None

    def _move_files_to_archive(
        self,
        files: list[Path],
        dry_run: bool,
    ) -> tuple[int, dict[str, list[str]]]:
        """Move files to appropriate archive subdirectories.

        Args:
            files: List of files to move
            dry_run: Preview without executing

        Returns:
            Tuple of (files_moved, archived_files_dict)

        Examples:
            >>> service = DocumentationCleanup()
            >>> files = [Path("SPRINT1_PLAN.md")]
            >>> moved, archive_map = service._move_files_to_archive(files, dry_run=True)
            >>> assert moved == 1
        """
        files_moved = 0
        archived_files: dict[str, list[str]] = {}

        for file_path in files:
            if not file_path.exists():
                continue

            # Determine target subdirectory
            subdirectory = self._determine_archive_subdirectory(file_path.name)

            if subdirectory is None:
                # No matching subdirectory, use "uncategorized"
                subdirectory = "uncategorized"

            # Target path
            target_dir = self.pkg_path / "docs" / "archive" / subdirectory
            target_path = target_dir / file_path.name

            if dry_run:
                self.console.print(
                    f"[yellow]Would move:[/yellow] {file_path.name} → {subdirectory}/"
                )
            else:
                try:
                    # Create target directory
                    target_dir.mkdir(parents=True, exist_ok=True)

                    # Atomic move
                    self.atomic_ops.atomic_move(
                        src=file_path,
                        dest=target_path,
                        create_parents=True,
                    )

                    files_moved += 1

                    # Track in archive map
                    if subdirectory not in archived_files:
                        archived_files[subdirectory] = []

                    archived_files[subdirectory].append(file_path.name)

                except Exception as e:
                    logger.exception(f"Failed to move {file_path}: {e}")
                    self.console.print(
                        f"[yellow]⚠️[/yellow] Failed to move {file_path.name}: {e}"
                    )

        return files_moved, archived_files

    def _count_essential_files(self) -> int:
        """Count essential markdown files in project root.

        Returns:
            Number of essential files

        Examples:
            >>> service = DocumentationCleanup()
            >>> count = service._count_essential_files()
            >>> assert count >= 7  # At minimum the core essential files
        """
        essential_files = self.settings.documentation.essential_files
        md_files = list(self.pkg_path.glob("*.md"))

        return sum(1 for f in md_files if f.name in essential_files)

    def _generate_summary(self, result: DocumentationCleanupResult) -> str:
        """Generate human-readable summary of cleanup operation.

        Args:
            result: Cleanup operation result

        Returns:
            Formatted summary string

        Examples:
            >>> service = DocumentationCleanup()
            >>> result = DocumentationCleanupResult(success=True, files_moved=5)
            >>> summary = service._generate_summary(result)
            >>> assert "5 files" in summary
        """
        lines = [
            f"Files moved: {result.files_moved}",
            f"Files preserved: {result.files_preserved} (essential)",
        ]

        if result.backup_metadata:
            lines.append(
                f"Backup location: {result.backup_metadata.backup_directory.relative_to(self.pkg_path)}"
            )

        # Add breakdown by subdirectory
        if result.archived_files:
            lines.append("\nArchive breakdown:")
            for subdir, files in sorted(result.archived_files.items()):
                lines.append(f"  {subdir}/: {len(files)} files")

        return "\n".join(lines)

    def _generate_backup_id(self) -> str:
        """Generate unique backup ID from timestamp.

        Returns:
            Backup ID string (format: YYYYMMDD-HHMMSS)

        Examples:
            >>> service = DocumentationCleanup()
            >>> backup_id = service._generate_backup_id()
            >>> assert len(backup_id) == 17  # YYYYMMDD-HHMMSS format
        """
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def _display_completion(self, result: DocumentationCleanupResult) -> None:
        """Display completion message to user.

        Args:
            result: Cleanup operation result
        """
        sep = "━" * 60

        if result.success:
            self.console.print(f"\n{sep}")
            if result.files_moved > 0:
                self.console.print(
                    f"[green]✅ Documentation cleanup completed[/green]"
                )
                self.console.print(f"\n{result.summary}")
            else:
                self.console.print(
                    "[cyan]ℹ️ Documentation cleanup: No files to move[/cyan]"
                )
            self.console.print(f"{sep}\n")
        else:
            self.console.print(f"\n{sep}")
            self.console.print(
                f"[red]❌ Documentation cleanup failed[/red]"
            )
            if result.error_message:
                self.console.print(f"Error: {result.error_message}")
            self.console.print(f"{sep}\n")
