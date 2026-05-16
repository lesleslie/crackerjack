"""Tests for linkcheckmd wrapper tool."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.tools.linkcheckmd_wrapper import (
    _check_broken_links,
    _get_scan_paths,
    _process_scan_results,
    _run_linkcheckmd,
    main,
)


class TestGetScanPaths:
    """Tests for _get_scan_paths function."""

    def test_single_file_returns_single_directory(self, tmp_path: Path) -> None:
        """Verify single file returns its parent directory."""
        file = tmp_path / "docs" / "test.md"
        file.parent.mkdir(parents=True, exist_ok=True)
        scan_paths = _get_scan_paths([file], tmp_path)
        assert scan_paths == [file.parent]

    def test_multiple_files_same_directory(self, tmp_path: Path) -> None:
        """Verify multiple files in same directory return single directory."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        files = [docs_dir / "test1.md", docs_dir / "test2.md"]
        scan_paths = _get_scan_paths(files, tmp_path)
        assert scan_paths == [docs_dir]

    def test_few_files_different_directories(self, tmp_path: Path) -> None:
        """Verify files in ≤5 directories return all directories."""
        dirs = [tmp_path / f"dir{i}" for i in range(3)]
        for d in dirs:
            d.mkdir()
        files = [d / "test.md" for d in dirs]
        scan_paths = _get_scan_paths(files, tmp_path)
        assert set(scan_paths) == set(dirs)
        assert scan_paths == sorted(dirs)

    def test_many_files_many_directories_returns_root(self, tmp_path: Path) -> None:
        """Verify >5 directories returns repo root."""
        dirs = [tmp_path / f"dir{i}" for i in range(6)]
        for d in dirs:
            d.mkdir()
        files = [d / "test.md" for d in dirs]
        scan_paths = _get_scan_paths(files, tmp_path)
        assert scan_paths == [tmp_path]

    def test_exactly_five_directories_returns_all(self, tmp_path: Path) -> None:
        """Verify exactly 5 directories returns all."""
        dirs = [tmp_path / f"dir{i}" for i in range(5)]
        for d in dirs:
            d.mkdir()
        files = [d / "test.md" for d in dirs]
        scan_paths = _get_scan_paths(files, tmp_path)
        assert set(scan_paths) == set(dirs)

    def test_paths_are_sorted(self, tmp_path: Path) -> None:
        """Verify returned paths are sorted."""
        dirs = [tmp_path / f"z_dir", tmp_path / f"a_dir", tmp_path / f"m_dir"]
        for d in dirs:
            d.mkdir()
        files = [d / "test.md" for d in dirs]
        scan_paths = _get_scan_paths(files, tmp_path)
        assert scan_paths == sorted(dirs)


class TestRunLinkcheckmd:
    """Tests for _run_linkcheckmd function."""

    @patch("subprocess.run")
    def test_successful_run(self, mock_run, tmp_path: Path) -> None:
        """Verify successful linkcheckmd execution."""
        mock_result = MagicMock()
        mock_result.stdout = "All links valid"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = _run_linkcheckmd(tmp_path / "docs", tmp_path)
        assert result.returncode == 0
        assert result.stdout == "All links valid"

    @patch("subprocess.run")
    def test_run_with_broken_links(self, mock_run, tmp_path: Path) -> None:
        """Verify linkcheckmd output on broken links."""
        mock_result = MagicMock()
        mock_result.stdout = "Broken link: http://example.com/dead"
        mock_result.returncode = 22
        mock_run.return_value = mock_result

        result = _run_linkcheckmd(tmp_path / "docs", tmp_path)
        assert result.returncode == 22

    @patch("subprocess.run")
    def test_run_uses_correct_python_module(self, mock_run, tmp_path: Path) -> None:
        """Verify subprocess uses correct python -m command."""
        mock_run.return_value = MagicMock(returncode=0)
        _run_linkcheckmd(tmp_path / "docs", tmp_path)

        call_args = mock_run.call_args
        assert "-m" in call_args[0][0]
        assert "linkcheckmd" in call_args[0][0]

    @patch("subprocess.run")
    def test_run_uses_correct_working_directory(self, mock_run, tmp_path: Path) -> None:
        """Verify subprocess uses repo_root as working directory."""
        mock_run.return_value = MagicMock(returncode=0)
        _run_linkcheckmd(tmp_path / "docs", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == tmp_path

    @patch("subprocess.run")
    def test_run_timeout(self, mock_run, tmp_path: Path) -> None:
        """Verify timeout is set correctly."""
        mock_run.return_value = MagicMock(returncode=0)
        _run_linkcheckmd(tmp_path / "docs", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 300

    @patch("subprocess.run")
    def test_run_uses_text_mode(self, mock_run, tmp_path: Path) -> None:
        """Verify subprocess uses text mode."""
        mock_run.return_value = MagicMock(returncode=0)
        _run_linkcheckmd(tmp_path / "docs", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["text"] is True
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["check"] is False


class TestCheckBrokenLinks:
    """Tests for _check_broken_links function."""

    def test_no_broken_links(self) -> None:
        """Verify no broken links detected in clean output."""
        results = ["All links valid", "No errors found"]
        assert _check_broken_links(results) is False

    def test_broken_link_found(self) -> None:
        """Verify broken link detection."""
        results = ["Broken link: http://example.com/dead"]
        assert _check_broken_links(results) is True

    def test_404_found(self) -> None:
        """Verify 404 error detection."""
        results = ["http://example.com/notfound: 404"]
        assert _check_broken_links(results) is True

    def test_case_insensitive_broken_link(self) -> None:
        """Verify case-insensitive broken link detection."""
        results = ["BROKEN LINK: http://example.com/dead"]
        assert _check_broken_links(results) is True

    def test_mixed_valid_and_broken(self) -> None:
        """Verify detection with mixed valid and broken links."""
        results = ["Valid link: http://example.com", "Broken link: http://dead.com"]
        assert _check_broken_links(results) is True

    def test_empty_results(self) -> None:
        """Verify empty results return no broken links."""
        results: list[str] = []
        assert _check_broken_links(results) is False

    def test_404_in_stderr(self) -> None:
        """Verify 404 detection in stderr output."""
        results = ["Error: 404 Not Found"]
        assert _check_broken_links(results) is True


class TestProcessScanResults:
    """Tests for _process_scan_results function."""

    @patch("crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd")
    def test_single_path_success(self, mock_run, tmp_path: Path) -> None:
        """Verify success with single path."""
        mock_result = MagicMock()
        mock_result.stdout = "All valid"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        paths = [tmp_path / "docs"]
        results, exit_code = _process_scan_results(paths, tmp_path)
        assert exit_code == 0

    @patch("crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd")
    def test_multiple_paths_success(self, mock_run, tmp_path: Path) -> None:
        """Verify success with multiple paths."""
        mock_result = MagicMock()
        mock_result.stdout = "All valid"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        paths = [tmp_path / "docs", tmp_path / "guides"]
        results, exit_code = _process_scan_results(paths, tmp_path)
        assert exit_code == 0
        assert mock_run.call_count == 2

    @patch("crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd")
    def test_skip_404_return_code(self, mock_run, tmp_path: Path) -> None:
        """Verify returncode 22 is skipped."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 22
        mock_run.return_value = mock_result

        paths = [tmp_path / "docs"]
        results, exit_code = _process_scan_results(paths, tmp_path)
        assert exit_code == 0

    @patch("crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd")
    def test_error_return_code_stops_processing(self, mock_run, tmp_path: Path) -> None:
        """Verify error returncode stops processing."""
        mock_result = MagicMock()
        mock_result.stdout = "Error occurred"
        mock_result.stderr = ""
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        paths = [tmp_path / "docs", tmp_path / "guides"]
        results, exit_code = _process_scan_results(paths, tmp_path)
        assert exit_code == 1
        assert mock_run.call_count == 1

    @patch("crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd")
    def test_timeout_exception(self, mock_run, tmp_path: Path) -> None:
        """Verify timeout exception returns exit code 1."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 300)

        paths = [tmp_path / "docs"]
        results, exit_code = _process_scan_results(paths, tmp_path)
        assert exit_code == 1

    @patch("crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd")
    def test_file_not_found_exception(self, mock_run, tmp_path: Path) -> None:
        """Verify FileNotFoundError returns exit code 127."""
        mock_run.side_effect = FileNotFoundError("linkcheckmd not found")

        paths = [tmp_path / "docs"]
        results, exit_code = _process_scan_results(paths, tmp_path)
        assert exit_code == 127

    @patch("crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd")
    @patch("builtins.print")
    def test_stdout_printed(self, mock_print, mock_run, tmp_path: Path) -> None:
        """Verify stdout is printed."""
        mock_result = MagicMock()
        mock_result.stdout = "Test output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        paths = [tmp_path / "docs"]
        _process_scan_results(paths, tmp_path)

        calls = [c[0][0] for c in mock_print.call_args_list if c[0]]
        assert any("Test output" in str(c) for c in calls)

    @patch("crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd")
    def test_results_collected(self, mock_run, tmp_path: Path) -> None:
        """Verify results are collected from all paths."""
        mock_result = MagicMock()
        mock_result.stdout = "Test output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        paths = [tmp_path / "docs", tmp_path / "guides"]
        results, _ = _process_scan_results(paths, tmp_path)
        assert len(results) == 2


class TestMain:
    """Tests for main function."""

    @patch("crackerjack.tools.linkcheckmd_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.linkcheckmd_wrapper._process_scan_results")
    def test_no_markdown_files(self, mock_process, mock_get_files) -> None:
        """Verify exit code 0 when no markdown files found."""
        mock_get_files.return_value = []
        result = main([])
        assert result == 0
        mock_process.assert_not_called()

    @patch("crackerjack.tools.linkcheckmd_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.linkcheckmd_wrapper._process_scan_results")
    def test_processes_md_and_markdown_files(self, mock_process, mock_get_files, tmp_path: Path) -> None:
        """Verify both .md and .markdown files are processed."""
        md_file = tmp_path / "README.md"
        markdown_file = tmp_path / "GUIDE.markdown"
        mock_get_files.side_effect = [[md_file], [markdown_file]]
        mock_process.return_value = ([], 0)

        result = main([])
        assert result == 0
        assert mock_get_files.call_count == 2

    @patch("crackerjack.tools.linkcheckmd_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.linkcheckmd_wrapper._process_scan_results")
    def test_handles_process_error(self, mock_process, mock_get_files, tmp_path: Path) -> None:
        """Verify error from _process_scan_results is returned."""
        md_file = tmp_path / "README.md"
        mock_get_files.side_effect = [[md_file], []]
        mock_process.return_value = ([], 1)

        result = main([])
        assert result == 1

    @patch("crackerjack.tools.linkcheckmd_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.linkcheckmd_wrapper._process_scan_results")
    def test_broken_links_return_code_22(self, mock_process, mock_get_files, tmp_path: Path) -> None:
        """Verify broken links detected returns exit code 22."""
        md_file = tmp_path / "README.md"
        mock_get_files.side_effect = [[md_file], []]
        mock_process.return_value = (["Broken link: http://dead.com"], 0)

        result = main([])
        assert result == 22

    @patch("crackerjack.tools.linkcheckmd_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.linkcheckmd_wrapper._process_scan_results")
    def test_success_with_valid_links(self, mock_process, mock_get_files, tmp_path: Path) -> None:
        """Verify success when all links valid."""
        md_file = tmp_path / "README.md"
        mock_get_files.side_effect = [[md_file], []]
        mock_process.return_value = (["All links valid"], 0)

        result = main([])
        assert result == 0
