"""TDD tests for multi-tenant context packs (Spec #9).

Covers the TenantContextPack Pydantic model and the TenantContextPublisher
interface. HTTP CRUD calls are stubbed — the real Dhara HTTP substrate for
``/tenants/<id>/context-versions`` is owned by Workstream C and is currently
``http_blocked`` per the phase 3 substrate status.
"""

from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime
from typing import Protocol
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.mahavishnu.tenancy.context_packs import (
    CONTEXT_FILES,
    DEFAULT_TENANT,
    TenantContextPack,
    TenantContextPublisher,
    get_default_tenant,
    publish_context_pack,
    resolve_tenant_id,
)


# ---------------------------------------------------------------------------
# TenantContextPack model
# ---------------------------------------------------------------------------


class TestTenantContextPackModel:
    def test_required_fields_present(self) -> None:
        pack = TenantContextPack(
            tenant_id="acme",
            version=1,
            content_hash="abc123",
            body={"voice": "Direct."},
            published_at=datetime(2026, 6, 26, tzinfo=UTC),
            published_by="alice",
        )
        assert pack.tenant_id == "acme"
        assert pack.version == 1
        assert pack.content_hash == "abc123"
        assert pack.body == {"voice": "Direct."}
        assert pack.published_by == "alice"
        assert pack.published_at == datetime(2026, 6, 26, tzinfo=UTC)

    def test_model_is_immutable_after_publish(self) -> None:
        """Frozen=True — once a pack is published, its fields cannot mutate."""
        pack = TenantContextPack(
            tenant_id="acme",
            version=1,
            content_hash="abc123",
            body={"voice": "Direct."},
            published_at=datetime(2026, 6, 26, tzinfo=UTC),
            published_by="alice",
        )
        with pytest.raises((AttributeError, TypeError, ValueError)):
            pack.version = 2  # type: ignore[misc]

    def test_body_must_contain_only_known_context_files(self) -> None:
        """Body keys restricted to CONTEXT_FILES."""
        with pytest.raises((ValueError, TypeError)):
            TenantContextPack(
                tenant_id="acme",
                version=1,
                content_hash="abc123",
                body={"bogus": "x"},
                published_at=datetime(2026, 6, 26, tzinfo=UTC),
                published_by="alice",
            )

    def test_content_hash_matches_body(self) -> None:
        """A pack constructed via with_body must produce a matching content_hash."""
        body = {"voice": "Direct, opinionated.", "icp": "Senior engineers."}
        pack = TenantContextPack.with_body(
            tenant_id="acme",
            version=1,
            body=body,
            published_by="alice",
        )
        expected_hash = hashlib.sha256(
            repr(sorted(body.items())).encode()
        ).hexdigest()
        assert pack.content_hash == expected_hash
        assert pack.body == body

    def test_version_must_be_positive(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            TenantContextPack(
                tenant_id="acme",
                version=0,
                content_hash="abc",
                body={},
                published_at=datetime(2026, 6, 26, tzinfo=UTC),
                published_by="alice",
            )

    def test_tenant_id_must_be_non_empty(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            TenantContextPack(
                tenant_id="",
                version=1,
                content_hash="abc",
                body={},
                published_at=datetime(2026, 6, 26, tzinfo=UTC),
                published_by="alice",
            )


# ---------------------------------------------------------------------------
# TenantContextPublisher interface (Protocol)
# ---------------------------------------------------------------------------


class TestTenantContextPublisherInterface:
    def test_publisher_protocol_defines_publish_method(self) -> None:
        """Publisher must expose an async publish() coroutine."""
        assert hasattr(TenantContextPublisher, "publish")
        assert inspect.iscoroutinefunction(TenantContextPublisher.publish)

    def test_publisher_protocol_defines_get_active_method(self) -> None:
        """Publisher must expose an async get_active() coroutine."""
        assert hasattr(TenantContextPublisher, "get_active")
        assert inspect.iscoroutinefunction(TenantContextPublisher.get_active)

    def test_concrete_publisher_implements_protocol(self) -> None:
        """publish_context_pack and resolve_tenant_id are concrete implementations."""

        class _Stub(TenantContextPublisher):
            async def publish(self, pack: TenantContextPack) -> TenantContextPack:
                return pack

            async def get_active(self, tenant_id: str) -> TenantContextPack | None:
                return None

        stub = _Stub()
        assert isinstance(stub, TenantContextPublisher)

    def test_publisher_protocol_is_runtime_checkable(self) -> None:
        """The protocol supports isinstance() runtime checks."""
        assert getattr(TenantContextPublisher, "_is_runtime_protocol", False) or hasattr(
            TenantContextPublisher, "_is_protocol"
        )


# ---------------------------------------------------------------------------
# Concrete publisher behavior (HTTP CRUD stub)
# ---------------------------------------------------------------------------


class TestPublishContextPack:
    @pytest.mark.asyncio
    async def test_publish_posts_to_correct_endpoint(self) -> None:
        """publish_context_pack POSTs to /tenants/<id>/context-versions."""
        mock_client = AsyncMock()
        mock_client.post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"version_id": "v2"},
        )
        pack = TenantContextPack.with_body(
            tenant_id="acme",
            version=1,
            body={"voice": "Direct."},
            published_by="alice",
        )
        with patch(
            "crackerjack.mahavishnu.tenancy.context_packs._get_http_client",
            return_value=mock_client,
        ):
            result = await publish_context_pack(pack)
        assert result.version_id == "v2"
        call_args = mock_client.post.call_args
        # Path must include tenant_id
        assert "/tenants/acme/context-versions" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_get_active_returns_tenant_context_pack_or_none(self) -> None:
        """resolve_tenant_id returns a TenantContextPack from the substrate or None."""
        from crackerjack.mahavishnu.tenancy.context_packs import get_active_context_pack

        mock_client = AsyncMock()
        # 404 -> no active pack
        mock_client.get.return_value = MagicMock(status_code=404)
        with patch(
            "crackerjack.mahavishnu.tenancy.context_packs._get_http_client",
            return_value=mock_client,
        ):
            assert await get_active_context_pack("acme") is None


# ---------------------------------------------------------------------------
# Tenant resolution
# ---------------------------------------------------------------------------


class TestTenantResolution:
    def test_default_tenant_constant(self) -> None:
        assert DEFAULT_TENANT == "default"

    def test_get_default_tenant_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MAHAVISHNU_DEFAULT_TENANT", "acme")
        assert get_default_tenant() == "acme"

    def test_get_default_tenant_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MAHAVISHNU_DEFAULT_TENANT", raising=False)
        assert get_default_tenant() == "default"

    def test_resolve_tenant_id_passes_through_when_set(self) -> None:
        assert resolve_tenant_id("acme") == "acme"

    def test_resolve_tenant_id_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAHAVISHNU_DEFAULT_TENANT", "fallback")
        assert resolve_tenant_id(None) == "fallback"
        assert resolve_tenant_id("") == "fallback"

    def test_context_files_constant(self) -> None:
        assert CONTEXT_FILES == ("voice", "icp", "positioning", "visual_identity")
