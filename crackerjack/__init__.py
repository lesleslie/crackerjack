"""Mahavishnu workspace package."""

from __future__ import annotations
import subprocess
import asyncio
from pathlib import Path
from typing import Any
from dataclasses import dataclass


@dataclass
class WorktreeInfo:
    """Information about a worktree."""
    repo: str
    path: str
    branch: str
    HEAD: str


class WorkspaceManager:
    """Manages git worktrees for workspace operations."""

    def __init__(self, base_path: str | None = None) -> None:
        """Initialize workspace manager.

        Args:
            base_path: Base path for workspaces (default: ~/.workspaces/)
        """
        if base_path is None:
            base_path = str(Path.home() / ".workspaces")
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def create_workspace(
        self,
        name: str,
        repos: list[str] | None = None,
        branch: str | None = None,
        create_branch: bool = True,
    ) -> dict[str, Any]:
        """Create a new workspace with git worktrees.

        Args:
            name: Workspace name
            repos: List of repository paths to include
            branch: Branch name (default: name)
            create_branch: Whether to create new branch

        Returns:
            Dict with workspace info including 'repos' list
        """
        workspace_path = self.base_path / name
        workspace_path.mkdir(exist_ok=True)

        # Determine branch name
        branch_name = branch or name

        # Create worktrees for repos
        repo_info = []
        if repos:
            for repo_path in repos:
                worktree_path = workspace_path / Path(repo_path).name
                worktree_path.mkdir(exist_ok=True)

                # Create git worktree
                proc = await asyncio.create_subprocess_exec(
                    *["git", "-C", repo_path, "worktree", "add",
                     str(worktree_path), "-b", branch_name],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    raise RuntimeError(f"Failed to create worktree: {stderr.decode()}")

                # Get worktree info
                info = await self._get_worktree_info(repo_path, str(worktree_path))
                repo_info.append(info)

        return {
            "name": name,
            "workspace": str(workspace_path),
            "repos": repo_info,
        }

    async def list_workspaces(
        self,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List all workspaces.

        Args:
            active_only: Only show workspaces with uncommitted changes

        Returns:
            List of workspace info dicts
        """
        workspaces = []

        for workspace_path in self.base_path.iterdir():
            if not workspace_path.is_dir():
                continue

            # Check for worktrees
            worktrees = []
            has_changes = False

            for worktree_path in workspace_path.iterdir():
                if not worktree_path.is_dir():
                    continue

                try:
                    # Get worktree status
                    proc = await asyncio.create_subprocess_exec(
                        *["git", "-C", str(worktree_path), "status", "--porcelain"],
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()
                    status_output = stdout.decode()

                    if status_output.strip():
                        has_changes = True

                    # Get branch info
                    proc = await asyncio.create_subprocess_exec(
                        *["git", "-C", str(worktree_path), "branch", "--show-current"],
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await proc.communicate()
                    branch = stdout.decode().strip()

                    # Get HEAD
                    proc = await asyncio.create_subprocess_exec(
                        *["git", "-C", str(worktree_path), "rev-parse", "HEAD"],
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await proc.communicate()
                    head = stdout.decode().strip()

                    worktrees.append({
                        "path": str(worktree_path),
                        "branch": branch,
                        "HEAD": head[:8],
                    })
                except Exception:
                    pass

            if active_only and not has_changes:
                continue

            ws_info = {
                "name": workspace_path.name,
                "path": str(workspace_path),
                "has_changes": has_changes,
            }

            if worktrees:
                ws_info["worktrees"] = worktrees

            workspaces.append(ws_info)

        return workspaces

    async def get_workspace_info(self, name: str) -> dict[str, Any]:
        """Get detailed information about a workspace.

        Args:
            name: Workspace name

        Returns:
            Dict with workspace details
        """
        workspace_path = self.base_path / name

        if not workspace_path.exists():
            raise ValueError(f"Workspace not found: {name}")

        info = {
            "name": name,
            "path": str(workspace_path),
        }

        # Get worktrees
        worktrees = []
        for worktree_path in workspace_path.iterdir():
            if not worktree_path.is_dir():
                continue

            try:
                proc = await asyncio.create_subprocess_exec(
                    *["git", "-C", str(worktree_path), "branch", "--show-current"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                branch = stdout.decode().strip()

                proc = await asyncio.create_subprocess_exec(
                    *["git", "-C", str(worktree_path), "rev-parse", "HEAD"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                head = stdout.decode().strip()

                worktrees.append({
                    "path": str(worktree_path),
                    "branch": branch,
                    "HEAD": head[:8],
                })
            except Exception:
                pass

        if worktrees:
            info["worktrees"] = worktrees

        return info

    async def remove_workspace(self, name: str, force: bool = False) -> dict[str, Any]:
        """Remove a workspace and its worktrees.

        Args:
            name: Workspace name
            force: Remove even if uncommitted changes exist

        Returns:
            Dict with removal results
        """
        workspace_path = self.base_path / name

        if not workspace_path.exists():
            raise ValueError(f"Workspace not found: {name}")

        removed_repos = []

        # Remove worktrees
        for worktree_path in workspace_path.iterdir():
            if not worktree_path.is_dir():
                continue

            try:
                proc = await asyncio.create_subprocess_exec(
                    *["git", "-C", str(worktree_path), "status", "--porcelain"],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if not force and stdout.decode().strip():
                    raise RuntimeError(f"Worktree has uncommitted changes: {worktree_path}")

                # Remove worktree
                repo_path = str(worktree_path.parent.parent)  # Navigate back to repo

                proc = await asyncio.create_subprocess_exec(
                    *["git", "-C", repo_path, "worktree", "remove", str(worktree_path)],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

                removed_repos.append(str(worktree_path))
            except Exception:
                pass

        # Remove workspace directory
        subprocess.run(["rm", "-rf", str(workspace_path)], check=True)

        return {
            "name": name,
            "removed_repos": removed_repos,
        }

    async def _get_worktree_info(
        self,
        repo_path: str,
        worktree_path: str,
    ) -> WorktreeInfo:
        """Get information about a worktree.

        Args:
            repo_path: Path to git repository
            worktree_path: Path to worktree

        Returns:
            WorktreeInfo with worktree details
        """
        # Get branch
        proc = await asyncio.create_subprocess_exec(
            *["git", "-C", worktree_path, "branch", "--show-current"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        branch = stdout.decode().strip()

        # Get HEAD
        proc = await asyncio.create_subprocess_exec(
            *["git", "-C", worktree_path, "rev-parse", "HEAD"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        head = stdout.decode().strip()

        return WorktreeInfo(
            repo=repo_path,
            path=worktree_path,
            branch=branch,
            HEAD=head[:8],
        )


def __dir__() -> str:
    """Get workspace package directory."""
    return str(Path(__file__).parent)


def get_manager() -> WorkspaceManager:
    """Get or create workspace manager instance."""
    manager = WorkspaceManager()
    return manager
