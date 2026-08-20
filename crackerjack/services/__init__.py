from __future__ import annotations

import typing as t

# Lazily-loaded submodule attributes. Keeping these out of the eager import
# chain means that ``import crackerjack.services.connection_pool`` (or any
# other submodule) does NOT trigger imports of every other submodule — some of
# which import ``crackerjack.models.protocols`` and ultimately reach
# ``crackerjack.config.mcp_settings_adapter`` -> ``mcp_common`` -> ``fastmcp``
# -> ``mcp.types``. That chain can fail when the test runner's ``sys.path``
# shim shadows the real ``mcp`` package (e.g.
# ``tests/unit/test_adapter_observability.py`` inserts the ``crackerjack/``
# source dir at ``sys.path[0]``). Symbols are loaded on first attribute access.
_LAZY_EXPORTS: dict[str, str] = {
    "CircuitBreakerState": "crackerjack.services.pycharm_mcp_integration",
    "LocalSequentialClient": "crackerjack.services.swarm_client",
    "MahavishnuSwarmClient": "crackerjack.services.swarm_client",
    "PyCharmMCPAdapter": "crackerjack.services.pycharm_mcp_integration",
    "SafeFileModifier": "crackerjack.services.file_modifier",
    "SearchResult": "crackerjack.services.pycharm_mcp_integration",
    "SwarmManager": "crackerjack.services.swarm_client",
    "SwarmMode": "crackerjack.services.swarm_client",
    "SwarmResult": "crackerjack.services.swarm_client",
    "SwarmTask": "crackerjack.services.swarm_client",
    "WorkflowInsights": "crackerjack.services.workflow_optimization",
    "WorkflowOptimizationEngine": "crackerjack.services.workflow_optimization",
    "WorkflowRecommendation": "crackerjack.services.workflow_optimization",
    "create_swarm_manager": "crackerjack.services.swarm_client",
}


def __getattr__(name: str) -> t.Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals().keys()))


__all__ = [
    "CircuitBreakerState",
    "LocalSequentialClient",
    "MahavishnuSwarmClient",
    "PyCharmMCPAdapter",
    "SafeFileModifier",
    "SearchResult",
    "SwarmManager",
    "SwarmMode",
    "SwarmResult",
    "SwarmTask",
    "WorkflowInsights",
    "WorkflowOptimizationEngine",
    "WorkflowRecommendation",
    "create_swarm_manager",
]