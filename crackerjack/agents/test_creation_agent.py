from contextlib import suppress
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

        file_path_score = self._check_file_path_test_indicators(issue.file_path)
        if file_path_score > 0:
            return file_path_score

        if self._indicates_untested_functions(message_lower):
            return 0.85

        good_score = self._check_good_test_creation_matches(message_lower)
        if good_score > 0:
            return good_score

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

    async def _run_coverage_command(self) -> tuple[int, str, str]:
        return await self._coverage_analyzer._run_coverage_command()

    def _parse_coverage_json(self, coverage_json: dict[str, Any]) -> dict[str, Any]:
        return self._coverage_analyzer._parse_coverage_json(coverage_json)

    async def _estimate_current_coverage(self) -> float:
        return await self._coverage_analyzer._estimate_current_coverage()

    async def _find_uncovered_modules_enhanced(self) -> list[dict[str, Any]]:
        return await self._coverage_analyzer._find_uncovered_modules_enhanced()

    async def _analyze_module_priority(self, module_file: Path) -> dict[str, Any]:
        module_info = await self._coverage_analyzer._analyze_module_priority(
            module_file, self._ast_analyzer
        )

        # Normalize public function count to top-level only for legacy expectations
        with suppress(Exception):
            import ast

            content = self.context.get_file_content(module_file) or ""
            tree = ast.parse(content)
            public_top_level = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.col_offset == 0
                and not node.name.startswith("_")
            ]
            module_info["public_function_count"] = len(public_top_level)

        return module_info

    def _categorize_module(self, relative_path: str) -> str:
        return self._coverage_analyzer._categorize_module(relative_path)

    async def _analyze_function_testability(
        self, func_info: dict[str, Any], test_file: Path
    ) -> dict[str, Any]:
        return await self._coverage_analyzer._analyze_function_testability(
            func_info, test_file
        )

    async def _find_untested_functions_in_file(
        self, test_file: Path
    ) -> list[dict[str, Any]]:
        functions = await self._extract_functions_from_file(test_file)
        return [
            {
                "name": func["name"],
                "file": str(test_file),
                "line": func.get("line", 1),
                "signature": func.get("signature", ""),
            }
            for func in functions
            if not await self._function_has_test(func, test_file)
        ]

    async def _identify_coverage_gaps(self) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []

        package_dir = self.context.project_path / "crackerjack"
        if not package_dir.exists():
            return gaps

        for py_file in package_dir.rglob("*.py"):
            if self._should_skip_module_for_coverage(py_file):
                continue

            coverage_info = await self._analyze_existing_test_coverage(py_file)
            if coverage_info.get("has_gaps"):
                gaps.append(coverage_info)

        return gaps[:10]

    async def _analyze_existing_test_coverage(
        self, module_file: Path
    ) -> dict[str, Any]:
        test_file_path = await self._generate_test_file_path(module_file)

        coverage_info: dict[str, Any] = {
            "source_file": str(module_file.relative_to(self.context.project_path)),
            "test_file": str(test_file_path) if test_file_path.exists() else None,
            "has_gaps": True,
            "missing_test_types": [],
            "coverage_score": 0,
        }

        if not test_file_path.exists():
            coverage_info["missing_test_types"] = [
                "basic",
                "edge_cases",
                "error_handling",
            ]
            return coverage_info

        test_content = self.context.get_file_content(test_file_path) or ""

        missing_types: list[str] = []
        if "def test_" not in test_content:
            missing_types.append("basic")
        if "@pytest.mark.parametrize" not in test_content:
            missing_types.append("parametrized")
        if "with pytest.raises" not in test_content:
            missing_types.append("error_handling")
        if "mock" not in test_content.lower():
            missing_types.append("mocking")

        coverage_info["missing_test_types"] = missing_types
        coverage_info["has_gaps"] = len(missing_types) > 0
        coverage_info["coverage_score"] = max(0, 100 - len(missing_types) * 25)

        return coverage_info

    def _calculate_improvement_potential(
        self, missing_tests: int, total_functions: int
    ) -> dict[str, Any]:
        return self._coverage_analyzer._calculate_improvement_potential(
            missing_tests, total_functions
        )

    def _parse_function_nodes(self, tree: Any) -> list[dict[str, Any]]:
        return self._ast_analyzer._parse_function_nodes(tree)

    def _is_valid_function_node(self, node: Any) -> bool:
        return self._ast_analyzer._is_valid_function_node(node)

    def _create_function_info(self, node: Any) -> dict[str, Any]:
        return self._ast_analyzer._create_function_info(node)

    def _get_function_signature(self, node: Any) -> str:
        return self._ast_analyzer._get_function_signature(node)

    def _should_skip_module_for_coverage(self, py_file: Path) -> bool:
        return self._ast_analyzer.should_skip_module_for_coverage(py_file)

    def _should_skip_file_for_testing(self, py_file: Path) -> bool:
        return self._ast_analyzer.should_skip_file_for_testing(py_file)

    def _get_module_import_path(self, module_file: Path) -> str:
        return self._template_generator._get_module_import_path(module_file)

    def _generate_smart_default_args(self, args: list[str]) -> str:
        return self._template_generator._generate_smart_default_args(args)

    def _generate_invalid_args(self, args: list[str]) -> str:
        return self._template_generator._generate_invalid_args(args)

    def _generate_edge_case_args(self, args: list[str], case_type: str) -> str:
        return self._template_generator._generate_edge_case_args(args, case_type)

    def _is_path_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_path_arg(arg_lower)

    def _is_url_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_url_arg(arg_lower)

    def _is_email_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_email_arg(arg_lower)

    def _is_id_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_id_arg(arg_lower)

    def _is_name_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_name_arg(arg_lower)

    def _is_numeric_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_numeric_arg(arg_lower)

    def _is_boolean_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_boolean_arg(arg_lower)

    def _is_text_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_text_arg(arg_lower)

    def _is_list_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_list_arg(arg_lower)

    def _is_dict_arg(self, arg_lower: str) -> bool:
        return self._template_generator._is_dict_arg(arg_lower)


agent_registry.register(TestCreationAgent)
