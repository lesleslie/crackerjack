"""Utility functions for cleaning up temporary files created by quality tools.

Some tools (complexipy, gitleaks) save JSON output to temporary files
instead of stdout. This module provides utilities to ensure these files
are cleaned up properly.
"""

import logging
import os
import glob

logger = logging.getLogger(__name__)


# Patterns for temporary files created by our tools
TEMP_FILE_PATTERNS = [
    "/tmp/complexipy_results_*.json",  # complexipy JSON output
    "/tmp/gitleaks-report.json",  # gitleaks JSON output
    "/tmp/ruff_output.json",  # If we save ruff output
    "complexipy_results_*.json",  # Also check in project directory
]


def cleanup_temp_files() -> int:
    """Clean up all temporary files created by quality tools.

    This function should be called:
    1. At the start of a crackerjack run (to clean up any leftover files)
    2. At the end of a crackerjack run (final cleanup as failsafe)
    3. After parsing individual files (immediate cleanup)

    Returns:
        Number of files cleaned up
    """
    cleaned_count = 0

    # Clean files in /tmp
    for pattern in TEMP_FILE_PATTERNS:
        if not pattern.startswith("/tmp/"):
            # Only process patterns that start with /tmp
            continue

        files = glob.glob(pattern)
        for file_path in files:
            try:
                os.remove(file_path)
                cleaned_count += 1
                logger.debug(f"Cleaned up temporary file: {file_path}")
            except FileNotFoundError:
                # File already gone, that's fine
                pass
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path}: {e}")

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} temporary tool output files")

    return cleaned_count


def get_temp_file_size() -> int:
    """Get total size of all temporary files.

    Returns:
        Total size in bytes
    """
    total_size = 0

    for pattern in TEMP_FILE_PATTERNS:
        if not pattern.startswith("/tmp/"):
            continue

        files = glob.glob(pattern)
        for file_path in files:
            try:
                total_size += os.path.getsize(file_path)
            except (FileNotFoundError, OSError):
                pass

    return total_size


def cleanup_old_complexipy_files(max_age_hours: int = 24) -> int:
    """Clean up old complexipy JSON files that may have been left behind.

    Args:
        max_age_hours: Maximum age in hours for files to keep

    Returns:
        Number of files cleaned up
    """
    import time

    cleaned_count = 0
    max_age_seconds = max_age_hours * 3600
    current_time = time.time()

    # complexipy creates files like: complexipy_results_YYYY_MM_DD__HH-MM-SS.json
    pattern = "/tmp/complexipy_results_*.json"

    for file_path in glob.glob(pattern):
        try:
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > max_age_seconds:
                os.remove(file_path)
                cleaned_count += 1
                logger.debug(f"Cleaned up old complexipy file: {file_path}")
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Failed to clean up old file {file_path}: {e}")

    return cleaned_count
