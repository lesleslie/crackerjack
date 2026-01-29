from __future__ import annotations

import logging
import shutil
import tarfile
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

from rich.console import Console

from crackerjack.models.protocols import (
    ConsoleInterface as ConsoleProtocol,
)
from crackerjack.models.protocols import (
    GitInterface,
)
from crackerjack.services.backup_service import BackupMetadata, PackageBackupService
from crackerjack.services.doc_categorizer import DocumentationCategorizer
from crackerjack.services.secure_path_utils import (
    AtomicFileOperations,
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
    success: bool
    files_moved: int = 0
    files_preserved: int = 0
    backup_metadata: BackupMetadata | None = None
    summary: str = ""
    error_message: str | None = None
    archived_files: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ArchiveMapping:
    pattern: str
    subdirectory: str


class DocumentationCleanup:
    def __init__(
        self,
        console: ConsoleProtocol | None = None,
        pkg_path: Path | None = None,
        git_service: GitInterface | None = None,
        settings: CrackerjackSettings | None = None,
    ) -> None:
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()
        self.git_service = git_service

        if settings is None:
            from crackerjack.config import load_settings
            from crackerjack.config.settings import CrackerjackSettings

            settings = load_settings(CrackerjackSettings)

        self.settings = settings
        self.security_logger = get_security_logger()

        self.categorizer = DocumentationCategorizer(self.pkg_path)

        self._archive_mappings = self._build_archive_mappings()

        self.backup_service = PackageBackupService(
            backup_root=self.pkg_path / "docs" / ".backups"
        )

        self.atomic_ops = AtomicFileOperations()

    def cleanup_documentation(
        self,
        dry_run: bool = False,
    ) -> DocumentationCleanupResult:
        result = DocumentationCleanupResult(success=False)

        try:
            archivable_files = self._detect_archivable_files()

            if not archivable_files:
                result.success = True
                result.summary = "No files to cleanup - all files are essential"
                self._display_completion(result)
                return result

            is_valid, error_msg = self._validate_preconditions()
            if not is_valid:
                result.success = False
                result.error_message = error_msg
                return result

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

            files_moved, archived_files = self._move_files_to_archive(
                archivable_files,
                dry_run=dry_run,
            )

            result.files_moved = files_moved
            result.archived_files = archived_files

            essential_count = self._count_essential_files()
            result.files_preserved = essential_count
            result.summary = self._generate_summary(result)

            result.success = True

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
        try:
            self.console.print(
                f"[cyan]ℹ️[/cyan] Rolling back cleanup: {backup_metadata.backup_id}"
            )

            if not backup_metadata.backup_directory.exists():
                self.console.print(
                    f"[red]❌[/red] Backup directory not found: {backup_metadata.backup_directory}"
                )
                return False

            backup_archive = backup_metadata.backup_directory / "backup.tar.gz"
            if not backup_archive.exists():
                self.console.print(
                    f"[red]❌[/red] Backup archive not found: {backup_archive}"
                )
                return False

            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                with tarfile.open(backup_archive, "r:gz") as tar:
                    tar.extractall(temp_path)

                restored = 0
                for file_path in temp_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(temp_path)
                        target_path = self.pkg_path / relative_path

                        target_path.parent.mkdir(parents=True, exist_ok=True)

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
        try:
            return self.categorizer.get_archivable_files()

        except Exception as e:
            logger.exception(f"Regex-based file detection failed: {e}")

            return self._detect_archivable_files_legacy()

    def _detect_archivable_files_legacy(self) -> list[Path]:
        try:
            md_files = list(self.pkg_path.glob("*.md"))
            archivable = []

            for md_file in md_files:
                filename = md_file.name

                if self._is_essential_file(filename):
                    continue

                if self._matches_archive_patterns(filename):
                    archivable.append(md_file)

            return archivable

        except Exception as e:
            logger.exception(f"Legacy file detection failed: {e}")
            return []

    def _is_essential_file(self, filename: str) -> bool:
        essential_files = self.settings.documentation.essential_files
        return filename in essential_files

    def _matches_archive_patterns(self, filename: str) -> bool:
        archive_patterns = self.settings.documentation.archive_patterns

        for pattern in archive_patterns:
            if fnmatch(filename, pattern):
                return True

        return False

    def _build_archive_mappings(self) -> list[ArchiveMapping]:
        mappings = []

        subdirectories = self.settings.documentation.archive_subdirectories

        for pattern, subdirectory in subdirectories.items():
            mappings.append(ArchiveMapping(pattern=pattern, subdirectory=subdirectory))

        return mappings

    def _determine_archive_subdirectory(self, filename: str) -> str | None:
        try:
            result = self.categorizer.get_archive_subdirectory(Path(filename))
            if result:
                return result
        except Exception as e:
            logger.debug(f"Regex categorization failed for {filename}: {e}")

        for mapping in self._archive_mappings:
            if fnmatch(filename, mapping.pattern):
                return mapping.subdirectory

        return None

    def _validate_preconditions(self) -> tuple[bool, str | None]:
        archive_dir = self.pkg_path / "docs" / "archive"
        if not archive_dir.exists():
            try:
                archive_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return False, f"Cannot create archive directory: {e}"

        return True, None

    def _create_backup(self, files: list[Path]) -> BackupMetadata | None:
        try:
            backup_id = self._generate_backup_id()
            if self.backup_service.backup_root is None:
                return None
            backup_dir = self.backup_service.backup_root / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_archive = backup_dir / "backup.tar.gz"

            with tarfile.open(backup_archive, "w:gz") as tar:
                for file_path in files:
                    if file_path.exists():
                        tar.add(file_path, arcname=file_path.name)

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
        files_moved = 0
        archived_files: dict[str, list[str]] = {}

        for file_path in files:
            if not file_path.exists():
                continue

            subdirectory = self._determine_archive_subdirectory(file_path.name)

            if subdirectory is None:
                subdirectory = "uncategorized"

            target_dir = self.pkg_path / "docs" / "archive" / subdirectory
            target_path = target_dir / file_path.name

            if dry_run:
                self.console.print(
                    f"[yellow]Would move:[/yellow] {file_path.name} → {subdirectory}/"
                )
            else:
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)

                    file_path.replace(target_path)

                    files_moved += 1

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
        essential_files = self.settings.documentation.essential_files
        md_files = list(self.pkg_path.glob("*.md"))

        return sum(1 for f in md_files if f.name in essential_files)

    def _generate_summary(self, result: DocumentationCleanupResult) -> str:
        lines = [
            f"Files moved: {result.files_moved}",
            f"Files preserved: {result.files_preserved} (essential)",
        ]

        if result.backup_metadata:
            lines.append(
                f"Backup location: {result.backup_metadata.backup_directory.relative_to(self.pkg_path)}"
            )

        if result.archived_files:
            lines.append("\nArchive breakdown:")
            for subdir, files in sorted(result.archived_files.items()):
                lines.append(f"  {subdir}/: {len(files)} files")

        return "\n".join(lines)

    def _generate_backup_id(self) -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def _display_completion(self, result: DocumentationCleanupResult) -> None:
        sep = "━" * 60

        if result.success:
            self.console.print(f"\n{sep}")
            if result.files_moved > 0:
                self.console.print("[green]✅ Documentation cleanup completed[/green]")
                self.console.print(f"\n{result.summary}")
            else:
                self.console.print(
                    "[cyan]ℹ️ Documentation cleanup: No files to move[/cyan]"
                )
            self.console.print(f"{sep}\n")
        else:
            self.console.print(f"\n{sep}")
            self.console.print("[red]❌ Documentation cleanup failed[/red]")
            if result.error_message:
                self.console.print(f"Error: {result.error_message}")
            self.console.print(f"{sep}\n")
