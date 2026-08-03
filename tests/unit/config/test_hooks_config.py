from __future__ import annotations

import pytest

from crackerjack.config.hooks import COMPREHENSIVE_HOOKS


def _find_hook(name: str):  # type: ignore[return]
    for hook in COMPREHENSIVE_HOOKS:
        if hook.name == name:
            return hook


class TestTyDefault:
    @pytest.mark.unit
    def test_ty_in_comprehensive_hooks_by_default(self) -> None:
        hook = _find_hook("ty")
        assert hook is not None, "ty hook must be in COMPREHENSIVE_HOOKS"

    @pytest.mark.unit
    def test_ty_not_disabled_by_default(self) -> None:
        hook = _find_hook("ty")
        assert hook is not None
        assert hook.disabled is False

    @pytest.mark.unit
    def test_zuban_opt_in_via_auto_run(self) -> None:
        # Per commit 13be8c1c (feat: disable zuban LSP by default — ty is the
        # new default type checker), zuban is opt-in via `settings.hooks.enable_zuban`.
        # The hook is still registered in COMPREHENSIVE_HOOKS so users can flip
        # the flag, but it must not auto-run. The canonical "active" filter
        # (see crackerjack/config/hooks.py lines 467 and 483) is
        # `auto_run and not disabled`, so zuban is excluded by auto_run=False.
        hook = _find_hook("zuban")
        assert hook is not None, "zuban hook must remain in COMPREHENSIVE_HOOKS"
        assert hook.auto_run is False, "zuban must be opt-in (auto_run=False)"

    @pytest.mark.unit
    def test_only_one_default_type_checker_active(self) -> None:
        # The canonical "active" filter is `auto_run and not disabled`. After
        # commit 13be8c1c flipped the default to ty and the 0.68.0 release
        # added the optional zuban entry, only ty satisfies both clauses.
        type_checker_names = {"ty", "zuban"}
        active = [
            h for h in COMPREHENSIVE_HOOKS
            if h.name in type_checker_names and h.auto_run and not h.disabled
        ]
        assert len(active) == 1, (
            f"Exactly one default type checker should be active, found: "
            f"{[h.name for h in active]}"
        )
        assert active[0].name == "ty"


class TestTask6Hooks:
    @pytest.mark.unit
    def test_complexipy_disabled_after_pyscn_migration(self) -> None:
        # Per commit b6b78b1d (refactor(hooks): disable skylos+complexipy,
        # align thresholds, re-task pyscn), complexipy is intentionally
        # disabled — pyscn's cyclomatic complexity + JSON parsing supersedes
        # it at ~60s vs ~10min. Re-enable by flipping disabled=False in
        # COMPREHENSIVE_HOOKS. This test pins the design decision.
        hook = _find_hook("complexipy")
        assert hook is not None, "complexipy hook must be in COMPREHENSIVE_HOOKS"
        assert hook.disabled is True, (
            "complexipy must be disabled (replaced by pyscn on 2026-06-29)"
        )

    @pytest.mark.unit
    def test_skylos_disabled_after_pyscn_migration(self) -> None:
        # Per commit b6b78b1d, skylos is intentionally disabled — pyscn's
        # CFG-based dead-code detection replaces it. Saves ~7min/runtime.
        # Re-enable by flipping disabled=False in COMPREHENSIVE_HOOKS.
        hook = _find_hook("skylos")
        assert hook is not None, "skylos hook must be in COMPREHENSIVE_HOOKS"
        assert hook.disabled is True, (
            "skylos must be disabled (replaced by pyscn on 2026-06-29)"
        )

    @pytest.mark.unit
    def test_cohesion_in_comprehensive_hooks(self) -> None:
        hook = _find_hook("cohesion")
        assert hook is not None, "cohesion HookDefinition must be in COMPREHENSIVE_HOOKS"
        assert hook.disabled is False, "cohesion must not be disabled"
