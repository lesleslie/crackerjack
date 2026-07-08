from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..agents.base import FixResult
from ..ai_fix.fixer_registry import FixerRegistry
from ..models.fix_plan import FixPlan
from .base import AgentContext, Issue, IssueType, Priority
from .iterative_fix_agent import TyDiagnostic
from .validation_coordinator import ValidationCoordinator

# Tier-3 eligible issue types. Mirrors ``crackerjack.tools.ty_classify``
# (kept inline here to avoid an import cycle: ``ty_classify`` doesn't
# depend on this coordinator, but a coordinator importing from
# ``ty_classify`` would force the classifier to be loaded for any
# user of FixerCoordinator). If the classifier gains new tier-3
# codes, sync this list.
TIER3_ISSUE_TYPES: frozenset[str] = frozenset(
    {
        # Note: unsupported-operator and not-subscriptable are
        # handled at tier-1 by ``ty_narrow`` (see
        # ``crackerjack.tools.ty_classify._CODE_TO_TIER``). They
        # only fall through to tier-3 when ty_narrow's candidate
        # finder rejects them (e.g., non-bare-identifier LHS).
        "unresolved-attribute",
        # Alternate form used in some ty versions.
        "unsupported-attribute",
        "invalid-argument-type",
        "invalid-return-type",
        "invalid-assignment",
        "invalid-key",
        "not-iterable",
        "not-callable",
        "missing-argument",
        "too-many-arguments",
        "invalid-await",
        "invalid-context-manager",
        "invalid-overload",
        "unsupported-right-operand",
        "unsupported-left-operand",
        "unsupported-bool-operand",
    }
)

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

        self.fixers: FixerRegistry = FixerRegistry()
        self.fixers["COMPLEXITY"] = RefactoringAgent(self.context)
        self.fixers["TYPE_ERROR"] = TypeErrorSpecialistAgent(self.context)
        self.fixers["SECURITY"] = SecurityAgent(self.context)

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

        # Optional tier-3 dispatcher. When set, plans classified as
        # ``TIER_3_ITERATIVE`` can be routed to it via
        # ``route_tier3_plan``. The agent is optional so existing
        # callers that don't pass one still work unchanged.
        self.iterative_agent: Any = None

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
            self.fixers.register_builtin(issue_type, agent_class(self.context))
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

            # Tier-3 fallback: if no regular fixer produced an effective
            # result and the issue type is in the tier-3 set, try the
            # attached iterative agent. This is the bridge that lets
            # the coordinator hand off long-tail errors to a full CLI
            # session (or a session-buddy skill replay).
            if (
                self.iterative_agent is not None
                and plan.issue_type in TIER3_ISSUE_TYPES
            ):
                # The agent's fix_file is sync (calls a blocking
                # subprocess in LocalClaudeSubprocess). Off-load to
                # a thread so the asyncio loop stays responsive for
                # other concurrent work — a single tier-3 fix can
                # otherwise freeze the whole ai-fix loop for up to
                # the worker's timeout (default 600s).
                tier3_result = await asyncio.to_thread(self.route_tier3_plan_sync, plan)
                if tier3_result is not None and self._is_effective_result(tier3_result):
                    logger.info(
                        f"Tier-3 fix succeeded for {plan.issue_type} on "
                        f"{plan.file_path}"
                    )
                    return tier3_result

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

    # ------------------------------------------------------------------
    # Tier-3 dispatch (IterativeFixAgent adapter)
    # ------------------------------------------------------------------

    def attach_iterative_agent(self, agent: Any) -> None:
        """Wire a tier-3 IterativeFixAgent to this coordinator.

        Pass an instance of ``crackerjack.agents.iterative_fix_agent
        .IterativeFixAgent``. After attaching, plans classified as
        ``TIER_3_ITERATIVE`` can be routed via ``route_tier3_plan``.
        """
        self.iterative_agent = agent
        logger.debug("Attached tier-3 IterativeFixAgent: %s", agent.__class__.__name__)

    async def route_tier3_plan(self, plan: FixPlan) -> FixResult | None:
        """Async wrapper that runs the sync route_tier3_plan_sync in a thread.

        Keeps the asyncio event loop responsive while the tier-3
        worker (which may block on subprocess.run for up to its
        timeout) does its work.
        """
        return await asyncio.to_thread(self.route_tier3_plan_sync, plan)

    def route_tier3_plan_sync(self, plan: FixPlan) -> FixResult | None:
        """Apply the tier-3 agent to a single FixPlan (sync).

        Returns a FixResult on success (or skill replay), ``None`` if
        no tier-3 agent is attached or the plan isn't applicable.

        Note: ``files_modified`` is set ONLY when the worker dispatch
        path actually wrote a file. Skill-replay is currently a
        no-op scaffold (see ``IterativeFixAgent._replay_skill``),
        so replay-only successes don't claim to have modified the
        file.
        """
        if self.iterative_agent is None:
            logger.debug("route_tier3_plan called but no iterative_agent attached")
            return None
        target_file = plan.file_path
        if not target_file:
            return None
        target_path = Path(target_file)
        # Build one TyDiagnostic per ChangeSpec; if the plan has no
        # changes, fall back to a single synthetic diagnostic so the
        # agent at least gets the plan's metadata.
        if plan.changes:
            diagnostics = [
                TyDiagnostic(
                    file=target_path,
                    line=change.line_range[0],
                    col=0,
                    code=plan.issue_type,
                    message=plan.issue_message or plan.rationale,
                )
                for change in plan.changes
            ]
        else:
            diagnostics = [
                TyDiagnostic(
                    file=target_path,
                    line=0,
                    col=0,
                    code=plan.issue_type,
                    message=plan.issue_message or plan.rationale,
                )
            ]
        outcome = self.iterative_agent.fix_file(target_path, diagnostics)
        # Only claim the file was modified if the worker actually
        # wrote something. Skill-replay alone (until the diff
        # applier lands) doesn't touch the file.
        actually_modified = outcome.success and outcome.dispatched_to_pool
        return FixResult(
            success=outcome.success,
            confidence=0.5 if outcome.success else 0.0,
            fixes_applied=[
                f"{'skill-replay' if outcome.path_was_skill_replay else 'worker-dispatch'}: {outcome.message}"
            ]
            if outcome.success
            else [],
            files_modified=[target_file] if actually_modified else [],
            remaining_issues=[] if outcome.success else [outcome.message],
        )
