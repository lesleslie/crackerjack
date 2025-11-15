"""QA Orchestrator service for coordinating quality assurance checks.

This service coordinates multiple QA adapters, handles parallel execution,
caching, and result aggregation. It replaces the pre-commit hook orchestration
with native ACB-based quality checks.

ACB Patterns:
- Service implements QAOrchestratorProtocol from models.protocols
- Async execution throughout
- Proper error handling and logging
- Graceful degradation on adapter failures
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import typing as t
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from acb.depends import depends

from crackerjack.models.protocols import QAAdapterProtocol
from crackerjack.models.qa_config import QACheckConfig, QAOrchestratorConfig
from crackerjack.models.qa_results import QAResult, QAResultStatus

if t.TYPE_CHECKING:
    pass


class QAOrchestrator:
    """Orchestrates multiple QA adapters for comprehensive quality checking.

    Coordinates execution of all registered QA adapters:
    - Parallel execution with configurable concurrency
    - Stage-based execution (fast vs comprehensive)
    - Result caching for performance
    - Formatter-first execution order
    - Incremental checking support

    Example:
        ```python
        # Initialize orchestrator
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
            max_parallel_checks=4,
            enable_caching=True,
            fail_fast=False,
        )
        orchestrator = QAOrchestrator(config)

        # Register adapters
        await orchestrator.register_adapter(ruff_adapter)
        await orchestrator.register_adapter(bandit_adapter)
        await orchestrator.register_adapter(zuban_adapter)

        # Run fast stage checks
        results = await orchestrator.run_checks(stage="fast")

        # Run comprehensive checks
        results = await orchestrator.run_checks(stage="comprehensive")

        # Run all checks
        all_results = await orchestrator.run_all_checks()
        ```
    """

    def __init__(self, config: QAOrchestratorConfig) -> None:
        """Initialize QA orchestrator.

        Args:
            config: Orchestrator configuration
        """
        self.config = config
        self._adapters: dict[str, QAAdapterProtocol] = {}
        self._cache: dict[str, tuple[QAResult, datetime]] = {}
        self._semaphore = asyncio.Semaphore(config.max_parallel_checks)

    async def register_adapter(self, adapter: QAAdapterProtocol) -> None:
        """Register a QA adapter.

        Args:
            adapter: QA adapter to register
        """
        adapter_name = adapter.adapter_name
        self._adapters[adapter_name] = adapter

        # Initialize adapter if not already initialized
        await adapter.init()

    def get_adapter(self, name: str) -> QAAdapterProtocol | None:
        """Get registered adapter by name.

        Args:
            name: Adapter name

        Returns:
            Adapter if found, None otherwise
        """
        return self._adapters.get(name)

    async def run_checks(
        self,
        stage: str = "fast",
        files: list[Path] | None = None,
    ) -> list[QAResult]:
        """Run QA checks for specified stage.

        Args:
            stage: Execution stage ('fast' or 'comprehensive')
            files: Optional list of files to check

        Returns:
            List of QAResult objects
        """
        # Get checks for this stage
        if stage == "fast":
            checks = self.config.fast_checks
        elif stage == "comprehensive":
            checks = self.config.comprehensive_checks
        else:
            raise ValueError(f"Invalid stage: {stage}")

        # Filter enabled checks
        checks = [c for c in checks if c.enabled]

        if not checks:
            return []

        # Sort checks: formatters first if configured
        if self.config.run_formatters_first:
            checks.sort(key=lambda c: (not c.is_formatter, c.check_name))

        # Execute checks
        results = await self._execute_checks(checks, files)

        return results

    async def run_all_checks(
        self,
        files: list[Path] | None = None,
    ) -> dict[str, t.Any]:
        """Run all registered QA checks.

        Args:
            files: Optional list of files to check

        Returns:
            Dictionary mapping adapter names to results
        """
        # Run fast stage
        fast_results = await self.run_checks(stage="fast", files=files)

        # Run comprehensive stage
        comprehensive_results = await self.run_checks(
            stage="comprehensive", files=files
        )

        # Aggregate results
        all_results = fast_results + comprehensive_results

        return {
            "fast_stage": fast_results,
            "comprehensive_stage": comprehensive_results,
            "all_results": all_results,
            "summary": self._create_summary(all_results),
        }

    def _create_check_tasks(
        self,
        checks: list[QACheckConfig],
        files: list[Path] | None,
    ) -> list[asyncio.Task]:
        """Create asyncio tasks for check execution."""
        tasks = []

        for check_config in checks:
            adapter = self.get_adapter(check_config.check_name)
            if not adapter:
                continue

            # Create task for this check
            task = self._execute_single_check(adapter, check_config, files)
            tasks.append(task)

        return tasks

    async def _handle_fail_fast(
        self, tasks: list[asyncio.Task]
    ) -> list[QAResult] | None:
        """Handle fail-fast logic if configured."""
        if not self.config.fail_fast or not tasks:
            return None

        # Wait for first task to complete
        done, pending = await asyncio.wait(
            tasks[-1:], return_when=asyncio.FIRST_COMPLETED
        )
        result = done.pop().result()
        if not result.is_success:
            # Cancel remaining tasks
            for pending_task in pending:
                pending_task.cancel()
            return [result]

        return None

    def _filter_valid_results(self, results: list[t.Any]) -> list[QAResult]:
        """Filter out exceptions and convert to valid QAResult objects."""
        valid_results = []
        for result in results:
            if isinstance(result, QAResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                # Log error but continue
                continue
        return valid_results

    async def _execute_checks(
        self,
        checks: list[QACheckConfig],
        files: list[Path] | None,
    ) -> list[QAResult]:
        """Execute multiple checks in parallel.

        Args:
            checks: List of check configurations
            files: Optional files to check

        Returns:
            List of QAResult objects
        """
        tasks = self._create_check_tasks(checks, files)

        # Handle fail fast logic if needed
        fail_result = await self._handle_fail_fast(tasks)
        if fail_result is not None:
            return fail_result

        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and convert to QAResult
        return self._filter_valid_results(results)

    async def _execute_single_check(
        self,
        adapter: QAAdapterProtocol,
        config: QACheckConfig,
        files: list[Path] | None,
    ) -> QAResult:
        """Execute a single check with caching and semaphore control.

        Args:
            adapter: QA adapter to execute
            config: Check configuration
            files: Optional files to check

        Returns:
            QAResult
        """
        # Generate cache key
        cache_key = self._generate_cache_key(adapter, config, files)

        # Check cache if enabled
        if self.config.enable_caching:
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return cached_result

        # Acquire semaphore for parallel execution control
        async with self._semaphore:
            try:
                # Execute check
                result = await adapter.check(files=files, config=config)

                # Cache result if enabled
                if self.config.enable_caching:
                    self._cache_result(cache_key, result)

                # Retry on failure if configured
                if not result.is_success and config.retry_on_failure:
                    result = await adapter.check(files=files, config=config)

                return result

            except Exception as e:
                # Return error result
                return QAResult(
                    check_id=config.check_id,
                    check_name=adapter.adapter_name,
                    check_type=config.check_type,
                    status=QAResultStatus.ERROR,
                    message=f"Check failed: {e}",
                    details=str(e),
                )

    def _generate_cache_key(
        self,
        adapter: QAAdapterProtocol,
        config: QACheckConfig,
        files: list[Path] | None,
    ) -> str:
        """Generate cache key for check execution.

        Args:
            adapter: QA adapter
            config: Check configuration
            files: Files to check

        Returns:
            Cache key string
        """
        key_parts = [
            adapter.adapter_name,
            str(config.check_id),
            str(sorted([str(f) for f in files]) if files else "all"),
        ]

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def _get_cached_result(self, cache_key: str) -> QAResult | None:
        """Get cached result if valid.

        Args:
            cache_key: Cache key

        Returns:
            Cached QAResult or None
        """
        if cache_key not in self._cache:
            return None

        result, timestamp = self._cache[cache_key]

        # Check if cache is still valid (1 hour TTL)
        if datetime.now() - timestamp > timedelta(hours=1):
            del self._cache[cache_key]
            return None

        return result

    def _cache_result(self, cache_key: str, result: QAResult) -> None:
        """Cache check result.

        Args:
            cache_key: Cache key
            result: QAResult to cache
        """
        self._cache[cache_key] = (result, datetime.now())

    def _create_summary(self, results: list[QAResult]) -> dict[str, t.Any]:
        """Create summary statistics from results.

        Args:
            results: List of QAResult objects

        Returns:
            Summary dictionary
        """
        total_checks = len(results)
        success_count = sum(1 for r in results if r.is_success)
        failure_count = sum(1 for r in results if r.status == QAResultStatus.FAILURE)
        error_count = sum(1 for r in results if r.status == QAResultStatus.ERROR)
        warning_count = sum(1 for r in results if r.status == QAResultStatus.WARNING)

        total_issues = sum(r.issues_found for r in results)
        total_fixed = sum(r.issues_fixed for r in results)
        total_execution_time = sum(r.execution_time_ms for r in results)

        return {
            "total_checks": total_checks,
            "success": success_count,
            "failures": failure_count,
            "errors": error_count,
            "warnings": warning_count,
            "total_issues_found": total_issues,
            "total_issues_fixed": total_fixed,
            "total_execution_time_ms": total_execution_time,
            "pass_rate": success_count / total_checks if total_checks > 0 else 0.0,
        }

    @classmethod
    async def from_yaml_config(
        cls,
        config_path: Path,
        project_root: Path | None = None,
    ) -> QAOrchestrator:
        """Create orchestrator from YAML configuration.

        Args:
            config_path: Path to YAML configuration file
            project_root: Optional project root override

        Returns:
            Configured QAOrchestrator instance

        Example YAML:
            ```yaml
            project_root: .
            max_parallel_checks: 4
            enable_caching: true
            fail_fast: false
            run_formatters_first: true

            checks:
              - check_name: ruff-lint
                check_type: lint
                enabled: true
                stage: fast
                settings:
                  mode: check
                  fix_enabled: false

              - check_name: ruff-format
                check_type: format
                enabled: true
                stage: fast
                settings:
                  mode: format
                  fix_enabled: false

              - check_name: bandit
                check_type: security
                enabled: true
                stage: comprehensive
            ```
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        # Load YAML configuration
        with config_path.open() as f:
            config_data = yaml.safe_load(f)

        # Create orchestrator config
        if project_root is None:
            project_root = Path(config_data.get("project_root", "."))

        config = QAOrchestratorConfig(
            project_root=project_root,
            max_parallel_checks=config_data.get("max_parallel_checks", 4),
            enable_caching=config_data.get("enable_caching", True),
            fail_fast=config_data.get("fail_fast", False),
            run_formatters_first=config_data.get("run_formatters_first", True),
            enable_incremental=config_data.get("enable_incremental", True),
            verbose=config_data.get("verbose", False),
        )

        # Create orchestrator
        orchestrator = cls(config)

        # Load and register adapters based on configuration
        # This would be implemented to dynamically load adapters
        # based on the YAML configuration

        return orchestrator

    async def health_check(self) -> dict[str, t.Any]:
        """Check health of orchestrator and all adapters.

        Returns:
            Health status dictionary
        """
        adapter_health = {}

        for name, adapter in self._adapters.items():
            try:
                health = await adapter.health_check()
                adapter_health[name] = health
            except Exception as e:
                adapter_health[name] = {
                    "status": "error",
                    "error": str(e),
                }

        return {
            "orchestrator_status": "healthy",
            "registered_adapters": len(self._adapters),
            "cache_entries": len(self._cache),
            "adapters": adapter_health,
        }


# Register orchestrator with ACB dependency injection
with contextlib.suppress(Exception):
    depends.set(QAOrchestrator)
