"""Test the crackerjack.interactive deprecation shim.

Plan Task 3.2.4 keeps `crackerjack.interactive` working as a
deprecation shim that points users at `crackerjack.cli.interactive`.
The shim warns on every import (not just first call), so each test
must purge the module from `sys.modules` before re-importing.
"""
from __future__ import annotations

import importlib
import sys
import warnings


def _fresh_import(mod_name: str):
    """Drop a module from sys.modules and re-import it to retrigger module-level code."""
    sys.modules.pop(mod_name, None)
    return importlib.import_module(mod_name)


def test_legacy_interactive_emits_deprecation_warning() -> None:
    """Importing `crackerjack.interactive` must emit DeprecationWarning mentioning the new path."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _fresh_import("crackerjack.interactive")
        assert any(
            issubclass(item.category, DeprecationWarning)
            and "cli.interactive" in str(item.message)
            for item in w
        ), f"no DeprecationWarning mentioning cli.interactive; got: {[str(x.message) for x in w]}"


def test_legacy_interactive_reexports_known_names() -> None:
    """Names from the old module must still be importable through the legacy path."""
    mod = _fresh_import("crackerjack.interactive")
    # Smoke test: pick a few well-known exports from the pre-consolidation
    # interactive module. If any move to cli.interactive, the test catches
    # the regression at PR time rather than at user runtime.
    for name in ("Confirm", "InteractiveCLI", "InteractiveWorkflowOptions"):
        assert hasattr(mod, name), f"legacy shim lost export '{name}'"