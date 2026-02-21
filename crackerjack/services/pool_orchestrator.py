"""Mahavishnu Pool Orchestrator for parallel hook execution.

This orchestrator manages the execution of quality hooks using Mahavishnu
worker pools, enabling parallel tool execution for improved performance.
"""

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
    """Result from pool-based hook execution.

    Attributes:
        success: Whether overall execution succeeded
        results: List of hook results
        pool_used: Whether pool execution was used
        fallback_used: Whether fallback to standard execution was used
        total_duration: Total execution time in seconds
        parallel_duration: Time for parallel execution portion
        error: Error message if execution failed
    """

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
    """Orchestrator for pool-based hook execution.

    Manages the execution of hooks using Mahavishnu worker pools,
    with graceful fallback to standard execution if pools are unavailable.

    Attributes:
        pool_client: Mahavishnu pool client instance
        pkg_path: Path to package root
        console: Console for output
        verbose: Enable verbose output
        debug: Enable debug output
    """

    def __init__(
        self,
        pool_client: t.Any,  # MahavishnuPoolClient
        pkg_path: Path,
        console: ConsoleInterface,
        verbose: bool = False,
        debug: bool = False,
    ) -> None:
        """Initialize pool orchestrator.

        Args:
            pool_client: Mahavishnu pool client instance
            pkg_path: Path to package root
            console: Console interface for output
            verbose: Enable verbose output
            debug: Enable debug output
        """
        self.pool_client = pool_client
        self.pkg_path = pkg_path
        self.console = console
        self.verbose = verbose
        self.debug = debug

    # ServiceProtocol implementation
    def initialize(self) -> None:
        """Initialize service."""
        logger.debug("PoolOrchestrator initialized")

    def cleanup(self) -> None:
        """Cleanup resources including pool client and pool itself."""
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
        """Check service health."""
        return True

    def shutdown(self) -> None:
        """Shutdown service."""
        self.cleanup()

    def metrics(self) -> dict[str, t.Any]:
        """Get service metrics."""
        return {
            "pool_available": getattr(self.pool_client, "is_available", False),
            "pool_id": getattr(self.pool_client, "pool_id", None),
        }

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return True

    def record_error(self, error: Exception) -> None:
        """Record error."""
        logger.error(f"PoolOrchestrator error: {error}")

    def increment_requests(self) -> None:
        """Increment request counter."""
        pass

    def register_resource(self, resource: t.Any) -> None:
        """Register resource."""
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        """Cleanup resource."""
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        """Get custom metric."""
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        """Set custom metric."""
        pass

    # Core orchestration methods
    async def execute_hooks_with_pools(
        self,
        hooks: list["HookDefinition"],
        file_filter: t.Any,  # SmartFileFilterV2
        use_pool: bool = True,
    ) -> PoolExecutionResult:
        """Execute hooks using Mahavishnu pools if available.

        Args:
            hooks: List of hook definitions to execute
            file_filter: SmartFileFilterV2 instance for incremental scanning
            use_pool: Whether to try pool execution (default: True)

        Returns:
            PoolExecutionResult with execution results
        """
        import time

        start_time = time.time()

        # Try pool execution first
        if use_pool and self._is_pool_available():
            try:
                return await self._execute_with_pools(hooks, file_filter, start_time)
            except Exception as e:
                logger.warning(f"Pool execution failed, falling back: {e}")
                self.console.print(
                    "[yellow]⚠️ Pool execution unavailable, using standard execution[/yellow]"
                )

        # Fallback to standard execution
        return await self._execute_standard(hooks, file_filter, start_time)

    def _is_pool_available(self) -> bool:
        """Check if Mahavishnu pool is available."""
        return getattr(self.pool_client, "is_available", False)

    async def _execute_with_pools(
        self,
        hooks: list["HookDefinition"],
        file_filter: t.Any,
        start_time: float,
    ) -> PoolExecutionResult:
        """Execute hooks using Mahavishnu pools.

        Args:
            hooks: List of hook definitions
            file_filter: SmartFileFilterV2 instance
            start_time: Execution start time

        Returns:
            PoolExecutionResult
        """
        import time

        # Group hooks by files to scan
        tool_files = self._group_hooks_by_files(hooks, file_filter)

        if self.verbose:
            self.console.print(
                f"[cyan]🔧 Executing {len(tool_files)} tools via pool[/cyan]"
            )

        # Ensure pool is created
        pool_id = self.pool_client.ensure_pool()

        if self.verbose:
            self.console.print(f"[cyan]   Pool ID: {pool_id}[/cyan]")

        # Execute tools via pool
        parallel_start = time.time()
        pool_results = self.pool_client.execute_tools_parallel(
            tool_files=tool_files,
            timeout=300,
        )
        parallel_duration = time.time() - parallel_start

        # Convert pool results to hook results
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
        """Execute hooks using standard subprocess execution.

        Args:
            hooks: List of hook definitions
            file_filter: SmartFileFilterV2 instance
            start_time: Execution start time

        Returns:
            PoolExecutionResult
        """
        import time

        results = []

        # Execute hooks sequentially (or in parallel using ThreadPoolExecutor)
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
                    # Create error result
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
        """Execute a single hook using standard subprocess.

        Args:
            hook: Hook definition
            file_filter: SmartFileFilterV2 instance

        Returns:
            HookResult
        """
        import time

        from crackerjack.models.task import HookResult

        start_time = time.time()

        try:
            # Get files for scan (using SmartFileFilterV2)
            files = self._get_files_for_hook(hook, file_filter)

            # Build command
            command = hook.build_command(files if files else None)

            # Execute
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                cwd=self.pkg_path,
            )

            duration = time.time() - start_time

            # Create HookResult
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
        """Get files to scan for a hook using SmartFileFilterV2.

        Args:
            hook: Hook definition
            file_filter: SmartFileFilterV2 instance

        Returns:
            List of files to scan, or None if hook doesn't accept files
        """
        if not hook.accepts_file_paths:
            return None

        try:
            # Try SmartFileFilterV2 API
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
        """Group hooks by files to scan for parallel execution.

        Args:
            hooks: List of hook definitions
            file_filter: SmartFileFilterV2 instance

        Returns:
            Dictionary mapping tool names to file lists
        """
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
        """Convert pool execution results to HookResult objects.

        Args:
            pool_results: Results from pool execution
            hooks: Original hook definitions

        Returns:
            List of HookResult objects
        """
        from crackerjack.models.task import HookResult

        results = []

        for hook in hooks:
            if hook.name not in pool_results:
                # Hook wasn't executed via pool
                continue

            pool_result = pool_results[hook.name]

            # Convert to HookResult
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
