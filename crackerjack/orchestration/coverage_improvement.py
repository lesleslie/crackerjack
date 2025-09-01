"""Coverage improvement orchestration.

This module provides proactive test coverage improvement by analyzing coverage gaps
and triggering the TestCreationAgent to automatically generate missing tests.
Integrated into the AI agent workflow after successful test execution.
"""

import logging
import typing as t
from pathlib import Path

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.agents.test_creation_agent import TestCreationAgent
from crackerjack.services.coverage_ratchet import CoverageRatchetService


class CoverageImprovementOrchestrator:
    """Orchestrates automatic test coverage improvement."""

    def __init__(self, project_path: Path, console: t.Any = None) -> None:
        self.project_path = project_path
        self.logger = logging.getLogger(__name__)
        self.console = console
        self.coverage_service = CoverageRatchetService(project_path, console)
        self.min_coverage_improvement = 2.0  # Minimum 2% improvement target per run

    async def should_improve_coverage(
        self, current_coverage: float | None = None
    ) -> bool:
        """Determine if coverage improvement should be attempted.

        Args:
            current_coverage: Current coverage percentage, will be detected if None

        Returns:
            True if coverage improvement should be attempted
        """
        try:
            if current_coverage is None:
                coverage_status = self.coverage_service.get_status_report()
                current_coverage = coverage_status.get("current_coverage", 0.0)

            # Always try to improve if coverage is below 100%
            if current_coverage is not None and current_coverage < 100.0:
                self.logger.info(
                    f"Coverage at {current_coverage:.1f}% - improvement recommended"
                )
                return True

            self.logger.info("Coverage at 100% - no improvement needed")
            return False

        except Exception as e:
            self.logger.warning(f"Could not determine coverage status: {e}")
            # Default to trying improvement if we can't determine coverage
            return True

    async def create_coverage_improvement_issue(
        self, coverage_gap: float | None = None
    ) -> Issue:
        """Create an issue for coverage improvement.

        Args:
            coverage_gap: Percentage gap to 100% coverage

        Returns:
            Issue configured for coverage improvement
        """
        if coverage_gap is None:
            try:
                coverage_status = self.coverage_service.get_status_report()
                current_coverage = coverage_status.get("current_coverage", 0.0)
                coverage_gap = 100.0 - current_coverage
            except Exception:
                coverage_gap = 90.0  # Default gap if we can't determine

        message = (
            f"Proactive coverage improvement requested. "
            f"Gap to 100%: {coverage_gap:.1f}%. "
            f"Target improvement: {min(self.min_coverage_improvement, coverage_gap) if coverage_gap is not None else self.min_coverage_improvement:.1f}%"
        )

        return Issue(
            id="coverage_improvement_proactive",
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.MEDIUM,
            message=message,
            file_path=None,  # Project-wide improvement
            stage="coverage_improvement",
        )

    async def execute_coverage_improvement(
        self, agent_context: t.Any
    ) -> dict[str, t.Any]:
        """Execute proactive coverage improvement.

        Args:
            agent_context: AgentContext for the TestCreationAgent

        Returns:
            Dictionary with improvement results
        """
        try:
            self.logger.info("Starting proactive coverage improvement")

            # Check if improvement is needed
            if not await self.should_improve_coverage():
                return {
                    "status": "skipped",
                    "reason": "Coverage improvement not needed",
                    "coverage_at_100": True,
                }

            # Create coverage improvement issue
            issue = await self.create_coverage_improvement_issue()

            # Initialize and execute TestCreationAgent
            test_agent = TestCreationAgent(agent_context)

            # Verify agent can handle the issue
            confidence = await test_agent.can_handle(issue)
            if confidence < 0.5:
                self.logger.warning(
                    f"TestCreationAgent confidence too low: {confidence}"
                )
                return {
                    "status": "skipped",
                    "reason": "Agent confidence too low",
                    "confidence": confidence,
                }

            # Execute the coverage improvement
            fix_result = await test_agent.analyze_and_fix(issue)

            result = {
                "status": "completed" if fix_result.success else "failed",
                "confidence": fix_result.confidence,
                "fixes_applied": fix_result.fixes_applied,
                "files_modified": fix_result.files_modified,
                "recommendations": fix_result.recommendations,
            }

            if fix_result.success:
                self.logger.info(
                    f"Coverage improvement successful: {len(fix_result.fixes_applied)} fixes applied"
                )
                if self.console:
                    self.console.print(
                        f"[green]📈[/green] Coverage improved: {len(fix_result.fixes_applied)} "
                        f"tests created in {len(fix_result.files_modified)} files"
                    )
            else:
                self.logger.warning("Coverage improvement failed")
                if self.console:
                    self.console.print(
                        "[yellow]⚠️[/yellow] Coverage improvement attempt completed with issues"
                    )

            return result

        except Exception as e:
            self.logger.error(f"Coverage improvement failed with error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "fixes_applied": [],
                "files_modified": [],
            }

    async def get_coverage_improvement_recommendations(self) -> list[str]:
        """Get recommendations for coverage improvement strategies.

        Returns:
            List of strategic recommendations for improving coverage
        """
        recommendations = [
            "Focus on core business logic functions first",
            "Add tests for error handling and edge cases",
            "Consider property-based testing for complex algorithms",
            "Test integration points and configuration handling",
            "Add parametrized tests for different input scenarios",
        ]

        from contextlib import suppress

        with suppress(Exception):
            # Add coverage-specific recommendations based on current state
            coverage_status = self.coverage_service.get_status_report()
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
    project_path: Path, console: t.Any = None
) -> CoverageImprovementOrchestrator:
    """Create a coverage improvement orchestrator instance."""
    return CoverageImprovementOrchestrator(project_path, console)
