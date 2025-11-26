"""Centralized file I/O operations with consistent error handling."""

import json
from pathlib import Path

import aiofiles
from loguru import logger


class FileIOService:
    """Centralized file I/O operations with consistent error handling."""

    @staticmethod
    async def read_text_file(path: str | Path, encoding: str = "utf-8") -> str:
        """
        Asynchronously read a text file with consistent error handling.

        Args:
            path: Path to the file to read
            encoding: Text encoding to use (default: utf-8)

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: If the file doesn't exist
            UnicodeDecodeError: If there's an encoding issue
            OSError: For other file system errors
        """
        try:
            async with aiofiles.open(path, encoding=encoding) as f:
                return await f.read()
        except FileNotFoundError:
            logger.warning(f"File not found: {path}")
            raise
        except UnicodeDecodeError:
            logger.error(f"Failed to decode file as {encoding}: {path}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise

    @staticmethod
    async def write_text_file(
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
    ) -> None:
        """
        Asynchronously write content to a text file with consistent error handling.

        Args:
            path: Path to the file to write
            content: Content to write to the file
            encoding: Text encoding to use (default: utf-8)
            create_dirs: Whether to create parent directories if they don't exist

        Raises:
            OSError: For file system errors
        """
        try:
            file_path = Path(path)

            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(file_path, "w", encoding=encoding) as f:
                await f.write(content)
        except Exception as e:
            logger.error(f"Error writing to file {path}: {e}")
            raise

    @staticmethod
    def read_text_file_sync(path: str | Path, encoding: str = "utf-8") -> str:
        """
        Synchronously read a text file with consistent error handling.

        Args:
            path: Path to the file to read
            encoding: Text encoding to use (default: utf-8)

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: If the file doesn't exist
            UnicodeDecodeError: If there's an encoding issue
            OSError: For other file system errors
        """
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"File not found: {path}")
            raise
        except UnicodeDecodeError:
            logger.error(f"Failed to decode file as {encoding}: {path}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise

    @staticmethod
    def write_text_file_sync(
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
    ) -> None:
        """
        Synchronously write content to a text file with consistent error handling.

        Args:
            path: Path to the file to write
            content: Content to write to the file
            encoding: Text encoding to use (default: utf-8)
            create_dirs: Whether to create parent directories if they don't exist

        Raises:
            OSError: For file system errors
        """
        try:
            file_path = Path(path)

            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            with file_path.open("w", encoding=encoding) as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Error writing to file {path}: {e}")
            raise

    @staticmethod
    async def read_json_file(path: str | Path) -> dict:
        """
        Asynchronously read and parse a JSON file.

        Args:
            path: Path to the JSON file to read

        Returns:
            Parsed JSON content as dictionary

        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file contains invalid JSON
            OSError: For other file system errors
        """
        try:
            content = await FileIOService.read_text_file(path)
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reading JSON file {path}: {e}")
            raise

    @staticmethod
    async def write_json_file(
        path: str | Path, data: dict, create_dirs: bool = True, indent: int = 2
    ) -> None:
        """
        Asynchronously write data to a JSON file.

        Args:
            path: Path to the JSON file to write
            data: Data to serialize to JSON
            create_dirs: Whether to create parent directories if they don't exist
            indent: JSON indentation (default: 2)

        Raises:
            OSError: For file system errors
            TypeError: If data is not JSON serializable
        """
        try:
            content = json.dumps(data, indent=indent, ensure_ascii=False)
            await FileIOService.write_text_file(path, content, create_dirs=create_dirs)
        except Exception as e:
            logger.error(f"Error writing JSON file {path}: {e}")
            raise

    @staticmethod
    def read_json_file_sync(path: str | Path) -> dict:
        """
        Synchronously read and parse a JSON file.

        Args:
            path: Path to the JSON file to read

        Returns:
            Parsed JSON content as dictionary

        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file contains invalid JSON
            OSError: For other file system errors
        """
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reading JSON file {path}: {e}")
            raise

    @staticmethod
    def write_json_file_sync(
        path: str | Path, data: dict, create_dirs: bool = True, indent: int = 2
    ) -> None:
        """
        Synchronously write data to a JSON file.

        Args:
            path: Path to the JSON file to write
            data: Data to serialize to JSON
            create_dirs: Whether to create parent directories if they don't exist
            indent: JSON indentation (default: 2)

        Raises:
            OSError: For file system errors
            TypeError: If data is not JSON serializable
        """
        try:
            file_path = Path(path)

            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            with file_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error writing JSON file {path}: {e}")
            raise

    @staticmethod
    def read_binary_file_sync(path: str | Path) -> bytes:
        """
        Synchronously read a binary file with consistent error handling.

        Args:
            path: Path to the binary file to read

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If the file doesn't exist
            OSError: For other file system errors
        """
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading binary file {path}: {e}")
            raise

    @staticmethod
    async def read_binary_file(path: str | Path) -> bytes:
        """
        Asynchronously read a binary file with consistent error handling.

        Args:
            path: Path to the binary file to read

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If the file doesn't exist
            OSError: For other file system errors
        """
        try:
            async with aiofiles.open(path, "rb") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Error reading binary file {path}: {e}")
            raise

    @staticmethod
    def write_binary_file_sync(
        path: str | Path, data: bytes, create_dirs: bool = True
    ) -> None:
        """
        Synchronously write bytes to a binary file with consistent error handling.

        Args:
            path: Path to the binary file to write
            data: Bytes to write to the file
            create_dirs: Whether to create parent directories if they don't exist

        Raises:
            OSError: For file system errors
        """
        try:
            file_path = Path(path)

            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            file_path.write_bytes(data)
        except Exception as e:
            logger.error(f"Error writing to binary file {path}: {e}")
            raise

    @staticmethod
    async def write_binary_file(
        path: str | Path, data: bytes, create_dirs: bool = True
    ) -> None:
        """
        Asynchronously write bytes to a binary file with consistent error handling.

        Args:
            path: Path to the binary file to write
            data: Bytes to write to the file
            create_dirs: Whether to create parent directories if they don't exist

        Raises:
            OSError: For file system errors
        """
        try:
            file_path = Path(path)

            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(file_path, "wb") as f:
                await f.write(data)
        except Exception as e:
            logger.error(f"Error writing to binary file {path}: {e}")
            raise

    @staticmethod
    def file_exists(path: str | Path) -> bool:
        """
        Check if a file exists.

        Args:
            path: Path to check for existence

        Returns:
            True if file exists, False otherwise
        """
        return Path(path).is_file()

    @staticmethod
    def directory_exists(path: str | Path) -> bool:
        """
        Check if a directory exists.

        Args:
            path: Path to check for existence

        Returns:
            True if directory exists, False otherwise
        """
        return Path(path).is_dir()
