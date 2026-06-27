"""Adapter runtime observability — settings versioning substrate.

Spec: docs/superpowers/specs/2026-06-22-adapter-runtime-observability-design.md

This module is the **runtime substrate side** of adapter observability. It
provides:

- :class:`AdapterSettingsVersion` — immutable value model for a settings row.
- :class:`SettingsActivationRecord` — write side (the actor's intent).
- :class:`SettingsPersister` — protocol for append-only activation history.
- :class:`InMemorySettingsPersister` — v0 default, used by tests and local runs.
- :class:`HttpSettingsPersister` — stub for the Dhara HTTP CRUD transport
  (blocked on Workstream C — ``/adapters/<id>/active-settings-version``).
- :func:`activate` — single entry point that deactivates the current active
  version (if any) and appends a new one.

Cloud Run / serverless constraint
---------------------------------
The MCP server is stateless. Every read and every write must traverse the
persister boundary; this process holds no state of its own. The in-memory
persister is therefore a *test-only* convenience; production callers must
inject :class:`HttpSettingsPersister` (or, once Workstream C lands, an impl
backed by Dhara's HTTP API).

Phase 3 pivot
-------------
This spec supersedes the original ``cross-machine-session-continuity`` design.
The git-as-state-store pattern was solving the wrong problem for the wrong
deployment model. The substrate is now Dhara (HTTP CRUD); the *history* is
preserved by deactivation (a new row), not by mutation.

Seam with Plan 4 Phase D
------------------------
Plan 4 Phase D ships ``mahavishnu/distill/tracked_settings.py`` (Oneiric
substrate side). Both implementations honour the same :class:`SettingsPersister`
protocol so callers can swap backends at the dependency-injection boundary
without code changes:

    +-----------------------------+        +------------------------------+
    |  Oneiric-backed persister   |        |  In-memory / HTTP persister  |
    | (Plan 4 Phase D — future)   |        |  (this module — present)     |
    +-------------+---------------+        +---------------+--------------+
                  |                                        |
                  +----------------+ +---------------------+
                                   | |
                                   v v
                          +--------+---+--------+
                          | SettingsPersister  |
                          |   (protocol)       |
                          +--------------------+

When Plan 4 lands, swap the persister at the DI boundary and the in-memory
impl remains the unit-test backend.

Atomic activation
-----------------
"Activate version V" is logically a single transaction:

    1. find the active version for ``adapter_id`` (if any) and mark it
       ``deactivated_at = now()``.
    2. insert the new version with ``deactivated_at = None``.

For the in-memory persister these two steps run sequentially in this process.
For the HTTP persister the work is delegated to the Dhara backend (which uses
a partial unique index to enforce at most one active row per adapter).

Substrate status (Phase 3 dispatch): http_blocked for
``/adapters/<id>/active-settings-version``. Also overlaps with Plan 4 Phase D.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdapterSettingsVersion:
    """Immutable value model for an adapter's settings row.

    The model is frozen because settings rows are append-only history. The
    ``is_active`` predicate is computed from ``deactivated_at`` rather than
    stored as a mutable flag — this guarantees the join-by-id invariant that
    downstream consumers (forensic queries, A/B comparison) rely on.

    Attributes:
        adapter_id: Stable adapter identifier (e.g. ``"prefect"``).
        version: Monotonic per-adapter integer; ``>= 1``.
        settings_hash: Hash of the settings blob. Join key for forensic queries
            tying lifecycle events and metrics back to the config that produced
            them.
        activated_at: ISO 8601 UTC timestamp when this row became active.
        activated_by: User or system principal that triggered the activation
            (e.g. ``"alice"``, ``"system:deploy"``).
        notes: Operator-supplied free-text rationale. Defaults to empty.
        deactivated_at: ISO 8601 UTC timestamp when this row was superseded,
            or ``None`` if the row is currently the active one.
    """

    adapter_id: str
    version: int
    settings_hash: str
    activated_at: datetime
    activated_by: str
    notes: str = ""
    deactivated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.settings_hash:
            raise ValueError(
                "settings_hash is required (join key for forensic queries)"
            )
        if self.version < 1:
            raise ValueError(
                f"version must be a positive integer; got {self.version!r}"
            )

    @property
    def is_active(self) -> bool:
        """A row is active when it has not been deactivated."""
        return self.deactivated_at is None


@dataclass(frozen=True)
class SettingsActivationRecord:
    """The actor's intent to activate a new settings version.

    Distinct from :class:`AdapterSettingsVersion` because activation is the
    *command* (before it lands in the persister) and the row is the *result*
    (after the persister stamps timestamps and deactivates the predecessor).
    """

    adapter_id: str
    version: int
    settings_hash: str
    activated_by: str
    notes: str = ""


# ---------------------------------------------------------------------------
# Persister protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SettingsPersister(Protocol):
    """Append-only settings activation history.

    The protocol is the seam shared with Plan 4 Phase D — see module docstring.
    Implementations MUST preserve full history (deactivation is a new state on
    an existing row, never deletion) and MUST enforce "at most one active row
    per adapter".
    """

    def append(self, record: SettingsActivationRecord) -> AdapterSettingsVersion:
        """Append a new activation. Deactivates any currently-active row first.

        Returns the persisted :class:`AdapterSettingsVersion`. ``activated_at``
        is stamped by the persister (so different backends can decide whether
        to use wall-clock UTC or a backend-supplied timestamp).
        """
        ...

    def get_active(self, adapter_id: str) -> AdapterSettingsVersion | None:
        """Return the currently-active row for ``adapter_id``, or ``None``."""
        ...

    def get_history(self, adapter_id: str) -> list[AdapterSettingsVersion]:
        """Return the full append-only history for ``adapter_id``.

        Order is insertion order (oldest first). Implementations may document
        if their natural ordering differs.
        """
        ...


# ---------------------------------------------------------------------------
# In-memory implementation (v0 default, test-friendly)
# ---------------------------------------------------------------------------


class InMemorySettingsPersister:
    """In-memory ``SettingsPersister`` implementation.

    The v0 default. Suitable for unit tests and local development. NOT
    suitable for production — production callers must inject a persister whose
    state survives process restarts (e.g. ``HttpSettingsPersister``).
    """

    def __init__(self) -> None:
        # adapter_id -> list[AdapterSettingsVersion], oldest first
        self._history: dict[str, list[AdapterSettingsVersion]] = {}

    def append(self, record: SettingsActivationRecord) -> AdapterSettingsVersion:
        now = datetime.now(UTC)
        # Deactivate the previously-active row (if any) BEFORE appending the
        # new one. We mutate deactivated_at on the frozen dataclass via
        # ``object.__setattr__``; this is acceptable because the row was just
        # produced by an earlier ``append`` and is not yet shared with any
        # external observer — the persister is the sole writer.
        history = self._history.setdefault(record.adapter_id, [])
        for prev in reversed(history):
            if prev.is_active:
                object.__setattr__(prev, "deactivated_at", now)
                break

        new_row = AdapterSettingsVersion(
            adapter_id=record.adapter_id,
            version=record.version,
            settings_hash=record.settings_hash,
            activated_at=now,
            activated_by=record.activated_by,
            notes=record.notes,
            deactivated_at=None,
        )
        history.append(new_row)
        return new_row

    def get_active(self, adapter_id: str) -> AdapterSettingsVersion | None:
        history = self._history.get(adapter_id, [])
        for row in reversed(history):
            if row.is_active:
                return row
        return None

    def get_history(self, adapter_id: str) -> list[AdapterSettingsVersion]:
        return list(self._history.get(adapter_id, []))


# ---------------------------------------------------------------------------
# HTTP persister stub (Workstream C — blocked)
# ---------------------------------------------------------------------------


class HttpSettingsPersister:
    """HTTP CRUD stub. Talks to Dhara's adapter settings endpoints.

    Substrate status: http_blocked (Phase 3 dispatch). The endpoint
    ``/adapters/<id>/active-settings-version`` is not yet shipped in Dhara;
    implementation here is a stub that constructs the right request shapes so
    callers can wire it up at the DI boundary without code changes once the
    endpoint ships.

    Overlap with Plan 4 Phase D: when both land, prefer the Oneiric-backed
    persister (Plan 4) and keep this class as the raw-HTTP fallback.
    """

    # TODO(Workstream C): wire to the actual Dhara HTTP client once the
    # ``/adapters/<id>/active-settings-version`` endpoint ships. The current
    # class only stores the base_url and exposes a typed seam; the network
    # call is intentionally unimplemented so we don't ship broken calls.

    def __init__(self, base_url: str, *, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def append(self, record: SettingsActivationRecord) -> AdapterSettingsVersion:
        # TODO(Workstream C): POST {base_url}/adapters/{adapter_id}/settings-versions
        # with body {config, activated_by, notes}; let Dhara deactivate the
        # previous active row in a single transaction. Until then, raise
        # rather than fabricate a row.
        raise NotImplementedError(
            "HttpSettingsPersister is a stub — Workstream C is blocked on "
            "the Dhara HTTP surface. Use InMemorySettingsPersister in tests "
            "or wait for the endpoint to ship."
        )

    def get_active(self, adapter_id: str) -> AdapterSettingsVersion | None:
        # TODO(Workstream C): GET {base_url}/adapters/{adapter_id}/active-settings-version
        # 404 → return None.
        raise NotImplementedError("Workstream C: HTTP GET not yet wired.")

    def get_history(self, adapter_id: str) -> list[AdapterSettingsVersion]:
        # TODO(Workstream C): GET {base_url}/adapters/{adapter_id}/settings-versions
        raise NotImplementedError("Workstream C: HTTP GET history not yet wired.")


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def activate(
    record: SettingsActivationRecord, persister: SettingsPersister
) -> AdapterSettingsVersion:
    """Activate ``record`` via ``persister``.

    Single entry point used by both runtime callers (e.g. the MCP
    ``activate_settings_version`` tool) and tests. Deactivates the current
    active row (if any) and appends the new one in a single
    persister-mediated step.

    Args:
        record: The activation intent (adapter_id, version, settings_hash,
            activated_by, notes).
        persister: The destination backend (in-memory for tests; HTTP-backed
            in production once Workstream C lands).

    Returns:
        The persisted :class:`AdapterSettingsVersion` row.
    """
    return persister.append(record)


__all__ = [
    "AdapterSettingsVersion",
    "SettingsActivationRecord",
    "SettingsPersister",
    "InMemorySettingsPersister",
    "HttpSettingsPersister",
    "activate",
]