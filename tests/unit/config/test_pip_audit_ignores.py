"""Tests for ``crackerjack.config.pip_audit_ignores``.

Covers:

- The hard-coded ``IGNORED_VULNERABILITY_IDS`` default set
- ``load_merged_ignores`` with and without ``project_dir``
- Loading from a project's ``pyproject.toml`` (``[tool.pip-audit].ignore-vuln``)
- Edge cases: missing files, malformed TOML, non-list values, mixed types,
  empty strings, duplicate IDs across defaults + project, stringly-typed
  paths, and the result being a sorted list.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from crackerjack.config.pip_audit_ignores import (
    IGNORED_VULNERABILITY_IDS,
    load_merged_ignores,
)

if TYPE_CHECKING:
    pass


class TestIgnoredVulnerabilityIdsDefaults:
    """The exported default tuple is stable and well-formed."""

    def test_is_tuple(self) -> None:
        assert isinstance(IGNORED_VULNERABILITY_IDS, tuple)

    def test_is_non_empty(self) -> None:
        assert len(IGNORED_VULNERABILITY_IDS) > 0

    def test_all_entries_are_non_empty_strings(self) -> None:
        for vid in IGNORED_VULNERABILITY_IDS:
            assert isinstance(vid, str)
            assert vid, "empty string in IGNORED_VULNERABILITY_IDS"

    def test_contains_cve_format_entries(self) -> None:
        assert any(vid.startswith("CVE-") for vid in IGNORED_VULNERABILITY_IDS)

    def test_contains_pysec_format_entries(self) -> None:
        assert any(vid.startswith("PYSEC-") for vid in IGNORED_VULNERABILITY_IDS)

    def test_contains_ghsa_format_entries(self) -> None:
        assert any(vid.startswith("GHSA-") for vid in IGNORED_VULNERABILITY_IDS)

    def test_has_no_duplicates(self) -> None:
        assert len(set(IGNORED_VULNERABILITY_IDS)) == len(IGNORED_VULNERABILITY_IDS)


class TestLoadMergedIgnoresNoProjectDir:
    """When no project_dir is passed, only the built-in defaults are returned."""

    def test_returns_list_type(self) -> None:
        assert isinstance(load_merged_ignores(None), list)

    def test_returns_all_defaults_when_project_dir_is_none(self) -> None:
        result = load_merged_ignores(None)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_default_call_has_no_arguments(self) -> None:
        # Default argument is None; calling with no arg should yield defaults.
        result = load_merged_ignores()
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_result_is_sorted(self) -> None:
        result = load_merged_ignores(None)
        assert result == sorted(result)

    def test_result_is_a_list_not_set(self) -> None:
        result = load_merged_ignores(None)
        # The function's return type hint is list[str].
        assert type(result) is list

    def test_each_item_is_a_string(self) -> None:
        result = load_merged_ignores(None)
        for vid in result:
            assert isinstance(vid, str)
            assert vid


class TestLoadMergedIgnoresMissingPyproject:
    """project_dir given, but no pyproject.toml — defaults only."""

    def test_directory_without_pyproject_returns_defaults(
        self, tmp_path: Path
    ) -> None:
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_directory_without_pyproject_is_sorted(
        self, tmp_path: Path
    ) -> None:
        result = load_merged_ignores(tmp_path)
        assert result == sorted(result)


class TestLoadMergedIgnoresPyprojectVariants:
    """Behavior across various pyproject.toml shapes."""

    def test_empty_pyproject_returns_defaults(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("")
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_pyproject_without_tool_section_returns_defaults(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\n'
        )
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_pyproject_with_tool_but_no_pip_audit_returns_defaults(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.ruff]\nline-length = 100\n'
        )
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_pyproject_with_pip_audit_section_but_no_ignore_vuln_returns_defaults(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\nenabled = true\n'
        )
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_empty_ignore_vuln_list_returns_defaults(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\nignore-vuln = []\n'
        )
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)
        assert result == sorted(result)


class TestLoadMergedIgnoresWithProjectIgnores:
    """User-supplied ignore-vuln entries get merged in."""

    def test_project_ignore_is_added(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["GHSA-test-1234-5678"]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert "GHSA-test-1234-5678" in result
        assert "CVE-2025-53000" in result  # default preserved

    def test_multiple_project_ignores_added(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = [\n'
            '  "GHSA-aaaa-bbbb-cccc",\n'
            '  "CVE-2099-99999",\n'
            '  "PYSEC-2099-999",\n'
            ']\n'
        )
        result = load_merged_ignores(tmp_path)
        for vid in (
            "GHSA-aaaa-bbbb-cccc",
            "CVE-2099-99999",
            "PYSEC-2099-999",
        ):
            assert vid in result, f"missing {vid}"

    def test_result_is_sorted(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["GHSA-zzzz-9999-8888", "GHSA-aaaa-1111-2222"]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert result == sorted(result)

    def test_returns_list_type(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["GHSA-test-1234-5678"]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert type(result) is list

    def test_count_grows_with_new_ignores(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["NEW-ID-1", "NEW-ID-2"]\n'
        )
        result = load_merged_ignores(tmp_path)
        # Two new ids added to a known-default set.
        assert len(result) == len(set(IGNORED_VULNERABILITY_IDS)) + 2


class TestLoadMergedIgnoresDeduplication:
    """Same id appearing in defaults and project is a single entry."""

    def test_duplicate_of_default_is_not_added_twice(
        self, tmp_path: Path
    ) -> None:
        first_default = IGNORED_VULNERABILITY_IDS[0]
        (tmp_path / "pyproject.toml").write_text(
            f'[tool.pip-audit]\nignore-vuln = ["{first_default}"]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert result.count(first_default) == 1

    def test_duplicate_of_default_in_long_list(self, tmp_path: Path) -> None:
        first_default = IGNORED_VULNERABILITY_IDS[0]
        second_default = IGNORED_VULNERABILITY_IDS[1]
        (tmp_path / "pyproject.toml").write_text(
            f'[tool.pip-audit]\n'
            f'ignore-vuln = ["{first_default}", "{second_default}", '
            f'"GHSA-newp-1111-2222"]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert result.count(first_default) == 1
        assert result.count(second_default) == 1
        assert "GHSA-newp-1111-2222" in result
        assert len(result) == len(set(IGNORED_VULNERABILITY_IDS)) + 1


class TestLoadMergedIgnoresIgnoresNonStringEntries:
    """Non-string entries inside the list are skipped; only valid strings added."""

    def test_empty_string_in_list_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["GHSA-real-aaaa-bbbb", ""]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert "GHSA-real-aaaa-bbbb" in result
        assert "" not in result

    def test_integer_entry_in_list_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["GHSA-real-cccc-dddd", 42]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert "GHSA-real-cccc-dddd" in result
        assert 42 not in result

    def test_only_strings_added_to_result(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["GHSA-mixed-eeee-ffff", "", 7]\n'
        )
        result = load_merged_ignores(tmp_path)
        for vid in result:
            assert isinstance(vid, str), f"non-string in result: {vid!r}"


class TestLoadMergedIgnoresIgnoreVulnWrongType:
    """``ignore-vuln`` must be a list; other shapes are silently ignored."""

    def test_ignore_vuln_as_string_is_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = "GHSA-string-not-list"\n'
        )
        result = load_merged_ignores(tmp_path)
        assert "GHSA-string-not-list" not in result
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_ignore_vuln_as_integer_is_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\nignore-vuln = 7\n'
        )
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)


class TestLoadMergedIgnoresMalformedPyproject:
    """Bad TOML falls back to the defaults, no crash."""

    def test_invalid_toml_falls_back_to_defaults(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "this is = not valid toml = at all [[["
        )
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)
        assert result == sorted(result)

    def test_invalid_toml_does_not_raise(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[unclosed")
        # Just calling it must not raise.
        result = load_merged_ignores(tmp_path)
        assert isinstance(result, list)


class TestLoadMergedIgnoresPathCoercion:
    """The ``project_dir`` arg accepts both ``Path`` and ``str``."""

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\nignore-vuln = ["GHSA-stringpath-1"]\n'
        )
        result = load_merged_ignores(str(tmp_path))
        assert "GHSA-stringpath-1" in result
        assert result == sorted(result)

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\nignore-vuln = ["GHSA-pathobj-1"]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert "GHSA-pathobj-1" in result


class TestLoadMergedIgnoresResultShape:
    """Sanity check the output shape: list[str], sorted, deduped."""

    def test_returns_list_not_set_or_tuple(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\nignore-vuln = ["GHSA-shape-1"]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert type(result) is list

    def test_returns_sorted_alphabetically(self, tmp_path: Path) -> None:
        # Project adds vids that should land at sorted positions.
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["GHSA-zzzz-9999-0000", "GHSA-aaaa-1111-2222"]\n'
        )
        result = load_merged_ignores(tmp_path)
        for prev, curr in zip(result, result[1:]):
            assert prev <= curr, f"{prev!r} > {curr!r}"

    def test_no_duplicates_in_merged_result(self, tmp_path: Path) -> None:
        # Even with full overlap the result must be a set under the hood.
        all_defaults = list(IGNORED_VULNERABILITY_IDS)
        quoted = ", ".join(f'"{v}"' for v in all_defaults)
        (tmp_path / "pyproject.toml").write_text(
            f'[tool.pip-audit]\nignore-vuln = [{quoted}]\n'
        )
        result = load_merged_ignores(tmp_path)
        assert len(result) == len(set(result))
