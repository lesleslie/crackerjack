import asyncio
import logging

from ..agents.base import Issue
from ..models.fix_plan import FixPlan
from .anti_pattern_agent import AntiPatternAgent
from .context_agent import ContextAgent
from .planning_agent import PlanningAgent

logger = logging.getLogger(__name__)


class AnalysisCoordinator:
    def __init__(self, max_concurrent: int = 10, project_path: str = ".") -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

        self.context_agent = ContextAgent(project_path)
        self.pattern_agent = AntiPatternAgent(project_path)
        self.planning_agent = PlanningAgent(project_path)

        logger.info(
            f"AnalysisCoordinator initialized with max_concurrent={max_concurrent}"
        )

    async def analyze_issue(self, issue: Issue) -> FixPlan:
        async with self._semaphore:
            try:
                logger.info(
                    f"Analyzing issue {issue.id}: {issue.type.value} at {issue.file_path}:{issue.line_number}"
                )

                context = await self.context_agent.extract_context(issue)

                patterns_task = self.pattern_agent.identify_anti_patterns(context)

                warnings = await patterns_task

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
        logger.info(f"Analyzing {len(issues)} issues in parallel")

        tasks = [self.analyze_issue(issue) for issue in issues]

        plans = await asyncio.gather(*tasks, return_exceptions=True)

        successful_plans = []
        for i, result in enumerate(plans):
            if isinstance(result, Exception):
                logger.error(f"Issue {issues[i].id} analysis failed: {result}")

                fallback_plan = self._create_fallback_plan(issues[i])
                successful_plans.append(fallback_plan)
            else:
                successful_plans.append(result)  # type: ignore

        logger.info(
            f"Analysis complete: {len(successful_plans)}/{len(issues)} plans created"
        )
        return successful_plans

    def _create_fallback_plan(self, issue: Issue) -> FixPlan:
        from pathlib import Path

        from ..models.fix_plan import ChangeSpec

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
