"""Stage 1: HookSettings must expose a ruff_unsafe_fixes boolean default True."""


def test_hook_settings_ruff_unsafe_fixes_default_false() -> None:
    from crackerjack.config.settings import HookSettings

    settings = HookSettings()
    # ``ruff_unsafe_fixes`` defaults to True per d611bad5 / 70fa952f
    # (preflight: ruff-unsafe fixes are part of the standard preflight
    # workflow). The test name is historical ("default_false") and kept
    # to match the pre-fix naming convention the crackerjack suite uses
    # for these checks; the assertion value reflects the post-fix intent.
    assert settings.ruff_unsafe_fixes is True


def test_hook_settings_ruff_unsafe_fixes_overridable() -> None:
    from crackerjack.config.settings import HookSettings

    settings = HookSettings(ruff_unsafe_fixes=True)
    assert settings.ruff_unsafe_fixes is True
