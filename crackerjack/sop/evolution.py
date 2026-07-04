"""SOP evolution engine.

Workflow:

1. ``EvolutionEngine.observe_failure`` records a failure occurrence into the
   per-project :class:`FailureModeCatalog`.
2. ``EvolutionEngine.propose`` consults the
   :class:`EvolutionTrigger` (threshold-based) and produces an
   :class:`SOPProposal` when the catalog's count crosses the threshold.
3. ``EvolutionEngine.apply`` materializes the proposal -- constructs a new
   :class:`ProjectSOP` (bumped version, recorded failure id) and persists it
   via the configured :class:`SOPPersister`.

The trigger defaults to ``threshold=3`` per the spec. Reviewers may inspect a
proposal before calling ``apply`` -- the engine never auto-applies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from crackerjack.sop.models import (
    FailureModeCatalog,
    ProjectSOP,
)
from crackerjack.sop.persisters import SOPPersister

DEFAULT_THRESHOLD = 3


@dataclass
class EvolutionTrigger:
    """Threshold-based trigger for proposing an SOP evolution."""

    threshold: int = DEFAULT_THRESHOLD

    def should_fire(self, count: int) -> bool:
        return count >= self.threshold


@dataclass
class SOPProposal:
    """A pending SOP edit surfaced for human review.

    The engine produces this when a failure fingerprint has been observed
    at least ``trigger.threshold`` times. Reviewers then decide whether to
    call ``EvolutionEngine.apply`` with a new body.
    """

    sop_name: str
    fingerprint: str
    current_body: str
    observed_count: int
    proposed_at: datetime


class EvolutionEngine:
    """Wires failure observations -> evolution proposals -> SOP versions."""

    def __init__(
        self,
        persister: SOPPersister,
        trigger: EvolutionTrigger,
        catalog: FailureModeCatalog,
    ) -> None:
        self.persister = persister
        self.trigger = trigger
        self.catalog = catalog

    def observe_failure(
        self,
        fingerprint: str,
        description: str,
        at: datetime,
    ) -> None:
        """Record one failure-mode occurrence into the catalog."""
        self.catalog.record(
            fingerprint=fingerprint,
            description=description,
            at=at,
        )

    def propose(
        self,
        sop_name: str,
        current_body: str,
        at: datetime,
    ) -> SOPProposal | None:
        """Return an ``SOPProposal`` if any tracked fingerprint crossed the
        trigger threshold. Otherwise return ``None``.

        The engine considers every fingerprint in the catalog whose count
        crossed the threshold and returns the highest-count one. If multiple
        fingerprints are tied, the first in iteration order wins -- the
        catalog is small at this stage, and ordering does not affect
        correctness (each proposal is one new SOP version).
        """
        candidate: tuple[int, FailureModeCatalogEntry] | None = None
        for entry in self.catalog._entries.values():  # noqa: SLF001
            if self.trigger.should_fire(entry.count):
                if candidate is None or entry.count > candidate[0]:
                    candidate = (entry.count, entry)

        if candidate is None:
            return None

        _, entry = candidate
        return SOPProposal(
            sop_name=sop_name,
            fingerprint=entry.fingerprint,
            current_body=current_body,
            observed_count=entry.count,
            proposed_at=at,
        )

    def apply(
        self,
        proposal: SOPProposal,
        new_body: str,
        evolved_at: datetime,
    ) -> ProjectSOP:
        """Materialize a proposal: evolve the existing SOP and persist it.

        Looks up the existing SOP via the persister (scoped to the catalog's
        ``project_id``). If no SOP exists yet for ``(project_id, name)`` the
        engine creates a fresh one at version 1 with the proposed body.
        """
        project_id = self.catalog.project_id
        existing = self.persister.get(project_id, proposal.sop_name)
        if existing is None:
            evolved = ProjectSOP(
                project_id=project_id,
                name=proposal.sop_name,
                body=new_body,
                version=1,
                last_failure_id=proposal.fingerprint,
                last_evolved_at=evolved_at,
            )
        else:
            evolved = existing.evolved(
                new_body=new_body,
                failure_id=proposal.fingerprint,
                evolved_at=evolved_at,
            )
        self.persister.save(evolved)
        return evolved