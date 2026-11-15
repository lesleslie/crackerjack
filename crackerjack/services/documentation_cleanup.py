from __future__ import annotations

import hashlib
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
from crackerjack.utils.path_redaction import redact_path

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
    #: The candidates the lifecycle gate held back, by path relative
    #: to the package root. A file here matched an archival category
    #: but its lifecycle did not permit moving it — it is still in the
    #: tree, and the operator needs to see that it was *held* rather
    #: than never found. The path is relative because the bare name
    #: is ambiguous: two documents with the same name in different
    #: directories are two files.
    gated_files: list[str] = field(default_factory=list)


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

        self.categorizer = DocumentationCategorizer(
            self.pkg_path,
            archivable_statuses=self.settings.documentation.archivable_statuses,
        )

        self._archive_mappings = self._build_archive_mappings()

        #: The candidates the lifecycle gate held back on the last
        #: detection, filled in by :meth:`_detect_archivable_files` —
        #: the single place the gate is applied.
        self._gated_files: list[Path] = []

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
            gated_files = self._gated_files.copy()
            result.gated_files = [self._gated_label(path) for path in gated_files]

            if not archivable_files:
                result.success = True
                result.summary = self._summarize_no_moves(gated_files)
                self._display_completion(result)
                return result

            is_valid, error_msg = self._validate_preconditions(archivable_files)
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

                with tarfile.open(str(backup_archive), "r|gz") as tar:
                    tar.extractall(temp_path)

                restored = 0
                for file_path in temp_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(temp_path)
                        target_path = self.pkg_path / relative_path

                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        shutil.move(file_path, target_path)
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
        """Return the files the archiver will take.

        This is the **single** place the lifecycle gate is applied. Both
        detection paths — the categorizer's and the legacy fallback's —
        produce candidates and pass through the gate here, so adding or
        removing a detection path cannot open a bypass: the gate is either
        applied to every path or to none.

        That single-choke-point shape is deliberate. A gate applied once
        per detection path would fail *quietly* if an editor deleted one
        of the two calls; a gate applied once, here, fails *loudly* —
        removing it removes the rule entirely.

        The files the gate holds back are recorded in
        :attr:`_gated_files`. The gate is where the two lists are
        separated, so this is the only place that can say which
        candidates were *held* rather than never found — and the
        cleanup's report needs that, because "all files are essential"
        is false for a file that matched a category and was held.
        """
        try:
            candidates = self.categorizer.get_archival_candidates()

        except Exception as e:
            logger.exception(f"Regex-based file detection failed: {e}")

            candidates = self._detect_archivable_files_legacy()

        archivable: list[Path] = []
        self._gated_files = []
        for path in candidates:
            if self._passes_lifecycle_gate(path):
                archivable.append(path)
            else:
                self._gated_files.append(path)
        return archivable

    def _passes_lifecycle_gate(self, path: Path) -> bool:
        """Apply the lifecycle gate to markdown documents.

        Only markdown carries a frontmatter lifecycle, so only markdown is
        gated. The non-markdown root artifacts the archiver also sweeps —
        loose ``.py`` / ``.json`` / ``.txt`` / ``.backup`` files — have no
        lifecycle to declare, and a binary ``.backup`` cannot even be read
        as UTF-8. Gating them would make them unarchivable, which is the
        cleanup's actual job.

        A *copy* of a document counts as one: a candidate whose name
        carries ``.md`` is gated even when it is not markdown-suffixed.
        The check is on the name rather than the suffix, and it is
        case-insensitive because the categorisation is —
        ``categorize_file`` matches its patterns with ``re.IGNORECASE``.

        This is a live path, not a hypothetical one. ``re.match`` anchors
        at the *start* of the name, so a pattern that is not end-anchored
        matches a prefix: the ``analysis`` category's ``TEST_.*\\.md``
        pattern classifies ``TEST_foo.md.backup`` as an analysis
        document, and the ``*.backup`` glob proposes it. A suffix test
        would have swept that copy ungated; the name test gates it like
        the document it copies.
        """
        name = path.name.lower()
        if ".md" not in name and ".markdown" not in name:
            return True
        return self.categorizer.lifecycle_permits_archival(path)

    def _detect_archivable_files_legacy(self) -> list[Path]:
        """Name-only fallback detector, used when the categorizer raises.

        The candidates it returns are gated by
        :meth:`_detect_archivable_files`, like every other path.
        """
        try:
            md_files = list(
                self.pkg_path.glob(DocumentationCategorizer.MARKDOWN_PATTERN)
            )
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

    def _validate_preconditions(
        self,
        archivable_files: list[Path] | None = None,
    ) -> tuple[bool, str | None]:
        # Per-area archive roots (docs/.archive/, docs/plans/.archive/, …).
        # Each is created on demand by _move_files_to_archive, but we
        # pre-create them here so a dry-run still surfaces the layout.
        for area in self.categorizer.SCANNED_ARCHIVE_AREAS:
            (self.pkg_path / area / ".archive").mkdir(parents=True, exist_ok=True)

        return True, None

    def _create_backup(self, files: list[Path]) -> BackupMetadata | None:
        try:
            backup_id = self._generate_backup_id()
            if self.backup_service.backup_root is None:
                return None
            backup_dir = self.backup_service.backup_root / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_archive = backup_dir / "backup.tar.gz"

            file_checksums: dict[str, str] = {}
            total_size = 0

            with tarfile.open(str(backup_archive), "w|gz") as tar:
                for file_path in files:
                    if file_path.exists():
                        content = file_path.read_bytes()
                        total_size += len(content)

                        checksum = hashlib.sha256(
                            content, usedforsecurity=False
                        ).hexdigest()
                        file_checksums[file_path.name] = checksum

                        tar.add(file_path, arcname=file_path.name)

            overall_checksum = self._calculate_backup_checksum(file_checksums)

            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=datetime.now(),
                package_directory=self.pkg_path,
                backup_directory=backup_dir,
                total_files=len(files),
                total_size=total_size,
                checksum=overall_checksum,
                file_checksums=file_checksums,
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

    def _calculate_backup_checksum(self, file_checksums: dict[str, str]) -> str:
        sorted_items = sorted(file_checksums.items())
        combined = "".join(f"{path}: {checksum}" for path, checksum in sorted_items)
        return hashlib.sha256(combined.encode(), usedforsecurity=False).hexdigest()

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

            # Compute the source relative path BEFORE the move — once
            # ``Path.replace`` runs, ``file_path`` no longer points at a
            # file on disk (though the Path object itself is unchanged).
            # We capture the path here for the git-index update below.
            source_relative = file_path.relative_to(self.pkg_path)

            # The categorizer now composes the full path from the file's
            # parent area plus the category subdir (per-area scheme:
            # `<area>/.archive/<subdir>/<filename>`).
            target_path = self.categorizer.archive_target_path(file_path, subdirectory)
            target_path_relative = target_path.relative_to(self.pkg_path)

            if dry_run:
                self.console.print(
                    f"[yellow]Would move:[/yellow] {file_path.name} "
                    f"→ {redact_path(target_path_relative)}"
                )
            else:
                try:
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    file_path.replace(target_path)

                    # Keep the git index in sync with the disk move —
                    # without this, the archive leaves every moved file
                    # flagged as `D`` in ``git status`` until something
                    # else ``git rm``s it. We pass the OLD/source path
                    # (not the new archive path): ``git rm`` can only act
                    # on tracked paths, and the source is what was tracked;
                    # the archive path is untracked until the next
                    # ``git add``. We tolerate failure here because the
                    # file is already on disk in the archive.
                    if self.git_service is not None:
                        try:
                            self.git_service.rm_files([str(source_relative)])
                        except Exception as e:
                            logger.warning(f"git rm skipped for {source_relative}: {e}")

                    files_moved += 1

                except Exception as e:
                    logger.exception(f"Failed to move {redact_path(file_path)}: {e}")
                    self.console.print(
                        f"[yellow]⚠️[/yellow] Failed to move {file_path.name}: {e}"
                    )

            if subdirectory not in archived_files:
                archived_files[subdirectory] = []
            archived_files[subdirectory].append(file_path.name)

        return files_moved, archived_files

    def _count_essential_files(self) -> int:
        essential_files = self.settings.documentation.essential_files
        md_files = list(self.pkg_path.glob(DocumentationCategorizer.MARKDOWN_PATTERN))

        return sum(1 for f in md_files if f.name in essential_files)

    def _gated_label(self, path: Path) -> str:
        """How a held file is named to the operator.

        The name alone is ambiguous: two documents with the same name in
        different directories are two files, and the operator has to be
        able to tell which one the gate held.
        """
        try:
            return str(path.relative_to(self.pkg_path))
        except ValueError:
            return path.name

    def _gate_criterion(self) -> str:
        """The statuses the lifecycle gate accepts, as the operator reads them.

        The gate's criterion is configurable -- a repo with a different
        vocabulary overrides ``archivable_statuses`` -- so a message
        that names one status is a false statement in that repo. It is
        worse than cosmetic: the message names the status to *set*, and
        a repo whose criterion is ``complete`` would set ``shipped`` and
        then find the document still not archivable.

        The criterion is read from the **categorizer**, not from the
        settings, because the categorizer is what the gate asks. It
        holds the set the gate actually compares against: the settings
        are snapshotted when it is built, and the set is normalised the
        same way a document's status is, so a configuration written as
        ``"Shipped"`` matches a ``status: shipped`` document. Reading
        the settings here would name a criterion the gate never
        applied -- the moment the two disagree, the message tells the
        operator to set a status the gate does not accept.
        """
        statuses = sorted(self.categorizer.archivable_statuses)
        if not statuses:
            return "status is not archivable"
        if len(statuses) == 1:
            return f"status is not {statuses[0]!r}"
        listed = ", ".join(repr(s) for s in statuses)
        return f"status is not one of {listed}"

    def _summarize_no_moves(self, gated: list[Path]) -> str:
        """The summary for a run that moved nothing.

        "No files to cleanup - all files are essential" is only true
        when the gate held nothing back. A file the gate held is in the
        tree on purpose, and the operator needs to know it was *held*
        rather than never found — otherwise a mis-declared lifecycle
        reads exactly like "there was nothing to do".
        """
        if not gated:
            return "No files to cleanup - all files are essential"
        names = ", ".join(sorted(self._gated_label(path) for path in gated))
        return (
            f"No files to cleanup - {len(gated)} file(s) held by the "
            f"lifecycle gate ({self._gate_criterion()}): {names}"
        )

    def _generate_summary(self, result: DocumentationCleanupResult) -> str:
        lines = [
            f"Files moved: {result.files_moved}",
            f"Files preserved: {result.files_preserved} (essential)",
        ]

        if result.gated_files:
            lines.append(
                f"Files held by the lifecycle gate: {len(result.gated_files)} "
                f"({self._gate_criterion()})"
            )

        if result.backup_metadata:
            lines.append(
                f"Backup location: {result.backup_metadata.backup_directory.relative_to(self.pkg_path)}"
            )

        if result.archived_files:
            lines.append("\nArchive breakdown:")
            for subdir, files in sorted(result.archived_files.items()):
                lines.append(f" {subdir}/: {len(files)} files")

        return "\n".join(lines)

    def _generate_backup_id(self) -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def _display_completion(self, result: DocumentationCleanupResult) -> None:
        if result.success:
            if result.files_moved > 0:
                self.console.print("[green]✅ Documentation cleanup completed[/green]")
                self.console.print(f"\n{result.summary}")
            else:
                self.console.print(
                    "[cyan]ℹ️ Documentation cleanup: No files to move[/cyan]"
                )
                if not result.gated_files:
                    self.console.print(
                        "[dim]All root files are essential or already archived.[/dim]"
                    )
            if result.gated_files:
                # The gate held files back. Saying "no files to move"
                # without saying that is the mis-report this fixes: the
                # operator cannot tell a held file from a file that
                # never matched.
                self.console.print(
                    f"[yellow]⚠️  {len(result.gated_files)} file(s) held by the "
                    f"lifecycle gate ({self._gate_criterion()}):[/yellow]"
                )
                for name in result.gated_files:
                    self.console.print(f"   [yellow]• {name}[/yellow]")
        else:
            self.console.print("[red]❌ Documentation cleanup failed[/red]")
            if result.error_message:
                self.console.print(f"Error: {result.error_message}")
