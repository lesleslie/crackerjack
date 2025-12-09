import shutil
from collections.abc import Iterator
from pathlib import Path

from crackerjack.errors import ErrorCode, FileError, ResourceError
from crackerjack.models.protocols import FileSystemInterface


class FileSystemService(FileSystemInterface):
    @staticmethod
    def clean_trailing_whitespace_and_newlines(content: str) -> str:
        lines = content.splitlines()
        cleaned_lines = [line.rstrip() for line in lines]

        result = "\n".join(cleaned_lines)
        if result and not result.endswith("\n"):
            result += "\n"

        return result

    def _validate_path_exists(self, path_obj: Path, operation: str) -> None:
        """Validate that a path exists."""
        if not path_obj.exists():
            raise FileError(
                message=f"File does not exist: {path_obj}",
                details=f"Attempted to {operation} file at {path_obj.absolute()}",
                recovery="Check file path and ensure file exists",
            )

    def _handle_permission_error(
        self, error: PermissionError, path: str | Path, operation: str
    ) -> None:
        """Handle permission errors."""
        raise FileError(
            message=f"Permission denied {operation}: {path}",
            error_code=ErrorCode.PERMISSION_ERROR,
            details=str(error),
            recovery="Check file permissions and user access rights",
        ) from error

    def _handle_unicode_error(
        self, error: UnicodeDecodeError, path: str | Path
    ) -> None:
        """Handle unicode decode errors."""
        raise FileError(
            message=f"Unable to decode file as UTF-8: {path}",
            error_code=ErrorCode.FILE_READ_ERROR,
            details=str(error),
            recovery="Ensure file is text - based and UTF-8 encoded",
        ) from error

    def _handle_os_error(
        self, error: OSError, path: str | Path, operation: str
    ) -> None:
        """Handle OS errors."""
        raise FileError(
            message=f"System error {operation}: {path}",
            error_code=ErrorCode.FILE_READ_ERROR,
            details=str(error),
            recovery="Check disk space and file system integrity",
        ) from error

    def _handle_disk_space_error(
        self, error: OSError, path: str | Path, operation: str
    ) -> None:
        """Handle disk space errors."""
        if "No space left on device" in str(error):
            raise ResourceError(
                message=f"Insufficient disk space to {operation}: {path}",
                details=str(error),
                recovery="Free up disk space and try again",
            ) from error
        raise FileError(
            message=f"System error {operation}: {path}",
            error_code=ErrorCode.FILE_WRITE_ERROR,
            details=str(error),
            recovery="Check disk space and file system integrity",
        ) from error

    def read_file(self, path: str | Path) -> str:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            self._validate_path_exists(path_obj, "read")
            return path_obj.read_text(encoding="utf-8")
        except PermissionError as e:
            self._handle_permission_error(e, path, "reading file")
            raise  # Ensure type checker knows this doesn't return
        except UnicodeDecodeError as e:
            self._handle_unicode_error(e, path)
            raise  # Ensure type checker knows this doesn't return
        except OSError as e:
            self._handle_os_error(e, path, "reading file")
            raise  # Ensure type checker knows this doesn't return

    def write_file(self, path: str | Path, content: str) -> None:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            try:
                path_obj.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise FileError(
                    message=f"Cannot create parent directories for: {path}",
                    error_code=ErrorCode.FILE_WRITE_ERROR,
                    details=str(e),
                    recovery="Check disk space and directory permissions",
                ) from e

            if path_obj.name in {".pre-commit-config.yaml", "pyproject.toml"}:
                content = self.clean_trailing_whitespace_and_newlines(content)

            path_obj.write_text(content, encoding="utf-8")
        except PermissionError as e:
            raise FileError(
                message=f"Permission denied writing file: {path}",
                error_code=ErrorCode.PERMISSION_ERROR,
                details=str(e),
                recovery="Check file and directory permissions",
            ) from e
        except OSError as e:
            if "No space left on device" in str(e):
                raise ResourceError(
                    message=f"Insufficient disk space to write file: {path}",
                    details=str(e),
                    recovery="Free up disk space and try again",
                ) from e
            raise FileError(
                message=f"System error writing file: {path}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
                details=str(e),
                recovery="Check disk space and file system integrity",
            ) from e

    def exists(self, path: str | Path) -> bool:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            return path_obj.exists()
        except OSError:
            return False

    def mkdir(self, path: str | Path, parents: bool = False) -> None:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            path_obj.mkdir(parents=parents, exist_ok=True)
        except PermissionError as e:
            self._handle_permission_error(e, path, "creating directory")
        except FileExistsError as e:
            if not parents:
                raise FileError(
                    message=f"Directory already exists: {path}",
                    details=str(e),
                    recovery="Use exist_ok=True or check if directory exists first",
                ) from e
        except OSError as e:
            self._handle_disk_space_error(e, path, "create directory")

    def glob(self, pattern: str, path: str | Path | None = None) -> list[Path]:
        base_path = Path(path) if path else Path.cwd()
        try:
            if not base_path.exists():
                raise FileError(
                    message=f"Base path does not exist: {base_path}",
                    details=f"Attempted to glob in {base_path.absolute()}",
                    recovery="Check base path and ensure directory exists",
                )
            return list(base_path.glob(pattern))
        except PermissionError as e:
            raise FileError(
                message=f"Permission denied accessing directory: {base_path}",
                error_code=ErrorCode.PERMISSION_ERROR,
                details=str(e),
                recovery="Check directory permissions",
            ) from e
        except OSError as e:
            raise FileError(
                message=f"System error during glob operation: {pattern}",
                error_code=ErrorCode.FILE_READ_ERROR,
                details=str(e),
                recovery="Check path validity and file system integrity",
            ) from e

    def rglob(self, pattern: str, path: str | Path | None = None) -> list[Path]:
        base_path = Path(path) if path else Path.cwd()
        try:
            if not base_path.exists():
                raise FileError(
                    message=f"Base path does not exist: {base_path}",
                    details=f"Attempted to rglob in {base_path.absolute()}",
                    recovery="Check base path and ensure directory exists",
                )
            return list(base_path.rglob(pattern))
        except PermissionError as e:
            raise FileError(
                message=f"Permission denied accessing directory: {base_path}",
                error_code=ErrorCode.PERMISSION_ERROR,
                details=str(e),
                recovery="Check directory permissions",
            ) from e
        except OSError as e:
            raise FileError(
                message=f"System error during recursive glob operation: {pattern}",
                error_code=ErrorCode.FILE_READ_ERROR,
                details=str(e),
                recovery="Check path validity and file system integrity",
            ) from e

    def copy_file(self, src: str | Path, dst: str | Path) -> None:
        src_path, dst_path = self._normalize_copy_paths(src, dst)
        self._validate_copy_source(src_path)
        self._prepare_copy_destination(dst_path)
        self._perform_file_copy(src_path, dst_path, src, dst)

    def _normalize_copy_paths(
        self, src: str | Path, dst: str | Path
    ) -> tuple[Path, Path]:
        src_path = Path(src) if isinstance(src, str) else src
        dst_path = Path(dst) if isinstance(dst, str) else dst
        return src_path, dst_path

    def _validate_copy_source(self, src_path: Path) -> None:
        if not src_path.exists():
            raise FileError(
                message=f"Source file does not exist: {src_path}",
                details=f"Attempted to copy from {src_path.absolute()}",
                recovery="Check source file path and ensure file exists",
            )
        if not src_path.is_file():
            raise FileError(
                message=f"Source is not a file: {src_path}",
                details=f"Source is a {src_path.stat().st_mode} type",
                recovery="Ensure source path points to a regular file",
            )

    def _prepare_copy_destination(self, dst_path: Path) -> None:
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise FileError(
                message=f"Cannot create destination parent directories: {dst_path.parent}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
                details=str(e),
                recovery="Check disk space and directory permissions",
            ) from e

    def _perform_file_copy(
        self, src_path: Path, dst_path: Path, src: str | Path, dst: str | Path
    ) -> None:
        try:
            shutil.copy2(src_path, dst_path)
        except PermissionError as e:
            self._handle_permission_error(e, f"{src} -> {dst}", "copying file")
        except shutil.SameFileError as e:
            raise FileError(
                message=f"Source and destination are the same file: {src}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
                details=str(e),
                recovery="Ensure source and destination paths are different",
            ) from e
        except OSError as e:
            self._handle_disk_space_error(e, f"{src} -> {dst}", "copy file")

    def remove_file(self, path: str | Path) -> None:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            if path_obj.exists():
                if not path_obj.is_file():
                    raise FileError(
                        message=f"Path is not a file: {path_obj}",
                        details=f"Path type: {path_obj.stat().st_mode}",
                        recovery="Use appropriate method for directory removal",
                    )
                path_obj.unlink()
        except PermissionError as e:
            raise FileError(
                message=f"Permission denied removing file: {path}",
                error_code=ErrorCode.PERMISSION_ERROR,
                details=str(e),
                recovery="Check file permissions and ownership",
            ) from e
        except OSError as e:
            raise FileError(
                message=f"System error removing file: {path}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
                details=str(e),
                recovery="Check file system integrity and try again",
            ) from e

    def get_file_size(self, path: str | Path) -> int:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            if not path_obj.exists():
                raise FileError(
                    message=f"File does not exist: {path_obj}",
                    details=f"Attempted to get size of {path_obj.absolute()}",
                    recovery="Check file path and ensure file exists",
                )
            if not path_obj.is_file():
                raise FileError(
                    message=f"Path is not a file: {path_obj}",
                    details=f"Path type: {path_obj.stat().st_mode}",
                    recovery="Ensure path points to a regular file",
                )
            return path_obj.stat().st_size
        except PermissionError as e:
            raise FileError(
                message=f"Permission denied accessing file: {path}",
                error_code=ErrorCode.PERMISSION_ERROR,
                details=str(e),
                recovery="Check file permissions",
            ) from e
        except OSError as e:
            raise FileError(
                message=f"System error getting file size: {path}",
                error_code=ErrorCode.FILE_READ_ERROR,
                details=str(e),
                recovery="Check file system integrity",
            ) from e

    def get_file_mtime(self, path: str | Path) -> float:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            if not path_obj.exists():
                raise FileError(
                    message=f"File does not exist: {path_obj}",
                    details=f"Attempted to get mtime of {path_obj.absolute()}",
                    recovery="Check file path and ensure file exists",
                )
            if not path_obj.is_file():
                raise FileError(
                    message=f"Path is not a file: {path_obj}",
                    details=f"Path type: {path_obj.stat().st_mode}",
                    recovery="Ensure path points to a regular file",
                )
            return path_obj.stat().st_mtime
        except PermissionError as e:
            raise FileError(
                message=f"Permission denied accessing file: {path}",
                error_code=ErrorCode.PERMISSION_ERROR,
                details=str(e),
                recovery="Check file permissions",
            ) from e
        except OSError as e:
            raise FileError(
                message=f"System error getting file modification time: {path}",
                error_code=ErrorCode.FILE_READ_ERROR,
                details=str(e),
                recovery="Check file system integrity",
            ) from e

    def read_file_chunked(
        self,
        path: str | Path,
        chunk_size: int = 8192,
    ) -> Iterator[str]:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            self._validate_path_exists(path_obj, "read")

            with path_obj.open(encoding="utf-8") as file:
                while chunk := file.read(chunk_size):
                    yield chunk

        except PermissionError as e:
            self._handle_permission_error(e, path, "reading file")
        except UnicodeDecodeError as e:
            self._handle_unicode_error(e, path)
        except OSError as e:
            self._handle_os_error(e, path, "reading file")

    def read_lines_streaming(self, path: str | Path) -> Iterator[str]:
        try:
            path_obj = Path(path) if isinstance(path, str) else path
            self._validate_path_exists(path_obj, "read")
            with path_obj.open(encoding="utf-8") as file:
                for line in file:
                    yield line.rstrip("\n\r")
        except PermissionError as e:
            self._handle_permission_error(e, path, "reading file")
        except UnicodeDecodeError as e:
            self._handle_unicode_error(e, path)
        except OSError as e:
            self._handle_os_error(e, path, "reading file")
