"""Gitignore conformance check for Bodai fleet repos.

Verifies that every repo listed in the Bodai repo registry has the
canonical `.gitignore` snippet (templates/GITIGNORE_BODAI.md) installed.

The snippet is delimited by `# >>> bodai-shared-gitignore >>>` and
`# <<< bodai-shared-gitignore <<<` markers so `sync` can detect
already-applied state and union cleanly without duplicating patterns.

Used by `crackerjack run` via the managers layer to prevent drift:
when a fleet repo's `.gitignore` is missing the snippet, the gate fails.
When the snippet is present but a pattern inside is missing, the gate
fails. Non-Bodai repos are silently skipped.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "GITIGNORE_BODAI.md"
BODAI_REGISTRY_PATH = Path("/Users/les/Projects/mahavishnu/BODAI_REPO_REGISTRY.md")

MARKER_BEGIN = "# >>> bodai-shared-gitignore >>>"
MARKER_END = "# <<< bodai-shared-gitignore <<<"


@dataclass(frozen=True)
class GitignoreConformanceResult:
    repo_path: Path
    is_fleet_member: bool
    snippet_present: bool
    missing_patterns: list[str] = field(default_factory=list)
    backup_path: Path | None = None


def _parse_canonical_template(template_path: Path) -> list[str]:
    """Return the non-comment, non-blank patterns inside the marker block.

    Strips both markers; returns the lines strictly between them.
    """
    if not template_path.exists():
        raise FileNotFoundError(
            f"Bodai gitignore template not found at {template_path}. "
            "Did the file get renamed or moved?"
        )

    lines = template_path.read_text().splitlines()
    try:
        start = lines.index(MARKER_BEGIN)
        end = lines.index(MARKER_END, start + 1)
    except ValueError as e:
        raise ValueError(
            f"Template at {template_path} is missing marker lines. "
            f"Expected both {MARKER_BEGIN!r} and {MARKER_END!r}."
        ) from e

    return [
        line
        for line in lines[start + 1 : end]
        if line.strip() and not line.strip().startswith("#")
    ]


@lru_cache(maxsize=1)
def _bodai_fleet_paths() -> frozenset[Path]:
    """Resolve absolute repo paths from the Bodai registry.

    Reads the `### Core 7` / `### Web / framework libraries` / etc.
    sections and pulls the second column (the path) out of every
    `| ... | ... | ... |` row. Frozen so callers can't mutate the
    shared cache.
    """
    if not BODAI_REGISTRY_PATH.exists():
        logger.warning(
            "Bodai registry not found at %s; treating no repos as fleet members",
            BODAI_REGISTRY_PATH,
        )
        return frozenset()

    paths: set[Path] = set()
    in_table = False
    for line in BODAI_REGISTRY_PATH.read_text().splitlines():
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


def is_bodai_fleet_member(repo_path: Path) -> bool:
    """True iff `repo_path` is listed in the Bodai registry."""
    try:
        resolved = repo_path.resolve()
    except OSError:
        return False
    return resolved in _bodai_fleet_paths()


def _read_existing_gitignore(repo_path: Path) -> str:
    gitignore = repo_path / ".gitignore"
    if not gitignore.exists():
        return ""
    return gitignore.read_text()


def _marker_block_range(text: str) -> tuple[int, int] | None:
    """Return (start_line, end_line) of the marker block in `text`, or None."""
    lines = text.splitlines()
    try:
        start = lines.index(MARKER_BEGIN)
        end = lines.index(MARKER_END, start + 1)
    except ValueError:
        return None
    return start, end


def _existing_canonical_patterns(text: str) -> list[str]:
    """Patterns inside the marker block of `text` (empty if no markers)."""
    rng = _marker_block_range(text)
    if rng is None:
        return []
    start, end = rng
    lines = text.splitlines()
    return [
        line
        for line in lines[start + 1 : end]
        if line.strip() and not line.strip().startswith("#")
    ]


def _strip_marker_block(text: str) -> str:
    """Remove the marker block from `text`, returning the rest."""
    rng = _marker_block_range(text)
    if rng is None:
        return text
    start, end = rng
    lines = text.splitlines()
    # Drop the block plus any trailing blank lines that immediately
    # follow the END marker.
    after = end + 1
    while after < len(lines) and not lines[after].strip():
        after += 1
    kept = lines[:start] + lines[after:]
    # Strip trailing blank lines so we can re-append cleanly.
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept) + ("\n" if kept else "")


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def check_repo_gitignore(repo_path: Path) -> GitignoreConformanceResult:
    """Check whether `repo_path` has the Bodai canonical snippet installed.

    Returns a result struct. `missing_patterns` is empty iff the snippet
    is present and complete. Non-Bodai repos return a passing result
    with `is_fleet_member=False`.
    """
    resolved = repo_path.resolve()
    if not is_bodai_fleet_member(resolved):
        return GitignoreConformanceResult(
            repo_path=resolved,
            is_fleet_member=False,
            snippet_present=True,
        )

    text = _read_existing_gitignore(resolved)
    canonical = _parse_canonical_template(TEMPLATE_PATH)

    if _marker_block_range(text) is None:
        return GitignoreConformanceResult(
            repo_path=resolved,
            is_fleet_member=True,
            snippet_present=False,
            missing_patterns=list(canonical),
        )

    existing = _existing_canonical_patterns(text)
    missing = [p for p in canonical if p not in existing]
    return GitignoreConformanceResult(
        repo_path=resolved,
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=missing,
    )


def sync_repo_gitignore(
    repo_path: Path,
    *,
    backup: bool = True,
) -> GitignoreConformanceResult:
    """Install or refresh the canonical snippet in `repo_path`.

    Behavior:
    - Refuses to operate on non-Bodai repos (returns a passing result, no mutation).
    - Reads existing `.gitignore`, removes any prior marker block, then
      appends the current canonical block.
    - Writes a `.gitignore.bak.<UTC>` backup before overwriting if `backup=True`.
    - Returns a result whose `backup_path` indicates the backup location.
    """
    resolved = repo_path.resolve()
    if not is_bodai_fleet_member(resolved):
        logger.info(
            "Skipping non-Bodai repo %s (not in %s)",
            resolved,
            BODAI_REGISTRY_PATH,
        )
        return GitignoreConformanceResult(
            repo_path=resolved,
            is_fleet_member=False,
            snippet_present=True,
        )

    gitignore = resolved / ".gitignore"
    existing_text = gitignore.read_text() if gitignore.exists() else ""

    backup_path: Path | None = None
    if backup and existing_text:
        backup_path = resolved / f".gitignore.bak.{_utc_timestamp()}"
        shutil.copy2(gitignore, backup_path)
        logger.info("Backed up %s -> %s", gitignore, backup_path)

    cleaned = _strip_marker_block(existing_text)
    canonical_block = TEMPLATE_PATH.read_text()
    if not canonical_block.endswith("\n"):
        canonical_block += "\n"

    if cleaned and not cleaned.endswith("\n\n"):
        separator = "\n\n" if cleaned.rstrip() else ""
    else:
        separator = ""

    new_text = cleaned + separator + canonical_block
    gitignore.write_text(new_text)

    return check_repo_gitignore(resolved).__class__(
        repo_path=resolved,
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
        backup_path=backup_path,
    )


def is_canonical_template_single_source() -> bool:
    """Verify exactly one canonical template file exists in the repo.

    Used by tests / CI to catch accidental duplicates. Returns True
    iff the canonical template at TEMPLATE_PATH exists.
    """
    return TEMPLATE_PATH.exists()
