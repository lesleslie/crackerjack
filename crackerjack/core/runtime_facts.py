"""Runtime facts builder for the FastMCP tool registry (Plan 1 Phase 3).

Mirrors the FastMCP-registered tool shape so the boot push in
:mod:`crackerjack.mcp.oneiric_runtime` can enumerate every tool the
Crackerjack MCP server exposes without re-implementing registry
introspection per call.

Wire contract:

* ``build_all`` returns a structured list with each tool's ``name``,
  ``description``, and ``parameters`` (JSON schema) plus a top-level
  ``count`` and ``capabilities`` summary.
* The Oneiric envelope (``success / registry / runtime / health``) is
  constructed in :func:`crackerjack.mcp.oneiric_runtime.report_runtime_to_oneiric`,
  NOT inside this builder. This keeps the FastMCP-side enumeration
  independent from the Oneiric envelope so the two surfaces can evolve
  separately.

Design rules (mirroring ``mahavishnu.core.runtime_facts``):

* No akosha / session_buddy / oneiric / mahavishnu imports
  (stdlib ``logging`` only).
* Pure introspection; ``build_all`` never ``await``s; never makes
  blocking I/O. The push to Oneiric lives in
  ``oneiric_runtime.report_runtime_to_oneiric`` (separate fire-and-
  forget scope) so boot never blocks on a degraded Oneiric.
* Reads only attributes exposed by the FastMCP ``Tool`` model
  (``name``, ``description``, ``parameters``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP


logger = logging.getLogger(__name__)


class RuntimeFactsBuilder:
    """Enumerate a FastMCP app's registered tools into a structured list.

    The returned dict matches the canonical wire shape consumed by
    :func:`crackerjack.mcp.oneiric_runtime.report_runtime_to_oneiric`.
    The Oneiric envelope is NOT constructed in this builder; it lives
    in the calling report_runtime_to_oneiric path so the two surfaces
    (MCP introspection vs Oneiric push) can evolve independently.

    The builder is intentionally pure-introspection: ``build_all`` does
    not ``await`` anything. Live HTTP probing is out of scope and
    belongs in the calling report_runtime_to_oneiric path (separate
    fire-and-forget scope).
    """

    CATEGORY_UNKNOWN = "unknown"

    def __init__(self, app: FastMCP) -> None:
        self._app = app

    def build_all(self) -> dict[str, Any]:
        """Return the canonical FastMCP-tool-enumeration envelope.

        Returns
        -------
        dict[str, Any]
            ``{"tools": list[{"name", "description", "parameters",
            "category"}], "count": int, "capabilities": {"total":
            int, "by_category": dict[str, int]}}``.
        """
        tools = self._collect_tools()
        tool_entries = [self._build_entry(tool) for tool in tools]
        capabilities = self.get_capabilities_summary(tool_entries)
        return {
            "tools": tool_entries,
            "count": len(tool_entries),
            "capabilities": capabilities,
        }

    def get_capabilities_summary(
        self, tool_entries: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Count tools per inferred category.

        Parameters
        ----------
        tool_entries : list[dict[str, Any]] | None
            Optional pre-built entries; if ``None`` the builder will
            enumerate the FastMCP tool registry on demand.

        Returns
        -------
        dict[str, Any]
            ``{"total": int, "by_category": {<category>: <count>}}``.
        """
        if tool_entries is None:
            tool_entries = [self._build_entry(t) for t in self._collect_tools()]
        by_category: dict[str, int] = {}
        for entry in tool_entries:
            category = entry.get("category", self.CATEGORY_UNKNOWN)
            by_category[category] = by_category.get(category, 0) + 1
        return {
            "total": len(tool_entries),
            "by_category": dict(sorted(by_category.items())),
        }

    def _collect_tools(self) -> list[Any]:
        """Return the registered FastMCP tools as a list.

        Tries the sync ``_tool_manager._tools`` dict first; falls back
        to the public async ``list_tools`` via ``asyncio.run`` only if
        the sync attribute is unavailable (keeps ``build_all`` callable
        from sync contexts without a running event loop).
        """
        tool_manager = getattr(self._app, "_tool_manager", None)
        if tool_manager is not None:
            sync_tools = getattr(tool_manager, "_tools", None)
            if sync_tools is not None:
                return list(sync_tools.values())

        list_tools = getattr(self._app, "list_tools", None)
        if list_tools is None:
            logger.warning("fastmcp_app_has_no_listable_registry")
            return []

        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return self._run_async(list_tools)
        return self._run_async(list_tools)

    @staticmethod
    def _run_async(coro_factory: Any) -> list[Any]:
        """Run an async coroutine factory to completion in a fresh loop.

        Used only as a fallback when the FastMCP app lacks the sync
        ``_tool_manager._tools`` attribute. Never reached on the
        canonical Crackerjack boot path.
        """
        import asyncio

        return list(asyncio.run(coro_factory()))

    def _build_entry(self, tool: Any) -> dict[str, Any]:
        """Translate one FastMCP ``Tool`` into a catalog row.

        Reads only public ``Tool`` attributes (``name``, ``description``,
        ``parameters``). Missing attributes fall back to safe defaults
        so the envelope is always well-formed.
        """
        name = getattr(tool, "name", None) or self.CATEGORY_UNKNOWN
        description = getattr(tool, "description", None) or ""
        parameters = getattr(tool, "parameters", None) or {}
        return {
            "name": name,
            "description": description,
            "parameters": parameters,
            "category": self._infer_category(name),
        }

    @staticmethod
    def _infer_category(tool_name: str) -> str:
        """Infer a category bucket from a tool's registered name.

        FastMCP tool names registered by Crackerjack use a flat
        ``<verb>_<noun>`` shape (e.g. ``crackerjack_run``,
        ``search_code``, ``mcp_health``). The first underscore-split
        token is treated as the category when it is a known prefix;
        otherwise the whole name is bucketed as ``"unknown"``.
        """
        if not tool_name:
            return RuntimeFactsBuilder.CATEGORY_UNKNOWN
        for prefix in (
            "crackerjack",
            "search",
            "health",
            "skill",
            "agent",
            "otel",
            "language",
            "workflow",
            "execution",
            "monitoring",
            "semantic",
            "progress",
            "doc",
            "eventbridge",
            "pycharm",
            "proactive",
            "utility",
            "error",
        ):
            if tool_name == prefix or tool_name.startswith(f"{prefix}_"):
                return prefix
        return RuntimeFactsBuilder.CATEGORY_UNKNOWN
