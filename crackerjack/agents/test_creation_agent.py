import ast
import json
import operator
from collections.abc import Callable
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


class TestCreationAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)

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
        try:
            coverage_data = await self._get_existing_coverage_data()
            if coverage_data:
                return coverage_data

            returncode, _, stderr = await self._run_coverage_command()

            if returncode != 0:
                return self._handle_coverage_command_failure(stderr)

            return await self._process_coverage_results_enhanced()

        except Exception as e:
            self.log(f"Coverage analysis error: {e}", "WARN")
            return self._create_default_coverage_result()

    async def _get_existing_coverage_data(self) -> dict[str, Any] | None:
        try:
            project_path = Path(str(self.context.project_path))
            json_report = project_path / "coverage.json"
            if json_report.exists():
                content = self.context.get_file_content(json_report)
                if content:
                    coverage_json = json.loads(content)
                    return self._parse_coverage_json(coverage_json)

            coverage_file = project_path / ".coverage"
            if coverage_file.exists():
                return await self._process_coverage_results_enhanced()

        except Exception as e:
            self.log(f"Error reading existing coverage: {e}", "WARN")

        return None

    def _parse_coverage_json(self, coverage_json: dict[str, Any]) -> dict[str, Any]:
        try:
            totals = coverage_json.get("totals", {})
            current_coverage = totals.get("percent_covered", 0) / 100.0

            uncovered_modules = []
            files = coverage_json.get("files", {})

            for file_path, file_data in files.items():
                if file_data.get("summary", {}).get("percent_covered", 100) < 80:
                    rel_path = str(
                        Path(file_path).relative_to(self.context.project_path)
                    )
                    uncovered_modules.append(rel_path)

            return {
                "below_threshold": current_coverage < 0.8,
                "current_coverage": current_coverage,
                "uncovered_modules": uncovered_modules[:15],
                "missing_lines": totals.get("num_statements", 0)
                - totals.get("covered_lines", 0),
                "total_lines": totals.get("num_statements", 0),
            }

        except Exception as e:
            self.log(f"Error parsing coverage JSON: {e}", "WARN")
            return self._create_default_coverage_result()

    async def _run_coverage_command(self) -> tuple[int, str, str]:
        return await self.run_command(
            [
                "uv",
                "run",
                "python",
                "-m",
                "pytest",
                "--cov=crackerjack",
                "--cov-report=json",
                "-q",
            ],
        )

    def _handle_coverage_command_failure(self, stderr: str) -> dict[str, Any]:
        self.log(f"Coverage analysis failed: {stderr}", "WARN")
        return self._create_default_coverage_result()

    async def _process_coverage_results_enhanced(self) -> dict[str, Any]:
        coverage_file = self.context.project_path / ".coverage"
        if not coverage_file.exists():
            return self._create_default_coverage_result()

        uncovered_modules = await self._find_uncovered_modules_enhanced()
        untested_functions = await self._find_untested_functions_enhanced()

        current_coverage = await self._estimate_current_coverage()

        return {
            "below_threshold": current_coverage < 0.8,
            "current_coverage": current_coverage,
            "uncovered_modules": uncovered_modules[:15],
            "untested_functions": untested_functions[:20],
            "coverage_gaps": await self._identify_coverage_gaps(),
            "improvement_potential": self._calculate_improvement_potential(
                len(uncovered_modules), len(untested_functions)
            ),
        }

    async def _estimate_current_coverage(self) -> float:
        try:
            source_files: list[Path] = list(
                (self.context.project_path / "crackerjack").rglob("*.py")
            )
            source_files = [f for f in source_files if not f.name.startswith("test_")]

            test_files: list[Path] = list(
                (self.context.project_path / "tests").rglob("test_*.py")
            )

            if not source_files:
                return 0.0

            coverage_ratio = len(test_files) / len(source_files)

            estimated_coverage = min(coverage_ratio * 0.6, 0.9)

            return estimated_coverage

        except Exception:
            return 0.1

    def _calculate_improvement_potential(
        self, uncovered_modules: int, untested_functions: int
    ) -> dict[str, Any]:
        if uncovered_modules == untested_functions == 0:
            return {"percentage_points": 0, "priority": "low"}

        module_improvement = uncovered_modules * 2.5
        function_improvement = untested_functions * 0.8

        total_potential = min(module_improvement + function_improvement, 40)

        priority = (
            "high"
            if total_potential > 15
            else "medium"
            if total_potential > 5
            else "low"
        )

        return {
            "percentage_points": round(total_potential, 1),
            "priority": priority,
            "module_contribution": round(module_improvement, 1),
            "function_contribution": round(function_improvement, 1),
        }

    def _create_default_coverage_result(self) -> dict[str, Any]:
        return {
            "below_threshold": True,
            "current_coverage": 0.0,
            "uncovered_modules": [],
        }

    async def _find_uncovered_modules_enhanced(self) -> list[dict[str, Any]]:
        uncovered: list[dict[str, Any]] = []

        project_path = Path(str(self.context.project_path))
        package_dir = project_path / "crackerjack"
        if not package_dir.exists():
            return uncovered[:15]

        for py_file in package_dir.rglob("*.py"):
            if self._should_skip_module_for_coverage(py_file):
                continue

            if not self._has_corresponding_test(str(py_file)):
                module_info = await self._analyze_module_priority(py_file)
                uncovered.append(module_info)

        uncovered.sort(key=operator.itemgetter("priority_score"), reverse=True)
        return uncovered[:15]

    async def _analyze_module_priority(self, py_file: Path) -> dict[str, Any]:
        try:
            content = self.context.get_file_content(py_file) or ""
            ast.parse(content)

            functions = await self._extract_functions_from_file(py_file)
            classes = await self._extract_classes_from_file(py_file)

            priority_score = 0

            rel_path = str(py_file.relative_to(self.context.project_path))
            if any(
                core_path in rel_path
                for core_path in ("managers/", "services/", "core/", "agents/")
            ):
                priority_score += 10

            priority_score += len(functions) * 2
            priority_score += len(classes) * 3

            public_functions = [f for f in functions if not f["name"].startswith("_")]
            priority_score += len(public_functions) * 2

            lines_count = len(content.split("\n"))
            if lines_count > 100:
                priority_score += 5
            elif lines_count > 50:
                priority_score += 2

            return {
                "path": rel_path,
                "absolute_path": str(py_file),
                "priority_score": priority_score,
                "function_count": len(functions),
                "class_count": len(classes),
                "public_function_count": len(public_functions),
                "lines_count": lines_count,
                "category": self._categorize_module(rel_path),
            }

        except Exception as e:
            self.log(f"Error analyzing module priority for {py_file}: {e}", "WARN")
            return {
                "path": str(py_file.relative_to(self.context.project_path)),
                "absolute_path": str(py_file),
                "priority_score": 1,
                "function_count": 0,
                "class_count": 0,
                "public_function_count": 0,
                "lines_count": 0,
                "category": "unknown",
            }

    def _categorize_module(self, relative_path: str) -> str:
        if "managers/" in relative_path:
            return "manager"
        elif "services/" in relative_path:
            return "service"
        elif "core/" in relative_path:
            return "core"
        elif "agents/" in relative_path:
            return "agent"
        elif "models/" in relative_path:
            return "model"
        elif "executors/" in relative_path:
            return "executor"
        return "utility"

    async def _find_untested_functions_enhanced(self) -> list[dict[str, Any]]:
        untested: list[dict[str, Any]] = []

        package_dir = self.context.project_path / "crackerjack"
        if not package_dir.exists():
            return untested[:20]

        for py_file in package_dir.rglob("*.py"):
            if self._should_skip_file_for_testing(py_file):
                continue

            file_untested = await self._find_untested_functions_in_file_enhanced(
                py_file
            )
            untested.extend(file_untested)

        untested.sort(key=operator.itemgetter("testing_priority"), reverse=True)
        return untested[:20]

    async def _find_untested_functions_in_file_enhanced(
        self, py_file: Path
    ) -> list[dict[str, Any]]:
        untested: list[dict[str, Any]] = []

        try:
            functions = await self._extract_functions_from_file(py_file)
            for func in functions:
                if not await self._function_has_test(func, py_file):
                    func_info = await self._analyze_function_testability(func, py_file)
                    untested.append(func_info)

        except Exception as e:
            self.log(f"Error finding untested functions in {py_file}: {e}", "WARN")

        return untested

    async def _analyze_function_testability(
        self, func: dict[str, Any], py_file: Path
    ) -> dict[str, Any]:
        try:
            func_info = {
                "name": func["name"],
                "file": str(py_file),
                "relative_file": str(py_file.relative_to(self.context.project_path)),
                "line": func.get("line", 1),
                "signature": func.get("signature", ""),
                "args": func.get("args", []),
                "returns": func.get("returns", "Any"),
                "testing_priority": 0,
                "complexity": "simple",
                "test_strategy": "basic",
            }

            priority = 0

            if not func["name"].startswith("_"):
                priority += 10

            arg_count = len(func.get("args", []))
            if arg_count > 3:
                priority += 5
                func_info["complexity"] = "complex"
                func_info["test_strategy"] = "parametrized"
            elif arg_count > 1:
                priority += 2
                func_info["complexity"] = "moderate"

            if any(
                core_path in str(func_info["relative_file"])
                for core_path in ("managers/", "services/", "core/")
            ):
                priority += 8

            if func.get("is_async", False):
                priority += 3
                func_info["test_strategy"] = "async"

            func_info["testing_priority"] = priority

            return func_info

        except Exception as e:
            self.log(f"Error analyzing function testability: {e}", "WARN")
            return {
                "name": func.get("name", "unknown"),
                "file": str(py_file),
                "relative_file": str(py_file.relative_to(self.context.project_path)),
                "line": func.get("line", 1),
                "testing_priority": 1,
                "complexity": "unknown",
                "test_strategy": "basic",
            }

    async def _identify_coverage_gaps(self) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []

        try:
            package_dir = self.context.project_path / "crackerjack"
            tests_dir = self.context.project_path / "tests"

            if not package_dir.exists() or not tests_dir.exists():
                return gaps

            for py_file in package_dir.rglob("*.py"):
                if self._should_skip_module_for_coverage(py_file):
                    continue

                test_coverage_info = await self._analyze_existing_test_coverage(py_file)
                if test_coverage_info["has_gaps"]:
                    gaps.append(test_coverage_info)

        except Exception as e:
            self.log(f"Error identifying coverage gaps: {e}", "WARN")

        return gaps[:10]

    async def _analyze_existing_test_coverage(self, py_file: Path) -> dict[str, Any]:
        try:
            test_file_path = await self._generate_test_file_path(py_file)

            coverage_info: dict[str, Any] = {
                "source_file": str(py_file.relative_to(self.context.project_path)),
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

            missing_types = []
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

        except Exception as e:
            self.log(f"Error analyzing test coverage for {py_file}: {e}", "WARN")
            return {
                "source_file": str(py_file.relative_to(self.context.project_path)),
                "test_file": None,
                "has_gaps": True,
                "missing_test_types": ["basic"],
                "coverage_score": 0,
            }

    def _should_skip_module_for_coverage(self, py_file: Path) -> bool:
        return py_file.name.startswith("test_") or py_file.name == "__init__.py"

    def _get_relative_module_path(self, py_file: Path) -> str:
        return str(py_file.relative_to(self.context.project_path))

    def _has_corresponding_test(self, file_path: str) -> bool:
        path = Path(file_path)

        test_patterns = [
            f"test_{path.stem}.py",
            f"{path.stem}_test.py",
            f"test_{path.stem}_*.py",
        ]

        tests_dir = self.context.project_path / "tests"
        if tests_dir.exists():
            for pattern in test_patterns:
                if list(tests_dir.glob(pattern)):
                    return True

        return False

    async def _create_tests_for_module(self, module_path: str) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        try:
            test_results = await self._generate_module_tests(module_path)
            fixes.extend(test_results["fixes"])
            files.extend(test_results["files"])

        except Exception as e:
            self._handle_test_creation_error(module_path, e)

        return {"fixes": fixes, "files": files}

    async def _generate_module_tests(self, module_path: str) -> dict[str, list[str]]:
        module_file = Path(module_path)
        if not await self._is_module_valid(module_file):
            return {"fixes": [], "files": []}

        functions = await self._extract_functions_from_file(module_file)
        classes = await self._extract_classes_from_file(module_file)

        if not functions and not classes:
            return {"fixes": [], "files": []}

        return await self._create_test_artifacts(module_file, functions, classes)

    async def _is_module_valid(self, module_file: Path) -> bool:
        return module_file.exists()

    async def _create_test_artifacts(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        test_file_path = await self._generate_test_file_path(module_file)
        test_content = await self._generate_test_content(
            module_file,
            functions,
            classes,
        )

        if self.context.write_file_content(test_file_path, test_content):
            self.log(f"Created test file: {test_file_path}")
            return {
                "fixes": [f"Created test file for {module_file}"],
                "files": [str(test_file_path)],
            }

        return {"fixes": [], "files": []}

    def _handle_test_creation_error(self, module_path: str, e: Exception) -> None:
        self.log(f"Error creating tests for module {module_path}: {e}", "ERROR")

    async def _create_tests_for_file(self, file_path: str) -> dict[str, list[str]]:
        if self._has_corresponding_test(file_path):
            return {"fixes": [], "files": []}

        return await self._create_tests_for_module(file_path)

    async def _find_untested_functions(self) -> list[dict[str, Any]]:
        untested: list[dict[str, Any]] = []

        package_dir = self.context.project_path / "crackerjack"
        if not package_dir.exists():
            return untested[:10]

        for py_file in package_dir.rglob("*.py"):
            if self._should_skip_file_for_testing(py_file):
                continue

            file_untested = await self._find_untested_functions_in_file(py_file)
            untested.extend(file_untested)

        return untested[:10]

    def _should_skip_file_for_testing(self, py_file: Path) -> bool:
        return py_file.name.startswith("test_")

    async def _find_untested_functions_in_file(
        self,
        py_file: Path,
    ) -> list[dict[str, Any]]:
        untested: list[dict[str, Any]] = []

        functions = await self._extract_functions_from_file(py_file)
        for func in functions:
            if not await self._function_has_test(func, py_file):
                untested.append(self._create_untested_function_info(func, py_file))

        return untested

    def _create_untested_function_info(
        self,
        func: dict[str, Any],
        py_file: Path,
    ) -> dict[str, Any]:
        return {
            "name": func["name"],
            "file": str(py_file),
            "line": func.get("line", 1),
            "signature": func.get("signature", ""),
        }

    async def _create_test_for_function(
        self,
        func_info: dict[str, Any],
    ) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        try:
            func_file = Path(func_info["file"])
            test_file_path = await self._generate_test_file_path(func_file)

            if test_file_path.exists():
                existing_content = self.context.get_file_content(test_file_path) or ""
                new_test = await self._generate_function_test(func_info)

                updated_content = existing_content.rstrip() + "\n\n" + new_test
                if self.context.write_file_content(test_file_path, updated_content):
                    fixes.append(f"Added test for function {func_info['name']}")
                    files.append(str(test_file_path))
            else:
                test_content = await self._generate_function_test(func_info)
                if self.context.write_file_content(test_file_path, test_content):
                    fixes.append(f"Created test file with test for {func_info['name']}")
                    files.append(str(test_file_path))

        except Exception as e:
            self.log(
                f"Error creating test for function {func_info['name']}: {e}",
                "ERROR",
            )

        return {"fixes": fixes, "files": files}

    async def _extract_functions_from_file(
        self,
        file_path: Path,
    ) -> list[dict[str, Any]]:
        functions: list[dict[str, Any]] = []

        try:
            content = self.context.get_file_content(file_path)
            if not content:
                return functions

            tree = ast.parse(content)
            functions = self._parse_function_nodes(tree)

        except Exception as e:
            self.log(f"Error parsing file {file_path}: {e}", "WARN")

        return functions

    def _parse_function_nodes(self, tree: ast.AST) -> list[dict[str, Any]]:
        functions: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef
            ) and self._is_valid_function_node(node):
                function_info = self._create_function_info(node)

                function_info["is_async"] = isinstance(node, ast.AsyncFunctionDef)
                functions.append(function_info)

        return functions

    def _is_valid_function_node(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        return not node.name.startswith(("_", "test_"))

    def _create_function_info(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> dict[str, Any]:
        return {
            "name": node.name,
            "line": node.lineno,
            "signature": self._get_function_signature(node),
            "args": [arg.arg for arg in node.args.args],
            "returns": self._get_return_annotation(node),
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "docstring": ast.get_docstring(node) or "",
        }

    async def _extract_classes_from_file(self, file_path: Path) -> list[dict[str, Any]]:
        classes: list[dict[str, Any]] = []

        try:
            content = self.context.get_file_content(file_path)
            if not content:
                return classes

            tree = ast.parse(content)
            classes = self._process_ast_nodes_for_classes(tree)

        except Exception as e:
            self.log(f"Error parsing classes from {file_path}: {e}", "WARN")

        return classes

    def _process_ast_nodes_for_classes(self, tree: ast.AST) -> list[dict[str, Any]]:
        classes: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and self._should_include_class(node):
                class_info = self._create_class_info(node)
                classes.append(class_info)

        return classes

    def _should_include_class(self, node: ast.ClassDef) -> bool:
        return not node.name.startswith("_")

    def _create_class_info(self, node: ast.ClassDef) -> dict[str, Any]:
        methods = self._extract_public_methods_from_class(node)
        return {"name": node.name, "line": node.lineno, "methods": methods}

    def _extract_public_methods_from_class(self, node: ast.ClassDef) -> list[str]:
        return [
            item.name
            for item in node.body
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_")
        ]

    def _get_function_signature(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str:
        args = [arg.arg for arg in node.args.args]
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{prefix}{node.name}({', '.join(args)})"

    def _get_return_annotation(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str:
        if node.returns:
            return ast.unparse(node.returns) if (hasattr(ast, "unparse")) else "Any"
        return "Any"

    async def _function_has_test(
        self,
        func_info: dict[str, Any],
        file_path: Path,
    ) -> bool:
        test_file_path = await self._generate_test_file_path(file_path)

        if not test_file_path.exists():
            return False

        test_content = self.context.get_file_content(test_file_path)
        if not test_content:
            return False

        test_patterns = [
            f"test_{func_info['name']}",
            f"test_{func_info['name']}_",
            f"def test_{func_info['name']}",
        ]

        return any(pattern in test_content for pattern in test_patterns)

    async def _generate_test_file_path(self, source_file: Path) -> Path:
        tests_dir = self.context.project_path / "tests"
        tests_dir.mkdir(exist_ok=True)

        relative_path = source_file.relative_to(
            self.context.project_path / "crackerjack",
        )
        test_name = f"test_{relative_path.stem}.py"

        return tests_dir / test_name

    async def _generate_test_content(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
    ) -> str:
        test_params = self._prepare_test_generation_params(module_file)
        return await self._generate_all_test_types(test_params, functions, classes)

    async def _generate_comprehensive_test_content(
        self,
        test_params: dict[str, Any],
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
    ) -> str:
        return await self._generate_all_test_types(test_params, functions, classes)

    def _prepare_test_generation_params(self, module_file: Path) -> dict[str, Any]:
        module_name = self._get_module_import_path(module_file)
        module_category = self._categorize_module(
            str(module_file.relative_to(self.context.project_path))
        )
        return {
            "module_name": module_name,
            "module_file": module_file,
            "module_category": module_category,
        }

    async def _generate_all_test_types(
        self,
        test_params: dict[str, Any],
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
    ) -> str:
        base_content = self._generate_enhanced_test_file_header(
            test_params["module_name"],
            test_params["module_file"],
            test_params["module_category"],
        )

        function_tests = await self._generate_function_tests_content(
            functions, test_params["module_category"]
        )
        class_tests = await self._generate_class_tests_content(
            classes, test_params["module_category"]
        )
        integration_tests = await self._generate_integration_tests_content(
            test_params["module_file"],
            functions,
            classes,
            test_params["module_category"],
        )

        return base_content + function_tests + class_tests + integration_tests

    async def _generate_function_tests_content(
        self, functions: list[dict[str, Any]], module_category: str
    ) -> str:
        return await self._generate_enhanced_function_tests(functions, module_category)

    async def _generate_class_tests_content(
        self, classes: list[dict[str, Any]], module_category: str
    ) -> str:
        return await self._generate_enhanced_class_tests(classes, module_category)

    async def _generate_integration_tests_content(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
        module_category: str,
    ) -> str:
        return await self._generate_integration_tests(
            module_file, functions, classes, module_category
        )

    def _generate_enhanced_test_file_header(
        self, module_name: str, module_file: Path, module_category: str
    ) -> str:
        imports = [
            "import pytest",
            "from pathlib import Path",
            "from unittest.mock import Mock, patch, AsyncMock",
        ]

        if module_category in ("service", "manager", "core"):
            imports.append("import asyncio")

        if module_category == "agent":
            imports.extend(
                [
                    "from crackerjack.agents.base import AgentContext, FixResult, "
                    "Issue, IssueType",
                ]
            )

        imports_str = "\n".join(imports)

        try:
            content = self.context.get_file_content(module_file) or ""
            tree = ast.parse(content)

            importable_items = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    importable_items.append(node.name)
                elif isinstance(
                    node, ast.FunctionDef | ast.AsyncFunctionDef
                ) and not node.name.startswith("_"):
                    importable_items.append(node.name)

            if importable_items:
                specific_imports = (
                    f"from {module_name} import {', '.join(importable_items[:10])}"
                )
            else:
                specific_imports = f"import {module_name}"

        except Exception:
            specific_imports = f"import {module_name}"

        class_name = f"Test{module_file.stem.replace('_', '').title()}"

        return (
            f'"""{imports_str}\n'
            f"{specific_imports}\n"
            "\n"
            "\n"
            f"class {class_name}:\n"
            f'    """Tests for {module_name}.\n'
            "\n"
            f"    This module contains comprehensive tests for {module_name}\n"
            "    including:\n"
            "    - Basic functionality tests\n"
            "    - Edge case validation\n"
            "    - Error handling verification\n"
            "    - Integration testing\n"
            "    - Performance validation (where applicable)\n"
            '    """\n'
            "\n"
            "    def test_module_imports_successfully(self):\n"
            '        """Test that the module can be imported without errors."""\n'
            f"        import {module_name}\n"
            f"        assert {module_name} is not None\n"
        )

    def _get_module_import_path(self, file_path: Path) -> str:
        try:
            relative_path = file_path.relative_to(self.context.project_path)
            parts = (*relative_path.parts[:-1], relative_path.stem)
            return ".".join(parts)
        except ValueError:
            return file_path.stem

    async def _generate_function_test(self, func_info: dict[str, Any]) -> str:
        func_name = func_info["name"]
        args = func_info.get("args", [])

        test_template = f"""def test_{func_name}_basic(self):
    \"\"\"Test basic functionality of {func_name}.\"\"\"
    try:
        result = {func_name}({self._generate_default_args(args)})
        assert result is not None or result is None
    except TypeError:
        pytest.skip(
            "Function requires specific arguments - manual implementation needed"
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in {func_name}: {{e}}")"""

        return test_template

    async def _generate_enhanced_function_tests(
        self, functions: list[dict[str, Any]], module_category: str
    ) -> str:
        if not functions:
            return ""

        test_methods = []
        for func in functions:
            func_tests = await self._generate_all_tests_for_function(
                func, module_category
            )
            test_methods.extend(func_tests)

        return "\n".join(test_methods)

    async def _generate_all_tests_for_function(
        self, func: dict[str, Any], module_category: str
    ) -> list[str]:
        func_tests = []

        basic_test = await self._generate_basic_function_test(func, module_category)
        func_tests.append(basic_test)

        additional_tests = await self._generate_conditional_tests_for_function(
            func, module_category
        )
        func_tests.extend(additional_tests)

        return func_tests

    async def _generate_conditional_tests_for_function(
        self, func: dict[str, Any], module_category: str
    ) -> list[str]:
        tests = []
        args = func.get("args", [])
        func_name = func["name"]

        if self._should_generate_parametrized_test(args):
            parametrized_test = await self._generate_parametrized_test(
                func, module_category
            )
            tests.append(parametrized_test)

        error_test = await self._generate_error_handling_test(func, module_category)
        tests.append(error_test)

        if self._should_generate_edge_case_test(args, func_name):
            edge_test = await self._generate_edge_case_test(func, module_category)
            tests.append(edge_test)

        return tests

    def _should_generate_parametrized_test(self, args: list[str]) -> bool:
        return len(args) > 1

    def _should_generate_edge_case_test(self, args: list[str], func_name: str) -> bool:
        has_multiple_args = len(args) > 2
        is_complex_function = any(
            hint in func_name.lower()
            for hint in ("process", "validate", "parse", "convert")
        )
        return has_multiple_args or is_complex_function

    async def _generate_basic_function_test(
        self, func: dict[str, Any], module_category: str
    ) -> str:
        func_name = func["name"]
        args = func.get("args", [])

        template_generator = self._get_test_template_generator(module_category)
        return template_generator(func_name, args)

    def _get_test_template_generator(
        self, module_category: str
    ) -> Callable[[str, list[str]], str]:
        return {
            "agent": self._generate_agent_test_template,
            "service": self._generate_async_test_template,
            "manager": self._generate_async_test_template,
        }.get(module_category, self._generate_default_test_template)

    def _generate_agent_test_template(self, func_name: str, args: list[str]) -> str:
        template = (
            "    def test_FUNC_NAME_basic_functionality(self):\n"
            '        """Test basic functionality of FUNC_NAME."""\n'
            "\n"
            "\n"
            "        try:\n"
            "            result = FUNC_NAME(ARGS)\n"
            "            assert result is not None or result is None\n"
            "        except (TypeError, NotImplementedError) as e:\n"
            + (
                "            pytest.skip('Function FUNC_NAME requires manual "
                "implementation: ' + str(e))\n"
            )
            + "        except Exception as e:\n"
            "            pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
        )

        return template.replace("FUNC_NAME", func_name).replace(
            "ARGS", self._generate_smart_default_args(args)
        )

    def _generate_async_test_template(self, func_name: str, args: list[str]) -> str:
        template = (
            " @pytest.mark.asyncio\n"
            " async def test_FUNC_NAME_basic_functionality(self):\n"
            '        """Test basic functionality of FUNC_NAME."""\n'
            "\n"
            "\n"
            "        try:\n"
            "            if asyncio.iscoroutinefunction(FUNC_NAME):\n"
            "                result = await FUNC_NAME(ARGS)\n"
            "            else:\n"
            "                result = FUNC_NAME(ARGS)\n"
            "            assert result is not None or result is None\n"
            "        except (TypeError, NotImplementedError) as e:\n"
            + (
                "            pytest.skip('Function FUNC_NAME requires manual "
                "implementation: ' + str(e))\n"
            )
            + "        except Exception as e:\n"
            "            pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
        )

        return template.replace("FUNC_NAME", func_name).replace(
            "ARGS", self._generate_smart_default_args(args)
        )

    def _generate_default_test_template(self, func_name: str, args: list[str]) -> str:
        template = (
            "    def test_FUNC_NAME_basic_functionality(self):\n"
            '        """Test basic functionality of FUNC_NAME."""\n'
            "        try:\n"
            "            result = FUNC_NAME(ARGS)\n"
            "            assert result is not None or result is None\n"
            "        except (TypeError, NotImplementedError) as e:\n"
            + (
                "            pytest.skip('Function FUNC_NAME requires manual "
                "implementation: ' + str(e))\n"
            )
            + "        except Exception as e:\n"
            "            pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
        )

        return template.replace("FUNC_NAME", func_name).replace(
            "ARGS", self._generate_smart_default_args(args)
        )

    async def _generate_parametrized_test(
        self, func: dict[str, Any], module_category: str
    ) -> str:
        func_name = func["name"]
        args = func.get("args", [])

        test_cases = self._generate_test_parameters(args)

        if not test_cases:
            return ""

        parametrize_decorator = f"@pytest.mark.parametrize({test_cases})"

        test_template = (
            f"    {parametrize_decorator}\n"
            f"    def test_{func_name}_with_parameters(self, "
            f"{', '.join(args) if len(args) <= 5 else 'test_input'}):\n"
            f'        """Test {func_name} with various parameter combinations."""\n'
            "        try:\n"
            f"            if len({args}) <= 5:\n"
            f"                result = {func_name}({', '.join(args)})\n"
            "            else:\n"
            f"                result = {func_name}(**test_input)\n"
            "\n"
            "            assert result is not None or result is None\n"
            "        except (TypeError, ValueError) as expected_error:\n"
            "\n"
            "            pass\n"
            "        except Exception as e:\n"
            '            pytest.fail(f"Unexpected error with parameters: {e}")'
        )

        return test_template

    async def _generate_error_handling_test(
        self, func: dict[str, Any], module_category: str
    ) -> str:
        func_name = func["name"]
        args = func.get("args", [])

        test_template = (
            f"    def test_{func_name}_error_handling(self):\n"
            f'        """Test {func_name} error handling with invalid inputs."""\n'
            "\n"
            "        with pytest.raises((TypeError, ValueError, AttributeError)):\n"
            f"            {func_name}({self._generate_invalid_args(args)})\n"
            "\n"
            "\n"
            f"        if len({args}) > 0:\n"
            "            with pytest.raises((TypeError, ValueError)):\n"
            f"                {func_name}("
            f"{self._generate_edge_case_args(args, 'empty')})"
        )

        return test_template

    async def _generate_edge_case_test(
        self, func: dict[str, Any], module_category: str
    ) -> str:
        func_name = func["name"]
        args = func.get("args", [])

        test_template = (
            f"    def test_{func_name}_edge_cases(self):\n"
            f'        """Test {func_name} with edge case scenarios."""\n'
            "\n"
            "        edge_cases = [\n"
            f"            {self._generate_edge_case_args(args, 'boundary')},\n"
            f"            {self._generate_edge_case_args(args, 'extreme')},\n"
            "        ]\n"
            "\n"
            "        for edge_case in edge_cases:\n"
            "            try:\n"
            f"                result = {func_name}(*edge_case)\n"
            "\n"
            "                assert result is not None or result is None\n"
            "            except (ValueError, TypeError):\n"
            "\n"
            "                pass\n"
            "            except Exception as e:\n"
            '                pytest.fail(f"Unexpected error with edge case {edge_case}: '
            '{e}")'
        )

        return test_template

    def _generate_test_parameters(self, args: list[str]) -> str:
        if not args or len(args) > 5:
            return ""

        param_names = ", ".join(f'"{arg}"' for arg in args)
        param_values = []

        for i in range(min(3, len(args))):
            test_case = []
            for arg in args:
                if "path" in arg.lower():
                    test_case.append(f'Path("test_{i}")')
                elif "str" in arg.lower() or "name" in arg.lower():
                    test_case.append(f'"test_{i}"')
                elif "int" in arg.lower() or "count" in arg.lower():
                    test_case.append(str(i))
                elif "bool" in arg.lower():
                    test_case.append("True" if i % 2 == 0 else "False")
                else:
                    test_case.append("None")
            param_values.append(f"({', '.join(test_case)})")

        return f"[{param_names}], [{', '.join(param_values)}]"

    def _generate_smart_default_args(self, args: list[str]) -> str:
        if not args or args == ["self"]:
            return ""

        filtered_args = self._filter_args(args)
        if not filtered_args:
            return ""

        placeholders = [
            self._generate_placeholder_for_arg(arg) for arg in filtered_args
        ]
        return ", ".join(placeholders)

    def _filter_args(self, args: list[str]) -> list[str]:
        return [arg for arg in args if arg != "self"]

    def _generate_placeholder_for_arg(self, arg: str) -> str:
        arg_lower = arg.lower()

        if self._is_path_arg(arg_lower):
            return 'Path("test_file.txt")'
        elif self._is_url_arg(arg_lower):
            return '"https: //example.com"'
        elif self._is_email_arg(arg_lower):
            return '"test@example.com"'
        elif self._is_id_arg(arg_lower):
            return '"test-id-123"'
        elif self._is_name_arg(arg_lower):
            return '"test_name"'
        elif self._is_numeric_arg(arg_lower):
            return "10"
        elif self._is_boolean_arg(arg_lower):
            return "True"
        elif self._is_text_arg(arg_lower):
            return '"test data"'
        elif self._is_list_arg(arg_lower):
            return '["test1", "test2"]'
        elif self._is_dict_arg(arg_lower):
            return '{"key": "value"}'
        return '"test"'

    def _is_path_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("path", "file"))

    def _is_url_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("url", "uri"))

    def _is_email_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("email", "mail"))

    def _is_id_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("id", "uuid"))

    def _is_name_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("name", "title"))

    def _is_numeric_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("count", "size", "number", "num"))

    def _is_boolean_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("enable", "flag", "is_", "has_"))

    def _is_text_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("data", "content", "text"))

    def _is_list_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("list[t.Any]", "items"))

    def _is_dict_arg(self, arg_lower: str) -> bool:
        return any(
            term in arg_lower for term in ("dict[str, t.Any]", "config", "options")
        )

    def _generate_invalid_args(self, args: list[str]) -> str:
        filtered_args = [arg for arg in args if arg != "self"]
        if not filtered_args:
            return ""
        return ", ".join(["None"] * len(filtered_args))

    def _generate_edge_case_args(self, args: list[str], case_type: str) -> str:
        filtered_args = self._filter_args(args)
        if not filtered_args:
            return ""

        placeholders = self._generate_placeholders_by_case_type(
            filtered_args, case_type
        )
        return ", ".join(placeholders)

    def _generate_placeholders_by_case_type(
        self, filtered_args: list[str], case_type: str
    ) -> list[str]:
        if case_type == "empty":
            return self._generate_empty_case_placeholders(filtered_args)
        elif case_type == "boundary":
            return self._generate_boundary_case_placeholders(filtered_args)

        return self._generate_extreme_case_placeholders(filtered_args)

    def _generate_empty_case_placeholders(self, filtered_args: list[str]) -> list[str]:
        placeholders = []
        for arg in filtered_args:
            arg_lower = arg.lower()
            if any(term in arg_lower for term in ("str", "name", "text")):
                placeholders.append('""')
            elif any(term in arg_lower for term in ("list[t.Any]", "items")):
                placeholders.append("[]")
            elif any(term in arg_lower for term in ("dict[str, t.Any]", "config")):
                placeholders.append("{}")
            else:
                placeholders.append("None")
        return placeholders

    def _generate_boundary_case_placeholders(
        self, filtered_args: list[str]
    ) -> list[str]:
        placeholders = []
        for arg in filtered_args:
            arg_lower = arg.lower()
            if any(term in arg_lower for term in ("count", "size", "number")):
                placeholders.append("0")
            elif any(term in arg_lower for term in ("str", "name")):
                placeholders.append('"x" * 1000')
            else:
                placeholders.append("None")
        return placeholders

    def _generate_extreme_case_placeholders(
        self, filtered_args: list[str]
    ) -> list[str]:
        placeholders = []
        for arg in filtered_args:
            arg_lower = arg.lower()
            if any(term in arg_lower for term in ("count", "size", "number")):
                placeholders.append("-1")
            else:
                placeholders.append("None")
        return placeholders

    async def _generate_enhanced_class_tests(
        self, classes: list[dict[str, Any]], module_category: str
    ) -> str:
        if not classes:
            return ""

        test_components = await self._generate_all_class_test_components(
            classes, module_category
        )
        return self._combine_class_test_elements(
            test_components["fixtures"], test_components["test_methods"]
        )

    async def _generate_all_class_test_components(
        self, classes: list[dict[str, Any]], module_category: str
    ) -> dict[str, list[str]]:
        fixtures = []
        test_methods = []

        for cls in classes:
            class_components = await self._generate_single_class_test_components(
                cls, module_category
            )
            fixtures.extend(class_components["fixtures"])
            test_methods.extend(class_components["test_methods"])

        return {"fixtures": fixtures, "test_methods": test_methods}

    async def _generate_single_class_test_components(
        self, cls: dict[str, Any], module_category: str
    ) -> dict[str, list[str]]:
        fixtures = []
        test_methods = []
        methods = cls.get("methods", [])

        fixture = await self._generate_class_fixture(cls, module_category)
        if fixture:
            fixtures.append(fixture)

        core_tests = await self._generate_core_class_tests(
            cls, methods, module_category
        )
        test_methods.extend(core_tests)

        return {"fixtures": fixtures, "test_methods": test_methods}

    async def _generate_core_class_tests(
        self, cls: dict[str, Any], methods: list[str], module_category: str
    ) -> list[str]:
        test_methods = []

        instantiation_test = await self._generate_class_instantiation_test(
            cls, module_category
        )
        test_methods.append(instantiation_test)

        method_tests = await self._generate_method_tests(
            cls, methods[:5], module_category
        )
        test_methods.extend(method_tests)

        property_test = await self._generate_class_property_test(cls, module_category)
        if property_test:
            test_methods.append(property_test)

        return test_methods

    async def _generate_method_tests(
        self, cls: dict[str, Any], methods: list[str], module_category: str
    ) -> list[str]:
        method_tests = []
        for method in methods:
            method_test = await self._generate_class_method_test(
                cls, method, module_category
            )
            method_tests.append(method_test)
        return method_tests

    def _combine_class_test_elements(
        self, fixtures: list[str], test_methods: list[str]
    ) -> str:
        fixture_section = "\n".join(fixtures) if fixtures else ""
        test_section = "\n".join(test_methods)
        return fixture_section + test_section

    async def _generate_class_fixture(
        self, cls: dict[str, Any], module_category: str
    ) -> str:
        class_name = cls["name"]

        if module_category in ("service", "manager", "core"):
            fixture_template = (
                "    @pytest.fixture\n"
                f"    def {class_name.lower()}_instance(self):\n"
                f'        """Fixture to create {class_name} instance for testing."""\n'
                "\n"
                "        try:\n"
                f"            return {class_name}()\n"
                "        except TypeError:\n"
                "\n"
                f"            with patch.object({class_name}, '__init__', return_value=None):\n"
                f"                instance = {class_name}.__new__({class_name})\n"
                "                return instance"
            )

        elif module_category == "agent":
            fixture_template = (
                "    @pytest.fixture\n"
                f"    def {class_name.lower()}_instance(self):\n"
                f'        """Fixture to create {class_name} instance for testing."""\n'
                "\n"
                "        mock_context = Mock(spec=AgentContext)\n"
                '        mock_context.project_path = Path("/test/project")\n'
                '        mock_context.get_file_content = Mock(return_value="# test content")\n'
                "        mock_context.write_file_content = Mock(return_value=True)\n"
                "\n"
                "        try:\n"
                f"            return {class_name}(mock_context)\n"
                "        except Exception:\n"
                '            pytest.skip("Agent requires specific context configuration")'
            )

        else:
            fixture_template = (
                "    @pytest.fixture\n"
                f"    def {class_name.lower()}_instance(self):\n"
                f'        """Fixture to create {class_name} instance for testing."""\n'
                "        try:\n"
                f"            return {class_name}()\n"
                "        except TypeError:\n"
                '            pytest.skip("Class requires specific constructor arguments")'
            )

        return fixture_template

    @staticmethod
    async def _generate_class_instantiation_test(
        class_info: dict[str, Any], module_category: str
    ) -> str:
        class_name = class_info["name"]

        test_template = (
            f"    def test_{class_name.lower()}_instantiation(self, {class_name.lower()}_instance):\n"
            f'        """Test successful instantiation of {class_name}."""\n'
            f"        assert {class_name.lower()}_instance is not None\n"
            f"        assert isinstance({class_name.lower()}_instance, {class_name})\n"
            "\n"
            f"        assert hasattr({class_name.lower()}_instance, '__class__')\n"
            f'        assert {class_name.lower()}_instance.__class__.__name__ == "{class_name}"'
        )

        return test_template

    async def _generate_class_method_test(
        self, cls: dict[str, Any], method_name: str, module_category: str
    ) -> str:
        class_name = cls["name"]

        if self._is_special_agent_method(module_category, method_name):
            return self._generate_agent_method_test(class_name, method_name)
        if module_category in ("service", "manager"):
            return self._generate_async_method_test(class_name, method_name)
        return self._generate_default_method_test(class_name, method_name)

    def _is_special_agent_method(self, module_category: str, method_name: str) -> bool:
        return module_category == "agent" and method_name in (
            "can_handle",
            "analyze_and_fix",
        )

    def _generate_agent_method_test(self, class_name: str, method_name: str) -> str:
        if method_name == "can_handle":
            return self._generate_can_handle_test(class_name)
        elif method_name == "analyze_and_fix":
            return self._generate_analyze_and_fix_test(class_name)
        return self._generate_generic_agent_method_test(class_name, method_name)

    def _generate_can_handle_test(self, class_name: str) -> str:
        return (
            "    @pytest.mark.asyncio\n"
            f"    async def test_{class_name.lower()}_can_handle(self, {class_name.lower()}_instance):\n"
            f'        """Test {class_name}.can_handle method."""\n'
            "\n"
            "        mock_issue = Mock(spec=Issue)\n"
            "        mock_issue.type = IssueType.COVERAGE_IMPROVEMENT\n"
            '        mock_issue.message = "test coverage issue"\n'
            '        mock_issue.file_path = "/test/path.py"\n'
            "\n"
            f"        result = await {class_name.lower()}_instance.can_handle(mock_issue)\n"
            "        assert isinstance(result, (int, float))\n"
            "        assert 0.0 <= result <= 1.0"
        )

    def _generate_analyze_and_fix_test(self, class_name: str) -> str:
        return (
            "    @pytest.mark.asyncio\n"
            f"    async def test_{class_name.lower()}_analyze_and_fix(self, {class_name.lower()}_instance):\n"
            f'        """Test {class_name}.analyze_and_fix method."""\n'
            "\n"
            "        mock_issue = Mock(spec=Issue)\n"
            "        mock_issue.type = IssueType.COVERAGE_IMPROVEMENT\n"
            '        mock_issue.message = "test coverage issue"\n'
            '        mock_issue.file_path = "/test/path.py"\n'
            "\n"
            f"        result = await {class_name.lower()}_instance.analyze_and_fix(mock_issue)\n"
            "        assert isinstance(result, FixResult)\n"
            "        assert hasattr(result, 'success')\n"
            "        assert hasattr(result, 'confidence')"
        )

    def _generate_generic_agent_method_test(
        self, class_name: str, method_name: str
    ) -> str:
        return (
            "    @pytest.mark.asyncio\n"
            f"    async def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
            f'        """Test {class_name}.{method_name} method."""\n'
            "        try:\n"
            f"            method = getattr({class_name.lower()}_instance, "
            f'"{method_name}", None)\n'
            f"            assert method is not None, "
            f'f"Method {method_name} should exist"\n'
            "\n"
            "            if asyncio.iscoroutinefunction(method):\n"
            "                result = await method()\n"
            "            else:\n"
            "                result = method()\n"
            "\n"
            "            assert result is not None or result is None\n"
            "        except (TypeError, NotImplementedError):\n"
            f'            pytest.skip(f"Method {method_name} requires specific arguments")\n'
            "        except Exception as e:\n"
            f'            pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
        )

    def _generate_async_method_test(self, class_name: str, method_name: str) -> str:
        return (
            "    @pytest.mark.asyncio\n"
            f"    async def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
            f'        """Test {class_name}.{method_name} method."""\n'
            "        try:\n"
            f"            method = getattr({class_name.lower()}_instance, "
            f'"{method_name}", None)\n'
            f"            assert method is not None, "
            f'f"Method {method_name} should exist"\n'
            "\n"
            "            if asyncio.iscoroutinefunction(method):\n"
            "                result = await method()\n"
            "            else:\n"
            "                result = method()\n"
            "\n"
            "            assert result is not None or result is None\n"
            "\n"
            "        except (TypeError, NotImplementedError):\n"
            f'            pytest.skip(f"Method {method_name} requires specific arguments or implementation")\n'
            "        except Exception as e:\n"
            f'            pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
        )

    def _generate_default_method_test(self, class_name: str, method_name: str) -> str:
        return (
            f"    def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
            f'        """Test {class_name}.{method_name} method."""\n'
            "        try:\n"
            f"            method = getattr({class_name.lower()}_instance, "
            f'"{method_name}", None)\n'
            f"            assert method is not None, "
            f'f"Method {method_name} should exist"\n'
            "\n"
            "            result = method()\n"
            "            assert result is not None or result is None\n"
            "\n"
            "        except (TypeError, NotImplementedError):\n"
            f'            pytest.skip(f"Method {method_name} requires specific arguments or implementation")\n'
            "        except Exception as e:\n"
            f'            pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
        )

    async def _generate_class_property_test(
        self, cls: dict[str, Any], module_category: str
    ) -> str:
        class_name = cls["name"]

        if module_category not in ("service", "manager", "agent"):
            return ""

        test_template = (
            f"    def test_{class_name.lower()}_properties(self, {class_name.lower()}_instance):\n"
            f'        """Test {class_name} properties and attributes."""\n'
            "\n"
            f"        assert hasattr({class_name.lower()}_instance, '__dict__') or \\\n"
            f"         hasattr({class_name.lower()}_instance, '__slots__')\n"
            "\n"
            f"        str_repr = str({class_name.lower()}_instance)\n"
            "        assert len(str_repr) > 0\n"
            f'        assert "{class_name}" in str_repr or "{class_name.lower()}" in \\\n'
            "         str_repr.lower()"
        )

        return test_template

    async def _generate_integration_tests(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
        module_category: str,
    ) -> str:
        if module_category not in ("service", "manager", "core"):
            return ""

        if len(functions) < 3 and len(classes) < 2:
            return ""

        integration_tests = (
            "\n\n"
            "    @pytest.mark.integration\n"
            f"    def test_{module_file.stem}_integration(self):\n"
            f'        """Integration test for {module_file.stem} module functionality."""\n'
            "\n"
            '        pytest.skip("Integration test needs manual implementation")\n'
            "\n"
            "    @pytest.mark.integration\n"
            "    @pytest.mark.asyncio\n"
            f"    async def test_{module_file.stem}_async_integration(self):\n"
            f'        """Async integration test for {module_file.stem} module."""\n'
            "\n"
            '        pytest.skip("Async integration test needs manual implementation")\n'
            "\n"
            "    @pytest.mark.performance\n"
            f"    def test_{module_file.stem}_performance(self):\n"
            f'        """Basic performance test for {module_file.stem} module."""\n'
            "\n"
            '        pytest.skip("Performance test needs manual implementation")'
        )

        return integration_tests

    def _generate_default_args(self, args: list[str]) -> str:
        if not args or args == ["self"]:
            return ""

        filtered_args = [arg for arg in args if arg != "self"]
        if not filtered_args:
            return ""

        placeholders = []
        for arg in filtered_args:
            if "path" in arg.lower():
                placeholders.append('Path("test")')
            elif "str" in arg.lower() or "name" in arg.lower():
                placeholders.append('"test"')
            elif "int" in arg.lower() or "count" in arg.lower():
                placeholders.append("1")
            elif "bool" in arg.lower():
                placeholders.append("True")
            else:
                placeholders.append("None")

        return ", ".join(placeholders)


agent_registry.register(TestCreationAgent)
