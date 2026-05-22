from __future__ import annotations

import logging
import os
from types import SimpleNamespace
from typing import Any

import jwt as pyjwt
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.permissions import Permission

logger = logging.getLogger(__name__)

_DEV_SECRET = "crackerjack-dev-secret-for-local-auth-flow-0123456789"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def get_auth_config() -> AuthConfig:
    return AuthConfig(
        service_name="crackerjack",
        secret_env_var="CRACKERJACK_JWT_SECRET",
    )


def _is_auth_enabled() -> bool:
    value = os.environ.get("CRACKERJACK_AUTH_ENABLED", "").strip().lower()
    return value in _TRUE_VALUES


def _configured_secret() -> str | None:
    return os.environ.get("CRACKERJACK_JWT_SECRET") or os.environ.get(
        "BODAI_SHARED_SECRET"
    )


def _token_secret() -> str:
    configured = _configured_secret()
    return configured if _is_auth_enabled() and configured else _DEV_SECRET


def _normalize_permission(permission: str) -> Permission | None:
    raw = permission.strip().lower()
    candidates = [raw]
    if raw.startswith("crackerjack:"):
        candidates.append(raw.removeprefix("crackerjack:").strip())
    if raw.startswith("crackerjack "):
        candidates.append(raw.removeprefix("crackerjack").strip(": "))
    if ":" in raw:
        candidates.append(raw.split(":")[-1].strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return Permission(candidate)
        except ValueError:
            continue
    return None


def get_authenticator() -> Any:
    if not _is_auth_enabled():
        return None
    secret = _configured_secret()
    if not secret:
        return None
    return SimpleNamespace(secret=secret)


def generate_token(user_id: str, permissions: list[str] | None = None) -> str:
    secret = _token_secret()
    perms: list[Permission] = []
    for p in permissions or ["read"]:
        normalized = _normalize_permission(p)
        if normalized is None:
            logger.warning("Unknown permission %r ignored", p)
            continue
        perms.append(normalized)
    if not perms:
        raise ValueError(f"No valid permissions in {permissions!r}")
    payload = {
        "sub": user_id,
        "iss": "crackerjack",
        "aud": "crackerjack",
        "scopes": [p.value for p in perms],
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def verify_token(token: str) -> dict[str, Any] | None:
    secret = _token_secret()
    try:
        raw = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="crackerjack",
            issuer="crackerjack",
        )
        raw = raw.copy()
        raw.setdefault("user_id", raw.get("sub") or raw.get("iss") or "anonymous")
        raw.setdefault("permissions", [scope for scope in raw.get("scopes", [])])
        return raw
    except Exception as exc:
        logger.warning("token verification failed: %s", exc)
        return None
