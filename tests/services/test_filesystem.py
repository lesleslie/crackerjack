"""Comprehensive tests for FileSystemService.

Tests all public methods and edge cases including:
- File reading/writing with error handling
- Directory creation and glob operations
- File copying with validation
- File metadata operations
- Streaming operations
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.errors import ErrorCode, FileError, ResourceError
from crackerjack.services.filesystem import FileSystemService


class TestFileSystemServiceInit:
    """Test FileSystemService initialization."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        fs = FileSystemService()
        assert fs is not None

    def test_clean_trailing_whitespace_and_newlines(self) -> None:
        """Test whitespace cleaning static method."""
        content = "line1   \nline2\t\nline3\n"
        result = FileSystemService.clean_trailing_whitespace_and_newlines(content)
        assert result == "line1\nline2\nline3\n"

    def test_clean_trailing_whitespace_no_trailing_newline(self) -> None:
        """Test cleaning when no trailing newline."""
        content = "line1\nline2"
        result = FileSystemService.clean_trailing_whitespace_and_newlines(content)
        assert result == "line1\nline2\n"

    def test_clean_empty_string(self) -> None:
        """Test cleaning empty string returns empty string."""
        result = FileSystemService.clean_trailing_whitespace_and_newlines("")
        assert result == ""


class TestReadFile:
    """Test read_file() method."""

    def test_read_file_success(self, tmp_path: Path) -> None:
        """Test successful file reading."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        fs = FileSystemService()
        content = fs.read_file(test_file)

        assert content == "Hello, World!"

    def test_read_file_string_path(self, tmp_path: Path) -> None:
        """Test reading with string path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        fs = FileSystemService()
        content = fs.read_file(str(test_file))

        assert content == "Hello, World!"

    def test_read_file_not_exists(self, tmp_path: Path) -> None:
        """Test reading non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.read_file(nonexistent)

        assert "File does not exist" in str(exc_info.value.message)

    def test_read_file_permission_error(self, tmp_path: Path) -> None:
        """Test reading file with permission error raises FileError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        with patch("pathlib.Path.read_text") as mock_read:
            mock_read.side_effect = PermissionError("Permission denied")

            with pytest.raises(FileError) as exc_info:
                fs.read_file(test_file)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_read_file_unicode_error(self, tmp_path: Path) -> None:
        """Test reading file with unicode error raises FileError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        with patch("pathlib.Path.read_text") as mock_read:
            mock_read.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")

            with pytest.raises(FileError) as exc_info:
                fs.read_file(test_file)

            assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR

    def test_read_file_os_error(self, tmp_path: Path) -> None:
        """Test reading file with OS error raises FileError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        with patch("pathlib.Path.read_text") as mock_read:
            mock_read.side_effect = OSError("I/O error")

            with pytest.raises(FileError) as exc_info:
                fs.read_file(test_file)

            assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR


class TestWriteFile:
    """Test write_file() method."""

    def test_write_file_success(self, tmp_path: Path) -> None:
        """Test successful file writing."""
        test_file = tmp_path / "test.txt"

        fs = FileSystemService()
        fs.write_file(test_file, "Hello, World!")

        assert test_file.read_text(encoding="utf-8") == "Hello, World!"

    def test_write_file_string_path(self, tmp_path: Path) -> None:
        """Test writing with string path."""
        test_file = tmp_path / "test.txt"

        fs = FileSystemService()
        fs.write_file(str(test_file), "Hello, World!")

        assert test_file.read_text(encoding="utf-8") == "Hello, World!"

    def test_write_file_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test writing creates parent directories."""
        subdir = tmp_path / "sub" / "dir"
        test_file = subdir / "test.txt"

        fs = FileSystemService()
        fs.write_file(test_file, "content")

        assert test_file.exists()
        assert test_file.read_text() == "content"

    def test_write_file_pyproject_cleaned(self, tmp_path: Path) -> None:
        """Test pyproject.toml files have trailing whitespace cleaned."""
        pyproject_file = tmp_path / "pyproject.toml"

        fs = FileSystemService()
        fs.write_file(pyproject_file, "line1   \nline2\n")

        content = pyproject_file.read_text()
        assert not content.endswith("   \n")

    def test_write_file_permission_error(self, tmp_path: Path) -> None:
        """Test writing file with permission error raises FileError."""
        test_file = tmp_path / "test.txt"

        fs = FileSystemService()
        with patch("pathlib.Path.write_text") as mock_write:
            mock_write.side_effect = PermissionError("Permission denied")

            with pytest.raises(FileError) as exc_info:
                fs.write_file(test_file, "content")

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_write_file_disk_space_error(self, tmp_path: Path) -> None:
        """Test writing file with disk space error raises ResourceError."""
        test_file = tmp_path / "test.txt"

        fs = FileSystemService()
        with patch("pathlib.Path.write_text") as mock_write:
            error = OSError("No space left on device")
            mock_write.side_effect = error

            with pytest.raises(ResourceError) as exc_info:
                fs.write_file(test_file, "content")

    def test_write_file_os_error(self, tmp_path: Path) -> None:
        """Test writing file with OS error raises FileError."""
        test_file = tmp_path / "test.txt"

        fs = FileSystemService()
        with patch("pathlib.Path.write_text") as mock_write:
            mock_write.side_effect = OSError("I/O error")

            with pytest.raises(FileError) as exc_info:
                fs.write_file(test_file, "content")

            assert exc_info.value.error_code == ErrorCode.FILE_WRITE_ERROR


class TestExists:
    """Test exists() method."""

    def test_exists_file_true(self, tmp_path: Path) -> None:
        """Test exists returns True for existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        assert fs.exists(test_file) is True

    def test_exists_file_false(self, tmp_path: Path) -> None:
        """Test exists returns False for non-existent file."""
        nonexistent = tmp_path / "nonexistent.txt"

        fs = FileSystemService()
        assert fs.exists(nonexistent) is False

    def test_exists_directory(self, tmp_path: Path) -> None:
        """Test exists returns True for existing directory."""
        fs = FileSystemService()
        assert fs.exists(tmp_path) is True

    def test_exists_os_error_returns_false(self) -> None:
        """Test exists returns False when OSError occurs."""
        fs = FileSystemService()
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.side_effect = OSError("I/O error")
            assert fs.exists(Path("/fake")) is False


class TestMkdir:
    """Test mkdir() method."""

    def test_mkdir_success(self, tmp_path: Path) -> None:
        """Test successful directory creation."""
        new_dir = tmp_path / "new_dir"

        fs = FileSystemService()
        fs.mkdir(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_mkdir_string_path(self, tmp_path: Path) -> None:
        """Test mkdir with string path."""
        new_dir = tmp_path / "new_dir"

        fs = FileSystemService()
        fs.mkdir(str(new_dir))

        assert new_dir.exists()

    def test_mkdir_parents(self, tmp_path: Path) -> None:
        """Test mkdir with parents=True."""
        new_dir = tmp_path / "parent" / "child"

        fs = FileSystemService()
        fs.mkdir(new_dir, parents=True)

        assert new_dir.exists()

    def test_mkdir_already_exists_no_parents(self, tmp_path: Path) -> None:
        """Test mkdir on existing directory without parents succeeds with exist_ok=True."""
        fs = FileSystemService()
        # mkdir with exist_ok=True always succeeds, so this doesn't raise
        fs.mkdir(tmp_path, parents=False)  # Should not raise because exist_ok=True

    def test_mkdir_permission_error(self, tmp_path: Path) -> None:
        """Test mkdir with permission error raises FileError."""
        new_dir = tmp_path / "new_dir"

        fs = FileSystemService()
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")

            with pytest.raises(FileError) as exc_info:
                fs.mkdir(new_dir)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR


class TestGlob:
    """Test glob() method."""

    def test_glob_success(self, tmp_path: Path) -> None:
        """Test successful glob operation."""
        (tmp_path / "test1.py").write_text("# py")
        (tmp_path / "test2.py").write_text("# py")

        fs = FileSystemService()
        result = fs.glob("*.py", tmp_path)

        assert len(result) == 2
        assert all(p.suffix == ".py" for p in result)

    def test_glob_no_matches(self, tmp_path: Path) -> None:
        """Test glob with no matches."""
        fs = FileSystemService()
        result = fs.glob("*.xyz", tmp_path)

        assert result == []

    def test_glob_base_path_not_exists(self, tmp_path: Path) -> None:
        """Test glob with non-existent base path raises FileError."""
        nonexistent = tmp_path / "nonexistent"

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.glob("*.py", nonexistent)

        assert "Base path does not exist" in str(exc_info.value.message)

    def test_glob_permission_error(self, tmp_path: Path) -> None:
        """Test glob with permission error raises FileError."""
        fs = FileSystemService()
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.side_effect = PermissionError("Permission denied")

            with pytest.raises(FileError) as exc_info:
                fs.glob("*.py", tmp_path)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR


class TestRglob:
    """Test rglob() method."""

    def test_rglob_success(self, tmp_path: Path) -> None:
        """Test successful recursive glob."""
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (tmp_path / "test1.py").write_text("# py")
        (subdir / "test2.py").write_text("# py")

        fs = FileSystemService()
        result = fs.rglob("*.py", tmp_path)

        assert len(result) == 2

    def test_rglob_base_path_not_exists(self, tmp_path: Path) -> None:
        """Test rglob with non-existent base path raises FileError."""
        nonexistent = tmp_path / "nonexistent"

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.rglob("*.py", nonexistent)

        assert "Base path does not exist" in str(exc_info.value.message)


class TestCopyFile:
    """Test copy_file() method."""

    def test_copy_file_success(self, tmp_path: Path) -> None:
        """Test successful file copy."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        fs.copy_file(src, dst)

        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "content"

    def test_copy_file_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test copy creates parent directories."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "sub" / "dest.txt"
        src.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        fs.copy_file(src, dst)

        assert dst.exists()
        assert dst.read_text() == "content"

    def test_copy_file_source_not_exists(self, tmp_path: Path) -> None:
        """Test copy with non-existent source raises FileError."""
        src = tmp_path / "nonexistent.txt"
        dst = tmp_path / "dest.txt"

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.copy_file(src, dst)

        assert "Source file does not exist" in str(exc_info.value.message)

    def test_copy_file_source_not_file(self, tmp_path: Path) -> None:
        """Test copy with directory as source raises FileError."""
        src = tmp_path / "somedir"
        src.mkdir()
        dst = tmp_path / "dest.txt"

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.copy_file(src, dst)

        assert "Source is not a file" in str(exc_info.value.message)

    def test_copy_file_same_file_error(self, tmp_path: Path) -> None:
        """Test copy to same file raises FileError."""
        src = tmp_path / "file.txt"
        src.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.copy_file(src, src)

        assert "same file" in str(exc_info.value.message).lower()


class TestRemoveFile:
    """Test remove_file() method."""

    def test_remove_file_success(self, tmp_path: Path) -> None:
        """Test successful file removal."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        fs.remove_file(test_file)

        assert not test_file.exists()

    def test_remove_file_not_found(self, tmp_path: Path) -> None:
        """Test removing non-existent file does nothing."""
        nonexistent = tmp_path / "nonexistent.txt"

        fs = FileSystemService()
        fs.remove_file(nonexistent)  # Should not raise

    def test_remove_file_is_directory(self, tmp_path: Path) -> None:
        """Test removing directory raises FileError."""
        directory = tmp_path / "directory"
        directory.mkdir()

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.remove_file(directory)

        assert "Path is not a file" in str(exc_info.value.message)


class TestGetFileSize:
    """Test get_file_size() method."""

    def test_get_file_size_success(self, tmp_path: Path) -> None:
        """Test getting file size."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        fs = FileSystemService()
        size = fs.get_file_size(test_file)

        assert size == 13  # "Hello, World!" is 13 bytes

    def test_get_file_size_not_exists(self, tmp_path: Path) -> None:
        """Test get_file_size on non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.get_file_size(nonexistent)

        assert "File does not exist" in str(exc_info.value.message)


class TestGetFileMtime:
    """Test get_file_mtime() method."""

    def test_get_file_mtime_success(self, tmp_path: Path) -> None:
        """Test getting file modification time."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        fs = FileSystemService()
        mtime = fs.get_file_mtime(test_file)

        assert mtime > 0

    def test_get_file_mtime_not_exists(self, tmp_path: Path) -> None:
        """Test get_file_mtime on non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        fs = FileSystemService()
        with pytest.raises(FileError) as exc_info:
            fs.get_file_mtime(nonexistent)

        assert "File does not exist" in str(exc_info.value.message)


class TestReadFileChunked:
    """Test read_file_chunked() method."""

    def test_read_file_chunked_success(self, tmp_path: Path) -> None:
        """Test successful chunked reading."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        fs = FileSystemService()
        chunks = list(fs.read_file_chunked(test_file, chunk_size=5))

        assert len(chunks) > 0
        assert "".join(chunks) == "Hello, World!"

    def test_read_file_chunked_not_exists(self, tmp_path: Path) -> None:
        """Test chunked reading of non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        fs = FileSystemService()
        with pytest.raises(FileError):
            list(fs.read_file_chunked(nonexistent))


class TestReadLinesStreaming:
    """Test read_lines_streaming() method."""

    def test_read_lines_streaming_success(self, tmp_path: Path) -> None:
        """Test successful line streaming."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2\nline3\n", encoding="utf-8")

        fs = FileSystemService()
        lines = list(fs.read_lines_streaming(test_file))

        assert lines == ["line1", "line2", "line3"]

    def test_read_lines_streaming_not_exists(self, tmp_path: Path) -> None:
        """Test line streaming of non-existent file raises FileError."""
        nonexistent = tmp_path / "nonexistent.txt"

        fs = FileSystemService()
        with pytest.raises(FileError):
            list(fs.read_lines_streaming(nonexistent))


class TestErrorHandlers:
    """Test error handler methods."""

    def test_handle_permission_error_raises_file_error(self, tmp_path: Path) -> None:
        """Test _handle_permission_error raises FileError."""
        fs = FileSystemService()
        error = PermissionError("Permission denied")

        with pytest.raises(FileError) as exc_info:
            fs._handle_permission_error(error, tmp_path / "test.txt", "reading")

        assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_handle_unicode_error_raises_file_error(self, tmp_path: Path) -> None:
        """Test _handle_unicode_error raises FileError."""
        fs = FileSystemService()
        error = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")

        with pytest.raises(FileError) as exc_info:
            fs._handle_unicode_error(error, tmp_path / "test.txt")

        assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR

    def test_handle_disk_space_error_raises_resource_error(self, tmp_path: Path) -> None:
        """Test _handle_disk_space_error raises ResourceError for disk space."""
        fs = FileSystemService()
        error = OSError("No space left on device")

        with pytest.raises(ResourceError):
            fs._handle_disk_space_error(error, tmp_path / "test.txt", "writing")

    def test_handle_disk_space_error_raises_file_error_for_other(self, tmp_path: Path) -> None:
        """Test _handle_disk_space_error raises FileError for other OSError."""
        fs = FileSystemService()
        error = OSError("Some other error")

        with pytest.raises(FileError) as exc_info:
            fs._handle_disk_space_error(error, tmp_path / "test.txt", "writing")

        assert exc_info.value.error_code == ErrorCode.FILE_WRITE_ERROR