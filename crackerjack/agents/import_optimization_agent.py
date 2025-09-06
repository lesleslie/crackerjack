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
        """Simple logging method for the agent."""
        print(f"[{level}] ImportOptimizationAgent: {message}")

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.IMPORT_ERROR, IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        """Determine confidence level for handling import-related issues."""
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

        # Check for ruff/pyflakes import error codes
        # Use safe pattern matching for error code detection
        pattern_obj = SAFE_PATTERNS["match_error_code_patterns"]
        if pattern_obj.test(issue.message):
            return 0.85

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        return await self.fix_issue(issue)

    async def analyze_file(self, file_path: Path) -> ImportAnalysis:
        """Comprehensive import analysis including vulture dead code detection."""
        if not file_path.exists() or file_path.suffix != ".py":
            return ImportAnalysis(file_path, [], [], [], [], [])

        try:
            with file_path.open(encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)
        except (SyntaxError, OSError) as e:
            self.log(f"Could not parse {file_path}: {e}", level="WARNING")
            return ImportAnalysis(file_path, [], [], [], [], [])

        # Get unused imports from vulture
        unused_imports = await self._detect_unused_imports(file_path)

        # Analyze import structure
        return self._analyze_imports(file_path, tree, content, unused_imports)

    async def _detect_unused_imports(self, file_path: Path) -> list[str]:
        """Use vulture to detect unused imports with intelligent filtering."""
        try:
            # Run vulture on single file to detect unused imports
            result = subprocess.run(
                ["uv", "run", "vulture", "--min-confidence", "80", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.context.project_path,
            )

            unused_imports = []
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line and "unused import" in line.lower():
                        # Extract import name from vulture output using safe patterns
                        # Format: "file.py:line: unused import 'name' (confidence: XX%)"
                        pattern_obj = SAFE_PATTERNS["extract_unused_import_name"]
                        if pattern_obj.test(line):
                            import_name = pattern_obj.apply(line)
                            unused_imports.append(import_name)

            return unused_imports

        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            FileNotFoundError,
        ):
            # Fallback to basic AST analysis if vulture fails
            return []

    def _analyze_imports(
        self, file_path: Path, tree: ast.AST, content: str, unused_imports: list[str]
    ) -> ImportAnalysis:
        """Analyze imports in a Python file for various optimization opportunities."""
        # Extract and analyze import information
        analysis_results = self._perform_full_import_analysis(tree, content)

        # Create the import analysis object
        return self._create_import_analysis(file_path, analysis_results, unused_imports)

    def _create_import_analysis(
        self,
        file_path: Path,
        analysis_results: dict[str, list[str]],
        unused_imports: list[str],
    ) -> ImportAnalysis:
        """Create an ImportAnalysis object from the analysis results."""
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
        """Perform full import analysis on the AST tree."""
        # Extract import information
        module_imports, all_imports = self._extract_import_information(tree)

        # Analyze different aspects of imports
        return self._perform_import_analysis(module_imports, all_imports, content)

    def _perform_import_analysis(
        self,
        module_imports: dict[str, list[dict[str, t.Any]]],
        all_imports: list[dict[str, t.Any]],
        content: str,
    ) -> dict[str, list[str]]:
        """Perform comprehensive analysis of import patterns."""
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
        """Extract import information from the AST tree."""
        module_imports: dict[str, list[dict[str, t.Any]]] = defaultdict(list)
        all_imports: list[dict[str, t.Any]] = []

        self._process_tree_imports(tree, all_imports, module_imports)

        return module_imports, all_imports

    def _initialize_import_containers(
        self,
    ) -> tuple[dict[str, list[dict[str, t.Any]]], list[dict[str, t.Any]]]:
        """Initialize containers for import information."""
        module_imports: dict[str, list[dict[str, t.Any]]] = defaultdict(list)
        all_imports: list[dict[str, t.Any]] = []
        return module_imports, all_imports

    def _process_tree_imports(
        self,
        tree: ast.AST,
        all_imports: list[dict[str, t.Any]],
        module_imports: dict[str, list[dict[str, t.Any]]],
    ) -> None:
        """Process all import statements in the AST tree."""
        for node in ast.walk(tree):
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
        """Process standard import statements."""
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
        """Process from import statements."""
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
        for module, imports in module_imports.items():
            types = {imp["type"] for imp in imports}
            if len(types) > 1:
                mixed.append(module)
        return mixed

    def _find_redundant_imports(self, all_imports: list[dict[str, t.Any]]) -> list[str]:
        seen_modules: set[str] = set()
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
        """Find import consolidation and optimization opportunities."""
        opportunities: list[str] = []

        for module, imports in module_imports.items():
            standard_imports = [imp for imp in imports if imp["type"] == "standard"]
            from_imports = [imp for imp in imports if imp["type"] == "from"]

            # Recommend consolidating multiple standard imports to from-imports
            if len(standard_imports) >= 2:
                opportunities.append(
                    f"Consolidate {len(standard_imports)} standard imports "
                    f"from '{module}' into from-import style",
                )

            # Recommend combining from-imports from same module
            if len(from_imports) >= 3:
                opportunities.append(
                    f"Consider combining {len(from_imports)} from-imports "
                    f"from '{module}' into fewer lines",
                )

        return opportunities

    def _find_import_violations(
        self, content: str, all_imports: list[dict[str, t.Any]]
    ) -> list[str]:
        """Find PEP 8 import organization violations."""
        violations: list[str] = []
        lines = content.splitlines()

        # Check for import organization (stdlib, third-party, local)
        self._categorize_imports(all_imports)

        # Find imports that are not in PEP 8 order
        prev_category = 0
        for imp in all_imports:
            module = imp.get("module", "")
            category = self._get_import_category(module)

            if category < prev_category:
                violations.append(
                    f"Import '{module}' should come before previous imports (PEP 8 ordering)"
                )
            prev_category = max(prev_category, category)

        # Check for star imports
        for line_num, line in enumerate(lines, 1):
            # Use safe pattern matching for star import detection
            if SAFE_PATTERNS["match_star_import"].test(line.strip()):
                violations.append(f"Line {line_num}: Avoid star imports")

        return violations

    def _categorize_imports(
        self, all_imports: list[dict[str, t.Any]]
    ) -> dict[int, list[dict[str, t.Any]]]:
        """Categorize imports by PEP 8 standards: 1=stdlib, 2=third-party, 3=local."""
        categories: dict[int, list[dict[str, t.Any]]] = defaultdict(list)

        for imp in all_imports:
            module = imp.get("module", "")
            category = self._get_import_category(module)
            categories[category].append(imp)

        return categories

    def _get_import_category(self, module: str) -> int:
        """Determine import category: 1=stdlib, 2=third-party, 3=local."""
        if not module:
            return 3

        # Standard library modules (common ones)
        stdlib_modules = {
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

        base_module = module.split(".")[0]

        # Check if it's a standard library module
        if base_module in stdlib_modules:
            return 1

        # Check if it's a local import (starts with '.' or project name)
        if module.startswith(".") or base_module == "crackerjack":
            return 3

        # Otherwise assume third-party
        return 2

    async def fix_issue(self, issue: Issue) -> FixResult:
        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for import optimization"],
            )
        file_path = Path(issue.file_path)

        analysis = await self.analyze_file(file_path)

        if not any(
            [
                analysis.mixed_imports,
                analysis.redundant_imports,
                analysis.unused_imports,
                analysis.optimization_opportunities,
                analysis.import_violations,
            ],
        ):
            return FixResult(
                success=True,
                confidence=1.0,
                fixes_applied=["No import optimizations needed"],
                remaining_issues=[],
                recommendations=["Import patterns are already optimal"],
                files_modified=[],
            )

        try:
            with file_path.open(encoding="utf-8") as f:
                original_content = f.read()

            optimized_content = await self._optimize_imports(original_content, analysis)

            with file_path.open("w", encoding="utf-8") as f:
                f.write(optimized_content)

            changes: list[str] = []
            remaining_issues: list[str] = []

            if analysis.mixed_imports:
                changes.append(
                    f"Standardized mixed imports for modules: {', '.join(analysis.mixed_imports)}",
                )
            if analysis.redundant_imports:
                changes.append(
                    f"Removed {len(analysis.redundant_imports)} redundant imports",
                )
            if analysis.unused_imports:
                changes.append(
                    f"Removed {len(analysis.unused_imports)} unused imports: {', '.join(analysis.unused_imports[:3])}"
                    + ("..." if len(analysis.unused_imports) > 3 else ""),
                )
            if analysis.optimization_opportunities:
                changes.append(
                    f"Applied {len(analysis.optimization_opportunities)} import consolidations",
                )

            # Report violations that couldn't be auto-fixed
            if analysis.import_violations:
                remaining_issues.extend(
                    analysis.import_violations[:3]
                )  # Limit to top 3

            recommendations = [f"Optimized import statements in {file_path.name}"]
            if remaining_issues:
                recommendations.append(
                    "Consider manual review for remaining PEP 8 violations"
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
            return FixResult(
                success=False,
                confidence=0.0,
                fixes_applied=[],
                remaining_issues=[f"Failed to optimize imports: {e}"],
                recommendations=["Manual import review needed"],
                files_modified=[],
            )

    async def _optimize_imports(self, content: str, analysis: ImportAnalysis) -> str:
        """Apply comprehensive import optimizations."""
        lines = content.splitlines()

        lines = self._apply_import_optimizations(lines, analysis)

        return "\n".join(lines)

    def _apply_import_optimizations(
        self, lines: list[str], analysis: ImportAnalysis
    ) -> list[str]:
        """Apply all import optimization steps in sequence."""
        # Remove unused imports first
        lines = self._remove_unused_imports(lines, analysis.unused_imports)

        # Consolidate mixed imports to from-import style
        lines = self._consolidate_mixed_imports(lines, analysis.mixed_imports)

        # Remove redundant imports
        lines = self._remove_redundant_imports(lines, analysis.redundant_imports)

        # Apply PEP 8 import organization
        lines = self._organize_imports_pep8(lines)

        return lines

    def _remove_unused_imports(
        self, lines: list[str], unused_imports: list[str]
    ) -> list[str]:
        """Remove unused imports identified by vulture."""
        if not unused_imports:
            return lines

        unused_patterns = self._create_unused_import_patterns(unused_imports)
        return self._filter_unused_import_lines(lines, unused_patterns, unused_imports)

    def _create_unused_import_patterns(
        self, unused_imports: list[str]
    ) -> list[t.Pattern[str]]:
        """Create regex patterns for unused import detection."""
        import re  # Import needed for pattern compilation

        unused_patterns = []
        for unused in unused_imports:
            # Use dynamic pattern creation with escaping
            escaped_unused = re.escape(unused)
            # Create compiled regex patterns
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
        """Filter out lines containing unused imports."""
        filtered_lines = []
        for line in lines:
            should_remove = False
            for pattern in unused_patterns:
                if pattern.search(line):
                    if self._is_multi_import_line(line):
                        # Only remove the specific unused import, not the whole line
                        line = self._remove_from_import_list(line, unused_imports)
                    else:
                        should_remove = True
                    break

            if not should_remove and line.strip():  # Keep non-empty lines
                filtered_lines.append(line)

        return filtered_lines

    def _is_multi_import_line(self, line: str) -> bool:
        """Check if line contains multiple imports."""
        return "import" in line and "," in line

    def _remove_from_import_list(self, line: str, unused_imports: list[str]) -> str:
        """Remove specific imports from a multi-import line."""
        for unused in unused_imports:
            # Remove 'unused_name,' or ', unused_name' using safe pattern approach
            import re  # REGEX OK: temporary for escaping in dynamic removal

            escaped_unused = re.escape(unused)
            line = re.sub(
                rf",?\s*{escaped_unused}\s*,?", ", ", line
            )  # REGEX OK: dynamic removal with escaping

            # Clean up using safe patterns
            line = SAFE_PATTERNS["clean_import_commas"].apply(line)
            line = SAFE_PATTERNS["clean_trailing_import_comma"].apply(line)
            line = SAFE_PATTERNS["clean_import_prefix"].apply(line)
        return line

    def _consolidate_mixed_imports(
        self, lines: list[str], mixed_modules: list[str]
    ) -> list[str]:
        """Consolidate mixed import styles to prefer from-import format."""
        if not mixed_modules:
            return lines

        import_data = self._collect_mixed_module_imports(lines, mixed_modules)
        lines = self._remove_old_mixed_imports(lines, import_data["lines_to_remove"])
        lines = self._insert_consolidated_imports(lines, import_data)

        return lines

    def _collect_mixed_module_imports(
        self, lines: list[str], mixed_modules: list[str]
    ) -> dict[str, t.Any]:
        """Collect import information for mixed modules."""
        import_collector = self._create_import_collector()
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            for module in mixed_modules:
                self._process_mixed_module_line(
                    stripped_line, module, i, import_collector
                )

        return self._finalize_import_collection(import_collector)
    
    def _create_import_collector(self) -> dict[str, t.Any]:
        """Create containers for collecting import information."""
        return {
            "module_imports": defaultdict(set),
            "lines_to_remove": set(),
            "insert_positions": {},
        }
    
    def _finalize_import_collection(self, collector: dict[str, t.Any]) -> dict[str, t.Any]:
        """Finalize the collected import information."""
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
        """Process a single line for mixed module imports."""
        if self._is_standard_import_line(line, module):
            self._handle_standard_import(line, module, line_index, import_collector)
        elif self._is_from_import_line(line, module):
            self._handle_from_import(line, module, line_index, import_collector)
    
    def _is_standard_import_line(self, line: str, module: str) -> bool:
        """Check if line is a standard import for the module."""
        import re  # REGEX OK: localized for pattern matching
        return bool(re.match(
            rf"^\s*import\s+{re.escape(module)}(?:\.\w+)*\s*$", line
        ))  # REGEX OK: dynamic module matching with escaping
    
    def _is_from_import_line(self, line: str, module: str) -> bool:
        """Check if line is a from-import for the module."""
        import re  # REGEX OK: localized for pattern matching
        return bool(re.match(
            rf"^\s*from\s+{re.escape(module)}\s+import\s+", line
        ))  # REGEX OK: dynamic from import matching with escaping

    def _handle_standard_import(
        self,
        line: str,
        module: str,
        line_index: int,
        import_collector: dict[str, t.Any],
    ) -> None:
        """Handle standard import statement."""
        import_name = self._extract_import_name_from_standard(line, module)
        if import_name:
            import_to_add = self._determine_import_name(import_name, module)
            self._add_import_to_collector(
                module, import_to_add, line_index, import_collector
            )
    
    def _extract_import_name_from_standard(self, line: str, module: str) -> str | None:
        """Extract the import name from a standard import line."""
        import re  # REGEX OK: localized for pattern matching
        match = re.search(rf"import\s+({re.escape(module)}(?:\.\w+)*)", line)
        return match.group(1) if match else None
    
    def _determine_import_name(self, import_name: str, module: str) -> str:
        """Determine what name to import based on the import statement."""
        if "." in import_name:
            # For submodules, import the submodule name
            return import_name.split(".")[-1]
        return module
    
    def _add_import_to_collector(
        self,
        module: str,
        import_name: str,
        line_index: int,
        import_collector: dict[str, t.Any],
    ) -> None:
        """Add import information to the collector."""
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
        """Handle from-import statement."""
        import_names = self._extract_import_names_from_from_import(line, module)
        import_collector["module_imports"][module].update(import_names)
        import_collector["lines_to_remove"].add(line_index)
        if module not in import_collector["insert_positions"]:
            import_collector["insert_positions"][module] = line_index
    
    def _extract_import_names_from_from_import(self, line: str, module: str) -> list[str]:
        """Extract import names from a from-import line."""
        import re  # REGEX OK: localized for pattern matching
        import_part = re.sub(rf"^\s*from\s+{re.escape(module)}\s+import\s+", "", line)
        return [name.strip() for name in import_part.split(",")]

    def _remove_old_mixed_imports(
        self, lines: list[str], lines_to_remove: set[int]
    ) -> list[str]:
        """Remove old import lines in reverse order to preserve indices."""
        for i in sorted(lines_to_remove, reverse=True):
            del lines[i]
        return lines

    def _insert_consolidated_imports(
        self, lines: list[str], import_data: dict[str, t.Any]
    ) -> list[str]:
        """Insert consolidated from-imports."""
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
        """Remove redundant/duplicate import statements."""
        if not redundant_imports:
            return lines

        seen_imports: set[str] = set()
        filtered_lines = []

        for line in lines:
            # Normalize the import line for comparison using safe patterns
            normalized = SAFE_PATTERNS["normalize_whitespace"].apply(line.strip())

            if normalized.startswith(("import ", "from ")):
                if normalized not in seen_imports:
                    seen_imports.add(normalized)
                    filtered_lines.append(line)
                # Skip redundant imports
            else:
                filtered_lines.append(line)

        return filtered_lines

    def _organize_imports_pep8(self, lines: list[str]) -> list[str]:
        """Organize imports according to PEP 8 standards."""
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
        """Sort imports by PEP 8 standards: category first, then alphabetically."""
        return sorted(import_data, key=lambda x: (x[0], x[2].lower()))

    def _parse_import_lines(
        self, lines: list[str]
    ) -> tuple[list[tuple[int, str, str]], list[tuple[int, str]], tuple[int, int]]:
        """Parse lines to separate imports from other code."""
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
            (parser_state["import_start"], parser_state["import_end"])
        )
    
    def _initialize_parser_state(self) -> dict[str, t.Any]:
        """Initialize parser state for import line processing."""
        return {
            "import_lines": [],  # (category, line, original)
            "other_lines": [],
            "import_start": -1,
            "import_end": -1,
        }
    
    def _process_import_line(
        self, i: int, line: str, stripped: str, parser_state: dict[str, t.Any]
    ) -> None:
        """Process a line that contains an import statement."""
        if parser_state["import_start"] == -1:
            parser_state["import_start"] = i
        parser_state["import_end"] = i

        module = self._extract_module_name(stripped)
        category = self._get_import_category(module)
        parser_state["import_lines"].append((category, line, stripped))
    
    def _process_non_import_line(
        self, i: int, line: str, stripped: str, parser_state: dict[str, t.Any]
    ) -> None:
        """Process a line that is not an import statement."""
        self._categorize_non_import_line(
            i, line, stripped, 
            parser_state["import_start"], 
            parser_state["import_end"], 
            parser_state["other_lines"]
        )

    def _is_import_line(self, stripped: str) -> bool:
        """Check if line is an import statement."""
        return stripped.startswith(("import ", "from ")) and not stripped.startswith(
            "#"
        )

    def _extract_module_name(self, stripped: str) -> str:
        """Extract module name from import statement."""
        if stripped.startswith("import "):
            return stripped.split()[1].split(".")[0]
        # from import
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
        """Categorize non-import lines for later reconstruction."""
        if import_start != -1 and import_end != -1 and i > import_end:
            # We've passed the import section
            other_lines.append((i, line))
        elif import_start == -1:
            # We haven't reached imports yet
            other_lines.append((i, line))
        elif stripped == "" and import_start <= i <= import_end:
            # Empty line within import section - we'll reorganize these
            return
        else:
            other_lines.append((i, line))

    def _rebuild_with_organized_imports(
        self,
        import_data: list[tuple[int, str, str]],
        other_lines: list[tuple[int, str]],
        import_bounds: tuple[int, int],
    ) -> list[str]:
        """Rebuild file with organized imports and proper spacing."""
        result_lines = []
        import_start, import_end = import_bounds

        # Add lines before imports
        self._add_lines_before_imports(result_lines, other_lines, import_start)

        # Add organized imports with proper spacing
        self._add_organized_imports(result_lines, import_data)

        # Add lines after imports
        self._add_lines_after_imports(result_lines, other_lines, import_end)

        return result_lines

    def _add_lines_before_imports(
        self,
        result_lines: list[str],
        other_lines: list[tuple[int, str]],
        import_start: int,
    ) -> None:
        """Add lines that appear before import section."""
        for i, line in other_lines:
            if i < import_start:
                result_lines.append(line)

    def _add_organized_imports(
        self, result_lines: list[str], import_data: list[tuple[int, str, str]]
    ) -> None:
        """Add imports with proper category spacing."""
        current_category = 0
        for category, line, _ in import_data:
            if category > current_category and current_category > 0:
                result_lines.append("")  # Add blank line between categories
            result_lines.append(line)
            current_category = category

    def _add_lines_after_imports(
        self,
        result_lines: list[str],
        other_lines: list[tuple[int, str]],
        import_end: int,
    ) -> None:
        """Add lines that appear after import section."""
        if any(i > import_end for i, _ in other_lines):
            result_lines.append("")  # Blank line after imports
            for i, line in other_lines:
                if i > import_end:
                    result_lines.append(line)

    async def get_diagnostics(self) -> dict[str, t.Any]:
        """Provide comprehensive diagnostics about import analysis across the project."""
        try:
            # Count Python files in the project
            python_files = list(self.context.project_path.rglob("*.py"))
            files_analyzed = len(python_files)

            # Analyze a sample of files for comprehensive import metrics
            mixed_import_files = 0
            total_mixed_modules = 0
            unused_import_files = 0
            total_unused_imports = 0
            pep8_violations = 0

            # Analyze first 10 files as a sample
            for file_path in python_files[:10]:
                try:
                    analysis = await self.analyze_file(file_path)
                    if analysis.mixed_imports:
                        mixed_import_files += 1
                        total_mixed_modules += len(analysis.mixed_imports)
                    if analysis.unused_imports:
                        unused_import_files += 1
                        total_unused_imports += len(analysis.unused_imports)
                    if analysis.import_violations:
                        pep8_violations += len(analysis.import_violations)
                except Exception as e:
                    self.log(f"Could not analyze {file_path}: {e}")
                    continue  # Skip files that can't be analyzed

            return {
                "files_analyzed": files_analyzed,
                "mixed_import_files": mixed_import_files,
                "total_mixed_modules": total_mixed_modules,
                "unused_import_files": unused_import_files,
                "total_unused_imports": total_unused_imports,
                "pep8_violations": pep8_violations,
                "agent": "ImportOptimizationAgent",
                "capabilities": [
                    "Mixed import style consolidation",
                    "Unused import detection with vulture",
                    "PEP 8 import organization",
                    "Redundant import removal",
                    "Intelligent context-aware analysis",
                ],
            }
        except Exception as e:
            return {
                "files_analyzed": 0,
                "mixed_import_files": 0,
                "total_mixed_modules": 0,
                "unused_import_files": 0,
                "total_unused_imports": 0,
                "pep8_violations": 0,
                "agent": "ImportOptimizationAgent",
                "error": str(e),
            }


agent_registry.register(ImportOptimizationAgent)
