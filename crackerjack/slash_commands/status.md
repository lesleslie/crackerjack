______________________________________________________________________

## description: Check comprehensive Crackerjack system status including running jobs, MCP server health, WebSocket connections, and progress monitoring with real-time updates.

# /crackerjack:status - Comprehensive System Status

Check the comprehensive status of the Crackerjack system including running jobs, MCP server health, WebSocket server status, and progress monitoring. This command provides real-time status from all system components.

## Usage

```
/crackerjack:status
```

## What This Command Does

1. **MCP Server Status** - Shows running processes, health, and resource usage
1. **WebSocket Server Status** - Displays connection status, port, and active monitoring
1. **Job Management** - Lists all active, completed, and failed jobs with detailed progress
1. **Progress Tracking** - Shows iteration counts, stage completion, and error resolution metrics
1. **System Health** - Comprehensive monitoring of all Crackerjack services and components
1. **Resource Usage** - Memory, CPU, and temporary file statistics

## Example Output

The command will show information like:

```json
{
  "services": {
    "mcp_server": {
      "running": true,
      "processes": [
        {
          "pid": 12345,
          "cpu": "0.5%",
          "mem": "0.8%",
          "command": "python -m crackerjack --start-mcp-server"
        }
      ]
    },
    "websocket_server": {
      "running": true,
      "port": 8675,
      "processes": [
        {
          "pid": 12346,
          "cpu": "0.2%",
          "mem": "0.6%"
        }
      ]
    }
  },
  "jobs": {
    "active_count": 2,
    "completed_count": 1,
    "failed_count": 0,
    "details": [
      {
        "job_id": "abc123-def456-ghi789",
        "status": "running",
        "iteration": 3,
        "max_iterations": 10,
        "current_stage": "comprehensive_hooks",
        "overall_progress": 30,
        "stage_progress": 75,
        "message": "Running pyright type checking...",
        "error_counts": {
          "hook_errors": 0,
          "test_failures": 2,
          "total": 13
        }
      }
    ]
  },
  "server_stats": {
    "resource_usage": {
      "temp_files_count": 5,
      "progress_dir": "/tmp/crackerjack-mcp-progress"
    },
    "rate_limiting": {
      "requests_per_minute": 60,
      "current_requests": 2,
      "can_execute": true
    }
  }
}
```

## When to Use

- **Before starting work** - Check if any jobs are already running
- **During development** - Monitor progress of long-running jobs
- **Troubleshooting** - Verify services are running correctly
- **Planning** - See completion status before starting new work

## Technical Implementation

This command uses the `get_comprehensive_status` MCP tool which:

- **Process Discovery**: Uses `ps aux` to find running Crackerjack processes
- **Progress File Analysis**: Reads job progress from `/tmp/crackerjack-mcp-progress/job-*.json` files
- **WebSocket Health**: Checks port availability and connection status
- **Resource Monitoring**: Tracks temporary files, memory usage, and rate limiting
- **State Management**: Integrates with MCP server state for session tracking

## Integration

This command integrates with:

- **WebSocket Progress Server** (localhost:8675)
- **MCP Server** progress and state files
- **Service Watchdog** monitoring
- **TUI Monitor** data sources
- **Server Manager** process discovery

The status information comes from the same sources that power the TUI monitor and web interface, ensuring consistent data across all interfaces.

## Usage in Claude Code

When using this command in Claude Code, the AI agent will:

1. Call the `get_comprehensive_status` MCP tool
1. Parse the JSON response for relevant information
1. Present a formatted summary of system health
1. Highlight any issues requiring attention
1. Suggest next actions based on current status
