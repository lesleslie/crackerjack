"""Tests for ``crackerjack.services.import_resolution``.

Covers the ``ImportSpec`` namedtuple, the ``SAFE_IMPORT_SPECS`` table,
and ``get_safe_import_spec`` lookup helper.
"""

from __future__ import annotations

from crackerjack.services.import_resolution import (
    ImportSpec,
    SAFE_IMPORT_SPECS,
    get_safe_import_spec,
)


def test_import_spec_is_namedtuple() -> None:
    spec = ImportSpec("typing", "Any", "from typing import Any")
    assert spec.module_name == "typing"
    assert spec.symbol_name == "Any"
    assert spec.import_line == "from typing import Any"


def test_import_spec_accepts_none_symbol_for_module_imports() -> None:
    """``symbol_name=None`` represents ``import module`` style imports."""
    spec = ImportSpec("operator", None, "import operator")
    assert spec.symbol_name is None


def test_safe_import_specs_contains_expected_keys() -> None:
    """Spot-check a few well-known safe-import keys exist in the table."""
    for key in ("Any", "Callable", "Path", "Optional", "suppress", "operator"):
        assert key in SAFE_IMPORT_SPECS, f"missing SAFE_IMPORT_SPECS key: {key}"


def test_get_safe_import_spec_returns_spec_for_known_name() -> None:
    spec = get_safe_import_spec("Any")
    assert spec is not None
    assert spec.module_name == "typing"
    assert spec.symbol_name == "Any"


def test_get_safe_import_spec_returns_none_for_unknown_name() -> None:
    assert get_safe_import_spec("ThisIsNotInTheTable") is None


def test_get_safe_import_spec_returns_module_only_import_for_operator() -> None:
    spec = get_safe_import_spec("operator")
    assert spec is not None
    assert spec.symbol_name is None  # bare ``import operator``
    assert spec.import_line == "import operator"


def test_safe_import_specs_all_have_module_name_and_import_line() -> None:
    """Every entry has a module name and import line; symbol may be None."""
    for key, spec in SAFE_IMPORT_SPECS.items():
        assert spec.module_name, f"{key} has empty module_name"
        assert spec.import_line, f"{key} has empty import_line"
