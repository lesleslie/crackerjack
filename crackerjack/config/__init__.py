from .hooks import (
    COMPREHENSIVE_STRATEGY,
    FAST_STRATEGY,
    HookConfigLoader,
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
)
from .settings import CrackerjackSettings

# Register settings with ACB dependency injection
from acb.depends import depends

depends.set(CrackerjackSettings, CrackerjackSettings())

__all__ = [
    "COMPREHENSIVE_STRATEGY",
    "FAST_STRATEGY",
    "HookConfigLoader",
    "HookDefinition",
    "HookStage",
    "HookStrategy",
    "RetryPolicy",
    "CrackerjackSettings",
]
