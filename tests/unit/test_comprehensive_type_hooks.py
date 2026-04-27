from types import SimpleNamespace
from unittest.mock import patch

from crackerjack.config.hooks import HookConfigLoader, HookStage


def test_comprehensive_strategy_is_type_tool_opt_in_by_default() -> None:
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
