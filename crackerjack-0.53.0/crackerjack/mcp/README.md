> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | [MCP](./README.md)

# MCP

Model Context Protocol (MCP) server implementation for AI agent interoperability and real-time workflow monitoring.

## Overview

The MCP package provides a comprehensive FastMCP server that enables Claude and other AI agents to interact directly with Crackerjack's quality enforcement tools. It includes WebSocket support for real-time progress monitoring, intelligent error caching, job tracking, and advanced workflow execution capabilities.

## Core Components

### Server Infrastructure

- **server.py / server_core.py**: Main FastMCP server entry point with tool registration
- **context.py**: MCP context management and session state tracking
- **state.py**: Global state management for jobs, sessions, and progress
- **cache.py**: Error pattern caching and intelligent analysis recommendations
- **rate_limiter.py**: Request rate limiting and abuse prevention
- **client_runner.py**: MCP client runner for testing and development

### WebSocket & Monitoring

- **websocket_server.py**: WebSocket server for real-time progress streaming
- **progress_monitor.py**: Real-time job progress monitoring and display
- **enhanced_progress_monitor.py**: Enhanced monitoring with pattern analysis
- **progress_components.py**: Reusable UI components for progress display
- **file_monitor.py**: File system monitoring for code changes
- **dashboard.py**: Comprehensive monitoring dashboard

### Workflow & Execution

- **task_manager.py**: Async task management and job coordination
- **service_watchdog.py**: Service health monitoring and auto-restart
- **tools/**: MCP tool implementations organized by category

## MCP Tools

Tools are organized into specialized modules:

### Core Tools (`tools/core_tools.py`)

- **execute_crackerjack**: Start iterative auto-fixing with job tracking
- **run_crackerjack_stage**: Execute specific quality stages (fast, comprehensive, tests)
- **get_comprehensive_status**: Full project status including health metrics
- **session_management**: Session lifecycle (start, checkpoint, resume, end)

### Execution Tools (`tools/execution_tools.py`)

- Workflow execution with subagent coordination
- Stage validation and argument parsing
- Settings adaptation for different execution modes

### Error Analysis (`tools/error_analyzer.py`)

- **analyze_errors**: Categorize and analyze code quality errors
- **analyze_errors_with_caching**: AI-powered error analysis with cached patterns
- Pattern detection and recommendation generation
- Error classification by type (security, performance, complexity, etc.)

### Progress Tools (`tools/progress_tools.py`)

- **get_job_progress**: Real-time progress for running jobs
- **get_stage_status**: Current status of quality stages
- Job metadata and completion tracking

### Intelligence Tools (`tools/intelligence_tools.py`)

- **get_next_action**: Optimal next action based on session state
- **smart_error_analysis**: Advanced error analysis with context
- Intelligent recommendations and fix suggestions

### Monitoring Tools (`tools/monitoring_tools.py`)

- Health metrics collection and reporting
- Performance tracking
- Resource usage monitoring

### Semantic Tools (`tools/semantic_tools.py`)

- Code comprehension and semantic analysis
- Context-aware recommendations
- Pattern recognition and suggestions

### Proactive Tools (`tools/proactive_tools.py`)

- Predictive issue prevention
- Preemptive optimization suggestions
- Pattern-based early detection

### Utility Tools (`tools/utility_tools.py`)

- Helper functions for tool development
- Common validation and formatting utilities

## Architecture

### Dual Protocol Support

The MCP server supports both standard MCP protocol and WebSocket for different use cases:

```python
# Standard MCP (stdio-based)
# Used by: Claude Desktop, MCP clients
# Protocol: JSON-RPC over stdio
python -m crackerjack --start-mcp-server

# WebSocket-enabled MCP
# Used by: Real-time progress monitoring, dashboards
# Protocol: WebSocket on localhost:8675
# Endpoints: /ws/progress/{job_id}
```

### Job Tracking System

Jobs are tracked through their complete lifecycle:

```python
# Job states
JobState.PENDING → JobState.RUNNING → JobState.COMPLETED
                                     → JobState.FAILED
                                     → JobState.CANCELLED

# Progress tracking
{
    "job_id": "uuid",
    "state": "RUNNING",
    "progress": 0.65,  # 0.0 to 1.0
    "current_phase": "comprehensive_hooks",
    "issues_fixed": 42,
    "total_issues": 100
}
```

### Error Pattern Caching

Intelligent caching system learns from error patterns:

```python
# Cache structure
{
    "error_hash": "sha256(error_pattern)",
    "category": "security|performance|complexity|...",
    "recommendations": ["Fix 1", "Fix 2"],
    "confidence": 0.85,
    "occurrences": 12,
    "last_seen": datetime,
}
```

## Usage

### Starting the MCP Server

```bash
# Start MCP server
python -m crackerjack start

# Restart server
python -m crackerjack restart

# Stop server
python -m crackerjack stop

# Check server status
python -m crackerjack status

# Health check
python -m crackerjack health
```

### MCP Client Configuration

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "uvx",
      "args": [
        "crackerjack",
        "start"
      ],
      "env": {
        "UV_KEYRING_PROVIDER": "subprocess",
        "EDITOR": "code --wait"
      }
    }
  }
}
```

### Using MCP Tools

From Claude or other MCP clients:

```python
# Execute quality workflow
execute_crackerjack(command="test", ai_agent_mode=True, timeout=600)

# Get job progress
progress = get_job_progress(job_id="abc123")

# Analyze errors with AI
analysis = analyze_errors_with_caching(
    errors=["Type error on line 42"], context={"file": "main.py"}
)

# Get smart recommendations
action = get_next_action(session_id="xyz789")
```

## Slash Commands

MCP integrates with crackerjack slash commands:

- `/crackerjack:run` — Autonomous code quality enforcement with AI agent
- `/crackerjack:init` — Initialize or update project configuration
- `/crackerjack:status` — Check current workflow status

See `crackerjack/slash_commands/` for implementation details.

## Security

### Rate Limiting

Built-in rate limiting prevents abuse:

```python
# Default limits
max_requests_per_minute = 60
max_concurrent_jobs = 5
max_job_duration = 3600  # 1 hour
```

### Input Validation

All MCP tool inputs are validated:

- JSON schema validation
- Type checking
- Size limits
- Injection prevention

## Configuration

MCP settings in `settings/crackerjack.yaml`:

```yaml
# MCP Server
mcp_server_enabled: true
mcp_max_concurrent_jobs: 5

# Error Caching
error_cache_size: 1000
error_cache_ttl: 3600  # seconds
```

## Performance

Typical MCP server performance:

- **Tool Execution**: < 100ms for metadata tools
- **Job Creation**: < 50ms overhead
- **Error Analysis**: 200-500ms with caching
- **Concurrent Jobs**: Up to 5 simultaneous workflows

## Tools Subdirectories

- `tools/` — Main tools directory
  - `README.md` — Tool development guide

## Best Practices

1. **Use Job IDs**: Always track jobs by their UUIDs
1. **Monitor Progress**: Use `get_job_progress` tool for job status
1. **Handle Errors**: Check job status and error messages
1. **Cache Patterns**: Let error caching learn common issues
1. **Session Management**: Use checkpoints for resumability
1. **Rate Limits**: Respect rate limits in automation

## Troubleshooting

### Server Won't Start

```bash
# Check server status
python -m crackerjack status

# View server logs
python -m crackerjack start --verbose

# Force restart
python -m crackerjack restart
```

### Job Stuck

```bash
# Check job status
get_job_progress(job_id="abc123")

# View comprehensive status
get_comprehensive_status()

# If necessary, restart server
python -m crackerjack restart
```

## Related

- [Agents](../agents/README.md) — AI agents that MCP coordinates

- [Slash Commands](../slash_commands/README.md) — MCP slash command implementations

- [Main README](../../README.md) — MCP integration overview

## Future Enhancements

- [ ] Multi-user support with authentication
- [ ] Distributed job execution across machines
- [ ] Persistent job history database
- [ ] Advanced analytics dashboard
- [ ] Plugin system for custom tools
- [ ] OpenTelemetry integration for observability
