"""Pure semver arithmetic, shared between ``VersionAnalyzer`` and ``PublishManager``.

This module contains the canonical semver-increment logic. Both the
version analyzer's recommendation path and the publisher's bump path
delegate here so the two callers cannot drift apart.

**Pure functions only.** No I/O, no console, no logging. Errors are
signaled via ``ValueError``; presentation of those errors is the
caller's responsibility (see ``PublishManager._calculate_next_version``
for the user-facing wrapper).

**Why a string parameter:** the math here has no dependency on
:class:`VersionBumpType`, so taking ``"major" | "minor" | "patch"`` as
a string breaks what would otherwise be a circular import between
this module and ``version_analyzer``. Both call sites have the value
as a string already (``VersionBumpType.value`` or user input).
"""

from __future__ import annotations

from typing import Literal

_BumpTypeStr = Literal["major", "minor", "patch"]


def calculate_next_version(current: str, bump_type: str) -> str:
    """Return ``current + 1`` of the requested component.

    Parameters
    ----------
    current
        A ``"X.Y.Z"`` semver string. Must contain exactly three dot-separated
        integer components.
    bump_type
        ``"major"`` zeros out ``minor`` and ``patch``; ``"minor"`` zeros
        out ``patch``; ``"patch"`` is in-place.

    Raises
    ------
    ValueError
        If ``current`` does not contain three dot-separated integer
        components, or if ``bump_type`` is not one of ``"major"`` /
        ``"minor"`` / ``"patch"``.
    """
    if bump_type not in ("major", "minor", "patch"):
        msg = f"Invalid bump type: {bump_type}"
        raise ValueError(msg)

    parts = current.split(".")
    if len(parts) != 3:
        msg = f"Invalid version format: {current}"
        raise ValueError(msg)

    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError as e:
        msg = f"Invalid version format: {current}"
        raise ValueError(msg) from e

    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"
