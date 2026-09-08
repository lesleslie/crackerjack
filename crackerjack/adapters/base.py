from __future__ import annotations

import abc
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class VersionSourceError(Exception):
    """Base class for version-source errors."""


class VersionNotFoundError(VersionSourceError):
    """The version could not be located in the source file."""


class VersionWriteError(VersionSourceError):
    """The version was successfully parsed but could not be written back."""


# ---------------------------------------------------------------------------
# Version source
# ---------------------------------------------------------------------------


class VersionSource(Protocol):
    """Reads and writes a project's version.

    Implementations MUST verify by reading back after writing.
    """

    def read(self) -> str:
        """Return the current version.

        Raises:
            VersionNotFoundError: if the version cannot be located.
        """
        ...

    def write(self, new_version: str) -> None:
        """Write a new version.

        Raises:
            VersionWriteError: if the write fails or read-back verification fails.
        """
        ...


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hook:
    """A single hook (lint, test, format, etc.) that an adapter can run.

    Only ``name`` and ``cli_command`` are required. All other fields default.
    """

    name: str
    cli_command: tuple[str, ...]
    fallback: Callable[..., Any] | None = None
    timeout_seconds: int = 600
    autofix: bool = False
    cli_required: bool = True


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Capabilities:
    """What a LanguageAdapter offers for a given project.

    Replaces the original 4-method Protocol decomposition. One method,
    one return value; no None-vs-empty ambiguity.
    """

    version_source: VersionSource | None = None
    hooks: tuple[Hook, ...] = ()
    has_lifecycle: bool = False

    @property
    def has_version(self) -> bool:
        return self.version_source is not None


# ---------------------------------------------------------------------------
# Adapter Protocol + ABC
# ---------------------------------------------------------------------------


@runtime_checkable
class LanguageAdapter(Protocol):
    """Protocol for crackerjack language adapters.

    Subclass :class:`LanguageAdapterBase` (recommended) for shared
    validation and registry integration, or implement this Protocol
    directly.

    The ``@runtime_checkable`` decorator enables ``isinstance()``
    validation for third-party adapter loaders.
    """

    name: ClassVar[str]  # kebab-case; used in CLI subcommands and MCP tool names

    def detect(self, project_root: Path) -> bool:
        """Return True if this adapter applies to the project."""
        ...

    def capabilities(self, project_root: Path) -> Capabilities:
        """Single source of truth for what this adapter offers."""
        ...


class LanguageAdapterBase(abc.ABC):
    """Recommended base class for third-party :class:`LanguageAdapter` authors.

    Subclassing is preferred over raw Protocol implementation for
    non-trivial adapters. Provides a concrete ``detect`` override hook
    and a default ``capabilities`` that subclasses customize.
    """

    name: ClassVar[str]  # Subclass must set

    @abc.abstractmethod
    def detect(self, project_root: Path) -> bool:
        ...

    @abc.abstractmethod
    def capabilities(self, project_root: Path) -> Capabilities:
        ...


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LifecycleOptions:
    """Inputs for :meth:`Lifecycle.run`."""

    level: Literal["major", "minor", "patch"]
    commit: bool = True
    tag: bool = True
    push: bool = True
    release: bool = False
    dry_run: bool = False

    def __post_init__(self) -> None:
        if self.level not in ("major", "minor", "patch"):
            raise ValueError(
                f"level must be one of 'major', 'minor', 'patch'; got {self.level!r}"
            )


@dataclass(frozen=True)
class LifecycleResult:
    """Outputs of :meth:`Lifecycle.run`."""

    new_version: str
    commit_sha: str | None
    tag_name: str | None
    release_url: str | None
    skipped_steps: tuple[str, ...] = field(default_factory=tuple)


class Lifecycle(Protocol):
    """Executes bump+commit+tag+push+release with rollback on failure.

    On any failure mid-flow: delete tag, reset commit, raise.
    Caller receives the exception with context; can retry with
    ``dry_run=True`` to test.
    """

    def run(self, options: LifecycleOptions) -> LifecycleResult:
        ...
