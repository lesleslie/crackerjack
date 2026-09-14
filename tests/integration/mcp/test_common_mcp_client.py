"""Smoke test: mcp-common's CommonMCPClient SDK is available and basic operations work.

Phase 3 of ``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``
(plan §5 Phase 3 task 6 ``crackerjack: tests/integration/mcp/test_common_mcp_client.py
— NEW (smoke test against the published SDK)``).

Crackerjack's mcp-common dep floor is currently ``>=0.18.0``. The
``CommonMCPClient`` class was extracted from akosha into mcp-common at
``0.26.0``; until crackerjack's floor is bumped to ``>=0.26.0,<0.27.0``
these tests gracefully skip. Once the dep is bumped, the smoke checks
become runnable without any change here.

This file is intentionally self-contained and has no internal import
dependencies on crackerjack internals — it's a wire-level SDK smoke.
"""

from __future__ import annotations

import pytest


def _try_import_common_mcp_client():
    """Import CommonMCPClient; return None + skip reason if unavailable."""
    try:
        from mcp_common.clients.common_mcp_client import CommonMCPClient
    except ImportError as exc:
        pytest.skip(
            "mcp_common.clients.common_mcp_client not available in crackerjack's venv "
            f"(reason: {exc}); bump crackerjack's mcp-common floor to >=0.26.0,<0.27.0 "
            "to enable this smoke check."
        )
    return CommonMCPClient


def _try_import_health_feed():
    try:
        from mcp_common.health.feed import (
            HealthFeedState,
            StatusValue,
            ReasonCode,
        )
    except ImportError as exc:
        pytest.skip(
            "mcp_common.health.feed not available in crackerjack's venv "
            f"(reason: {exc})."
        )
    return HealthFeedState, StatusValue, ReasonCode


def _try_import_aggregator():
    try:
        from mcp_common.health.aggregator import aggregate_feed_states
    except ImportError as exc:
        pytest.skip(
            f"mcp_common.health.aggregator not available (reason: {exc})."
        )
    return aggregate_feed_states


@pytest.mark.smoke
@pytest.mark.integration
def test_common_mcp_client_sdk_importable() -> None:
    """``CommonMCPClient`` is importable from mcp-common >= 0.26.x.

    Implements: REQ-001 (mcp-common SDK extraction from akosha).
    """
    CommonMCPClient = _try_import_common_mcp_client()
    assert CommonMCPClient is not None
    assert CommonMCPClient.__module__ == "mcp_common.clients.common_mcp_client"


@pytest.mark.smoke
@pytest.mark.integration
def test_common_mcp_client_ssrf_guard_rejects_non_http() -> None:
    """SSRF guard: ``file://`` and ``gopher://`` are rejected pre-connect.

    The BodaiCommonMCPClient maintains a ``_ALLOWED_SCHREFS`` allowlist
    (per akosha's prior implementation carried into mcp-common); the
    smoke verifies the guard is wired.
    """
    CommonMCPClient = _try_import_common_mcp_client()

    with pytest.raises(ValueError):
        CommonMCPClient(base_url="file:///etc/passwd")

    with pytest.raises(ValueError):
        CommonMCPClient(base_url="gopher://evil.example/")


@pytest.mark.smoke
@pytest.mark.integration
def test_common_mcp_client_instantiate_with_http_url() -> None:
    """``http://`` URL passes the SSRF guard; client is constructable."""
    CommonMCPClient = _try_import_common_mcp_client()
    client = CommonMCPClient(base_url="http://localhost:8680/mcp", timeout=5.0)
    assert client is not None


@pytest.mark.smoke
@pytest.mark.integration
def test_health_feed_state_enum_values() -> None:
    """``StatusValue`` and ``ReasonCode`` enum values match plan §11."""
    _, StatusValue, ReasonCode = _try_import_health_feed()
    assert StatusValue.HEALTHY.value == "healthy"
    assert StatusValue.WARMING_UP.value == "warming_up"
    assert StatusValue.DEGRADED.value == "degraded"
    assert StatusValue.FAILED.value == "failed"
    assert ReasonCode.WARMING_UP_EMPTY_FEED.value == "warming_up_empty_feed"
    assert ReasonCode.RECENT_ERROR_IN_WINDOW.value == "recent_error_in_window"


@pytest.mark.smoke
@pytest.mark.integration
def test_aggregate_feed_states_empty_input() -> None:
    """``aggregate_feed_states({})`` returns the documented wire shape.

    Empty input → status healthy (no feeds → no failures), no reason_codes.
    """
    aggregate_feed_states = _try_import_aggregator()
    result = aggregate_feed_states({})
    assert isinstance(result, dict)
    assert result["status"] == "healthy"
    assert result["checks"] == {}
    assert result["reason_codes"] == []
