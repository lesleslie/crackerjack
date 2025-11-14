import logging
import time
import typing as t
from pathlib import Path

from acb.console import Console

from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.models.task import HookResult
from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.file_hasher import FileHasher

from .hook_executor import HookExecutionResult, HookExecutor


class CachedHookExecutor:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        cache: CrackerjackCache | None = None,
        cache_ttl_seconds: int = 1800,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.cache = cache or CrackerjackCache()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.file_hasher = FileHasher(self.cache)
        self.base_executor = HookExecutor(console, pkg_path, quiet=True)
        self.logger = logging.getLogger("crackerjack.cached_executor")

        self.file_patterns = {
            "python": [" * .py"],
            "config": [" * .toml", " * .cfg", " * .ini", " * .yaml", " * .yml"],
            "all": [
                " * .py",
                " * .toml",
                " * .cfg",
                " * .ini",
                " * .yaml",
                " * .yml",
                " * .md",
                " * .txt",
            ],
        }

    def execute_strategy(self, strategy: HookStrategy) -> HookExecutionResult:
        self.logger.info(
            f"Executing cached strategy '{strategy.name}' with {len(strategy.hooks)} hooks",
        )

        start_time = time.time()
        execution_context = self._initialize_execution_context(strategy)

        for hook_def in strategy.hooks:
            self._execute_single_hook_with_cache(hook_def, execution_context)

        return self._build_execution_result(strategy, execution_context, start_time)

    def _initialize_execution_context(self, strategy: HookStrategy) -> dict[str, t.Any]:
        """Initialize execution context for the strategy."""
        relevant_files = self._get_relevant_files_for_strategy(strategy)
        current_file_hashes = self.file_hasher.get_files_hash_list(relevant_files)

        return {
            "results": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "current_file_hashes": current_file_hashes,
        }

    def _execute_single_hook_with_cache(
        self, hook_def: HookDefinition, context: dict[str, t.Any]
    ) -> None:
        """Execute a single hook with caching logic."""
        cached_result = self._get_cached_result(
            hook_def, context["current_file_hashes"]
        )

        if cached_result and self._is_cache_valid(cached_result, hook_def):
            self._handle_cache_hit(hook_def, cached_result, context)
        else:
            self._handle_cache_miss(hook_def, context)

    def _get_cached_result(
        self, hook_def: HookDefinition, current_file_hashes: list[str]
    ) -> HookResult | None:
        """Get cached result for a hook definition."""
        try:
            if hook_def.name in self.cache.EXPENSIVE_HOOKS:
                tool_version = self._get_tool_version(hook_def.name)
                return self.cache.get_expensive_hook_result(
                    hook_def.name, current_file_hashes, tool_version
                )
            else:
                return self.cache.get_hook_result(hook_def.name, current_file_hashes)
        except Exception as e:
            self.logger.warning(f"Cache error for hook {hook_def.name}: {e}")
            return None

    def _handle_cache_hit(
        self,
        hook_def: HookDefinition,
        cached_result: HookResult,
        context: dict[str, t.Any],
    ) -> None:
        """Handle a cache hit scenario."""
        self.logger.debug(f"Using cached result for hook: {hook_def.name}")
        context["results"].append(cached_result)
        context["cache_hits"] += 1

    def _handle_cache_miss(
        self, hook_def: HookDefinition, context: dict[str, t.Any]
    ) -> None:
        """Handle a cache miss scenario."""
        self.logger.debug(f"Executing hook (cache miss): {hook_def.name}")

        hook_result = self.base_executor.execute_single_hook(hook_def)
        context["results"].append(hook_result)
        context["cache_misses"] += 1

        if hook_result.status == "passed":
            self._cache_successful_result(
                hook_def, hook_result, context["current_file_hashes"]
            )

    def _cache_successful_result(
        self,
        hook_def: HookDefinition,
        hook_result: HookResult,
        current_file_hashes: list[str],
    ) -> None:
        """Cache a successful hook result."""
        try:
            if hook_def.name in self.cache.EXPENSIVE_HOOKS:
                tool_version = self._get_tool_version(hook_def.name)
                self.cache.set_expensive_hook_result(
                    hook_def.name, current_file_hashes, hook_result, tool_version
                )
            else:
                self.cache.set_hook_result(
                    hook_def.name, current_file_hashes, hook_result
                )
        except Exception as e:
            self.logger.warning(f"Failed to cache result for {hook_def.name}: {e}")

    def _build_execution_result(
        self, strategy: HookStrategy, context: dict[str, t.Any], start_time: float
    ) -> HookExecutionResult:
        """Build the final execution result."""
        total_time = time.time() - start_time
        success = all(result.status == "passed" for result in context["results"])

        self.logger.info(
            f"Cached strategy '{strategy.name}' completed in {total_time:.2f}s - "
            f"Success: {success}, Cache hits: {context['cache_hits']}, "
            f"Cache misses: {context['cache_misses']}"
        )

        return HookExecutionResult(
            strategy_name=strategy.name,
            results=context["results"],
            success=success,
            total_duration=total_time,
            cache_hits=context["cache_hits"],
            cache_misses=context["cache_misses"],
        )

    def _get_relevant_files_for_strategy(self, strategy: HookStrategy) -> list[Path]:
        if self._strategy_affects_python_only(strategy):
            patterns = self.file_patterns["python"]
        elif self._strategy_affects_config_only(strategy):
            patterns = self.file_patterns["config"]
        else:
            patterns = self.file_patterns["all"]

        files: list[Path] = []
        for pattern in patterns:
            files.extend(list[t.Any](self.pkg_path.rglob(pattern)))

        return [f for f in files if f.is_file() and not self._should_ignore_file(f)]

    def _strategy_affects_python_only(self, strategy: HookStrategy) -> bool:
        python_only_hooks = {
            "ruff-format",
            "ruff-check",
            "pyright",
            "bandit",
            "vulture",
            "refurb",
            "complexipy",
        }
        return all(hook.name in python_only_hooks for hook in strategy.hooks)

    def _strategy_affects_config_only(self, strategy: HookStrategy) -> bool:
        config_only_hooks = {"creosote"}
        return all(hook.name in config_only_hooks for hook in strategy.hooks)

    def _should_ignore_file(self, file_path: Path) -> bool:
        ignore_patterns = [
            ".git /",
            ".venv /",
            "__pycache__ /",
            ".pytest_cache /",
            ".coverage",
            ".crackerjack_cache /",
            "node_modules /",
            ".tox /",
            "dist /",
            "build /",
            ".egg-info /",
        ]

        path_str = str(file_path)
        return any(pattern in path_str for pattern in ignore_patterns)

    def _is_cache_valid(
        self,
        cached_result: HookResult,
        hook_def: HookDefinition,
    ) -> bool:
        if cached_result.status != "passed":
            return False

        cache_age = time.time() - getattr(cached_result, "timestamp", time.time())
        return not cache_age > self.cache_ttl_seconds

    def invalidate_hook_cache(self, hook_name: str | None = None) -> None:
        self.cache.invalidate_hook_cache(hook_name)
        self.logger.info(f"Invalidated cache for hook: {hook_name or 'all hooks'}")

    def get_cache_stats(self) -> dict[str, t.Any]:
        return self.cache.get_cache_stats()

    def cleanup_cache(self) -> dict[str, int]:
        return self.cache.cleanup_all()

    def _get_tool_version(self, tool_name: str) -> str | None:
        """Get version of a tool for cache invalidation."""
        # This is a simplified version - in production, you might want to
        # actually call the tool to get its version
        version_mapping = {
            "pyright": "1.1.0",  # Could be dynamic: subprocess.run(["pyright", "--version"])
            "bandit": "1.7.5",
            "vulture": "2.7.0",
            "complexipy": "0.13.0",
            "refurb": "1.17.0",
            "ruff": "0.1.0",
            "gitleaks": "8.18.0",
        }
        return version_mapping.get(tool_name)


class SmartCacheManager:
    def __init__(self, cached_executor: CachedHookExecutor) -> None:
        self.cached_executor = cached_executor
        self.logger = logging.getLogger("crackerjack.cache_manager")

    def should_use_cache_for_hook(
        self,
        hook_name: str,
        project_state: dict[str, t.Any],
    ) -> bool:
        external_hooks: set[str] = set()
        if hook_name in external_hooks:
            return False

        expensive_hooks = {"pyright", "bandit", "vulture", "complexipy", "gitleaks"}
        if hook_name in expensive_hooks:
            return True

        formatting_hooks = {
            "ruff-format",
            "trailing-whitespace",
            "end-of-file-fixer",
        }
        if hook_name in formatting_hooks:
            recent_changes = project_state.get("recent_changes", 0)
            result: bool = recent_changes < 5
            return result

        return True

    def get_optimal_cache_strategy(
        self,
        hook_strategy: HookStrategy,
    ) -> dict[str, bool]:
        project_state = self._analyze_project_state()

        cache_decisions = {}
        for hook_def in hook_strategy.hooks:
            cache_decisions[hook_def.name] = self.should_use_cache_for_hook(
                hook_def.name,
                project_state,
            )

        return cache_decisions

    def _analyze_project_state(self) -> dict[str, t.Any]:
        pkg_path = self.cached_executor.pkg_path

        recent_changes = 0
        for py_file in pkg_path.rglob("*.py"):
            if py_file.is_file():
                from contextlib import suppress

                with suppress(OSError):
                    mtime = py_file.stat().st_mtime
                    if time.time() - mtime < 3600:
                        recent_changes += 1

        return {
            "recent_changes": recent_changes,
            "total_python_files": len(list[t.Any](pkg_path.rglob("*.py"))),
            "project_size": "large" if recent_changes > 50 else "small",
        }
