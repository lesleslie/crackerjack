from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from crackerjack.config.hooks import HookConfigLoader, HookStage


def test_comprehensive_strategy_excludes_type_tools_when_disabled() -> None:
    settings = SimpleNamespace(
        hooks=SimpleNamespace(enable_ty=False, enable_pyrefly=False),
        adapter_timeouts=SimpleNamespace(ty_timeout=120, pyrefly_timeout=120),
    )

    with patch("crackerjack.config.load_settings", return_value=settings):
        strategy = HookConfigLoader.load_strategy("comprehensive")

    hook_names = [hook.name for hook in strategy.hooks]
    assert "ty" not in hook_names
    assert "pyrefly" not in hook_names


def test_comprehensive_strategy_can_enable_type_tools_explicitly() -> None:
    settings = SimpleNamespace(
        hooks=SimpleNamespace(enable_ty=True, enable_pyrefly=True),
        adapter_timeouts=SimpleNamespace(ty_timeout=91, pyrefly_timeout=92),
    )

    with patch("crackerjack.config.load_settings", return_value=settings):
        strategy = HookConfigLoader.load_strategy("comprehensive")

    ty_hook = next((hook for hook in strategy.hooks if hook.name == "ty"), None)
    pyrefly_hook = next(
        (hook for hook in strategy.hooks if hook.name == "pyrefly"), None
    )

    assert ty_hook is not None
    assert pyrefly_hook is not None
    assert ty_hook.stage == HookStage.COMPREHENSIVE
    assert pyrefly_hook.stage == HookStage.COMPREHENSIVE
    assert ty_hook.accepts_file_paths is True
    assert pyrefly_hook.accepts_file_paths is True
    assert ty_hook.timeout == 91
    assert pyrefly_hook.timeout == 92


def test_shipped_default_enables_ty() -> None:
    """ty is the primary type checker and must be active out of the box.

    REGRESSION GUARD. Every other test in this module injects an explicit
    enable_ty value, so none of them cover the value that actually ships.
    That blind spot let 370983cf (2026-08-03) demote ty from auto_run=True to
    opt-in while the whole suite stayed green — type checking was silently off
    for every consumer that upgraded past crackerjack 0.70.x.

    ty replaced zuban as primary; zuban stays opt-in. If this fails, do not
    "fix" it by flipping the assertion — that is exactly how the regression
    happened the first time.
    """
    from crackerjack.config.settings import HookSettings

    defaults = HookSettings()

    assert defaults.enable_ty is True, (
        "shipped enable_ty default is False — ty is the primary type checker "
        "and must be active by default; see 370983cf"
    )
    assert defaults.enable_zuban is False, (
        "zuban was replaced by ty as primary and must remain opt-in"
    )


def test_shipped_settings_yaml_does_not_disable_ty() -> None:
    """The repo's own settings YAML must not switch the primary checker off.

    settings/crackerjack.yaml has carried ``enable_ty: false`` since 2025-10-09,
    predating the ty migration. It was inert while the static ty hook still had
    auto_run=True, then became load-bearing after 370983cf — a dormant config
    value silently disabling type checking without changing any code.
    """
    settings_path = (
        Path(__file__).resolve().parents[2] / "settings" / "crackerjack.yaml"
    )
    if not settings_path.is_file():
        pytest.skip("settings/crackerjack.yaml not present")

    data = yaml.safe_load(settings_path.read_text()) or {}

    assert data.get("enable_ty") is not False, (
        "settings/crackerjack.yaml sets enable_ty: false, which disables the "
        "primary type checker for this repo regardless of the code default"
    )
