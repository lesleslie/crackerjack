"""Project-scoped SOP evolution substrate (Spec #7).

SOPs (standard operating procedures) live per project and evolve based on
recurring failure modes. The substrate for now is in-memory; a Dhara-backed
persister is documented as a stub.
"""

from __future__ import annotations

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

__all__ = [
    "EvolutionEngine",
    "EvolutionTrigger",
    "SOPProposal",
    "FailureModeCatalog",
    "FailureModeCatalogEntry",
    "ProjectSOP",
    "DharaSOPPersister",
    "InMemorySOPPersister",
    "SOPPersister",
]
