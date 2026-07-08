"""Test the new AI fix sandbox settings fields."""

from __future__ import annotations

from crackerjack.config.settings import AISettings


def test_ai_fix_use_sandbox_defaults_to_false() -> None:
    s = AISettings()
    assert s.ai_fix_use_sandbox is False


def test_ai_fix_sandbox_timeout_defaults_to_300() -> None:
    s = AISettings()
    assert s.ai_fix_sandbox_timeout_s == 300


def test_ai_fix_use_sandbox_can_be_enabled() -> None:
    s = AISettings(ai_fix_use_sandbox=True)
    assert s.ai_fix_use_sandbox is True


def test_ai_fix_sandbox_timeout_can_be_overridden() -> None:
    s = AISettings(ai_fix_sandbox_timeout_s=120)
    assert s.ai_fix_sandbox_timeout_s == 120