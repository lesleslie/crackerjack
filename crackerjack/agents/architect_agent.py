import typing as t

from .base import FixResult, Issue, IssueType, agent_registry
from .formatting_agent import FormattingAgent
from .import_optimization_agent import ImportOptimizationAgent
from .proactive_agent import ProactiveAgent
from .refactoring_agent import RefactoringAgent
from .security_agent import SecurityAgent


class ArchitectAgent(ProactiveAgent):
    def __init__(self, context) -> None:
        super().__init__(context)
        # Initialize specialist agents for delegation
        self._refactoring_agent = RefactoringAgent(context)
        self._formatting_agent = FormattingAgent(context)
        self._import_agent = ImportOptimizationAgent(context)
        self._security_agent = SecurityAgent(context)

    def get_supported_types(self) -> set[IssueType]:
        # Reduced scope - only handle issues that don't have specialized agents
        return {
            IssueType.TYPE_ERROR,  # Only type errors, delegate others
            IssueType.DEPENDENCY,
            IssueType.DOCUMENTATION,
            IssueType.TEST_ORGANIZATION,
        }

    async def can_handle(self, issue: Issue) -> float:
        # VERY LOW confidence - let specialists handle issues first
        # Only act as fallback when no one else can handle
        if issue.type == IssueType.TYPE_ERROR:
            return 0.1  # Let RefactoringAgent handle it

        if issue.type == IssueType.DEPENDENCY:
            return 0.1

        if issue.type == IssueType.DOCUMENTATION:
            return 0.1

        if issue.type == IssueType.TEST_ORGANIZATION:
            return 0.1

        return 0.0  # Don't claim to handle types we've delegated

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        if await self._needs_external_specialist(issue):
            return await self._get_specialist_plan(issue)

        return await self._get_internal_plan(issue)

    async def _needs_external_specialist(self, issue: Issue) -> bool:
        if issue.type == IssueType.COMPLEXITY:
            return True

        return issue.type == IssueType.DRY_VIOLATION

    async def _get_specialist_plan(self, issue: Issue) -> dict[str, t.Any]:
        return {
            "strategy": "external_specialist_guided",
            "specialist": "crackerjack-architect",
            "approach": self._get_specialist_approach(issue),
            "patterns": self._get_recommended_patterns(issue),
            "dependencies": self._analyze_dependencies(issue),
            "risks": self._identify_risks(issue),
            "validation": self._get_validation_steps(issue),
        }

    async def _get_internal_plan(self, issue: Issue) -> dict[str, t.Any]:
        return {
            "strategy": "internal_pattern_based",
            "approach": self._get_internal_approach(issue),
            "patterns": self._get_cached_patterns_for_issue(issue),
            "dependencies": [],
            "risks": ["minimal"],
            "validation": ["run_quality_checks"],
        }

    def _get_specialist_approach(self, issue: Issue) -> str:
        if issue.type == IssueType.COMPLEXITY:
            return "break_into_helper_methods"
        if issue.type == IssueType.DRY_VIOLATION:
            return "extract_common_patterns"
        if issue.type == IssueType.PERFORMANCE:
            return "optimize_algorithms"
        if issue.type == IssueType.SECURITY:
            return "apply_secure_patterns"
        return "apply_clean_code_principles"

    def _get_internal_approach(self, issue: Issue) -> str:
        return {
            IssueType.FORMATTING: "apply_standard_formatting",
            IssueType.IMPORT_ERROR: "optimize_imports",
            IssueType.TYPE_ERROR: "add_type_annotations",
            IssueType.TEST_FAILURE: "fix_test_patterns",
            IssueType.DEAD_CODE: "remove_unused_code",
            IssueType.DOCUMENTATION: "update_documentation",
        }.get(issue.type, "apply_standard_fix")

    def _get_recommended_patterns(self, issue: Issue) -> list[str]:
        return {
            IssueType.COMPLEXITY: [
                "extract_method",
                "dependency_injection",
                "protocol_interfaces",
                "helper_methods",
            ],
            IssueType.DRY_VIOLATION: [
                "common_base_class",
                "utility_functions",
                "protocol_pattern",
                "composition",
            ],
            IssueType.PERFORMANCE: [
                "list_comprehension",
                "generator_pattern",
                "caching",
                "algorithm_optimization",
            ],
            IssueType.SECURITY: [
                "secure_temp_files",
                "input_validation",
                "safe_subprocess",
                "token_handling",
            ],
        }.get(issue.type, ["standard_patterns"])

    def _get_cached_patterns_for_issue(self, issue: Issue) -> list[str]:
        cached = self.get_cached_patterns()
        matching_patterns = []

        for pattern_key, pattern_data in cached.items():
            if pattern_key.startswith(issue.type.value):
                matching_patterns.extend(
                    pattern_data.get("plan", {}).get("patterns", []),
                )

        return matching_patterns or ["default_pattern"]

    def _analyze_dependencies(self, issue: Issue) -> list[str]:
        dependencies = []

        if issue.type == IssueType.COMPLEXITY:
            dependencies.extend(
                [
                    "update_tests_for_extracted_methods",
                    "update_type_annotations",
                    "verify_imports",
                ],
            )

        if issue.type == IssueType.DRY_VIOLATION:
            dependencies.extend(
                ["update_all_usage_sites", "ensure_backward_compatibility"],
            )

        return dependencies

    def _identify_risks(self, issue: Issue) -> list[str]:
        risks = []

        if issue.type == IssueType.COMPLEXITY:
            risks.extend(
                [
                    "breaking_existing_functionality",
                    "changing_method_signatures",
                    "test_failures",
                ],
            )

        if issue.type == IssueType.DRY_VIOLATION:
            risks.extend(["breaking_dependent_code", "performance_impact"])

        return risks

    def _get_validation_steps(self, issue: Issue) -> list[str]:
        return [
            "run_fast_hooks",
            "run_full_tests",
            "run_comprehensive_hooks",
            "validate_complexity_reduction",
            "check_pattern_compliance",
        ]

    async def execute_with_plan(
        self,
        issue: Issue,
        plan: dict[str, t.Any],
    ) -> FixResult:
        """Execute the fix using the provided plan.

        This is called by analyze_and_fix_proactively() for issue types
        that ArchitectAgent handles directly (TYPE_ERROR, DEPENDENCY, etc.).
        """
        strategy = plan.get("strategy", "internal_pattern_based")

        if strategy == "external_specialist_guided":
            # This should have been delegated in analyze_and_fix()
            self.log(
                f"Warning: execute_with_plan() called for specialist issue {issue.type.value}"
            )
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Issue type {issue.type.value} should be delegated to specialist"
                ],
            )

        # Handle internal pattern-based fixes for types we support
        if issue.type == IssueType.TYPE_ERROR:
            return await self._fix_type_error_with_plan(issue, plan)

        if issue.type == IssueType.DEPENDENCY:
            return await self._fix_dependency_with_plan(issue, plan)

        if issue.type == IssueType.DOCUMENTATION:
            return await self._fix_documentation_with_plan(issue, plan)

        if issue.type == IssueType.TEST_ORGANIZATION:
            return await self._fix_test_organization_with_plan(issue, plan)

        # Unknown type for proactive handling
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                f"ArchitectAgent does not handle {issue.type.value} proactively"
            ],
        )

    async def _fix_type_error_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        """Handle type errors using the plan."""
        # For now, return a failure - type errors need careful analysis
        self.log(f"Type error fixing not yet implemented: {issue.message}")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Type error: {issue.message}"],
        )

    async def _fix_dependency_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        """Handle dependency issues using the plan."""
        # For now, return a failure - dependency issues need careful analysis
        self.log(f"Dependency fixing not yet implemented: {issue.message}")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Dependency issue: {issue.message}"],
        )

    async def _fix_documentation_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        """Handle documentation issues using the plan."""
        # For now, return a failure - documentation issues need careful analysis
        self.log(f"Documentation fixing not yet implemented: {issue.message}")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Documentation issue: {issue.message}"],
        )

    async def _fix_test_organization_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        """Handle test organization issues using the plan."""
        # For now, return a failure - test organization needs careful analysis
        self.log(f"Test organization fixing not yet implemented: {issue.message}")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Test organization issue: {issue.message}"],
        )

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        # Delegate to specialized agents based on issue type
        if issue.type in {
            IssueType.COMPLEXITY,
            IssueType.DRY_VIOLATION,
            IssueType.DEAD_CODE,
        }:
            self.log(f"Delegating to RefactoringAgent for {issue.type.value}")
            return await self._refactoring_agent.analyze_and_fix(issue)

        if issue.type == IssueType.FORMATTING:
            self.log(f"Delegating to FormattingAgent for {issue.type.value}")
            return await self._formatting_agent.analyze_and_fix(issue)

        if issue.type == IssueType.IMPORT_ERROR:
            self.log(f"Delegating to ImportOptimizationAgent for {issue.type.value}")
            return await self._import_agent.analyze_and_fix(issue)

        if issue.type == IssueType.SECURITY:
            self.log(f"Delegating to SecurityAgent for {issue.type.value}")
            return await self._security_agent.analyze_and_fix(issue)

        # For types we still handle, use proactive approach
        return await self.analyze_and_fix_proactively(issue)


agent_registry.register(ArchitectAgent)
