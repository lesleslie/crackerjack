"""Tests for end_of_file_fixer native tool (Phase 8)."""

import pytest

from crackerjack.tools.end_of_file_fixer import (
    fix_end_of_file,
    main,
    needs_newline_fix,
)


class TestEndOfFileDetection:
    """Test end-of-file newline detection logic."""

    def test_detects_missing_newline(self):
        """Test detection of missing newline."""
        content = b"hello world"
        needs_fix, fixed = needs_newline_fix(content)
        assert needs_fix
        assert fixed == b"hello world\n"

    def test_detects_correct_newline(self):
        """Test file with correct single newline."""
        content = b"hello world\n"
        needs_fix, fixed = needs_newline_fix(content)
        assert not needs_fix
        assert fixed is None

    def test_detects_multiple_newlines(self):
        """Test detection of multiple trailing newlines."""
        content = b"hello world\n\n\n"
        needs_fix, fixed = needs_newline_fix(content)
        assert needs_fix
        assert fixed == b"hello world\n"

    def test_empty_file(self):
        """Test empty file doesn't need newline."""
        content = b""
        needs_fix, fixed = needs_newline_fix(content)
        assert not needs_fix
        assert fixed is None

    def test_single_newline_only(self):
        """Test file with only newline."""
        content = b"\n"
        needs_fix, fixed = needs_newline_fix(content)
        assert not needs_fix
        assert fixed is None

    def test_preserves_content(self):
        """Test that content before newline is preserved."""
        content = b"line1\nline2\nline3"
        needs_fix, fixed = needs_newline_fix(content)
        assert needs_fix
        assert fixed == b"line1\nline2\nline3\n"


class TestEndOfFileFixer:
    """Test end-of-file fixing logic."""

    def test_fixes_missing_newline(self, tmp_path):
        """Test adding missing newline."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == b"hello world\n"

    def test_fixes_multiple_newlines(self, tmp_path):
        """Test fixing multiple trailing newlines."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world\n\n\n")

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == b"hello world\n"

    def test_no_modification_when_correct(self, tmp_path):
        """Test no modification when file is correct."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world\n")

        assert not fix_end_of_file(test_file)
        assert test_file.read_bytes() == b"hello world\n"

    def test_preserves_unix_newlines(self, tmp_path):
        """Test Unix newlines are preserved."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"line1\nline2\nline3")

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == b"line1\nline2\nline3\n"

    def test_handles_windows_newlines(self, tmp_path):
        """Test Windows newlines are handled."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"line1\r\nline2\r\nline3")

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == b"line1\r\nline2\r\nline3\n"

    def test_handles_binary_files(self, tmp_path):
        """Test binary files are handled gracefully."""
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")

        # Should add newline even to binary files
        assert fix_end_of_file(binary_file)
        assert binary_file.read_bytes() == b"\x00\x01\x02\x03\n"

    def test_handles_missing_file(self, tmp_path):
        """Test graceful handling of missing file."""
        missing_file = tmp_path / "nonexistent.txt"

        # Should return False and not raise
        assert not fix_end_of_file(missing_file)

    def test_multiline_content(self, tmp_path):
        """Test fixing multiline content."""
        test_file = tmp_path / "test.txt"
        content = b"line1\nline2\nline3\nline4"
        test_file.write_bytes(content)

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == b"line1\nline2\nline3\nline4\n"


class TestEndOfFileCLI:
    """Test end_of_file_fixer CLI interface."""

    def test_cli_help(self):
        """Test --help displays correctly."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0

    def test_cli_no_args_default_behavior(self, tmp_path, monkeypatch):
        """Test CLI with no arguments uses current directory."""
        monkeypatch.chdir(tmp_path)

        # Create test files
        (tmp_path / "test1.py").write_bytes(b"hello")
        (tmp_path / "test2.py").write_bytes(b"world\n")

        # Run main with no args
        exit_code = main([])

        # Should fix test1.py and return 1 (files modified)
        assert exit_code == 1
        assert (tmp_path / "test1.py").read_bytes() == b"hello\n"
        assert (tmp_path / "test2.py").read_bytes() == b"world\n"

    def test_cli_with_file_arguments(self, tmp_path):
        """Test CLI with explicit file arguments."""
        test_file1 = tmp_path / "test1.txt"
        test_file2 = tmp_path / "test2.txt"

        test_file1.write_bytes(b"hello")
        test_file2.write_bytes(b"world")

        exit_code = main([str(test_file1), str(test_file2)])

        assert exit_code == 1  # Files were modified
        assert test_file1.read_bytes() == b"hello\n"
        assert test_file2.read_bytes() == b"world\n"

    def test_cli_check_mode(self, tmp_path):
        """Test --check mode doesn't modify files."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello")

        exit_code = main(["--check", str(test_file)])

        assert exit_code == 1  # Issues found
        assert test_file.read_bytes() == b"hello"  # Not modified

    def test_cli_check_mode_correct_file(self, tmp_path):
        """Test --check mode with correct file."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello\n")

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

    def test_cli_mixed_correct_and_incorrect(self, tmp_path):
        """Test CLI with mix of correct and incorrect files."""
        correct_file = tmp_path / "correct.txt"
        incorrect_file = tmp_path / "incorrect.txt"

        correct_file.write_bytes(b"correct\n")
        incorrect_file.write_bytes(b"incorrect")

        exit_code = main([str(correct_file), str(incorrect_file)])

        assert exit_code == 1  # At least one file modified
        assert correct_file.read_bytes() == b"correct\n"
        assert incorrect_file.read_bytes() == b"incorrect\n"


class TestEndOfFileEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_file(self, tmp_path):
        """Test handling of empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_bytes(b"")

        assert not fix_end_of_file(empty_file)
        assert empty_file.read_bytes() == b""

    def test_file_with_only_whitespace(self, tmp_path):
        """Test file with only whitespace."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"   ")

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == b"   \n"

    def test_very_long_file(self, tmp_path):
        """Test handling of very long files."""
        test_file = tmp_path / "test.txt"
        long_content = b"x" * 100000
        test_file.write_bytes(long_content)

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == long_content + b"\n"

    def test_unicode_content(self, tmp_path):
        """Test handling of Unicode content."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes("hello 世界".encode())

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == "hello 世界\n".encode()

    def test_many_trailing_newlines(self, tmp_path):
        """Test fixing many trailing newlines."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content\n\n\n\n\n\n")

        assert fix_end_of_file(test_file)
        assert test_file.read_bytes() == b"content\n"

    def test_mixed_newline_types(self, tmp_path):
        """Test mixed Unix and Windows newlines."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"line1\nline2\r\nline3")

        assert fix_end_of_file(test_file)
        # Should add Unix newline at end
        assert test_file.read_bytes() == b"line1\nline2\r\nline3\n"


class TestEndOfFileIntegration:
    """Integration tests with real-world scenarios."""

    def test_python_file_with_code(self, tmp_path):
        """Test Python file with real code."""
        py_file = tmp_path / "test.py"
        code = b'def hello():\n    """Docstring"""\n    return "world"'
        py_file.write_bytes(code)

        assert fix_end_of_file(py_file)
        assert py_file.read_bytes() == code + b"\n"

    def test_markdown_file(self, tmp_path):
        """Test Markdown file."""
        md_file = tmp_path / "test.md"
        content = b"# Title\n\nParagraph text."
        md_file.write_bytes(content)

        assert fix_end_of_file(md_file)
        assert md_file.read_bytes() == content + b"\n"

    def test_json_file(self, tmp_path):
        """Test JSON file."""
        json_file = tmp_path / "test.json"
        content = b'{"key": "value"}'
        json_file.write_bytes(content)

        assert fix_end_of_file(json_file)
        assert json_file.read_bytes() == content + b"\n"

    def test_mixed_file_types(self, tmp_path):
        """Test CLI with mixed file types."""
        py_file = tmp_path / "test.py"
        txt_file = tmp_path / "test.txt"
        md_file = tmp_path / "test.md"

        py_file.write_bytes(b"code")
        txt_file.write_bytes(b"text\n")  # Already correct
        md_file.write_bytes(b"# Title")

        exit_code = main([str(py_file), str(txt_file), str(md_file)])

        assert exit_code == 1  # At least one modified
        assert py_file.read_bytes() == b"code\n"
        assert txt_file.read_bytes() == b"text\n"
        assert md_file.read_bytes() == b"# Title\n"

    def test_preserves_file_permissions(self, tmp_path):
        """Test that file permissions are preserved."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content")
        test_file.chmod(0o644)

        original_stat = test_file.stat()
        fix_end_of_file(test_file)
        new_stat = test_file.stat()

        assert original_stat.st_mode == new_stat.st_mode
