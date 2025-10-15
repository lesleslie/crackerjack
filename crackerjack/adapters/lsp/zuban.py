"""Zuban adapter for type checking with LSP integration."""

import asyncio
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from ._base import BaseRustToolAdapter, Issue, ToolResult

if t.TYPE_CHECKING:
    from crackerjack.orchestration.execution_strategies import ExecutionContext
    from crackerjack.services.lsp_client import LSPClient

# Import the LSP client wrapper
from ._client import ZubanLSPClient


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
    """Zuban type checking adapter with LSP integration."""

    def __init__(
        self,
        context: "ExecutionContext",
        strict_mode: bool = True,
        mypy_compatibility: bool = True,
        use_lsp: bool = True,
    ) -> None:
        """Initialize Zuban adapter.

        Args:
            context: Execution context
            strict_mode: Enable strict type checking
            mypy_compatibility: Use MyPy-compatible mode
            use_lsp: Enable LSP integration for faster checking
        """
        super().__init__(context)
        self.strict_mode = strict_mode
        self.mypy_compatibility = mypy_compatibility
        self.use_lsp = use_lsp
        self._lsp_client: LSPClient | None = None
        self._lsp_wrapper: ZubanLSPClient | None = None
        self._lsp_available = False

    def get_tool_name(self) -> str:
        """Get the name of the tool."""
        return "zuban"

    def check_tool_health(self) -> bool:
        """Check if Zuban is functional before use.

        Returns:
            True if Zuban can be used safely, False otherwise
        """
        try:
            import subprocess

            # Test basic version command - this should not crash
            result = subprocess.run(
                ["uv", "run", "zuban", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return False

            # Test if we can parse TOML without crashing
            # Create a minimal test to check for TOML parsing bug
            result = subprocess.run(
                ["uv", "run", "zuban", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            return result.returncode == 0

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception):
            return False

    def supports_json_output(self) -> bool:
        """Zuban does not support JSON output mode."""
        return False

    def _ensure_lsp_client(self) -> None:
        """Initialize LSP client if not already available."""
        if not self.use_lsp or self._lsp_client is not None:
            return

        try:
            # Import here to avoid circular imports
            from crackerjack.services.lsp_client import LSPClient

            self._lsp_client = LSPClient()
            self._lsp_available = self._lsp_client.is_server_running()

        except ImportError:
            self._lsp_available = False

    async def get_lsp_diagnostics(self, target_files: list[Path]) -> list[TypeIssue]:
        """Get real-time diagnostics from LSP server.

        Args:
            target_files: List of files to check

        Returns:
            List of type issues found by LSP server
        """
        self._ensure_lsp_client()

        if not self._lsp_available or not self._lsp_client:
            return []

        try:
            # Convert paths to strings for LSP client
            [str(f.resolve()) for f in target_files]

            # Get diagnostics from LSP client
            diagnostics, _ = self._lsp_client.check_project_with_feedback(
                project_path=target_files[0].parent if target_files else Path.cwd(),
                show_progress=False,
            )

            # Convert LSP diagnostics to TypeIssue objects
            issues: list[TypeIssue] = []
            for file_path, file_diagnostics in diagnostics.items():
                for diag in file_diagnostics:
                    issues.append(
                        TypeIssue(
                            file_path=Path(file_path),
                            line_number=diag.get("line", 1),
                            column=diag.get("column", 1),
                            message=diag.get("message", "Type error"),
                            severity=diag.get("severity", "error"),
                            error_code=diag.get("code"),
                        )
                    )

            return issues

        except Exception:
            # LSP failed, return empty list[t.Any] to trigger fallback
            self._lsp_available = False
            return []

    async def get_lsp_diagnostics_optimized(
        self, target_files: list[Path]
    ) -> list[TypeIssue]:
        """Get diagnostics using optimized LSP wrapper.

        Args:
            target_files: List of files to check

        Returns:
            List of type issues found by LSP server
        """
        if not self.use_lsp:
            return []

        if not self._lsp_wrapper:
            self._lsp_wrapper = ZubanLSPClient()

        try:
            async with self._lsp_wrapper as lsp:
                if not await self._initialize_lsp_workspace(lsp, target_files):
                    return []

                issues = await self._process_files_with_lsp(lsp, target_files)
                return issues

        except Exception:
            # Fallback to original LSP client method
            return await self.get_lsp_diagnostics(target_files)

    async def _initialize_lsp_workspace(
        self, lsp: t.Any, target_files: list[Path]
    ) -> bool:
        """Initialize LSP workspace and return success status."""
        root_path = target_files[0].parent if target_files else Path.cwd()
        init_result = await lsp.initialize(root_path)
        return init_result and not init_result.get("error")

    async def _process_files_with_lsp(
        self, lsp: t.Any, target_files: list[Path]
    ) -> list[TypeIssue]:
        """Process files with LSP and collect diagnostics."""
        issues: list[TypeIssue] = []
        for file_path in target_files:
            if file_path.exists():
                file_issues = await self._get_file_diagnostics_from_lsp(lsp, file_path)
                issues.extend(file_issues)
        return issues

    async def _get_file_diagnostics_from_lsp(
        self, lsp: t.Any, file_path: Path
    ) -> list[TypeIssue]:
        """Get diagnostics for a single file from LSP."""
        await lsp.text_document_did_open(file_path)
        await asyncio.sleep(0.1)  # Wait briefly for diagnostics

        diagnostics = await lsp.get_diagnostics()
        issues = []

        for diag in diagnostics:
            issue = self._create_type_issue_from_diagnostic(diag, file_path)
            issues.append(issue)

        await lsp.text_document_did_close(file_path)
        return issues

    def _create_type_issue_from_diagnostic(
        self, diag: dict[str, t.Any], file_path: Path
    ) -> TypeIssue:
        """Create a TypeIssue from an LSP diagnostic."""
        return TypeIssue(
            file_path=Path(diag.get("uri", str(file_path)).replace("file://", "")),
            line_number=diag.get("range", {}).get("start", {}).get("line", 0) + 1,
            column=diag.get("range", {}).get("start", {}).get("character", 0) + 1,
            message=diag.get("message", "Type error"),
            severity=self._map_lsp_severity(diag.get("severity", 1)),
            error_code=diag.get("code"),
        )

    def _map_lsp_severity(self, lsp_severity: int) -> str:
        """Map LSP severity codes to string values.

        Args:
            lsp_severity: LSP severity (1=Error, 2=Warning, 3=Information, 4=Hint)

        Returns:
            String severity level
        """
        return {1: "error", 2: "warning", 3: "info", 4: "info"}.get(
            lsp_severity, "error"
        )

    def get_command_args(self, target_files: list[Path]) -> list[str]:
        """Get command arguments for Zuban execution (fallback mode)."""
        args = ["uv", "run", "zuban"]

        # Mode selection
        if self.mypy_compatibility:
            args.append("mypy")  # MyPy-compatible mode
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

    async def check_with_lsp_or_fallback(self, target_files: list[Path]) -> ToolResult:
        """Check files using LSP if available, otherwise fallback to CLI mode.

        Args:
            target_files: Files to type-check

        Returns:
            ToolResult with issues found
        """
        # First check if Zuban is functional at all
        if not self.check_tool_health():
            return self._create_error_result(
                "Zuban is not functional due to TOML parsing bug. "
                "Consider using pyright as alternative. "
                "See ZUBAN_TOML_PARSING_BUG_ANALYSIS.md for details."
            )

        # Try optimized LSP mode first
        if self.use_lsp:
            # Try optimized LSP wrapper first, then fallback to basic LSP client
            lsp_issues = await self.get_lsp_diagnostics_optimized(target_files)
            if not lsp_issues:  # If optimized fails, try basic LSP client
                lsp_issues = await self.get_lsp_diagnostics(target_files)

            if lsp_issues is not None:  # LSP succeeded (empty list is valid)
                # Create successful result from LSP
                error_issues = [i for i in lsp_issues if i.severity == "error"]
                success = len(error_issues) == 0

                result = ToolResult(
                    success=success,
                    issues=list[Issue](
                        lsp_issues
                    ),  # Convert TypeIssue list to Issue list
                    raw_output=f"LSP diagnostics: {len(lsp_issues)} issue(s) found",
                    tool_version=self.get_tool_version(),
                )
                # Add execution mode as custom attribute for tracking
                result._execution_mode = "lsp"
                return result

        # LSP unavailable or failed, fallback to CLI mode
        return await self._run_cli_fallback(target_files)

    async def _run_cli_fallback(self, target_files: list[Path]) -> ToolResult:
        """Run Zuban in CLI mode as fallback.

        Args:
            target_files: Files to check

        Returns:
            ToolResult from CLI execution
        """
        # Use the existing CLI execution logic
        import subprocess

        try:
            cmd_args = self.get_command_args(target_files)
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.context.root_path
                if hasattr(self.context, "root_path")
                else None,
            )

            # Parse the CLI output using existing methods
            tool_result = self.parse_output(result.stdout + result.stderr)

            # Mark as CLI mode for tracking
            tool_result._execution_mode = "cli"

            return tool_result

        except subprocess.TimeoutExpired:
            return self._create_error_result("Zuban execution timed out")
        except Exception as e:
            return self._create_error_result(f"Zuban execution failed: {e}")

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
