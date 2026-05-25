"""Tests for tools modules with low/no coverage.

Covers: check_added_large_files, end_of_file_fixer, trailing_whitespace,
validate_regex_patterns, format_json, linkcheckmd_wrapper, local_link_checker,
validate_input_validator_patterns
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCheckAddedLargeFiles:
    """Test suite for check_added_large_files tool."""

    def test_format_size_bytes(self):
        """Test size formatting for bytes."""
        from crackerjack.tools.check_added_large_files import format_size

        assert format_size(500) == "500.0 B"
        assert format_size(0) == "0.0 B"

    def test_format_size_kilobytes(self):
        """Test size formatting for kilobytes."""
        from crackerjack.tools.check_added_large_files import format_size

        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"

    def test_format_size_megabytes(self):
        """Test size formatting for megabytes."""
        from crackerjack.tools.check_added_large_files import format_size

        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(2.5 * 1024 * 1024) == "2.5 MB"

    def test_format_size_gigabytes(self):
        """Test size formatting for gigabytes."""
        from crackerjack.tools.check_added_large_files import format_size

        assert format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_get_file_size_success(self, tmp_path):
        """Test get_file_size returns correct size."""
        from crackerjack.tools.check_added_large_files import get_file_size

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        size = get_file_size(test_file)
        assert size == 11

    def test_get_file_size_missing_file(self):
        """Test get_file_size returns 0 for missing file."""
        from crackerjack.tools.check_added_large_files import get_file_size

        size = get_file_size(Path("/nonexistent/file.txt"))
        assert size == 0

    def test_suggest_gitignore_action_archive(self, tmp_path):
        """Test suggest_gitignore_action for archive files."""
        from crackerjack.tools.check_added_large_files import suggest_gitignore_action

        archive = tmp_path / ".backup" / "archive.tar.gz"
        archive.parent.mkdir()
        archive.touch()

        action = suggest_gitignore_action(archive)
        assert action is not None
        assert "git rm --cached" in action

    def test_suggest_gitignore_action_bak(self, tmp_path):
        """Test suggest_gitignore_action for .bak files."""
        from crackerjack.tools.check_added_large_files import suggest_gitignore_action

        bak_file = tmp_path / "file.bak"
        bak_file.touch()

        action = suggest_gitignore_action(bak_file)
        assert action is not None
        assert ".bak" in action

    def test_suggest_gitignore_action_lock_files(self, tmp_path):
        """Test suggest_gitignore_action returns None for lock files."""
        from crackerjack.tools.check_added_large_files import suggest_gitignore_action

        lock_files = [
            tmp_path / "uv.lock",
            tmp_path / "poetry.lock",
            tmp_path / "Pipfile.lock",
            tmp_path / "package-lock.json",
            tmp_path / "yarn.lock",
        ]
        for lock_file in lock_files:
            lock_file.touch()
            action = suggest_gitignore_action(lock_file)
            assert action is None

    def test_suggest_gitignore_action_venv(self, tmp_path):
        """Test suggest_gitignore_action for virtual environments."""
        from crackerjack.tools.check_added_large_files import suggest_gitignore_action

        venv_path = tmp_path / ".venv" / "lib"
        venv_path.mkdir(parents=True)

        action = suggest_gitignore_action(venv_path)
        assert action is not None
        assert "virtual environment" in action

    def test_suggest_gitignore_action_cache(self, tmp_path):
        """Test suggest_gitignore_action for cache directories."""
        from crackerjack.tools.check_added_large_files import suggest_gitignore_action

        cache_path = tmp_path / ".cache" / "data"
        cache_path.mkdir(parents=True)

        action = suggest_gitignore_action(cache_path)
        assert action is not None
        assert "cache" in action

    def test_suggest_gitignore_action_image_docs(self, tmp_path):
        """Test suggest_gitignore_action returns None for images in docs."""
        from crackerjack.tools.check_added_large_files import suggest_gitignore_action

        docs_path = tmp_path / "docs" / "diagrams" / "image.png"
        docs_path.parent.mkdir(parents=True)

        action = suggest_gitignore_action(docs_path)
        assert action is None

    def test_main_no_files(self):
        """Test main returns 0 when no files provided and none found."""
        from crackerjack.tools.check_added_large_files import main

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files", return_value=[]):
            result = main([])
            assert result == 0

    def test_find_large_files_lock_files_exempted(self, tmp_path):
        """Test lock files are exempted from size check."""
        from crackerjack.tools.check_added_large_files import _find_large_files

        lock_file = tmp_path / "uv.lock"
        lock_file.write_bytes(b"x" * 2000)

        result = _find_large_files([lock_file], 1000, False)
        assert len(result) == 0  # Lock files exempted

    def test_find_large_files_detects_large_file(self, tmp_path):
        """Test large files are detected."""
        from crackerjack.tools.check_added_large_files import _find_large_files

        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * 2000)

        result = _find_large_files([large_file], 1000, False)
        assert len(result) == 1
        assert result[0][0] == large_file
        assert result[0][1] == 2000


class TestEndOfFileFixer:
    """Test suite for end_of_file_fixer tool."""

    def test_needs_newline_fix_empty_content(self):
        """Test needs_newline_fix with empty content."""
        from crackerjack.tools.end_of_file_fixer import needs_newline_fix

        needs_fix, fixed = needs_newline_fix(b"")
        assert needs_fix is False
        assert fixed is None

    def test_needs_newline_fix_single_newline(self):
        """Test needs_newline_fix with single trailing newline."""
        from crackerjack.tools.end_of_file_fixer import needs_newline_fix

        needs_fix, fixed = needs_newline_fix(b"hello\n")
        assert needs_fix is False
        assert fixed is None

    def test_needs_newline_fix_multiple_newlines(self):
        """Test needs_newline_fix with multiple trailing newlines."""
        from crackerjack.tools.end_of_file_fixer import needs_newline_fix

        needs_fix, fixed = needs_newline_fix(b"hello\n\n\n")
        assert needs_fix is True
        assert fixed == b"hello\n"

    def test_needs_newline_fix_no_newline(self):
        """Test needs_newline_fix with no trailing newline."""
        from crackerjack.tools.end_of_file_fixer import needs_newline_fix

        needs_fix, fixed = needs_newline_fix(b"hello")
        assert needs_fix is True
        assert fixed == b"hello\n"

    def test_fix_end_of_file_no_change_needed(self, tmp_path):
        """Test fix_end_of_file when no change needed."""
        from crackerjack.tools.end_of_file_fixer import fix_end_of_file

        test_file = tmp_path / "good.txt"
        test_file.write_bytes(b"hello\n")

        result = fix_end_of_file(test_file)
        assert result is False
        assert test_file.read_bytes() == b"hello\n"

    def test_fix_end_of_file_adds_newline(self, tmp_path):
        """Test fix_end_of_file adds missing newline."""
        from crackerjack.tools.end_of_file_fixer import fix_end_of_file

        test_file = tmp_path / "missing_newline.txt"
        test_file.write_bytes(b"hello")

        result = fix_end_of_file(test_file)
        assert result is True
        assert test_file.read_bytes() == b"hello\n"

    def test_fix_end_of_file_removes_extra_newlines(self, tmp_path):
        """Test fix_end_of_file removes extra newlines."""
        from crackerjack.tools.end_of_file_fixer import fix_end_of_file

        test_file = tmp_path / "extra_newlines.txt"
        test_file.write_bytes(b"hello\n\n\n")

        result = fix_end_of_file(test_file)
        assert result is True
        assert test_file.read_bytes() == b"hello\n"

    def test_process_files_in_check_mode(self, tmp_path):
        """Test _process_files_in_check_mode counts violations."""
        from crackerjack.tools.end_of_file_fixer import _process_files_in_check_mode

        good_file = tmp_path / "good.txt"
        good_file.write_bytes(b"hello\n")

        bad_file = tmp_path / "bad.txt"
        bad_file.write_bytes(b"hello")

        count = _process_files_in_check_mode([good_file, bad_file])
        assert count == 1


class TestTrailingWhitespace:
    """Test suite for trailing_whitespace tool."""

    def test_has_trailing_whitespace_true(self):
        """Test has_trailing_whitespace detects trailing spaces."""
        from crackerjack.tools.trailing_whitespace import has_trailing_whitespace

        assert has_trailing_whitespace("hello   \n") is True
        assert has_trailing_whitespace("hello  \r\n") is True

    def test_has_trailing_whitespace_false(self):
        """Test has_trailing_whitespace returns False for clean lines."""
        from crackerjack.tools.trailing_whitespace import has_trailing_whitespace

        assert has_trailing_whitespace("hello\n") is False
        assert has_trailing_whitespace("hello") is False
        assert has_trailing_whitespace("") is False

    def test_fix_line_whitespace_linux(self):
        """Test _fix_line_whitespace handles Linux line endings."""
        from crackerjack.tools.trailing_whitespace import _fix_line_whitespace

        result = _fix_line_whitespace("hello   \n")
        assert result == "hello\n"

    def test_fix_line_whitespace_windows(self):
        """Test _fix_line_whitespace handles Windows line endings."""
        from crackerjack.tools.trailing_whitespace import _fix_line_whitespace

        result = _fix_line_whitespace("hello   \r\n")
        assert result == "hello\r\n"

    def test_fix_line_whitespace_no_newline(self):
        """Test _fix_line_whitespace handles lines without newlines."""
        from crackerjack.tools.trailing_whitespace import _fix_line_whitespace

        result = _fix_line_whitespace("hello   ")
        assert result == "hello"

    def test_fix_trailing_whitespace_success(self, tmp_path):
        """Test fix_trailing_whitespace fixes file."""
        from crackerjack.tools.trailing_whitespace import fix_trailing_whitespace

        test_file = tmp_path / "whitespace.txt"
        test_file.write_text("hello   \n", encoding="utf-8")

        result = fix_trailing_whitespace(test_file)
        assert result is True
        assert test_file.read_text(encoding="utf-8") == "hello\n"

    def test_fix_trailing_whitespace_no_change_needed(self, tmp_path):
        """Test fix_trailing_whitespace when no change needed."""
        from crackerjack.tools.trailing_whitespace import fix_trailing_whitespace

        test_file = tmp_path / "clean.txt"
        test_file.write_text("hello\n", encoding="utf-8")

        result = fix_trailing_whitespace(test_file)
        assert result is False

    def test_process_files_in_check_mode(self, tmp_path):
        """Test _process_files_in_check_mode detects violations."""
        from crackerjack.tools.trailing_whitespace import _process_files_in_check_mode

        good_file = tmp_path / "good.txt"
        good_file.write_text("hello\n", encoding="utf-8")

        bad_file = tmp_path / "bad.txt"
        bad_file.write_text("hello   \n", encoding="utf-8")

        count = _process_files_in_check_mode([good_file, bad_file])
        assert count == 1


class TestValidateRegexPatterns:
    """Test suite for validate_regex_patterns tool."""

    def test_validate_regex_patterns_main_no_args(self):
        """Test main with no arguments uses default behavior."""
        from crackerjack.tools.validate_regex_patterns import main

        # main([]) returns 0 when no file_paths are provided
        result = main([])
        assert result == 0

    def test_validate_file_reads_python_file(self, tmp_path):
        """Test validate_file reads and validates a Python file."""
        from crackerjack.tools.validate_regex_patterns import validate_file

        test_file = tmp_path / "test.py"
        test_file.write_text("import re\nre.compile('pattern')\n", encoding="utf-8")

        issues = validate_file(test_file)
        assert isinstance(issues, list)


class TestFormatJson:
    """Test suite for format_json tool."""

    def test_format_json_file_valid(self, tmp_path):
        """Test formatting a valid JSON file."""
        from crackerjack.tools.format_json import format_json_file

        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}', encoding="utf-8")

        result, _ = format_json_file(test_file)
        assert result is True

    def test_format_json_file_invalid(self, tmp_path):
        """Test formatting an invalid JSON file."""
        from crackerjack.tools.format_json import format_json_file

        test_file = tmp_path / "invalid.json"
        test_file.write_text('{"key": }', encoding="utf-8")  # Invalid JSON

        result, _ = format_json_file(test_file)
        assert result is False

    def test_format_json_no_op_files(self):
        """Test main handles no files gracefully."""
        from crackerjack.tools.format_json import main

        with patch("crackerjack.tools.format_json.get_files_by_extension", return_value=[]):
            result = main([])
            assert result == 0


class TestLinkcheckmdWrapper:
    """Test suite for linkcheckmd_wrapper tool."""

    def test_main_no_args(self):
        """Test main with no arguments."""
        from crackerjack.tools.linkcheckmd_wrapper import main

        with patch("sys.stdout.write"):
            result = main([])
            # Returns 0 for no files found scenario
            assert result in (0, 1)


class TestLocalLinkChecker:
    """Test suite for local_link_checker tool."""

    def test_is_local_link(self):
        """Test is_local_link detection."""
        from crackerjack.tools.local_link_checker import is_local_link

        assert is_local_link("http://example.com") is False
        assert is_local_link("/path/to/file") is True
        assert is_local_link("./relative") is True
        assert is_local_link("../parent") is True

    def test_validate_local_link_existing(self, tmp_path):
        """Test validate_local_link with existing file."""
        from crackerjack.tools.local_link_checker import validate_local_link

        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        # validate_local_link takes (link_url, source_file, repo_root)
        result, msg = validate_local_link("./test.md", test_file, tmp_path)
        assert result is True

    def test_validate_local_link_missing(self, tmp_path):
        """Test validate_local_link with missing file."""
        from crackerjack.tools.local_link_checker import validate_local_link

        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        # validate_local_link takes (link_url, source_file, repo_root)
        result, msg = validate_local_link("./nonexistent.md", test_file, tmp_path)
        assert result is False

    def test_main_no_files(self):
        """Test main when no markdown files found."""
        from crackerjack.tools.local_link_checker import main

        with patch("crackerjack.tools.local_link_checker.get_git_tracked_files", return_value=[]):
            with patch("sys.stdout.write"):
                result = main([])
                assert result == 0


class TestValidateInputValidatorPatterns:
    """Test suite for validate_input_validator_patterns tool."""

    def test_validate_patterns_all_valid(self):
        """Test validation passes for valid patterns."""
        from crackerjack.tools.validate_input_validator_patterns import main

        # main() returns 0 if all tests pass
        result = main()
        assert result == 0

    def test_sql_injection_patterns(self):
        """Test SQL injection pattern detection."""
        from crackerjack.tools.validate_input_validator_patterns import test_sql_injection_patterns

        result = test_sql_injection_patterns()
        assert result is True

    def test_code_injection_patterns(self):
        """Test code injection pattern detection."""
        from crackerjack.tools.validate_input_validator_patterns import test_code_injection_patterns

        result = test_code_injection_patterns()
        assert result is True


class TestCodespellWrapper:
    """Test suite for codespell_wrapper tool."""

    def test_main_no_args(self):
        """Test main with no arguments."""
        from crackerjack.tools.codespell_wrapper import main

        with patch("sys.stdout.write"):
            result = main([])
            # Returns 0 or 1 depending on whether issues found
            assert result in (0, 1)


class TestMdformatWrapper:
    """Test suite for mdformat_wrapper tool."""

    def test_should_skip_file(self):
        """Test should_skip_file detection for archive and special files."""
        from crackerjack.tools.mdformat_wrapper import should_skip_file

        # These match the fnmatch patterns exactly (asterisk is literal in filename)
        assert should_skip_file(Path("docs/archive/old.md")) is True
        assert should_skip_file(Path("COMPLETE_report.md")) is False  # fnmatch *COMPLETE.md means ending with COMPLETE.md
        assert should_skip_file(Path("normal_file.md")) is False
        assert should_skip_file(Path("README.md")) is False

    def test_main_no_files(self):
        """Test main when no markdown files found."""
        from crackerjack.tools.mdformat_wrapper import main

        with patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files", return_value=[]):
            result = main([])
            assert result == 0