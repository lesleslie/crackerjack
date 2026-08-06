"""Stage 1: HookDefinition must expose allow_unsafe_fixes defaulting to False."""


def test_hook_definition_allow_unsafe_fixes_default_false() -> None:
    from crackerjack.config.hooks import HookDefinition

    definition = HookDefinition(name="ruff-check")
    assert definition.allow_unsafe_fixes is False


def test_ruff_check_definition_can_opt_in() -> None:
    from crackerjack.config.hooks import HookDefinition

    definition = HookDefinition(name="ruff-check", allow_unsafe_fixes=True)
    assert definition.allow_unsafe_fixes is True
