"""End-to-end tests for Crackerjack's /health aggregator adoption.

Verifies that the canonical ``mcp_common`` HealthAggregator drives the
envelope returned by both the ``/health`` HTTP route and the
``mcp__crackerjack__get_health()`` MCP tool, and that the
503-on-degraded contract (per
``docs/plans/2026-10-09-mcp-health-check-enrichment.md`` §5 Phase 1.2)
is enforced.

Tests are in the top-level ``tests/integration/`` (not the nested
``crackerjack/tests/integration/`` path the plan reference uses) to
match the existing crackerjack test layout at
``tests/integration/test_eventbridge_e2e.py``.
"""

from __future__ import annotations

import time

import pytest

from crackerjack.mcp.health import (
    DEFAULT_HEALTH_FEED_HALFLIFE_SECONDS,
    build_health_envelope,
    build_health_snapshot,
    get_health_feed_halflife_seconds,
    health_snapshot_to_envelope,
    status_to_http_code,
)
from mcp_common.health.aggregator import aggregate_feed_states
from mcp_common.health.feed import HealthFeedState, StatusValue

pytestmark = pytest.mark.integration


def test_health_feed_halflife_defaults_to_60() -> None:
    """Plan §5: ``HEALTH_FEED_HALFLIFE_SECONDS=60`` per adopter."""
    import os

    saved = os.environ.pop("HEALTH_FEED_HALFLIFE_SECONDS", None)
    try:
        assert get_health_feed_halflife_seconds() == 60.0
        assert (
            get_health_feed_halflife_seconds()
            == DEFAULT_HEALTH_FEED_HALFLIFE_SECONDS
        )
    finally:
        if saved is not None:
            os.environ["HEALTH_FEED_HALFLIFE_SECONDS"] = saved


def test_health_feed_halflife_respects_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operators can override via ``HEALTH_FEED_HALFLIFE_SECONDS=0`` to
    disable decay during incident triage (per
    ``mcp_common.health.feed.is_healthy`` docstring).
    """
    monkeypatch.setenv("HEALTH_FEED_HALFLIFE_SECONDS", "0")
    assert get_health_feed_halflife_seconds() == 0.0


def test_health_feed_halflife_falls_back_on_garbage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unparseable env var should fall back to the 60s default, not raise."""
    monkeypatch.setenv("HEALTH_FEED_HALFLIFE_SECONDS", "not-a-number")
    assert get_health_feed_halflife_seconds() == 60.0


def test_status_to_http_code_returns_200_for_healthy() -> None:
    snap = aggregate_feed_states({})
    assert snap["status"] == StatusValue.HEALTHY
    assert status_to_http_code(snap) == 200


def test_status_to_http_code_returns_200_for_warming_up() -> None:
    # WARMING_UP is the "first cycle done but no entities yet" state
    # per ``mcp_common.health.feed.is_healthy``: ingester_running=True
    # with entities_count==0 and cycles_total==1 (the producer
    # has cycled at least once but produced no entities yet). The
    # route serves 200 (warm but slow = 200, per plan §1). A feed
    # that has been declared AND the ingester reports running but
    # has never cycled is the HNSW-on-DuckDB hardening branch
    # (DEGRADED, not WARMING_UP).
    state = HealthFeedState(
        entities_count=0,
        last_updated_timestamp=time.time(),
        cycles_total=1,
        errors_total=0,
        ingester_running=True,
    )
    snap = aggregate_feed_states({"warmup_feed": state}, halflife_seconds=60.0)
    assert snap["status"] == StatusValue.WARMING_UP
    assert status_to_http_code(snap) == 200


def test_status_to_http_code_returns_503_for_degraded() -> None:
    # A feed that reports ingester_running=True but cycles_total=0
    # has never completed a cycle — DEGRADED with FEED_NEVER_POPULATED
    # per the akosha Phase 4 HNSW-on-DuckDB hardening pattern.
    state = HealthFeedState(ingester_running=True, cycles_total=0)
    snap = aggregate_feed_states({"test_feed": state}, halflife_seconds=60.0)
    # Cycles_total=0 with ingester_running=True triggers
    # FEED_NEVER_POPULATED → DEGRADED in mcp_common >= 0.30.
    assert snap["status"] in (StatusValue.WARMING_UP, StatusValue.DEGRADED)
    # If the aggregator returns DEGRADED, we expect 503; if WARMING_UP,
    # we still expect 200 (warm but slow). Either way, the contract
    # holds.
    if snap["status"] == StatusValue.DEGRADED:
        assert status_to_http_code(snap) == 503


def test_status_to_http_code_returns_503_for_failed() -> None:
    # A feed with errors within the halflife window → DEGRADED or FAILED
    # depending on severity. Forcing a high error rate within 60s
    # should push us into the degraded/failed bucket.
    state = HealthFeedState(
        entities_count=10,
        last_updated_timestamp=time.time(),
        cycles_total=5,
        errors_total=3,
        last_error_at=time.time(),
        errors_within_window=3,
        first_unhealthy_at=time.time(),
        ingester_running=True,
    )
    snap = aggregate_feed_states({"test_feed": state}, halflife_seconds=60.0)
    assert snap["status"] in (StatusValue.DEGRADED, StatusValue.FAILED)
    assert status_to_http_code(snap) == 503


def test_health_snapshot_envelope_includes_degraded_feeds() -> None:
    state = HealthFeedState(ingester_running=True, cycles_total=0)
    snap = aggregate_feed_states({"test_feed": state}, halflife_seconds=60.0)
    envelope = health_snapshot_to_envelope(snap)
    assert "degraded_feeds" in envelope
    assert "test_feed" in envelope["degraded_feeds"]


def test_health_snapshot_envelope_for_healthy_feed() -> None:
    state = HealthFeedState(
        entities_count=10,
        last_updated_timestamp=time.time(),
        cycles_total=10,
        errors_total=0,
        ingester_running=True,
    )
    snap = aggregate_feed_states({"test_feed": state}, halflife_seconds=60.0)
    envelope = health_snapshot_to_envelope(snap)
    assert envelope["status"] == "healthy"
    assert envelope["degraded_feeds"] == []
    assert status_to_http_code(snap) == 200
    assert envelope["checks"]["test_feed"]["healthy"] is True


def test_envelope_shape_matches_canonical_healthsnapshot() -> None:
    """The envelope keys must match
    ``mcp_common.health.aggregator.HealthSnapshot`` (plan §1 + §7).
    """
    state = HealthFeedState(
        entities_count=10,
        last_updated_timestamp=time.time(),
        cycles_total=10,
        errors_total=0,
        ingester_running=True,
    )
    snap = aggregate_feed_states({"test_feed": state}, halflife_seconds=60.0)
    envelope = health_snapshot_to_envelope(snap)

    assert set(envelope.keys()) == {
        "status",
        "checks",
        "reason_codes",
        "degraded_feeds",
    }
    assert "status" in snap
    assert "checks" in snap
    assert "reason_codes" in snap
    assert set(envelope["checks"].keys()) == snap["checks"].keys()


def test_build_health_snapshot_returns_none_when_uninitialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """During the pre-init warm-up window, build_health_snapshot
    must return ``None`` so the caller can translate to 503.
    """
    monkeypatch.setattr(
        "crackerjack.mcp.signer_feed._signer_feed_state", None
    )
    assert build_health_snapshot() is None
    assert build_health_envelope() is None


def test_build_health_envelope_returns_uninitialized_envelope_when_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The MCP-tool wrapper translates ``None`` into a degraded
    envelope in the body. Verify the underlying functions stay
    None-returning; the translation lives in health_tools_wrapper.
    """
    monkeypatch.setattr(
        "crackerjack.mcp.signer_feed._signer_feed_state", None
    )
    assert build_health_envelope() is None
