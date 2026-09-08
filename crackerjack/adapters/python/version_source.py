from __future__ import annotations

import logging
import re
from pathlib import Path

from crackerjack.adapters.base import (
    VersionNotFoundError,
    VersionSource,
    VersionWriteError,
)

logger = logging.getLogger(__name__)


_VERSION_PATTERN = re.compile(
    r'^(?P<prefix>\s*version\s*=\s*")(?P<version>[^"]+)(?P<suffix>"\s*(?:#.*)?$)',
    re.MULTILINE,
)


class PyprojectVersionSource(VersionSource):
    """Reads and writes ``[project] version`` from ``pyproject.toml``.

    Uses :class:`crackerjack.services.config_parsers.TOMLParser` for
    reads, and a regex-based replacement for writes (which the
    underlying TOML parser does not support cleanly). Read-back
    verification is mandatory per spec API F8.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._pyproject_path = project_root / "pyproject.toml"

    def read(self) -> str:
        from crackerjack.services.config_parsers import TOMLParser

        parser = TOMLParser()
        data = parser.load(self._pyproject_path)
        try:
            version = data["project"]["version"]
        except (KeyError, TypeError) as exc:
            logger.exception(
                "Failed to read [project] version from %s", self._pyproject_path
            )
            raise VersionNotFoundError(
                f"No [project] version in {self._pyproject_path}",
            ) from exc
        if not isinstance(version, str) or not version.strip():
            raise VersionNotFoundError(
                f"Empty [project] version in {self._pyproject_path}",
            )
        return version.strip()

    def write(self, new_version: str) -> None:
        original = self._pyproject_path.read_text()

        match = _VERSION_PATTERN.search(original)
        if match is None:
            raise VersionWriteError(
                f"Could not locate [project] version line in {self._pyproject_path}",
            )

        replacement = f"{match.group('prefix')}{new_version}{match.group('suffix')}"
        rewritten = _VERSION_PATTERN.sub(replacement, original, count=1)
        self._pyproject_path.write_text(rewritten)

        # Verify by reading back (mandatory per spec API F8).
        try:
            actual = self.read()
        except VersionNotFoundError as exc:
            logger.exception("Read-back after write failed: missing version")
            raise VersionWriteError(
                f"Read-back after write failed: {exc}",
            ) from exc

        if actual != new_version:
            raise VersionWriteError(
                f"Read-back mismatch: wrote {new_version!r}, got {actual!r}",
            )
