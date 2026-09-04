"""Tests for changelog_automation.BREAKING CHANGE detection.

These tests target the false-positive class where any commit body that
mentions the phrase "BREAKING CHANGE:" in passing (citing prior releases,
documenting history, negation) was flagged as a real breaking change.

The regex must anchor the phrase at the start of a body line and accept
common conventional-commit prefixes (e.g. `# BREAKING CHANGE:`).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crackerjack.services.changelog_automation import ChangelogGenerator


def _make_generator() -> ChangelogGenerator:
    return ChangelogGenerator(git_service=MagicMock())


def _parse(header: str, body: str) -> bool:
    """Parse a commit message and return whether it was flagged breaking."""
    gen = _make_generator()
    msg = header if not body else f"{header}\n\n{body}"
    entry = gen.parse_commit_message(msg)
    assert entry is not None, f"parse_commit_message returned None for {msg!r}"
    return entry.breaking_change


@pytest.mark.unit
class TestBreakingChangeFalsePositives:
    """Commit bodies mentioning BREAKING CHANGE in passing must NOT be flagged."""

    def test_supersedes_phrase_not_breaking(self) -> None:
        """'supersedes BREAKING CHANGE: ...' is history, not a new breaking change."""
        assert (
            _parse(
                "fix: handle edge case",
                "Note: this supersedes BREAKING CHANGE: behavior in v0.5",
            )
            is False
        )

    def test_documents_phrase_not_breaking(self) -> None:
        """'Documents BREAKING CHANGE: ...' describes prior PRs, not new breaks."""
        assert (
            _parse(
                "docs: update README",
                "Documents BREAKING CHANGE: policy from earlier PR (already merged).",
            )
            is False
        )

    def test_mentions_phrase_not_breaking(self) -> None:
        """'Mentions BREAKING CHANGE roadmap.' is forward-looking, not a break."""
        assert (
            _parse(
                "refactor: cleanup imports",
                "No actual API change. Mentions BREAKING CHANGE roadmap.",
            )
            is False
        )

    def test_changelog_reference_not_breaking(self) -> None:
        """Mid-sentence reference in CHANGELOG is not a new breaking change."""
        assert (
            _parse(
                "chore: update CHANGELOG",
                "See BREAKING CHANGE: section for prior releases.",
            )
            is False
        )


@pytest.mark.unit
class TestBreakingChangeGenuineCases:
    """Genuine BREAKING CHANGE notes must still be flagged."""

    def test_bare_breaking_change_at_line_start(self) -> None:
        """'BREAKING CHANGE: ...' as the first body line is a real breaking change."""
        assert (
            _parse(
                "feat: new endpoint",
                "BREAKING CHANGE: requires new env var DB_URL",
            )
            is True
        )

    def test_hashed_breaking_change(self) -> None:
        """Markdown-style '# BREAKING CHANGE: ...' is conventional."""
        assert (
            _parse(
                "feat(api)!: redesign",
                "# BREAKING CHANGE: removed legacy endpoints",
            )
            is True
        )

    def test_dash_variant_breaking_change(self) -> None:
        """'BREAKING-CHANGE:' (dash form) is accepted by some teams."""
        assert (
            _parse(
                "feat: rework auth",
                "BREAKING-CHANGE: auth tokens are now JWT-only",
            )
            is True
        )

    def test_conventional_commit_bang_marker(self) -> None:
        """`feat!:` and similar conventional-commit bang markers still flag breaking."""
        assert (
            _parse("feat!: rework auth flow", "")
            is True
        )


@pytest.mark.unit
class TestBreakingChangePositioning:
    """The match must be at a body line boundary, not mid-sentence."""

    def test_bang_marker_mid_sentence_not_breaking(self) -> None:
        """'!:' mid-sentence in body should not be treated as conventional marker."""
        assert (
            _parse(
                "fix: handle weird input",
                "User input was:!:'something' which broke the parser.",
            )
            is False
        )
