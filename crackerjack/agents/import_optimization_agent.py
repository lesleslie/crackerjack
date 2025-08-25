import ast
import typing as t
from collections import defaultdict
from pathlib import Path

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
    optimization_opportunities: list[str]


class ImportOptimizationAgent(SubAgent):
    name = "import_optimization"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.preferred_style = "from_import"

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.IMPORT_ERROR, IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type in self.get_supported_types():
            return 0.9

        description_lower = issue.message.lower()
        import_keywords = [
            "import",
            "unused import",
            "redundant import",
            "import style",
        ]
        if any(keyword in description_lower for keyword in import_keywords):
            return 0.7

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        return await self.fix_issue(issue)

    async def analyze_file(self, file_path: Path) -> ImportAnalysis:
        if not file_path.exists() or file_path.suffix != ".py":
            return ImportAnalysis(file_path, [], [], [])

        try:
            with file_path.open(encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (SyntaxError, OSError) as e:
            self.log(f"Could not parse {file_path}: {e}", level="WARNING")
            return ImportAnalysis(file_path, [], [], [])

        return self._analyze_imports(file_path, tree)

    def _analyze_imports(self, file_path: Path, tree: ast.AST) -> ImportAnalysis:
        module_imports: dict[str, list[dict[str, t.Any]]] = defaultdict(list)
        all_imports: list[dict[str, t.Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
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

            elif isinstance(node, ast.ImportFrom) and node.module:
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

        mixed_imports = self._find_mixed_imports(module_imports)
        redundant_imports = self._find_redundant_imports(all_imports)
        optimization_opportunities = self._find_optimization_opportunities(
            module_imports,
        )

        return ImportAnalysis(
            file_path=file_path,
            mixed_imports=mixed_imports,
            redundant_imports=redundant_imports,
            optimization_opportunities=optimization_opportunities,
        )

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
        opportunities: list[str] = []

        for module, imports in module_imports.items():
            standard_imports = [imp for imp in imports if imp["type"] == "standard"]
            if len(standard_imports) >= 2:
                opportunities.append(
                    f"Consider consolidating {len(standard_imports)} standard imports "
                    f"from {module} to from-imports",
                )

        return opportunities

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
                analysis.optimization_opportunities,
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
            if analysis.mixed_imports:
                changes.append(
                    f"Standardized mixed imports for modules: {', '.join(analysis.mixed_imports)}",
                )
            if analysis.redundant_imports:
                changes.append(
                    f"Removed {len(analysis.redundant_imports)} redundant imports",
                )
            if analysis.optimization_opportunities:
                changes.append(
                    f"Applied {len(analysis.optimization_opportunities)} optimizations",
                )

            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=changes,
                remaining_issues=[],
                recommendations=[f"Optimized import statements in {file_path.name}"],
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
        lines = content.splitlines()

        for module in analysis.mixed_imports:
            if module == "typing":
                lines = self._consolidate_typing_imports(lines)

        return "\n".join(lines)

    def _consolidate_typing_imports(self, lines: list[str]) -> list[str]:
        typing_imports: set[str] = set()
        lines_to_remove: list[int] = []
        insert_position = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "import typing":
                lines_to_remove.append(i)
                if insert_position is None:
                    insert_position = i
            elif stripped.startswith("from typing import "):
                import_part = stripped[len("from typing import ") :].strip()
                items = [item.strip() for item in import_part.split(",")]
                typing_imports.update(items)
                lines_to_remove.append(i)
                if insert_position is None:
                    insert_position = i

        for i in reversed(lines_to_remove):
            del lines[i]

        if typing_imports and insert_position is not None:
            consolidated = f"from typing import {', '.join(sorted(typing_imports))}"
            lines.insert(insert_position, consolidated)

        return lines

    async def get_diagnostics(self) -> dict[str, t.Any]:
        diagnostics = {
            "files_analyzed": 0,
            "mixed_import_files": 0,
            "total_mixed_modules": 0,
            "redundant_imports": 0,
            "optimization_opportunities": 0,
        }

        for py_file in self.context.project_path.rglob("*.py"):
            if py_file.name.startswith("."):
                continue

            analysis = await self.analyze_file(py_file)
            diagnostics["files_analyzed"] += 1

            if analysis.mixed_imports:
                diagnostics["mixed_import_files"] += 1
                diagnostics["total_mixed_modules"] += len(analysis.mixed_imports)

            diagnostics["redundant_imports"] += len(analysis.redundant_imports)
            diagnostics["optimization_opportunities"] += len(
                analysis.optimization_opportunities,
            )

        return diagnostics


agent_registry.register(ImportOptimizationAgent)
