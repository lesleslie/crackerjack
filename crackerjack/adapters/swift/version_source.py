from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from crackerjack.adapters.base import (
    VersionNotFoundError,
    VersionSource,
)

logger = logging.getLogger(__name__)


_SEMVER_TAG_PATTERN = re.compile(r"v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class GitTagVersionSource(VersionSource):
    """Reads the project version from the most recent ``v*`` git tag.

    Swift treats the git tag as the source of truth for project version
    (per spec Swift F1). The SwiftLifecycle creates and deletes tags via
    ``_reset`` rather than rewriting a manifest file, so :meth:`write` is a
    no-op for Phase 2.

    Read flow (per Security F7/F8):

    1. Run ``git describe --tags --abbrev=0 --match 'v*'`` in the repo root.
    2. Reject the output if it starts with ``--`` (defense-in-depth against
       tag names that could otherwise be interpreted as ``git`` flags).
    3. Validate the tag against :data:`_SEMVER_TAG_PATTERN`. Any tag that does
       not match is treated as "no version found" so the SwiftLifecycle can
       surface a consistent error rather than propagating corrupted
       ``git describe`` output.
    4. ``lstrip("v")`` and return the bare semver string.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def read(self) -> str:
        completed = subprocess.run(
            [
                "git",
                "describe",
                "--tags",
                "--abbrev=0",
                "--match",
                "v*",
            ],
            cwd=self._project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            logger.debug(
                "git describe failed (rc=%s): %s",
                completed.returncode,
                completed.stderr.strip(),
            )
            raise VersionNotFoundError(
                f"No v*-tagged version in {self._project_root}",
            )

        tag = completed.stdout.strip()
        if not tag or tag.startswith("--"):
            raise VersionNotFoundError(
                f"Refusing to parse tag that looks like a git flag: {tag!r}",
            )
        if not _SEMVER_TAG_PATTERN.match(tag):
            raise VersionNotFoundError(
                f"Tag {tag!r} does not match semver pattern",
            )

        return tag.lstrip("v")

    def write(self, new_version: str) -> None:
        # No-op per spec Swift F1: SwiftLifecycle resets the tag instead of
        # rewriting a manifest file, so write() deliberately performs no I/O.
        return
