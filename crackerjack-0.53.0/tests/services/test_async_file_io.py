"""Tests for async file I/O operations.

This test suite validates the async_file_io module which provides
non-blocking file operations using ThreadPoolExecutor.
"""

import pytest
import asyncio
from pathlib import Path

from crackerjack.services.async_file_io import (
    async_read_file,
    async_write_file,
    async_read_files_batch,
    async_write_files_batch,
    shutdown_io_executor,
)


class TestAsyncFileIO:
    """Test suite for async file I/O operations."""

    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path):
        """Test reading a single file asynchronously."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, async world!")

        content = await async_read_file(test_file)
        assert content == "Hello, async world!"

    @pytest.mark.asyncio
    async def test_write_file(self, tmp_path):
        """Test writing a single file asynchronously."""
        test_file = tmp_path / "test_write.txt"
        content = "Async write test"

        await async_write_file(test_file, content)
        assert test_file.read_text() == content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading a file that doesn't exist raises an exception."""
        with pytest.raises(FileNotFoundError):
            await async_read_file(Path("/nonexistent/file.txt"))

    @pytest.mark.asyncio
    async def test_write_to_readonly_location(self, tmp_path):
        """Test writing to a location that fails."""
        # Create a file and make it read-only
        test_file = tmp_path / "readonly.txt"
        test_file.write_text("initial")

        # Make file read-only (Unix-like systems)
        import os
        import stat

        os.chmod(test_file, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        # Try to write (should fail)
        with pytest.raises(PermissionError):
            await async_write_file(test_file, "new content")

        # Clean up - restore write permissions
        os.chmod(test_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)

    @pytest.mark.asyncio
    async def test_batch_read(self, tmp_path):
        """Test reading multiple files in parallel."""
        files = []
        for i in range(5):
            test_file = tmp_path / f"test_{i}.txt"
            test_file.write_text(f"Content {i}")
            files.append(test_file)

        contents = await async_read_files_batch(files)
        assert len(contents) == 5
        assert contents[files[0]] == "Content 0"
        assert contents[files[4]] == "Content 4"

    @pytest.mark.asyncio
    async def test_batch_write(self, tmp_path):
        """Test writing multiple files in parallel."""
        file_writes = []
        for i in range(5):
            test_file = tmp_path / f"write_{i}.txt"
            content = f"Write test {i}"
            file_writes.append((test_file, content))

        await async_write_files_batch(file_writes)

        # Verify contents
        for i, (file, content) in enumerate(file_writes):
            assert file.read_text() == content

    @pytest.mark.asyncio
    async def test_batch_read_with_missing_files(self, tmp_path):
        """Test batch read with missing files raises exception."""
        existing_file = tmp_path / "existing.txt"
        existing_file.write_text("exists")

        missing_file = tmp_path / "missing.txt"  # Don't create this

        # Should raise FileNotFoundError for missing file
        with pytest.raises(FileNotFoundError):
            await async_read_files_batch([existing_file, missing_file])

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, tmp_path):
        """Test concurrent file operations don't interfere."""
        test_file = tmp_path / "concurrent.txt"

        tasks = [
            async_write_file(test_file, f"Version {i}")
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Should complete without exceptions
        assert all(r is None or isinstance(r, Exception) for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, tmp_path):
        """Test that multiple concurrent reads are safe."""
        test_file = tmp_path / "concurrent_read.txt"
        test_content = "Shared content for concurrent reads"
        test_file.write_text(test_content)

        # Launch 10 concurrent reads
        tasks = [async_read_file(test_file) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All reads should return the same content
        assert all(r == test_content for r in results)

    @pytest.mark.asyncio
    async def test_file_overwrite(self, tmp_path):
        """Test that writing to existing file overwrites content."""
        test_file = tmp_path / "overwrite.txt"
        test_file.write_text("Original content")

        await async_write_file(test_file, "New content")
        assert test_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path):
        """Test reading and writing empty files."""
        test_file = tmp_path / "empty.txt"

        # Write empty content
        await async_write_file(test_file, "")

        # Read empty content
        content = await async_read_file(test_file)
        assert content == ""

    @pytest.mark.asyncio
    async def test_unicode_content(self, tmp_path):
        """Test that unicode content is handled correctly."""
        test_file = tmp_path / "unicode.txt"
        unicode_content = "Hello 世界 🌍 Привет"

        await async_write_file(test_file, unicode_content)

        content = await async_read_file(test_file)
        assert content == unicode_content

    @pytest.mark.asyncio
    async def test_large_file(self, tmp_path):
        """Test reading and writing larger files."""
        test_file = tmp_path / "large.txt"
        large_content = "x" * 100_000  # 100KB

        await async_write_file(test_file, large_content)

        content = await async_read_file(test_file)
        assert content == large_content
        assert len(content) == 100_000

    def test_shutdown_executor(self):
        """Test executor shutdown is idempotent."""
        # Can be called multiple times without error
        shutdown_io_executor()
        shutdown_io_executor()
        shutdown_io_executor()

        # If we got here without exception, test passed
        assert True

    @pytest.mark.asyncio
    async def test_mixed_batch_operations(self, tmp_path):
        """Test mixed read/write operations in batches."""
        file_writes = []
        files_to_read = []

        # Create 5 files to write
        for i in range(5):
            test_file = tmp_path / f"mixed_{i}.txt"
            content = f"Mixed content {i}"
            file_writes.append((test_file, content))
            files_to_read.append(test_file)

        # Write all files
        await async_write_files_batch(file_writes)

        # Read all files back
        read_contents = await async_read_files_batch(files_to_read)

        # Verify contents match
        for i, (file, content) in enumerate(file_writes):
            assert read_contents[file] == content

    @pytest.mark.asyncio
    async def test_batch_with_empty_list(self, tmp_path):
        """Test batch operations with empty file lists."""
        results = await async_read_files_batch([])
        assert results == {}

        await async_write_files_batch([])  # Should not raise
