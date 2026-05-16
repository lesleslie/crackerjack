"""Tests for ULID generator service."""

import re
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.ulid_generator import generate_ulid, is_valid_ulid


class TestGenerateUlid:
    """Tests for generate_ulid function."""

    def test_generate_ulid_returns_string(self):
        """Verify generate_ulid returns a string."""
        result = generate_ulid()
        assert isinstance(result, str)

    def test_generate_ulid_is_not_empty(self):
        """Verify generated ULID is not empty."""
        result = generate_ulid()
        assert len(result) > 0

    def test_generate_ulid_format(self):
        """Verify generated ULID contains only valid characters."""
        valid_chars = set("0123456789abcdefghjkmnpqrstvwxyz")
        result = generate_ulid()
        assert all(c in valid_chars for c in result)


class TestIsValidUlid:
    """Tests for is_valid_ulid function."""

    def test_valid_ulid_all_zeros(self):
        """Verify ULID with all zeros is valid."""
        assert is_valid_ulid("00000000000000000000000000") is True

    def test_valid_ulid_all_valid_chars(self):
        """Verify ULID with all valid characters is valid."""
        ulid = "0123456789abcdefghjkmnpqrs"  # 26 chars from valid set
        assert is_valid_ulid(ulid) is True

    def test_invalid_ulid_wrong_length_short(self):
        """Verify ULID with wrong length (too short) is invalid."""
        assert is_valid_ulid("0123456789abcdefghjkmnpq") is False  # 25 chars

    def test_invalid_ulid_wrong_length_long(self):
        """Verify ULID with wrong length (too long) is invalid."""
        assert is_valid_ulid("0123456789abcdefghjkmnpqrstvwxyz0") is False

    def test_invalid_ulid_wrong_length_empty(self):
        """Verify empty string is invalid ULID."""
        assert is_valid_ulid("") is False

    def test_invalid_ulid_contains_invalid_char_i(self):
        """Verify ULID with invalid character 'i' is invalid."""
        invalid_ulid = "0123456789abcdefghijkmnpqrstvwxy"
        assert is_valid_ulid(invalid_ulid) is False

    def test_invalid_ulid_contains_invalid_char_l(self):
        """Verify ULID with invalid character 'l' is invalid."""
        invalid_ulid = "0123456789abcdefghjkmnpqrstvwxyzl"
        assert is_valid_ulid(invalid_ulid) is False

    def test_invalid_ulid_contains_invalid_char_o(self):
        """Verify ULID with invalid character 'o' is invalid."""
        invalid_ulid = "0123456789abcdefghjkmnopqrstvwxyz"
        assert is_valid_ulid(invalid_ulid) is False

    def test_invalid_ulid_contains_invalid_char_u(self):
        """Verify ULID with invalid character 'u' is invalid."""
        invalid_ulid = "0123456789abcdefghjkmnpqrstvwxyzu"
        assert is_valid_ulid(invalid_ulid) is False

    def test_invalid_ulid_uppercase(self):
        """Verify ULID with uppercase characters is invalid."""
        assert is_valid_ulid("0123456789ABCDEFGHJKMNPQRS") is False

    def test_invalid_ulid_with_space(self):
        """Verify ULID with space is invalid."""
        invalid_ulid = "0123456789abcdefghjkmnpq rs"
        assert is_valid_ulid(invalid_ulid) is False
