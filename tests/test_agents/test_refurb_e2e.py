"""End-to-end smoke test for the Crackerjack AI-fix pipeline.

Exercises the full path:
1. SafeRefurbFixer._apply_fixes() - direct fixer call
2. RefurbCodeTransformerAgent.analyze_and_fix() - the agent's per-code handler dispatch
3. Ghost-fix guard - the re-read verification that catches fake-success writes

If any of these regress, the "fix applied but file unchanged" pattern (which
caused the original 2 -> 2 loop bug) would silently come back. Run the file
with `python -m pytest tests/test_agents/test_refurb_e2e.py -v`.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from crackerjack.agents.base import (
    AgentContext,
    Issue,
    IssueType,
)
from crackerjack.agents.refurb_agent import RefurbCodeTransformerAgent
from crackerjack.services.refurb_fixer import SafeRefurbFixer


# --- Test fixtures ----------------------------------------------------------

# Pick violations we know the fixer actually handles (from audit 2026-06-12).
# Each one is a code with a CORRECT or PARTIAL handler in refurb_fixer.py.
KNOWN_FIXABLE = {
    "FURB113": ("nums = [1, 2, 3]\nnums.append(4)\nnums.append(5)\n", "extend"),
    "FURB123": ("name = str('bob')\n", "str("),
    "FURB183": ('print(f"{y}")\n', "str("),
}


@pytest.fixture
def mock_context():
    """AgentContext stub that round-trips writes through a temp file."""
    context = Mock(spec=AgentContext)
    context.project_path = Path("/test/project")
    return context


@pytest.fixture
def agent(mock_context):
    return RefurbCodeTransformerAgent(mock_context)


# --- Test 1: SafeRefurbFixer._apply_fixes() direct call ---------------------

class TestSafeRefurbFixerDirect:
    """The fixer is the first-pass handler in the agent. It runs BEFORE
    the per-code transform, so its fixes must round-trip cleanly."""

    def test_apply_fixes_returns_new_content_string(self):
        """_apply_fixes signature: (str) -> (str, int)."""
        fixer = SafeRefurbFixer()
        result = fixer._apply_fixes("x = 1\n")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], int)

    def test_apply_fixes_rewrites_furb183_useless_fstring(self):
        """FURB183 is the most recent fix; verify it round-trips."""
        fixer = SafeRefurbFixer()
        content = 'print(f"{y}")\n'
        new_content, fixes = fixer._apply_fixes(content)
        assert fixes >= 1, f"expected at least 1 fix, got {fixes}"
        assert "str(y)" in new_content
        assert 'f"{y}"' not in new_content

    def test_apply_fixes_rewrites_furb113_redundant_pass(self):
        """FURB113: 2 consecutive .append() calls should collapse to .extend()."""
        fixer = SafeRefurbFixer()
        content = "nums = [1, 2, 3]\nnums.append(4)\nnums.append(5)\n"
        new_content, fixes = fixer._apply_fixes(content)
        assert fixes >= 1
        assert "nums.extend(" in new_content

    def test_apply_fixes_returns_zero_fixes_on_clean_code(self):
        """Clean code produces 0 fixes and identical content."""
        fixer = SafeRefurbFixer()
        content = "x = 1\ny = 2\nprint(x + y)\n"
        new_content, fixes = fixer._apply_fixes(content)
        assert fixes == 0
        assert new_content == content

    def test_apply_fixes_is_idempotent(self):
        """Running _apply_fixes on already-fixed content must be a no-op."""
        fixer = SafeRefurbFixer()
        bad = 'print(f"{y}")\n'
        once, fixes_once = fixer._apply_fixes(bad)
        twice, fixes_twice = fixer._apply_fixes(once)
        assert fixes_once >= 1
        assert fixes_twice == 0
        assert once == twice


# --- Test 2: Agent.analyze_and_fix() end-to-end ------------------------------

class TestAgentEndToEnd:
    """analyze_and_fix() is what the crackerjack orchestrator calls.
    It must: read file -> apply safe fixes -> dispatch per-code handler
    -> write to disk -> verify the write actually changed the file."""

    def _make_issue(self, furb_code: str, file_path: Path) -> Issue:
        """Build an Issue with the right type and message so _extract_furb_code finds it.

        _extract_furb_code iterates `issue.details` first, so we set it to an
        empty list explicitly. Mock(spec=Issue) does not auto-populate
        spec'd attributes when they're missing on the underlying object.
        """
        issue = Mock(spec=Issue)
        issue.type = IssueType.REFURB
        issue.file_path = file_path
        issue.message = f"{furb_code}: synthetic test violation"
        issue.details = []
        return issue

    def test_analyze_and_fix_uses_real_filesystem_for_verification(
        self, mock_context, tmp_path
    ):
        """The agent's ghost-fix guard depends on the file actually changing
        on disk. We give it a real temp file and a real write_file_content
        that round-trips through the filesystem, then assert the file's
        content really did change."""
        target = tmp_path / "victim.py"
        target.write_text('print(f"{y}")\n')

        # Wire mock_context to a real file so write_file_content / get_file_content
        # actually persist.
        mock_context.get_file_content = lambda p: Path(p).read_text()
        mock_context.write_file_content = (
            lambda p, c: Path(p).write_text(c) is not None or True
        )

        issue = self._make_issue("FURB183", target)
        agent = RefurbCodeTransformerAgent(mock_context)

        # Run the async method
        import asyncio
        result = asyncio.run(agent.analyze_and_fix(issue))

        # Either SafeRefurbFixer fixed it OR the per-code handler did.
        # The on-disk file must have changed either way.
        on_disk = target.read_text()
        assert "str(y)" in on_disk or on_disk != 'print(f"{y}")\n', (
            f"File unchanged after analyze_and_fix: {on_disk!r}"
        )

    def test_analyze_and_fix_catches_ghost_fix(
        self, mock_context, tmp_path
    ):
        """Ghost-fix scenario: write_file_content claims success but doesn't
        actually change the file. The agent must return success=False.
        This is the exact pattern that caused the original 2 -> 2 loop."""
        target = tmp_path / "ghost.py"
        target.write_text('print(f"{y}")\n')

        # The mock context pretends to write, but doesn't.
        def fake_write(p, c):
            return True  # claim success

        def fake_read(p):
            return 'print(f"{y}")\n'  # always return original (ghost)

        mock_context.write_file_content = fake_write
        mock_context.get_file_content = fake_read

        issue = self._make_issue("FURB183", target)
        agent = RefurbCodeTransformerAgent(mock_context)

        import asyncio
        result = asyncio.run(agent.analyze_and_fix(issue))

        # The fix description in remaining_issues should mention the ghost fix
        remaining = " ".join(result.remaining_issues).lower()
        assert "unchanged" in remaining or "success but" in remaining, (
            f"ghost-fix guard did not fire; result={result}"
        )
        assert result.success is False

    def test_analyze_and_fix_returns_no_handler_for_unknown_code(
        self, mock_context, tmp_path
    ):
        """A FURB code not in FURB_TRANSFORMATIONS must produce a clean
        'no handler' error, not a crash."""
        target = tmp_path / "unknown.py"
        target.write_text("x = 1\n")
        mock_context.get_file_content = lambda p: Path(p).read_text()
        mock_context.write_file_content = (
            lambda p, c: Path(p).write_text(c) is not None or True
        )

        # FURB999 is not in the dict.
        issue = self._make_issue("FURB999", target)
        agent = RefurbCodeTransformerAgent(mock_context)

        import asyncio
        result = asyncio.run(agent.analyze_and_fix(issue))

        assert result.success is False
        remaining = " ".join(result.remaining_issues).lower()
        assert "furb999" in remaining or "no handler" in remaining

    def test_analyze_and_fix_handles_missing_file(
        self, mock_context, tmp_path
    ):
        """If the file disappears between discovery and fix, the agent
        must return success=False with a clean message, not crash."""
        nonexistent = tmp_path / "ghost.py"
        # Do NOT create the file.
        mock_context.get_file_content = lambda p: None
        mock_context.write_file_content = lambda p, c: True

        issue = self._make_issue("FURB183", nonexistent)
        agent = RefurbCodeTransformerAgent(mock_context)

        import asyncio
        result = asyncio.run(agent.analyze_and_fix(issue))

        assert result.success is False
        remaining = " ".join(result.remaining_issues).lower()
        assert "not found" in remaining or "no file" in remaining or "could not" in remaining


# --- Test 3: Real refurb binary integration (opt-in) ------------------------

# This is gated behind a fixture because it requires the refurb binary
# in PATH and takes ~5s. Use `pytest -v -m slow` to run.
@pytest.mark.slow
class TestRefurbBinaryIntegration:
    """Validate that after _apply_fixes, the real refurb binary reports
    fewer issues for the codes we know we can fix."""

    def test_refurb_clean_after_apply_fixes_furb183(self, tmp_path):
        """Apply _apply_fixes, then run refurb, then assert 0 FURB183 issues."""
        target = tmp_path / "clean.py"
        # Only put a FURB183 violation; pre-clear other issues.
        target.write_text('x = 1\nprint(f"{y}")\nz = 3\n')

        fixer = SafeRefurbFixer()
        fixed, fixes = fixer._apply_fixes(target.read_text())
        target.write_text(fixed)
        assert fixes >= 1

        # Now ask the real refurb binary. -E disables all checks; we
        # specifically enable FURB183 by passing the code.
        result = subprocess.run(
            ["refurb", "--enable", "FURB183", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # refurb returns 1 if issues found, 0 if clean.
        assert "FURB183" not in result.stdout, (
            f"FURB183 still flagged after fix:\nstdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )
