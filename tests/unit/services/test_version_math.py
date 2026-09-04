"""Tests for the canonical semver arithmetic in ``version_math``.

These tests pin the arithmetic independently of any wrapping object so
that ``VersionAnalyzer._calculate_next_version`` and
``PublishManager._calculate_next_version`` cannot drift apart.
"""

from __future__ import annotations

import pytest

from crackerjack.services.version_math import calculate_next_version


@pytest.mark.unit
class TestMajor:
    def test_zero_zero_zero_to_one_zero_zero(self) -> None:
        assert calculate_next_version("0.0.0", "major") == "1.0.0"

    def test_zero_seventy_eight_to_one_zero_zero(self) -> None:
        assert calculate_next_version("0.78.0", "major") == "1.0.0"

    def test_one_two_three_to_two_zero_zero(self) -> None:
        assert calculate_next_version("1.2.3", "major") == "2.0.0"

    def test_major_zeros_out_minor_and_patch(self) -> None:
        """MAJOR bump must reset minor and patch to 0, never carry them over."""
        assert calculate_next_version("3.7.11", "major") == "4.0.0"


@pytest.mark.unit
class TestMinor:
    def test_increments_minor_zeroes_patch(self) -> None:
        assert calculate_next_version("0.78.0", "minor") == "0.79.0"

    def test_increments_minor_carries_major(self) -> None:
        assert calculate_next_version("1.2.3", "minor") == "1.3.0"

    def test_minor_zeroes_patch(self) -> None:
        assert calculate_next_version("2.4.9", "minor") == "2.5.0"


@pytest.mark.unit
class TestPatch:
    def test_increments_patch_in_place(self) -> None:
        assert calculate_next_version("1.2.3", "patch") == "1.2.4"

    def test_patch_with_zero_minor(self) -> None:
        assert calculate_next_version("1.0.0", "patch") == "1.0.1"

    def test_patch_does_not_affect_major_or_minor(self) -> None:
        assert calculate_next_version("9.9.9", "patch") == "9.9.10"


@pytest.mark.unit
class TestInvalidInputs:
    def test_two_part_version_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid version format"):
            calculate_next_version("1.2", "major")

    def test_four_part_version_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid version format"):
            calculate_next_version("1.2.3.4", "major")

    def test_non_integer_components_raise(self) -> None:
        with pytest.raises(ValueError, match="Invalid version format"):
            calculate_next_version("1.x.3", "major")

    def test_unknown_bump_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid bump type"):
            calculate_next_version("1.2.3", "drift")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid version format"):
            calculate_next_version("", "major")
