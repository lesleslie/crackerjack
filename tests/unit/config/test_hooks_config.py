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
    def test_zuban_disabled_by_default(self) -> None:
        hook = _find_hook("zuban")
        assert hook is not None, "zuban hook must remain in COMPREHENSIVE_HOOKS"
        assert hook.disabled is True

    @pytest.mark.unit
    def test_only_one_default_type_checker_active(self) -> None:
        type_checker_names = {"ty", "zuban"}
        active = [
            h for h in COMPREHENSIVE_HOOKS
            if h.name in type_checker_names and not h.disabled
        ]
        assert len(active) == 1, (
            f"Exactly one default type checker should be active, found: "
            f"{[h.name for h in active]}"
        )
        assert active[0].name == "ty"


class TestTask6Hooks:
    @pytest.mark.unit
    def test_complexipy_not_disabled_in_hooks(self) -> None:
        hook = _find_hook("complexipy")
        assert hook is not None, "complexipy hook must be in COMPREHENSIVE_HOOKS"
        assert hook.disabled is False, (
            "complexipy must be enabled (disabled=False) after Task 6"
        )

    @pytest.mark.unit
    def test_skylos_not_disabled_in_hooks(self) -> None:
        hook = _find_hook("skylos")
        assert hook is not None, "skylos hook must be in COMPREHENSIVE_HOOKS"
        assert hook.disabled is False, (
            "skylos must be enabled (disabled=False) after Task 6"
        )

    @pytest.mark.unit
    def test_cohesion_in_comprehensive_hooks(self) -> None:
        hook = _find_hook("cohesion")
        assert hook is not None, "cohesion HookDefinition must be in COMPREHENSIVE_HOOKS"
        assert hook.disabled is False, "cohesion must not be disabled"
