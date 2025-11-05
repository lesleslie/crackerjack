"""Workflow event bus built on top of ACB event primitives.

Provides a lightweight in-process event bus that uses ``acb.events`` data
structures so the rest of the codebase can adopt the forthcoming ACB EventBus
without waiting on external messaging infrastructure. Subscribers register
handlers for workflow event types and publishers emit events that are dispatched
asynchronously.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import typing as t
from dataclasses import dataclass, field
from enum import Enum

from acb.events import (
    Event,
    EventHandlerResult,
    FunctionalEventHandler,
    create_event,
)
from acb.events._base import EventSubscription

logger = logging.getLogger(__name__)

HandlerCallable = t.Callable[
    [Event], t.Awaitable[EventHandlerResult] | EventHandlerResult
]


class WorkflowEvent(str, Enum):
    """Standard workflow events emitted inside Crackerjack."""

    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_SESSION_INITIALIZING = "workflow.session.initializing"
    WORKFLOW_SESSION_READY = "workflow.session.ready"
    CONFIG_PHASE_STARTED = "workflow.config.started"
    CONFIG_PHASE_COMPLETED = "workflow.config.completed"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_INTERRUPTED = "workflow.interrupted"

    QUALITY_PHASE_STARTED = "workflow.quality.started"
    QUALITY_PHASE_COMPLETED = "workflow.quality.completed"

    PUBLISH_PHASE_STARTED = "workflow.publish.started"
    PUBLISH_PHASE_COMPLETED = "workflow.publish.completed"

    COMMIT_PHASE_STARTED = "workflow.commit.started"
    COMMIT_PHASE_COMPLETED = "workflow.commit.completed"

    HOOK_STRATEGY_STARTED = "hooks.strategy.started"
    HOOK_STRATEGY_COMPLETED = "hooks.strategy.completed"
    HOOK_STRATEGY_FAILED = "hooks.strategy.failed"

    HOOK_EXECUTION_STARTED = "hooks.execution.started"
    HOOK_EXECUTION_COMPLETED = "hooks.execution.completed"
    HOOK_EXECUTION_FAILED = "hooks.execution.failed"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


@dataclass
class WorkflowEventDispatchResult:
    """Result returned from publishing an event."""

    event: Event
    results: list[EventHandlerResult] = field(default_factory=list)


@dataclass
class _SubscriptionEntry:
    """Internal representation of a subscription with concurrency control."""

    subscription: EventSubscription
    description: str | None = None
    semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(1))
    max_retries: int = 0
    retry_backoff: float = 0.5

    def __post_init__(self) -> None:
        max_concurrent = self.subscription.max_concurrent or 1
        self.semaphore = asyncio.Semaphore(max_concurrent)


class WorkflowEventBus:
    """In-process event bus compatible with ACB event handlers."""

    def __init__(self) -> None:
        self._subscriptions: dict[str | None, dict[str, _SubscriptionEntry]] = {}
        self._lock = threading.RLock()
        self._default_handlers_registered = False

    def subscribe(
        self,
        event_type: WorkflowEvent | str | None,
        handler: HandlerCallable,
        *,
        predicate: t.Callable[[Event], bool] | None = None,
        max_concurrent: int | None = None,
        description: str | None = None,
        max_retries: int = 0,
        retry_backoff: float = 0.5,
    ) -> str:
        """Register a handler for an event type.

        Args:
            event_type: WorkflowEvent enum value, string, or ``None`` for wildcard.
            handler: Callable invoked when the event is published.
            predicate: Optional additional filter predicate.
            max_concurrent: Maximum concurrent invocations for this handler.
            description: Optional human readable identifier.
            max_retries: Number of retry attempts when a handler raises.
            retry_backoff: Initial backoff delay (seconds) between retries; doubles each attempt.

        Returns:
            Subscription ID string.
        """
        event_type_value = (
            event_type.value if isinstance(event_type, WorkflowEvent) else event_type
        )

        event_handler = FunctionalEventHandler(
            handler,
            event_type=event_type_value,
            predicate=predicate,
        )
        subscription = EventSubscription(
            handler=event_handler,
            event_type=event_type_value,
            predicate=predicate,
            max_concurrent=max_concurrent or 1,
        )
        entry = _SubscriptionEntry(
            subscription=subscription,
            description=description,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )

        key = event_type_value

        with self._lock:
            bucket = self._subscriptions.setdefault(key, {})
            bucket[str(subscription.subscription_id)] = entry

        logger.debug(
            "Registered workflow event subscription",
            extra={
                "event_type": event_type_value or "*",
                "subscription_id": str(subscription.subscription_id),
                "description": description,
                "max_concurrent": max_concurrent or 1,
                "max_retries": max_retries,
                "retry_backoff": retry_backoff,
            },
        )

        return str(subscription.subscription_id)

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription by ID."""
        with self._lock:
            for bucket in self._subscriptions.values():
                if subscription_id in bucket:
                    del bucket[subscription_id]
                    logger.debug(
                        "Removed workflow event subscription",
                        extra={"subscription_id": subscription_id},
                    )
                    return True
        return False

    def list_subscriptions(self) -> list[dict[str, t.Any]]:
        """Return summary information for registered subscriptions."""
        data: list[dict[str, t.Any]] = []
        with self._lock:
            for event_type, bucket in self._subscriptions.items():
                for subscription_id, entry in bucket.items():
                    data.append(
                        {
                            "subscription_id": subscription_id,
                            "event_type": event_type or "*",
                            "description": entry.description,
                            "max_concurrent": entry.subscription.max_concurrent,
                        }
                    )
        return data

    async def publish(
        self,
        event_type: WorkflowEvent | str,
        payload: dict[str, t.Any] | None = None,
        *,
        source: str = "crackerjack.workflow",
        **metadata: t.Any,
    ) -> WorkflowEventDispatchResult:
        """Publish an event to subscribed handlers."""
        event_type_value = (
            event_type.value if isinstance(event_type, WorkflowEvent) else event_type
        )
        payload = payload or {}
        event = create_event(event_type_value, source, payload, **metadata)

        entries = self._collect_subscriptions(event)
        if not entries:
            logger.debug(
                "Workflow event published with no subscribers",
                extra={"event_type": event_type_value},
            )
            return WorkflowEventDispatchResult(event=event, results=[])

        tasks = [self._invoke_subscription(entry, event) for entry in entries]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[EventHandlerResult] = []
        for entry, result in zip(entries, raw_results, strict=False):
            if isinstance(result, EventHandlerResult):
                results.append(result)
                continue

            if isinstance(result, Exception):
                logger.exception(
                    "Workflow event handler raised an exception",
                    extra={
                        "event_type": event_type_value,
                        "subscription_id": entry.subscription.subscription_id,
                        "description": entry.description,
                    },
                    exc_info=result,
                )
                results.append(
                    EventHandlerResult(
                        success=False,
                        error_message=str(result),
                        metadata={
                            "subscription_id": str(entry.subscription.subscription_id)
                        },
                    )
                )
                continue

            # Allow handlers to return truthy values instead of EventHandlerResult
            success = True if result is None else bool(result)
            results.append(
                EventHandlerResult(
                    success=success,
                    metadata={
                        "subscription_id": str(entry.subscription.subscription_id)
                    },
                )
            )

        return WorkflowEventDispatchResult(event=event, results=results)

    def register_logging_handler(self) -> None:
        """Install a default debug logging handler (idempotent)."""
        if self._default_handlers_registered:
            return

        async def _log_event(event: Event) -> EventHandlerResult:
            logger.debug(
                "Workflow event dispatched",
                extra={
                    "event_type": event.metadata.event_type,
                    "source": event.metadata.source,
                    "payload": event.payload,
                },
            )
            return EventHandlerResult(success=True)

        self.subscribe(
            event_type=None,
            handler=_log_event,
            description="workflow.logging",
        )
        self._default_handlers_registered = True

    def _collect_subscriptions(self, event: Event) -> list[_SubscriptionEntry]:
        with self._lock:
            specific = list(
                self._subscriptions.get(event.metadata.event_type, {}).values()
            )
            wildcard = list(self._subscriptions.get(None, {}).values())
        return specific + wildcard

    async def _invoke_subscription(
        self,
        entry: _SubscriptionEntry,
        event: Event,
    ) -> EventHandlerResult:
        handler = entry.subscription.handler
        if not handler.can_handle(event):
            return EventHandlerResult(
                success=True,
                metadata={
                    "subscription_id": str(entry.subscription.subscription_id),
                    "skipped": True,
                },
            )

        async with entry.semaphore:
            attempt = 0
            delay = max(entry.retry_backoff, 0.0)
            while True:
                try:
                    return await handler.handle(event)
                except Exception as exc:
                    attempt += 1
                    if attempt > entry.max_retries:
                        logger.exception(
                            "Workflow event handler failed after retries",
                            extra={
                                "subscription_id": str(
                                    entry.subscription.subscription_id
                                ),
                                "description": entry.description,
                                "event_type": event.metadata.event_type,
                                "attempts": attempt,
                            },
                            exc_info=exc,
                        )
                        raise

                    logger.warning(
                        "Workflow event handler raised; retrying",
                        extra={
                            "subscription_id": str(entry.subscription.subscription_id),
                            "description": entry.description,
                            "event_type": event.metadata.event_type,
                            "attempt": attempt,
                            "max_retries": entry.max_retries,
                            "retry_delay": delay,
                        },
                        exc_info=exc,
                    )
                    if delay > 0:
                        await asyncio.sleep(delay)
                        delay *= 2


__all__ = ["WorkflowEventBus", "WorkflowEvent", "WorkflowEventDispatchResult"]
