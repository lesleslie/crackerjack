"""Guard test: every Bodai ecosystem repo must use the hatchling build backend.

Per the BODAI_REPO_REGISTRY audit 2026-08-26, all 31 active Bodai repos
must declare ``[build-system] requires = ["hatchling"]`` and
``build-backend = "hatchling.build"``.

The repo list is sourced from ``BODAI_REPO_REGISTRY.md`` (authoritative
maintained list of Bodai-authored Python-pinned repos). The registry lives
in the mahavishnu repo, sibling to crackerjack.

Rationale:
    1. PEP 517 compliance: a missing or malformed ``build-backend`` field
       silently falls back to setuptools under uv, but breaks strict
       PEP 517 frontends (``build``, ``pip``, non-uv PEP 517 callers).
    2. Ecosystem consistency: 7 of 31 repos had drifted to setuptools or
       were missing ``[build-system]`` entirely; this guard prevents
       regression.
    3. Tooling simplicity: ``crackerjack run`` already enforces the
       Bodai quality gate; running this guard alongside means a drift
       back to setuptools fails CI before it lands.

This test is fast (reads 31 small TOML files), runs on every
``crackerjack run``, and self-skips when the registry file is not
present (e.g. when crackerjack is run from a fresh checkout without
mahavishnu as a sibling).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import pytest

from crackerjack.checks.bodai_registry import (
    parse_registry_repo_paths,
    resolve_projects_root,
    resolve_registry_path,
)


# Authoritative registry maintained by the Bodai ecosystem, living in the
# *mahavishnu* repo. `crackerjack.checks.bodai_registry` owns the resolution
# chain so this test stays portable across clone layouts (CI runners,
# worktrees, different home directories).
def _find_registry() -> Path | None:
    return resolve_registry_path()


def _extract_repos(registry: Path) -> list[Path]:
    """Parse the registry markdown and return the list of Bodai repo paths.

    The registry's Path column is relative to a projects root (the registry
    lives in a public repo, so it publishes no absolute paths), so each row
    is resolved against the root before being returned. Entries from
    "Deprecated" or "Excluded" sections are skipped.
    """
    text = registry.read_text(encoding="utf-8")
    return parse_registry_repo_paths(text, resolve_projects_root(registry))


@pytest.fixture(scope="module")
def bodai_repos() -> list[Path]:
    """Yield the list of Bodai repos to validate. Skip the test module if
    the registry is not available locally — see module docstring.
    """
    registry = _find_registry()
    if registry is None:
        pytest.skip(
            "BODAI_REPO_REGISTRY.md not found at any known sibling location; "
            "this guard test only runs in the full Bodai checkout."
        )
    return _extract_repos(registry)


class TestBodaiBuildSystemGuard:
    """Standardize the build backend across the Bodai ecosystem."""

    def test_registry_lists_at_least_one_repo(self, bodai_repos: list[Path]) -> None:
        # The registry currently tracks 31 active repos. Asserting >0 only
        # here keeps the guard from being trivially satisfied by an empty
        # parse; the count-specific expectation lives in
        # test_registry_matches_known_active_repos below.
        assert len(bodai_repos) > 0, (
            "BODAI_REPO_REGISTRY.md parsed to zero repos; "
            "table-row regex may have drifted from the registry format."
        )

    def test_each_repo_uses_hatchling(
        self,
        bodai_repos: list[Path],
    ) -> None:
        """Every Bodai repo's pyproject.toml must declare hatchling.

        Asserts three things per repo:
            1. ``[build-system]`` block exists (PEP 517 mandate).
            2. ``build-backend = "hatchling.build"`` is set explicitly.
            3. ``requires`` array contains ``"hatchling"`` (string form,
               accepting both single-line ``["hatchling"]`` and the
               multi-line ``[\\n  "hatchling",\\n]`` form hatch itself
               emits when configured via ``hatch new``).

        A repo that fails any check is reported individually so the
        failure message points the operator at the exact repo + field.
        """
        failures: list[str] = []
        for repo in bodai_repos:
            pyproject = repo / "pyproject.toml"
            if not pyproject.is_file():
                failures.append(f"{repo.name}: pyproject.toml missing")
                continue
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as exc:
                failures.append(f"{repo.name}: TOML parse error: {exc}")
                continue

            build_system_raw: object = data.get("build-system")
            if not isinstance(build_system_raw, dict):
                failures.append(
                    f"{repo.name}: [build-system] block missing or malformed "
                    f"(PEP 517 requires build-backend; missing field falls "
                    f"back to setuptools under uv)"
                )
                continue

            build_system = cast("dict[str, object]", build_system_raw)
            backend: object = build_system.get("build-backend")
            if backend != "hatchling.build":
                failures.append(
                    f"{repo.name}: build-backend is {backend!r}; "
                    f"expected 'hatchling.build'"
                )
                continue

            requires: object = build_system.get("requires", [])
            if not isinstance(requires, list) or "hatchling" not in requires:
                failures.append(
                    f"{repo.name}: build-system.requires must contain "
                    f"'hatchling'; got {requires!r}"
                )
                continue

        assert not failures, (
            "Bodai build-system guard failed for "
            f"{len(failures)} repo(s):\n  - " + "\n  - ".join(failures)
        )

    def test_registry_path_format_is_stable(self, bodai_repos: list[Path]) -> None:
        """Each path in the registry should point to an existing directory.

        Catches typos in BODAI_REPO_REGISTRY.md before they cause the
        build-system guard to silently skip a repo.
        """
        missing = [str(p) for p in bodai_repos if not p.is_dir()]
        assert not missing, (
            "BODAI_REPO_REGISTRY.md references paths that don't exist on "
            "disk; this guard would silently skip them:\n  - " + "\n  - ".join(missing)
        )

    def test_registry_matches_known_active_repos(self) -> None:
        """Pin the active-repo count so registry drift is caught quickly.

        When a new Bodai repo is added or one is archived, this count
        changes and the operator must explicitly update it. A silent
        change in the count is exactly the kind of drift this whole
        guard exists to prevent.
        """
        registry = _find_registry()
        if registry is None:
            pytest.skip("BODAI_REPO_REGISTRY.md not found")
        repos = _extract_repos(registry)
        # 2026-09-19 baseline: 34 active repos per current registry audit.
        # Updated from 36 → 34 after moving jinja2-custom-delimiters to
        # "Excluded from scope" (it is an IntelliJ Platform Gradle plugin,
        # not a Python project). The exclusions are now enforced by the
        # generator (settings/registry_metadata.yaml), so this count is
        # reproducible rather than dependent on a per-machine overlay.
        # Update this number when the registry's authoritative count changes
        # (new repo added, or repo moved to Deprecated section).
        assert len(repos) == 34, (
            f"BODAI_REPO_REGISTRY.md reports {len(repos)} active repos; "
            f"expected 34 (2026-09-19 baseline). If the count legitimately "
            f"changed, update the test; if it changed accidentally, fix the "
            f"registry."
        )
