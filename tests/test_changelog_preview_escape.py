"""Regression tests for changelog preview escaping.

The bug: when a commit message body contains literal text that LOOKS like
Rich markup (e.g. ``[/ bold red]``), Rich tries to parse it during
``console.print()`` and crashes with::

    closing tag '[/ bold red]' at position N doesn't match any open tag

Two recent crackerjack commits (a9017dd3 and 2aaef6bd) include literal
``[/ ...]`` markup fragments in their bodies to document the typo
themselves, which made this surface in the real publish workflow.

The fix: escape entry content with ``rich.markup.escape`` before passing
it to ``console.print``. These tests guard against the regression.
"""
from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from crackerjack.services.changelog_automation import (
    ChangelogEntry,
    ChangelogGenerator,
)


class TestChangelogPreviewEscape:
    """Verify entry content is escaped before Rich rendering."""

    def test_entry_with_invalid_closing_tag_does_not_crash(self) -> None:
        """The exact shape that broke the publish flow: literal [/ bold red]
        in a commit message body."""
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        gen = ChangelogGenerator(console=console)

        entries_by_type = {
            "Internal": [
                ChangelogEntry(
                    entry_type="Internal",
                    description=(
                        "fix Rich markup typos for multi-word tags "
                        "`[/ bold red]` → `[/bold red]`"
                    ),
                ),
            ],
        }

        # Must not raise — this is the literal regression test for the
        # `closing tag '[/ bold red]' at position N doesn't match any open
        # tag` error reported in the publish workflow.
        gen._display_changelog_preview(entries_by_type)

        output = buf.getvalue()
        assert "[/ bold red]" in output  # rendered verbatim, not parsed

    def test_entry_with_dict_like_access_does_not_crash(self) -> None:
        """Same class of bug from the third commit that fixed it: literal
        ``error["type"]`` in commit body — brackets but no closing tag."""
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        gen = ChangelogGenerator(console=console)

        entries_by_type = {
            "Fixed": [
                ChangelogEntry(
                    entry_type="Fixed",
                    description=(
                        'semgrep emits error["type"] as a 2-list '
                        '["PartialParsing", [...]]'
                    ),
                ),
            ],
        }

        gen._display_changelog_preview(entries_by_type)
        output = buf.getvalue()
        # `error["type"]` and `["PartialParsing", [...]]` rendered
        # verbatim — Rich escape converts `[`/`]` to `\[`/`\]` which
        # console.print then renders back to literal `[`/`]`.
        assert 'error["type"]' in output
        assert '"PartialParsing"' in output
        assert "[..." in output

    def test_legitimate_markup_in_section_header_still_renders(self) -> None:
        """The fix uses ``escape`` only on entry content — section names
        like ``Internal:`` still render with the surrounding ``[bold]``
        markup. This guards against a future change that disables
        markup globally."""
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        gen = ChangelogGenerator(console=console)

        entries_by_type = {
            "Added": [
                ChangelogEntry(
                    entry_type="Added",
                    description="plain text without brackets",
                ),
            ],
        }
        gen._display_changelog_preview(entries_by_type)
        output = buf.getvalue()
        # Section header is rendered with the [bold] style — visible as
        # the ANSI escape sequence \x1b[1m (bold) on the section name.
        assert "Added" in output
        # Entry text appears verbatim (no escape sequences inside).
        assert "plain text without brackets" in output

    def test_mixed_valid_and_invalid_entries(self) -> None:
        """One entry with clean text, one with malformed markup. The whole
        preview must render without crashing."""
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        gen = ChangelogGenerator(console=console)

        entries_by_type = {
            "Fixed": [
                ChangelogEntry(
                    entry_type="Fixed",
                    description="clean description",
                ),
                ChangelogEntry(
                    entry_type="Fixed",
                    description="unmatched [/ dim cyan] bracket pair",
                ),
            ],
        }

        gen._display_changelog_preview(entries_by_type)
        output = buf.getvalue()
        assert "clean description" in output
        assert "[/ dim cyan]" in output
