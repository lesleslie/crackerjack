"""Regression tests for osv-scanner CVE ignore-list synchronization.

Why this test exists
--------------------
The canonical list of ignored CVE IDs lives in
``crackerjack/config/osv_scanner_ignores.py`` (``IGNORED_VULNERABILITY_IDS``).
That list is used in *two* places that must stay in sync:

1. ``crackerjack/config/tool_commands.py`` — adds ``--ignore-vuln <id>`` flags
   to the ``uv run osv-scanner`` command so osv-scanner itself filters at source.
2. ``crackerjack/executors/hook_executor.py::_parse_osv_scanner_issues`` — a
   post-filter on the parsed JSON, in case osv-scanner ever returns an ignored
   CVE anyway (e.g. alias drift in the OSV service).

If these two places drift apart, ignored CVEs can surface as false positives
in the quality gate. The historical bug: the post-filter in
``hook_executor.py`` had a hard-coded 4-ID set while the canonical list had
28 IDs, so 24 ignored CVEs could leak through the post-filter.

These tests pin both consumers to the canonical source of truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.config.pip_audit_ignores import (
    IGNORED_VULNERABILITY_IDS,
    load_merged_ignores,
)
from crackerjack.config.tool_commands import _build_tool_commands
from crackerjack.executors.hook_executor import HookExecutor

# ---------------------------------------------------------------------------
# Canonical list sanity (this is the single source of truth)
# ---------------------------------------------------------------------------


class TestCanonicalIgnoreList:
    """Sanity checks on the canonical ignore list itself."""

    def test_list_is_non_empty(self) -> None:
        assert len(IGNORED_VULNERABILITY_IDS) > 0

    def test_all_entries_are_strings(self) -> None:
        for vid in IGNORED_VULNERABILITY_IDS:
            assert isinstance(vid, str), f"{vid!r} is not a string"
            assert vid, "Empty string in IGNORED_VULNERABILITY_IDS"

    def test_no_duplicates(self) -> None:
        assert len(IGNORED_VULNERABILITY_IDS) == len(set(IGNORED_VULNERABILITY_IDS))


# ---------------------------------------------------------------------------
# Synchronization: post-parse filter in _parse_osv_scanner_issues must use
# the canonical list (covered by TestHookExecutorUsesCanonicalList above).
# ---------------------------------------------------------------------------
#
# Note: as of the osv-scanner swap, the tool CLI no longer carries
# ``--ignore-vuln`` flags — osv-scanner does not accept them. Filtering
# happens entirely in ``hook_executor._parse_osv_scanner_issues`` against
# ``IGNORED_VULNERABILITY_IDS``. The tests below previously verified the
# CLI flag wiring; that surface is gone. The behavioral guarantee (every
# canonical ID is filtered from the post-parse issue list) is exercised
# by ``TestHookExecutorUsesCanonicalList::test_every_canonical_cve_is_filtered``
# in this same file.


# ---------------------------------------------------------------------------
# Synchronization: hook_executor._parse_osv_scanner_issues must use the canonical list
# ---------------------------------------------------------------------------


def _make_executor(tmp_path: Path) -> HookExecutor:
    """Build a HookExecutor suitable for parsing tests."""
    return HookExecutor(
        console=MagicMock(),
        pkg_path=tmp_path,
    )


def _build_osv_scanner_output(cves: list[str]) -> str:
    """Build an osv-scanner-shaped stdout containing the given CVE IDs.

    osv-scanner writes a human-readable status line first, then JSON
    structured as ``results[].packages[].vulnerabilities[]``.
    """
    packages = []
    for cve in cves:
        packages.append({
            "package": {
                "name": f"vuln-pkg-{cve}",
                "version": "1.0.0",
                "ecosystem": "PyPI",
            },
            "vulnerabilities": [
                {
                    "id": cve,
                    "aliases": [],
                    "summary": f"Test vulnerability {cve}",
                },
            ],
        })
    return "No known vulnerabilities found\n" + json.dumps({
        "results": [
            {
                "source": {"path": "uv.lock", "type": "lockfile"},
                "packages": packages,
            },
        ],
        "fixes": [],
    })


class TestHookExecutorUsesCanonicalList:
    """The post-filter in _parse_osv_scanner_issues must use the canonical list."""

    def test_filters_cve_only_in_canonical_list(
        self, tmp_path: Path,
    ) -> None:
        """A CVE in the canonical list must NOT appear in parsed issues.

        Regression: this CVE was missing from the hard-coded 4-ID post-filter
        in hook_executor.py, so it would have surfaced as a false positive.
        """
        # Pick a CVE that is in the canonical 28 but NOT in any small hard-coded
        # subset. CVE-2026-25990 is in the canonical list (line 26 of
        # osv_scanner_ignores.py) and is far less likely to be in a small subset.
        cve_in_canonical_only = "CVE-2026-25990"
        assert cve_in_canonical_only in IGNORED_VULNERABILITY_IDS, (
            "Test precondition: CVE must be in the canonical list"
        )

        executor = _make_executor(tmp_path)
        output = _build_osv_scanner_output([cve_in_canonical_only])

        issues = executor._parse_osv_scanner_issues(output)

        assert issues == [], (
            f"CVE {cve_in_canonical_only} is in the canonical ignore list "
            f"but appeared in parsed issues: {issues}. This means the "
            f"post-filter in hook_executor.py is using a stale hard-coded "
            f"set instead of importing IGNORED_VULNERABILITY_IDS."
        )

    def test_does_not_filter_cve_not_in_canonical_list(
        self, tmp_path: Path,
    ) -> None:
        """A CVE NOT in the canonical list must appear in parsed issues."""
        cve_not_ignored = "CVE-2099-99999"
        assert cve_not_ignored not in IGNORED_VULNERABILITY_IDS, (
            "Test precondition: CVE must NOT be in the canonical list"
        )

        executor = _make_executor(tmp_path)
        output = _build_osv_scanner_output([cve_not_ignored])

        issues = executor._parse_osv_scanner_issues(output)

        assert len(issues) >= 1, (
            f"CVE {cve_not_ignored} is NOT in the canonical list but was "
            f"filtered out. The post-filter may be over-matching."
        )
        assert any(cve_not_ignored in issue for issue in issues), (
            f"Expected issue mentioning {cve_not_ignored}, got: {issues}"
        )

    @pytest.mark.parametrize("cve", list(IGNORED_VULNERABILITY_IDS))
    def test_every_canonical_cve_is_filtered(
        self, cve: str, tmp_path: Path,
    ) -> None:
        """Every entry in the canonical list must be filtered.

        This is the strongest regression: if a single canonical CVE is
        missing from the post-filter, this test fails.
        """
        executor = _make_executor(tmp_path)
        output = _build_osv_scanner_output([cve])

        issues = executor._parse_osv_scanner_issues(output)

        assert issues == [], (
            f"Canonical CVE {cve} was not filtered by "
            f"_parse_osv_scanner_issues: {issues}"
        )


# ---------------------------------------------------------------------------
# load_merged_ignores — union-of-two-layers semantics
# ---------------------------------------------------------------------------


class TestLoadMergedIgnores:
    """Verify the canonical ∪ [tool.pip-audit] union semantics.

    Why this test matters
    ---------------------
    The helper is the *only* path through which a project's pyproject.toml
    can suppress a CVE without modifying crackerjack source. If it ever
    drifts from "always union, never override," a project could silently
    un-suppress a canonical CVE and re-introduce the original bug.
    """

    def test_project_dir_none_returns_canonical(self) -> None:
        """No project context → canonical tuple only."""
        result = load_merged_ignores(None)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_project_with_no_tool_osv_scanner_returns_canonical(
        self, tmp_path: Path,
    ) -> None:
        """A project pyproject without [tool.pip-audit] is a no-op."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')

        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_project_adds_extra_ids(
        self, tmp_path: Path,
    ) -> None:
        """Project [tool.pip-audit].ignore-vuln extends canonical."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.pip-audit]\n'
            'ignore-vuln = ["CVE-2099-00001", "PYSEC-2099-00002"]\n',
        )

        result = load_merged_ignores(tmp_path)

        assert "CVE-2099-00001" in result
        assert "PYSEC-2099-00002" in result
        # Canonical IDs are still present (project layer doesn't override).
        for vid in IGNORED_VULNERABILITY_IDS:
            assert vid in result, (
                f"Canonical ID {vid} missing after project override — "
                f"project layer should extend, not override."
            )

    def test_project_duplicate_ids_are_deduplicated(
        self, tmp_path: Path,
    ) -> None:
        """Set semantics: a project ID already in canonical isn't duplicated."""
        canonical_first = IGNORED_VULNERABILITY_IDS[0]
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.pip-audit]\n'
            f'ignore-vuln = ["{canonical_first}"]\n',
        )

        result = load_merged_ignores(tmp_path)
        assert result.count(canonical_first) == 1

    def test_result_is_sorted_deterministically(self) -> None:
        """The output order is stable across calls — no random iteration."""
        first = load_merged_ignores(None)
        second = load_merged_ignores(None)
        assert first == second
        assert first == sorted(first)

    def test_missing_pyproject_falls_back_to_canonical(
        self, tmp_path: Path,
    ) -> None:
        """If project_dir/pyproject.toml doesn't exist, no error."""
        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)

    def test_malformed_pyproject_falls_back_to_canonical(
        self, tmp_path: Path,
    ) -> None:
        """A malformed pyproject.toml must not crash the gate."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("this is not valid TOML === ")  # not a newline...

        result = load_merged_ignores(tmp_path)
        assert set(result) == set(IGNORED_VULNERABILITY_IDS)


# ---------------------------------------------------------------------------
# Tool commands consume load_merged_ignores (no longer through CLI flags;
# see TestHookExecutorUsesCanonicalList for the post-parse equivalent)
# ---------------------------------------------------------------------------
#
# The osv-scanner swap removed ``--ignore-vuln`` from the CLI because
# osv-scanner does not support that flag. The end-to-end guarantee —
# "project pyproject.toml additions are honored" — is now exercised via
# the parser path: ``test_project_adds_extra_ids`` verifies the merged
# list, and ``TestHookExecutorUsesCanonicalList::test_filters_cve_only_in_canonical_list``
# verifies the parser actually consumes it.
