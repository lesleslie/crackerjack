#!/usr/bin/env python3
"""Session management MCP tools.

This module provides tools for managing Claude session lifecycle including
initialization, checkpoints, and cleanup.
"""

import shutil
import subprocess
from pathlib import Path

from session_mgmt_mcp.core import SessionLifecycleManager
from session_mgmt_mcp.utils.logging import get_session_logger

# Global session manager
session_manager = SessionLifecycleManager()
logger = get_session_logger()


# Tool implementations
async def _init_impl(working_directory: str | None = None) -> str:
    """Implementation for init tool."""
    output = []
    output.append("🚀 Claude Session Initialization via MCP Server")
    output.append("=" * 60)

    try:
        # Use the session manager for initialization
        result = await session_manager.initialize_session(working_directory)

        if result["success"]:
            output.append(f"📁 Current project: {result['project']}")
            output.append(f"📂 Working directory: {result['working_directory']}")
            output.append(f"🏠 Claude directory: {result['claude_directory']}")
            output.append(f"📊 Initial quality score: {result['quality_score']}/100")

            # Add project context info
            context = result["project_context"]
            context_items = sum(1 for detected in context.values() if detected)
            output.append(
                f"🎯 Project context: {context_items}/{len(context)} indicators detected",
            )

            # Add UV setup
            output.extend(_setup_uv_dependencies(Path(result["working_directory"])))

            # Add recommendations
            recommendations = result["quality_data"].get("recommendations", [])
            if recommendations:
                output.append("\n💡 Setup recommendations:")
                for rec in recommendations[:3]:
                    output.append(f"   • {rec}")

            output.append("\n✅ Session initialization completed successfully!")

        else:
            output.append(f"❌ Session initialization failed: {result['error']}")

    except Exception as e:
        logger.exception("Session initialization error", error=str(e))
        output.append(f"❌ Unexpected error during initialization: {e}")

    return "\n".join(output)


async def _checkpoint_impl() -> str:
    """Implementation for checkpoint tool."""
    output = []
    output.append(
        f"🔍 Claude Session Checkpoint - {session_manager.current_project or 'Current Project'}",
    )
    output.append("=" * 50)

    try:
        result = await session_manager.checkpoint_session()

        if result["success"]:
            # Add quality assessment output
            output.extend(result["quality_output"])

            # Add git checkpoint output
            output.extend(result["git_output"])

            output.append(f"\n⏰ Checkpoint completed at: {result['timestamp']}")
            output.append(
                "\n💡 Use this checkpoint data to track session progress and identify optimization opportunities.",
            )

        else:
            output.append(f"❌ Checkpoint failed: {result['error']}")

    except Exception as e:
        logger.exception("Checkpoint error", error=str(e))
        output.append(f"❌ Unexpected checkpoint error: {e}")

    return "\n".join(output)


async def _end_impl() -> str:
    """Implementation for end tool."""
    output = []
    output.append("🏁 Claude Session End - Cleanup and Handoff")
    output.append("=" * 50)

    try:
        result = await session_manager.end_session()

        if result["success"]:
            summary = result["summary"]
            output.append(f"📁 Project: {summary['project']}")
            output.append(
                f"📊 Final quality score: {summary['final_quality_score']}/100",
            )
            output.append(f"⏰ Session ended: {summary['session_end_time']}")

            # Add final recommendations
            recommendations = summary.get("recommendations", [])
            if recommendations:
                output.append("\n🎯 Final recommendations for future sessions:")
                for rec in recommendations[:5]:
                    output.append(f"   • {rec}")

            output.append("\n📝 Session Summary:")
            output.append(f"   • Working directory: {summary['working_directory']}")
            output.append("   • Session data has been logged for future reference")
            output.append("   • All temporary resources have been cleaned up")

            output.append("\n✅ Session ended successfully!")
            output.append(
                "💡 Use the session data to improve future development workflows.",
            )

        else:
            output.append(f"❌ Session end failed: {result['error']}")

    except Exception as e:
        logger.exception("Session end error", error=str(e))
        output.append(f"❌ Unexpected error during session end: {e}")

    return "\n".join(output)


async def _status_impl(working_directory: str | None = None) -> str:
    """Implementation for status tool."""
    output = []
    output.append("📊 Claude Session Status Report")
    output.append("=" * 40)

    try:
        result = await session_manager.get_session_status(working_directory)

        if result["success"]:
            output.append(f"📁 Project: {result['project']}")
            output.append(f"📂 Working directory: {result['working_directory']}")
            output.append(f"📊 Quality score: {result['quality_score']}/100")

            # Quality breakdown
            breakdown = result["quality_breakdown"]
            output.append("\n📈 Quality breakdown:")
            output.append(f"   • Project health: {breakdown['project_health']:.1f}/40")
            output.append(f"   • Permissions: {breakdown['permissions']:.1f}/20")
            output.append(
                f"   • Session tools: {breakdown['session_management']:.1f}/20",
            )
            output.append(f"   • Tool availability: {breakdown['tools']:.1f}/20")

            # System health
            health = result["system_health"]
            output.append("\n🏥 System health:")
            output.append(
                f"   • UV package manager: {'✅' if health['uv_available'] else '❌'}",
            )
            output.append(
                f"   • Git repository: {'✅' if health['git_repository'] else '❌'}",
            )
            output.append(
                f"   • Claude directory: {'✅' if health['claude_directory'] else '❌'}",
            )

            # Project context
            context = result["project_context"]
            context_items = sum(1 for detected in context.values() if detected)
            output.append(
                f"\n🎯 Project context: {context_items}/{len(context)} indicators",
            )

            # Key indicators
            key_indicators = [
                ("pyproject.toml", context.get("has_pyproject_toml", False)),
                ("Git repository", context.get("has_git_repo", False)),
                ("Test suite", context.get("has_tests", False)),
                ("Documentation", context.get("has_docs", False)),
            ]

            for name, detected in key_indicators:
                status_icon = "✅" if detected else "❌"
                output.append(f"   • {name}: {status_icon}")

            # Recommendations
            recommendations = result["recommendations"]
            if recommendations:
                output.append("\n💡 Recommendations:")
                for rec in recommendations[:3]:
                    output.append(f"   • {rec}")

            output.append(f"\n⏰ Status generated: {result['timestamp']}")

        else:
            output.append(f"❌ Status check failed: {result['error']}")

    except Exception as e:
        logger.exception("Status check error", error=str(e))
        output.append(f"❌ Unexpected error during status check: {e}")

    return "\n".join(output)


def _setup_uv_dependencies(current_dir: Path) -> list[str]:
    """Set up UV dependencies and requirements.txt generation."""
    output = []
    output.append("\n" + "=" * 50)
    output.append("📦 UV Package Management Setup")
    output.append("=" * 50)

    # Check if uv is available
    uv_available = shutil.which("uv") is not None
    if not uv_available:
        output.append("⚠️ UV not found in PATH")
        output.append("💡 Install UV: curl -LsSf https://astral.sh/uv/install.sh | sh")
        return output

    # Check for pyproject.toml
    pyproject_path = current_dir / "pyproject.toml"
    if pyproject_path.exists():
        output.append("✅ Found pyproject.toml - UV project detected")

        # Run uv sync if dependencies need updating
        try:
            sync_result = subprocess.run(
                ["uv", "sync"],
                check=False,
                cwd=current_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if sync_result.returncode == 0:
                output.append("✅ UV dependencies synchronized")
            else:
                output.append(f"⚠️ UV sync had issues: {sync_result.stderr}")
        except subprocess.TimeoutExpired:
            output.append(
                "⚠️ UV sync timed out - dependencies may need manual attention",
            )
        except Exception as e:
            output.append(f"⚠️ UV sync error: {e}")
    else:
        output.append("ℹ️ No pyproject.toml found")
        output.append("💡 Consider running 'uv init' to create a new UV project")

    return output


def register_session_tools(mcp_server) -> None:
    """Register all session management tools with the MCP server."""

    @mcp_server.tool()
    async def init(working_directory: str | None = None) -> str:
        """Initialize Claude session with comprehensive setup including UV dependencies and automation tools.

        Args:
            working_directory: Optional working directory override (defaults to PWD environment variable or current directory)

        """
        return await _init_impl(working_directory)

    @mcp_server.tool()
    async def checkpoint() -> str:
        """Perform mid-session quality checkpoint with workflow analysis and optimization recommendations."""
        return await _checkpoint_impl()

    @mcp_server.tool()
    async def end() -> str:
        """End Claude session with cleanup, learning capture, and handoff file creation."""
        return await _end_impl()

    @mcp_server.tool()
    async def status(working_directory: str | None = None) -> str:
        """Get current session status and project context information with health checks.

        Args:
            working_directory: Optional working directory override (defaults to PWD environment variable or current directory)

        """
        return await _status_impl(working_directory)
