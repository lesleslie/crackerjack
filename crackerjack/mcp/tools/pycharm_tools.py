from __future__ import annotations

import json
import logging
import re
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.mcp.context import get_context
from crackerjack.services.pycharm_mcp_integration import (
    PyCharmMCPAdapter,
)

logger = logging.getLogger(__name__)


def _resolve_local_search_root() -> Path:
    """Resolve the directory to walk for the local regex fallback.

    Prefers the MCP server context's configured ``project_path`` (set in
    ``crackerjack/mcp/server_core.py:_setup_server_context``), then falls back
    to ``Path.cwd()``. This keeps ``search_code`` deterministic regardless of
    which working directory the MCP client launched from.
    """
    try:
        ctx = get_context()
        project_path = getattr(ctx.config, "project_path", None)  # type: ignore[attr-defined]
        if project_path is not None:
            return Path(project_path).resolve()
    except RuntimeError:
        logger.debug("MCP context not initialized; using Path.cwd() for search root")
    return Path.cwd().resolve()


def register_pycharm_tools(mcp_app: t.Any) -> None:
    _register_get_ide_diagnostics_tool(mcp_app)
    _register_search_code_tool(mcp_app)
    _register_get_symbol_info_tool(mcp_app)
    _register_find_usages_tool(mcp_app)
    _register_pycharm_health_tool(mcp_app)

    logger.info("Registered PyCharm MCP tools")


def _get_adapter() -> PyCharmMCPAdapter | None:
    try:
        context = get_context()
    except RuntimeError:
        logger.debug("MCP context not initialized")
        return None
    if not hasattr(context, "_pycharm_adapter"):
        context._pycharm_adapter = PyCharmMCPAdapter(  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
            mcp_client=None,
            timeout=30.0,
            max_results=100,
        )
        logger.debug("Created PyCharm MCP adapter singleton")
    return context._pycharm_adapter  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]


def _create_success_response(data: dict[str, t.Any]) -> str:
    return json.dumps({"success": True} | data)


def _create_error_response(message: str, **extra: t.Any) -> str:
    return json.dumps({"success": False, "error": message} | extra)


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


def _local_regex_search(
    pattern: str,
    file_pattern: str | None,
    search_root: Path,
    max_results: int = 100,
) -> list[dict[str, t.Any]]:
    """Walk ``search_root`` and return up to ``max_results`` matches.

    Used as the local fallback when the PyCharm MCP adapter is unavailable
    (no PyCharm IDE running) or returns no results. Cwd-independent: the
    caller passes ``_resolve_local_search_root()`` so the search is scoped
    to the configured project_path, not whatever directory the MCP client
    launched from.
    """
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        logger.warning(f"Invalid regex pattern rejected: {pattern[:50]!r}: {e}")
        return []

    results: list[dict[str, t.Any]] = []
    if file_pattern:
        if file_pattern.startswith("*."):
            extensions = [file_pattern[1:]]
        else:
            extensions = []
            if file_pattern.startswith("."):
                extensions = [file_pattern]
            else:
                extensions = (
                    [f".{file_pattern}"] if "." not in file_pattern else [file_pattern]
                )
    else:
        extensions = [".py"]

    if not search_root.exists():
        logger.debug(f"search_root does not exist: {search_root}")
        return []

    try:
        for file_path in search_root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix not in extensions:
                continue
            try:
                lines = file_path.read_text(
                    encoding="utf-8", errors="ignore"
                ).splitlines()
            except OSError, UnicodeError:
                continue

            for line_no, line_text in enumerate(lines, start=1):
                if compiled.search(line_text):
                    rel_path = file_path
                    try:
                        rel_path = file_path.relative_to(search_root)
                    except ValueError:
                        pass
                    results.append(
                        {
                            "file_path": str(rel_path),
                            "line": line_no,
                            "column": 0,
                            "match": line_text.strip()[:200],
                            "context_before": None,
                            "context_after": None,
                        }
                    )
                    if len(results) >= max_results:
                        return results
    except Exception as e:
        logger.debug(f"Local regex search failed: {e}")
        return results

    return results


def _register_search_code_tool(mcp_app: t.Any) -> None:

    @mcp_app.tool()
    async def search_code(
        pattern: str,
        file_pattern: str | None = None,
    ) -> str:
        adapter = _get_adapter()

        results: list = []
        adapter_used: bool = False
        adapter_error: str | None = None

        if adapter is not None:
            try:
                results = await adapter.search_regex(pattern, file_pattern)
                adapter_used = True
            except Exception as e:
                logger.error(f"Code search via adapter failed: {e}")
                adapter_error = str(e)

        if not results:
            try:
                search_root = _resolve_local_search_root()
                local = _local_regex_search(pattern, file_pattern, search_root)
                if local:
                    results = local
            except Exception as e:
                logger.debug(f"Local search fallback failed: {e}")

        formatted_results = [
            {
                "file_path": r["file_path"] if isinstance(r, dict) else r.file_path,
                "line": r["line"] if isinstance(r, dict) else r.line_number,
                "column": r["column"] if isinstance(r, dict) else r.column,
                "match": r["match"] if isinstance(r, dict) else r.match_text,
                "context_before": r["context_before"] if isinstance(r, dict) else r.context_before,
                "context_after": r["context_after"] if isinstance(r, dict) else r.context_after,
            }
            for r in results
        ]

        if formatted_results:
            status = "ok"
        else:
            status = "degraded"
        payload: dict[str, t.Any] = {
            "results": formatted_results,
            "count": len(formatted_results),
            "pattern": pattern,
            "file_pattern": file_pattern,
            "status": status,
            "source": "pycharm_adapter" if adapter_used else "local_fallback",
        }
        if adapter_error:
            payload["adapter_error"] = adapter_error
        if status == "degraded":
            payload["hint"] = (
                "No matches found via PyCharm MCP and the local fallback. "
                "Ensure PyCharm is running with the MCP server enabled, or "
                "verify the search root contains files matching pattern."
            )
        return _create_success_response(payload)


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
