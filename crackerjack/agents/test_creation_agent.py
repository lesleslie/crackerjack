from pathlib import Path
from typing import Any

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)
from .helpers.test_creation.test_ast_analyzer import TestASTAnalyzer
from .helpers.test_creation.test_coverage_analyzer import TestCoverageAnalyzer
from .helpers.test_creation.test_template_generator import TestTemplateGenerator


class TestCreationAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self._ast_analyzer = TestASTAnalyzer(context)
        self._template_generator = TestTemplateGenerator(context)
        self._coverage_analyzer = TestCoverageAnalyzer(context)

    def get_supported_types(self) -> set[IssueType]:
        return {
            IssueType.TEST_FAILURE,
            IssueType.DEPENDENCY,
            IssueType.TEST_ORGANIZATION,
            IssueType.COVERAGE_IMPROVEMENT,
        }

    async def can_handle(self, issue: Issue) -> float:
        if issue.type not in self.get_supported_types():
            return 0.0

        message_lower = issue.message.lower()

        if issue.type == IssueType.COVERAGE_IMPROVEMENT:
            if any(
                term in message_lower
                for term in (
                    "coverage below",
                    "missing tests",
                    "untested functions",
                    "no tests found",
                    "coverage requirement",
                )
            ):
                return 0.95
            return 0.9

        if issue.type == IssueType.TEST_ORGANIZATION:
            return self._check_test_organization_confidence(message_lower)

        perfect_score = self._check_perfect_test_creation_matches(message_lower)
        if perfect_score > 0:
            return perfect_score

        good_score = self._check_good_test_creation_matches(message_lower)
        if good_score > 0:
            return good_score

        file_path_score = self._check_file_path_test_indicators(issue.file_path)
        if file_path_score > 0:
            return file_path_score

        if self._indicates_untested_functions(message_lower):
            return 0.85

        return 0.0

    def _check_test_organization_confidence(self, message_lower: str) -> float:
        organization_keywords = [
            "redundant tests",
            "duplicate tests",
            "overlapping tests",
            "consolidate tests",
            "test suite optimization",
            "obsolete tests",
            "broken tests",
            "coverage booster",
            "victory test",
            "test cleanup",
        ]
        return (
            0.9
            if any(keyword in message_lower for keyword in organization_keywords)
            else 0.7
        )

    def _check_perfect_test_creation_matches(self, message_lower: str) -> float:
        perfect_keywords = [
            "coverage below",
            "missing tests",
            "untested",
            "no tests found",
            "test coverage",
            "coverage requirement",
            "coverage gap",
        ]
        return (
            1.0
            if any(keyword in message_lower for keyword in perfect_keywords)
            else 0.0
        )

    def _check_good_test_creation_matches(self, message_lower: str) -> float:
        good_keywords = [
            "coverage",
            "test",
            "missing",
            "untested code",
            "no test",
            "empty test",
            "test missing",
        ]
        return (
            0.8 if any(keyword in message_lower for keyword in good_keywords) else 0.0
        )

    def _check_file_path_test_indicators(self, file_path: str | None) -> float:
        if not file_path:
            return 0.0

        if not self._has_corresponding_test(file_path):
            if any(
                core_path in file_path
                for core_path in ("/managers/", "/services/", "/core/", "/agents/")
            ):
                return 0.8
            return 0.7
        return 0.0

    def _indicates_untested_functions(self, message_lower: str) -> bool:
        return any(
            indicator in message_lower
            for indicator in (
                "function not tested",
                "untested method",
                "no test for function",
                "function coverage",
                "method coverage",
                "untested code path",
            )
        )

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self._log_analysis(issue)

        return await self._apply_fixes_and_create_result(issue)

    def _log_analysis(self, issue: Issue) -> None:
        self.log(f"Analyzing test creation need: {issue.message}")

    async def _apply_fixes_and_create_result(self, issue: Issue) -> FixResult:
        try:
            fixes_applied, files_modified = await self._apply_test_creation_fixes(issue)
            return self._create_test_creation_result(fixes_applied, files_modified)

        except Exception as e:
            self.log(f"Error creating tests: {e}", "ERROR")
            return self._create_error_result(e)

    async def _apply_test_creation_fixes(
        self,
        issue: Issue,
    ) -> tuple[list[str], list[str]]:
        return await self._apply_all_test_creation_fixes(issue)

    async def _apply_all_test_creation_fixes(
        self,
        issue: Issue,
    ) -> tuple[list[str], list[str]]:
        fixes_applied: list[str] = []
        files_modified: list[str] = []

        fixes_applied, files_modified = await self._apply_all_fix_types(
            issue, fixes_applied, files_modified
        )

        return fixes_applied, files_modified

    async def _apply_all_fix_types(
        self,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        return await self._apply_sequential_fixes(issue, fixes_applied, files_modified)

    async def _apply_sequential_fixes(
        self,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        return await self._apply_all_fix_types_sequentially(
            issue, fixes_applied, files_modified
        )

    async def _apply_all_fix_types_sequentially(
        self,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        return await self._apply_all_fix_types_in_sequence(
            issue, fixes_applied, files_modified
        )

    async def _apply_all_fix_types_in_sequence(
        self,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        return await self._apply_fix_types_in_defined_order(
            issue, fixes_applied, files_modified
        )

    async def _apply_fix_types_in_defined_order(
        self,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        (
            fixes_applied,
            files_modified,
        ) = await self._apply_coverage_based_fixes_sequentially(
            fixes_applied, files_modified
        )

        (
            fixes_applied,
            files_modified,
        ) = await self._apply_file_specific_fixes_sequentially(
            issue, fixes_applied, files_modified
        )

        (
            fixes_applied,
            files_modified,
        ) = await self._apply_function_specific_fixes_sequentially(
            fixes_applied, files_modified
        )

        return fixes_applied, files_modified

    async def _apply_coverage_based_fixes_sequentially(
        self,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        coverage_fixes, coverage_files = await self._apply_coverage_based_fixes()
        fixes_applied.extend(coverage_fixes)
        files_modified.extend(coverage_files)
        return fixes_applied, files_modified

    async def _apply_file_specific_fixes_sequentially(
        self,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        file_fixes, file_modified = await self._apply_file_specific_fixes(
            issue.file_path,
        )
        fixes_applied.extend(file_fixes)
        files_modified.extend(file_modified)
        return fixes_applied, files_modified

    async def _apply_function_specific_fixes_sequentially(
        self,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        function_fixes, function_files = await self._apply_function_specific_fixes()
        fixes_applied.extend(function_fixes)
        files_modified.extend(function_files)
        return fixes_applied, files_modified

    async def _apply_coverage_fixes(
        self,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        coverage_fixes, coverage_files = await self._apply_coverage_based_fixes()
        fixes_applied.extend(coverage_fixes)
        files_modified.extend(coverage_files)
        return fixes_applied, files_modified

    async def _apply_file_fixes(
        self,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        file_fixes, file_modified = await self._apply_file_specific_fixes(
            issue.file_path,
        )
        fixes_applied.extend(file_fixes)
        files_modified.extend(file_modified)
        return fixes_applied, files_modified

    async def _apply_function_fixes(
        self,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        function_fixes, function_files = await self._apply_function_specific_fixes()
        fixes_applied.extend(function_fixes)
        files_modified.extend(function_files)
        return fixes_applied, files_modified

    async def _apply_coverage_based_fixes(self) -> tuple[list[str], list[str]]:
        fixes_applied: list[str] = []
        files_modified: list[str] = []

        coverage_analysis = await self._analyze_coverage()

        if coverage_analysis["below_threshold"]:
            fixes_applied, files_modified = await self._handle_low_coverage(
                coverage_analysis, fixes_applied, files_modified
            )

        return fixes_applied, files_modified

    async def _handle_low_coverage(
        self,
        coverage_analysis: dict[str, Any],
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        self.log(
            f"Coverage below threshold: {coverage_analysis['current_coverage']: .1%}",
        )

        return await self._process_uncovered_modules_for_low_coverage(
            coverage_analysis["uncovered_modules"], fixes_applied, files_modified
        )

    async def _process_uncovered_modules_for_low_coverage(
        self,
        uncovered_modules: list[str],
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        for module_path in uncovered_modules:
            test_fixes = await self._create_tests_for_module(module_path)
            fixes_applied.extend(test_fixes["fixes"])
            files_modified.extend(test_fixes["files"])

        return fixes_applied, files_modified

    async def _process_uncovered_modules(
        self,
        uncovered_modules: list[str],
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        return await self._process_each_uncovered_module(
            uncovered_modules, fixes_applied, files_modified
        )

    async def _process_each_uncovered_module(
        self,
        uncovered_modules: list[str],
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        return await self._process_all_uncovered_modules(
            uncovered_modules, fixes_applied, files_modified
        )

    async def _process_all_uncovered_modules(
        self,
        uncovered_modules: list[str],
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        for module_path in uncovered_modules:
            fixes_applied, files_modified = await self._process_single_uncovered_module(
                module_path, fixes_applied, files_modified
            )

        return fixes_applied, files_modified

    async def _process_single_uncovered_module(
        self,
        module_path: str,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        test_fixes = await self._create_tests_for_module(module_path)
        fixes_applied.extend(test_fixes["fixes"])
        files_modified.extend(test_fixes["files"])
        return fixes_applied, files_modified

    async def _apply_file_specific_fixes(
        self,
        file_path: str | None,
    ) -> tuple[list[str], list[str]]:
        if not file_path:
            return [], []

        file_fixes = await self._create_tests_for_file(file_path)
        return file_fixes["fixes"], file_fixes["files"]

    async def _apply_function_specific_fixes(self) -> tuple[list[str], list[str]]:
        fixes_applied: list[str] = []
        files_modified: list[str] = []

        untested_functions = await self._find_untested_functions()
        fixes_applied, files_modified = await self._process_untested_functions(
            untested_functions, fixes_applied, files_modified
        )

        return fixes_applied, files_modified

    async def _process_untested_functions(
        self,
        untested_functions: list[dict[str, Any]],
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        for func_info in untested_functions[:5]:
            func_fixes = await self._create_test_for_function(func_info)
            fixes_applied.extend(func_fixes["fixes"])
            files_modified.extend(func_fixes["files"])

        return fixes_applied, files_modified

    def _create_test_creation_result(
        self,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> FixResult:
        success = len(fixes_applied) > 0

        confidence = self._calculate_confidence(success, fixes_applied, files_modified)

        return FixResult(
            success=success,
            confidence=confidence,
            fixes_applied=fixes_applied,
            remaining_issues=[],
            recommendations=self._generate_recommendations(success),
            files_modified=files_modified,
        )

    def _calculate_confidence(
        self, success: bool, fixes_applied: list[str], files_modified: list[str]
    ) -> float:
        if not success:
            return 0.0

        confidence = 0.5

        test_file_fixes = [f for f in fixes_applied if "test file" in f.lower()]
        function_fixes = [f for f in fixes_applied if "function" in f.lower()]
        coverage_fixes = [f for f in fixes_applied if "coverage" in f.lower()]

        if test_file_fixes:
            confidence += 0.25
        if function_fixes:
            confidence += 0.15
        if coverage_fixes:
            confidence += 0.1

        if len(files_modified) > 1:
            confidence += 0.1

        return min(confidence, 0.95)

    def _generate_recommendations(self, success: bool) -> list[str]:
        if success:
            return [
                "Generated comprehensive test suite",
                "Consider running pytest to validate new tests",
                "Review generated tests for edge cases",
            ]
        return [
            "No test creation opportunities identified",
            "Consider manual test creation for complex scenarios",
        ]

    def _get_enhanced_test_creation_recommendations(self) -> list[str]:
        return [
            "Run 'python -m crackerjack -t' to execute comprehensive coverage analysis",
            (
                "Focus on testing high-priority functions in managers/ services/ "
                "and core/ modules"
            ),
            (
                "Implement parametrized tests (@pytest.mark.parametrize) "
                "for functions with multiple arguments"
            ),
            "Add edge case testing for boundary conditions and error scenarios",
            "Use fixtures for complex object instantiation and dependency injection",
            "Consider integration tests for modules with multiple classes/functions",
            "Add async tests for coroutine functions using @pytest.mark.asyncio",
            "Mock external dependencies to ensure isolated unit testing",
            "Target ≥10% coverage improvement through systematic test creation",
            "Validate generated tests are syntactically correct before committing",
        ]

    def _create_error_result(self, error: Exception) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to create tests: {error}"],
            recommendations=[
                "Manual test creation may be required",
                "Check existing test structure and patterns",
            ],
        )

    async def _analyze_coverage(self) -> dict[str, Any]:
        return await self._coverage_analyzer.analyze_coverage()

    async def _create_tests_for_module(self, module_path: str) -> dict[str, list[str]]:
        return await self._coverage_analyzer.create_tests_for_module(module_path)

    async def _create_tests_for_file(self, file_path: str) -> dict[str, list[str]]:
        return await self._coverage_analyzer.create_tests_for_file(file_path)

    async def _find_untested_functions(self) -> list[dict[str, Any]]:
        return await self._coverage_analyzer.find_untested_functions()

    async def _create_test_for_function(
        self,
        func_info: dict[str, Any],
    ) -> dict[str, list[str]]:
        return await self._coverage_analyzer.create_test_for_function(func_info)

    async def _extract_functions_from_file(
        self,
        file_path: Path,
    ) -> list[dict[str, Any]]:
        return await self._ast_analyzer.extract_functions_from_file(file_path)

    async def _extract_classes_from_file(self, file_path: Path) -> list[dict[str, Any]]:
        return await self._ast_analyzer.extract_classes_from_file(file_path)

    async def _function_has_test(
        self,
        func_info: dict[str, Any],
        file_path: Path,
    ) -> bool:
        return await self._ast_analyzer.function_has_test(func_info, file_path)

    async def _generate_test_file_path(self, source_file: Path) -> Path:
        return await self._ast_analyzer.generate_test_file_path(source_file)

    def _has_corresponding_test(self, file_path: str) -> bool:
        return self._ast_analyzer.has_corresponding_test(file_path)

    async def _generate_test_content(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
    ) -> str:
        return await self._template_generator.generate_test_content(
            module_file, functions, classes
        )


agent_registry.register(TestCreationAgent)
