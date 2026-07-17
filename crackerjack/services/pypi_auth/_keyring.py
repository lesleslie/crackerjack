from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

# PyPI's legacy upload URL is the only supported target. Trusted
# publishing uses a different flow that does not go through keyring.
PYPI_KEYRING_URL = "https://upload.pypi.org/legacy/"
PYPI_KEYRING_USER = "__token__"


def _keyring_get_raw(url: str, username: str, timeout: int = 10) -> str | None:
    """Call ``keyring get <url> <username>`` and return the raw token.

    This is the **only** place in crackerjack where a subprocess stdout
    is intentionally NOT fed through :func:`SecurityService.mask_tokens`.
    PyPI tokens are 100+ character strings of base64-ish characters,
    many of which would be wrongly matched by the ``mask_generic_long_token``
    regex and corrupted. By isolating the unmasking to this single
    function, we make accidental re-introduction of the corruption bug
    impossible at any other call site.
    """
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
