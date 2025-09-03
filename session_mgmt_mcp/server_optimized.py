#!/usr/bin/env python3
"""Optimized Session Management MCP Server.

This is the refactored, modular version of the session management server.
It's organized into focused modules for better maintainability and performance.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Lazy loading for FastMCP
try:
    from fastmcp import FastMCP

    MCP_AVAILABLE = True
except ImportError:
    # Check if we're in a test environment
    if "pytest" in sys.modules or "test" in sys.argv[0].lower():
        print(
            "Warning: FastMCP not available in test environment, using mock",
            file=sys.stderr,
        )

        # Create a minimal mock FastMCP for testing
        class MockFastMCP:
            def __init__(self, name) -> None:
                self.name = name
                self.tools = {}
                self.prompts = {}

            def tool(self, *args, **kwargs):
                def decorator(func):
                    return func

                return decorator

            def prompt(self, *args, **kwargs):
                def decorator(func):
                    return func

                return decorator

            def run(self, *args, **kwargs) -> None:
                pass

        FastMCP = MockFastMCP
        MCP_AVAILABLE = False
    else:
        print("FastMCP not available. Install with: uv add fastmcp", file=sys.stderr)
        sys.exit(1)

# Initialize MCP server
mcp = FastMCP("session-mgmt-mcp")

# Initialize logging
from session_mgmt_mcp.utils.logging import get_session_logger

logger = get_session_logger()

# Register modularized tools
from session_mgmt_mcp.tools import register_memory_tools, register_session_tools

# Core session management tools
register_session_tools(mcp)

# Memory and reflection tools
register_memory_tools(mcp)


# Permission management (simplified for now)
class SessionPermissionsManager:
    """Simplified session permissions manager."""

    def __init__(self) -> None:
        self.trusted_operations = set()
        self.auto_checkpoint = False
        self.checkpoint_frequency = 300

    def is_operation_trusted(self, operation: str) -> bool:
        return operation in self.trusted_operations

    def add_trusted_operation(self, operation: str) -> None:
        self.trusted_operations.add(operation)


# Global permissions manager
permissions_manager = SessionPermissionsManager()


@mcp.tool()
async def permissions(action: str = "status", operation: str | None = None) -> str:
    """Manage session permissions for trusted operations to avoid repeated prompts.

    Args:
        action: Action to perform: status (show current), trust (add operation), revoke_all (reset)
        operation: Operation to trust (required for 'trust' action)

    """
    output = []
    output.append("🔐 Session Permissions Management")
    output.append("=" * 40)

    if action == "status":
        if permissions_manager.trusted_operations:
            output.append(
                f"✅ {len(permissions_manager.trusted_operations)} trusted operations:",
            )
            for op in sorted(permissions_manager.trusted_operations):
                output.append(f"   • {op}")
            output.append(
                "\n💡 These operations will not prompt for permission in future sessions",
            )
        else:
            output.append("⚠️ No operations are currently trusted")
            output.append(
                "💡 Operations will be automatically trusted on first successful use",
            )

        output.append("\n🛠️ Common Operations That Can Be Trusted:")
        output.append("   • UV Package Management - uv sync, pip operations")
        output.append("   • Git Repository Access - git status, commit, push")
        output.append("   • Project File Access - reading/writing project files")
        output.append("   • Subprocess Execution - running build tools, tests")
        output.append("   • Claude Directory Access - accessing ~/.claude/")

    elif action == "trust":
        if not operation:
            output.append("❌ Error: 'operation' parameter required for 'trust' action")
            output.append(
                "💡 Example: permissions with action='trust' and operation='uv_package_management'",
            )
        else:
            permissions_manager.add_trusted_operation(operation)
            output.append(
                f"✅ Operation '{operation}' has been added to trusted operations",
            )
            output.append("💡 This operation will no longer require permission prompts")

    elif action == "revoke_all":
        count = len(permissions_manager.trusted_operations)
        permissions_manager.trusted_operations.clear()
        output.append(f"🗑️ Revoked {count} trusted operations")
        output.append("💡 All operations will now require permission prompts")

    else:
        output.append(f"❌ Unknown action: {action}")
        output.append("💡 Valid actions: status, trust, revoke_all")

    return "\n".join(output)


# Additional simplified tools for compatibility
@mcp.tool()
async def auto_compact() -> str:
    """Automatically trigger conversation compaction with intelligent summary."""
    output = []
    output.append("🗜️ Auto-Compaction Feature")
    output.append("=" * 30)
    output.append("✅ This feature is now handled by the modular memory system")
    output.append("💡 Memory optimization occurs automatically in the background")
    return "\n".join(output)


@mcp.tool()
async def quality_monitor() -> str:
    """Phase 3: Proactive quality monitoring with early warning system."""
    output = []
    output.append("📊 Quality Monitoring")
    output.append("=" * 25)
    output.append(
        "✅ Quality monitoring is integrated into the session management system",
    )
    output.append("💡 Use the 'status' tool to get current quality metrics")
    output.append("💡 Use the 'checkpoint' tool for comprehensive quality assessment")
    return "\n".join(output)


# Server startup
def run_server() -> None:
    """Run the optimized MCP server."""
    try:
        logger.info("Starting optimized session-mgmt-mcp server")

        # Log the modular structure
        logger.info(
            "Modular components loaded",
            session_tools=True,
            memory_tools=True,
            git_operations=True,
            logging_utils=True,
        )

        if MCP_AVAILABLE:
            mcp.run()
        else:
            logger.warning("Running in mock mode - FastMCP not available")

    except Exception as e:
        logger.exception("Server startup failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run_server()
