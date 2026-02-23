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
