"""Tests for trailing_whitespace native tool (Phase 8)."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.tools.trailing_whitespace import (
    fix_trailing_whitespace,
    has_trailing_whitespace,
    main,
)


class TestTrailingWhitespaceDetection:
    """Test trailing whitespace detection logic."""

    def test_detects_space_at_end(self):
        """Test detection of space at end of line."""
        assert has_trailing_whitespace("hello world \n")
        assert has_trailing_whitespace("hello world  \n")

    def test_detects_tab_at_end(self):
        """Test detection of tab at end of line."""
        assert has_trailing_whitespace("hello world\t\n")
        assert has_trailing_whitespace("hello world\t\t\n")

    def test_detects_mixed_whitespace(self):
        """Test detection of mixed trailing whitespace."""
        assert has_trailing_whitespace("hello world \t \n")
        assert has_trailing_whitespace("hello world\t \t\n")

    def test_no_trailing_whitespace(self):
        """Test lines without trailing whitespace."""
        assert not has_trailing_whitespace("hello world\n")
        assert not has_trailing_whitespace("hello world\r\n")
        assert not has_trailing_whitespace("hello world")

    def test_empty_line(self):
        """Test empty line detection."""
        assert not has_trailing_whitespace("\n")
        assert not has_trailing_whitespace("\r\n")

    def test_only_whitespace(self):
        """Test line with only whitespace."""
        assert has_trailing_whitespace("   \n")
        assert has_trailing_whitespace("\t\t\n")


class TestTrailingWhitespaceFixer:
    """Test trailing whitespace fixing logic."""

    def test_fixes_trailing_space(self, tmp_path):
        """Test removal of trailing spaces."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world \n")

        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text() == "hello world\n"

    def test_fixes_trailing_tab(self, tmp_path):
        """Test removal of trailing tabs."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world\t\n")

        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text() == "hello world\n"

    def test_fixes_mixed_whitespace(self, tmp_path):
        """Test removal of mixed trailing whitespace."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world \t \n")

        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text() == "hello world\n"

    def test_preserves_newline_type(self, tmp_path):
        """Test that line ending type is preserved."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world \r\n", newline="")

        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text(newline="") == "hello world\r\n"

    def test_no_modification_when_clean(self, tmp_path):
        """Test no modification when file is already clean."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world\n")

        assert not fix_trailing_whitespace(test_file)
        assert test_file.read_text() == "hello world\n"

    def test_multiple_lines_with_mixed_issues(self, tmp_path):
        """Test fixing multiple lines with various issues."""
        test_file = tmp_path / "test.txt"
        content = "line1 \nline2\t\nline3\nline4  \n"
        expected = "line1\nline2\nline3\nline4\n"

        test_file.write_text(content)
        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text() == expected

    def test_skips_binary_files(self, tmp_path):
        """Test binary files are skipped gracefully."""
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")

        # Should return False (not modified) and not raise
        assert not fix_trailing_whitespace(binary_file)

    def test_handles_missing_file(self, tmp_path):
        """Test graceful handling of missing file."""
        missing_file = tmp_path / "nonexistent.txt"

        # Should return False and not raise
        assert not fix_trailing_whitespace(missing_file)


class TestTrailingWhitespaceCLI:
    """Test trailing_whitespace CLI interface."""

    def test_cli_help(self):
        """Test --help displays correctly."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0

    def test_cli_no_args_default_behavior(self, tmp_path, monkeypatch):
        """Test CLI with no arguments uses current directory."""
        monkeypatch.chdir(tmp_path)

        # Create test files
        (tmp_path / "test1.py").write_text("hello \n")
        (tmp_path / "test2.py").write_text("world\n")

        # Run main with no args
        exit_code = main([])

        # Should fix test1.py and return 1 (files modified)
        assert exit_code == 1
        assert (tmp_path / "test1.py").read_text() == "hello\n"
        assert (tmp_path / "test2.py").read_text() == "world\n"

    def test_cli_with_file_arguments(self, tmp_path):
        """Test CLI with explicit file arguments."""
        test_file1 = tmp_path / "test1.txt"
        test_file2 = tmp_path / "test2.txt"

        test_file1.write_text("hello \n")
        test_file2.write_text("world\t\n")

        exit_code = main([str(test_file1), str(test_file2)])

        assert exit_code == 1  # Files were modified
        assert test_file1.read_text() == "hello\n"
        assert test_file2.read_text() == "world\n"

    def test_cli_check_mode(self, tmp_path):
        """Test --check mode doesn't modify files."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello \n")

        exit_code = main(["--check", str(test_file)])

        assert exit_code == 1  # Issues found
        assert test_file.read_text() == "hello \n"  # Not modified

    def test_cli_check_mode_clean_file(self, tmp_path):
        """Test --check mode with clean file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello\n")

        exit_code = main(["--check", str(test_file)])

        assert exit_code == 0  # No issues

    def test_cli_no_files_to_check(self, tmp_path, monkeypatch, capsys):
        """Test CLI with no files to check."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        exit_code = main([])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No files to check" in captured.out

    def test_cli_nonexistent_file(self, tmp_path):
        """Test CLI with nonexistent file."""
        exit_code = main([str(tmp_path / "nonexistent.txt")])

        # Should handle gracefully
        assert exit_code == 0  # No files processed

    def test_cli_mixed_clean_and_dirty(self, tmp_path):
        """Test CLI with mix of clean and dirty files."""
        clean_file = tmp_path / "clean.txt"
        dirty_file = tmp_path / "dirty.txt"

        clean_file.write_text("clean\n")
        dirty_file.write_text("dirty \n")

        exit_code = main([str(clean_file), str(dirty_file)])

        assert exit_code == 1  # At least one file modified
        assert clean_file.read_text() == "clean\n"
        assert dirty_file.read_text() == "dirty\n"


class TestTrailingWhitespaceEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_file(self, tmp_path):
        """Test handling of empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        assert not fix_trailing_whitespace(empty_file)
        assert empty_file.read_text() == ""

    def test_file_with_no_newline_at_end(self, tmp_path):
        """Test file without trailing newline."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world ", newline="")

        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text(newline="") == "hello world"

    def test_file_with_only_whitespace_lines(self, tmp_path):
        """Test file with lines containing only whitespace."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("   \n\t\t\n  \t  \n")

        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text() == "\n\n\n"

    def test_very_long_line(self, tmp_path):
        """Test handling of very long lines."""
        test_file = tmp_path / "test.txt"
        long_line = "x" * 10000 + " \n"
        test_file.write_text(long_line)

        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text() == "x" * 10000 + "\n"

    def test_unicode_content(self, tmp_path):
        """Test handling of Unicode content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello 世界 \n")

        assert fix_trailing_whitespace(test_file)
        assert test_file.read_text() == "hello 世界\n"

    def test_permission_error(self, tmp_path, monkeypatch):
        """Test handling of permission errors."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello \n")

        # Mock read_text to raise PermissionError
        original_read_text = Path.read_text

        def mock_read_text(*args, **kwargs):
            raise PermissionError("Permission denied")

        monkeypatch.setattr(Path, "read_text", mock_read_text)

        # Should handle gracefully
        assert not fix_trailing_whitespace(test_file)


class TestTrailingWhitespaceIntegration:
    """Integration tests with real-world scenarios."""

    def test_python_file_with_code(self, tmp_path):
        """Test Python file with real code."""
        py_file = tmp_path / "test.py"
        code = '''def hello():
    """Docstring"""
    return "world"
'''
        expected = '''def hello():
    """Docstring"""
    return "world"
'''
        py_file.write_text(code)

        assert fix_trailing_whitespace(py_file)
        assert py_file.read_text() == expected

    def test_markdown_file(self, tmp_path):
        """Test Markdown file."""
        md_file = tmp_path / "test.md"
        content = "# Title  \n\nParagraph with trailing space. \n"
        expected = "# Title\n\nParagraph with trailing space.\n"

        md_file.write_text(content)
        assert fix_trailing_whitespace(md_file)
        assert md_file.read_text() == expected

    def test_mixed_file_types(self, tmp_path):
        """Test CLI with mixed file types."""
        py_file = tmp_path / "test.py"
        txt_file = tmp_path / "test.txt"
        md_file = tmp_path / "test.md"

        py_file.write_text("code \n")
        txt_file.write_text("text\n")  # Already clean
        md_file.write_text("# Title\t\n")

        exit_code = main([str(py_file), str(txt_file), str(md_file)])

        assert exit_code == 1  # At least one modified
        assert py_file.read_text() == "code\n"
        assert txt_file.read_text() == "text\n"
        assert md_file.read_text() == "# Title\n"
