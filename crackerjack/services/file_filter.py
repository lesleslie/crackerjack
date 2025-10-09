"""Smart file filtering for incremental tool execution.

Filters files based on git changes, patterns, and tool requirements.
Part of Phase 10.2: Development Velocity Improvements.
"""

import subprocess
from pathlib import Path

from crackerjack.models.protocols import GitInterface


class SmartFileFilter:
    """Filter files for tool execution based on git changes and patterns.

    Provides intelligent file filtering to enable incremental execution,
    reducing unnecessary tool runs and improving feedback loops.
    """

    def __init__(
        self, git_service: GitInterface | None = None, project_root: Path | None = None
    ):
        """Initialize file filter.

        Args:
            git_service: Git service for repository operations (optional, not currently used)
            project_root: Project root directory (defaults to cwd)
        """
        self.git = git_service
        self.project_root = project_root or Path.cwd()

    def get_changed_files(self, since: str = "HEAD") -> list[Path]:
        """Get files changed since a git reference.

        Args:
            since: Git reference (commit, branch, tag, or "HEAD")

        Returns:
            List of changed file paths relative to project root
        """
        try:
            # Get diff between working tree and specified reference
            result = subprocess.run(
                ["git", "diff", "--name-only", since],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            changed_files = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    file_path = self.project_root / line
                    if file_path.exists():
                        changed_files.append(file_path)

            return changed_files

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Fallback: return empty list if git command fails
            return []

    def get_staged_files(self) -> list[Path]:
        """Get currently staged files (in git index).

        Returns:
            List of staged file paths relative to project root
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            staged_files = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    file_path = self.project_root / line
                    if file_path.exists():
                        staged_files.append(file_path)

            return staged_files

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []

    def get_unstaged_files(self) -> list[Path]:
        """Get unstaged modified files (working tree changes).

        Returns:
            List of unstaged file paths relative to project root
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            unstaged_files = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    file_path = self.project_root / line
                    if file_path.exists():
                        unstaged_files.append(file_path)

            return unstaged_files

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []

    def filter_by_pattern(self, files: list[Path], pattern: str) -> list[Path]:
        """Filter files by glob pattern.

        Args:
            files: List of file paths to filter
            pattern: Glob pattern (e.g., '*.py', '**/*.ts')

        Returns:
            List of files matching the pattern
        """
        from fnmatch import fnmatch

        filtered = []
        for file_path in files:
            # Check both absolute and relative patterns
            if fnmatch(str(file_path), pattern) or fnmatch(file_path.name, pattern):
                filtered.append(file_path)

        return filtered

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

        filtered = []
        for file_path in files:
            if file_path.suffix in normalized:
                filtered.append(file_path)

        return filtered

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
