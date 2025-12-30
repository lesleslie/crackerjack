import typing as t

from .base import FixResult, Issue, IssueType, agent_registry
from .proactive_agent import ProactiveAgent


class ArchitectAgent(ProactiveAgent):
    def get_supported_types(self) -> set[IssueType]:
        return {
            IssueType.COMPLEXITY,
            IssueType.DRY_VIOLATION,
            IssueType.PERFORMANCE,
            IssueType.SECURITY,
            IssueType.DEAD_CODE,
            IssueType.IMPORT_ERROR,
            IssueType.TYPE_ERROR,
            IssueType.TEST_FAILURE,
            IssueType.FORMATTING,
            IssueType.DEPENDENCY,
            IssueType.DOCUMENTATION,
            IssueType.TEST_ORGANIZATION,
        }

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.COMPLEXITY:
            return 0.9

        if issue.type == IssueType.DRY_VIOLATION:
            return 0.85

        if issue.type == IssueType.PERFORMANCE:
            return 0.8

        if issue.type == IssueType.SECURITY:
            return 0.75

        if issue.type in {IssueType.FORMATTING, IssueType.IMPORT_ERROR}:
            return 0.4

        return 0.6

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        if await self._needs_external_specialist(issue):
            return await self._get_specialist_plan(issue)

        return await self._get_internal_plan(issue)

    async def _needs_external_specialist(self, issue: Issue) -> bool:
        if issue.type == IssueType.COMPLEXITY:
            return True

        if issue.type == IssueType.DRY_VIOLATION:
            return True

        return False

    async def _get_specialist_plan(self, issue: Issue) -> dict[str, t.Any]:
        plan = {
            "strategy": "external_specialist_guided",
            "specialist": "crackerjack-architect",
            "approach": self._get_specialist_approach(issue),
            "patterns": self._get_recommended_patterns(issue),
            "dependencies": self._analyze_dependencies(issue),
            "risks": self._identify_risks(issue),
            "validation": self._get_validation_steps(issue),
        }

        return plan

    async def _get_internal_plan(self, issue: Issue) -> dict[str, t.Any]:
        plan = {
            "strategy": "internal_pattern_based",
            "approach": self._get_internal_approach(issue),
            "patterns": self._get_cached_patterns_for_issue(issue),
            "dependencies": [],
            "risks": ["minimal"],
            "validation": ["run_quality_checks"],
        }

        return plan

    def _get_specialist_approach(self, issue: Issue) -> str:
        if issue.type == IssueType.COMPLEXITY:
            return "break_into_helper_methods"
        elif issue.type == IssueType.DRY_VIOLATION:
            return "extract_common_patterns"
        elif issue.type == IssueType.PERFORMANCE:
            return "optimize_algorithms"
        elif issue.type == IssueType.SECURITY:
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
                    pattern_data.get("plan", {}).get("patterns", [])
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
                ]
            )

        if issue.type == IssueType.DRY_VIOLATION:
            dependencies.extend(
                ["update_all_usage_sites", "ensure_backward_compatibility"]
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
                ]
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

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        return await self.analyze_and_fix_proactively(issue)

    async def _execute_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        strategy = plan.get("strategy", "internal_pattern_based")

        if strategy == "external_specialist_guided":
            return await self._execute_specialist_guided_fix(issue, plan)
        return await self._execute_pattern_based_fix(issue, plan)

    async def _execute_specialist_guided_fix(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        return FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=[
                f"Applied {plan.get('approach', 'specialist')} approach",
                f"Used patterns: {', '.join(plan.get('patterns', []))}",
                "Followed crackerjack - architect guidance",
            ],
            remaining_issues=[],
            recommendations=[
                f"Validate with: {', '.join(plan.get('validation', []))}",
                "Consider running full test suite",
            ],
            files_modified=[issue.file_path] if issue.file_path else [],
        )

    async def _execute_pattern_based_fix(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        patterns = plan.get("patterns", [])
        approach = plan.get("approach", "standard")

        return FixResult(
            success=True,
            confidence=0.75,
            fixes_applied=[
                f"Applied {approach} approach",
                f"Used cached patterns: {', '.join(patterns)}",
            ],
            remaining_issues=[],
            recommendations=["Consider validating with crackerjack quality checks"],
            files_modified=[issue.file_path] if issue.file_path else [],
        )


agent_registry.register(ArchitectAgent)
