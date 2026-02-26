import asyncio
import logging
from pathlib import Path
from typing import Any

from ..agents.base import FixResult
from ..models.fix_plan import FixPlan
from .base import AgentContext

logger = logging.getLogger(__name__)


class FixerCoordinator:
    BATCH_SIZE = 10

    def __init__(self, project_path: str = ".") -> None:

        self.context = AgentContext(
            project_path=Path(project_path),
            config={},
        )

        from .architect_agent import ArchitectAgent
        from .refactoring_agent import RefactoringAgent
        from .security_agent import SecurityAgent

        self.fixers: dict[str, Any] = {
            "COMPLEXITY": RefactoringAgent(self.context),
            "TYPE_ERROR": ArchitectAgent(self.context),
            "SECURITY": SecurityAgent(self.context),
        }

        self._try_register_fixer("FORMATTING", ".formatting_agent", "FormattingAgent")
        self._try_register_fixer(
            "DOCUMENTATION", ".documentation_agent", "DocumentationAgent"
        )
        self._try_register_fixer(
            "DEAD_CODE", ".dead_code_removal_agent", "DeadCodeRemovalAgent"
        )
        self._try_register_fixer("DEPENDENCY", ".dependency_agent", "DependencyAgent")
        self._try_register_fixer("DRY_VIOLATION", ".dry_agent", "DRYAgent")
        self._try_register_fixer(
            "PERFORMANCE", ".performance_agent", "PerformanceAgent"
        )
        self._try_register_fixer(
            "IMPORT_ERROR", ".import_optimization_agent", "ImportOptimizationAgent"
        )
        self._try_register_fixer(
            "TEST_FAILURE", ".test_specialist_agent", "TestSpecialistAgent"
        )
        self._try_register_fixer(
            "REFURB", ".refurb_agent", "RefurbCodeTransformerAgent"
        )
        self._try_register_fixer("WARNING", ".refactoring_agent", "RefactoringAgent")

        self._file_locks: dict[str, asyncio.Lock] = {}
        self._lock_manager_lock = asyncio.Lock()

        logger.info(
            f"FixerCoordinator initialized with {len(self.fixers)} fixer agents"
        )

    def _try_register_fixer(
        self, issue_type: str, module_path: str, class_name: str
    ) -> None:
        try:
            import importlib

            module = importlib.import_module(module_path, package="crackerjack.agents")
            agent_class = getattr(module, class_name)
            self.fixers[issue_type] = agent_class(self.context)
            logger.debug(f"Registered fixer for {issue_type}: {class_name}")
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not register fixer for {issue_type}: {e}")

    async def _get_file_lock(self, file_path: str) -> asyncio.Lock:
        async with self._lock_manager_lock:
            if file_path not in self._file_locks:
                self._file_locks[file_path] = asyncio.Lock()
                logger.debug(f"Created lock for {file_path}")
            return self._file_locks[file_path]

    async def execute_plans(self, plans: list[FixPlan]) -> list[FixResult]:
        if not plans:
            return []

        results = []
        logger.info(f"Executing {len(plans)} FixPlans in batches of {self.BATCH_SIZE}")

        for i in range(0, len(plans), self.BATCH_SIZE):
            batch = plans[i : i + self.BATCH_SIZE]

            plans_by_file = self._group_by_file(batch)

            for file_path, file_plans in plans_by_file.items():
                file_lock = await self._get_file_lock(file_path)
                async with file_lock:
                    tasks = [self._execute_single_plan(plan) for plan in file_plans]

                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                    for result in list(batch_results):
                        if isinstance(result, Exception):
                            logger.error(
                                f"Plan {result.file_path if hasattr(result, 'file_path') else 'unknown'} failed: {result}"
                            )

                            results.append(
                                FixResult(
                                    success=False,
                                    confidence=0.0,
                                    remaining_issues=[str(result)],
                                    recommendations=["Manual review required"],
                                )
                            )
                        elif isinstance(result, FixResult):
                            results.append(result)

        logger.info(f"Execution complete: {len(results)} results")
        return results

    async def _execute_single_plan(self, plan: FixPlan) -> FixResult:
        try:
            fixer = self.fixers.get(plan.issue_type) or self.fixers.get(
                plan.issue_type.upper()
            )

            if fixer is None:
                logger.warning(f"No fixer for issue type {plan.issue_type}")
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[f"No fixer for {plan.issue_type}"],
                    recommendations=["Register a fixer for this issue type"],
                )

            logger.info(
                f"Routing plan {plan.issue_type} to {fixer.__class__.__name__}: "
                f"{len(plan.changes)} changes"
            )

            if hasattr(fixer, "execute_fix_plan"):
                result = await fixer.execute_fix_plan(plan)
            elif hasattr(fixer, "analyze_and_fix"):
                from .base import Issue, IssueType, Priority

                issue_type = IssueType(plan.issue_type.lower())
                issue = Issue(
                    type=issue_type,
                    severity=Priority.LOW,
                    message=plan.rationale or f"Fix for {plan.issue_type}",
                    file_path=plan.file_path,
                    line_number=plan.changes[0].line_range[0] if plan.changes else None,
                )
                result = await fixer.analyze_and_fix(issue)
            else:
                logger.error(
                    f"Fixer {fixer.__class__.__name__} has no execution method"
                )
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[
                        f"Fixer {fixer.__class__.__name__} lacks execute_fix_plan or analyze_and_fix"
                    ],
                    recommendations=["Implement execute_fix_plan in this agent"],
                )

            return result

        except Exception as e:
            logger.error(f"Execution failed for {plan.file_path}: {e}", exc_info=True)
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Exception: {e}"],
                recommendations=["Manual review required"],
            )

    def _group_by_file(self, plans: list[FixPlan]) -> dict[str, list[FixPlan]]:
        groups: dict[str, list[FixPlan]] = {}

        for plan in plans:
            if plan.file_path not in groups:
                groups[plan.file_path] = []
            groups[plan.file_path].append(plan)

        return groups

    def get_agent_stats(self) -> dict[str, dict[str, Any]]:
        stats = {}

        for issue_type, fixer in self.fixers.items():
            agent_name = fixer.__class__.__name__
            stats[issue_type] = {
                "agent": agent_name,
                "executions": 0,
                "successes": 0,
                "success_rate": 0.0,
            }

        return stats
