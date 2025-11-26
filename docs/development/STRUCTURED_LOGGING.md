# Crackerjack Structured Logging with Structlog

## Overview

Crackerjack now leverages the advanced structured logging capabilities provided by the ACB (AI-Centric Building blocks) project, specifically using structlog. This provides enhanced logging features that are optimized for AI agent consumption as well as human readability.

## Key Features

### 1. Dual Output Strategy

- **Human Output**: Standard console output via Rich for readable UI
- **AI/Machine Output**: Structured JSON logs to stderr for AI agent consumption

### 2. Structured Logging Benefits

- **Machine-Readable**: JSON format suitable for parsing by AI agents
- **Context-Rich**: Includes metadata like correlation IDs, performance metrics, and operation context
- **Searchable**: Structured format enables efficient querying of log data

### 3. AI-Optimized Logging

- Specialized logging for `--ai-fix` and `--ai-debug` modes
- Structured events for AI agent fixing phases
- Detailed metrics for AI decision making

## Usage

### Enabling Structured Logging

Structured logging is automatically enabled when using AI-related flags:

```bash
# Enable AI agent fixing with structured logging
python -m crackerjack --ai-fix --verbose

# Enable AI debug mode with enhanced structured logging
python -m crackerjack --ai-debug --run-tests

# Both flags together provide maximum debugging information
python -m crackerjack --ai-fix --ai-debug --run-tests
```

### AI Agent Fixing Phase Logging

When using `--ai-fix`, enhanced structured logs include:

- AI agent fixing phase start/end events
- Fix counts and success metrics
- Error information with context
- Performance metrics for AI operations

### Debug Mode Logging

When using `--ai-debug`, logs include:

- Detailed workflow progression information
- AI decision making processes
- Error details with traceback capability
- Performance metrics and timing information

## JSON Format for AI Consumption

The structured logs output to stderr follow this format:

```json
{
  "timestamp": "2025-01-01T00:00:00.000000Z",
  "level": "INFO",
  "event": "crackerjack.module.function",
  "message": "Descriptive message",
  "attributes": {
    "line": 123,
    "module": "module_name",
    "pathname": "/path/to/file.py",
    "ai_agent_fixing": true,
    "event_type": "ai_fix_start",
    "correlation_id": "unique-correlation-id"
  },
  "version": "1.0.0"
}
```

## Integration Points

### Agent Coordinator Updates

- The `AgentCoordinator` and `EnhancedAgentCoordinator` now use structured logging
- AI agent activities are logged with rich context information
- Performance metrics for individual agents are captured

### Workflow Orchestrator Updates

- AI fixing phases include detailed structured logging
- Error handling provides contextual information for AI agents
- Performance metrics are logged in structured format

## Best Practices

1. **For AI Agent Integration**: Use `--ai-fix` and `--ai-debug` flags together for maximum visibility into the AI decision-making process.

1. **For Troubleshooting**: Enable `--ai-debug` to get detailed structured logs about the workflow execution.

1. **For Monitoring**: The JSON output to stderr can be easily consumed by monitoring and analysis tools.

## Advanced Configuration

The logging system can be configured through the ACB settings system. For custom configurations, see the ACB documentation for logger settings.
