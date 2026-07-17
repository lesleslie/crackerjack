from __future__ import annotations

import logging
import os

from crackerjack.services.pypi_auth._auth import PyPIAuth
from crackerjack.services.pypi_auth._keyring import (
    PYPI_KEYRING_URL,
    PYPI_KEYRING_USER,
    _keyring_get_raw,
)

logger = logging.getLogger(__name__)


class _EnvVarPyPIAuth(PyPIAuth):
    """PyPIAuth labeled with ``env:UV_PUBLISH_TOKEN`` provenance."""

    def source(self) -> str:
        return "env:UV_PUBLISH_TOKEN"


class _KeyringPyPIAuth(PyPIAuth):
    """PyPIAuth labeled with ``keyring`` provenance."""

    def source(self) -> str:
        return "keyring"


class EnvVarAuthProvider:
    """PyPI auth from ``UV_PUBLISH_TOKEN`` environment variable."""

    name = "UV_PUBLISH_TOKEN env var"

    def is_available(self) -> bool:
        return bool(os.getenv("UV_PUBLISH_TOKEN"))

    def resolve(self) -> PyPIAuth | None:
        value = os.getenv("UV_PUBLISH_TOKEN")
        if not value:
            return None
        try:
            return _EnvVarPyPIAuth(value)
        except ValueError:
            logger.warning(
                "UV_PUBLISH_TOKEN is set but malformed (must start with 'pypi-'"
                " and be at least 16 chars). Falling through to next provider.",
            )
            return None


class KeyringAuthProvider:
    """PyPI auth from system keyring via the ``keyring`` CLI."""

    name = "Keyring storage"

    def is_available(self) -> bool:
        # Don't probe the backend in is_available; the cost is non-zero
        # and the actual call happens in resolve() anyway. Always
        # advertise as available so the banner tells the operator it
        # was checked.
        return True

    def resolve(self) -> PyPIAuth | None:
        raw = _keyring_get_raw(PYPI_KEYRING_URL, PYPI_KEYRING_USER)
        if raw is None:
            return None
        try:
            return _KeyringPyPIAuth(raw)
        except ValueError:
            logger.warning(
                "Keyring token at %s has wrong format (expected 'pypi-'"
                " prefix). Re-run: keyring set %s %s",
                PYPI_KEYRING_URL,
                PYPI_KEYRING_URL,
                PYPI_KEYRING_USER,
            )
            return None
