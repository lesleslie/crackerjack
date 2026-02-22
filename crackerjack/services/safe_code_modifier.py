from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import subprocess
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

if t.TYPE_CHECKING:
    from rich.console import Console


logger = logging.getLogger(__name__)


_backup_locks: dict[str, asyncio.Lock] = {}


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    severity: ValidationSeverity
    message: str
    file_path: Path
    line_number: int | None = None


@dataclass
class ValidationResult:
    success: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


@dataclass
class BackupMetadata:
    original_path: Path
    backup_path: Path
    timestamp: datetime
    hash: str
    size: int
    sequence: int


class SafeCodeModifier:
    def __init__(
        self,
        console: Console,
        project_path: Path,
        max_backups: int = 5,
    ) -> None:
        from rich.console import Console as RichConsole

        self.console: RichConsole = console
        self.project_path = project_path
        self.max_backups = max_backups
        self._backup_sequences: dict[Path, int] = {}

    async def apply_changes_with_validation(
        self,
        file_path: Path,
        changes: list[tuple[str, str]],
        context: str,
        smoke_test_cmd: list[str] | None = None,
    ) -> bool:

        backup_metadata = await self._backup_file(file_path)

        if not backup_metadata:
            self.console.print(f"[red]✗ Failed to create backup for {file_path}[/red]")
            return False

        self.console.print(
            f"[dim]→ Created backup: {backup_metadata.backup_path.name}[/dim]"
        )

        try:
            modified_content = await self._apply_changes(file_path, changes)
        except Exception as e:
            self.console.print(f"[red]✗ Failed to apply changes: {e}[/red]")
            await self._rollback_file(file_path, backup_metadata)
            return False

        validation_result = await self._validate_changes(file_path, modified_content)

        if not validation_result.success:
            self.console.print(f"[red]✗ Validation failed for {context}[/red]")
            for error in validation_result.errors:
                self.console.print(f"  [red]Error:[/red] {error.message}")

            await self._rollback_file(file_path, backup_metadata)
            return False

        if validation_result.warnings:
            self.console.print(
                f"[yellow]⚠ Validation passed with {len(validation_result.warnings)} warnings[/yellow]"
            )
            for warning in validation_result.warnings[:3]:
                self.console.print(f"  [yellow]Warning:[/yellow] {warning.message}")

        if smoke_test_cmd:
            if not await self._run_smoke_test(smoke_test_cmd):
                self.console.print(f"[red]✗ Smoke test failed for {context}[/red]")
                await self._rollback_file(file_path, backup_metadata)
                return False

        await self._cleanup_old_backups(file_path)

        self.console.print(f"[green]✓ Successfully applied: {context}[/green]")
        return True

    async def apply_content_with_validation(
        self,
        file_path: Path,
        new_content: str,
        context: str,
        smoke_test_cmd: list[str] | None = None,
    ) -> bool:

        backup_metadata = await self._backup_file(file_path)

        if not backup_metadata:
            self.console.print(f"[red]✗ Failed to create backup for {file_path}[/red]")
            return False

        self.console.print(
            f"[dim]→ Created backup: {backup_metadata.backup_path.name}[/dim]"
        )

        if not await self._validate_and_write(
            file_path, new_content, context, backup_metadata, smoke_test_cmd
        ):
            return False

        await self._cleanup_old_backups(file_path)

        return True

    async def _validate_and_write(
        self,
        file_path: Path,
        content: str,
        context: str,
        backup_metadata: BackupMetadata,
        smoke_test_cmd: list[str] | None = None,
    ) -> bool:

        validation_result = await self._validate_changes(file_path, content)

        if not validation_result.success:
            self.console.print(f"[red]✗ Validation failed for {context}[/red]")
            for error in validation_result.errors:
                self.console.print(f"  [red]Error:[/red] {error.message}")

            await self._rollback_file(file_path, backup_metadata)
            return False

        if validation_result.warnings:
            self.console.print(
                f"[yellow]⚠ Validation passed with {len(validation_result.warnings)} warnings[/yellow]"
            )
            for warning in validation_result.warnings[:3]:
                self.console.print(f"  [yellow]Warning:[/yellow] {warning.message}")

        try:
            from crackerjack.services.async_file_io import async_write_file

            await async_write_file(file_path, content)
        except Exception as e:
            self.console.print(f"[red]✗ Failed to write file: {e}[/red]")
            await self._rollback_file(file_path, backup_metadata)
            return False

        if smoke_test_cmd:
            if not await self._run_smoke_test(smoke_test_cmd):
                self.console.print(f"[red]✗ Smoke test failed for {context}[/red]")
                await self._rollback_file(file_path, backup_metadata)
                return False

        self.console.print(f"[green]✓ Successfully applied: {context}[/green]")
        return True

    async def _backup_file(self, file_path: Path) -> BackupMetadata | None:
        lock_key = str(file_path)

        if lock_key not in _backup_locks:
            _backup_locks[lock_key] = asyncio.Lock()

        try:
            from crackerjack.services.async_file_io import (
                async_read_file,
                async_write_file,
            )

            async with _backup_locks[lock_key]:
                content = await async_read_file(file_path)

                file_hash = hashlib.sha256(content.encode()).hexdigest()

                sequence = self._backup_sequences.get(file_path, 0) + 1
                self._backup_sequences[file_path] = sequence

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = (
                    f"{file_path.stem}.bak.{timestamp}.{sequence}{file_path.suffix}"
                )
                backup_path = file_path.parent / backup_name

                await async_write_file(backup_path, content)

                os.chmod(backup_path, 0o600)

                return BackupMetadata(
                    original_path=file_path,
                    backup_path=backup_path,
                    timestamp=datetime.now(),
                    hash=file_hash,
                    size=len(content),
                    sequence=sequence,
                )

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None

    async def _apply_changes(
        self,
        file_path: Path,
        changes: list[tuple[str, str]],
    ) -> str:
        from crackerjack.services.async_file_io import async_read_file, async_write_file

        content = await async_read_file(file_path)
        modified_content = content

        for old_str, new_str in changes:
            if old_str not in modified_content:
                raise ValueError(
                    f"Could not find old string in {file_path}: {old_str[:50]}..."
                )

            modified_content = modified_content.replace(old_str, new_str)

        await async_write_file(file_path, modified_content)

        # Apply ruff format to fix any indentation issues
        if str(file_path).endswith(".py"):
            try:
                result = subprocess.run(
                    ["ruff", "format", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    logger.debug(f"Applied ruff format to {file_path}")
                else:
                    logger.warning(f"Ruff format warning: {result.stderr}")
            except Exception as e:
                logger.warning(f"Ruff format failed: {e}")

        return modified_content

    async def _validate_changes(
        self,
        file_path: Path,
        content: str,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []

        syntax_result = await self._validate_syntax(file_path, content)
        issues.extend(syntax_result.issues)

        if syntax_result.errors:
            return ValidationResult(success=False, issues=issues)

        quality_result = await self._validate_quality(file_path)
        issues.extend(quality_result.issues)

        success = not any(i.severity == ValidationSeverity.ERROR for i in issues)

        return ValidationResult(success=success, issues=issues)

    async def _validate_syntax(
        self,
        file_path: Path,
        content: str,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []

        try:
            compile(content, str(file_path), "exec")
        except SyntaxError as e:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Syntax error: {e.msg}",
                    file_path=file_path,
                    line_number=e.lineno,
                )
            )

        return ValidationResult(success=len(issues) == 0, issues=issues)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                self.console.print(
                    f"[dim]Smoke test output:\n{result.stdout}\n{result.stderr}[/dim]"
                )
                return False

            return True

        except subprocess.TimeoutExpired:
            self.console.print("[red]Smoke test timed out after 300s[/red]")
            return False
        except Exception as e:
            self.console.print(f"[red]Smoke test failed: {e}[/red]")
            return False

    async def _rollback_file(
        self,
        file_path: Path,
        backup_metadata: BackupMetadata,
    ) -> bool:
        try:
            if not backup_metadata.backup_path.exists():
                logger.error(f"Backup file not found: {backup_metadata.backup_path}")
                return False

            shutil.copy2(backup_metadata.backup_path, file_path)

            self.console.print(
                f"[yellow]↩ Rolled back {file_path.name} to {backup_metadata.backup_path.name}[/yellow]"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to rollback file: {e}")
            self.console.print(f"[red]✗ Rollback failed: {e}[/red]")
            return False

    async def _cleanup_old_backups(self, file_path: Path) -> None:
        try:
            backup_pattern = f"{file_path.stem}.bak.*{file_path.suffix}"
            backups = sorted(
                file_path.parent.glob(backup_pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            for old_backup in backups[self.max_backups :]:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup.name}")

        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")

    async def _validate_quality(self, file_path: Path) -> ValidationResult:
        issues: list[ValidationIssue] = []

        try:
            result = subprocess.run(
                ["ruff", "check", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue

                    parts = line.split(":", 4)
                    if len(parts) >= 4:
                        try:
                            line_number = int(parts[1])
                            message = parts[3].strip()

                            issues.append(
                                ValidationIssue(
                                    severity=ValidationSeverity.WARNING,
                                    message=message,
                                    file_path=file_path,
                                    line_number=line_number,
                                )
                            )
                        except (ValueError, IndexError):
                            continue

        except subprocess.TimeoutExpired:
            logger.warning(f"Ruff check timeout for {file_path}")
        except FileNotFoundError:
            logger.debug("Ruff not installed, skipping quality check")
        except Exception as e:
            logger.warning(f"Ruff check failed: {e}")

        return ValidationResult(success=True, issues=issues)


__all__ = [
    "SafeCodeModifier",
    "BackupMetadata",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
]
