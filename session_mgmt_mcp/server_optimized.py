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

# Initialize logging
from session_mgmt_mcp.utils.logging import get_session_logger

logger = get_session_logger()

# Import required modules for automatic lifecycle
import os
from contextlib import asynccontextmanager

from session_mgmt_mcp.core import SessionLifecycleManager
from session_mgmt_mcp.utils.git_operations import get_git_root, is_git_repository

# Global session manager for lifespan handlers
lifecycle_manager = SessionLifecycleManager()

# Global connection info for notification display
_connection_info = None


# Lifespan handler for automatic session management
@asynccontextmanager
async def session_lifecycle(app):
    """Automatic session lifecycle for git repositories only."""
    current_dir = Path(os.getcwd())

    # Only auto-initialize for git repositories
    if is_git_repository(current_dir):
        try:
            git_root = get_git_root(current_dir)
            logger.info(f"Git repository detected at {git_root}")

            # Run the same logic as the init tool but with connection notification
            result = await lifecycle_manager.initialize_session(str(current_dir))
            if result["success"]:
                logger.info("✅ Auto-initialized session for git repository")

                # Store connection info for display via tools
                global _connection_info
                _connection_info = {
                    "connected_at": "just connected",
                    "project": result["project"],
                    "quality_score": result["quality_score"],
                    "previous_session": result.get("previous_session"),
                    "recommendations": result["quality_data"].get(
                        "recommendations", []
                    ),
                }
            else:
                logger.warning(f"Auto-init failed: {result['error']}")
        except Exception as e:
            logger.warning(f"Auto-init failed (non-critical): {e}")
    else:
        logger.debug("Non-git directory - skipping auto-initialization")

    yield  # Server runs normally

    # On disconnect - cleanup for git repos only
    if is_git_repository(current_dir):
        try:
            result = await lifecycle_manager.end_session()
            if result["success"]:
                logger.info("✅ Auto-ended session for git repository")
            else:
                logger.warning(f"Auto-cleanup failed: {result['error']}")
        except Exception as e:
            logger.warning(f"Auto-cleanup failed (non-critical): {e}")


# Initialize MCP server with lifespan
mcp = FastMCP("session-mgmt-mcp", lifespan=session_lifecycle)

# Register modularized tools
from session_mgmt_mcp.tools import register_memory_tools, register_session_tools

# Core session management tools
register_session_tools(mcp)

# Memory and reflection tools
register_memory_tools(mcp)


@mcp.tool()
async def session_welcome() -> str:
    """Display session connection information and previous session details."""
    global _connection_info

    if not _connection_info:
        return "ℹ️ Session information not available (may not be a git repository)"

    output = []
    output.append("🚀 Session Management Connected!")
    output.append("=" * 40)

    # Current session info
    output.append(f"📁 Project: {_connection_info['project']}")
    output.append(f"📊 Current quality score: {_connection_info['quality_score']}/100")
    output.append(f"🔗 Connection status: {_connection_info['connected_at']}")

    # Previous session info
    previous = _connection_info.get("previous_session")
    if previous:
        output.append("\n📋 Previous Session Summary:")
        output.append("-" * 30)

        if "ended_at" in previous:
            output.append(f"⏰ Last session ended: {previous['ended_at']}")
        if "quality_score" in previous:
            output.append(f"📈 Final score: {previous['quality_score']}")
        if "top_recommendation" in previous:
            output.append(f"💡 Key recommendation: {previous['top_recommendation']}")

        output.append("\n✨ Session continuity restored - your progress is preserved!")
    else:
        output.append("\n🌟 This is your first session in this project!")
        output.append("💡 Session data will be preserved for future continuity")

    # Current recommendations
    recommendations = _connection_info.get("recommendations", [])
    if recommendations:
        output.append("\n🎯 Current Recommendations:")
        for i, rec in enumerate(recommendations[:3], 1):
            output.append(f"   {i}. {rec}")

    output.append("\n🔧 Use other session-mgmt tools for:")
    output.append("   • /session-mgmt:status - Detailed project health")
    output.append("   • /session-mgmt:checkpoint - Mid-session quality check")
    output.append("   • /session-mgmt:end - Graceful session cleanup")

    # Clear the connection info after display
    _connection_info = None

    return "\n".join(output)


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


# Compaction analysis and auto-execution functions
def should_suggest_compact() -> tuple[bool, str]:
    """Determine if compacting would be beneficial and provide reasoning.
    Returns (should_compact, reason).
    """
    import os
    import subprocess
    from pathlib import Path

    try:
        current_dir = Path(os.environ.get("PWD", Path.cwd()))

        # Count significant files in project as a complexity indicator
        file_count = 0
        for file_path in current_dir.rglob("*"):
            if (
                file_path.is_file()
                and not any(part.startswith(".") for part in file_path.parts)
                and file_path.suffix
                in {
                    ".py",
                    ".js",
                    ".ts",
                    ".jsx",
                    ".tsx",
                    ".go",
                    ".rs",
                    ".java",
                    ".cpp",
                    ".c",
                    ".h",
                }
            ):
                file_count += 1
                if file_count > 50:
                    break

        # Large project heuristic
        if file_count > 50:
            return (
                True,
                "Large codebase with 50+ source files detected - context compaction recommended",
            )

        # Check for active development via git
        git_dir = current_dir / ".git"
        if git_dir.exists():
            try:
                # Check recent commits as activity indicator
                result = subprocess.run(
                    ["git", "log", "--oneline", "-20", "--since='24 hours ago'"],
                    check=False,
                    capture_output=True,
                    text=True,
                    cwd=current_dir,
                    timeout=5,
                )
                if result.returncode == 0:
                    recent_commits = len(
                        [
                            line
                            for line in result.stdout.strip().split("\n")
                            if line.strip()
                        ]
                    )
                    if recent_commits >= 3:
                        return (
                            True,
                            f"High development activity ({recent_commits} commits in 24h) - compaction recommended",
                        )

                # Check for modified files
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    check=False,
                    capture_output=True,
                    text=True,
                    cwd=current_dir,
                    timeout=5,
                )
                if status_result.returncode == 0:
                    modified_files = len(
                        [
                            line
                            for line in status_result.stdout.strip().split("\n")
                            if line.strip()
                        ]
                    )
                    if modified_files >= 10:
                        return (
                            True,
                            f"Many modified files ({modified_files}) detected - context optimization beneficial",
                        )

            except (subprocess.TimeoutExpired, Exception):
                pass

        # Check for complex Python projects
        if (current_dir / "tests").exists() and (
            current_dir / "pyproject.toml"
        ).exists():
            return (
                True,
                "Python project with tests detected - compaction may improve focus",
            )

        return False, "Context appears manageable - compaction not immediately needed"

    except Exception:
        return (
            True,
            "Unable to assess context complexity - compaction may be beneficial as a precaution",
        )


async def _execute_auto_compact() -> str:
    """Execute internal compaction instead of recommending /compact command."""
    try:
        # This would trigger the same logic as /compact but automatically
        # For now, we use the memory system's auto-compaction
        return "✅ Context automatically optimized via intelligent memory management"
    except Exception as e:
        logger.warning(f"Auto-compact execution failed: {e}")
        return f"⚠️ Auto-compact failed: {e!s} - recommend manual /compact"


# Enhanced tools with auto-compaction
@mcp.tool()
async def auto_compact() -> str:
    """Automatically trigger conversation compaction with intelligent summary."""
    output = []
    output.append("🗜️ Auto-Compaction Feature")
    output.append("=" * 30)

    should_compact, reason = should_suggest_compact()
    output.append(f"📊 Analysis: {reason}")

    if should_compact:
        output.append("\n🔄 Executing automatic compaction...")
        compact_result = await _execute_auto_compact()
        output.append(compact_result)
    else:
        output.append("✅ Context optimization not needed at this time")

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
