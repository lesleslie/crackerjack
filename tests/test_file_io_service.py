"""Tests for the FileIOService."""

import asyncio
import json
from pathlib import Path
import tempfile
import pytest
from crackerjack.services.file_io_service import FileIOService


class TestFileIOService:
    """Test cases for FileIOService functionality."""

    def test_read_text_file_sync(self):
        """Test synchronous reading of text files."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
            tmp.write("Hello, World!")
            tmp_path = Path(tmp.name)

        try:
            content = FileIOService.read_text_file_sync(tmp_path)
            assert content == "Hello, World!"
        finally:
            tmp_path.unlink()

    def test_write_text_file_sync(self):
        """Test synchronous writing of text files."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            tmp_path = Path(tmp.name)

        try:
            FileIOService.write_text_file_sync(tmp_path, "Hello, World!")
            with open(tmp_path) as f:
                content = f.read()
            assert content == "Hello, World!"
        finally:
            tmp_path.unlink()

    def test_read_json_file_sync(self):
        """Test synchronous reading of JSON files."""
        test_data = {"key": "value", "number": 42}
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
            json.dump(test_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            content = FileIOService.read_json_file_sync(tmp_path)
            assert content == test_data
        finally:
            tmp_path.unlink()

    def test_write_json_file_sync(self):
        """Test synchronous writing of JSON files."""
        test_data = {"key": "value", "number": 42}
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            tmp_path = Path(tmp.name)

        try:
            FileIOService.write_json_file_sync(tmp_path, test_data)
            with open(tmp_path) as f:
                content = json.load(f)
            assert content == test_data
        finally:
            tmp_path.unlink()

    def test_read_binary_file_sync(self):
        """Test synchronous reading of binary files."""
        test_data = b"Hello, World!"
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as tmp:
            tmp.write(test_data)
            tmp_path = Path(tmp.name)

        try:
            content = FileIOService.read_binary_file_sync(tmp_path)
            assert content == test_data
        finally:
            tmp_path.unlink()

    def test_write_binary_file_sync(self):
        """Test synchronous writing of binary files."""
        test_data = b"Hello, World!"
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp:
            tmp_path = Path(tmp.name)

        try:
            FileIOService.write_binary_file_sync(tmp_path, test_data)
            with open(tmp_path, "rb") as f:
                content = f.read()
            assert content == test_data
        finally:
            tmp_path.unlink()

    def test_file_exists(self):
        """Test file existence checking."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            tmp_path = Path(tmp.name)

        try:
            assert FileIOService.file_exists(tmp_path) == True
            assert FileIOService.file_exists(Path("nonexistent_file.txt")) == False
        finally:
            tmp_path.unlink()

    def test_directory_exists(self):
        """Test directory existence checking."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assert FileIOService.directory_exists(tmp_path) == True
            assert FileIOService.directory_exists(Path("nonexistent_dir")) == False

    @pytest.mark.asyncio
    async def test_read_text_file_async(self):
        """Test asynchronous reading of text files."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
            tmp.write("Hello, Async World!")
            tmp_path = Path(tmp.name)

        try:
            content = await FileIOService.read_text_file(tmp_path)
            assert content == "Hello, Async World!"
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_write_text_file_async(self):
        """Test asynchronous writing of text files."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            tmp_path = Path(tmp.name)

        try:
            await FileIOService.write_text_file(tmp_path, "Hello, Async World!")
            with open(tmp_path) as f:
                content = f.read()
            assert content == "Hello, Async World!"
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_read_json_file_async(self):
        """Test asynchronous reading of JSON files."""
        test_data = {"key": "async_value", "number": 99}
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
            json.dump(test_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            content = await FileIOService.read_json_file(tmp_path)
            assert content == test_data
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_write_json_file_async(self):
        """Test asynchronous writing of JSON files."""
        test_data = {"key": "async_value", "number": 99}
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            tmp_path = Path(tmp.name)

        try:
            await FileIOService.write_json_file(tmp_path, test_data)
            with open(tmp_path) as f:
                content = json.load(f)
            assert content == test_data
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_read_binary_file_async(self):
        """Test asynchronous reading of binary files."""
        test_data = b"Hello, Async World!"
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as tmp:
            tmp.write(test_data)
            tmp_path = Path(tmp.name)

        try:
            content = await FileIOService.read_binary_file(tmp_path)
            assert content == test_data
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_write_binary_file_async(self):
        """Test asynchronous writing of binary files."""
        test_data = b"Hello, Async World!"
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as tmp:
            tmp_path = Path(tmp.name)

        try:
            await FileIOService.write_binary_file(tmp_path, test_data)
            with open(tmp_path, "rb") as f:
                content = f.read()
            assert content == test_data
        finally:
            tmp_path.unlink()

    def test_write_text_file_sync_with_dir_creation(self):
        """Test that write_text_file creates directories when create_dirs=True."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir) / "subdir"
            file_path = dir_path / "test.txt"

            FileIOService.write_text_file_sync(file_path, "Hello, World!")

            assert file_path.exists()
            with open(file_path) as f:
                content = f.read()
            assert content == "Hello, World!"

    def test_write_json_file_sync_with_dir_creation(self):
        """Test that write_json_file creates directories when create_dirs=True."""
        test_data = {"key": "value", "number": 42}
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir) / "subdir"
            file_path = dir_path / "test.json"

            FileIOService.write_json_file_sync(file_path, test_data)

            assert file_path.exists()
            with open(file_path) as f:
                content = json.load(f)
            assert content == test_data

    @pytest.mark.asyncio
    async def test_write_text_file_async_with_dir_creation(self):
        """Test that async write_text_file creates directories when create_dirs=True."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir) / "async_subdir"
            file_path = dir_path / "test.txt"

            await FileIOService.write_text_file(file_path, "Hello, Async World!")

            assert file_path.exists()
            with open(file_path) as f:
                content = f.read()
            assert content == "Hello, Async World!"

    @pytest.mark.asyncio
    async def test_write_json_file_async_with_dir_creation(self):
        """Test that async write_json_file creates directories when create_dirs=True."""
        test_data = {"key": "value", "number": 42}
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir) / "async_subdir"
            file_path = dir_path / "test.json"

            await FileIOService.write_json_file(file_path, test_data)

            assert file_path.exists()
            with open(file_path) as f:
                content = json.load(f)
            assert content == test_data
