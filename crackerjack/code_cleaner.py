import ast
import typing as t
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from .errors import ErrorCode, ExecutionError
from .services.backup_service import BackupMetadata, PackageBackupService
from .services.regex_patterns import SAFE_PATTERNS
from .services.secure_path_utils import (
    AtomicFileOperations,
    SecurePathValidator,
)
from .services.security_logger import (
    SecurityEventLevel,
    SecurityEventType,
    get_security_logger,
)


class SafePatternApplicator:
    def apply_docstring_patterns(self, code: str) -> str:
        # Intentionally a no-op for docstrings here. Actual docstring removal is
        # handled by the structured AST cleaning step (_create_docstring_step).
        # This keeps SafePatternApplicator focused on formatting-only changes.
        return code

    def apply_formatting_patterns(self, content: str) -> str:
        content = SAFE_PATTERNS["spacing_after_comma"].apply(content)
        content = SAFE_PATTERNS["spacing_after_colon"].apply(content)
        content = SAFE_PATTERNS["multiple_spaces"].apply(content)
        return content

    def has_preserved_comment(self, line: str) -> bool:
        if line.strip().startswith("#! /"):
            return True

        line_lower = line.lower()
        preserved_keywords = [
            "coding: ",
            "encoding: ",
            "type: ",
            "noqa",
            "pragma",
            "regex ok",
            "todo",
        ]
        return any(keyword in line_lower for keyword in preserved_keywords)


_safe_applicator = SafePatternApplicator()


@dataclass
class CleaningResult:
    file_path: Path
    success: bool
    steps_completed: list[str]
    steps_failed: list[str]
    warnings: list[str]
    original_size: int
    cleaned_size: int
    backup_metadata: BackupMetadata | None = None


@dataclass
class PackageCleaningResult:
    total_files: int
    successful_files: int
    failed_files: int
    file_results: list[CleaningResult]
    backup_metadata: BackupMetadata | None
    backup_restored: bool = False
    overall_success: bool = False


class CleaningStepProtocol(Protocol):
    def __call__(self, code: str, file_path: Path) -> str: ...

    @property
    def name(self) -> str: ...


class FileProcessor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    console: t.Any
    logger: t.Any = None
    base_directory: Path | None = None
    security_logger: t.Any = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.code_cleaner.file_processor")

        if self.security_logger is None:
            self.security_logger = get_security_logger()

    def read_file_safely(self, file_path: Path) -> str:
        validated_path = SecurePathValidator.validate_file_path(
            file_path, self.base_directory
        )
        SecurePathValidator.validate_file_size(validated_path)

        self.security_logger.log_security_event(
            SecurityEventType.FILE_CLEANED,
            SecurityEventLevel.LOW,
            f"Reading file for cleaning: {validated_path}",
            file_path=validated_path,
        )

        try:
            return validated_path.read_text(encoding="utf-8")

        except UnicodeDecodeError:
            for encoding in ("latin1", "cp1252"):
                try:
                    content = validated_path.read_text(encoding=encoding)
                    self.logger.warning(
                        f"File {validated_path} read with {encoding} encoding",
                    )
                    return content
                except UnicodeDecodeError:
                    continue

            self.security_logger.log_validation_failed(
                "encoding",
                file_path,
                "Could not decode file with any supported encoding",
            )

            raise ExecutionError(
                message=f"Could not decode file {file_path}",
                error_code=ErrorCode.FILE_READ_ERROR,
            )

        except ExecutionError:
            raise

        except Exception as e:
            self.security_logger.log_validation_failed(
                "file_read", file_path, f"Unexpected error during file read: {e}"
            )

            raise ExecutionError(
                message=f"Failed to read file {file_path}: {e}",
                error_code=ErrorCode.FILE_READ_ERROR,
            ) from e

    def write_file_safely(self, file_path: Path, content: str) -> None:
        try:
            AtomicFileOperations.atomic_write(file_path, content, self.base_directory)

            self.security_logger.log_atomic_operation("write", file_path, True)

        except ExecutionError:
            self.security_logger.log_atomic_operation("write", file_path, False)
            raise

        except Exception as e:
            self.security_logger.log_atomic_operation(
                "write", file_path, False, error=str(e)
            )

            raise ExecutionError(
                message=f"Failed to write file {file_path}: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e

    def backup_file(self, file_path: Path) -> Path:
        try:
            backup_path = AtomicFileOperations.atomic_backup_and_write(
                file_path, file_path.read_bytes(), self.base_directory
            )

            self.security_logger.log_backup_created(file_path, backup_path)

            return backup_path

        except ExecutionError:
            raise

        except Exception as e:
            self.security_logger.log_validation_failed(
                "backup_creation", file_path, f"Backup creation failed: {e}"
            )

            raise ExecutionError(
                message=f"Failed to create backup for {file_path}: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e


class CleaningErrorHandler(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    console: t.Any
    logger: t.Any = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.code_cleaner.error_handler")

    def handle_file_error(self, file_path: Path, error: Exception, step: str) -> None:
        self.console.print(
            f"[bold bright_yellow]⚠️ Warning: {step} failed for {file_path}: {error}[/ bold bright_yellow]",
        )

        self.logger.warning(
            "Cleaning step failed",
            extra={
                "file_path": str(file_path),
                "step": step,
                "error": str(error),
                "error_type": type(error).__name__,
            },
        )

    def log_cleaning_result(self, result: CleaningResult) -> None:
        if result.success:
            self.console.print(
                f"[green]✅ Cleaned {result.file_path}[/ green] "
                f"({result.original_size} → {result.cleaned_size} bytes)",
            )
        else:
            self.console.print(
                f"[red]❌ Failed to clean {result.file_path}[/ red] "
                f"({len(result.steps_failed)} steps failed)",
            )

        if result.warnings:
            for warning in result.warnings:
                self.console.print(f"[yellow]⚠️ {warning}[/ yellow]")

        self.logger.info(
            "File cleaning completed",
            extra={
                "file_path": str(result.file_path),
                "success": result.success,
                "steps_completed": result.steps_completed,
                "steps_failed": result.steps_failed,
                "original_size": result.original_size,
                "cleaned_size": result.cleaned_size,
            },
        )


class CleaningPipeline(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_processor: t.Any
    error_handler: t.Any
    console: t.Any
    logger: t.Any = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.code_cleaner.pipeline")

    def clean_file(
        self,
        file_path: Path,
        cleaning_steps: list[CleaningStepProtocol],
    ) -> CleaningResult:
        self.logger.info(f"Starting clean_file for {file_path}")
        try:
            original_code = self.file_processor.read_file_safely(file_path)
            original_size = len(original_code.encode("utf-8"))

            result = self._apply_cleaning_pipeline(
                original_code,
                file_path,
                cleaning_steps,
            )

            cleaned_size = original_size
            if result.success and result.cleaned_code != original_code:
                self.file_processor.write_file_safely(file_path, result.cleaned_code)
                cleaned_size = len(result.cleaned_code.encode("utf-8"))

            cleaning_result = CleaningResult(
                file_path=file_path,
                success=result.success,
                steps_completed=result.steps_completed,
                steps_failed=result.steps_failed,
                warnings=result.warnings,
                original_size=original_size,
                cleaned_size=cleaned_size,
            )

            self.error_handler.log_cleaning_result(cleaning_result)
            return cleaning_result

        except Exception as e:
            self.error_handler.handle_file_error(file_path, e, "file_processing")
            return CleaningResult(
                file_path=file_path,
                success=False,
                steps_completed=[],
                steps_failed=["file_processing"],
                warnings=[],
                original_size=0,
                cleaned_size=0,
            )

    @dataclass
    class PipelineResult:
        cleaned_code: str
        success: bool
        steps_completed: list[str]
        steps_failed: list[str]
        warnings: list[str]

    def _apply_cleaning_pipeline(
        self,
        code: str,
        file_path: Path,
        cleaning_steps: list[CleaningStepProtocol],
    ) -> PipelineResult:
        current_code = code
        steps_completed: list[str] = []
        steps_failed: list[str] = []
        warnings: list[str] = []
        overall_success = True

        for step in cleaning_steps:
            try:
                step_result = step(current_code, file_path)
                current_code = step_result
                steps_completed.append(step.name)

                self.logger.debug(
                    "Cleaning step completed",
                    extra={"step": step.name, "file_path": str(file_path)},
                )

            except Exception as e:
                self.error_handler.handle_file_error(file_path, e, step.name)
                steps_failed.append(step.name)
                warnings.append(f"{step.name} failed: {e}")

                self.logger.warning(
                    "Cleaning step failed, continuing with original code",
                    extra={
                        "step": step.name,
                        "file_path": str(file_path),
                        "error": str(e),
                    },
                )

        if steps_failed:
            success_ratio = len(steps_completed) / (
                len(steps_completed) + len(steps_failed)
            )
            overall_success = success_ratio >= 0.7

        return self.PipelineResult(
            cleaned_code=current_code,
            success=overall_success,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            warnings=warnings,
        )


class CodeCleaner(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    console: t.Any
    file_processor: t.Any = None
    error_handler: t.Any = None
    pipeline: t.Any = None
    logger: t.Any = None
    base_directory: Path | None = None
    security_logger: t.Any = None
    backup_service: t.Any = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.code_cleaner")

        if self.base_directory is None:
            self.base_directory = Path.cwd()

        if self.file_processor is None:
            self.file_processor = FileProcessor(
                console=self.console, base_directory=self.base_directory
            )

        if self.error_handler is None:
            self.error_handler = CleaningErrorHandler(console=self.console)

        if self.pipeline is None:
            self.pipeline = CleaningPipeline(
                file_processor=self.file_processor,
                error_handler=self.error_handler,
                console=self.console,
            )

        if self.security_logger is None:
            self.security_logger = get_security_logger()

        if self.backup_service is None:
            self.backup_service = PackageBackupService()

    def clean_file(self, file_path: Path) -> CleaningResult:
        cleaning_steps = [
            self._create_line_comment_step(),
            self._create_docstring_step(),
            self._create_whitespace_step(),
            self._create_formatting_step(),
        ]

        result = self.pipeline.clean_file(file_path, cleaning_steps)
        return t.cast(CleaningResult, result)

    def clean_files(
        self, pkg_dir: Path | None = None, use_backup: bool = True
    ) -> list[CleaningResult] | PackageCleaningResult:
        if use_backup:
            package_result = self.clean_files_with_backup(pkg_dir)
            self.logger.info(
                f"Package cleaning with backup completed: "
                f"success={package_result.overall_success}, "
                f"restored={package_result.backup_restored}"
            )
            return package_result

        self.console.print(
            "[yellow]⚠️ WARNING: Running without backup protection. "
            "Consider using use_backup=True for safety.[/yellow]"
        )

        if pkg_dir is None:
            # Use configured base directory when no explicit path is provided
            pkg_dir = self.base_directory or Path.cwd()

        python_files = self._discover_package_files(pkg_dir)

        files_to_process = [
            file_path
            for file_path in python_files
            if self.should_process_file(file_path)
        ]

        results: list[CleaningResult] = []
        self.logger.info(f"Starting clean_files for {len(files_to_process)} files")

        cleaning_steps = [
            self._create_line_comment_step(),
            self._create_docstring_step(),
            self._create_whitespace_step(),
            self._create_formatting_step(),
        ]

        for file_path in files_to_process:
            result = self.pipeline.clean_file(file_path, cleaning_steps)
            results.append(result)

        return results

    def clean_files_with_backup(
        self, pkg_dir: Path | None = None
    ) -> PackageCleaningResult:
        validated_pkg_dir = self._prepare_package_directory(pkg_dir)

        self.logger.info(
            f"Starting safe package cleaning with backup: {validated_pkg_dir}"
        )
        self.console.print(
            "[cyan]🛡️ Starting package cleaning with backup protection...[/cyan]"
        )

        backup_metadata: BackupMetadata | None = None

        try:
            backup_metadata = self._create_backup(validated_pkg_dir)
            files_to_process = self._find_files_to_process(validated_pkg_dir)

            if not files_to_process:
                return self._handle_no_files_to_process(backup_metadata)

            cleaning_result = self._execute_cleaning_with_backup(
                files_to_process, backup_metadata
            )

            return self._finalize_cleaning_result(cleaning_result, backup_metadata)

        except Exception as e:
            return self._handle_critical_error(e, backup_metadata)

    def _prepare_package_directory(self, pkg_dir: Path | None) -> Path:
        if pkg_dir is None:
            pkg_dir = self.base_directory or Path.cwd()
        # Avoid normalizing symlinks to preserve exact input path semantics
        # while still enforcing base-directory containment.
        if self.base_directory and not SecurePathValidator.is_within_directory(
            pkg_dir, self.base_directory
        ):
            raise ExecutionError(
                message=(
                    f"Path outside allowed directory: {pkg_dir} not within "
                    f"{self.base_directory}"
                ),
                error_code=ErrorCode.VALIDATION_ERROR,
            )
        return pkg_dir

    def _create_backup(self, validated_pkg_dir: Path) -> BackupMetadata:
        self.console.print(
            "[yellow]📦 Creating backup of all package files...[/yellow]"
        )

        backup_result = self.backup_service.create_package_backup(
            validated_pkg_dir, self.base_directory
        )
        backup_metadata: BackupMetadata = t.cast(BackupMetadata, backup_result)

        self.console.print(
            f"[green]✅ Backup created: {backup_metadata.backup_id}[/green] "
            f"({backup_metadata.total_files} files, {backup_metadata.total_size} bytes)"
        )

        return backup_metadata

    def _find_files_to_process(self, validated_pkg_dir: Path) -> list[Path]:
        python_files = self._discover_package_files(validated_pkg_dir)
        return [
            file_path
            for file_path in python_files
            if self.should_process_file(file_path)
        ]

    def _discover_package_files(self, root_dir: Path) -> list[Path]:
        package_dir = self._find_package_directory(root_dir)

        if not package_dir or not package_dir.exists():
            self.console.print(
                "[yellow]⚠️ Could not determine package directory, searching for Python packages...[/yellow]"
            )
            return self._fallback_discover_packages(root_dir)

        self.logger.debug(f"Using package directory: {package_dir}")

        package_files = list[t.Any](package_dir.rglob("*.py"))

        exclude_dirs = {
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".venv",
            "venv",
        }
        filtered_files = [
            f
            for f in package_files
            if not any(excl in f.parts for excl in exclude_dirs)
        ]

        return filtered_files

    def _find_package_directory(self, root_dir: Path) -> Path | None:
        pyproject_path = root_dir / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib

                with pyproject_path.open("rb") as f:
                    config = tomllib.load(f)

                project_name_raw = config.get("project", {}).get("name")
                project_name: str | None = t.cast(str | None, project_name_raw)
                if project_name:
                    package_name = project_name.replace("-", "_").lower()
                    package_dir = root_dir / package_name

                    if package_dir.exists() and (package_dir / "__init__.py").exists():
                        return package_dir

            except Exception as e:
                self.logger.debug(f"Could not parse pyproject.toml: {e}")

        package_name = root_dir.name.replace("-", "_").lower()
        package_dir = root_dir / package_name

        if package_dir.exists() and (package_dir / "__init__.py").exists():
            return package_dir

        return None

    def _fallback_discover_packages(self, root_dir: Path) -> list[Path]:
        python_files = []
        exclude_dirs = {
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "site-packages",
            ".pytest_cache",
            "build",
            "dist",
            ".tox",
            "node_modules",
            "tests",
            "test",
            "examples",
            "example",
            "docs",
            "doc",
            ".mypy_cache",
            ".ruff_cache",
            "htmlcov",
            ".coverage",
        }

        for item in root_dir.iterdir():
            if (
                not item.is_dir()
                or item.name.startswith(".")
                or item.name in exclude_dirs
            ):
                continue

            if (item / "__init__.py").exists():
                package_files = [
                    f
                    for f in item.rglob("*.py")
                    if self._should_include_file_path(f, exclude_dirs)
                ]
                python_files.extend(package_files)

        return python_files

    def _should_include_file_path(
        self, file_path: Path, exclude_dirs: set[str]
    ) -> bool:
        path_parts = set[t.Any](file_path.parts)

        return not bool(path_parts.intersection(exclude_dirs))

    def _handle_no_files_to_process(
        self, backup_metadata: BackupMetadata
    ) -> PackageCleaningResult:
        self.console.print("[yellow]⚠️ No files found to process[/yellow]")
        self.backup_service.cleanup_backup(backup_metadata)

        return PackageCleaningResult(
            total_files=0,
            successful_files=0,
            failed_files=0,
            file_results=[],
            backup_metadata=None,
            backup_restored=False,
            overall_success=True,
        )

    def _execute_cleaning_with_backup(
        self, files_to_process: list[Path], backup_metadata: BackupMetadata
    ) -> dict[str, t.Any]:
        self.console.print(f"[cyan]🧹 Cleaning {len(files_to_process)} files...[/cyan]")

        cleaning_steps = [
            self._create_line_comment_step(),
            self._create_docstring_step(),
            self._create_whitespace_step(),
            self._create_formatting_step(),
        ]

        file_results: list[CleaningResult] = []
        cleaning_errors: list[Exception] = []

        for file_path in files_to_process:
            try:
                result = self.pipeline.clean_file(file_path, cleaning_steps)
                result.backup_metadata = backup_metadata
                file_results.append(result)

                if not result.success:
                    cleaning_errors.append(
                        ExecutionError(
                            message=f"Cleaning failed for {file_path}: {result.steps_failed}",
                            error_code=ErrorCode.CODE_CLEANING_ERROR,
                        )
                    )
            except Exception as e:
                cleaning_errors.append(e)
                file_results.append(
                    CleaningResult(
                        file_path=file_path,
                        success=False,
                        steps_completed=[],
                        steps_failed=["file_processing"],
                        warnings=[f"Exception during cleaning: {e}"],
                        original_size=0,
                        cleaned_size=0,
                        backup_metadata=backup_metadata,
                    )
                )

        return {
            "file_results": file_results,
            "cleaning_errors": cleaning_errors,
            "files_to_process": files_to_process,
        }

    def _finalize_cleaning_result(
        self, cleaning_result: dict[str, t.Any], backup_metadata: BackupMetadata
    ) -> PackageCleaningResult:
        file_results = cleaning_result["file_results"]
        cleaning_errors = cleaning_result["cleaning_errors"]
        files_to_process = cleaning_result["files_to_process"]

        successful_files = sum(1 for result in file_results if result.success)
        failed_files = len(file_results) - successful_files

        if cleaning_errors or failed_files > 0:
            return self._handle_cleaning_failure(
                backup_metadata,
                file_results,
                files_to_process,
                successful_files,
                failed_files,
                cleaning_errors,
            )

        return self._handle_cleaning_success(
            backup_metadata, file_results, files_to_process, successful_files
        )

    def _handle_cleaning_failure(
        self,
        backup_metadata: BackupMetadata,
        file_results: list[CleaningResult],
        files_to_process: list[Path],
        successful_files: int,
        failed_files: int,
        cleaning_errors: list[Exception],
    ) -> PackageCleaningResult:
        self.console.print(
            f"[red]❌ Cleaning failed ({failed_files} files failed). "
            f"Restoring from backup...[/red]"
        )

        self.logger.error(
            f"Package cleaning failed with {len(cleaning_errors)} errors, "
            f"restoring from backup {backup_metadata.backup_id}"
        )

        self.backup_service.restore_from_backup(backup_metadata, self.base_directory)

        self.console.print("[green]✅ Files restored from backup successfully[/green]")

        return PackageCleaningResult(
            total_files=len(files_to_process),
            successful_files=successful_files,
            failed_files=failed_files,
            file_results=file_results,
            backup_metadata=backup_metadata,
            backup_restored=True,
            overall_success=False,
        )

    def _handle_cleaning_success(
        self,
        backup_metadata: BackupMetadata,
        file_results: list[CleaningResult],
        files_to_process: list[Path],
        successful_files: int,
    ) -> PackageCleaningResult:
        self.console.print(
            f"[green]✅ Package cleaning completed successfully![/green] "
            f"({successful_files} files cleaned)"
        )

        self.backup_service.cleanup_backup(backup_metadata)

        return PackageCleaningResult(
            total_files=len(files_to_process),
            successful_files=successful_files,
            failed_files=0,
            file_results=file_results,
            backup_metadata=None,
            backup_restored=False,
            overall_success=True,
        )

    def _handle_critical_error(
        self, error: Exception, backup_metadata: BackupMetadata | None
    ) -> PackageCleaningResult:
        self.logger.error(f"Critical error during package cleaning: {error}")
        self.console.print(f"[red]💥 Critical error: {error}[/red]")

        backup_restored = False

        if backup_metadata:
            backup_restored = self._attempt_emergency_restoration(backup_metadata)

        return PackageCleaningResult(
            total_files=0,
            successful_files=0,
            failed_files=0,
            file_results=[],
            backup_metadata=backup_metadata,
            backup_restored=backup_restored,
            overall_success=False,
        )

    def _attempt_emergency_restoration(self, backup_metadata: BackupMetadata) -> bool:
        try:
            self.console.print(
                "[yellow]🔄 Attempting emergency restoration...[/yellow]"
            )
            self.backup_service.restore_from_backup(
                backup_metadata, self.base_directory
            )
            self.console.print("[green]✅ Emergency restoration completed[/green]")
            return True

        except Exception as restore_error:
            self.logger.error(f"Emergency restoration failed: {restore_error}")
            self.console.print(
                f"[red]💥 Emergency restoration failed: {restore_error}[/red]\n"
                f"[yellow]⚠️ Manual restoration may be needed from: "
                f"{backup_metadata.backup_directory}[/yellow]"
            )
            return False

    def restore_from_backup_metadata(self, backup_metadata: BackupMetadata) -> None:
        self.console.print(
            f"[yellow]🔄 Manually restoring from backup: {backup_metadata.backup_id}[/yellow]"
        )

        self.backup_service.restore_from_backup(backup_metadata, self.base_directory)

        self.console.print(
            f"[green]✅ Manual restoration completed from backup: "
            f"{backup_metadata.backup_id}[/green]"
        )

    def create_emergency_backup(self, pkg_dir: Path | None = None) -> BackupMetadata:
        validated_pkg_dir = self._prepare_package_directory(pkg_dir)

        self.console.print(
            "[cyan]🛡️ Creating emergency backup before risky operation...[/cyan]"
        )

        backup_metadata = self._create_backup(validated_pkg_dir)

        self.console.print(
            f"[green]✅ Emergency backup created: {backup_metadata.backup_id}[/green]"
        )

        return backup_metadata

    def restore_emergency_backup(self, backup_metadata: BackupMetadata) -> bool:
        try:
            self.console.print(
                f"[yellow]🔄 Restoring emergency backup: {backup_metadata.backup_id}[/yellow]"
            )

            self.backup_service.restore_from_backup(
                backup_metadata, self.base_directory
            )

            self.console.print(
                f"[green]✅ Emergency backup restored successfully: {backup_metadata.backup_id}[/green]"
            )

            return True

        except Exception as e:
            self.logger.error(f"Emergency backup restoration failed: {e}")
            self.console.print(
                f"[red]💥 Emergency backup restoration failed: {e}[/red]\n"
                f"[yellow]⚠️ Manual intervention required. Backup location: "
                f"{backup_metadata.backup_directory}[/yellow]"
            )

            return False

    def verify_backup_integrity(self, backup_metadata: BackupMetadata) -> bool:
        try:
            validation_result = self.backup_service._validate_backup(backup_metadata)

            if validation_result.is_valid:
                self.console.print(
                    f"[green]✅ Backup verification passed: {backup_metadata.backup_id}[/green] "
                    f"({validation_result.total_validated} files verified)"
                )
                return True
            else:
                self.console.print(
                    f"[red]❌ Backup verification failed: {backup_metadata.backup_id}[/red]"
                )

                for error in validation_result.validation_errors[:3]:
                    self.console.print(f"[red] • {error}[/red]")

                if len(validation_result.validation_errors) > 3:
                    remaining = len(validation_result.validation_errors) - 3
                    self.console.print(f"[red] ... and {remaining} more errors[/red]")

                return False

        except Exception as e:
            self.logger.error(f"Backup verification failed with exception: {e}")
            self.console.print(f"[red]💥 Backup verification error: {e}[/red]")
            return False

    def list_available_backups(self) -> list[Path]:
        if (
            not self.backup_service.backup_root
            or not self.backup_service.backup_root.exists()
        ):
            self.console.print("[yellow]⚠️ No backup root directory found[/yellow]")
            return []

        try:
            backup_dirs = [
                path
                for path in self.backup_service.backup_root.iterdir()
                if path.is_dir() and path.name.startswith("backup_")
            ]

            if backup_dirs:
                self.console.print(
                    f"[cyan]📦 Found {len(backup_dirs)} available backups: [/cyan]"
                )
                for backup_dir in sorted(backup_dirs):
                    self.console.print(f" • {backup_dir.name}")
            else:
                self.console.print("[yellow]⚠️ No backups found[/yellow]")

            return backup_dirs

        except Exception as e:
            self.logger.error(f"Failed to list[t.Any] backups: {e}")
            self.console.print(f"[red]💥 Error listing backups: {e}[/red]")
            return []

    def should_process_file(self, file_path: Path) -> bool:
        try:
            validated_path = SecurePathValidator.validate_file_path(
                file_path, self.base_directory
            )

            SecurePathValidator.validate_file_size(validated_path)

            ignore_patterns = {
                "__pycache__",
                ".git",
                ".venv",
                "site-packages",
                ".pytest_cache",
                "build",
                "dist",
                "tests",
                "test",
                "examples",
                "example",
            }

            for parent in validated_path.parents:
                if parent.name in ignore_patterns:
                    return False

            should_process = not (
                validated_path.name.startswith(".") or validated_path.suffix != ".py"
            )

            if should_process:
                self.security_logger.log_security_event(
                    SecurityEventType.FILE_CLEANED,
                    SecurityEventLevel.LOW,
                    f"File approved for processing: {validated_path}",
                    file_path=validated_path,
                )

            return should_process

        except ExecutionError as e:
            self.security_logger.log_validation_failed(
                "file_processing_check",
                file_path,
                f"File failed security validation: {e}",
            )

            return False

        except Exception as e:
            self.logger.warning(f"Unexpected error checking file {file_path}: {e}")
            return False

    def _create_line_comment_step(self) -> CleaningStepProtocol:
        return self._LineCommentStep()

    def _create_docstring_step(self) -> CleaningStepProtocol:
        return self._DocstringStep()

    class _DocstringStep:
        name = "remove_docstrings"

        def _is_docstring_node(self, node: ast.AST) -> bool:
            body = getattr(node, "body", None)
            return (
                hasattr(node, "body")
                and body is not None
                and len(body) > 0
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            )

        def _find_docstrings(self, tree: ast.AST) -> list[ast.AST]:
            docstring_nodes: list[ast.AST] = []
            finder = self._DocstringFinder(docstring_nodes, self._is_docstring_node)
            finder.visit(tree)
            return docstring_nodes

        class _DocstringFinder(ast.NodeVisitor):
            def __init__(
                self,
                docstring_nodes: list[ast.AST],
                is_docstring_node: t.Callable[[ast.AST], bool],
            ):
                self.docstring_nodes = docstring_nodes
                self.is_docstring_node = is_docstring_node

            def _add_if_docstring(self, node: ast.AST) -> None:
                if self.is_docstring_node(node) and hasattr(node, "body"):
                    body: list[ast.stmt] = getattr(node, "body")
                    self.docstring_nodes.append(body[0])
                self.generic_visit(node)

            def visit_Module(self, node: ast.Module) -> None:
                self._add_if_docstring(node)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._add_if_docstring(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._add_if_docstring(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._add_if_docstring(node)

        def __call__(self, code: str, file_path: Path) -> str:
            try:
                tree = ast.parse(code, filename=str(file_path))
            except SyntaxError:
                return self._regex_fallback_removal(code)

            docstring_nodes = self._find_docstrings(tree)

            if not docstring_nodes:
                return code

            lines = code.split("\n")
            lines_to_remove: set[int] = set()

            for node in docstring_nodes:
                start_line = getattr(node, "lineno", 1)
                end_line = getattr(node, "end_lineno", start_line)

                lines_to_remove.update(range(start_line, end_line + 1))

            result_lines = [
                line for i, line in enumerate(lines, 1) if i not in lines_to_remove
            ]

            result = "\n".join(result_lines)
            return self._regex_fallback_removal(result)

        def _regex_fallback_removal(self, code: str) -> str:
            return _safe_applicator.apply_docstring_patterns(code)

    class _LineCommentStep:
        name = "remove_line_comments"

        def __call__(self, code: str, file_path: Path) -> str:
            lines = code.split("\n")

            processed_lines = [self._process_line_for_comments(line) for line in lines]
            return "\n".join(processed_lines)

        def _process_line_for_comments(self, line: str) -> str:
            if not line.strip() or self._is_preserved_comment_line(line):
                return line
            return self._remove_comment_from_line(line)

        def _is_preserved_comment_line(self, line: str) -> bool:
            stripped = line.strip()
            if not stripped.startswith("#"):
                return False
            return self._has_preserved_pattern(stripped)

        def _has_preserved_pattern(self, stripped_line: str) -> bool:
            return _safe_applicator.has_preserved_comment(stripped_line)

        def _remove_comment_from_line(self, line: str) -> str:
            """Remove comment from line while preserving strings."""
            if not self._line_needs_comment_processing(line):
                return line

            return self._process_line_for_comment_removal(line)

        def _line_needs_comment_processing(self, line: str) -> bool:
            """Check if line needs comment processing."""
            return '"' in line or "'" in line or "#" in line

        def _process_line_for_comment_removal(self, line: str) -> str:
            """Process line to remove comments while preserving strings."""
            result_chars = []
            string_state = {"in_string": False, "quote_char": None}

            for i, char in enumerate(line):
                if self._should_break_for_comment(char, string_state):
                    break

                self._update_string_state(char, i, line, string_state)
                result_chars.append(char)

            return "".join(result_chars).rstrip()

        def _should_break_for_comment(
            self, char: str, string_state: dict[str, t.Any]
        ) -> bool:
            """Check if we should break for a comment character."""
            return not string_state["in_string"] and char == "#"

        def _update_string_state(
            self, char: str, index: int, line: str, string_state: dict[str, t.Any]
        ) -> None:
            """Update string parsing state."""
            if not string_state["in_string"]:
                if char in ('"', "'"):
                    string_state["in_string"] = True
                    string_state["quote_char"] = char
            elif char == string_state["quote_char"] and (
                index == 0 or line[index - 1] != "\\"
            ):
                string_state["in_string"] = False
                string_state["quote_char"] = None

    def _create_docstring_finder_class(
        self,
        docstring_nodes: list[ast.AST],
    ) -> type[ast.NodeVisitor]:
        class DocstringFinder(ast.NodeVisitor):
            def _is_docstring_node(self, node: ast.AST) -> bool:
                body = getattr(node, "body", None)
                return (
                    hasattr(node, "body")
                    and body is not None
                    and len(body) > 0
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                )

            def _add_if_docstring(self, node: ast.AST) -> None:
                if self._is_docstring_node(node) and hasattr(node, "body"):
                    body: list[ast.stmt] = getattr(node, "body")
                    docstring_nodes.append(body[0])
                self.generic_visit(node)

            def visit_Module(self, node: ast.Module) -> None:
                self._add_if_docstring(node)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._add_if_docstring(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._add_if_docstring(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._add_if_docstring(node)

        return DocstringFinder

    def _create_whitespace_step(self) -> CleaningStepProtocol:
        class WhitespaceStep:
            name = "remove_extra_whitespace"

            def __call__(self, code: str, file_path: Path) -> str:
                lines = code.split("\n")
                cleaned_lines: list[str] = []
                empty_line_count = 0

                for line in lines:
                    cleaned_line = line.rstrip()

                    if not cleaned_line.strip():
                        empty_line_count += 1
                        if empty_line_count <= 2:
                            cleaned_lines.append("")
                    else:
                        empty_line_count = 0
                        leading_whitespace = len(cleaned_line) - len(
                            cleaned_line.lstrip()
                        )
                        content = cleaned_line.lstrip()

                        content = SAFE_PATTERNS["multiple_spaces"].apply(content)

                        cleaned_line = cleaned_line[:leading_whitespace] + content
                        cleaned_lines.append(cleaned_line)

                while cleaned_lines and not cleaned_lines[-1].strip():
                    cleaned_lines.pop()

                result = "\n".join(cleaned_lines)
                if result and not result.endswith("\n"):
                    result += "\n"

                return result

        return WhitespaceStep()

    def _create_formatting_step(self) -> CleaningStepProtocol:
        class FormattingStep:
            name = "format_code"

            def _is_preserved_comment_line(self, line: str) -> bool:
                stripped = line.strip()
                if not stripped.startswith("#"):
                    return False
                return _safe_applicator.has_preserved_comment(line)

            def __call__(self, code: str, file_path: Path) -> str:
                lines = code.split("\n")
                formatted_lines: list[str] = []

                for line in lines:
                    if line.strip():
                        if self._is_preserved_comment_line(line):
                            formatted_lines.append(line)
                            continue

                        leading_whitespace = len(line) - len(line.lstrip())
                        content = line.lstrip()

                        content = _safe_applicator.apply_formatting_patterns(content)

                        formatted_line = line[:leading_whitespace] + content
                        formatted_lines.append(formatted_line)
                    else:
                        formatted_lines.append(line)

                return "\n".join(formatted_lines)

        return FormattingStep()

    def remove_line_comments(self, code: str, file_path: Path | None = None) -> str:
        file_path = file_path or Path("temp.py")
        step = self._create_line_comment_step()
        return step(code, file_path)

    def remove_docstrings(self, code: str, file_path: Path | None = None) -> str:
        file_path = file_path or Path("temp.py")
        step = self._create_docstring_step()
        return step(code, file_path)

    def remove_extra_whitespace(self, code: str, file_path: Path | None = None) -> str:
        file_path = file_path or Path("temp.py")
        step = self._create_whitespace_step()
        return step(code, file_path)

    def format_code(self, code: str, file_path: Path | None = None) -> str:
        file_path = file_path or Path("temp.py")
        step = self._create_formatting_step()
        return step(code, file_path)
