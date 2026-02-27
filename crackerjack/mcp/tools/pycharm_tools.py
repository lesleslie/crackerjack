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
    _register_get_ide_diagnostics_tool(mcp_app)
    _register_search_code_tool(mcp_app)
    _register_get_symbol_info_tool(mcp_app)
    _register_find_usages_tool(mcp_app)
    _register_pycharm_health_tool(mcp_app)

    logger.info("Registered PyCharm MCP tools")


def _get_adapter() -> PyCharmMCPAdapter | None:
    """Get PyCharm adapter, returning None if context not initialized."""
    try:
        context = get_context()
    except RuntimeError:
        logger.debug("MCP context not initialized")
        return None
    if not hasattr(context, "_pycharm_adapter"):
        context._pycharm_adapter = PyCharmMCPAdapter(  # type: ignore[attr-defined]
            mcp_client=None,
            timeout=30.0,
            max_results=100,
        )
        logger.debug("Created PyCharm MCP adapter singleton")
    return context._pycharm_adapter  # type: ignore[attr-defined]


def _create_success_response(data: dict[str, t.Any]) -> str:
    return json.dumps({"success": True, **data})


def _create_error_response(message: str, **extra: t.Any) -> str:
    return json.dumps({"success": False, "error": message, **extra})


def _register_get_ide_diagnostics_tool(mcp_app: t.Any) -> None:

    @mcp_app.tool()
    async def get_ide_diagnostics(
        file_path: str,
        errors_only: bool = False,
    ) -> str:
        adapter = _get_adapter()

        if adapter is None:
            return _create_error_response(
                "MCP context not initialized",
                file_path=file_path,
            )

        try:
            problems = await adapter.get_file_problems(file_path, errors_only)
        except Exception as e:
            logger.error(f"Failed to get IDE diagnostics: {e}")
            return _create_error_response(str(e), file_path=file_path)

        issues = []
        for problem in problems:
            severity = problem.get("severity", "warning").lower()

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

    @mcp_app.tool()
    async def search_code(
        pattern: str,
        file_pattern: str | None = None,
    ) -> str:
        adapter = _get_adapter()

        if adapter is None:
            return _create_error_response(
                "MCP context not initialized",
                pattern=pattern,
            )

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

    @mcp_app.tool()
    async def get_symbol_info(
        symbol_name: str,
        include_usages: bool = False,
    ) -> str:
        adapter = _get_adapter()

        if adapter is None:
            return _create_error_response(
                "MCP context not initialized",
                symbol=symbol_name,
            )

        health = await adapter.health_check()
        if not health.get("mcp_available"):
            return _create_error_response(
                "PyCharm MCP server not connected. Symbol info requires IDE connection.",
                symbol=symbol_name,
                hint="Ensure PyCharm is running with MCP server enabled.",
            )

        # TODO: Implement actual symbol lookup when PyCharm MCP provides this

        return _create_error_response(
            "Symbol info tool not yet implemented - requires PyCharm MCP extension",
            symbol=symbol_name,
            status="not_implemented",
        )


def _register_find_usages_tool(mcp_app: t.Any) -> None:

    @mcp_app.tool()
    async def find_usages(
        symbol_name: str,
        file_path: str | None = None,
        limit: int = 50,
    ) -> str:
        adapter = _get_adapter()

        if adapter is None:
            return _create_error_response(
                "MCP context not initialized",
                symbol=symbol_name,
            )

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

    @mcp_app.tool()
    async def pycharm_health() -> str:
        adapter = _get_adapter()

        if adapter is None:
            return _create_success_response(
                {
                    "healthy": False,
                    "pycharm_mcp_available": False,
                    "circuit_breaker_open": False,
                    "failure_count": 0,
                    "cache_size": 0,
                    "error": "MCP context not initialized",
                }
            )

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
    mapping = {
        "error": "error",
        "warning": "warning",
        "weak_warning": "info",
        "info": "info",
        "typo": "info",
        "server_problem": "error",
    }
    return mapping.get(pycharm_severity.lower(), "warning")
