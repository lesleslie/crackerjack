"""Intelligent commit message generation service."""

import re
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.models.protocols import GitInterface

from .regex_patterns import CompiledPatternCache


class CommitMessageGenerator:
    """Generate intelligent commit messages based on changes and context."""

    def __init__(self, console: Console, git_service: GitInterface) -> None:
        """Initialize commit message generator."""
        self.console = console
        self.git = git_service

        # Common change type patterns
        self.patterns = {
            "feat": [
                r"add|create|implement|introduce",
                r"new.*feature",
                r"support.*for",
            ],
            "fix": [
                r"fix|resolve|correct|repair",
                r"bug|issue|problem",
                r"error|exception|failure",
            ],
            "refactor": [
                r"refactor|restructure|reorganize",
                r"extract|move|rename",
                r"improve.*structure",
            ],
            "test": [
                r"test|spec|fixture",
                r"coverage|assertion",
                r"mock|stub",
            ],
            "docs": [
                r"readme|documentation|doc",
                r"comment|docstring",
                r"\.md$|\.rst$|\.txt$",
            ],
            "style": [
                r"format|style|lint",
                r"whitespace|indentation",
                r"prettier|black|ruff",
            ],
            "chore": [
                r"config|setup|build",
                r"dependency|requirement",
                r"version|release",
            ],
        }

    def generate_commit_message(
        self,
        include_body: bool = True,
        conventional_commits: bool = True,
    ) -> str:
        """Generate an intelligent commit message based on staged changes."""
        try:
            # Get changed files and their changes
            staged_files = self.git.get_staged_files()
            if not staged_files:
                return "chore: no changes to commit"

            # Analyze file changes
            change_analysis = self._analyze_changes(staged_files)

            # Generate message components
            commit_type = self._determine_commit_type(change_analysis)
            scope = self._determine_scope(change_analysis)
            subject = self._generate_subject(change_analysis)

            # Build commit message
            if conventional_commits:
                header = self._build_conventional_header(commit_type, scope, subject)
            else:
                header = subject

            if not include_body:
                return header

            # Add body with details
            body = self._generate_body(change_analysis)

            if body:
                return f"{header}\n\n{body}"

            return header

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/yellow] Error generating commit message: {e}"
            )
            return "chore: update files"

    def _analyze_changes(self, staged_files: list[str]) -> dict[str, t.Any]:
        """Analyze staged files to understand the nature of changes."""
        analysis: dict[str, t.Any] = {
            "files": staged_files,
            "file_types": set(),
            "directories": set(),
            "total_files": len(staged_files),
            "patterns_found": set(),
        }

        for file_path in staged_files:
            path = Path(file_path)

            # Track file types
            if path.suffix:
                analysis["file_types"].add(path.suffix)

            # Track directories
            if path.parent != Path():
                analysis["directories"].add(str(path.parent))

            # Check for patterns in file names
            file_str = str(path).lower()
            for commit_type, patterns in self.patterns.items():
                for pattern in patterns:
                    # Use safe compiled pattern cache instead of raw re.search
                    compiled_pattern = (
                        CompiledPatternCache.get_compiled_pattern_with_flags(
                            f"commit_{commit_type}_{pattern}", pattern, re.IGNORECASE
                        )
                    )
                    if compiled_pattern.search(file_str):
                        analysis["patterns_found"].add(commit_type)

        return analysis

    def _determine_commit_type(self, analysis: dict[str, t.Any]) -> str:
        """Determine the most appropriate commit type."""
        patterns_found = analysis["patterns_found"]
        files = analysis["files"]
        file_types = analysis["file_types"]

        # Check commit types in priority order
        commit_type_checks = self._get_commit_type_checks()

        for commit_type, check_func in commit_type_checks:
            if check_func(patterns_found, files, file_types):
                return commit_type

        # Default to chore for misc changes
        return "chore"

    def _get_commit_type_checks(self) -> list[tuple[str, t.Callable[..., t.Any]]]:
        """Get ordered list[t.Any] of commit type checks."""
        return [
            ("fix", self._is_fix_commit),
            ("feat", self._is_feat_commit),
            ("test", self._is_test_commit),
            ("docs", self._is_docs_commit),
            ("style", self._is_style_commit),
            ("refactor", self._is_refactor_commit),
        ]

    def _is_fix_commit(
        self, patterns: set[t.Any], files: list[t.Any], file_types: set[t.Any]
    ) -> bool:
        """Check if this is a fix commit."""
        return "fix" in patterns

    def _is_feat_commit(
        self, patterns: set[t.Any], files: list[t.Any], file_types: set[t.Any]
    ) -> bool:
        """Check if this is a feature commit."""
        return "feat" in patterns

    def _is_test_commit(
        self, patterns: set[t.Any], files: list[t.Any], file_types: set[t.Any]
    ) -> bool:
        """Check if this is a test commit."""
        return "test" in patterns or any(
            ".py" in f and "test" in f.lower() for f in files
        )

    def _is_docs_commit(
        self, patterns: set[t.Any], files: list[t.Any], file_types: set[t.Any]
    ) -> bool:
        """Check if this is a documentation commit."""
        return "docs" in patterns or any(
            ext in file_types for ext in (".md", ".rst", ".txt")
        )

    def _is_style_commit(
        self, patterns: set[t.Any], files: list[t.Any], file_types: set[t.Any]
    ) -> bool:
        """Check if this is a style commit."""
        return (
            "style" in patterns or len(files) > 5
        )  # Multiple files suggest style changes

    def _is_refactor_commit(
        self, patterns: set[t.Any], files: list[t.Any], file_types: set[t.Any]
    ) -> bool:
        """Check if this is a refactor commit."""
        return "refactor" in patterns

    def _determine_scope(self, analysis: dict[str, t.Any]) -> str | None:
        """Determine an appropriate scope for the commit."""
        directories = analysis["directories"]
        files = analysis["files"]

        if len(directories) == 1:
            # Single directory - use as scope
            directory = list[str](directories)[0]
            # Simplify common directory patterns
            if "/" in directory:
                return directory.split("/")[0]  # Use top-level directory
            return directory

        # Check for common patterns
        if any("test" in f.lower() for f in files):
            return "test"
        if any("doc" in f.lower() for f in files):
            return "docs"
        if any(f.endswith(".py") for f in files):
            return "core"
        if any(f.endswith((".yml", ".yaml", ".toml", ".json")) for f in files):
            return "config"

        # No clear scope
        return None

    def _generate_subject(self, analysis: dict[str, t.Any]) -> str:
        """Generate a descriptive subject line."""
        files = analysis["files"]
        file_types = analysis["file_types"]
        total_files = analysis["total_files"]

        # Handle single file changes
        if total_files == 1:
            file_path = Path(files[0])
            file_name = file_path.stem

            # Generate descriptive action based on file name
            if "test" in file_name.lower():
                return f"update {file_name} test"
            elif file_path.suffix in (".md", ".rst", ".txt"):
                return f"update {file_name} documentation"
            elif "config" in file_name.lower():
                return f"update {file_name} configuration"
            else:
                return f"update {file_name}"

        # Handle multiple files
        if total_files <= 3:
            # List specific files
            file_names = [Path(f).stem for f in files]
            return f"update {', '.join(file_names)}"

        # Handle bulk changes
        if len(file_types) == 1:
            file_type = list[t.Any](file_types)[0]
            return f"update {total_files} {file_type} files"

        return f"update {total_files} files"

    def _build_conventional_header(
        self, commit_type: str, scope: str | None, subject: str
    ) -> str:
        """Build conventional commit header format."""
        if scope:
            return f"{commit_type}({scope}): {subject}"
        return f"{commit_type}: {subject}"

    def _generate_body(self, analysis: dict[str, t.Any]) -> str:
        """Generate detailed commit body."""
        files = analysis["files"]
        total_files = analysis["total_files"]

        if total_files <= 3:
            # List specific files for small changes
            body_lines = ["Modified files:"]
            for file_path in sorted(files):
                body_lines.append(f"- {file_path}")
            return "\n".join(body_lines)

        # Summarize for larger changes
        directories = analysis["directories"]
        file_types = analysis["file_types"]

        body_lines = [f"Updated {total_files} files across:"]

        if directories:
            body_lines.append("Directories:")
            for directory in sorted(directories):
                body_lines.append(f"- {directory}")

        if file_types:
            body_lines.append("File types:")
            for file_type in sorted(file_types):
                body_lines.append(f"- {file_type}")

        return "\n".join(body_lines)

    def commit_with_generated_message(
        self,
        include_body: bool = True,
        conventional_commits: bool = True,
        dry_run: bool = False,
    ) -> bool:
        """Generate commit message and create commit."""
        message = self.generate_commit_message(
            include_body=include_body,
            conventional_commits=conventional_commits,
        )

        if dry_run:
            self.console.print("[cyan]📝[/cyan] Generated commit message:")
            self.console.print(f"[dim]{message}[/dim]")
            return True

        self.console.print(
            f"[cyan]📝[/cyan] Committing with message: {message.split(chr(10))[0]}"
        )
        return self.git.commit(message)
