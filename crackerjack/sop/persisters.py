"""SOP persister protocol + in-memory implementation + Dhara stub.

The protocol intentionally mirrors the minimal CRUD surface needed by the
evolution engine:

- ``save(sop)`` -- upsert keyed by ``(project_id, name)``
- ``get(project_id, name)`` -- fetch a single SOP or ``None``
- ``list(project_id)`` -- return all SOPs for one project

Two implementations ship today:

1. :class:`InMemorySOPPersister` -- used by tests + dev
2. :class:`DharaSOPPersister` -- stub that raises ``NotImplementedError`` until
   the Dhara-backed substrate lands (documented follow-up).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from crackerjack.sop.models import ProjectSOP


@runtime_checkable
class SOPPersister(Protocol):
    """Storage interface for ProjectSOPs."""

    def save(self, sop: ProjectSOP) -> None:
        """Persist (upsert) a SOP keyed by ``(project_id, name)``."""
        ...

    def get(self, project_id: str, name: str) -> ProjectSOP | None:
        """Fetch a SOP by its natural key, or ``None`` if missing."""
        ...

    def list(self, project_id: str) -> list[ProjectSOP]:
        """Return all SOPs belonging to one project."""
        ...


class InMemorySOPPersister:
    """In-memory SOPPersister suitable for tests and local development."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], ProjectSOP] = {}

    def save(self, sop: ProjectSOP) -> None:
        self._store[(sop.project_id, sop.name)] = sop

    def get(self, project_id: str, name: str) -> ProjectSOP | None:
        return self._store.get((project_id, name))

    def list(self, project_id: str) -> list[ProjectSOP]:
        return [
            sop for (pid, _name), sop in self._store.items() if pid == project_id
        ]


class DharaSOPPersister:
    """Stub for the Dhara-backed SOP persister.

    Will be implemented when the Dhara substrate exposes the
    ``project_sops`` collection. Until then this stub raises
    ``NotImplementedError`` so callers fail loudly rather than silently
    persist to the wrong store.
    """

    def save(self, sop: ProjectSOP) -> None:
        # TODO(spec-7-dhara): implement when Dhara ``project_sops`` lands
        raise NotImplementedError(
            "DharaSOPPersister.save is a stub pending Dhara project_sops "
            "collection (Spec #7 follow-up)."
        )

    def get(self, project_id: str, name: str) -> ProjectSOP | None:
        raise NotImplementedError(
            "DharaSOPPersister.get is a stub pending Dhara project_sops "
            "collection (Spec #7 follow-up)."
        )

    def list(self, project_id: str) -> list[ProjectSOP]:
        raise NotImplementedError(
            "DharaSOPPersister.list is a stub pending Dhara project_sops "
            "collection (Spec #7 follow-up)."
        )