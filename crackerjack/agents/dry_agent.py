import re
import typing as t
from pathlib import Path

from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class DRYAgent(SubAgent):
    """Agent specialized in detecting and fixing DRY (Don't Repeat Yourself) violations."""

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DRY_VIOLATION}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.DRY_VIOLATION:
            return 0.9
        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing DRY violation: {issue.message}")

        validation_result = self._validate_dry_issue(issue)
        if validation_result:
            return validation_result

        if issue.file_path is None:
            return self._create_dry_error_result(
                ValueError("File path is required for DRY violation"),
            )

        file_path = Path(issue.file_path)

        try:
            return await self._process_dry_violation(file_path)
        except Exception as e:
            return self._create_dry_error_result(e)

    def _validate_dry_issue(self, issue: Issue) -> FixResult | None:
        """Validate the DRY violation issue has required information."""
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path specified for DRY violation"],
            )

        # At this point, issue.file_path is not None due to the check above
        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        return None

    async def _process_dry_violation(self, file_path: Path) -> FixResult:
        """Process DRY violation detection and fixing for a file."""
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        violations = self._detect_dry_violations(content, file_path)

        if not violations:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No DRY violations detected"],
            )

        return self._apply_and_save_dry_fixes(file_path, content, violations)

    def _apply_and_save_dry_fixes(
        self,
        file_path: Path,
        content: str,
        violations: list[dict[str, t.Any]],
    ) -> FixResult:
        """Apply DRY fixes and save changes."""
        fixed_content = self._apply_dry_fixes(content, violations)

        if fixed_content == content:
            return self._create_no_fixes_result()

        success = self.context.write_file_content(file_path, fixed_content)
        if not success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write fixed file: {file_path}"],
            )

        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=[
                f"Fixed {len(violations)} DRY violations",
                "Consolidated repetitive patterns",
            ],
            files_modified=[str(file_path)],
            recommendations=["Verify functionality after DRY fixes"],
        )

    def _create_no_fixes_result(self) -> FixResult:
        """Create result for when no fixes could be applied."""
        return FixResult(
            success=False,
            confidence=0.5,
            remaining_issues=["Could not automatically fix DRY violations"],
            recommendations=[
                "Manual refactoring required",
                "Consider extracting common patterns to utility functions",
                "Create base classes or mixins for repeated functionality",
            ],
        )

    def _create_dry_error_result(self, error: Exception) -> FixResult:
        """Create result for DRY processing errors."""
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Error processing file: {error}"],
        )

    def _detect_dry_violations(
        self,
        content: str,
        file_path: Path,
    ) -> list[dict[str, t.Any]]:
        """Detect various types of DRY violations in the code."""
        violations: list[dict[str, t.Any]] = []

        # Detect error response patterns
        violations.extend(self._detect_error_response_patterns(content))

        # Detect path conversion patterns
        violations.extend(self._detect_path_conversion_patterns(content))

        # Detect file existence patterns
        violations.extend(self._detect_file_existence_patterns(content))

        # Detect exception handling patterns
        violations.extend(self._detect_exception_patterns(content))

        return violations

    def _detect_error_response_patterns(self, content: str) -> list[dict[str, t.Any]]:
        """Detect repetitive error response patterns."""
        violations: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        # Pattern: return f'{"error": "message", "success": false}'
        error_pattern = re.compile(
            r'return\s+f?[\'\"]\{[\'\""]error[\'\""]:\s*[\'\""]([^\'\"]*)[\'\""].*\}[\'\""]',
        )

        error_responses: list[dict[str, t.Any]] = []
        for i, line in enumerate(lines):
            match = error_pattern.search(line.strip())
            if match:
                error_responses.append(
                    {
                        "line_number": i + 1,
                        "content": line.strip(),
                        "error_message": match.group(1),
                    },
                )

        if len(error_responses) >= 3:  # Only flag if 3+ similar patterns
            violations.append(
                {
                    "type": "error_response_pattern",
                    "instances": error_responses,
                    "suggestion": "Extract to error utility function",
                },
            )

        return violations

    def _detect_path_conversion_patterns(self, content: str) -> list[dict[str, t.Any]]:
        """Detect repetitive path conversion patterns."""
        violations: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        # Pattern: Path(path) if isinstance(path, str) else path
        path_pattern = re.compile(
            r"Path\([^)]+\)\s+if\s+isinstance\([^)]+,\s*str\)\s+else\s+[^)]+",
        )

        path_conversions: list[dict[str, t.Any]] = [
            {
                "line_number": i + 1,
                "content": line.strip(),
            }
            for i, line in enumerate(lines)
            if path_pattern.search(line)
        ]

        if len(path_conversions) >= 2:
            violations.append(
                {
                    "type": "path_conversion_pattern",
                    "instances": path_conversions,
                    "suggestion": "Extract to path utility function",
                },
            )

        return violations

    def _detect_file_existence_patterns(self, content: str) -> list[dict[str, t.Any]]:
        """Detect repetitive file existence check patterns."""
        violations: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        # Pattern: if not *.exists():
        existence_pattern = re.compile(r"if\s+not\s+\w+\.exists\(\):")

        existence_checks: list[dict[str, t.Any]] = [
            {
                "line_number": i + 1,
                "content": line.strip(),
            }
            for i, line in enumerate(lines)
            if existence_pattern.search(line.strip())
        ]

        if len(existence_checks) >= 3:
            violations.append(
                {
                    "type": "file_existence_pattern",
                    "instances": existence_checks,
                    "suggestion": "Extract to file validation utility",
                },
            )

        return violations

    def _detect_exception_patterns(self, content: str) -> list[dict[str, t.Any]]:
        """Detect repetitive exception handling patterns."""
        violations: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        # Pattern: except Exception as e: return {"error": str(e)}
        exception_pattern = re.compile(r"except\s+\w*Exception\s+as\s+\w+:")

        exception_handlers: list[dict[str, t.Any]] = []
        for i, line in enumerate(lines):
            if exception_pattern.search(line.strip()):
                # Look ahead for error return pattern
                if (
                    i + 1 < len(lines)
                    and "error" in lines[i + 1]
                    and "str(" in lines[i + 1]
                ):
                    exception_handlers.append(
                        {
                            "line_number": i + 1,
                            "content": line.strip(),
                            "next_line": lines[i + 1].strip(),
                        },
                    )

        if len(exception_handlers) >= 3:
            violations.append(
                {
                    "type": "exception_handling_pattern",
                    "instances": exception_handlers,
                    "suggestion": "Extract to error handling utility or decorator",
                },
            )

        return violations

    def _apply_dry_fixes(self, content: str, violations: list[dict[str, t.Any]]) -> str:
        """Apply fixes for detected DRY violations."""
        lines = content.split("\n")
        modified = False

        for violation in violations:
            if violation["type"] == "error_response_pattern":
                lines, changed = self._fix_error_response_pattern(lines, violation)
                modified = modified or changed
            elif violation["type"] == "path_conversion_pattern":
                lines, changed = self._fix_path_conversion_pattern(lines, violation)
                modified = modified or changed

        return "\n".join(lines) if modified else content

    def _fix_error_response_pattern(
        self,
        lines: list[str],
        violation: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix error response patterns by adding utility function."""
        # Add utility function at the top of the file (after imports)
        utility_function = '''
def _create_error_response(message: str, success: bool = False) -> str:
    """Utility function to create standardized error responses."""
    import json
    return json.dumps({"error": message, "success": success})
'''

        # Find the right place to insert (after imports)
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                insert_pos = i + 1
            elif line.strip() and not line.strip().startswith("#"):
                break

        # Insert utility function
        utility_lines = utility_function.strip().split("\n")
        for i, util_line in enumerate(utility_lines):
            lines.insert(insert_pos + i, util_line)

        # Replace error response patterns
        for instance in violation["instances"]:
            line_number: int = int(instance["line_number"])
            line_idx = line_number - 1 + len(utility_lines)  # Adjust for inserted lines
            if line_idx < len(lines):
                original_line: str = lines[line_idx]
                # Extract the error message
                error_msg: str = str(instance["error_message"])
                # Replace with utility function call
                indent = len(original_line) - len(original_line.lstrip())
                new_line = (
                    " " * indent + f'return _create_error_response("{error_msg}")'
                )
                lines[line_idx] = new_line

        return lines, True

    def _fix_path_conversion_pattern(
        self,
        lines: list[str],
        violation: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix path conversion patterns by adding utility function."""
        # Add utility function
        utility_function = '''
def _ensure_path(path: str | Path) -> Path:
    """Utility function to ensure a path is a Path object."""
    return Path(path) if isinstance(path, str) else path
'''

        # Find insertion point (after imports)
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                insert_pos = i + 1
            elif line.strip() and not line.strip().startswith("#"):
                break

        # Insert utility function
        utility_lines = utility_function.strip().split("\n")
        for i, util_line in enumerate(utility_lines):
            lines.insert(insert_pos + i, util_line)

        # Replace path conversion patterns
        path_pattern = re.compile(
            r"Path\([^)]+\)\s+if\s+isinstance\([^)]+,\s*str\)\s+else\s+([^)]+)",
        )

        for instance in violation["instances"]:
            line_number: int = int(instance["line_number"])
            line_idx = line_number - 1 + len(utility_lines)
            if line_idx < len(lines):
                original_line: str = lines[line_idx]
                # Replace pattern with utility function call
                new_line: str = path_pattern.sub(r"_ensure_path(\1)", original_line)
                lines[line_idx] = new_line

        return lines, True


agent_registry.register(DRYAgent)
