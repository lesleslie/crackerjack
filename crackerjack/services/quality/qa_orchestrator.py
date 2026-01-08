from __future__ import annotations

import asyncio
import hashlib
import typing as t
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from crackerjack.models.protocols import QAAdapterProtocol
from crackerjack.models.qa_config import QACheckConfig, QAOrchestratorConfig
from crackerjack.models.qa_results import QAResult, QAResultStatus

if t.TYPE_CHECKING:
    pass


class QAOrchestrator:
    def __init__(self, config: QAOrchestratorConfig) -> None:
        self.config = config
        self._adapters: dict[str, QAAdapterProtocol] = {}
        self._cache: dict[str, tuple[QAResult, datetime]] = {}
        self._semaphore = asyncio.Semaphore(config.max_parallel_checks)

    async def register_adapter(self, adapter: QAAdapterProtocol) -> None:
        adapter_name = adapter.adapter_name
        self._adapters[adapter_name] = adapter

        await adapter.init()

    def get_adapter(self, name: str) -> QAAdapterProtocol | None:
        return self._adapters.get(name)

    async def run_checks(
        self,
        stage: str = "fast",
        files: list[Path] | None = None,
    ) -> list[QAResult]:
        if stage == "fast":
            checks = self.config.fast_checks
        elif stage == "comprehensive":
            checks = self.config.comprehensive_checks
        else:
            raise ValueError(f"Invalid stage: {stage}")

        checks = [c for c in checks if c.enabled]

        if not checks:
            return []

        if self.config.run_formatters_first:
            checks.sort(key=lambda c: (not c.is_formatter, c.check_name))

        results = await self._execute_checks(checks, files)

        return results

    async def run_all_checks(
        self,
        files: list[Path] | None = None,
    ) -> dict[str, t.Any]:
        fast_results = await self.run_checks(stage="fast", files=files)

        comprehensive_results = await self.run_checks(
            stage="comprehensive", files=files
        )

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
    ) -> list[t.Coroutine[t.Any, t.Any, QAResult]]:
        tasks: list[t.Coroutine[t.Any, t.Any, QAResult]] = []

        for check_config in checks:
            adapter = self.get_adapter(check_config.check_name)
            if not adapter:
                continue

            task = self._execute_single_check(adapter, check_config, files)
            tasks.append(task)

        return tasks

    async def _handle_fail_fast(
        self, tasks: list[t.Coroutine[t.Any, t.Any, QAResult]]
    ) -> list[QAResult] | None:
        if not self.config.fail_fast or not tasks:
            return None

        task_list: list[asyncio.Task[QAResult]] = [
            asyncio.create_task(t) for t in tasks
        ]

        done, pending = await asyncio.wait(
            task_list[-1:], return_when=asyncio.FIRST_COMPLETED
        )
        result = done.pop().result()
        if not result.is_success:
            for pending_task in pending:
                pending_task.cancel()
            return [result]

        return None

    def _filter_valid_results(self, results: list[t.Any]) -> list[QAResult]:
        valid_results = []
        for result in results:
            if isinstance(result, QAResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                continue
        return valid_results

    async def _execute_checks(
        self,
        checks: list[QACheckConfig],
        files: list[Path] | None,
    ) -> list[QAResult]:
        tasks = self._create_check_tasks(checks, files)

        fail_result = await self._handle_fail_fast(tasks)
        if fail_result is not None:
            return fail_result

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return self._filter_valid_results(results)

    async def _execute_single_check(
        self,
        adapter: QAAdapterProtocol,
        config: QACheckConfig,
        files: list[Path] | None,
    ) -> QAResult:
        cache_key = self._generate_cache_key(adapter, config, files)

        if self.config.enable_caching:
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return cached_result

        async with self._semaphore:
            try:
                result = await adapter.check(files=files, config=config)

                if self.config.enable_caching:
                    self._cache_result(cache_key, result)

                if not result.is_success and config.retry_on_failure:
                    result = await adapter.check(files=files, config=config)

                return result

            except Exception as e:
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
        key_parts = [
            adapter.adapter_name,
            str(config.check_id),
            str(sorted([str(f) for f in files]) if files else "all"),
        ]

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def _get_cached_result(self, cache_key: str) -> QAResult | None:
        if cache_key not in self._cache:
            return None

        result, timestamp = self._cache[cache_key]

        if datetime.now() - timestamp > timedelta(hours=1):
            del self._cache[cache_key]
            return None

        return result

    def _cache_result(self, cache_key: str, result: QAResult) -> None:
        self._cache[cache_key] = (result, datetime.now())

    def _create_summary(self, results: list[QAResult]) -> dict[str, t.Any]:
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
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with config_path.open() as f:
            config_data = yaml.safe_load(f)

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

        orchestrator = cls(config)

        return orchestrator

    async def health_check(self) -> dict[str, t.Any]:
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
