import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.errors import ErrorCode, FileError, ResourceError
from crackerjack.services.filesystem import FileSystemService


class TestFileSystemServiceBasics:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_read_file_success(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_content = "Hello, World ! "
        test_file.write_text(test_content)

        result = fs_service.read_file(test_file)
        assert result == test_content

    def test_read_file_str_path(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_content = "Test content"
        test_file.write_text(test_content)

        result = fs_service.read_file(str(test_file))
        assert result == test_content

    def test_read_file_not_found(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent.txt"

        with pytest.raises(FileError) as exc_info:
            fs_service.read_file(non_existent)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_read_file_permission_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(
            Path,
            "read_text",
            side_effect=PermissionError("Access denied"),
        ):
            with pytest.raises(FileError) as exc_info:
                fs_service.read_file(test_file)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_read_file_unicode_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_bytes(b"\xff\xfe")

        with pytest.raises(FileError) as exc_info:
            fs_service.read_file(test_file)

        assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR

    def test_read_file_os_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(Path, "read_text", side_effect=OSError("Disk error")):
            with pytest.raises(FileError) as exc_info:
                fs_service.read_file(test_file)

            assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR

    def test_write_file_success(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_content = "New content"

        fs_service.write_file(test_file, test_content)
        assert test_file.read_text() == test_content

    def test_write_file_str_path(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_content = "String path content"

        fs_service.write_file(str(test_file), test_content)
        assert test_file.read_text() == test_content

    def test_write_file_create_parent_dirs(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "sub" / "dir" / "test.txt"
        test_content = "Nested content"

        fs_service.write_file(test_file, test_content)
        assert test_file.read_text() == test_content

    def test_write_file_parent_dir_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "sub" / "test.txt"

        with patch.object(Path, "mkdir", side_effect=OSError("Cannot create")):
            with pytest.raises(FileError) as exc_info:
                fs_service.write_file(test_file, "content")

            assert exc_info.value.error_code == ErrorCode.FILE_WRITE_ERROR

    def test_write_file_permission_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"

        with patch.object(
            Path,
            "write_text",
            side_effect=PermissionError("Access denied"),
        ):
            with pytest.raises(FileError) as exc_info:
                fs_service.write_file(test_file, "content")

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_write_file_no_space_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"

        with patch.object(
            Path,
            "write_text",
            side_effect=OSError("No space left on device"),
        ):
            with pytest.raises(ResourceError) as exc_info:
                fs_service.write_file(test_file, "content")

            assert exc_info.value.error_code == ErrorCode.RESOURCE_ERROR

    def test_write_file_os_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"

        with patch.object(Path, "write_text", side_effect=OSError("Disk error")):
            with pytest.raises(FileError) as exc_info:
                fs_service.write_file(test_file, "content")

            assert exc_info.value.error_code == ErrorCode.FILE_WRITE_ERROR

    def test_exists_true(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        assert fs_service.exists(test_file) is True

    def test_exists_false(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent.txt"

        assert fs_service.exists(non_existent) is False

    def test_exists_str_path(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        assert fs_service.exists(str(test_file)) is True

    def test_exists_os_error(self, fs_service) -> None:
        with patch.object(Path, "exists", side_effect=OSError("Error")):
            assert fs_service.exists(" / some / path") is False


class TestFileSystemServiceDirectories:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_mkdir_success(self, fs_service, temp_dir) -> None:
        new_dir = temp_dir / "new_directory"

        fs_service.mkdir(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_mkdir_with_parents(self, fs_service, temp_dir) -> None:
        new_dir = temp_dir / "parent" / "child" / "grandchild"

        fs_service.mkdir(new_dir, parents=True)
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_mkdir_already_exists(self, fs_service, temp_dir) -> None:
        existing_dir = temp_dir / "existing"
        existing_dir.mkdir()

        fs_service.mkdir(existing_dir)
        assert existing_dir.exists()

    def test_mkdir_permission_error(self, fs_service, temp_dir) -> None:
        new_dir = temp_dir / "new_dir"

        with patch.object(Path, "mkdir", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                fs_service.mkdir(new_dir)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_mkdir_no_space_error(self, fs_service, temp_dir) -> None:
        new_dir = temp_dir / "new_dir"

        with patch.object(
            Path,
            "mkdir",
            side_effect=OSError("No space left on device"),
        ):
            with pytest.raises(ResourceError) as exc_info:
                fs_service.mkdir(new_dir)

            assert exc_info.value.error_code == ErrorCode.RESOURCE_ERROR

    def test_mkdir_os_error(self, fs_service, temp_dir) -> None:
        new_dir = temp_dir / "new_dir"

        with patch.object(Path, "mkdir", side_effect=OSError("Disk error")):
            with pytest.raises(FileError) as exc_info:
                fs_service.mkdir(new_dir)

            assert exc_info.value.error_code == ErrorCode.FILE_WRITE_ERROR


class TestFileSystemServiceGlob:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "test1.txt").write_text("content1")
            (temp_path / "test2.txt").write_text("content2")
            (temp_path / "data.json").write_text("{}")
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "test3.txt").write_text("content3")
            yield temp_path

    def test_glob_success(self, fs_service, temp_dir) -> None:
        results = fs_service.glob("*.txt", temp_dir)
        assert len(results) == 2
        assert all(r.suffix == ".txt" for r in results)

    def test_glob_no_path(self, fs_service) -> None:
        with patch.object(Path, "glob", return_value=[]):
            results = fs_service.glob("*.txt")
            assert results == []

    def test_glob_base_path_not_exists(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent"

        with pytest.raises(FileError) as exc_info:
            fs_service.glob("*.txt", non_existent)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_glob_permission_error(self, fs_service, temp_dir) -> None:
        with patch.object(Path, "glob", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                fs_service.glob("*.txt", temp_dir)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_glob_os_error(self, fs_service, temp_dir) -> None:
        with patch.object(Path, "glob", side_effect=OSError("Disk error")):
            with pytest.raises(FileError) as exc_info:
                fs_service.glob("*.txt", temp_dir)

            assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR

    def test_rglob_success(self, fs_service, temp_dir) -> None:
        results = fs_service.rglob("*.txt", temp_dir)
        assert len(results) == 3
        assert all(r.suffix == ".txt" for r in results)

    def test_rglob_no_path(self, fs_service) -> None:
        with patch.object(Path, "rglob", return_value=[]):
            results = fs_service.rglob("*.txt")
            assert results == []

    def test_rglob_base_path_not_exists(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent"

        with pytest.raises(FileError) as exc_info:
            fs_service.rglob("*.txt", non_existent)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_rglob_permission_error(self, fs_service, temp_dir) -> None:
        with patch.object(Path, "rglob", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                fs_service.rglob(" * .txt", temp_dir)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_rglob_os_error(self, fs_service, temp_dir) -> None:
        with patch.object(Path, "rglob", side_effect=OSError("Disk error")):
            with pytest.raises(FileError) as exc_info:
                fs_service.rglob(" * .txt", temp_dir)

            assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR


class TestFileSystemServiceFileOperations:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_copy_file_success(self, fs_service, temp_dir) -> None:
        src_file = temp_dir / "source.txt"
        dst_file = temp_dir / "destination.txt"
        src_content = "Source content"
        src_file.write_text(src_content)

        fs_service.copy_file(src_file, dst_file)
        assert dst_file.exists()
        assert dst_file.read_text() == src_content

    def test_copy_file_str_paths(self, fs_service, temp_dir) -> None:
        src_file = temp_dir / "source.txt"
        dst_file = temp_dir / "destination.txt"
        src_content = "String path content"
        src_file.write_text(src_content)

        fs_service.copy_file(str(src_file), str(dst_file))
        assert dst_file.exists()
        assert dst_file.read_text() == src_content

    def test_copy_file_create_parent_dirs(self, fs_service, temp_dir) -> None:
        src_file = temp_dir / "source.txt"
        dst_file = temp_dir / "sub" / "dir" / "destination.txt"
        src_content = "Nested copy"
        src_file.write_text(src_content)

        fs_service.copy_file(src_file, dst_file)
        assert dst_file.exists()
        assert dst_file.read_text() == src_content

    def test_copy_file_source_not_exists(self, fs_service, temp_dir) -> None:
        src_file = temp_dir / "non_existent.txt"
        dst_file = temp_dir / "destination.txt"

        with pytest.raises(FileError) as exc_info:
            fs_service.copy_file(src_file, dst_file)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_copy_file_source_not_file(self, fs_service, temp_dir) -> None:
        src_dir = temp_dir / "source_dir"
        src_dir.mkdir()
        dst_file = temp_dir / "destination.txt"

        with pytest.raises(FileError) as exc_info:
            fs_service.copy_file(src_dir, dst_file)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_copy_file_permission_error(self, fs_service, temp_dir) -> None:
        src_file = temp_dir / "source.txt"
        dst_file = temp_dir / "destination.txt"
        src_file.write_text("content")

        with patch("shutil.copy2", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                fs_service.copy_file(src_file, dst_file)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_copy_file_same_file_error(self, fs_service, temp_dir) -> None:
        src_file = temp_dir / "source.txt"
        src_file.write_text("content")

        with patch("shutil.copy2", side_effect=shutil.SameFileError("Same file")):
            with pytest.raises(FileError) as exc_info:
                fs_service.copy_file(src_file, src_file)

            assert exc_info.value.error_code == ErrorCode.FILE_WRITE_ERROR

    def test_copy_file_no_space_error(self, fs_service, temp_dir) -> None:
        src_file = temp_dir / "source.txt"
        dst_file = temp_dir / "destination.txt"
        src_file.write_text("content")

        with patch("shutil.copy2", side_effect=OSError("No space left on device")):
            with pytest.raises(ResourceError) as exc_info:
                fs_service.copy_file(src_file, dst_file)

            assert exc_info.value.error_code == ErrorCode.RESOURCE_ERROR

    def test_remove_file_success(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        fs_service.remove_file(test_file)
        assert not test_file.exists()

    def test_remove_file_not_exists(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent.txt"

        fs_service.remove_file(non_existent)

    def test_remove_file_not_file(self, fs_service, temp_dir) -> None:
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        with pytest.raises(FileError) as exc_info:
            fs_service.remove_file(test_dir)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_remove_file_permission_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                fs_service.remove_file(test_file)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR


class TestFileSystemServiceFileInfo:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_get_file_size_success(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_content = "Hello, World ! "
        test_file.write_text(test_content)

        size = fs_service.get_file_size(test_file)
        assert size == len(test_content)

    def test_get_file_size_not_exists(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent.txt"

        with pytest.raises(FileError) as exc_info:
            fs_service.get_file_size(non_existent)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_get_file_size_not_file(self, fs_service, temp_dir) -> None:
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        with pytest.raises(FileError) as exc_info:
            fs_service.get_file_size(test_dir)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_get_file_size_permission_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(Path, "stat", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                fs_service.get_file_size(test_file)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_get_file_mtime_success(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        mtime = fs_service.get_file_mtime(test_file)
        assert isinstance(mtime, float)
        assert mtime > 0

    def test_get_file_mtime_not_exists(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent.txt"

        with pytest.raises(FileError) as exc_info:
            fs_service.get_file_mtime(non_existent)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_get_file_mtime_not_file(self, fs_service, temp_dir) -> None:
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        with pytest.raises(FileError) as exc_info:
            fs_service.get_file_mtime(test_dir)

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_get_file_mtime_permission_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(Path, "stat", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                fs_service.get_file_mtime(test_file)

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR


class TestFileSystemServiceStreaming:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_read_file_chunked_success(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_content = "A" * 20000
        test_file.write_text(test_content)

        chunks = list(fs_service.read_file_chunked(test_file, chunk_size=1000))
        assert len(chunks) == 20
        assert all(len(chunk) == 1000 for chunk in chunks)
        assert "".join(chunks) == test_content

    def test_read_file_chunked_not_exists(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent.txt"

        with pytest.raises(FileError) as exc_info:
            list(fs_service.read_file_chunked(non_existent))

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_read_file_chunked_permission_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(Path, "open", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                list(fs_service.read_file_chunked(test_file))

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_read_file_chunked_unicode_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_bytes(b"\xff\xfe")

        with pytest.raises(FileError) as exc_info:
            list(fs_service.read_file_chunked(test_file))

        assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR

    def test_read_lines_streaming_success(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        lines = ["Line 1", "Line 2", "Line 3"]
        test_file.write_text("\n".join(lines))

        result_lines = list(fs_service.read_lines_streaming(test_file))
        assert result_lines == lines

    def test_read_lines_streaming_strip_newlines(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("Line 1\r\nLine 2\rLine 3\n")

        result_lines = list(fs_service.read_lines_streaming(test_file))
        assert result_lines == ["Line 1", "Line 2", "Line 3"]

    def test_read_lines_streaming_not_exists(self, fs_service, temp_dir) -> None:
        non_existent = temp_dir / "non_existent.txt"

        with pytest.raises(FileError) as exc_info:
            list(fs_service.read_lines_streaming(non_existent))

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_read_lines_streaming_permission_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(Path, "open", side_effect=PermissionError("Access denied")):
            with pytest.raises(FileError) as exc_info:
                list(fs_service.read_lines_streaming(test_file))

            assert exc_info.value.error_code == ErrorCode.PERMISSION_ERROR

    def test_read_lines_streaming_unicode_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_bytes(b"\xff\xfe")

        with pytest.raises(FileError) as exc_info:
            list(fs_service.read_lines_streaming(test_file))

        assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR

    def test_read_lines_streaming_os_error(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        mock_file = MagicMock()
        mock_file.__enter__.side_effect = OSError("Disk error")

        with patch.object(Path, "open", return_value=mock_file):
            with pytest.raises(FileError) as exc_info:
                list(fs_service.read_lines_streaming(test_file))

            assert exc_info.value.error_code == ErrorCode.FILE_READ_ERROR
