from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..agents.base import FixResult
from ..models.fix_plan import FixPlan
from .base import AgentContext, Issue, IssueType, Priority
from .validation_coordinator import ValidationCoordinator

logger = logging.getLogger(__name__)


class FixerCoordinator:
    BATCH_SIZE = 10

    def __init__(self, project_path: str = ".") -> None:

        self.context = AgentContext(
            project_path=Path(project_path),
            config={},
        )

        from .refactoring_agent import RefactoringAgent
        from .security_agent import SecurityAgent
        from .type_error_specialist import TypeErrorSpecialistAgent

        self.fixers: dict[str, Any] = {
            "COMPLEXITY": RefactoringAgent(self.context),
            "TYPE_ERROR": TypeErrorSpecialistAgent(self.context),
            "SECURITY": SecurityAgent(self.context),
        }

        self._type_change_validator: ValidationCoordinator | None = None

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
        self._try_register_fixer("ARCHITECT", ".architect_agent", "ArchitectAgent")

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

    def _get_type_change_validator(self) -> ValidationCoordinator:
        if self._type_change_validator is None:
            self._type_change_validator = ValidationCoordinator(
                project_path=self.context.project_path,
            )
        return self._type_change_validator

    async def _validate_type_change(
        self,
        plan: FixPlan,
        result: FixResult,
    ) -> FixResult | None:
        """Run project-wide ty validation for TYPE_ERROR fixes.

        Returns ``None`` when the plan is not a TYPE_ERROR plan, the
        fixer did not modify a Python file, or the type check is
        unavailable — in which case the caller falls through to the
        normal return path.

        Returns a downgraded ``FixResult(success=False)`` when the
        fix introduced new type errors in dependent files (the file
        has been rolled back to its original contents by the
        validator).
        """
        if plan.issue_type.strip().upper() != "TYPE_ERROR":
            return None

        if not result.files_modified:
            return None

        modified_path = result.files_modified[0]
        target = Path(modified_path)
        if not target.exists() or target.suffix != ".py":
            return None

        try:
            new_content = target.read_text(encoding="utf-8")
        except OSError as e:
            logger.debug(f"Could not read {target} for type validation: {e}")
            return None

        first_change = plan.changes[0] if plan.changes else None
        original_code = first_change.old_code if first_change else None

        validator = self._get_type_change_validator()
        is_valid, feedback = await validator.validate_fix_for_type_change(
            code=new_content,
            file_path=str(target),
            original_code=original_code,
        )

        if is_valid:
            logger.info(
                f"Project-wide ty check passed for {target.name}; "
                f"keeping the TYPE_ERROR fix on disk."
            )
            return None

        logger.warning(
            f"Project-wide ty check rejected TYPE_ERROR fix for {target.name}: "
            f"{feedback}"
        )
        return FixResult(
            success=False,
            confidence=result.confidence,
            fixes_applied=[],
            remaining_issues=[
                f"Project-wide ty check introduced new errors: {feedback}"
            ],
            recommendations=[
                "Revert the type change and let the architect agent "
                "propose a project-aware fix."
            ],
            files_modified=[],
        )

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
                    ordered_plans = sorted(
                        file_plans,
                        key=lambda plan: (
                            plan.changes[0].line_range[0] if plan.changes else 0,
                            plan.issue_type,
                        ),
                    )
                    for plan in ordered_plans:
                        result = await self._execute_single_plan(plan)
                        results.append(result)

        logger.info(f"Execution complete: {len(results)} results")
        return results

    async def _execute_single_plan(self, plan: FixPlan) -> FixResult:
        try:
            issue = self._plan_to_issue(plan)
            fixer_keys = self._candidate_fixer_keys(plan.issue_type)
            last_result: FixResult | None = None

            for fixer_key in fixer_keys:
                fixer = self.fixers.get(fixer_key)
                if fixer is None:
                    continue

                logger.info(
                    f"Routing plan {plan.issue_type} to {fixer.__class__.__name__}: "
                    f"{len(plan.changes)} changes"
                )

                if hasattr(fixer, "execute_fix_plan"):
                    result = await fixer.execute_fix_plan(plan)
                elif hasattr(fixer, "analyze_and_fix"):
                    result = await fixer.analyze_and_fix(issue)
                else:
                    logger.error(
                        f"Fixer {fixer.__class__.__name__} has no execution method"
                    )
                    last_result = FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[
                            f"Fixer {fixer.__class__.__name__} lacks execute_fix_plan or analyze_and_fix"
                        ],
                        recommendations=["Implement execute_fix_plan in this agent"],
                    )
                    continue

                if self._is_effective_result(result):
                    type_validated = await self._validate_type_change(plan, result)
                    if type_validated is not None:
                        return type_validated
                    return result

                last_result = result
                logger.info(
                    f"Fixer {fixer.__class__.__name__} made no effective changes; "
                    "trying fallback fixer if available"
                )

            if last_result is not None:
                return last_result

            logger.warning(f"No fixer for issue type {plan.issue_type}")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"No fixer for {plan.issue_type}"],
                recommendations=["Register a fixer for this issue type"],
            )

        except Exception as e:
            logger.error(f"Execution failed for {plan.file_path}: {e}", exc_info=True)
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Exception: {e}"],
                recommendations=["Manual review required"],
            )

    def _plan_to_issue(self, plan: FixPlan) -> Issue:
        from .base import Issue

        issue_type = self._resolve_issue_type(plan.issue_type)
        line_number = plan.changes[0].line_range[0] if plan.changes else None
        message = plan.issue_message or plan.rationale or f"Fix for {plan.issue_type}"

        return Issue(
            type=issue_type,
            severity=Priority.LOW,
            message=message,
            file_path=plan.file_path,
            line_number=line_number,
            details=plan.issue_details.copy(),
            stage=plan.issue_stage or plan.issue_type.lower(),
        )

    def _resolve_issue_type(self, issue_type: str) -> IssueType:
        from .base import IssueType

        normalized = issue_type.strip().lower()
        for candidate in (normalized, normalized.replace("-", "_")):
            with suppress(ValueError):
                return IssueType(candidate)
            with suppress(KeyError):
                return IssueType[candidate.upper()]
        return IssueType.TYPE_ERROR

    def _group_by_file(self, plans: list[FixPlan]) -> dict[str, list[FixPlan]]:
        groups: dict[str, list[FixPlan]] = {}

        for plan in plans:
            if plan.file_path not in groups:
                groups[plan.file_path] = []
            groups[plan.file_path].append(plan)

        return groups

    def _candidate_fixer_keys(self, issue_type: str) -> list[str]:
        normalized = issue_type.strip().upper()
        candidates = [normalized]

        fallback_map = {
            "TYPE_ERROR": ["ARCHITECT"],
            "IMPORT_ERROR": ["ARCHITECT"],
            "FORMATTING": ["ARCHITECT"],
            "COMPLEXITY": ["ARCHITECT"],
            "REFURB": ["ARCHITECT"],
            "WARNING": ["ARCHITECT"],
        }

        for fallback_key in fallback_map.get(normalized, []):
            if fallback_key not in candidates:
                candidates.append(fallback_key)

        return candidates

    def _is_effective_result(self, result: FixResult) -> bool:
        if not result.success:
            return False
        return bool(result.fixes_applied or result.files_modified)

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
