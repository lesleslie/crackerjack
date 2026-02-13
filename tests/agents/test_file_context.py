"""
Tests for FileContextReader.

Test thread-safe caching and file reading functionality.
"""
import asyncio
import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.file_context import FileContextReader


class TestFileContextReader:
    """Test suite for FileContextReader."""

    @pytest.mark.asyncio
    async def test_read_file_basic(self) -> None:
        """Test basic file reading."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("test content")
            f.flush()

            reader = FileContextReader()
            content = await reader.read_file(f.name)

            assert content == "test content"

    @pytest.mark.asyncio
    async def test_caching_works(self) -> None:
        """Test that caching returns same content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            original_content = "cached content"
            f.write(original_content)
            f.flush()

            reader = FileContextReader()

            # First read - should cache
            content1 = await reader.read_file(f.name)
            # Second read - should return cached
            content2 = await reader.read_file(f.name)

            assert content1 == original_content
            assert content2 == original_content

    @pytest.mark.asyncio
    async def test_clear_cache(self) -> None:
        """Test cache clearing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("test content")
            f.flush()

            reader = FileContextReader()

            # Read to populate cache
            await reader.read_file(f.name)

            # Clear cache
            reader.clear_cache()

            # Verify cache is cleared by reading again
            content = await reader.read_file(f.name)
            assert content == "test content"

    @pytest.mark.asyncio
    async def test_clear_cache_for_file(self) -> None:
        """Test clearing cache for specific file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("test content")
            f.flush()

            reader = FileContextReader()

            # Read to populate cache
            await reader.read_file(f.name)

            # Clear cache for this file
            reader.clear_cache_for_file(f.name)

            # Verify cache is cleared by reading again
            content = await reader.read_file(f.name)
            assert content == "test content"

    @pytest.mark.asyncio
    async def test_nonexistent_file_raises_error(self) -> None:
        """Test that reading nonexistent file raises error."""
        reader = FileContextReader()

        with pytest.raises(FileNotFoundError):
            await reader.read_file("/nonexistent/file.py")

    @pytest.mark.asyncio
    async def test_concurrent_reads(self) -> None:
        """Test thread-safe concurrent reads."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("concurrent test")
            f.flush()

            reader = FileContextReader()

            # Read same file multiple times concurrently
            tasks = [reader.read_file(f.name) for _ in range(10)]
            results = await asyncio.gather(*tasks)

            # All should return same content
            assert all(r == "concurrent test" for r in results)
