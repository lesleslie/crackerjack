#!/usr/bin/env python3
"""Git operation utilities for session management.

This module provides Git-related functionality following crackerjack
architecture patterns with single responsibility principle.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _parse_git_status(status_lines: list[str]) -> tuple[list[str], list[str]]:
    """Parse git status output into staged and untracked files."""
    staged_files = []
    untracked_files = []

    for line in status_lines:
        if line.startswith(("A ", "M ", "D ")):
            staged_files.append(line[3:])  # Remove status prefix
        elif line.startswith("?? "):
            untracked_files.append(line[3:])  # Remove ?? prefix

    return staged_files, untracked_files


def _format_untracked_files(untracked_files: list[str]) -> list[str]:
    """Format untracked files for display."""
    if not untracked_files:
        return ["✅ No untracked files"]

    formatted = ["📁 Untracked Files:"]
    for file in untracked_files[:10]:  # Limit display
        formatted.append(f"   • {file}")

    if len(untracked_files) > 10:
        formatted.append(f"   ... and {len(untracked_files) - 10} more files")

    return formatted


def _stage_and_commit_files(
    current_dir: Path,
    commit_message: str,
    files_to_stage: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Stage files and create commit with given message."""
    output = []

    try:
        # Stage files
        if files_to_stage:
            for file_path in files_to_stage:
                stage_cmd = ["git", "add", str(file_path)]
                result = subprocess.run(
                    stage_cmd,
                    cwd=current_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    output.append(
                        f"⚠️ Failed to stage {file_path}: {result.stderr.strip()}"
                    )
        else:
            # Stage all changes
            stage_cmd = ["git", "add", "-A"]
            result = subprocess.run(
                stage_cmd,
                cwd=current_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                output.append(f"⚠️ Failed to stage changes: {result.stderr.strip()}")
                return False, output

        # Create commit
        commit_cmd = ["git", "commit", "-m", commit_message]
        result = subprocess.run(
            commit_cmd,
            cwd=current_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            output.append(f"✅ Committed changes: {commit_message}")
            return True, output
        output.append(f"⚠️ Commit failed: {result.stderr.strip()}")
        return False, output

    except Exception as e:
        output.append(f"❌ Git operation error: {e}")
        return False, output


def _optimize_git_repository(current_dir: Path) -> list[str]:
    """Optimize Git repository with garbage collection and pruning."""
    optimization_results = []

    try:
        # Git garbage collection
        gc_cmd = ["git", "gc", "--auto"]
        result = subprocess.run(
            gc_cmd,
            cwd=current_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            optimization_results.append("🗑️ Git garbage collection completed")
        else:
            optimization_results.append(f"⚠️ Git gc failed: {result.stderr.strip()}")

        # Prune remote tracking branches
        prune_cmd = ["git", "remote", "prune", "origin"]
        result = subprocess.run(
            prune_cmd,
            cwd=current_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            optimization_results.append("🌿 Pruned remote tracking branches")
        else:
            # Remote prune failure is non-critical
            optimization_results.append(
                "ℹ️ Remote pruning skipped (no remote or access issues)"
            )

    except Exception as e:
        optimization_results.append(f"⚠️ Git optimization error: {e}")

    return optimization_results
