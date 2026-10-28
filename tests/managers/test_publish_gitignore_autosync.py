"""Tests for the auto-sync gitignore behavior in publish_manager.

Validates the contract documented in
`.claude/decisions/2026-10-12-publish-auto-sync-gitignore.md`:

  - snippet present, no missing patterns  -> PASS, no sync subprocess
  - snippet missing                       -> auto-sync attempt, PASS on success
  - snippet + patterns missing            -> auto-sync attempt, PASS on success
  - sync subprocess fails                 -> FAIL, abort publish
  - sync succeeds but drift persists      -> FAIL, abort publish
  - pre-flight: `.gitignore` has uncommitted edits -> refuse auto-sync
  - non-fleet member                      -> PASS silently (no sync)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.checks.gitignore_conformance import GitignoreConformanceResult
from crackerjack.managers.publish_manager import (
    PublishManagerImpl,
    _sanitize_subprocess_output,
)


def _completed(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Real CompletedProcess so .stdout.strip() returns the actual string."""
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_console() -> MagicMock:
    return MagicMock(spec=Console)


def _make_conform_result(
    *,
    is_fleet_member: bool = True,
    snippet_present: bool = True,
    missing_patterns: list[str] | None = None,
    repo_path: Path | None = None,
) -> GitignoreConformanceResult:
    return GitignoreConformanceResult(
        repo_path=repo_path or Path("/fake/repo"),
        is_fleet_member=is_fleet_member,
        snippet_present=snippet_present,
        missing_patterns=missing_patterns or [],
    )


def _make_publish_manager(
    pkg_path: Path,
    console: MagicMock,
) -> PublishManagerImpl:
    """Build a minimal PublishManagerImpl with mocked dependencies.

    We only exercise `_validate_gitignore_conformance`, which is an
    instance method that touches self.pkg_path and self.console. All
    other constructor args default to None, which auto-resolves via
    PublishManagerImpl._resolve_*().
    """
    return PublishManagerImpl(
        console=console,
        pkg_path=pkg_path,
    )


# ---------------------------------------------------------------------------
# Cases: gate behavior
# ---------------------------------------------------------------------------


def test_pass_when_conformant_no_sync_invoked(tmp_path: Path, mock_console: MagicMock) -> None:
    """Clean state: PASS, no subprocess, no error log."""
    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(is_fleet_member=True, snippet_present=True, missing_patterns=[])

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ) as check_mock,
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    check_mock.assert_called_once_with(tmp_path)
    run_mock.assert_not_called()


def test_non_fleet_repo_passes_silently(tmp_path: Path, mock_console: MagicMock) -> None:
    """Non-Bodai repos: PASS, no sync."""
    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(is_fleet_member=False)

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ) as check_mock,
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    check_mock.assert_called_once_with(tmp_path)
    run_mock.assert_not_called()


def test_snippet_missing_triggers_sync_and_passes(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: snippet missing. Auto-sync succeeds, gate PASSES."""
    pm = _make_publish_manager(tmp_path, mock_console)
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*", "!.claude/decisions/"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=_completed(),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    assert run_mock.call_count == 1


def test_patterns_missing_triggers_sync_and_passes(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: snippet present but patterns missing. Auto-sync succeeds."""
    pm = _make_publish_manager(tmp_path, mock_console)
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[".claude/*"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=_completed(),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    assert run_mock.call_count == 1


def test_sync_subprocess_failure_aborts(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: sync subprocess returns nonzero. Gate ABORTS."""
    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=_completed(returncode=1, stderr="boom"),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    assert run_mock.call_count == 1


def test_sync_subprocess_timeout_aborts(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: sync subprocess hangs and times out. Gate ABORTS."""
    import subprocess

    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gitignore sync", timeout=60),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    assert run_mock.call_count == 1


def test_sync_succeeds_but_drift_persists_aborts(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: sync subprocess returns 0 but re-check still shows missing.
    Gate ABORTS — likely a stale backup blocking the sync.
    """
    pm = _make_publish_manager(tmp_path, mock_console)
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[".claude/*", "!.claude/decisions/"],  # drift persists
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=_completed(),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    assert run_mock.call_count == 1


def test_uncommitted_gitignore_refuses_auto_sync(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift + dirty .gitignore working tree -> auto-sync REFUSED, gate ABORTS."""
    pm = _make_publish_manager(tmp_path, mock_console)
    (tmp_path / ".gitignore").write_text("# operator WIP\n")
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )

    fake_status = _completed(stdout=" M .gitignore\n")
    fake_sync = _completed()

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            side_effect=[fake_status, fake_sync],
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    # Only the pre-flight `git status` ran; the sync subprocess did NOT.
    assert run_mock.call_count == 1


def test_clean_gitignore_proceeds_with_sync(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift + clean .gitignore working tree -> both pre-flight + sync execute."""
    pm = _make_publish_manager(tmp_path, mock_console)
    (tmp_path / ".gitignore").write_text("# clean\n")
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
    )

    fake_status_clean = _completed()
    fake_sync_ok = _completed()

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            side_effect=[fake_status_clean, fake_sync_ok],
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    assert run_mock.call_count == 2  # git status + crackerjack gitignore sync


def test_sync_subprocess_uses_correct_args(tmp_path: Path, mock_console: MagicMock) -> None:
    """The subprocess invocation must use --pkg-path and the target."""
    import sys

    (tmp_path / ".gitignore").write_text("# clean\n")
    pm = _make_publish_manager(tmp_path, mock_console)
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
    )

    fake_status = _completed()

    captured_args: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_args.append(cmd)
        # First call: git status (return clean). Second call: crackerjack sync.
        if cmd and cmd[0] == "git":
            return fake_status
        return _completed()

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            side_effect=fake_run,
        ),
    ):
        pm._validate_gitignore_conformance()

    assert len(captured_args) == 2
    sync_call = captured_args[1]
    assert sync_call[0] == sys.executable
    assert sync_call[1] == "-m"
    assert sync_call[2] == "crackerjack"
    assert sync_call[3] == "gitignore"
    assert sync_call[4] == "sync"
    assert sync_call[5] == "--pkg-path"
    assert sync_call[6] == str(tmp_path)


# ---------------------------------------------------------------------------
# Cases: _sanitize_subprocess_output (observability safety)
# ---------------------------------------------------------------------------


def test_sanitize_returns_empty_for_empty_input() -> None:
    """None and empty strings yield empty output (defensive default)."""
    assert _sanitize_subprocess_output(None) == ""
    assert _sanitize_subprocess_output("") == ""


def test_sanitize_passes_short_text_through() -> None:
    """Text shorter than the truncation limit is returned unchanged."""
    text = "ERROR: missing canonical snippet\n"
    assert _sanitize_subprocess_output(text) == text


def test_sanitize_truncates_long_text_with_marker() -> None:
    """Text longer than the tail limit is truncated and marked."""
    text = "X" * 4096
    out = _sanitize_subprocess_output(text)
    assert "…<truncated>…" in out
    # Tail of original is preserved.
    assert out.endswith("X" * 32)
    # No prefix from the head survives.
    assert not out.startswith("X" * 4096)


def test_sanitize_truncation_respects_tail_bytes_kwarg() -> None:
    """Custom tail_bytes is honored for tests of small inputs."""
    text = "A" * 100 + "B" * 100
    out = _sanitize_subprocess_output(text, tail_bytes=50)
    assert "…<truncated>…" in out
    # The B-tail is the only thing kept.
    assert "B" * 50 in out
    assert "A" not in out


def test_sanitize_redacts_github_token() -> None:
    """GitHub PAT prefixes are redacted (gho_, ghp_, etc.)."""
    text = "Traceback: ghp_abc123def456ghi789jkl012mno\n"
    out = _sanitize_subprocess_output(text)
    assert "ghp_abc123def456ghi789jkl012mno" not in out
    assert "<REDACTED>" in out


def test_sanitize_redacts_google_token() -> None:
    """Google OAuth token prefix (ya29.) is redacted."""
    text = "leaked ya29.A0ARrdaM-abcdefghijklmnopqrstuvwxyz\n"
    out = _sanitize_subprocess_output(text)
    assert "ya29.A0ARrdaM" not in out
    assert "<REDACTED>" in out


def test_sanitize_redacts_key_value_credentials() -> None:
    """`token=...`, `api_key: ...`, `password=...` patterns are redacted."""
    text = (
        "config error: token=supersecretvalue12345\n"
        'api_key: "AKIAIOSFODNN7EXAMPLE"\n'
        "password=hunter2hunter2hunter2hunter2\n"
    )
    out = _sanitize_subprocess_output(text)
    assert "supersecretvalue12345" not in out
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "hunter2hunter2hunter2hunter2" not in out
    assert out.count("<REDACTED>") >= 3


def test_sanitize_redacts_authorization_header() -> None:
    """`Authorization: ...` values are redacted."""
    text = "request: Authorization: Bearer abcdef1234567890abcdef\n"
    out = _sanitize_subprocess_output(text)
    assert "abcdef1234567890abcdef" not in out
    assert "authorization: <REDACTED>" in out


def test_sanitize_preserves_non_sensitive_context() -> None:
    """Sanitization keeps normal log lines untouched (no over-redaction)."""
    text = (
        "Traceback (most recent call last):\n"
        '  File "/usr/lib/python3.12/json/__init__.py", line 354, in loads\n'
        "    raise JSONDecodeError(\"Expecting value\", s, err.value) from None\n"
        "json.decoder.JSONDecodeError: Expecting value: line 1 column 1\n"
    )
    out = _sanitize_subprocess_output(text)
    # Path and message are preserved (no credential-shaped content).
    assert "json/__init__.py" in out
    assert "JSONDecodeError" in out


def test_sync_failure_passes_sanitized_stderr_to_console(
    tmp_path: Path, mock_console: MagicMock,
) -> None:
    """End-to-end: sync subprocess emits a token in stderr; only <REDACTED> reaches console."""
    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )

    leak = "Traceback:\n  ghp_abcdefghijklmnopqrstuvwx\n"
    fake_sync = _completed(returncode=2, stderr=leak)

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=fake_sync,
        ),
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    # The raw token must NEVER appear in any console.print call.
    for call in mock_console.print.call_args_list:
        rendered = " ".join(str(arg) for arg in call.args)
        assert "ghp_abcdefghijklmnopqrstuvwx" not in rendered, (
            f"Raw token leaked to console: {rendered!r}"
        )


# ---------------------------------------------------------------------------
# Cases: parser-differential redaction (wrapped-line tokens)
# ---------------------------------------------------------------------------


def test_sanitize_redacts_github_token_wrapped_across_newline() -> None:
    """A GitHub token wrapped across a line break is still fully redacted.

    Python ``repr()`` and curl verbose output commonly wrap long values
    at column 80. A line-anchored regex pattern misses the wrapped
    continuation, leaking the rest of the token. The value class in
    this sanitizer includes ``\\s`` so a single match consumes the
    full wrapped shape.
    """
    text = (
        "Traceback (most recent call last):\n"
        "  File 'x.py', line 5, in <module>\n"
        "    raise ValueError(token)\n"
        "ValueError: ghp_abcdefghijklmnopqrstuvwxyz012345\n"
        "6789ABCDEFGHIJ\n"
    )
    out = _sanitize_subprocess_output(text)
    assert "ghp_abcdefghijklmnopqrstuvwxyz012345" not in out
    assert "6789ABCDEFGHIJ" not in out
    assert "<REDACTED>" in out


def test_sanitize_redacts_long_github_token_wrapped_mid_value() -> None:
    """A 40-char GitHub token (ghp_ + 36 chars) wrapped mid-value.

    Realistic: GitHub's classic PAT is exactly 40 chars, and Python
    ``repr()`` wraps at 80 chars — so the token's third character
    can land on the wrap. The 400-char cap with ``\\s`` in the
    value class catches the full wrapped shape.
    """
    text = (
        "Token: ghp_abcdefghijklmnopqrstuvwxyz0123456789\n"
        "tail_garbage_that_should_also_be_swept_in\n"
    )
    out = _sanitize_subprocess_output(text)
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in out
    assert "tail_garbage" not in out  # within 400 char reach from prefix


def test_sanitize_caps_value_length_at_400_chars() -> None:
    """The value class cap is 400 chars, bounding over-redaction.

    With a 1000-char tail of unrelated text, the cap stops the
    match before consuming the whole blob — operator context past
    400 chars is preserved.
    """
    long_tail = "x" * 1000
    text = f"ghp_a{'b' * 100}{long_tail}\n"
    out = _sanitize_subprocess_output(text, tail_bytes=10_000)
    # The token's first 100 'b' chars are within the 400 cap and
    # are redacted. Most of the 1000 x's (the ones past the 400
    # cap) are preserved.
    assert "ghp_a" not in out
    # The cap is value-class length (6-400). With prefix `ghp_a`
    # (5 chars) + 100 b's + 1000 x's + 1 \n = 1106 chars total,
    # the regex consumes the first 400 chars of the value
    # (`a` + 100 b's + 299 x's). The remaining 701 x's + \n are
    # preserved. (299 x's consumed is a one-off from the \n being
    # in the value class — fine, the cap still bounds over-match.)
    assert out.count("x") == 701, (
        f"expected 701 x's preserved, got {out.count('x')}"
    )


def test_sanitize_key_value_pattern_is_line_scoped() -> None:
    """`key=value` pattern does NOT span newlines (over-match risk).

    A permissive value class that includes whitespace lets a single
    match consume the next line's `key=` as part of THIS line's
    value, missing the second key. The key=value pattern keeps its
    value class to a single token (no whitespace) to prevent that
    false-negative. Wrap-case coverage comes from the prefix pattern
    in the next test.
    """
    text = (
        "config error: token=supersecretvalue12345\n"
        "api_key: \"AKIAIOSFODNN7EXAMPLE\"\n"
        "password=hunter2hunter2hunter2hunter2\n"
    )
    out = _sanitize_subprocess_output(text)
    # All three values redacted (line-scoped, one per line).
    assert "supersecretvalue12345" not in out
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "hunter2hunter2hunter2hunter2" not in out
    assert out.count("<REDACTED>") >= 3


def test_sanitize_redacts_authorization_with_wrapped_token() -> None:
    """An Authorization: Bearer line where the token wraps is fully redacted."""
    text = (
        "request failed: Authorization: Bearer\n"
        "  ghp_abcdefghijklmnopqrstuvwxyz012345\n"
    )
    out = _sanitize_subprocess_output(text)
    assert "ghp_abcdefghijklmnopqrstuvwxyz012345" not in out


def test_sanitize_caps_value_length_to_bound_over_redaction() -> None:
    """Value class is capped at 400 chars to prevent runaway over-redaction.

    A benign log line with a 1000-char value following ``token=`` must
    not consume the whole blob — the cap forces a finite match.
    """
    text = "token=" + "a" * 1000 + "\n"
    out = _sanitize_subprocess_output(text, tail_bytes=10_000)
    # Most of the 'a's should survive the cap (only up to 400 are
    # consumed by the value class).
    surviving_a_count = out.count("a")
    assert surviving_a_count >= 600, (
        f"cap under-matched: only {surviving_a_count} 'a' chars survived "
        f"(expected >= 600)"
    )


def test_sanitize_end_to_end_wrapped_token_does_not_reach_console(
    tmp_path: Path, mock_console: MagicMock,
) -> None:
    """End-to-end: a wrapped token in sync stderr must not reach console."""
    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )

    leak = (
        "Traceback:\n"
        "  ghp_abcdefghijklmnopqrstuvwxyz012345\n"
        "  6789ABCDEFGHIJKLMNOPQRSTUVWXYZ\n"
    )
    fake_sync = _completed(returncode=2, stderr=leak)

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=fake_sync,
        ),
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    leaked_substrings = (
        "ghp_abcdefghijklmnopqrstuvwxyz012345",
        "6789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
    for call in mock_console.print.call_args_list:
        rendered = " ".join(str(arg) for arg in call.args)
        for sub in leaked_substrings:
            assert sub not in rendered, (
                f"Wrapped token leaked to console: {sub!r} in {rendered!r}"
            )


# ---------------------------------------------------------------------------
# Path disclosure
# ---------------------------------------------------------------------------


def test_pass_message_redacts_home_directory(
    tmp_path: Path, mock_console: MagicMock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The PASS message must not disclose the user's home directory.

    Guards the log line that reads
    ``Gitignore-conformance passed for <path>``: the path is rendered
    home-relative (``~/Projects/oneiric``) so the OS account name never
    reaches the console or a log file.
    """
    home = tmp_path / "home"
    repo = home / "Projects" / "oneiric"
    repo.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    pm = _make_publish_manager(repo, mock_console)
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
        repo_path=repo,
    )

    with patch(
        "crackerjack.managers.publish_manager.check_repo_gitignore",
        return_value=conform,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    rendered = " ".join(
        str(arg) for call in mock_console.print.call_args_list for arg in call.args
    )
    assert "Gitignore-conformance passed for ~/Projects/oneiric" in rendered
    assert str(home) not in rendered, (
        f"Home directory leaked to console: {str(home)!r} in {rendered!r}"
    )


def test_drift_message_redacts_home_directory(
    tmp_path: Path, mock_console: MagicMock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The drift message must not disclose the user's home directory."""
    home = tmp_path / "home"
    repo = home / "Projects" / "oneiric"
    repo.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    pm = _make_publish_manager(repo, mock_console)
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
        repo_path=repo,
    )
    fake_sync = _completed(returncode=0)

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=fake_sync,
        ),
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    rendered = " ".join(
        str(arg) for call in mock_console.print.call_args_list for arg in call.args
    )
    assert str(home) not in rendered, (
        f"Home directory leaked to console: {str(home)!r} in {rendered!r}"
    )
