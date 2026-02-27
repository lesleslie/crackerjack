from __future__ import annotations

import ast
import logging
import re
import typing as t
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
    code_type: str
    name: str
    line_number: int
    confidence: float
    end_line: int | None = None
    decorators: list[str] | None = None


class DeadCodeRemovalAgent(SubAgent):
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

        self.high_confidence_types = {"import", "variable"}

        self.min_confidence_threshold = 0.70

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.DEAD_CODE:
            return 0.0

        if not issue.message:
            return 0.0

        message_lower = issue.message.lower()

        confidence = self._extract_confidence(message_lower)

        if "unused" in message_lower or "dead code" in message_lower:
            if confidence >= 0.60:
                return min(confidence + 0.1, 0.95)
            return 0.7

        return 0.0

    def _extract_confidence(self, message: str) -> float:

        confidence_match = re.search(r"(\d+)%\s+confidence", message)
        if confidence_match:
            return int(confidence_match.group(1)) / 100

        if "definitely" in message or "certainly" in message:
            return 0.95
        if "likely" in message or "probably" in message:
            return 0.75
        if "possibly" in message or "might be" in message:
            return 0.50

        return 0.70

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

        dead_code_info = self._parse_dead_code_issue_enhanced(issue, content)
        if not dead_code_info:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not parse dead code issue"],
            )

        safety_result = self._perform_safety_checks_enhanced(content, dead_code_info)

        if not safety_result["safe_to_remove"]:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=safety_result["reasons"],
                recommendations=safety_result.get("recommendations", []),
            )

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
                files_modified=[file_path],  # type: ignore
            )

        await self._rollback_file(file_path)

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=removal_result.get("errors", ["Removal failed"]),
        )

    def _is_test_file(self, file_path: Path) -> bool:
        path_str = file_path
        return any(
            x in path_str for x in ("/test_", "/tests/", "conftest.py", "_test.py")
        )

    def _parse_dead_code_issue_enhanced(
        self, issue: Issue, content: str
    ) -> DeadCodeInfo | None:

        message = issue.message
        line_number = issue.line_number or 0

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
        with suppress(SyntaxError):
            tree = ast.parse(content)
            lines = content.split("\n")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.lineno == start_line:
                        return node.end_lineno

                if isinstance(node, ast.ClassDef):
                    if node.lineno == start_line:
                        return node.end_lineno

            if code_type in ("function", "method", "class"):
                return self._find_block_end_by_indent(lines, start_line)

        return None

    def _find_block_end_by_indent(
        self, lines: list[str], start_line: int
    ) -> int | None:
        if start_line < 1 or start_line > len(lines):
            return None

        start_idx = start_line - 1
        base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())

        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if not line.strip():
                continue

            current_indent = len(line) - len(line.lstrip())

            if current_indent <= base_indent:
                return i

        return len(lines)

    def _get_decorators(self, content: str, line_number: int) -> list[str]:
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
        reasons = []
        recommendations = []
        confidence = dead_code.confidence
        safe = True

        if dead_code.decorators:
            for decorator in dead_code.decorators:
                for protected in self.protected_decorators:
                    if decorator.startswith(protected):
                        safe = False
                        confidence = 0.0
                        reasons.append(f"Has protected decorator: {decorator}")
                        recommendations.append(
                            "Manually verify decorator usage before removal"
                        )
                        break

        if self._has_docstring(content, dead_code.line_number):
            confidence -= 0.10
            reasons.append("Has docstring - may be documented API")
            if confidence < self.min_confidence_threshold:
                safe = False
                recommendations.append("Manual review for documented code")

        if self._is_exported(content, dead_code.name):
            safe = False
            confidence = 0.0
            reasons.append(f"'{dead_code.name}' is exported in __all__ - public API")
            recommendations.append("Never remove public API without review")

        usage_info = self._analyze_usage(content, dead_code)
        if usage_info["has_dynamic_usage"]:
            confidence -= 0.20
            reasons.append("May have dynamic usage (getattr, __dict__, etc.)")
            recommendations.append("Check for dynamic access patterns")

        if usage_info["string_references"] > 0:
            confidence -= 0.05 * usage_info["string_references"]
            reasons.append(f"Referenced in {usage_info['string_references']} string(s)")

        if dead_code.code_type in self.high_confidence_types:
            confidence = max(confidence, 0.85)

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
        name = dead_code.name
        if name == "unknown":
            return {"has_dynamic_usage": False, "string_references": 0}

        dynamic_patterns = [
            rf"getattr\s*\(\s*[^,]+,\s*['\"]({name})['\"]",
            rf"hasattr\s*\(\s*[^,]+,\s*['\"]({name})['\"]",
            rf"setattr\s*\(\s*[^,]+,\s*['\"]({name})['\"]",
            rf"\[['\"]({name})['\"]\]",
            rf"\.get\s*\(\s*['\"]({name})['\"]",
            rf"__dict__\s*\[\s*['\"]({name})['\"]",
        ]

        has_dynamic_usage = False
        for pattern in dynamic_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                has_dynamic_usage = True
                break

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
                new_lines, fix = self._remove_variable_enhanced(lines, start_line, name)
                fixes.append(fix)
            else:
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
        new_lines = []

        for i, line in enumerate(lines):
            if i == line_number - 1 or (import_name in line and "import" in line):
                if "," in line and "import" in line:
                    parts_match = re.match(r"^(\s*from\s+\S+\s+import\s+)(.+)$", line)
                    if parts_match:
                        prefix = parts_match.group(1)
                        imports = parts_match.group(2)

                        import_list = [i.strip() for i in imports.split(",")]
                        new_imports = [i for i in import_list if import_name not in i]
                        if new_imports:
                            new_line = prefix + ", ".join(new_imports)
                            new_lines.append(new_line)
                            continue

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

        actual_start = start_line - 1
        if decorators:
            for i in range(start_line - 2, max(0, start_line - 12), -1):
                line = lines[i].strip()
                if line.startswith("@"):
                    actual_start = i
                elif line and not line.startswith("#"):
                    break

        if end_line:
            actual_end = end_line
        else:
            actual_end = self._find_block_end_by_indent(lines, start_line) or start_line

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

        actual_start = start_line - 1
        if decorators:
            for i in range(start_line - 2, max(0, start_line - 12), -1):
                line = lines[i].strip()
                if line.startswith("@"):
                    actual_start = i
                elif line and not line.startswith("#"):
                    break

        if end_line:
            actual_end = end_line
        else:
            actual_end = self._find_block_end_by_indent(lines, start_line) or start_line

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

        new_lines = lines[: line_number - 1] + lines[line_number:]
        return new_lines, f"Removed variable: {name}"


agent_registry.register(DeadCodeRemovalAgent)
