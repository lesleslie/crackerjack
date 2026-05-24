"""Centralized reset for all Crackerjack global singletons and caches.

This module provides reset_all_singletons() to tear down global state between tests,
preventing test pollution from shared singletons, caches, and module-level instances.

Usage:
    from tests.conftest_reset import reset_all_singletons
    reset_all_singletons()
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.executors.hook_lock_manager import HookLockManager


@contextmanager
def reset_hook_lock_manager():
    """Reset HookLockManager singleton."""
    from crackerjack.executors.hook_lock_manager import HookLockManager

    # Cancel heartbeat tasks and reset singleton
    try:
        existing = HookLockManager._instance
        if existing is not None:
            for task in existing._heartbeat_tasks.values():
                if task and not task.done():
                    task.cancel()
            existing._heartbeat_tasks.clear()
            existing._active_global_locks.clear()
    except Exception:
        pass

    original_instance = HookLockManager._instance
    original_initialized = HookLockManager._initialized
    HookLockManager._instance = None
    HookLockManager._initialized = False

    try:
        yield
    finally:
        HookLockManager._instance = None
        HookLockManager._initialized = False


def reset_timeout_manager() -> None:
    """Reset global AsyncTimeoutManager."""
    from crackerjack.core import timeout_manager

    timeout_manager._global_timeout_manager = None


def reset_service_watchdog() -> None:
    """Reset global ServiceWatchdog."""
    from crackerjack.core import service_watchdog

    service_watchdog._global_watchdog = None


def reset_metrics_collector() -> None:
    """Reset global MetricsCollector."""
    from crackerjack.services import metrics

    if metrics._metrics_collector is not None:
        try:
            metrics._metrics_collector.close()
        except Exception:
            pass
    metrics._metrics_collector = None


def reset_performance_monitor() -> None:
    """Reset global AsyncPerformanceMonitor via ContextVar."""
    from crackerjack.core.performance_monitor import _performance_monitor_context

    _performance_monitor_context.set(None)


def reset_intelligent_system() -> None:
    """Reset global IntelligentAgentSystem."""
    from crackerjack.intelligence import integration

    integration._intelligent_system_instance = None


def reset_agent_orchestrator() -> None:
    """Reset global AgentOrchestrator."""
    from crackerjack.intelligence import agent_orchestrator

    agent_orchestrator._orchestrator_instance = None


def reset_learning_system() -> None:
    """Reset global AdaptiveLearningSystem."""
    from crackerjack.intelligence import adaptive_learning

    adaptive_learning._learning_system_instance = None


def reset_agent_registry() -> None:
    """Reset global AgentRegistry instance."""
    from crackerjack.intelligence.agent_registry import agent_registry_instance

    # Reset internal state if initialize was called
    agent_registry_instance._agents.clear()
    agent_registry_instance._initialized = False
    agent_registry_instance._lock = asyncio.Lock()


def reset_issue_embedder() -> None:
    """Reset global IssueEmbedder."""
    from crackerjack.memory import issue_embedder

    issue_embedder._embedder_instance = None


def reset_fallback_embedder() -> None:
    """Reset global FallbackIssueEmbedder."""
    from crackerjack.memory import fallback_embedder

    fallback_embedder._embedder_instance = None


def reset_connection_pool() -> None:
    """Reset global HTTPConnectionPool."""
    from crackerjack.services import connection_pool

    connection_pool._global_pool = None


def reset_structlog() -> None:
    """Reset structlog defaults."""
    try:
        import structlog

        structlog.reset_defaults()
    except Exception:
        pass


def clear_lru_caches() -> None:
    """Clear all LRU caches in the codebase."""
    # tool_commands.py
    try:
        from crackerjack.config import tool_commands

        tool_commands.get_tool_command.cache_clear()
        tool_commands.get_all_tool_commands.cache_clear()
    except Exception:
        pass

    # _git_utils.py
    try:
        from crackerjack.tools import _git_utils

        _git_utils.get_git_root.cache_clear()
        _git_utils.get_git_tracked_files.cache_clear()
        _git_utils.get_files_by_extension.cache_clear()
        _git_utils._load_gitignore_spec.cache_clear()
    except Exception:
        pass


def clear_oneiric_modules() -> None:
    """Clear oneiric modules from sys.modules."""
    modules_to_clear = [k for k in list(sys.modules.keys()) if k.startswith("oneiric")]
    for mod in modules_to_clear:
        del sys.modules[mod]


def reset_all_singletons() -> None:
    """Reset all Crackerjack global singletons and caches.

    Call this in an autouse fixture to ensure test isolation.
    """
    reset_hook_lock_manager()
    reset_timeout_manager()
    reset_service_watchdog()
    reset_metrics_collector()
    reset_performance_monitor()
    reset_intelligent_system()
    reset_agent_orchestrator()
    reset_learning_system()
    reset_agent_registry()
    reset_issue_embedder()
    reset_fallback_embedder()
    reset_connection_pool()
    reset_structlog()
    clear_lru_caches()
    clear_oneiric_modules()