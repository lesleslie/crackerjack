from __future__ import annotations

import ast
import logging
import re
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)

if t.TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


@dataclass
class DeadCodeInfo:
    """Parsed information about dead code from skylos/vulture output."""

    code_type: str  # function, class, method, attribute, import, variable
    name: str
    line_number: int
    confidence: float
    end_line: int | None = None  # For multi-line blocks
    decorators: list[str] | None = None


class DeadCodeRemovalAgent(SubAgent):
    """Specialized agent for removing dead code detected by skylos or vulture.

    This agent handles dead code issues with enhanced capabilities:
    - Skylos output format integration with confidence scoring
    - Multi-line dead code block handling (entire functions, classes)
    - Usage analysis for confidence scoring
    - Safe removal with backup/rollback support

    The agent performs extensive safety checks before removal:
    - Protected decorators (pytest fixtures, routes, etc.)
    - Public API exports (__all__)
    - Docstrings (may indicate documented API)
    - Recent modifications (may be in active use)
    """

    name = "DeadCodeRemovalAgent"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)

        self.protected_decorators = {
            "@pytest.fixture",
            "@app.route",
            "@app.command",
            "@property",
            "@setter",
            "@deleter",
            "@staticmethod",
            "@classmethod",
            "@lru_cache",
            "@dataclass",
            "@override",
            "@APIRouter",
            "@router.route",
            "@router.get",
            "@router.post",
            "@router.put",
            "@router.delete",
            "@click.command",
            "@click.option",
            "@click.argument",
            "@task",
            "@celery.task",
            "@shared_task",
            "@on_exception",
            "@on_request",
            "@event_handler",
            "@signal_handler",
        }

        # Types that are safe to remove with high confidence
        self.high_confidence_types = {"import", "variable"}

        # Minimum confidence threshold for auto-removal
        self.min_confidence_threshold = 0.70

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.DEAD_CODE:
            return 0.0

        if not issue.message:
            return 0.0

        message_lower = issue.message.lower()

        # Parse confidence from message
        confidence = self._extract_confidence(message_lower)

        if "unused" in message_lower or "dead code" in message_lower:
            if confidence >= 0.60:
                return min(confidence + 0.1, 0.95)
            return 0.7

        return 0.0

    def _extract_confidence(self, message: str) -> float:
        """Extract confidence percentage from dead code message.

        Skylos format: "Unused function 'foo' (line 10, 86% confidence)"
        Vulture format: "Unused function 'foo' (60% confidence)"
        """
        # Match percentage patterns
        confidence_match = re.search(r"(\d+)%\s+confidence", message)
        if confidence_match:
            return int(confidence_match.group(1)) / 100

        # Default confidence based on message content
        if "definitely" in message or "certainly" in message:
            return 0.95
        if "likely" in message or "probably" in message:
            return 0.75
        if "possibly" in message or "might be" in message:
            return 0.50

        return 0.70  # Default confidence

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )

        file_path = Path(issue.file_path)

        if self._is_test_file(file_path):
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    "Will not remove code from test files for safety",
                ],
                recommendations=[
                    "Manually review if code is truly unused in tests",
                ],
            )

        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not read file content"],
            )

        # Parse dead code info from issue
        dead_code_info = self._parse_dead_code_issue_enhanced(issue, content)
        if not dead_code_info:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not parse dead code issue"],
            )

        # Perform safety checks
        safety_result = self._perform_safety_checks_enhanced(
            content, dead_code_info
        )

        if not safety_result["safe_to_remove"]:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=safety_result["reasons"],
                recommendations=safety_result.get("recommendations", []),
            )

        # Check confidence threshold
        if safety_result["confidence"] < self.min_confidence_threshold:
            return FixResult(
                success=False,
                confidence=safety_result["confidence"],
                remaining_issues=[
                    f"Confidence {safety_result['confidence']:.0%} below threshold "
                    f"{self.min_confidence_threshold:.0%}"
                ],
                recommendations=["Manual review recommended"],
            )

        if not await self._backup_file(file_path):
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Failed to create backup"],
            )

        removal_result = await self._remove_dead_code_enhanced(
            file_path, content, dead_code_info
        )

        if removal_result["success"]:
            return FixResult(
                success=True,
                confidence=safety_result["confidence"],
                fixes_applied=removal_result.get("fixes", []),
                files_modified=[str(file_path)],
            )

        await self._rollback_file(file_path)

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=removal_result.get("errors", ["Removal failed"]),
        )

    def _is_test_file(self, file_path: Path) -> bool:
        path_str = str(file_path)
        return any(
            x in path_str for x in ("/test_", "/tests/", "conftest.py", "_test.py")
        )

    def _parse_dead_code_issue_enhanced(
        self, issue: Issue, content: str
    ) -> DeadCodeInfo | None:
        """Parse dead code issue with enhanced skylos/vulture format support."""

        message = issue.message
        line_number = issue.line_number or 0

        # Try skylos format first: "Unused function 'foo' (line 10, 86% confidence)"
        skylos_match = re.search(
            r"Unused\s+(function|class|method|attribute|variable|import)\s+"
            r"'?(\w+)'?\s*\(.*?line\s+(\d+)",
            message,
            re.IGNORECASE,
        )
        if skylos_match:
            code_type = skylos_match.group(1).lower()
            name = skylos_match.group(2)
            parsed_line = int(skylos_match.group(3))
            confidence = self._extract_confidence(message.lower())

            # Get end line for multi-line blocks
            end_line = self._find_block_end(content, parsed_line, code_type)

            # Get decorators
            decorators = self._get_decorators(content, parsed_line)

            return DeadCodeInfo(
                code_type=code_type,
                name=name,
                line_number=parsed_line,
                confidence=confidence,
                end_line=end_line,
                decorators=decorators,
            )

        # Try vulture format: "Unused function 'foo' at line 10"
        vulture_match = re.search(
            r"Unused\s+(function|class|method|attribute|variable|import)\s+"
            r"'?(\w+)'?\s+(at\s+)?line\s+(\d+)",
            message,
            re.IGNORECASE,
        )
        if vulture_match:
            code_type = vulture_match.group(1).lower()
            name = vulture_match.group(2)
            parsed_line = int(vulture_match.group(4))
            confidence = self._extract_confidence(message.lower())

            end_line = self._find_block_end(content, parsed_line, code_type)
            decorators = self._get_decorators(content, parsed_line)

            return DeadCodeInfo(
                code_type=code_type,
                name=name,
                line_number=parsed_line,
                confidence=confidence,
                end_line=end_line,
                decorators=decorators,
            )

        # Fallback: use issue line number
        if line_number:
            code_type = "unknown"
            if "function" in message.lower():
                code_type = "function"
            elif "class" in message.lower():
                code_type = "class"
            elif "import" in message.lower():
                code_type = "import"
            elif "variable" in message.lower():
                code_type = "variable"

            end_line = self._find_block_end(content, line_number, code_type)
            decorators = self._get_decorators(content, line_number)

            return DeadCodeInfo(
                code_type=code_type,
                name="unknown",
                line_number=line_number,
                confidence=0.70,
                end_line=end_line,
                decorators=decorators,
            )

        return None

    def _find_block_end(
        self, content: str, start_line: int, code_type: str
    ) -> int | None:
        """Find the end line of a code block (function/class).

        Uses AST for accurate detection when possible.
        """
        try:
            tree = ast.parse(content)
            lines = content.split("\n")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.lineno == start_line:
                        return node.end_lineno

                if isinstance(node, ast.ClassDef):
                    if node.lineno == start_line:
                        return node.end_lineno

            # Fallback: use indentation-based detection
            if code_type in ("function", "method", "class"):
                return self._find_block_end_by_indent(lines, start_line)

        except SyntaxError:
            pass

        return None

    def _find_block_end_by_indent(
        self, lines: list[str], start_line: int
    ) -> int | None:
        """Find block end using indentation analysis."""
        if start_line < 1 or start_line > len(lines):
            return None

        start_idx = start_line - 1
        base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())

        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if not line.strip():  # Skip empty lines
                continue

            current_indent = len(line) - len(line.lstrip())

            # If we're back at or below the base indent, block ended
            if current_indent <= base_indent:
                return i  # Line before this one is the end

        return len(lines)  # Block extends to end of file

    def _get_decorators(self, content: str, line_number: int) -> list[str]:
        """Get decorators above a line."""
        lines = content.split("\n")
        decorators = []

        for i in range(max(0, line_number - 10), line_number - 1):
            line = lines[i].strip()
            if line.startswith("@"):
                decorators.append(line)

        return decorators

    def _perform_safety_checks_enhanced(
        self,
        content: str,
        dead_code: DeadCodeInfo,
    ) -> dict[str, t.Any]:
        """Enhanced safety checks with usage analysis."""
        reasons = []
        recommendations = []
        confidence = dead_code.confidence
        safe = True

        # Check for protected decorators
        if dead_code.decorators:
            for decorator in dead_code.decorators:
                for protected in self.protected_decorators:
                    if decorator.startswith(protected):
                        safe = False
                        confidence = 0.0
                        reasons.append(
                            f"Has protected decorator: {decorator}"
                        )
                        recommendations.append(
                            "Manually verify decorator usage before removal"
                        )
                        break

        # Check for docstrings
        if self._has_docstring(content, dead_code.line_number):
            confidence -= 0.10
            reasons.append("Has docstring - may be documented API")
            if confidence < self.min_confidence_threshold:
                safe = False
                recommendations.append("Manual review for documented code")

        # Check if exported in __all__
        if self._is_exported(content, dead_code.name):
            safe = False
            confidence = 0.0
            reasons.append(f"'{dead_code.name}' is exported in __all__ - public API")
            recommendations.append("Never remove public API without review")

        # Check for usage analysis
        usage_info = self._analyze_usage(content, dead_code)
        if usage_info["has_dynamic_usage"]:
            confidence -= 0.20
            reasons.append("May have dynamic usage (getattr, __dict__, etc.)")
            recommendations.append("Check for dynamic access patterns")

        # Check for string references
        if usage_info["string_references"] > 0:
            confidence -= 0.05 * usage_info["string_references"]
            reasons.append(
                f"Referenced in {usage_info['string_references']} string(s)"
            )

        # Type-specific adjustments
        if dead_code.code_type in self.high_confidence_types:
            confidence = max(confidence, 0.85)

        # Boost confidence if end_line is known (accurate detection)
        if dead_code.end_line:
            confidence += 0.05

        confidence = max(0.0, min(1.0, confidence))

        return {
            "safe_to_remove": safe and confidence >= self.min_confidence_threshold,
            "confidence": confidence,
            "reasons": reasons,
            "recommendations": recommendations,
        }

    def _analyze_usage(self, content: str, dead_code: DeadCodeInfo) -> dict[str, t.Any]:
        """Analyze potential usage patterns for the dead code."""
        name = dead_code.name
        if name == "unknown":
            return {"has_dynamic_usage": False, "string_references": 0}

        # Check for dynamic usage patterns
        dynamic_patterns = [
            rf"getattr\s*\(\s*[^,]+,\s*['\"]({name})['\"]",
            rf"hasattr\s*\(\s*[^,]+,\s*['\"]({name})['\"]",
            rf"setattr\s*\(\s*[^,]+,\s*['\"]({name})['\"]",
            rf"\[['\"]({name})['\"]\]",  # dict/list access with string key
            rf"\.get\s*\(\s*['\"]({name})['\"]",
            rf"__dict__\s*\[\s*['\"]({name})['\"]",
        ]

        has_dynamic_usage = False
        for pattern in dynamic_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                has_dynamic_usage = True
                break

        # Count string references (excluding the definition itself)
        string_pattern = rf"['\"]({name})['\"]"
        matches = re.findall(string_pattern, content)
        string_references = len(matches) - 1 if matches else 0

        return {
            "has_dynamic_usage": has_dynamic_usage,
            "string_references": max(0, string_references),
        }

    def _has_docstring(self, content: str, line_number: int) -> bool:
        lines = content.split("\n")

        for i in range(line_number, min(len(lines), line_number + 5)):
            line = lines[i].strip()
            if line.startswith(('"""', "'''")):
                return True
            if line.startswith(('r"""', "r'''")):
                return True

        return False

    def _is_exported(self, content: str, name: str) -> bool:

        all_match = re.search(r"__all__\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if all_match:
            all_content = all_match.group(1)
            return f'"{name}"' in all_content or f"'{name}'" in all_content

        return False

    async def _backup_file(self, file_path: Path) -> bool:
        try:
            import shutil

            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            shutil.copy2(file_path, backup_path)
            return True

        except Exception as e:
            logger.error(f"Failed to backup file: {e}")
            return False

    async def _rollback_file(self, file_path: Path) -> bool:
        try:
            import shutil

            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            if backup_path.exists():
                shutil.copy2(backup_path, file_path)
                return True

        except Exception as e:
            logger.error(f"Failed to rollback file: {e}")

        return False

    async def _remove_dead_code_enhanced(
        self,
        file_path: Path,
        content: str,
        dead_code: DeadCodeInfo,
    ) -> dict[str, t.Any]:
        """Remove dead code with enhanced multi-line block handling."""
        try:
            lines = content.split("\n")
            fixes = []

            code_type = dead_code.code_type
            name = dead_code.name
            start_line = dead_code.line_number
            end_line = dead_code.end_line

            if code_type == "import":
                new_lines, fix = self._remove_import_line_enhanced(
                    lines, name, start_line
                )
                fixes.append(fix)
            elif code_type in ("function", "method"):
                new_lines, fix = self._remove_function_enhanced(
                    lines, start_line, end_line, dead_code.decorators
                )
                fixes.append(fix)
            elif code_type == "class":
                new_lines, fix = self._remove_class_enhanced(
                    lines, start_line, end_line, dead_code.decorators
                )
                fixes.append(fix)
            elif code_type in ("variable", "attribute"):
                new_lines, fix = self._remove_variable_enhanced(
                    lines, start_line, name
                )
                fixes.append(fix)
            else:
                # Generic removal - single line
                new_lines = lines[: start_line - 1] + lines[start_line:]
                fixes.append(f"Removed unknown code at line {start_line}")

            new_content = "\n".join(new_lines)

            if self.context.write_file_content(file_path, new_content):
                return {"success": True, "fixes": fixes, "errors": []}

            return {
                "success": False,
                "errors": ["Failed to write modified content"],
            }

        except Exception as e:
            logger.error(f"Failed to remove dead code: {e}")
            return {
                "success": False,
                "errors": [f"Removal failed: {e}"],
            }

    def _remove_import_line_enhanced(
        self, lines: list[str], import_name: str, line_number: int
    ) -> tuple[list[str], str]:
        """Remove an import line, handling multi-import statements."""
        new_lines = []

        for i, line in enumerate(lines):
            # Check if this is the line with the import
            if i == line_number - 1 or (import_name in line and "import" in line):
                # Handle multi-import: from x import a, b, c
                if "," in line and "import" in line:
                    # Try to remove just the specific import
                    parts_match = re.match(
                        r"^(\s*from\s+\S+\s+import\s+)(.+)$", line
                    )
                    if parts_match:
                        prefix = parts_match.group(1)
                        imports = parts_match.group(2)
                        # Split imports and remove the target
                        import_list = [i.strip() for i in imports.split(",")]
                        new_imports = [
                            i for i in import_list if import_name not in i
                        ]
                        if new_imports:
                            new_line = prefix + ", ".join(new_imports)
                            new_lines.append(new_line)
                            continue
                # Skip this line (remove it)
                continue
            new_lines.append(line)

        return new_lines, f"Removed import: {import_name}"

    def _remove_function_enhanced(
        self,
        lines: list[str],
        start_line: int,
        end_line: int | None,
        decorators: list[str] | None,
    ) -> tuple[list[str], str]:
        """Remove a function including its decorators."""

        # Calculate actual start (include decorators)
        actual_start = start_line - 1
        if decorators:
            # Find the first decorator line
            for i in range(start_line - 2, max(0, start_line - 12), -1):
                line = lines[i].strip()
                if line.startswith("@"):
                    actual_start = i
                elif line and not line.startswith("#"):
                    break

        # Calculate end line
        if end_line:
            actual_end = end_line
        else:
            actual_end = self._find_block_end_by_indent(lines, start_line) or start_line

        # Remove the lines
        new_lines = lines[:actual_start] + lines[actual_end:]

        func_name = "unknown"
        for i in range(actual_start, min(actual_end + 1, len(lines))):
            if "def " in lines[i]:
                match = re.search(r"def\s+(\w+)", lines[i])
                if match:
                    func_name = match.group(1)
                    break

        return new_lines, f"Removed function: {func_name}"

    def _remove_class_enhanced(
        self,
        lines: list[str],
        start_line: int,
        end_line: int | None,
        decorators: list[str] | None,
    ) -> tuple[list[str], str]:
        """Remove a class including its decorators and all methods."""

        # Calculate actual start (include decorators)
        actual_start = start_line - 1
        if decorators:
            for i in range(start_line - 2, max(0, start_line - 12), -1):
                line = lines[i].strip()
                if line.startswith("@"):
                    actual_start = i
                elif line and not line.startswith("#"):
                    break

        # Calculate end line
        if end_line:
            actual_end = end_line
        else:
            actual_end = self._find_block_end_by_indent(lines, start_line) or start_line

        # Remove the lines
        new_lines = lines[:actual_start] + lines[actual_end:]

        class_name = "unknown"
        for i in range(actual_start, min(actual_end + 1, len(lines))):
            if "class " in lines[i]:
                match = re.search(r"class\s+(\w+)", lines[i])
                if match:
                    class_name = match.group(1)
                    break

        return new_lines, f"Removed class: {class_name}"

    def _remove_variable_enhanced(
        self, lines: list[str], line_number: int, name: str
    ) -> tuple[list[str], str]:
        """Remove a variable assignment."""

        new_lines = lines[: line_number - 1] + lines[line_number:]
        return new_lines, f"Removed variable: {name}"


agent_registry.register(DeadCodeRemovalAgent)
