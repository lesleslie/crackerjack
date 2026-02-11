"""WebSocket authentication configuration for Crackerjack.

This module provides JWT authentication configuration for the Crackerjack
WebSocket server, using environment variables for secure credential management.
"""

from __future__ import annotations

import os
import logging

from mcp_common.websocket.auth import WebSocketAuthenticator

logger = logging.getLogger(__name__)


# Get JWT secret from environment
JWT_SECRET = os.getenv("CRACKERJACK_JWT_SECRET", "dev-secret-change-in-production")

# Get token expiry from environment (default: 1 hour)
TOKEN_EXPIRY = int(os.getenv("CRACKERJACK_TOKEN_EXPIRY", "3600"))

# Check if authentication is enabled
AUTH_ENABLED = os.getenv("CRACKERJACK_AUTH_ENABLED", "false").lower() == "true"


def get_authenticator() -> WebSocketAuthenticator | None:
    """Get configured WebSocket authenticator.

    Returns:
        WebSocketAuthenticator instance if JWT secret is configured,
        None for development mode
    """
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
    """Generate a JWT token for testing or development.

    Args:
        user_id: User identifier
        permissions: List of permissions (default: ["read"])

    Returns:
        JWT token string

    Example:
        >>> token = generate_token("user123", ["read", "write"])
        >>> print(f"Token: {token}")
    """
    authenticator = get_authenticator()
    if authenticator is None:
        # Development mode - create a temporary authenticator
        authenticator = WebSocketAuthenticator(
            secret=JWT_SECRET,
            algorithm="HS256",
            token_expiry=TOKEN_EXPIRY,
        )

    return authenticator.create_token({
        "user_id": user_id,
        "permissions": permissions or ["read"],
    })


def verify_token(token: str) -> dict[str, object] | None:
    """Verify a JWT token.

    Args:
        token: JWT token to verify

    Returns:
        Token payload if valid, None otherwise
    """
    authenticator = get_authenticator()
    if authenticator is None:
        # Development mode - create a temporary authenticator
        authenticator = WebSocketAuthenticator(
            secret=JWT_SECRET,
            algorithm="HS256",
            token_expiry=TOKEN_EXPIRY,
        )

    return authenticator.verify_token(token)
