import asyncio
import tempfile
from pathlib import Path

import pytest

from crackerjack.core.file_lifecycle import SafeDirectoryCreator


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.mark.asyncio
async def test_safe_directory_creator_basic(temp_dir):
    """Test basic functionality of SafeDirectoryCreator."""
    dir_path = temp_dir / "new_dir"

    # Create with cleanup_on_error=False to keep directory after cleanup
    creator = SafeDirectoryCreator(dir_path, cleanup_on_error=False)
    await creator.initialize()
    assert dir_path.exists()

    # Add a file so directory won't be removed as empty
    (dir_path / "test.txt").write_text("test content")

    await creator.cleanup()
    # Directory should still exist because:
    # 1. cleanup_on_error=False (only cleanup on error)
    # 2. Directory is not empty (has test.txt)
    assert dir_path.exists()


@pytest.mark.asyncio
async def test_safe_directory_creator_nested(temp_dir):
    """Test SafeDirectoryCreator with nested directories."""
    dir_path = temp_dir / "nested" / "subdir"

    # Create with cleanup_on_error=False to keep directory after cleanup
    creator = SafeDirectoryCreator(dir_path, cleanup_on_error=False)
    await creator.initialize()
    assert dir_path.exists()

    # Add a file so directory won't be removed as empty
    (dir_path / "test.txt").write_text("nested test")

    await creator.cleanup()
    # Directory should still exist because:
    # 1. cleanup_on_error=False (only cleanup on error)
    # 2. Directory is not empty (has test.txt)
    assert dir_path.exists()
