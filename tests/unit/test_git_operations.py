#!/usr/bin/env python3
"""Unit tests for git_operations utilities."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from session_mgmt_mcp.utils.git_operations import (
    WorktreeInfo,
    _format_untracked_files,
    _parse_git_status,
    _parse_worktree_entry,
    _process_worktree_line,
    create_checkpoint_commit,
    create_commit,
    get_git_root,
    get_git_status,
    get_staged_files,
    get_worktree_info,
    is_git_repository,
    is_git_worktree,
    list_worktrees,
    stage_files,
)


class TestGitRepositoryDetection:
    """Test git repository detection functions."""

    def test_is_git_repository_with_git_directory(self):
        """Test is_git_repository with .git directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            git_dir = repo_path / ".git"
            git_dir.mkdir()

            assert is_git_repository(repo_path) is True

    def test_is_git_repository_with_git_file(self):
        """Test is_git_repository with .git file (worktree)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            git_file = repo_path / ".git"
            git_file.touch()

            assert is_git_repository(repo_path) is True

    def test_is_git_repository_nonexistent(self):
        """Test is_git_repository with non-git directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            assert is_git_repository(repo_path) is False

    def test_is_git_worktree(self):
        """Test is_git_worktree function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            git_file = repo_path / ".git"
            git_file.touch()

            assert is_git_worktree(repo_path) is True
            assert is_git_worktree(str(repo_path)) is True

    def test_is_git_worktree_not_worktree(self):
        """Test is_git_worktree with regular git repo."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            git_dir = repo_path / ".git"
            git_dir.mkdir()

            assert is_git_worktree(repo_path) is False


class TestGitRootDetection:
    """Test git root detection functionality."""

    @patch("subprocess.run")
    def test_get_git_root_success(self, mock_run):
        """Test get_git_root with successful git command."""
        mock_result = Mock()
        mock_result.stdout = "/path/to/repo\n"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = get_git_root(repo_path)

            assert result == Path("/path/to/repo")
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                check=True,
            )

    @patch("subprocess.run")
    def test_get_git_root_failure(self, mock_run):
        """Test get_git_root with failed git command."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = get_git_root(repo_path)

            assert result is None


class TestWorktreeInfo:
    """Test WorktreeInfo dataclass."""

    def test_worktree_info_creation(self):
        """Test WorktreeInfo creation with all parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            wt_info = WorktreeInfo(
                path=path,
                branch="main",
                is_bare=False,
                is_detached=False,
                is_main_worktree=True,
                locked=False,
                prunable=False,
            )

            assert wt_info.path == path
            assert wt_info.branch == "main"
            assert wt_info.is_bare is False
            assert wt_info.is_detached is False
            assert wt_info.is_main_worktree is True
            assert wt_info.locked is False
            assert wt_info.prunable is False


class TestWorktreeProcessing:
    """Test worktree processing functions."""

    def test_process_worktree_line_worktree(self):
        """Test _process_worktree_line with worktree line."""
        current_worktree = {}
        _process_worktree_line("worktree /path/to/worktree", current_worktree)

        assert current_worktree["path"] == "/path/to/worktree"

    def test_process_worktree_line_head(self):
        """Test _process_worktree_line with HEAD line."""
        current_worktree = {}
        _process_worktree_line("HEAD abc123", current_worktree)

        assert current_worktree["head"] == "abc123"

    def test_process_worktree_line_branch(self):
        """Test _process_worktree_line with branch line."""
        current_worktree = {}
        _process_worktree_line("branch refs/heads/main", current_worktree)

        assert current_worktree["branch"] == "refs/heads/main"

    def test_process_worktree_line_flags(self):
        """Test _process_worktree_line with flag lines."""
        test_cases = [
            ("bare", "bare", True),
            ("detached", "detached", True),
            ("locked", "locked", True),
            ("prunable", "prunable", True),
        ]

        for line, key, expected in test_cases:
            current_worktree = {}
            _process_worktree_line(line, current_worktree)

            assert current_worktree[key] is expected

    def test_parse_worktree_entry(self):
        """Test _parse_worktree_entry function."""
        entry = {
            "path": "/path/to/worktree",
            "branch": "refs/heads/feature",
            "bare": False,
            "detached": False,
            "locked": True,
            "prunable": False,
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=True):
                result = _parse_worktree_entry(entry)

                assert isinstance(result, WorktreeInfo)
                assert str(result.path) == "/path/to/worktree"
                assert result.branch == "refs/heads/feature"
                assert result.is_bare is False
                assert result.is_detached is False
                assert result.locked is True
                assert result.prunable is False
                assert result.is_main_worktree is False  # Because it's a worktree file


class TestListWorktrees:
    """Test list_worktrees function."""

    @patch("subprocess.run")
    def test_list_worktrees_success(self, mock_run):
        """Test list_worktrees with successful command."""
        mock_output = """worktree /path/to/main
HEAD abc123
branch refs/heads/main

worktree /path/to/feature
HEAD def456
branch refs/heads/feature
"""
        mock_result = Mock()
        mock_result.stdout = mock_output
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = list_worktrees(repo_path)

                assert len(result) == 2
                assert isinstance(result[0], WorktreeInfo)
                assert isinstance(result[1], WorktreeInfo)

    @patch("subprocess.run")
    def test_list_worktrees_failure(self, mock_run):
        """Test list_worktrees with failed command."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = list_worktrees(repo_path)

                assert result == []

    def test_list_worktrees_non_git_repo(self):
        """Test list_worktrees with non-git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = list_worktrees(repo_path)

            assert result == []


class TestGitStatus:
    """Test git status functions."""

    @patch("subprocess.run")
    def test_get_git_status_success(self, mock_run):
        """Test get_git_status with successful command."""
        mock_output = """ M modified_file.py
?? untracked_file.py
D  deleted_file.py
"""
        mock_result = Mock()
        mock_result.stdout = mock_output
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                modified, untracked = get_git_status(repo_path)

                assert modified == ["modified_file.py", "deleted_file.py"]
                assert untracked == ["untracked_file.py"]

    @patch("subprocess.run")
    def test_get_git_status_failure(self, mock_run):
        """Test get_git_status with failed command."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                modified, untracked = get_git_status(repo_path)

                assert modified == []
                assert untracked == []

    def test_parse_git_status(self):
        """Test _parse_git_status function."""
        status_lines = [
            " M modified_file.py",
            "?? untracked_file.py",
            "D  deleted_file.py",
            "A  added_file.py",
            " M another_modified.py",
        ]

        modified, untracked = _parse_git_status(status_lines)

        assert modified == [
            "modified_file.py",
            "deleted_file.py",
            "added_file.py",
            "another_modified.py",
        ]
        assert untracked == ["untracked_file.py"]

    def test_get_git_status_non_git_repo(self):
        """Test get_git_status with non-git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            modified, untracked = get_git_status(repo_path)

            assert modified == []
            assert untracked == []


class TestStagingAndCommits:
    """Test staging and commit functions."""

    @patch("subprocess.run")
    def test_stage_files_success(self, mock_run):
        """Test stage_files with successful command."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = stage_files(repo_path, ["file1.py", "file2.py"])

                assert result is True
                mock_run.assert_called_once_with(
                    ["git", "add", "-A"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )

    @patch("subprocess.run")
    def test_stage_files_failure(self, mock_run):
        """Test stage_files with failed command."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = stage_files(repo_path, ["file1.py"])

                assert result is False

    def test_stage_files_no_files(self):
        """Test stage_files with no files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = stage_files(repo_path, [])

            assert result is False

    def test_stage_files_non_git_repo(self):
        """Test stage_files with non-git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = stage_files(repo_path, ["file1.py"])

            assert result is False

    @patch("subprocess.run")
    def test_get_staged_files_success(self, mock_run):
        """Test get_staged_files with successful command."""
        mock_output = """staged_file1.py
staged_file2.py
"""
        mock_result = Mock()
        mock_result.stdout = mock_output
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = get_staged_files(repo_path)

                assert result == ["staged_file1.py", "staged_file2.py"]

    @patch("subprocess.run")
    def test_get_staged_files_failure(self, mock_run):
        """Test get_staged_files with failed command."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = get_staged_files(repo_path)

                assert result == []

    def test_get_staged_files_non_git_repo(self):
        """Test get_staged_files with non-git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = get_staged_files(repo_path)

            assert result == []

    @patch("subprocess.run")
    def test_create_commit_success(self, mock_run):
        """Test create_commit with successful commands."""
        # Mock the commit command
        commit_result = Mock()
        commit_result.stdout = ""
        commit_result.stderr = ""
        commit_result.returncode = 0

        # Mock the rev-parse command
        hash_result = Mock()
        hash_result.stdout = "abc123def456\n"
        hash_result.stderr = ""
        hash_result.returncode = 0

        mock_run.side_effect = [commit_result, hash_result]

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                success, commit_hash = create_commit(repo_path, "Test commit message")

                assert success is True
                assert commit_hash == "abc123de"

    @patch("subprocess.run")
    def test_create_commit_failure(self, mock_run):
        """Test create_commit with failed command."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git", stderr="Commit failed"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                success, error = create_commit(repo_path, "Test commit message")

                assert success is False
                assert error == "Commit failed"

    def test_create_commit_non_git_repo(self):
        """Test create_commit with non-git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            success, error = create_commit(repo_path, "Test commit message")

            assert success is False
            assert error == "Not a git repository"


class TestWorktreeInfoFunctions:
    """Test worktree information functions."""

    @patch("subprocess.run")
    def test_get_worktree_info_success(self, mock_run):
        """Test get_worktree_info with successful commands."""
        # Mock branch command
        branch_result = Mock()
        branch_result.stdout = "main\n"
        branch_result.stderr = ""
        branch_result.returncode = 0

        # Mock rev-parse HEAD command
        head_result = Mock()
        head_result.stdout = "abc123\n"
        head_result.stderr = ""
        head_result.returncode = 0

        # Mock rev-parse --show-toplevel command
        toplevel_result = Mock()
        toplevel_result.stdout = "/path/to/repo\n"
        toplevel_result.stderr = ""
        toplevel_result.returncode = 0

        mock_run.side_effect = [branch_result, head_result, toplevel_result]

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = get_worktree_info(repo_path)

                assert isinstance(result, WorktreeInfo)
                assert str(result.path) == "/path/to/repo"
                assert result.branch == "main"

    @patch("subprocess.run")
    def test_get_worktree_info_detached_head(self, mock_run):
        """Test get_worktree_info with detached HEAD."""
        # Mock branch command (empty output for detached HEAD)
        branch_result = Mock()
        branch_result.stdout = "\n"
        branch_result.stderr = ""
        branch_result.returncode = 0

        # Mock rev-parse HEAD command
        head_result = Mock()
        head_result.stdout = "abc123\n"
        head_result.stderr = ""
        head_result.returncode = 0

        # Mock rev-parse --show-toplevel command
        toplevel_result = Mock()
        toplevel_result.stdout = "/path/to/repo\n"
        toplevel_result.stderr = ""
        toplevel_result.returncode = 0

        mock_run.side_effect = [branch_result, head_result, toplevel_result]

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = get_worktree_info(repo_path)

                assert isinstance(result, WorktreeInfo)
                assert result.branch == "HEAD (abc123)"
                assert result.is_detached is True

    @patch("subprocess.run")
    def test_get_worktree_info_failure(self, mock_run):
        """Test get_worktree_info with failed command."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch(
                "session_mgmt_mcp.utils.git_operations.is_git_repository",
                return_value=True,
            ):
                result = get_worktree_info(repo_path)

                assert result is None


class TestCheckpointCommit:
    """Test checkpoint commit functionality."""

    def test_format_untracked_files(self):
        """Test _format_untracked_files function."""
        untracked_files = [f"file{i}.py" for i in range(15)]  # 15 files
        result = _format_untracked_files(untracked_files)

        assert len(result) > 0
        assert "Untracked files found:" in result[0]
        assert (
            "and 5 more" in result[-2]
        )  # Should show "and X more" for files beyond 10

    @patch("session_mgmt_mcp.utils.git_operations.is_git_repository")
    def test_create_checkpoint_commit_non_git_repo(self, mock_is_git_repo):
        """Test create_checkpoint_commit with non-git repository."""
        mock_is_git_repo.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            success, result, output = create_checkpoint_commit(
                repo_path, "test-project", 85
            )

            assert success is False
            assert result == "Not a git repository"
            assert "Not a git repository - skipping commit" in output

    @patch("session_mgmt_mcp.utils.git_operations.is_git_repository")
    @patch("session_mgmt_mcp.utils.git_operations.get_worktree_info")
    @patch("session_mgmt_mcp.utils.git_operations.get_git_status")
    def test_create_checkpoint_commit_clean_repo(
        self, mock_get_status, mock_get_worktree, mock_is_git_repo
    ):
        """Test create_checkpoint_commit with clean repository."""
        mock_is_git_repo.return_value = True
        mock_get_worktree.return_value = None
        mock_get_status.return_value = ([], [])  # No modified or untracked files

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            success, result, output = create_checkpoint_commit(
                repo_path, "test-project", 85
            )

            assert success is True
            assert result == "clean"
            assert "Working directory is clean - no changes to commit" in output


if __name__ == "__main__":
    pytest.main([__file__])
