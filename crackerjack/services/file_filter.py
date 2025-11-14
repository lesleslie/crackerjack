"""Smart file filtering for incremental tool execution.

Filters files based on git changes, patterns, and tool requirements.
Part of Phase 10.2: Development Velocity Improvements.
"""

import typing as t
from fnmatch import fnmatch
from pathlib import Path

from crackerjack.models.protocols import (
    GitServiceProtocol,
    ServiceProtocol,
    SmartFileFilterProtocol,
)


class SmartFileFilter(SmartFileFilterProtocol, ServiceProtocol):
    """Filter files for tool execution based on git changes and patterns.

    Provides intelligent file filtering to enable incremental execution,
    reducing unnecessary tool runs and improving feedback loops.
    """

    def __init__(
        self,
        git_service: GitServiceProtocol,
        project_root: Path | None = None,
    ):
        """Initialize file filter.

        Args:
            git_service: Git service for repository operations
            project_root: Project root directory (defaults to cwd)
        """
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
        """Get files changed since a git reference.

        Args:
            since: Git reference (commit, branch, tag, or "HEAD")

        Returns:
            List of changed file paths relative to project root
        """
        return self._git_service.get_changed_files_since(since, self.project_root)

    def get_staged_files(self) -> list[Path]:
        """Get currently staged files (in git index).

        Returns:
            List of staged file paths relative to project root
        """
        return self._git_service.get_staged_files(self.project_root)

    def get_unstaged_files(self) -> list[Path]:
        """Get unstaged modified files (working tree changes).

        Returns:
            List of unstaged file paths relative to project root
        """
        return self._git_service.get_unstaged_files(self.project_root)

    def filter_by_pattern(self, files: list[Path], pattern: str) -> list[Path]:
        """Filter files by glob pattern.

        Args:
            files: List of file paths to filter
            pattern: Glob pattern (e.g., '*.py', '**/*.ts')

        Returns:
            List of files matching the pattern
        """
        return [
            file_path
            for file_path in files
            if fnmatch(str(file_path), pattern) or fnmatch(file_path.name, pattern)
        ]

    def filter_by_tool(self, files: list[Path], tool: str) -> list[Path]:
        """Filter files relevant to a specific tool.

        Args:
            files: List of file paths to filter
            tool: Tool name (e.g., 'ruff-check', 'zuban', 'skylos')

        Returns:
            List of files applicable to the tool
        """
        # Tool-specific file type mappings
        tool_patterns = {
            # Python tools
            "ruff-check": ["*.py"],
            "ruff-format": ["*.py"],
            "zuban": ["*.py"],
            "skylos": ["*.py"],
            "bandit": ["*.py"],
            "refurb": ["*.py"],
            "complexipy": ["*.py"],
            "creosote": ["*.py"],
            # Markdown tools
            "mdformat": ["*.md"],
            # YAML/TOML tools
            "check-yaml": ["*.yaml", "*.yml"],
            "check-toml": ["*.toml"],
            # Text tools (apply to most files)
            "trailing-whitespace": ["*"],
            "end-of-file-fixer": ["*"],
            "codespell": ["*"],
            # Special tools
            "validate-regex-patterns": ["*.py"],
            "gitleaks": ["*"],
            "uv-lock": ["pyproject.toml"],
            "check-added-large-files": ["*"],
        }

        patterns = tool_patterns.get(tool, ["*"])

        # Apply all patterns for the tool
        filtered = []
        for pattern in patterns:
            filtered.extend(self.filter_by_pattern(files, pattern))

        # Remove duplicates while preserving order
        seen = set()
        result = []
        for file_path in filtered:
            if file_path not in seen:
                seen.add(file_path)
                result.append(file_path)

        return result

    def get_all_modified_files(self) -> list[Path]:
        """Get all modified files (staged + unstaged).

        Returns:
            Combined list of staged and unstaged files
        """
        staged = set(self.get_staged_files())
        unstaged = set(self.get_unstaged_files())
        all_modified = staged | unstaged

        return sorted(all_modified)

    def filter_by_extensions(
        self, files: list[Path], extensions: list[str]
    ) -> list[Path]:
        """Filter files by file extensions.

        Args:
            files: List of file paths to filter
            extensions: List of extensions (e.g., ['.py', '.md'])

        Returns:
            List of files with matching extensions
        """
        # Normalize extensions to include leading dot
        normalized = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

        return [file_path for file_path in files if file_path.suffix in normalized]

    def get_python_files(self, files: list[Path]) -> list[Path]:
        """Convenience method to filter Python files.

        Args:
            files: List of file paths to filter

        Returns:
            List of Python files (.py)
        """
        return self.filter_by_extensions(files, [".py"])

    def get_markdown_files(self, files: list[Path]) -> list[Path]:
        """Convenience method to filter Markdown files.

        Args:
            files: List of file paths to filter

        Returns:
            List of Markdown files (.md)
        """
        return self.filter_by_extensions(files, [".md"])
