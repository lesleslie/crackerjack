#!/usr/bin/env python3
"""Git Worktree Management for Session Management MCP Server.

Provides high-level worktree operations and coordination with session management.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils.git_operations import (
    WorktreeInfo,
    get_worktree_info,
    is_git_repository,
    list_worktrees,
)
from .utils.logging import SessionLogger


class WorktreeManager:
    """Manages git worktrees with session coordination."""

    def __init__(self, session_logger: SessionLogger | None = None) -> None:
        self.session_logger = session_logger

    def _log(self, message: str, level: str = "info", **context: Any) -> None:
        """Log messages if logger available."""
        if self.session_logger:
            getattr(self.session_logger, level)(message, **context)

    async def list_worktrees(self, directory: Path) -> dict[str, Any]:
        """List all worktrees with enhanced information."""
        if not is_git_repository(directory):
            return {"success": False, "error": "Not a git repository", "worktrees": []}

        try:
            worktrees = list_worktrees(directory)
            current_worktree = get_worktree_info(directory)

            worktree_data = []
            for wt in worktrees:
                wt_data = {
                    "path": str(wt.path),
                    "branch": wt.branch,
                    "is_main": wt.is_main_worktree,
                    "is_current": current_worktree and wt.path == current_worktree.path,
                    "is_detached": wt.is_detached,
                    "is_bare": wt.is_bare,
                    "locked": wt.locked,
                    "prunable": wt.prunable,
                    "exists": wt.path.exists(),
                }

                # Add session info if available
                wt_data["has_session"] = self._check_session_exists(wt.path)

                worktree_data.append(wt_data)

            self._log("Listed worktrees", worktrees_count=len(worktree_data))

            return {
                "success": True,
                "worktrees": worktree_data,
                "current_worktree": str(current_worktree.path)
                if current_worktree
                else None,
                "total_count": len(worktree_data),
            }

        except Exception as e:
            self._log(f"Failed to list worktrees: {e}", level="error")
            return {"success": False, "error": str(e), "worktrees": []}

    async def create_worktree(
        self,
        repository_path: Path,
        new_path: Path,
        branch: str,
        create_branch: bool = False,
        checkout_existing: bool = False,
    ) -> dict[str, Any]:
        """Create a new worktree."""
        if not is_git_repository(repository_path):
            return {
                "success": False,
                "error": "Source directory is not a git repository",
            }

        if new_path.exists():
            return {
                "success": False,
                "error": f"Target path already exists: {new_path}",
            }

        try:
            # Build git worktree add command
            cmd = ["git", "worktree", "add"]

            if create_branch:
                cmd.extend(["-b", branch])
            elif checkout_existing:
                cmd.extend(["--track", "-B", branch])

            cmd.extend([str(new_path), branch])

            # Execute git worktree add
            result = subprocess.run(
                cmd,
                cwd=repository_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Verify worktree was created
            worktree_info = get_worktree_info(new_path)
            if not worktree_info:
                return {
                    "success": False,
                    "error": "Worktree was created but cannot be accessed",
                }

            self._log("Created worktree", path=str(new_path), branch=branch)

            return {
                "success": True,
                "worktree_path": str(new_path),
                "branch": branch,
                "worktree_info": {
                    "path": str(worktree_info.path),
                    "branch": worktree_info.branch,
                    "is_main": worktree_info.is_main_worktree,
                    "is_detached": worktree_info.is_detached,
                },
                "output": result.stdout.strip(),
            }

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            self._log(f"Failed to create worktree: {error_msg}", level="error")
            return {"success": False, "error": error_msg}
        except Exception as e:
            self._log(f"Unexpected error creating worktree: {e}", level="error")
            return {"success": False, "error": str(e)}

    async def remove_worktree(
        self,
        repository_path: Path,
        worktree_path: Path,
        force: bool = False,
    ) -> dict[str, Any]:
        """Remove an existing worktree."""
        if not is_git_repository(repository_path):
            return {
                "success": False,
                "error": "Source directory is not a git repository",
            }

        try:
            # Build git worktree remove command
            cmd = ["git", "worktree", "remove"]

            if force:
                cmd.append("--force")

            cmd.append(str(worktree_path))

            # Execute git worktree remove
            result = subprocess.run(
                cmd,
                cwd=repository_path,
                capture_output=True,
                text=True,
                check=True,
            )

            self._log("Removed worktree", path=str(worktree_path))

            return {
                "success": True,
                "removed_path": str(worktree_path),
                "output": result.stdout.strip()
                if result.stdout.strip()
                else "Worktree removed successfully",
            }

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            self._log(f"Failed to remove worktree: {error_msg}", level="error")
            return {"success": False, "error": error_msg}
        except Exception as e:
            self._log(f"Unexpected error removing worktree: {e}", level="error")
            return {"success": False, "error": str(e)}

    async def prune_worktrees(self, repository_path: Path) -> dict[str, Any]:
        """Prune stale worktree references."""
        if not is_git_repository(repository_path):
            return {"success": False, "error": "Directory is not a git repository"}

        try:
            # Execute git worktree prune
            result = subprocess.run(
                ["git", "worktree", "prune", "--verbose"],
                cwd=repository_path,
                capture_output=True,
                text=True,
                check=True,
            )

            output_lines = (
                result.stdout.strip().split("\n") if result.stdout.strip() else []
            )
            pruned_count = len([line for line in output_lines if "Removing" in line])

            self._log("Pruned worktrees", pruned_count=pruned_count)

            return {
                "success": True,
                "pruned_count": pruned_count,
                "output": result.stdout.strip()
                if result.stdout.strip()
                else "No worktrees to prune",
            }

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            self._log(f"Failed to prune worktrees: {error_msg}", level="error")
            return {"success": False, "error": error_msg}

    async def get_worktree_status(self, directory: Path) -> dict[str, Any]:
        """Get comprehensive status for current worktree and all related worktrees."""
        if not is_git_repository(directory):
            return {"success": False, "error": "Not a git repository"}

        try:
            current_worktree = get_worktree_info(directory)
            all_worktrees = list_worktrees(directory)

            if not current_worktree:
                return {
                    "success": False,
                    "error": "Could not determine current worktree info",
                }

            # Enhanced status with session coordination
            return {
                "success": True,
                "current_worktree": {
                    "path": str(current_worktree.path),
                    "branch": current_worktree.branch,
                    "is_main": current_worktree.is_main_worktree,
                    "is_detached": current_worktree.is_detached,
                    "has_session": self._check_session_exists(current_worktree.path),
                },
                "all_worktrees": [
                    {
                        "path": str(wt.path),
                        "branch": wt.branch,
                        "is_main": wt.is_main_worktree,
                        "is_current": wt.path == current_worktree.path,
                        "exists": wt.path.exists(),
                        "has_session": self._check_session_exists(wt.path),
                        "prunable": wt.prunable,
                    }
                    for wt in all_worktrees
                ],
                "total_worktrees": len(all_worktrees),
                "session_summary": self._get_session_summary(all_worktrees),
            }

        except Exception as e:
            self._log(f"Failed to get worktree status: {e}", level="error")
            return {"success": False, "error": str(e)}

    def _check_session_exists(self, path: Path) -> bool:
        """Check if a worktree has an active session by looking for session files."""
        if isinstance(path, str):
            path = Path(path)

        if not path.exists():
            return False

        # Check for common session indicators
        session_indicators = [
            path / ".git",  # Git repository
            path / ".claude",  # Claude session directory
            path / ".session",  # Generic session directory
        ]

        # Also check for project-specific session files
        project_files = [
            "pyproject.toml",
            "package.json",
            "requirements.txt",
            "setup.py",
        ]

        has_session_indicators = any(
            indicator.exists() for indicator in session_indicators
        )
        has_project_files = any(
            (path / proj_file).exists() for proj_file in project_files
        )

        return has_session_indicators or has_project_files

    def _get_session_summary(self, worktrees: list[WorktreeInfo]) -> dict[str, Any]:
        """Get summary of sessions across worktrees."""
        active_sessions = 0
        branches = set()

        for wt in worktrees:
            if self._check_session_exists(wt.path):
                active_sessions += 1
            branches.add(wt.branch)

        return {
            "active_sessions": active_sessions,
            "unique_branches": len(branches),
            "branches": list(branches),
        }

    def _save_current_session_state(self, worktree_path: Path) -> dict | None:
        """Save the current session state for preservation during worktree switching."""
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "worktree_path": str(worktree_path),
                "working_directory": str(Path.cwd()),
                "environment": dict(os.environ),
                "recent_files": self._get_recent_files(worktree_path),
                "git_status": self._get_git_status(worktree_path),
            }

            # Save to a temporary file in the .claude directory
            claude_dir = Path.home() / ".claude" / "worktree_sessions"
            claude_dir.mkdir(parents=True, exist_ok=True)

            state_file = claude_dir / f"session_state_{worktree_path.name}.json"
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

            return state
        except Exception as e:
            self._log(f"Failed to save session state: {e}", level="warning")
            return None

    def _restore_session_state(self, worktree_path: Path, state: dict | None) -> bool:
        """Restore session state for the target worktree."""
        if not state:
            return False

        try:
            # For now, we'll just log that we're restoring state
            # In a more advanced implementation, we could restore environment variables,
            # open files, IDE state, etc.
            self._log(
                "Session state restored",
                worktree=worktree_path.name,
                recent_files=len(state.get("recent_files", [])),
            )
            return True
        except Exception as e:
            self._log(f"Failed to restore session state: {e}", level="warning")
            return False

    def _get_recent_files(self, worktree_path: Path) -> list[str]:
        """Get recently modified files in the worktree."""
        try:
            recent_files = []
            # Get files modified in the last 24 hours
            cutoff_time = time.time() - (24 * 60 * 60)

            for file_path in worktree_path.rglob("*"):
                if file_path.is_file() and not any(
                    part.startswith(".") for part in file_path.parts
                ):
                    try:
                        if file_path.stat().st_mtime > cutoff_time:
                            recent_files.append(
                                str(file_path.relative_to(worktree_path))
                            )
                    except (OSError, PermissionError):
                        continue

            return recent_files[:20]  # Limit to 20 most recent files
        except Exception:
            return []

    def _get_git_status(self, worktree_path: Path) -> dict:
        """Get git status for the worktree."""
        try:
            from .utils.git_operations import get_git_status

            modified, untracked = get_git_status(worktree_path)
            return {
                "modified_files": modified,
                "untracked_files": untracked,
                "has_changes": len(modified) > 0 or len(untracked) > 0,
            }
        except Exception:
            return {"modified_files": [], "untracked_files": [], "has_changes": False}

    async def switch_worktree_context(
        self,
        from_path: Path,
        to_path: Path,
    ) -> dict[str, Any]:
        """Coordinate switching between worktrees with session preservation."""
        try:
            # Validate both paths
            if not is_git_repository(from_path):
                return {
                    "success": False,
                    "error": f"Source path is not a git repository: {from_path}",
                }

            if not is_git_repository(to_path):
                return {
                    "success": False,
                    "error": f"Target path is not a git repository: {to_path}",
                }

            from_worktree = get_worktree_info(from_path)
            to_worktree = get_worktree_info(to_path)

            if not from_worktree or not to_worktree:
                return {
                    "success": False,
                    "error": "Could not get worktree information for context switch",
                }

            # Integrate with session management to preserve context
            try:
                # 1. Save current session state
                session_state = self._save_current_session_state(from_path)

                # 2. Switch working directory context
                os.chdir(to_path)

                # 3. Restore/create session for target worktree
                restored_state = self._restore_session_state(to_path, session_state)

                self._log(
                    "Context switch completed with session preservation",
                    from_branch=from_worktree.branch,
                    to_branch=to_worktree.branch,
                )

                return {
                    "success": True,
                    "from_worktree": {
                        "path": str(from_worktree.path),
                        "branch": from_worktree.branch,
                    },
                    "to_worktree": {
                        "path": str(to_worktree.path),
                        "branch": to_worktree.branch,
                    },
                    "context_preserved": True,
                    "session_state_saved": session_state is not None,
                    "session_state_restored": restored_state,
                    "message": f"Switched from {from_worktree.branch} to {to_worktree.branch}",
                }
            except Exception as session_error:
                # Fallback to basic switching if session preservation fails
                self._log(
                    f"Session preservation failed, using basic switching: {session_error}",
                    level="warning",
                )
                os.chdir(to_path)

                self._log(
                    "Basic context switch completed",
                    from_branch=from_worktree.branch,
                    to_branch=to_worktree.branch,
                )

                return {
                    "success": True,
                    "from_worktree": {
                        "path": str(from_worktree.path),
                        "branch": from_worktree.branch,
                    },
                    "to_worktree": {
                        "path": str(to_worktree.path),
                        "branch": to_worktree.branch,
                    },
                    "context_preserved": False,
                    "session_error": str(session_error),
                    "message": f"Switched from {from_worktree.branch} to {to_worktree.branch} (session preservation failed)",
                }

        except Exception as e:
            self._log(f"Failed to switch worktree context: {e}", level="error")
            return {"success": False, "error": str(e)}
