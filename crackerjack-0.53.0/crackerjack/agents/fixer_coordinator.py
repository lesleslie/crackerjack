"""
Fixer coordinator for parallel AI fix execution.

Routes FixPlans to appropriate fixer agents and executes them with file-level locking.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from ..agents.base import FixResult
from ..models.fix_plan import FixPlan
from .base import AgentContext

logger = logging.getLogger(__name__)


class FixerCoordinator:
    """
    Coordinate fixer agents with parallel execution and file locking.

    Workflow:
    1. Receive FixPlans from AnalysisCoordinator
    2. Route to appropriate fixer by issue_type
    3. Execute multiple fixers in parallel (different files)
    4. Execute sequentially for same file (file-level locking)
    5. Track success rates per agent
    """

    BATCH_SIZE = 10

    def __init__(self, project_path: str = ".") -> None:
        """
        Initialize fixer coordinator with fixer agents.

        Args:
            project_path: Root path for file operations
        """
        # Create shared AgentContext for all fixers
        self.context = AgentContext(
            project_path=Path(project_path),
            config={},
        )

        # Import fixer agents here to avoid circular imports
        from .architect_agent import ArchitectAgent
        from .refactoring_agent import RefactoringAgent
        from .security_agent import SecurityAgent

        # Try to import formatting_agent
        try:
            from .formatting_agent import FormattingAgent

            has_formatting = True
        except ImportError:
            has_formatting = False
            FormattingAgent = None  # type: ignore

        self.fixers = {
            "COMPLEXITY": RefactoringAgent(self.context),
            "TYPE_ERROR": ArchitectAgent(self.context),
            "SECURITY": SecurityAgent(self.context),
        }

        if has_formatting and FormattingAgent:
            self.fixers["FORMATTING"] = FormattingAgent(self.context)

        # File-level locking to prevent concurrent modifications
        self._file_locks: dict[str, asyncio.Lock] = {}
        self._lock_manager_lock = asyncio.Lock()

        logger.info(
            f"FixerCoordinator initialized with {len(self.fixers)} fixer agents"
        )

    async def _get_file_lock(self, file_path: str) -> asyncio.Lock:
        """Get or create file-level lock."""
        async with self._lock_manager_lock:
            if file_path not in self._file_locks:
                self._file_locks[file_path] = asyncio.Lock()
                logger.debug(f"Created lock for {file_path}")
            return self._file_locks[file_path]

    async def execute_plans(self, plans: list[FixPlan]) -> list[FixResult]:
        """
        Execute multiple FixPlans in parallel with file locking.

        Args:
            plans: List of FixPlans to execute

        Returns:
            List of FixResults (one per plan)

        Note:
            - Bounded batching (BATCH_SIZE) prevents memory exhaustion
            - File-level locking prevents concurrent modifications to same file
            - Different files execute in parallel
        """
        if not plans:
            return []

        results = []
        logger.info(f"Executing {len(plans)} FixPlans in batches of {self.BATCH_SIZE}")

        # Process in batches
        for i in range(0, len(plans), self.BATCH_SIZE):
            batch = plans[i : i + self.BATCH_SIZE]

            # Group by file to prevent concurrent modifications
            plans_by_file = self._group_by_file(batch)

            # Execute sequentially per file, parallel across files
            for file_path, file_plans in plans_by_file.items():
                file_lock = await self._get_file_lock(file_path)
                async with file_lock:
                    # Execute all plans for this file in parallel
                    tasks = [self._execute_single_plan(plan) for plan in file_plans]

                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Collect results
                    for result in batch_results:
                        if isinstance(result, Exception):
                            logger.error(
                                f"Plan {result.file_path if hasattr(result, 'file_path') else 'unknown'} failed: {result}"
                            )
                            # Create failure result
                            batch_results.append(
                                FixResult(
                                    success=False,
                                    confidence=0.0,
                                    remaining_issues=[str(result)],
                                    recommendations=["Manual review required"],
                                )
                            )
                        elif isinstance(result, FixResult):
                            batch_results.append(result)

                    results.extend(batch_results)

        logger.info(f"Execution complete: {len(results)} results")
        return results

    async def _execute_single_plan(self, plan: FixPlan) -> FixResult:
        """Execute a single FixPlan by routing to appropriate fixer."""
        try:
            # Get fixer for this issue type
            fixer = self.fixers.get(plan.issue_type)

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

            # Execute the plan (fixer agent now has execute_fix_plan method)
            result = await fixer.execute_fix_plan(plan)

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
        """Group plans by file path."""
        groups: dict[str, list[FixPlan]] = {}

        for plan in plans:
            if plan.file_path not in groups:
                groups[plan.file_path] = []
            groups[plan.file_path].append(plan)

        return groups

    def get_agent_stats(self) -> dict[str, dict[str, Any]]:
        """Get success rate statistics per agent type."""
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
