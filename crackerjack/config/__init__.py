# Register settings with ACB dependency injection
from acb.depends import depends

from .hooks import (
    COMPREHENSIVE_STRATEGY,
    FAST_STRATEGY,
    HookConfigLoader,
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
)
from .loader import load_settings, load_settings_async
from .settings import CrackerjackSettings

# Load settings from YAML files (synchronous for module-level initialization)
# Configuration files: settings/crackerjack.yaml + settings/local.yaml (gitignored)
# Priority: local.yaml > crackerjack.yaml > defaults
depends.set(CrackerjackSettings, CrackerjackSettings.load())

__all__ = [
    "COMPREHENSIVE_STRATEGY",
    "FAST_STRATEGY",
    "HookConfigLoader",
    "HookDefinition",
    "HookStage",
    "HookStrategy",
    "RetryPolicy",
    "CrackerjackSettings",
    "load_settings",
    "load_settings_async",
]
