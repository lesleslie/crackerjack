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