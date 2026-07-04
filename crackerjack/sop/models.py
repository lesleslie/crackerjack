"""SOP domain models.

This module defines the core data shapes for project-scoped SOPs and the
failure-mode catalog:

- :class:`ProjectSOP` -- a versioned SOP body keyed by ``(project_id, name)``
- :class:`FailureModeCatalog` -- per-project collection of failure modes
- :class:`FailureModeCatalogEntry` -- one observed failure mode + counters

All classes are plain dataclasses so they're cheap to construct in tests and
cheap to serialize for the upcoming Dhara-backed persister.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProjectSOP:
    """A versioned standard operating procedure scoped to one project.

    ``(project_id, name)`` is the natural key. ``evolved`` produces a new
    ProjectSOP with ``version + 1`` and an updated ``last_failure_id`` /
    ``last_evolved_at`` -- the original instance is left untouched.
    """

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
        """Return a new ProjectSOP with body replaced and version bumped.

        The original ProjectSOP is left unchanged so callers can keep an
        audit trail of every evolution.
        """
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
    """A single observed failure mode within one project.

    ``count`` starts at zero and grows by one per ``record()`` call.
    ``first_seen_at`` / ``last_seen_at`` capture the observation timestamps.
    """

    project_id: str
    fingerprint: str
    description: str
    count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

    def record(self, at: datetime) -> None:
        """Record an occurrence and update timestamps."""
        if self.first_seen_at is None:
            self.first_seen_at = at
        self.last_seen_at = at
        self.count += 1


@dataclass
class FailureModeCatalog:
    """Per-project catalog of failure mode entries keyed by fingerprint."""

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
        """Record an occurrence; create the entry if it doesn't exist yet."""
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
