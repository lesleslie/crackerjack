"""Git cleanup service for removing deleted files from git index.

This service handles smart cleanup of files that have been added to .gitignore
but still exist in the git index. It uses a three-tiered strategy:

1. Config files → git rm --cached (remove from index, keep local)
2. Cache directories → git rm (remove from git and local)
3. Large cleanups → Suggest git filter-branch (for history rewrite)
"""

from __future__ import annotations

import logging
import subprocess
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.config.settings import CrackerjackSettings, GitCleanupSettings
from crackerjack.models.protocols import GitInterface

if t.TYPE_CHECKING:
    from crackerjack.models.protocols import (
        ConsoleInterface as Console,
    )


@dataclass
class GitCommandResult:
    """Result of a git command execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


logger = logging.getLogger(__name__)


@dataclass
class GitCleanupResult:
    """Result of git cleanup operation."""

    success: bool
    files_removed_cached: int = 0  # Config files (git rm --cached)
    files_removed_hard: int = 0  # Cache dirs (git rm)
    total_files: int = 0
    config_files_removed: list[str] = field(default_factory=list)
    cache_dirs_removed: list[str] = field(default_factory=list)
    summary: str = ""
    error_message: str = ""
    suggested_filter_branch: bool = False
    dry_run: bool = False


class GitCleanupService:
    """Service for cleaning up git index before push operations.

    This service identifies files that have been added to .gitignore but
    are still tracked in git, and removes them using appropriate strategies.
    """

    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        git_service: GitInterface,
        settings: CrackerjackSettings | None = None,
    ) -> None:
        """Initialize git cleanup service with dependencies.

        Args:
            console: Console protocol for output
            pkg_path: Path to package directory
            git_service: Git interface for git operations
            settings: Optional CrackerjackSettings (loads default if None)
        """
        self.console = console
        self.pkg_path = pkg_path
        self.git_service = git_service
        self._settings = settings

        # Cache gitignore settings on first access
        self._gitignore_content: list[str] | None = None

    def _run_git_command(
        self,
        args: list[str],
    ) -> GitCommandResult:
        """Run a git command and return the result.

        Args:
            args: Git command arguments (without 'git' prefix)

        Returns:
            GitCommandResult with success status and output
        """
        cmd = ["git", *args]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return GitCommandResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        except Exception as e:
            logger.error(f"Failed to run git command: {e}")
            return GitCommandResult(
                success=False,
                stderr=str(e),
            )

    @property
    def settings(self) -> GitCleanupSettings:
        """Lazy load settings if not provided."""
        if self._settings is None:
            from crackerjack.config import load_settings
            from crackerjack.config.settings import CrackerjackSettings

            self._settings = load_settings(CrackerjackSettings)
        return self._settings.git_cleanup

    def cleanup_git_deleted_files(
        self,
        dry_run: bool = False,
    ) -> GitCleanupResult:
        """Remove .gitignore files from git index using smart strategy.

        This method implements a three-tiered cleanup approach:
        1. Config files → git rm --cached (keep local, remove from index)
        2. Cache directories → git rm (remove entirely)
        3. Large cleanups → Suggest git filter-branch

        Args:
            dry_run: If True, preview changes without executing

        Returns:
            GitCleanupResult with operation details
        """
        # Precondition check: clean working tree
        if self.settings.require_clean_working_tree:
            is_clean, error_msg = self._validate_working_tree_clean()
            if not is_clean:
                return GitCleanupResult(
                    success=False,
                    error_message=str(error_msg or "Working tree validation failed"),
                    summary=str(error_msg or "Working tree validation failed"),
                )

        # Get all .gitignore patterns
        gitignore_patterns = self._load_gitignore_patterns()
        if not gitignore_patterns:
            return GitCleanupResult(
                success=True,
                summary="No .gitignore patterns found - nothing to clean",
            )

        # Get tracked files that match .gitignore patterns
        tracked_files = self._get_gitignore_changes(gitignore_patterns)

        if not tracked_files:
            return GitCleanupResult(
                success=True,
                summary="No tracked files match .gitignore patterns",
            )

        # Categorize files by cleanup strategy
        config_files, cache_dirs = self._categorize_files(tracked_files)

        # Build summary for dry-run
        if dry_run:
            summary = self._generate_dry_run_summary(
                config_files=config_files,
                cache_dirs=cache_dirs,
            )
            return GitCleanupResult(
                success=True,
                files_removed_cached=len(config_files),
                files_removed_hard=len(cache_dirs),
                total_files=len(config_files) + len(cache_dirs),
                config_files_removed=[str(f) for f in config_files],
                cache_dirs_removed=[str(d) for d in cache_dirs],
                summary=summary,
                dry_run=True,
            )

        # Execute cleanup
        removed_cached = self._remove_from_index_cached(config_files)
        removed_hard = self._remove_from_index_hard(cache_dirs)

        # Check if filter-branch should be suggested
        total_removed = removed_cached + removed_hard
        suggest_filter_branch = (
            self.settings.smart_approach
            and total_removed >= self.settings.filter_branch_threshold
        )

        # Generate summary
        summary = self._generate_cleanup_summary(
            removed_cached=removed_cached,
            removed_hard=removed_hard,
            config_files=config_files,
            cache_dirs=cache_dirs,
            suggest_filter_branch=suggest_filter_branch,
        )

        return GitCleanupResult(
            success=True,
            files_removed_cached=removed_cached,
            files_removed_hard=removed_hard,
            total_files=total_removed,
            config_files_removed=[str(f) for f in config_files],
            cache_dirs_removed=[str(d) for d in cache_dirs],
            summary=summary,
            suggested_filter_branch=suggest_filter_branch,
        )

    def _validate_working_tree_clean(self) -> tuple[bool, str | None]:
        """Validate that git working tree is clean.

        Returns:
            Tuple of (is_clean, error_message)
        """
        try:
            changed_files = self.git_service.get_changed_files()
            if changed_files:
                return (
                    False,
                    f"Working tree has {len(changed_files)} uncommitted changes. "
                    "Please commit or stash changes before git cleanup.",
                )
            return True, None
        except Exception as e:
            logger.error(f"Failed to validate working tree: {e}")
            return False, f"Failed to validate working tree: {e}"

    def _load_gitignore_patterns(self) -> list[str]:
        """Load and parse .gitignore file patterns.

        Returns:
            List of .gitignore patterns (empty if file doesn't exist)
        """
        if self._gitignore_content is not None:
            return self._gitignore_content

        gitignore_path = self.pkg_path / ".gitignore"
        if not gitignore_path.exists():
            self._gitignore_content = []
            return self._gitignore_content

        try:
            content = gitignore_path.read_text()
            # Filter out comments and empty lines
            patterns = [
                line.strip()
                for line in content.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            self._gitignore_content = patterns
            return self._gitignore_content
        except Exception as e:
            logger.error(f"Failed to read .gitignore: {e}")
            self._gitignore_content = []
            return self._gitignore_content

    def _get_gitignore_changes(
        self,
        gitignore_patterns: list[str],
    ) -> list[Path]:
        """Find files tracked in git that match .gitignore patterns.

        Args:
            gitignore_patterns: List of .gitignore patterns

        Returns:
            List of tracked files that match patterns
        """
        tracked_files = []

        # Use git ls-files to get all tracked files
        result = self._run_git_command(["ls-files"])

        if not result.success or not result.stdout:
            return []

        # Parse tracked files
        all_tracked = [
            self.pkg_path / line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        ]

        # Simple pattern matching (doesn't support full .gitignore semantics)
        # For production, consider using 'pathspec' library
        from fnmatch import fnmatch

        for tracked_file in all_tracked:
            rel_path = tracked_file.relative_to(self.pkg_path)
            for pattern in gitignore_patterns:
                # Handle directory patterns
                if pattern.endswith("/"):
                    pattern = pattern[:-1]

                # Match against file name
                if fnmatch(rel_path.name, pattern) or fnmatch(
                    str(rel_path),
                    pattern,
                ):
                    tracked_files.append(tracked_file)
                    break

        return tracked_files

    def _categorize_files(
        self,
        files: list[Path],
    ) -> tuple[list[Path], list[Path]]:
        """Categorize files into config files and cache directories.

        Args:
            files: List of files to categorize

        Returns:
            Tuple of (config_files, cache_dirs)
        """
        config_files = []
        cache_dirs = []

        # Config file patterns (keep local, remove from index)
        config_patterns = [
            ".ruffignore",
            ".mdformatignore",
            "mypy.ini",
            "pyrightconfig.json",
            ".codespell-ignore",
            ".codespellrc",
            ".semgrep.yml",
            ".semgrepignore",
            ".gitleaksignore",
            ".gitleaks.toml",
        ]

        # Cache directory patterns (remove entirely)
        cache_patterns = [
            ".complexipy_cache",
            ".pyscn",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            ".mypy_cache",
            ".coverage",
            "htmlcov",
        ]

        for file_path in files:
            # Check if it's a config file
            if any(file_path.name == pattern for pattern in config_patterns):
                config_files.append(file_path)
                continue

            # Check if it's a cache directory
            if any(
                file_path.name == pattern or file_path.name.startswith(pattern)
                for pattern in cache_patterns
            ):
                cache_dirs.append(file_path)
                continue

            # Default: treat as config file (conservative)
            config_files.append(file_path)

        return config_files, cache_dirs

    def _remove_from_index_cached(self, files: list[Path]) -> int:
        """Remove config files from git index but keep local copies.

        Uses 'git rm --cached' to remove from index only.

        Args:
            files: List of config files to remove

        Returns:
            Number of files removed
        """
        if not files:
            return 0

        removed_count = 0

        for file_path in files:
            try:
                # Use relative path for git command
                rel_path = file_path.relative_to(self.pkg_path)

                result = self._run_git_command(["rm", "--cached", str(rel_path)])

                if result.success:
                    removed_count += 1
                    self.console.print(
                        f"[green]✓[/green] Removed from index: {rel_path}"
                    )
                else:
                    logger.warning(f"Failed to remove {rel_path} from index")

            except Exception as e:
                logger.error(f"Error removing {file_path} from index: {e}")

        return removed_count

    def _remove_from_index_hard(self, files: list[Path]) -> int:
        """Remove cache directories from git index and local filesystem.

        Uses 'git rm' to remove entirely.

        Args:
            files: List of cache directories to remove

        Returns:
            Number of directories removed
        """
        if not files:
            return 0

        removed_count = 0

        for file_path in files:
            try:
                # Use relative path for git command
                rel_path = file_path.relative_to(self.pkg_path)

                result = self._run_git_command(["rm", "-r", str(rel_path)])

                if result.success:
                    removed_count += 1
                    self.console.print(f"[green]✓[/green] Removed entirely: {rel_path}")
                else:
                    logger.warning(f"Failed to remove {rel_path}")

            except Exception as e:
                logger.error(f"Error removing {file_path}: {e}")

        return removed_count

    def _suggest_filter_branch(self, large_cleanup: bool) -> bool:
        """Suggest git filter-branch for large cleanups.

        Args:
            large_cleanup: Whether cleanup exceeds threshold

        Returns:
            True if suggestion was made, False otherwise
        """
        if not large_cleanup:
            return False

        self.console.print()
        self.console.print(
            "[yellow]⚠️[/yellow] "
            f"Large cleanup detected (>{self.settings.filter_branch_threshold} files)"
        )
        self.console.print(
            "[yellow]⚠️[/yellow] "
            "Consider using 'git filter-branch' to remove files from history:"
        )
        self.console.print()
        self.console.print("  [cyan]git filter-branch --force --index-filter \\[/cyan]")
        self.console.print(
            "    [cyan]'git rm --cached --ignore-unmatch <file>' \\[/cyan]"
        )
        self.console.print(
            "    [cyan]--prune-empty --tag-name-filter cat -- --all[/cyan]"
        )
        self.console.print()
        self.console.print(
            "[yellow]⚠️[/yellow] "
            "Warning: This rewrites git history. Only use if necessary."
        )

        return True

    def _generate_dry_run_summary(
        self,
        config_files: list[Path],
        cache_dirs: list[Path],
    ) -> str:
        """Generate summary for dry-run mode.

        Args:
            config_files: Config files to be removed
            cache_dirs: Cache directories to be removed

        Returns:
            Formatted summary string
        """
        lines = [
            "Git Cleanup (Dry Run)",
            "=" * 40,
            f"Config files to remove (git rm --cached): {len(config_files)}",
        ]

        if config_files:
            for file_path in config_files[:10]:  # Show first 10
                rel_path = file_path.relative_to(self.pkg_path)
                lines.append(f"  - {rel_path}")
            if len(config_files) > 10:
                lines.append(f"  ... and {len(config_files) - 10} more")

        lines.append(f"Cache dirs to remove (git rm -r): {len(cache_dirs)}")

        if cache_dirs:
            for dir_path in cache_dirs[:10]:  # Show first 10
                rel_path = dir_path.relative_to(self.pkg_path)
                lines.append(f"  - {rel_path}")
            if len(cache_dirs) > 10:
                lines.append(f"  ... and {len(cache_dirs) - 10} more")

        total = len(config_files) + len(cache_dirs)
        lines.append("=" * 40)
        lines.append(f"Total files to be removed: {total}")

        return "\n".join(lines)

    def _generate_cleanup_summary(
        self,
        removed_cached: int,
        removed_hard: int,
        config_files: list[Path],
        cache_dirs: list[Path],
        suggest_filter_branch: bool,
    ) -> str:
        """Generate summary of cleanup operation.

        Args:
            removed_cached: Number of config files removed
            removed_hard: Number of cache dirs removed
            config_files: Config files that were removed
            cache_dirs: Cache dirs that were removed
            suggest_filter_branch: Whether filter-branch was suggested

        Returns:
            Formatted summary string
        """
        lines = [
            "Git Cleanup Complete",
            "=" * 40,
            f"Config files removed (git rm --cached): {removed_cached}",
            f"Cache directories removed (git rm -r): {removed_hard}",
            f"Total files removed: {removed_cached + removed_hard}",
        ]

        if suggest_filter_branch:
            lines.append("")
            lines.append("Note: Consider using git filter-branch for history cleanup")

        return "\n".join(lines)
