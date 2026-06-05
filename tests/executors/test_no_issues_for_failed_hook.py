"""Tests for HookExecutor._handle_no_issues_for_failed_hook.

Regression: when a reporting tool (e.g. lychee) exits non-zero but the JSON
parser found 0 issues, the user previously saw "FAILED" with 0 issues and no
indication of why. These tests pin the corrected fallback behaviour.
"""

from unittest.mock import MagicMock

from crackerjack.executors.hook_executor import HookExecutor


def _make_executor() -> HookExecutor:
    """Build a HookExecutor bypassing __init__ (we only need the helper)."""
    executor = HookExecutor.__new__(HookExecutor)
    executor.debug = False
    executor.console = MagicMock()
    return executor


def _make_result(*, returncode: int, stdout: str, stderr: str) -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestHandleNoIssuesForFailedHook:
    """Pin the fallback behaviour for hooks that fail with no parsed issues."""

    def test_uses_stderr_when_present(self) -> None:
        """stderr usually holds the real error for reporting tools - prefer it."""
        executor = _make_executor()
        result = _make_result(
            returncode=2,
            stdout='{"errors": 0, "error_map": {}}',
            stderr="ERROR: rate limited by weaviate.io\n",
        )

        out = executor._handle_no_issues_for_failed_hook("failed", [], result)

        assert out == ["ERROR: rate limited by weaviate.io"]

    def test_returns_hint_when_only_json_stdout(self) -> None:
        """Avoid dumping huge JSON - return a short hint instead."""
        executor = _make_executor()
        result = _make_result(
            returncode=2,
            stdout='{"errors": 0, "error_map": {}}',
            stderr="",
        )

        out = executor._handle_no_issues_for_failed_hook("failed", [], result)

        assert len(out) == 1
        assert "2" in out[0]
        assert "no parseable issues" in out[0]

    def test_uses_stdout_when_text(self) -> None:
        """Text output should still be surfaced as error lines (legacy behaviour)."""
        executor = _make_executor()
        result = _make_result(
            returncode=1,
            stdout="panic: connection refused\nat /path/to/file",
            stderr="",
        )

        out = executor._handle_no_issues_for_failed_hook("failed", [], result)

        assert out == ["panic: connection refused", "at /path/to/file"]

    def test_no_op_when_hook_passed(self) -> None:
        """A passed hook never needs a fallback - leave issues alone."""
        executor = _make_executor()
        result = _make_result(returncode=0, stdout="", stderr="")

        out = executor._handle_no_issues_for_failed_hook("passed", [], result)

        assert out == []

    def test_preserves_existing_issues(self) -> None:
        """If parsing already produced issues, the fallback must not clobber them."""
        executor = _make_executor()
        result = _make_result(
            returncode=2,
            stdout="",
            stderr="should not appear in output",
        )

        out = executor._handle_no_issues_for_failed_hook(
            "failed",
            ["existing issue"],
            result,
        )

        assert out == ["existing issue"]

    def test_skips_empty_stderr_lines(self) -> None:
        """Blank lines in stderr should not become empty 'issues'."""
        executor = _make_executor()
        result = _make_result(
            returncode=1,
            stdout='{"errors": 0}',
            stderr="\n\nreal error\n\n",
        )

        out = executor._handle_no_issues_for_failed_hook("failed", [], result)

        assert out == ["real error"]

    def test_caps_stderr_at_ten_lines(self) -> None:
        """Don't flood the results panel with thousands of stderr lines."""
        executor = _make_executor()
        stderr = "\n".join(f"line {i}" for i in range(50))
        result = _make_result(returncode=1, stdout='{"errors": 0}', stderr=stderr)

        out = executor._handle_no_issues_for_failed_hook("failed", [], result)

        assert len(out) == 10
        assert out[0] == "line 0"
        assert out[-1] == "line 9"
