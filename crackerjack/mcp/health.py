"""Adopt mcp_common HealthAggregator for Crackerjack's /health surface.

Per ``docs/plans/2026-10-09-mcp-health-check-enrichment.md`` Phase 1.2,
both the HTTP ``/health`` route and ``mcp__crackerjack__get_health()``
MCP tool must route through the canonical
``mcp_common.health.aggregator.HealthAggregator`` so the two surfaces
agree on the same feed-state (REQ-HC-003) and return 503 when any
feed is degraded (REQ-HC-002).

This module is the single source of truth for the canonical
``HealthSnapshot`` envelope and the per-adopter halflife config.
``crackerjack.mcp.server_core.create_mcp_server`` and
``crackerjack.mcp.tools.health_tools_wrapper`` both call into it;
no other code path should construct per-feed health state.
"""

from __future__ import annotations

import os
from typing import Any

from mcp_common.health.aggregator import HealthSnapshot, aggregate_feed_states
from mcp_common.health.feed import HealthFeedState, StatusValue

from crackerjack.mcp.signer_feed import SignerFeedState, get_signer_feed_state

# Plan §5 Phase 1.2: ``HEALTH_FEED_HALFLIFE_SECONDS=60`` per adopter
# (default in mcp-common is 300s). The 60s window keeps warm-up brief
# so a fresh server doesn't sit in 503 for a full interval.
DEFAULT_HEALTH_FEED_HALFLIFE_SECONDS: float = 60.0


def get_health_feed_halflife_seconds() -> float:
    """Return the per-adopter health-feed halflife override.

    Reads ``HEALTH_FEED_HALFLIFE_SECONDS`` from the environment; falls
    back to :data:`DEFAULT_HEALTH_FEED_HALFLIFE_SECONDS` (60s) when
    the var is unset or unparsable.
    """
    raw = os.getenv("HEALTH_FEED_HALFLIFE_SECONDS")
    if raw is None:
        return DEFAULT_HEALTH_FEED_HALFLIFE_SECONDS
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_HEALTH_FEED_HALFLIFE_SECONDS


def _signer_to_feed_state(state: SignerFeedState) -> HealthFeedState:
    """Translate the lifespan-owned :class:`SignerFeedState` into the
    canonical :class:`HealthFeedState` expected by ``mcp_common``.

    The four mandatory signals (``entities_count``,
    ``last_updated_timestamp``, ``cycles_total``, ``errors_total``)
    come straight from the signer state. The remaining fields get
    conservative defaults: ``ingester_running=True`` once init
    succeeded; the others ``None``/``0`` because ``SignerFeedState``
    doesn't model those transitions (its error counter is a lifetime
    count, not a windowed burn rate).
    """
    manifest_dict = state.manifest.as_dict()
    return HealthFeedState(
        entities_count=int(manifest_dict.get("key_count", 0)),
        last_updated_timestamp=state.last_updated_timestamp,
        cycles_total=state.cycles_total,
        errors_total=state.errors_total,
        last_error_at=None,
        errors_within_window=0,
        first_unhealthy_at=None,
        ingester_running=True,
    )


def build_health_snapshot() -> HealthSnapshot | None:
    """Return the canonical :class:`HealthSnapshot` for Crackerjack.

    Returns ``None`` only during the pre-init warm-up window
    (``create_mcp_server`` has not yet called
    :func:`crackerjack.mcp.signer_feed.init_signer_feed_state`).
    Callers must translate ``None`` into a 503 (per the plan §10.3.2
    warm-up contract).
    """
    state = get_signer_feed_state()
    if state is None:
        return None

    feed_state = _signer_to_feed_state(state)
    halflife = get_health_feed_halflife_seconds()
    return aggregate_feed_states({"skills_signer": feed_state}, halflife)


def build_health_envelope() -> dict[str, Any] | None:
    """Return the operator-facing envelope, or ``None`` if uninitialized.

    Translates the :class:`HealthSnapshot` into a JSON-safe dict and
    appends the derived ``degraded_feeds`` key (per plan §1) listing
    feed names where ``healthy=False`` so operators can spot the
    silent-degraded case at a glance.
    """
    snap = build_health_snapshot()
    if snap is None:
        return None
    return health_snapshot_to_envelope(snap)


def health_snapshot_to_envelope(snap: HealthSnapshot) -> dict[str, Any]:
    """Convert a :class:`HealthSnapshot` into the operator-facing envelope.

    Adds a derived ``degraded_feeds`` key (per plan §1 acceptance
    gate) listing the feed names where ``healthy=False``.
    """
    degraded_feeds = [
        feed_name
        for feed_name, verdict in snap["checks"].items()
        if not verdict["healthy"]
    ]
    return {
        "status": snap["status"].value,
        "checks": {
            feed_name: {
                "status": verdict["status"].value,
                "healthy": verdict["healthy"],
                "reason_codes": [code.value for code in verdict["reason_codes"]],
            }
            for feed_name, verdict in snap["checks"].items()
        },
        "reason_codes": [code.value for code in snap["reason_codes"]],
        "degraded_feeds": degraded_feeds,
    }


def status_to_http_code(snap: HealthSnapshot) -> int:
    """Map a :class:`HealthSnapshot`'s status to the HTTP code for /health.

    :data:`StatusValue.HEALTHY` and :data:`StatusValue.WARMING_UP` both
    return 200 (warm but slow = serving 200); :data:`StatusValue.DEGRADED`
    and :data:`StatusValue.FAILED` return 503. This is the canonical
    503-on-degraded contract from ``mcp-backend-wiring-discipline.md``.
    """
    if snap["status"] in (StatusValue.HEALTHY, StatusValue.WARMING_UP):
        return 200
    return 503


__all__ = [
    "DEFAULT_HEALTH_FEED_HALFLIFE_SECONDS",
    "build_health_envelope",
    "build_health_snapshot",
    "get_health_feed_halflife_seconds",
    "health_snapshot_to_envelope",
    "status_to_http_code",
]
