#!/usr/bin/env python3
"""MCP prompt management tools.

This module provides all MCP prompt definitions following crackerjack
architecture patterns with single responsibility principle.
"""

from __future__ import annotations

from session_mgmt_mcp.session_commands import SESSION_COMMANDS


def register_prompt_tools(mcp) -> None:
    """Register all MCP prompt definitions.

    Args:
        mcp: FastMCP server instance

    """

    @mcp.prompt("init")
    async def get_session_init_prompt() -> str:
        """Initialize Claude session with comprehensive setup including UV dependencies, global workspace verification, and automation tools."""
        return SESSION_COMMANDS["init"]

    @mcp.prompt("checkpoint")
    async def get_session_checkpoint_prompt() -> str:
        """Perform mid-session quality checkpoint with workflow analysis and optimization recommendations."""
        return SESSION_COMMANDS["checkpoint"]

    @mcp.prompt("end")
    async def get_session_end_prompt() -> str:
        """End Claude session with cleanup, learning capture, and handoff file creation."""
        return SESSION_COMMANDS["end"]

    @mcp.prompt("status")
    async def get_session_status_prompt() -> str:
        """Get current session status and project context information with health checks."""
        return SESSION_COMMANDS["status"]

    @mcp.prompt("permissions")
    async def get_session_permissions_prompt() -> str:
        """Manage session permissions for trusted operations to avoid repeated prompts."""
        return SESSION_COMMANDS["permissions"]

    @mcp.prompt("reflect")
    async def get_session_reflect_prompt() -> str:
        """Search past conversations and store reflections with semantic similarity."""
        return SESSION_COMMANDS["reflect"]

    @mcp.prompt("quick-search")
    async def get_session_quick_search_prompt() -> str:
        """Quick search that returns only the count and top result for fast overview."""
        return SESSION_COMMANDS["quick-search"]

    @mcp.prompt("search-summary")
    async def get_session_search_summary_prompt() -> str:
        """Get aggregated insights from search results without individual result details."""
        return SESSION_COMMANDS["search-summary"]

    @mcp.prompt("reflection-stats")
    async def get_session_reflection_stats_prompt() -> str:
        """Get statistics about the reflection database and conversation memory."""
        return SESSION_COMMANDS["reflection-stats"]

    @mcp.prompt("crackerjack-run")
    async def get_crackerjack_run_prompt() -> str:
        """Execute a Crackerjack command and parse the output for insights."""
        return SESSION_COMMANDS["crackerjack-run"]

    @mcp.prompt("crackerjack-history")
    async def get_crackerjack_history_prompt() -> str:
        """Get recent Crackerjack command execution history with parsed results."""
        return SESSION_COMMANDS["crackerjack-history"]

    @mcp.prompt("crackerjack-metrics")
    async def get_crackerjack_metrics_prompt() -> str:
        """Get quality metrics trends from Crackerjack execution history."""
        return SESSION_COMMANDS["crackerjack-metrics"]

    @mcp.prompt("crackerjack-patterns")
    async def get_crackerjack_patterns_prompt() -> str:
        """Analyze test failure patterns and trends for debugging insights."""
        return SESSION_COMMANDS["crackerjack-patterns"]

    @mcp.prompt("compress-memory")
    async def get_compress_memory_prompt() -> str:
        """Compress conversation memory by consolidating old conversations into summaries."""
        return """# Memory Compression

Compress conversation memory by consolidating old conversations into summaries.

This command will:
- Analyze conversation age and importance
- Group related conversations into clusters
- Create consolidated summaries of old conversations
- Remove redundant conversation data
- Calculate space savings and compression ratios

Examples:
- Default compression: compress_memory()
- Preview changes: dry_run=True
- Aggressive compression: max_age_days=14, importance_threshold=0.5

Use this periodically to keep your conversation memory manageable and efficient."""

    @mcp.prompt("compression-stats")
    async def get_compression_stats_prompt() -> str:
        """Get detailed statistics about memory compression history and current database status."""
        return """# Compression Statistics

Get detailed statistics about memory compression history and current database status.

This command will:
- Show last compression run details
- Display space savings and compression ratios
- Report current database size and conversation count
- Show number of consolidated conversations
- Provide compression efficiency metrics

Use this to monitor memory usage and compression effectiveness."""

    @mcp.prompt("retention-policy")
    async def get_retention_policy_prompt() -> str:
        """Configure memory retention policy parameters for automatic compression."""
        return """# Retention Policy

Configure memory retention policy parameters for automatic compression.

This command will:
- Set maximum conversation age and count limits
- Configure importance threshold for retention
- Define consolidation age triggers
- Adjust compression ratio targets

Examples:
- Conservative: max_age_days=365, importance_threshold=0.2
- Aggressive: max_age_days=90, importance_threshold=0.5
- Custom: consolidation_age_days=14

Use this to customize how your conversation memory is managed over time."""

    @mcp.prompt("auto-load-context")
    async def get_auto_load_context_prompt() -> str:
        """Automatically detect current development context and load relevant conversations."""
        return """# Auto-Context Loading

Automatically detect current development context and load relevant conversations.

This command will:
- Analyze your current project structure and files
- Detect programming languages and tools in use
- Identify project type (web app, CLI tool, library, etc.)
- Find recent file modifications
- Load conversations relevant to your current context
- Score conversations by relevance to current work

Examples:
- Load default context: auto_load_context()
- Increase results: max_conversations=20
- Lower threshold: min_relevance=0.2

Use this at the start of coding sessions to get relevant context automatically."""

    @mcp.prompt("context-summary")
    async def get_context_summary_prompt() -> str:
        """Get a quick summary of your current development context without loading conversations."""
        return """# Context Summary

Get a quick summary of your current development context without loading conversations.

This command will:
- Detect current project name and type
- Identify programming languages and tools
- Show Git repository information
- Display recently modified files
- Calculate detection confidence score

Use this to understand what context the system has detected about your current work."""

    @mcp.prompt("search-code")
    async def get_search_code_prompt() -> str:
        """Search for code patterns in conversations using AST parsing."""
        return """# Code Pattern Search

Search for code patterns in your conversation history using AST (Abstract Syntax Tree) parsing.

This command will:
- Parse Python code blocks from conversations
- Extract functions, classes, imports, loops, and other patterns
- Rank results by relevance to your query
- Show code context and project information

Examples:
- Search for functions: pattern_type='function'
- Search for class definitions: pattern_type='class'
- Search for error handling: query='try except'

Use this to find code examples and patterns from your development sessions."""

    @mcp.prompt("search-errors")
    async def get_search_errors_prompt() -> str:
        """Search for error patterns and debugging contexts in conversations."""
        return """# Error Pattern Search

Search for error messages, exceptions, and debugging contexts in your conversation history.

This command will:
- Find Python tracebacks and exceptions
- Detect JavaScript errors and warnings
- Identify debugging and testing contexts
- Show error context and solutions

Examples:
- Find Python errors: error_type='python_exception'
- Find import issues: query='ImportError'
- Find debugging sessions: query='debug'

Use this to quickly find solutions to similar errors you've encountered before."""

    @mcp.prompt("search-temporal")
    async def get_search_temporal_prompt() -> str:
        """Search conversations within a specific time range using natural language."""
        return """# Temporal Search

Search your conversation history using natural language time expressions.

This command will:
- Parse time expressions like "yesterday", "last week", "2 days ago"
- Find conversations within that time range
- Optionally filter by additional search terms
- Sort results by time and relevance

Examples:
- "yesterday" - conversations from yesterday
- "last week" - conversations from the past week
- "2 days ago" - conversations from 2 days ago
- "this month" + query - filter by content within the month

Use this to find recent discussions or work from specific time periods."""

    @mcp.prompt("start-app-monitoring")
    async def get_start_app_monitoring_prompt() -> str:
        """Start monitoring IDE activity and browser documentation usage."""
        return """# Start Application Monitoring

Monitor your development activity to provide better context and insights.

This command will:
- Start file system monitoring for code changes
- Track application focus (IDE, browser, terminal)
- Monitor documentation site visits
- Build activity profiles for better context

Monitoring includes:
- File modifications in your project directories
- IDE and editor activity patterns
- Browser navigation to documentation sites
- Application focus and context switching

Use this to automatically capture your development context for better session insights."""

    @mcp.prompt("stop-app-monitoring")
    async def get_stop_app_monitoring_prompt() -> str:
        """Stop all application monitoring."""
        return """# Stop Application Monitoring

Stop monitoring your development activity.

This command will:
- Stop file system monitoring
- Stop application focus tracking
- Preserve collected activity data
- Clean up monitoring resources

Use this when you want to pause monitoring or when you're done with a development session."""

    @mcp.prompt("activity-summary")
    async def get_activity_summary_prompt() -> str:
        """Get activity summary for recent development work."""
        return """# Activity Summary

Get a comprehensive summary of your recent development activity.

This command will:
- Show file modification patterns
- List most active applications
- Display visited documentation sites
- Calculate productivity metrics

Summary includes:
- Event counts by type and application
- Most actively edited files
- Documentation resources consulted
- Average relevance scores

Use this to understand your development patterns and identify productive sessions."""

    @mcp.prompt("context-insights")
    async def get_context_insights_prompt() -> str:
        """Get contextual insights from recent activity."""
        return """# Context Insights

Analyze recent development activity for contextual insights.

This command will:
- Identify primary focus areas
- Detect technologies being used
- Count context switches
- Calculate productivity scores

Insights include:
- Primary application focus
- Active programming languages
- Documentation topics explored
- Project switching patterns
- Overall productivity assessment

Use this to understand your current development context and optimize your workflow."""

    @mcp.prompt("active-files")
    async def get_active_files_prompt() -> str:
        """Get files currently being worked on."""
        return """# Active Files

Show files that are currently being actively worked on.

This command will:
- List recently modified files
- Show activity scores and patterns
- Highlight most frequently changed files
- Include project context

File activity is scored based on:
- Frequency of modifications
- Recency of changes
- File type and relevance
- Project context

Use this to quickly see what you're currently working on and resume interrupted tasks."""

    @mcp.prompt("quality-monitor")
    async def get_quality_monitor_prompt() -> str:
        """Proactive session quality monitoring with trend analysis and early warnings."""
        return """# Quality Monitor

Phase 3: Proactive quality monitoring with early warning system.

This command will:
- Monitor code quality trends in real-time
- Detect quality degradation early
- Provide alerts for potential issues
- Generate improvement recommendations
- Track quality metrics over time

Use this for continuous quality assurance during development."""

    @mcp.prompt("auto-compact")
    async def get_auto_compact_prompt() -> str:
        """Automatically trigger conversation compaction with context preservation."""
        return """# Auto Compact

Automatically trigger conversation compaction with intelligent summary.

This command will:
- Analyze conversation length and complexity
- Identify consolidation opportunities
- Preserve important context and decisions
- Compress redundant information
- Maintain searchable history

Use this to manage conversation memory efficiently."""
