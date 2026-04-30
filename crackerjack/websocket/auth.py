from __future__ import annotations

import logging
from typing import Any

from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import create_service_token, verify_token as _verify_token
from mcp_common.auth.permissions import Permission

logger = logging.getLogger(__name__)

_config: AuthConfig | None = None


def get_auth_config() -> AuthConfig:
    """Get or initialize the authentication configuration.

    Returns:
        AuthConfig: The authentication configuration for Crackerjack.
    """
    global _config
    if _config is None:
        _config = AuthConfig(
            service_name="crackerjack",
            secret_env_var="CRACKERJACK_JWT_SECRET",
        )
    return _config


def get_authenticator() -> Any:
    """Get the authenticator (backward compatibility shim).

    Returns:
        None: Always returns None as authentication is now handled via mcp_common.auth.

    Note:
        This function is kept for backward compatibility with existing code that imports it.
        The actual authentication logic is in get_auth_config(), generate_token(), and verify_token().
    """
    return None


def generate_token(user_id: str, permissions: list[str] | None = None) -> str:
    """Generate a JWT token for WebSocket authentication.

    Args:
        user_id: The user identifier to embed in the token.
        permissions: List of permission strings. Defaults to ["read"].

    Returns:
        str: A signed JWT token.
    """
    cfg = get_auth_config()
    perms = [
        Permission(p)
        for p in (permissions or ["read"])
        if p in Permission._value2member_map_
    ]
    return create_service_token(
        secret=cfg.secret,
        issuer="crackerjack",
        audience="crackerjack",
        permissions=perms,
    )


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return its payload.

    Args:
        token: The JWT token to verify.

    Returns:
        dict[str, Any] | None: The token payload if valid, None if invalid or auth is disabled.
    """
    cfg = get_auth_config()
    if not cfg.enabled:
        return {"user_id": "anonymous", "auth": "disabled"}
    try:
        payload = _verify_token(token, secret=cfg.secret, expected_audience="crackerjack")
        return payload.raw
    except Exception as exc:
        logger.warning("token verification failed: %s", exc)
        return None
