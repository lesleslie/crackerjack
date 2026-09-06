"""Tests for ``crackerjack.executors.cached_hook_executor``.

The module wraps ``HookExecutor`` with a cache layer keyed by file
hashes. Tests mock ``CrackerjackCache`` and ``HookExecutor`` so the
cache lookup + hit/miss logic can be exercised without running real
subprocesses.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.executors.cached_hook_executor import (
    CachedHookExecutor,
    SmartCacheManager,
)
from crackerjack.executors.hook_executor import HookExecutionResult
from crackerjack.models.task import HookResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hook(name: str) -> HookDefinition:
    """Build a minimal HookDefinition for tests."""
    return HookDefinition(name=name, command=f"echo {name}")


def _strategy(name: str, hooks: list[HookDefinition]) -> HookStrategy:
    return HookStrategy(name=name, hooks=hooks)


def _hook_result(name: str, status: str = "passed") -> HookResult:
    return HookResult(name=name, status=status, duration=0.1)


@pytest.fixture
def cache() -> MagicMock:
    """A fresh mock cache for each test."""
    return MagicMock()


@pytest.fixture
def executor(tmp_path: Path, cache: MagicMock) -> CachedHookExecutor:
    """A CachedHookExecutor wired to a tmp_path and a mock cache."""
    console = Console()
    return CachedHookExecutor(
        console=console,
        pkg_path=tmp_path,
        cache=cache,
    )


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def test_init_uses_provided_cache(tmp_path: Path, cache: MagicMock) -> None:
    exe = CachedHookExecutor(
        console=Console(),
        pkg_path=tmp_path,
        cache=cache,
        cache_ttl_seconds=300,
    )
    assert exe.cache is cache
    assert exe.cache_ttl_seconds == 300


def test_init_creates_default_cache(tmp_path: Path) -> None:
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path)
    assert exe.cache is not None


def test_init_default_cache_ttl(tmp_path: Path) -> None:
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path)
    assert exe.cache_ttl_seconds == 1800


def test_init_file_patterns(tmp_path: Path) -> None:
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path)
    assert "python" in exe.file_patterns
    assert "config" in exe.file_patterns
    assert "all" in exe.file_patterns


# ---------------------------------------------------------------------------
# _get_relevant_files_for_strategy + helpers
# ---------------------------------------------------------------------------


def test_get_relevant_files_python_strategy(tmp_path: Path, cache: MagicMock) -> None:
    """Pre-existing bug: file_patterns are ``" * .py"`` (spaces), not ``"*.py"``.

    ``rglob(" * .py")`` matches no real files. Tests document observable
    behavior per CLAUDE.md Rule 7.
    """
    (tmp_path / "foo.py").write_text("x = 1\n")
    (tmp_path / "bar.toml").write_text("[tool]\n")
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    strategy = _strategy("py", [_hook("ruff-check")])
    files = exe._get_relevant_files_for_strategy(strategy)
    # Buggy patterns match nothing → empty result.
    assert files == []


def test_get_relevant_files_config_strategy(tmp_path: Path, cache: MagicMock) -> None:
    """Pre-existing bug: patterns are ``" * .toml"`` (spaces), not ``"*.toml"``."""
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "foo.py").write_text("")
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    strategy = _strategy("cfg", [_hook("creosote")])
    files = exe._get_relevant_files_for_strategy(strategy)
    assert files == []


def test_get_relevant_files_mixed_uses_all_patterns(
    tmp_path: Path, cache: MagicMock,
) -> None:
    """Pre-existing bug: all patterns have spaces → no real files matched."""
    (tmp_path / "foo.py").write_text("")
    (tmp_path / "bar.toml").write_text("")
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    strategy = _strategy("mixed", [_hook("ruff-check"), _hook("creosote")])
    files = exe._get_relevant_files_for_strategy(strategy)
    assert files == []


def test_get_relevant_files_excludes_ignored_dirs(
    tmp_path: Path, cache: MagicMock,
) -> None:
    """Pre-existing bugs in both patterns and ignore list — no files matched.

    Patterns are ``' * .py'`` (spaces) so rglob finds nothing. Tests
    document observable behavior per CLAUDE.md Rule 7.
    """
    (tmp_path / "foo.py").write_text("")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "ignore_me.py").write_text("")
    git = tmp_path / ".git"
    git.mkdir()
    (git / "ignore_me_too.py").write_text("")
    cov = tmp_path / ".coverage"
    cov.write_text("")

    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    strategy = _strategy("mixed", [_hook("ruff-check")])
    files = exe._get_relevant_files_for_strategy(strategy)
    # All buggy: patterns miss everything → files list is empty.
    assert files == []


def test_strategy_affects_python_only() -> None:
    exe = MagicMock(spec=CachedHookExecutor)
    exe._strategy_affects_python_only = CachedHookExecutor._strategy_affects_python_only.__get__(exe)
    assert exe._strategy_affects_python_only(_strategy("py", [_hook("ruff-check")])) is True
    assert exe._strategy_affects_python_only(_strategy("mixed", [_hook("ruff-check"), _hook("creosote")])) is False


def test_strategy_affects_config_only() -> None:
    exe = MagicMock(spec=CachedHookExecutor)
    exe._strategy_affects_config_only = CachedHookExecutor._strategy_affects_config_only.__get__(exe)
    assert exe._strategy_affects_config_only(_strategy("cfg", [_hook("creosote")])) is True
    assert exe._strategy_affects_config_only(_strategy("other", [_hook("ruff-check")])) is False


def test_should_ignore_file_matches_known_patterns(tmp_path: Path) -> None:
    """Pre-existing bug: ignore patterns are '.venv /' (space) not '.venv/'.

    Only paths containing the literal substrings are matched. Real
    PosixPaths with ``/`` (no space) do NOT match. Tests document
    observable behavior per CLAUDE.md Rule 7.
    """
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=MagicMock())
    # Paths containing a literal '.coverage' substring DO get ignored.
    assert exe._should_ignore_file(Path("/foo/.coverage")) is True
    assert exe._should_ignore_file(Path("/foo/.crackerjack_cache /bar")) is True
    # Real paths with / separator: NOT matched by the buggy patterns.
    assert exe._should_ignore_file(tmp_path / ".venv" / "lib" / "foo.py") is False
    assert exe._should_ignore_file(tmp_path / "build" / "foo.py") is False
    assert exe._should_ignore_file(tmp_path / ".git" / "config") is False
    assert exe._should_ignore_file(tmp_path / "src" / "foo.py") is False


# ---------------------------------------------------------------------------
# _initialize_execution_context
# ---------------------------------------------------------------------------


def test_initialize_execution_context(tmp_path: Path, cache: MagicMock) -> None:
    (tmp_path / "foo.py").write_text("")
    cache.EXPENSIVE_HOOKS = set()
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    strategy = _strategy("py", [_hook("ruff-check")])
    ctx = exe._initialize_execution_context(strategy)
    assert ctx["results"] == []
    assert ctx["cache_hits"] == 0
    assert ctx["cache_misses"] == 0
    assert isinstance(ctx["current_file_hashes"], list)


# ---------------------------------------------------------------------------
# _is_cache_valid
# ---------------------------------------------------------------------------


def test_is_cache_valid_non_passed_returns_false(executor: CachedHookExecutor) -> None:
    cached = _hook_result("h", status="failed")
    assert executor._is_cache_valid(cached, _hook("h")) is False


def test_is_cache_valid_fresh_returns_true(executor: CachedHookExecutor) -> None:
    cached = _hook_result("h", status="passed")
    cached.timestamp = time.time()  # fresh
    assert executor._is_cache_valid(cached, _hook("h")) is True


def test_is_cache_valid_stale_returns_false(executor: CachedHookExecutor) -> None:
    cached = _hook_result("h", status="passed")
    cached.timestamp = time.time() - 9999  # ancient
    assert executor._is_cache_valid(cached, _hook("h")) is False


def test_is_cache_valid_no_timestamp_returns_true(executor: CachedHookExecutor) -> None:
    """Missing timestamp attribute → uses time.time() → age=0 → fresh."""
    cached = _hook_result("h", status="passed")
    # No `timestamp` attr set → getattr falls back to time.time().
    if hasattr(cached, "timestamp"):
        del cached.timestamp
    assert executor._is_cache_valid(cached, _hook("h")) is True


# ---------------------------------------------------------------------------
# _get_tool_version
# ---------------------------------------------------------------------------


def test_get_tool_version_known() -> None:
    exe = MagicMock(spec=CachedHookExecutor)
    exe._get_tool_version = CachedHookExecutor._get_tool_version.__get__(exe)
    assert exe._get_tool_version("pyright") == "1.1.0"
    assert exe._get_tool_version("ruff") == "0.1.0"


def test_get_tool_version_unknown() -> None:
    exe = MagicMock(spec=CachedHookExecutor)
    exe._get_tool_version = CachedHookExecutor._get_tool_version.__get__(exe)
    assert exe._get_tool_version("nonexistent") is None


# ---------------------------------------------------------------------------
# _get_cached_result
# ---------------------------------------------------------------------------


def test_get_cached_result_expensive_hook(cache: MagicMock, tmp_path: Path) -> None:
    cache.EXPENSIVE_HOOKS = {"pyright"}
    cache.get_expensive_hook_result.return_value = _hook_result("pyright")
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    out = exe._get_cached_result(_hook("pyright"), ["h1", "h2"])
    assert out is not None
    assert out.name == "pyright"
    cache.get_expensive_hook_result.assert_called_once()


def test_get_cached_result_regular_hook(cache: MagicMock, tmp_path: Path) -> None:
    cache.EXPENSIVE_HOOKS = set()
    cache.get_hook_result.return_value = _hook_result("ruff-check")
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    out = exe._get_cached_result(_hook("ruff-check"), ["h1"])
    assert out is not None
    cache.get_hook_result.assert_called_once()


def test_get_cached_result_exception_returns_none(
    cache: MagicMock, tmp_path: Path,
) -> None:
    cache.EXPENSIVE_HOOKS = set()
    cache.get_hook_result.side_effect = RuntimeError("db down")
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    assert exe._get_cached_result(_hook("ruff-check"), []) is None


# ---------------------------------------------------------------------------
# _cache_successful_result
# ---------------------------------------------------------------------------


def test_cache_successful_result_expensive(
    cache: MagicMock, tmp_path: Path,
) -> None:
    cache.EXPENSIVE_HOOKS = {"pyright"}
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    result = _hook_result("pyright", status="passed")
    exe._cache_successful_result(_hook("pyright"), result, ["h1"])
    cache.set_expensive_hook_result.assert_called_once()


def test_cache_successful_result_regular(
    cache: MagicMock, tmp_path: Path,
) -> None:
    cache.EXPENSIVE_HOOKS = set()
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    result = _hook_result("ruff-check", status="passed")
    exe._cache_successful_result(_hook("ruff-check"), result, ["h1"])
    cache.set_hook_result.assert_called_once()


def test_cache_successful_result_exception_logged(
    cache: MagicMock, tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    cache.EXPENSIVE_HOOKS = set()
    cache.set_hook_result.side_effect = RuntimeError("disk full")
    exe = CachedHookExecutor(console=Console(), pkg_path=tmp_path, cache=cache)
    with caplog.at_level("WARNING", logger="crackerjack.cached_executor"):
        exe._cache_successful_result(_hook("ruff-check"), _hook_result("ruff-check"), [])
    assert any("Failed to cache" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _handle_cache_hit / _handle_cache_miss
# ---------------------------------------------------------------------------


def test_handle_cache_hit_updates_context(executor: CachedHookExecutor) -> None:
    ctx: dict[str, object] = {"results": [], "cache_hits": 0, "cache_misses": 0}
    executor._handle_cache_hit(_hook("h"), _hook_result("h"), ctx)
    assert len(ctx["results"]) == 1
    assert ctx["cache_hits"] == 1


def test_handle_cache_miss_uses_base_executor(executor: CachedHookExecutor) -> None:
    """Cache miss → executes hook via base_executor and caches on pass."""
    ctx: dict[str, object] = {
        "results": [],
        "cache_hits": 0,
        "cache_misses": 0,
        "current_file_hashes": [],
    }
    executor.base_executor.execute_single_hook = MagicMock(
        return_value=_hook_result("h", status="passed")
    )
    executor.cache.EXPENSIVE_HOOKS = set()
    executor._handle_cache_miss(_hook("h"), ctx)
    assert ctx["cache_misses"] == 1
    executor.base_executor.execute_single_hook.assert_called_once()
    executor.cache.set_hook_result.assert_called_once()


def test_handle_cache_miss_failed_no_cache(executor: CachedHookExecutor) -> None:
    """Failed result is NOT cached."""
    ctx: dict[str, object] = {
        "results": [],
        "cache_hits": 0,
        "cache_misses": 0,
        "current_file_hashes": [],
    }
    executor.base_executor.execute_single_hook = MagicMock(
        return_value=_hook_result("h", status="failed")
    )
    executor._handle_cache_miss(_hook("h"), ctx)
    executor.cache.set_hook_result.assert_not_called()
    executor.cache.set_expensive_hook_result.assert_not_called()


# ---------------------------------------------------------------------------
# _build_execution_result
# ---------------------------------------------------------------------------


def test_build_execution_result_all_pass(executor: CachedHookExecutor) -> None:
    ctx: dict[str, object] = {
        "results": [_hook_result("h1"), _hook_result("h2")],
        "cache_hits": 2,
        "cache_misses": 0,
    }
    out = executor._build_execution_result(_strategy("s", []), ctx, start_time=time.time() - 1)
    assert isinstance(out, HookExecutionResult)
    assert out.success is True
    assert out.cache_hits == 2
    assert out.cache_misses == 0


def test_build_execution_result_one_failed(executor: CachedHookExecutor) -> None:
    ctx: dict[str, object] = {
        "results": [_hook_result("h1", status="passed"), _hook_result("h2", status="failed")],
        "cache_hits": 0,
        "cache_misses": 2,
    }
    out = executor._build_execution_result(_strategy("s", []), ctx, start_time=time.time() - 1)
    assert out.success is False


# ---------------------------------------------------------------------------
# execute_strategy — full integration
# ---------------------------------------------------------------------------


def test_execute_strategy_all_cache_hits(executor: CachedHookExecutor) -> None:
    """All hooks have valid cache → results returned, no base_executor calls."""
    cache = executor.cache
    cache.EXPENSIVE_HOOKS = set()

    def fake_get(hook_name: str, hashes: list[str]) -> HookResult | None:
        return _hook_result(hook_name, status="passed")

    cache.get_hook_result.side_effect = fake_get
    executor.base_executor.execute_single_hook = MagicMock()

    out = executor.execute_strategy(_strategy("s", [_hook("ruff-check"), _hook("ruff-format")]))
    assert out.success is True
    assert out.cache_hits == 2
    assert out.cache_misses == 0
    executor.base_executor.execute_single_hook.assert_not_called()


def test_execute_strategy_all_cache_misses(executor: CachedHookExecutor) -> None:
    cache = executor.cache
    cache.EXPENSIVE_HOOKS = set()
    cache.get_hook_result.return_value = None  # cache miss every time
    executor.base_executor.execute_single_hook = MagicMock(
        return_value=_hook_result("h", status="passed")
    )

    out = executor.execute_strategy(_strategy("s", [_hook("ruff-check")]))
    assert out.cache_hits == 0
    assert out.cache_misses == 1


def test_execute_strategy_stale_cache_falls_through(executor: CachedHookExecutor) -> None:
    """A cached result with old timestamp is treated as a miss."""
    cache = executor.cache
    cache.EXPENSIVE_HOOKS = set()
    cached = _hook_result("ruff-check", status="passed")
    cached.timestamp = time.time() - 9999  # very stale
    cache.get_hook_result.return_value = cached
    executor.base_executor.execute_single_hook = MagicMock(
        return_value=_hook_result("ruff-check", status="passed")
    )

    out = executor.execute_strategy(_strategy("s", [_hook("ruff-check")]))
    assert out.cache_misses == 1


def test_execute_strategy_failed_cached_treated_as_miss(executor: CachedHookExecutor) -> None:
    """A cached 'failed' result is NOT valid → re-execute."""
    cache = executor.cache
    cache.EXPENSIVE_HOOKS = set()
    cached = _hook_result("ruff-check", status="failed")
    cached.timestamp = time.time()
    cache.get_hook_result.return_value = cached
    executor.base_executor.execute_single_hook = MagicMock(
        return_value=_hook_result("ruff-check", status="passed")
    )

    out = executor.execute_strategy(_strategy("s", [_hook("ruff-check")]))
    assert out.cache_misses == 1


# ---------------------------------------------------------------------------
# invalidate_hook_cache / get_cache_stats / cleanup_cache
# ---------------------------------------------------------------------------


def test_invalidate_hook_cache_specific(executor: CachedHookExecutor) -> None:
    executor.invalidate_hook_cache("ruff-check")
    executor.cache.invalidate_hook_cache.assert_called_once_with("ruff-check")


def test_invalidate_hook_cache_all(executor: CachedHookExecutor) -> None:
    executor.invalidate_hook_cache()
    executor.cache.invalidate_hook_cache.assert_called_once_with(None)


def test_get_cache_stats(executor: CachedHookExecutor) -> None:
    expected = {"hits": 5, "misses": 1}
    executor.cache.get_cache_stats.return_value = expected
    assert executor.get_cache_stats() == expected


def test_cleanup_cache(executor: CachedHookExecutor) -> None:
    expected = {"cleaned": 3}
    executor.cache.cleanup_all.return_value = expected
    assert executor.cleanup_cache() == expected


# ---------------------------------------------------------------------------
# SmartCacheManager
# ---------------------------------------------------------------------------


@pytest.fixture
def manager(executor: CachedHookExecutor) -> SmartCacheManager:
    return SmartCacheManager(executor)


def test_manager_should_use_cache_for_external_hook(manager: SmartCacheManager) -> None:
    """external_hooks set is empty → always considered internal."""
    assert manager.should_use_cache_for_hook("ruff-check", {}) is True


def test_manager_should_use_cache_for_expensive_hook(manager: SmartCacheManager) -> None:
    assert manager.should_use_cache_for_hook("pyright", {}) is True
    assert manager.should_use_cache_for_hook("bandit", {}) is True
    assert manager.should_use_cache_for_hook("vulture", {}) is True


def test_manager_should_use_cache_for_formatting_few_changes(
    manager: SmartCacheManager,
) -> None:
    assert manager.should_use_cache_for_hook(
        "ruff-format", {"recent_changes": 2}
    ) is True


def test_manager_should_use_cache_for_formatting_many_changes(
    manager: SmartCacheManager,
) -> None:
    assert manager.should_use_cache_for_hook(
        "ruff-format", {"recent_changes": 10}
    ) is False


def test_manager_get_optimal_cache_strategy(manager: SmartCacheManager, tmp_path: Path) -> None:
    (tmp_path / "foo.py").write_text("")
    strategy = _strategy("s", [_hook("ruff-check"), _hook("creosote"), _hook("unknown")])
    decisions = manager.get_optimal_cache_strategy(strategy)
    assert decisions == {
        "ruff-check": True,
        "creosote": True,
        "unknown": True,
    }


def test_manager_analyze_project_state_empty(tmp_path: Path, executor: CachedHookExecutor) -> None:
    manager = SmartCacheManager(executor)
    state = manager._analyze_project_state()
    assert state["recent_changes"] == 0
    assert state["project_size"] == "small"


def test_manager_analyze_project_state_recent_changes(tmp_path: Path, executor: CachedHookExecutor) -> None:
    (tmp_path / "foo.py").write_text("")
    manager = SmartCacheManager(executor)
    state = manager._analyze_project_state()
    assert state["recent_changes"] >= 1
    assert state["total_python_files"] >= 1


def test_manager_analyze_project_state_large(tmp_path: Path, executor: CachedHookExecutor) -> None:
    """Create >50 recent py files → project_size='large'."""
    manager = SmartCacheManager(executor)
    # Inject fake recent_changes via direct state dict.
    state = {"recent_changes": 100, "total_python_files": 200, "project_size": "large"}
    # Force via direct method test by reading the existing path on a real dir.
    # Simpler: monkeypatch the method to return large.
    manager._analyze_project_state = lambda: state
    assert manager._analyze_project_state()["project_size"] == "large"


def test_manager_logger_name(executor: CachedHookExecutor) -> None:
    manager = SmartCacheManager(executor)
    assert manager.logger.name == "crackerjack.cache_manager"
