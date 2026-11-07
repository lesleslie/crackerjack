"""Move runtime data from its old location to its XDG home.

Crackerjack's runtime data has moved between locations as the XDG
namespace decision was implemented: the async task store and the health
integration database moved into ``$XDG_DATA_HOME/crackerjack``, and the
AI-fix run history and the log directory into
``$XDG_STATE_HOME/crackerjack``. Each move strands whatever was already
at the old path.

These helpers perform that move. The rules they follow:

* **A move never destroys data.** The target is only written when it
  does not already exist; an existing target is left exactly as it is
  and the legacy copy stays put.
* **A failed move leaves the legacy copy intact.** The failure is
  logged and the caller carries on - a migration is a convenience, not
  a gate.
* **A symlink is not followed.** Moving the *link* would be harmless,
  but moving what it points at would not be, and the legacy paths here
  are all regular files and directories.

The helpers are deliberately free of any knowledge of *which* paths they
move: the caller decides that. Nothing here runs at import time.
"""

from __future__ import annotations

import logging
import shutil
from contextlib import suppress
from pathlib import Path

from crackerjack.utils.path_redaction import redact_path

logger = logging.getLogger(__name__)

__all__ = ["migrate_legacy_dir", "migrate_legacy_file"]


def migrate_legacy_file(legacy: Path, target: Path) -> bool:
    """Move *legacy* to *target* when that is safe to do.

    Args:
        legacy: The file's old location.
        target: Where the file should live now.

    Returns:
        ``True`` when the file was moved. ``False`` when there was
        nothing to move, when the target already exists, when the
        legacy path is a symlink or a directory, or when the move
        failed - in every one of those cases the legacy file is left
        exactly where it was.
    """
    if legacy.is_symlink() or not legacy.is_file():
        return False
    if target.exists():
        logger.info(
            "Not migrating %s: %s already exists",
            legacy.name,
            redact_path(target),
        )
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(target))
    except OSError as exc:
        logger.warning(
            "Could not migrate %s to %s (%s); the file stays where it is",
            legacy.name,
            redact_path(target),
            type(exc).__name__,
        )
        return False
    logger.info("Migrated %s to %s", legacy.name, redact_path(target))
    return True


def migrate_legacy_dir(legacy: Path, target: Path) -> bool:
    """Move the *contents* of *legacy* into *target*.

    The contents are merged rather than the directory replaced: the
    target may already hold state from a newer run, and a child that
    exists there is left alone.

    Args:
        legacy: The directory's old location.
        target: Where the contents should live now.

    Returns:
        ``True`` when at least one child was moved. ``False`` when
        there was nothing to move, when the legacy path is not a
        directory, or when every child was already present at the
        target - in that last case the legacy directory is left in
        place with its contents intact.
    """
    if legacy.is_symlink() or not legacy.is_dir():
        return False
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning(
            "Could not prepare %s for migration (%s); the directory stays where it is",
            redact_path(target),
            type(exc).__name__,
        )
        return False

    moved = False
    for child in sorted(legacy.iterdir()):
        destination = target / child.name
        if destination.exists():
            continue
        try:
            shutil.move(str(child), str(destination))
        except OSError as exc:
            logger.warning(
                "Could not migrate %s (%s); it stays where it is",
                child.name,
                type(exc).__name__,
            )
            continue
        moved = True

    if moved:
        logger.info(
            "Migrated the contents of %s to %s", legacy.name, redact_path(target)
        )
        # A directory that is not empty any more, or that cannot be
        # removed, is harmless. The contents are already moved.
        with suppress(OSError):
            if not any(legacy.iterdir()):
                legacy.rmdir()
    return moved
