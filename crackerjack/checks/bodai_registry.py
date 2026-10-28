"""Locate and parse the Bodai fleet registry.

The authoritative registry (``BODAI_REPO_REGISTRY.md``) is maintained in the
*mahavishnu* repo, not in crackerjack, so finding it is a cross-repo lookup
rather than a package-relative one. This module owns both the resolution
chain and the table parsing, so the gitignore conformance gate and the
build-system guard agree on where the registry lives.

Resolution order (first hit wins):

  1. ``$CRACKERJACK_BODAI_REGISTRY`` — explicit operator override.
  2. A sibling ``mahavishnu`` checkout next to the running package.
  3. A sibling ``mahavishnu`` checkout next to the current working
     directory (walking up a few levels).
  4. ``~/Projects/mahavishnu/BODAI_REPO_REGISTRY.md`` — canonical dev layout.

When nothing resolves, the registry is *absent* rather than broken: callers
treat that as "no fleet members" so the gate stays a no-op off-fleet.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from crackerjack.utils.path_redaction import redact_path

logger = logging.getLogger(__name__)


REGISTRY_FILENAME = "BODAI_REPO_REGISTRY.md"
REGISTRY_REPO_DIRNAME = "mahavishnu"
REGISTRY_ENV_VAR = "CRACKERJACK_BODAI_REGISTRY"

# How far up from the working directory to look for a sibling checkout.
_SIBLING_SEARCH_DEPTH = 4

# Markdown table row whose second column is an absolute path:
#   | repo-name | /absolute/path/ | >=3.13 | notes... |
# Anchored on the path column so free-form prose rows never match. The
# trailing slash is optional, and the path itself is machine-independent.
_TABLE_ROW_RE = re.compile(
    r"^\|\s*(?P<repo>[a-zA-Z0-9_-]+)\s*\|\s*(?P<path>/[^\s|]+?)/?\s*\|",
    re.MULTILINE,
)

# Sections that document repos but are out of scope for the fleet guard.
_OUT_OF_SCOPE_HEADINGS = frozenset({
    "deprecated",
    "excluded from scope",
})


def _sibling_candidates(start: Path, depth: int) -> Iterator[Path]:
    """Yield ``<ancestor>/../mahavishnu/<registry>`` for each ancestor of `start`.

    `start` is a checkout root or a working directory. Climbing to its
    parents lets a run from ``~/Projects/crackerjack/tests`` still find the
    sibling ``~/Projects/mahavishnu`` checkout.
    """
    seen: set[Path] = set()
    for level in range(depth):
        candidate = start.parent / REGISTRY_REPO_DIRNAME / REGISTRY_FILENAME
        if candidate not in seen:
            seen.add(candidate)
            yield candidate
        if start.parent == start:
            break
        start = start.parent


def registry_candidates() -> list[Path]:
    """Return the ordered locations the registry is looked for, in priority order."""
    candidates: list[Path] = []

    override = os.environ.get(REGISTRY_ENV_VAR)
    if override:
        candidates.append(Path(override).expanduser())

    # Sibling of the running package. In a source checkout this is
    # ``<repo root>/../mahavishnu``; from an installed wheel it simply does
    # not exist, which is correct.
    package_root = Path(__file__).resolve().parents[2]
    candidates.append(package_root.parent / REGISTRY_REPO_DIRNAME / REGISTRY_FILENAME)

    # Sibling of the working directory, walking up a few levels.
    try:
        cwd = Path.cwd().resolve()
    except OSError:
        cwd = None
    if cwd is not None:
        candidates.extend(_sibling_candidates(cwd, _SIBLING_SEARCH_DEPTH))

    # Canonical developer layout, for a registry that is not a sibling
    # checkout (e.g. a bare clone elsewhere under the home directory).
    try:
        home = Path.home()
    except RuntimeError:
        home = None
    if home is not None:
        candidates.append(home / "Projects" / REGISTRY_REPO_DIRNAME / REGISTRY_FILENAME)

    # De-duplicate while preserving order.
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def resolve_registry_path() -> Path | None:
    """Return the first existing registry file, or None when none is found.

    An explicit ``$CRACKERJACK_BODAI_REGISTRY`` override is *authoritative*:
    if it points at something that is not a file, resolution stops there
    rather than silently falling through to a different registry. Silently
    using another registry would make an operator believe they were testing
    against their override when they were not.
    """
    override = os.environ.get(REGISTRY_ENV_VAR)
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return candidate
        logger.warning(
            "%s points at %s, which is not a file; "
            "treating no repos as fleet members",
            REGISTRY_ENV_VAR,
            redact_path(candidate),
        )
        return None

    candidates = registry_candidates()
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    logger.warning(
        "Bodai registry not found; tried %s; treating no repos as fleet members",
        ", ".join(redact_path(c) for c in candidates),
    )
    return None


def parse_registry_repo_paths(text: str) -> list[Path]:
    """Extract repo paths from every non-excluded table row in `text`.

    A row qualifies when its second column is an absolute path. Sections
    whose heading mentions "deprecated" or "excluded from scope" are
    skipped.

    Args:
        text: The full registry markdown.

    Returns:
        The repo paths in document order.
    """
    paths: list[Path] = []
    section_excluded = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            lower = stripped.lower()
            section_excluded = any(
                marker in lower for marker in _OUT_OF_SCOPE_HEADINGS
            )
            continue
        if section_excluded:
            continue
        match = _TABLE_ROW_RE.match(line)
        if not match:
            continue
        paths.append(Path(match.group("path")))
    return paths


@lru_cache(maxsize=1)
def load_fleet_repo_paths() -> frozenset[Path]:
    """Resolve the set of repos that are members of the Bodai fleet.

    Reads the ``### Core 7`` / ``### Web / framework libraries`` / etc.
    sections and pulls the second column (the path) out of every
    ``| ... | ... | ... |`` row. Only existing directories count. Frozen so
    callers cannot mutate the shared cache.

    Returns:
        The fleet repo paths; empty when the registry cannot be resolved.
    """
    registry = resolve_registry_path()
    if registry is None or not registry.is_file():
        return frozenset()

    paths: set[Path] = set()
    in_table = False
    for line in registry.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            in_table = True
            continue
        if stripped.startswith("##"):
            in_table = False
            continue
        if not in_table or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.split("|") if c.strip()]
        if len(cells) < 2:
            continue
        candidate = cells[1].rstrip("/")
        if candidate.startswith("/") and Path(candidate).is_dir():
            paths.add(Path(candidate).resolve())
    return frozenset(paths)
