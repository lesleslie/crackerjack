from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTEXT_FILES: tuple[str, ...] = ("voice", "icp", "positioning", "visual_identity")

DEFAULT_TENANT: str = "default"


# TODO(Workstream C): the tenant-context HTTP CRUD surface
# (``/tenants/<id>/context-versions``) is owned by Workstream C and has not
# shipped. Until it does, the module-level helpers below stay stubs rather
# than pointing at a store that does not exist.


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
    """Publish a context-pack version to the tenant-context substrate.

    Stub: the tenant-context HTTP CRUD surface has not shipped, so this
    raises loudly rather than writing to a store that does not exist.
    """
    raise NotImplementedError(
        "publish_context_pack is a stub — the tenant-context HTTP CRUD "
        "substrate (/tenants/<id>/context-versions) is owned by Workstream C "
        "and has not shipped."
    )


async def get_active_context_pack(tenant_id: str) -> TenantContextPack | None:
    """Fetch the active context pack for ``tenant_id`` from the substrate.

    Stub: same blocked-surface caveat as :func:`publish_context_pack`.
    """
    raise NotImplementedError(
        "get_active_context_pack is a stub — the tenant-context HTTP CRUD "
        "substrate (/tenants/<id>/active-context-version) is owned by "
        "Workstream C and has not shipped."
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
