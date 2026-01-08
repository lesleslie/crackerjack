import typing as t
from fnmatch import fnmatch
from pathlib import Path

from crackerjack.models.protocols import (
    GitServiceProtocol,
    ServiceProtocol,
    SmartFileFilterProtocol,
)


class SmartFileFilter(SmartFileFilterProtocol, ServiceProtocol):
    def __init__(
        self,
        git_service: GitServiceProtocol,
        project_root: Path | None = None,
    ):
        self._git_service = git_service
        self.project_root = project_root or Path.cwd()

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    def get_changed_files(self, since: str = "HEAD") -> list[Path]:
        files_str = self._git_service.get_changed_files_since(since, self.project_root)
        return [Path(f) for f in files_str]

    def get_staged_files(self) -> list[Path]:
        files_str = self._git_service.get_staged_files()
        return [Path(f) for f in files_str]

    def get_unstaged_files(self) -> list[Path]:
        return self._git_service.get_unstaged_files(self.project_root)

    def filter_by_pattern(self, files: list[Path], pattern: str) -> list[Path]:
        return [
            file_path
            for file_path in files
            if fnmatch(str(file_path), pattern) or fnmatch(file_path.name, pattern)
        ]

    def filter_by_tool(self, files: list[Path], tool: str) -> list[Path]:
        tool_patterns = {
            "ruff-check": ["*.py"],
            "ruff-format": ["*.py"],
            "zuban": ["*.py"],
            "skylos": ["*.py"],
            "bandit": ["*.py"],
            "refurb": ["*.py"],
            "complexipy": ["*.py"],
            "creosote": ["*.py"],
            "mdformat": ["*.md"],
            "check-yaml": ["*.yaml", "*.yml"],
            "check-toml": ["*.toml"],
            "trailing-whitespace": ["*"],
            "end-of-file-fixer": ["*"],
            "codespell": ["*"],
            "validate-regex-patterns": ["*.py"],
            "gitleaks": ["*"],
            "uv-lock": ["pyproject.toml"],
            "check-added-large-files": ["*"],
        }

        patterns = tool_patterns.get(tool, ["*"])

        filtered = []
        for pattern in patterns:
            filtered.extend(self.filter_by_pattern(files, pattern))

        seen = set()
        result = []
        for file_path in filtered:
            if file_path not in seen:
                seen.add(file_path)
                result.append(file_path)

        return result

    def get_all_modified_files(self) -> list[Path]:
        staged = set(self.get_staged_files())
        unstaged = set(self.get_unstaged_files())
        all_modified = staged | unstaged

        return sorted(all_modified)

    def filter_by_extensions(
        self, files: list[Path], extensions: list[str]
    ) -> list[Path]:
        normalized = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

        return [file_path for file_path in files if file_path.suffix in normalized]

    def get_python_files(self, files: list[Path]) -> list[Path]:
        return self.filter_by_extensions(files, [".py"])

    def get_markdown_files(self, files: list[Path]) -> list[Path]:
        return self.filter_by_extensions(files, [".md"])
