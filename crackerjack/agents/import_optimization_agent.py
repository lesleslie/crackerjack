import ast
import subprocess
import typing as t
from collections import defaultdict
from pathlib import Path

from ..services.regex_patterns import SAFE_PATTERNS
from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class ImportAnalysis(t.NamedTuple):
    file_path: Path
    mixed_imports: list[str]
    redundant_imports: list[str]
    unused_imports: list[str]
    optimization_opportunities: list[str]
    import_violations: list[str]


class ImportOptimizationAgent(SubAgent):
    name = "import_optimization"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)

    def log(self, message: str, level: str = "INFO") -> None:
        print(f"[{level}] ImportOptimizationAgent: {message}")

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.IMPORT_ERROR, IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type in self.get_supported_types():
            return 0.85

        description_lower = issue.message.lower()
        import_keywords = [
            "import",
            "unused import",
            "redundant import",
            "import style",
            "mixed import",
            "import organization",
            "from import",
            "star import",
            "unused variable",
            "defined but never used",
        ]
        if any(keyword in description_lower for keyword in import_keywords):
            return 0.8

        pattern_obj = SAFE_PATTERNS["match_error_code_patterns"]
        if pattern_obj.test(issue.message):
            return 0.85

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        return await self.fix_issue(issue)

    async def analyze_file(self, file_path: Path) -> ImportAnalysis:
        if not self._is_valid_python_file(file_path):
            return self._create_empty_import_analysis(file_path)

        return await self._parse_and_analyze_file(file_path)

    def _is_valid_python_file(self, file_path: Path) -> bool:
        return file_path.exists() and file_path.suffix == ".py"

    def _create_empty_import_analysis(self, file_path: Path) -> ImportAnalysis:
        return ImportAnalysis(file_path, [], [], [], [], [])

    async def _parse_and_analyze_file(self, file_path: Path) -> ImportAnalysis:
        try:
            with file_path.open(encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)
        except (SyntaxError, OSError) as e:
            return self._handle_parse_error(file_path, e)

        unused_imports = await self._detect_unused_imports(file_path)

        return self._analyze_imports(file_path, tree, content, unused_imports)

    def _handle_parse_error(self, file_path: Path, e: Exception) -> ImportAnalysis:
        self.log(f"Could not parse {file_path}: {e}", level="WARNING")
        return ImportAnalysis(file_path, [], [], [], [], [])

    async def _detect_unused_imports(self, file_path: Path) -> list[str]:
        try:
            result = self._run_vulture_analysis(file_path)
            return self._extract_unused_imports_from_result(result)
        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            FileNotFoundError,
        ):
            return []

    def _run_vulture_analysis(
        self, file_path: Path
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["uv", "run", "vulture", "--min-confidence", "80", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=self.context.project_path,
        )

    def _extract_unused_imports_from_result(
        self, result: subprocess.CompletedProcess[str]
    ) -> list[str]:
        unused_imports: list[str] = []
        if not self._is_valid_vulture_result(result):
            return unused_imports

        for line in result.stdout.strip().split("\n"):
            import_name = self._extract_import_name_from_line(line)
            if import_name:
                unused_imports.append(import_name)

        return unused_imports

    def _is_valid_vulture_result(
        self, result: subprocess.CompletedProcess[str]
    ) -> bool:
        return result.returncode == 0 and bool(result.stdout)

    def _extract_import_name_from_line(self, line: str) -> str | None:
        if not line or "unused import" not in line.lower():
            return None

        pattern_obj = SAFE_PATTERNS["extract_unused_import_name"]
        if pattern_obj.test(line):
            return pattern_obj.apply(line)
        return None

    def _analyze_imports(
        self, file_path: Path, tree: ast.AST, content: str, unused_imports: list[str]
    ) -> ImportAnalysis:
        analysis_results = self._perform_full_import_analysis(tree, content)

        return self._create_import_analysis(file_path, analysis_results, unused_imports)

    def _create_import_analysis(
        self,
        file_path: Path,
        analysis_results: dict[str, list[str]],
        unused_imports: list[str],
    ) -> ImportAnalysis:
        return ImportAnalysis(
            file_path=file_path,
            mixed_imports=analysis_results["mixed_imports"],
            redundant_imports=analysis_results["redundant_imports"],
            unused_imports=unused_imports,
            optimization_opportunities=analysis_results["optimization_opportunities"],
            import_violations=analysis_results["import_violations"],
        )

    def _perform_full_import_analysis(
        self, tree: ast.AST, content: str
    ) -> dict[str, list[str]]:
        module_imports, all_imports = self._extract_import_information(tree)

        return self._perform_import_analysis(module_imports, all_imports, content)

    def _perform_import_analysis(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
        all_imports: list[dict[str, t.Any]],
        content: str,
    ) -> dict[str, list[str]]:
        analysis_results = self._analyze_import_patterns(
            module_imports, all_imports, content
        )

        return analysis_results

    def _analyze_import_patterns(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
        all_imports: list[dict[str, t.Any]],
        content: str,
    ) -> dict[str, list[str]]:
        return self._analyze_import_aspects(module_imports, all_imports, content)

    def _analyze_import_aspects(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
        all_imports: list[dict[str, t.Any]],
        content: str,
    ) -> dict[str, list[str]]:
        return self._analyze_each_import_aspect(module_imports, all_imports, content)

    def _analyze_each_import_aspect(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
        all_imports: list[dict[str, t.Any]],
        content: str,
    ) -> dict[str, list[str]]:
        mixed_imports = self._find_mixed_imports(module_imports)
        redundant_imports = self._find_redundant_imports(all_imports)
        optimization_opportunities = self._find_optimization_opportunities(
            module_imports
        )
        import_violations = self._find_import_violations(content, all_imports)

        return {
            "mixed_imports": mixed_imports,
            "redundant_imports": redundant_imports,
            "optimization_opportunities": optimization_opportunities,
            "import_violations": import_violations,
        }

    def _extract_import_information(
        self, tree: ast.AST
    ) -> tuple[dict[str, list[dict[str, t.Any]]], list[dict[str, t.Any]]]:
        module_imports: dict[str, list[dict[str, t.Any]]] = defaultdict(list)
        all_imports: list[dict[str, t.Any]] = []

        self._process_tree_imports(tree, all_imports, module_imports)

        return module_imports, all_imports

    def _initialize_import_containers(
        self,
    ) -> tuple[dict[str, list[dict[str, t.Any]]], list[dict[str, t.Any]]]:
        module_imports: dict[str, list[dict[str, t.Any]]] = defaultdict(list)
        all_imports: list[dict[str, t.Any]] = []
        return module_imports, all_imports

    def _process_tree_imports(
        self,
        tree: ast.AST,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        self._process_all_nodes(tree, all_imports, module_imports)

    def _process_all_nodes(
        self,
        tree: ast.AST,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        self._process_import_statements_in_tree(tree, all_imports, module_imports)

    def _process_import_statements_in_tree(
        self,
        tree: ast.AST,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        for node in ast.walk(tree):
            self._process_node_if_import(node, all_imports, module_imports)

    def _process_node_if_import(
        self,
        node: ast.AST,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        if isinstance(node, ast.Import):
            self._process_standard_import(node, all_imports, module_imports)
        elif isinstance(node, ast.ImportFrom) and node.module:
            self._process_from_import(node, all_imports, module_imports)

    def _process_standard_import(
        self,
        node: ast.Import,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        self._process_standard_import_aliases(node, all_imports, module_imports)

    def _process_standard_import_aliases(
        self,
        node: ast.Import,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        for alias in node.names:
            import_info = {
                "type": "standard",
                "module": alias.name,
                "name": alias.asname or alias.name,
                "line": node.lineno,
            }
            all_imports.append(import_info)
            base_module = alias.name.split(".")[0]
            module_imports[base_module].append(import_info)

    def _process_from_import(
        self,
        node: ast.ImportFrom,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        self._process_from_import_aliases(node, all_imports, module_imports)

    def _process_from_import_aliases(
        self,
        node: ast.ImportFrom,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        if node.module is None:
            return  # Skip relative imports without module name

        for alias in node.names:
            import_info = {
                "type": "from",
                "module": node.module,
                "name": alias.name,
                "asname": alias.asname,
                "line": node.lineno,
            }
            all_imports.append(import_info)
            base_module = node.module.split(".")[0]
            module_imports[base_module].append(import_info)

    def _find_mixed_imports(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> list[str]:
        mixed: list[str] = []

        mixed.extend(self._check_mixed_imports_per_module(module_imports))
        return mixed

    def _check_mixed_imports_per_module(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> list[str]:
        mixed: list[str] = []
        for module, imports in module_imports.items():
            types = {imp["type"] for imp in imports}
            if len(types) > 1:
                mixed.append(module)
        return mixed

    def _find_redundant_imports(self, all_imports: list[dict[str, t.Any]]) -> list[str]:
        seen_modules: set[str] = set()
        redundant: list[str] = []

        redundant.extend(self._check_redundant_imports(all_imports, seen_modules))

        return redundant

    def _check_redundant_imports(
        self, all_imports: list[dict[str, t.Any]], seen_modules: set[str]
    ) -> list[str]:
        redundant: list[str] = []

        for imp in all_imports:
            module_key = f"{imp['module']}: {imp['name']}"
            if module_key in seen_modules:
                redundant.append(f"Line {imp['line']}: {imp['module']}.{imp['name']}")
            seen_modules.add(module_key)

        return redundant

    def _find_optimization_opportunities(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> list[str]:
        return self._find_consolidation_opportunities(module_imports)

    def _find_consolidation_opportunities(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> list[str]:
        opportunities: list[str] = []

        for module, imports in module_imports.items():
            standard_imports = [imp for imp in imports if imp["type"] == "standard"]
            from_imports = [imp for imp in imports if imp["type"] == "from"]

            if len(standard_imports) >= 2:
                opportunities.append(
                    f"Consolidate {len(standard_imports)} standard imports "
                    f"from '{module}' into from-import style",
                )

            if len(from_imports) >= 3:
                opportunities.append(
                    f"Consider combining {len(from_imports)} from-imports "
                    f"from '{module}' into fewer lines",
                )

        return opportunities

    def _find_import_violations(
        self, content: str, all_imports: list[dict[str, t.Any]]
    ) -> list[str]:
        violations = self._check_import_ordering(all_imports)

        violations.extend(self._check_star_imports(content))

        return violations

    def _check_import_ordering(self, all_imports: list[dict[str, t.Any]]) -> list[str]:
        violations: list[str] = []

        self._categorize_imports(all_imports)

        violations.extend(self._find_pep8_order_violations(all_imports))

        return violations

    def _find_pep8_order_violations(
        self, all_imports: list[dict[str, t.Any]]
    ) -> list[str]:
        violations: list[str] = []
        prev_category = 0

        for imp in all_imports:
            module = imp.get("module", "")
            category = self._get_import_category(module)

            if category < prev_category:
                violations.append(
                    f"Import '{module}' should come before previous imports (PEP 8 ordering)"
                )
            prev_category = max(prev_category, category)

        return violations

    def _check_star_imports(self, content: str) -> list[str]:
        violations: list[str] = []
        lines = content.splitlines()

        for line_num, line in enumerate(lines, 1):
            if SAFE_PATTERNS["match_star_import"].test(line.strip()):
                violations.append(f"Line {line_num}: Avoid star imports")

        return violations

    def _categorize_imports(
        self, all_imports: list[dict[str, t.Any]]
    ) -> dict[int, list[dict[str, t.Any]]]:
        categories: dict[int, list[dict[str, t.Any]]] = defaultdict(list)

        for imp in all_imports:
            module = imp.get("module", "")
            category = self._get_import_category(module)
            categories[category].append(imp)

        return categories

    def _get_import_category(self, module: str) -> int:
        if not module:
            return 3

        return self._determine_module_category(module)

    def _determine_module_category(self, module: str) -> int:
        base_module = module.split(".")[0]

        if self._is_stdlib_module(base_module):
            return 1

        if self._is_local_import(module, base_module):
            return 3

        return 2

    def _is_stdlib_module(self, base_module: str) -> bool:
        stdlib_modules = self._get_stdlib_modules()
        return base_module in stdlib_modules

    def _get_stdlib_modules(self) -> set[str]:
        return {
            "os",
            "sys",
            "json",
            "ast",
            "re",
            "pathlib",
            "subprocess",
            "typing",
            "collections",
            "functools",
            "itertools",
            "tempfile",
            "contextlib",
            "dataclasses",
            "enum",
            "abc",
            "asyncio",
            "concurrent",
            "urllib",
            "http",
            "socket",
            "ssl",
            "time",
            "datetime",
            "calendar",
            "math",
            "random",
            "hashlib",
            "hmac",
            "base64",
            "uuid",
            "logging",
            "warnings",
        }

    def _is_local_import(self, module: str, base_module: str) -> bool:
        return module.startswith(".") or base_module == "crackerjack"

    async def fix_issue(self, issue: Issue) -> FixResult:
        validation_result = self._validate_issue(issue)
        if validation_result:
            return validation_result

        return await self._process_import_optimization_issue(issue)

    async def _process_import_optimization_issue(self, issue: Issue) -> FixResult:
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                fixes_applied=[],
                remaining_issues=["No file path provided in issue"],
            )
        file_path = Path(issue.file_path)

        analysis = await self.analyze_file(file_path)

        if not self._are_optimizations_needed(analysis):
            return self._create_no_optimization_needed_result()

        return await self._apply_optimizations_and_prepare_results(file_path, analysis)

    def _create_no_optimization_needed_result(self) -> FixResult:
        return FixResult(
            success=True,
            confidence=1.0,
            fixes_applied=["No import optimizations needed"],
            remaining_issues=[],
            recommendations=["Import patterns are already optimal"],
            files_modified=[],
        )

    def _validate_issue(self, issue: Issue) -> FixResult | None:
        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for import optimization"],
            )
        return None

    def _are_optimizations_needed(self, analysis: ImportAnalysis) -> bool:
        return any(
            [
                analysis.mixed_imports,
                analysis.redundant_imports,
                analysis.unused_imports,
                analysis.optimization_opportunities,
                analysis.import_violations,
            ],
        )

    async def _apply_optimizations_and_prepare_results(
        self, file_path: Path, analysis: ImportAnalysis
    ) -> FixResult:
        try:
            optimized_content = await self._read_and_optimize_file(file_path, analysis)
            await self._write_optimized_content(file_path, optimized_content)

            changes, remaining_issues = self._prepare_fix_results(analysis)
            recommendations = self._prepare_recommendations(
                file_path.name, remaining_issues
            )

            return FixResult(
                success=True,
                confidence=0.85,
                fixes_applied=changes,
                remaining_issues=remaining_issues,
                recommendations=recommendations,
                files_modified=[str(file_path)],
            )

        except Exception as e:
            return self._handle_optimization_error(e)

    async def _read_and_optimize_file(
        self, file_path: Path, analysis: ImportAnalysis
    ) -> str:
        with file_path.open(encoding="utf-8") as f:
            original_content = f.read()
        return await self._optimize_imports(original_content, analysis)

    async def _write_optimized_content(
        self, file_path: Path, optimized_content: str
    ) -> None:
        with file_path.open("w", encoding="utf-8") as f:
            f.write(optimized_content)

    def _handle_optimization_error(self, e: Exception) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            fixes_applied=[],
            remaining_issues=[f"Failed to optimize imports: {e}"],
            recommendations=["Manual import review needed"],
            files_modified=[],
        )

    def _prepare_fix_results(
        self, analysis: ImportAnalysis
    ) -> tuple[list[str], list[str]]:
        changes: list[str] = []
        remaining_issues: list[str] = []

        changes.extend(self._get_mixed_import_changes(analysis.mixed_imports))
        changes.extend(self._get_redundant_import_changes(analysis.redundant_imports))
        changes.extend(self._get_unused_import_changes(analysis.unused_imports))
        changes.extend(
            self._get_optimization_opportunity_changes(
                analysis.optimization_opportunities
            )
        )

        remaining_issues.extend(
            self._get_remaining_violations(analysis.import_violations)
        )

        return changes, remaining_issues

    def _get_mixed_import_changes(self, mixed_imports: list[str]) -> list[str]:
        changes: list[str] = []
        if mixed_imports:
            changes.append(
                f"Standardized mixed imports for modules: {', '.join(mixed_imports)}",
            )
        return changes

    def _get_redundant_import_changes(self, redundant_imports: list[str]) -> list[str]:
        changes: list[str] = []
        if redundant_imports:
            changes.append(
                f"Removed {len(redundant_imports)} redundant imports",
            )
        return changes

    def _get_unused_import_changes(self, unused_imports: list[str]) -> list[str]:
        changes: list[str] = []
        if unused_imports:
            changes.append(
                f"Removed {len(unused_imports)} unused imports: {', '.join(unused_imports[:3])}"
                + ("..." if len(unused_imports) > 3 else ""),
            )
        return changes

    def _get_optimization_opportunity_changes(
        self, optimization_opportunities: list[str]
    ) -> list[str]:
        changes: list[str] = []
        if optimization_opportunities:
            changes.append(
                f"Applied {len(optimization_opportunities)} import consolidations",
            )
        return changes

    def _get_remaining_violations(self, import_violations: list[str]) -> list[str]:
        remaining_issues: list[str] = []
        if import_violations:
            remaining_issues.extend(import_violations[:3])
        return remaining_issues

    def _prepare_recommendations(
        self, file_name: str, remaining_issues: list[str]
    ) -> list[str]:
        recommendations = [f"Optimized import statements in {file_name}"]
        if remaining_issues:
            recommendations.append(
                "Consider manual review for remaining PEP 8 violations"
            )
        return recommendations

    async def _optimize_imports(self, content: str, analysis: ImportAnalysis) -> str:
        lines = content.splitlines()

        lines = self._apply_import_optimizations(lines, analysis)

        return "\n".join(lines)

    def _apply_import_optimizations(
        self, lines: list[str], analysis: ImportAnalysis
    ) -> list[str]:
        lines = self._apply_all_optimization_steps(lines, analysis)
        return lines

    def _apply_all_optimization_steps(
        self, lines: list[str], analysis: ImportAnalysis
    ) -> list[str]:
        lines = self._remove_unused_imports(lines, analysis.unused_imports)

        lines = self._consolidate_mixed_imports(lines, analysis.mixed_imports)

        lines = self._remove_redundant_imports(lines, analysis.redundant_imports)

        lines = self._organize_imports_pep8(lines)

        return lines

    def _remove_unused_imports(
        self, lines: list[str], unused_imports: list[str]
    ) -> list[str]:
        if not unused_imports:
            return lines

        unused_patterns = self._create_unused_import_patterns(unused_imports)
        return self._filter_unused_import_lines(lines, unused_patterns, unused_imports)

    def _create_unused_import_patterns(
        self, unused_imports: list[str]
    ) -> list[t.Pattern[str]]:
        import re

        unused_patterns: list[t.Pattern[str]] = []
        for unused in unused_imports:
            escaped_unused = re.escape(unused)

            unused_patterns.extend(
                (
                    re.compile(f"^\\s*import\\s+{escaped_unused}\\s*$"),
                    re.compile(
                        f"^\\s*from\\s+\\w+\\s+import\\s+.*\\b{escaped_unused}\\b"
                    ),
                )
            )
        return unused_patterns

    def _filter_unused_import_lines(
        self,
        lines: list[str],
        unused_patterns: list[t.Pattern[str]],
        unused_imports: list[str],
    ) -> list[str]:
        filtered_lines = []
        for line in lines:
            should_remove = False
            for pattern in unused_patterns:
                if pattern.search(line):
                    if self._is_multi_import_line(line):
                        line = self._remove_from_import_list(line, unused_imports)
                    else:
                        should_remove = True
                    break

            if not should_remove and line.strip():
                filtered_lines.append(line)

        return filtered_lines

    def _is_multi_import_line(self, line: str) -> bool:
        return "import" in line and ", " in line

    def _remove_from_import_list(self, line: str, unused_imports: list[str]) -> str:
        for unused in unused_imports:
            import re

            escaped_unused = re.escape(unused)
            line = re.sub(rf", ?\s*{escaped_unused}\s*, ?", ", ", line)

            line = SAFE_PATTERNS["clean_import_commas"].apply(line)
            line = SAFE_PATTERNS["clean_trailing_import_comma"].apply(line)
            line = SAFE_PATTERNS["clean_import_prefix"].apply(line)
        return line

    def _consolidate_mixed_imports(
        self, lines: list[str], mixed_modules: list[str]
    ) -> list[str]:
        if not mixed_modules:
            return lines

        import_data = self._collect_mixed_module_imports(lines, mixed_modules)
        lines = self._remove_old_mixed_imports(lines, import_data["lines_to_remove"])
        lines = self._insert_consolidated_imports(lines, import_data)

        return lines

    def _collect_mixed_module_imports(
        self, lines: list[str], mixed_modules: list[str]
    ) -> dict[str, t.Any]:
        import_collector = self._create_import_collector()

        for i, line in enumerate(lines):
            stripped_line = line.strip()
            for module in mixed_modules:
                self._process_mixed_module_line(
                    stripped_line, module, i, import_collector
                )

        return self._finalize_import_collection(import_collector)

    def _create_import_collector(self) -> dict[str, t.Any]:
        return {
            "module_imports": defaultdict(set),
            "lines_to_remove": set(),
            "insert_positions": {},
        }

    def _finalize_import_collection(
        self, collector: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        return {
            "module_imports": collector["module_imports"],
            "lines_to_remove": collector["lines_to_remove"],
            "insert_positions": collector["insert_positions"],
        }

    def _process_mixed_module_line(
        self,
        line: str,
        module: str,
        line_index: int,
        import_collector: dict[str, t.Any],
    ) -> None:
        if self._is_standard_import_line(line, module):
            self._handle_standard_import(line, module, line_index, import_collector)
        elif self._is_from_import_line(line, module):
            self._handle_from_import(line, module, line_index, import_collector)

    def _is_standard_import_line(self, line: str, module: str) -> bool:
        import re

        return bool(re.match(rf"^\s*import\s+{re.escape(module)}(?: \.\w+)*\s*$", line))

    def _is_from_import_line(self, line: str, module: str) -> bool:
        import re

        return bool(re.match(rf"^\s*from\s+{re.escape(module)}\s+import\s+", line))

    def _handle_standard_import(
        self,
        line: str,
        module: str,
        line_index: int,
        import_collector: dict[str, t.Any],
    ) -> None:
        import_name = self._extract_import_name_from_standard(line, module)
        if import_name:
            import_to_add = self._determine_import_name(import_name, module)
            self._add_import_to_collector(
                module, import_to_add, line_index, import_collector
            )

    def _extract_import_name_from_standard(self, line: str, module: str) -> str | None:
        import re

        match = re.search(rf"import\s+({re.escape(module)}(?: \.\w+)*)", line)
        return match.group(1) if match else None

    def _determine_import_name(self, import_name: str, module: str) -> str:
        if "." in import_name:
            return import_name.split(".")[-1]
        return module

    def _add_import_to_collector(
        self,
        module: str,
        import_name: str,
        line_index: int,
        import_collector: dict[str, t.Any],
    ) -> None:
        import_collector["module_imports"][module].add(import_name)
        import_collector["lines_to_remove"].add(line_index)
        if module not in import_collector["insert_positions"]:
            import_collector["insert_positions"][module] = line_index

    def _handle_from_import(
        self,
        line: str,
        module: str,
        line_index: int,
        import_collector: dict[str, t.Any],
    ) -> None:
        import_names = self._extract_import_names_from_from_import(line, module)
        import_collector["module_imports"][module].update(import_names)
        import_collector["lines_to_remove"].add(line_index)
        if module not in import_collector["insert_positions"]:
            import_collector["insert_positions"][module] = line_index

    def _extract_import_names_from_from_import(
        self, line: str, module: str
    ) -> list[str]:
        import re

        import_part = re.sub(rf"^\s*from\s+{re.escape(module)}\s+import\s+", "", line)
        return [name.strip() for name in import_part.split(", ")]

    def _remove_old_mixed_imports(
        self, lines: list[str], lines_to_remove: set[int]
    ) -> list[str]:
        for i in sorted(lines_to_remove, reverse=True):
            del lines[i]
        return lines

    def _insert_consolidated_imports(
        self, lines: list[str], import_data: dict[str, t.Any]
    ) -> list[str]:
        module_imports = import_data["module_imports"]
        insert_positions = import_data["insert_positions"]
        lines_to_remove = import_data["lines_to_remove"]

        offset = 0
        for module, imports in module_imports.items():
            if module in insert_positions:
                imports_list = sorted(imports)
                consolidated = f"from {module} import {', '.join(imports_list)}"
                insert_pos = insert_positions[module] - offset
                lines.insert(insert_pos, consolidated)
                offset += (
                    len([i for i in lines_to_remove if i <= insert_positions[module]])
                    - 1
                )
        return lines

    def _remove_redundant_imports(
        self, lines: list[str], redundant_imports: list[str]
    ) -> list[str]:
        if not redundant_imports:
            return lines

        seen_imports: set[str] = set()
        filtered_lines = []

        for line in lines:
            normalized = SAFE_PATTERNS["normalize_whitespace"].apply(line.strip())

            if normalized.startswith(("import ", "from ")):
                if normalized not in seen_imports:
                    seen_imports.add(normalized)
                    filtered_lines.append(line)

            else:
                filtered_lines.append(line)

        return filtered_lines

    def _organize_imports_pep8(self, lines: list[str]) -> list[str]:
        parsed_data = self._parse_import_lines(lines)
        import_data, other_lines, import_bounds = parsed_data

        if not import_data:
            return lines

        sorted_imports = self._sort_imports_by_pep8_standards(import_data)
        return self._rebuild_with_organized_imports(
            sorted_imports, other_lines, import_bounds
        )

    def _sort_imports_by_pep8_standards(
        self, import_data: list[tuple[int, str, str]]
    ) -> list[tuple[int, str, str]]:
        return sorted(import_data, key=lambda x: (x[0], x[2].lower()))

    def _parse_import_lines(
        self, lines: list[str]
    ) -> tuple[list[tuple[int, str, str]], list[tuple[int, str]], tuple[int, int]]:
        parser_state = self._initialize_parser_state()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if self._is_import_line(stripped):
                self._process_import_line(i, line, stripped, parser_state)
            else:
                self._process_non_import_line(i, line, stripped, parser_state)

        return (
            parser_state["import_lines"],
            parser_state["other_lines"],
            (parser_state["import_start"], parser_state["import_end"]),
        )

    def _initialize_parser_state(self) -> dict[str, t.Any]:
        return {
            "import_lines": [],
            "other_lines": [],
            "import_start": -1,
            "import_end": -1,
        }

    def _process_import_line(
        self, i: int, line: str, stripped: str, parser_state: dict[str, t.Any]
    ) -> None:
        if parser_state["import_start"] == -1:
            parser_state["import_start"] = i
        parser_state["import_end"] = i

        module = self._extract_module_name(stripped)
        category = self._get_import_category(module)
        parser_state["import_lines"].append((category, line, stripped))

    def _process_non_import_line(
        self, i: int, line: str, stripped: str, parser_state: dict[str, t.Any]
    ) -> None:
        self._categorize_non_import_line(
            i,
            line,
            stripped,
            parser_state["import_start"],
            parser_state["import_end"],
            parser_state["other_lines"],
        )

    def _is_import_line(self, stripped: str) -> bool:
        return stripped.startswith(("import ", "from ")) and not stripped.startswith(
            "#"
        )

    def _extract_module_name(self, stripped: str) -> str:
        if stripped.startswith("import "):
            return stripped.split()[1].split(".")[0]

        return stripped.split()[1]

    def _categorize_non_import_line(
        self,
        i: int,
        line: str,
        stripped: str,
        import_start: int,
        import_end: int,
        other_lines: list[tuple[int, str]],
    ) -> None:
        if import_start != -1 and import_end != -1 and i > import_end:
            other_lines.append((i, line))
        elif import_start == -1:
            other_lines.append((i, line))
        elif stripped == "" and import_start <= i <= import_end:
            return
        else:
            other_lines.append((i, line))

    def _rebuild_with_organized_imports(
        self,
        import_data: list[tuple[int, str, str]],
        other_lines: list[tuple[int, str]],
        import_bounds: tuple[int, int],
    ) -> list[str]:
        result_lines: list[str] = []
        import_start, import_end = import_bounds

        self._add_lines_before_imports(result_lines, other_lines, import_start)

        self._add_organized_imports(result_lines, import_data)

        self._add_lines_after_imports(result_lines, other_lines, import_end)

        return result_lines

    def _add_lines_before_imports(
        self,
        result_lines: list[str],
        other_lines: list[tuple[int, str]],
        import_start: int,
    ) -> None:
        for i, line in other_lines:
            if i < import_start:
                result_lines.append(line)

    def _add_organized_imports(
        self, result_lines: list[str], import_data: list[tuple[int, str, str]]
    ) -> None:
        current_category = 0
        for category, line, _ in import_data:
            if category > current_category and current_category > 0:
                result_lines.append("")
            result_lines.append(line)
            current_category = category

    def _add_lines_after_imports(
        self,
        result_lines: list[str],
        other_lines: list[tuple[int, str]],
        import_end: int,
    ) -> None:
        if any(i > import_end for i, _ in other_lines):
            result_lines.append("")
            for i, line in other_lines:
                if i > import_end:
                    result_lines.append(line)

    async def get_diagnostics(self) -> dict[str, t.Any]:
        try:
            python_files = self._get_python_files()
            metrics = await self._analyze_file_sample(python_files[:10])
            return self._build_success_diagnostics(len(python_files), metrics)
        except Exception as e:
            return self._build_error_diagnostics(str(e))

    def _get_python_files(self) -> list[Path]:
        return list[t.Any](self.context.project_path.rglob("*.py"))

    async def _analyze_file_sample(self, python_files: list[Path]) -> dict[str, int]:
        metrics = {
            "mixed_import_files": 0,
            "total_mixed_modules": 0,
            "unused_import_files": 0,
            "total_unused_imports": 0,
            "pep8_violations": 0,
        }

        for file_path in python_files:
            file_metrics = await self._analyze_single_file_metrics(file_path)
            if file_metrics:
                self._update_metrics(metrics, file_metrics)

        return metrics

    async def _analyze_single_file_metrics(
        self, file_path: Path
    ) -> dict[str, int] | None:
        try:
            analysis = await self.analyze_file(file_path)
            return self._extract_file_metrics(analysis)
        except Exception as e:
            self.log(f"Could not analyze {file_path}: {e}")
            return None

    def _extract_file_metrics(self, analysis: ImportAnalysis) -> dict[str, int]:
        metrics = {
            "mixed_import_files": 1 if analysis.mixed_imports else 0,
            "total_mixed_modules": len(analysis.mixed_imports),
            "unused_import_files": 1 if analysis.unused_imports else 0,
            "total_unused_imports": len(analysis.unused_imports),
            "pep8_violations": len(analysis.import_violations),
        }
        return metrics

    def _update_metrics(
        self, metrics: dict[str, int], file_metrics: dict[str, int]
    ) -> None:
        for key, value in file_metrics.items():
            metrics[key] += value

    def _build_success_diagnostics(
        self, files_analyzed: int, metrics: dict[str, int]
    ) -> dict[str, t.Any]:
        return {
            "files_analyzed": files_analyzed,
            **metrics,
            "agent": "ImportOptimizationAgent",
            "capabilities": [
                "Mixed import style consolidation",
                "Unused import detection with vulture",
                "PEP 8 import organization",
                "Redundant import removal",
                "Intelligent context-aware analysis",
            ],
        }

    def _build_error_diagnostics(self, error: str) -> dict[str, t.Any]:
        return {
            "files_analyzed": 0,
            "mixed_import_files": 0,
            "total_mixed_modules": 0,
            "unused_import_files": 0,
            "total_unused_imports": 0,
            "pep8_violations": 0,
            "agent": "ImportOptimizationAgent",
            "error": error,
        }


agent_registry.register(ImportOptimizationAgent)
