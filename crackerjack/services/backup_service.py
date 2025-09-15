import hashlib
import shutil
import time
import typing as t
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..errors import ErrorCode, ExecutionError
from .secure_path_utils import AtomicFileOperations, SecurePathValidator
from .security_logger import SecurityEventLevel, SecurityEventType, get_security_logger


class BackupMetadata(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    backup_id: str
    timestamp: datetime
    package_directory: Path
    backup_directory: Path
    total_files: int
    total_size: int
    checksum: str
    file_checksums: dict[str, str]


class BackupValidationResult(BaseModel):
    is_valid: bool
    missing_files: list[Path]
    corrupted_files: list[Path]
    total_validated: int
    validation_errors: list[str]


class PackageBackupService(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    logger: t.Any = None
    security_logger: t.Any = None
    backup_root: Path | None = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.backup_service")

        if self.security_logger is None:
            self.security_logger = get_security_logger()

        if self.backup_root is None:
            import tempfile

            self.backup_root = Path(tempfile.gettempdir()) / "crackerjack_backups"

    def create_package_backup(
        self,
        package_directory: Path,
        base_directory: Path | None = None,
    ) -> BackupMetadata:
        validated_pkg_dir = SecurePathValidator.validate_file_path(
            package_directory, base_directory
        )

        if not validated_pkg_dir.is_dir():
            raise ExecutionError(
                message=f"Package directory does not exist: {validated_pkg_dir}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        backup_id = self._generate_backup_id()
        backup_dir = self._create_backup_directory(backup_id)

        self.logger.info(f"Creating package backup: {backup_id}")
        self.security_logger.log_security_event(
            SecurityEventType.BACKUP_CREATED,
            SecurityEventLevel.MEDIUM,
            f"Starting package backup: {backup_id}",
            file_path=validated_pkg_dir,
            backup_id=backup_id,
        )

        try:
            python_files = list[t.Any](validated_pkg_dir.rglob("*.py"))

            files_to_backup = self._filter_package_files(
                python_files, validated_pkg_dir
            )

            if not files_to_backup:
                raise ExecutionError(
                    message="No package files found to backup",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            backup_metadata = self._perform_backup(
                files_to_backup,
                validated_pkg_dir,
                backup_dir,
                backup_id,
            )

            validation_result = self._validate_backup(backup_metadata)

            if not validation_result.is_valid:
                self._cleanup_backup_directory(backup_dir)
                raise ExecutionError(
                    message=f"Backup validation failed: {validation_result.validation_errors}",
                    error_code=ErrorCode.FILE_WRITE_ERROR,
                )

            self.logger.info(
                f"Package backup completed successfully: {backup_id} "
                f"({backup_metadata.total_files} files, {backup_metadata.total_size} bytes)"
            )

            self.security_logger.log_backup_created(
                validated_pkg_dir,
                backup_dir,
                backup_id=backup_id,
                file_count=backup_metadata.total_files,
            )

            return backup_metadata

        except Exception as e:
            self._cleanup_backup_directory(backup_dir)

            if isinstance(e, ExecutionError):
                raise

            raise ExecutionError(
                message=f"Failed to create package backup: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e

    def restore_from_backup(
        self,
        backup_metadata: BackupMetadata,
        base_directory: Path | None = None,
    ) -> None:
        backup_dir = backup_metadata.backup_directory

        if not backup_dir.exists():
            raise ExecutionError(
                message=f"Backup directory not found: {backup_dir}",
                error_code=ErrorCode.FILE_READ_ERROR,
            )

        self.logger.info(f"Restoring from backup: {backup_metadata.backup_id}")
        self.security_logger.log_security_event(
            SecurityEventType.BACKUP_RESTORED,
            SecurityEventLevel.HIGH,
            f"Starting backup restoration: {backup_metadata.backup_id}",
            file_path=backup_dir,
            backup_id=backup_metadata.backup_id,
        )

        validation_result = self._validate_backup(backup_metadata)
        if not validation_result.is_valid:
            raise ExecutionError(
                message=f"Cannot restore corrupted backup: {validation_result.validation_errors}",
                error_code=ErrorCode.FILE_READ_ERROR,
            )

        temp_restore_dir = None
        try:
            temp_restore_dir = self._create_temp_restore_directory(
                backup_metadata.backup_id
            )

            self._stage_backup_files(backup_metadata, temp_restore_dir)

            self._commit_restoration(backup_metadata, temp_restore_dir, base_directory)

            self.logger.info(
                f"Backup restoration completed successfully: {backup_metadata.backup_id}"
            )

            self.security_logger.log_security_event(
                SecurityEventType.BACKUP_RESTORED,
                SecurityEventLevel.HIGH,
                f"Backup restoration completed: {backup_metadata.backup_id}",
                file_path=backup_metadata.package_directory,
                backup_id=backup_metadata.backup_id,
            )

        except Exception as e:
            if isinstance(e, ExecutionError):
                raise

            raise ExecutionError(
                message=f"Failed to restore from backup {backup_metadata.backup_id}: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e

        finally:
            if temp_restore_dir and temp_restore_dir.exists():
                self._cleanup_backup_directory(temp_restore_dir)

    def cleanup_backup(self, backup_metadata: BackupMetadata) -> None:
        backup_dir = backup_metadata.backup_directory

        if backup_dir.exists():
            self._cleanup_backup_directory(backup_dir)

            self.logger.info(f"Backup cleaned up: {backup_metadata.backup_id}")
            self.security_logger.log_security_event(
                SecurityEventType.BACKUP_DELETED,
                SecurityEventLevel.LOW,
                f"Backup cleanup completed: {backup_metadata.backup_id}",
                file_path=backup_dir,
                backup_id=backup_metadata.backup_id,
            )

    def _generate_backup_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_hash = hashlib.md5(
            f"{timestamp}_{time.time()}".encode(),
            usedforsecurity=False,
        ).hexdigest()[:8]
        return f"backup_{timestamp}_{random_hash}"

    def _create_backup_directory(self, backup_id: str) -> Path:
        if not self.backup_root:
            raise ExecutionError(
                message="Backup root directory not configured",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        self.backup_root.mkdir(parents=True, exist_ok=True)

        backup_dir = self.backup_root / backup_id
        backup_dir.mkdir(parents=True, exist_ok=True)

        import stat

        backup_dir.chmod(stat.S_IRWXU)

        return backup_dir

    def _create_temp_restore_directory(self, backup_id: str) -> Path:
        import tempfile

        temp_dir = Path(tempfile.mkdtemp(prefix=f"restore_{backup_id}_"))

        import stat

        temp_dir.chmod(stat.S_IRWXU)

        return temp_dir

    def _filter_package_files(
        self,
        python_files: list[Path],
        package_directory: Path,
    ) -> list[Path]:
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
            ".tox",
            "htmlcov",
        }

        files_to_backup = []

        for file_path in python_files:
            skip_file = False
            for parent in file_path.parents:
                if parent.name in ignore_patterns:
                    skip_file = True
                    break

            if skip_file:
                continue

            if file_path.name.startswith("."):
                continue

            if file_path.suffix != ".py":
                continue

            files_to_backup.append(file_path)

        return files_to_backup

    def _perform_backup(
        self,
        files_to_backup: list[Path],
        package_directory: Path,
        backup_dir: Path,
        backup_id: str,
    ) -> BackupMetadata:
        file_checksums: dict[str, str] = {}
        total_size = 0

        for file_path in files_to_backup:
            try:
                relative_path = file_path.relative_to(package_directory)
                backup_file_path = backup_dir / relative_path

                backup_file_path.parent.mkdir(parents=True, exist_ok=True)

                content = file_path.read_bytes()
                total_size += len(content)

                checksum = hashlib.sha256(content, usedforsecurity=False).hexdigest()
                file_checksums[str(relative_path)] = checksum

                AtomicFileOperations.atomic_write(backup_file_path, content)

                self.logger.debug(f"Backed up file: {relative_path}")

            except Exception as e:
                raise ExecutionError(
                    message=f"Failed to backup file {file_path}: {e}",
                    error_code=ErrorCode.FILE_WRITE_ERROR,
                ) from e

        overall_checksum = self._calculate_backup_checksum(file_checksums)

        return BackupMetadata(
            backup_id=backup_id,
            timestamp=datetime.now(),
            package_directory=package_directory,
            backup_directory=backup_dir,
            total_files=len(files_to_backup),
            total_size=total_size,
            checksum=overall_checksum,
            file_checksums=file_checksums,
        )

    def _calculate_backup_checksum(self, file_checksums: dict[str, str]) -> str:
        sorted_items = sorted(file_checksums.items())
        combined = "".join(f"{path}: {checksum}" for path, checksum in sorted_items)
        return hashlib.sha256(combined.encode(), usedforsecurity=False).hexdigest()

    def _validate_backup(
        self, backup_metadata: BackupMetadata
    ) -> BackupValidationResult:
        missing_files: list[Path] = []
        corrupted_files: list[Path] = []
        validation_errors: list[str] = []
        total_validated = 0

        backup_dir = backup_metadata.backup_directory

        if not backup_dir.exists():
            validation_errors.append(f"Backup directory missing: {backup_dir}")
            return BackupValidationResult(
                is_valid=False,
                missing_files=missing_files,
                corrupted_files=corrupted_files,
                total_validated=0,
                validation_errors=validation_errors,
            )

        for (
            relative_path_str,
            expected_checksum,
        ) in backup_metadata.file_checksums.items():
            backup_file_path = backup_dir / relative_path_str

            if not backup_file_path.exists():
                missing_files.append(backup_file_path)
                validation_errors.append(f"Missing backup file: {relative_path_str}")
                continue

            try:
                content = backup_file_path.read_bytes()
                actual_checksum = hashlib.sha256(
                    content, usedforsecurity=False
                ).hexdigest()

                if actual_checksum != expected_checksum:
                    corrupted_files.append(backup_file_path)
                    validation_errors.append(
                        f"Corrupted backup file: {relative_path_str} "
                        f"(expected: {expected_checksum}, actual: {actual_checksum})"
                    )
                    continue

                total_validated += 1

            except Exception as e:
                validation_errors.append(f"Error validating {relative_path_str}: {e}")

        if not validation_errors:
            recalculated_checksum = self._calculate_backup_checksum(
                backup_metadata.file_checksums
            )
            if recalculated_checksum != backup_metadata.checksum:
                validation_errors.append("Overall backup checksum mismatch")

        is_valid = len(validation_errors) == 0

        if is_valid:
            self.logger.debug(f"Backup validation passed: {backup_metadata.backup_id}")
        else:
            self.logger.warning(
                f"Backup validation failed: {backup_metadata.backup_id}, "
                f"errors: {len(validation_errors)}"
            )

        return BackupValidationResult(
            is_valid=is_valid,
            missing_files=missing_files,
            corrupted_files=corrupted_files,
            total_validated=total_validated,
            validation_errors=validation_errors,
        )

    def _stage_backup_files(
        self,
        backup_metadata: BackupMetadata,
        temp_restore_dir: Path,
    ) -> None:
        backup_dir = backup_metadata.backup_directory

        for relative_path_str in backup_metadata.file_checksums.keys():
            backup_file_path = backup_dir / relative_path_str
            staging_file_path = temp_restore_dir / relative_path_str

            staging_file_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(backup_file_path, staging_file_path)

    def _commit_restoration(
        self,
        backup_metadata: BackupMetadata,
        temp_restore_dir: Path,
        base_directory: Path | None,
    ) -> None:
        package_dir = backup_metadata.package_directory

        for relative_path_str in backup_metadata.file_checksums.keys():
            staging_file_path = temp_restore_dir / relative_path_str
            final_file_path = package_dir / relative_path_str

            final_file_path.parent.mkdir(parents=True, exist_ok=True)

            content = staging_file_path.read_bytes()

            AtomicFileOperations.atomic_write(
                final_file_path,
                content,
                base_directory,
            )

            self.logger.debug(f"Restored file: {relative_path_str}")

    def _cleanup_backup_directory(self, directory: Path) -> None:
        if directory.exists() and directory.is_dir():
            try:
                shutil.rmtree(directory)
            except Exception as e:
                self.logger.warning(f"Failed to cleanup directory {directory}: {e}")
