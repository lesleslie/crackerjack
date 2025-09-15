import asyncio
import contextlib
import fcntl
import logging
import os
import shutil
import time
import typing as t
from pathlib import Path

from ..models.resource_protocols import AbstractFileResource
from .resource_manager import ResourceManager


class AtomicFileWriter(AbstractFileResource):
    def __init__(
        self,
        target_path: Path,
        backup: bool = True,
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(target_path)
        self.backup = backup
        self.manager = manager
        self.temp_path: Path | None = None
        self.backup_path: Path | None = None
        self._file_handle: t.IO[str] | None = None
        self.logger = logging.getLogger(__name__)

        if manager:
            manager.register_resource(self)

    async def _do_initialize(self) -> None:
        self.temp_path = self.path.parent / f".{self.path.name}.tmp.{os.getpid()}"

        if self.backup and self.path.exists():
            self.backup_path = self.path.with_suffix(f"{self.path.suffix}.bak")
            shutil.copy2(self.path, self.backup_path)

        self._file_handle = self.temp_path.open("w", encoding="utf-8")

    async def _do_cleanup(self) -> None:
        if self._file_handle and not self._file_handle.closed:
            self._file_handle.close()

        if self.temp_path and self.temp_path.exists():
            try:
                self.temp_path.unlink()
            except OSError as e:
                self.logger.warning(f"Failed to remove temp file {self.temp_path}: {e}")

        if self.backup_path and self.backup_path.exists():
            try:
                self.backup_path.unlink()
            except OSError as e:
                self.logger.warning(
                    f"Failed to remove backup file {self.backup_path}: {e}"
                )

    def write(self, content: str) -> None:
        if not self._file_handle:
            raise RuntimeError("AtomicFileWriter not initialized")
        self._file_handle.write(content)

    def writelines(self, lines: t.Iterable[str]) -> None:
        if not self._file_handle:
            raise RuntimeError("AtomicFileWriter not initialized")
        self._file_handle.writelines(lines)

    def flush(self) -> None:
        if not self._file_handle:
            raise RuntimeError("AtomicFileWriter not initialized")
        self._file_handle.flush()
        os.fsync(self._file_handle.fileno())

    async def commit(self) -> None:
        if not self.temp_path:
            raise RuntimeError("AtomicFileWriter not initialized")

        self.flush()

        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

        try:
            self.temp_path.replace(self.path)
            self.logger.debug(f"Successfully committed changes to {self.path}")
        except OSError as e:
            if self.backup_path and self.backup_path.exists():
                try:
                    self.backup_path.replace(self.path)
                    self.logger.info(
                        f"Restored {self.path} from backup after commit failure"
                    )
                except OSError:
                    self.logger.error(f"Failed to restore {self.path} from backup")
            raise RuntimeError(f"Failed to commit changes to {self.path}") from e

    async def rollback(self) -> None:
        if self.backup_path and self.backup_path.exists():
            try:
                self.backup_path.replace(self.path)
                self.logger.info(f"Rolled back changes to {self.path}")
            except OSError as e:
                self.logger.error(f"Failed to rollback {self.path}: {e}")
                raise


class LockedFileResource(AbstractFileResource):
    def __init__(
        self,
        path: Path,
        mode: str = "r+",
        timeout: float = 30.0,
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(path)
        self.mode = mode
        self.timeout = timeout
        self._file_handle: t.IO[str] | None = None
        self.logger = logging.getLogger(__name__)

        if manager:
            manager.register_resource(self)

    async def _do_initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._file_handle = self.path.open(self.mode)

        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.logger.debug(f"Acquired lock on {self.path}")
                return
            except OSError:
                await asyncio.sleep(0.1)

        raise TimeoutError(
            f"Failed to acquire lock on {self.path} within {self.timeout}s"
        )

    async def _do_cleanup(self) -> None:
        if self._file_handle and not self._file_handle.closed:
            try:
                fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
                self.logger.debug(f"Released lock on {self.path}")
            except OSError as e:
                self.logger.warning(f"Failed to release lock on {self.path}: {e}")
            finally:
                self._file_handle.close()

    @property
    def file_handle(self) -> t.IO[str]:
        if not self._file_handle:
            raise RuntimeError("LockedFileResource not initialized")
        return self._file_handle

    def read(self) -> str:
        self.file_handle.seek(0)
        return self.file_handle.read()

    def write(self, content: str) -> None:
        self.file_handle.seek(0)
        self.file_handle.write(content)
        self.file_handle.truncate()
        self.file_handle.flush()
        os.fsync(self.file_handle.fileno())


class SafeDirectoryCreator(AbstractFileResource):
    def __init__(
        self,
        path: Path,
        cleanup_on_error: bool = True,
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(path)
        self.cleanup_on_error = cleanup_on_error
        self._created_dirs: list[Path] = []
        self.logger = logging.getLogger(__name__)

        if manager:
            manager.register_resource(self)

    async def _do_initialize(self) -> None:
        current = self.path

        while not current.exists():
            self._created_dirs.append(current)
            current = current.parent

        self._created_dirs.reverse()

        for dir_path in self._created_dirs:
            try:
                dir_path.mkdir(exist_ok=True)
                self.logger.debug(f"Created directory: {dir_path}")
            except OSError as e:
                self.logger.error(f"Failed to create directory {dir_path}: {e}")
                if self.cleanup_on_error:
                    await self._cleanup_created_dirs()
                raise

    async def _do_cleanup(self) -> None:
        if self.cleanup_on_error:
            await self._cleanup_created_dirs()

    async def _cleanup_created_dirs(self) -> None:
        for dir_path in reversed(self._created_dirs):
            try:
                if dir_path.exists() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    self.logger.debug(f"Removed directory: {dir_path}")
            except OSError as e:
                self.logger.warning(f"Failed to remove directory {dir_path}: {e}")


class BatchFileOperations:
    def __init__(self, manager: ResourceManager | None = None) -> None:
        self.manager = manager or ResourceManager()
        self.operations: list[t.Callable[[], None]] = []
        self.rollback_operations: list[t.Callable[[], None]] = []
        self.logger = logging.getLogger(__name__)

    def add_write_operation(
        self,
        path: Path,
        content: str,
        backup: bool = True,
    ) -> None:
        def write_op() -> None:
            writer = AtomicFileWriter(path, backup, self.manager)
            asyncio.create_task(writer.initialize())
            writer.write(content)
            asyncio.create_task(writer.commit())

        def rollback_op() -> None:
            writer = AtomicFileWriter(path, backup)
            asyncio.create_task(writer.rollback())

        self.operations.append(write_op)
        self.rollback_operations.append(rollback_op)

    def add_copy_operation(
        self,
        source: Path,
        dest: Path,
        backup: bool = True,
    ) -> None:
        def copy_op() -> None:
            if backup and dest.exists():
                backup_path = dest.with_suffix(f"{dest.suffix}.bak")
                shutil.copy2(dest, backup_path)
            shutil.copy2(source, dest)

        def rollback_op() -> None:
            if backup:
                backup_path = dest.with_suffix(f"{dest.suffix}.bak")
                if backup_path.exists():
                    shutil.move(backup_path, dest)

        self.operations.append(copy_op)
        self.rollback_operations.append(rollback_op)

    def add_move_operation(
        self,
        source: Path,
        dest: Path,
    ) -> None:
        def move_op() -> None:
            shutil.move(source, dest)

        def rollback_op() -> None:
            shutil.move(dest, source)

        self.operations.append(move_op)
        self.rollback_operations.append(rollback_op)

    def add_delete_operation(
        self,
        path: Path,
        backup: bool = True,
    ) -> None:
        backup_path: Path | None = None

        def delete_op() -> None:
            nonlocal backup_path
            if backup and path.exists():
                backup_path = path.with_suffix(f"{path.suffix}.bak.{os.getpid()}")
                shutil.move(path, backup_path)
            elif path.exists():
                path.unlink()

        def rollback_op() -> None:
            if backup_path and backup_path.exists():
                shutil.move(backup_path, path)

        self.operations.append(delete_op)
        self.rollback_operations.append(rollback_op)

    async def commit_all(self) -> None:
        executed_ops = 0

        try:
            for i, operation in enumerate(self.operations):
                operation()
                executed_ops = i + 1

            self.logger.info(f"Successfully executed {executed_ops} file operations")

        except Exception as e:
            self.logger.error(f"Batch operation failed at step {executed_ops}: {e}")

            for i in range(executed_ops - 1, -1, -1):
                try:
                    self.rollback_operations[i]()
                except Exception as rollback_error:
                    self.logger.error(
                        f"Rollback failed for operation {i}: {rollback_error}"
                    )

            raise RuntimeError("Batch file operations failed and rolled back") from e


@contextlib.asynccontextmanager
async def atomic_file_write(
    path: Path,
    backup: bool = True,
) -> t.AsyncGenerator[AtomicFileWriter]:
    writer = AtomicFileWriter(path, backup)
    try:
        await writer.initialize()
        yield writer
        await writer.commit()
    except Exception:
        await writer.rollback()
        raise
    finally:
        await writer.cleanup()


@contextlib.asynccontextmanager
async def locked_file_access(
    path: Path,
    mode: str = "r+",
    timeout: float = 30.0,
) -> t.AsyncGenerator[LockedFileResource]:
    file_resource = LockedFileResource(path, mode, timeout)
    try:
        await file_resource.initialize()
        yield file_resource
    finally:
        await file_resource.cleanup()


@contextlib.asynccontextmanager
async def safe_directory_creation(
    path: Path,
    cleanup_on_error: bool = True,
) -> t.AsyncGenerator[SafeDirectoryCreator]:
    creator = SafeDirectoryCreator(path, cleanup_on_error)
    try:
        await creator.initialize()
        yield creator
    finally:
        await creator.cleanup()


@contextlib.asynccontextmanager
async def batch_file_operations() -> t.AsyncGenerator[BatchFileOperations]:
    batch = BatchFileOperations()
    try:
        yield batch
        await batch.commit_all()
    except Exception:
        raise


class SafeFileOperations:
    @staticmethod
    async def safe_read_text(
        path: Path,
        encoding: str = "utf-8",
        fallback_encodings: list[str] | None = None,
    ) -> str:
        fallback_encodings = fallback_encodings or ["latin-1", "cp1252"]

        for enc in [encoding] + fallback_encodings:
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                raise
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Failed to read {path} with encoding {enc}: {e}"
                )
                continue

        raise RuntimeError(f"Failed to read {path} with any supported encoding")

    @staticmethod
    async def safe_write_text(
        path: Path,
        content: str,
        encoding: str = "utf-8",
        atomic: bool = True,
        backup: bool = True,
    ) -> None:
        if atomic:
            async with atomic_file_write(path, backup) as writer:
                writer.write(content)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=encoding)

    @staticmethod
    async def safe_copy_file(
        source: Path,
        dest: Path,
        preserve_metadata: bool = True,
        backup: bool = True,
    ) -> None:
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        if backup and dest.exists():
            backup_path = dest.with_suffix(f"{dest.suffix}.bak")
            shutil.copy2(dest, backup_path)

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)

            if preserve_metadata:
                shutil.copy2(source, dest)
            else:
                shutil.copy(source, dest)

        except Exception as e:
            if backup and dest.with_suffix(f"{dest.suffix}.bak").exists():
                shutil.move(dest.with_suffix(f"{dest.suffix}.bak"), dest)
            raise RuntimeError(f"Failed to copy {source} to {dest}") from e

    @staticmethod
    async def safe_move_file(
        source: Path,
        dest: Path,
        backup: bool = True,
    ) -> None:
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        backup_path = None
        if backup and dest.exists():
            backup_path = dest.with_suffix(f"{dest.suffix}.bak.{os.getpid()}")
            shutil.move(dest, backup_path)

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source, dest)

            if backup_path and backup_path.exists():
                backup_path.unlink()

        except Exception as e:
            if backup_path and backup_path.exists():
                shutil.move(backup_path, dest)
            raise RuntimeError(f"Failed to move {source} to {dest}") from e
