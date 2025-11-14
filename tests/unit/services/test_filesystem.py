"""Unit tests for FileSystemService.

Tests file system operations including reading, writing, copying,
glob patterns, and streaming operations with comprehensive error handling.
"""

from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from crackerjack.errors import ErrorCode, FileError, ResourceError
from crackerjack.services.filesystem import FileSystemService


@pytest.mark.unit
class TestFileSystemServiceReadOperations:
    """Test file reading operations."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_read_file_success(self, service, tmp_path):
        """Test successful file reading."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content)

        result = service.read_file(test_file)

        assert result == content

    def test_read_file_with_string_path(self, service, tmp_path):
        """Test reading file with string path."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content)

        result = service.read_file(str(test_file))

        assert result == content

    def test_read_file_nonexistent(self, service, tmp_path):
        """Test reading non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(FileError) as exc_info:
            service.read_file(nonexistent)

        assert "does not exist" in str(exc_info.value)

    def test_read_file_permission_error(self, service, tmp_path):
        """Test reading file without permissions raises FileError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        test_file.chmod(0o000)

        try:
            with pytest.raises(FileError) as exc_info:
                service.read_file(test_file)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR
            assert "Permission denied" in str(exc_info.value)
        finally:
            test_file.chmod(0o644)

    def test_read_file_unicode_decode_error(self, service, tmp_path):
        """Test reading binary file as text raises FileError."""
        test_file = tmp_path / "binary.dat"
        # Write invalid UTF-8 bytes
        test_file.write_bytes(b"\xff\xfe\xfd")

        with pytest.raises(FileError) as exc_info:
            service.read_file(test_file)

        assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR
        assert "UTF-8" in str(exc_info.value)


@pytest.mark.unit
class TestFileSystemServiceWriteOperations:
    """Test file writing operations."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_write_file_success(self, service, tmp_path):
        """Test successful file writing."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"

        service.write_file(test_file, content)

        assert test_file.read_text() == content

    def test_write_file_creates_parent_dirs(self, service, tmp_path):
        """Test writing file creates parent directories."""
        test_file = tmp_path / "subdir" / "nested" / "test.txt"
        content = "Hello, World!"

        service.write_file(test_file, content)

        assert test_file.exists()
        assert test_file.read_text() == content

    def test_write_file_cleans_trailing_whitespace_precommit(self, service, tmp_path):
        """Test writing .pre-commit-config.yaml cleans trailing whitespace."""
        test_file = tmp_path / ".pre-commit-config.yaml"
        content = "line1  \nline2\t\nline3"  # Has trailing spaces/tabs

        service.write_file(test_file, content)

        result = test_file.read_text()
        assert result == "line1\nline2\nline3\n"
        assert not any(line.endswith((" ", "\t")) for line in result.splitlines())

    def test_write_file_cleans_trailing_whitespace_pyproject(self, service, tmp_path):
        """Test writing pyproject.toml cleans trailing whitespace."""
        test_file = tmp_path / "pyproject.toml"
        content = "line1  \nline2\t"

        service.write_file(test_file, content)

        result = test_file.read_text()
        assert "line1\n" in result
        assert not result.rstrip("\n").endswith(" ")

    def test_write_file_adds_final_newline(self, service, tmp_path):
        """Test writing file adds final newline."""
        test_file = tmp_path / ".pre-commit-config.yaml"
        content = "line1\nline2"  # No final newline

        service.write_file(test_file, content)

        result = test_file.read_text()
        assert result.endswith("\n")

    def test_write_file_with_string_path(self, service, tmp_path):
        """Test writing file with string path."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"

        service.write_file(str(test_file), content)

        assert test_file.read_text() == content

    def test_write_file_permission_error(self, service, tmp_path):
        """Test writing to read-only directory raises FileError."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)
        test_file = readonly_dir / "test.txt"

        try:
            with pytest.raises(FileError) as exc_info:
                service.write_file(test_file, "content")

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR
        finally:
            readonly_dir.chmod(0o755)


@pytest.mark.unit
class TestFileSystemServiceExistsAndMkdir:
    """Test exists and mkdir operations."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_exists_file_true(self, service, tmp_path):
        """Test exists returns True for existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        assert service.exists(test_file) is True

    def test_exists_directory_true(self, service, tmp_path):
        """Test exists returns True for existing directory."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        assert service.exists(test_dir) is True

    def test_exists_nonexistent_false(self, service, tmp_path):
        """Test exists returns False for non-existent path."""
        nonexistent = tmp_path / "nonexistent.txt"

        assert service.exists(nonexistent) is False

    def test_exists_with_string_path(self, service, tmp_path):
        """Test exists works with string path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        assert service.exists(str(test_file)) is True

    def test_mkdir_creates_directory(self, service, tmp_path):
        """Test mkdir creates directory."""
        new_dir = tmp_path / "newdir"

        service.mkdir(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_mkdir_with_parents(self, service, tmp_path):
        """Test mkdir creates parent directories."""
        nested_dir = tmp_path / "parent" / "child" / "grandchild"

        service.mkdir(nested_dir, parents=True)

        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_mkdir_already_exists(self, service, tmp_path):
        """Test mkdir with exist_ok=True doesn't raise for existing dir."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        # Should not raise - exist_ok=True is always set
        service.mkdir(test_dir)

        assert test_dir.exists()


@pytest.mark.unit
class TestFileSystemServiceGlobOperations:
    """Test glob and rglob pattern matching."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    @pytest.fixture
    def test_structure(self, tmp_path):
        """Create test directory structure."""
        (tmp_path / "file1.py").write_text("# python file")
        (tmp_path / "file2.txt").write_text("text file")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.py").write_text("# nested python")
        (tmp_path / "subdir" / "file4.md").write_text("# markdown")
        return tmp_path

    def test_glob_pattern_matching(self, service, test_structure):
        """Test glob finds files matching pattern."""
        results = service.glob("*.py", test_structure)

        assert len(results) == 1
        assert results[0].name == "file1.py"

    def test_glob_all_files(self, service, test_structure):
        """Test glob with wildcard finds all files."""
        results = service.glob("*", test_structure)

        # Should find files and subdirectory in root
        assert len(results) >= 3
        names = {p.name for p in results}
        assert "file1.py" in names
        assert "file2.txt" in names
        assert "subdir" in names

    def test_glob_no_matches(self, service, test_structure):
        """Test glob returns empty list when no matches."""
        results = service.glob("*.nonexistent", test_structure)

        assert results == []

    def test_glob_nonexistent_base_path(self, service, tmp_path):
        """Test glob raises FileError for non-existent base path."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(FileError) as exc_info:
            service.glob("*", nonexistent)

        assert "does not exist" in str(exc_info.value)

    def test_rglob_recursive_matching(self, service, test_structure):
        """Test rglob finds files recursively."""
        results = service.rglob("*.py", test_structure)

        assert len(results) == 2
        names = {p.name for p in results}
        assert "file1.py" in names
        assert "file3.py" in names

    def test_rglob_all_files_recursive(self, service, test_structure):
        """Test rglob with wildcard finds all files recursively."""
        results = service.rglob("*", test_structure)

        # Should find all files and directories recursively
        assert len(results) >= 4
        names = {p.name for p in results}
        assert "file1.py" in names
        assert "file3.py" in names
        assert "file4.md" in names


@pytest.mark.unit
class TestFileSystemServiceCopyOperations:
    """Test file copying operations."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_copy_file_success(self, service, tmp_path):
        """Test successful file copy."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        content = "Hello, World!"
        src.write_text(content)

        service.copy_file(src, dst)

        assert dst.exists()
        assert dst.read_text() == content

    def test_copy_file_creates_parent_dirs(self, service, tmp_path):
        """Test copy creates destination parent directories."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "nested" / "subdir" / "dest.txt"
        src.write_text("content")

        service.copy_file(src, dst)

        assert dst.exists()
        assert dst.read_text() == "content"

    def test_copy_file_preserves_metadata(self, service, tmp_path):
        """Test copy preserves file metadata (using copy2)."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("content")
        original_mtime = src.stat().st_mtime

        service.copy_file(src, dst)

        # copy2 should preserve mtime
        assert abs(dst.stat().st_mtime - original_mtime) < 1

    def test_copy_file_with_string_paths(self, service, tmp_path):
        """Test copy works with string paths."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("content")

        service.copy_file(str(src), str(dst))

        assert dst.exists()

    def test_copy_file_nonexistent_source(self, service, tmp_path):
        """Test copying non-existent source raises FileError."""
        src = tmp_path / "nonexistent.txt"
        dst = tmp_path / "dest.txt"

        with pytest.raises(FileError) as exc_info:
            service.copy_file(src, dst)

        assert "does not exist" in str(exc_info.value)

    def test_copy_file_source_is_directory(self, service, tmp_path):
        """Test copying directory as file raises FileError."""
        src = tmp_path / "srcdir"
        src.mkdir()
        dst = tmp_path / "dest.txt"

        with pytest.raises(FileError) as exc_info:
            service.copy_file(src, dst)

        assert "not a file" in str(exc_info.value)


@pytest.mark.unit
class TestFileSystemServiceRemoveOperations:
    """Test file removal operations."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_remove_file_success(self, service, tmp_path):
        """Test successful file removal."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        service.remove_file(test_file)

        assert not test_file.exists()

    def test_remove_file_nonexistent(self, service, tmp_path):
        """Test removing non-existent file doesn't raise error."""
        nonexistent = tmp_path / "nonexistent.txt"

        # Should not raise
        service.remove_file(nonexistent)

    def test_remove_file_is_directory(self, service, tmp_path):
        """Test removing directory as file raises FileError."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        with pytest.raises(FileError) as exc_info:
            service.remove_file(test_dir)

        assert "not a file" in str(exc_info.value)

    def test_remove_file_with_string_path(self, service, tmp_path):
        """Test remove works with string path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        service.remove_file(str(test_file))

        assert not test_file.exists()


@pytest.mark.unit
class TestFileSystemServiceFileInfo:
    """Test file information operations."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_get_file_size(self, service, tmp_path):
        """Test getting file size."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content)

        size = service.get_file_size(test_file)

        assert size == len(content.encode("utf-8"))

    def test_get_file_size_empty_file(self, service, tmp_path):
        """Test getting size of empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        size = service.get_file_size(test_file)

        assert size == 0

    def test_get_file_size_nonexistent(self, service, tmp_path):
        """Test getting size of non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(FileError) as exc_info:
            service.get_file_size(nonexistent)

        assert "does not exist" in str(exc_info.value)

    def test_get_file_size_directory(self, service, tmp_path):
        """Test getting size of directory raises FileError."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        with pytest.raises(FileError) as exc_info:
            service.get_file_size(test_dir)

        assert "not a file" in str(exc_info.value)

    def test_get_file_mtime(self, service, tmp_path):
        """Test getting file modification time."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mtime = service.get_file_mtime(test_file)

        assert isinstance(mtime, float)
        assert mtime > 0

    def test_get_file_mtime_nonexistent(self, service, tmp_path):
        """Test getting mtime of non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(FileError) as exc_info:
            service.get_file_mtime(nonexistent)

        assert "does not exist" in str(exc_info.value)

    def test_get_file_mtime_directory(self, service, tmp_path):
        """Test getting mtime of directory raises FileError."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        with pytest.raises(FileError) as exc_info:
            service.get_file_mtime(test_dir)

        assert "not a file" in str(exc_info.value)


@pytest.mark.unit
class TestFileSystemServiceStreamingOperations:
    """Test streaming read operations."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_read_file_chunked(self, service, tmp_path):
        """Test reading file in chunks."""
        test_file = tmp_path / "test.txt"
        content = "A" * 1000  # 1000 characters
        test_file.write_text(content)

        chunks = list(service.read_file_chunked(test_file, chunk_size=100))

        # Should have multiple chunks
        assert len(chunks) > 1
        # Reassembled content should match
        assert "".join(chunks) == content

    def test_read_file_chunked_small_file(self, service, tmp_path):
        """Test chunked reading of small file."""
        test_file = tmp_path / "small.txt"
        content = "Hello"
        test_file.write_text(content)

        chunks = list(service.read_file_chunked(test_file, chunk_size=100))

        # Small file should be one chunk
        assert len(chunks) == 1
        assert chunks[0] == content

    def test_read_file_chunked_nonexistent(self, service, tmp_path):
        """Test chunked reading of non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(FileError) as exc_info:
            list(service.read_file_chunked(nonexistent))

        assert "does not exist" in str(exc_info.value)

    def test_read_lines_streaming(self, service, tmp_path):
        """Test streaming line-by-line reading."""
        test_file = tmp_path / "lines.txt"
        lines = ["line1", "line2", "line3"]
        test_file.write_text("\n".join(lines))

        result = list(service.read_lines_streaming(test_file))

        assert result == lines

    def test_read_lines_streaming_strips_newlines(self, service, tmp_path):
        """Test streaming reads strip newline characters."""
        test_file = tmp_path / "lines.txt"
        test_file.write_text("line1\r\nline2\nline3\r")

        result = list(service.read_lines_streaming(test_file))

        # All newline variants should be stripped
        assert all("\n" not in line and "\r" not in line for line in result)

    def test_read_lines_streaming_empty_file(self, service, tmp_path):
        """Test streaming read of empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        result = list(service.read_lines_streaming(test_file))

        assert result == []

    def test_read_lines_streaming_nonexistent(self, service, tmp_path):
        """Test streaming read of non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(FileError) as exc_info:
            list(service.read_lines_streaming(nonexistent))

        assert "does not exist" in str(exc_info.value)


@pytest.mark.unit
class TestFileSystemServiceTrailingWhitespace:
    """Test trailing whitespace cleaning logic."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_clean_trailing_whitespace_and_newlines(self, service):
        """Test static method cleans trailing whitespace."""
        content = "line1  \nline2\t\nline3 "

        result = service.clean_trailing_whitespace_and_newlines(content)

        lines = result.splitlines()
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert lines[2] == "line3"

    def test_clean_trailing_whitespace_adds_final_newline(self, service):
        """Test cleaning adds final newline."""
        content = "line1\nline2"

        result = service.clean_trailing_whitespace_and_newlines(content)

        assert result.endswith("\n")

    def test_clean_trailing_whitespace_empty_string(self, service):
        """Test cleaning empty string."""
        result = service.clean_trailing_whitespace_and_newlines("")

        assert result == ""

    def test_clean_trailing_whitespace_preserves_content(self, service):
        """Test cleaning preserves line content."""
        content = "  indented\nnormal line\n\ttabbed"

        result = service.clean_trailing_whitespace_and_newlines(content)

        # Leading whitespace should be preserved
        assert "  indented" in result
        assert "\ttabbed" in result


@pytest.mark.unit
class TestFileSystemServiceErrorHandling:
    """Test comprehensive error handling."""

    @pytest.fixture
    def service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    def test_resource_error_no_space_write(self, service, tmp_path, monkeypatch):
        """Test ResourceError raised when no disk space for write."""
        test_file = tmp_path / "test.txt"

        def mock_write_text(*args, **kwargs):
            raise OSError("No space left on device")

        monkeypatch.setattr(Path, "write_text", mock_write_text)

        with pytest.raises(ResourceError) as exc_info:
            service.write_file(test_file, "content")

        assert "Insufficient disk space" in str(exc_info.value)

    def test_resource_error_no_space_mkdir(self, service, tmp_path, monkeypatch):
        """Test ResourceError raised when no disk space for mkdir."""
        test_dir = tmp_path / "testdir"

        def mock_mkdir(*args, **kwargs):
            raise OSError("No space left on device")

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        with pytest.raises(ResourceError) as exc_info:
            service.mkdir(test_dir)

        assert "Insufficient disk space" in str(exc_info.value)

    def test_error_code_preservation(self, service, tmp_path):
        """Test FileError preserves error codes."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        test_file.chmod(0o000)

        try:
            with pytest.raises(FileError) as exc_info:
                service.read_file(test_file)

            # Error code should be set correctly
            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR
        finally:
            test_file.chmod(0o644)

    def test_recovery_messages_provided(self, service, tmp_path):
        """Test FileError includes recovery messages."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(FileError) as exc_info:
            service.read_file(nonexistent)

        # Should have recovery suggestion
        assert exc_info.value.recovery is not None
        assert "check" in exc_info.value.recovery.lower()
