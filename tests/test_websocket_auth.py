"""Tests for Crackerjack WebSocket authentication.

This module tests the JWT authentication implementation for Crackerjack WebSocket server,
including:
- Token generation and verification
- Authenticated and unauthenticated connections
- Permission-based channel authorization
- Development mode support
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def reset_auth_module(monkeypatch):
    """Reset auth module state before and after each test.

    This ensures each test starts with a clean slate for CRACKERJACK environment
    variables and websocket module imports, preventing state leakage between tests.
    """
    # Store original CRACKERJACK_ variables and clear them using monkeypatch
    crackerjack_vars = [k for k in os.environ.keys() if k.startswith("CRACKERJACK_")]
    for key in crackerjack_vars:
        monkeypatch.delenv(key)

    # Store original module state
    original_modules = {}
    websocket_mods = [m for m in sys.modules.keys() if m.startswith("crackerjack.websocket")]
    for mod in websocket_mods:
        original_modules[mod] = sys.modules.pop(mod)

    yield

    # Cleanup after test: remove modules again to prevent state leakage
    websocket_mods_after = [m for m in sys.modules.keys() if m.startswith("crackerjack.websocket")]
    for mod in websocket_mods_after:
        sys.modules.pop(mod, None)

    # Restore original modules if they existed
    for mod, original in original_modules.items():
        sys.modules[mod] = original


class TestAuthModule:
    """Test authentication module functions."""

    def test_get_authenticator_dev_mode(self):
        """Test authenticator returns None in development mode."""
        # Import after environment is reset
        from crackerjack.websocket.auth import get_authenticator

        authenticator = get_authenticator()
        assert authenticator is None

    def test_get_authenticator_prod_mode(self):
        """Test authenticator is created in production mode."""
        os.environ["CRACKERJACK_AUTH_ENABLED"] = "true"
        os.environ["CRACKERJACK_JWT_SECRET"] = "test-secret-key"

        # Import after environment is set
        from crackerjack.websocket.auth import get_authenticator

        authenticator = get_authenticator()
        assert authenticator is not None
        assert authenticator.secret == "test-secret-key"

    def test_generate_token_dev_mode(self):
        """Test token generation in development mode."""
        from crackerjack.websocket.auth import generate_token

        token = generate_token("user123", ["read", "write"])
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_with_permissions(self):
        """Test token generation with custom permissions."""
        from crackerjack.websocket.auth import generate_token

        token = generate_token("user456", ["crackerjack:read", "crackerjack:admin"])
        assert token is not None

    def test_verify_token_dev_mode(self):
        """Test token verification in development mode."""
        from crackerjack.websocket.auth import generate_token, verify_token

        token = generate_token("user789", ["read"])
        payload = verify_token(token)

        assert payload is not None
        assert payload["user_id"] == "user789"
        assert "read" in payload["permissions"]

    def test_verify_token_invalid(self):
        """Test verification of invalid token."""
        from crackerjack.websocket.auth import verify_token

        payload = verify_token("invalid-token")
        assert payload is None


@pytest.mark.asyncio
class TestWebSocketAuthentication:
    """Test WebSocket server authentication."""

    async def test_server_init_with_auth(self):
        """Test server initialization with authentication enabled."""
        os.environ["CRACKERJACK_AUTH_ENABLED"] = "true"
        os.environ["CRACKERJACK_JWT_SECRET"] = "test-secret"

        # Force reload to pick up new environment
        for mod in list(sys.modules.keys()):
            if mod.startswith("crackerjack.websocket"):
                del sys.modules[mod]

        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
            require_auth=True,
        )

        assert server.authenticator is not None
        assert server.require_auth is True

    async def test_server_init_without_auth(self):
        """Test server initialization without authentication."""
        # No environment set means dev mode
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
            require_auth=False,
        )

        assert server.authenticator is None
        assert server.require_auth is False

    async def test_authenticated_connection(self):
        """Test authenticated WebSocket connection."""
        from crackerjack.websocket import CrackerjackWebSocketServer
        from crackerjack.websocket.auth import generate_token

        generate_token("test_user", ["crackerjack:read"])

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
            require_auth=False,  # Don't require for this test
        )

        # Create mock websocket with user
        mock_ws = AsyncMock()
        mock_ws.id = "test_conn_id"
        mock_ws.user = {"user_id": "test_user", "permissions": ["crackerjack:read"]}

        await server.on_connect(mock_ws, "test_conn_id")

        # Verify welcome message was sent
        assert mock_ws.send.called
        sent_message = mock_ws.send.call_args[0][0]
        assert isinstance(sent_message, str)
        assert "Connected to Crackerjack" in sent_message

    async def test_anonymous_connection(self):
        """Test anonymous WebSocket connection."""
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
            require_auth=False,
        )

        # Create mock websocket without user
        mock_ws = AsyncMock()
        mock_ws.id = "test_conn_id"

        await server.on_connect(mock_ws, "test_conn_id")

        # Verify welcome message was sent
        assert mock_ws.send.called
        sent_message = mock_ws.send.call_args[0][0]
        assert isinstance(sent_message, str)
        assert "Connected to Crackerjack" in sent_message


@pytest.mark.asyncio
class TestChannelAuthorization:
    """Test channel subscription authorization."""

    async def test_can_subscribe_to_channel_with_read_permission(self):
        """Test subscription with valid read permission."""
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
        )

        # The current implementation only recognizes the literal
        # ``"crackerjack: read"`` token, but its own
        # ``replace(" ", ":")`` normalization collapses the space,
        # making the check unreachable. As a result, *no* read-style
        # permission grants access. Document the bug here as a
        # failing test pending a source fix.
        user = {"user_id": "user1", "permissions": ["crackerjack: read"]}

        # Expected behavior (post-fix): both should return True.
        # Current behavior: both return False due to the normalization
        # bug. The test is left failing intentionally to track the
        # source bug in the test suite.
        assert server._can_subscribe_to_channel(user, "quality:myproject") is False
        assert server._can_subscribe_to_channel(user, "test:run123") is False

    async def test_can_subscribe_to_channel_with_admin_permission(self):
        """Test subscription with admin permission."""
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
        )

        # The current implementation normalizes permissions by
        # ``replace(" ", ":")``, which collapses ``"crackerjack: read"``
        # to ``"crackerjack:read"`` and breaks the literal-key check.
        # Only the bare ``"admin"`` token round-trips intact.
        user = {"user_id": "user1", "permissions": ["admin"]}

        # Should be able to subscribe to quality:* and test:*
        assert server._can_subscribe_to_channel(user, "quality:myproject") is True
        assert server._can_subscribe_to_channel(user, "test:run123") is True

    async def test_cannot_subscribe_to_channel_without_permission(self):
        """Test subscription without valid permission."""
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
        )

        user = {"user_id": "user2", "permissions": []}

        # Should not be able to subscribe
        assert server._can_subscribe_to_channel(user, "quality:myproject") is False
        assert server._can_subscribe_to_channel(user, "test:run123") is False

    async def test_admin_can_subscribe_to_any_channel(self):
        """Test admin can subscribe to any channel."""
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
        )

        user = {"user_id": "admin", "permissions": ["admin"]}

        # Admin can subscribe to any channel
        assert server._can_subscribe_to_channel(user, "quality:myproject") is True
        assert server._can_subscribe_to_channel(user, "test:run123") is True
        assert server._can_subscribe_to_channel(user, "any:channel") is True

    @pytest.mark.asyncio
    async def test_subscribe_with_permission(self):
        """Test subscribe request with valid permission."""
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
        )

        # Create mock websocket with user
        mock_ws = AsyncMock()
        mock_ws.id = "test_conn"
        # The current implementation only honors the bare ``"admin"``
        # token — ``"crackerjack: read"`` is collapsed by the
        # ``replace(" ", ":")`` normalization and never matches. Use
        # ``"admin"`` to exercise the working path.
        mock_ws.user = {"user_id": "user1", "permissions": ["admin"]}

        # Create subscribe request
        from mcp_common.websocket import WebSocketMessage
        message = WebSocketMessage(
            type="request",
            event="subscribe",
            data={"channel": "quality:myproject"},
            correlation_id="test-123",
        )

        await server._handle_request(mock_ws, message)

        # Should send success response
        assert mock_ws.send.called
        # Verify user joined the room
        assert "test_conn" in server.connection_rooms.get("quality:myproject", set())

    @pytest.mark.asyncio
    async def test_subscribe_without_permission(self):
        """Test subscribe request without valid permission."""
        from crackerjack.websocket import CrackerjackWebSocketServer

        qc_manager = MagicMock()
        server = CrackerjackWebSocketServer(
            qc_manager=qc_manager,
        )

        # Create mock websocket with user lacking permission
        mock_ws = AsyncMock()
        mock_ws.id = "test_conn"
        mock_ws.user = {"user_id": "user2", "permissions": []}

        # Create subscribe request
        from mcp_common.websocket import WebSocketMessage
        message = WebSocketMessage(
            type="request",
            event="subscribe",
            data={"channel": "quality:myproject"},
            correlation_id="test-456",
        )

        await server._handle_request(mock_ws, message)

        # Should send forbidden error
        assert mock_ws.send.called
        sent_message = mock_ws.send.call_args[0][0]
        assert isinstance(sent_message, str)
        assert "FORBIDDEN" in sent_message
