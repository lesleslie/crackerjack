"""Registration tests for the Phase 1.5 skill-coverage fast hook.

Wires ``pre_commit_skill_coverage_gate`` into ``crackerjack run`` via the
``FAST_HOOKS`` registry. Without this wiring the gate ships but never
fires when an operator invokes ``crackerjack run``.
"""

from __future__ import annotations

import pytest

from crackerjack.config.hooks import FAST_HOOKS, HookStage, SecurityLevel


class TestSkillCoverageHookRegistration:
    @pytest.mark.unit
    def test_skill_coverage_registered_in_fast_hooks(self) -> None:
        names = {h.name for h in FAST_HOOKS}
        assert "skill-coverage" in names, (
            "skill-coverage hook must be registered in FAST_HOOKS so "
            "`crackerjack run` invokes the Phase 1.5 gate"
        )

    @pytest.mark.unit
    def test_skill_coverage_command_invokes_pre_commit_entry_point(self) -> None:
        hook = next(h for h in FAST_HOOKS if h.name == "skill-coverage")
        assert hook.command == ["python", "-m", "crackerjack.hooks.pre_commit"], (
            "skill-coverage hook must delegate to the "
            "`python -m crackerjack.hooks.pre_commit` entry point"
        )

    @pytest.mark.unit
    def test_skill_coverage_stage_is_fast(self) -> None:
        hook = next(h for h in FAST_HOOKS if h.name == "skill-coverage")
        assert hook.stage is HookStage.FAST

    @pytest.mark.unit
    def test_skill_coverage_security_level_is_low(self) -> None:
        hook = next(h for h in FAST_HOOKS if h.name == "skill-coverage")
        assert hook.security_level is SecurityLevel.LOW

    @pytest.mark.unit
    def test_skill_coverage_does_not_accept_file_paths(self) -> None:
        hook = next(h for h in FAST_HOOKS if h.name == "skill-coverage")
        assert hook.accepts_file_paths is False

    @pytest.mark.unit
    def test_skill_coverage_does_not_retry_on_failure(self) -> None:
        hook = next(h for h in FAST_HOOKS if h.name == "skill-coverage")
        assert hook.retry_on_failure is False
