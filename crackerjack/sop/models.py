
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProjectSOP:

    project_id: str
    name: str
    body: str
    version: int = 1
    last_failure_id: str | None = None
    last_evolved_at: datetime | None = None

    def evolved(
        self,
        new_body: str,
        failure_id: str,
        evolved_at: datetime,
    ) -> ProjectSOP:
        return ProjectSOP(
            project_id=self.project_id,
            name=self.name,
            body=new_body,
            version=self.version + 1,
            last_failure_id=failure_id,
            last_evolved_at=evolved_at,
        )


@dataclass
class FailureModeCatalogEntry:

    project_id: str
    fingerprint: str
    description: str
    count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

    def record(self, at: datetime) -> None:
        if self.first_seen_at is None:
            self.first_seen_at = at
        self.last_seen_at = at
        self.count += 1


@dataclass
class FailureModeCatalog:

    project_id: str
    _entries: dict[str, FailureModeCatalogEntry] = field(default_factory=dict)

    def add(self, entry: FailureModeCatalogEntry) -> None:
        self._entries[entry.fingerprint] = entry

    def get(self, fingerprint: str) -> FailureModeCatalogEntry | None:
        return self._entries.get(fingerprint)

    def record(
        self,
        fingerprint: str,
        description: str,
        at: datetime,
    ) -> FailureModeCatalogEntry:
        entry = self._entries.get(fingerprint)
        if entry is None:
            entry = FailureModeCatalogEntry(
                project_id=self.project_id,
                fingerprint=fingerprint,
                description=description,
            )
            self._entries[fingerprint] = entry
        entry.record(at=at)
        return entry
