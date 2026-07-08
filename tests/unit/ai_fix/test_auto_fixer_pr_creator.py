"""Tests for :class:`GhPRCreator` (PR 8 of 2026-07-07 ai-fix design).

The real :class:`GhPRCreator` shells out to the ``gh`` CLI. Tests
monkey-patch :func:`subprocess.run` to capture the invocation
without actually opening a PR. The PR body is the public contract
that needs to be stable — the tests assert on the body format
directly via :func:`_build_pr_body` and on the ``gh`` argv via
the captured :func:`subprocess.run` call.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.ai_fix.auto_fixer_pr_creator import (
    AUTO_FIXERS_DIRNAME,
    GhPRCreator,
    _build_pr_body,
)


# ---------------------------------------------------------------------------
# 1. _build_pr_body — pure
# ---------------------------------------------------------------------------


class TestBuildPrBody:
    """The PR body is a Markdown-ish text block. Tests assert the contract."""

    def test_includes_signature_in_header(self) -> None:
        body = _build_pr_body(
            signature="abc123",
            skill_diff="@@ -1 +1 @@\n-x\n+y\n",
        )
        assert "abc123" in body
        assert "Promoted from skill" in body

    def test_truncates_long_diffs(self) -> None:
        long_diff = "x" * 10_000
        body = _build_pr_body(signature="s", skill_diff=long_diff)
        # The truncated marker should appear.
        assert "truncated" in body
        # The body should be shorter than the input.
        assert len(body) < len(long_diff) + 500  # some slack for the wrapper text

    def test_includes_sandbox_output_when_provided(self) -> None:
        body = _build_pr_body(
            signature="s",
            skill_diff="diff",
            sandbox_stdout="test passed",
            sandbox_stderr="",
        )
        assert "## Sandbox test output" in body
        assert "test passed" in body

    def test_omits_sandbox_section_when_no_output(self) -> None:
        body = _build_pr_body(
            signature="s",
            skill_diff="diff",
            sandbox_stdout="",
            sandbox_stderr="",
        )
        assert "## Sandbox test output" not in body

    def test_includes_review_checklist(self) -> None:
        body = _build_pr_body(signature="s", skill_diff="d")
        assert "Review checklist" in body


# ---------------------------------------------------------------------------
# 2. GhPRCreator.create_pr — mocked subprocess
# ---------------------------------------------------------------------------


class TestGhPRCreatorCreatePR:
    """The :class:`GhPRCreator` writes the file then shells out to ``gh``."""

    def test_writes_fixer_to_auto_fixers_dir(self, tmp_path: Path) -> None:
        # The PR creator needs the file at auto_fixers/<safe_sig>.py.
        target_dir = tmp_path / AUTO_FIXERS_DIRNAME
        target_dir.mkdir()

        with patch("crackerjack.ai_fix.auto_fixer_pr_creator.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="https://github.com/x/y/pull/1\n", stderr=""
            )
            creator = GhPRCreator(project_root=tmp_path)
            creator.create_pr(
                fixer_source="# my fixer\n",
                signature="abc123",
                skill_diff="d",
            )

        written = list(target_dir.glob("*.py"))
        assert len(written) == 1
        assert written[0].name == "abc123.py"
        assert written[0].read_text() == "# my fixer\n"

    def test_gh_invocation_args(self, tmp_path: Path) -> None:
        with patch("crackerjack.ai_fix.auto_fixer_pr_creator.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="https://github.com/x/y/pull/1\n", stderr=""
            )
            creator = GhPRCreator(project_root=tmp_path, gh_executable="gh-test")
            url = creator.create_pr(
                fixer_source="",
                signature="abc",
                skill_diff="d",
            )

        run.assert_called_once()
        argv = run.call_args[0][0]
        assert argv[0] == "gh-test"
        assert argv[1:3] == ["pr", "create"]
        assert "--title" in argv
        assert "--body" in argv
        assert "--base" in argv
        assert "main" in argv
        assert "--head" in argv
        assert url == "https://github.com/x/y/pull/1"

    def test_nonghzero_exit_raises(self, tmp_path: Path) -> None:
        with patch("crackerjack.ai_fix.auto_fixer_pr_creator.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="auth failed"
            )
            creator = GhPRCreator(project_root=tmp_path)
            with pytest.raises(RuntimeError, match="gh pr create exited 1"):
                creator.create_pr(
                    fixer_source="",
                    signature="abc",
                    skill_diff="d",
                )

    def test_no_url_in_stdout_raises(self, tmp_path: Path) -> None:
        with patch("crackerjack.ai_fix.auto_fixer_pr_creator.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Created PR (no URL printed)\n",  # valid exit but no http:// line
                stderr="",
            )
            creator = GhPRCreator(project_root=tmp_path)
            with pytest.raises(RuntimeError, match="did not return a URL"):
                creator.create_pr(
                    fixer_source="",
                    signature="abc",
                    skill_diff="d",
                )

    def test_unsafe_signature_chars_sanitized(self, tmp_path: Path) -> None:
        """A signature with path-unsafe chars gets a safe filename."""
        with patch("crackerjack.ai_fix.auto_fixer_pr_creator.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="https://github.com/x/y/pull/1\n", stderr=""
            )
            creator = GhPRCreator(project_root=tmp_path)
            creator.create_pr(
                fixer_source="",
                signature="../etc/passwd&rm -rf /",  # all kinds of unsafe
                skill_diff="d",
            )
        written = list((tmp_path / AUTO_FIXERS_DIRNAME).glob("*.py"))
        assert len(written) == 1
        # The filename stem should not contain /, &, or space.
        assert "/" not in written[0].name
        assert "&" not in written[0].name
        assert " " not in written[0].name

    def test_subprocess_timeout_raises(self, tmp_path: Path) -> None:
        with patch(
            "crackerjack.ai_fix.auto_fixer_pr_creator.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=120),
        ):
            creator = GhPRCreator(project_root=tmp_path)
            with pytest.raises(RuntimeError, match="gh pr create failed"):
                creator.create_pr(
                    fixer_source="",
                    signature="abc",
                    skill_diff="d",
                )

    def test_long_signature_truncated_to_64(self, tmp_path: Path) -> None:
        with patch("crackerjack.ai_fix.auto_fixer_pr_creator.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="https://github.com/x/y/pull/1\n", stderr=""
            )
            creator = GhPRCreator(project_root=tmp_path)
            creator.create_pr(
                fixer_source="",
                signature="a" * 200,
                skill_diff="d",
            )
        written = list((tmp_path / AUTO_FIXERS_DIRNAME).glob("*.py"))
        assert len(written) == 1
        # Filename without .py extension should be <= 64 chars.
        assert len(written[0].stem) <= 64
