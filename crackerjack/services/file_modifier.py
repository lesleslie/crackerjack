import difflib
import os
import shutil
import tempfile
import typing as t
from contextlib import suppress
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

from loguru import logger

from crackerjack.models.protocols import SafeFileModifierProtocol, ServiceProtocol


class SafeFileModifier(SafeFileModifierProtocol, ServiceProtocol):
    FORBIDDEN_PATTERNS = [
        ".env*",
        ".git/*",
        "*.key",
        "*.pem",
        "*.crt",
        "*_rsa",
        "*_dsa",
        "*_ed25519",
        "*.p12",
        "*.pfx",
        "id_rsa*",
        "*.secret",
        "secrets.*",
        ".ssh/*",
    ]

    def __init__(
        self,
        backup_dir: Path | None = None,
        max_file_size: int = 10_485_760,
    ):
        self._backup_dir = backup_dir or Path(".backups")
        self._max_file_size = max_file_size
        self._ensure_backup_dir()

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    def _ensure_backup_dir(self) -> None:
        if not self._backup_dir.exists():
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created backup directory: {self._backup_dir}")

    async def apply_fix(
        self,
        file_path: str,
        fixed_content: str,
        dry_run: bool = False,
        create_backup: bool = True,
    ) -> dict[str, t.Any]:
        return await self._apply_fix(file_path, fixed_content, dry_run, create_backup)

    async def _apply_fix(
        self,
        file_path: str,
        fixed_content: str,
        dry_run: bool,
        create_backup: bool,
    ) -> dict[str, t.Any]:
        path = Path(file_path)

        result: dict[str, t.Any] = self._validate_fix_inputs(path, fixed_content)
        if not result["success"]:
            return result

        result = self._read_original_content(path)
        if not result["success"]:
            return result
        original_content = result["content"]

        assert isinstance(original_content, str)
        diff = self._generate_diff(original_content, fixed_content, file_path)

        if dry_run:
            return self._create_dry_run_result(diff)

        assert isinstance(original_content, str)
        result = self._handle_backup(path, original_content, create_backup, diff)
        if not result["success"]:
            return result
        backup_path = result.get("backup_path")

        assert backup_path is None or isinstance(backup_path, Path)

        return self._atomic_write_fix(path, fixed_content, diff, backup_path, file_path)

    def _validate_fix_inputs(
        self, path: Path, fixed_content: str
    ) -> dict[str, str | bool | None]:
        validation_result = self._validate_file_path(path)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": validation_result["error"],
                "diff": "",
                "backup_path": None,
            }

        if len(fixed_content) > self._max_file_size:
            return {
                "success": False,
                "error": f"Content size {len(fixed_content)} exceeds limit {self._max_file_size}",
                "diff": "",
                "backup_path": None,
            }

        return {"success": True}

    def _read_original_content(self, path: Path) -> dict[str, str | bool | None]:
        try:
            original_content = path.read_text(encoding="utf-8")
            return {"success": True, "content": original_content}
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": f"File is not valid UTF-8: {path}",
                "diff": "",
                "backup_path": None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read file: {e}",
                "diff": "",
                "backup_path": None,
            }

    def _create_dry_run_result(self, diff: str) -> dict[str, str | bool | None]:
        return {
            "success": True,
            "diff": diff,
            "backup_path": None,
            "dry_run": True,
            "message": "Dry-run: Changes not applied",
        }

    def _handle_backup(
        self, path: Path, original_content: str, create_backup: bool, diff: str
    ) -> dict[str, str | bool | Path | None]:
        if not create_backup:
            return {"success": True, "backup_path": None}

        try:
            backup_path = self._create_backup(path, original_content)
            return {"success": True, "backup_path": backup_path}
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return {
                "success": False,
                "error": f"Backup creation failed: {e}",
                "diff": diff,
                "backup_path": None,
            }

    def _atomic_write_fix(
        self,
        path: Path,
        fixed_content: str,
        diff: str,
        backup_path: Path | None,
        file_path: str,
    ) -> dict[str, str | bool | None]:
        try:
            temp_fd, temp_path_str = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
            )

            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                    f.flush()
                    os.fsync(f.fileno())

                original_stat = path.stat()
                os.chmod(temp_path_str, original_stat.st_mode)
                shutil.move(temp_path_str, path)

                logger.info(f"Successfully applied fix to {file_path}")

                return {
                    "success": True,
                    "diff": diff,
                    "backup_path": str(backup_path) if backup_path else None,
                    "dry_run": False,
                    "message": f"Fix applied successfully to {file_path}",
                }

            except Exception:
                with suppress(Exception):
                    Path(temp_path_str).unlink()
                raise

        except Exception as e:
            if backup_path:
                logger.warning(f"Fix failed, restoring from backup: {e}")
                try:
                    self._restore_backup(path, backup_path)
                except Exception as restore_error:
                    logger.error(f"Rollback failed: {restore_error}")
                    return {
                        "success": False,
                        "error": f"Failed to write file AND rollback failed: {e} (rollback: {restore_error})",
                        "diff": diff,
                        "backup_path": str(backup_path) if backup_path else None,
                    }

            return {
                "success": False,
                "error": f"Failed to write file: {e}",
                "diff": diff,
                "backup_path": str(backup_path) if backup_path else None,
            }

    def _check_file_exists(self, path: Path) -> dict[str, bool | str]:
        if not path.exists():
            return {
                "valid": False,
                "error": f"File does not exist: {path}",
            }
        return {"valid": True, "error": ""}

    def _check_is_symlink(self, path: Path) -> dict[str, bool | str]:
        if path.is_symlink():
            return {
                "valid": False,
                "error": f"Symlinks are not allowed for security reasons: {path}",
            }
        return {"valid": True, "error": ""}

    def _check_is_file(self, path: Path) -> dict[str, bool | str]:
        if not path.is_file():
            return {
                "valid": False,
                "error": f"Path is not a file: {path}",
            }
        return {"valid": True, "error": ""}

    def _check_forbidden_patterns(self, path: Path) -> dict[str, bool | str]:
        file_str = str(path)
        for pattern in self.FORBIDDEN_PATTERNS:
            if fnmatch(file_str, pattern) or fnmatch(path.name, pattern):
                return {
                    "valid": False,
                    "error": f"File matches forbidden pattern '{pattern}': {path}",
                }
        return {"valid": True, "error": ""}

    def _check_file_size(self, path: Path) -> dict[str, bool | str]:
        try:
            file_size = path.stat().st_size
            if file_size > self._max_file_size:
                return {
                    "valid": False,
                    "error": f"File size {file_size} exceeds limit {self._max_file_size}",
                }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Failed to check file size: {e}",
            }
        return {"valid": True, "error": ""}

    def _check_file_writable(self, path: Path) -> dict[str, bool | str]:
        if not os.access(path, os.W_OK):
            return {
                "valid": False,
                "error": f"File is not writable: {path}",
            }
        return {"valid": True, "error": ""}

    def _check_path_traversal(self, path: Path) -> dict[str, bool | str]:
        try:
            resolved_path = path.resolve()
            project_root = Path.cwd().resolve()

            resolved_path.relative_to(project_root)

        except ValueError:
            return {
                "valid": False,
                "error": f"File path outside project directory: {path}",
            }
        return {"valid": True, "error": ""}

    def _check_symlinks_in_path_chain(self, path: Path) -> dict[str, bool | str]:
        current = path
        while current != current.parent:
            if current.is_symlink():
                return {
                    "valid": False,
                    "error": f"Symlink in path chain not allowed: {current}",
                }
            current = current.parent
        return {"valid": True, "error": ""}

    def _validate_file_path(self, path: Path) -> dict[str, bool | str]:
        result = self._check_file_exists(path)
        if not result["valid"]:
            return result

        result = self._check_is_symlink(path)
        if not result["valid"]:
            return result

        result = self._check_is_file(path)
        if not result["valid"]:
            return result

        result = self._check_forbidden_patterns(path)
        if not result["valid"]:
            return result

        result = self._check_file_size(path)
        if not result["valid"]:
            return result

        result = self._check_file_writable(path)
        if not result["valid"]:
            return result

        result = self._check_path_traversal(path)
        if not result["valid"]:
            return result

        return self._check_symlinks_in_path_chain(path)

    def _create_backup(
        self,
        file_path: Path,
        content: str,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}_{timestamp}.bak"
        backup_path = self._backup_dir / backup_name

        backup_path.write_text(content, encoding="utf-8")

        logger.debug(f"Created backup: {backup_path}")

        return backup_path

    def _restore_backup(
        self,
        file_path: Path,
        backup_path: Path,
    ) -> None:
        try:
            backup_content = backup_path.read_text(encoding="utf-8")
            file_path.write_text(backup_content, encoding="utf-8")

            logger.info(f"Restored {file_path} from backup")

        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise

    def _generate_diff(
        self,
        original: str,
        fixed: str,
        filename: str,
    ) -> str:
        original_lines = original.splitlines(keepends=True)
        fixed_lines = fixed.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            fixed_lines,
            fromfile=f"{filename} (original)",
            tofile=f"{filename} (fixed)",
            lineterm="",
        )

        return "".join(diff)
