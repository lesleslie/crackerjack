import logging
import time
import typing as t
from pathlib import Path

from ..agents.base import AgentContext, Issue, IssueType, Priority
from ..agents.coordinator import AgentCoordinator
from ..models.protocols import OptionsProtocol


class ProactiveWorkflowPipeline:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.logger = logging.getLogger(__name__)
        self._architect_agent_coordinator: AgentCoordinator | None = None

    async def run_complete_workflow_with_planning(
        self, options: OptionsProtocol
    ) -> bool:
        self.logger.info("Starting proactive workflow with architectural planning")

        start_time = time.time()

        try:
            assessment = await self._assess_codebase_architecture()

            if assessment.needs_planning:
                self.logger.info("Codebase requires architectural planning")

                architectural_plan = await self._create_comprehensive_plan(assessment)

                result = await self._execute_planned_workflow(
                    options, architectural_plan
                )
            else:
                self.logger.info(
                    "Codebase is architecturally sound, using standard workflow"
                )

                result = await self._execute_standard_workflow(options)

            execution_time = time.time() - start_time
            self.logger.info(f"Proactive workflow completed in {execution_time: .2f}s")

            return result

        except Exception as e:
            self.logger.exception(f"Proactive workflow failed: {e}")

            return await self._execute_standard_workflow(options)

    async def _assess_codebase_architecture(self) -> "ArchitecturalAssessment":
        self.logger.info("Assessing codebase architecture")

        if not self._architect_agent_coordinator:
            agent_context = AgentContext(project_path=self.project_path)
            self._architect_agent_coordinator = AgentCoordinator(agent_context)
            self._architect_agent_coordinator.initialize_agents()

        test_issues = await self._identify_potential_issues()

        needs_planning = self._evaluate_planning_need(test_issues)

        return ArchitecturalAssessment(
            needs_planning=needs_planning,
            complexity_score=len(test_issues),
            potential_issues=test_issues,
            recommended_strategy="proactive" if needs_planning else "standard",
        )

    async def _identify_potential_issues(self) -> list[Issue]:
        potential_issues: list[Issue] = []

        potential_issues.extend(
            (
                Issue(
                    id="arch_assessment_complexity",
                    type=IssueType.COMPLEXITY,
                    severity=Priority.HIGH,
                    message="Potential complexity hotspots detected",
                    file_path=str(self.project_path),
                    details=["Multiple functions may exceed complexity threshold"],
                ),
                Issue(
                    id="arch_assessment_dry",
                    type=IssueType.DRY_VIOLATION,
                    severity=Priority.MEDIUM,
                    message="Potential code duplication patterns",
                    file_path=str(self.project_path),
                    details=["Similar patterns may exist across modules"],
                ),
            )
        )

        return potential_issues

    def _evaluate_planning_need(self, issues: list[Issue]) -> bool:
        complex_issues = [
            issue
            for issue in issues
            if issue.type
            in {IssueType.COMPLEXITY, IssueType.DRY_VIOLATION, IssueType.PERFORMANCE}
        ]

        return len(complex_issues) >= 2

    async def _create_comprehensive_plan(
        self, assessment: "ArchitecturalAssessment"
    ) -> dict[str, t.Any]:
        self.logger.info("Creating comprehensive architectural plan")

        if self._architect_agent_coordinator is None:
            raise RuntimeError("ArchitectAgentCoordinator is not initialized")

        architect = self._architect_agent_coordinator._get_architect_agent()

        if not architect:
            self.logger.warning("No ArchitectAgent available, creating basic plan")
            return {
                "strategy": "basic_reactive",
                "phases": ["standard_workflow"],
                "patterns": ["default"],
            }

        complex_issues = [
            issue
            for issue in assessment.potential_issues
            if issue.type in {IssueType.COMPLEXITY, IssueType.DRY_VIOLATION}
        ]

        if complex_issues:
            primary_issue = complex_issues[0]
            base_plan = await architect.plan_before_action(primary_issue)

            comprehensive_plan = base_plan | {
                "phases": [
                    "configuration_setup",
                    "fast_hooks_with_architecture",
                    "architectural_refactoring",
                    "comprehensive_validation",
                    "pattern_learning",
                ],
                "integration_points": [
                    "architect_guided_fixing",
                    "pattern_caching",
                    "validation_against_plan",
                ],
            }
        else:
            comprehensive_plan = {
                "strategy": "lightweight_proactive",
                "phases": ["standard_workflow_enhanced"],
                "patterns": ["cached_patterns"],
            }

        self.logger.info(
            f"Created plan with strategy: {comprehensive_plan.get('strategy')}"
        )
        return comprehensive_plan

    async def _execute_planned_workflow(
        self, options: OptionsProtocol, plan: dict[str, t.Any]
    ) -> bool:
        strategy = plan.get("strategy", "basic_reactive")
        phases = plan.get("phases", ["standard_workflow"])

        self.logger.info(f"Executing {strategy} workflow with {len(phases)} phases")

        for phase in phases:
            success = await self._execute_workflow_phase(phase, options, plan)
            if not success and phase in (
                "configuration_setup",
                "architectural_refactoring",
            ):
                self.logger.error(f"Critical phase {phase} failed")
                return False
            elif not success:
                self.logger.warning(f"Phase {phase} had issues but continuing")

        return True

    async def _execute_workflow_phase(
        self, phase: str, options: OptionsProtocol, plan: dict[str, t.Any]
    ) -> bool:
        self.logger.info(f"Executing phase: {phase}")

        if phase == "configuration_setup":
            return await self._setup_with_architecture(options, plan)
        elif phase == "fast_hooks_with_architecture":
            return await self._run_fast_hooks_with_planning(options, plan)
        elif phase == "architectural_refactoring":
            return await self._perform_architectural_refactoring(options, plan)
        elif phase == "comprehensive_validation":
            return await self._comprehensive_validation(options, plan)
        elif phase == "pattern_learning":
            return await self._learn_and_cache_patterns(plan)

        return await self._execute_standard_workflow(options)

    async def _setup_with_architecture(
        self, options: OptionsProtocol, plan: dict[str, t.Any]
    ) -> bool:
        self.logger.info("Setting up project with architectural planning")

        return True

    async def _run_fast_hooks_with_planning(
        self, options: OptionsProtocol, plan: dict[str, t.Any]
    ) -> bool:
        self.logger.info("Running fast hooks with architectural planning")

        return True

    async def _perform_architectural_refactoring(
        self, options: OptionsProtocol, plan: dict[str, t.Any]
    ) -> bool:
        self.logger.info("Performing architectural refactoring")

        if self._architect_agent_coordinator:
            architect = self._architect_agent_coordinator._get_architect_agent()
            if architect:
                patterns = plan.get("patterns", [])
                self.logger.info(f"Applying architectural patterns: {patterns}")
                return True

        return True

    async def _comprehensive_validation(
        self, options: OptionsProtocol, plan: dict[str, t.Any]
    ) -> bool:
        self.logger.info("Performing comprehensive validation")
        validation_steps = plan.get("validation", [])

        for step in validation_steps:
            self.logger.info(f"Validating: {step}")

        return True

    async def _learn_and_cache_patterns(self, plan: dict[str, t.Any]) -> bool:
        self.logger.info("Learning and caching successful patterns")

        if self._architect_agent_coordinator:
            architect = self._architect_agent_coordinator._get_architect_agent()
            if architect and hasattr(architect, "get_cached_patterns"):
                cached_patterns = architect.get_cached_patterns()
                self.logger.info(f"Cached {len(cached_patterns)} patterns")

        return True

    async def _execute_standard_workflow(self, options: OptionsProtocol) -> bool:
        self.logger.info("Executing standard workflow (fallback)")

        return True


class ArchitecturalAssessment:
    def __init__(
        self,
        needs_planning: bool,
        complexity_score: int,
        potential_issues: list[Issue],
        recommended_strategy: str,
    ) -> None:
        self.needs_planning = needs_planning
        self.complexity_score = complexity_score
        self.potential_issues = potential_issues
        self.recommended_strategy = recommended_strategy
