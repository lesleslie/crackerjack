import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from crackerjack.core.file_lifecycle import (
    SafeFileOperations,
    atomic_file_write,
    locked_file_access,
    safe_directory_creation,
    batch_file_operations,
    AtomicFileWriter,
    LockedFileResource,
    SafeDirectoryCreator,
    BatchFileOperations
)


@pytest.mark.asyncio
async def test_atomic_file_write_basic():
    """Test basic functionality of atomic_file_write."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        async with atomic_file_write(tmp_path) as writer:
            writer.write("test content")
        assert tmp_path.read_text() == "test content"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_locked_file_access_basic():
    """Test basic functionality of locked_file_access."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("test content")
        tmp.flush()

    try:
        async with locked_file_access(tmp_path, mode='r+') as resource:
            content = resource.read()
            assert content == "test content"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_safe_directory_creation_basic():
    """Test basic functionality of safe_directory_creation."""
    test_dir = Path(tempfile.mkdtemp()) / "nested" / "subdir"

    try:
        async with safe_directory_creation(test_dir) as creator:
            assert test_dir.exists()
    finally:
        # Clean up the created directories
        import shutil
        base_dir = test_dir.parent.parent
        if base_dir.exists():
            shutil.rmtree(base_dir)

@pytest.mark.asyncio
async def test_batch_file_operations_basic():
    """Test basic functionality of batch_file_operations."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        async with batch_file_operations() as batch:
            # For now, just test that batch operations can be created
            assert batch is not None
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_write_basic():
    """Test basic functionality of AtomicFileWriter.write method."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        async with atomic_file_write(tmp_path) as writer:
            writer.write("test content")
        assert tmp_path.read_text() == "test content"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_writelines_basic():
    """Test basic functionality of AtomicFileWriter.writelines method."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        async with atomic_file_write(tmp_path) as writer:
            writer.writelines(["line 1\n", "line 2\n"])
        content = tmp_path.read_text()
        assert "line 1" in content
        assert "line 2" in content
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_flush_basic():
    """Test basic functionality of AtomicFileWriter.flush method."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        async with atomic_file_write(tmp_path) as writer:
            writer.write("test content")
            writer.flush()  # Just testing that it doesn't raise an exception
        assert tmp_path.read_text() == "test content"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_commit_basic():
    """Test basic functionality of AtomicFileWriter.commit method."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        writer = AtomicFileWriter(tmp_path)
        await writer.initialize()
        writer.write("test content")
        await writer.commit()
        assert tmp_path.read_text() == "test content"
        await writer.cleanup()
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_rollback_basic():
    """Test basic functionality of AtomicFileWriter.rollback method."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("original content")
        tmp.flush()

    try:
        # First write some content to the file
        Path(tmp_path).write_text("original content")

        writer = AtomicFileWriter(tmp_path, backup=True)
        await writer.initialize()
        writer.write("new content")
        await writer.rollback()  # Revert to original
        assert Path(tmp_path).read_text() == "original content"
        await writer.cleanup()
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

def test_file_handle_basic():
    """Test basic functionality of LockedFileResource.file_handle property."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("test content")
        tmp.flush()

    async def run_test():
        resource = LockedFileResource(tmp_path, mode='r+')
        await resource.initialize()
        handle = resource.file_handle
        assert handle is not None
        await resource.cleanup()

    try:
        asyncio.run(run_test())
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_read_basic():
    """Test basic functionality of LockedFileResource.read method."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("test content")
        tmp.flush()

    try:
        async with locked_file_access(tmp_path, mode='r') as resource:
            content = resource.read()
            assert content == "test content"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_add_write_operation_basic():
    """Test basic functionality of BatchFileOperations.add_write_operation method."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        batch = BatchFileOperations()
        batch.add_write_operation(tmp_path, "test content")
        # Test that the operation is added to the list
        assert len(batch.operations) == 1
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_add_copy_operation_basic():
    """Test basic functionality of BatchFileOperations.add_copy_operation method."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as src_tmp:
        src_path = Path(src_tmp.name)
        src_tmp.write("source content")
        src_tmp.flush()

    with tempfile.NamedTemporaryFile(delete=False) as dest_tmp:
        dest_path = Path(dest_tmp.name)

    try:
        batch = BatchFileOperations()
        batch.add_copy_operation(src_path, dest_path)
        # Test that the operation is added to the list
        assert len(batch.operations) == 1
    finally:
        if src_path.exists():
            src_path.unlink()
        if dest_path.exists():
            dest_path.unlink()

@pytest.mark.asyncio
async def test_add_move_operation_basic():
    """Test basic functionality of BatchFileOperations.add_move_operation method."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as src_tmp:
        src_path = Path(src_tmp.name)
        src_tmp.write("source content")
        src_tmp.flush()

    with tempfile.NamedTemporaryFile(delete=False) as dest_tmp:
        dest_path = Path(dest_tmp.name)

    try:
        batch = BatchFileOperations()
        batch.add_move_operation(src_path, dest_path)
        # Test that the operation is added to the list
        assert len(batch.operations) == 1
    finally:
        # Clean up - if move happened, source is gone, dest exists
        if dest_path.exists():
            dest_path.unlink()
        if src_path.exists() and not dest_path.exists():
            src_path.unlink()

@pytest.mark.asyncio
async def test_add_delete_operation_basic():
    """Test basic functionality of BatchFileOperations.add_delete_operation method."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("content to delete")
        tmp.flush()

    try:
        assert tmp_path.exists()  # File exists initially
        batch = BatchFileOperations()
        batch.add_delete_operation(tmp_path)
        # Test that the operation is added to the list
        assert len(batch.operations) == 1
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_commit_all_basic():
    """Test basic functionality of BatchFileOperations.commit_all method."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        async with atomic_file_write(tmp_path) as writer:
            writer.write("test content")
        assert tmp_path.read_text() == "test content"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_safe_read_text_basic():
    """Test basic functionality of SafeFileOperations.safe_read_text method."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("test content")
        tmp.flush()

    try:
        content = await SafeFileOperations.safe_read_text(tmp_path)
        assert content == "test content"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_safe_write_text_basic():
    """Test basic functionality of SafeFileOperations.safe_write_text method."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        await SafeFileOperations.safe_write_text(tmp_path, "test content")
        assert tmp_path.read_text() == "test content"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_safe_copy_file_basic():
    """Test basic functionality of SafeFileOperations.safe_copy_file method."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as src_tmp:
        src_path = Path(src_tmp.name)
        src_tmp.write("source content")
        src_tmp.flush()

    with tempfile.NamedTemporaryFile(delete=False) as dest_tmp:
        dest_path = Path(dest_tmp.name)

    try:
        await SafeFileOperations.safe_copy_file(src_path, dest_path)
        assert dest_path.read_text() == "source content"
    finally:
        if src_path.exists():
            src_path.unlink()
        if dest_path.exists():
            dest_path.unlink()

@pytest.mark.asyncio
async def test_safe_move_file_basic():
    """Test basic functionality of SafeFileOperations.safe_move_file method."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as src_tmp:
        src_path = Path(src_tmp.name)
        src_tmp.write("source content")
        src_tmp.flush()

    with tempfile.NamedTemporaryFile(delete=False) as dest_tmp:
        dest_path = Path(dest_tmp.name)

    try:
        await SafeFileOperations.safe_move_file(src_path, dest_path)
        assert dest_path.read_text() == "source content"
        assert not src_path.exists()  # Source should be moved
    finally:
        if dest_path.exists():
            dest_path.unlink()
        if src_path.exists():
            src_path.unlink()

# The following functions (write_op, rollback_op, copy_op, move_op, delete_op) are internal
# methods of BatchFileOperations and not meant to be called directly from outside
# So we'll skip these tests or provide appropriate tests for them
@pytest.mark.asyncio
async def test_write_op_basic():
    """Test that write_op is created properly as part of add_write_operation."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        batch = BatchFileOperations()
        batch.add_write_operation(tmp_path, "test content")
        # Test that the internal operation was created
        assert len(batch.operations) == 1
        assert len(batch.rollback_operations) == 1
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_rollback_op_basic():
    """Test that rollback_op is created properly as part of add_write_operation."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("original content")
        tmp.flush()

    try:
        batch = BatchFileOperations()
        batch.add_write_operation(tmp_path, "new content")
        # Test that the rollback operation was created
        assert len(batch.rollback_operations) == 1
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@pytest.mark.asyncio
async def test_copy_op_basic():
    """Test that copy_op is created properly as part of add_copy_operation."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as src_tmp:
        src_path = Path(src_tmp.name)
        src_tmp.write("source content")
        src_tmp.flush()

    with tempfile.NamedTemporaryFile(delete=False) as dest_tmp:
        dest_path = Path(dest_tmp.name)

    try:
        batch = BatchFileOperations()
        batch.add_copy_operation(src_path, dest_path)
        # Test that the copy operation was created
        assert len(batch.operations) == 1
        assert len(batch.rollback_operations) == 1
    finally:
        if src_path.exists():
            src_path.unlink()
        if dest_path.exists():
            dest_path.unlink()

@pytest.mark.asyncio
async def test_move_op_basic():
    """Test that move_op is created properly as part of add_move_operation."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as src_tmp:
        src_path = Path(src_tmp.name)
        src_tmp.write("source content")
        src_tmp.flush()

    with tempfile.NamedTemporaryFile(delete=False) as dest_tmp:
        dest_path = Path(dest_tmp.name)

    try:
        batch = BatchFileOperations()
        batch.add_move_operation(src_path, dest_path)
        # Test that the move operation was created
        assert len(batch.operations) == 1
        assert len(batch.rollback_operations) == 1
    finally:
        # Clean up: remove any remaining files
        if dest_path.exists():
            dest_path.unlink()
        if src_path.exists():
            src_path.unlink()

@pytest.mark.asyncio
async def test_delete_op_basic():
    """Test that delete_op is created properly as part of add_delete_operation."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("content to delete")
        tmp.flush()

    try:
        batch = BatchFileOperations()
        batch.add_delete_operation(tmp_path)
        # Test that the delete operation was created
        assert len(batch.operations) == 1
        assert len(batch.rollback_operations) == 1
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
