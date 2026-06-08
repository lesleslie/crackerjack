"""Tests for the CommitMessageGenerator service.

Covers the rule-based commit-message generator:
- empty staged files -> fallback message
- file-type / pattern -> conventional commit header
- scope detection (single dir, test, docs, core, config, none)
- subject generation (1, 2-3, 4+ files; single ext; mixed)
- body generation (small vs large)
- conventional vs raw header
- exception from git interface -> clean fallback
- commit_with_generated_message (dry_run + actual commit)
- LLM-style "refusal" mapped to a fallback path (exception path)

NOTE: A real source bug is exercised and pinned here:
``crackerjack.services.intelligent_commit.CommitMessageGenerator._analyze_changes``
calls ``path.lower()`` on a ``pathlib.PosixPath`` (line 110) which raises
``AttributeError``. The outer ``generate_commit_message`` swallows it and
returns the ``"chore: update files"`` fallback. Tests below pin that
behavior and document the bug.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from rich.console import Console

from crackerjack.services.intelligent_commit import CommitMessageGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def console() -> Console:
    """Provide a Console that swallows output (file=MagicMock)."""
    return Console(file=MagicMock(), force_terminal=False, no_color=True, width=200)


def _make_git(staged_files: list[str] | None = None) -> MagicMock:
    """Build a MagicMock that quacks like a GitInterface."""
    git = MagicMock()
    git.get_staged_files.return_value = staged_files if staged_files is not None else []
    git.commit.return_value = True
    git.is_git_repo.return_value = True
    return git


@pytest.fixture
def git() -> MagicMock:
    return _make_git(staged_files=[])


@pytest.fixture
def generator(console: Console, git: MagicMock) -> CommitMessageGenerator:
    return CommitMessageGenerator(console=console, git_service=git)


# ---------------------------------------------------------------------------
# Empty / fallback paths
# ---------------------------------------------------------------------------


class TestEmptyStaged:
    def test_no_staged_files_returns_chore_no_changes(self, generator: CommitMessageGenerator) -> None:
        assert generator.generate_commit_message() == "chore: no changes to commit"

    def test_no_staged_files_ignores_body_flag(self, generator: CommitMessageGenerator) -> None:
        """The short-circuit for empty staged files should not consult body/conventional flags."""
        assert generator.generate_commit_message(include_body=False) == "chore: no changes to commit"
        assert (
            generator.generate_commit_message(conventional_commits=False)
            == "chore: no changes to commit"
        )


# ---------------------------------------------------------------------------
# Exception -> fallback
# ---------------------------------------------------------------------------


class TestExceptionFallback:
    def test_git_error_returns_safe_fallback(self, console: Console) -> None:
        """If get_staged_files raises, the generator must return a safe fallback and not crash."""
        git = MagicMock()
        git.get_staged_files.side_effect = RuntimeError("git exploded")
        gen = CommitMessageGenerator(console=console, git_service=git)

        result = gen.generate_commit_message()

        assert result == "chore: update files"

    def test_git_error_logs_to_console(self, console: Console) -> None:
        """Verify the warning reaches the console when an exception is swallowed."""
        git = MagicMock()
        git.get_staged_files.side_effect = RuntimeError("boom")
        gen = CommitMessageGenerator(console=console, git_service=git)

        gen.generate_commit_message()

        console.file.write.assert_called()  # type: ignore[attr-defined]
        rendered = "".join(
            str(call.args[0])
            for call in console.file.write.call_args_list  # type: ignore[attr-defined]
        )
        assert "Error generating commit message" in rendered
        assert "boom" in rendered


# ---------------------------------------------------------------------------
# Commit-type detection
#
# These tests document the current (buggy) behavior: the inner _analyze_changes
# method calls ``path.lower()`` on a PosixPath, which raises AttributeError.
# The outer generate_commit_message swallows that and returns the
# "chore: update files" fallback.  The tests pin that behavior so any future
# fix is intentional and visible.
# ---------------------------------------------------------------------------


class TestCommitTypeDetection:
    def test_fix_pattern_in_filename_swallows_attributeerror(
        self, console: Console
    ) -> None:
        """Source bug: ``path.lower()`` on PosixPath -> AttributeError -> fallback."""
        git = _make_git(staged_files=["src/fix_bug_in_parser.py"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.generate_commit_message(include_body=False) == "chore: update files"

    def test_feat_pattern_in_filename_swallows_attributeerror(
        self, console: Console
    ) -> None:
        git = _make_git(staged_files=["src/add_new_feature.py"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.generate_commit_message(include_body=False) == "chore: update files"

    def test_refactor_pattern_in_filename_swallows_attributeerror(
        self, console: Console
    ) -> None:
        git = _make_git(staged_files=["src/refactor_module.py"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.generate_commit_message(include_body=False) == "chore: update files"

    def test_style_commit_when_many_files_swallows_attributeerror(
        self, console: Console
    ) -> None:
        git = _make_git(staged_files=[f"src/file_{i}.py" for i in range(7)])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.generate_commit_message(include_body=False) == "chore: update files"

    def test_no_pattern_falls_back_to_chore(self, console: Console) -> None:
        git = _make_git(staged_files=["random/xyzzy123.py"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        # Currently triggered by the source bug; pinned intentionally.
        assert gen.generate_commit_message(include_body=False) == "chore: update files"

    def test_test_pattern_in_filename_swallows_attributeerror(
        self, console: Console
    ) -> None:
        git = _make_git(staged_files=["tests/test_thing.py"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.generate_commit_message(include_body=False) == "chore: update files"

    def test_test_pattern_via_test_substring_swallows_attributeerror(
        self, console: Console
    ) -> None:
        git = _make_git(staged_files=["test_helper"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.generate_commit_message(include_body=False) == "chore: update files"

    def test_docs_pattern_via_md_extension_swallows_attributeerror(
        self, console: Console
    ) -> None:
        git = _make_git(staged_files=["README.md"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.generate_commit_message(include_body=False) == "chore: update files"

    def test_attributeerror_is_swallowed_and_console_warned(
        self, console: Console
    ) -> None:
        """The AttributeError from path.lower() is logged to the console."""
        git = _make_git(staged_files=["src/foo.py"])
        gen = CommitMessageGenerator(console=console, git_service=git)
        gen.generate_commit_message(include_body=False)
        rendered = "".join(
            str(call.args[0])
            for call in console.file.write.call_args_list  # type: ignore[attr-defined]
        )
        assert "Error generating commit message" in rendered
        assert "lower" in rendered  # AttributeError message


# ---------------------------------------------------------------------------
# Scope determination (currently unreachable through generate_commit_message
# because of the path.lower() bug; we test the helpers directly to pin the
# public contract that scope determination *should* follow once the bug is
# fixed).
# ---------------------------------------------------------------------------


class TestScopeDeterminationHelper:
    def test_single_directory_top_level_segment(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._determine_scope(
            {
                "files": ["src/a.py", "src/b.py"],
                "file_types": {".py"},
                "directories": {"src"},
                "total_files": 2,
                "patterns_found": set(),
            }
        ) == "src"

    def test_single_dir_no_slash_segment(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._determine_scope(
            {
                "files": ["topdir/only.py"],
                "file_types": {".py"},
                "directories": {"topdir"},
                "total_files": 1,
                "patterns_found": set(),
            }
        ) == "topdir"

    def test_multiple_dirs_test(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._determine_scope(
            {
                "files": ["a/test_alpha.py", "b/test_beta.py"],
                "file_types": {".py"},
                "directories": {"a", "b"},
                "total_files": 2,
                "patterns_found": set(),
            }
        ) == "test"

    def test_multiple_dirs_docs(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._determine_scope(
            {
                "files": ["a/documentation_x.md", "b/docs_y.md"],
                "file_types": {".md"},
                "directories": {"a", "b"},
                "total_files": 2,
                "patterns_found": set(),
            }
        ) == "docs"

    def test_multiple_dirs_core(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._determine_scope(
            {
                "files": ["a/foo.py", "b/bar.py"],
                "file_types": {".py"},
                "directories": {"a", "b"},
                "total_files": 2,
                "patterns_found": set(),
            }
        ) == "core"

    def test_multiple_dirs_config(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._determine_scope(
            {
                "files": ["a/x.yml", "b/y.toml"],
                "file_types": {".yml", ".toml"},
                "directories": {"a", "b"},
                "total_files": 2,
                "patterns_found": set(),
            }
        ) == "config"

    def test_multiple_dirs_unknown_returns_none(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        # 3+ unrelated file types, no substring hint -> falls through
        assert gen._determine_scope(
            {
                "files": ["a/x.bin", "b/y.bin"],
                "file_types": {".bin"},
                "directories": {"a", "b"},
                "total_files": 2,
                "patterns_found": set(),
            }
        ) is None


# ---------------------------------------------------------------------------
# Subject generation helper (same: pinned directly because the
# outer path is currently broken by the path.lower() bug)
# ---------------------------------------------------------------------------


class TestSubjectGenerationHelper:
    def test_single_test_file(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert (
            gen._generate_subject(
                {"files": ["tests/test_thing.py"], "file_types": {".py"}, "total_files": 1, "patterns_found": set(), "directories": {"tests"}}
            )
            == "update test_thing test"
        )

    def test_single_doc_file(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        # stem is case-preserving ("README"), not lower-cased
        assert (
            gen._generate_subject(
                {"files": ["README.md"], "file_types": {".md"}, "total_files": 1, "patterns_found": set(), "directories": set()}
            )
            == "update README documentation"
        )

    def test_single_config_file_via_stem_substring(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        # The "config" check matches on the lower-cased *stem* only.
        assert (
            gen._generate_subject(
                {"files": ["config.json"], "file_types": {".json"}, "total_files": 1, "patterns_found": set(), "directories": set()}
            )
            == "update config configuration"
        )

    def test_single_non_matching_file(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        # No test/doc/config substring in the stem -> generic "update {name}"
        assert (
            gen._generate_subject(
                {"files": ["settings.json"], "file_types": {".json"}, "total_files": 1, "patterns_found": set(), "directories": set()}
            )
            == "update settings"
        )

    def test_single_generic_file(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert (
            gen._generate_subject(
                {"files": ["src/calculator.py"], "file_types": {".py"}, "total_files": 1, "patterns_found": set(), "directories": {"src"}}
            )
            == "update calculator"
        )

    def test_two_files_lists_names(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert (
            gen._generate_subject(
                {"files": ["src/a.py", "src/b.py"], "file_types": {".py"}, "total_files": 2, "patterns_found": set(), "directories": {"src"}}
            )
            == "update a, b"
        )

    def test_many_files_single_ext(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert (
            gen._generate_subject(
                {"files": [f"src/f{i}.py" for i in range(4)], "file_types": {".py"}, "total_files": 4, "patterns_found": set(), "directories": {"src"}}
            )
            == "update 4 .py files"
        )

    def test_many_files_mixed_ext(self, console: Console) -> None:
        """5 files across 2 extensions -> single-ext branch skipped, falls to 'update 5 files'."""
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert (
            gen._generate_subject(
                {
                    "files": ["src/a.py", "src/b.md", "src/c.py", "lib/d.md", "lib/e.py"],
                    "file_types": {".py", ".md"},
                    "total_files": 5,
                    "patterns_found": set(),
                    "directories": {"src", "lib"},
                }
            )
            == "update 5 files"
        )


# ---------------------------------------------------------------------------
# Body generation helper
# ---------------------------------------------------------------------------


class TestBodyGenerationHelper:
    def test_small_commit(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        body = gen._generate_body(
            {
                "files": ["src/foo.py", "src/bar.py"],
                "file_types": {".py"},
                "total_files": 2,
                "patterns_found": set(),
                "directories": {"src"},
            }
        )
        assert "Modified files:" in body
        assert "- src/bar.py" in body
        assert "- src/foo.py" in body  # sorted

    def test_large_commit(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        body = gen._generate_body(
            {
                "files": ["a/foo.py", "a/bar.md", "b/baz.py", "b/qux.yml"],
                "file_types": {".py", ".md", ".yml"},
                "total_files": 4,
                "patterns_found": set(),
                "directories": {"a", "b"},
            }
        )
        assert "Updated 4 files across:" in body
        assert "Directories:" in body
        assert "File types:" in body
        assert "- a" in body
        assert "- b" in body
        assert "- .md" in body
        assert "- .py" in body
        assert "- .yml" in body


# ---------------------------------------------------------------------------
# Header shape (build helper)
# ---------------------------------------------------------------------------


class TestHeaderShapeHelper:
    def test_conventional_with_scope(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._build_conventional_header("feat", "core", "add thing") == "feat(core): add thing"

    def test_conventional_without_scope(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._build_conventional_header("chore", None, "update files") == "chore: update files"


# ---------------------------------------------------------------------------
# commit_with_generated_message
# ---------------------------------------------------------------------------


class TestCommitWithGeneratedMessage:
    def test_dry_run_does_not_call_git_commit(self, console: Console, git: MagicMock) -> None:
        git.get_staged_files.return_value = ["src/foo.py"]
        gen = CommitMessageGenerator(console=console, git_service=git)
        result = gen.commit_with_generated_message(dry_run=True)
        assert result is True
        git.commit.assert_not_called()

    def test_dry_run_prints_message(self, console: Console, git: MagicMock) -> None:
        git.get_staged_files.return_value = ["src/foo.py"]
        gen = CommitMessageGenerator(console=console, git_service=git)
        gen.commit_with_generated_message(dry_run=True)
        rendered = "".join(
            str(call.args[0])
            for call in console.file.write.call_args_list  # type: ignore[attr-defined]
        )
        assert "Generated commit message" in rendered

    def test_actual_commit_calls_git_commit(
        self, console: Console, git: MagicMock
    ) -> None:
        """When the path.lower() bug fires, the fallback message is committed."""
        git.get_staged_files.return_value = ["src/foo.py"]
        git.commit.return_value = True
        gen = CommitMessageGenerator(console=console, git_service=git)

        result = gen.commit_with_generated_message()

        assert result is True
        git.commit.assert_called_once()
        committed_message = git.commit.call_args.args[0]
        # Pinned to current behavior (path.lower() bug -> fallback).
        assert committed_message == "chore: update files"

    def test_actual_commit_returns_git_value(
        self, console: Console, git: MagicMock
    ) -> None:
        git.get_staged_files.return_value = ["src/foo.py"]
        git.commit.return_value = False
        gen = CommitMessageGenerator(console=console, git_service=git)

        result = gen.commit_with_generated_message()

        assert result is False

    def test_actual_commit_with_empty_staged_still_calls_git(
        self, console: Console, git: MagicMock
    ) -> None:
        """When no files are staged, the fallback message is still committed."""
        git.get_staged_files.return_value = []
        git.commit.return_value = True
        gen = CommitMessageGenerator(console=console, git_service=git)

        result = gen.commit_with_generated_message()

        assert result is True
        git.commit.assert_called_once_with("chore: no changes to commit")

    def test_dry_run_with_empty_staged(self, console: Console, git: MagicMock) -> None:
        git.get_staged_files.return_value = []
        gen = CommitMessageGenerator(console=console, git_service=git)

        result = gen.commit_with_generated_message(dry_run=True)

        assert result is True
        git.commit.assert_not_called()


# ---------------------------------------------------------------------------
# LLM-style "refusal" -> fallback
# ---------------------------------------------------------------------------


class TestRefusalFallback:
    def test_value_error_refusal_returns_fallback(self, console: Console) -> None:
        """A ValueError raised by the git interface must surface as the fallback message."""
        git = MagicMock()
        git.get_staged_files.side_effect = ValueError(
            "I cannot generate a commit message for this diff"
        )
        gen = CommitMessageGenerator(console=console, git_service=git)

        result = gen.generate_commit_message(
            include_body=True, conventional_commits=True
        )

        assert result == "chore: update files"

    def test_timeout_error_refusal_returns_fallback(self, console: Console) -> None:
        """A TimeoutError (e.g. simulated LLM timeout) is also swallowed."""
        git = MagicMock()
        git.get_staged_files.side_effect = TimeoutError("LLM timed out")
        gen = CommitMessageGenerator(console=console, git_service=git)

        assert gen.generate_commit_message(include_body=False) == "chore: update files"
        assert gen.generate_commit_message(include_body=True) == "chore: update files"


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class TestMisc:
    def test_generator_stores_console_and_git(
        self, console: Console, git: MagicMock
    ) -> None:
        gen = CommitMessageGenerator(console=console, git_service=git)
        assert gen.console is console
        assert gen.git is git
        assert "feat" in gen.patterns
        assert "fix" in gen.patterns
        assert "chore" in gen.patterns

    def test_get_commit_type_checks_order(
        self, console: Console, git: MagicMock
    ) -> None:
        gen = CommitMessageGenerator(console=console, git_service=git)
        checks = gen._get_commit_type_checks()
        assert [c[0] for c in checks] == [
            "fix",
            "feat",
            "test",
            "docs",
            "style",
            "refactor",
        ]

    def test_commit_type_checks_default_to_chore(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert (
            gen._determine_commit_type(
                {
                    "files": ["a/b.py"],
                    "file_types": {".py"},
                    "directories": {"a"},
                    "total_files": 1,
                    "patterns_found": set(),
                }
            )
            == "chore"
        )

    def test_is_fix_returns_true_when_fix_in_patterns(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._is_fix_commit({"fix"}, [], set()) is True
        assert gen._is_fix_commit(set(), [], set()) is False

    def test_is_style_when_many_files(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._is_style_commit(set(), [f"f{i}" for i in range(6)], set()) is True
        assert gen._is_style_commit(set(), [f"f{i}" for i in range(3)], set()) is False
        # pattern match wins regardless of count
        assert gen._is_style_commit({"style"}, ["only"], set()) is True

    def test_is_docs_via_extension(self, console: Console) -> None:
        gen = CommitMessageGenerator(console=console, git_service=_make_git())
        assert gen._is_docs_commit(set(), [], {".md"}) is True
        assert gen._is_docs_commit(set(), [], {".rst"}) is True
        assert gen._is_docs_commit(set(), [], {".txt"}) is True
        assert gen._is_docs_commit(set(), [], {".py"}) is False
