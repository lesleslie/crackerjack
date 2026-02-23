"""
Analysis coordinator for parallel AI fix planning.

Orchestrates ContextAgent, PatternAgent, and PlanningAgent in parallel.
"""

import asyncio
import logging

from ..agents.base import Issue
from ..models.fix_plan import FixPlan
from .anti_pattern_agent import AntiPatternAgent
from .context_agent import ContextAgent
from .planning_agent import PlanningAgent

logger = logging.getLogger(__name__)


class AnalysisCoordinator:
    """
    Coordinate analysis agents in parallel to create FixPlans.

    Workflow:
    1. Extract context (ContextAgent)
    2. Identify anti-patterns (PatternAgent)
    3. Create FixPlan (PlanningAgent)

    Uses semaphore for bounded concurrency.
    """

    def __init__(self, max_concurrent: int = 10, project_path: str = ".") -> None:
        """
        Initialize analysis coordinator.

        Args:
            max_concurrent: Maximum concurrent analysis operations
            project_path: Root path for file operations
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)

        self.context_agent = ContextAgent(project_path)
        self.pattern_agent = AntiPatternAgent(project_path)
        self.planning_agent = PlanningAgent(project_path)

        logger.info(
            f"AnalysisCoordinator initialized with max_concurrent={max_concurrent}"
        )

    async def analyze_issue(self, issue: Issue) -> FixPlan:
        """
        Analyze issue and create FixPlan.

        Args:
            issue: Issue to analyze

        Returns:
            Validated FixPlan for execution

        Raises:
            ValueError: If analysis fails
        """
        async with self._semaphore:
            try:
                logger.info(
                    f"Analyzing issue {issue.id}: {issue.type.value} at {issue.file_path}:{issue.line_number}"
                )

                # Step 1: Extract context (required first, PatternAgent depends on it)
                context = await self.context_agent.extract_context(issue)

                # Step 2: Identify anti-patterns (can run parallel with context)
                patterns_task = self.pattern_agent.identify_anti_patterns(context)

                # Wait for pattern detection
                warnings = await patterns_task

                # Step 3: Create FixPlan from context + patterns
                plan = await self.planning_agent.create_fix_plan(
                    issue=issue, context=context, warnings=warnings
                )

                logger.info(
                    f"Created FixPlan for {issue.id}: "
                    f"{len(plan.changes)} changes, risk={plan.risk_level}"
                )

                return plan

            except Exception as e:
                logger.error(
                    f"Analysis failed for issue {issue.id}: {e}", exc_info=True
                )
                raise

    async def analyze_issues(self, issues: list[Issue]) -> list[FixPlan]:
        """
        Analyze multiple issues in parallel.

        Args:
            issues: List of issues to analyze

        Returns:
            List of FixPlans (one per issue)

        Note:
            Concurrency is limited by semaphore.
        """
        logger.info(f"Analyzing {len(issues)} issues in parallel")

        # Create analysis tasks
        tasks = [self.analyze_issue(issue) for issue in issues]

        # Execute with semaphore limiting concurrency
        plans = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for exceptions
        successful_plans = []
        for i, result in enumerate(plans):
            if isinstance(result, Exception):
                logger.error(f"Issue {issues[i].id} analysis failed: {result}")
                # Create minimal fallback plan
                fallback_plan = self._create_fallback_plan(issues[i])
                successful_plans.append(fallback_plan)
            else:
                successful_plans.append(result)

        logger.info(
            f"Analysis complete: {len(successful_plans)}/{len(issues)} plans created"
        )
        return successful_plans

    def _create_fallback_plan(self, issue: Issue) -> FixPlan:
        """
        Create minimal fallback plan when analysis fails.

        Args:
            issue: Issue that failed analysis

        Returns:
            Minimal FixPlan marking for manual review

        Note:
            Reads actual file content for old_code to ensure EditTool
            can find and replace the line correctly.
        """
        from pathlib import Path

        from ..models.fix_plan import ChangeSpec

        # Read actual file content for old_code
        old_code = "# Unknown line"
        line_number = issue.line_number or 1

        if issue.file_path:
            try:
                file_path = Path(issue.file_path)
                if file_path.exists():
                    lines = file_path.read_text().split("\n")
                    if 1 <= line_number <= len(lines):
                        old_code = lines[line_number - 1]
                    else:
                        logger.warning(
                            f"Line {line_number} out of range for {issue.file_path} "
                            f"(file has {len(lines)} lines)"
                        )
            except Exception as e:
                logger.warning(f"Could not read file {issue.file_path}: {e}")

        return FixPlan(
            file_path=issue.file_path or "",
            issue_type=issue.type.value,
            changes=[
                ChangeSpec(
                    line_range=(line_number, line_number),
                    old_code=old_code,
                    new_code=old_code.rstrip() + "  # FIXME: Requires manual review",
                    reason=f"Analysis failed: {issue.message}",
                )
            ],
            rationale="Analysis failed, requires manual review",
            risk_level="high",
            validated_by="AnalysisCoordinator::Fallback",
        )
