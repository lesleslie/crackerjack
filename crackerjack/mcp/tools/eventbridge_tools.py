from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any

from crackerjack.core.eventbridge_publisher import (
    publish_test_completed,
    publish_test_failed,
    publish_test_started,
)

if TYPE_CHECKING:
    from mcp_common.fastmcp import FastMCP

logger = logging.getLogger(__name__)

_publisher: Any | None = None


def set_eventbridge_publisher(publisher: Any | None) -> None:
    global _publisher
    _publisher = publisher


async def _dispatch_topic(topic: str, payload: dict[str, Any]) -> None:
    if topic == "test.started":
        await publish_test_started(
            run_id=payload["run_id"],
            test_suite=payload["test_suite"],
            total_tests=payload["total_tests"],
            publisher=_publisher,
        )
    elif topic == "test.completed":
        await publish_test_completed(
            run_id=payload["run_id"],
            tests_completed=payload["tests_completed"],
            tests_failed=payload["tests_failed"],
            duration_seconds=payload["duration_seconds"],
            publisher=_publisher,
        )
    elif topic == "test.failed":
        await publish_test_failed(
            run_id=payload["run_id"],
            test_name=payload["test_name"],
            error=payload["error"],
            traceback=payload["traceback"],
            publisher=_publisher,
        )
    else:
        logger.warning(
            "crackerjack.eventbridge_tools: unknown topic=%s; ignoring", topic
        )


def register_eventbridge_tools(
    mcp_app: FastMCP,
    publisher: Any | None = None,
    enabled: bool = False,
) -> None:
    if not enabled:
        return

    if publisher is not None:
        set_eventbridge_publisher(publisher)

    @mcp_app.tool()
    async def publish_to_eventbridge(
        topic: str,
        payload: dict[str, Any],
        async_callback: bool = False,
    ) -> dict[str, Any]:
        if _publisher is None:
            return {
                "status": "no_publisher",
                "warning": (
                    "eventbridge enabled but publisher not wired; "
                    "no envelope will be emitted"
                ),
            }

        if async_callback:
            workflow_id = f"pub_{uuid.uuid4().hex[:12]}"
            asyncio.create_task(_dispatch_topic(topic, payload))
            return {"workflow_id": workflow_id, "status": "queued"}

        await _dispatch_topic(topic, payload)
        return {"status": "published"}


__all__ = ["register_eventbridge_tools", "set_eventbridge_publisher"]
