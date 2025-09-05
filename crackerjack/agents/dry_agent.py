import typing as t
from pathlib import Path

from ..services.regex_patterns import SAFE_PATTERNS
from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class DRYAgent(SubAgent):
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
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path specified for DRY violation"],
            )

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        return None

    async def _process_dry_violation(self, file_path: Path) -> FixResult:
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
        violations: list[dict[str, t.Any]] = []

        violations.extend(self._detect_error_response_patterns(content))

        violations.extend(self._detect_path_conversion_patterns(content))

        violations.extend(self._detect_file_existence_patterns(content))

        violations.extend(self._detect_exception_patterns(content))

        return violations

    def _detect_error_response_patterns(self, content: str) -> list[dict[str, t.Any]]:
        violations: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        error_pattern = SAFE_PATTERNS["detect_error_response_patterns"]

        error_responses: list[dict[str, t.Any]] = []
        for i, line in enumerate(lines):
            if error_pattern.test(line.strip()):
                # Extract error message using the pattern's compiled regex access
                # Access the compiled pattern from SAFE_PATTERNS to get groups
                compiled_pattern = error_pattern._get_compiled_pattern()
                match = compiled_pattern.search(line.strip())
                if match:
                    error_responses.append(
                        {
                            "line_number": i + 1,
                            "content": line.strip(),
                            "error_message": match.group(1),
                        },
                    )

        if len(error_responses) >= 3:
            violations.append(
                {
                    "type": "error_response_pattern",
                    "instances": error_responses,
                    "suggestion": "Extract to error utility function",
                },
            )

        return violations

    def _detect_path_conversion_patterns(self, content: str) -> list[dict[str, t.Any]]:
        violations: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        path_pattern = SAFE_PATTERNS["detect_path_conversion_patterns"]

        path_conversions: list[dict[str, t.Any]] = [
            {
                "line_number": i + 1,
                "content": line.strip(),
            }
            for i, line in enumerate(lines)
            if path_pattern.test(line)
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
        violations: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        existence_pattern = SAFE_PATTERNS["detect_file_existence_patterns"]

        existence_checks: list[dict[str, t.Any]] = [
            {
                "line_number": i + 1,
                "content": line.strip(),
            }
            for i, line in enumerate(lines)
            if existence_pattern.test(line.strip())
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
        violations: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        exception_pattern = SAFE_PATTERNS["detect_exception_patterns"]

        exception_handlers: list[dict[str, t.Any]] = []
        for i, line in enumerate(lines):
            if exception_pattern.test(line.strip()):
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
        lines = content.split("\n")
        modified = False

        for violation in violations:
            lines, changed = self._apply_violation_fix(lines, violation)
            modified = modified or changed

        return "\n".join(lines) if modified else content

    def _apply_violation_fix(
        self, lines: list[str], violation: dict[str, t.Any]
    ) -> tuple[list[str], bool]:
        """Apply fix for a specific violation type."""
        violation_type = violation["type"]

        if violation_type == "error_response_pattern":
            return self._fix_error_response_pattern(lines, violation)
        elif violation_type == "path_conversion_pattern":
            return self._fix_path_conversion_pattern(lines, violation)

        return lines, False

    def _fix_error_response_pattern(
        self,
        lines: list[str],
        violation: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        # Add utility functions to the file
        utility_lines = self._add_error_response_utilities(lines)

        # Apply pattern replacements to affected lines
        self._apply_error_pattern_replacements(lines, violation, len(utility_lines))

        return lines, True

    def _add_error_response_utilities(self, lines: list[str]) -> list[str]:
        """Add utility functions for error responses and path conversion."""
        utility_function = """
def _create_error_response(message: str, success: bool = False) -> str:

    import json
    return json.dumps({"error": message, "success": success})

def _ensure_path(path: str | Path) -> Path:

    return Path(path) if isinstance(path, str) else path
"""

        insert_pos = self._find_utility_insert_position(lines)
        utility_lines = utility_function.strip().split("\n")

        for i, util_line in enumerate(utility_lines):
            lines.insert(insert_pos + i, util_line)

        return [line for line in utility_lines]

    def _find_utility_insert_position(self, lines: list[str]) -> int:
        """Find the best position to insert utility functions."""
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                insert_pos = i + 1
            elif line.strip() and not line.strip().startswith("#"):
                break
        return insert_pos

    def _apply_error_pattern_replacements(
        self, lines: list[str], violation: dict[str, t.Any], utility_lines_count: int
    ) -> None:
        """Apply pattern replacements to lines with error response patterns."""
        path_pattern = SAFE_PATTERNS["fix_path_conversion_with_ensure_path"]

        for instance in violation["instances"]:
            line_number: int = int(instance["line_number"])
            line_idx = line_number - 1 + utility_lines_count

            if line_idx < len(lines):
                original_line: str = lines[line_idx]
                new_line: str = path_pattern.apply(original_line)
                lines[line_idx] = new_line

    def _fix_path_conversion_pattern(
        self,
        lines: list[str],
        violation: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix path conversion patterns by adding utility function."""
        utility_function_added = self._check_ensure_path_exists(lines)
        adjustment = 0

        if not utility_function_added:
            adjustment = self._add_ensure_path_utility(lines)

        modified = self._apply_path_pattern_replacements(
            lines, violation, adjustment, utility_function_added
        )

        return lines, modified

    def _check_ensure_path_exists(self, lines: list[str]) -> bool:
        """Check if _ensure_path utility function already exists."""
        return any(
            "_ensure_path" in line and "def _ensure_path" in line for line in lines
        )

    def _add_ensure_path_utility(self, lines: list[str]) -> int:
        """Add the _ensure_path utility function and return adjustment count."""
        insert_pos = self._find_utility_insert_position(lines)

        utility_lines = [
            "",
            "def _ensure_path(path: str | Path) -> Path:",
            '    """Convert string path to Path object if needed."""',
            "    return Path(path) if isinstance(path, str) else path",
            "",
        ]

        for i, util_line in enumerate(utility_lines):
            lines.insert(insert_pos + i, util_line)

        return len(utility_lines)

    def _apply_path_pattern_replacements(
        self,
        lines: list[str],
        violation: dict[str, t.Any],
        adjustment: int,
        utility_function_added: bool,
    ) -> bool:
        """Replace path conversion patterns with utility function calls."""
        path_pattern = SAFE_PATTERNS["fix_path_conversion_simple"]

        modified = False
        for instance in violation["instances"]:
            line_number: int = int(instance["line_number"])
            line_idx = line_number - 1 + (0 if utility_function_added else adjustment)

            if line_idx < len(lines):
                original_line: str = lines[line_idx]
                new_line = path_pattern.apply(original_line)

                if new_line != original_line:
                    lines[line_idx] = new_line
                    modified = True

        return modified


agent_registry.register(DRYAgent)
