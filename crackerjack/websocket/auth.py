from __future__ import annotations

import logging
from typing import Any

from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import create_service_token
from mcp_common.auth.core import verify_token as _verify_token
from mcp_common.auth.exceptions import AuthError
from mcp_common.auth.permissions import Permission

logger = logging.getLogger(__name__)

_config: AuthConfig | None = None


def get_auth_config() -> AuthConfig:
    global _config
    if _config is None:
        _config = AuthConfig(
            service_name="crackerjack",
            secret_env_var="CRACKERJACK_JWT_SECRET",
        )
    return _config


def get_authenticator() -> Any:
    return None


def generate_token(user_id: str, permissions: list[str] | None = None) -> str:
    cfg = get_auth_config()
    if not cfg.enabled:
        return ""
    perms: list[Permission] = []
    for p in permissions or ["read"]:
        try:
            perms.append(Permission(p))
        except ValueError:
            logger.warning("Unknown permission %r ignored", p)
    if not perms:
        raise ValueError(f"No valid permissions in {permissions!r}")
    return create_service_token(
        secret=cfg.secret,
        issuer="crackerjack",
        audience="crackerjack",
        permissions=perms,
    )


def verify_token(token: str) -> dict[str, Any] | None:
    cfg = get_auth_config()
    if not cfg.enabled:
        return {"user_id": "anonymous", "auth": "disabled"}
    try:
        payload = _verify_token(
            token, secret=cfg.secret, expected_audience="crackerjack"
        )
        return payload.raw
    except AuthError as exc:
        logger.warning("token verification failed: %s", exc)
        return None
