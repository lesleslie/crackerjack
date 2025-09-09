"""Zuban adapter for type checking."""

import typing as t
from dataclasses import dataclass
from pathlib import Path

from .rust_tool_adapter import BaseRustToolAdapter, Issue, ToolResult

if t.TYPE_CHECKING:
    from crackerjack.models.context import ExecutionContext


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
        """Zuban supports JSON output mode."""
        return True

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

        # JSON output for AI agents
        if self._should_use_json_output():
            args.append("--output-format=json")

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
            issues = []
            for item in data.get("diagnostics", []):
                # Determine severity
                severity = item.get("severity", "error").lower()
                if severity not in ["error", "warning", "info"]:
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
        issues = []

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
            # MyPy/Zuban format: "file.py:line:col: severity: message [error-code]"
            # Also support: "file.py:line: severity: message"

            if ":" not in line:
                return None

            # Split and parse components
            parts = line.split(":", 3)
            if len(parts) < 3:
                return None

            file_path = Path(parts[0].strip())

            try:
                line_number = int(parts[1].strip())
            except ValueError:
                return None

            # Check if we have column number
            column = 1
            message_part = ""

            if len(parts) == 4:
                # Try to parse column
                try:
                    column = int(parts[2].strip())
                    message_part = parts[3].strip()
                except ValueError:
                    # parts[2] might be severity, not column
                    message_part = f"{parts[2]}:{parts[3]}".strip()
            else:
                message_part = parts[2].strip()

            # Parse severity and message
            severity = "error"  # default
            message = message_part
            error_code = None

            # Extract severity if present
            severity_indicators = ["error:", "warning:", "note:", "info:"]
            for indicator in severity_indicators:
                if message_part.lower().startswith(indicator):
                    severity = indicator[:-1]  # Remove colon
                    message = message_part[len(indicator) :].strip()
                    break

            # Extract error code if present (e.g., [attr-defined])
            if "[" in message and "]" in message:
                code_start = message.rfind("[")
                code_end = message.rfind("]")
                if code_start < code_end:
                    error_code = message[code_start + 1 : code_end]
                    message = message[:code_start].strip()

            # Map severity to standard values
            if severity in ["note", "info"]:
                severity = "info"
            elif severity not in ["error", "warning"]:
                severity = "error"

            return TypeIssue(
                file_path=file_path,
                line_number=line_number,
                column=column,
                message=message,
                severity=severity,
                error_code=error_code,
            )

        except (IndexError, ValueError):
            return None
