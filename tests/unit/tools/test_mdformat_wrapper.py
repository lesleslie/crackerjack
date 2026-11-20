"""Tests for mdformat_wrapper tool."""

from pathlib import Path
from unittest.mock import Mock, patch

from crackerjack.tools.mdformat_wrapper import (
    _bom_frontmatter_documents,
    _build_mdformat_cmd,
    _frontmatter_documents,
    _frontmatter_extension_available,
    _frontmatter_extension_count,
    _multi_document_yaml_documents,
    _resolve_mdformat_bin,
    main,
    should_skip_file,
)


def _dispatcher(*results):
    """A subprocess.run side effect that returns each result in turn.

    A ``side_effect`` LIST returns its elements; it does not call them.
    So an element that has to act at call time -- a mock that writes
    the file mdformat would have written -- has to be reached through
    a dispatcher that calls it.
    """
    remaining = list(results)

    def _run(cmd, *args, **kwargs):
        result = remaining.pop(0)
        # A Mock is callable, so a plain `callable` check would CALL
        # the configured mock instead of returning it -- and a called
        # mock returns its auto-created return_value, whose attributes
        # are auto-created Mocks rather than the configured ones.
        if isinstance(result, Mock):
            return result
        if callable(result):
            return result(cmd, *args, **kwargs)
        return result

    return _run


def _writing_format(target: Path, formatted: str):
    """A subprocess.run side effect that formats the target file.

    The wrapper decides whether to report a change by comparing the
    file's bytes before and after the run. A mock that only returns a
    return code therefore looks to the wrapper exactly like a run that
    changed nothing -- which is a different behaviour, and a different
    result.
    """

    def _run(cmd, *args, **kwargs):
        target.write_text(formatted, encoding="utf-8")
        return Mock(returncode=0, stdout="", stderr="")

    return _run


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


class TestMultiDocumentYaml:
    """A ``.md`` file that is really multi-document YAML must not be formatted.

    The fleet has files that wear a ``.md`` extension but hold YAML:
    Claude Code slash-command definitions are a stream of ``---``-separated
    YAML documents. mdformat is a *markdown* formatter -- handed such a
    file it reads ``Run ... \\n---`` as a setext heading and turns each
    document separator into an ATX heading, so::

        ---
        description: Show jot inbox vitals
        allowed-tools: []
        ---

    becomes ``## description: Show jot inbox vitals allowed-tools: []``.

    That is not a formatting difference, it is a destroyed file. The
    discriminator is the *count* of YAML blocks: a markdown document
    with frontmatter has exactly one (its own opener), a multi-document
    YAML file has many.
    """

    def test_multi_document_yaml_file_is_skipped(self, tmp_path):
        """A slash-command style file is excluded from formatting."""
        command = tmp_path / "command.md"
        command.write_text(
            "---\n"
            "description: Show jot inbox vitals\n"
            "allowed-tools: []\n"
            "---\n"
            "\n"
            "Run `mahavishnu jot vitals` and display the output verbatim.\n"
            "---\n"
            "description: Create a new jot from text\n"
            "allowed-tools: []\n"
            "---\n"
            "\n"
            "Run `mahavishnu jot add {{text}}` and display the output verbatim.\n"
        )
        assert should_skip_file(command)

    def test_single_frontmatter_document_is_not_skipped(self, tmp_path):
        """One YAML block is frontmatter, not a YAML stream."""
        plan = tmp_path / "plan.md"
        plan.write_text("---\nstatus: draft\n---\n\n# Body\n")
        assert not should_skip_file(plan)

    def test_yaml_block_inside_a_fenced_code_block_does_not_count(self, tmp_path):
        """A ``---`` inside a fence is sample content, not a separator.

        This is the false-positive that a naive scan produces: the
        fleet's templates show YAML frontmatter inside a ```yaml fence,
        and counting those as document boundaries would exclude
        ordinary markdown templates from formatting.
        """
        template = tmp_path / "TEMPLATE.md"
        template.write_text(
            "---\n"
            "status: active\n"
            "---\n"
            "\n"
            "# Template\n"
            "\n"
            "Example:\n"
            "\n"
            "```yaml\n"
            "---\n"
            "title: <Human-readable title>\n"
            "audience: crackerjack maintainer\n"
            "---\n"
            "```\n"
        )
        assert not should_skip_file(template)

    def test_thematic_break_after_a_paragraph_is_not_a_yaml_boundary(self, tmp_path):
        """A ``---`` under prose is a setext heading, not a YAML block."""
        doc = tmp_path / "doc.md"
        doc.write_text("# Title\n\nSome prose.\n\n---\n\nMore prose.\n")
        assert not should_skip_file(doc)

    def test_multi_document_yaml_documents_finds_the_file(self, tmp_path):
        """The excluded files are reported, not skipped quietly."""
        command = tmp_path / "command.md"
        command.write_text(
            "---\n"
            "description: One\n"
            "allowed-tools: []\n"
            "---\n"
            "prose\n"
            "---\n"
            "description: Two\n"
            "allowed-tools: []\n"
            "---\n"
        )
        plan = tmp_path / "plan.md"
        plan.write_text("---\nstatus: draft\n---\n\n# Body\n")

        found = _multi_document_yaml_documents([command, plan])
        assert found == [command]


class TestGfmTableSafety:
    """mdformat must not change what a document reads as.

    mdformat's own safety net renders both sides of a comparison with
    its own parser, which has NO GFM table support -- a table is just a
    paragraph to it. So mdformat can merge a table's rows, or re-indent
    a table out of the list item that holds it, and pass its own check.
    The wrapper closes that gap by comparing the GFM rendering before
    and after, and restoring anything that reads differently.
    """

    def test_rendered_html_sees_a_table(self):
        """The comparison renderer must understand GFM tables."""
        from crackerjack.tools.mdformat_wrapper import _rendered_html

        html = _rendered_html("| a | b |\n|---|---|\n| 1 | 2 |\n")
        assert "<table>" in html
        assert "<td>1</td>" in html

    def test_rendered_html_ignores_frontmatter(self):
        """Frontmatter is not body text, and its round-trip is not a change.

        The frontmatter plugin re-serialises YAML through a ruamel
        round-trip, which changes the frontmatter's TEXT. That is not a
        change to the document, so the comparison must not see it as one.
        """
        from crackerjack.tools.mdformat_wrapper import _rendered_html

        before = "---\nstatus: null\n---\n\n# Body\n"
        after = "---\nstatus:\n---\n\n# Body\n"
        assert _rendered_html(before) == _rendered_html(after)

    def test_merged_table_rows_change_the_rendering(self):
        """A table whose rows merge reads differently -- and must be caught."""
        from crackerjack.tools.mdformat_wrapper import _rendering_changes

        table = (
            "| Symptom | Cause | Fix |\n|---|---|---|\n| `a` | b | c |\n| d | e | f |\n"
        )
        merged = (
            "| Symptom | Cause | Fix |\n|---|---|---|\n| `a` | b | c | | d | e | f |\n"
        )
        assert _rendering_changes(table, merged)

    def test_reflowed_paragraph_does_not_change_the_rendering(self):
        """Unwrapping a paragraph is formatting, not a change of meaning."""
        from crackerjack.tools.mdformat_wrapper import _rendering_changes

        before = "One paragraph that\nwraps across lines.\n"
        after = "One paragraph that wraps across lines.\n"
        assert not _rendering_changes(before, after)

    def test_refused_file_is_found_in_the_error_message(self):
        """mdformat names the file it refused; the path must be matched."""
        from crackerjack.tools.mdformat_wrapper import _refused_file

        target = Path("/tmp/doc.md")
        stderr = 'Error: Could not format\n"/tmp/doc.md".\n\nFormatted Markdown renders'
        assert _refused_file(stderr, [target]) == target

    def test_refused_file_returns_none_for_other_errors(self):
        """A failure that is not a file refusal must not be misread as one."""
        from crackerjack.tools.mdformat_wrapper import _refused_file

        stderr = "Error: something else went wrong\n"
        assert _refused_file(stderr, [Path("/tmp/doc.md")]) is None


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
        target.write_text("---\nstatus: draft\n---\n\n# Body  \n")
        mock_get_files.side_effect = lambda pattern: (
            [target] if pattern == "*.md" else []
        )

        mock_probe = Mock(stdout="1\n", stderr="", returncode=0)
        mock_check = Mock(returncode=1, stdout="", stderr="")
        mock_run.side_effect = _dispatcher(
            mock_probe,
            mock_check,
            _writing_format(target, "---\nstatus: draft\n---\n\n# Body\n"),
        )

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
        target = tmp_path / "README.md"
        target.write_text("# Body  \n")
        mock_get_files.side_effect = lambda pattern: (
            [target] if pattern == "*.md" else []
        )

        # Mock check fails (needs formatting)
        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""

        mock_run.side_effect = _dispatcher(
            mock_check, _writing_format(target, "# Body\n")
        )

        result = main()

        assert result == 1  # Returns 1 because files needed formatting
        assert target.read_text() == "# Body\n"

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
        """When mdformat auto-formats files, surface the change on stderr.

        The contract this pins: the silent-exit-1 path at the bottom of
        ``main()`` must name the files that changed so the next "1 issue"
        hook failure has substance. Prior to this fix the wrapper
        returned 1 without naming anything, which forced a manual
        ``git status`` dance every time.

        The names are the files THIS run changed. An earlier version ran
        ``git diff --name-only`` over them, which reports every file
        that differs from HEAD -- including files another session had
        edited and this run never touched.

        Each diagnostic line is prefixed with a success marker (``✓``) so
        that ``crackerjack.parsers.regex_parsers`` (regex parser) and
        ``crackerjack.utils.issue_detection`` (line-counting fallback)
        both treat the diagnostic as "passed" rather than as a tool issue.
        Without the prefix a 3-line diagnostic inflates to "3 issues" in
        the Fast Hook Results panel.
        """
        target = tmp_path / "README.md"
        target.write_text("# Body  \n")
        mock_get_files.side_effect = lambda pattern: (
            [target] if pattern == "*.md" else []
        )

        # check fails → needs_formatting
        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""

        mock_run.side_effect = _dispatcher(
            mock_check, _writing_format(target, "# Body\n")
        )

        result = main()
        captured = capsys.readouterr()

        assert result == 1
        # success-marker prefix is required so neither the regex
        # parser nor the line-counting safety net reports issues for
        # the diagnostic itself
        assert "✓ mdformat: PASSED" in captured.err
        assert "auto-formatted 1 file(s)" in captured.err
        assert f"✓   {target}" in captured.err
        # The ``files were modified by this hook`` literal is the
        # magic phrase ``crackerjack/executors/hook_executor.py:802``
        # checks for on ``is_formatting=True`` hooks with exit-code 1.
        # Without it the hook_executor routes exit-1 to status="failed"
        # instead of "passed".
        assert "files were modified by this hook" in captured.err, (
            "magic phrase missing — hook_executor will mark status=failed "
            "instead of passed for the silent auto-format path"
        )

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_excludes_a_file_mdformat_refuses(
        self,
        mock_run,
        mock_get_files,
        tmp_path,
        capsys,
    ):
        """A refused file must not stop the rest of the batch.

        mdformat aborts the whole invocation at the first file it
        cannot format. Left alone, that leaves the tree half
        formatted and the gate reporting the same failure on every
        run, so it never converges. The wrapper drops the refused file
        and re-runs, then reports it so the exclusion is visible.
        """
        refused = tmp_path / "refused.md"
        refused.write_text("# Body\n")
        formatted = tmp_path / "formatted.md"
        formatted.write_text("# Body  \n")
        # The two patterns are disjoint in production, so the mock
        # returns the documents for one and nothing for the other.
        mock_get_files.side_effect = lambda pattern: (
            [refused, formatted] if pattern == "*.md" else []
        )

        mock_check = Mock(returncode=1, stdout="", stderr="")

        def _run(cmd, *args, **kwargs):
            # First format call: mdformat refuses the first file and
            # aborts the batch.
            if str(refused) in cmd:
                return Mock(
                    returncode=1,
                    stdout="",
                    stderr=(
                        "Error: Could not format\n"
                        f'"{refused}".\n\n'
                        "Formatted Markdown renders to different HTML than "
                        "input Markdown."
                    ),
                )
            formatted.write_text("# Body\n", encoding="utf-8")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = _dispatcher(mock_check, _run, _run)

        result = main()
        captured = capsys.readouterr()

        assert result == 1
        # The refused file is reported, not silently dropped.
        assert "not formatted (mdformat refused)" in captured.err
        assert str(refused) in captured.err
        # The rest of the batch was still formatted.
        assert formatted.read_text() == "# Body\n"
        # The refused file was left alone.
        assert refused.read_text() == "# Body\n"

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
        target.write_text("# Body  \n")
        mock_get_files.side_effect = lambda pattern: (
            [target] if pattern == "*.md" else []
        )

        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""
        mock_run.side_effect = _dispatcher(
            mock_check, _writing_format(target, "# Body\n")
        )

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
        target.write_text("# Body  \n")
        mock_get_files.side_effect = lambda pattern: (
            [target] if pattern == "*.md" else []
        )

        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""
        mock_run.side_effect = _dispatcher(
            mock_check, _writing_format(target, "# Body\n")
        )

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
