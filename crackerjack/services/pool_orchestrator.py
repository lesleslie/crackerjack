import logging
import subprocess
import typing as t
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from crackerjack.models.protocols import ConsoleInterface, ServiceProtocol

if t.TYPE_CHECKING:
    from crackerjack.config.hooks import HookDefinition
    from crackerjack.models.task import HookResult

logger = logging.getLogger(__name__)


@dataclass
class PoolExecutionResult:
    success: bool
    results: list["HookResult"]
    pool_used: bool = False
    fallback_used: bool = False
    total_duration: float = 0.0
    parallel_duration: float = 0.0
    error: str | None = None

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "passed")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")


class PoolOrchestrator(ServiceProtocol):
    def __init__(
        self,
        pool_client: t.Any,
        pkg_path: Path,
        console: ConsoleInterface,
        verbose: bool = False,
        debug: bool = False,
    ) -> None:
        self.pool_client = pool_client
        self.pkg_path = pkg_path
        self.console = console
        self.verbose = verbose
        self.debug = debug

    def initialize(self) -> None:
        logger.debug("PoolOrchestrator initialized")

    def cleanup(self) -> None:
        try:
            if hasattr(self.pool_client, "cleanup"):
                self.pool_client.cleanup()
        except Exception as e:
            logger.warning(f"Failed to cleanup pool client: {e}")

        try:
            if hasattr(self.pool_client, "close_pool"):
                self.pool_client.close_pool()
        except Exception as e:
            logger.warning(f"Failed to close pool: {e}")

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        self.cleanup()

    def metrics(self) -> dict[str, t.Any]:
        return {
            "pool_available": getattr(self.pool_client, "is_available", False),
            "pool_id": getattr(self.pool_client, "pool_id", None),
        }

    def is_healthy(self) -> bool:
        return True

    def record_error(self, error: Exception) -> None:
        logger.error(f"PoolOrchestrator error: {error}")

    def increment_requests(self) -> None:
        pass

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    async def execute_hooks_with_pools(
        self,
        hooks: list["HookDefinition"],
        file_filter: t.Any,
        use_pool: bool = True,
    ) -> PoolExecutionResult:
        import time

        start_time = time.time()

        if use_pool and self._is_pool_available():
            try:
                return await self._execute_with_pools(hooks, file_filter, start_time)
            except Exception as e:
                logger.warning(f"Pool execution failed, falling back: {e}")
                self.console.print(
                    "[yellow]⚠️ Pool execution unavailable, using standard execution[/yellow]"
                )

        return await self._execute_standard(hooks, file_filter, start_time)

    def _is_pool_available(self) -> bool:
        return getattr(self.pool_client, "is_available", False)

    async def _execute_with_pools(
        self,
        hooks: list["HookDefinition"],
        file_filter: t.Any,
        start_time: float,
    ) -> PoolExecutionResult:
        import time

        tool_files = self._group_hooks_by_files(hooks, file_filter)

        if self.verbose:
            self.console.print(
                f"[cyan]🔧 Executing {len(tool_files)} tools via pool[/cyan]"
            )

        pool_id = self.pool_client.ensure_pool()

        if self.verbose:
            self.console.print(f"[cyan]   Pool ID: {pool_id}[/cyan]")

        parallel_start = time.time()
        pool_results = self.pool_client.execute_tools_parallel(
            tool_files=tool_files,
            timeout=300,
        )
        parallel_duration = time.time() - parallel_start

        results = self._convert_pool_results_to_hook_results(
            pool_results,
            hooks,
        )

        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in results)

        return PoolExecutionResult(
            success=success,
            results=results,
            pool_used=True,
            total_duration=total_duration,
            parallel_duration=parallel_duration,
        )

    async def _execute_standard(
        self,
        hooks: list["HookDefinition"],
        file_filter: t.Any,
        start_time: float,
    ) -> PoolExecutionResult:
        import time

        results = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    self._execute_single_hook_standard, hook, file_filter
                ): hook
                for hook in hooks
            }

            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    hook = futures[future]
                    logger.error(f"Hook execution failed for {hook.name}: {e}")

                    from crackerjack.models.task import HookResult

                    results.append(
                        HookResult(
                            id=hook.name,
                            name=hook.name,
                            status="error",
                            duration=0.0,
                            issues_found=[str(e)],
                            issues_count=1,
                            stage=hook.stage.value,
                            exit_code=1,
                            error_message=str(e),
                        )
                    )

        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in results)

        return PoolExecutionResult(
            success=success,
            results=results,
            pool_used=False,
            fallback_used=True,
            total_duration=total_duration,
        )

    def _execute_single_hook_standard(
        self,
        hook: "HookDefinition",
        file_filter: t.Any,
    ) -> "HookResult":
        import time

        from crackerjack.models.task import HookResult

        start_time = time.time()

        try:
            files = self._get_files_for_hook(hook, file_filter)

            command = hook.build_command(files or None)

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                cwd=self.pkg_path,
            )

            duration = time.time() - start_time

            status = "passed" if result.returncode == 0 else "failed"

            issues_found = []
            if status == "failed" and result.stderr:
                issues_found = [result.stderr.strip()][:10]

            return HookResult(
                id=hook.name,
                name=hook.name,
                status=status,
                duration=duration,
                files_processed=len(files) if files else 0,
                issues_found=issues_found,
                issues_count=len(issues_found),
                stage=hook.stage.value,
                exit_code=result.returncode if status == "failed" else None,
                output=result.stdout,
                error=result.stderr,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="timeout",
                duration=duration,
                issues_found=[f"Timeout after {duration:.1f}s"],
                issues_count=1,
                stage=hook.stage.value,
                exit_code=124,
                is_timeout=True,
                error_message=f"Execution exceeded timeout of {hook.timeout}s",
            )
        except Exception as e:
            duration = time.time() - start_time
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="error",
                duration=duration,
                issues_found=[str(e)],
                issues_count=1,
                stage=hook.stage.value,
                exit_code=1,
                error_message=str(e),
            )

    def _get_files_for_hook(
        self, hook: "HookDefinition", file_filter: t.Any
    ) -> list[Path] | None:
        if not hook.accepts_file_paths:
            return None

        try:
            if hasattr(file_filter, "get_files_for_scan"):
                return file_filter.get_files_for_scan(
                    tool_name=hook.name,
                    force_incremental=False,
                )
        except Exception as e:
            logger.debug(f"Failed to get files from filter: {e}")

        return None

    def _group_hooks_by_files(
        self,
        hooks: list["HookDefinition"],
        file_filter: t.Any,
    ) -> dict[str, list[Path]]:
        tool_files: dict[str, list[Path]] = {}

        for hook in hooks:
            if not hook.accepts_file_paths:
                continue

            try:
                files = self._get_files_for_hook(hook, file_filter)
                if files:
                    tool_files[hook.name] = files
            except Exception as e:
                logger.debug(f"Failed to get files for {hook.name}: {e}")

        return tool_files

    def _convert_pool_results_to_hook_results(
        self,
        pool_results: dict[str, dict[str, t.Any]],
        hooks: list["HookDefinition"],
    ) -> list["HookResult"]:
        from crackerjack.models.task import HookResult

        results = []

        for hook in hooks:
            if hook.name not in pool_results:
                continue

            pool_result = pool_results[hook.name]

            status = "passed" if pool_result.get("success", False) else "failed"

            results.append(
                HookResult(
                    id=hook.name,
                    name=hook.name,
                    hook_name=hook.name,
                    status=status,
                    duration=pool_result.get("duration", 0.0),
                    files_processed=len(pool_result.get("files", [])),
                    issues_found=(
                        [pool_result.get("error", "")]
                        if not pool_result.get("success")
                        else []
                    ),
                    issues_count=1 if not pool_result.get("success") else 0,
                    stage=hook.stage.value,
                    exit_code=pool_result.get("exit_code"),
                    output=pool_result.get("output", ""),
                    error=pool_result.get("error", ""),
                )
            )

        return results
