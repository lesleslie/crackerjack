"""Tests for check_added_large_files native tool (Phase 8)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.tools.check_added_large_files import (
    format_size,
    get_file_size,
    get_git_tracked_files,
    main,
)


class TestFileSizeDetection:
    """Test file size detection and formatting."""

    def test_get_file_size_normal_file(self, tmp_path):
        """Test getting size of normal file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        size = get_file_size(test_file)
        assert size == 11  # "hello world" is 11 bytes

    def test_get_file_size_empty_file(self, tmp_path):
        """Test getting size of empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        size = get_file_size(test_file)
        assert size == 0

    def test_get_file_size_missing_file(self, tmp_path):
        """Test handling of missing file."""
        missing_file = tmp_path / "nonexistent.txt"

        size = get_file_size(missing_file)
        assert size == 0  # Returns 0 for missing files

    def test_get_file_size_binary_file(self, tmp_path):
        """Test getting size of binary file."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"\x00" * 1000)

        size = get_file_size(test_file)
        assert size == 1000

    def test_get_file_size_large_file(self, tmp_path):
        """Test getting size of large file."""
        test_file = tmp_path / "large.txt"
        test_file.write_text("x" * 1_000_000)

        size = get_file_size(test_file)
        assert size == 1_000_000

    def test_format_size_bytes(self):
        """Test formatting size in bytes."""
        assert format_size(0) == "0.0 B"
        assert format_size(100) == "100.0 B"
        assert format_size(1023) == "1023.0 B"

    def test_format_size_kilobytes(self):
        """Test formatting size in kilobytes."""
        assert format_size(1024) == "1.0 KB"
        assert format_size(5120) == "5.0 KB"
        assert format_size(1024 * 500) == "500.0 KB"

    def test_format_size_megabytes(self):
        """Test formatting size in megabytes."""
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(1024 * 1024 * 10) == "10.0 MB"
        assert format_size(1024 * 1024 * 100) == "100.0 MB"

    def test_format_size_gigabytes(self):
        """Test formatting size in gigabytes."""
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_size(1024 * 1024 * 1024 * 5) == "5.0 GB"

    def test_format_size_terabytes(self):
        """Test formatting size in terabytes."""
        assert format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"
        assert format_size(1024 * 1024 * 1024 * 1024 * 2) == "2.0 TB"


class TestGitIntegration:
    """Test git integration for file discovery."""

    @patch("subprocess.run")
    def test_get_git_tracked_files_success(self, mock_run):
        """Test getting tracked files from git."""
        mock_run.return_value = MagicMock(
            stdout="file1.py\nfile2.py\nfile3.txt\n",
            returncode=0,
        )

        files = get_git_tracked_files()

        assert len(files) == 3
        assert Path("file1.py") in files
        assert Path("file2.py") in files
        assert Path("file3.txt") in files
        mock_run.assert_called_once_with(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("subprocess.run")
    def test_get_git_tracked_files_empty_repo(self, mock_run):
        """Test getting tracked files from empty git repo."""
        mock_run.return_value = MagicMock(
            stdout="",
            returncode=0,
        )

        files = get_git_tracked_files()

        assert len(files) == 0

    @patch("subprocess.run")
    def test_get_git_tracked_files_not_git_repo(self, mock_run):
        """Test handling of non-git directory."""
        mock_run.side_effect = subprocess.CalledProcessError(128, ["git", "ls-files"])

        files = get_git_tracked_files()

        assert len(files) == 0  # Returns empty list

    @patch("subprocess.run")
    def test_get_git_tracked_files_git_not_installed(self, mock_run):
        """Test handling when git is not installed."""
        mock_run.side_effect = FileNotFoundError("git command not found")

        files = get_git_tracked_files()

        assert len(files) == 0  # Returns empty list

    @patch("subprocess.run")
    def test_get_git_tracked_files_with_subdirectories(self, mock_run):
        """Test getting tracked files with subdirectories."""
        mock_run.return_value = MagicMock(
            stdout="src/main.py\ntests/test_main.py\ndocs/README.md\n",
            returncode=0,
        )

        files = get_git_tracked_files()

        assert len(files) == 3
        assert Path("src/main.py") in files
        assert Path("tests/test_main.py") in files
        assert Path("docs/README.md") in files


class TestLargeFileDetection:
    """Test large file detection logic."""

    def test_detects_file_above_threshold(self, tmp_path, monkeypatch):
        """Test detection of file above size threshold."""
        monkeypatch.chdir(tmp_path)

        # Create file larger than 500KB (default threshold)
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (600 * 1024))  # 600KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("large.bin")]
            exit_code = main([])

        assert exit_code == 1  # Large file detected

    def test_allows_file_below_threshold(self, tmp_path, monkeypatch):
        """Test file below threshold is allowed."""
        monkeypatch.chdir(tmp_path)

        # Create file smaller than 500KB
        small_file = tmp_path / "small.txt"
        small_file.write_bytes(b"x" * (100 * 1024))  # 100KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("small.txt")]
            exit_code = main([])

        assert exit_code == 0  # No large files

    def test_custom_threshold_flag(self, tmp_path, monkeypatch):
        """Test --maxkb flag with custom threshold."""
        monkeypatch.chdir(tmp_path)

        # Create file that is 200KB
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"x" * (200 * 1024))  # 200KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("test.bin")]

            # Should fail with 100KB threshold
            exit_code_fail = main(["--maxkb", "100"])
            assert exit_code_fail == 1

            # Should pass with 300KB threshold
            exit_code_pass = main(["--maxkb", "300"])
            assert exit_code_pass == 0

    def test_multiple_files_mixed_sizes(self, tmp_path, monkeypatch):
        """Test detection with multiple files of varying sizes."""
        monkeypatch.chdir(tmp_path)

        # Create multiple files
        (tmp_path / "small1.txt").write_bytes(b"x" * (50 * 1024))  # 50KB
        (tmp_path / "small2.txt").write_bytes(b"x" * (100 * 1024))  # 100KB
        (tmp_path / "large.bin").write_bytes(b"x" * (600 * 1024))  # 600KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [
                Path("small1.txt"),
                Path("small2.txt"),
                Path("large.bin"),
            ]
            exit_code = main([])

        assert exit_code == 1  # At least one large file

    def test_enforce_all_flag(self, tmp_path, monkeypatch):
        """Test --enforce-all flag checks all files."""
        monkeypatch.chdir(tmp_path)

        # Create a large file
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (600 * 1024))  # 600KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("large.bin")]

            # Should detect with --enforce-all
            exit_code = main(["--enforce-all"])
            assert exit_code == 1


class TestCLI:
    """Test check_added_large_files CLI interface."""

    def test_cli_help(self):
        """Test --help displays correctly."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0

    def test_cli_no_args_default_behavior(self, tmp_path, monkeypatch):
        """Test CLI with no arguments uses current directory."""
        monkeypatch.chdir(tmp_path)

        # Create test files
        (tmp_path / "test1.txt").write_bytes(b"x" * (100 * 1024))  # 100KB
        (tmp_path / "test2.txt").write_bytes(b"x" * (200 * 1024))  # 200KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("test1.txt"), Path("test2.txt")]
            exit_code = main([])

        # Should pass (both under 500KB default)
        assert exit_code == 0

    def test_cli_with_file_arguments(self, tmp_path, monkeypatch):
        """Test CLI with explicit file arguments."""
        monkeypatch.chdir(tmp_path)

        test_file1 = tmp_path / "test1.bin"
        test_file2 = tmp_path / "test2.bin"

        test_file1.write_bytes(b"x" * (100 * 1024))  # 100KB
        test_file2.write_bytes(b"x" * (200 * 1024))  # 200KB

        exit_code = main([str(test_file1), str(test_file2)])

        assert exit_code == 0  # Both under default threshold

    def test_cli_no_git_repo(self, tmp_path, monkeypatch, capsys):
        """Test CLI with no git repository."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        exit_code = main([])

        assert exit_code == 0  # No files to check
        captured = capsys.readouterr()
        assert "No files to check" in captured.out

    def test_cli_nonexistent_file(self, tmp_path):
        """Test CLI with nonexistent file."""
        exit_code = main([str(tmp_path / "nonexistent.bin")])

        # Should handle gracefully (0 size = pass)
        assert exit_code == 0

    def test_cli_mixed_valid_and_large(self, tmp_path, monkeypatch, capsys):
        """Test CLI with mix of valid and large files."""
        monkeypatch.chdir(tmp_path)

        valid_file = tmp_path / "valid.txt"
        large_file = tmp_path / "large.bin"

        valid_file.write_bytes(b"x" * (100 * 1024))  # 100KB
        large_file.write_bytes(b"x" * (600 * 1024))  # 600KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("valid.txt"), Path("large.bin")]
            exit_code = main([])

        assert exit_code == 1  # At least one large file
        captured = capsys.readouterr()
        assert "large.bin" in captured.err  # Large file reported

    def test_cli_maxkb_flag_parsing(self, tmp_path, monkeypatch):
        """Test --maxkb flag parsing."""
        monkeypatch.chdir(tmp_path)

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"x" * (250 * 1024))  # 250KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("test.bin")]

            # Test various thresholds
            assert main(["--maxkb", "200"]) == 1  # Over 200KB
            assert main(["--maxkb", "300"]) == 0  # Under 300KB
            assert main(["--maxkb", "250"]) == 0  # Exactly 250KB (not over)

    def test_cli_enforce_all_flag_parsing(self, tmp_path, monkeypatch):
        """Test --enforce-all flag parsing."""
        monkeypatch.chdir(tmp_path)

        # Create file
        (tmp_path / "test.bin").write_bytes(b"x" * (100 * 1024))  # 100KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("test.bin")]

            # Should work with flag
            exit_code = main(["--enforce-all"])
            assert exit_code == 0  # Small file passes


class TestIntegration:
    """Integration tests with real-world scenarios."""

    def test_real_python_project(self, tmp_path, monkeypatch):
        """Test with typical Python project files."""
        monkeypatch.chdir(tmp_path)

        # Create typical project files with realistic sizes
        (tmp_path / "main.py").write_bytes(b"x" * (10 * 1024))  # 10KB
        (tmp_path / "test_main.py").write_bytes(b"x" * (5 * 1024))  # 5KB
        (tmp_path / "README.md").write_bytes(b"x" * (3 * 1024))  # 3KB
        (tmp_path / "requirements.txt").write_bytes(b"x" * 1024)  # 1KB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [
                Path("main.py"),
                Path("test_main.py"),
                Path("README.md"),
                Path("requirements.txt"),
            ]
            exit_code = main([])

        assert exit_code == 0  # All normal-sized files

    def test_real_with_accidentally_added_binary(self, tmp_path, monkeypatch):
        """Test detection of accidentally added binary files."""
        monkeypatch.chdir(tmp_path)

        # Create normal files and large binary
        (tmp_path / "main.py").write_bytes(b"x" * (10 * 1024))  # 10KB
        (tmp_path / "data.db").write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("main.py"), Path("data.db")]
            exit_code = main([])

        assert exit_code == 1  # Large binary detected

    def test_size_formatting_in_output(self, tmp_path, monkeypatch, capsys):
        """Test that file sizes are formatted in output."""
        monkeypatch.chdir(tmp_path)

        # Create file that will trigger size formatting
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (1024 * 1024))  # Exactly 1MB

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("large.bin")]
            main([])

        captured = capsys.readouterr()
        # Should show "1.0 MB" somewhere in output
        assert "MB" in captured.err or "MB" in captured.out

    def test_git_tracked_files_excludes_untracked(self, tmp_path, monkeypatch):
        """Test that only git-tracked files are checked."""
        monkeypatch.chdir(tmp_path)

        # Create tracked and untracked files
        (tmp_path / "tracked_small.txt").write_bytes(b"x" * (100 * 1024))  # 100KB
        (tmp_path / "untracked_large.bin").write_bytes(b"x" * (600 * 1024))  # 600KB

        # Mock to return only the tracked file
        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            mock_git.return_value = [Path("tracked_small.txt")]
            exit_code = main([])

        assert exit_code == 0  # Only tracked file checked, which is small

    def test_threshold_boundary_conditions(self, tmp_path, monkeypatch):
        """Test files at exact threshold boundary."""
        monkeypatch.chdir(tmp_path)

        # Create file exactly at threshold (500KB = 512000 bytes)
        exact_file = tmp_path / "exact.bin"
        exact_file.write_bytes(b"x" * (500 * 1024))

        # Create file 1 byte over threshold
        over_file = tmp_path / "over.bin"
        over_file.write_bytes(b"x" * (500 * 1024 + 1))

        with patch("crackerjack.tools.check_added_large_files.get_git_tracked_files") as mock_git:
            # Exactly at threshold should pass
            mock_git.return_value = [Path("exact.bin")]
            assert main([]) == 0

            # 1 byte over should fail
            mock_git.return_value = [Path("over.bin")]
            assert main([]) == 1
