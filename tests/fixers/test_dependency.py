"""Tests for crackerjack.fixers.dependency.

Ported from tests/unit/agents/test_dependency_agent.py, keeping only the
cases that exercise real pyproject.toml regex/TOML-parsing logic. Cases
exercising SubAgent/coordinator dispatch (``can_handle``,
``get_supported_types``, ``DependencyAgent.__init__``) were dropped, since
that machinery no longer exists -- see the module docstring of
``crackerjack/fixers/dependency.py`` for the full kept/dropped rationale,
including the dead-code chain (``_check_for_false_positive`` and friends)
that was never ported because it has zero call sites anywhere in the
original codebase.

All file-based tests operate on synthetic ``pyproject.toml``-shaped content
written to ``tmp_path`` -- never on this repo's real ``pyproject.toml``.
"""

from __future__ import annotations

import os
import stat
import tomllib
from pathlib import Path

import pytest

from crackerjack.fixers import dependency
from crackerjack.models.issues import Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "type": IssueType.DEPENDENCY,
        "severity": Priority.MEDIUM,
        "message": "Unused dependency: pytest-snob",
        "file_path": "pyproject.toml",
        "line_number": 1,
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


class TestExtractDependencyName:
    def test_extract_pattern_colon_format(self) -> None:
        message = "Unused dependency: pytest-snob"
        assert dependency._extract_dependency_name(message) == "pytest-snob"

    def test_extract_pattern_quoted_format(self) -> None:
        message = "Dependency 'pytest-snob' is unused"
        assert dependency._extract_dependency_name(message) == "pytest-snob"

    def test_extract_pattern_simple_format(self) -> None:
        message = "pytest-snob is unused"
        assert dependency._extract_dependency_name(message) == "pytest-snob"

    def test_extract_case_insensitive(self) -> None:
        message = "UNUSED DEPENDENCY: PyTest-Snob"
        assert dependency._extract_dependency_name(message) == "PyTest-Snob"

    def test_extract_with_dashes_and_underscores(self) -> None:
        message = "Unused dependency: pytest-snob_extra"
        assert dependency._extract_dependency_name(message) == "pytest-snob_extra"

    def test_extract_malformed_message_returns_none(self) -> None:
        assert dependency._extract_dependency_name("Some random message") is None

    def test_extract_empty_message_returns_none(self) -> None:
        assert dependency._extract_dependency_name("") is None

    def test_extract_none_message_returns_none(self) -> None:
        assert dependency._extract_dependency_name(None) is None

    def test_extract_redundant_exclusion_name(self) -> None:
        assert (
            dependency._extract_dependency_name(
                "Redundant exclusion 'pip-audit': import detected in source code"
            )
            == "pip-audit"
        )
        assert (
            dependency._extract_dependency_name(
                "Redundant exclusion 'pyright': not found in pyproject.toml"
            )
            == "pyright"
        )

    def test_extract_excluded_dep_not_found_name(self) -> None:
        assert (
            dependency._extract_dependency_name(
                "Excluded dependencies not found in virtual environment: "
                "ty, pyrefly, pyright"
            )
            == "ty"
        )

    def test_ansi_escape_codes_stripped(self) -> None:
        message = "\x1b[31mUnused dependency: pytest-snob\x1b[0m"
        assert dependency._extract_dependency_name(message) == "pytest-snob"


class TestRemoveDependencyFromToml:
    def test_remove_double_quoted_dependency(self) -> None:
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
]
"""
        new_content = dependency._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "pytest-snob" not in new_content
        assert "pytest>=7.0.0" in new_content
        assert "ruff>=0.1.0" in new_content

    def test_remove_single_quoted_dependency(self) -> None:
        content = """
[project]
dependencies = [
    'pytest>=7.0.0',
    'pytest-snob>=0.1.0',
    'ruff>=0.1.0',
]
"""
        new_content = dependency._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "pytest-snob" not in new_content
        assert "pytest>=7.0.0" in new_content

    def test_remove_preserves_other_dependencies(self) -> None:
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
    "black>=23.0.0",
]
"""
        new_content = dependency._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "pytest>=7.0.0" in new_content
        assert "ruff>=0.1.0" in new_content
        assert "black>=23.0.0" in new_content

    def test_remove_handles_comments_correctly(self) -> None:
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    # "pytest-snob>=0.1.0",  # Commented out
    "ruff>=0.1.0",
]
"""
        new_content = dependency._remove_dependency_from_toml(content, "pytest-snob")
        # Should return None because the dependency is commented out
        assert new_content is None

    def test_remove_dependency_not_found_returns_none(self) -> None:
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
]
"""
        new_content = dependency._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is None

    def test_remove_preserves_sections_outside_dependencies(self) -> None:
        content = """
[tool.ruff]
line-length = 100

[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]

[tool.pytest]
testpaths = ["tests"]
"""
        new_content = dependency._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "[tool.ruff]" in new_content
        assert "line-length = 100" in new_content
        assert "[tool.pytest]" in new_content

    def test_remove_no_partial_matches(self) -> None:
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
        # Try to remove 'pytest' - should not remove 'pytest-snob'
        new_content = dependency._remove_dependency_from_toml(content, "pytest")
        if new_content:  # If it found and removed pytest
            assert "pytest-snob" in new_content

    def test_remove_bleeds_into_optional_dependencies_section(self) -> None:
        """Pre-existing scoping quirk, preserved verbatim (not fixed).

        `_update_dependencies_state` only turns off "in dependencies" scope
        at a `[section]` header that does NOT contain the substring
        "dependencies". `[project.optional-dependencies]` contains that
        substring, so the scanner treats it as still being inside a
        dependencies block and will remove matching entries there too.
        """
        content = """
[project]
name = "test"
dependencies = [
    "pytest>=7.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest-snob>=0.1.0",
]
"""
        new_content = dependency._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "pytest-snob" not in new_content
        assert "[project.optional-dependencies]" in new_content
        assert "dev = [" in new_content
        # The unrelated dependency in [project] is untouched.
        assert "pytest>=7.0.0" in new_content


class TestRemoveDependencyFromContent:
    def test_removes_from_list_style_dependencies(self) -> None:
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
        new_content = dependency._remove_dependency_from_content(content, "pytest-snob")
        assert new_content is not None
        assert "pytest-snob" not in new_content
        assert "pytest>=7.0.0" in new_content

    def test_no_project_table_returns_none(self) -> None:
        content = """
[tool.ruff]
line-length = 100
"""
        assert (
            dependency._remove_dependency_from_content(content, "pytest-snob") is None
        )

    def test_no_dependencies_key_returns_none(self) -> None:
        content = """
[project]
name = "test"
version = "0.1.0"
"""
        assert (
            dependency._remove_dependency_from_content(content, "pytest-snob") is None
        )

    def test_dependency_absent_returns_none(self) -> None:
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
]
"""
        assert (
            dependency._remove_dependency_from_content(content, "pytest-snob") is None
        )

    def test_invalid_toml_falls_back_to_regex_removal(self) -> None:
        """When tomllib.loads raises, the except branch still attempts the
        line-based regex removal on the raw text -- no existence check is
        performed in that fallback path."""
        content = """
[project
dependencies = [
    "pytest-snob>=0.1.0",
]
"""
        new_content = dependency._remove_dependency_from_content(content, "pytest-snob")
        assert new_content is not None
        assert "pytest-snob" not in new_content

    def test_dict_style_dependencies_table(self) -> None:
        """Non-standard per PEP 621 (dependencies is normally an array),
        but tomllib will happily parse `[project.dependencies]` as a table,
        exercising the dict branch of `_remove_dependency_from_deps`."""
        content = """
[project.dependencies]
pytest = "7.0.0"
ruff = "0.1.0"
"""
        # The dict-existence check passes (exact key membership), but the
        # actual edit is still performed by the line-based regex remover,
        # which is scoped to arrays like `dependencies = [...]` and finds
        # no such line here -- so the overall result is None. This pins
        # the real (if surprising) behavior rather than asserting a
        # hypothetical "should work" outcome.
        assert dependency._remove_dependency_from_content(content, "pytest") is None

    def test_substring_false_positive_does_not_cause_wrong_removal(self) -> None:
        """Pre-existing quirk, preserved verbatim (not fixed).

        `_remove_dependency_from_deps`'s list branch checks
        `dep_name not in dep` -- substring containment, not exact match.
        Checking for "pytest" existence against `"pytest-snob>=0.1.0"`
        yields a false positive (`removed=True`), but the actual edit is
        delegated to the exact-pattern-matching
        `_remove_dependency_from_toml`, which finds no line matching a
        standalone "pytest" dependency and correctly returns None.
        """
        content = """
[project]
dependencies = [
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
]
"""
        # Confirm the loose existence check itself reports a false positive.
        deps = ["pytest-snob>=0.1.0", "ruff>=0.1.0"]
        assert dependency._remove_dependency_from_deps(deps, "pytest") is True

        # But the end-to-end content transform correctly does nothing.
        result = dependency._remove_dependency_from_content(content, "pytest")
        assert result is None


class TestRemoveCreosoteExclusion:
    CREOSOTE_TOML = """
[project]
name = "test"
dependencies = [
    "pytest>=7.0.0",
]

[tool.creosote]
paths = [
    "crackerjack",
]
exclude-deps = [
    "hatchling",
    "pytest",
    "pip-audit",
    "pyright",
    "websockets",
]
"""

    def test_remove_creosote_exclusion(self) -> None:
        new_content = dependency._remove_creosote_exclusion(
            self.CREOSOTE_TOML, "pip-audit"
        )
        assert new_content is not None
        assert '"pip-audit"' not in new_content
        assert '"pytest"' in new_content
        assert '"pyright"' in new_content
        # Section structure preserved.
        assert "[tool.creosote]" in new_content
        assert "exclude-deps = [" in new_content
        assert new_content.rstrip().endswith("]")

    def test_remove_creosote_exclusion_missing_returns_none(self) -> None:
        new_content = dependency._remove_creosote_exclusion(
            self.CREOSOTE_TOML, "nonexistent-dep"
        )
        assert new_content is None

    def test_remove_creosote_exclusion_does_not_touch_dependencies(self) -> None:
        """Verify the helper only edits [tool.creosote].exclude-deps, not
        [project.dependencies] -- contrast with
        `_remove_dependency_from_toml`'s imprecise scoping (see
        TestRemoveDependencyFromToml.test_remove_bleeds_into_optional_dependencies_section)."""
        new_content = dependency._remove_creosote_exclusion(
            self.CREOSOTE_TOML, "pytest"
        )
        assert new_content is not None
        assert "pytest>=7.0.0" in new_content

    def test_is_exclusion_line_ignores_comments(self) -> None:
        assert dependency._is_exclusion_line('    # "pip-audit",', "pip-audit") is (
            False
        )

    def test_is_exclusion_line_strips_trailing_comma_and_comment(self) -> None:
        assert dependency._is_exclusion_line(
            '    "pip-audit",  # transitive', "pip-audit"
        )


class TestValidateIssue:
    def test_no_file_path(self) -> None:
        issue = _issue(file_path=None)
        result = dependency._validate_issue(issue)
        assert result is not None
        assert result.success is False
        assert "No file path provided" in result.remaining_issues

    def test_non_pyproject_toml(self) -> None:
        issue = _issue(file_path="requirements.txt")
        result = dependency._validate_issue(issue)
        assert result is not None
        assert result.success is False
        assert "only fix dependencies in pyproject.toml" in result.remaining_issues[0]

    def test_cannot_extract_dependency_name(self) -> None:
        issue = _issue(message="Some random message")
        result = dependency._validate_issue(issue)
        assert result is not None
        assert result.success is False
        assert "Could not extract dependency name" in result.remaining_issues[0]

    def test_valid_issue_returns_none(self) -> None:
        issue = _issue()
        assert dependency._validate_issue(issue) is None


class TestFixDependencyIssue:
    async def test_no_file_path(self) -> None:
        issue = _issue(file_path=None)

        result = await dependency.fix_dependency_issue(issue)

        assert result.success is False
        assert result.confidence == 0.0
        assert "No file path provided" in result.remaining_issues

    async def test_non_pyproject_toml(self) -> None:
        issue = _issue(file_path="requirements.txt")

        result = await dependency.fix_dependency_issue(issue)

        assert result.success is False
        assert result.confidence == 0.0
        assert "only fix dependencies in pyproject.toml" in result.remaining_issues[0]

    async def test_missing_file(self, tmp_path: Path) -> None:
        missing_file = tmp_path / "pyproject.toml"

        issue = _issue(file_path=str(missing_file))

        result = await dependency.fix_dependency_issue(issue)

        assert result.success is False
        assert "Could not read pyproject.toml" in result.remaining_issues

    async def test_no_dependencies_section(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test"
version = "0.1.0"
"""
        )

        issue = _issue(file_path=str(pyproject))

        result = await dependency.fix_dependency_issue(issue)

        assert result.success is False
        assert len(result.remaining_issues) > 0

    async def test_dependency_not_found(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test"
dependencies = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
]
"""
        )

        issue = _issue(file_path=str(pyproject))

        result = await dependency.fix_dependency_issue(issue)

        assert result.success is False
        assert len(result.remaining_issues) > 0
        error_msg = result.remaining_issues[0]
        assert "not found" in error_msg or "Failed to remove" in error_msg
        # The original file is untouched.
        assert "pytest-snob" not in pyproject.read_text()

    async def test_success_list_style(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test"
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
]
"""
        )

        issue = _issue(file_path=str(pyproject))

        result = await dependency.fix_dependency_issue(issue)

        assert result.success is True
        assert result.confidence == 0.9
        assert "Removed unused dependency: pytest-snob" in result.fixes_applied
        assert len(result.files_modified) > 0
        assert "pyproject.toml" in result.files_modified[0]

        written_content = pyproject.read_text()
        assert "pytest-snob" not in written_content
        assert "pytest>=7.0.0" in written_content  # Other deps preserved

    async def test_no_backup_file_created_after_successful_fix(
        self, tmp_path: Path
    ) -> None:
        """Genuine proof of Claim 1 ("no backup/rollback mechanism"): after
        a *successful* edit, no `.bak` sibling (or any other extra file)
        is left behind in the directory, because there is no backup step
        to create one. Contrast with `dead_code.py`'s `_backup_file`,
        which does create a `.bak` sibling before every removal write --
        if an equivalent step were ever added here, this test would start
        failing the moment a second file appeared next to
        `pyproject.toml`."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
        )

        issue = _issue(file_path=str(pyproject))
        result = await dependency.fix_dependency_issue(issue)

        assert result.success is True
        # The directory contains exactly the original file -- no backup,
        # no temp file, no rollback artifact of any kind.
        assert [p.name for p in tmp_path.iterdir()] == ["pyproject.toml"]
        assert not (tmp_path / "pyproject.toml.bak").exists()

    async def test_no_rollback_on_simulated_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Genuine proof of Claim 1 for a write failure that isn't a
        permission-denied short-circuit (which fails atomically *before*
        any bytes are written, so it can't distinguish "no rollback" from
        "rollback never triggered"). This monkeypatches the module's own
        `_write_file` I/O boundary -- the same technique `dead_code.py`'s
        rollback tests use -- to perform a real corrupting write to disk
        and then report failure, simulating a write that fails partway
        through (e.g. disk full after some bytes already landed). Because
        `DependencyAgent` never had a rollback step (unlike
        `dead_code.py`'s `_rollback_file`, which restores the pre-edit
        `.bak` on write failure), the corrupted content is left on disk
        exactly as the fake write left it -- nothing restores the
        original. If a rollback mechanism were ever added, this test
        would start failing (the final assertion would need to become
        `== original_content` instead)."""
        pyproject = tmp_path / "pyproject.toml"
        original_content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
        pyproject.write_text(original_content)

        def fake_write_that_corrupts(file_path: str | Path, content: str) -> bool:
            Path(file_path).write_text("CORRUPTED MID-EDIT", encoding="utf-8")
            return False

        monkeypatch.setattr(dependency, "_write_file", fake_write_that_corrupts)

        issue = _issue(file_path=str(pyproject))
        result = await dependency.fix_dependency_issue(issue)

        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]
        # No rollback: the real on-disk content is the corrupted write,
        # not the restored original.
        assert pyproject.read_text() == "CORRUPTED MID-EDIT"

    async def test_write_failure_real_permission_denied(self, tmp_path: Path) -> None:
        """Real (non-mocked) write failure: the target file is made
        read-only so the actual `Path.write_text` call raises OSError,
        exercising `_write_file`'s except branch and the
        "Failed to write modified pyproject.toml" error path."""
        if os.getuid() == 0:
            pytest.skip("root bypasses filesystem permission checks")

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
        )
        original_content = pyproject.read_text()
        pyproject.chmod(stat.S_IREAD)

        try:
            issue = _issue(file_path=str(pyproject))
            result = await dependency.fix_dependency_issue(issue)
        finally:
            pyproject.chmod(stat.S_IREAD | stat.S_IWRITE)

        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]
        # No backup/rollback mechanism exists for this fixer -- the
        # original on-disk content is untouched only because the write
        # itself never got past permission checks, not because of any
        # explicit safety net.
        assert pyproject.read_text() == original_content

    async def test_no_post_edit_toml_validation_output_happens_to_be_valid(
        self, tmp_path: Path
    ) -> None:
        """Secondary illustration only -- NOT a pin of Claim 2 by itself.
        The written content here happens to still be valid TOML, so this
        test alone would keep passing even if post-edit re-validation were
        added to `fix_dependency_issue` (a validator would have nothing to
        reject). See
        `test_no_post_edit_toml_validation_malformed_output_still_reports_success`
        below for the actual proof that no validation occurs, using a
        fixture where the output is genuinely invalid TOML."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
        )

        issue = _issue(file_path=str(pyproject))
        result = await dependency.fix_dependency_issue(issue)

        assert result.success is True
        tomllib.loads(pyproject.read_text())  # would raise if malformed

    async def test_no_post_edit_toml_validation_malformed_output_still_reports_success(
        self, tmp_path: Path
    ) -> None:
        """Genuine proof of Claim 2 ("no post-edit TOML validation"): this
        fixture drives the full `fix_dependency_issue` pipeline -- the
        `_remove_dependency_from_content` existence pre-check *and* the
        `_remove_dependency_from_toml` regex removal -- into a structural
        edge case where the final output is no longer valid TOML at all.

        The fixture names an `[project.optional-dependencies]` group the
        same as the real dependency being removed ("pytest"): the
        `[project].dependencies` array legitimately contains
        `"pytest>=7.0.0"`, so the substring existence pre-check passes
        (not a false positive here). But `_remove_dependency_from_toml`'s
        scoping-bleed quirk (see
        TestRemoveDependencyFromToml.test_remove_bleeds_into_optional_dependencies_section)
        keeps "in dependencies" scope active through the
        `[project.optional-dependencies]` header, and `_is_dependency_line`
        treats any in-scope line that *starts with* the dep name as
        removable -- not just array entries -- so it also strips the
        `pytest = [` key/array-open line of the *unrelated*
        `[project.optional-dependencies].pytest` group. That group's
        array contents and closing bracket are left behind with no key,
        which is not valid TOML: `tomllib.loads` raises `TOMLDecodeError`
        on the result.

        `fix_dependency_issue` still reports `success=True`, because
        nothing in the write path re-parses its own output to catch this.
        If post-edit validation were ever added, this specific case would
        have to start failing (or at least warning) instead of silently
        succeeding -- which is exactly what makes this a real pin rather
        than an incidental one."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test"
dependencies = [
    "pytest>=7.0.0",
]

[project.optional-dependencies]
pytest = [
    "pytest-cov>=4.0.0",
]
"""
        )

        issue = _issue(message="Unused dependency: pytest", file_path=str(pyproject))
        result = await dependency.fix_dependency_issue(issue)

        assert result.success is True

        written_content = pyproject.read_text()
        # The real [project].dependencies entry was removed...
        assert "pytest>=7.0.0" not in written_content
        # ...but so was the unrelated `pytest = [` key line under
        # [project.optional-dependencies], leaving its array contents
        # orphaned with no key.
        assert "pytest = [" not in written_content
        assert '"pytest-cov>=4.0.0"' in written_content

        with pytest.raises(tomllib.TOMLDecodeError):
            tomllib.loads(written_content)

    async def test_creosote_redundant_exclusion_import_detected(
        self, tmp_path: Path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(TestRemoveCreosoteExclusion.CREOSOTE_TOML)

        issue = _issue(
            message="Redundant exclusion 'pip-audit': import detected in source code",
            file_path=str(pyproject),
            stage="creosote",
        )

        result = await dependency.fix_dependency_issue(issue)

        assert result.success is True
        assert result.confidence == 0.9
        assert any("pip-audit" in f for f in result.fixes_applied)
        assert any("exclude-deps" in f for f in result.fixes_applied)
        assert "pyproject.toml" in result.files_modified[0]

        written_content = pyproject.read_text()
        assert '"pip-audit"' not in written_content
        assert '"hatchling"' in written_content
        assert '"pytest"' in written_content
        assert '"pyright"' in written_content
        assert '"websockets"' in written_content
        assert "pytest>=7.0.0" in written_content

    async def test_creosote_redundant_exclusion_not_in_pyproject(
        self, tmp_path: Path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(TestRemoveCreosoteExclusion.CREOSOTE_TOML)

        issue = _issue(
            message=(
                "Redundant exclusion 'pyright': not found in pyproject.toml "
                "(transitive dependency or typo)"
            ),
            file_path=str(pyproject),
            stage="creosote",
        )

        result = await dependency.fix_dependency_issue(issue)

        assert result.success is True
        assert any("pyright" in f for f in result.fixes_applied)

        written_content = pyproject.read_text()
        assert '"pyright"' not in written_content
        assert '"pip-audit"' in written_content  # Other exclusions preserved

    async def test_excluded_dependencies_not_found_header(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(TestRemoveCreosoteExclusion.CREOSOTE_TOML)

        issue = _issue(
            message=(
                "Excluded dependencies not found in virtual environment: "
                "pip-audit, ty, pyrefly"
            ),
            file_path=str(pyproject),
            stage="creosote",
        )

        result = await dependency.fix_dependency_issue(issue)

        # First dep in the list is the one extracted; should be removed.
        assert result.success is True
        assert any("pip-audit" in f for f in result.fixes_applied)
        written_content = pyproject.read_text()
        assert '"pip-audit"' not in written_content
