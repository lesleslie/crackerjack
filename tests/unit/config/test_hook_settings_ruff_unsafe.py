"""Stage 1: HookSettings must expose a ruff_unsafe_fixes boolean default False."""


def test_hook_settings_ruff_unsafe_fixes_default_false() -> None:
    from crackerjack.config.settings import HookSettings

    settings = HookSettings()
    assert settings.ruff_unsafe_fixes is False


def test_hook_settings_ruff_unsafe_fixes_overridable() -> None:
    from crackerjack.config.settings import HookSettings

    settings = HookSettings(ruff_unsafe_fixes=True)
    assert settings.ruff_unsafe_fixes is True
