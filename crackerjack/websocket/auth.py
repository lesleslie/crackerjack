from __future__ import annotations

import logging
import os

from mcp_common.websocket.auth import WebSocketAuthenticator

logger = logging.getLogger(__name__)


JWT_SECRET = os.getenv("CRACKERJACK_JWT_SECRET", "dev-secret-change-in-production")


TOKEN_EXPIRY = int(os.getenv("CRACKERJACK_TOKEN_EXPIRY", "3600"))


AUTH_ENABLED = os.getenv("CRACKERJACK_AUTH_ENABLED", "false").lower() == "true"


def get_authenticator() -> WebSocketAuthenticator | None:
    if not AUTH_ENABLED:
        logger.info("WebSocket authentication disabled (development mode)")
        return None

    if JWT_SECRET == "dev-secret-change-in-production":
        logger.warning(
            "Using default JWT secret - please set CRACKERJACK_JWT_SECRET "
            "environment variable in production"
        )

    return WebSocketAuthenticator(
        secret=JWT_SECRET,
        algorithm="HS256",
        token_expiry=TOKEN_EXPIRY,
    )


def generate_token(user_id: str, permissions: list[str] | None = None) -> str:
    authenticator = get_authenticator()
    if authenticator is None:
        authenticator = WebSocketAuthenticator(
            secret=JWT_SECRET,
            algorithm="HS256",
            token_expiry=TOKEN_EXPIRY,
        )

    return authenticator.create_token(
        {
            "user_id": user_id,
            "permissions": permissions or ["read"],
        }
    )


def verify_token(token: str) -> dict[str, object] | None:
    authenticator = get_authenticator()
    if authenticator is None:
        authenticator = WebSocketAuthenticator(
            secret=JWT_SECRET,
            algorithm="HS256",
            token_expiry=TOKEN_EXPIRY,
        )

    return authenticator.verify_token(token)
