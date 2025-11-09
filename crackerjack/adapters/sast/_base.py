"""SAST (Static Application Security Testing) adapter protocol and base classes.

This module defines the protocol interface that all SAST adapters must implement,
providing a consistent API for static security analysis tools.

SAST tools analyze source code for:
- Security vulnerabilities (SQL injection, XSS, etc.)
- Security anti-patterns and insecure practices
- Weak cryptography implementations
- Authentication/authorization flaws
- Potential injection vulnerabilities

Protocol-based design ensures:
- Type safety via runtime_checkable protocol
- Loose coupling for testing and mocking
- Consistent interface across all SAST tools
- Integration with ACB dependency injection
"""

from __future__ import annotations

import typing as t
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from crackerjack.adapters._tool_adapter_base import (
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig
    from crackerjack.models.qa_results import QACheckType


@runtime_checkable
class SASTAdapterProtocol(Protocol):
    """Protocol for SAST (Static Application Security Testing) adapters.

    All SAST adapters must implement this protocol to ensure consistent
    behavior and integration with the Crackerjack quality assurance framework.

    SAST tools focus on finding security vulnerabilities in source code through
    static analysis, complementing secret detection (gitleaks) which prevents
    credential leaks.

    Attributes:
        settings: Tool-specific settings (severity thresholds, rulesets, etc.)
        adapter_name: Human-readable adapter name (e.g., "Semgrep (SAST)")
        module_id: Unique UUID7 identifier for this adapter module
        tool_name: CLI tool name for command execution

    Example:
        ```python
        from crackerjack.adapters.sast import SemgrepAdapter

        adapter: SASTAdapterProtocol = SemgrepAdapter()
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: ToolAdapterSettings | None

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name.

        Returns:
            Name identifying the adapter (e.g., "Bandit (SAST)", "Semgrep (SAST)")
        """
        ...

    @property
    def module_id(self) -> UUID:
        """Unique module identifier.

        Returns:
            UUID7 for reproducible module identity (ACB registration)
        """
        ...

    @property
    def tool_name(self) -> str:
        """CLI tool name.

        Returns:
            Command-line tool name for subprocess execution
        """
        ...

    async def init(self) -> None:
        """Initialize adapter with settings and dependencies.

        Must be called before using check() or other operations.
        Sets up default settings if not provided during construction.

        Raises:
            RuntimeError: If initialization fails
        """
        ...

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build tool command for execution.

        Args:
            files: Files or directories to scan for vulnerabilities
            config: Optional configuration override

        Returns:
            Command as list of strings for subprocess execution

        Example:
            ```python
            cmd = adapter.build_command(
                files=[Path("src/")],
                config=None,
            )
            # Returns: ["semgrep", "scan", "--json", "--config", "p/security-audit", "src/"]
            ```
        """
        ...

    async def check(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> ToolExecutionResult:
        """Execute SAST scan on specified files.

        Args:
            files: Files or directories to analyze for security issues
            config: Optional configuration override

        Returns:
            Execution result with parsed issues, timing, and metadata

        Example:
            ```python
            result = await adapter.check(files=[Path("src/")])
            for issue in result.issues:
                print(f"{issue.file_path}:{issue.line_number} - {issue.message}")
            ```
        """
        ...

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse tool output into standardized issues.

        Args:
            result: Raw execution result from SAST tool

        Returns:
            List of parsed security issues with severity, location, and suggestions

        Note:
            Implementations should handle both JSON and text output formats,
            with JSON preferred for structured parsing.
        """
        ...

    def _get_check_type(self) -> QACheckType:
        """Return the check type for this adapter.

        Returns:
            QACheckType.SAST for all SAST adapters
        """
        ...

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for this SAST adapter.

        Returns:
            Default QACheckConfig with sensible defaults for the tool

        Example:
            ```python
            config = adapter.get_default_config()
            assert config.check_type == QACheckType.SAST
            assert config.stage == "comprehensive"
            ```
        """
        ...


# Type alias for convenience
SASTAdapter = SASTAdapterProtocol

__all__ = [
    "SASTAdapterProtocol",
    "SASTAdapter",
]
