#!/usr/bin/env python3
"""Crackerjack integration tools for session-mgmt-mcp.

Following crackerjack architecture patterns for quality monitoring,
code analysis, and development workflow integration.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def register_crackerjack_tools(mcp) -> None:
    """Register all crackerjack integration MCP tools.

    Args:
        mcp: FastMCP server instance

    """

    @mcp.tool()
    async def execute_crackerjack_command(
        command: str,
        args: str = "",
        working_directory: str = ".",
        timeout: int = 300,
        ai_agent_mode: bool = False,
    ) -> str:
        """Execute a Crackerjack command with enhanced AI integration."""
        try:
            from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration

            # Build full command
            full_command = ["python", "-m", "crackerjack"]
            if command != "crackerjack":
                full_command.append(command)
            if args:
                full_command.extend(args.split())
            if ai_agent_mode:
                full_command.append("--ai-agent")

            integration = CrackerjackIntegration()
            result = await integration.execute_crackerjack_command(
                command,
                args.split() if args else None,
                working_directory,
                timeout,
                ai_agent_mode,
            )

            # Format response
            output = f"🔧 **Crackerjack {command}** executed\n\n"

            if result.exit_code == 0:
                output += "✅ **Status**: Success\n"
            else:
                output += f"❌ **Status**: Failed (exit code: {result.exit_code})\n"

            if result.stdout.strip():
                output += f"\n**Output**:\n```\n{result.stdout}\n```\n"

            if result.stderr.strip():
                output += f"\n**Errors**:\n```\n{result.stderr}\n```\n"

            # Add execution metrics
            output += "\n📊 **Metrics**:\n"
            output += f"- Execution time: {result.execution_time:.2f}s\n"
            output += f"- Exit code: {result.exit_code}\n"

            # Add quality metrics if available
            if result.quality_metrics:
                output += "\n📈 **Quality Metrics**:\n"
                for metric, value in result.quality_metrics.items():
                    output += f"- {metric.replace('_', ' ').title()}: {value:.1f}\n"

            # Add memory insights if available
            if result.memory_insights:
                output += "\n🧠 **Insights**:\n"
                for insight in result.memory_insights[:5]:  # Limit to top 5
                    output += f"- {insight}\n"

            return output

        except ImportError:
            logger.warning("Crackerjack integration not available")
            return (
                "❌ Crackerjack integration not available. Install crackerjack package."
            )
        except Exception as e:
            logger.exception(f"Crackerjack execution failed: {e}")
            return f"❌ Crackerjack execution failed: {e!s}"

    @mcp.tool()
    async def crackerjack_run(
        command: str,
        args: str = "",
        working_directory: str = ".",
        timeout: int = 300,
        ai_agent_mode: bool = False,
    ) -> str:
        """Run crackerjack with enhanced analytics (replaces /crackerjack:run)."""
        try:
            from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration

            # Use the enhanced execution method
            integration = CrackerjackIntegration()
            result = await integration.execute_crackerjack_command(
                command,
                args.split() if args else None,
                working_directory,
                timeout,
                ai_agent_mode,
            )

            # Format response similar to execute_crackerjack_command
            formatted_result = f"🔧 **Crackerjack {command}** executed\n\n"

            if result.exit_code == 0:
                formatted_result += "✅ **Status**: Success\n"
            else:
                formatted_result += (
                    f"❌ **Status**: Failed (exit code: {result.exit_code})\n"
                )

            if result.stdout.strip():
                formatted_result += f"\n**Output**:\n```\n{result.stdout}\n```\n"

            if result.stderr.strip():
                formatted_result += f"\n**Errors**:\n```\n{result.stderr}\n```\n"

            # Add session management integration
            output = f"🔧 **Enhanced Crackerjack Run**\n\n{formatted_result}\n"

            # Store execution in history
            try:
                from session_mgmt_mcp.reflection_tools import ReflectionDatabase

                # Store in reflection database for future reference
                db = ReflectionDatabase()
                async with db:
                    await db.store_conversation(
                        content=f"Crackerjack {command} execution: {formatted_result[:500]}...",
                        project=Path(working_directory).name,
                    )

                output += "📝 Execution stored in session history\n"

            except Exception as e:
                logger.debug(f"Failed to store crackerjack execution: {e}")

            return output

        except Exception as e:
            logger.exception(f"Enhanced crackerjack run failed: {e}")
            return f"❌ Enhanced crackerjack run failed: {e!s}"

    @mcp.tool()
    async def crackerjack_history(
        command_filter: str = "",
        days: int = 7,
        working_directory: str = ".",
    ) -> str:
        """View crackerjack execution history with trends and patterns."""
        try:
            from datetime import datetime, timedelta

            from session_mgmt_mcp.reflection_tools import ReflectionDatabase

            db = ReflectionDatabase()
            async with db:
                # Search for crackerjack executions
                end_date = datetime.now()
                end_date - timedelta(days=days)

                results = await db.search_conversations(
                    query=f"crackerjack {command_filter}".strip(),
                    project=Path(working_directory).name,
                    limit=50,
                )

                if not results:
                    return f"📊 No crackerjack executions found in last {days} days"

                output = f"📊 **Crackerjack History** (last {days} days)\n\n"

                # Group by command
                commands = {}
                for result in results:
                    content = result.get("content", "")
                    if "crackerjack" in content.lower():
                        # Extract command from content

                        # Use validated pattern for command extraction
                        from session_mgmt_mcp.utils.regex_patterns import SAFE_PATTERNS

                        crackerjack_cmd_pattern = SAFE_PATTERNS["crackerjack_command"]
                        match = crackerjack_cmd_pattern.search(content.lower())
                        cmd = match.group(1) if match else "unknown"

                        if cmd not in commands:
                            commands[cmd] = []
                        commands[cmd].append(result)

                # Display summary
                output += f"**Total Executions**: {len(results)}\n"
                output += f"**Commands Used**: {', '.join(commands.keys())}\n\n"

                # Show recent executions
                output += "**Recent Executions**:\n"
                for i, result in enumerate(results[:10], 1):
                    timestamp = result.get("timestamp", "Unknown")
                    content = result.get("content", "")[:100]
                    output += f"{i}. ({timestamp}) {content}...\n"

                return output

        except Exception as e:
            logger.exception(f"Crackerjack history failed: {e}")
            return f"❌ History retrieval failed: {e!s}"

    @mcp.tool()
    async def crackerjack_metrics(working_directory: str = ".", days: int = 30) -> str:
        """Get quality metrics trends from crackerjack execution history."""
        try:
            from session_mgmt_mcp.reflection_tools import ReflectionDatabase

            db = ReflectionDatabase()
            async with db:
                results = await db.search_conversations(
                    query="crackerjack metrics quality",
                    project=Path(working_directory).name,
                    limit=100,
                )

                output = f"📊 **Crackerjack Quality Metrics** (last {days} days)\n\n"

                if not results:
                    output += "No quality metrics data available\n"
                    output += "💡 Run `crackerjack analyze` to generate metrics\n"
                    return output

                # Basic metrics analysis
                success_count = sum(
                    1 for r in results if "success" in r.get("content", "").lower()
                )
                failure_count = len(results) - success_count

                output += "**Execution Summary**:\n"
                output += f"- Total runs: {len(results)}\n"
                output += f"- Successful: {success_count}\n"
                output += f"- Failed: {failure_count}\n"
                output += (
                    f"- Success rate: {(success_count / len(results) * 100):.1f}%\n\n"
                )

                # Extract quality patterns
                quality_keywords = [
                    "lint",
                    "test",
                    "security",
                    "complexity",
                    "coverage",
                ]
                keyword_counts = {}

                for result in results:
                    content = result.get("content", "").lower()
                    for keyword in quality_keywords:
                        if keyword in content:
                            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

                if keyword_counts:
                    output += "**Quality Focus Areas**:\n"
                    for keyword, count in sorted(
                        keyword_counts.items(), key=lambda x: x[1], reverse=True
                    ):
                        output += f"- {keyword.title()}: {count} mentions\n"

                output += "\n💡 Use `crackerjack analyze` for detailed quality analysis"

                return output

        except Exception as e:
            logger.exception(f"Metrics analysis failed: {e}")
            return f"❌ Metrics analysis failed: {e!s}"

    @mcp.tool()
    async def crackerjack_patterns(days: int = 7, working_directory: str = ".") -> str:
        """Analyze test failure patterns and trends."""
        try:
            from session_mgmt_mcp.reflection_tools import ReflectionDatabase

            db = ReflectionDatabase()
            async with db:
                results = await db.search_conversations(
                    query="test failure error pattern",
                    project=Path(working_directory).name,
                    limit=50,
                )

                output = f"🔍 **Test Failure Patterns** (last {days} days)\n\n"

                if not results:
                    output += "No test failure patterns found\n"
                    output += "✅ This might indicate good code quality!\n"
                    return output

                # Extract common failure patterns
                failure_keywords = [
                    "failed",
                    "error",
                    "exception",
                    "assertion",
                    "timeout",
                ]
                patterns = {}

                for result in results:
                    content = result.get("content", "").lower()
                    for keyword in failure_keywords:
                        if keyword in content:
                            # Extract context around the keyword

                            # Find keyword occurrences using simple string search
                            matches = []
                            start_pos = 0
                            while True:
                                pos = content.find(keyword, start_pos)
                                if pos == -1:
                                    break

                                # Create a match-like object with start() and end() methods
                                class SimpleMatch:
                                    def __init__(self, start_pos, end_pos):
                                        self._start = start_pos
                                        self._end = end_pos

                                    def start(self):
                                        return self._start

                                    def end(self):
                                        return self._end

                                matches.append(SimpleMatch(pos, pos + len(keyword)))
                                start_pos = pos + 1
                            for match in matches:
                                start = max(0, match.start() - 30)
                                end = min(len(content), match.end() + 30)
                                context = content[start:end].strip()
                                patterns[context] = patterns.get(context, 0) + 1

                if patterns:
                    output += "**Common Failure Patterns**:\n"
                    sorted_patterns = sorted(
                        patterns.items(), key=lambda x: x[1], reverse=True
                    )

                    for i, (pattern, count) in enumerate(sorted_patterns[:10], 1):
                        output += f"{i}. ({count}x) {pattern}...\n"

                    output += f"\n📊 Total unique patterns: {len(patterns)}\n"
                    output += f"📊 Total failure mentions: {sum(patterns.values())}\n"
                else:
                    output += "No clear failure patterns identified\n"

                return output

        except Exception as e:
            logger.exception(f"Pattern analysis failed: {e}")
            return f"❌ Pattern analysis failed: {e!s}"

    @mcp.tool()
    async def crackerjack_help() -> str:
        """Get comprehensive help for choosing the right crackerjack commands."""
        return """🔧 **Crackerjack Command Guide**

**Quick Quality Checks**:
- `crackerjack` - Fast lint and format
- `crackerjack -t` - Include tests
- `crackerjack --ai-agent -t` - AI-powered autonomous fixing

**Analysis Commands**:
- `crackerjack analyze` - Code quality analysis
- `crackerjack security` - Security scanning
- `crackerjack complexity` - Complexity analysis
- `crackerjack typecheck` - Type checking

**Development Workflow**:
- `crackerjack lint` - Code formatting and linting
- `crackerjack test` - Run test suite
- `crackerjack check` - Comprehensive quality checks
- `crackerjack clean` - Clean temporary files

**Advanced Features**:
- `--ai-agent` - Enable autonomous AI fixing
- `--verbose` - Detailed output
- `--fix` - Automatically fix issues where possible

**MCP Integration**:
- Use `execute_crackerjack_command` for any crackerjack command
- Use `crackerjack_run` for enhanced analytics and history
- Use `crackerjack_metrics` for quality trends

💡 **Pro Tips**:
- Always run `crackerjack -t` before commits
- Use `--ai-agent` for complex quality issues
- Check `crackerjack_history` to learn from past runs
- Monitor trends with `crackerjack_metrics`
"""

    @mcp.tool()
    async def get_crackerjack_results_history(
        command_filter: str = "",
        days: int = 7,
        working_directory: str = ".",
    ) -> str:
        """Get recent Crackerjack command execution history."""
        # This is essentially the same as crackerjack_history
        return await crackerjack_history(command_filter, days, working_directory)

    @mcp.tool()
    async def get_crackerjack_quality_metrics(
        days: int = 30,
        working_directory: str = ".",
    ) -> str:
        """Get quality metrics trends from Crackerjack execution history."""
        # This is essentially the same as crackerjack_metrics
        return await crackerjack_metrics(working_directory, days)

    @mcp.tool()
    async def analyze_crackerjack_test_patterns(
        days: int = 7,
        working_directory: str = ".",
    ) -> str:
        """Analyze test failure patterns and trends."""
        # This is essentially the same as crackerjack_patterns
        return await crackerjack_patterns(days, working_directory)

    @mcp.tool()
    async def crackerjack_quality_trends(
        days: int = 30,
        working_directory: str = ".",
    ) -> str:
        """Analyze quality trends over time with actionable insights."""
        try:
            from session_mgmt_mcp.reflection_tools import ReflectionDatabase

            db = ReflectionDatabase()
            async with db:
                results = await db.search_conversations(
                    query="crackerjack quality success failed",
                    project=Path(working_directory).name,
                    limit=200,
                )

                output = f"📈 **Quality Trends Analysis** (last {days} days)\n\n"

                if len(results) < 5:
                    output += "Insufficient data for trend analysis\n"
                    output += (
                        "💡 Run more crackerjack commands to build trend history\n"
                    )
                    return output

                # Analyze success rate over time
                success_trend = []
                failure_trend = []

                for result in results:
                    content = result.get("content", "").lower()
                    timestamp = result.get("timestamp", "")

                    if "success" in content or "✅" in content:
                        success_trend.append(timestamp)
                    elif "failed" in content or "error" in content or "❌" in content:
                        failure_trend.append(timestamp)

                # Basic trend analysis
                total_runs = len(success_trend) + len(failure_trend)
                success_rate = (
                    (len(success_trend) / total_runs * 100) if total_runs > 0 else 0
                )

                output += "**Overall Trends**:\n"
                output += f"- Total quality runs: {total_runs}\n"
                output += f"- Success rate: {success_rate:.1f}%\n"
                output += f"- Success trend: {len(success_trend)} passes\n"
                output += f"- Failure trend: {len(failure_trend)} issues\n\n"

                # Quality insights
                if success_rate > 80:
                    output += "🎉 **Excellent quality trend!** Your code quality is consistently high.\n"
                elif success_rate > 60:
                    output += "✅ **Good quality trend.** Room for improvement in consistency.\n"
                else:
                    output += "⚠️ **Quality attention needed.** Consider more frequent quality checks.\n"

                output += "\n**Recommendations**:\n"
                if success_rate < 70:
                    output += "- Run `crackerjack --ai-agent -t` for automated fixing\n"
                    output += "- Increase frequency of quality checks\n"
                    output += "- Focus on test coverage improvement\n"
                else:
                    output += "- Maintain current quality practices\n"
                    output += "- Consider adding complexity monitoring\n"

                return output

        except Exception as e:
            logger.exception(f"Trend analysis failed: {e}")
            return f"❌ Trend analysis failed: {e!s}"

    @mcp.tool()
    async def crackerjack_health_check() -> str:
        """Check Crackerjack integration health and provide diagnostics."""
        output = "🔧 **Crackerjack Health Check**\n\n"

        try:
            # Check if crackerjack is available
            import subprocess

            result = subprocess.run(
                ["python", "-m", "crackerjack", "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                output += "✅ **Crackerjack Installation**: Available\n"
                output += f"   Version: {result.stdout.strip()}\n"
            else:
                output += "❌ **Crackerjack Installation**: Not working properly\n"
                output += f"   Error: {result.stderr}\n"

        except subprocess.TimeoutExpired:
            output += "⏰ **Crackerjack Installation**: Timeout (slow system?)\n"
        except FileNotFoundError:
            output += "❌ **Crackerjack Installation**: Not found\n"
            output += "   💡 Install with: `uv add crackerjack`\n"
        except Exception as e:
            output += f"❌ **Crackerjack Installation**: Error - {e!s}\n"

        # Check integration components
        try:
            # CrackerjackIntegration will be imported when needed
            import session_mgmt_mcp.crackerjack_integration  # noqa: F401

            output += "✅ **Integration Module**: Available\n"
        except ImportError:
            output += "❌ **Integration Module**: Not available\n"

        # Check reflection database for history
        try:
            from session_mgmt_mcp.reflection_tools import ReflectionDatabase

            db = ReflectionDatabase()
            async with db:
                # Quick test
                stats = await db.get_stats()
                output += "✅ **History Storage**: Available\n"
                output += f"   Conversations: {stats.get('conversation_count', 0)}\n"
        except Exception as e:
            output += f"⚠️ **History Storage**: Limited - {e!s}\n"

        output += "\n**Recommendations**:\n"
        output += "- Run `crackerjack -t` to test full functionality\n"
        output += "- Use `crackerjack_run` for enhanced analytics\n"
        output += "- Check `crackerjack_history` for execution patterns\n"

        return output

    # Alias for backward compatibility
    @mcp.tool()
    async def quality_monitor() -> str:
        """Phase 3: Proactive quality monitoring with early warning system."""
        return await crackerjack_health_check()
