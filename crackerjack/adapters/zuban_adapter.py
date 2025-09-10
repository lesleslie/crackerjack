"""Zuban adapter for type checking."""

import typing as t
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .rust_tool_adapter import BaseRustToolAdapter, Issue, ToolResult

if t.TYPE_CHECKING:
    from crackerjack.orchestration.execution_strategies import ExecutionContext


@dataclass
class TypeIssue(Issue):
    """Zuban type checking issue."""

    severity: str = "error"  # Override default, type errors are typically errors
    column: int = 1
    error_code: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
        """Convert issue to dictionary with Zuban-specific fields."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "column": self.column,
                "error_code": self.error_code,
            }
        )
        return base_dict


class ZubanAdapter(BaseRustToolAdapter):
    """Zuban type checking adapter."""

    def __init__(
        self,
        context: "ExecutionContext",
        strict_mode: bool = True,
        mypy_compatibility: bool = True,
    ) -> None:
        """Initialize Zuban adapter."""
        super().__init__(context)
        self.strict_mode = strict_mode
        self.mypy_compatibility = mypy_compatibility

    def get_tool_name(self) -> str:
        """Get the name of the tool."""
        return "zuban"

    def supports_json_output(self) -> bool:
        """Zuban does not support JSON output mode."""
        return False

    def get_command_args(self, target_files: list[Path]) -> list[str]:
        """Get command arguments for Zuban execution."""
        args = ["uv", "run", "zuban"]

        # Mode selection
        if self.mypy_compatibility:
            args.append("zmypy")  # MyPy-compatible mode
        else:
            args.append("check")  # Native Zuban mode

        # Strictness
        if self.strict_mode:
            args.append("--strict")

        # Add error codes for better parsing
        args.append("--show-error-codes")

        # Target files/directories
        if target_files:
            args.extend(str(f) for f in target_files)
        else:
            args.append(".")  # Check entire project

        return args

    def parse_output(self, output: str) -> ToolResult:
        """Parse Zuban output into standardized result."""
        if self._should_use_json_output():
            return self._parse_json_output(output)
        return self._parse_text_output(output)

    def _parse_json_output(self, output: str) -> ToolResult:
        """Parse JSON output for AI agents."""
        data = self._parse_json_output_safe(output)
        if data is None:
            return self._create_error_result(
                "Invalid JSON output from Zuban", raw_output=output
            )

        try:
            issues: list[Issue] = []
            for item in data.get("diagnostics", []):
                # Determine severity
                severity = item.get("severity", "error").lower()
                if severity not in ("error", "warning", "info"):
                    severity = "error"

                issues.append(
                    TypeIssue(
                        file_path=Path(item["file"]),
                        line_number=item.get("line", 1),
                        column=item.get("column", 1),
                        message=item["message"],
                        severity=severity,
                        error_code=item.get("code"),
                    )
                )

            # Success if no error-level issues
            error_issues = [i for i in issues if i.severity == "error"]
            success = len(error_issues) == 0

            return ToolResult(
                success=success,
                issues=issues,
                raw_output=output,
                tool_version=self.get_tool_version(),
            )

        except (KeyError, TypeError, ValueError) as e:
            return self._create_error_result(
                f"Failed to parse Zuban JSON output: {e}", raw_output=output
            )

    def _parse_text_output(self, output: str) -> ToolResult:
        """Parse text output for human-readable display."""
        issues: list[Issue] = []

        if not output.strip():
            # No output typically means no type errors found
            return ToolResult(
                success=True,
                issues=[],
                raw_output=output,
                tool_version=self.get_tool_version(),
            )

        # Parse Zuban/MyPy-style text output
        for line in output.strip().split("\\n"):
            line = line.strip()
            if not line:
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        # Success if no error-level issues
        error_issues = [i for i in issues if i.severity == "error"]
        success = len(error_issues) == 0

        return ToolResult(
            success=success,
            issues=issues,
            raw_output=output,
            tool_version=self.get_tool_version(),
        )

    def _parse_text_line(self, line: str) -> TypeIssue | None:
        """Parse a single line of Zuban text output."""
        try:
            basic_info = self._extract_line_components(line)
            if not basic_info:
                return None

            file_path, line_number, message_part = basic_info
            column = self._extract_column_number(message_part)

            message_data = self._parse_message_content(message_part)
            severity = self._normalize_severity(message_data["severity"] or "error")

            return TypeIssue(
                file_path=file_path,
                line_number=line_number,
                column=column,
                message=message_data["message"] or "Unknown error",
                severity=severity,
                error_code=message_data["error_code"],
            )

        except (IndexError, ValueError):
            return None

    def _extract_line_components(self, line: str) -> tuple[Path, int, str] | None:
        """Extract file path, line number, and remaining message from line."""
        if ":" not in line:
            return None

        parts = line.split(":", 3)
        if len(parts) < 3:
            return None

        file_path = Path(parts[0].strip())

        try:
            line_number = int(parts[1].strip())
        except ValueError:
            return None

        # Handle both 3-part and 4-part formats
        if len(parts) == 4:
            message_part = f"{parts[2]}:{parts[3]}".strip()
        else:
            message_part = parts[2].strip()

        return file_path, line_number, message_part

    def _extract_column_number(self, message_part: str) -> int:
        """Extract column number if present in message part."""
        # Try to extract column from the beginning of message_part
        parts = message_part.split(":", 2)
        if len(parts) >= 2:
            with suppress(ValueError):
                return int(parts[0].strip())
        return 1

    def _parse_message_content(self, message_part: str) -> dict[str, str | None]:
        """Parse message content to extract severity, message, and error code."""
        # Skip column number if present
        parts = message_part.split(":", 2)
        if len(parts) >= 2:
            try:
                int(parts[0].strip())  # Check if first part is column number
                working_message = ":".join(parts[1:]).strip()
            except ValueError:
                working_message = message_part
        else:
            working_message = message_part

        severity, message = self._extract_severity_and_message(working_message)
        error_code = self._extract_error_code(message)

        # Remove error code from message if found
        if error_code and "[" in message:
            code_start = message.rfind("[")
            message = message[:code_start].strip()

        return {"severity": severity, "message": message, "error_code": error_code}

    def _extract_severity_and_message(self, working_message: str) -> tuple[str, str]:
        """Extract severity indicator and remaining message."""
        severity_indicators = ["error:", "warning:", "note:", "info:"]

        for indicator in severity_indicators:
            if working_message.lower().startswith(indicator):
                severity = indicator[:-1]  # Remove colon
                message = working_message[len(indicator) :].strip()
                return severity, message

        # Default to error severity
        return "error", working_message

    def _extract_error_code(self, message: str) -> str | None:
        """Extract error code from message if present."""
        if "[" in message and "]" in message:
            code_start = message.rfind("[")
            code_end = message.rfind("]")
            if code_start < code_end:
                return message[code_start + 1 : code_end]
        return None

    def _normalize_severity(self, severity: str) -> str:
        """Normalize severity to standard values."""
        if severity in ("note", "info"):
            return "info"
        elif severity not in ("error", "warning"):
            return "error"
        return severity
