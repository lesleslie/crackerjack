from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


_PLATFORM_PATTERN = re.compile(r"\.([A-Za-z]+)\s*\(")
_PLATFORMS_BLOCK = re.compile(
    r"platforms\s*:\s*\[([^\]]*)\]",
    re.DOTALL,
)


@dataclass(frozen=True)
class PlatformInfo:
    """Parsed `Package.swift` `platforms:` directive."""

    platforms: tuple[str, ...]
    requires_ios_destination: bool
    requires_visionos_destination: bool
    requires_macos_destination: bool

    @property
    def has_apple_simulator_target(self) -> bool:
        """True if Package.swift targets at least one Apple platform (iOS, visionOS, etc.)."""
        return self.requires_ios_destination or self.requires_visionos_destination


def parse_platforms(package_swift_path: Path) -> PlatformInfo:
    """Parse the `platforms:` directive from `Package.swift`.

    Returns macOS-only by default if no directive is present.
    Raises FileNotFoundError if the file doesn't exist.
    """
    if not package_swift_path.exists():
        raise FileNotFoundError(f"Package.swift not found: {package_swift_path}")

    content = package_swift_path.read_text()

    match = _PLATFORMS_BLOCK.search(content)
    if match is None:
        return PlatformInfo(
            platforms=("macos",),
            requires_ios_destination=False,
            requires_visionos_destination=False,
            requires_macos_destination=True,
        )

    block = match.group(1)
    platforms = tuple(name.lower() for name in _PLATFORM_PATTERN.findall(block))

    if not platforms:
        return PlatformInfo(
            platforms=("macos",),
            requires_ios_destination=False,
            requires_visionos_destination=False,
            requires_macos_destination=True,
        )

    return PlatformInfo(
        platforms=platforms,
        requires_ios_destination="ios" in platforms,
        requires_visionos_destination="visionos" in platforms,
        requires_macos_destination="macos" in platforms,
    )