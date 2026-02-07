# ADR-001: MCP-First Architecture with FastMCP

## Status

**Accepted** - 2025-01-15

## Context

Crackerjack needed to integrate with AI agents (Claude, Qwen) for autonomous code quality enforcement. The Model Context Protocol (MCP) emerged as the standard for AI tool integration, but several architectural approaches needed consideration.

### Problem Statement

How should Crackerjack expose its capabilities to AI agents while maintaining:

1. **Performance**: Minimal overhead during quality checks
2. **Security**: Safe code execution with proper validation
3. **Extensibility**: Easy addition of new tools and capabilities
4. **Developer Experience**: Simple integration for AI agents
5. **Separation of Concerns**: Clear boundary between CLI and MCP interfaces

### Key Requirements

- AI agents must be able to trigger quality checks asynchronously
- Real-time progress tracking for long-running operations
- Structured error output for programmatic analysis
- Support for both interactive and batch workflows
- Backward compatibility with existing CLI commands

## Decision Drivers

| Driver | Importance | Rationale |
|--------|------------|-----------|
| **Performance** | High | Quality checks must remain fast (<5s for fast hooks) |
| **Developer Experience** | High | Simple API for AI agents to consume |
| **Security** | Critical | Prevent arbitrary code execution |
| **Extensibility** | High | Easy to add new tools without breaking changes |
| **Maintainability** | Medium | Clear separation of MCP and CLI concerns |

## Considered Options

### Option 1: Stdio-based MCP Server (Rejected)

**Description**: Use stdio transport for MCP communication.

**Pros**:
- Simpler setup (no network ports)
- Built-in process isolation
- Standard MCP pattern

**Cons**:
- No persistent connection across sessions
- Difficult to query job status after initial request
- Harder to debug connection issues
- Limited concurrent client support

**Decision**: Rejected due to inability to track long-running operations across requests.

### Option 2: HTTP-based MCP Server (Rejected)

**Description**: Use HTTP transport with REST-like endpoints.

**Pros**:
- Easy to debug (can use curl/browser)
- Stateful connections
- Supports multiple concurrent clients

**Cons**:
- More complex deployment (port management)
- HTTP overhead for every call
- Authentication complexity
- No native MCP server lifecycle management

**Decision**: Rejected due to complexity and lack of native MCP support.

### Option 3: Hybrid MCP with WebSocket (SELECTED)

**Description**: Use FastMCP with both stdio and WebSocket transport, plus dedicated MCP server lifecycle commands.

**Pros**:
- **FastMCP**: Declarative tool registration with type safety
- **WebSocket transport**: Real-time progress updates
- **Dedicated lifecycle commands**: `start`, `stop`, `status`, `health`, `restart`
- **Job tracking**: Persistent job IDs for async operations
- **Backward compatible**: CLI remains unchanged
- **Security**: Localhost-only WebSocket by default

**Cons**:
- More complex implementation
- Requires WebSocket dependency
- Additional testing surface

**Decision**: Selected as best balance of performance, extensibility, and developer experience.

## Decision Outcome

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Agent (Claude/Qwen)                  │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP Protocol (stdio or WebSocket)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastMCP Server Layer                     │
│  ┌─────────────────┬─────────────────┬──────────────────┐  │
│  │  Tool Registry  │  Job Manager    │  Error Cache     │  │
│  │  (@mcp.tool)    │  (WebSocket)    │  (Pattern DB)    │  │
│  └─────────────────┴─────────────────┴──────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ Direct Python calls (no subprocess)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Crackerjack Core Layer                    │
│  ┌──────────────┬──────────────┬────────────────────────┐  │
│  │ CLI Handler  │   Pipeline   │  Quality Adapters      │  │
│  │  (Typer)     │  (Oneiric)   │  (Ruff/Zuban/Bandit)   │  │
│  └──────────────┴──────────────┴────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. MCP Server Lifecycle (New in Phase 3)

**File**: `crackerjack/mcp/server_lifecycle.py`

```python
class MCPServerLifecycle:
    """Manage MCP server startup, shutdown, and health checks."""

    async def start(self) -> None:
        """Initialize WebSocket server and register signal handlers."""

    async def stop(self, graceful: bool = True) -> None:
        """Shutdown server gracefully or forcefully."""

    async def health_check(self) -> HealthStatus:
        """Return server health status."""
```

**CLI Commands**:

```bash
python -m crackerjack start      # Start MCP server
python -m crackerjack stop       # Stop server
python -m crackerjack restart    # Restart server
python -m crackerjack status     # Server status
python -m crackerjack health     # Health check
```

#### 2. Tool Registration with FastMCP

**File**: `crackerjack/mcp/tools.py`

```python
from fastmcp import FastMCP

mcp = FastMCP("crackerjack")

@mcp.tool()
async def execute_crackerjack(
    command: str,
    args: str = "",
    ai_agent_mode: bool = False,
    timeout: int = 600,
) -> dict:
    """
    Execute crackerjack command with job tracking.

    Args:
        command: Command type (run, test, check, etc.)
        args: Additional command arguments
        ai_agent_mode: Enable AI agent mode with structured output
        timeout: Maximum execution time in seconds

    Returns:
        Job tracking dictionary with job_id and status
    """
    job_id = await job_manager.create_job(command, args)
    return {"job_id": job_id, "status": "started"}

@mcp.tool()
async def get_job_progress(job_id: str) -> dict:
    """Get real-time progress for a running job."""
    return await job_manager.get_progress(job_id)
```

#### 3. Job Manager with WebSocket

**File**: `crackerjack/mcp/job_manager.py`

```python
class JobManager:
    """Track async jobs and provide WebSocket progress updates."""

    async def create_job(self, command: str, args: str) -> str:
        """Create new job and return job_id."""

    async def update_progress(self, job_id: str, progress: float) -> None:
        """Broadcast progress via WebSocket."""

    async def complete_job(self, job_id: str, result: dict) -> None:
        """Mark job as complete and store result."""
```

#### 4. Error Pattern Cache

**File**: `crackerjack/mcp/error_cache.py`

```python
class ErrorCache:
    """Cache error patterns for AI fix recommendations."""

    async def get_pattern(self, error_type: str) -> Pattern | None:
        """Retrieve cached fix pattern for error type."""

    async def store_pattern(self, error_type: str, pattern: Pattern) -> None:
        """Store successful fix pattern for reuse."""
```

### MCP Tool Specification

**Core Tools** (11 tools):

| Tool | Purpose | Async |
|------|---------|-------|
| `execute_crackerjack` | Start quality workflow | Yes |
| `get_job_progress` | Get real-time progress | Yes |
| `run_crackerjack_stage` | Run specific stage | Yes |
| `analyze_errors` | Analyze error patterns | Yes |
| `smart_error_analysis` | AI-powered analysis | Yes |
| `get_stage_status` | Check workflow status | No |
| `get_next_action` | Get recommended action | No |
| `session_management` | Session checkpoints | Yes |

### Configuration

**File**: `settings/mcp_settings.yml`

```yaml
# MCP Server Configuration
mcp:
  host: "127.0.0.1"
  http_port: 8676
  websocket_port: 8675
  http_enabled: true

# Job Manager
jobs:
  max_concurrent: 3
  timeout_seconds: 600
  cleanup_interval_seconds: 3600

# WebSocket Security
websocket:
  allowed_origins: ["localhost:*"]
  rate_limit_per_minute: 60
```

### Usage Examples

#### AI Agent Integration

**Python MCP Client**:

```python
from mcp import ClientSession, StdioServerParameters

async def run_quality_checks():
    server_params = StdioServerParameters(
        command="uvx",
        args=["--from", "/path/to/crackerjack", "crackerjack", "start"]
    )

    async with ClientSession(server_params) as session:
        # Start quality workflow
        result = await session.call_tool(
            "execute_crackerjack",
            arguments={
                "command": "test",
                "ai_agent_mode": True,
                "timeout": 600
            }
        )
        job_id = result[1]["job_id"]

        # Monitor progress
        while True:
            progress = await session.call_tool(
                "get_job_progress",
                arguments={"job_id": job_id}
            )
            print(f"Progress: {progress[1]['percent']}%")

            if progress[1]["status"] == "complete":
                break
            await asyncio.sleep(2)
```

**Configuration for Claude Desktop**:

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "uvx",
      "args": [
        "--from",
        "/Users/les/Projects/crackerjack",
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

## Consequences

### Positive

1. **Performance**: Direct Python API calls (no subprocess overhead) - 47% faster than pre-commit
2. **Extensibility**: Adding new tools is trivial with `@mcp.tool()` decorator
3. **Real-time Monitoring**: WebSocket enables live progress tracking
4. **Type Safety**: FastMCP provides automatic type validation
5. **Separation of Concerns**: MCP layer is isolated from core logic
6. **Backward Compatible**: CLI commands remain unchanged
7. **Security**: Localhost-only WebSocket prevents external access

### Negative

1. **Complexity**: More moving parts (WebSocket server, job manager)
2. **Dependency**: Requires FastMCP and websockets libraries
3. **Testing Surface**: Need to test both stdio and WebSocket transports
4. **Debugging**: WebSocket issues can be harder to debug than HTTP
5. **Memory**: Job manager needs periodic cleanup to prevent memory leaks

### Risks

| Risk | Mitigation |
|------|------------|
| WebSocket connection drops | Implement auto-reconnect with exponential backoff |
| Job manager memory leaks | Periodic cleanup of completed jobs (>1 hour old) |
| FastMCP version conflicts | Pin to `fastmcp~=2.13.0` in pyproject.toml |
| Port conflicts (8675/8676) | Allow configuration via environment variables |

## Migration Notes

### From Pre-commit Subprocess Calls

**Before** (Phase 7):

```python
result = subprocess.run(
    ["pre-commit", "run", "--all-files"],
    capture_output=True,
    text=True
)
```

**After** (Phase 8):

```python
# Direct adapter calls (no subprocess)
from crackerjack.adapters.ruff_format import RuffFormatAdapter
adapter = RuffFormatAdapter()
result = await adapter.check(files, config)
```

**Performance Improvement**: 47% faster due to no subprocess overhead.

### CLI Commands Unchanged

All existing CLI commands remain backward compatible:

```bash
python -m crackerjack run                    # Still works
python -m crackerjack run --ai-fix --run-tests  # Still works
```

## Related Decisions

- **ADR-002**: Multi-agent quality check orchestration
- **ADR-003**: Property-based testing with Hypothesis
- **ADR-004**: Quality gate threshold system

## References

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Phase 3 Implementation](../PHASE1_COMPLETE.md) - MCP server lifecycle modernization
- [MCP Tools Specification](../MCP_TOOLS_SPECIFICATION.md)

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-01-15 | Les Leslie | Initial ADR creation |
| 2025-01-20 | Les Leslie | Added WebSocket job manager details |
| 2025-02-01 | Les Leslie | Updated with Phase 8 performance metrics |
