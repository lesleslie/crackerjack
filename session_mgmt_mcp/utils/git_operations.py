#!/usr/bin/env python3
"""Git operations utilities for session management."""

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""

    path: Path
    branch: str
    is_bare: bool = False
    is_detached: bool = False
    is_main_worktree: bool = False
    locked: bool = False
    prunable: bool = False


def is_git_repository(directory) -> bool:
    """Check if the given directory is a git repository or worktree."""
    if isinstance(directory, str):
        directory = Path(directory)
    git_dir = directory / ".git"
    # Check for both main repo (.git directory) and worktree (.git file)
    return git_dir.exists() and (git_dir.is_dir() or git_dir.is_file())


def is_git_worktree(directory: Path) -> bool:
    """Check if the directory is a git worktree (not the main repository)."""
    if isinstance(directory, str):
        directory = Path(directory)
    git_path = directory / ".git"
    # Worktrees have a .git file that points to the actual git directory
    return git_path.exists() and git_path.is_file()


def get_git_root(directory: Path) -> Path | None:
    """Get the root directory of the git repository."""
    if not is_git_repository(directory):
        return None

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=directory,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def get_worktree_info(directory: Path) -> WorktreeInfo | None:
    """Get information about the current worktree."""
    if not is_git_repository(directory):
        return None

    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=directory,
            check=True,
        )
        branch = branch_result.stdout.strip()

        # Check if detached HEAD
        is_detached = False
        if not branch:
            head_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=directory,
                check=True,
            )
            branch = f"HEAD ({head_result.stdout.strip()})"
            is_detached = True

        # Get worktree path (normalized)
        toplevel_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=directory,
            check=True,
        )
        path = Path(toplevel_result.stdout.strip())

        return WorktreeInfo(
            path=path,
            branch=branch,
            is_detached=is_detached,
            is_main_worktree=not is_git_worktree(directory),
        )

    except subprocess.CalledProcessError:
        return None


def _process_worktree_line(line: str, current_worktree: dict) -> None:
    """Process a single line from git worktree list --porcelain output."""
    if line.startswith("worktree "):
        current_worktree["path"] = line[9:]  # Remove 'worktree ' prefix
    elif line.startswith("HEAD "):
        current_worktree["head"] = line[5:]  # Remove 'HEAD ' prefix
    elif line.startswith("branch "):
        current_worktree["branch"] = line[7:]  # Remove 'branch ' prefix
    elif line == "bare":
        current_worktree["bare"] = True
    elif line == "detached":
        current_worktree["detached"] = True
    elif line.startswith("locked"):
        current_worktree["locked"] = True
    elif line == "prunable":
        current_worktree["prunable"] = True


def list_worktrees(directory: Path) -> list[WorktreeInfo]:
    """List all worktrees for the repository."""
    if not is_git_repository(directory):
        return []

    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=directory,
            check=True,
        )

        worktrees = []
        current_worktree = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                if current_worktree:
                    worktrees.append(_parse_worktree_entry(current_worktree))
                    current_worktree = {}
                continue

            _process_worktree_line(line, current_worktree)

        # Handle last worktree if exists
        if current_worktree:
            worktrees.append(_parse_worktree_entry(current_worktree))

        return worktrees

    except subprocess.CalledProcessError:
        return []


def _parse_worktree_entry(entry: dict) -> WorktreeInfo:
    """Parse a single worktree entry from git worktree list output."""
    path = Path(entry.get("path", ""))
    branch = entry.get("branch", entry.get("head", "unknown"))

    # Check if this is the main worktree (bare repos don't have .git file)
    is_main = not (path / ".git").is_file() if path.exists() else False

    return WorktreeInfo(
        path=path,
        branch=branch,
        is_bare=entry.get("bare", False),
        is_detached=entry.get("detached", False),
        is_main_worktree=is_main,
        locked=entry.get("locked", False),
        prunable=entry.get("prunable", False),
    )


def get_git_status(directory: Path) -> tuple[list[str], list[str]]:
    """Get modified and untracked files from git status."""
    if not is_git_repository(directory):
        return [], []

    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=directory,
            check=True,
        )

        status_lines = (
            status_result.stdout.strip().split("\n")
            if status_result.stdout.strip()
            else []
        )

        return _parse_git_status(status_lines)
    except subprocess.CalledProcessError:
        return [], []


def _parse_git_status(status_lines: list[str]) -> tuple[list[str], list[str]]:
    """Parse git status output into modified and untracked files."""
    modified_files = []
    untracked_files = []

    for line in status_lines:
        if line:
            status = line[:2]
            filepath = line[3:]
            if status == "??":
                untracked_files.append(filepath)
            elif status.strip():
                modified_files.append(filepath)

    return modified_files, untracked_files


def stage_files(directory: Path, files: list[str]) -> bool:
    """Stage files for commit."""
    if not is_git_repository(directory) or not files:
        return False

    try:
        for file in files:
            subprocess.run(
                ["git", "add", file],
                cwd=directory,
                capture_output=True,
                check=True,
            )
        return True
    except subprocess.CalledProcessError:
        return False


def get_staged_files(directory: Path) -> list[str]:
    """Get list of staged files."""
    if not is_git_repository(directory):
        return []

    try:
        staged_result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=directory,
            check=True,
        )

        return (
            staged_result.stdout.strip().split("\n")
            if staged_result.stdout.strip()
            else []
        )
    except subprocess.CalledProcessError:
        return []


def create_commit(directory: Path, message: str) -> tuple[bool, str]:
    """Create a git commit with the given message.

    Returns:
        tuple: (success, commit_hash or error_message)

    """
    if not is_git_repository(directory):
        return False, "Not a git repository"

    try:
        subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
            cwd=directory,
            check=True,
        )

        # Get commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=directory,
            check=True,
        )

        commit_hash = hash_result.stdout.strip()[:8]
        return True, commit_hash

    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip() if e.stderr else str(e)


def _add_worktree_context_output(
    worktree_info: WorktreeInfo | None,
    output: list[str],
) -> None:
    """Add worktree context information to output."""
    if worktree_info:
        if worktree_info.is_main_worktree:
            output.append(f"📝 Main repository on branch '{worktree_info.branch}'")
        else:
            output.append(
                f"🌿 Worktree on branch '{worktree_info.branch}' at {worktree_info.path}",
            )


def _create_checkpoint_message(
    project: str,
    quality_score: int,
    worktree_info: WorktreeInfo | None,
) -> str:
    """Create the checkpoint commit message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Enhanced commit message with worktree info
    worktree_suffix = ""
    if worktree_info and not worktree_info.is_main_worktree:
        worktree_suffix = f" [worktree: {worktree_info.branch}]"

    commit_message = (
        f"checkpoint: Session checkpoint - {timestamp}{worktree_suffix}\n\n"
        f"Automatic checkpoint commit via session-management MCP server\n"
        f"Project: {project}\n"
        f"Quality Score: {quality_score}/100"
    )

    if worktree_info:
        commit_message += f"\nBranch: {worktree_info.branch}"
        if not worktree_info.is_main_worktree:
            commit_message += f"\nWorktree: {worktree_info.path}"

    return commit_message


def _handle_staging_and_commit(
    directory: Path,
    modified_files: list[str],
    project: str,
    quality_score: int,
    worktree_info: WorktreeInfo | None,
    output: list[str],
) -> tuple[bool, str]:
    """Handle staging and committing of modified files."""
    if not stage_files(directory, modified_files):
        output.append("⚠️ Failed to stage files")
        return False, "Failed to stage files"

    staged_files = get_staged_files(directory)
    if not staged_files:
        output.append("ℹ️ No staged changes to commit")
        return False, "No staged changes"

    commit_message = _create_checkpoint_message(project, quality_score, worktree_info)
    success, result = create_commit(directory, commit_message)

    if success:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output.append(f"✅ Checkpoint commit created: {result}")
        output.append(f"   Message: checkpoint: Session checkpoint - {timestamp}")
        output.append("   💡 Use 'git reset HEAD~1' to undo if needed")
        return True, result
    output.append(f"⚠️ Commit failed: {result}")
    return False, result


def create_checkpoint_commit(
    directory: Path,
    project: str,
    quality_score: int,
) -> tuple[bool, str, list[str]]:
    """Create an automatic checkpoint commit.

    Returns:
        tuple: (success, commit_hash_or_error, output_messages)

    """
    output = []

    if not is_git_repository(directory):
        output.append("ℹ️ Not a git repository - skipping commit")
        return False, "Not a git repository", output

    try:
        # Get worktree info for enhanced commit messages
        worktree_info = get_worktree_info(directory)
        modified_files, untracked_files = get_git_status(directory)

        if not modified_files and not untracked_files:
            output.append("✅ Working directory is clean - no changes to commit")
            return True, "clean", output

        # Add worktree context to output
        _add_worktree_context_output(worktree_info, output)
        output.append(
            f"📝 Found {len(modified_files)} modified files and {len(untracked_files)} untracked files",
        )

        # Handle untracked files
        if untracked_files:
            output.extend(_format_untracked_files(untracked_files))

        # Stage and commit modified files
        if modified_files:
            success, result = _handle_staging_and_commit(
                directory,
                modified_files,
                project,
                quality_score,
                worktree_info,
                output,
            )
            return success, result, output
        if untracked_files:
            output.append("ℹ️ No staged changes to commit")
            output.append(
                "   💡 Add untracked files with 'git add' if you want to include them",
            )
            return False, "No staged changes", output

    except Exception as e:
        error_msg = f"Git operations error: {e}"
        output.append(f"⚠️ {error_msg}")
        return False, error_msg, output

    return False, "Unexpected error", output


def _format_untracked_files(untracked_files: list[str]) -> list[str]:
    """Format untracked files display."""
    output = []
    output.append("🆕 Untracked files found:")

    for file in untracked_files[:10]:  # Limit to first 10 for display
        output.append(f"   • {file}")

    if len(untracked_files) > 10:
        output.append(f"   ... and {len(untracked_files) - 10} more")

    output.append("⚠️ Please manually review and add untracked files if needed:")
    output.append("   Use: git add <file> for files you want to include")

    return output
