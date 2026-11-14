"""Centralized reset for all Crackerjack global singletons and caches.

This module provides reset_all_singletons() to tear down global state between tests,
preventing test pollution from shared singletons, caches, and module-level instances.

Restored 2026-08-10 after the AI-fix subsystem wholesale deletion. AI-fix related
resets (intelligent_system, agent_orchestrator, learning_system, agent_registry,
issue_embedder, fallback_embedder) were removed with their target modules.

Usage:
    from tests.conftest_reset import reset_all_singletons
    reset_all_singletons()
"""

from __future__ import annotations

import asyncio
import importlib
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.executors.hook_lock_manager import HookLockManager


@contextmanager
def reset_hook_lock_manager():
    """Reset HookLockManager singleton."""
    try:
        from crackerjack.executors.hook_lock_manager import HookLockManager
    except ImportError:
        # Module not importable in this environment — no singleton to reset.
        yield
        return

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
    try:
        from crackerjack.core import timeout_manager
    except ImportError:
        return
    timeout_manager._global_timeout_manager = None


def reset_service_watchdog() -> None:
    """Reset global ServiceWatchdog."""
    try:
        from crackerjack.core import service_watchdog
    except ImportError:
        return
    service_watchdog._global_watchdog = None


def reset_metrics_collector() -> None:
    """Reset global MetricsCollector."""
    try:
        from crackerjack.services import metrics
    except ImportError:
        return
    if metrics._metrics_collector is not None:
        try:
            metrics._metrics_collector.close()
        except Exception:
            pass
    metrics._metrics_collector = None


def reset_performance_monitor() -> None:
    """Reset global AsyncPerformanceMonitor via ContextVar."""
    try:
        from crackerjack.core.performance_monitor import _performance_monitor_context
    except ImportError:
        return
    _performance_monitor_context.set(None)


def reset_connection_pool() -> None:
    """Reset global HTTPConnectionPool."""
    try:
        from crackerjack.services import connection_pool
    except ImportError:
        return
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
    from pathlib import Path

    # tool_commands.py
    try:
        from crackerjack.config import tool_commands

        tool_commands._detect_package_name_cached.cache_clear()
        tool_commands._build_tool_commands_cached.cache_clear()
        tool_commands.get_tool_command.cache_clear()
        tool_commands.get_all_tool_commands.cache_clear()
        # Recompute module-level defaults to match current cwd
        tool_commands._DEFAULT_CWD_STR = str(Path.cwd())
        tool_commands._DEFAULT_PACKAGE_NAME = tool_commands._detect_package_name_cached(tool_commands._DEFAULT_CWD_STR)
        tool_commands._DEFAULT_COMMANDS = tool_commands._build_tool_commands_cached(tool_commands._DEFAULT_PACKAGE_NAME)
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

    # patterns/core.py - CompiledPatternCache
    try:
        from crackerjack.services.patterns import core as patterns_core

        with patterns_core.CompiledPatternCache._lock:
            patterns_core.CompiledPatternCache._cache.clear()
    except Exception:
        pass

    # profile_loader.py
    try:
        from crackerjack.config import profile_loader

        profile_loader._default_loader = None
        if hasattr(profile_loader, '_cache'):
            profile_loader._cache.clear()
        # Also clear the ProfileLoader instance cache if it has one
        if profile_loader._default_loader is not None and hasattr(profile_loader._default_loader, '_cache'):
            profile_loader._default_loader._cache.clear()
    except Exception:
        pass


def reset_oneiric_state() -> None:
    """Reset oneiric's cross-test state without breaking class identity.

    This used to evict every ``oneiric.*`` entry from ``sys.modules``.
    That was the blunt way to reset oneiric's state, and it breaks
    ``isinstance`` checks: a module that was already imported keeps the
    OLD class object, while a fresh import produces a NEW one with the
    same name. Pydantic validates by identity, so a ``OneiricSettings``
    built before the eviction rejects an ``OTelStorageSettings``
    instance built after it -- and ``OneiricSettings`` has exactly two
    such fields, ``observability`` and ``auth``.

    The mechanism: ``oneiric.core.config`` was imported at collection
    time, so its ``observability`` annotation resolved to the
    ``OTelStorageSettings`` class of that generation. The eviction
    removed the module, but the already-imported
    ``crackerjack.runtime.oneiric_workflow`` still held the old
    ``OneiricSettings``, whose default factory performs a *fresh*
    ``from oneiric.adapters.observability.settings import
    OTelStorageSettings`` at call time -- and got the new generation.
    Same name, different class, validation error.

    oneiric ships a targeted escape hatch for precisely this
    (``clear_project_settings_cache`` -- "Test-only escape hatch"), so
    reset the state instead of the modules.
    """
    # Public escape hatch: the memoized per-project settings models.
    try:
        from oneiric.core.build_settings import clear_project_settings_cache

        clear_project_settings_cache()
    except Exception:
        pass

    # Two more module-level caches in oneiric carry genuine per-test
    # runtime state. They are private to oneiric, but the eviction this
    # replaces used to reset them too, so resetting them keeps the
    # isolation guarantee the autouse fixture promises.
    #
    # ``oneiric.modes.base._MODE_REGISTRY`` is deliberately NOT reset:
    # it is a permanent registry filled by ``@register_mode`` decorators
    # at import time, so clearing it would leave mode resolution empty
    # until the module happened to be re-imported.
    for module_name, attr in (
        ("oneiric.core.resiliency", "_ADAPTIVE_RETRY_STATE"),
        ("oneiric.adapters.observability.embeddings", "_EMBED_CACHE"),
    ):
        try:
            module = importlib.import_module(module_name)
            cache = getattr(module, attr, None)
            if isinstance(cache, dict):
                cache.clear()
        except Exception:
            pass


def reset_all_singletons() -> None:
    """Reset all Crackerjack global singletons and caches.

    Call this in an autouse fixture to ensure test isolation.
    """
    reset_hook_lock_manager()
    reset_timeout_manager()
    reset_service_watchdog()
    reset_metrics_collector()
    reset_performance_monitor()
    reset_connection_pool()
    reset_structlog()
    clear_lru_caches()
    reset_oneiric_state()
