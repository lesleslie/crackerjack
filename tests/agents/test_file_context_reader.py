"""Tests for FileContextReader."""

import asyncio
import pytest
from pathlib import Path

from crackerjack.agents.file_context_reader import FileContextReader


@pytest.mark.asyncio
async def test_cache_hit():
    """Test that cache returns cached content."""
    reader = FileContextReader()

    # Read file (should cache it)
    content1 = await reader.read_file(__file__)

    # Read again (should hit cache)
    content2 = await reader.read_file(__file__)

    assert content1 == content2, "Cache should return same content on second read"


@pytest.mark.asyncio
async def test_cache_miss():
    """Test that cache miss reads from disk."""
    reader = FileContextReader()

    # First read caches the file
    content1 = await reader.read_file(__file__)

    # Clear cache
    reader.clear_cache()

    # Read again (should read from disk)
    content2 = await reader.read_file(__file__)

    assert content1 == content2, "Content should be same after cache clear"
    # Verify we're reading this test file (which starts with its own docstring)
    assert content2.startswith('"""Tests for FileContextReader'), "Full content should be returned"


@pytest.mark.asyncio
async def test_concurrent_reads():
    """Test thread-safe concurrent reads."""
    reader = FileContextReader()

    # Create tasks for concurrent reads
    tasks = [
        asyncio.create_task(reader.read_file(__file__)),
        asyncio.create_task(reader.read_file(__file__)),
        asyncio.create_task(reader.read_file(__file__)),
    ]

    # Execute concurrently
    results = await asyncio.gather(*tasks)

    # All should return same content
    assert len(set(results)) == 1, "All concurrent reads should return same content"


@pytest.mark.asyncio
async def test_clear_cache():
    """Test cache clearing."""
    reader = FileContextReader()

    # Read file to populate cache
    await reader.read_file(__file__)

    # Clear cache
    reader.clear_cache()

    # Verify cache is empty
    cached = await reader.get_cached_files()
    assert len(cached) == 0, "Cache should be empty after clear"


@pytest.mark.asyncio
async def test_file_path_handling():
    """Test various file path input types."""
    reader = FileContextReader()

    # String path - read an existing file (this test file)
    result = await reader.read_file(__file__)

    assert isinstance(result, str)
    # Verify the docstring content from this test file
    assert '"""Tests for FileContextReader.' in result

    # Path object
    result2 = await reader.read_file(Path(__file__))

    assert isinstance(result2, str)
    assert result == result2


@pytest.mark.asyncio
async def test_file_not_found():
    """Test that FileNotFoundError is raised for non-existent files."""
    reader = FileContextReader()

    # Try to read non-existent file
    with pytest.raises(FileNotFoundError):
        await reader.read_file("path/to/nonexistent/file.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
