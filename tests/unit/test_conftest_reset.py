"""Tests for ``tests.conftest_reset``.

The ``reset_all_singletons`` fixture is ``autouse=True`` and runs
before *every* test in the project. If one of its sub-resets raises
because a target module can't be imported (e.g. a missing optional
extra, a stubbed test environment, a partial venv), the fixture
itself propagates the error and the test crashes in setup with a
``ModuleNotFoundError`` or ``ImportError`` — even when the actual
test function has nothing to do with the broken module.

The contract this test locks: ``reset_all_singletons`` is best-effort
cleanup. When a target module is unimportable, the corresponding
singleton doesn't exist, so there's nothing to reset; the function
must return cleanly. Anything else defeats the purpose of running
the autouse fixture in the first place.

Background: 2026-10-14 — the
``tests/tools/test_validate_input_validator_patterns`` suite produced
13 ERRORs (one per collected test) because
``reset_service_watchdog`` transitively imported oneiric's
``mcp.server`` → ``fastmcp.server.server`` → ``mcp.server.lowlevel``,
which is missing the ``[server]`` extra in some environments. The
import crashed before any test body ran.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from unittest.mock import patch

import pytest

from tests.conftest_reset import reset_all_singletons


def test_reset_all_singletons_runs_clean_when_no_modules_break() -> None:
    """Baseline: in a healthy environment, every reset target imports.

    This is the "happy path" — it must always pass; if it ever fails
    in CI, a target module has been removed and the corresponding
    reset function is dead code that should be deleted.
    """
    reset_all_singletons()  # must not raise


def test_reset_all_singletons_survives_missing_hook_lock_manager() -> None:
    """``HookLockManager`` is unimportable → reset is skipped, no raise.

    Simulates an environment where the executors submodule was pruned
    (e.g. a minimal install). The autouse fixture must still complete
    so the test that triggered it can actually run.
    """
    with patch.dict(sys.modules, {"crackerjack.executors.hook_lock_manager": None}):
        reset_all_singletons()  # must not raise


def test_reset_all_singletons_survives_missing_service_watchdog() -> None:
    """``service_watchdog`` is unimportable → reset is skipped, no raise.

    This is the exact failure mode that produced the 2026-10-14
    ERRORs: importing ``crackerjack.core.service_watchdog`` cascades
    through ``crackerjack.models.__init__`` → ``crackerjack.config.settings``
    → ``oneiric.mcp.server`` → ``fastmcp.server.server``. The fix
    guards the import inside ``reset_service_watchdog`` so the cascade
    is short-circuited at the first unimportable module.
    """
    with patch.dict(sys.modules, {"crackerjack.core.service_watchdog": None}):
        reset_all_singletons()  # must not raise


def test_reset_all_singletons_survives_all_targets_missing() -> None:
    """Every target submodule is unimportable → fixture still completes.

    The contract is: if no singleton can be found, there is nothing
    to reset, and the fixture returns None. This is the extreme case;
    if this ever fails, the fix has regressed.
    """
    blocked = {
        "crackerjack.executors.hook_lock_manager": None,
        "crackerjack.core.timeout_manager": None,
        "crackerjack.core.service_watchdog": None,
        "crackerjack.services.metrics": None,
        "crackerjack.core.performance_monitor": None,
        "crackerjack.services.connection_pool": None,
    }
    with patch.dict(sys.modules, blocked):
        reset_all_singletons()  # must not raise


def test_reset_all_singletons_importable_via_test_path() -> None:
    """The conftest_reset module is importable from a test context.

    Guards against a regression where the conftest's relative imports
    (or a circular dep) make ``tests.conftest_reset`` only importable
    via pytest's conftest-loading magic, not a normal
    ``import tests.conftest_reset``. Both the autouse fixture in
    ``tests/conftest.py`` and any direct test (like this one) need the
    import to work the same way.
    """
    spec = importlib.util.find_spec("tests.conftest_reset")
    assert spec is not None, "tests.conftest_reset must be importable"
    # Re-import the module to make sure it round-trips.
    importlib.import_module("tests.conftest_reset")
