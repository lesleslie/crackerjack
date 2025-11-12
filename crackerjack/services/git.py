import subprocess  # nosec B404
import typing as t
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.models.protocols import GitInterface

from .secure_subprocess import execute_secure_subprocess
from .security_logger import get_security_logger

GIT_COMMANDS = {
    "git_dir": ["rev-parse", "--git-dir"],
    "staged_files": ["diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
    "unstaged_files": ["diff", "--name-only", "--diff-filter=ACMRT"],
    "untracked_files": ["ls-files", "--others", "--exclude-standard"],
    "staged_files_simple": ["diff", "--cached", "--name-only"],
    "add_file": ["add"],
    "add_all": ["add", "-A", "."],
    "commit": ["commit", "-m"],
    "add_updated": ["add", "-u"],
    "push_porcelain": ["push", "--porcelain"],
    "push_with_tags": ["push", "--porcelain", "--follow-tags"],
    "current_branch": ["branch", "--show-current"],
    "commits_ahead": ["rev-list", "--count", "@{u}..HEAD"],
}


class FailedGitResult:
    def __init__(self, command: list[str], error: str) -> None:
        self.args = command
        self.returncode = -1
        self.stdout = ""
        self.stderr = f"Git security validation failed: {error}"


class GitService(GitInterface):
    @depends.inject
    def __init__(self, console: Inject[Console], pkg_path: Path | None = None) -> None:
        self.console = console
        self.pkg_path = pkg_path or Path.cwd()

    def _run_git_command(
        self, args: list[str]
    ) -> subprocess.CompletedProcess[str] | FailedGitResult:
        cmd = ["git", *args]

        try:
            return execute_secure_subprocess(
                command=cmd,
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except Exception as e:
            security_logger = get_security_logger()
            security_logger.log_subprocess_failure(
                command=cmd,
                exit_code=-1,
                error_output=str(e),
            )

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

            all_files = set[t.Any](staged_files + unstaged_files + untracked_files)
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
            "[yellow]🔄[/yellow] Pre-commit hooks modified files - attempting to re-stage and retry commit"
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
            result = self._run_git_command(GIT_COMMANDS["push_porcelain"])
            if result.returncode == 0:
                self._display_push_success(result.stdout)
                return True
            self.console.print(f"[red]❌[/ red] Push failed: {result.stderr}")
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error pushing: {e}")
            return False

    def push_with_tags(self) -> bool:
        """Push commits and any tags to remote using --follow-tags."""
        try:
            result = self._run_git_command(GIT_COMMANDS["push_with_tags"])
            if result.returncode == 0:
                self._display_push_success(result.stdout)
                return True
            self.console.print(f"[red]❌[/ red] Push failed: {result.stderr}")
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error pushing: {e}")
            return False

    def _display_push_success(self, push_output: str) -> None:
        lines = push_output.strip().split("\n") if push_output.strip() else []

        if not lines:
            self._display_no_commits_message()
            return

        pushed_refs = self._parse_pushed_refs(lines)
        self._display_push_results(pushed_refs)

    def _display_no_commits_message(self) -> None:
        self.console.print("[green]✅[/ green] Pushed to remote (no new commits)")

    def _parse_pushed_refs(self, lines: list[str]) -> list[str]:
        pushed_refs = []
        for line in lines:
            if line.startswith(("*", "+", "=")):
                parts = line.split("\t")
                if len(parts) >= 2:
                    summary = parts[1] if len(parts) > 1 else ""
                    pushed_refs.append(summary)
        return pushed_refs

    def _display_push_results(self, pushed_refs: list[str]) -> None:
        if pushed_refs:
            self.console.print(
                f"[green]✅[/ green] Successfully pushed {len(pushed_refs)} ref(s) to remote: "
            )
            for ref in pushed_refs:
                self.console.print(f" [dim]→ {ref}[/ dim]")
        else:
            self._display_commit_count_push()

    def _display_commit_count_push(self) -> None:
        try:
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
        from contextlib import suppress

        with suppress(ValueError, Exception):
            result = self._run_git_command(GIT_COMMANDS["commits_ahead"])
            if result.returncode == 0 and result.stdout.strip().isdigit():
                return int(result.stdout.strip())
        return 0

    def get_changed_files_by_extension(
        self,
        extensions: list[str],
        include_staged: bool = True,
        include_unstaged: bool = True,
    ) -> list[Path]:
        """Get changed files filtered by file extensions.

        Args:
            extensions: List of extensions to filter by (e.g., [".py", ".md"])
            include_staged: Include staged files in results
            include_unstaged: Include unstaged files in results

        Returns:
            List of Path objects for changed files matching the extensions

        Example:
            >>> git_service.get_changed_files_by_extension([".py"])
            [Path("crackerjack/services/git.py"), Path("tests/test_git.py")]
        """
        try:
            all_changed: set[str] = set()

            if include_staged:
                staged_result = self._run_git_command(GIT_COMMANDS["staged_files"])
                if staged_result.stdout.strip():
                    all_changed.update(staged_result.stdout.strip().split("\n"))

            if include_unstaged:
                unstaged_result = self._run_git_command(GIT_COMMANDS["unstaged_files"])
                if unstaged_result.stdout.strip():
                    all_changed.update(unstaged_result.stdout.strip().split("\n"))

            # Filter by extensions
            filtered = [
                self.pkg_path / f
                for f in all_changed
                if f and any(f.endswith(ext) for ext in extensions)
            ]

            # Only return files that actually exist
            return [f for f in filtered if f.exists()]

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/yellow] Error getting changed files by extension: {e}"
            )
            return []

    def get_current_commit_hash(self) -> str | None:
        """Get the hash of the current commit (HEAD)."""
        try:
            result = self._run_git_command(["rev-parse", "HEAD"])
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception:
            self.console.print("[red]❌[/red] Error getting current commit hash")
            return None

    def reset_hard(self, commit_hash: str) -> bool:
        """Reset the repository to a specific commit hash (hard reset)."""
        try:
            result = self._run_git_command(["reset", "--hard", commit_hash])
            if result.returncode == 0:
                self.console.print(
                    f"[green]✅[/green] Repository reset to {commit_hash[:8]}"
                )
                return True
            else:
                self.console.print(f"[red]❌[/red] Reset failed: {result.stderr}")
                return False
        except Exception as e:
            self.console.print(f"[red]❌[/red] Error during reset: {e}")
            return False
