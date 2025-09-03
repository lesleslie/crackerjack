import logging
import time
import typing as t
from pathlib import Path

from rich.console import Console

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
        results: list[HookResult] = []
        cache_hits = 0
        cache_misses = 0

        relevant_files = self._get_relevant_files_for_strategy(strategy)
        current_file_hashes = self.file_hasher.get_files_hash_list(relevant_files)

        for hook_def in strategy.hooks:
            cached_result = None
            try:
                cached_result = self.cache.get_hook_result(
                    hook_def.name,
                    current_file_hashes,
                )
            except Exception as e:
                self.logger.warning(f"Cache error for hook {hook_def.name}: {e}")
                cached_result = None

            if cached_result and self._is_cache_valid(cached_result, hook_def):
                self.logger.debug(f"Using cached result for hook: {hook_def.name}")
                results.append(cached_result)
                cache_hits += 1
            else:
                self.logger.debug(f"Executing hook (cache miss): {hook_def.name}")

                hook_result = self.base_executor.execute_single_hook(hook_def)
                results.append(hook_result)
                cache_misses += 1

                if hook_result.status == "passed":
                    try:
                        self.cache.set_hook_result(
                            hook_def.name,
                            current_file_hashes,
                            hook_result,
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to cache result for {hook_def.name}: {e}",
                        )

        total_time = time.time() - start_time
        success = all(result.status == "passed" for result in results)

        self.logger.info(
            f"Cached strategy '{strategy.name}' completed in {total_time: .2f}s-"
            f"Success: {success}, Cache hits: {cache_hits}, Cache misses: {cache_misses}",
        )

        return HookExecutionResult(
            strategy_name=strategy.name,
            results=results,
            success=success,
            total_duration=total_time,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
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
            files.extend(list(self.pkg_path.rglob(pattern)))

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


class SmartCacheManager:
    def __init__(self, cached_executor: CachedHookExecutor) -> None:
        self.cached_executor = cached_executor
        self.logger = logging.getLogger("crackerjack.cache_manager")

    def should_use_cache_for_hook(
        self,
        hook_name: str,
        project_state: dict[str, t.Any],
    ) -> bool:
        external_hooks = {"detect-secrets"}
        if hook_name in external_hooks:
            return False

        expensive_hooks = {"pyright", "bandit", "vulture", "complexipy"}
        if hook_name in expensive_hooks:
            return True

        formatting_hooks = {
            "ruff-format",
            "trailing-whitespace",
            "end-of-file-fixer",
        }
        if hook_name in formatting_hooks:
            recent_changes = project_state.get("recent_changes", 0)
            return recent_changes < 5

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
            "total_python_files": len(list(pkg_path.rglob("*.py"))),
            "project_size": "large" if recent_changes > 50 else "small",
        }
