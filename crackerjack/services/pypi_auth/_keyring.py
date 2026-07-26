from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


PYPI_KEYRING_URL = "https://upload.pypi.org/legacy/"
PYPI_KEYRING_USER = "__token__"


def _keyring_get_raw(url: str, username: str, timeout: int = 10) -> str | None:
    try:
        result = subprocess.run(
            ["keyring", "get", url, username],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        logger.debug("keyring CLI not installed")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("keyring get timed out after %ds", timeout)
        return None

    if result.returncode != 0:
        logger.debug(
            "keyring get failed (exit %d): %s",
            result.returncode,
            result.stderr.strip()[:200],
        )
        return None

    stripped = result.stdout.strip()
    return stripped or None
