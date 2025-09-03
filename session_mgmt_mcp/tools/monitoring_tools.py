#!/usr/bin/env python3
"""Application monitoring and activity tracking MCP tools.

This module provides tools for monitoring application activity, tracking interruptions,
and managing session context following crackerjack architecture patterns.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazy loading for optional monitoring dependencies
_app_monitor = None
_app_monitor_available = None
_interruption_manager = None
_interruption_available = None


async def _get_app_monitor():
    """Get application monitor instance with lazy loading."""
    global _app_monitor, _app_monitor_available

    if _app_monitor_available is False:
        return None

    if _app_monitor is None:
        try:
            from session_mgmt_mcp.app_monitor import ApplicationMonitor

            _app_monitor = ApplicationMonitor()
            _app_monitor_available = True
        except ImportError as e:
            logger.warning(f"Application monitoring not available: {e}")
            _app_monitor_available = False
            return None

    return _app_monitor


async def _get_interruption_manager():
    """Get interruption manager instance with lazy loading."""
    global _interruption_manager, _interruption_available

    if _interruption_available is False:
        return None

    if _interruption_manager is None:
        try:
            from session_mgmt_mcp.interruption_manager import InterruptionManager

            _interruption_manager = InterruptionManager()
            _interruption_available = True
        except ImportError as e:
            logger.warning(f"Interruption management not available: {e}")
            _interruption_available = False
            return None

    return _interruption_manager


def _check_app_monitor_available() -> bool:
    """Check if application monitoring is available."""
    global _app_monitor_available

    if _app_monitor_available is None:
        try:
            import importlib.util

            spec = importlib.util.find_spec("session_mgmt_mcp.app_monitor")
            _app_monitor_available = spec is not None
        except ImportError:
            _app_monitor_available = False

    return _app_monitor_available


def _check_interruption_available() -> bool:
    """Check if interruption management is available."""
    global _interruption_available

    if _interruption_available is None:
        try:
            import importlib.util

            spec = importlib.util.find_spec("session_mgmt_mcp.interruption_manager")
            _interruption_available = spec is not None
        except ImportError:
            _interruption_available = False

    return _interruption_available


def register_monitoring_tools(mcp) -> None:
    """Register all monitoring and activity tracking MCP tools.

    Args:
        mcp: FastMCP server instance

    """

    @mcp.tool()
    async def start_app_monitoring(project_paths: list[str] | None = None) -> str:
        """Start monitoring IDE activity and browser documentation usage.

        Args:
            project_paths: Optional list of project directories to monitor

        """
        if not _check_app_monitor_available():
            return "❌ Application monitoring not available. Features may be limited."

        try:
            monitor = await _get_app_monitor()
            if not monitor:
                return "❌ Failed to initialize application monitor"

            await monitor.start_monitoring(project_paths=project_paths)

            output = ["🔍 Application Monitoring Started", ""]

            if project_paths:
                output.append("📁 Monitoring project paths:")
                for path in project_paths:
                    output.append(f"   • {path}")
            else:
                output.append("📁 Monitoring all accessible paths")

            output.append("")
            output.append("👁️ Now tracking:")
            output.append("   • IDE file access and editing patterns")
            output.append("   • Browser documentation and research activity")
            output.append("   • Application focus and context switches")
            output.append("   • File system changes and development flow")

            output.append("\n💡 Use `get_activity_summary` to view tracked activity")
            output.append("💡 Use `stop_app_monitoring` to end tracking")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error starting app monitoring", error=str(e))
            return f"❌ Error starting monitoring: {e}"

    @mcp.tool()
    async def stop_app_monitoring() -> str:
        """Stop all application monitoring."""
        if not _check_app_monitor_available():
            return "❌ Application monitoring not available"

        try:
            monitor = await _get_app_monitor()
            if not monitor:
                return "❌ Failed to initialize application monitor"

            summary = await monitor.stop_monitoring()

            output = ["⏹️ Application Monitoring Stopped", ""]
            output.append("📊 Session summary:")
            output.append(
                f"   • Duration: {summary.get('duration_minutes', 0):.1f} minutes"
            )
            output.append(f"   • Files tracked: {summary.get('files_tracked', 0)}")
            output.append(
                f"   • Applications monitored: {summary.get('apps_monitored', 0)}"
            )
            output.append(
                f"   • Context switches: {summary.get('context_switches', 0)}"
            )

            output.append("\n✅ All monitoring stopped successfully")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error stopping app monitoring", error=str(e))
            return f"❌ Error stopping monitoring: {e}"

    @mcp.tool()
    async def get_activity_summary(hours: int = 2) -> str:
        """Get activity summary for the specified number of hours.

        Args:
            hours: Number of hours to look back (default: 2)

        """
        if not _check_app_monitor_available():
            return "❌ Application monitoring not available"

        try:
            monitor = await _get_app_monitor()
            if not monitor:
                return "❌ Failed to initialize application monitor"

            summary = await monitor.get_activity_summary(hours=hours)

            output = [f"📊 Activity Summary - Last {hours} Hours", ""]

            if not summary.get("has_data"):
                output.append("🔍 No activity data available")
                output.append("💡 Start monitoring with `start_app_monitoring`")
                return "\n".join(output)

            # File activity
            files = summary.get("file_activity", [])
            if files:
                output.append(f"📄 File Activity ({len(files)} files):")
                for file_info in files[:10]:  # Show top 10
                    output.append(
                        f"   • {file_info['path']} ({file_info['access_count']} accesses)"
                    )
                if len(files) > 10:
                    output.append(f"   • ... and {len(files) - 10} more files")

            # Application focus
            apps = summary.get("app_activity", [])
            if apps:
                output.append("\n🖥️ Application Focus:")
                for app_info in apps[:5]:  # Show top 5
                    duration = app_info["focus_time_minutes"]
                    output.append(f"   • {app_info['name']}: {duration:.1f} minutes")

            # Productivity metrics
            metrics = summary.get("productivity_metrics", {})
            if metrics:
                output.append("\n📈 Productivity Metrics:")
                output.append(
                    f"   • Focus time: {metrics.get('focus_time_minutes', 0):.1f} minutes"
                )
                output.append(
                    f"   • Context switches: {metrics.get('context_switches', 0)}"
                )
                output.append(
                    f"   • Deep work periods: {metrics.get('deep_work_periods', 0)}"
                )

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error getting activity summary", error=str(e))
            return f"❌ Error getting activity summary: {e}"

    @mcp.tool()
    async def get_context_insights(hours: int = 1) -> str:
        """Get contextual insights from recent activity.

        Args:
            hours: Number of hours to analyze (default: 1)

        """
        if not _check_app_monitor_available():
            return "❌ Application monitoring not available"

        try:
            monitor = await _get_app_monitor()
            if not monitor:
                return "❌ Failed to initialize application monitor"

            insights = await monitor.get_context_insights(hours=hours)

            output = [f"🧠 Context Insights - Last {hours} Hours", ""]

            if not insights.get("has_data"):
                output.append("🔍 No context data available")
                return "\n".join(output)

            # Current focus area
            focus = insights.get("current_focus")
            if focus:
                output.append(f"🎯 Current Focus: {focus['area']}")
                output.append(f"   Duration: {focus['duration_minutes']:.1f} minutes")

            # Project patterns
            patterns = insights.get("project_patterns", [])
            if patterns:
                output.append("\n📋 Project Patterns:")
                for pattern in patterns[:3]:
                    output.append(f"   • {pattern['description']}")

            # Technology context
            tech_context = insights.get("technology_context", [])
            if tech_context:
                output.append("\n⚙️ Technology Context:")
                for tech in tech_context[:5]:
                    output.append(
                        f"   • {tech['name']}: {tech['confidence']:.0%} confidence"
                    )

            # Recommendations
            recommendations = insights.get("recommendations", [])
            if recommendations:
                output.append("\n💡 Recommendations:")
                for rec in recommendations[:3]:
                    output.append(f"   • {rec}")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error getting context insights", error=str(e))
            return f"❌ Error getting context insights: {e}"

    @mcp.tool()
    async def get_active_files(minutes: int = 60) -> str:
        """Get files currently being worked on.

        Args:
            minutes: Number of minutes to look back (default: 60)

        """
        if not _check_app_monitor_available():
            return "❌ Application monitoring not available"

        try:
            monitor = await _get_app_monitor()
            if not monitor:
                return "❌ Failed to initialize application monitor"

            active_files = await monitor.get_active_files(minutes=minutes)

            output = [f"📁 Active Files - Last {minutes} Minutes", ""]

            if not active_files:
                output.append("🔍 No active files detected")
                output.append("💡 Files may not be monitored or no recent activity")
                return "\n".join(output)

            for i, file_info in enumerate(active_files, 1):
                output.append(f"{i}. **{file_info['path']}**")
                output.append(f"   Last accessed: {file_info['last_access']}")
                output.append(f"   Access count: {file_info['access_count']}")
                output.append(
                    f"   Duration: {file_info['total_time_minutes']:.1f} minutes"
                )

                if file_info.get("project"):
                    output.append(f"   Project: {file_info['project']}")

                output.append("")

            output.append(f"📊 Total: {len(active_files)} active files")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error getting active files", error=str(e))
            return f"❌ Error getting active files: {e}"

    # Interruption Management Tools

    @mcp.tool()
    async def start_interruption_monitoring(
        watch_files: bool = True,
        working_directory: str = ".",
    ) -> str:
        """Start smart interruption monitoring with context switch detection."""
        if not _check_interruption_available():
            return "❌ Interruption monitoring not available"

        try:
            manager = await _get_interruption_manager()
            if not manager:
                return "❌ Failed to initialize interruption manager"

            await manager.start_monitoring(
                watch_files=watch_files,
                working_directory=working_directory,
            )

            output = ["🚨 Interruption Monitoring Started", ""]
            output.append(f"📁 Working directory: {working_directory}")
            output.append(
                f"👁️ File watching: {'Enabled' if watch_files else 'Disabled'}"
            )

            output.append("\n🔍 Now detecting:")
            output.append("   • Context switches and interruptions")
            output.append("   • File system changes requiring attention")
            output.append("   • Long idle periods indicating breaks")
            output.append("   • Return from interruptions needing context restore")

            output.append(
                "\n💡 Context will be automatically preserved on interruptions"
            )
            output.append(
                "💡 Use `get_interruption_history` to view detected interruptions"
            )

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error starting interruption monitoring", error=str(e))
            return f"❌ Error starting interruption monitoring: {e}"

    @mcp.tool()
    async def stop_interruption_monitoring() -> str:
        """Stop interruption monitoring."""
        if not _check_interruption_available():
            return "❌ Interruption monitoring not available"

        try:
            manager = await _get_interruption_manager()
            if not manager:
                return "❌ Failed to initialize interruption manager"

            summary = await manager.stop_monitoring()

            output = ["⏹️ Interruption Monitoring Stopped", ""]
            output.append("📊 Session summary:")
            output.append(
                f"   • Duration: {summary.get('duration_minutes', 0):.1f} minutes"
            )
            output.append(
                f"   • Interruptions detected: {summary.get('interruptions_detected', 0)}"
            )
            output.append(f"   • Context saves: {summary.get('context_saves', 0)}")
            output.append(
                f"   • Context restores: {summary.get('context_restores', 0)}"
            )

            output.append("\n✅ Interruption monitoring stopped successfully")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error stopping interruption monitoring", error=str(e))
            return f"❌ Error stopping interruption monitoring: {e}"

    @mcp.tool()
    async def create_session_context(
        user_id: str,
        project_id: str | None = None,
        working_directory: str = ".",
    ) -> str:
        """Create new session context for interruption management."""
        if not _check_interruption_available():
            return "❌ Interruption monitoring not available"

        try:
            manager = await _get_interruption_manager()
            if not manager:
                return "❌ Failed to initialize interruption manager"

            session_id = await manager.create_session_context(
                user_id=user_id,
                project_id=project_id,
                working_directory=working_directory,
            )

            output = ["📝 Session Context Created", ""]
            output.append(f"🆔 Session ID: {session_id}")
            output.append(f"👤 User: {user_id}")
            if project_id:
                output.append(f"🏗️ Project: {project_id}")
            output.append(f"📁 Directory: {working_directory}")

            output.append("\n✅ Context tracking initialized")
            output.append("💡 Context will be automatically saved during interruptions")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error creating session context", error=str(e))
            return f"❌ Error creating session context: {e}"

    @mcp.tool()
    async def preserve_current_context(
        session_id: str | None = None,
        force: bool = False,
    ) -> str:
        """Manually preserve current session context."""
        if not _check_interruption_available():
            return "❌ Interruption monitoring not available"

        try:
            manager = await _get_interruption_manager()
            if not manager:
                return "❌ Failed to initialize interruption manager"

            context_id = await manager.preserve_context(
                session_id=session_id,
                force=force,
            )

            output = ["💾 Context Preserved", ""]
            output.append(f"🆔 Context ID: {context_id}")

            if session_id:
                output.append(f"📋 Session: {session_id}")

            output.append("✅ Current context saved successfully")
            output.append(
                "💡 Use `restore_session_context` to restore this state later"
            )

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error preserving context", error=str(e))
            return f"❌ Error preserving context: {e}"

    @mcp.tool()
    async def restore_session_context(session_id: str) -> str:
        """Restore session context from snapshot."""
        if not _check_interruption_available():
            return "❌ Interruption monitoring not available"

        try:
            manager = await _get_interruption_manager()
            if not manager:
                return "❌ Failed to initialize interruption manager"

            restored = await manager.restore_context(session_id)

            if restored:
                output = ["🔄 Context Restored", ""]
                output.append(f"📋 Session: {session_id}")
                output.append("✅ Context state restored successfully")

                # Show restored context details
                if restored.get("context_data"):
                    data = restored["context_data"]
                    output.append("\n📊 Restored context:")
                    if data.get("working_directory"):
                        output.append(
                            f"   • Working directory: {data['working_directory']}"
                        )
                    if data.get("active_files"):
                        output.append(f"   • Active files: {len(data['active_files'])}")
                    if data.get("timestamp"):
                        output.append(f"   • Saved at: {data['timestamp']}")

                return "\n".join(output)
            return f"❌ Context not found: {session_id}"

        except Exception as e:
            logger.exception("Error restoring context", error=str(e))
            return f"❌ Error restoring context: {e}"

    @mcp.tool()
    async def get_interruption_history(user_id: str, hours: int = 24) -> str:
        """Get recent interruption history for user."""
        if not _check_interruption_available():
            return "❌ Interruption monitoring not available"

        try:
            manager = await _get_interruption_manager()
            if not manager:
                return "❌ Failed to initialize interruption manager"

            history = await manager.get_interruption_history(
                user_id=user_id,
                hours=hours,
            )

            output = [
                f"📊 Interruption History - Last {hours} Hours",
                f"👤 User: {user_id}",
                "",
            ]

            if not history:
                output.append("🔍 No interruptions detected")
                output.append(
                    "💡 Either no interruptions occurred or monitoring wasn't active"
                )
                return "\n".join(output)

            for i, interruption in enumerate(history, 1):
                output.append(
                    f"{i}. **{interruption['type']}** - {interruption['timestamp']}"
                )
                output.append(
                    f"   Duration: {interruption['duration_minutes']:.1f} minutes"
                )

                if interruption.get("context_saved"):
                    output.append("   💾 Context preserved")

                if interruption.get("context_restored"):
                    output.append("   🔄 Context restored")

                if interruption.get("trigger"):
                    output.append(f"   🎯 Trigger: {interruption['trigger']}")

                output.append("")

            # Summary statistics
            total_interruptions = len(history)
            avg_duration = (
                sum(i["duration_minutes"] for i in history) / total_interruptions
            )
            context_saves = sum(1 for i in history if i.get("context_saved"))

            output.append("📈 Summary:")
            output.append(f"   • Total interruptions: {total_interruptions}")
            output.append(f"   • Average duration: {avg_duration:.1f} minutes")
            output.append(f"   • Context saves: {context_saves}/{total_interruptions}")

            return "\n".join(output)

        except Exception as e:
            logger.exception("Error getting interruption history", error=str(e))
            return f"❌ Error getting interruption history: {e}"
