
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import httpx
from mcp.server.fastmcp import Context # noqa: F401 (placeholder for future use)
from pydantic import BaseModel, ConfigDict, Field, field_validator


CONTEXT_FILES: tuple[str, ...] = ("voice", "icp", "positioning", "visual_identity")

DEFAULT_TENANT: str = "default"


# TODO(Workstream C): replace with the real substrate-bound async client


_http_stub_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_stub_client
    if _http_stub_client is None:
        _http_stub_client = httpx.AsyncClient(
            base_url=os.environ.get("MAHAVISHNU_DHARA_URL", "http://localhost: 8683"),
            timeout=httpx.Timeout(5.0),
        )
    return _http_stub_client


class TenantContextPack(BaseModel):

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
        content_hash = hashlib.sha256(repr(sorted(body.items())).encode()).hexdigest()
        return cls(
            tenant_id=tenant_id,
            version=version,
            content_hash=content_hash,
            body=body,
            published_at=published_at or datetime.now(UTC),
            published_by=published_by,
        )


@runtime_checkable
class TenantContextPublisher(Protocol):

    async def publish(self, pack: TenantContextPack) -> PublishedContextPack: ...

    async def get_active(self, tenant_id: str) -> TenantContextPack | None: ...


class PublishedContextPack(BaseModel):

    model_config = ConfigDict(frozen=True)

    pack: TenantContextPack
    version_id: str


async def publish_context_pack(pack: TenantContextPack) -> PublishedContextPack:
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


def get_default_tenant() -> str:
    return os.environ.get("MAHAVISHNU_DEFAULT_TENANT", DEFAULT_TENANT)


def resolve_tenant_id(tenant_id: str | None) -> str:
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
