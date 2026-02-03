import glob
import logging
import os

logger = logging.getLogger(__name__)


TEMP_FILE_PATTERNS = [
    "/tmp/complexipy_results_*.json",
    "/tmp/gitleaks-report.json",
    "/tmp/ruff_output.json",
    "complexipy_results_*.json",
]


def cleanup_temp_files() -> int:
    cleaned_count = 0

    for pattern in TEMP_FILE_PATTERNS:
        if not pattern.startswith("/tmp/"):
            continue

        files = glob.glob(pattern)
        for file_path in files:
            try:
                os.remove(file_path)
                cleaned_count += 1
                logger.debug(f"Cleaned up temporary file: {file_path}")
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path}: {e}")

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} temporary tool output files")

    return cleaned_count


def get_temp_file_size() -> int:
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
    import time

    cleaned_count = 0
    max_age_seconds = max_age_hours * 3600
    current_time = time.time()

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
