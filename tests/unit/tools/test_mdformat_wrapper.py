"""Tests for mdformat_wrapper tool."""

from pathlib import Path
from unittest.mock import Mock, patch

from crackerjack.tools.mdformat_wrapper import (
    _bom_frontmatter_documents,
    _build_mdformat_cmd,
    _frontmatter_documents,
    _frontmatter_extension_available,
    _frontmatter_extension_count,
    _resolve_mdformat_bin,
    main,
    should_skip_file,
)


class TestShouldSkipFile:
    """Test should_skip_file function."""

    def test_skip_archive_patterns(self):
        """Test that per-area archive patterns are skipped."""
        # Per-area archives (`docs/.archive/`, `docs/plans/.archive/`, …)
        # and the rare plural variant should all be skipped. The legacy
        # `docs/archive/` location is intentionally unsupported — the
        # archive stage now writes to per-area `.archive/` directories.
        assert should_skip_file(Path("docs/.archive/file.md"))
        assert should_skip_file(Path("docs/plans/.archive/file.md"))
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

    def test_frontmatter_documents_are_not_skipped(self, tmp_path):
        """Frontmatter documents are now IN scope for the formatter.

        The skip existed because mdformat 1.0.0 core destroys YAML
        frontmatter, so a document whose first line is ``---`` was
        excluded rather than mangled. The ``mdformat-frontmatter``
        plugin re-serialises the block through a ruamel round-trip
        that preserves quotes, comments and key order, so the parsed
        values survive and the exclusion is no longer needed. Lifting
        it is the point of the change: a plan whose frontmatter still
        parses still reaches the plan index.

        The rule keys off the file's FIRST LINE, so the file has to
        exist for it to apply.
        """
        plan = tmp_path / "plan.md"
        plan.write_text("---\nstatus: draft\n---\n\n# Body\n")
        assert not should_skip_file(plan)

        readme = tmp_path / "README.md"
        readme.write_text("# Body\n")
        assert not should_skip_file(readme)

    def test_underscore_rule_still_skips(self, tmp_path):
        """The underscore clause is a different rule about a different
        thing, and it stays.

        Only the ``---`` clause was lifted. A document whose first line
        is a run of underscores is still excluded, because that rule is
        not about YAML frontmatter.
        """
        underline = tmp_path / "doc.md"
        underline.write_text("___\n\n# Body\n")
        assert should_skip_file(underline)

    def test_underscore_rule_needs_three_characters(self, tmp_path):
        """Two underscores is not a rule; three is.

        The clause is ``len(stripped) >= 3``, so a run of two
        underscores falls through and the document is formatted.
        """
        two = tmp_path / "two.md"
        two.write_text("__\n\n# Body\n")
        assert not should_skip_file(two)

    def test_bom_frontmatter_document_is_skipped(self, tmp_path):
        """A BOM'd frontmatter document is excluded, not mangled.

        The plugin's own front-matter rule is BOM-blind, so formatting
        such a document would flatten its frontmatter into a heading and
        drop the document out of the plan index -- the exact failure the
        guard exists to prevent. A byte-order mark is also not
        whitespace, so ``"﻿".strip()`` keeps it and the fence
        test would never match.
        """
        bom_plan = tmp_path / "bomplan.md"
        bom_plan.write_text("﻿---\nstatus: draft\n---\n\n# Body\n", encoding="utf-8")
        assert should_skip_file(bom_plan)

        plain = tmp_path / "plain.md"
        plain.write_text("---\nstatus: draft\n---\n\n# Body\n", encoding="utf-8")
        assert not should_skip_file(plain)


class TestFrontmatterSafety:
    """The formatter must not destroy YAML frontmatter.

    mdformat 1.0.0 core has no frontmatter support: it rewrites the
    ``---`` fence into a horizontal rule and flattens the YAML into
    body text. A mangled plan can then fail extraction and vanish from
    ``PLAN_INDEX.md``.
    """

    def test_resolve_mdformat_bin_prefers_repo_venv(self):
        """The repo's own venv binary wins over whatever is on PATH."""
        with patch.object(Path, "exists", return_value=True):
            resolved = _resolve_mdformat_bin()
        assert resolved.endswith(".venv/bin/mdformat")

    def test_build_cmd_passes_number_and_names_no_extension(self):
        """Two flags, both load-bearing.

        ``--number`` preserves the source numbering of ordered lists.
        mdformat's default renders every ordered-list item with the
        marker ``1.``, so a list written ``3. 4.`` becomes ``3. 1.`` and
        any prose pointing at "item 4" points at nothing. The number is
        often a reference, not decoration.

        The wrapper names NO extension. ``mdformat --extensions
        frontmatter`` RESTRICTS the enabled set -- verified against
        mdformat-gfm, whose ``tables`` extension stopped formatting
        tables. The CLI enables all installed extensions by default.
        """
        cmd = _build_mdformat_cmd([Path("README.md")], None)
        assert "--number" in cmd
        # Position matters. mdformat's paths are a ``nargs="*"``
        # positional, so a flag after the file list would be read as a
        # path rather than as a flag.
        assert cmd.index("--number") < cmd.index("README.md")
        assert "--extensions" not in cmd
        assert "--no-codeformatters" in cmd

    def test_extension_available_when_probe_reports_one(self):
        """A probe printing 1 means exactly one front-matter extension."""
        with patch("crackerjack.tools.mdformat_wrapper.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="1\n", stderr="", returncode=0)
            assert _frontmatter_extension_available("/tmp/x/mdformat") is True

    def test_extension_unavailable_when_probe_reports_zero(self):
        """A probe printing 0 means the plugin is missing."""
        with patch("crackerjack.tools.mdformat_wrapper.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="0\n", stderr="", returncode=0)
            assert _frontmatter_extension_available("/tmp/x/mdformat") is False

    def test_extension_unavailable_when_two_are_installed(self):
        """Two front-matter extensions is not "available" either.

        ``mdformat-frontmatter`` registers as ``frontmatter`` and
        ``mdformat-front-matters`` as ``front_matters``, so pip lets
        both be installed side by side. mdformat then logs a plugin
        conflict and silently keeps one renderer -- and the two packages
        behave oppositely on the same input. Exactly one is the only
        safe state.
        """
        with patch("crackerjack.tools.mdformat_wrapper.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="2\n", stderr="", returncode=0)
            assert _frontmatter_extension_available("/tmp/x/mdformat") is False

    def test_extension_unavailable_when_probe_crashes(self):
        """A probe that cannot run must not be read as available."""
        with patch(
            "crackerjack.tools.mdformat_wrapper.subprocess.run",
            side_effect=OSError("boom"),
        ):
            assert _frontmatter_extension_available("/tmp/x/mdformat") is False

    def test_extension_count_is_none_when_the_probe_crashes(self):
        """A probe that cannot run reports no count at all."""
        with patch(
            "crackerjack.tools.mdformat_wrapper.subprocess.run",
            side_effect=OSError("boom"),
        ):
            assert _frontmatter_extension_count("/tmp/x/mdformat") is None

    def test_extension_count_is_none_when_the_probe_prints_nonsense(self):
        """Unparseable probe output is no count at all."""
        with patch("crackerjack.tools.mdformat_wrapper.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                stdout="not a number\n", stderr="", returncode=0
            )
            assert _frontmatter_extension_count("/tmp/x/mdformat") is None

    def test_bom_frontmatter_documents_detects_the_bom(self, tmp_path):
        """Only a BOM'd frontmatter document is detected."""
        bom_plan = tmp_path / "bomplan.md"
        bom_plan.write_text("﻿---\nstatus: draft\n---\n\n# Body\n", encoding="utf-8")
        plain = tmp_path / "plain.md"
        plain.write_text("---\nstatus: draft\n---\n\n# Body\n", encoding="utf-8")

        assert _bom_frontmatter_documents([bom_plan, plain]) == [bom_plan]

    def test_frontmatter_documents_detects_the_fence(self, tmp_path):
        """Only files whose FIRST line opens a YAML block are detected."""
        with_frontmatter = tmp_path / "plan.md"
        with_frontmatter.write_text("---\nstatus: draft\n---\n\n# Body\n")
        without = tmp_path / "readme.md"
        without.write_text("# Body\n")

        found = _frontmatter_documents([with_frontmatter, without])
        assert found == [with_frontmatter]

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.mdformat_wrapper.subprocess.run")
    def test_main_fails_loud_when_extension_is_missing(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
        capsys,
    ):
        """A tracked frontmatter document with no plugin must stop the run.

        Silently formatting it would destroy the frontmatter, which is
        how a plan ends up missing from the plan index.

        The guard scans every tracked document, not only the ones in
        scope. The skip list still excludes documents by other rules
        (archive paths, ``*PLAN.md``), and the guard asserts the safety
        property over the whole tracked tree rather than only over what
        this particular run would format.
        """
        target = tmp_path / "plan.md"
        target.write_text("---\nstatus: draft\n---\n\n# Body\n")
        mock_get_files.return_value = [target]

        mock_run.return_value = Mock(stdout="0\n", stderr="", returncode=0)

        result = main()
        captured = capsys.readouterr()

        assert result == 1
        assert "frontmatter" in captured.err
        assert "uv sync --all-groups" in captured.err

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.mdformat_wrapper.subprocess.run")
    def test_main_proceeds_when_the_extension_is_installed(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
    ):
        """A tracked frontmatter document is safe when the plugin exists."""
        target = tmp_path / "plan.md"
        target.write_text("---\nstatus: draft\n---\n\n# Body\n")
        # The two patterns are disjoint in production, so the mock
        # returns the document for one and nothing for the other. A
        # single ``return_value`` would put every document in the list
        # twice, which production never does.
        mock_get_files.side_effect = lambda pattern: (
            [target] if pattern == "*.md" else []
        )

        mock_probe = Mock(stdout="1\n", stderr="", returncode=0)
        mock_check = Mock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = [mock_probe, mock_check]

        assert main() == 0
        # the preflight actually ran: the first subprocess call is the
        # extension probe, not the formatter's --check
        probe_call = mock_run.call_args_list[0].args[0]
        assert "-c" in probe_call
        assert any("mdformat.parser_extension" in str(part) for part in probe_call)

        # The frontmatter document reached mdformat. Before the skip was
        # lifted, the "nothing to do" short-circuit returned before any
        # formatter call, so this assertion is what proves the document
        # is in scope now rather than merely tolerated.
        assert len(mock_run.call_args_list) == 2, (
            "expected the formatter to be invoked on the frontmatter "
            "document; it was skipped"
        )
        formatter_call = mock_run.call_args_list[1].args[0]
        assert "--number" in formatter_call
        assert str(target) in formatter_call

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.mdformat_wrapper.subprocess.run")
    def test_main_fails_loud_when_two_frontmatter_extensions_are_installed(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
        capsys,
    ):
        """Two front-matter extensions must stop the run.

        The two packages register under different entry-point names, so
        pip installs both without complaint. mdformat then logs a plugin
        conflict and keeps one renderer, and the packages behave
        oppositely on the same input -- one preserves quotes, the other
        strips them, which turns a quoted "yes" into a YAML 1.1 boolean.
        That is a silent semantic change to frontmatter, so the guard
        has to fail loudly rather than let it happen.
        """
        target = tmp_path / "plan.md"
        target.write_text("---\nstatus: draft\n---\n\n# Body\n")
        mock_get_files.return_value = [target]

        mock_run.return_value = Mock(stdout="2\n", stderr="", returncode=0)

        result = main()
        captured = capsys.readouterr()

        assert result == 1
        assert "2" in captured.err
        assert "frontmatter" in captured.err

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.mdformat_wrapper.subprocess.run")
    def test_main_surfaces_mdformat_stderr_on_the_clean_path(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
        capsys,
    ):
        """mdformat's own warnings must not be swallowed.

        The wrapper used to discard ``check_result.stderr`` entirely
        when the check passed, so a front-matter block mdformat could
        not parse -- or a plugin conflict -- was invisible. The
        diagnostic is prefixed with the success marker so it reaches the
        operator without being counted as an issue by the regex parser
        or the line-counting safety net.
        """
        target = tmp_path / "plan.md"
        target.write_text("---\nstatus: draft\n---\n\n# Body\n")
        mock_get_files.return_value = [target]

        mock_probe = Mock(stdout="1\n", stderr="", returncode=0)
        mock_check = Mock(
            returncode=0,
            stdout="",
            stderr="Warning: Invalid YAML in a front matter block: boom.\n",
        )
        mock_run.side_effect = [mock_probe, mock_check]

        assert main() == 0
        captured = capsys.readouterr()

        assert "Invalid YAML" in captured.err
        assert captured.err.strip().startswith("✓")

        from crackerjack.parsers.factory import ParserFactory
        from crackerjack.utils.issue_detection import extract_issue_lines

        assert ParserFactory().parse_with_validation("mdformat", captured.err) == []
        assert extract_issue_lines(captured.err, tool_name="mdformat") == []

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.mdformat_wrapper.subprocess.run")
    def test_main_reports_bom_frontmatter_documents(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
        capsys,
    ):
        """A BOM'd frontmatter document is reported, not silently skipped.

        It is excluded from formatting because the plugin's front-matter
        rule is BOM-blind, and excluded documents are the ones nobody
        notices. Saying so is the difference between a visible
        condition and a plan that quietly stops being formatted.
        """
        bom_plan = tmp_path / "bomplan.md"
        bom_plan.write_text("﻿---\nstatus: draft\n---\n\n# Body\n", encoding="utf-8")
        mock_get_files.return_value = [bom_plan]

        mock_probe = Mock(stdout="1\n", stderr="", returncode=0)
        mock_check = Mock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = [mock_probe, mock_check]

        assert main() == 0
        captured = capsys.readouterr()

        assert "byte-order mark" in captured.err
        assert "bomplan.md" in captured.err

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.mdformat_wrapper.subprocess.run")
    def test_format_invocation_carries_number(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
    ):
        """The FORMAT command carries --number, not only the check.

        The check command is what most assertions look at, so a
        regression that dropped the flag from the format path would
        pass every other test in this file.
        """
        target = tmp_path / "plan.md"
        target.write_text("---\nstatus: draft\n---\n\n# Body\n")
        mock_get_files.side_effect = lambda pattern: (
            [target] if pattern == "*.md" else []
        )

        mock_probe = Mock(stdout="1\n", stderr="", returncode=0)
        mock_check = Mock(returncode=1, stdout="", stderr="")
        mock_format = Mock(returncode=0, stdout="", stderr="")
        mock_diff = Mock(returncode=0, stdout="plan.md\n", stderr="")
        mock_run.side_effect = [mock_probe, mock_check, mock_format, mock_diff]

        assert main() == 1

        format_cmd = mock_run.call_args_list[2].args[0]
        assert "--number" in format_cmd
        assert "--check" not in format_cmd
        assert format_cmd.index("--number") < format_cmd.index(str(target))

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.mdformat_wrapper.subprocess.run")
    def test_main_proceeds_when_no_frontmatter_is_tracked(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
    ):
        """No frontmatter anywhere means the missing plugin is irrelevant."""
        target = tmp_path / "README.md"
        target.write_text("# Body\n")
        mock_get_files.return_value = [target]

        mock_check = Mock()
        mock_check.returncode = 0
        mock_check.stderr = ""
        mock_run.return_value = mock_check

        assert main() == 0


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
        mock_check.stderr = ""
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
            Path("docs/plans/.archive/old.md"),
            Path("ANALYSIS.md"),
        ]

        mock_check = Mock()
        mock_check.returncode = 0
        mock_check.stderr = ""
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
        mock_check.stderr = ""
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
        mock_check.stderr = ""
        mock_run.return_value = mock_check

        result = main()

        assert result == 0

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_auto_format_surfaces_diff(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
        capsys,
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
        self,
        mock_run,
        mock_get_files,
        tmp_path,
        capsys,
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
        self,
        mock_run,
        mock_get_files,
        tmp_path,
        capsys,
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
        assert ParserFactory().parse_with_validation("mdformat", captured.err) == []
        # line counter: every non-blank diagnostic line starts with ``✓``
        # and is filtered out by ``_SUCCESS_PREFIXES``
        counted = extract_issue_lines(captured.err, tool_name="mdformat")
        assert counted == [], (
            f"diagnostic lines leaked into the line-counting safety net: {counted!r}"
        )

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_auto_format_flips_hook_status_to_passed(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
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
        from crackerjack.config.hooks import HookDefinition, SecurityLevel
        from crackerjack.executors.hook_executor import HookExecutor

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
