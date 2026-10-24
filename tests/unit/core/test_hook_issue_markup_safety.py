"""Regression tests: hook issue strings must never be parsed as Rich markup.

Hook issue strings are *external tool output*, not trusted display text. The
osv-scanner formatter emits ``[{source_path}]`` -- a bracketed absolute path
(see ``HookExecutor._format_osv_vulnerability_message``). Rich treats
``[...]`` as a markup tag, so a path beginning with ``/`` is read as a
*closing* tag with no matching open tag. Rich then raises ``MarkupError``,
which escaped the ``fast_hooks`` task and aborted the whole run:

    Workflow failed: Task fast_hooks failed after 1 attempt(s): closing tag
    '[/Users/les/Projects/crackerjack/uv.lock]' at position 115 doesn't match
    any open tag

The same class of bug has a second, quieter failure mode: a bracket group
whose contents look like a Rich style name (``[low,medium]``) is silently
swallowed, so the issue text vanishes from the output instead of raising.

The fix belongs at the render boundary, not in each tool's formatter: tool
output is arbitrary text, and no formatter can guarantee its output is
markup-safe. Rendering must therefore disable markup parsing.
"""

from __future__ import annotations

import typing as t
from pathlib import Path

import pytest

from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.executors.async_hook_executor import AsyncHookExecutor
from crackerjack.models.task import HookResult

# Mirrors the real osv-scanner issue line produced by
# ``HookExecutor._format_osv_vulnerability_message``.
OSV_ISSUE = (
    "fastmcp==4.1.0 GHSA-7xgj-8392-5q4r - FastMCP: Post-transform component "
    "authorization is skipped on direct calls "
    "[/Users/les/Projects/crackerjack/uv.lock]"
)

# A bracket group whose contents look like a Rich style name. Rich swallows
# these silently when markup parsing is enabled.
TAGLIKE_ISSUE = "gitleaks finding [low,medium] hardcoded secret"


def _normalize(text: str) -> str:
    """Collapse whitespace so assertions survive Rich's word wrapping.

    Rich hard-wraps console output at the terminal width, inserting
    newlines mid-sentence. Comparing raw substrings against captured output
    would therefore fail on layout rather than on content.
    """
    return " ".join(text.split())


def _render(console: CrackerjackConsole, render: t.Callable[[], None]) -> str:
    """Run ``render`` against a real console and return the captured text.

    A mocked console would never raise ``MarkupError``, so the regression
    would go unnoticed.
    """
    with console.capture() as capture:
        render()
    return capture.get()


@pytest.fixture
def coordinator(tmp_path: Path) -> PhaseCoordinator:
    """PhaseCoordinator wired to a throwaway directory."""
    coord = PhaseCoordinator()
    coord.pkg_path = tmp_path
    return coord


class TestPrintHookIssues:
    """``_print_hook_issues`` renders external tool output verbatim."""

    def test_bracket_path_does_not_raise(self, coordinator: PhaseCoordinator) -> None:
        """A bracketed absolute path must not be read as a markup tag."""
        result = HookResult(
            id="h1",
            name="osv-scanner",
            status="failed",
            issues_found=[OSV_ISSUE],
        )
        console = CrackerjackConsole()
        coordinator.console = console

        output = _render(console, lambda: coordinator._print_hook_issues(result))

        assert _normalize(OSV_ISSUE) in _normalize(output)

    def test_taglike_bracket_group_is_preserved(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """A bracket group that looks like a style must not be swallowed."""
        result = HookResult(
            id="h1",
            name="gitleaks",
            status="failed",
            issues_found=[TAGLIKE_ISSUE],
        )
        console = CrackerjackConsole()
        coordinator.console = console

        output = _render(console, lambda: coordinator._print_hook_issues(result))

        assert _normalize(TAGLIKE_ISSUE) in _normalize(output)


class TestDisplayIssueDetails:
    """``_display_issue_details`` renders external tool output verbatim."""

    def test_bracket_path_does_not_raise(self, coordinator: PhaseCoordinator) -> None:
        """A bracketed absolute path must not be read as a markup tag."""
        result = HookResult(
            id="h1",
            name="osv-scanner",
            status="failed",
            issues_found=[OSV_ISSUE],
        )
        console = CrackerjackConsole()
        coordinator.console = console

        output = _render(console, lambda: coordinator._display_issue_details(result))

        assert _normalize(OSV_ISSUE) in _normalize(output)


class TestDisplayErrorMessage:
    """``_display_error_message`` renders tool stderr verbatim."""

    def test_bracket_path_does_not_raise(self, coordinator: PhaseCoordinator) -> None:
        """A bracketed path in tool stderr must not abort the run."""
        result = HookResult(
            id="h1",
            name="osv-scanner",
            status="failed",
            error_message="scan failed for [/Users/les/Projects/crackerjack/uv.lock]",
        )
        console = CrackerjackConsole()
        coordinator.console = console

        output = _render(console, lambda: coordinator._display_error_message(result))

        assert "[/Users/les/Projects/crackerjack/uv.lock]" in _normalize(output)


class TestAsyncHookExecutorDisplay:
    """The async executor's issue renderer has the same exposure."""

    def test_bracket_path_does_not_raise(self, tmp_path: Path) -> None:
        """A bracketed absolute path must not be read as a markup tag."""
        console = CrackerjackConsole()
        executor = AsyncHookExecutor(console=console, pkg_path=tmp_path)
        result = HookResult(
            id="h1",
            name="osv-scanner",
            status="failed",
            issues_found=[OSV_ISSUE],
        )

        output = _render(console, lambda: executor._display_hook_result(result))

        assert _normalize(OSV_ISSUE) in _normalize(output)
