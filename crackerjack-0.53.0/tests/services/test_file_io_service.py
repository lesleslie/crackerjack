import json
import tempfile
import asyncio
from pathlib import Path
import pytest
from unittest.mock import patch
from crackerjack.services.file_io_service import FileIOService


def test_read_text_file_sync():
    """Test reading a text file synchronously."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
        tmp.write("Hello, world!")
        tmp_path = Path(tmp.name)

    try:
        content = FileIOService.read_text_file_sync(tmp_path)
        assert content == "Hello, world!"
    finally:
        tmp_path.unlink()


def test_write_text_file_sync():
    """Test writing a text file synchronously."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.txt"

        FileIOService.write_text_file_sync(file_path, "Hello, world!")

        assert file_path.exists()
        assert file_path.read_text() == "Hello, world!"


@pytest.mark.asyncio
async def test_read_text_file():
    """Test reading a text file asynchronously."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
        tmp.write("Hello, async world!")
        tmp_path = Path(tmp.name)

    try:
        content = await FileIOService.read_text_file(tmp_path)
        assert content == "Hello, async world!"
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_write_text_file():
    """Test writing a text file asynchronously."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "async_test.txt"

        await FileIOService.write_text_file(file_path, "Hello, async world!")

        assert file_path.exists()
        assert file_path.read_text() == "Hello, async world!"


def test_read_json_file_sync():
    """Test reading a JSON file synchronously."""
    test_data = {"name": "test", "value": 42}

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
        json.dump(test_data, tmp)
        tmp_path = Path(tmp.name)

    try:
        data = FileIOService.read_json_file_sync(tmp_path)
        assert data == test_data
    finally:
        tmp_path.unlink()


def test_write_json_file_sync():
    """Test writing a JSON file synchronously."""
    test_data = {"name": "test", "value": 42}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.json"

        FileIOService.write_json_file_sync(file_path, test_data)

        assert file_path.exists()
        with open(file_path) as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data


@pytest.mark.asyncio
async def test_read_json_file():
    """Test reading a JSON file asynchronously."""
    test_data = {"name": "test", "value": 42}

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
        json.dump(test_data, tmp)
        tmp_path = Path(tmp.name)

    try:
        data = await FileIOService.read_json_file(tmp_path)
        assert data == test_data
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_write_json_file():
    """Test writing a JSON file asynchronously."""
    test_data = {"name": "test", "value": 42}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "async_test.json"

        await FileIOService.write_json_file(file_path, test_data)

        assert file_path.exists()
        with open(file_path) as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data


def test_read_binary_file_sync():
    """Test reading a binary file synchronously."""
    binary_data = b"Hello, binary world!"

    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp:
        tmp.write(binary_data)
        tmp_path = Path(tmp.name)

    try:
        data = FileIOService.read_binary_file_sync(tmp_path)
        assert data == binary_data
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_read_binary_file():
    """Test reading a binary file asynchronously."""
    binary_data = b"Hello, async binary world!"

    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp:
        tmp.write(binary_data)
        tmp_path = Path(tmp.name)

    try:
        data = await FileIOService.read_binary_file(tmp_path)
        assert data == binary_data
    finally:
        tmp_path.unlink()


def test_write_binary_file_sync():
    """Test writing a binary file synchronously."""
    binary_data = b"Hello, binary world!"

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "binary_test.bin"

        FileIOService.write_binary_file_sync(file_path, binary_data)

        assert file_path.exists()
        assert file_path.read_bytes() == binary_data


@pytest.mark.asyncio
async def test_write_binary_file():
    """Test writing a binary file asynchronously."""
    binary_data = b"Hello, async binary world!"

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "async_binary_test.bin"

        await FileIOService.write_binary_file(file_path, binary_data)

        assert file_path.exists()
        assert file_path.read_bytes() == binary_data


def test_file_exists():
    """Test checking if a file exists."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        assert FileIOService.file_exists(tmp_path) is True
        assert FileIOService.file_exists("nonexistent_file.txt") is False
    finally:
        tmp_path.unlink()


def test_directory_exists():
    """Test checking if a directory exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        assert FileIOService.directory_exists(tmp_path) is True
        assert FileIOService.directory_exists("nonexistent_dir") is False


def test_read_text_file_sync_file_not_found():
    """Test reading a non-existent file synchronously."""
    with pytest.raises(FileNotFoundError):
        FileIOService.read_text_file_sync("nonexistent.txt")


@pytest.mark.asyncio
async def test_read_text_file_async_file_not_found():
    """Test reading a non-existent file asynchronously."""
    with pytest.raises(FileNotFoundError):
        await FileIOService.read_text_file("nonexistent.txt")


def test_write_text_file_sync_with_directory_creation():
    """Test writing a text file with automatic directory creation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "subdir" / "nested" / "test.txt"

        FileIOService.write_text_file_sync(file_path, "Hello, nested world!", create_dirs=True)

        assert file_path.exists()
        assert file_path.read_text() == "Hello, nested world!"


@pytest.mark.asyncio
async def test_write_text_file_async_with_directory_creation():
    """Test writing a text file with automatic directory creation asynchronously."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "async_subdir" / "async_nested" / "async_test.txt"

        await FileIOService.write_text_file(file_path, "Hello, async nested world!", create_dirs=True)

        assert file_path.exists()
        assert file_path.read_text() == "Hello, async nested world!"


def test_write_json_file_sync_with_custom_indent():
    """Test writing a JSON file with custom indentation."""
    test_data = {"name": "test", "value": 42}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "indented_test.json"

        FileIOService.write_json_file_sync(file_path, test_data, indent=4)

        assert file_path.exists()
        content = file_path.read_text()
        # Check that the content has 4-space indentation
        assert "    " in content  # 4 spaces


@pytest.mark.asyncio
async def test_write_json_file_async_with_custom_indent():
    """Test writing a JSON file with custom indentation asynchronously."""
    test_data = {"name": "test", "value": 42}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "async_indented_test.json"

        await FileIOService.write_json_file(file_path, test_data, indent=4)

        assert file_path.exists()
        content = file_path.read_text()
        # Check that the content has 4-space indentation
        assert "    " in content  # 4 spaces


def test_read_json_file_sync_invalid_json():
    """Test reading an invalid JSON file synchronously."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
        tmp.write("{ invalid json }")
        tmp_path = Path(tmp.name)

    try:
        with pytest.raises(json.JSONDecodeError):
            FileIOService.read_json_file_sync(tmp_path)
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_read_json_file_async_invalid_json():
    """Test reading an invalid JSON file asynchronously."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
        tmp.write("{ invalid json }")
        tmp_path = Path(tmp.name)

    try:
        with pytest.raises(json.JSONDecodeError):
            await FileIOService.read_json_file(tmp_path)
    finally:
        tmp_path.unlink()
