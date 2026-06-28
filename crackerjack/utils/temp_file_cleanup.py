import glob
import logging
from contextlib import suppress
from pathlib import Path

logger = logging.getLogger(__name__)


TEMP_FILE_PATTERNS = [
    "/tmp/complexipy_results_*.json",
    "/tmp/gitleaks-report.json",
    "/tmp/ruff_output.json",
]


PROJECT_ROOT_TEMP_PATTERNS = [
    # Complexipy may write to project root when --output is not specified.
    # Phase O: ensure these don't accumulate or get accidentally committed.
    "complexipy*.json",
]


def cleanup_temp_files() -> int:
    cleaned_count = 0

    for pattern in TEMP_FILE_PATTERNS:
        if not pattern.startswith("/tmp/"):
            continue

        files = glob.glob(pattern)
        for file_path in files:
            try:
                Path(file_path).unlink()
                cleaned_count += 1
                logger.debug(f"Cleaned up temporary file: {file_path}")
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path}: {e}")

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} temporary tool output files")

    return cleaned_count


def cleanup_project_root_temp_files(project_root: Path | None = None) -> int:
    """Clean up tool-output files that landed in the project root.

    Some tools (notably complexipy without --output) write to the current
    working directory. These shouldn't be committed; this utility removes
    them so they don't accumulate or trigger ``check-added-large-files``.

    Args:
        project_root: Directory to clean. Defaults to ``Path.cwd()``.

    Returns:
        Number of files removed.
    """
    if project_root is None:
        project_root = Path.cwd()

    cleaned_count = 0
    for pattern in PROJECT_ROOT_TEMP_PATTERNS:
        for file_path in project_root.glob(pattern):
            try:
                file_path.unlink()
                cleaned_count += 1
                logger.debug(f"Cleaned up project-root temp file: {file_path}")
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path}: {e}")

    return cleaned_count


def cleanup_all_temp_outputs(project_root: Path | None = None) -> int:
    """Clean up both /tmp/ and project-root tool outputs."""
    return cleanup_temp_files() + cleanup_project_root_temp_files(project_root)


def get_temp_file_size() -> int:
    total_size = 0

    for pattern in TEMP_FILE_PATTERNS:
        if not pattern.startswith("/tmp/"):
            continue

        files = glob.glob(pattern)
        for file_path in files:
            with suppress(FileNotFoundError, OSError):
                total_size += Path(file_path).stat().st_size

    return total_size


def cleanup_old_complexipy_files(max_age_hours: int = 24) -> int:
    import time

    cleaned_count = 0
    max_age_seconds = max_age_hours * 3600
    current_time = time.time()

    pattern = "/tmp/complexipy_results_*.json"

    for file_path in glob.glob(pattern):
        try:
            path = Path(file_path)
            file_age = current_time - path.stat().st_mtime
            if file_age > max_age_seconds:
                path.unlink()
                cleaned_count += 1
                logger.debug(f"Cleaned up old complexipy file: {file_path}")
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Failed to clean up old file {file_path}: {e}")

    return cleaned_count
