from __future__ import annotations

import logging
import re
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
)

if t.TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class DeadCodeRemovalAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.name = "DeadCodeRemovalAgent"

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
        }

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.DEAD_CODE:
            return 0.0

        if not issue.message:
            return 0.0

        message_lower = issue.message.lower()

        if "unused" in message_lower or "dead code" in message_lower:
            confidence_match = re.search(r"(\d+)%\s+confidence", message_lower)
            if confidence_match:
                reported_confidence = int(confidence_match.group(1))

                if reported_confidence >= 60:
                    return min(reported_confidence / 100, 0.90)

            return 0.7

        return 0.0

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

        parse_result = self._parse_dead_code_issue(issue)
        if not parse_result:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not parse dead code issue"],
            )

        code_type, name, line_number = parse_result

        safety_result = self._perform_safety_checks(
            content, code_type, name, line_number
        )

        if not safety_result["safe_to_remove"]:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=safety_result["reasons"],
                recommendations=safety_result.get("recommendations", []),
            )

        if not await self._backup_file(file_path):
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Failed to create backup"],
            )

        removal_result = await self._remove_dead_code(
            file_path, content, code_type, name, line_number
        )

        if removal_result["success"]:
            return FixResult(
                success=True,
                confidence=safety_result["confidence"],
                fixes_applied=[f"Removed unused {code_type}: {name}"],
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

    def _parse_dead_code_issue(self, issue: Issue) -> tuple[str, str, int] | None:

        vulture_match = re.search(
            r"Unused\s+(\w+):\s+'?(\w+)'?", issue.message, re.IGNORECASE
        )
        if vulture_match:
            code_type = vulture_match.group(1)
            name = vulture_match.group(2)
            line_number = issue.line_number or 0
            return (code_type, name, line_number)

        if issue.line_number:
            if "function" in issue.message.lower():
                return ("function", "unknown", issue.line_number)
            if "class" in issue.message.lower():
                return ("class", "unknown", issue.line_number)
            if "import" in issue.message.lower():
                return ("import", "unknown", issue.line_number)

        return None

    def _perform_safety_checks(
        self,
        content: str,
        code_type: str,
        name: str,
        line_number: int,
    ) -> dict[str, t.Any]:
        reasons = []
        recommendations = []
        confidence = 0.90
        safe = True

        content.split("\n")

        if self._has_decorators(content, line_number):
            safe = False
            confidence = 0.0
            reasons.append(
                "Code has decorators - may be used externally or by framework"
            )
            recommendations.append("Manually verify decorators are safe to remove")

        if self._has_docstring(content, line_number):
            confidence -= 0.10
            reasons.append("Code has docstring - may be documented API")
            if confidence < 0.80:
                safe = False
                recommendations.append("Manual review required for documented code")

        if self._is_exported(content, name):
            safe = False
            confidence = 0.0
            reasons.append("Code is exported in __all__ - public API")
            recommendations.append("Never remove public API code without manual review")

        if self._is_recently_modified(content, line_number):
            confidence -= 0.15
            reasons.append("Code was recently modified (may be in active use)")
            if confidence < 0.80:
                safe = False
                recommendations.append("Wait 1-2 weeks before removing")

        if code_type == "import":
            safe = True
            confidence = 0.95
            reasons = []

        return {
            "safe_to_remove": safe,
            "confidence": confidence,
            "reasons": reasons,
            "recommendations": recommendations,
        }

    def _has_decorators(self, content: str, line_number: int) -> bool:
        lines = content.split("\n")

        for i in range(max(0, line_number - 10), line_number):
            line = lines[i].strip()
            if line.startswith("@"):
                for protected in self.protected_decorators:
                    if line.startswith(protected):
                        return True
                return True

        return False

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

    def _is_recently_modified(self, content: str, line_number: int) -> bool:
        with suppress(Exception):
            import subprocess

            file_path = self.context.project_path

            result = subprocess.run(
                [
                    "git",
                    "blame",
                    "-L",
                    f"{line_number},{line_number}+1",
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                blame_output = result.stdout
                return "(not committed)" not in blame_output.lower()

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

    async def _remove_dead_code(
        self,
        file_path: Path,
        content: str,
        code_type: str,
        name: str,
        line_number: int,
    ) -> dict[str, t.Any]:
        try:
            lines = content.split("\n")

            if code_type == "import":
                new_lines = self._remove_import_line(lines, name)
            elif code_type in ("function", "method"):
                new_lines = self._remove_function(lines, line_number)
            elif code_type == "class":
                new_lines = self._remove_class(lines, line_number)
            elif code_type == "attribute":
                new_lines = self._remove_attribute(lines, line_number)
            else:
                return {
                    "success": False,
                    "errors": [f"Unsupported code type: {code_type}"],
                }

            new_content = "\n".join(new_lines)

            if self.context.write_file_content(file_path, new_content):
                return {"success": True, "errors": []}

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

    def _remove_import_line(self, lines: list[str], import_name: str) -> list[str]:
        new_lines = []

        for line in lines:
            if import_name in line and ("import" in line or "from" in line):
                continue
            new_lines.append(line)

        return new_lines

    def _remove_function(self, lines: list[str], start_line: int) -> list[str]:

        indent = None
        for i in range(start_line - 1, len(lines)):
            line = lines[i]
            if i >= start_line - 1:
                if indent is None and line.strip():
                    indent = len(line) - len(line.lstrip())
                elif line.strip():
                    current_indent = len(line) - len(line.lstrip())

                    if current_indent <= indent:
                        return lines[: start_line - 1] + lines[i:]

        return lines[: start_line - 1] + lines[start_line:]

    def _remove_class(self, lines: list[str], start_line: int) -> list[str]:

        return self._remove_function(lines, start_line)

    def _remove_attribute(self, lines: list[str], line_number: int) -> list[str]:

        return lines[: line_number - 1] + lines[line_number:]


agent_registry = t.Any
