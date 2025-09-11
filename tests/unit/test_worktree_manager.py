#!/usr/bin/env python3
"""Unit tests for WorktreeManager class."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from session_mgmt_mcp.utils.logging import SessionLogger
from session_mgmt_mcp.worktree_manager import WorktreeManager


class TestWorktreeManagerInitialization:
    """Test WorktreeManager initialization."""

    def test_init_without_logger(self):
        """Test WorktreeManager initialization without logger."""
        manager = WorktreeManager()
        assert manager.session_logger is None

    def test_init_with_logger(self):
        """Test WorktreeManager initialization with logger."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            logger = SessionLogger(log_dir)
            manager = WorktreeManager(session_logger=logger)
            assert manager.session_logger is logger


class TestWorktreeManagerListWorktrees:
    """Test WorktreeManager list_worktrees method."""

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_list_worktrees_non_git_repo(self, mock_is_git_repo):
        """Test list_worktrees with non-git repository."""
        mock_is_git_repo.return_value = False

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = await manager.list_worktrees(repo_path)

            assert result["success"] is False
            assert result["error"] == "Not a git repository"
            assert result["worktrees"] == []

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("session_mgmt_mcp.worktree_manager.list_worktrees")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    async def test_list_worktrees_success(
        self, mock_get_worktree_info, mock_list_worktrees, mock_is_git_repo
    ):
        """Test list_worktrees with successful operation."""
        mock_is_git_repo.return_value = True

        # Mock worktree info
        mock_worktree_info = Mock()
        mock_worktree_info.path = Path("/path/to/worktree")
        mock_worktree_info.branch = "main"
        mock_worktree_info.is_main_worktree = True
        mock_worktree_info.is_detached = False
        mock_worktree_info.is_bare = False
        mock_worktree_info.locked = False
        mock_worktree_info.prunable = False
        mock_get_worktree_info.return_value = mock_worktree_info

        # Mock list_worktrees return value
        mock_list_worktrees.return_value = [mock_worktree_info]

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = await manager.list_worktrees(repo_path)

            assert result["success"] is True
            assert "worktrees" in result
            assert "current_worktree" in result
            assert "total_count" in result

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_list_worktrees_exception(self, mock_is_git_repo):
        """Test list_worktrees with exception."""
        mock_is_git_repo.return_value = True

        manager = WorktreeManager()
        with patch(
            "session_mgmt_mcp.worktree_manager.list_worktrees",
            side_effect=Exception("Test error"),
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_path = Path(temp_dir)
                result = await manager.list_worktrees(repo_path)

                assert result["success"] is False
                assert "Test error" in result["error"]


class TestWorktreeManagerCreateWorktree:
    """Test WorktreeManager create_worktree method."""

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_create_worktree_non_git_repo(self, mock_is_git_repo):
        """Test create_worktree with non-git repository."""
        mock_is_git_repo.return_value = False

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            new_path = Path(temp_dir) / "new_worktree"
            result = await manager.create_worktree(
                repo_path, new_path, "feature-branch"
            )

            assert result["success"] is False
            assert "not a git repository" in result["error"].lower()

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_create_worktree_target_exists(self, mock_is_git_repo):
        """Test create_worktree when target path already exists."""
        mock_is_git_repo.return_value = True

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            new_path = Path(temp_dir) / "existing_dir"
            new_path.mkdir()  # Create the directory to make it exist
            result = await manager.create_worktree(
                repo_path, new_path, "feature-branch"
            )

            assert result["success"] is False
            assert "already exists" in result["error"]

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    async def test_create_worktree_success(
        self, mock_get_worktree_info, mock_subprocess_run, mock_is_git_repo
    ):
        """Test create_worktree with successful operation."""
        mock_is_git_repo.return_value = True
        mock_subprocess_run.return_value = Mock(
            stdout="Created worktree", stderr="", returncode=0
        )

        # Mock worktree info
        mock_worktree_info = Mock()
        mock_worktree_info.path = Path("/path/to/new_worktree")
        mock_worktree_info.branch = "feature-branch"
        mock_worktree_info.is_main_worktree = False
        mock_worktree_info.is_detached = False
        mock_get_worktree_info.return_value = mock_worktree_info

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            new_path = Path(temp_dir) / "new_worktree"
            result = await manager.create_worktree(
                repo_path, new_path, "feature-branch"
            )

            assert result["success"] is True
            assert result["worktree_path"] == str(new_path)
            assert result["branch"] == "feature-branch"

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    async def test_create_worktree_subprocess_error(
        self, mock_subprocess_run, mock_is_git_repo
    ):
        """Test create_worktree with subprocess error."""
        from subprocess import CalledProcessError

        mock_is_git_repo.return_value = True
        mock_subprocess_run.side_effect = CalledProcessError(
            1, "git", stderr="Git error"
        )

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            new_path = Path(temp_dir) / "new_worktree"
            result = await manager.create_worktree(
                repo_path, new_path, "feature-branch"
            )

            assert result["success"] is False
            assert "Git error" in result["error"]

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    async def test_create_worktree_general_exception(
        self, mock_subprocess_run, mock_is_git_repo
    ):
        """Test create_worktree with general exception."""
        mock_is_git_repo.return_value = True
        mock_subprocess_run.side_effect = Exception("Unexpected error")

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            new_path = Path(temp_dir) / "new_worktree"
            result = await manager.create_worktree(
                repo_path, new_path, "feature-branch"
            )

            assert result["success"] is False
            assert "Unexpected error" in result["error"]

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    async def test_create_worktree_with_create_branch(
        self, mock_get_worktree_info, mock_subprocess_run, mock_is_git_repo
    ):
        """Test create_worktree with create_branch flag."""
        mock_is_git_repo.return_value = True
        mock_subprocess_run.return_value = Mock(
            stdout="Created worktree", stderr="", returncode=0
        )

        # Mock worktree info
        mock_worktree_info = Mock()
        mock_worktree_info.path = Path("/path/to/new_worktree")
        mock_worktree_info.branch = "new-feature"
        mock_worktree_info.is_main_worktree = False
        mock_worktree_info.is_detached = False
        mock_get_worktree_info.return_value = mock_worktree_info

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            new_path = Path(temp_dir) / "new_worktree"
            result = await manager.create_worktree(
                repo_path, new_path, "new-feature", create_branch=True
            )

            # Verify subprocess was called with -b flag
            mock_subprocess_run.assert_called_once()
            call_args = mock_subprocess_run.call_args
            assert "-b" in call_args[0][0]  # Command list contains -b flag

            assert result["success"] is True


class TestWorktreeManagerRemoveWorktree:
    """Test WorktreeManager remove_worktree method."""

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_remove_worktree_non_git_repo(self, mock_is_git_repo):
        """Test remove_worktree with non-git repository."""
        mock_is_git_repo.return_value = False

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            worktree_path = Path(temp_dir) / "worktree_to_remove"
            result = await manager.remove_worktree(repo_path, worktree_path)

            assert result["success"] is False
            assert "not a git repository" in result["error"].lower()

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    async def test_remove_worktree_success(self, mock_subprocess_run, mock_is_git_repo):
        """Test remove_worktree with successful operation."""
        mock_is_git_repo.return_value = True
        mock_subprocess_run.return_value = Mock(stdout="", stderr="", returncode=0)

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            worktree_path = Path(temp_dir) / "worktree_to_remove"
            result = await manager.remove_worktree(repo_path, worktree_path)

            assert result["success"] is True
            assert result["removed_path"] == str(worktree_path)

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    async def test_remove_worktree_with_force(
        self, mock_subprocess_run, mock_is_git_repo
    ):
        """Test remove_worktree with force flag."""
        mock_is_git_repo.return_value = True
        mock_subprocess_run.return_value = Mock(stdout="", stderr="", returncode=0)

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            worktree_path = Path(temp_dir) / "worktree_to_remove"
            result = await manager.remove_worktree(repo_path, worktree_path, force=True)

            # Verify subprocess was called with --force flag
            mock_subprocess_run.assert_called_once()
            call_args = mock_subprocess_run.call_args
            assert "--force" in call_args[0][0]  # Command list contains --force flag

            assert result["success"] is True

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    async def test_remove_worktree_subprocess_error(
        self, mock_subprocess_run, mock_is_git_repo
    ):
        """Test remove_worktree with subprocess error."""
        from subprocess import CalledProcessError

        mock_is_git_repo.return_value = True
        mock_subprocess_run.side_effect = CalledProcessError(
            1, "git", stderr="Remove failed"
        )

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            worktree_path = Path(temp_dir) / "worktree_to_remove"
            result = await manager.remove_worktree(repo_path, worktree_path)

            assert result["success"] is False
            assert "Remove failed" in result["error"]


class TestWorktreeManagerPruneWorktrees:
    """Test WorktreeManager prune_worktrees method."""

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_prune_worktrees_non_git_repo(self, mock_is_git_repo):
        """Test prune_worktrees with non-git repository."""
        mock_is_git_repo.return_value = False

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = await manager.prune_worktrees(repo_path)

            assert result["success"] is False
            assert "not a git repository" in result["error"].lower()

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    async def test_prune_worktrees_success(self, mock_subprocess_run, mock_is_git_repo):
        """Test prune_worktrees with successful operation."""
        mock_is_git_repo.return_value = True
        mock_output = (
            "Removing worktree /path/to/stale\nRemoving worktree /path/to/another\n"
        )
        mock_subprocess_run.return_value = Mock(
            stdout=mock_output, stderr="", returncode=0
        )

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = await manager.prune_worktrees(repo_path)

            assert result["success"] is True
            assert result["pruned_count"] == 2

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    async def test_prune_worktrees_no_pruning_needed(
        self, mock_subprocess_run, mock_is_git_repo
    ):
        """Test prune_worktrees when no pruning is needed."""
        mock_is_git_repo.return_value = True
        mock_subprocess_run.return_value = Mock(stdout="", stderr="", returncode=0)

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = await manager.prune_worktrees(repo_path)

            assert result["success"] is True
            assert result["pruned_count"] == 0
            assert "No worktrees to prune" in result["output"]

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("subprocess.run")
    async def test_prune_worktrees_subprocess_error(
        self, mock_subprocess_run, mock_is_git_repo
    ):
        """Test prune_worktrees with subprocess error."""
        from subprocess import CalledProcessError

        mock_is_git_repo.return_value = True
        mock_subprocess_run.side_effect = CalledProcessError(
            1, "git", stderr="Prune failed"
        )

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = await manager.prune_worktrees(repo_path)

            assert result["success"] is False
            assert "Prune failed" in result["error"]


class TestWorktreeManagerGetWorktreeStatus:
    """Test WorktreeManager get_worktree_status method."""

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_get_worktree_status_non_git_repo(self, mock_is_git_repo):
        """Test get_worktree_status with non-git repository."""
        mock_is_git_repo.return_value = False

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = await manager.get_worktree_status(repo_path)

            assert result["success"] is False
            assert "not a git repository" in result["error"].lower()

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    async def test_get_worktree_status_no_worktree_info(
        self, mock_get_worktree_info, mock_is_git_repo
    ):
        """Test get_worktree_status when worktree info cannot be obtained."""
        mock_is_git_repo.return_value = True
        mock_get_worktree_info.return_value = None

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            result = await manager.get_worktree_status(repo_path)

            assert result["success"] is False
            assert "worktree info" in result["error"].lower()

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    @patch("session_mgmt_mcp.worktree_manager.list_worktrees")
    async def test_get_worktree_status_success(
        self, mock_list_worktrees, mock_get_worktree_info, mock_is_git_repo
    ):
        """Test get_worktree_status with successful operation."""
        mock_is_git_repo.return_value = True

        # Mock current worktree info
        mock_current_worktree = Mock()
        mock_current_worktree.path = Path("/path/to/current")
        mock_current_worktree.branch = "main"
        mock_current_worktree.is_main_worktree = True
        mock_current_worktree.is_detached = False
        mock_get_worktree_info.return_value = mock_current_worktree

        # Mock list of worktrees
        mock_worktree1 = Mock()
        mock_worktree1.path = Path("/path/to/current")
        mock_worktree1.branch = "main"
        mock_worktree1.is_main_worktree = True
        mock_worktree1.prunable = False

        mock_worktree2 = Mock()
        mock_worktree2.path = Path("/path/to/feature")
        mock_worktree2.branch = "feature"
        mock_worktree2.is_main_worktree = False
        mock_worktree2.prunable = False

        mock_list_worktrees.return_value = [mock_worktree1, mock_worktree2]

        # Mock session checking
        manager = WorktreeManager()
        with patch.object(manager, "_check_session_exists", return_value=True):
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_path = Path(temp_dir)
                result = await manager.get_worktree_status(repo_path)

                assert result["success"] is True
                assert "current_worktree" in result
                assert "all_worktrees" in result
                assert "total_worktrees" in result
                assert "session_summary" in result
                assert result["total_worktrees"] == 2


class TestWorktreeManagerSessionCheck:
    """Test WorktreeManager session checking methods."""

    def test_check_session_exists_with_existing_path(self):
        """Test _check_session_exists with existing path."""
        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            worktree_path = Path(temp_dir)

            # Create a .git directory to simulate a git repo
            (worktree_path / ".git").mkdir()

            result = manager._check_session_exists(worktree_path)
            assert result is True

    def test_check_session_exists_with_nonexistent_path(self):
        """Test _check_session_exists with nonexistent path."""
        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            worktree_path = Path(temp_dir) / "nonexistent"
            result = manager._check_session_exists(worktree_path)
            assert result is False

    def test_check_session_exists_with_project_files(self):
        """Test _check_session_exists with project files."""
        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            worktree_path = Path(temp_dir)

            # Create a project file
            (worktree_path / "pyproject.toml").touch()

            result = manager._check_session_exists(worktree_path)
            assert result is True

    def test_get_session_summary(self):
        """Test _get_session_summary method."""
        manager = WorktreeManager()

        # Create mock worktrees
        mock_worktree1 = Mock()
        mock_worktree1.path = Path("/path/to/worktree1")
        mock_worktree1.branch = "main"

        mock_worktree2 = Mock()
        mock_worktree2.path = Path("/path/to/worktree2")
        mock_worktree2.branch = "feature"

        worktrees = [mock_worktree1, mock_worktree2]

        # Mock session checking
        with patch.object(manager, "_check_session_exists", side_effect=[True, False]):
            result = manager._get_session_summary(worktrees)

            assert "active_sessions" in result
            assert "unique_branches" in result
            assert "branches" in result
            assert result["active_sessions"] == 1
            assert result["unique_branches"] == 2
            assert len(result["branches"]) == 2


class TestWorktreeManagerSwitchContext:
    """Test WorktreeManager switch_worktree_context method."""

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_switch_worktree_context_source_not_git_repo(self, mock_is_git_repo):
        """Test switch_worktree_context with non-git source path."""
        mock_is_git_repo.side_effect = [False, True]  # Source not git, target is git

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            from_path = Path(temp_dir) / "source"
            to_path = Path(temp_dir) / "target"
            (from_path).mkdir()
            (to_path).mkdir()

            result = await manager.switch_worktree_context(from_path, to_path)

            assert result["success"] is False
            assert "source path is not a git repository" in result["error"].lower()

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    async def test_switch_worktree_context_target_not_git_repo(self, mock_is_git_repo):
        """Test switch_worktree_context with non-git target path."""
        mock_is_git_repo.side_effect = [True, False]  # Source is git, target not git

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            from_path = Path(temp_dir) / "source"
            to_path = Path(temp_dir) / "target"
            (from_path).mkdir()
            (to_path).mkdir()

            # Create .git directory in source to make it a git repo
            (from_path / ".git").mkdir()

            result = await manager.switch_worktree_context(from_path, to_path)

            assert result["success"] is False
            assert "target path is not a git repository" in result["error"].lower()

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    async def test_switch_worktree_context_worktree_info_failure(
        self, mock_get_worktree_info, mock_is_git_repo
    ):
        """Test switch_worktree_context when worktree info cannot be obtained."""
        mock_is_git_repo.return_value = True
        mock_get_worktree_info.return_value = None  # Simulate failure

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            from_path = Path(temp_dir) / "source"
            to_path = Path(temp_dir) / "target"
            (from_path).mkdir()
            (to_path).mkdir()

            # Create .git directories
            (from_path / ".git").mkdir()
            (to_path / ".git").mkdir()

            result = await manager.switch_worktree_context(from_path, to_path)

            assert result["success"] is False
            assert "worktree information" in result["error"].lower()

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    @patch("os.chdir")
    async def test_switch_worktree_context_success(
        self, mock_chdir, mock_get_worktree_info, mock_is_git_repo
    ):
        """Test switch_worktree_context with successful operation."""
        mock_is_git_repo.return_value = True

        # Mock from worktree info
        mock_from_worktree = Mock()
        mock_from_worktree.path = Path("/path/to/source")
        mock_from_worktree.branch = "main"

        # Mock to worktree info
        mock_to_worktree = Mock()
        mock_to_worktree.path = Path("/path/to/target")
        mock_to_worktree.branch = "feature"

        mock_get_worktree_info.side_effect = [mock_from_worktree, mock_to_worktree]

        manager = WorktreeManager()
        with patch.object(
            manager, "_save_current_session_state", return_value={"test": "data"}
        ):
            with patch.object(manager, "_restore_session_state", return_value=True):
                with tempfile.TemporaryDirectory() as temp_dir:
                    from_path = Path(temp_dir) / "source"
                    to_path = Path(temp_dir) / "target"
                    (from_path).mkdir()
                    (to_path).mkdir()

                    # Create .git directories
                    (from_path / ".git").mkdir()
                    (to_path / ".git").mkdir()

                    result = await manager.switch_worktree_context(from_path, to_path)

                    assert result["success"] is True
                    assert result["context_preserved"] is True
                    assert "switched" in result["message"].lower()
                    mock_chdir.assert_called_once_with(to_path)

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    @patch("os.chdir")
    async def test_switch_worktree_context_session_preservation_failure(
        self, mock_chdir, mock_get_worktree_info, mock_is_git_repo
    ):
        """Test switch_worktree_context when session preservation fails but basic switching succeeds."""
        mock_is_git_repo.return_value = True

        # Mock from worktree info
        mock_from_worktree = Mock()
        mock_from_worktree.path = Path("/path/to/source")
        mock_from_worktree.branch = "main"

        # Mock to worktree info
        mock_to_worktree = Mock()
        mock_to_worktree.path = Path("/path/to/target")
        mock_to_worktree.branch = "feature"

        mock_get_worktree_info.side_effect = [mock_from_worktree, mock_to_worktree]

        manager = WorktreeManager()
        with patch.object(
            manager,
            "_save_current_session_state",
            side_effect=Exception("Session error"),
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                from_path = Path(temp_dir) / "source"
                to_path = Path(temp_dir) / "target"
                (from_path).mkdir()
                (to_path).mkdir()

                # Create .git directories
                (from_path / ".git").mkdir()
                (to_path / ".git").mkdir()

                result = await manager.switch_worktree_context(from_path, to_path)

                assert result["success"] is True
                assert result["context_preserved"] is False
                assert "session preservation failed" in result["message"].lower()
                mock_chdir.assert_called_once_with(to_path)

    @patch("session_mgmt_mcp.worktree_manager.is_git_repository")
    @patch("session_mgmt_mcp.worktree_manager.get_worktree_info")
    async def test_switch_worktree_context_general_exception(
        self, mock_get_worktree_info, mock_is_git_repo
    ):
        """Test switch_worktree_context with general exception."""
        mock_is_git_repo.return_value = True
        mock_get_worktree_info.side_effect = Exception("Unexpected error")

        manager = WorktreeManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            from_path = Path(temp_dir) / "source"
            to_path = Path(temp_dir) / "target"
            (from_path).mkdir()
            (to_path).mkdir()

            # Create .git directories
            (from_path / ".git").mkdir()
            (to_path / ".git").mkdir()

            result = await manager.switch_worktree_context(from_path, to_path)

            assert result["success"] is False
            assert "unexpected error" in result["error"].lower()
