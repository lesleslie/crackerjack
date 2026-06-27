"""Multi-tenant context packs (Spec #9).

A ``TenantContextPack`` is a versioned, immutable bundle of per-tenant
context files (voice, icp, positioning, visual_identity). One bundle is
"active" per tenant at any given time; older bundles remain queryable for
forensic recall.

This module ships the Python model + a ``TenantContextPublisher`` interface.
The actual Dhara HTTP substrate at ``/tenants/<id>/context-versions`` is owned
by Workstream C and is currently ``http_blocked`` — the publish / get-active
calls below stub the HTTP path so the interface compiles and tests pass. Once
Workstream C unblocks the route, swap the stub for the real client (no public
API change required).
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import httpx
from mcp.server.fastmcp import Context  # noqa: F401  (placeholder for future use)
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


CONTEXT_FILES: tuple[str, ...] = ("voice", "icp", "positioning", "visual_identity")

DEFAULT_TENANT: str = "default"


# ---------------------------------------------------------------------------
# HTTP client (stub; replaced when Workstream C lands)
# ---------------------------------------------------------------------------


# TODO(Workstream C): replace with the real substrate-bound async client
# once ``/tenants/<tenant_id>/context-versions`` is exposed by Dhara's HTTP
# CRUD surface. Until then, this stub is what tests patch via
# ``_get_http_client``.
_http_stub_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Return the HTTP client used for tenant context CRUD.

    Stub: returns a process-wide httpx.AsyncClient pointed at Dhara's URL.
    Substrate status: ``http_blocked`` for the
    ``/tenants/<tenant_id>/context-versions`` endpoint; once Workstream C
    unblocks the route, the publish / get-active code paths here start
    hitting real storage with no API change.
    """
    global _http_stub_client
    if _http_stub_client is None:
        _http_stub_client = httpx.AsyncClient(
            base_url=os.environ.get("MAHAVISHNU_DHARA_URL", "http://localhost:8683"),
            timeout=httpx.Timeout(5.0),
        )
    return _http_stub_client


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class TenantContextPack(BaseModel):
    """Versioned, immutable tenant context bundle.

    A pack is published atomically (single-active-version per tenant) and
    never mutated post-publish. To "edit" a tenant's context, publish a new
    pack with ``version + 1`` and the changed body.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    content_hash: str = Field(min_length=1)
    body: dict[str, str]
    published_at: datetime
    published_by: str = Field(min_length=1)

    @field_validator("body")
    @classmethod
    def _body_keys_must_be_known_files(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = set(value) - set(CONTEXT_FILES)
        if unknown:
            msg = (
                f"body contains unknown context files: {sorted(unknown)!r}; "
                f"expected only {CONTEXT_FILES!r}"
            )
            raise ValueError(msg)
        return value

    @classmethod
    def with_body(
        cls,
        *,
        tenant_id: str,
        version: int,
        body: dict[str, str],
        published_by: str,
        published_at: datetime | None = None,
    ) -> TenantContextPack:
        """Construct a pack with content_hash derived deterministically from body."""
        content_hash = hashlib.sha256(
            repr(sorted(body.items())).encode()
        ).hexdigest()
        return cls(
            tenant_id=tenant_id,
            version=version,
            content_hash=content_hash,
            body=body,
            published_at=published_at or datetime.now(UTC),
            published_by=published_by,
        )


# ---------------------------------------------------------------------------
# Publisher interface
# ---------------------------------------------------------------------------


@runtime_checkable
class TenantContextPublisher(Protocol):
    """Interface for publishing and retrieving tenant context packs."""

    async def publish(self, pack: TenantContextPack) -> PublishedContextPack: ...

    async def get_active(self, tenant_id: str) -> TenantContextPack | None: ...


class PublishedContextPack(BaseModel):
    """Substrate-side handle returned by ``publish()``.

    Carries the substrate-issued ``version_id`` so callers can address the
    version later (e.g. for read-after-write consistency checks).
    """

    model_config = ConfigDict(frozen=True)

    pack: TenantContextPack
    version_id: str


# ---------------------------------------------------------------------------
# Concrete publisher (HTTP CRUD stub)
# ---------------------------------------------------------------------------


async def publish_context_pack(pack: TenantContextPack) -> PublishedContextPack:
    """Publish a tenant context pack via Dhara's HTTP CRUD surface.

    POST ``/tenants/<tenant_id>/context-versions`` with the pack payload.
    On success, returns a ``PublishedContextPack`` carrying the substrate's
    ``version_id``.

    NOTE: Substrate status is ``http_blocked`` for this endpoint (Workstream C).
    The function below will work end-to-end once that route is exposed; until
    then it raises ``httpx.HTTPStatusError`` from the stub.
    """
    client = _get_http_client()
    resp = await client.post(
        f"/tenants/{pack.tenant_id}/context-versions",
        json={
            "tenant_id": pack.tenant_id,
            "version": pack.version,
            "content_hash": pack.content_hash,
            "body": pack.body,
            "published_at": pack.published_at.isoformat(),
            "published_by": pack.published_by,
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    return PublishedContextPack(pack=pack, version_id=payload["version_id"])


async def get_active_context_pack(tenant_id: str) -> TenantContextPack | None:
    """Return the active context pack for a tenant, or ``None`` if none exists."""
    client = _get_http_client()
    resp = await client.get(f"/tenants/{tenant_id}/active-context-version")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    payload = resp.json()
    return TenantContextPack(
        tenant_id=payload["tenant_id"],
        version=payload["version"],
        content_hash=payload["content_hash"],
        body=payload["body"],
        published_at=datetime.fromisoformat(payload["published_at"]),
        published_by=payload["published_by"],
    )


# ---------------------------------------------------------------------------
# Tenant resolution
# ---------------------------------------------------------------------------


def get_default_tenant() -> str:
    """Return the configured default tenant id.

    Reads ``MAHAVISHNU_DEFAULT_TENANT``; falls back to ``DEFAULT_TENANT``.
    """
    return os.environ.get("MAHAVISHNU_DEFAULT_TENANT", DEFAULT_TENANT)


def resolve_tenant_id(tenant_id: str | None) -> str:
    """Return ``tenant_id`` if provided, otherwise the configured default.

    Used by per-request middleware to map an absent ``X-Tenant-Id`` header
    onto the operator-configured default tenant.
    """
    if tenant_id:
        return tenant_id
    return get_default_tenant()


__all__ = [
    "CONTEXT_FILES",
    "DEFAULT_TENANT",
    "PublishedContextPack",
    "TenantContextPack",
    "TenantContextPublisher",
    "get_active_context_pack",
    "get_default_tenant",
    "publish_context_pack",
    "resolve_tenant_id",
]