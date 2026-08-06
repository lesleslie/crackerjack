"""Stage 0: default ruff-check must not pass --unsafe-fixes."""

from __future__ import annotations


def test_ruff_check_default_omits_unsafe_fixes() -> None:
    from crackerjack.config.tool_commands import get_tool_command

    cmd = get_tool_command("ruff-check")

    assert "--unsafe-fixes" not in cmd, (
        f"ruff-check default must not include --unsafe-fixes; got {cmd!r}"
    )
    assert "--fix" in cmd, "ruff-check default must still apply safe fixes"
    assert "--output-format" in cmd
    assert "json" in cmd
    assert "./crackerjack" in cmd


def test_ruff_check_includes_unsafe_fixes_when_settings_allow() -> None:
    from crackerjack.config.settings import HookSettings
    from crackerjack.config.tool_commands import get_tool_command

    settings = HookSettings(ruff_unsafe_fixes=True)
    cmd = get_tool_command("ruff-check", settings=settings)

    assert "--unsafe-fixes" in cmd, (
        f"ruff-check must emit --unsafe-fixes when settings allow; got {cmd!r}"
    )
    assert "--fix" in cmd
