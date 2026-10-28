"""Tests for ``crackerjack.checks.bodai_registry``.

Covers the resolution chain that locates the Bodai fleet registry, and the
projects-root chain that turns the registry's relative Path column back into
a location on disk. The registry lives in the sibling ``mahavishnu`` repo,
so it has to be found without hardcoding one machine's home directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from crackerjack.checks import bodai_registry
from crackerjack.checks.bodai_registry import (
    PROJECTS_ROOT_ENV_VAR,
    REGISTRY_ENV_VAR,
    REGISTRY_FILENAME,
    load_fleet_repo_paths,
    parse_registry_repo_paths,
    registry_candidates,
    resolve_projects_root,
    resolve_registry_path,
)


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    """Keep the fleet-path cache from leaking between tests."""
    load_fleet_repo_paths.cache_clear()
    yield
    load_fleet_repo_paths.cache_clear()


@pytest.fixture(autouse=True)
def _clear_projects_root_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may inherit a projects-root override from the environment."""
    monkeypatch.delenv(PROJECTS_ROOT_ENV_VAR, raising=False)


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
        "| repo-a | repo-a/ | py | notes |\n"
        "| repo-b | repo-b/ | py | notes |\n"
        "\n"
        "## Deprecated\n"
        "| repo-old | repo-old/ | py | notes |\n"
        "\n"
        "## Excluded from scope (not a fleet member)\n"
        "| repo-x | repo-x/ | - | notes |\n"
    )

    paths = parse_registry_repo_paths(text, Path("/projects"))

    assert paths == [Path("/projects/repo-a"), Path("/projects/repo-b")]


def test_parse_resolves_relative_paths_against_the_root() -> None:
    """A root-relative row becomes a location under the projects root."""
    text = "### Core\n| oneiric | oneiric/ | py | notes |\n"

    assert parse_registry_repo_paths(text, Path("/projects")) == [
        Path("/projects/oneiric")
    ]


def test_parse_still_accepts_legacy_absolute_paths() -> None:
    """A registry generated before the relative format still resolves.

    Such a registry holds absolute paths *under the projects root*, so the
    legacy form keeps working without a special case.
    """
    text = "### Core\n| repo-a | /projects/repo-a | py | notes |\n"

    assert parse_registry_repo_paths(text, Path("/projects")) == [
        Path("/projects/repo-a")
    ]


def test_parse_rejects_paths_that_escape_the_root() -> None:
    """A row must not steer the fleet tools outside the projects root.

    The registry is an input -- it can be pointed at any file -- so a
    ``..`` segment must not be able to reach an arbitrary directory.
    """
    text = "### Core\n| evil | ../../etc | py | notes |\n"

    assert parse_registry_repo_paths(text, Path("/projects")) == []


def test_parse_rejects_absolute_paths_outside_the_root() -> None:
    """An absolute path is honoured only when it lands inside the root."""
    text = "### Core\n| evil | /etc | py | notes |\n"

    assert parse_registry_repo_paths(text, Path("/projects")) == []


def test_parse_rejects_a_row_pointing_at_the_root_itself() -> None:
    """The projects root is not itself a fleet member."""
    text = "### Core\n| evil | . | py | notes |\n"

    assert parse_registry_repo_paths(text, Path("/projects")) == []


def test_parse_ignores_header_and_separator_rows() -> None:
    """The table's own header and separator rows are not repos."""
    text = (
        "### Core\n"
        "| Repo | Path | requires-python | Notes |\n"
        "|---|---|---|---|\n"
        "| repo-a | repo-a/ | py | notes |\n"
    )

    assert parse_registry_repo_paths(text, Path("/projects")) == [
        Path("/projects/repo-a")
    ]


def test_parse_ignores_rows_whose_second_column_is_prose() -> None:
    """Rows whose second column is not a path-like token are not repos."""
    text = (
        "### Core\n"
        "| repo-a | repo-a/ | py | notes |\n"
        "| prose | not a path at all | py | notes |\n"
    )

    assert parse_registry_repo_paths(text, Path("/projects")) == [
        Path("/projects/repo-a")
    ]


def test_projects_root_env_var_overrides_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``$BODAI_PROJECTS_ROOT`` wins over the registry's own location."""
    registry = tmp_path / "mahavishnu" / REGISTRY_FILENAME
    registry.parent.mkdir(parents=True)
    registry.write_text("| demo | demo/ | py | notes |\n")
    monkeypatch.setenv(PROJECTS_ROOT_ENV_VAR, "/opt/repos")

    assert resolve_projects_root(registry) == Path("/opt/repos")


def test_projects_root_is_derived_from_the_registry_location(tmp_path: Path) -> None:
    """The registry sits at ``<root>/mahavishnu/``, so its parent is the root."""
    registry = tmp_path / "mahavishnu" / REGISTRY_FILENAME
    registry.parent.mkdir(parents=True)
    registry.write_text("| demo | demo/ | py | notes |\n")

    assert resolve_projects_root(registry) == tmp_path


def test_projects_root_falls_back_to_the_home_layout() -> None:
    """With no override and no registry, the standard layout is assumed."""
    assert resolve_projects_root(None) == Path.home() / "Projects"


def test_registry_module_has_no_hardcoded_home_path() -> None:
    """No absolute home path may be baked into the resolver."""
    source = Path(bodai_registry.__file__).read_text()
    assert "/Users/" not in source
