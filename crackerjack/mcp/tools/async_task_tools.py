"""Result-store MCP tools for AsyncTaskManager (C-WIRE Task 6).

Exposes ``crackerjack_result_store``: a read-only MCP tool that looks up
a persisted async task record by id. The tool delegates to
``AsyncTaskManager.get_task``, which is backed by the SQLite
``AsyncTaskStore``.
"""

from __future__ import annotations

import json
import logging
import typing as t

from crackerjack.mcp.task_manager import AsyncTaskManager

logger = logging.getLogger(__name__)


# Module-level singleton: ``create_mcp_server`` constructs the live
# ``AsyncTaskManager`` and stashes it here before tool registration.
# The closure inside ``register_async_task_tools`` reads from this holder,
# sidestepping mcp_common's ``_apply_tool_profile`` signature
# restriction (``register_fn(server)`` — no kwargs).
_task_manager: AsyncTaskManager | None = None


def set_task_manager(manager: AsyncTaskManager | None) -> None:
    """Inject the live ``AsyncTaskManager`` (called once at server startup).

    Pass ``None`` to clear (used by tests that don't wire a manager).
    """
    global _task_manager
    _task_manager = manager


def get_task_manager() -> AsyncTaskManager | None:
    """Read-only accessor for the current ``AsyncTaskManager``."""
    return _task_manager


def register_async_task_tools(mcp_app: t.Any) -> None:
    """Register the async-task MCP tool group on ``mcp_app``.

    Currently exposes one tool: ``crackerjack_result_store``.
    """

    @mcp_app.tool(name="crackerjack_result_store")  # type: ignore[misc]
    async def result_store(task_id: str) -> str:
        """Look up a persisted async task record by id.

        Returns a JSON envelope:
            {"found": true, "task": {...}} on hit
            {"found": false, "task_id": "..."} on miss
        """
        manager = get_task_manager()
        record = await manager.get_task(task_id) if manager is not None else None
        if record is None:
            logger.info(
                "crackerjack_async_task_result_query task_id=%s found=false",
                task_id,
            )
            return json.dumps({"found": False, "task_id": task_id})
        payload = {
            "task_id": record.task_id,
            "status": record.status,
            "registered_at": record.registered_at.isoformat(),
            "metadata": record.metadata,
        }
        logger.info(
            "crackerjack_async_task_result_query task_id=%s found=true status=%s",
            task_id,
            record.status,
        )
        return json.dumps({"found": True, "task": payload})


__all__ = [
    "get_task_manager",
    "register_async_task_tools",
    "set_task_manager",
]
