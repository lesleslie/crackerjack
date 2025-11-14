"""Coverage analysis helper for test creation.

This module provides coverage analysis and gap detection capabilities
for test creation. Uses AgentContext pattern (legacy, intentional).
"""

import json
import operator
from pathlib import Path
from typing import Any

from crackerjack.agents.base import AgentContext


class TestCoverageAnalyzer:
    """Coverage analyzer helper for test creation.

    Uses AgentContext pattern (legacy, intentional).
    May use TestASTAnalyzer for code structure analysis.
    """

    def __init__(self, context: AgentContext) -> None:
        self.context = context

    async def analyze_coverage(self) -> dict[str, Any]:
        """Analyze test coverage and identify gaps."""
        try:
            coverage_data = await self._get_existing_coverage_data()
            if coverage_data:
                return coverage_data

            returncode, _, stderr = await self._run_coverage_command()

            if returncode != 0:
                return self._handle_coverage_command_failure(stderr)

            return await self._process_coverage_results_enhanced()

        except Exception as e:
            self._log(f"Coverage analysis error: {e}", "WARN")
            return self._create_default_coverage_result()

    async def _get_existing_coverage_data(self) -> dict[str, Any] | None:
        """Try to get existing coverage data from files."""
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
            self._log(f"Error reading existing coverage: {e}", "WARN")

        return None

    def _parse_coverage_json(self, coverage_json: dict[str, Any]) -> dict[str, Any]:
        """Parse coverage JSON report."""
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
            self._log(f"Error parsing coverage JSON: {e}", "WARN")
            return self._create_default_coverage_result()

    async def _run_coverage_command(self) -> tuple[int, str, str]:
        """Run coverage command via context."""
        # This would call through the context's run_command method
        # For now, return a placeholder
        return 1, "", "Coverage command not available in helper"

    def _handle_coverage_command_failure(self, stderr: str) -> dict[str, Any]:
        """Handle coverage command failure."""
        self._log(f"Coverage analysis failed: {stderr}", "WARN")
        return self._create_default_coverage_result()

    async def _process_coverage_results_enhanced(self) -> dict[str, Any]:
        """Process coverage results with enhanced analysis."""
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
        """Estimate current test coverage."""
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
        """Calculate coverage improvement potential."""
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
        """Create default coverage result."""
        return {
            "below_threshold": True,
            "current_coverage": 0.0,
            "uncovered_modules": [],
        }

    async def _find_uncovered_modules_enhanced(self) -> list[dict[str, Any]]:
        """Find uncovered modules with priority scoring."""
        from .test_ast_analyzer import TestASTAnalyzer

        uncovered: list[dict[str, Any]] = []

        project_path = Path(str(self.context.project_path))
        package_dir = project_path / "crackerjack"
        if not package_dir.exists():
            return uncovered[:15]

        ast_analyzer = TestASTAnalyzer(self.context)

        for py_file in package_dir.rglob("*.py"):
            if ast_analyzer.should_skip_module_for_coverage(py_file):
                continue

            if not ast_analyzer.has_corresponding_test(str(py_file)):
                module_info = await self._analyze_module_priority(py_file, ast_analyzer)
                uncovered.append(module_info)

        uncovered.sort(key=operator.itemgetter("priority_score"), reverse=True)
        return uncovered[:15]

    async def _analyze_module_priority(
        self, py_file: Path, ast_analyzer: "TestASTAnalyzer"
    ) -> dict[str, Any]:
        """Analyze module priority for testing."""
        try:
            content = self.context.get_file_content(py_file) or ""
            import ast

            ast.parse(content)

            functions = await ast_analyzer.extract_functions_from_file(py_file)
            classes = await ast_analyzer.extract_classes_from_file(py_file)

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
            self._log(f"Error analyzing module priority for {py_file}: {e}", "WARN")
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
        """Categorize module by path."""
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
        """Find untested functions with priority scoring."""
        from .test_ast_analyzer import TestASTAnalyzer

        untested: list[dict[str, Any]] = []

        package_dir = self.context.project_path / "crackerjack"
        if not package_dir.exists():
            return untested[:20]

        ast_analyzer = TestASTAnalyzer(self.context)

        for py_file in package_dir.rglob("*.py"):
            if ast_analyzer.should_skip_file_for_testing(py_file):
                continue

            file_untested = await self._find_untested_functions_in_file_enhanced(
                py_file, ast_analyzer
            )
            untested.extend(file_untested)

        untested.sort(key=operator.itemgetter("testing_priority"), reverse=True)
        return untested[:20]

    async def _find_untested_functions_in_file_enhanced(
        self, py_file: Path, ast_analyzer: "TestASTAnalyzer"
    ) -> list[dict[str, Any]]:
        """Find untested functions in file with enhanced analysis."""
        untested: list[dict[str, Any]] = []

        try:
            functions = await ast_analyzer.extract_functions_from_file(py_file)
            for func in functions:
                if not await ast_analyzer.function_has_test(func, py_file):
                    func_info = await self._analyze_function_testability(func, py_file)
                    untested.append(func_info)

        except Exception as e:
            self._log(f"Error finding untested functions in {py_file}: {e}", "WARN")

        return untested

    async def _analyze_function_testability(
        self, func: dict[str, Any], py_file: Path
    ) -> dict[str, Any]:
        """Analyze function testability and priority."""
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
            self._log(f"Error analyzing function testability: {e}", "WARN")
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
        """Identify coverage gaps in existing tests."""
        from .test_ast_analyzer import TestASTAnalyzer

        gaps: list[dict[str, Any]] = []

        try:
            package_dir = self.context.project_path / "crackerjack"
            tests_dir = self.context.project_path / "tests"

            if not package_dir.exists() or not tests_dir.exists():
                return gaps

            ast_analyzer = TestASTAnalyzer(self.context)

            for py_file in package_dir.rglob("*.py"):
                if ast_analyzer.should_skip_module_for_coverage(py_file):
                    continue

                test_coverage_info = await self._analyze_existing_test_coverage(
                    py_file, ast_analyzer
                )
                if test_coverage_info["has_gaps"]:
                    gaps.append(test_coverage_info)

        except Exception as e:
            self._log(f"Error identifying coverage gaps: {e}", "WARN")

        return gaps[:10]

    async def _analyze_existing_test_coverage(
        self, py_file: Path, ast_analyzer: "TestASTAnalyzer"
    ) -> dict[str, Any]:
        """Analyze existing test coverage for file."""
        try:
            test_file_path = await ast_analyzer.generate_test_file_path(py_file)

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
            self._log(f"Error analyzing test coverage for {py_file}: {e}", "WARN")
            return {
                "source_file": str(py_file.relative_to(self.context.project_path)),
                "test_file": None,
                "has_gaps": True,
                "missing_test_types": ["basic"],
                "coverage_score": 0,
            }

    async def create_tests_for_module(self, module_path: str) -> dict[str, list[str]]:
        """Create tests for a module."""
        from .test_ast_analyzer import TestASTAnalyzer
        from .test_template_generator import TestTemplateGenerator

        fixes: list[str] = []
        files: list[str] = []

        try:
            test_results = await self._generate_module_tests(
                module_path,
                TestASTAnalyzer(self.context),
                TestTemplateGenerator(self.context),
            )
            fixes.extend(test_results["fixes"])
            files.extend(test_results["files"])

        except Exception as e:
            self._handle_test_creation_error(module_path, e)

        return {"fixes": fixes, "files": files}

    async def _generate_module_tests(
        self,
        module_path: str,
        ast_analyzer: "TestASTAnalyzer",
        template_gen: "TestTemplateGenerator",
    ) -> dict[str, list[str]]:
        """Generate tests for module."""
        module_file = Path(module_path)
        if not await self._is_module_valid(module_file):
            return {"fixes": [], "files": []}

        functions = await ast_analyzer.extract_functions_from_file(module_file)
        classes = await ast_analyzer.extract_classes_from_file(module_file)

        if not functions and not classes:
            return {"fixes": [], "files": []}

        return await self._create_test_artifacts(
            module_file, functions, classes, ast_analyzer, template_gen
        )

    async def _is_module_valid(self, module_file: Path) -> bool:
        """Check if module file is valid."""
        return module_file.exists()

    async def _create_test_artifacts(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
        ast_analyzer: "TestASTAnalyzer",
        template_gen: "TestTemplateGenerator",
    ) -> dict[str, list[str]]:
        """Create test artifacts for module."""
        test_file_path = await ast_analyzer.generate_test_file_path(module_file)
        test_content = await template_gen.generate_test_content(
            module_file,
            functions,
            classes,
        )

        if self.context.write_file_content(test_file_path, test_content):
            self._log(f"Created test file: {test_file_path}")
            return {
                "fixes": [f"Created test file for {module_file}"],
                "files": [str(test_file_path)],
            }

        return {"fixes": [], "files": []}

    def _handle_test_creation_error(self, module_path: str, e: Exception) -> None:
        """Handle test creation error."""
        self._log(f"Error creating tests for module {module_path}: {e}", "ERROR")

    async def create_tests_for_file(self, file_path: str) -> dict[str, list[str]]:
        """Create tests for file."""
        from .test_ast_analyzer import TestASTAnalyzer

        ast_analyzer = TestASTAnalyzer(self.context)
        if ast_analyzer.has_corresponding_test(file_path):
            return {"fixes": [], "files": []}

        return await self.create_tests_for_module(file_path)

    async def find_untested_functions(self) -> list[dict[str, Any]]:
        """Find untested functions (basic version)."""
        from .test_ast_analyzer import TestASTAnalyzer

        untested: list[dict[str, Any]] = []

        package_dir = self.context.project_path / "crackerjack"
        if not package_dir.exists():
            return untested[:10]

        ast_analyzer = TestASTAnalyzer(self.context)

        for py_file in package_dir.rglob("*.py"):
            if ast_analyzer.should_skip_file_for_testing(py_file):
                continue

            file_untested = await self._find_untested_functions_in_file(
                py_file, ast_analyzer
            )
            untested.extend(file_untested)

        return untested[:10]

    async def _find_untested_functions_in_file(
        self,
        py_file: Path,
        ast_analyzer: "TestASTAnalyzer",
    ) -> list[dict[str, Any]]:
        """Find untested functions in file (basic version)."""
        untested: list[dict[str, Any]] = []

        functions = await ast_analyzer.extract_functions_from_file(py_file)
        for func in functions:
            if not await ast_analyzer.function_has_test(func, py_file):
                untested.append(self._create_untested_function_info(func, py_file))

        return untested

    def _create_untested_function_info(
        self,
        func: dict[str, Any],
        py_file: Path,
    ) -> dict[str, Any]:
        """Create untested function info."""
        return {
            "name": func["name"],
            "file": str(py_file),
            "line": func.get("line", 1),
            "signature": func.get("signature", ""),
        }

    async def create_test_for_function(
        self,
        func_info: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Create test for function."""
        from .test_ast_analyzer import TestASTAnalyzer
        from .test_template_generator import TestTemplateGenerator

        fixes: list[str] = []
        files: list[str] = []

        try:
            func_file = Path(func_info["file"])
            ast_analyzer = TestASTAnalyzer(self.context)
            template_gen = TestTemplateGenerator(self.context)

            test_file_path = await ast_analyzer.generate_test_file_path(func_file)

            if test_file_path.exists():
                existing_content = self.context.get_file_content(test_file_path) or ""
                new_test = await template_gen.generate_function_test(func_info)

                updated_content = existing_content.rstrip() + "\n\n" + new_test
                if self.context.write_file_content(test_file_path, updated_content):
                    fixes.append(f"Added test for function {func_info['name']}")
                    files.append(str(test_file_path))
            else:
                test_content = await template_gen.generate_function_test(func_info)
                if self.context.write_file_content(test_file_path, test_content):
                    fixes.append(f"Created test file with test for {func_info['name']}")
                    files.append(str(test_file_path))

        except Exception as e:
            self._log(
                f"Error creating test for function {func_info['name']}: {e}",
                "ERROR",
            )

        return {"fixes": fixes, "files": files}

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message through context."""
        # This is a helper - logging would typically go through the agent
        pass
