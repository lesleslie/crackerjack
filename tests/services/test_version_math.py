"""Tests for ``crackerjack.services.version_math``.

Covers the pure ``calculate_next_version`` semver-increment function used by
``VersionAnalyzer`` and ``PublishManager``. The function is referenced from
``PublishManager._calculate_next_version`` (user-facing wrapper) so it must
stay in sync — these tests pin the semantics.
"""

from __future__ import annotations

import pytest

from crackerjack.services.version_math import calculate_next_version


@pytest.mark.parametrize(
    ("current", "bump_type", "expected"),
    [
        ("1.2.3", "patch", "1.2.4"),
        ("0.0.0", "patch", "0.0.1"),
        ("10.20.30", "patch", "10.20.31"),
        ("0.0.5", "minor", "0.1.0"),
        ("1.2.3", "minor", "1.3.0"),
        ("9.9.9", "major", "10.0.0"),
        ("1.2.3", "major", "2.0.0"),
    ],
)
def test_calculate_next_version_happy_paths(
    current: str, bump_type: str, expected: str
) -> None:
    """Pin the canonical happy-path increments for all three bump types."""
    assert calculate_next_version(current, bump_type) == expected


def test_calculate_next_version_patch_increments_last_component() -> None:
    assert calculate_next_version("1.2.3", "patch") == "1.2.4"


def test_calculate_next_version_minor_zeroes_patch() -> None:
    assert calculate_next_version("1.2.3", "minor") == "1.3.0"


def test_calculate_next_version_major_zeroes_minor_and_patch() -> None:
    assert calculate_next_version("1.2.3", "major") == "2.0.0"


def test_calculate_next_version_zero_zero_one_patch() -> None:
    assert calculate_next_version("0.0.0", "patch") == "0.0.1"


def test_calculate_next_version_zero_zero_five_minor() -> None:
    assert calculate_next_version("0.0.5", "minor") == "0.1.0"


def test_calculate_next_version_double_digit_major_increment() -> None:
    """Major increment can carry into higher-order digit."""
    assert calculate_next_version("9.9.9", "major") == "10.0.0"


def test_calculate_next_version_invalid_bump_type_raises() -> None:
    with pytest.raises(ValueError, match="Invalid bump type"):
        calculate_next_version("1.2.3", "feature")


def test_calculate_next_version_invalid_bump_type_empty_raises() -> None:
    with pytest.raises(ValueError, match="Invalid bump type"):
        calculate_next_version("1.2.3", "")


def test_calculate_next_version_too_few_components_raises() -> None:
    with pytest.raises(ValueError, match="Invalid version format"):
        calculate_next_version("1.2", "patch")


def test_calculate_next_version_too_many_components_raises() -> None:
    with pytest.raises(ValueError, match="Invalid version format"):
        calculate_next_version("1.2.3.4", "patch")


def test_calculate_next_version_non_numeric_component_raises() -> None:
    with pytest.raises(ValueError, match="Invalid version format"):
        calculate_next_version("1.2.x", "patch")


def test_calculate_next_version_empty_string_raises() -> None:
    with pytest.raises(ValueError, match="Invalid version format"):
        calculate_next_version("", "patch")


def test_calculate_next_version_v_prefix_strips_in_components() -> None:
    """``v1.2.3`` parses as ``v.2.3`` with the ``v`` rejected — must raise."""
    with pytest.raises(ValueError, match="Invalid version format"):
        calculate_next_version("v1.2.3", "patch")
