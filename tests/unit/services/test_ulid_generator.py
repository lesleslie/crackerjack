"""Tests for ULID generation helpers."""

from __future__ import annotations

import types
from unittest.mock import patch

from crackerjack.services.ulid_generator import generate_ulid, is_valid_ulid


def test_generate_ulid_fallback_when_druva_missing() -> None:
    with patch.dict("sys.modules", {"druva": None}):
        ulid = generate_ulid()

    assert len(ulid) == 16
    assert is_valid_ulid(ulid) is False


def test_generate_ulid_uses_druva_when_available() -> None:
    fake_druva = types.SimpleNamespace(generate=lambda: "0123456789abcdefghjkmnpqrs")

    with patch.dict("sys.modules", {"druva": fake_druva}):
        ulid = generate_ulid()

    assert ulid == "0123456789abcdefghjkmnpqrs"


def test_is_valid_ulid_rejects_invalid_values() -> None:
    assert is_valid_ulid("0123456789abcdefghjkmnpqrs") is True
    assert is_valid_ulid("short") is False
    assert is_valid_ulid("0123456789abcdefghjkmnpqrst") is False
    assert is_valid_ulid("0123456789abcdefghjkmnpqrs!") is False
