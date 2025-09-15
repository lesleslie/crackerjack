"""Skylos adapter for dead code detection."""

import typing as t
from dataclasses import dataclass
from pathlib import Path

from .rust_tool_adapter import BaseRustToolAdapter, Issue, ToolResult

if t.TYPE_CHECKING:
    from crackerjack.orchestration.execution_strategies import ExecutionContext


@dataclass
class DeadCodeIssue(Issue):
    """Skylos dead code detection issue."""

    severity: str = "warning"  # Override default, dead code is typically warning
    issue_type: str = "unknown"  # "import", "function", "class", "variable", etc.
    name: str = "unknown"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, t.Any]:
        """Convert issue to dictionary with Skylos-specific fields."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "issue_type": self.issue_type,
                "name": self.name,
                "confidence": self.confidence,
            }
        )
        return base_dict


class SkylosAdapter(BaseRustToolAdapter):
    """Skylos dead code detection adapter."""

    def __init__(
        self,
        context: "ExecutionContext",
        confidence_threshold: int = 86,
        web_dashboard_port: int = 5090,
    ) -> None:
        """Initialize Skylos adapter."""
        super().__init__(context)
        self.confidence_threshold = confidence_threshold
        self.web_dashboard_port = web_dashboard_port

    def get_tool_name(self) -> str:
        """Get the name of the tool."""
        return "skylos"

    def supports_json_output(self) -> bool:
        """Skylos supports JSON output mode."""
        return True

    def get_command_args(self, target_files: list[Path]) -> list[str]:
        """Get command arguments for Skylos execution."""
        args = ["uv", "run", "skylos", "--confidence", str(self.confidence_threshold)]

        # Add JSON mode for AI agents
        if self._should_use_json_output():
            args.append("--json")

        # Add web dashboard for interactive mode
        if self.context.interactive:
            args.extend(["--web", "--port", str(self.web_dashboard_port)])

        # Add target files or default to current directory
        if target_files:
            args.extend(str(f) for f in target_files)
        else:
            args.append(".")

        return args

    def parse_output(self, output: str) -> ToolResult:
        """Parse Skylos output into standardized result."""
        if self._should_use_json_output():
            return self._parse_json_output(output)
        return self._parse_text_output(output)

    def _parse_json_output(self, output: str) -> ToolResult:
        """Parse JSON output for AI agents."""
        data = self._parse_json_output_safe(output)
        if data is None:
            return self._create_error_result(
                "Invalid JSON output from Skylos", raw_output=output
            )

        try:
            issues: list[Issue] = [
                DeadCodeIssue(
                    file_path=Path(item["file"]),
                    line_number=item.get("line", 1),
                    message=f"Dead {item['type']}: {item['name']}",
                    severity="warning",  # Dead code is typically a warning, not error
                    issue_type=item["type"],
                    name=item["name"],
                    confidence=item.get("confidence", 0.0),
                )
                for item in data.get("dead_code", [])
            ]

            # Skylos success means no issues found
            success = len(issues) == 0

            return ToolResult(
                success=success,
                issues=issues,
                raw_output=output,
                tool_version=self.get_tool_version(),
            )

        except (KeyError, TypeError, ValueError) as e:
            return self._create_error_result(
                f"Failed to parse Skylos JSON output: {e}", raw_output=output
            )

    def _parse_text_output(self, output: str) -> ToolResult:
        """Parse text output for human-readable display."""
        issues: list[Issue] = []

        if not output.strip():
            # No output typically means no dead code found
            return ToolResult(
                success=True,
                issues=[],
                raw_output=output,
                tool_version=self.get_tool_version(),
            )

        # Parse Skylos text output
        # Expected format: "file.py:line: unused import 'name' (confidence: 86%)"
        for line in output.strip().split("\\n"):
            line = line.strip()
            if not line:
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        # Success if no issues found
        success = len(issues) == 0

        return ToolResult(
            success=success,
            issues=issues,
            raw_output=output,
            tool_version=self.get_tool_version(),
        )

    def _parse_text_line(self, line: str) -> DeadCodeIssue | None:
        """Parse a single line of Skylos text output."""
        try:
            basic_info = self._extract_basic_line_info(line)
            if not basic_info:
                return None

            file_path, line_number, message_part = basic_info
            issue_details = self._extract_issue_details(message_part)
            confidence = self._extract_confidence(message_part)

            return DeadCodeIssue(
                file_path=file_path,
                line_number=line_number,
                message=f"Dead {issue_details['type']}: {issue_details['name']}",
                severity="warning",
                issue_type=issue_details["type"],
                name=issue_details["name"],
                confidence=confidence,
            )

        except (IndexError, ValueError):
            return None

    def _extract_basic_line_info(self, line: str) -> tuple[Path, int, str] | None:
        """Extract file path, line number, and message from line."""
        if ":" not in line:
            return None

        parts = line.split(":", 2)
        if len(parts) < 3:
            return None

        file_path = Path(parts[0].strip())
        try:
            line_number = int(parts[1].strip())
        except ValueError:
            line_number = 1

        message_part = parts[2].strip()
        return file_path, line_number, message_part

    def _extract_issue_details(self, message_part: str) -> dict[str, str]:
        """Extract issue type and name from message."""
        issue_type = "unknown"
        name = "unknown"

        lower_message = message_part.lower()

        if "unused import" in lower_message:
            issue_type = "import"
            name = self._extract_name_from_quotes(message_part)
        elif "unused function" in lower_message:
            issue_type = "function"
            name = self._extract_name_from_quotes(message_part)
        elif "unused class" in lower_message:
            issue_type = "class"
            name = self._extract_name_from_quotes(message_part)

        return {"type": issue_type, "name": name}

    def _extract_name_from_quotes(self, message_part: str) -> str:
        """Extract name from single quotes in message."""
        quoted_parts = message_part.split("'")
        if len(quoted_parts) >= 2:
            return quoted_parts[1]
        return "unknown"

    def _extract_confidence(self, message_part: str) -> float:
        """Extract confidence percentage from message."""
        if "(confidence:" not in message_part:
            return float(self.confidence_threshold)

        try:
            conf_part = message_part.split("(confidence:")[1].split(")")[0]
            return float(conf_part.strip().replace("%", ""))
        except (ValueError, IndexError):
            return float(self.confidence_threshold)
