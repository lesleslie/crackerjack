# AI Agent Debugging Guide

This document explains the enhanced debugging capabilities for Crackerjack's AI agent mode, designed to provide detailed visibility into MCP server operations and sub-agent activities.

## Quick Start

Enable AI agent debugging with comprehensive output:

```bash
# Enable AI agent mode with full debugging
python -m crackerjack --ai-debug -t

# Or use the traditional flags
python -m crackerjack --ai-agent --verbose -t
```

## Debug Modes

### 1. Standard Mode (`--ai-agent`)

- Basic AI agent functionality
- Standard console output
- Minimal debugging information

### 2. Debug Mode (`--ai-debug`)

- **Implies `--ai-agent` and `--verbose`**
- Detailed console output during execution
- Comprehensive debug logging to file
- Real-time progress information
- Agent activity tracking
- MCP operation monitoring

### 3. Verbose Mode (`--verbose`)

- Enhanced console output
- Detailed operation timings
- Agent confidence scores
- Workflow phase transitions

## What Gets Debugged

### MCP Server Operations

- **Tool Calls**: All MCP tool invocations with parameters and results
- **Execution Times**: Duration of each MCP operation
- **Error Tracking**: Detailed error information when operations fail
- **Progress Updates**: Real-time job progress and status changes

### Sub-Agent Activities

- **Agent Assignment**: Which agents are selected for specific issues
- **Confidence Scores**: How confident each agent is about handling issues
- **Processing Events**: Start/completion of agent processing
- **Collaboration**: When multiple agents work together
- **Cache Operations**: Hit/miss statistics for issue caching

### Workflow Phases

- **Phase Transitions**: Start/completion of each workflow phase
- **Timing Information**: Duration of each phase
- **Success/Failure Status**: Detailed status reporting
- **Configuration Details**: Options and settings used

## Debug Output Locations

### Console Output

When `--ai-debug` or `--verbose` is enabled, you'll see:

- Real-time agent activity updates
- MCP operation status
- Workflow phase transitions
- Error events with context

### Debug Log Files

Automatically created debug logs:

- `crackerjack-ai-debug-{session_id}.log` - Comprehensive debug log
- Contains structured logging with timestamps and context
- Includes all MCP operations, agent activities, and workflow events

### Debug Summary

At the end of execution, a comprehensive summary shows:

- Total MCP operations and tools used
- Agent activity breakdown with confidence scores
- Workflow phase completion status
- Error event summary

## Environment Variables

The debug system uses these environment variables (set automatically):

```bash
AI_AGENT=1              # Enables AI agent mode
AI_AGENT_DEBUG=1        # Enables debug logging
AI_AGENT_VERBOSE=1      # Enables verbose console output
```

## Debug Data Export

The debug system can export all collected data:

```python
from crackerjack.services.debug import get_ai_agent_debugger

debugger = get_ai_agent_debugger()
export_path = debugger.export_debug_data()
print(f"Debug data exported to: {export_path}")
```

## Understanding Debug Output

### Agent Activity Examples

```
🤖 FormattingAgent: processing_started (confidence: 0.95) [issue: FMT001]
🤖 FormattingAgent: processing_completed (confidence: 0.95) [issue: FMT001]
```

### MCP Operation Examples

```
✅ MCP tool_call: execute_crackerjack (2.34s)
❌ MCP tool_call: analyze_errors (0.12s)
   Error: Connection timeout
```

### Workflow Phase Examples

```
📋 Workflow started: fast_hooks
📋 Workflow completed: fast_hooks (5.23s)
📋 Workflow failed: comprehensive_hooks (12.45s)
```

## Debug Summary Breakdown

The debug summary provides:

| Category | Description |
|----------|-------------|
| **MCP Operations** | Total tool calls, unique tools used |
| **Agent Activities** | Total activities, active agents count |
| **Workflow Phases** | Total phases, completed count |
| **Error Events** | Total errors, unique error types |

### Agent Activity Breakdown

Shows per-agent statistics:

- Number of activities
- Average confidence score
- Success rate

### MCP Tool Usage

Shows per-tool statistics:

- Number of calls
- Error count
- Average execution time

## Troubleshooting with Debug Mode

### Common Debugging Scenarios

1. **Agent Selection Issues**

   - Check confidence scores in debug output
   - Review agent activity breakdown
   - Look for collaboration events

1. **MCP Communication Problems**

   - Monitor MCP operation timings
   - Check for error patterns in tool calls
   - Review connection status

1. **Performance Issues**

   - Analyze phase durations
   - Check agent processing times
   - Review cache hit/miss ratios

1. **Workflow Failures**

   - Follow workflow phase transitions
   - Check error events for root causes
   - Review retry patterns

### Debug Log Analysis

The debug log contains structured entries:

```
2024-01-15T10:30:45.123 | crackerjack.agents | INFO | Agent processing_started: FormattingAgent
2024-01-15T10:30:45.456 | crackerjack.mcp | INFO | MCP tool_call: execute_crackerjack
```

Each entry includes:

- Timestamp
- Logger name (component)
- Log level
- Detailed message with context

## Performance Impact

Debug mode adds minimal overhead:

- **Console Output**: ~5-10ms per message
- **File Logging**: ~1-2ms per log entry
- **Summary Generation**: ~50-100ms total
- **Memory Usage**: ~1-5MB for typical sessions

Debug mode is designed to be safe for production troubleshooting when needed.

## Integration with Other Tools

### MCP Progress Monitoring

Debug information integrates with:

- WebSocket progress streaming
- Progress monitor TUI
- Service watchdog

### Log Aggregation

Debug logs can be consumed by:

- ELK Stack (Elasticsearch, Logstash, Kibana)
- Grafana + Loki
- CloudWatch Logs
- Custom log analysis tools

## Best Practices

1. **Enable debug mode when troubleshooting** issues with AI agent workflows
1. **Use verbose mode** for development and testing
1. **Export debug data** for offline analysis of complex issues
1. **Monitor debug summaries** to understand agent performance patterns
1. **Correlate debug logs** with MCP server logs for complete visibility

## Advanced Configuration

For fine-tuned debugging control:

```python
from crackerjack.services.debug import enable_ai_agent_debugging

# Enable with custom settings
debugger = enable_ai_agent_debugging(verbose=True)

# Log custom events
debugger.log_agent_activity(
    agent_name="CustomAgent",
    activity="custom_processing",
    confidence=0.8,
    metadata={"custom_data": "value"},
)
```
