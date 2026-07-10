"""Test the env-var helpers for AI fix sandbox settings."""

from __future__ import annotations

import pytest

from crackerjack.core.autofix_coordinator import AutofixCoordinator


def test_get_ai_fix_use_sandbox_defaults_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CRACKERJACK_AI_FIX_USE_SANDBOX", raising=False)
    assert AutofixCoordinator._get_ai_fix_use_sandbox() is False


def test_get_ai_fix_use_sandbox_env_var_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_USE_SANDBOX", "1")
    assert AutofixCoordinator._get_ai_fix_use_sandbox() is True


def test_get_ai_fix_use_sandbox_env_var_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_USE_SANDBOX", "false")
    assert AutofixCoordinator._get_ai_fix_use_sandbox() is False


def test_get_ai_fix_sandbox_timeout_s_env_var_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_SANDBOX_TIMEOUT_S", "120")
    assert AutofixCoordinator._get_ai_fix_sandbox_timeout_s() == 120


def test_get_ai_fix_sandbox_timeout_s_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CRACKERJACK_AI_FIX_SANDBOX_TIMEOUT_S", raising=False)
    assert AutofixCoordinator._get_ai_fix_sandbox_timeout_s() == 300
