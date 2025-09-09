"""Skylos adapter for dead code detection."""

import typing as t
from dataclasses import dataclass
from pathlib import Path

from .rust_tool_adapter import BaseRustToolAdapter, Issue, ToolResult

if t.TYPE_CHECKING:
    from crackerjack.models.context import ExecutionContext


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


class SkylsAdapter(BaseRustToolAdapter):
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
            issues = []
            for item in data.get("dead_code", []):
                issues.append(
                    DeadCodeIssue(
                        file_path=Path(item["file"]),
                        line_number=item.get("line", 1),
                        message=f"Dead {item['type']}: {item['name']}",
                        severity="warning",  # Dead code is typically a warning, not error
                        issue_type=item["type"],
                        name=item["name"],
                        confidence=item.get("confidence", 0.0),
                    )
                )

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
        issues = []

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
            # Example: "src/main.py:10: unused import 'os' (confidence: 86%)"
            if ":" not in line:
                return None

            # Split on first two colons to get file:line:message
            parts = line.split(":", 2)
            if len(parts) < 3:
                return None

            file_path = Path(parts[0].strip())
            try:
                line_number = int(parts[1].strip())
            except ValueError:
                line_number = 1

            message_part = parts[2].strip()

            # Extract issue type and name
            issue_type = "unknown"
            name = "unknown"
            confidence = float(self.confidence_threshold)

            # Parse message for details
            if "unused import" in message_part.lower():
                issue_type = "import"
                # Extract import name from quotes
                import_match = message_part.split("'")
                if len(import_match) >= 2:
                    name = import_match[1]
            elif "unused function" in message_part.lower():
                issue_type = "function"
                func_match = message_part.split("'")
                if len(func_match) >= 2:
                    name = func_match[1]
            elif "unused class" in message_part.lower():
                issue_type = "class"
                class_match = message_part.split("'")
                if len(class_match) >= 2:
                    name = class_match[1]

            # Extract confidence if available
            if "(confidence:" in message_part:
                conf_part = message_part.split("(confidence:")[1].split(")")[0]
                try:
                    confidence = float(conf_part.strip().replace("%", ""))
                except ValueError:
                    pass

            return DeadCodeIssue(
                file_path=file_path,
                line_number=line_number,
                message=f"Dead {issue_type}: {name}",
                severity="warning",
                issue_type=issue_type,
                name=name,
                confidence=confidence,
            )

        except (IndexError, ValueError):
            return None
