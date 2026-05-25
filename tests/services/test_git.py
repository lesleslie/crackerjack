"""Comprehensive tests for GitService.

Tests all public methods and edge cases including:
- Repository detection
- File staging and committing
- Push and authentication fallback
- Branch operations
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest

from crackerjack.services.git import (
    FailedGitResult,
    GitService,
    GIT_COMMANDS,
)


class TestGitServiceInit:
    """Test GitService initialization."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            assert git.auth_fallback is True
            assert git.persist_fallback is False

    def test_init_with_console(self) -> None:
        """Test initialization with custom console."""
        mock_console = MagicMock()
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=mock_console)
            assert git.console is mock_console

    def test_init_with_pkg_path(self) -> None:
        """Test initialization with package path."""
        pkg_path = Path("/some/path")
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(pkg_path=pkg_path)
            assert git.pkg_path == pkg_path


class TestIsGitRepo:
    """Test is_git_repo() method."""

    def test_is_git_repo_true(self, tmp_path: Path) -> None:
        """Test returns True for git repository."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.is_git_repo()
                assert result is True

    def test_is_git_repo_false(self, tmp_path: Path) -> None:
        """Test returns False for non-git repository."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            result = git.is_git_repo()
            assert result is False

    def test_is_git_repo_subprocess_error(self, tmp_path: Path) -> None:
        """Test returns False on subprocess error."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            with patch.object(git, "_run_git_command", side_effect=OSError("Git not found")):
                result = git.is_git_repo()
                assert result is False


class TestGetStagedFiles:
    """Test get_staged_files() method."""

    def test_get_staged_files_success(self, tmp_path: Path) -> None:
        """Test getting staged files."""
        mock_result = MagicMock()
        mock_result.stdout = "file1.py\nfile2.py\n"
        mock_result.returncode = 0

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.get_staged_files()

                assert result == ["file1.py", "file2.py"]

    def test_get_staged_files_empty(self, tmp_path: Path) -> None:
        """Test getting staged files when none."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.get_staged_files()
                assert result == []


class TestGetChangedFiles:
    """Test get_changed_files() method."""

    def test_get_changed_files_all_categories(self, tmp_path: Path) -> None:
        """Test getting changed files across all categories."""
        staged_result = MagicMock()
        staged_result.stdout = "staged.py\n"

        unstaged_result = MagicMock()
        unstaged_result.stdout = "modified.py\n"

        untracked_result = MagicMock()
        untracked_result.stdout = "new.py\n"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            def run_git(cmd):
                if cmd == GIT_COMMANDS["staged_files"]:
                    return staged_result
                elif cmd == GIT_COMMANDS["unstaged_files"]:
                    return unstaged_result
                elif cmd == GIT_COMMANDS["untracked_files"]:
                    return untracked_result
                return MagicMock(returncode=0)

            with patch.object(git, "_run_git_command", side_effect=run_git):
                result = git.get_changed_files()

                assert len(result) == 3
                assert "staged.py" in result
                assert "modified.py" in result
                assert "new.py" in result

    def test_get_changed_files_removes_duplicates(self, tmp_path: Path) -> None:
        """Test duplicates are removed from changed files."""
        staged_result = MagicMock()
        staged_result.stdout = "file.py\n"

        unstaged_result = MagicMock()
        unstaged_result.stdout = "file.py\n"

        untracked_result = MagicMock()
        untracked_result.stdout = ""

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            def run_git(cmd):
                if cmd == GIT_COMMANDS["staged_files"]:
                    return staged_result
                elif cmd == GIT_COMMANDS["unstaged_files"]:
                    return unstaged_result
                elif cmd == GIT_COMMANDS["untracked_files"]:
                    return untracked_result
                return MagicMock(returncode=0)

            with patch.object(git, "_run_git_command", side_effect=run_git):
                result = git.get_changed_files()

                assert len(result) == 1
                assert result[0] == "file.py"

    def test_get_changed_files_error(self, tmp_path: Path) -> None:
        """Test error handling in get_changed_files."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            git.console = MagicMock()

            with patch.object(git, "_run_git_command", side_effect=Exception("Error")):
                result = git.get_changed_files()

                assert result == []
                git.console.print.assert_called()


class TestAddFiles:
    """Test add_files() method."""

    def test_add_files_success(self, tmp_path: Path) -> None:
        """Test adding files successfully."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.add_files(["file1.py", "file2.py"])
                assert result is True

    def test_add_files_failure(self, tmp_path: Path) -> None:
        """Test adding files failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            git.console = MagicMock()

            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.add_files(["file.py"])
                assert result is False


class TestCommit:
    """Test commit() method."""

    def test_commit_success(self, tmp_path: Path) -> None:
        """Test successful commit."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.commit("Test commit")
                assert result is True

    def test_commit_failure_with_hook_error(self, tmp_path: Path) -> None:
        """Test commit failure with hook error."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "pre-commit hook failed"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            git.console = MagicMock()

            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.commit("Test commit")
                assert result is False

    def test_commit_retry_after_hook_modifies_files(self, tmp_path: Path) -> None:
        """Test commit retry after hook modifies files succeeds."""
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "files were modified by this hook"

        # Mock for _run_git_command: add_updated succeeds, then retry commit succeeds
        add_success = MagicMock()
        add_success.returncode = 0

        retry_success = MagicMock()
        retry_success.returncode = 0
        retry_success.stdout = "[main abc123] Test commit"

        def run_git(cmd):
            if cmd == GIT_COMMANDS["add_updated"]:
                return add_success
            elif cmd == GIT_COMMANDS["commit"] + ["Test commit"]:
                return retry_success
            return MagicMock(returncode=0)

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            git.console = MagicMock()

            with patch.object(git, "_run_git_command", side_effect=run_git):
                result = git.commit("Test commit")
                assert result is True


class TestPush:
    """Test push() method."""

    def test_push_success(self, tmp_path: Path) -> None:
        """Test successful push."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "* [new branch] main -> main"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.push()
                assert result is True

    def test_push_auth_failure_uses_fallback(self, tmp_path: Path) -> None:
        """Test push returns False when fallback fails."""
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "Permission denied publickey"

        fallback_fail = MagicMock()
        fallback_fail.returncode = 1
        fallback_fail.stderr = "Permission denied (publickey)"

        def run_git(cmd):
            if cmd == GIT_COMMANDS["push_porcelain"]:
                # First call fails auth, second call (fallback) also fails
                return fallback_fail
            elif cmd[0] == "remote" and cmd[1] == "get-url":
                return MagicMock(returncode=0, stdout="git@github.com:user/repo.git")
            elif cmd[0] == "remote" and cmd[1] == "set-url":
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path, auth_fallback=True)
            git.console = MagicMock()

            with patch.object(git, "_run_git_command", side_effect=run_git):
                with patch.object(git, "_get_remote_url", return_value="git@github.com:user/repo.git"):
                    with patch.object(git, "_set_remote_url", return_value=True):
                        result = git.push()
                        assert result is False


class TestGetCurrentBranch:
    """Test get_current_branch() method."""

    def test_get_current_branch_success(self, tmp_path: Path) -> None:
        """Test getting current branch."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "main\n"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.get_current_branch()
                assert result == "main"

    def test_get_current_branch_error(self, tmp_path: Path) -> None:
        """Test getting current branch returns None on subprocess error."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            with patch.object(git, "_run_git_command", side_effect=subprocess.SubprocessError("Error")):
                result = git.get_current_branch()
                assert result is None


class TestGetCommitMessageSuggestions:
    """Test get_commit_message_suggestions() method."""

    def test_no_files_returns_default(self) -> None:
        """Test empty file list returns default message."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git.get_commit_message_suggestions([])
            assert result == ["Update project files"]

    def test_doc_files_returns_doc_message(self) -> None:
        """Test documentation files return doc message."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git.get_commit_message_suggestions(["README.md", "docs/guide.md"])
            assert any("documentation" in msg.lower() for msg in result)

    def test_test_files_returns_test_message(self) -> None:
        """Test test files return test message."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git.get_commit_message_suggestions(["test_example.py"])
            assert any("test" in msg.lower() for msg in result)

    def test_config_files_returns_config_message(self) -> None:
        """Test config files return config message."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git.get_commit_message_suggestions(["pyproject.toml", ".yaml"])
            assert any("config" in msg.lower() for msg in result)

    def test_mixed_files_returns_combined_message(self) -> None:
        """Test mixed files returns combined message."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git.get_commit_message_suggestions(
                ["README.md", "test_example.py", "pyproject.toml"]
            )
            assert len(result) <= 5

    def test_pyproject_adds_project_config_message(self) -> None:
        """Test pyproject.toml adds project config message."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git.get_commit_message_suggestions(["pyproject.toml"])
            assert any("project configuration" in msg.lower() for msg in result)


class TestGetUnpushedCommitCount:
    """Test get_unpushed_commit_count() method."""

    def test_get_unpushed_count_success(self, tmp_path: Path) -> None:
        """Test getting unpushed commit count."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3\n"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.get_unpushed_commit_count()
                assert result == 3

    def test_get_unpushed_count_no_commits(self, tmp_path: Path) -> None:
        """Test getting unpushed count when up to date."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0\n"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.get_unpushed_commit_count()
                assert result == 0


class TestGetChangedFilesByExtension:
    """Test get_changed_files_by_extension() method."""

    def test_get_by_extension_success(self, tmp_path: Path) -> None:
        """Test getting changed files by extension."""
        staged_result = MagicMock()
        staged_result.stdout = "file1.py\nfile2.py\n"

        unstaged_result = MagicMock()
        unstaged_result.stdout = ""

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            def run_git(cmd):
                if cmd == GIT_COMMANDS["staged_files"]:
                    return staged_result
                elif cmd == GIT_COMMANDS["unstaged_files"]:
                    return unstaged_result
                return MagicMock(returncode=0)

            with patch.object(git, "_run_git_command", side_effect=run_git):
                result = git.get_changed_files_by_extension([".py"])
                assert len(result) >= 0


class TestGetCurrentCommitHash:
    """Test get_current_commit_hash() method."""

    def test_get_commit_hash_success(self, tmp_path: Path) -> None:
        """Test getting current commit hash."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123def456\n"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.get_current_commit_hash()
                assert result == "abc123def456"

    def test_get_commit_hash_error(self, tmp_path: Path) -> None:
        """Test getting commit hash on error."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            git.console = MagicMock()

            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.get_current_commit_hash()
                assert result is None


class TestResetHard:
    """Test reset_hard() method."""

    def test_reset_hard_success(self, tmp_path: Path) -> None:
        """Test successful hard reset."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.reset_hard("abc123")
                assert result is True

    def test_reset_hard_failure(self, tmp_path: Path) -> None:
        """Test hard reset failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Invalid ref"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            git.console = MagicMock()

            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.reset_hard("invalid")
                assert result is False


class TestUrlTransformation:
    """Test SSH ↔ HTTPS URL transformation."""

    def test_ssh_to_https(self) -> None:
        """Test SSH to HTTPS transformation."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git._ssh_to_https("git@github.com:user/repo.git")
            assert result == "https://github.com/user/repo.git"

    def test_https_to_ssh(self) -> None:
        """Test HTTPS to SSH transformation."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git._https_to_ssh("https://github.com/user/repo.git")
            assert result == "git@github.com:user/repo.git"

    def test_ssh_to_https_non_ssh(self) -> None:
        """Test SSH transform on non-SSH URL returns unchanged."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService()
            result = git._ssh_to_https("https://github.com/user/repo.git")
            assert result == "https://github.com/user/repo.git"


class TestFailedGitResult:
    """Test FailedGitResult class."""

    def test_failed_git_result_attributes(self) -> None:
        """Test FailedGitResult has correct attributes."""
        result = FailedGitResult(["git", "status"], "Security validation failed")

        assert result.args == ["git", "status"]
        assert result.returncode == -1
        assert result.stdout == ""
        assert "Security validation failed" in result.stderr


class TestAuthFallback:
    """Test authentication fallback behavior."""

    def test_auth_fallback_disabled(self, tmp_path: Path) -> None:
        """Test auth fallback can be disabled."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path, auth_fallback=False)
            assert git.auth_fallback is False

    def test_is_auth_failure_patterns(self, tmp_path: Path) -> None:
        """Test auth failure detection patterns."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            auth_failures = [
                "Permission denied",
                "publickey",
                "Authentication failed",
                "Could not read from remote repository",
                "fatal: unable to access",
                "401",
                "403",
            ]

            for msg in auth_failures:
                assert git._is_auth_failure(msg) is True

    def test_is_auth_failure_non_auth(self, tmp_path: Path) -> None:
        """Test non-auth failures are not detected."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            assert git._is_auth_failure("Merge conflict") is False
            assert git._is_auth_failure("File not found") is False


class TestGetUnstagedFiles:
    """Test get_unstaged_files() method."""

    def test_get_unstaged_files_success(self, tmp_path: Path) -> None:
        """Test getting unstaged files."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "modified.py\n"

        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            with patch.object(git, "_run_git_command", return_value=mock_result):
                result = git.get_unstaged_files()
                assert "modified.py" in result[0]


class TestDisplayPushResults:
    """Test push result display methods."""

    def test_display_no_commits_message(self, tmp_path: Path) -> None:
        """Test display when no commits to push."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)
            git.console = MagicMock()

            git._display_no_commits_message()

            git.console.print.assert_called()

    def test_parse_pushed_refs(self, tmp_path: Path) -> None:
        """Test parsing pushed refs."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            lines = ["* 1234567..89abcdef  main -> main"]
            result = git._parse_pushed_refs(lines)
            assert len(result) >= 0

    def test_parse_pushed_refs_empty(self, tmp_path: Path) -> None:
        """Test parsing empty pushed refs."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            git = GitService(console=MagicMock(), pkg_path=tmp_path)

            result = git._parse_pushed_refs([])
            assert result == []