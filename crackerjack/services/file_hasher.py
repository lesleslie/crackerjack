import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .cache import CrackerjackCache


class FileHasher:
    def __init__(self, cache: CrackerjackCache | None = None) -> None:
        self.cache = cache or CrackerjackCache()
        self._executor = ThreadPoolExecutor(max_workers=4)

    def get_file_hash(self, file_path: Path, algorithm: str = "md5") -> str:
        if not file_path.exists():
            return ""

        cached_hash = self.cache.get_file_hash(file_path)
        if cached_hash:
            return cached_hash

        file_hash = self._compute_file_hash(file_path, algorithm)
        self.cache.set_file_hash(file_path, file_hash)
        return file_hash

    def get_directory_hash(
        self,
        directory: Path,
        patterns: list[str] | None = None,
    ) -> str:
        if patterns is None:
            patterns = ["*.py"]

        file_hashes: list[str] = []
        for pattern in patterns:
            for file_path in directory.rglob(pattern):
                if file_path.is_file():
                    file_hash = self.get_file_hash(file_path)
                    file_hashes.append(
                        f"{file_path.relative_to(directory)}: {file_hash}",
                    )

        file_hashes.sort()
        combined_content = "\n".join(file_hashes)
        return hashlib.md5(combined_content.encode(), usedforsecurity=False).hexdigest()

    def get_files_hash_list(self, files: list[Path]) -> list[str]:
        return [
            self.get_file_hash(file_path) for file_path in files if file_path.exists()
        ]

    async def get_files_hash_list_async(self, files: list[Path]) -> list[str]:
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(self._executor, self.get_file_hash, file_path, "md5")
            for file_path in files
            if file_path.exists()
        ]
        return await asyncio.gather(*tasks)

    def has_files_changed(self, files: list[Path], cached_hashes: list[str]) -> bool:
        if len(files) != len(cached_hashes):
            return True

        current_hashes = self.get_files_hash_list(files)
        return current_hashes != cached_hashes

    def _compute_file_hash(self, file_path: Path, algorithm: str = "md5") -> str:
        hash_func = hashlib.new(algorithm)

        try:
            with file_path.open("rb") as f:
                while chunk := f.read(8192):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except OSError:
            return ""

    def get_project_files_hash(self, project_path: Path) -> dict[str, str]:
        patterns = ["*.py", "*.toml", "*.cfg", "*.ini", "*.yaml", "*.yml"]
        file_hashes = {}

        for pattern in patterns:
            for file_path in project_path.rglob(pattern):
                if file_path.is_file() and not self._should_ignore_file(file_path):
                    relative_path = str(file_path.relative_to(project_path))
                    file_hashes[relative_path] = self.get_file_hash(file_path)

        return file_hashes

    def _should_ignore_file(self, file_path: Path) -> bool:
        ignore_patterns = [
            ".git",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            ".coverage",
            ".crackerjack_cache",
            "node_modules",
            ".tox",
            "dist",
            "build",
            "*.egg-info",
        ]

        path_str = str(file_path)
        return any(pattern in path_str for pattern in ignore_patterns)

    def invalidate_cache(self, file_path: Path | None = None) -> None:
        # CrackerjackCache doesn't have direct access to its underlying cache,
        # so for targeted invalidation we would need to clear all file hashes
        # For a specific file, we can't directly invalidate just that entry
        # since the cache key contains mtime and size that would trigger invalidation naturally
        pass  # No direct way to clear individual cache entries in CrackerjackCache


class SmartFileWatcher:
    def __init__(self, file_hasher: FileHasher) -> None:
        self.file_hasher = file_hasher
        self._watched_files: dict[Path, tuple[float, int]] = {}

    def register_files(self, files: list[Path]) -> None:
        for file_path in files:
            if file_path.exists():
                stat = file_path.stat()
                self._watched_files[file_path] = (stat.st_mtime, stat.st_size)

    def check_changes(self) -> list[Path]:
        changed_files: list[Path] = []

        for file_path, (old_mtime, old_size) in self._watched_files.items():
            if not file_path.exists():
                changed_files.append(file_path)
                continue

            stat = file_path.stat()
            if stat.st_mtime != old_mtime or stat.st_size != old_size:
                changed_files.append(file_path)
                self._watched_files[file_path] = (stat.st_mtime, stat.st_size)

        return changed_files

    def invalidate_changed_files(self) -> int:
        changed_files = self.check_changes()

        for file_path in changed_files:
            self.file_hasher.invalidate_cache(file_path)

        return len(changed_files)
