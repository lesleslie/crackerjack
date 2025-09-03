#!/usr/bin/env python3
"""Serverless session management MCP tools.

This module provides tools for managing serverless sessions with external storage
following crackerjack architecture patterns.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy loading for optional serverless dependencies
_serverless_manager = None
_serverless_available = None


async def _get_serverless_manager():
    """Get serverless manager instance with lazy loading."""
    global _serverless_manager, _serverless_available

    if _serverless_available is False:
        return None

    if _serverless_manager is None:
        try:
            from session_mgmt_mcp.serverless_mode import ServerlessSessionManager

            _serverless_manager = ServerlessSessionManager()
            _serverless_available = True
        except ImportError as e:
            logger.warning(f"Serverless mode not available: {e}")
            _serverless_available = False
            return None

    return _serverless_manager


def _check_serverless_available() -> bool:
    """Check if serverless mode is available."""
    global _serverless_available

    if _serverless_available is None:
        try:
            import importlib.util

            spec = importlib.util.find_spec("session_mgmt_mcp.serverless_mode")
            _serverless_available = spec is not None
        except ImportError:
            _serverless_available = False

    return _serverless_available


def register_serverless_tools(mcp) -> None:
    """Register all serverless session management MCP tools.

    Args:
        mcp: FastMCP server instance

    """

    @mcp.tool()
    async def create_serverless_session(
        user_id: str,
        project_id: str,
        session_data: dict[str, Any] | None = None,
        ttl_hours: int = 24,
    ) -> str:
        """Create a new serverless session with external storage.

        Args:
            user_id: User identifier for the session
            project_id: Project identifier for the session
            session_data: Optional metadata for the session
            ttl_hours: Time-to-live in hours (default: 24)

        """
        if not _check_serverless_available():
            return "❌ Serverless mode not available. Install dependencies: pip install redis boto3"

        try:
            manager = await _get_serverless_manager()
            if not manager:
                return "❌ Failed to initialize serverless manager"

            session_id = await manager.create_session(
                user_id=user_id,
                project_id=project_id,
                session_data=session_data,
                ttl_hours=ttl_hours,
            )

            return f"✅ Created serverless session: {session_id}\n🕐 TTL: {ttl_hours} hours"

        except Exception as e:
            logger.exception("Error creating serverless session", error=str(e))
            return f"❌ Error creating session: {e}"

    @mcp.tool()
    async def get_serverless_session(session_id: str) -> str:
        """Get serverless session state.

        Args:
            session_id: Session identifier to retrieve

        """
        if not _check_serverless_available():
            return "❌ Serverless mode not available. Install dependencies: pip install redis boto3"

        try:
            manager = await _get_serverless_manager()
            if not manager:
                return "❌ Failed to initialize serverless manager"

            session_data = await manager.get_session(session_id)

            if session_data:
                output = ["📋 Serverless Session Details", ""]
                output.append(f"🆔 Session ID: {session_id}")
                output.append(f"👤 User ID: {session_data.get('user_id', 'N/A')}")
                output.append(f"🏗️ Project ID: {session_data.get('project_id', 'N/A')}")
                output.append(f"📅 Created: {session_data.get('created_at', 'N/A')}")
                output.append(f"⏰ Expires: {session_data.get('expires_at', 'N/A')}")

                # Show custom session data if present
                custom_data = session_data.get("session_data", {})
                if custom_data:
                    output.append("\n📊 Session Data:")
                    for key, value in custom_data.items():
                        output.append(f"   • {key}: {value}")

                return "\n".join(output)
            return f"❌ Session not found: {session_id}"

        except Exception as e:
            logger.exception("Error getting serverless session", error=str(e))
            return f"❌ Error retrieving session: {e}"

    @mcp.tool()
    async def update_serverless_session(
        session_id: str,
        updates: dict[str, Any],
        ttl_hours: int | None = None,
    ) -> str:
        """Update serverless session state.

        Args:
            session_id: Session identifier to update
            updates: Dictionary of updates to apply
            ttl_hours: Optional new TTL in hours

        """
        if not _check_serverless_available():
            return "❌ Serverless mode not available. Install dependencies: pip install redis boto3"

        try:
            manager = await _get_serverless_manager()
            if not manager:
                return "❌ Failed to initialize serverless manager"

            success = await manager.update_session(
                session_id=session_id,
                updates=updates,
                ttl_hours=ttl_hours,
            )

            if success:
                output = ["✅ Session updated successfully", ""]
                output.append(f"🆔 Session ID: {session_id}")
                output.append("📝 Updates applied:")

                for key, value in updates.items():
                    output.append(f"   • {key}: {value}")

                if ttl_hours:
                    output.append(f"🕐 New TTL: {ttl_hours} hours")

                return "\n".join(output)
            return f"❌ Failed to update session: {session_id}"

        except Exception as e:
            logger.exception("Error updating serverless session", error=str(e))
            return f"❌ Error updating session: {e}"

    @mcp.tool()
    async def delete_serverless_session(session_id: str) -> str:
        """Delete a serverless session.

        Args:
            session_id: Session identifier to delete

        """
        if not _check_serverless_available():
            return "❌ Serverless mode not available. Install dependencies: pip install redis boto3"

        try:
            manager = await _get_serverless_manager()
            if not manager:
                return "❌ Failed to initialize serverless manager"

            success = await manager.delete_session(session_id)

            if success:
                return f"✅ Deleted serverless session: {session_id}"
            return f"❌ Session not found: {session_id}"

        except Exception as e:
            logger.exception("Error deleting serverless session", error=str(e))
            return f"❌ Error deleting session: {e}"

    @mcp.tool()
    async def list_serverless_sessions(
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> str:
        """List serverless sessions by user or project.

        Args:
            user_id: Filter by user ID (optional)
            project_id: Filter by project ID (optional)

        """
        if not _check_serverless_available():
            return "❌ Serverless mode not available. Install dependencies: pip install redis boto3"

        try:
            manager = await _get_serverless_manager()
            if not manager:
                return "❌ Failed to initialize serverless manager"

            sessions = await manager.list_sessions(
                user_id=user_id,
                project_id=project_id,
            )

            output = ["📋 Serverless Sessions", ""]

            if not sessions:
                output.append("🔍 No sessions found")
                if user_id:
                    output.append(f"   📌 User filter: {user_id}")
                if project_id:
                    output.append(f"   📌 Project filter: {project_id}")
                return "\n".join(output)

            output.append(f"📊 Found {len(sessions)} sessions:")

            for i, session in enumerate(sessions, 1):
                output.append(f"\n{i}. **{session['session_id']}**")
                output.append(f"   👤 User: {session.get('user_id', 'N/A')}")
                output.append(f"   🏗️ Project: {session.get('project_id', 'N/A')}")
                output.append(f"   📅 Created: {session.get('created_at', 'N/A')}")
                output.append(f"   ⏰ Expires: {session.get('expires_at', 'N/A')}")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error listing serverless sessions", error=str(e))
            return f"❌ Error listing sessions: {e}"

    @mcp.tool()
    async def test_serverless_storage() -> str:
        """Test serverless storage backends for availability."""
        if not _check_serverless_available():
            return "❌ Serverless mode not available. Install dependencies: pip install redis boto3"

        try:
            manager = await _get_serverless_manager()
            if not manager:
                return "❌ Failed to initialize serverless manager"

            test_results = await manager.test_storage_backends()

            output = ["🧪 Serverless Storage Test Results", ""]

            for backend, result in test_results.items():
                status = "✅" if result["available"] else "❌"
                output.append(f"{status} {backend.title()}")

                if result["available"]:
                    output.append(
                        f"   ⚡ Response time: {result.get('response_time_ms', 0):.0f}ms"
                    )
                    if result.get("config"):
                        output.append(f"   ⚙️ Config: {result['config']}")
                else:
                    output.append(f"   ❌ Error: {result.get('error', 'Unknown')}")
                output.append("")

            working_count = sum(1 for r in test_results.values() if r["available"])
            total_count = len(test_results)
            output.append(
                f"📊 Summary: {working_count}/{total_count} backends available"
            )

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error testing serverless storage", error=str(e))
            return f"❌ Error testing storage: {e}"

    @mcp.tool()
    async def cleanup_serverless_sessions() -> str:
        """Clean up expired serverless sessions."""
        if not _check_serverless_available():
            return "❌ Serverless mode not available. Install dependencies: pip install redis boto3"

        try:
            manager = await _get_serverless_manager()
            if not manager:
                return "❌ Failed to initialize serverless manager"

            cleanup_result = await manager.cleanup_expired_sessions()

            output = ["🧹 Serverless Session Cleanup", ""]
            output.append(
                f"🗑️ Cleaned up {cleanup_result['removed_count']} expired sessions"
            )

            if cleanup_result.get("errors"):
                output.append(f"⚠️ Encountered {len(cleanup_result['errors'])} errors:")
                for error in cleanup_result["errors"]:
                    output.append(f"   • {error}")

            output.append("✅ Cleanup completed successfully")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error cleaning up serverless sessions", error=str(e))
            return f"❌ Error during cleanup: {e}"

    @mcp.tool()
    async def configure_serverless_storage(
        backend: str,
        config_updates: dict[str, Any],
    ) -> str:
        """Configure serverless storage backend settings.

        Args:
            backend: Storage backend (redis, s3, local)
            config_updates: Configuration updates to apply

        """
        if not _check_serverless_available():
            return "❌ Serverless mode not available. Install dependencies: pip install redis boto3"

        try:
            manager = await _get_serverless_manager()
            if not manager:
                return "❌ Failed to initialize serverless manager"

            success = await manager.configure_storage(backend, config_updates)

            if success:
                output = ["⚙️ Storage Configuration Updated", ""]
                output.append(f"🗄️ Backend: {backend}")
                output.append("📝 Configuration changes:")

                for key, value in config_updates.items():
                    # Mask sensitive values
                    if (
                        "password" in key.lower()
                        or "secret" in key.lower()
                        or "key" in key.lower()
                    ):
                        masked_value = f"{str(value)[:4]}***"
                    else:
                        masked_value = str(value)
                    output.append(f"   • {key}: {masked_value}")

                output.append("\n✅ Configuration saved successfully!")
                output.append(
                    "💡 Use `test_serverless_storage` to verify the configuration"
                )

                return "\n".join(output)
            return f"❌ Failed to configure {backend} storage backend"

        except Exception as e:
            logger.exception("Error configuring serverless storage", error=str(e))
            return f"❌ Error configuring storage: {e}"
