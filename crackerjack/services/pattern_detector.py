import ast
import logging
import typing as t
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from ..agents.base import Issue, IssueType, Priority
from .pattern_cache import CachedPattern, PatternCache

DetectorMethod = Callable[[Path, str, ast.AST], Awaitable[list["AntiPattern"]]]


class AntiPatternConfig(t.TypedDict):
    detector: DetectorMethod
    description: str
    prevention: str


@dataclass
class AntiPattern:
    pattern_type: str
    severity: Priority
    file_path: str
    line_number: int | None
    description: str
    suggestion: str
    prevention_strategy: str


class PatternDetector:
    def __init__(self, project_path: Path, pattern_cache: PatternCache) -> None:
        self.project_path = project_path
        self.pattern_cache = pattern_cache
        self.logger = logging.getLogger(__name__)

        self._anti_patterns: dict[str, AntiPatternConfig] = {
            "complexity_hotspot": {
                "detector": self._detect_complexity_hotspots,
                "description": "Functions approaching complexity limits",
                "prevention": "Extract methods, use helper functions",
            },
            "code_duplication": {
                "detector": self._detect_code_duplication,
                "description": "Repeated code patterns across files",
                "prevention": "Extract common functionality to utilities",
            },
            "performance_issues": {
                "detector": self._detect_performance_issues,
                "description": "Inefficient code patterns",
                "prevention": "Use optimized algorithms and data structures",
            },
            "security_risks": {
                "detector": self._detect_security_risks,
                "description": "Potentially unsafe code patterns",
                "prevention": "Apply secure coding practices",
            },
            "import_complexity": {
                "detector": self._detect_import_complexity,
                "description": "Complex or problematic import patterns",
                "prevention": "Organize imports, avoid circular dependencies",
            },
        }

    async def analyze_codebase(self) -> list[AntiPattern]:
        self.logger.info("Starting proactive anti-pattern analysis")

        anti_patterns = []
        python_files = list[t.Any](self.project_path.glob("**/*.py"))

        for file_path in python_files:
            if self._should_skip_file(file_path):
                continue

            file_anti_patterns = await self._analyze_file(file_path)
            anti_patterns.extend(file_anti_patterns)

        self.logger.info(f"Detected {len(anti_patterns)} potential anti-patterns")
        return anti_patterns

    async def _analyze_file(self, file_path: Path) -> list[AntiPattern]:
        anti_patterns = []

        try:
            content = file_path.read_text(encoding="utf-8")

            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError as e:
                self.logger.warning(f"Syntax error in {file_path}: {e}")
                return []

            for pattern_name, pattern_info in self._anti_patterns.items():
                detector_method = pattern_info["detector"]
                try:
                    detected = await detector_method(file_path, content, tree)
                    anti_patterns.extend(detected)
                except Exception as e:
                    self.logger.warning(
                        f"Error in {pattern_name} detector for {file_path}: {e}"
                    )

        except Exception as e:
            self.logger.warning(f"Failed to analyze {file_path}: {e}")

        return anti_patterns

    async def _detect_complexity_hotspots(
        self, file_path: Path, content: str, tree: ast.AST
    ) -> list[AntiPattern]:
        anti_patterns = []

        class ComplexityVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.functions: list[tuple[str, int, int]] = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                complexity = 1

                for child in ast.walk(node):
                    if isinstance(child, ast.If | ast.For | ast.While | ast.With):
                        complexity += 1
                    elif isinstance(child, ast.Try):
                        complexity += 1
                    elif isinstance(child, ast.ExceptHandler):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1

                self.functions.append((node.name, node.lineno, complexity))
                self.generic_visit(node)

        visitor = ComplexityVisitor()
        visitor.visit(tree)

        for func_name, line_no, complexity in visitor.functions:
            if complexity >= 10:
                anti_patterns.append(
                    AntiPattern(
                        pattern_type="complexity_hotspot",
                        severity=Priority.HIGH if complexity >= 12 else Priority.MEDIUM,
                        file_path=str(file_path),
                        line_number=line_no,
                        description=f"Function '{func_name}' has complexity {complexity} (approaching limit of 15)",
                        suggestion=f"Break down '{func_name}' into smaller helper methods",
                        prevention_strategy="extract_method",
                    )
                )

        return anti_patterns

    async def _detect_code_duplication(
        self, file_path: Path, content: str, tree: ast.AST
    ) -> list[AntiPattern]:
        anti_patterns = []

        lines = content.split("\n")
        line_groups: dict[str, list[int]] = {}

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if len(stripped) > 20 and not stripped.startswith("#"):
                if stripped in line_groups:
                    line_groups[stripped].append(i)
                else:
                    line_groups[stripped] = [i]

        for line_content, line_numbers in line_groups.items():
            if len(line_numbers) >= 3:
                anti_patterns.append(
                    AntiPattern(
                        pattern_type="code_duplication",
                        severity=Priority.MEDIUM,
                        file_path=str(file_path),
                        line_number=line_numbers[0],
                        description=f"Line appears {len(line_numbers)} times: '{line_content[:50]}...'",
                        suggestion="Extract common functionality to a utility function",
                        prevention_strategy="extract_utility",
                    )
                )

        return anti_patterns

    async def _detect_performance_issues(
        self, file_path: Path, content: str, tree: ast.AST
    ) -> list[AntiPattern]:
        anti_patterns = []

        class PerformanceVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.issues: list[tuple[int, str, str]] = []

            def visit_For(self, node: ast.For) -> None:
                for child in ast.walk(node.body[0] if node.body else node):
                    if isinstance(child, ast.For | ast.While) and child != node:
                        self.issues.append(
                            (
                                node.lineno,
                                "Nested loop detected-potential O(n²) complexity",
                                "Consider using dictionary lookups or set[t.Any] operations",
                            )
                        )
                        break

                for stmt in node.body:
                    if (
                        isinstance(stmt, ast.AugAssign)
                        and isinstance(stmt.op, ast.Add)
                        and isinstance(stmt.target, ast.Name)
                    ):
                        self.issues.append(
                            (
                                stmt.lineno,
                                "List concatenation in loop-inefficient",
                                "Use list[t.Any].append() and join at the end",
                            )
                        )

                self.generic_visit(node)

        visitor = PerformanceVisitor()
        visitor.visit(tree)

        for line_no, description, suggestion in visitor.issues:
            anti_patterns.append(
                AntiPattern(
                    pattern_type="performance_issues",
                    severity=Priority.MEDIUM,
                    file_path=str(file_path),
                    line_number=line_no,
                    description=description,
                    suggestion=suggestion,
                    prevention_strategy="optimize_algorithm",
                )
            )

        return anti_patterns

    async def _detect_security_risks(
        self, file_path: Path, content: str, tree: ast.AST
    ) -> list[AntiPattern]:
        anti_patterns = []

        hardcoded_path_patterns = self._check_hardcoded_paths(file_path, content)
        anti_patterns.extend(hardcoded_path_patterns)

        subprocess_patterns = self._check_subprocess_security(file_path, tree)
        anti_patterns.extend(subprocess_patterns)

        return anti_patterns

    def _check_hardcoded_paths(
        self, file_path: Path, content: str
    ) -> list[AntiPattern]:
        anti_patterns = []

        if "/tmp/" in content or "C: \\" in content:  # nosec B108
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "/tmp/" in line or "C: \\" in line:  # nosec B108
                    anti_patterns.append(
                        AntiPattern(
                            pattern_type="security_risks",
                            severity=Priority.HIGH,
                            file_path=str(file_path),
                            line_number=i,
                            description="Hardcoded path detected-potential security risk",
                            suggestion="Use tempfile module for temporary files",
                            prevention_strategy="use_secure_temp_files",
                        )
                    )
                    break

        return anti_patterns

    def _check_subprocess_security(
        self, file_path: Path, tree: ast.AST
    ) -> list[AntiPattern]:
        anti_patterns = []

        class SecurityVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.issues: list[tuple[int, str, str]] = []

            def visit_Call(self, node: ast.Call) -> None:
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                ):
                    for keyword in node.keywords:
                        if (
                            keyword.arg == "shell"
                            and isinstance(keyword.value, ast.Constant)
                            and keyword.value.value is True
                        ):
                            self.issues.append(
                                (
                                    node.lineno,
                                    "subprocess with shell=True-security risk",
                                    "Avoid shell=True or validate inputs carefully",
                                )
                            )

                self.generic_visit(node)

        visitor = SecurityVisitor()
        visitor.visit(tree)

        for line_no, description, suggestion in visitor.issues:
            anti_patterns.append(
                AntiPattern(
                    pattern_type="security_risks",
                    severity=Priority.HIGH,
                    file_path=str(file_path),
                    line_number=line_no,
                    description=description,
                    suggestion=suggestion,
                    prevention_strategy="secure_subprocess",
                )
            )

        return anti_patterns

    async def _detect_import_complexity(
        self, file_path: Path, content: str, tree: ast.AST
    ) -> list[AntiPattern]:
        anti_patterns = []

        class ImportVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.imports: list[tuple[int, str]] = []
                self.import_count = 0

            def visit_Import(self, node: ast.Import) -> None:
                self.import_count += len(node.names)
                for alias in node.names:
                    if alias.name.count(".") > 2:
                        self.imports.append((node.lineno, f"Deep import: {alias.name}"))
                self.generic_visit(node)

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if node.module:
                    self.import_count += len(node.names) if node.names else 1
                    if node.names and len(node.names) > 10:
                        self.imports.append(
                            (node.lineno, f"Many imports from {node.module}")
                        )
                self.generic_visit(node)

        visitor = ImportVisitor()
        visitor.visit(tree)

        if visitor.import_count > 50:
            anti_patterns.append(
                AntiPattern(
                    pattern_type="import_complexity",
                    severity=Priority.MEDIUM,
                    file_path=str(file_path),
                    line_number=1,
                    description=f"File has {visitor.import_count} imports-may indicate tight coupling",
                    suggestion="Consider breaking file into smaller modules",
                    prevention_strategy="modular_design",
                )
            )

        for line_no, description in visitor.imports:
            anti_patterns.append(
                AntiPattern(
                    pattern_type="import_complexity",
                    severity=Priority.LOW,
                    file_path=str(file_path),
                    line_number=line_no,
                    description=description,
                    suggestion="Simplify import structure",
                    prevention_strategy="clean_imports",
                )
            )

        return anti_patterns

    def _should_skip_file(self, file_path: Path) -> bool:
        skip_patterns = [
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            ".tox",
            "build",
            "dist",
            ".pytest_cache",
            "node_modules",
        ]

        path_str = str(file_path)
        return any(pattern in path_str for pattern in skip_patterns)

    async def suggest_proactive_refactoring(
        self, anti_patterns: list[AntiPattern]
    ) -> list[Issue]:
        issues = []

        for anti_pattern in anti_patterns:
            issue_type_map = {
                "complexity_hotspot": IssueType.COMPLEXITY,
                "code_duplication": IssueType.DRY_VIOLATION,
                "performance_issues": IssueType.PERFORMANCE,
                "security_risks": IssueType.SECURITY,
                "import_complexity": IssueType.IMPORT_ERROR,
            }

            issue_type = issue_type_map.get(
                anti_pattern.pattern_type, IssueType.FORMATTING
            )

            issue = Issue(
                id=f"proactive_{anti_pattern.pattern_type}_{hash(anti_pattern.file_path + str(anti_pattern.line_number))}",
                type=issue_type,
                severity=anti_pattern.severity,
                message=f"Proactive: {anti_pattern.description}",
                file_path=anti_pattern.file_path,
                line_number=anti_pattern.line_number,
                details=[
                    anti_pattern.suggestion,
                    f"Prevention strategy: {anti_pattern.prevention_strategy}",
                ],
                stage="proactive_analysis",
            )

            issues.append(issue)

        return issues

    async def get_cached_solutions(
        self, anti_patterns: list[AntiPattern]
    ) -> dict[str, CachedPattern]:
        solutions = {}

        for anti_pattern in anti_patterns:
            solution_key = self._generate_solution_key(anti_pattern)
            cached_pattern = self._find_cached_pattern_for_anti_pattern(anti_pattern)

            if cached_pattern:
                solutions[solution_key] = cached_pattern

        return solutions

    def _generate_solution_key(self, anti_pattern: AntiPattern) -> str:
        return f"{anti_pattern.pattern_type}_{anti_pattern.file_path}_{anti_pattern.line_number}"

    def _find_cached_pattern_for_anti_pattern(
        self, anti_pattern: AntiPattern
    ) -> CachedPattern | None:
        issue_type = self._map_anti_pattern_to_issue_type(anti_pattern.pattern_type)
        if not issue_type:
            return None

        temp_issue = self._create_temp_issue_for_lookup(anti_pattern, issue_type)
        return self.pattern_cache.get_best_pattern_for_issue(temp_issue)

    def _map_anti_pattern_to_issue_type(self, pattern_type: str) -> IssueType | None:
        return {
            "complexity_hotspot": IssueType.COMPLEXITY,
            "code_duplication": IssueType.DRY_VIOLATION,
            "performance_issues": IssueType.PERFORMANCE,
            "security_risks": IssueType.SECURITY,
        }.get(pattern_type)

    def _create_temp_issue_for_lookup(
        self, anti_pattern: AntiPattern, issue_type: IssueType
    ) -> Issue:
        return Issue(
            id="temp",
            type=issue_type,
            severity=anti_pattern.severity,
            message=anti_pattern.description,
            file_path=anti_pattern.file_path,
        )
