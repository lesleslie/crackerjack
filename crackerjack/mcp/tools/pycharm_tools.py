"""PyCharm MCP Tools for IDE-level diagnostics and operations.

This module provides MCP tools that integrate with PyCharm's IDE capabilities,
including diagnostics, code search, and symbol information.

Security: All inputs are sanitized via PyCharmMCPAdapter.
Performance: Circuit breaker and caching handled by PyCharmMCPAdapter.
"""

from __future__ import annotations

import json
import logging
import typing as t
from contextlib import suppress

from crackerjack.mcp.context import get_context
from crackerjack.services.pycharm_mcp_integration import (
    PyCharmMCPAdapter,
)

logger = logging.getLogger(__name__)


def register_pycharm_tools(mcp_app: t.Any) -> None:
    """Register PyCharm integration tools with the MCP server.

    Args:
        mcp_app: The FastMCP application instance.
    """
    _register_get_ide_diagnostics_tool(mcp_app)
    _register_search_code_tool(mcp_app)
    _register_get_symbol_info_tool(mcp_app)
    _register_find_usages_tool(mcp_app)
    _register_pycharm_health_tool(mcp_app)

    logger.info("Registered PyCharm MCP tools")


def _get_adapter() -> PyCharmMCPAdapter:
    """Get or create the PyCharm MCP adapter singleton.

    The adapter is stored in the MCP context for reuse across requests.

    Returns:
        PyCharmMCPAdapter instance.
    """
    context = get_context()
    if not hasattr(context, "_pycharm_adapter"):
        context._pycharm_adapter = PyCharmMCPAdapter(
            mcp_client=None,
            timeout=30.0,
            max_results=100,
        )
        logger.debug("Created PyCharm MCP adapter singleton")
    return context._pycharm_adapter


def _create_success_response(data: dict[str, t.Any]) -> str:
    """Create a successful JSON response."""
    return json.dumps({"success": True, **data})


def _create_error_response(message: str, **extra: t.Any) -> str:
    """Create an error JSON response."""
    return json.dumps({"success": False, "error": message, **extra})


def _register_get_ide_diagnostics_tool(mcp_app: t.Any) -> None:
    """Register the get_ide_diagnostics tool."""

    @mcp_app.tool()
    async def get_ide_diagnostics(
        file_path: str,
        errors_only: bool = False,
    ) -> str:
        """Get IDE-level diagnostics for a file from PyCharm.

        This tool retrieves diagnostics from PyCharm's inspections, which include:
        - Syntax errors and warnings
        - Type checking issues
        - Code style violations
        - Unused imports and variables
        - Potential bugs and code smells

        Args:
            file_path: Path to the file to analyze (relative to project root).
            errors_only: If True, only return errors (not warnings or info).

        Returns:
            JSON string with list of diagnostic issues in ToolIssue-compatible format.

        Example:
            >>> result = await get_ide_diagnostics("src/main.py")
            >>> data = json.loads(result)
            >>> for issue in data["issues"]:
            ...     print(f"{issue['line_number']}: {issue['message']}")
        """
        adapter = _get_adapter()

        try:
            problems = await adapter.get_file_problems(file_path, errors_only)
        except Exception as e:
            logger.error(f"Failed to get IDE diagnostics: {e}")
            return _create_error_response(str(e), file_path=file_path)

        # Convert to ToolIssue-compatible format for consistency with other tools
        issues = []
        for problem in problems:
            severity = problem.get("severity", "warning").lower()
            # Filter by errors_only if requested
            if errors_only and severity != "error":
                continue

            issues.append(
                {
                    "file_path": file_path,
                    "line_number": problem.get("line"),
                    "column_number": problem.get("column"),
                    "message": problem.get("message", ""),
                    "code": problem.get("code"),
                    "severity": _map_severity(severity),
                    "suggestion": problem.get("quick_fix"),
                    "source": "pycharm",
                }
            )

        return _create_success_response(
            {
                "issues": issues,
                "count": len(issues),
                "file_path": file_path,
            }
        )


def _register_search_code_tool(mcp_app: t.Any) -> None:
    """Register the search_code tool."""

    @mcp_app.tool()
    async def search_code(
        pattern: str,
        file_pattern: str | None = None,
    ) -> str:
        """Search for a regex pattern in the codebase via PyCharm's index.

        This uses PyCharm's optimized search index for fast results across
        large codebases. Falls back to grep if PyCharm is unavailable.

        Args:
            pattern: Regex pattern to search for.
            file_pattern: Optional glob pattern to filter files (e.g., "*.py").

        Returns:
            JSON string with search results including file, line, column, and context.

        Example:
            >>> result = await search_code(r"# type: ignore", "*.py")
            >>> data = json.loads(result)
            >>> for match in data["results"]:
            ...     print(f"{match['file_path']}:{match['line']}")
        """
        adapter = _get_adapter()

        try:
            results = await adapter.search_regex(pattern, file_pattern)
        except Exception as e:
            logger.error(f"Code search failed: {e}")
            return _create_error_response(str(e), pattern=pattern)

        formatted_results = [
            {
                "file_path": r.file_path,
                "line": r.line_number,
                "column": r.column,
                "match": r.match_text,
                "context_before": r.context_before,
                "context_after": r.context_after,
            }
            for r in results
        ]

        return _create_success_response(
            {
                "results": formatted_results,
                "count": len(formatted_results),
                "pattern": pattern,
                "file_pattern": file_pattern,
            }
        )


def _register_get_symbol_info_tool(mcp_app: t.Any) -> None:
    """Register the get_symbol_info tool."""

    @mcp_app.tool()
    async def get_symbol_info(
        symbol_name: str,
        include_usages: bool = False,
    ) -> str:
        """Get information about a code symbol from PyCharm's index.

        Retrieves symbol metadata including type, definition location,
        and optionally usage count.

        Args:
            symbol_name: Name of the symbol to look up (function, class, variable).
            include_usages: If True, include usage count (slower).

        Returns:
            JSON string with symbol information or error if not found.

        Note:
            This tool requires PyCharm MCP server to be connected.
            Returns an error if the connection is not available.

        Example:
            >>> result = await get_symbol_info("BaseModel")
            >>> data = json.loads(result)
            >>> if data["success"]:
            ...     print(f"Type: {data['symbol_type']}")
            ...     print(f"Defined in: {data['definition_file']}")
        """
        adapter = _get_adapter()

        # Check if MCP is available
        health = await adapter.health_check()
        if not health.get("mcp_available"):
            return _create_error_response(
                "PyCharm MCP server not connected. Symbol info requires IDE connection.",
                symbol=symbol_name,
                hint="Ensure PyCharm is running with MCP server enabled.",
            )

        # TODO: Implement actual symbol lookup when PyCharm MCP provides this
        # For now, return a placeholder indicating the feature needs implementation
        return _create_error_response(
            "Symbol info tool not yet implemented - requires PyCharm MCP extension",
            symbol=symbol_name,
            status="not_implemented",
        )


def _register_find_usages_tool(mcp_app: t.Any) -> None:
    """Register the find_usages tool."""

    @mcp_app.tool()
    async def find_usages(
        symbol_name: str,
        file_path: str | None = None,
        limit: int = 50,
    ) -> str:
        """Find all usages of a symbol in the codebase.

        Uses PyCharm's index for fast cross-file usage detection.

        Args:
            symbol_name: Name of the symbol to find usages for.
            file_path: Optional file path to scope the search.
            limit: Maximum number of results to return (default 50).

        Returns:
            JSON string with list of usage locations.

        Note:
            This tool requires PyCharm MCP server to be connected.

        Example:
            >>> result = await find_usages("process_data")
            >>> data = json.loads(result)
            >>> for usage in data["usages"]:
            ...     print(f"{usage['file']}:{usage['line']}")
        """
        adapter = _get_adapter()

        # Check if MCP is available
        health = await adapter.health_check()
        if not health.get("mcp_available"):
            return _create_error_response(
                "PyCharm MCP server not connected. Find usages requires IDE connection.",
                symbol=symbol_name,
            )

        # TODO: Implement actual usage search when PyCharm MCP provides this
        return _create_error_response(
            "Find usages tool not yet implemented - requires PyCharm MCP extension",
            symbol=symbol_name,
            status="not_implemented",
        )


def _register_pycharm_health_tool(mcp_app: t.Any) -> None:
    """Register the pycharm_health tool."""

    @mcp_app.tool()
    async def pycharm_health() -> str:
        """Check the health of the PyCharm MCP connection.

        Returns status information about the PyCharm integration including:
        - Whether MCP connection is available
        - Circuit breaker state
        - Failure count
        - Cache size

        Returns:
            JSON string with health status information.

        Example:
            >>> result = await pycharm_health()
            >>> data = json.loads(result)
            >>> if data["mcp_available"]:
            ...     print("PyCharm MCP is connected")
            ... else:
            ...     print("Using fallback mode")
        """
        adapter = _get_adapter()

        with suppress(Exception):
            health = await adapter.health_check()
            return _create_success_response(
                {
                    "mcp_available": health.get("mcp_available", False),
                    "circuit_breaker_open": health.get("circuit_breaker_open", False),
                    "failure_count": health.get("failure_count", 0),
                    "cache_size": health.get("cache_size", 0),
                    "status": "healthy"
                    if not health.get("circuit_breaker_open")
                    else "degraded",
                }
            )

        return _create_error_response("Health check failed")


def _map_severity(pycharm_severity: str) -> str:
    """Map PyCharm severity to Crackerjack severity.

    Args:
        pycharm_severity: Severity from PyCharm (error, warning, info, etc.)

    Returns:
        Crackerjack-compatible severity (error, warning, info).
    """
    mapping = {
        "error": "error",
        "warning": "warning",
        "weak_warning": "info",
        "info": "info",
        "typo": "info",
        "server_problem": "error",
    }
    return mapping.get(pycharm_severity.lower(), "warning")
