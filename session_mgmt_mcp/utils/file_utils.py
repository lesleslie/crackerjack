#!/usr/bin/env python3
"""File and directory utilities for session management.

This module provides file system operations following crackerjack
architecture patterns with single responsibility principle.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _cleanup_session_logs() -> str:
    """Clean up old session log files, keeping recent ones."""
    claude_dir = Path.home() / ".claude" / "logs"
    if not claude_dir.exists():
        return "📝 No log directory found"

    log_files = list(claude_dir.glob("session_management_*.log"))
    if not log_files:
        return "📝 No session log files found"

    # Keep logs from last 10 days
    cutoff_date = datetime.now(UTC) - timedelta(days=10)
    cleaned_count = 0

    for log_file in log_files:
        try:
            # Extract date from filename: session_management_YYYYMMDD.log
            date_str = log_file.stem.split("_")[-1]  # Gets the YYYYMMDD part
            if len(date_str) == 8 and date_str.isdigit():
                log_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=UTC)
                if log_date < cutoff_date:
                    log_file.unlink()
                    cleaned_count += 1
        except (ValueError, OSError):
            # Skip files with invalid names or permission issues
            continue

    remaining_count = len(list(claude_dir.glob("session_management_*.log")))
    return f"📝 Cleaned {cleaned_count} old log files, {remaining_count} retained"


def _cleanup_temp_files(current_dir: Path) -> str:
    """Clean up temporary files and caches."""
    cleanup_patterns = [
        "**/.DS_Store",
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        "**/node_modules/.cache",
        "**/.pytest_cache",
        "**/coverage.xml",
        "**/.coverage",
        "**/htmlcov",
        "**/tmp_*",
        "**/.tmp",
        "**/temp_*",
    ]

    cleaned_items = []
    total_size_mb = 0

    for pattern in cleanup_patterns:
        try:
            for item in current_dir.glob(pattern):
                if item.exists():
                    size_mb = 0
                    if item.is_file():
                        size_mb = item.stat().st_size / (1024 * 1024)
                        item.unlink()
                        cleaned_items.append(f"🗑️ {item.name}")
                    elif item.is_dir():
                        # Calculate directory size
                        try:
                            for subitem in item.rglob("*"):
                                if subitem.is_file():
                                    size_mb += subitem.stat().st_size / (1024 * 1024)
                        except (PermissionError, OSError):
                            pass  # Skip if we can't read the directory

                        shutil.rmtree(item, ignore_errors=True)
                        cleaned_items.append(f"📁 {item.name}/")

                    total_size_mb += size_mb
        except (PermissionError, OSError):
            # Skip patterns we can't access
            continue

    if not cleaned_items:
        return "🧹 No temporary files found to clean"

    # Limit display to avoid overwhelming output
    display_items = cleaned_items[:10]
    if len(cleaned_items) > 10:
        display_items.append(f"... and {len(cleaned_items) - 10} more items")

    return (
        f"🧹 Cleaned {len(cleaned_items)} items ({total_size_mb:.1f} MB): "
        + ", ".join(display_items)
    )


def _cleanup_uv_cache() -> str:
    """Clean up UV package manager cache to free space."""
    try:
        # Run uv cache clean command
        result = subprocess.run(
            ["uv", "cache", "clean"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            # Parse output for size information
            output = result.stdout.strip()
            if "freed" in output.lower() or "removed" in output.lower():
                return f"📦 UV cache cleaned: {output}"
            return "📦 UV cache cleaned successfully"
        return f"⚠️ UV cache clean failed: {result.stderr.strip()}"

    except FileNotFoundError:
        return "⚠️ UV not found, skipping cache cleanup"
    except Exception as e:
        return f"⚠️ UV cache cleanup error: {e}"


def validate_claude_directory() -> dict[str, Any]:
    """Validate and set up Claude directory structure."""
    claude_dir = Path.home() / ".claude"

    results = {
        "success": True,
        "directory": str(claude_dir),
        "created": False,
        "structure": {},
        "permissions": "ok",
        "size_mb": 0.0,
    }

    try:
        # Create main directory if it doesn't exist
        if not claude_dir.exists():
            claude_dir.mkdir(parents=True, exist_ok=True)
            results["created"] = True

        # Create subdirectories
        subdirs = ["logs", "data", "temp", "backups"]
        for subdir in subdirs:
            subdir_path = claude_dir / subdir
            subdir_path.mkdir(exist_ok=True)
            results["structure"][subdir] = {
                "exists": True,
                "writable": os.access(subdir_path, os.W_OK),
                "files": len(list(subdir_path.iterdir()))
                if subdir_path.exists()
                else 0,
            }

        # Calculate total size
        total_size = 0
        for item in claude_dir.rglob("*"):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                except (OSError, PermissionError):
                    continue

        results["size_mb"] = total_size / (1024 * 1024)

        # Check permissions
        if not os.access(claude_dir, os.W_OK):
            results["permissions"] = "readonly"
            results["success"] = False

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)

    return results
