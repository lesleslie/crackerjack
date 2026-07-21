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
    def source(self) -> str:
        return "env:UV_PUBLISH_TOKEN"


class _KeyringPyPIAuth(PyPIAuth):
    def source(self) -> str:
        return "keyring"


class EnvVarAuthProvider:
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
    name = "Keyring storage"

    def is_available(self) -> bool:

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
