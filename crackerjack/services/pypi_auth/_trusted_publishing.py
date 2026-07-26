from __future__ import annotations

import logging
import os

from crackerjack.services.pypi_auth._auth import PyPIAuth, _TrustedPublishingSentinel

logger = logging.getLogger(__name__)


class TrustedPublishingProvider:
    name = "Trusted Publishing (OIDC)"

    def is_available(self) -> bool:
        return os.getenv("GITHUB_ACTIONS") == "true" and bool(
            os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
        )

    def resolve(self) -> PyPIAuth | None:
        if not self.is_available():
            return None
        logger.debug(
            "Detected Trusted Publishing: GITHUB_ACTIONS + ACTIONS_ID_TOKEN_REQUEST_TOKEN"
        )
        return _TrustedPublishingSentinel()
