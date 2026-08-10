"""Tests for crackerjack.fixers.dry.

Ported from tests/unit/agents/test_dry_agent.py, but rewritten to exercise
real SAFE_PATTERNS-based regex detection/fixing on real content instead of
mocking ``SAFE_PATTERNS`` (as the original test module did throughout). The
original's semantic-duplicate-detection tests (``TestDRYAgentSemanticDetection``,
``TestDRYAgentFunctionExtraction``) and SubAgent/coordinator dispatch tests
(``TestDRYAgentInitialization``, ``TestDRYAgentCanHandle``) were dropped
entirely, since that machinery (the embeddings-backed semantic enhancer, and
``can_handle``/``get_supported_types``) no longer exists -- see the module
docstring of ``crackerjack/fixers/dry.py`` for the full kept/dropped
rationale, including four pre-existing behavioral quirks/bugs preserved
verbatim (not fixed) per CLAUDE.md Rule 7, each covered by an explicit test
below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.fixers import dry
from crackerjack.models.issues import Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "id": "dry-test",
        "type": IssueType.DRY_VIOLATION,
        "severity": Priority.MEDIUM,
        "message": "DRY violation",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


class TestDetectErrorResponsePatterns:
    def test_no_matching_lines_returns_empty_list(self) -> None:
        content = 'def foo():\n    return {"success": True}\n'

        assert dry.detect_error_response_patterns(content) == []

    def test_raises_index_error_on_real_match_pre_existing_bug(self) -> None:
        """SAFE_PATTERNS["detect_error_response_patterns"] has zero capturing
        groups, but the code unconditionally does ``match.group(1)`` once it
        matches -- any real match raises ``IndexError``. Preserved verbatim
        from DRYAgent per CLAUDE.md Rule 7 -- not fixed."""
        content = (
            "def func1():\n"
            '    return \'{"error": "msg1"}\'\n'
            "\n"
            "def func2():\n"
            '    return \'{"error": "msg2"}\'\n'
            "\n"
            "def func3():\n"
            '    return \'{"error": "msg3"}\'\n'
        )

        with pytest.raises(IndexError):
            dry.detect_error_response_patterns(content)


class TestDetectPathConversionPatterns:
    def test_below_threshold_no_violation(self) -> None:
        content = "path1 = Path(value) if isinstance(value, str) else value\n"

        assert dry.detect_path_conversion_patterns(content) == []

    def test_two_or_more_matches_detected(self) -> None:
        content = (
            "path1 = Path(str_path1) if isinstance(str_path1, str) else str_path1\n"
            "path2 = Path(str_path2) if isinstance(str_path2, str) else str_path2\n"
        )

        violations = dry.detect_path_conversion_patterns(content)

        assert len(violations) == 1
        violation = violations[0]
        assert violation["type"] == "path_conversion_pattern"
        assert violation["suggestion"] == "Extract to path utility function"
        assert [i["line_number"] for i in violation["instances"]] == [1, 2]

    def test_non_matching_content_no_violation(self) -> None:
        content = "x = 1\ny = 2\nz = Path('/tmp/file')\n"

        assert dry.detect_path_conversion_patterns(content) == []


class TestDetectFileExistencePatterns:
    def test_plain_colon_never_matches_pre_existing_bug(self) -> None:
        """SAFE_PATTERNS["detect_file_existence_patterns"] requires a
        trailing space right after the colon, but the caller tests against
        ``line.strip()`` -- which strips that trailing space whenever the
        colon is the last thing on the line. A normally-formatted
        ``if not x.exists():`` therefore never matches. Preserved verbatim
        from DRYAgent per CLAUDE.md Rule 7 -- not fixed."""
        content = (
            "if not file1.exists():\nif not file2.exists():\nif not file3.exists():\n"
        )

        assert dry.detect_file_existence_patterns(content) == []

    def test_inline_statement_after_colon_matches(self) -> None:
        content = (
            "if not file1.exists(): raise ValueError(1)\n"
            "if not file2.exists(): raise ValueError(2)\n"
            "if not file3.exists(): raise ValueError(3)\n"
        )

        violations = dry.detect_file_existence_patterns(content)

        assert len(violations) == 1
        violation = violations[0]
        assert violation["type"] == "file_existence_pattern"
        assert violation["suggestion"] == "Extract to file validation utility"
        assert [i["line_number"] for i in violation["instances"]] == [1, 2, 3]

    def test_below_threshold_no_violation(self) -> None:
        content = (
            "if not file1.exists(): raise ValueError(1)\n"
            "if not file2.exists(): raise ValueError(2)\n"
        )

        assert dry.detect_file_existence_patterns(content) == []


class TestDetectExceptionPatterns:
    def test_plain_colon_never_matches_pre_existing_bug(self) -> None:
        """Same trailing-space-vs-strip quirk as
        ``detect_file_existence_patterns`` (see its test docstring).
        Preserved verbatim from DRYAgent per CLAUDE.md Rule 7 -- not fixed."""
        content = (
            "except Exception as e:\n"
            "    error = str(e)\n"
            "except BaseException as e:\n"
            "    error = str(e)\n"
            "except MyException as e:\n"
            "    error = str(e)\n"
        )

        assert dry.detect_exception_patterns(content) == []

    def test_inline_handler_with_error_str_next_line_matches(self) -> None:
        content = (
            "except Exception as e: pass\n"
            "    error = str(e)\n"
            "except BaseException as e: pass\n"
            "    error = str(e)\n"
            "except MyException as e: pass\n"
            "    error = str(e)\n"
        )

        violations = dry.detect_exception_patterns(content)

        assert len(violations) == 1
        violation = violations[0]
        assert violation["type"] == "exception_handling_pattern"
        assert violation["suggestion"] == (
            "Extract to error handling utility or decorator"
        )
        assert [i["line_number"] for i in violation["instances"]] == [1, 3, 5]

    def test_non_exception_suffixed_name_never_matches(self) -> None:
        """The underlying pattern requires the exception name to end in
        ``Exception``; ``ValueError`` does not match regardless of trailing
        content."""
        content = (
            "except ValueError as e: pass\n"
            "    error = str(e)\n"
            "except ValueError as e: pass\n"
            "    error = str(e)\n"
            "except ValueError as e: pass\n"
            "    error = str(e)\n"
        )

        assert dry.detect_exception_patterns(content) == []

    def test_missing_error_str_on_next_line_not_matched(self) -> None:
        content = (
            "except Exception as e: pass\n"
            "    logger.warning(e)\n"
            "except Exception as e: pass\n"
            "    logger.warning(e)\n"
            "except Exception as e: pass\n"
            "    logger.warning(e)\n"
        )

        assert dry.detect_exception_patterns(content) == []


class TestDetectDryViolations:
    def test_aggregates_multiple_detector_types(self) -> None:
        content = (
            "path1 = Path(str_path1) if isinstance(str_path1, str) else str_path1\n"
            "path2 = Path(str_path2) if isinstance(str_path2, str) else str_path2\n"
            "if not file1.exists(): raise ValueError(1)\n"
            "if not file2.exists(): raise ValueError(2)\n"
            "if not file3.exists(): raise ValueError(3)\n"
        )

        violations = dry.detect_dry_violations(content)

        types = {v["type"] for v in violations}
        assert types == {"path_conversion_pattern", "file_existence_pattern"}

    def test_no_violations_on_clean_content(self) -> None:
        content = "def foo():\n    return True\n"

        assert dry.detect_dry_violations(content) == []

    def test_propagates_index_error_from_error_response_detector(self) -> None:
        """``detect_error_response_patterns`` runs first inside
        ``detect_dry_violations``; its pre-existing IndexError bug (see
        ``TestDetectErrorResponsePatterns``) propagates all the way up."""
        content = (
            "def func1():\n"
            '    return \'{"error": "msg1"}\'\n'
            "\n"
            "def func2():\n"
            '    return \'{"error": "msg2"}\'\n'
            "\n"
            "def func3():\n"
            '    return \'{"error": "msg3"}\'\n'
        )

        with pytest.raises(IndexError):
            dry.detect_dry_violations(content)


class TestApplyDryFixes:
    def test_no_violations_returns_original_content(self) -> None:
        content = "def foo():\n    pass\n"

        assert dry.apply_dry_fixes(content, []) == content

    def test_path_conversion_fix_inserts_ensure_path_and_replaces_lines(self) -> None:
        content = (
            "path1 = Path(str_path1) if isinstance(str_path1, str) else str_path1\n"
            "path2 = Path(str_path2) if isinstance(str_path2, str) else str_path2\n"
        )
        violations = dry.detect_path_conversion_patterns(content)

        fixed = dry.apply_dry_fixes(content, violations)

        assert "def _ensure_path(path: str | Path) -> Path:" in fixed
        assert "path1 = _ensure_path(str_path1)" in fixed
        assert "path2 = _ensure_path(str_path2)" in fixed
        assert (
            "Path(str_path1) if isinstance(str_path1, str) else str_path1" not in fixed
        )

    def test_path_conversion_fix_skips_utility_when_already_present(self) -> None:
        content = (
            "def _ensure_path(path):\n"
            "    return Path(path)\n"
            "\n"
            "path1 = Path(str_path1) if isinstance(str_path1, str) else str_path1\n"
            "path2 = Path(str_path2) if isinstance(str_path2, str) else str_path2\n"
        )
        violations = dry.detect_path_conversion_patterns(content)

        fixed = dry.apply_dry_fixes(content, violations)

        # Only one _ensure_path definition -- no duplicate utility inserted.
        assert fixed.count("def _ensure_path") == 1
        assert "path1 = _ensure_path(str_path1)" in fixed
        assert "path2 = _ensure_path(str_path2)" in fixed

    def test_error_response_fix_inserts_utilities_but_leaves_line_unchanged(
        self,
    ) -> None:
        """``_apply_error_pattern_replacements`` applies the *path
        conversion* fix pattern to error-response lines, which never
        matches them -- the flagged line is left untouched even though the
        fix is reported as applied. Preserved verbatim from DRYAgent per
        CLAUDE.md Rule 7 -- not fixed."""
        content = 'import json\n\ndef func1():\n    return \'{"error": "msg1"}\'\n'
        lines = content.split("\n")
        violation = {
            "type": "error_response_pattern",
            "instances": [
                {"line_number": 4, "content": lines[3], "error_message": "msg1"}
            ],
            "suggestion": "Extract to error utility function",
        }

        fixed = dry.apply_dry_fixes(content, [violation])

        assert "def _create_error_response" in fixed
        assert "def _ensure_path" in fixed
        assert 'return \'{"error": "msg1"}\'' in fixed

    def test_file_existence_violations_not_fixed(self) -> None:
        """``_apply_violation_fix`` has no dispatch case for
        ``"file_existence_pattern"`` -- detected but never fixed. Preserved
        verbatim from DRYAgent per CLAUDE.md Rule 7 -- not fixed."""
        content = (
            "if not file1.exists(): raise ValueError(1)\n"
            "if not file2.exists(): raise ValueError(2)\n"
            "if not file3.exists(): raise ValueError(3)\n"
        )
        violations = dry.detect_file_existence_patterns(content)

        fixed = dry.apply_dry_fixes(content, violations)

        assert fixed == content

    def test_exception_handling_violations_not_fixed(self) -> None:
        content = (
            "except Exception as e: pass\n"
            "    error = str(e)\n"
            "except BaseException as e: pass\n"
            "    error = str(e)\n"
            "except MyException as e: pass\n"
            "    error = str(e)\n"
        )
        violations = dry.detect_exception_patterns(content)

        fixed = dry.apply_dry_fixes(content, violations)

        assert fixed == content

    def test_unknown_violation_type_returns_unmodified(self) -> None:
        content = "def foo():\n    pass\n"

        fixed = dry.apply_dry_fixes(content, [{"type": "not_a_real_type"}])

        assert fixed == content


class TestFindUtilityInsertPosition:
    def test_inserts_after_imports(self) -> None:
        lines = ["import os", "import sys", "", "def main():", "    pass"]

        assert dry._find_utility_insert_position(lines) == 2

    def test_no_imports_inserts_at_top(self) -> None:
        lines = ["def main():", "    pass"]

        assert dry._find_utility_insert_position(lines) == 0


class TestCheckEnsurePathExists:
    def test_detects_existing_definition(self) -> None:
        lines = ["def _ensure_path(path):", "    return Path(path)"]

        assert dry._check_ensure_path_exists(lines) is True

    def test_detects_missing_definition(self) -> None:
        lines = ["def foo():", "    pass"]

        assert dry._check_ensure_path_exists(lines) is False


class TestValidateDryIssue:
    def test_no_file_path(self) -> None:
        issue = _issue(file_path=None)

        result = dry._validate_dry_issue(issue)

        assert result is not None
        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    def test_file_not_found(self, tmp_path: Path) -> None:
        issue = _issue(file_path=str(tmp_path / "missing.py"))

        result = dry._validate_dry_issue(issue)

        assert result is not None
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    def test_valid_file_returns_none(self, tmp_path: Path) -> None:
        test_file = tmp_path / "valid.py"
        test_file.write_text("def foo(): pass")
        issue = _issue(file_path=str(test_file))

        assert dry._validate_dry_issue(issue) is None


class TestProcessDryViolation:
    def test_no_violations_found(self, tmp_path: Path) -> None:
        test_file = tmp_path / "clean.py"
        test_file.write_text("def foo():\n    return True\n")

        result = dry._process_dry_violation(test_file)

        assert result.success is True
        assert result.confidence == 0.7
        assert "No DRY violations" in result.recommendations[0]

    def test_unreadable_file_reports_could_not_read(self, tmp_path: Path) -> None:
        # A directory "exists" but Path.read_text() raises IsADirectoryError
        # (an OSError subclass), which _read_file swallows into None.
        a_dir = tmp_path / "adir"
        a_dir.mkdir()

        result = dry._process_dry_violation(a_dir)

        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    def test_violations_found_triggers_fix_and_save(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "path1 = Path(str_path1) if isinstance(str_path1, str) else str_path1\n"
            "path2 = Path(str_path2) if isinstance(str_path2, str) else str_path2\n"
        )

        result = dry._process_dry_violation(test_file)

        assert result.success is True
        assert result.confidence == 0.8
        assert "_ensure_path(str_path1)" in test_file.read_text()


class TestApplyAndSaveDryFixes:
    def test_success_writes_file_and_returns_result(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        content = (
            "path1 = Path(str_path1) if isinstance(str_path1, str) else str_path1\n"
            "path2 = Path(str_path2) if isinstance(str_path2, str) else str_path2\n"
        )
        violations = dry.detect_dry_violations(content)

        result = dry._apply_and_save_dry_fixes(test_file, content, violations)

        assert result.success is True
        assert result.confidence == 0.8
        assert result.files_modified == [str(test_file)]
        assert result.recommendations == ["Verify functionality after DRY fixes"]
        assert "_ensure_path(str_path1)" in test_file.read_text()

    def test_no_changes_returns_no_fixes_result(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        content = "original content\n"
        violations = [{"type": "not_a_real_type"}]

        result = dry._apply_and_save_dry_fixes(test_file, content, violations)

        assert result.success is False
        assert result.confidence == 0.5
        assert not test_file.exists()

    def test_write_failure_returns_error_result(self, tmp_path: Path) -> None:
        a_dir = tmp_path / "adir"
        a_dir.mkdir()
        content = (
            "path1 = Path(str_path1) if isinstance(str_path1, str) else str_path1\n"
            "path2 = Path(str_path2) if isinstance(str_path2, str) else str_path2\n"
        )
        violations = dry.detect_dry_violations(content)

        result = dry._apply_and_save_dry_fixes(a_dir, content, violations)

        assert result.success is False
        assert result.confidence == 0.0
        assert "Failed to write" in result.remaining_issues[0]


class TestCreateResultHelpers:
    def test_create_no_fixes_result(self) -> None:
        result = dry._create_no_fixes_result()

        assert result.success is False
        assert result.confidence == 0.5
        assert len(result.remaining_issues) == 1
        assert len(result.recommendations) == 3

    def test_create_dry_error_result(self) -> None:
        result = dry._create_dry_error_result(Exception("boom"))

        assert result.success is False
        assert result.confidence == 0.0
        assert "Error processing file: boom" in result.remaining_issues[0]


class TestFixDryViolation:
    async def test_no_file_path(self) -> None:
        issue = _issue(file_path=None)

        result = await dry.fix_dry_violation(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_file_not_found(self, tmp_path: Path) -> None:
        issue = _issue(file_path=str(tmp_path / "nonexistent.py"))

        result = await dry.fix_dry_violation(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_end_to_end_fixes_and_writes_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "path1 = Path(str_path1) if isinstance(str_path1, str) else str_path1\n"
            "path2 = Path(str_path2) if isinstance(str_path2, str) else str_path2\n"
        )
        issue = _issue(file_path=str(test_file))

        result = await dry.fix_dry_violation(issue)

        assert result.success is True
        assert result.confidence == 0.8
        assert result.files_modified == [str(test_file)]
        fixed_content = test_file.read_text()
        assert "_ensure_path(str_path1)" in fixed_content
        assert "_ensure_path(str_path2)" in fixed_content

    async def test_catches_index_error_from_detection_pre_existing_bug(
        self, tmp_path: Path
    ) -> None:
        """The top-level entry point catches the pre-existing IndexError
        from ``detect_error_response_patterns`` (see
        ``TestDetectErrorResponsePatterns``) and reports it as a normal
        failed ``FixResult`` instead of propagating -- so callers of
        ``fix_dry_violation`` never see a raw exception even though the
        underlying detector is buggy."""
        test_file = tmp_path / "test2.py"
        test_file.write_text(
            "def func1():\n"
            '    return \'{"error": "msg1"}\'\n'
            "\n"
            "def func2():\n"
            '    return \'{"error": "msg2"}\'\n'
            "\n"
            "def func3():\n"
            '    return \'{"error": "msg3"}\'\n'
        )
        issue = _issue(file_path=str(test_file))

        result = await dry.fix_dry_violation(issue)

        assert result.success is False
        assert "Error processing file" in result.remaining_issues[0]
