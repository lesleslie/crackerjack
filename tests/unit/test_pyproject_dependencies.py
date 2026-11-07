"""Guard the test-selection dependency contract declared in pyproject.toml.

The ``pytest-snob`` integration was removed from crackerjack because
``snob-lib`` ships no cp314/cp315 wheel. ``pytest-testmon`` replaces it:
pure-python (``py3-none-any``), ``requires-python >= 3.10``, so it installs
on Python 3.14 and 3.15 without a compiler.

These tests pin that swap so the dependency cannot silently regress to a
compiled plugin, and so the dead ``snob`` dependency group does not come
back with a comment that still advertises ``uv sync --group snob``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"

# The oldest pytest-testmon that is pure-python and 3.14/3.15-capable.
# Newer releases are fine too - the floor exists so a future bump does not
# silently reintroduce a version with a compiled dependency.
MIN_TESTMON_VERSION = (2, 2, 0)


def _pyproject() -> dict[str, Any]:
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _version_tuple(raw: str) -> tuple[int, ...]:
    return tuple(int(part) for part in raw.split(".") if part.isdigit())


def test_pytest_testmon_is_a_main_dependency() -> None:
    dependencies = _pyproject()["project"]["dependencies"]

    testmon = [
        dependency for dependency in dependencies if dependency.startswith("pytest-testmon")
    ]

    assert testmon, (
        "pytest-testmon must be a main dependency: it is pure-python and "
        "installs on Python 3.14/3.15, so it needs no optional group"
    )


def test_pytest_testmon_floor_is_pure_python_capable() -> None:
    dependencies = _pyproject()["project"]["dependencies"]

    floors = [
        _version_tuple(dependency.split(">=", 1)[1])
        for dependency in dependencies
        if dependency.startswith("pytest-testmon>=")
    ]

    assert floors, "pytest-testmon must declare a version floor"
    assert floors[0] >= MIN_TESTMON_VERSION, (
        f"pytest-testmon floor {floors[0]} predates the pure-python release "
        "line; versions before 2.2.0 are not safe on Python 3.14/3.15"
    )


def test_no_snob_dependency_group() -> None:
    dependency_groups = _pyproject().get("dependency-groups", {})

    assert "snob" not in dependency_groups, (
        "the snob dependency group is dead - pytest-snob was removed because "
        "snob-lib has no cp314/cp315 wheel"
    )


def test_pytest_snob_is_not_a_dependency() -> None:
    dependencies = _pyproject()["project"]["dependencies"]

    assert not any(
        dependency.startswith("pytest-snob") for dependency in dependencies
    ), "pytest-snob pulls in snob-lib, a maturin-built Rust extension"
