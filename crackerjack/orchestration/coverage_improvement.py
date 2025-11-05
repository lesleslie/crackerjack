import logging
import typing as t
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.agents.test_creation_agent import TestCreationAgent
from crackerjack.services.coverage_ratchet import CoverageRatchetService


class CoverageImprovementOrchestrator:
    @depends.inject  # type: ignore[misc]
    def __init__(self, project_path: Path, console: Inject[Console]) -> None:
        self.project_path = project_path
        self.logger = logging.getLogger(__name__)
        self.console = console
        self.coverage_service = CoverageRatchetService(project_path)
        self.min_coverage_improvement = 2.0

    async def should_improve_coverage(
        self, current_coverage: float | None = None
    ) -> bool:
        try:
            if current_coverage is None:
                coverage_status = self.coverage_service.get_ratchet_data()
                current_coverage = coverage_status.get("current_coverage", 0.0)

            if current_coverage is not None and current_coverage < 100.0:
                self.logger.info(
                    f"Coverage at {current_coverage: .1f}%-improvement recommended"
                )
                return True

            self.logger.info("Coverage at 100 %-no improvement needed")
            return False

        except Exception as e:
            self.logger.warning(f"Could not determine coverage status: {e}")

            return True

    async def create_coverage_improvement_issue(
        self, coverage_gap: float | None = None
    ) -> Issue:
        if coverage_gap is None:
            try:
                coverage_status = self.coverage_service.get_ratchet_data()
                current_coverage = coverage_status.get("current_coverage", 0.0)
                coverage_gap = 100.0 - current_coverage
            except Exception:
                coverage_gap = 90.0

        message = (
            f"Proactive coverage improvement requested. "
            f"Gap to 100 %: {coverage_gap: .1f}%. "
            f"Target improvement: {min(self.min_coverage_improvement, coverage_gap) if coverage_gap is not None else self.min_coverage_improvement: .1f}%"
        )

        return Issue(
            id="coverage_improvement_proactive",
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.MEDIUM,
            message=message,
            file_path=None,
            stage="coverage_improvement",
        )

    async def execute_coverage_improvement(
        self, agent_context: t.Any
    ) -> dict[str, t.Any]:
        try:
            self.logger.info("Starting proactive coverage improvement")

            if not await self.should_improve_coverage():
                return self._create_skipped_result("Coverage improvement not needed")

            issue = await self.create_coverage_improvement_issue()
            test_agent = TestCreationAgent(agent_context)

            confidence = await test_agent.can_handle(issue)
            if confidence < 0.5:
                return self._create_low_confidence_result(confidence)

            fix_result = await test_agent.analyze_and_fix(issue)
            result = self._create_completion_result(fix_result)

            self._log_and_display_results(fix_result)
            return result

        except Exception as e:
            return self._create_error_result(e)

    def _create_skipped_result(self, reason: str) -> dict[str, t.Any]:
        return {
            "status": "skipped",
            "reason": reason,
            "coverage_at_100": True,
        }

    def _create_low_confidence_result(self, confidence: float) -> dict[str, t.Any]:
        self.logger.warning(f"TestCreationAgent confidence too low: {confidence}")
        return {
            "status": "skipped",
            "reason": "Agent confidence too low",
            "confidence": confidence,
        }

    def _create_completion_result(self, fix_result: t.Any) -> dict[str, t.Any]:
        return {
            "status": "completed" if fix_result.success else "failed",
            "confidence": fix_result.confidence,
            "fixes_applied": fix_result.fixes_applied,
            "files_modified": fix_result.files_modified,
            "recommendations": fix_result.recommendations,
        }

    def _log_and_display_results(self, fix_result: t.Any) -> None:
        if fix_result.success:
            self.logger.info(
                f"Coverage improvement successful: {len(fix_result.fixes_applied)} fixes applied"
            )
            if self.console:
                self.console.print(
                    f"[green]📈[/ green] Coverage improved: {len(fix_result.fixes_applied)} "
                    f"tests created in {len(fix_result.files_modified)} files"
                )
        else:
            # Log at debug level rather than warning since this is normal behavior
            self.logger.debug(
                "Test creation for coverage improvement was not successful"
            )
            if self.console:
                self.console.print(
                    "[dim]📈 Coverage improvement: no new tests created[/dim]"
                )

    def _create_error_result(self, error: Exception) -> dict[str, t.Any]:
        self.logger.error(f"Coverage improvement failed with error: {error}")
        return {
            "status": "error",
            "error": str(error),
            "fixes_applied": [],
            "files_modified": [],
        }

    async def get_coverage_improvement_recommendations(self) -> list[str]:
        recommendations = [
            "Focus on core business logic functions first",
            "Add tests for error handling and edge cases",
            "Consider property-based testing for complex algorithms",
            "Test integration points and configuration handling",
            "Add parametrized tests for different input scenarios",
        ]

        from contextlib import suppress

        with suppress(Exception):
            coverage_status = self.coverage_service.get_ratchet_data()
            current_coverage = coverage_status.get("current_coverage", 0.0)

            if current_coverage < 25.0:
                recommendations.insert(
                    0, "Start with basic import and instantiation tests"
                )
            elif current_coverage < 50.0:
                recommendations.insert(0, "Focus on testing public method interfaces")
            elif current_coverage < 75.0:
                recommendations.insert(0, "Add tests for internal helper methods")
            else:
                recommendations.insert(0, "Target remaining edge cases and error paths")

        return recommendations


async def create_coverage_improvement_orchestrator(
    project_path: Path,
) -> CoverageImprovementOrchestrator:
    return CoverageImprovementOrchestrator(project_path)
