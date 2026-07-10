from __future__ import annotations

import builtins
from typing import Protocol, runtime_checkable

from crackerjack.sop.models import ProjectSOP


@runtime_checkable
class SOPPersister(Protocol):
    def save(self, sop: ProjectSOP) -> None: ...

    def get(self, project_id: str, name: str) -> ProjectSOP | None: ...

    def list(self, project_id: str) -> builtins.list[ProjectSOP]: ...


class InMemorySOPPersister:
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], ProjectSOP] = {}

    def save(self, sop: ProjectSOP) -> None:
        self._store[(sop.project_id, sop.name)] = sop

    def get(self, project_id: str, name: str) -> ProjectSOP | None:
        return self._store.get((project_id, name))

    def list(self, project_id: str) -> builtins.list[ProjectSOP]:
        return [sop for (pid, _name), sop in self._store.items() if pid == project_id]


class DharaSOPPersister:
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

    def list(self, project_id: str) -> builtins.list[ProjectSOP]:
        raise NotImplementedError(
            "DharaSOPPersister.list is a stub pending Dhara project_sops "
            "collection (Spec #7 follow-up)."
        )
