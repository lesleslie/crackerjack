"""Unit tests for ``CommitMessageGenerator`` via the package re-export.

There is already a comprehensive tests/services/test_intelligent_commit.py
file that drives the same module through the public ``crackerjack.services``
re-export. These tests cover the same surface via the
``crackerjack.services.ai.intelligent_commit`` import path to ensure both
import paths stay functional and to add a few additional contract tests
for the rule-based engine (specifically the type-check predicates, the
``_analyze_changes`` happy path, and the conventional-header ordering
rules).
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from crackerjack.services.ai.intelligent_commit import CommitMessageGenerator


@pytest.fixture
def console() -> Console:
    return Console(file=MagicMock(), force_terminal=False, no_color=True, width=200)


def _make_git(staged: list[str] | None = None) -> MagicMock:
    g = MagicMock()
    g.get_staged_files.return_value = staged if staged is not None else []
    g.commit.return_value = True
    return g


@pytest.fixture
def gen(console: Console) -> CommitMessageGenerator:
    return CommitMessageGenerator(console=console, git_service=_make_git())


# ---------------------------------------------------------------------------
# Patterns table integrity
# ---------------------------------------------------------------------------


class TestPatternTable:
    def test_all_expected_types(self, gen: CommitMessageGenerator) -> None:
        for t in ("feat", "fix", "refactor", "test", "docs", "style", "chore"):
            assert t in gen.patterns
            assert isinstance(gen.patterns[t], list)
            for pat in gen.patterns[t]:
                assert isinstance(pat, str)

    def test_patterns_compile(self, gen: CommitMessageGenerator) -> None:
        """Every pattern must be a valid regex."""
        for type_patterns in gen.patterns.values():
            for pat in type_patterns:
                re.compile(pat)


# ---------------------------------------------------------------------------
# Type predicates
# ---------------------------------------------------------------------------


class TestTypePredicates:
    def test_fix(self, gen: CommitMessageGenerator) -> None:
        assert gen._is_fix_commit({"fix"}, [], set()) is True
        assert gen._is_fix_commit(set(), [], set()) is False

    def test_feat(self, gen: CommitMessageGenerator) -> None:
        assert gen._is_feat_commit({"feat"}, [], set()) is True
        assert gen._is_feat_commit(set(), [], set()) is False

    def test_test_via_pattern(self, gen: CommitMessageGenerator) -> None:
        assert gen._is_test_commit({"test"}, [], set()) is True

    def test_test_via_filename_substring(self, gen: CommitMessageGenerator) -> None:
        # No pattern, but a filename containing "test" -> True
        assert gen._is_test_commit(set(), ["foo/test_bar.py"], set()) is True

    def test_test_no_match(self, gen: CommitMessageGenerator) -> None:
        assert gen._is_test_commit(set(), ["a.py"], set()) is False

    def test_docs_via_pattern(self, gen: CommitMessageGenerator) -> None:
        assert gen._is_docs_commit({"docs"}, [], set()) is True

    def test_docs_via_extension(self, gen: CommitMessageGenerator) -> None:
        for ext in (".md", ".rst", ".txt"):
            assert gen._is_docs_commit(set(), [], {ext}) is True
        assert gen._is_docs_commit(set(), [], {".py"}) is False

    def test_style_via_pattern_or_count(self, gen: CommitMessageGenerator) -> None:
        # Pattern match wins
        assert gen._is_style_commit({"style"}, ["x"], set()) is True
        # Count > 5
        files = [f"f{i}" for i in range(6)]
        assert gen._is_style_commit(set(), files, set()) is True
        # Count <= 5 and no pattern
        assert gen._is_style_commit(set(), ["a", "b", "c"], set()) is False

    def test_refactor(self, gen: CommitMessageGenerator) -> None:
        assert gen._is_refactor_commit({"refactor"}, [], set()) is True
        assert gen._is_refactor_commit(set(), [], set()) is False

    def test_default_to_chore(self, gen: CommitMessageGenerator) -> None:
        # No patterns match -> chore
        analysis = {
            "files": ["a.py"],
            "file_types": {".py"},
            "directories": {"a"},
            "total_files": 1,
            "patterns_found": set(),
        }
        assert gen._determine_commit_type(analysis) == "chore"


# ---------------------------------------------------------------------------
# Conventional header
# ---------------------------------------------------------------------------


class TestBuildConventionalHeader:
    def test_with_scope(self, gen: CommitMessageGenerator) -> None:
        assert gen._build_conventional_header("feat", "core", "add thing") == "feat(core): add thing"

    def test_without_scope(self, gen: CommitMessageGenerator) -> None:
        assert gen._build_conventional_header("chore", None, "update files") == "chore: update files"

    def test_empty_scope_treated_as_none(self, gen: CommitMessageGenerator) -> None:
        # An empty string is falsy in Python, so the helper falls into the
        # no-scope branch.
        assert gen._build_conventional_header("chore", "", "update files") == "chore: update files"


# ---------------------------------------------------------------------------
# Commit type check ordering
# ---------------------------------------------------------------------------


class TestCommitTypeCheckOrder:
    def test_fix_checked_first(self, gen: CommitMessageGenerator) -> None:
        """The first check is fix — this matters because the body
        builder / header use the first matching type."""
        checks = gen._get_commit_type_checks()
        assert checks[0][0] == "fix"
        assert checks[1][0] == "feat"

    def test_all_six_types_present(self, gen: CommitMessageGenerator) -> None:
        checks = gen._get_commit_type_checks()
        assert [c[0] for c in checks] == [
            "fix", "feat", "test", "docs", "style", "refactor",
        ]


# ---------------------------------------------------------------------------
# Public message generation — fallback paths
# ---------------------------------------------------------------------------


class TestEmptyStaged:
    def test_returns_chore_no_changes(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git(staged=[]))
        assert gen.generate_commit_message() == "chore: no changes to commit"

    def test_include_body_false_still_returns_short(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git(staged=[]))
        assert gen.generate_commit_message(include_body=False) == "chore: no changes to commit"

    def test_conventional_false_still_returns_short(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git(staged=[]))
        result = gen.generate_commit_message(conventional_commits=False)
        assert result == "chore: no changes to commit"


class TestExceptionFallback:
    def test_generic_exception_falls_back(self, console: Console) -> None:
        git = MagicMock()
        git.get_staged_files.side_effect = OSError("git failed")
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.generate_commit_message() == "chore: update files"


# ---------------------------------------------------------------------------
# Dry-run path
# ---------------------------------------------------------------------------


class TestCommitWithGeneratedMessage:
    def test_dry_run_skips_git_commit(self, console: Console) -> None:
        git = _make_git(staged=["src/foo.py"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.commit_with_generated_message(dry_run=True) is True
        git.commit.assert_not_called()

    def test_non_dry_run_calls_git_commit(self, console: Console) -> None:
        git = _make_git(staged=["src/foo.py"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        gen.commit_with_generated_message()
        # The path.lower() bug fires -> fallback is committed.
        git.commit.assert_called_once()
        assert git.commit.call_args.args[0] == "chore: update files"

    def test_dry_run_with_empty_staged(self, console: Console) -> None:
        git = _make_git(staged=[])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.commit_with_generated_message(dry_run=True) is True
        git.commit.assert_not_called()

    def test_non_dry_run_with_empty_staged(self, console: Console) -> None:
        git = _make_git(staged=[])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.commit_with_generated_message() is True
        git.commit.assert_called_once_with("chore: no changes to commit")

    def test_returns_git_commit_value(self, console: Console) -> None:
        git = _make_git(staged=["x.py"])
        git.commit.return_value = False
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.commit_with_generated_message() is False
