"""Tests for ``crackerjack.checks.bodai_registry``.

Covers the resolution chain that locates the Bodai fleet registry. The
registry lives in the sibling ``mahavishnu`` repo, so it has to be found
without hardcoding one machine's home directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from crackerjack.checks import bodai_registry
from crackerjack.checks.bodai_registry import (
    REGISTRY_ENV_VAR,
    REGISTRY_FILENAME,
    load_fleet_repo_paths,
    parse_registry_repo_paths,
    registry_candidates,
    resolve_registry_path,
)


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    """Keep the fleet-path cache from leaking between tests."""
    load_fleet_repo_paths.cache_clear()
    yield
    load_fleet_repo_paths.cache_clear()


def test_env_var_overrides_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``$CRACKERJACK_BODAI_REGISTRY`` wins over every other candidate."""
    registry = tmp_path / REGISTRY_FILENAME
    registry.write_text("| demo | /tmp/demo | py | notes |\n")
    monkeypatch.setenv(REGISTRY_ENV_VAR, str(registry))

    assert resolve_registry_path() == registry


def test_env_var_is_first_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The override is consulted before any directory-derived candidate."""
    registry = tmp_path / REGISTRY_FILENAME
    registry.write_text("| demo | /tmp/demo | py | notes |\n")
    monkeypatch.setenv(REGISTRY_ENV_VAR, str(registry))

    assert registry_candidates()[0] == registry


def test_candidates_are_unique_and_ordered() -> None:
    """Candidates are de-duplicated but keep their priority order."""
    candidates = registry_candidates()
    assert len(candidates) == len(set(candidates))
    assert all(c.name == REGISTRY_FILENAME for c in candidates)


def test_missing_registry_resolves_to_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreachable registry is absent, not broken — it resolves to None."""
    monkeypatch.setenv(REGISTRY_ENV_VAR, str(tmp_path / "nope.md"))
    assert resolve_registry_path() is None


def test_fleet_paths_empty_when_registry_unresolvable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No registry means no fleet members, so the gate stays a no-op."""
    monkeypatch.setenv(REGISTRY_ENV_VAR, str(tmp_path / "nope.md"))
    load_fleet_repo_paths.cache_clear()
    assert load_fleet_repo_paths() == frozenset()


def test_parse_extracts_paths_and_skips_excluded_sections() -> None:
    """Deprecated and excluded sections do not contribute repo paths."""
    text = (
        "### Core\n"
        "| repo-a | /Users/example/Projects/repo-a | py | notes |\n"
        "| repo-b | /Users/example/Projects/repo-b | py | notes |\n"
        "\n"
        "## Deprecated\n"
        "| repo-old | /Users/example/Projects/repo-old | py | notes |\n"
        "\n"
        "## Excluded from scope (verified non-Python)\n"
        "| repo-x | /Users/example/Projects/repo-x | - | notes |\n"
    )

    paths = parse_registry_repo_paths(text)

    assert paths == [
        Path("/Users/example/Projects/repo-a"),
        Path("/Users/example/Projects/repo-b"),
    ]


def test_parse_ignores_rows_without_an_absolute_path() -> None:
    """Rows whose second column is not a path are not repos."""
    text = (
        "### Core\n"
        "| repo-a | /Users/example/Projects/repo-a | py | notes |\n"
        "| prose | not-a-path | py | notes |\n"
    )

    assert parse_registry_repo_paths(text) == [
        Path("/Users/example/Projects/repo-a"),
    ]


def test_registry_module_has_no_hardcoded_home_path() -> None:
    """No absolute home path may be baked into the resolver."""
    source = Path(bodai_registry.__file__).read_text()
    assert "/Users/" not in source
