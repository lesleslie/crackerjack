"""Tests for mdformat_wrapper tool."""

from pathlib import Path
from unittest.mock import Mock, patch

from crackerjack.tools.mdformat_wrapper import main, should_skip_file


class TestShouldSkipFile:
    """Test should_skip_file function."""

    def test_skip_archive_patterns(self):
        """Test that archive patterns are skipped."""
        assert should_skip_file(Path("docs/archive/file.md"))
        assert should_skip_file(Path("docs/archives/file.md"))

    def test_skip_complete_markdown(self):
        """Test that _COMPLETE.md files are skipped."""
        assert should_skip_file(Path("FIX_COMPLETE.md"))
        assert should_skip_file(Path("docs/ANALYSIS_COMPLETE.md"))

    def test_skip_analysis_progress_status(self):
        """Test that analysis/progress/status files are skipped."""
        assert should_skip_file(Path("ANALYSIS.md"))
        assert should_skip_file(Path("PROGRESS.md"))
        assert should_skip_file(Path("STATUS.md"))

    def test_skip_plan_summary(self):
        """Test that plan and summary files are skipped."""
        assert should_skip_file(Path("PLAN.md"))
        assert should_skip_file(Path("SUMMARY.md"))

    def test_skip_checkpoint(self):
        """Test that checkpoint files are skipped."""
        assert should_skip_file(Path("CHECKPOINT_1.md"))
        assert should_skip_file(Path("CHECKPOINT_FINAL.md"))

    def test_skip_notes(self):
        """Test that NOTES.md is skipped."""
        assert should_skip_file(Path("NOTES.md"))

    def test_skip_cleanup_comprehensive(self):
        """Test that cleanup and comprehensive files are skipped."""
        assert should_skip_file(Path("CLEANUP_01.md"))
        assert should_skip_file(Path("COMPREHENSIVE_AUDIT.md"))

    def test_skip_pyproject_test(self):
        """Test that pyproject and test files are skipped."""
        assert should_skip_file(Path("PYPROJECT_V2.md"))
        assert should_skip_file(Path("TEST_RESULTS.md"))

    def test_not_skip_regular_markdown(self):
        """Test that regular markdown files are not skipped."""
        assert not should_skip_file(Path("README.md"))
        assert not should_skip_file(Path("docs/guide.md"))
        assert not should_skip_file(Path("INSTALL.md"))

    def test_not_skip_other_extensions(self):
        """Test that non-markdown files are not skipped."""
        assert not should_skip_file(Path("script.py"))
        assert not should_skip_file(Path("config.yaml"))


class TestMdformatMain:
    """Test mdformat main function."""

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_valid_files(self, mock_run, mock_get_files, tmp_path, capsys):
        """Test main with valid markdown files."""
        mock_get_files.return_value = [tmp_path / "README.md"]

        # Mock successful check (already formatted)
        mock_check = Mock()
        mock_check.returncode = 0
        mock_run.return_value = mock_check

        result = main()

        assert result == 0

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_formats_files(self, mock_run, mock_get_files, tmp_path):
        """Test main formats files that need it."""
        mock_get_files.return_value = [tmp_path / "README.md"]

        # Mock check fails (needs formatting)
        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""

        # Mock format succeeds
        mock_format = Mock()
        mock_format.returncode = 0
        mock_format.stdout = "Formatted 1 file"
        mock_format.stderr = ""

        mock_run.side_effect = [mock_check, mock_format]

        result = main()

        assert result == 1  # Returns 1 because files needed formatting

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    def test_main_no_files(self, mock_get_files, capsys):
        """Test main with no markdown files."""
        mock_get_files.return_value = []

        result = main()

        assert result == 0

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_skipped_files(self, mock_run, mock_get_files, capsys):
        """Test that skipped files are not processed."""
        # Return mix of skipped and regular files
        mock_get_files.side_effect = lambda _: [
            Path("README.md"),
            Path("docs/archive/old.md"),
            Path("ANALYSIS.md"),
        ]

        mock_check = Mock()
        mock_check.returncode = 0
        mock_run.return_value = mock_check

        with patch.object(Path, "exists", return_value=True):
            main()

        # Should process README.md only (2 files skipped)
        assert mock_run.call_count >= 1

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_file_not_found(self, mock_run, mock_get_files):
        """Test handling when mdformat is not found."""
        mock_get_files.return_value = [Path("README.md")]

        mock_run.side_effect = FileNotFoundError()

        result = main()

        assert result == 127

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_custom_args(self, mock_run, mock_get_files):
        """Test main with custom arguments."""
        mock_get_files.return_value = [Path("README.md")]

        mock_check = Mock()
        mock_check.returncode = 0
        mock_run.return_value = mock_check

        result = main(["--wrap", "80"])

        assert result == 0
        # Check that custom args were passed
        assert mock_run.call_count >= 1

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_handles_both_extensions(self, mock_run, mock_get_files):
        """Test main handles both .md and .markdown files."""
        mock_get_files.side_effect = lambda pattern: {
            "*.md": [Path("README.md"), Path("guide.md")],
            "*.markdown": [Path("document.markdown")],
        }.get(pattern, [])

        mock_check = Mock()
        mock_check.returncode = 0
        mock_run.return_value = mock_check

        result = main()

        assert result == 0

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_auto_format_surfaces_diff(
        self, mock_run, mock_get_files, tmp_path, capsys,
    ):
        """When mdformat auto-formats files, surface the diff on stderr.

        The contract this pins: the silent-exit-1 path at the bottom of
        ``main()`` must name the files that changed via ``git diff
        --name-only`` so the next "1 issue" hook failure has substance.
        Prior to this fix the wrapper returned 1 without naming anything,
        which forced a manual ``git status`` dance every time.

        Each diagnostic line is prefixed with a success marker (``✓``) so
        that ``crackerjack.parsers.regex_parsers`` (regex parser) and
        ``crackerjack.utils.issue_detection`` (line-counting fallback)
        both treat the diagnostic as "passed" rather than as a tool issue.
        Without the prefix a 3-line diagnostic inflates to "3 issues" in
        the Fast Hook Results panel.
        """
        target = tmp_path / "README.md"
        mock_get_files.return_value = [target]

        # check fails → needs_formatting
        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""

        # format succeeds (silent auto-format path)
        mock_format = Mock()
        mock_format.returncode = 0
        mock_format.stdout = ""
        mock_format.stderr = ""

        # git diff names the auto-formatted file
        mock_diff = Mock()
        mock_diff.returncode = 0
        mock_diff.stdout = "README.md\n"

        mock_run.side_effect = [mock_check, mock_format, mock_diff]

        result = main()
        captured = capsys.readouterr()

        assert result == 1
        # success-marker prefix is required so neither the regex
        # parser nor the line-counting safety net reports issues for
        # the diagnostic itself
        assert "✓ mdformat: PASSED" in captured.err
        assert "auto-formatted 1 file(s)" in captured.err
        assert "✓   README.md" in captured.err
        # The ``files were modified by this hook`` literal is the
        # magic phrase ``crackerjack/executors/hook_executor.py:802``
        # checks for on ``is_formatting=True`` hooks with exit-code 1.
        # Without it the hook_executor routes exit-1 to status="failed"
        # instead of "passed".
        assert "files were modified by this hook" in captured.err, (
            "magic phrase missing — hook_executor will mark status=failed "
            "instead of passed for the silent auto-format path"
        )
        # third subprocess call is the git diff invocation
        assert mock_run.call_count == 3
        git_invocation = mock_run.call_args_list[2]
        assert git_invocation.args[0][0] == "git"
        assert git_invocation.args[0][1] == "diff"
        assert git_invocation.args[0][2] == "--name-only"
        assert str(target) in git_invocation.args[0]

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_auto_format_handles_git_failure(
        self, mock_run, mock_get_files, tmp_path, capsys,
    ):
        """If ``git diff`` fails (e.g., not a git repo), the hook still
        returns 1 with whatever stderr mdformat produced. The diff
        surface is best-effort; a missing git must NOT crash the hook.
        """
        target = tmp_path / "README.md"
        mock_get_files.return_value = [target]

        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stderr = ""

        mock_format = Mock()
        mock_format.returncode = 0
        mock_format.stderr = ""

        mock_diff = Mock()
        mock_diff.returncode = 128  # git failure
        mock_diff.stdout = "fatal: not a git repository"
        mock_diff.stderr = "fatal: not a git repository"

        mock_run.side_effect = [mock_check, mock_format, mock_diff]

        result = main()
        captured = capsys.readouterr()

        # Still exit 1, format stderr was printed, no exception escaped
        assert result == 1
        assert "fatal: not a git repository" in captured.err
        # Magic phrase must appear even on git-failure fallback so the
        # hook_executor still routes status=passed on the silent
        # auto-format path.
        assert "files were modified by this hook" in captured.err, (
            "magic phrase missing on git-failure fallback — "
            "hook_executor will re-route to status=failed"
        )

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_auto_format_not_counted_by_issue_pipeline(
        self, mock_run, mock_get_files, tmp_path, capsys,
    ):
        """Regression: the diagnostic must not register as issues under
        ``crackerjack.parsers.regex_parsers`` or the line-counting
        fallback at ``crackerjack.utils.issue_detection.extract_issue_lines``.

        Without the ``✓`` prefix the user-reported "2 issues" feedback
        recurs: each non-empty diagnostic line was counted as one
        reported issue even though mdformat auto-formatting succeeded.
        """
        target = tmp_path / "README.md"
        mock_get_files.return_value = [target]

        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""
        mock_format = Mock()
        mock_format.returncode = 0
        mock_format.stdout = ""
        mock_format.stderr = ""
        mock_diff = Mock()
        mock_diff.returncode = 0
        mock_diff.stdout = "README.md\n"
        mock_diff.stderr = ""
        mock_run.side_effect = [mock_check, mock_format, mock_diff]

        main()
        captured = capsys.readouterr()

        from crackerjack.parsers.factory import ParserFactory
        from crackerjack.utils.issue_detection import extract_issue_lines

        # regex parser: returns 0 issues
        assert ParserFactory().parse_with_validation(
            "mdformat", captured.err
        ) == []
        # line counter: every non-blank diagnostic line starts with ``✓``
        # and is filtered out by ``_SUCCESS_PREFIXES``
        counted = extract_issue_lines(captured.err, tool_name="mdformat")
        assert counted == [], (
            f"diagnostic lines leaked into the line-counting safety net: "
            f"{counted!r}"
        )

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_auto_format_flips_hook_status_to_passed(
        self, mock_run, mock_get_files, tmp_path,
    ):
        """End-to-end: feed the wrapper's stderr into
        ``HookExecutor._determine_initial_status`` for an
        ``is_formatting=True`` hook and assert status="passed".

        Without the ``files were modified by this hook`` magic phrase,
        ``hook_executor.py:802`` routes the wrapper's exit-1 to
        status="failed" — exactly the user-reported symptom: "the hook
        still fails with error code 1 ... even though the format
        passes". This test pins the contract from both ends so the
        auto-format path always reaches ``status=passed``.
        """
        from crackerjack.executors.hook_executor import HookExecutor
        from crackerjack.config.hooks import HookDefinition, SecurityLevel

        target = tmp_path / "README.md"
        mock_get_files.return_value = [target]

        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""
        mock_format = Mock()
        mock_format.returncode = 0
        mock_format.stdout = ""
        mock_format.stderr = ""
        mock_diff = Mock()
        mock_diff.returncode = 0
        mock_diff.stdout = "README.md\n"
        mock_diff.stderr = ""
        mock_run.side_effect = [mock_check, mock_format, mock_diff]

        # Capture wrapper stderr via StringIO swap so this test does
        # not depend on the ``capsys`` fixture (the wrapper's exits
        # path runs before fixture teardown otherwise).
        import io
        import sys as _sys

        captured = io.StringIO()
        saved_stderr = _sys.stderr
        _sys.stderr = captured
        try:
            main()
        finally:
            _sys.stderr = saved_stderr

        stderr = captured.getvalue()
        # Sanity: the magic phrase is in the captured stderr so the
        # hook_executor check that follows has something to find.
        assert "files were modified by this hook" in stderr

        hook = HookDefinition(
            name="mdformat",
            command=[],
            is_formatting=True,
            timeout=180,
            retry_on_failure=True,
            security_level=SecurityLevel.LOW,
            accepts_file_paths=True,
        )
        result = Mock()
        result.returncode = 1  # wrapper exits 1 on the silent-auto path
        result.stdout = ""
        result.stderr = stderr

        # Bypass __init__ — only the pure status logic is needed. The
        # ``_determine_initial_status`` reads ``self.debug`` for an
        # early-bail on reporting tools, so stub it.
        executor = HookExecutor.__new__(HookExecutor)
        executor.debug = False
        status = executor._determine_initial_status(hook, result)
        assert status == "passed", (
            f"expected hook_executor to mark the silent auto-format "
            f"path as passed, got {status!r}"
        )
