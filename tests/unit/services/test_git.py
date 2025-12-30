"""Unit tests for GitService.

Tests git operations including repository detection, file staging,
commits, pushes, and branch operations.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from crackerjack.services.git import FailedGitResult, GitService


@pytest.mark.unit
class TestGitServiceInitialization:
    """Test GitService initialization."""

    def test_initialization_with_default_path(self):
        """Test GitService initializes with current working directory."""
        with patch("crackerjack.services.git.Console"):
            service = GitService(console=Mock(), pkg_path=None)

            assert service.pkg_path == Path.cwd()

    def test_initialization_with_custom_path(self, tmp_path):
        """Test GitService initializes with custom path."""
        with patch("crackerjack.services.git.Console"):
            service = GitService(console=Mock(), pkg_path=tmp_path)

            assert service.pkg_path == tmp_path


@pytest.mark.unit
class TestGitServiceRepositoryDetection:
    """Test git repository detection."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.Console"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_is_git_repo_true(self, mock_execute, service):
        """Test is_git_repo returns True for valid git repository."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=["git", "rev-parse", "--git-dir"],
            returncode=0,
            stdout=".git\n",
            stderr="",
        )

        assert service.is_git_repo() is True

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_is_git_repo_false(self, mock_execute, service):
        """Test is_git_repo returns False for non-git directory."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=["git", "rev-parse", "--git-dir"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )

        assert service.is_git_repo() is False

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_is_git_repo_handles_exception(self, mock_execute, service):
        """Test is_git_repo handles exceptions gracefully."""
        mock_execute.side_effect = FileNotFoundError("git not found")

        assert service.is_git_repo() is False


@pytest.mark.unit
class TestGitServiceFileOperations:
    """Test git file operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.Console"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_changed_files(self, mock_execute, service):
        """Test getting all changed files."""
        # Mock staged files
        mock_execute.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file1.py\nfile2.py\n", stderr=""
            ),
            # Mock unstaged files
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file3.py\n", stderr=""
            ),
            # Mock untracked files
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file4.py\n", stderr=""
            ),
        ]

        files = service.get_changed_files()

        assert len(files) == 4
        assert "file1.py" in files
        assert "file2.py" in files
        assert "file3.py" in files
        assert "file4.py" in files

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_changed_files_empty(self, mock_execute, service):
        """Test getting changed files when none exist."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        files = service.get_changed_files()

        assert files == []

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_staged_files(self, mock_execute, service):
        """Test getting staged files."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="staged1.py\nstaged2.py\n", stderr=""
        )

        files = service.get_staged_files()

        assert len(files) == 2
        assert "staged1.py" in files
        assert "staged2.py" in files

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_add_files_success(self, mock_execute, service):
        """Test successfully adding files."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        result = service.add_files(["file1.py", "file2.py"])

        assert result is True
        assert mock_execute.call_count == 2

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_add_files_failure(self, mock_execute, service):
        """Test handling of git add failure."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal: pathspec 'file.py' did not match any files"
        )

        result = service.add_files(["file.py"])

        assert result is False

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_add_all_files_success(self, mock_execute, service):
        """Test successfully adding all files."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        result = service.add_all_files()

        assert result is True

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_add_all_files_failure(self, mock_execute, service):
        """Test handling of add all failure."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )

        result = service.add_all_files()

        assert result is False


@pytest.mark.unit
class TestGitServiceCommit:
    """Test git commit operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.Console"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_commit_success(self, mock_execute, service):
        """Test successful commit."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="[main abc123] Test commit", stderr=""
        )

        result = service.commit("Test commit")

        assert result is True

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_commit_hook_modification(self, mock_execute, service):
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
                args=[], returncode=0, stdout="", stderr=""
            ),
            # Retry commit succeeds
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="[main abc123] Test commit", stderr=""
            ),
        ]

        result = service.commit("Test commit")

        assert result is True
        assert mock_execute.call_count == 3

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_commit_hook_blocked(self, mock_execute, service):
        """Test commit blocked by hooks."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="pre-commit hook failed",
        )

        result = service.commit("Test commit")

        assert result is False

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_commit_generic_failure(self, mock_execute, service):
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
        with patch("crackerjack.services.git.Console"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_push_success(self, mock_execute, service):
        """Test successful push."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="* refs/heads/main:refs/heads/main [new branch]\n",
            stderr="",
        )

        result = service.push()

        assert result is True

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_push_failure(self, mock_execute, service):
        """Test failed push."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="error: failed to push some refs",
        )

        result = service.push()

        assert result is False

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_push_with_tags_success(self, mock_execute, service):
        """Test successful push with tags."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="* refs/heads/main:refs/heads/main\n* refs/tags/v1.0.0:refs/tags/v1.0.0\n",
            stderr="",
        )

        result = service.push_with_tags()

        assert result is True

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_push_no_new_commits(self, mock_execute, service):
        """Test push with no new commits."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        result = service.push()

        assert result is True


@pytest.mark.unit
class TestGitServiceBranch:
    """Test git branch operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.Console"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_current_branch_success(self, mock_execute, service):
        """Test getting current branch name."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="main\n", stderr=""
        )

        branch = service.get_current_branch()

        assert branch == "main"

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_current_branch_failure(self, mock_execute, service):
        """Test getting current branch when not in repo."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal: not a git repository"
        )

        branch = service.get_current_branch()

        assert branch is None

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_unpushed_commit_count(self, mock_execute, service):
        """Test getting unpushed commit count."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="3\n", stderr=""
        )

        count = service.get_unpushed_commit_count()

        assert count == 3

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_unpushed_commit_count_zero(self, mock_execute, service):
        """Test unpushed commit count when up to date."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="0\n", stderr=""
        )

        count = service.get_unpushed_commit_count()

        assert count == 0

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_unpushed_commit_count_error(self, mock_execute, service):
        """Test unpushed commit count with error."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="error"
        )

        count = service.get_unpushed_commit_count()

        assert count == 0


@pytest.mark.unit
class TestGitServiceCommitMessages:
    """Test commit message generation."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create GitService instance for testing."""
        with patch("crackerjack.services.git.Console"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    def test_get_commit_message_suggestions_empty(self, service):
        """Test commit message suggestions with no files."""
        suggestions = service.get_commit_message_suggestions([])

        assert len(suggestions) > 0
        assert "Update project files" in suggestions

    def test_get_commit_message_suggestions_docs(self, service):
        """Test commit message suggestions for documentation files."""
        files = ["README.md", "docs/guide.md"]

        suggestions = service.get_commit_message_suggestions(files)

        assert any("documentation" in msg.lower() for msg in suggestions)

    def test_get_commit_message_suggestions_tests(self, service):
        """Test commit message suggestions for test files."""
        files = ["test_git.py", "tests/test_service.py"]

        suggestions = service.get_commit_message_suggestions(files)

        assert any("test" in msg.lower() for msg in suggestions)

    def test_get_commit_message_suggestions_config(self, service):
        """Test commit message suggestions for config files."""
        files = ["pyproject.toml", "config.yaml"]

        suggestions = service.get_commit_message_suggestions(files)

        assert any("config" in msg.lower() for msg in suggestions)

    def test_get_commit_message_suggestions_mixed(self, service):
        """Test commit message suggestions for mixed file types."""
        files = ["README.md", "test_git.py", "pyproject.toml"]

        suggestions = service.get_commit_message_suggestions(files)

        # Should return max 5 suggestions
        assert len(suggestions) <= 5

    def test_get_commit_message_suggestions_pyproject_specific(self, service):
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

        with patch("crackerjack.services.git.Console"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_changed_files_by_extension(self, mock_execute, service):
        """Test getting changed files filtered by extension."""
        # Mock staged and unstaged files
        mock_execute.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file1.py\nfile2.md\n", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="file3.py\n", stderr=""
            ),
        ]

        # Get only Python files
        py_files = service.get_changed_files_by_extension([".py"])

        assert len(py_files) == 2
        assert all(str(f).endswith(".py") for f in py_files)

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_changed_files_by_extension_staged_only(self, mock_execute, service):
        """Test getting only staged files by extension."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="file1.py\n", stderr=""
        )

        py_files = service.get_changed_files_by_extension(
            [".py"],
            include_staged=True,
            include_unstaged=False,
        )

        assert len(py_files) == 1
        assert mock_execute.call_count == 1

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_changed_files_by_extension_unstaged_only(self, mock_execute, service):
        """Test getting only unstaged files by extension."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="file3.py\n", stderr=""
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
        with patch("crackerjack.services.git.Console"):
            return GitService(console=Mock(), pkg_path=tmp_path)

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_current_commit_hash(self, mock_execute, service):
        """Test getting current commit hash."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="abc123def456\n", stderr=""
        )

        commit_hash = service.get_current_commit_hash()

        assert commit_hash == "abc123def456"

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_get_current_commit_hash_failure(self, mock_execute, service):
        """Test getting commit hash with error."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="error"
        )

        commit_hash = service.get_current_commit_hash()

        assert commit_hash is None

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_reset_hard_success(self, mock_execute, service):
        """Test hard reset to commit."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        result = service.reset_hard("abc123")

        assert result is True

    @patch("crackerjack.services.git.execute_secure_subprocess")
    def test_reset_hard_failure(self, mock_execute, service):
        """Test hard reset failure."""
        mock_execute.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error: invalid commit"
        )

        result = service.reset_hard("invalid")

        assert result is False


@pytest.mark.unit
class TestFailedGitResult:
    """Test FailedGitResult class."""

    def test_failed_git_result_initialization(self):
        """Test FailedGitResult creates proper error result."""
        cmd = ["git", "status"]
        error = "Command validation failed"

        result = FailedGitResult(cmd, error)

        assert result.args == cmd
        assert result.returncode == -1
        assert result.stdout == ""
        assert "Git security validation failed" in result.stderr
        assert error in result.stderr
