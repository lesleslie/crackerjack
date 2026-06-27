"""TDD red-green tests for adapter runtime observability.

Spec: docs/superpowers/specs/2026-06-22-adapter-runtime-observability-design.md
Pivot (Phase 3): Dhara-backed settings versioning (was: cross-machine session continuity).

Coverage targets:
    - AdapterSettingsVersion: immutable value model for a settings row.
    - SettingsActivationRecord: write side (persister interface + in-memory impl).
    - HttpSettingsPersister: stub for HTTP CRUD (Workstream C — blocked on Dhara HTTP).

The seam with Plan 4 Phase D (``mahavishnu/distill/tracked_settings.py``, Oneiric side)
is documented in ``mahavishnu/observability/adapter_runtime.py``. Both sides share
the ``SettingsPersister`` protocol so the Oneiric substrate and the runtime
persister can be swapped at the dependency-injection boundary.
"""

from __future__ import annotations

# Path shim: this test file lives in the worktree under
# ``tests/unit/`` but the implementation under test sits in
# ``crackerjack/mahavishnu/observability/adapter_runtime.py`` (Phase 3 spec
# layout). Insert that nested package directory at the front of sys.path so
# ``import mahavishnu.observability.adapter_runtime`` resolves to the worktree
# copy rather than the editable-installed ``mahavishnu`` package.
#
# When this work is merged upstream into /Users/les/Projects/mahavishnu,
# the shim is a no-op: the implementation lives at the canonical path and the
# editable install picks it up.
import sys
from pathlib import Path

_NESTED = Path(__file__).resolve().parents[2] / "crackerjack"
if str(_NESTED) not in sys.path:
    sys.path.insert(0, str(_NESTED))

from datetime import UTC, datetime  # noqa: E402

import pytest  # noqa: E402

from mahavishnu.observability.adapter_runtime import (  # noqa: E402
    AdapterSettingsVersion,
    HttpSettingsPersister,
    InMemorySettingsPersister,
    SettingsActivationRecord,
    SettingsPersister,
    activate,
)


# ---------------------------------------------------------------------------
# AdapterSettingsVersion model
# ---------------------------------------------------------------------------


class TestAdapterSettingsVersion:
    """AdapterSettingsVersion is the immutable value model for a settings row."""

    def test_required_fields_present(self) -> None:
        activated_at = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)
        v = AdapterSettingsVersion(
            adapter_id="prefect",
            version=1,
            settings_hash="abc123",
            activated_at=activated_at,
            activated_by="alice",
        )
        assert v.adapter_id == "prefect"
        assert v.version == 1
        assert v.settings_hash == "abc123"
        assert v.activated_at == activated_at
        assert v.activated_by == "alice"

    def test_optional_fields_have_sensible_defaults(self) -> None:
        """notes default empty; deactivated_at default None (i.e. currently active)."""
        v = AdapterSettingsVersion(
            adapter_id="prefect",
            version=1,
            settings_hash="abc123",
            activated_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
            activated_by="alice",
        )
        assert v.notes == ""
        assert v.deactivated_at is None

    def test_is_active_returns_true_when_not_deactivated(self) -> None:
        v = AdapterSettingsVersion(
            adapter_id="prefect",
            version=1,
            settings_hash="abc123",
            activated_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
            activated_by="alice",
        )
        assert v.is_active is True

    def test_is_active_returns_false_when_deactivated(self) -> None:
        v = AdapterSettingsVersion(
            adapter_id="prefect",
            version=1,
            settings_hash="abc123",
            activated_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
            activated_by="alice",
            deactivated_at=datetime(2026, 6, 26, 13, 0, 0, tzinfo=UTC),
        )
        assert v.is_active is False

    def test_settings_hash_is_required(self) -> None:
        """settings_hash is the join key for forensic queries — must be present."""
        with pytest.raises(Exception):
            AdapterSettingsVersion(  # type: ignore[call-arg]
                adapter_id="prefect",
                version=1,
                activated_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
                activated_by="alice",
            )

    def test_version_is_positive_integer(self) -> None:
        """version is monotonic per adapter — must be positive int."""
        with pytest.raises(Exception):
            AdapterSettingsVersion(
                adapter_id="prefect",
                version=0,  # invalid: zero
                settings_hash="abc123",
                activated_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
                activated_by="alice",
            )


# ---------------------------------------------------------------------------
# InMemorySettingsPersister
# ---------------------------------------------------------------------------


class TestInMemorySettingsPersister:
    """In-memory implementation of SettingsPersister — the v0 default."""

    def test_active_returns_none_for_unknown_adapter(self) -> None:
        p = InMemorySettingsPersister()
        assert p.get_active("unknown") is None

    def test_full_history_returns_none_for_unknown_adapter(self) -> None:
        p = InMemorySettingsPersister()
        assert p.get_history("unknown") == []

    def test_first_activation_makes_version_active(self) -> None:
        p = InMemorySettingsPersister()
        record = SettingsActivationRecord(
            adapter_id="prefect",
            version=1,
            settings_hash="hash-1",
            activated_by="alice",
        )
        v = p.append(record)
        assert v.is_active is True
        assert p.get_active("prefect") == v
        assert p.get_history("prefect") == [v]

    def test_second_activation_deactivates_previous(self) -> None:
        """At most one active version per adapter. Old row is deactivated, not deleted."""
        p = InMemorySettingsPersister()
        v1 = p.append(
            SettingsActivationRecord(
                adapter_id="prefect",
                version=1,
                settings_hash="hash-1",
                activated_by="alice",
            )
        )
        v2 = p.append(
            SettingsActivationRecord(
                adapter_id="prefect",
                version=2,
                settings_hash="hash-2",
                activated_by="bob",
            )
        )

        # v1 is now deactivated (history retained)
        assert v1.is_active is False
        assert v1.deactivated_at is not None

        # v2 is the active one
        assert v2.is_active is True
        assert p.get_active("prefect") == v2

        # Full history retains both rows in insertion order
        history = p.get_history("prefect")
        assert history == [v1, v2]

    def test_three_activations_keep_full_history(self) -> None:
        p = InMemorySettingsPersister()
        versions: list[AdapterSettingsVersion] = []
        for i in range(1, 4):
            versions.append(
                p.append(
                    SettingsActivationRecord(
                        adapter_id="prefect",
                        version=i,
                        settings_hash=f"hash-{i}",
                        activated_by=f"user-{i}",
                    )
                )
            )
        # Only the last is active; all three are in history.
        assert versions[0].is_active is False
        assert versions[1].is_active is False
        assert versions[2].is_active is True
        assert p.get_history("prefect") == versions

    def test_adapters_isolated(self) -> None:
        """Activation on one adapter must not touch another."""
        p = InMemorySettingsPersister()
        v_prefect = p.append(
            SettingsActivationRecord(
                adapter_id="prefect",
                version=1,
                settings_hash="h-prefect",
                activated_by="alice",
            )
        )
        v_llama = p.append(
            SettingsActivationRecord(
                adapter_id="llamaindex",
                version=1,
                settings_hash="h-llama",
                activated_by="bob",
            )
        )
        assert v_prefect.is_active is True
        assert v_llama.is_active is True
        assert p.get_active("prefect") == v_prefect
        assert p.get_active("llamaindex") == v_llama

    def test_satisfies_protocol(self) -> None:
        """InMemorySettingsPersister must be usable wherever SettingsPersister is accepted."""
        p: SettingsPersister = InMemorySettingsPersister()
        p.append(
            SettingsActivationRecord(
                adapter_id="prefect",
                version=1,
                settings_hash="h",
                activated_by="alice",
            )
        )
        assert p.get_active("prefect") is not None


# ---------------------------------------------------------------------------
# HttpSettingsPersister (stub — Workstream C)
# ---------------------------------------------------------------------------


class TestHttpSettingsPersister:
    """HTTP CRUD stub.

    Substrate status (Phase 3 dispatch): http_blocked for
    /adapters/<id>/active-settings-version. Also overlaps with Plan 4 Phase D.
    """

    def test_is_a_settings_persister(self) -> None:
        """Even though the stub does not yet ship, it must satisfy the protocol."""
        p: SettingsPersister = HttpSettingsPersister(base_url="http://localhost:8683")
        assert isinstance(p, SettingsPersister)

    def test_constructs_with_base_url(self) -> None:
        p = HttpSettingsPersister(base_url="http://example/dhara")
        assert p.base_url == "http://example/dhara"


# ---------------------------------------------------------------------------
# activate() convenience — produces a record + delegates to persister
# ---------------------------------------------------------------------------


class TestActivate:
    """activate(record, persister) — single entry point used by both substrates."""

    def test_returns_persisted_version(self) -> None:
        p = InMemorySettingsPersister()
        record = SettingsActivationRecord(
            adapter_id="prefect",
            version=1,
            settings_hash="h",
            activated_by="alice",
        )
        v = activate(record, p)
        assert v.is_active is True
        assert p.get_active("prefect") == v

    def test_replaces_active_predecessor(self) -> None:
        p = InMemorySettingsPersister()
        first = activate(
            SettingsActivationRecord(
                adapter_id="prefect",
                version=1,
                settings_hash="h1",
                activated_by="alice",
            ),
            p,
        )
        second = activate(
            SettingsActivationRecord(
                adapter_id="prefect",
                version=2,
                settings_hash="h2",
                activated_by="bob",
            ),
            p,
        )
        assert first.is_active is False
        assert second.is_active is True
        assert p.get_active("prefect") == second


# ---------------------------------------------------------------------------
# Plan 4 Phase D overlap — protocol seam
# ---------------------------------------------------------------------------


class TestPlan4PhaseDSeam:
    """The persister protocol is the seam shared with Plan 4 Phase D.

    Plan 4 Phase D ships ``mahavishnu/distill/tracked_settings.py`` (Oneiric
    substrate side). Both implementations honour the same protocol so callers
    can swap backends at the dependency-injection boundary without code changes.

    This test pins that the protocol is importable and the in-memory impl satisfies
    it — i.e. when Plan 4 lands, a one-liner swap of the persister in DI config is
    sufficient.
    """

    def test_settings_persister_is_a_protocol(self) -> None:
        from typing import Protocol

        # Persister must be a Protocol so both the in-memory impl and the
        # Oneiric-backed impl (Plan 4 Phase D) are substitutable.
        assert issubclass(SettingsPersister, Protocol)

    def test_protocol_has_required_methods(self) -> None:
        for name in ("append", "get_active", "get_history"):
            assert hasattr(SettingsPersister, name), f"protocol missing {name!r}"