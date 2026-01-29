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
    
    creator = SafeDirectoryCreator(dir_path)
    await creator.initialize()
    await creator.cleanup()
    
    assert dir_path.exists()


@pytest.mark.asyncio
async def test_safe_directory_creator_nested(temp_dir):
    """Test SafeDirectoryCreator with nested directories."""
    dir_path = temp_dir / "nested" / "subdir"
    
    creator = SafeDirectoryCreator(dir_path)
    await creator.initialize()
    await creator.cleanup()
    
    assert dir_path.exists()