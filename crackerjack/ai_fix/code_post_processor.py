from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


RUFF_FORMAT_TIMEOUT_S: int = 30


def wrap_long_lines(
    code: str,
    max_length: int = 88,
    file_path: Path | None = None,
) -> str:
    if file_path is not None and file_path.suffix != ".py":
        return code

    if not any(len(line) > max_length for line in code.splitlines()):
        return code

    if shutil.which("ruff") is None:
        logger.debug("wrap_long_lines: ruff not on PATH; passing through")
        return code

    cmd = [
        "ruff",
        "format",
        "--line-length",
        str(max_length),
        "--stdin-filename",
        "<post_processor>",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=code,
            capture_output=True,
            text=True,
            timeout=RUFF_FORMAT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(f"wrap_long_lines: ruff format failed: {exc}; passing through")
        return code

    if proc.returncode != 0:
        logger.warning(
            f"wrap_long_lines: ruff format exited {proc.returncode}; "
            f"passing through. stderr: {proc.stderr[:200]}"
        )
        return code

    return proc.stdout


__all__ = ["RUFF_FORMAT_TIMEOUT_S", "wrap_long_lines"]
