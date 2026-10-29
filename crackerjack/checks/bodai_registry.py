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

The registry's ``Path`` column is relative to a *projects root* rather than
absolute — the registry lives in a public repository, so an absolute path
would disclose the operator's account name and local directory layout.
:func:`resolve_projects_root` turns a row back into a location on disk.
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

# Consumer-side override for the projects root. The registry's Path column
# is relative to it; see ``resolve_projects_root``.
PROJECTS_ROOT_ENV_VAR = "BODAI_PROJECTS_ROOT"
DEFAULT_PROJECTS_DIRNAME = "Projects"

# How far up from the working directory to look for a sibling checkout.
_SIBLING_SEARCH_DEPTH = 4

# Markdown table row whose second column is a path:
#   | repo-name | path/relative/to/projects/root/ | >=3.13 | notes... |
# Anchored on the path column so free-form prose rows never match. The
# trailing slash is optional. Both root-relative (``oneiric/``) and legacy
# absolute (``/some/absolute/checkout``) forms match, so a registry
# generated before the relative-path format still resolves.
_TABLE_ROW_RE = re.compile(
    r"^\|\s*(?P<repo>[a-zA-Z0-9_-]+)\s*\|\s*(?P<path>[A-Za-z0-9._~/-]+?)/?\s*\|",
    re.MULTILINE,
)

# Sections that document repos but are out of scope for the fleet guard.
_OUT_OF_SCOPE_HEADINGS = frozenset(
    {
        "deprecated",
        "excluded from scope",
    }
)


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
            "%s points at %s, which is not a file; treating no repos as fleet members",
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


def _is_primary_checkout(repo_root: Path) -> bool:
    """Whether `repo_root` is a primary git checkout rather than a worktree.

    A git worktree's ``.git`` is a *file* that points at the real
    repository; a primary checkout's is a *directory*. The fleet's
    worktree bucket (``~/.local/state/mahavishnu/worktrees/``) holds
    directories named after fleet repos, so the name alone cannot tell a
    projects root from the bucket -- but the ``.git`` entry can.
    """
    return (repo_root / ".git").is_dir()


def resolve_projects_root(registry_path: Path | None = None) -> Path:
    """Resolve the projects root that the registry's Path column is relative to.

    Resolution order (first hit wins):

      1. ``$BODAI_PROJECTS_ROOT`` — explicit operator override.
      2. The registry's own location — the registry lives at
         ``<projects root>/mahavishnu/BODAI_REPO_REGISTRY.md``.
      3. ``~/Projects`` — the standard developer layout.

    Args:
        registry_path: The registry file, when it is known. Passing it lets
            the root be derived from where the registry actually sits, which
            is the most reliable signal available.

    Returns:
        The projects root. Never raises: when nothing can be resolved the
        current working directory is returned, and every repo path derived
        from it simply will not exist.
    """
    override = os.environ.get(PROJECTS_ROOT_ENV_VAR)
    if override:
        return Path(override).expanduser()

    if registry_path is not None:
        repo_dir = registry_path.resolve().parent
        if repo_dir.name == REGISTRY_REPO_DIRNAME and _is_primary_checkout(repo_dir):
            return repo_dir.parent

    try:
        home = Path.home()
    except RuntimeError:
        logger.warning(
            "Cannot resolve the projects root (no home directory, no $%s); "
            "falling back to the working directory",
            PROJECTS_ROOT_ENV_VAR,
        )
        return Path.cwd()
    return home / DEFAULT_PROJECTS_DIRNAME


def _iter_table_paths(text: str) -> Iterator[str]:
    """Yield the raw path cell of every in-scope table row in `text`.

    Sections whose heading mentions "deprecated" or "excluded from scope"
    are skipped, as are the markdown header and separator rows.
    """
    section_excluded = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            lower = stripped.lower()
            section_excluded = any(marker in lower for marker in _OUT_OF_SCOPE_HEADINGS)
            continue
        if section_excluded:
            continue
        match = _TABLE_ROW_RE.match(line)
        if not match:
            continue
        repo = match.group("repo")
        raw = match.group("path")
        # Skip the table's own header ("Repo | Path | ...") and its
        # separator row ("---|--- ...").
        if repo.lower() == "repo" or not raw.strip("-"):
            continue
        yield raw


def _resolve_under_root(raw: str, trusted_root: Path) -> Path | None:
    """Resolve a registry path cell against the trusted projects root.

    Returns ``None`` when the path escapes the root.

    The registry is an *input*, not a trusted constant: it can be pointed at
    any file via ``$CRACKERJACK_BODAI_REGISTRY``, and it is tracked in a
    public repository. A row must therefore not be able to steer the fleet
    tools at an arbitrary directory. The containment check runs on the
    *resolved* path, so ``..`` segments and symlinks whose target lies
    outside the root are both rejected. An absolute path is accepted only
    when it lands inside the root, which keeps a registry generated before
    the relative-path format working.

    Args:
        raw: The path cell from a registry table row.
        trusted_root: The canonical projects root.

    Returns:
        The canonical path, or None when it is not contained by the root.
    """
    # pathlib's join keeps an absolute component absolute, so this handles
    # both the relative and the legacy absolute form.
    candidate = (trusted_root / raw).resolve()
    try:
        relative = candidate.relative_to(trusted_root)
    except ValueError:
        logger.warning(
            "Registry row %r resolves outside the projects root (%s); skipping it",
            raw,
            trusted_root,
        )
        return None
    if not relative.parts:
        # The row points at the root itself, which is not a repo.
        return None
    return candidate


def parse_registry_repo_paths(text: str, root: Path | None = None) -> list[Path]:
    """Extract repo paths from every non-excluded table row in `text`.

    A row qualifies when its second column is a path. The path is relative
    to the projects root, so it is joined against `root` to produce a
    location on disk. Rows that resolve outside the root are skipped.

    Args:
        text: The full registry markdown.
        root: The projects root the Path column is relative to. Defaults to
            :func:`resolve_projects_root` without a registry path.

    Returns:
        The repo paths in document order.
    """
    base = root if root is not None else resolve_projects_root()
    trusted_root = base.resolve()
    paths: list[Path] = []
    for raw in _iter_table_paths(text):
        candidate = _resolve_under_root(raw, trusted_root)
        if candidate is not None:
            paths.append(candidate)
    return paths


@lru_cache(maxsize=1)
def load_fleet_repo_paths() -> frozenset[Path]:
    """Resolve the set of repos that are members of the Bodai fleet.

    Reads the ``### Core 6`` / ``### Web / framework libraries`` / etc.
    sections and pulls the second column (the path) out of every
    ``| ... | ... | ... |`` row. The path is relative to the projects root,
    so it is resolved before the directory check, and rows that resolve
    outside the root are skipped. Only existing directories count. Frozen
    so callers cannot mutate the shared cache.

    Returns:
        The fleet repo paths; empty when the registry cannot be resolved.
    """
    registry = resolve_registry_path()
    if registry is None or not registry.is_file():
        return frozenset()

    trusted_root = resolve_projects_root(registry).resolve()
    paths: set[Path] = set()
    for raw in _iter_table_paths(registry.read_text(encoding="utf-8")):
        candidate = _resolve_under_root(raw, trusted_root)
        if candidate is not None and candidate.is_dir():
            paths.add(candidate)
    return frozenset(paths)
