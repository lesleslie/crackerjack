from __future__ import annotations

import logging
import os

from crackerjack.services.pypi_auth._auth import PyPIAuth, _TrustedPublishingSentinel

logger = logging.getLogger(__name__)


class TrustedPublishingProvider:
    """PyPI auth via PyPI's OIDC-based Trusted Publishing flow.

    Today this detects GitHub Actions only. When uv's OIDC support is
    configured for the repo (PyPI project settings → Publishing →
    "Add a new pending publisher" → GitHub), running ``uv publish``
    inside that workflow exchanges the OIDC token for a PyPI upload
    token without ever touching a secret.

    Detection is conservative: we only claim availability when both
    signals (``GITHUB_ACTIONS == "true"`` AND a non-empty
    ``ACTIONS_ID_TOKEN_REQUEST_TOKEN``) are present. Missing either
    means Trusted Publishing isn't configured for this workflow.
    """

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
