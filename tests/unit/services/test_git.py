"""Unit tests for GitService.

Tests git operations including repository detection, file staging,
commits, pushes, and branch operations.
"""

import signal
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.services.git import FailedGitResult, GitService


@pytest.mark.unit
class TestGitServiceInitialization:
    """Test GitService initialization."""

    def test_initialization_with_default_path(self) -> None:
        """Test GitService initializes with current working directory."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            service = GitService(console=Mock(), pkg_path=None)

            assert service.pkg_path == Path.cwd()

    def test_initialization_with_custom_path(self, tmp_path) -> None:
        """Test GitService initializes with custom path."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            service = GitService(console=Mock(), pkg_path=tmp_path)

            assert service.pkg_path == tmp_path


@pytest.mark.unit
class TestGitServiceRepositoryDetection:
    """Test git repository detection."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_is_git_repo_true(self, mock_execute, service) -> None:
        """Test is_git_repo returns True for valid git repository."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=["git", "rev-parse", "--git-dir"],
            returncode=0,
            stdout=".git\n",
            stderr="",
        )

        assert service.is_git_repo() is True

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_is_git_repo_false(self, mock_execute, service) -> None:
        """Test is_git_repo returns False for non-git directory."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=["git", "rev-parse", "--git-dir"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )

        assert service.is_git_repo() is False

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_is_git_repo_handles_exception(self, mock_execute, service) -> None:
        """Test is_git_repo handles exceptions gracefully."""
        mock_execute.side_effect = FileNotFoundError("git not found")

        assert service.is_git_repo() is False


@pytest.mark.unit
class TestGitServiceFileOperations:
    """Test git file operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_changed_files(self, mock_execute, service) -> None:
        """Test getting all changed files."""
        # Mock staged files
        mock_execute.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file1.py\nfile2.py\n", stderr="",
            ),
            # Mock unstaged files
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file3.py\n", stderr="",
            ),
            # Mock untracked files
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file4.py\n", stderr="",
            ),
        ]

        files = service.get_changed_files()

        assert len(files) == 4
        assert "file1.py" in files
        assert "file2.py" in files
        assert "file3.py" in files
        assert "file4.py" in files

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_changed_files_empty(self, mock_execute, service) -> None:
        """Test getting changed files when none exist."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

        files = service.get_changed_files()

        assert files == []

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_staged_files(self, mock_execute, service) -> None:
        """Test getting staged files."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="staged1.py\nstaged2.py\n", stderr="",
        )

        files = service.get_staged_files()

        assert len(files) == 2
        assert "staged1.py" in files
        assert "staged2.py" in files

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_add_files_success(self, mock_execute, service) -> None:
        """Test successfully adding files."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

        result = service.add_files(["file1.py", "file2.py"])

        assert result is True
        assert mock_execute.call_count == 2

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_add_files_failure(self, mock_execute, service) -> None:
        """Test handling of git add failure."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal: pathspec 'file.py' did not match any files",
        )

        result = service.add_files(["file.py"])

        assert result is False

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_add_all_files_success(self, mock_execute, service) -> None:
        """Test successfully adding all files."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

        result = service.add_all_files()

        assert result is True

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_add_all_files_failure(self, mock_execute, service) -> None:
        """Test handling of add all failure."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error",
        )

        result = service.add_all_files()

        assert result is False


@pytest.mark.unit
class TestGitServiceCommit:
    """Test git commit operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_commit_success(self, mock_execute, service) -> None:
        """Test successful commit."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="[main abc123] Test commit", stderr="",
        )

        result = service.commit("Test commit")

        assert result is True

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_commit_hook_modification(self, mock_execute, service) -> None:
        """Test commit with hook modification and retry."""
        # First commit fails due to hook modification
        mock_execute.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="files were modified by this hook",
            ),
            # Re-add files
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr="",
            ),
            # Retry commit succeeds
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="[main abc123] Test commit", stderr="",
            ),
        ]

        result = service.commit("Test commit")

        assert result is True
        assert mock_execute.call_count == 3

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_commit_hook_blocked(self, mock_execute, service) -> None:
        """Test commit blocked by hooks."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="pre-commit hook failed",
        )

        result = service.commit("Test commit")

        assert result is False

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_commit_generic_failure(self, mock_execute, service) -> None:
        """Test commit with generic failure."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="error: failed to commit",
        )

        result = service.commit("Test commit")

        assert result is False


@pytest.mark.unit
class TestGitServicePush:
    """Test git push operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_success(self, mock_execute, service) -> None:
        """Test successful push."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="* refs/heads/main:refs/heads/main [new branch]\n",
            stderr="",
        )

        result = service.push()

        assert result is True

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_failure(self, mock_execute, service) -> None:
        """Test failed push."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="error: failed to push some refs",
        )

        result = service.push()

        assert result is False

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_with_tags_success(self, mock_execute, service) -> None:
        """Test successful push with tags."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="* refs/heads/main:refs/heads/main\n* refs/tags/v1.0.0:refs/tags/v1.0.0\n",
            stderr="",
        )

        result = service.push_with_tags()

        assert result is True

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_no_new_commits(self, mock_execute, service) -> None:
        """Test push with no new commits."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

        result = service.push()

        assert result is True

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_failure_non_auth(self, mock_execute) -> None:
        """Test failed push with non-auth error (should not trigger fallback)."""
        service = GitService(console=Mock(), pkg_path=Path("/tmp"), auth_fallback=True)
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="error: failed to push some refs",
        )

        result = service.push()

        assert result is False

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_ssh_fallback_to_https_success(self, mock_execute) -> None:
        """Test SSH auth failure falls back to HTTPS successfully."""
        service = GitService(console=Mock(), pkg_path=Path("/tmp"), auth_fallback=True)

        # Mock sequence: push fails (auth), get-url (SSH), set-url, push succeeds,
        # commits_ahead (for display), set-url back
        mock_execute.side_effect = [
            # First push attempt - fails with auth error
            subprocess.CompletedProcess(
                args=[], returncode=128, stdout="",
                stderr="Permission denied (publickey)",
            ),
            # Get remote URL (SSH)
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="git@gitlab.com:user/repo.git", stderr="",
            ),
            # Set remote URL to HTTPS
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            # Second push attempt - succeeds
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="* refs/heads/main:refs/heads/main\n", stderr="",
            ),
            # Get unpushed commit count (called by _display_commit_count_push)
            subprocess.CompletedProcess(args=[], returncode=0, stdout="0\n", stderr=""),
            # Set remote URL back to SSH
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]

        result = service.push()

        assert result is True
        assert mock_execute.call_count == 6

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_https_fallback_to_ssh_success(self, mock_execute) -> None:
        """Test HTTPS auth failure falls back to SSH successfully."""
        service = GitService(console=Mock(), pkg_path=Path("/tmp"), auth_fallback=True)

        mock_execute.side_effect = [
            # First push attempt - fails with auth error
            subprocess.CompletedProcess(
                args=[], returncode=128, stdout="",
                stderr="fatal: Authentication failed for https://gitlab.com/",
            ),
            # Get remote URL (HTTPS)
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="https://gitlab.com/user/repo.git", stderr="",
            ),
            # Set remote URL to SSH
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            # Second push attempt - succeeds
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="* refs/heads/main:refs/heads/main\n", stderr="",
            ),
            # Get unpushed commit count (called by _display_commit_count_push)
            subprocess.CompletedProcess(args=[], returncode=0, stdout="0\n", stderr=""),
            # Set remote URL back to HTTPS
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]

        result = service.push()

        assert result is True
        assert mock_execute.call_count == 6

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_fallback_disabled(self, mock_execute) -> None:
        """Test that fallback is skipped when auth_fallback=False."""
        service = GitService(console=Mock(), pkg_path=Path("/tmp"), auth_fallback=False)

        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="",
            stderr="Permission denied (publickey)",
        )

        result = service.push()

        assert result is False
        # Should only be called once (no fallback attempts)
        assert mock_execute.call_count == 1

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_push_fallback_persist_enabled(self, mock_execute) -> None:
        """Test that successful fallback is persisted when persist_fallback=True."""
        service = GitService(
            console=Mock(), pkg_path=Path("/tmp"),
            auth_fallback=True, persist_fallback=True,
        )

        mock_execute.side_effect = [
            # First push attempt - fails with auth error
            subprocess.CompletedProcess(
                args=[], returncode=128, stdout="",
                stderr="Permission denied (publickey)",
            ),
            # Get remote URL (SSH)
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="git@gitlab.com:user/repo.git", stderr="",
            ),
            # Set remote URL to HTTPS
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            # Second push attempt - succeeds
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="* refs/heads/main:refs/heads/main\n", stderr="",
            ),
            # Get unpushed commit count (called by _display_commit_count_push)
            subprocess.CompletedProcess(args=[], returncode=0, stdout="0\n", stderr=""),
            # Note: No set-url back when persist_fallback=True
        ]

        result = service.push()

        assert result is True
        # 5 calls: push(fail), get-url, set-url, push(success), commits_ahead
        # Note: No set-url back when persist_fallback=True
        assert mock_execute.call_count == 5

    def test_ssh_to_https_conversion(self) -> None:
        """Test SSH to HTTPS URL conversion."""
        service = GitService(console=Mock(), pkg_path=Path("/tmp"))

        assert service._ssh_to_https("git@gitlab.com:user/repo.git") == "https://gitlab.com/user/repo.git"
        assert service._ssh_to_https("git@github.com:org/repo.git") == "https://github.com/org/repo.git"
        # Non-SSH URL should be returned unchanged
        assert service._ssh_to_https("https://gitlab.com/user/repo.git") == "https://gitlab.com/user/repo.git"

    def test_https_to_ssh_conversion(self) -> None:
        """Test HTTPS to SSH URL conversion."""
        service = GitService(console=Mock(), pkg_path=Path("/tmp"))

        assert service._https_to_ssh("https://gitlab.com/user/repo.git") == "git@gitlab.com:user/repo.git"
        assert service._https_to_ssh("https://github.com/org/repo.git") == "git@github.com:org/repo.git"
        # Non-HTTPS URL should be returned unchanged
        assert service._https_to_ssh("git@gitlab.com:user/repo.git") == "git@gitlab.com:user/repo.git"


@pytest.mark.unit
class TestGitServiceBranch:
    """Test git branch operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_current_branch_success(self, mock_execute, service) -> None:
        """Test getting current branch name."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="main\n", stderr="",
        )

        branch = service.get_current_branch()

        assert branch == "main"

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_current_branch_failure(self, mock_execute, service) -> None:
        """Test getting current branch when not in repo."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal: not a git repository",
        )

        branch = service.get_current_branch()

        assert branch is None

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_unpushed_commit_count(self, mock_execute, service) -> None:
        """Test getting unpushed commit count."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="3\n", stderr="",
        )

        count = service.get_unpushed_commit_count()

        assert count == 3

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_unpushed_commit_count_zero(self, mock_execute, service) -> None:
        """Test unpushed commit count when up to date."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="0\n", stderr="",
        )

        count = service.get_unpushed_commit_count()

        assert count == 0

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_unpushed_commit_count_error(self, mock_execute, service) -> None:
        """Test unpushed commit count with error."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="error",
        )

        count = service.get_unpushed_commit_count()

        assert count == 0


@pytest.mark.unit
class TestGitServiceCommitMessages:
    """Test commit message generation."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    def test_get_commit_message_suggestions_empty(self, service) -> None:
        """Test commit message suggestions with no files."""
        suggestions = service.get_commit_message_suggestions([])

        assert len(suggestions) > 0
        assert "Update project files" in suggestions

    def test_get_commit_message_suggestions_docs(self, service) -> None:
        """Test commit message suggestions for documentation files."""
        files = ["README.md", "docs/guide.md"]

        suggestions = service.get_commit_message_suggestions(files)

        assert any("documentation" in msg.lower() for msg in suggestions)

    def test_get_commit_message_suggestions_tests(self, service) -> None:
        """Test commit message suggestions for test files."""
        files = ["test_git.py", "tests/test_service.py"]

        suggestions = service.get_commit_message_suggestions(files)

        assert any("test" in msg.lower() for msg in suggestions)

    def test_get_commit_message_suggestions_config(self, service) -> None:
        """Test commit message suggestions for config files."""
        files = ["pyproject.toml", "config.yaml"]

        suggestions = service.get_commit_message_suggestions(files)

        assert any("config" in msg.lower() for msg in suggestions)

    def test_get_commit_message_suggestions_mixed(self, service) -> None:
        """Test commit message suggestions for mixed file types."""
        files = ["README.md", "test_git.py", "pyproject.toml"]

        suggestions = service.get_commit_message_suggestions(files)

        # Should return max 5 suggestions
        assert len(suggestions) <= 5

    def test_get_commit_message_suggestions_pyproject_specific(self, service) -> None:
        """Test specific message for pyproject.toml."""
        files = ["pyproject.toml"]

        suggestions = service.get_commit_message_suggestions(files)

        assert any("project configuration" in msg.lower() for msg in suggestions)


@pytest.mark.unit
class TestGitServiceFilteredFiles:
    """Test filtered file operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        # Create some test files
        (tmp_path / "file1.py").write_text("# python file")
        (tmp_path / "file2.md").write_text("# markdown file")
        (tmp_path / "file3.py").write_text("# another python file")

        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_changed_files_by_extension(self, mock_execute, service) -> None:
        """Test getting changed files filtered by extension."""
        # Mock staged and unstaged files
        mock_execute.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file1.py\nfile2.md\n", stderr="",
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file3.py\n", stderr="",
            ),
        ]

        # Get only Python files
        py_files = service.get_changed_files_by_extension([".py"])

        assert len(py_files) == 2
        assert all(str(f).endswith(".py") for f in py_files)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_changed_files_by_extension_staged_only(self, mock_execute, service) -> None:
        """Test getting only staged files by extension."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="file1.py\n", stderr="",
        )

        py_files = service.get_changed_files_by_extension(
            [".py"],
            include_staged=True,
            include_unstaged=False,
        )

        assert len(py_files) == 1
        assert mock_execute.call_count == 1

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_changed_files_by_extension_unstaged_only(self, mock_execute, service) -> None:
        """Test getting only unstaged files by extension."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="file3.py\n", stderr="",
        )

        py_files = service.get_changed_files_by_extension(
            [".py"],
            include_staged=False,
            include_unstaged=True,
        )

        assert len(py_files) == 1
        assert mock_execute.call_count == 1


@pytest.mark.unit
class TestGitServiceCommitOperations:
    """Test commit hash and reset operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_current_commit_hash(self, mock_execute, service) -> None:
        """Test getting current commit hash."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="abc123def456\n", stderr="",
        )

        commit_hash = service.get_current_commit_hash()

        assert commit_hash == "abc123def456"

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_current_commit_hash_failure(self, mock_execute, service) -> None:
        """Test getting commit hash with error."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="error",
        )

        commit_hash = service.get_current_commit_hash()

        assert commit_hash is None

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_reset_hard_success(self, mock_execute, service) -> None:
        """Test hard reset to commit."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

        result = service.reset_hard("abc123")

        assert result is True

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_reset_hard_failure(self, mock_execute, service) -> None:
        """Test hard reset failure."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error: invalid commit",
        )

        result = service.reset_hard("invalid")

        assert result is False


@pytest.mark.unit
class TestGitServiceRollback:
    """Tests for the version-bump rollback path.

    Regression suite for the 2026-08-24 incident where ``checkout_files``
    ran ``git checkout -- <files>``, which only resets the working tree
    to match the index — a no-op for staged files. The fix is to pass
    ``HEAD`` explicitly so both the index AND working tree are reset.
    """

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.core.console.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_checkout_files_passes_head_argument(
        self, mock_run, service
    ) -> None:
        """checkout_files must include HEAD so staged files actually revert.

        Regression: ``git checkout -- <file>`` does NOT reset the index.
        For a staged file at v2, ``checkout -- file`` copies v2 from
        index to working tree — i.e. it's a no-op. The fix is to add
        ``HEAD`` between ``checkout`` and ``--``.
        """
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

        result = service.checkout_files(["pyproject.toml", "CHANGELOG.md"])

        assert result is True
        mock_run.assert_called_once()
        called_cmd = mock_run.call_args.kwargs["cmd"]
        # Must be: ['git', 'checkout', 'HEAD', '--', file1, file2, ...]
        assert called_cmd[:3] == ["git", "checkout", "HEAD"]
        assert "--" in called_cmd
        assert called_cmd[called_cmd.index("--") + 1:] == [
            "pyproject.toml",
            "CHANGELOG.md",
        ]

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_checkout_files_empty_returns_true_without_invoking_git(
        self, mock_run, service
    ) -> None:
        """Empty file list is a no-op (no git invocation)."""
        result = service.checkout_files([])

        assert result is True
        mock_run.assert_not_called()

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_checkout_files_returns_false_on_nonzero_returncode(
        self, mock_run, service
    ) -> None:
        """A non-zero returncode from ``git checkout HEAD --`` must surface as False."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error: pathspec 'x' did not match",
        )

        result = service.checkout_files(["x"])

        assert result is False


@pytest.mark.unit
class TestRunSubprocessWithKillOnTimeout:
    """Tests for the kill-on-timeout helper.

    Regression suite for the 2026-08-24 incident where ``subprocess.run``
    ``timeout=N`` was misleading: it abandoned the wait but left the
    child running orphaned, so a slow ``git commit`` could finish AFTER
    the caller declared the commit a failure and re-apply staged
    changes. The fix wraps the call in ``Popen.communicate(timeout=...)``
    + ``os.killpg`` so the entire process group is killed.
    """

    def test_killpg_invoked_on_timeout(self, monkeypatch, tmp_path) -> None:
        """TimeoutExpired must trigger os.killpg(SIGKILL) on the child group."""
        from crackerjack.services.git import _run_subprocess_with_kill_on_timeout

        popen_calls: list[dict] = []
        killpg_calls: list[tuple[int, int]] = []

        class _FakeProc:
            def __init__(self) -> None:
                self.pid = 99999  # arbitrary fake pid

            def communicate(self, *, timeout: float | None = None):  # type: ignore[no-untyped-def]
                # Always time out so we exercise the kill path.
                raise subprocess.TimeoutExpired(["sleep"], timeout or 0.0)

        def fake_popen(cmd, **kwargs):  # type: ignore[no-untyped-def]
            popen_calls.append({"cmd": cmd, "kwargs": kwargs})
            return _FakeProc()

        def fake_killpg(pid, sig):  # type: ignore[no-untyped-def]
            killpg_calls.append((pid, sig))

        monkeypatch.setattr(
            "crackerjack.services.git.subprocess.Popen", fake_popen,
        )
        monkeypatch.setattr("crackerjack.services.git.os.killpg", fake_killpg)

        with pytest.raises(subprocess.TimeoutExpired):
            _run_subprocess_with_kill_on_timeout(
                cmd=["git", "commit", "-m", "test"],
                cwd=tmp_path,
                timeout=1.0,
            )

        # Popen was started in a new session so killpg can target the group.
        assert popen_calls, "Popen was not invoked"
        assert popen_calls[0]["kwargs"].get("start_new_session") is True
        # The fake proc's pid was used; SIGKILL was the signal.
        assert killpg_calls == [(99999, signal.SIGKILL)]

    def test_no_killpg_when_child_completes(self, monkeypatch, tmp_path) -> None:
        """A successful child must not invoke killpg."""
        from crackerjack.services.git import _run_subprocess_with_kill_on_timeout

        class _FakeProc:
            def __init__(self) -> None:
                self.pid = 12345
                self.returncode = 0

            def communicate(self, *, timeout: float | None = None):  # type: ignore[no-untyped-def]
                return ("ok stdout", "ok stderr")

        killpg_calls: list = []

        def fake_popen(cmd, **kwargs):  # type: ignore[no-untyped-def]
            return _FakeProc()

        def fake_killpg(pid, sig):  # type: ignore[no-untyped-def]
            killpg_calls.append((pid, sig))

        monkeypatch.setattr(
            "crackerjack.services.git.subprocess.Popen", fake_popen,
        )
        monkeypatch.setattr("crackerjack.services.git.os.killpg", fake_killpg)

        result = _run_subprocess_with_kill_on_timeout(
            cmd=["git", "status"], cwd=tmp_path, timeout=5.0,
        )

        assert result.returncode == 0
        assert result.stdout == "ok stdout"
        assert result.stderr == "ok stderr"
        assert killpg_calls == []

    def test_timeout_none_disables_deadline(self, monkeypatch, tmp_path) -> None:
        """``timeout=None`` should call communicate() without a deadline."""
        from crackerjack.services.git import _run_subprocess_with_kill_on_timeout

        communicate_calls: list[dict] = []

        class _FakeProc:
            def __init__(self) -> None:
                self.pid = 7777
                self.returncode = 0

            def communicate(self, *, timeout: float | None = None):  # type: ignore[no-untyped-def]
                communicate_calls.append({"timeout": timeout})
                return ("", "")

        monkeypatch.setattr(
            "crackerjack.services.git.subprocess.Popen", lambda *a, **kw: _FakeProc(),
        )

        _run_subprocess_with_kill_on_timeout(
            cmd=["git", "log"], cwd=tmp_path, timeout=None,
        )

        assert communicate_calls == [{"timeout": None}]


@pytest.mark.unit
class TestGitServiceDefaultTimeout:
    """Verify the bumped default timeout is wired through ``_run_git_command``."""

    def test_default_timeout_is_300_seconds(self) -> None:
        """The hardcoded default is 300s (was 60s, bumped 2026-08-24)."""
        from crackerjack.services import git as git_module

        assert git_module._GIT_DEFAULT_TIMEOUT_SECONDS == 300

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_run_git_command_forwards_default_timeout(
        self, mock_run, tmp_path
    ) -> None:
        """``_run_git_command`` passes the 300s default to the helper."""
        with patch("crackerjack.core.console.CrackerjackConsole"):
            service = GitService(console=Mock(), pkg_path=tmp_path)
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

        service._run_git_command(["status"])

        mock_run.assert_called_once()
        # The timeout kwarg must equal the module-level default constant.
        passed_timeout = mock_run.call_args.kwargs["timeout"]
        assert passed_timeout == 300


@pytest.mark.unit
class TestFailedGitResult:
    """Test FailedGitResult class."""

    def test_failed_git_result_initialization(self) -> None:
        """Test FailedGitResult creates proper error result."""
        cmd = ["git", "status"]
        error = "Command validation failed"

        result = FailedGitResult(cmd, error)

        assert result.args == cmd
        assert result.returncode == -1
        assert result.stdout == ""
        assert "Git security validation failed" in result.stderr
        assert error in result.stderr


@pytest.mark.unit
class TestGitServiceEdgeCases:
    """Test edge cases for git operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.CrackerjackConsole"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_handles_permission_denied_on_add(self, mock_execute, service, tmp_path) -> None:
        """Test handling of permission denied when adding files."""
        # Create file without read permissions
        test_file = tmp_path / "secret.txt"
        test_file.write_text("content")
        test_file.chmod(0o000)

        try:
            mock_execute.return_value = subprocess.CompletedProcess(
                args=["git", "add"],
                returncode=128,
                stdout="",
                stderr="fatal: open('secret.txt'): Permission denied",
            )

            result = service.add_files(["secret.txt"])

            assert result is False
        finally:
            test_file.chmod(0o644)

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_handles_symlink_in_changed_files(self, mock_execute, service, tmp_path) -> None:
        """Test that symlinks are properly handled in changed files."""
        # Create actual file and symlink
        actual_file = tmp_path / "actual.txt"
        actual_file.write_text("content")
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(actual_file)

        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="link.txt\n", stderr="",
        )

        files = service.get_staged_files()

        assert len(files) == 1
        assert "link.txt" in files

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_handles_broken_symlink_in_repo(self, mock_execute, service, tmp_path) -> None:
        """Test handling of broken symlinks in repository."""
        # Create broken symlink
        broken_link = tmp_path / "broken.txt"
        broken_link.symlink_to(tmp_path / "nonexistent.txt")

        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="broken.txt\n", stderr="",
        )

        files = service.get_changed_files()

        # Should detect the broken symlink
        assert "broken.txt" in files

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_handles_disk_full_on_commit(self, mock_execute, service) -> None:
        """Test handling of disk full error during commit."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=["git", "commit"],
            returncode=128,
            stdout="",
            stderr="error: unable to write new_index file\nNo space left on device",
        )

        result = service.commit("Test commit")

        assert result is False

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_handles_corrupt_git_repository(self, mock_execute, service) -> None:
        """Test handling of corrupt git repository."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=128,
            stdout="",
            stderr="fatal: bad object HEAD",
        )

        # Should handle gracefully
        is_repo = service.is_git_repo()
        assert is_repo is False

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_handles_race_condition_on_push(self, mock_execute, service) -> None:
        """Test handling of concurrent push operations."""
        # Simulate race condition: another push happened first
        mock_execute.return_value = subprocess.CompletedProcess(
            args=["git", "push"],
            returncode=1,
            stdout="",
            stderr="To prevent you from losing history, non-fast-forward updates were rejected",
        )

        result = service.push()

        assert result is False

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_get_changed_files_with_mixed_symlinks_and_files(
        self, mock_execute, service, tmp_path
    ) -> None:
        """Test getting changed files with mix of symlinks and regular files."""
        # Create mix of files
        (tmp_path / "file1.py").write_text("# python file")
        (tmp_path / "file2.md").write_text("# markdown")
        actual_file = tmp_path / "actual.txt"
        actual_file.write_text("content")
        (tmp_path / "link.txt").symlink_to(actual_file)

        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="file1.py\nfile2.md\nlink.txt\n", stderr="",
        )

        files = service.get_changed_files()

        # Should handle all types
        assert len(files) == 3
        assert "file1.py" in files
        assert "file2.md" in files
        assert "link.txt" in files

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_handles_submodule_in_changed_files(self, mock_execute, service) -> None:
        """Test that git submodules are handled correctly."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="submodule/\n", stderr="",
        )

        files = service.get_changed_files()

        # Should detect submodule (with trailing slash)
        assert len(files) == 1
        assert "submodule/" in files

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_commit_with_special_characters_in_message(self, mock_execute, service) -> None:
        """Test commit with special characters in commit message."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=["git", "commit"],
            returncode=0,
            stdout="[main abc123] Fix: handle émojis 🎉 and spëcial çhars",
            stderr="",
        )

        message = "Fix: handle émojis 🎉 and spëcial çhars"
        result = service.commit(message)

        assert result is True

    @patch("crackerjack.services.git._run_subprocess_with_kill_on_timeout")
    def test_handles_large_number_of_changed_files(self, mock_execute, service) -> None:
        """Test handling of large number of changed files (performance edge case)."""
        # Simulate 1000 changed files
        files_list = "\n".join([f"file{i}.py" for i in range(1000)])
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=files_list, stderr="",
        )

        files = service.get_changed_files()

        # Should handle large lists
        assert len(files) == 1000
