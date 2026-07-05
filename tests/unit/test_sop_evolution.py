"""Tests for Spec #7: project-scoped SOP evolution.

SOPs (standard operating procedures) live per project and evolve based on
recurring failure modes. The substrate for now is in-memory; a Dhara-backed
persister is documented as a stub.

Coverage:

- ``ProjectSOP`` model construction and immutability of version metadata
- ``FailureModeCatalogEntry`` recording and counting
- ``EvolutionTrigger`` proposing an SOP edit after N occurrences
- ``InMemorySOPPersister`` CRUD (save / get / list)
- ``DharaSOPPersister`` stub raises ``NotImplementedError`` (documented stub)
- ``EvolutionEngine`` end-to-end: failure_mode -> trigger -> proposal
"""

from __future__ import annotations

from datetime import datetime

import pytest

from crackerjack.sop.evolution import (
    EvolutionEngine,
    EvolutionTrigger,
    SOPProposal,
)
from crackerjack.sop.models import (
    FailureModeCatalog,
    FailureModeCatalogEntry,
    ProjectSOP,
)
from crackerjack.sop.persisters import (
    DharaSOPPersister,
    InMemorySOPPersister,
    SOPPersister,
)


# ── ProjectSOP model ──────────────────────────────────────────────────────


class TestProjectSOP:
    def test_basic_construction(self):
        now = datetime(2026, 6, 27, 10, 0, 0)
        sop = ProjectSOP(
            project_id="mahavishnu",
            name="deploy",
            body="Step 1: run tests. Step 2: tag release.",
            version=1,
            last_failure_id=None,
            last_evolved_at=now,
        )
        assert sop.project_id == "mahavishnu"
        assert sop.name == "deploy"
        assert sop.version == 1
        assert sop.body.startswith("Step 1")
        assert sop.last_failure_id is None
        assert sop.last_evolved_at == now

    def test_version_increments_on_evolve(self):
        original = ProjectSOP(
            project_id="p1",
            name="release",
            body="old body",
            version=3,
            last_failure_id=None,
            last_evolved_at=datetime(2026, 6, 27),
        )
        evolved = original.evolved(
            new_body="new body",
            failure_id="fail-42",
            evolved_at=datetime(2026, 6, 27, 11, 0, 0),
        )
        # Version bumps by 1
        assert evolved.version == 4
        # Failure id recorded
        assert evolved.last_failure_id == "fail-42"
        # Body replaced
        assert evolved.body == "new body"
        # Original is unchanged (frozen semantics via evolve())
        assert original.version == 3
        assert original.last_failure_id is None

    def test_project_id_and_name_required(self):
        with pytest.raises(TypeError):
            ProjectSOP()  # type: ignore[call-arg]

    def test_equality_by_identity_fields(self):
        a = ProjectSOP(
            project_id="p1",
            name="release",
            body="x",
            version=1,
            last_failure_id=None,
            last_evolved_at=datetime(2026, 6, 27),
        )
        b = ProjectSOP(
            project_id="p1",
            name="release",
            body="x",
            version=1,
            last_failure_id=None,
            last_evolved_at=datetime(2026, 6, 27),
        )
        # ProjectSOP is a regular dataclass; equality is structural
        assert a == b


# ── FailureModeCatalog entry ──────────────────────────────────────────────


class TestFailureModeCatalogEntry:
    def test_initial_count_is_zero(self):
        entry = FailureModeCatalogEntry(
            project_id="p1",
            fingerprint="missing-fixture",
            description="Tests missing required fixture",
        )
        assert entry.count == 0
        assert entry.fingerprint == "missing-fixture"
        assert entry.first_seen_at is None
        assert entry.last_seen_at is None

    def test_record_increments_count(self):
        entry = FailureModeCatalogEntry(
            project_id="p1",
            fingerprint="missing-fixture",
            description="Tests missing required fixture",
        )
        ts1 = datetime(2026, 6, 27, 10, 0, 0)
        ts2 = datetime(2026, 6, 27, 11, 0, 0)
        entry.record(at=ts1)
        entry.record(at=ts2)
        assert entry.count == 2
        assert entry.first_seen_at == ts1
        assert entry.last_seen_at == ts2

    def test_failure_mode_catalog_holds_entries(self):
        catalog = FailureModeCatalog(project_id="p1")
        entry = FailureModeCatalogEntry(
            project_id="p1",
            fingerprint="x",
            description="desc",
        )
        catalog.add(entry)
        # Get returns same fingerprint entry
        fetched = catalog.get("x")
        assert fetched is not None
        assert fetched.fingerprint == "x"
        # Unknown fingerprint returns None
        assert catalog.get("does-not-exist") is None

    def test_catalog_record_creates_or_increments(self):
        catalog = FailureModeCatalog(project_id="p1")
        catalog.record(
            fingerprint="fp-1",
            description="first error",
            at=datetime(2026, 6, 27),
        )
        catalog.record(
            fingerprint="fp-1",
            description="first error",
            at=datetime(2026, 6, 27, 10, 5, 0),
        )
        assert catalog.get("fp-1").count == 2


# ── EvolutionTrigger ──────────────────────────────────────────────────────


class TestEvolutionTrigger:
    def test_does_not_fire_below_threshold(self):
        trigger = EvolutionTrigger(threshold=3)
        assert trigger.should_fire(count=2) is False
        assert trigger.should_fire(count=0) is False

    def test_fires_at_threshold(self):
        trigger = EvolutionTrigger(threshold=3)
        assert trigger.should_fire(count=3) is True

    def test_fires_above_threshold(self):
        trigger = EvolutionTrigger(threshold=3)
        assert trigger.should_fire(count=4) is True

    def test_default_threshold(self):
        trigger = EvolutionTrigger()
        # Default threshold should be a sensible positive integer
        assert isinstance(trigger.threshold, int)
        assert trigger.threshold >= 1


# ── InMemorySOPPersister CRUD ─────────────────────────────────────────────


class TestInMemorySOPPersister:
    def test_save_and_get(self):
        persister: SOPPersister = InMemorySOPPersister()
        sop = ProjectSOP(
            project_id="p1",
            name="release",
            body="body",
            version=1,
            last_failure_id=None,
            last_evolved_at=datetime(2026, 6, 27),
        )
        persister.save(sop)
        fetched = persister.get(project_id="p1", name="release")
        assert fetched == sop

    def test_get_returns_none_when_missing(self):
        persister: SOPPersister = InMemorySOPPersister()
        result = persister.get(project_id="p1", name="missing")
        assert result is None

    def test_list_filters_by_project(self):
        persister: SOPPersister = InMemorySOPPersister()
        for project_id, name in [("p1", "release"), ("p1", "deploy"), ("p2", "release")]:
            persister.save(
                ProjectSOP(
                    project_id=project_id,
                    name=name,
                    body="body",
                    version=1,
                    last_failure_id=None,
                    last_evolved_at=datetime(2026, 6, 27),
                )
            )
        p1_sops = persister.list(project_id="p1")
        assert len(p1_sops) == 2
        p2_sops = persister.list(project_id="p2")
        assert len(p2_sops) == 1

    def test_save_overwrites_same_key(self):
        persister: SOPPersister = InMemorySOPPersister()
        original = ProjectSOP(
            project_id="p1",
            name="release",
            body="old",
            version=1,
            last_failure_id=None,
            last_evolved_at=datetime(2026, 6, 27),
        )
        evolved = original.evolved(
            new_body="new",
            failure_id="fail-1",
            evolved_at=datetime(2026, 6, 27, 11),
        )
        persister.save(original)
        persister.save(evolved)
        fetched = persister.get(project_id="p1", name="release")
        assert fetched == evolved
        assert fetched.version == 2


# ── DharaSOPPersister stub ────────────────────────────────────────────────


class TestDharaSOPPersister:
    def test_stub_raises_not_implemented(self):
        persister = DharaSOPPersister()
        with pytest.raises(NotImplementedError):
            persister.save(
                ProjectSOP(
                    project_id="p1",
                    name="release",
                    body="body",
                    version=1,
                    last_failure_id=None,
                    last_evolved_at=datetime(2026, 6, 27),
                )
            )

    def test_stub_is_sop_persister(self):
        # DharaSOPPersister implements the SOPPersister protocol
        persister = DharaSOPPersister()
        assert isinstance(persister, SOPPersister)


# ── EvolutionEngine end-to-end ────────────────────────────────────────────


class TestEvolutionEngine:
    def _make_engine(self, threshold=3):
        persister = InMemorySOPPersister()
        trigger = EvolutionTrigger(threshold=threshold)
        catalog = FailureModeCatalog(project_id="p1")
        return EvolutionEngine(
            persister=persister,
            trigger=trigger,
            catalog=catalog,
        ), persister, catalog

    def test_propose_returns_none_below_threshold(self):
        engine, _, _ = self._make_engine(threshold=3)
        for _ in range(2):
            engine.observe_failure(
                fingerprint="fp-1",
                description="error",
                at=datetime(2026, 6, 27),
            )
        proposal = engine.propose(
            sop_name="release",
            current_body="old",
            at=datetime(2026, 6, 27),
        )
        assert proposal is None

    def test_propose_returns_proposal_at_threshold(self):
        engine, persister, catalog = self._make_engine(threshold=3)
        for i in range(3):
            engine.observe_failure(
                fingerprint="fp-1",
                description="error",
                at=datetime(2026, 6, 27, 0, i, 0),
            )
        proposal = engine.propose(
            sop_name="release",
            current_body="old body",
            at=datetime(2026, 6, 27, 1, 0, 0),
        )
        assert proposal is not None
        assert isinstance(proposal, SOPProposal)
        assert proposal.sop_name == "release"
        assert proposal.fingerprint == "fp-1"
        assert proposal.current_body == "old body"
        assert proposal.observed_count == 3

    def test_apply_proposal_writes_new_sop_version(self):
        engine, persister, _ = self._make_engine(threshold=2)
        # Seed an existing SOP
        persister.save(
            ProjectSOP(
                project_id="p1",
                name="release",
                body="old",
                version=1,
                last_failure_id=None,
                last_evolved_at=datetime(2026, 6, 27),
            )
        )
        for i in range(2):
            engine.observe_failure(
                fingerprint="fp-1",
                description="error",
                at=datetime(2026, 6, 27, 0, i, 0),
            )
        proposal = engine.propose(
            sop_name="release",
            current_body="old",
            at=datetime(2026, 6, 27, 1, 0, 0),
        )
        assert proposal is not None
        evolved = engine.apply(
            proposal=proposal,
            new_body="new improved body",
            evolved_at=datetime(2026, 6, 27, 2, 0, 0),
        )
        assert evolved.version == 2
        assert evolved.body == "new improved body"
        assert evolved.last_failure_id == "fp-1"
        # Persister now reflects the evolved SOP
        assert persister.get("p1", "release") == evolved
