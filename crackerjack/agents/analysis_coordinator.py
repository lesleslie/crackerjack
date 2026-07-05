import asyncio
import logging

from ..agents.base import Issue
from ..models.fix_plan import FixPlan
from ..models.protocols import DebuggerProtocol
from .anti_pattern_agent import AntiPatternAgent
from .context_agent import ContextAgent
from .planning_agent import PlanningAgent

logger = logging.getLogger(__name__)


def _is_ai_fix_eligible(issue: Issue) -> bool:
    """Return True if the issue should be routed through the AI-fix pipeline.

    Filters two categories that have no business entering the plan/execute
    loop:

    1. **Compiled artifacts** (``.pyc`` and friends under ``__pycache__/``).
       These are binary cache files that the file reader cannot decode
       as UTF-8. They occasionally surface as Issue.file_path when a
       prior tool walk enumerated the worktree broadly and a downstream
       scanner forwarded the path. The AI agents downstream of this
       function all call ``read_file()`` on ``plan.file_path``; routing
       a .pyc through that pipeline raises ``UnicodeDecodeError`` for
       every read attempt and floods the run output.

    2. **Test files** (``tests/`` directories and ``test_*.py`` /
       ``*_test.py`` filenames). The AI-fix loop targets production code;
       fixing tests via the same code-modification pipeline is the wrong
       tool (tests need to be authored, not patched via AST transforms).
       Test-creation has its own flow (``test_creation_agent``) that
       bypasses this function, so excluding tests here is safe.
    """
    path = issue.file_path or ""
    if not path:
        # Issues without a file_path can't be auto-fixed by file-targeted
        # agents; let them through so the analyzer can decide.
        return True

    # Compiled / cached artifacts.
    if path.endswith(".pyc") or path.endswith(".pyo"):
        return False
    if "__pycache__" in path.split("/"):
        return False

    # Test files and test directories.
    parts = path.split("/")
    if "tests" in parts or "test" in parts:
        return False
    name = parts[-1]
    if name.startswith("test_") or name.endswith("_test.py"):
        return False
    if name == "conftest.py":
        return False

    return True


class AnalysisCoordinator:
    def __init__(
        self,
        max_concurrent: int = 10,
        project_path: str = ".",
        debugger: DebuggerProtocol | None = None,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

        self.context_agent = ContextAgent(project_path)
        self.pattern_agent = AntiPatternAgent(project_path)
        self.planning_agent = PlanningAgent(project_path, debugger=debugger)

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

        eligible, skipped = self._partition_eligible_issues(issues)
        if skipped:
            logger.info(
                f"⏭️ Filtered {len(skipped)} non-AI-fix-eligible issue(s) "
                "(.pyc / __pycache__ / tests/): "
                f"{[i.file_path for i in skipped[:5]]}"
                f"{'...' if len(skipped) > 5 else ''}"
            )

        tasks = [self.analyze_issue(issue) for issue in eligible]

        plans = await asyncio.gather(*tasks, return_exceptions=True)

        successful_plans: list[FixPlan] = []
        for i, result in enumerate(plans):
            if isinstance(result, Exception):
                logger.error(f"Issue {eligible[i].id} analysis failed: {result}")

                fallback_plan = self._create_fallback_plan(eligible[i])
                successful_plans.append(fallback_plan)
            else:
                assert isinstance(result, FixPlan)
                successful_plans.append(result)

        logger.info(
            f"Analysis complete: {len(successful_plans)}/{len(issues)} plans created"
        )
        return successful_plans

    @staticmethod
    def _partition_eligible_issues(
        issues: list[Issue],
    ) -> tuple[list[Issue], list[Issue]]:
        """Split issues into (eligible, skipped) for AI-fix processing."""
        eligible: list[Issue] = []
        skipped: list[Issue] = []
        for issue in issues:
            if _is_ai_fix_eligible(issue):
                eligible.append(issue)
            else:
                skipped.append(issue)
        return eligible, skipped

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
                    new_code=old_code.rstrip() + " # FIXME: Requires manual review",
                    reason=f"Analysis failed: {issue.message}",
                )
            ],
            rationale="Analysis failed, requires manual review",
            risk_level="high",
            validated_by="AnalysisCoordinator::Fallback",
            issue_message=issue.message,
            issue_stage=issue.stage,
            issue_details=issue.details.copy(),
        )
