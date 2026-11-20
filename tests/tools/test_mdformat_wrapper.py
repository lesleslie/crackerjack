"""Tests for mdformat_wrapper tool."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from crackerjack.tools.mdformat_wrapper import main, should_skip_file


def test_should_skip_file_archive_patterns():
    """Test should_skip_file with archive patterns."""
    # Per-area archives (`docs/.archive/`, `docs/plans/.archive/`, …)
    # plus the rare plural variant should all be skipped.
    assert should_skip_file(Path("docs/.archive/test.md"))
    assert should_skip_file(Path("docs/plans/.archive/implementation-plans/PLAN.md"))
    assert should_skip_file(Path("docs/specs/.archive/foo.md"))
    assert should_skip_file(Path("project/archives/old.md"))
    assert should_skip_file(Path("REMEDIATION_COMPLETE.md"))
    assert should_skip_file(Path("ANALYSIS_COMPLETE.md"))


def test_should_skip_file_special_files():
    """Test should_skip_file with special documentation files."""
    # Test special file patterns
    assert should_skip_file(Path("CHECKPOINT_2026-01-01.md"))
    assert should_skip_file(Path("CLEANUP_NEEDED.md"))
    assert should_skip_file(Path("COMPREHENSIVE_REVIEW.md"))
    assert should_skip_file(Path("PYPROJECT_LOCK.md"))
    assert should_skip_file(Path("TEST_RESULTS.md"))


def test_should_skip_file_regular_files(tmp_path):
    """Test should_skip_file with regular markdown files.

    Uses ``tmp_path`` so the file-content heuristic (production reads
    the first line and skips lines made entirely of underscores) is
    tested against content we control rather than whatever happens to
    live in the repo at test time.
    """
    regular = tmp_path / "regular.md"
    regular.write_text("# Heading\n\nSome content.\n")
    assert not should_skip_file(regular)
    assert not should_skip_file(tmp_path / "CHANGELOG.md")  # nonexistent → not skipped
    assert not should_skip_file(tmp_path / "README.md")
    assert not should_skip_file(tmp_path / "CONTRIBUTING.md")


def test_mdformat_no_files(monkeypatch):
    """Test mdformat_wrapper with no git-tracked files."""
    with patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files") as mock:
        mock.return_value = []
        result = main()
        assert result == 0, "Should return 0 when no files found"


def test_mdformat_all_files_skipped(monkeypatch):
    """Test mdformat_wrapper when all files are skipped."""
    with patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files") as mock:
        # Return files that should all be skipped — pattern matches
        # plus the per-area archive location.
        mock.return_value = [
            Path("ARCHIVE_COMPLETE.md"),
            Path("docs/plans/.archive/old.md"),
        ]
        result = main()
        assert result == 0, "Should return 0 when all files are skipped"


def test_mdformat_already_formatted(monkeypatch):
    """Test mdformat_wrapper when files are already formatted."""
    mock_file = Path("README.md")

    with patch(
        "crackerjack.tools.mdformat_wrapper.get_git_tracked_files"
    ) as mock_files:
        mock_files.return_value = [mock_file]

        with patch("subprocess.run") as mock_run:
            # Simulate files already formatted (check passes)
            mock_check = MagicMock()
            mock_check.returncode = 0
            mock_check.stderr = ""
            mock_run.return_value = mock_check

            result = main()
            assert result == 0, "Should return 0 when already formatted"
            # Should only run check, not format
            assert mock_run.call_count == 1
            assert "--check" in mock_run.call_args[0][0]


def test_mdformat_needs_formatting(monkeypatch):
    """Test mdformat_wrapper when files need formatting.

    The wrapper runs two subprocess calls in sequence when formatting
    is needed:

      1. ``mdformat --check`` — probes for needed changes (rc=1 ⇒ dirty).
      2. ``mdformat`` — applies the fix.

    The files that changed are named in the success message, which is
    required by ``crackerjack/executors/hook_executor.py`` for any
    ``is_formatting=True`` hook that exits 1.

    The wrapper decides whether to report a change by comparing each
    file's bytes before and after the run, so the format pass in this
    test has to actually write the file. A mock that only returns a
    return code looks to the wrapper exactly like a run that changed
    nothing.

    Earlier versions of this test ran a third subprocess call,
    ``git diff --name-only``, to list the changed files. That call
    reported every file that differed from HEAD — including files
    another session had edited and the formatter never touched — so
    the wrapper now names the files it changed itself.
    """
    mock_file = Path("README.md")
    original = mock_file.read_text(encoding="utf-8")

    with patch(
        "crackerjack.tools.mdformat_wrapper.get_git_tracked_files"
    ) as mock_files:
        mock_files.return_value = [mock_file]

        with patch("subprocess.run") as mock_run:
            mock_check = MagicMock()
            mock_check.returncode = 1  # Needs formatting
            mock_check.stdout = "Would format README.md"
            mock_check.stderr = ""

            def _format(cmd, *args, **kwargs):
                # mdformat would rewrite the file; the wrapper sees the
                # difference on disk afterwards.
                mock_file.write_text(original + "\n", encoding="utf-8")
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            mock_run.side_effect = [mock_check, _format]

            try:
                result = main()
                assert result == 1, "Should return 1 when formatting was applied"
                # Two subprocess invocations: check + format.
                assert mock_run.call_count == 2, (
                    f"expected 2 calls (check, format), got {mock_run.call_count}"
                )
                # First call must be the check.
                assert "--check" in mock_run.call_args_list[0].args[0]
                # Second call must NOT be the check (it's the format pass).
                assert "--check" not in mock_run.call_args_list[1].args[0]
            finally:
                mock_file.write_text(original, encoding="utf-8")


def test_mdformat_not_installed(monkeypatch):
    """Test mdformat_wrapper when mdformat is not installed."""
    mock_file = Path("README.md")

    with patch(
        "crackerjack.tools.mdformat_wrapper.get_git_tracked_files"
    ) as mock_files:
        mock_files.return_value = [mock_file]

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = main()
            assert result == 127, "Should return 127 when mdformat not found"


def test_mdformat_with_custom_args(monkeypatch):
    """Test mdformat_wrapper with custom command-line arguments."""
    mock_file = Path("README.md")

    with patch(
        "crackerjack.tools.mdformat_wrapper.get_git_tracked_files"
    ) as mock_files:
        mock_files.return_value = [mock_file]

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            # Pass custom arguments
            result = main(["--wrap", "80"])

            assert result == 0
            # Verify custom args were passed
            call_args = mock_run.call_args
            assert "--wrap" in call_args[0][0]
            assert "80" in call_args[0][0]


def test_mdformat_exception_handling(monkeypatch):
    """Test mdformat_wrapper handles unexpected exceptions."""
    mock_file = Path("README.md")

    with patch(
        "crackerjack.tools.mdformat_wrapper.get_git_tracked_files"
    ) as mock_files:
        mock_files.return_value = [mock_file]

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Unexpected error")

            result = main()
            assert result == 1, "Should return 1 on exception"
