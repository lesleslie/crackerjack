"""WebSocket bridge for routing WorkflowEventBus events to connected clients.

This module provides the EventBusWebSocketBridge class that connects the
WorkflowEventBus to WebSocket clients, enabling real-time workflow progress
updates without polling.

Phase 7.3: WebSocket Streaming for Real-Time Updates
"""

from __future__ import annotations

import typing as t
from collections import defaultdict

from acb.depends import Inject, depends

from crackerjack.events.workflow_bus import WorkflowEvent, WorkflowEventBus

if t.TYPE_CHECKING:
    from acb.actions.events import Event
    from fastapi import WebSocket


@depends.inject
class EventBusWebSocketBridge:
    """Bridges workflow events to WebSocket clients for real-time updates.

    This class subscribes to all WorkflowEvent types from the WorkflowEventBus
    and routes them to appropriate WebSocket clients based on job_id.

    Architecture:
        WorkflowActions → WorkflowEventBus → EventBusWebSocketBridge → WebSocket Clients

    Usage:
        bridge = EventBusWebSocketBridge(event_bus)
        await bridge.register_client(job_id, websocket)
        # Events automatically routed to client
        await bridge.unregister_client(job_id, websocket)
    """

    def __init__(
        self,
        event_bus: Inject[WorkflowEventBus] = None,
    ) -> None:
        """Initialize event bridge with WorkflowEventBus.

        Args:
            event_bus: WorkflowEventBus instance (injected via DI)
        """
        self._event_bus = event_bus
        self._clients: dict[str, list[WebSocket]] = defaultdict(list)
        self._subscription_ids: list[str] = []

        # Subscribe to all workflow events
        if self._event_bus:
            self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """Subscribe to all WorkflowEvent types for event routing."""
        for event_type in WorkflowEvent:
            subscription_id = self._event_bus.subscribe(
                event_type,
                self._handle_workflow_event,
            )
            self._subscription_ids.append(subscription_id)

    async def _handle_workflow_event(self, event: Event) -> None:
        """Handle workflow event and route to appropriate clients.

        Args:
            event: ACB Event object with workflow event data
        """
        # Extract job_id from event payload
        # Events include step_id in format "action_name_timestamp" or "workflow_id"
        payload = event.payload
        step_id = payload.get("step_id", "")

        if not step_id:
            # No step_id in payload, skip routing
            return

        # For now, broadcast to all connected clients
        # In future, could parse step_id to extract workflow_id/job_id for filtering
        all_clients: list[WebSocket] = []
        for clients in self._clients.values():
            all_clients.extend(clients)

        if not all_clients:
            # No clients connected
            return

        # Transform event to WebSocket message format
        message = self._transform_event_to_message(event)

        # Send to all clients
        await self._broadcast_to_clients(all_clients, message)

    def _transform_event_to_message(self, event: Event) -> dict[str, t.Any]:
        """Transform ACB Event to WebSocket message format.

        Args:
            event: ACB Event object

        Returns:
            dict with event_type, data, and timestamp
        """
        return {
            "event_type": event.event_type.value
            if hasattr(event.event_type, "value")
            else str(event.event_type),
            "data": event.payload,
            "timestamp": event.payload.get("timestamp"),
        }

    async def _broadcast_to_clients(
        self,
        clients: list[WebSocket],
        message: dict[str, t.Any],
    ) -> None:
        """Broadcast message to all clients, removing disconnected ones.

        Args:
            clients: List of WebSocket clients to send to
            message: Message data to send
        """
        disconnected: list[WebSocket] = []

        for websocket in clients:
            try:
                await websocket.send_json(message)
            except Exception:
                # Client disconnected, mark for removal
                disconnected.append(websocket)

        # Remove disconnected clients
        for websocket in disconnected:
            clients.remove(websocket)

    async def register_client(self, job_id: str, websocket: WebSocket) -> None:
        """Register WebSocket client for job-specific event updates.

        Args:
            job_id: Job identifier to subscribe to
            websocket: WebSocket connection to send events to
        """
        self._clients[job_id].append(websocket)

    async def unregister_client(self, job_id: str, websocket: WebSocket) -> None:
        """Unregister WebSocket client from event updates.

        Args:
            job_id: Job identifier to unsubscribe from
            websocket: WebSocket connection to remove
        """
        if job_id in self._clients:
            with suppress(ValueError):
                self._clients[job_id].remove(websocket)

            # Clean up empty job client lists
            if not self._clients[job_id]:
                del self._clients[job_id]

    def get_active_connections(self) -> int:
        """Get count of active WebSocket connections.

        Returns:
            Total number of active WebSocket connections across all jobs
        """
        return sum(len(clients) for clients in self._clients.values())

    def get_jobs_with_clients(self) -> list[str]:
        """Get list of job IDs with active clients.

        Returns:
            List of job_id strings that have connected clients
        """
        return [job_id for job_id, clients in self._clients.items() if clients]

    def cleanup(self) -> None:
        """Cleanup event subscriptions and client connections."""
        # Unsubscribe from all events
        if self._event_bus:
            for subscription_id in self._subscription_ids:
                self._event_bus.unsubscribe(subscription_id)

        # Clear client lists
        self._clients.clear()
        self._subscription_ids.clear()
