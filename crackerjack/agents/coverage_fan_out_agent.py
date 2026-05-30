from __future__ import annotations

import asyncio
import logging
from typing import Any

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)
from crackerjack.agents.helpers.test_creation.test_coverage_analyzer import (
    TestCoverageAnalyzer,
)

logger = logging.getLogger(__name__)


class CoverageFanOutAgent(SubAgent):
    __test__ = False

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self._coverage_analyzer = TestCoverageAnalyzer(context)

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.COVERAGE_IMPROVEMENT}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type not in self.get_supported_types():
            return 0.0
        message_lower = issue.message.lower()
        coverage_keywords = (
            "coverage below",
            "missing tests",
            "untested functions",
            "no tests found",
            "coverage requirement",
            "coverage gap",
            "improve coverage",
            "increase coverage",
        )
        return 0.95 if any(k in message_lower for k in coverage_keywords) else 0.8

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Fan-out coverage analysis: {issue.message}")

        try:
            coverage_analysis = await self._coverage_analyzer.analyze_coverage()
        except Exception as e:
            self.log(f"Coverage analysis failed: {e}", "ERROR")
            return self._create_error_result(e)

        uncovered_modules = coverage_analysis.get("uncovered_modules", [])
        if not uncovered_modules:
            self.log("No uncovered modules found")
            return FixResult(
                success=True,
                confidence=0.5,
                remaining_issues=[],
                recommendations=["No uncovered modules found — coverage is adequate"],
            )

        self.log(f"Found {len(uncovered_modules)} uncovered modules, fanning out...")

        semaphore = asyncio.Semaphore(8)
        tasks = [
            _create_tests_for_module_with_limit(
                module_info, self._coverage_analyzer, semaphore
            )
            for module_info in uncovered_modules
        ]

        results: list[dict[str, list[str]] | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        fixes_applied: list[str] = []
        files_modified: list[str] = []
        errors: list[str] = []

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif isinstance(result, dict):
                fixes_applied.extend(result.get("fixes", []))
                files_modified.extend(result.get("files", []))

                if not result.get("fixes") and not result.get("files"):
                    module_path = result.get("path", "unknown")
                    errors.append(f"No tests created for {module_path}")

        if not fixes_applied and errors:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=errors,
                recommendations=[
                    "All test creation attempts failed — manual intervention required"
                ],
            )

        confidence = self._calculate_confidence(
            fixes_applied, files_modified, len(uncovered_modules)
        )

        self.log(
            f"Fan-out complete: {len(fixes_applied)} fixes, {len(files_modified)} files"
        )

        return FixResult(
            success=bool(fixes_applied),
            confidence=confidence,
            fixes_applied=fixes_applied,
            remaining_issues=errors[:5],
            recommendations=self._generate_recommendations(
                fixes_applied, files_modified
            ),
            files_modified=files_modified,
        )

    def _calculate_confidence(
        self,
        fixes: list[str],
        files: list[str],
        total_modules: int,
    ) -> float:
        if not fixes:
            return 0.0
        confidence = 0.5
        if files:
            coverage = min(len(files) / total_modules, 1.0)
            confidence += coverage * 0.4
        if any("manager" in f.lower() or "service" in f.lower() for f in files):
            confidence += 0.1
        return min(confidence, 0.95)

    def _generate_recommendations(
        self,
        fixes: list[str],
        files: list[str],
    ) -> list[str]:
        if not fixes:
            return [
                "No tests were created — check module structure and permissions",
                "Consider running 'pytest --cov' to verify current coverage",
            ]
        return [
            f"Created {len(fixes)} tests across {len(files)} files",
            "Run 'pytest' to validate generated tests",
            "Review tests for edge cases and error scenarios",
        ]

    def _create_error_result(self, error: Exception) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Coverage fan-out failed: {error}"],
            recommendations=["Manual test creation may be required for this module"],
        )


async def _create_tests_for_module_with_limit(
    module_info: dict[str, Any],
    coverage_analyzer: TestCoverageAnalyzer,
    semaphore: asyncio.Semaphore,
) -> dict[str, list[str]]:
    async with semaphore:
        module_path = module_info.get("absolute_path") or module_info.get("path")
        if not module_path:
            return {"fixes": [], "files": []}
        try:
            return await coverage_analyzer.create_tests_for_module(module_path)
        except Exception as e:
            logger.warning(f"Test creation failed for {module_path}: {e}")
            return {"fixes": [], "files": []}


agent_registry.register(CoverageFanOutAgent)
