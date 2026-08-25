"""Tests for ``_PhaseTask.run`` error propagation and verbose-mode detail dumping.

These tests guard against the regression where a phase returning ``False``
produced only ``workflow-task-failed: <task_name>`` to the user, even though
``session.fail_task(...)`` had already recorded the real error message.
After the fix, the RuntimeError includes the recorded error_message and
verbose mode dumps the recorded details (multi-line) to stderr.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest

from crackerjack.runtime.oneiric_workflow import _PhaseTask


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_runner_true_returns_true() -> None:
    async def go() -> None:
        result = await _PhaseTask("noop", lambda: True).run()
        assert result is True

    _run(go())


def test_runner_false_without_provider_keeps_bare_name() -> None:
    """Without an error_provider, the message is still bare.

    The wrapper should never lose the *task name*, even when no session is
    wired up (e.g. tests, custom oneiric configs without progress tracking).
    """

    async def go() -> None:
        with pytest.raises(RuntimeError) as excinfo:
            await _PhaseTask("documentation_cleanup", lambda: False).run()
        assert str(excinfo.value) == "workflow-task-failed: documentation_cleanup"

    _run(go())


def test_runner_false_with_provider_includes_error_message() -> None:
    """When the provider returns a recorded error_message, it is included.

    This is the central bug fix: previously, the user saw only
    ``workflow-task-failed: documentation_cleanup`` even when the
    frontmatter validator had already recorded ``frontmatter validation
    failed: 11 errors``.
    """

    async def go() -> None:
        with pytest.raises(RuntimeError) as excinfo:
            await _PhaseTask(
                "documentation_cleanup",
                lambda: False,
                error_provider=lambda: (
                    "frontmatter validation failed: 11 errors",
                    None,
                ),
            ).run()
        msg = str(excinfo.value)
        assert msg.startswith("workflow-task-failed: documentation_cleanup: ")
        assert "frontmatter validation failed: 11 errors" in msg

    _run(go())


def test_runner_raises_chains_into_runtime_error() -> None:
    """If the runner itself raises, the original exception is chained."""

    class BoomError(RuntimeError):
        pass

    def runner() -> None:
        raise BoomError("disk full")

    async def go() -> None:
        with pytest.raises(RuntimeError) as excinfo:
            await _PhaseTask("cleanup_docs", runner).run()
        # The original exception is the chained __cause__
        assert isinstance(excinfo.value.__cause__, BoomError)
        assert "disk full" in str(excinfo.value)

    _run(go())


def test_verbose_dumps_details_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Verbose mode prints the multi-line details block to stderr."""

    async def go() -> None:
        details = (
            "  2 frontmatter error(s):\n"
            "  docs/adr/015.md status_invalid: status 'reference' not in [...]\n"
            "  docs/adr/015.md role_invalid: role 'adr' not in [...]"
        )
        with contextlib.suppress(RuntimeError):
            await _PhaseTask(
                "documentation_cleanup",
                lambda: False,
                verbose=True,
                error_provider=lambda: (
                    "frontmatter validation failed: 2 errors",
                    details,
                ),
            ).run()

    _run(go())
    captured = capsys.readouterr()
    assert "[verbose] documentation_cleanup failure details:" in captured.err
    assert "docs/adr/015.md status_invalid" in captured.err
    assert "docs/adr/015.md role_invalid" in captured.err


def test_non_verbose_skips_details_dump(capsys: pytest.CaptureFixture[str]) -> None:
    """Default mode does NOT dump details to stderr (still records them in the error message)."""

    async def go() -> None:
        with pytest.raises(RuntimeError):
            await _PhaseTask(
                "documentation_cleanup",
                lambda: False,
                verbose=False,
                error_provider=lambda: (
                    "frontmatter validation failed: 2 errors",
                    "should-not-appear",
                ),
            ).run()

    _run(go())
    captured = capsys.readouterr()
    assert "should-not-appear" not in captured.err


def test_provider_exception_falls_back_to_bare_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An exception inside error_provider is logged, but does not mask the failure."""

    async def go() -> None:
        def broken() -> tuple[str | None, str | None]:
            raise RuntimeError("provider broken")

        with pytest.raises(RuntimeError) as excinfo:
            await _PhaseTask(
                "documentation_cleanup",
                lambda: False,
                error_provider=broken,
            ).run()
        # The bare task name still appears — provider failure does NOT
        # silently swallow the workflow error.
        assert str(excinfo.value) == "workflow-task-failed: documentation_cleanup"

    _run(go())
