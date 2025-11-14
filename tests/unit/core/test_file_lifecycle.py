"""Unit tests for file_lifecycle.

Tests atomic file writing, file locking, safe directory creation,
batch operations, and safe file operations.
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.core.file_lifecycle import (
    AtomicFileWriter,
    BatchFileOperations,
    LockedFileResource,
    SafeDirectoryCreator,
    SafeFileOperations,
    atomic_file_write,
    batch_file_operations,
    locked_file_access,
    safe_directory_creation,
)
from crackerjack.core.resource_manager import ResourceManager


@pytest.mark.unit
class TestAtomicFileWriterInitialization:
    """Test AtomicFileWriter initialization."""

    def test_initialization_basic(self, tmp_path):
        """Test basic initialization."""
        target = tmp_path / "test.txt"

        writer = AtomicFileWriter(target)

        assert writer.path == target
        assert writer.backup is True
        assert writer.manager is None
        assert writer.temp_path is None
        assert writer.backup_path is None

    def test_initialization_no_backup(self, tmp_path):
        """Test initialization without backup."""
        target = tmp_path / "test.txt"

        writer = AtomicFileWriter(target, backup=False)

        assert writer.backup is False

    def test_initialization_with_manager(self, tmp_path):
        """Test initialization with resource manager."""
        target = tmp_path / "test.txt"
        manager = ResourceManager()

        writer = AtomicFileWriter(target, manager=manager)

        assert writer.manager == manager


@pytest.mark.unit
class TestAtomicFileWriterLifecycle:
    """Test AtomicFileWriter lifecycle."""

    @pytest.mark.asyncio
    async def test_initialize_creates_temp_file(self, tmp_path):
        """Test initialization creates temp file."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=False)

        await writer.initialize()

        assert writer.temp_path is not None
        assert writer.temp_path.exists()
        assert writer._file_handle is not None

        await writer.cleanup()

    @pytest.mark.asyncio
    async def test_initialize_creates_backup(self, tmp_path):
        """Test initialization creates backup of existing file."""
        target = tmp_path / "test.txt"
        target.write_text("original content")

        writer = AtomicFileWriter(target, backup=True)
        await writer.initialize()

        assert writer.backup_path is not None
        assert writer.backup_path.exists()
        assert writer.backup_path.read_text() == "original content"

        await writer.cleanup()

    @pytest.mark.asyncio
    async def test_initialize_no_backup_for_new_file(self, tmp_path):
        """Test no backup created for non-existent file."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=True)

        await writer.initialize()

        assert writer.backup_path is None

        await writer.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_removes_temp_file(self, tmp_path):
        """Test cleanup removes temp file."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=False)

        await writer.initialize()
        temp_path = writer.temp_path

        await writer.cleanup()

        assert not temp_path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_removes_backup(self, tmp_path):
        """Test cleanup removes backup file."""
        target = tmp_path / "test.txt"
        target.write_text("original")

        writer = AtomicFileWriter(target, backup=True)
        await writer.initialize()
        backup_path = writer.backup_path

        await writer.cleanup()

        assert not backup_path.exists()


@pytest.mark.unit
class TestAtomicFileWriterOperations:
    """Test AtomicFileWriter write operations."""

    @pytest.mark.asyncio
    async def test_write_content(self, tmp_path):
        """Test writing content."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=False)

        await writer.initialize()
        writer.write("test content")
        await writer.commit()

        assert target.read_text() == "test content"

        await writer.cleanup()

    @pytest.mark.asyncio
    async def test_write_without_initialize_raises_error(self, tmp_path):
        """Test writing without initialization raises error."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=False)

        with pytest.raises(RuntimeError, match="not initialized"):
            writer.write("content")

    @pytest.mark.asyncio
    async def test_writelines(self, tmp_path):
        """Test writing lines."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=False)

        await writer.initialize()
        writer.writelines(["line1\n", "line2\n", "line3\n"])
        await writer.commit()

        assert target.read_text() == "line1\nline2\nline3\n"

        await writer.cleanup()

    @pytest.mark.asyncio
    async def test_flush_syncs_data(self, tmp_path):
        """Test flush syncs data to disk."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=False)

        await writer.initialize()
        writer.write("test")
        writer.flush()

        # Data should be written to temp file
        assert writer.temp_path.exists()

        await writer.cleanup()


@pytest.mark.unit
class TestAtomicFileWriterCommitRollback:
    """Test AtomicFileWriter commit and rollback."""

    @pytest.mark.asyncio
    async def test_commit_replaces_target(self, tmp_path):
        """Test commit replaces target file."""
        target = tmp_path / "test.txt"
        target.write_text("original")

        writer = AtomicFileWriter(target, backup=True)
        await writer.initialize()
        writer.write("updated")
        await writer.commit()

        assert target.read_text() == "updated"

        await writer.cleanup()

    @pytest.mark.asyncio
    async def test_commit_without_initialize_raises_error(self, tmp_path):
        """Test commit without initialization raises error."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=False)

        with pytest.raises(RuntimeError, match="not initialized"):
            await writer.commit()

    @pytest.mark.asyncio
    async def test_commit_failure_restores_backup(self, tmp_path):
        """Test commit failure restores from backup."""
        target = tmp_path / "test.txt"
        target.write_text("original")

        writer = AtomicFileWriter(target, backup=True)
        await writer.initialize()
        writer.write("updated")

        # Simulate commit failure by making target read-only
        with patch.object(Path, "replace", side_effect=OSError("Permission denied")):
            with pytest.raises(RuntimeError, match="Failed to commit"):
                await writer.commit()

        await writer.cleanup()

    @pytest.mark.asyncio
    async def test_rollback_restores_backup(self, tmp_path):
        """Test rollback restores from backup."""
        target = tmp_path / "test.txt"
        target.write_text("original")

        writer = AtomicFileWriter(target, backup=True)
        await writer.initialize()
        writer.write("updated")
        await writer.rollback()

        assert target.read_text() == "original"

        await writer.cleanup()

    @pytest.mark.asyncio
    async def test_rollback_without_backup_does_nothing(self, tmp_path):
        """Test rollback without backup does nothing."""
        target = tmp_path / "test.txt"
        writer = AtomicFileWriter(target, backup=False)

        await writer.initialize()
        await writer.rollback()

        # Should not raise error


@pytest.mark.unit
class TestLockedFileResourceInitialization:
    """Test LockedFileResource initialization."""

    def test_initialization_basic(self, tmp_path):
        """Test basic initialization."""
        target = tmp_path / "test.txt"

        resource = LockedFileResource(target)

        assert resource.path == target
        assert resource.mode == "r+"
        assert resource.timeout == 30.0

    def test_initialization_custom_mode(self, tmp_path):
        """Test initialization with custom mode."""
        target = tmp_path / "test.txt"

        resource = LockedFileResource(target, mode="w")

        assert resource.mode == "w"

    def test_initialization_custom_timeout(self, tmp_path):
        """Test initialization with custom timeout."""
        target = tmp_path / "test.txt"

        resource = LockedFileResource(target, timeout=60.0)

        assert resource.timeout == 60.0


@pytest.mark.unit
class TestLockedFileResourceLocking:
    """Test LockedFileResource file locking."""

    @pytest.mark.asyncio
    async def test_initialize_acquires_lock(self, tmp_path):
        """Test initialization acquires file lock."""
        target = tmp_path / "test.txt"
        target.write_text("content")

        resource = LockedFileResource(target)
        await resource.initialize()

        assert resource._file_handle is not None

        await resource.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_releases_lock(self, tmp_path):
        """Test cleanup releases file lock."""
        target = tmp_path / "test.txt"
        target.write_text("content")

        resource = LockedFileResource(target)
        await resource.initialize()
        await resource.cleanup()

        assert resource._file_handle.closed

    @pytest.mark.asyncio
    async def test_file_handle_property(self, tmp_path):
        """Test file_handle property."""
        target = tmp_path / "test.txt"
        target.write_text("content")

        resource = LockedFileResource(target)
        await resource.initialize()

        handle = resource.file_handle

        assert handle is not None
        assert not handle.closed

        await resource.cleanup()

    @pytest.mark.asyncio
    async def test_file_handle_property_not_initialized(self, tmp_path):
        """Test file_handle property raises error when not initialized."""
        target = tmp_path / "test.txt"
        resource = LockedFileResource(target)

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = resource.file_handle


@pytest.mark.unit
class TestLockedFileResourceOperations:
    """Test LockedFileResource read/write operations."""

    @pytest.mark.asyncio
    async def test_read_content(self, tmp_path):
        """Test reading file content."""
        target = tmp_path / "test.txt"
        target.write_text("test content")

        resource = LockedFileResource(target)
        await resource.initialize()

        content = resource.read()

        assert content == "test content"

        await resource.cleanup()

    @pytest.mark.asyncio
    async def test_write_content(self, tmp_path):
        """Test writing file content."""
        target = tmp_path / "test.txt"
        target.write_text("original")

        resource = LockedFileResource(target)
        await resource.initialize()

        resource.write("updated")

        await resource.cleanup()

        assert target.read_text() == "updated"

    @pytest.mark.asyncio
    async def test_write_truncates_file(self, tmp_path):
        """Test write truncates file."""
        target = tmp_path / "test.txt"
        target.write_text("long original content")

        resource = LockedFileResource(target)
        await resource.initialize()

        resource.write("short")

        await resource.cleanup()

        assert target.read_text() == "short"


@pytest.mark.unit
class TestSafeDirectoryCreatorInitialization:
    """Test SafeDirectoryCreator initialization."""

    def test_initialization_basic(self, tmp_path):
        """Test basic initialization."""
        target = tmp_path / "newdir"

        creator = SafeDirectoryCreator(target)

        assert creator.path == target
        assert creator.cleanup_on_error is True
        assert creator._created_dirs == []

    def test_initialization_no_cleanup(self, tmp_path):
        """Test initialization without cleanup."""
        target = tmp_path / "newdir"

        creator = SafeDirectoryCreator(target, cleanup_on_error=False)

        assert creator.cleanup_on_error is False


@pytest.mark.unit
class TestSafeDirectoryCreatorOperations:
    """Test SafeDirectoryCreator directory operations."""

    @pytest.mark.asyncio
    async def test_initialize_creates_directory(self, tmp_path):
        """Test initialization creates directory."""
        target = tmp_path / "new" / "nested" / "dir"

        creator = SafeDirectoryCreator(target, cleanup_on_error=False)
        await creator.initialize()

        assert target.exists()
        assert target.is_dir()

    @pytest.mark.asyncio
    async def test_initialize_tracks_created_dirs(self, tmp_path):
        """Test initialization tracks created directories."""
        target = tmp_path / "new" / "nested" / "dir"

        creator = SafeDirectoryCreator(target, cleanup_on_error=False)
        await creator.initialize()

        assert len(creator._created_dirs) == 3

    @pytest.mark.asyncio
    async def test_cleanup_removes_empty_dirs(self, tmp_path):
        """Test cleanup removes empty directories."""
        target = tmp_path / "new" / "nested" / "dir"

        creator = SafeDirectoryCreator(target, cleanup_on_error=True)
        await creator.initialize()

        await creator.cleanup()

        # Empty directories should be removed
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_cleanup_preserves_non_empty_dirs(self, tmp_path):
        """Test cleanup preserves non-empty directories."""
        target = tmp_path / "new" / "nested" / "dir"

        creator = SafeDirectoryCreator(target, cleanup_on_error=True)
        await creator.initialize()

        # Create a file in the directory
        (target / "file.txt").write_text("content")

        await creator.cleanup()

        # Directory with file should not be removed
        assert target.exists()


@pytest.mark.unit
class TestBatchFileOperationsInitialization:
    """Test BatchFileOperations initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        batch = BatchFileOperations()

        assert batch.manager is not None
        assert batch.operations == []
        assert batch.rollback_operations == []

    def test_initialization_with_manager(self):
        """Test initialization with resource manager."""
        manager = ResourceManager()

        batch = BatchFileOperations(manager=manager)

        assert batch.manager == manager


@pytest.mark.unit
class TestBatchFileOperationsWriteOperation:
    """Test BatchFileOperations write operation."""

    def test_add_write_operation(self, tmp_path):
        """Test adding write operation."""
        target = tmp_path / "test.txt"
        batch = BatchFileOperations()

        batch.add_write_operation(target, "content")

        assert len(batch.operations) == 1
        assert len(batch.rollback_operations) == 1


@pytest.mark.unit
class TestBatchFileOperationsCopyOperation:
    """Test BatchFileOperations copy operation."""

    def test_add_copy_operation(self, tmp_path):
        """Test adding copy operation."""
        source = tmp_path / "source.txt"
        dest = tmp_path / "dest.txt"
        batch = BatchFileOperations()

        batch.add_copy_operation(source, dest)

        assert len(batch.operations) == 1
        assert len(batch.rollback_operations) == 1

    @pytest.mark.asyncio
    async def test_copy_operation_execution(self, tmp_path):
        """Test copy operation execution."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        batch = BatchFileOperations()
        batch.add_copy_operation(source, dest, backup=False)

        await batch.commit_all()

        assert dest.exists()
        assert dest.read_text() == "content"


@pytest.mark.unit
class TestBatchFileOperationsMoveOperation:
    """Test BatchFileOperations move operation."""

    def test_add_move_operation(self, tmp_path):
        """Test adding move operation."""
        source = tmp_path / "source.txt"
        dest = tmp_path / "dest.txt"
        batch = BatchFileOperations()

        batch.add_move_operation(source, dest)

        assert len(batch.operations) == 1
        assert len(batch.rollback_operations) == 1

    @pytest.mark.asyncio
    async def test_move_operation_execution(self, tmp_path):
        """Test move operation execution."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        batch = BatchFileOperations()
        batch.add_move_operation(source, dest)

        await batch.commit_all()

        assert dest.exists()
        assert not source.exists()


@pytest.mark.unit
class TestBatchFileOperationsDeleteOperation:
    """Test BatchFileOperations delete operation."""

    def test_add_delete_operation(self, tmp_path):
        """Test adding delete operation."""
        target = tmp_path / "test.txt"
        batch = BatchFileOperations()

        batch.add_delete_operation(target)

        assert len(batch.operations) == 1
        assert len(batch.rollback_operations) == 1

    @pytest.mark.asyncio
    async def test_delete_operation_execution(self, tmp_path):
        """Test delete operation execution."""
        target = tmp_path / "test.txt"
        target.write_text("content")

        batch = BatchFileOperations()
        batch.add_delete_operation(target, backup=False)

        await batch.commit_all()

        assert not target.exists()


@pytest.mark.unit
class TestBatchFileOperationsCommitRollback:
    """Test BatchFileOperations commit and rollback."""

    @pytest.mark.asyncio
    async def test_commit_all_executes_operations(self, tmp_path):
        """Test commit_all executes all operations."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        batch = BatchFileOperations()
        batch.add_copy_operation(source, dest, backup=False)

        await batch.commit_all()

        assert dest.exists()

    @pytest.mark.asyncio
    async def test_commit_all_rollback_on_failure(self, tmp_path):
        """Test commit_all rolls back on failure."""
        batch = BatchFileOperations()

        # Add operations
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        batch.add_delete_operation(file1, backup=False)

        # Add failing operation
        def failing_op():
            raise RuntimeError("Simulated failure")

        def rollback_op():
            file1.write_text("restored")

        batch.operations.append(failing_op)
        batch.rollback_operations.append(rollback_op)

        with pytest.raises(RuntimeError, match="Batch file operations failed"):
            await batch.commit_all()


@pytest.mark.unit
class TestContextManagers:
    """Test context manager functions."""

    @pytest.mark.asyncio
    async def test_atomic_file_write_context(self, tmp_path):
        """Test atomic_file_write context manager."""
        target = tmp_path / "test.txt"

        async with atomic_file_write(target, backup=False) as writer:
            writer.write("content")

        assert target.read_text() == "content"

    @pytest.mark.asyncio
    async def test_atomic_file_write_rollback_on_exception(self, tmp_path):
        """Test atomic_file_write rolls back on exception."""
        target = tmp_path / "test.txt"
        target.write_text("original")

        try:
            async with atomic_file_write(target, backup=True) as writer:
                writer.write("updated")
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        assert target.read_text() == "original"

    @pytest.mark.asyncio
    async def test_locked_file_access_context(self, tmp_path):
        """Test locked_file_access context manager."""
        target = tmp_path / "test.txt"
        target.write_text("content")

        async with locked_file_access(target) as resource:
            content = resource.read()

        assert content == "content"

    @pytest.mark.asyncio
    async def test_safe_directory_creation_context(self, tmp_path):
        """Test safe_directory_creation context manager."""
        target = tmp_path / "new" / "dir"

        async with safe_directory_creation(target, cleanup_on_error=False):
            pass

        assert target.exists()

    @pytest.mark.asyncio
    async def test_batch_file_operations_context(self, tmp_path):
        """Test batch_file_operations context manager."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        async with batch_file_operations() as batch:
            batch.add_copy_operation(source, dest, backup=False)

        assert dest.exists()


@pytest.mark.unit
class TestSafeFileOperationsRead:
    """Test SafeFileOperations read methods."""

    @pytest.mark.asyncio
    async def test_safe_read_text_success(self, tmp_path):
        """Test safe_read_text with UTF-8."""
        target = tmp_path / "test.txt"
        target.write_text("content", encoding="utf-8")

        content = await SafeFileOperations.safe_read_text(target)

        assert content == "content"

    @pytest.mark.asyncio
    async def test_safe_read_text_fallback_encoding(self, tmp_path):
        """Test safe_read_text with fallback encoding."""
        target = tmp_path / "test.txt"
        target.write_bytes(b"content\xff")

        content = await SafeFileOperations.safe_read_text(target)

        assert "content" in content

    @pytest.mark.asyncio
    async def test_safe_read_text_file_not_found(self, tmp_path):
        """Test safe_read_text with non-existent file."""
        target = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            await SafeFileOperations.safe_read_text(target)


@pytest.mark.unit
class TestSafeFileOperationsWrite:
    """Test SafeFileOperations write methods."""

    @pytest.mark.asyncio
    async def test_safe_write_text_atomic(self, tmp_path):
        """Test safe_write_text with atomic write."""
        target = tmp_path / "test.txt"

        await SafeFileOperations.safe_write_text(
            target, "content", atomic=True, backup=False
        )

        assert target.read_text() == "content"

    @pytest.mark.asyncio
    async def test_safe_write_text_non_atomic(self, tmp_path):
        """Test safe_write_text without atomic write."""
        target = tmp_path / "subdir" / "test.txt"

        await SafeFileOperations.safe_write_text(target, "content", atomic=False)

        assert target.read_text() == "content"


@pytest.mark.unit
class TestSafeFileOperationsCopy:
    """Test SafeFileOperations copy methods."""

    @pytest.mark.asyncio
    async def test_safe_copy_file_success(self, tmp_path):
        """Test safe_copy_file success."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        await SafeFileOperations.safe_copy_file(
            source, dest, preserve_metadata=True, backup=False
        )

        assert dest.read_text() == "content"

    @pytest.mark.asyncio
    async def test_safe_copy_file_source_not_found(self, tmp_path):
        """Test safe_copy_file with non-existent source."""
        source = tmp_path / "nonexistent.txt"
        dest = tmp_path / "dest.txt"

        with pytest.raises(FileNotFoundError, match="Source file not found"):
            await SafeFileOperations.safe_copy_file(source, dest)

    @pytest.mark.asyncio
    async def test_safe_copy_file_with_backup(self, tmp_path):
        """Test safe_copy_file creates backup."""
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original")

        await SafeFileOperations.safe_copy_file(source, dest, backup=True)

        backup = dest.with_suffix(f"{dest.suffix}.bak")
        assert backup.exists()


@pytest.mark.unit
class TestSafeFileOperationsMove:
    """Test SafeFileOperations move methods."""

    @pytest.mark.asyncio
    async def test_safe_move_file_success(self, tmp_path):
        """Test safe_move_file success."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        await SafeFileOperations.safe_move_file(source, dest, backup=False)

        assert dest.read_text() == "content"
        assert not source.exists()

    @pytest.mark.asyncio
    async def test_safe_move_file_source_not_found(self, tmp_path):
        """Test safe_move_file with non-existent source."""
        source = tmp_path / "nonexistent.txt"
        dest = tmp_path / "dest.txt"

        with pytest.raises(FileNotFoundError, match="Source file not found"):
            await SafeFileOperations.safe_move_file(source, dest)

    @pytest.mark.asyncio
    async def test_safe_move_file_with_backup(self, tmp_path):
        """Test safe_move_file creates and removes backup."""
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original")

        await SafeFileOperations.safe_move_file(source, dest, backup=True)

        assert dest.read_text() == "new content"
        # Backup should be removed after successful move
        backup_pattern = f"{dest.stem}{dest.suffix}.bak.*"
        backups = list(dest.parent.glob(backup_pattern))
        assert len(backups) == 0
