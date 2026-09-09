from __future__ import annotations

import logging
import shutil
from pathlib import Path

from crackerjack.adapters.base import Hook
from crackerjack.adapters.swift.platforms import parse_platforms

logger = logging.getLogger(__name__)


def _swift_format_command() -> tuple[str, ...]:
    """Per spec Swift F2: prefer third-party swift-format if installed.

    Falls back to built-in ``swift format`` if swift-format is not in
    PATH. The built-in reads ``.swift-format`` config automatically.
    """
    if shutil.which("swift-format") is not None:
        return ("swift-format", "format")
    logger.warning(
        "swift-format (third-party) not in PATH; falling back to built-in "
        "`swift format`. Formatting may diverge from project's CI.",
    )
    return ("swift", "format")


def swift_hooks(package_swift_path: Path) -> tuple[Hook, ...]:
    """Return the Swift hook set.

    Per BLOCKER B1 (Swift lens review): ``swift test -destination`` is
    INVALID — SwiftPM's ``swift test`` does not accept ``-destination``
    (that flag is xcodebuild-only). Verified against Apple Swift 6.3.1:
    neither ``swift test --help`` nor ``swift build --help`` mentions it.

    Consequence: iOS-only packages cannot be tested through these hooks.
    They will fail at runtime with a clear SwiftPM error. Full iOS
    testing support requires ``xcodebuild test``, which is out of Phase 2
    scope (future plan).

    Per spec Swift F4: the original destination-detection requirement is
    broken at the spec level, so no destination flag is emitted here.
    """
    parse_platforms(package_swift_path)  # validates the file; result discarded
    format_cmd = _swift_format_command()

    return (
        Hook(
            name="swift.test",
            cli_command=("swift", "test"),
            timeout_seconds=1800,  # 30min — cold build cache can be slow
        ),
        Hook(
            name="swift.build",
            cli_command=("swift", "build"),
            timeout_seconds=1800,
        ),
        Hook(
            name="swift.format",
            cli_command=format_cmd,
            timeout_seconds=300,
            autofix=True,
        ),
        Hook(
            name="swift.package.update",
            cli_command=("swift", "package", "update"),
            timeout_seconds=300,
            # Per spec Swift F3: Package.resolved changes are reviewed,
            # never applied automatically.
            autofix=False,
        ),
    )
