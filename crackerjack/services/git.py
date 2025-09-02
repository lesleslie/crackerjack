import subprocess
from pathlib import Path

from rich.console import Console


class GitService:
    def __init__(self, console: Console, pkg_path: Path | None = None) -> None:
        self.console = console
        self.pkg_path = pkg_path or Path.cwd()

    def _run_git_command(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        cmd = ["git", *args]
        return subprocess.run(
            cmd,
            check=False,
            cwd=self.pkg_path,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def is_git_repo(self) -> bool:
        try:
            result = self._run_git_command(["rev-parse", "--git-dir"])
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            return False

    def get_changed_files(self) -> list[str]:
        try:
            # Get staged files excluding deletions
            staged_result = self._run_git_command(
                ["diff", "--cached", "--name-only", "--diff-filter=ACMRT"]
            )
            staged_files = (
                staged_result.stdout.strip().split("\n")
                if staged_result.stdout.strip()
                else []
            )

            # Get unstaged files excluding deletions
            unstaged_result = self._run_git_command(
                ["diff", "--name-only", "--diff-filter=ACMRT"]
            )
            unstaged_files = (
                unstaged_result.stdout.strip().split("\n")
                if unstaged_result.stdout.strip()
                else []
            )

            # Get untracked files
            untracked_result = self._run_git_command(
                ["ls-files", "--others", "--exclude-standard"],
            )
            untracked_files = (
                untracked_result.stdout.strip().split("\n")
                if untracked_result.stdout.strip()
                else []
            )

            all_files = set(staged_files + unstaged_files + untracked_files)
            return [f for f in all_files if f]
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Error getting changed files: {e}")
            return []

    def get_staged_files(self) -> list[str]:
        try:
            result = self._run_git_command(["diff", "--cached", "--name-only"])
            return result.stdout.strip().split("\n") if result.stdout.strip() else []
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Error getting staged files: {e}")
            return []

    def add_files(self, files: list[str]) -> bool:
        try:
            for file in files:
                result = self._run_git_command(["add", file])
                if result.returncode != 0:
                    self.console.print(
                        f"[red]❌[/red] Failed to add {file}: {result.stderr}",
                    )
                    return False
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/red] Error adding files: {e}")
            return False

    def commit(self, message: str) -> bool:
        try:
            result = self._run_git_command(["commit", "-m", message])
            if result.returncode == 0:
                self.console.print(f"[green]✅[/green] Committed: {message}")
                return True

            return self._handle_commit_failure(result, message)
        except Exception as e:
            self.console.print(f"[red]❌[/red] Error committing: {e}")
            return False

    def _handle_commit_failure(
        self, result: subprocess.CompletedProcess[str], message: str
    ) -> bool:
        # Check if pre-commit hooks modified files and need re-staging
        if "files were modified by this hook" in result.stderr:
            return self._retry_commit_after_restage(message)

        return self._handle_hook_error(result)

    def _retry_commit_after_restage(self, message: str) -> bool:
        self.console.print(
            "[yellow]🔄[/yellow] Pre-commit hooks modified files - attempting to re-stage and retry commit"
        )

        # Re-stage all modified files
        add_result = self._run_git_command(["add", "-u"])
        if add_result.returncode != 0:
            self.console.print(
                f"[red]❌[/red] Failed to re-stage files: {add_result.stderr}"
            )
            return False

        # Retry the commit
        retry_result = self._run_git_command(["commit", "-m", message])
        if retry_result.returncode == 0:
            self.console.print(
                f"[green]✅[/green] Committed after re-staging: {message}"
            )
            return True

        self.console.print(
            f"[red]❌[/red] Commit failed on retry: {retry_result.stderr}"
        )
        return False

    def _handle_hook_error(self, result: subprocess.CompletedProcess[str]) -> bool:
        # When git commit fails due to pre-commit hooks, stderr contains hook output
        if "pre-commit" in result.stderr or "hook" in result.stderr.lower():
            self.console.print("[red]❌[/red] Commit blocked by pre-commit hooks")
            if result.stderr.strip():
                self.console.print(
                    f"[yellow]Hook output:[/yellow]\n{result.stderr.strip()}"
                )
        else:
            self.console.print(f"[red]❌[/red] Commit failed: {result.stderr}")
        return False

    def push(self) -> bool:
        try:
            result = self._run_git_command(["push"])
            if result.returncode == 0:
                self.console.print("[green]✅[/green] Pushed to remote")
                return True
            self.console.print(f"[red]❌[/red] Push failed: {result.stderr}")
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/red] Error pushing: {e}")
            return False

    def get_current_branch(self) -> str | None:
        try:
            result = self._run_git_command(["branch", "--show-current"])
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            return None

    def get_commit_message_suggestions(self, files: list[str]) -> list[str]:
        if not files:
            return ["Update project files"]
        file_categories = self._categorize_files(files)
        messages = self._generate_category_messages(file_categories)
        messages.extend(self._generate_specific_messages(files))

        return messages[:5]

    def _categorize_files(self, files: list[str]) -> set[str]:
        categories = {
            "docs": ["README", "CLAUDE", "docs/", ".md"],
            "tests": ["test_", "tests/", "conftest.py"],
            "config": ["pyproject.toml", ".yaml", ".yml", ".json", ".gitignore"],
            "ci": [".github/", "ci/", ".pre-commit"],
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
            "ci": "Update CI/CD configuration",
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
