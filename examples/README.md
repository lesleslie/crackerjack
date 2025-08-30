# Crackerjack Examples

This directory contains practical examples demonstrating Crackerjack's features and capabilities.

## Plugin System Examples

### Hook Plugins

- **[`custom_hook_plugin.py`](custom_hook_plugin.py)** - Complete custom hook plugin implementation

  - Shows custom hook definitions for TODO/FIXME checking, print statement detection, and JSON validation
  - Demonstrates plugin metadata, activation/deactivation, and custom execution logic
  - Uses modern plugin architecture with `HookPluginBase` and `CustomHookDefinition`

- **[`plugin_config.json`](plugin_config.json)** - Configuration-based hook definitions

  - Example JSON configuration for defining hooks without writing Python code
  - Shows file size checking and security scanning hook configurations
  - Demonstrates `fast` vs `comprehensive` stage assignments

## Progress Monitoring Examples

### Real-Time Progress Display

- **[`enhanced_monitor_demo.py`](enhanced_monitor_demo.py)** - Enhanced multi-project monitor demonstration

  - Shows AsyncIO-based progress monitoring with Textual TUI support
  - Includes command-line options for refresh rate and display mode
  - Demonstrates integration with `crackerjack.mcp.enhanced_progress_monitor`

- **[`enhanced_monitor_demo_fixed.py`](enhanced_monitor_demo_fixed.py)** - Improved monitor demo

  - Fixed version with better error handling and timeout protection
  - Shows watchdog service integration and graceful shutdown
  - Includes WebSocket connection with fallback mechanisms

### Progress API Integration

- **[`enhanced_progress_example.py`](enhanced_progress_example.py)** - WebSocket progress monitoring example

  - Demonstrates WebSocket-based real-time progress updates
  - Shows Rich console formatting with progress bars and displays
  - Includes API integration patterns and feature detection

- **[`slash_command_progress_example.py`](slash_command_progress_example.py)** - Simulated MCP progress polling

  - Shows realistic progress sequence with multiple stages
  - Demonstrates progress display with iteration tracking
  - Useful for understanding AI agent workflow progress

- **[`test_progress_display.py`](test_progress_display.py)** - Progress display testing utility

  - Simple demonstration of progress state transitions
  - Shows different stages: fast_hooks, comprehensive_hooks, tests, analyzing, fixing
  - Useful for testing progress display components

## MCP Integration Examples

### Client Integration

- **[`mcp_client_example.py`](mcp_client_example.py)** - Complete MCP client implementation
  - Shows autonomous quality workflow with intelligent retry logic
  - Demonstrates stage-based execution: fast hooks → tests → comprehensive hooks
  - Includes error analysis and auto-fix application patterns
  - Uses modern async HTTP client with proper error handling

### Orchestrated Workflows

- **[`orchestrated_workflow_demo.py`](orchestrated_workflow_demo.py)** - Advanced workflow orchestration
  - Shows `AdvancedWorkflowOrchestrator` with intelligent coordination
  - Demonstrates execution strategies: BATCH, INDIVIDUAL, ADAPTIVE, SELECTIVE
  - Includes progress levels: BASIC, DETAILED, GRANULAR, STREAMING
  - Shows AI coordination modes and advanced configuration options

## Running the Examples

### Prerequisites

Ensure Crackerjack is installed and properly configured:

```bash
pip install crackerjack
# or
uv add crackerjack
```

### Plugin Examples

```bash
# Test the custom hook plugin
python examples/custom_hook_plugin.py

# The plugin will be automatically discovered if placed in:
# - Project plugins/ directory
# - ~/.config/crackerjack/plugins/
# - System-wide plugin directories
```

### Progress Monitoring Examples

```bash
# Enhanced monitor with Textual TUI
python examples/enhanced_monitor_demo.py --textual

# Fixed monitor demo with watchdog
python examples/enhanced_monitor_demo_fixed.py --no-clear

# Progress display demonstration
python examples/test_progress_display.py

# WebSocket progress features demo
python examples/enhanced_progress_example.py
```

### MCP Integration Examples

```bash
# Start MCP server first
python -m crackerjack --start-mcp-server

# Then run MCP client example (in separate terminal)
python examples/mcp_client_example.py

# Orchestrated workflow demonstration
python examples/orchestrated_workflow_demo.py
```

## Example Integration Patterns

### 1. Custom Hook Plugin Pattern

```python
from crackerjack.plugins import HookPluginBase, CustomHookDefinition
from crackerjack.models.task import HookResult


class MyHookPlugin(HookPluginBase):
    def get_hook_definitions(self) -> list[CustomHookDefinition]:
        return [
            CustomHookDefinition(
                name="my-custom-hook",
                description="My custom validation",
                command=["my-validator"],
                file_patterns=["*.py"],
                stage=HookStage.FAST,
            )
        ]
```

### 2. Progress Monitor Integration Pattern

```python
from crackerjack.mcp.enhanced_progress_monitor import run_enhanced_monitor

await run_enhanced_monitor(
    clear_terminal=True,
    use_textual=True,
    refresh_interval=0.5,
    enable_watchdog=True,
)
```

### 3. MCP Client Integration Pattern

```python
class MyMCPClient:
    async def run_quality_workflow(self):
        # Run stages in order with intelligent retry
        fast_result = await self.run_stage("fast")
        if fast_result["success"]:
            test_result = await self.run_stage("tests")
            if test_result["success"]:
                comp_result = await self.run_stage("comprehensive")
        return {"status": "success"}
```

## Architecture Integration

These examples demonstrate integration with Crackerjack's modular architecture:

- **Plugin System**: Custom hooks and configuration-based plugins
- **MCP Server**: WebSocket-based real-time progress and tool integration
- **Progress Monitoring**: Rich display with async updates and fallback handling
- **Workflow Orchestration**: Intelligent stage coordination with AI agent integration
- **Error Recovery**: Graceful failure handling with automatic retry logic

## Development and Testing

All examples are maintained to use current Crackerjack APIs and architecture patterns. They serve as:

- **Integration Tests**: Verify API compatibility and feature functionality
- **Documentation**: Show real-world usage patterns and best practices
- **Development Tools**: Help test new features and debug issues
- **Learning Resources**: Demonstrate advanced integration techniques

For more information, see the main [README.md](../README.md) and [CLAUDE.md](../CLAUDE.md) documentation.
