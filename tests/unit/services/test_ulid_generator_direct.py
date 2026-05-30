from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch


def _load_ulid_module() -> types.ModuleType:
    module_path = (
        Path(__file__).resolve().parents[3]
        / "crackerjack"
        / "services"
        / "ulid_generator.py"
    )
    spec = importlib.util.spec_from_file_location(
        "tests.unit.services.ulid_generator_direct",
        module_path,
    )
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tests.unit.services.ulid_generator_direct"] = module
    spec.loader.exec_module(module)
    return module


def test_generate_ulid_falls_back_when_druva_is_missing() -> None:
    module = _load_ulid_module()

    with (
        patch.dict("sys.modules", {"druva": None}),
        patch.object(module.time, "time", return_value=1_234_567.89),
        patch.object(module.os, "urandom", return_value=b"1234567890"),
    ):
        ulid = module.generate_ulid()

    assert len(ulid) == 16
    assert module.is_valid_ulid(ulid) is False


def test_generate_ulid_uses_druva_when_available() -> None:
    module = _load_ulid_module()
    fake_druva = types.SimpleNamespace(generate=lambda: "0123456789abcdefghjkmnpqrs")

    with patch.dict("sys.modules", {"druva": fake_druva}):
        assert module.generate_ulid() == "0123456789abcdefghjkmnpqrs"


def test_is_valid_ulid_covers_valid_and_invalid_inputs() -> None:
    module = _load_ulid_module()

    assert module.is_valid_ulid("0123456789abcdefghjkmnpqrs") is True
    assert module.is_valid_ulid("short") is False
    assert module.is_valid_ulid("0123456789abcdefghjkmnpqrst") is False
    assert module.is_valid_ulid("0123456789abcdefghjkmnpqrs!") is False
