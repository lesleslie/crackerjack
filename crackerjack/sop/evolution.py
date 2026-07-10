from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from crackerjack.sop.models import (
    FailureModeCatalog,
    FailureModeCatalogEntry,
    ProjectSOP,
)
from crackerjack.sop.persisters import SOPPersister

DEFAULT_THRESHOLD = 3


@dataclass
class EvolutionTrigger:
    threshold: int = DEFAULT_THRESHOLD

    def should_fire(self, count: int) -> bool:
        return count >= self.threshold


@dataclass
class SOPProposal:
    sop_name: str
    fingerprint: str
    current_body: str
    observed_count: int
    proposed_at: datetime


class EvolutionEngine:
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
