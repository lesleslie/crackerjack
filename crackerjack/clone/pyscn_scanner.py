"""Run pyscn's clone scan and group the clone pairs it finds.

This is a *feature*, not a quality check: it produces clone groups for
the refactoring engine, so it lives beside ``grouper.py`` and
``classifier.py`` rather than under ``crackerjack/adapters/``.
"""

from __future__ import annotations

import glob
import json
import logging
import subprocess
from pathlib import Path

from crackerjack.clone.grouper import CloneGroup, CloneGrouper
from crackerjack.config.tool_commands import preferred_binary_command_with_min_version

logger = logging.getLogger(__name__)

DEFAULT_CLONE_THRESHOLD = 0.9
CLONE_SCAN_TIMEOUT_SECONDS = 300


class PyscnCloneScanError(RuntimeError):
    """pyscn's clone scan could not be run, or its report could not be read.

    Deliberately distinct from "no clones found": an empty result means
    the scan ran cleanly and found nothing, while this exception means
    the scan's outcome is unknown. Callers must not report the latter
    as a clean repo -- that turns a broken toolchain into a silent pass.
    """


def scan_clone_groups(
    repo_root: Path,
    threshold: float = DEFAULT_CLONE_THRESHOLD,
) -> list[CloneGroup]:
    """Run pyscn's clone scan over ``repo_root`` and group the clone pairs.

    Returns:
        The clone groups found. An empty list means the scan ran cleanly
        and found nothing.

    Raises:
        PyscnCloneScanError: the scan could not be run, or its report
            could not be read.
    """
    report_dir = repo_root / ".pyscn" / "reports"

    try:
        result = subprocess.run(
            preferred_binary_command_with_min_version(
                "pyscn",
                "1.30",
                "analyze",
                "--json",
                "--select",
                "clones",
                "--clone-threshold",
                str(threshold),
                str(repo_root),
            ),
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=CLONE_SCAN_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise PyscnCloneScanError(f"pyscn clone scan failed: {exc}") from exc

    if result.returncode not in (0, 1):
        raise PyscnCloneScanError(
            f"pyscn exited with code {result.returncode}: {result.stderr.strip()}"
        )

    pattern = str(report_dir / "analyze_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        # pyscn only writes a report when it finds clones, so a missing
        # report means "nothing found", not a failure.
        logger.info("pyscn: no clone report in %s", report_dir)
        return []

    try:
        with open(files[-1], encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise PyscnCloneScanError(f"could not parse pyscn JSON report: {exc}") from exc

    raw_pairs: list[dict] = (data.get("clone") or {}).get("clone_pairs") or []
    groups = CloneGrouper().group_pairs(raw_pairs)
    logger.info("pyscn: parsed %d clone groups from JSON report", len(groups))
    return groups
