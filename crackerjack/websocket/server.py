from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from mcp_common.websocket import (
    EventTypes,
    MessageType,
    WebSocketMessage,
    WebSocketProtocol,
    WebSocketServer,
)

from crackerjack.websocket.auth import get_authenticator

logger = logging.getLogger(__name__)


class CrackerjackWebSocketServer(WebSocketServer):
    def __init__(
        self,
        qc_manager: Any,
        host: str = "127.0.0.1",
        port: int = 8686,
        max_connections: int = 1000,
        message_rate_limit: int = 100,
        require_auth: bool = False,
        ssl_context: Any = None,
        cert_file: str | None = None,
        key_file: str | None = None,
        ca_file: str | None = None,
        tls_enabled: bool = False,
        verify_client: bool = False,
        auto_cert: bool = False,
        enable_metrics: bool = False,
        metrics_port: int = 9091,
    ):
        authenticator = get_authenticator()

        super().__init__(
            host=host,
            port=port,
            max_connections=max_connections,
            message_rate_limit=message_rate_limit,
            authenticator=authenticator,
            require_auth=require_auth,
            ssl_context=ssl_context,
            cert_file=cert_file,
            key_file=key_file,
            ca_file=ca_file,
            tls_enabled=tls_enabled,
            verify_client=verify_client,
            auto_cert=auto_cert,
            server_name="crackerjack",
            enable_metrics=enable_metrics,
            metrics_port=metrics_port,
        )

        self.qc_manager = qc_manager

        tls_mode = "WSS" if tls_enabled or ssl_context else "WS"
        logger.info(
            f"CrackerjackWebSocketServer initialized: {host}:{port} ({tls_mode})"
        )

    async def on_connect(self, websocket: Any, connection_id: str) -> None:
        user = getattr(websocket, "user", None)
        user_id = user.get("user_id") if user else "anonymous"

        tls_mode = "WSS" if self.ssl_context else "WS"
        logger.info(
            f"Client connected: {connection_id} (user: {user_id}, mode: {tls_mode})"
        )

        welcome = WebSocketProtocol.create_event(
            EventTypes.SESSION_CREATED,
            {
                "connection_id": connection_id,
                "server": "crackerjack",
                "message": "Connected to Crackerjack quality monitoring",
                "authenticated": user is not None,
                "tls_mode": tls_mode,
            },
        )
        await websocket.send(WebSocketProtocol.encode(welcome))

    async def on_disconnect(self, websocket: Any, connection_id: str) -> None:
        logger.info(f"Client disconnected: {connection_id}")

        await self.leave_all_rooms(connection_id)

    async def on_message(self, websocket: Any, message: WebSocketMessage) -> None:
        if message.type == MessageType.REQUEST:
            await self._handle_request(websocket, message)
        elif message.type == MessageType.EVENT:
            await self._handle_event(websocket, message)
        else:
            logger.warning(f"Unhandled message type: {message.type}")

    async def _handle_request(self, websocket: Any, message: WebSocketMessage) -> None:

        user = getattr(websocket, "user", None)

        if message.event == "subscribe":
            channel = message.data.get("channel")

            if user and not self._can_subscribe_to_channel(user, channel):
                error = WebSocketProtocol.create_error(
                    error_code="FORBIDDEN",
                    error_message=f"Not authorized to subscribe to {channel}",
                    correlation_id=message.correlation_id,
                )
                await websocket.send(WebSocketProtocol.encode(error))
                return

            if channel:
                connection_id = getattr(websocket, "id", str(uuid.uuid4()))
                await self.join_room(channel, connection_id)

                response = WebSocketProtocol.create_response(
                    message, {"status": "subscribed", "channel": channel}
                )
                await websocket.send(WebSocketProtocol.encode(response))

        elif message.event == "unsubscribe":
            channel = message.data.get("channel")
            if channel:
                connection_id = getattr(websocket, "id", str(uuid.uuid4()))
                await self.leave_room(channel, connection_id)

                response = WebSocketProtocol.create_response(
                    message, {"status": "unsubscribed", "channel": channel}
                )
                await websocket.send(WebSocketProtocol.encode(response))

        elif message.event == "get_test_status":
            run_id = message.data.get("run_id")
            if run_id:
                status = await self._get_test_status(run_id)
                response = WebSocketProtocol.create_response(message, status)
                await websocket.send(WebSocketProtocol.encode(response))

        elif message.event == "get_quality_gate":
            project = message.data.get("project")
            if project:
                status = await self._get_quality_gate_status(project)
                response = WebSocketProtocol.create_response(message, status)
                await websocket.send(WebSocketProtocol.encode(response))

        else:
            error = WebSocketProtocol.create_error(
                error_code="UNKNOWN_REQUEST",
                error_message=f"Unknown request event: {message.event}",
                correlation_id=message.correlation_id,
            )
            await websocket.send(WebSocketProtocol.encode(error))

    async def _handle_event(self, websocket: Any, message: WebSocketMessage) -> None:

        logger.debug(f"Received client event: {message.event}")

    def _can_subscribe_to_channel(self, user: dict[str, Any], channel: str) -> bool:
        permissions = user.get("permissions", [])

        if "admin" in permissions:
            return True

        if channel.startswith("quality:"):
            return (
                "crackerjack:read" in permissions
                or "crackerjack:admin" in permissions
            )

        if channel.startswith("test:"):
            return (
                "crackerjack:read" in permissions
                or "crackerjack:admin" in permissions
            )

        return False

    async def _get_test_status(self, run_id: str) -> dict:
        try:
            return {
                "run_id": run_id,
                "status": "running",
                "tests_completed": 0,
                "tests_total": 100,
                "failures": 0,
            }
        except Exception as e:
            logger.error(f"Error getting test status: {e}")
            return {"run_id": run_id, "error": str(e)}

    async def _get_quality_gate_status(self, project: str) -> dict:
        try:
            return {
                "project": project,
                "status": "passed",
                "gates": [],
            }
        except Exception as e:
            logger.error(f"Error getting quality gate status: {e}")
            return {"project": project, "error": str(e)}

    async def broadcast_test_started(
        self, run_id: str, test_suite: str, total_tests: int
    ) -> None:
        event = WebSocketProtocol.create_event(
            EventTypes.TEST_STARTED,
            {
                "run_id": run_id,
                "test_suite": test_suite,
                "total_tests": total_tests,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            room=f"test:{run_id}",
        )
        await self.broadcast_to_room(f"test:{run_id}", event)

    async def broadcast_test_completed(
        self,
        run_id: str,
        tests_completed: int,
        tests_failed: int,
        duration_seconds: float,
    ) -> None:
        event = WebSocketProtocol.create_event(
            EventTypes.TEST_COMPLETED,
            {
                "run_id": run_id,
                "tests_completed": tests_completed,
                "tests_failed": tests_failed,
                "duration_seconds": duration_seconds,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            room=f"test:{run_id}",
        )
        await self.broadcast_to_room(f"test:{run_id}", event)

    async def broadcast_test_failed(
        self, run_id: str, test_name: str, error: str, traceback: str
    ) -> None:
        event = WebSocketProtocol.create_event(
            EventTypes.TEST_FAILED,
            {
                "run_id": run_id,
                "test_name": test_name,
                "error": error,
                "traceback": traceback,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            room=f"test:{run_id}",
        )
        await self.broadcast_to_room(f"test:{run_id}", event)

    async def broadcast_quality_gate_checked(
        self,
        project: str,
        gate_name: str,
        status: str,
        score: float,
        threshold: float,
    ) -> None:
        event = WebSocketProtocol.create_event(
            EventTypes.QUALITY_GATE_CHECKED,
            {
                "project": project,
                "gate_name": gate_name,
                "status": status,
                "score": score,
                "threshold": threshold,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            room=f"quality:{project}",
        )
        await self.broadcast_to_room(f"quality:{project}", event)

    async def broadcast_coverage_updated(
        self,
        project: str,
        line_coverage: float,
        branch_coverage: float,
        path_coverage: float,
    ) -> None:
        event = WebSocketProtocol.create_event(
            EventTypes.COVERAGE_UPDATED,
            {
                "project": project,
                "line_coverage": line_coverage,
                "branch_coverage": branch_coverage,
                "path_coverage": path_coverage,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            room=f"quality:{project}",
        )
        await self.broadcast_to_room(f"quality:{project}", event)
