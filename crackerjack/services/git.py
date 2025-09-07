import subprocess
from pathlib import Path

from rich.console import Console

from .secure_subprocess import execute_secure_subprocess
from .security_logger import get_security_logger

# Centralized Git command registry for security validation
GIT_COMMANDS = {
    "git_dir": ["rev-parse", "--git-dir"],
    "staged_files": ["diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
    "unstaged_files": ["diff", "--name-only", "--diff-filter=ACMRT"],
    "untracked_files": ["ls-files", "--others", "--exclude-standard"],
    "staged_files_simple": ["diff", "--cached", "--name-only"],
    "add_file": ["add"],  # File path will be appended
    "add_all": ["add", "-A", "."],
    "commit": ["commit", "-m"],  # Message will be appended
    "add_updated": ["add", "-u"],
    "push_porcelain": ["push", "--porcelain"],
    "current_branch": ["branch", "--show-current"],
    "commits_ahead": ["rev-list", "--count", "@{u}..HEAD"],
}


class FailedGitResult:
    """A Git result object compatible with subprocess.CompletedProcess."""

    def __init__(self, command: list[str], error: str) -> None:
        self.args = command
        self.returncode = -1
        self.stdout = ""
        self.stderr = f"Git security validation failed: {error}"


class GitService:
    def __init__(self, console: Console, pkg_path: Path | None = None) -> None:
        self.console = console
        self.pkg_path = pkg_path or Path.cwd()

    def _run_git_command(
        self, args: list[str]
    ) -> subprocess.CompletedProcess[str] | FailedGitResult:
        """Execute Git commands with secure subprocess validation."""
        cmd = ["git", *args]

        try:
            return execute_secure_subprocess(
                command=cmd,
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,  # Don't raise on non-zero exit codes
            )
        except Exception as e:
            # Log security issues but return a compatible result
            security_logger = get_security_logger()
            security_logger.log_subprocess_failure(
                command=cmd,
                exit_code=-1,
                error_output=str(e),
            )

            # Create compatible result for Git operations
            return FailedGitResult(cmd, str(e))

    def is_git_repo(self) -> bool:
        try:
            result = self._run_git_command(GIT_COMMANDS["git_dir"])
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            return False

    def get_changed_files(self) -> list[str]:
        try:
            staged_result = self._run_git_command(GIT_COMMANDS["staged_files"])
            staged_files = (
                staged_result.stdout.strip().split("\n")
                if staged_result.stdout.strip()
                else []
            )

            unstaged_result = self._run_git_command(GIT_COMMANDS["unstaged_files"])
            unstaged_files = (
                unstaged_result.stdout.strip().split("\n")
                if unstaged_result.stdout.strip()
                else []
            )

            untracked_result = self._run_git_command(GIT_COMMANDS["untracked_files"])
            untracked_files = (
                untracked_result.stdout.strip().split("\n")
                if untracked_result.stdout.strip()
                else []
            )

            all_files = set(staged_files + unstaged_files + untracked_files)
            return [f for f in all_files if f]
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/ yellow] Error getting changed files: {e}")
            return []

    def get_staged_files(self) -> list[str]:
        try:
            result = self._run_git_command(GIT_COMMANDS["staged_files_simple"])
            return result.stdout.strip().split("\n") if result.stdout.strip() else []
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/ yellow] Error getting staged files: {e}")
            return []

    def add_files(self, files: list[str]) -> bool:
        try:
            for file in files:
                cmd = GIT_COMMANDS["add_file"] + [file]
                result = self._run_git_command(cmd)
                if result.returncode != 0:
                    self.console.print(
                        f"[red]❌[/ red] Failed to add {file}: {result.stderr}",
                    )
                    return False
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error adding files: {e}")
            return False

    def add_all_files(self) -> bool:
        """Stage all changes including new, modified, and deleted files."""
        try:
            result = self._run_git_command(GIT_COMMANDS["add_all"])
            if result.returncode == 0:
                self.console.print("[green]✅[/ green] Staged all changes")
                return True
            self.console.print(
                f"[red]❌[/ red] Failed to stage changes: {result.stderr}"
            )
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error staging files: {e}")
            return False

    def commit(self, message: str) -> bool:
        try:
            cmd = GIT_COMMANDS["commit"] + [message]
            result = self._run_git_command(cmd)
            if result.returncode == 0:
                self.console.print(f"[green]✅[/ green] Committed: {message}")
                return True

            return self._handle_commit_failure(result, message)
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error committing: {e}")
            return False

    def _handle_commit_failure(
        self, result: subprocess.CompletedProcess[str] | FailedGitResult, message: str
    ) -> bool:
        if "files were modified by this hook" in result.stderr:
            return self._retry_commit_after_restage(message)

        return self._handle_hook_error(result)

    def _retry_commit_after_restage(self, message: str) -> bool:
        self.console.print(
            "[yellow]🔄[/ yellow] Pre - commit hooks modified files - attempting to re-stage and retry commit"
        )

        add_result = self._run_git_command(GIT_COMMANDS["add_updated"])
        if add_result.returncode != 0:
            self.console.print(
                f"[red]❌[/ red] Failed to re-stage files: {add_result.stderr}"
            )
            return False

        cmd = GIT_COMMANDS["commit"] + [message]
        retry_result = self._run_git_command(cmd)
        if retry_result.returncode == 0:
            self.console.print(
                f"[green]✅[/ green] Committed after re-staging: {message}"
            )
            return True

        self.console.print(
            f"[red]❌[/ red] Commit failed on retry: {retry_result.stderr}"
        )
        return False

    def _handle_hook_error(
        self, result: subprocess.CompletedProcess[str] | FailedGitResult
    ) -> bool:
        if "pre-commit" in result.stderr or "hook" in result.stderr.lower():
            self.console.print("[red]❌[/ red] Commit blocked by pre-commit hooks")
            if result.stderr.strip():
                self.console.print(
                    f"[yellow]Hook output: [/ yellow]\n{result.stderr.strip()}"
                )
        else:
            self.console.print(f"[red]❌[/ red] Commit failed: {result.stderr}")
        return False

    def push(self) -> bool:
        try:
            # Get detailed push information
            result = self._run_git_command(GIT_COMMANDS["push_porcelain"])
            if result.returncode == 0:
                self._display_push_success(result.stdout)
                return True
            self.console.print(f"[red]❌[/ red] Push failed: {result.stderr}")
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error pushing: {e}")
            return False

    def _display_push_success(self, push_output: str) -> None:
        """Display detailed push success information."""
        lines = push_output.strip().split("\n") if push_output.strip() else []

        if not lines:
            self._display_no_commits_message()
            return

        pushed_refs = self._parse_pushed_refs(lines)
        self._display_push_results(pushed_refs)

    def _display_no_commits_message(self) -> None:
        """Display message for no new commits."""
        self.console.print("[green]✅[/ green] Pushed to remote (no new commits)")

    def _parse_pushed_refs(self, lines: list[str]) -> list[str]:
        """Parse pushed references from git output."""
        pushed_refs = []
        for line in lines:
            if line.startswith(("*", "+", "=")):
                # Parse porcelain output: flag:from:to summary
                parts = line.split("\t")
                if len(parts) >= 2:
                    summary = parts[1] if len(parts) > 1 else ""
                    pushed_refs.append(summary)
        return pushed_refs

    def _display_push_results(self, pushed_refs: list[str]) -> None:
        """Display the push results to console."""
        if pushed_refs:
            self.console.print(
                f"[green]✅[/ green] Successfully pushed {len(pushed_refs)} ref(s) to remote:"
            )
            for ref in pushed_refs:
                self.console.print(f"  [dim]→ {ref}[/ dim]")
        else:
            # Get commit count as fallback
            self._display_commit_count_push()

    def _display_commit_count_push(self) -> None:
        """Fallback method to show commit count information."""
        try:
            # Get commits ahead of remote
            result = self._run_git_command(GIT_COMMANDS["commits_ahead"])
            if result.returncode == 0 and result.stdout.strip().isdigit():
                commit_count = int(result.stdout.strip())
                if commit_count > 0:
                    self.console.print(
                        f"[green]✅[/ green] Pushed {commit_count} commit(s) to remote"
                    )
                else:
                    self.console.print(
                        "[green]✅[/ green] Pushed to remote (up to date)"
                    )
            else:
                # Even more basic fallback
                self.console.print("[green]✅[/ green] Successfully pushed to remote")
        except (ValueError, Exception):
            self.console.print("[green]✅[/ green] Successfully pushed to remote")

    def get_current_branch(self) -> str | None:
        try:
            result = self._run_git_command(GIT_COMMANDS["current_branch"])
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            return None

    def get_commit_message_suggestions(self, changed_files: list[str]) -> list[str]:
        if not changed_files:
            return ["Update project files"]
        file_categories = self._categorize_files(changed_files)
        messages = self._generate_category_messages(file_categories)
        messages.extend(self._generate_specific_messages(changed_files))

        return messages[:5]

    def _categorize_files(self, files: list[str]) -> set[str]:
        categories = {
            "docs": ["README", "CLAUDE", "docs /", ".md"],
            "tests": ["test_", "tests /", "conftest.py"],
            "config": ["pyproject.toml", ".yaml", ".yml", ".json", ".gitignore"],
            "ci": [".github /", "ci /", ".pre-commit"],
            "deps": ["requirements", "uv.lock", "Pipfile"],
        }
        file_categories: set[str] = set()
        for file in files:
            category = self._get_file_category(file, categories)
            file_categories.add(category)

        return file_categories

    def _get_file_category(self, file: str, categories: dict[str, list[str]]) -> str:
        for category, patterns in categories.items():
            if any(pattern in file for pattern in patterns):
                return category
        return "core"

    def _generate_category_messages(self, file_categories: set[str]) -> list[str]:
        if len(file_categories) == 1:
            return self._generate_single_category_message(next(iter(file_categories)))
        return [f"Update {', '.join(sorted(file_categories))}"]

    def _generate_single_category_message(self, category: str) -> list[str]:
        category_messages = {
            "docs": "Update documentation",
            "tests": "Update tests",
            "config": "Update configuration",
            "ci": "Update CI / CD configuration",
            "deps": "Update dependencies",
        }
        return [category_messages.get(category, "Update core functionality")]

    def _generate_specific_messages(self, files: list[str]) -> list[str]:
        messages: list[str] = []
        if "pyproject.toml" in files:
            messages.append("Update project configuration")
        if any("test_" in f for f in files):
            messages.append("Improve test coverage")
        if "README.md" in files:
            messages.append("Update README documentation")

        return messages

    def get_unpushed_commit_count(self) -> int:
        """Get the number of unpushed commits."""
        from contextlib import suppress

        with suppress(ValueError, Exception):
            result = self._run_git_command(GIT_COMMANDS["commits_ahead"])
            if result.returncode == 0 and result.stdout.strip().isdigit():
                return int(result.stdout.strip())
        return 0
