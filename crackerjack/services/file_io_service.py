import json
from pathlib import Path

import aiofiles
from loguru import logger


class FileIOService:
    @staticmethod
    async def read_text_file(path: str | Path, encoding: str = "utf-8") -> str:
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
        try:
            content = json.dumps(data, indent=indent, ensure_ascii=False)
            await FileIOService.write_text_file(path, content, create_dirs=create_dirs)
        except Exception as e:
            logger.error(f"Error writing JSON file {path}: {e}")
            raise

    @staticmethod
    def read_json_file_sync(path: str | Path) -> dict:
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
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading binary file {path}: {e}")
            raise

    @staticmethod
    async def read_binary_file(path: str | Path) -> bytes:
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
        return Path(path).is_file()

    @staticmethod
    def directory_exists(path: str | Path) -> bool:
        return Path(path).is_dir()
