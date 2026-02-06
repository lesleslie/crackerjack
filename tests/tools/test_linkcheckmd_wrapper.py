"""Tests for linkcheckmd_wrapper tool."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from crackerjack.tools.linkcheckmd_wrapper import (
    _check_broken_links,
    _get_scan_paths,
    _process_scan_results,
    main,
)


def test_get_scan_paths_few_files():
    """Test _get_scan_paths with few files (<=5)."""
    repo_root = Path("/repo")
    files = [
        Path("/repo/README.md"),
        Path("/repo/docs/guide.md"),
        Path("/repo/src/main.py"),
    ]

    result = _get_scan_paths(files, repo_root)

    assert len(result) == 3
    assert all(isinstance(p, Path) for p in result)


def test_get_scan_paths_many_files():
    """Test _get_scan_paths with many files (>5)."""
    repo_root = Path("/repo")
    files = [Path(f"/repo/dir{i}/file.md") for i in range(10)]

    result = _get_scan_paths(files, repo_root)

    assert len(result) == 1
    assert result[0] == repo_root


def test_check_broken_links_found():
    """Test _check_broken_links with broken links detected."""
    results = [
        "Checking links... OK",
        "Found broken link: http://example.com/404",
        "All links valid",
    ]

    result = _check_broken_links(results)

    assert result is True, "Should detect broken link (404)"


def test_check_broken_links_none_found():
    """Test _check_broken_links with no broken links."""
    results = [
        "Checking links... OK",
        "All links valid",
        "No issues found",
    ]

    result = _check_broken_links(results)

    assert result is False, "Should not detect broken links"


def test_process_scan_results_success():
    """Test _process_scan_results with successful scans."""
    scan_paths = [Path("/repo/docs")]

    with patch('crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd') as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "All links valid"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        results, exit_code = _process_scan_results(scan_paths, Path("/repo"))

        assert exit_code == 0
        assert len(results) == 1


def test_process_scan_results_timeout():
    """Test _process_scan_results with timeout."""
    scan_paths = [Path("/repo/docs")]

    with patch('crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd') as mock_run:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 300)

        results, exit_code = _process_scan_results(scan_paths, Path("/repo"))

        assert exit_code == 1


def test_process_scan_results_not_found():
    """Test _process_scan_results when linkcheckmd not found."""
    scan_paths = [Path("/repo/docs")]

    with patch('crackerjack.tools.linkcheckmd_wrapper._run_linkcheckmd') as mock_run:
        mock_run.side_effect = FileNotFoundError()

        results, exit_code = _process_scan_results(scan_paths, Path("/repo"))

        assert exit_code == 127


def test_main_no_files(monkeypatch):
    """Test main with no markdown files."""
    with patch('crackerjack.tools.linkcheckmd_wrapper.get_git_tracked_files') as mock:
        mock.return_value = []
        result = main()
        assert result == 0


def test_main_with_broken_links(monkeypatch):
    """Test main that detects broken links."""
    with patch('crackerjack.tools.linkcheckmd_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [Path("README.md")]

        with patch('crackerjack.tools.linkcheckmd_wrapper._get_scan_paths') as mock_paths:
            mock_paths.return_value = [Path.cwd()]

            with patch('crackerjack.tools.linkcheckmd_wrapper._process_scan_results') as mock_process:
                mock_process.return_value = (["Found broken link: http://example.com/404"], 0)

                result = main()

                assert result == 22, "Should return 22 when broken links found"


def test_main_success(monkeypatch):
    """Test main with all links valid."""
    with patch('crackerjack.tools.linkcheckmd_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [Path("README.md")]

        with patch('crackerjack.tools.linkcheckmd_wrapper._get_scan_paths') as mock_paths:
            mock_paths.return_value = [Path.cwd()]

            with patch('crackerjack.tools.linkcheckmd_wrapper._process_scan_results') as mock_process:
                mock_process.return_value = (["All links valid"], 0)

                result = main()

                assert result == 0, "Should return 0 when all links valid"
