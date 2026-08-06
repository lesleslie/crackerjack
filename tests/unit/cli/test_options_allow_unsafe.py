"""Stage 1: --allow-unsafe-fixes and --safe-only are wired into options."""


def test_allow_unsafe_fixes_default_false() -> None:
    from crackerjack.cli import options

    assert options.allow_unsafe_fixes is False


def test_safe_only_default_false() -> None:
    from crackerjack.cli import options

    assert options.safe_only is False
