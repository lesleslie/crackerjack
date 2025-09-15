# Zuban Language Server Integration Plan for Crackerjack

## Executive Summary

Integrate zuban's Language Server Protocol (LSP) capabilities into crackerjack to provide real-time type checking feedback, enabled by default in both normal and MCP workflows. IDE integration (PyCharm) will remain a separate user configuration task.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Crackerjack Core                         │
├─────────────────────────────────────────────────────────────┤
│  CLI Layer           │  MCP Server      │  Workflow Layer   │
│  --start-zuban-lsp   │  LSP Tools       │  Phase Coord.     │
│  --no-zuban-lsp      │  Status/Restart  │  AI Agents        │
├──────────────────────┴──────────────────┴───────────────────┤
│                    Zuban LSP Service                         │
│  • Lifecycle Management  • Health Checks  • Auto-restart    │
├─────────────────────────────────────────────────────────────┤
│                Service Watchdog & Monitoring                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    Zuban LSP Server (Port 8677)
                              ↓
                    IDE Clients (User Config)
```

## Phase 1: Core LSP Infrastructure (Foundation)

### 1.1 Create Zuban LSP Service Module

**File**: `crackerjack/services/zuban_lsp_service.py`

```python
class ZubanLSPService:
    """Manages zuban language server lifecycle."""

    def __init__(self, port: int = 8677, mode: str = "tcp"):
        self.port = port
        self.mode = mode  # "tcp" or "stdio"
        self.process: subprocess.Popen | None = None

    async def start(self) -> bool:
        """Start the zuban LSP server."""

    async def stop(self) -> None:
        """Gracefully stop the LSP server."""

    async def health_check(self) -> bool:
        """Check if LSP server is responsive."""

    async def restart(self) -> bool:
        """Restart the LSP server."""
```

**Key Features**:

- Handle stdio/TCP transport modes
- Manage process spawning with `uv run zuban server`
- Implement health checking and auto-restart capabilities
- Add port management (default: 8677, configurable)

### 1.2 Extend Service Watchdog

**File**: `crackerjack/core/service_watchdog.py`

Add zuban LSP to default service configurations:

```python
"zuban_lsp": ServiceConfig(
    name="Zuban LSP Server",
    command=["uv", "run", "zuban", "server"],
    health_check_url="tcp://localhost:8677",
    health_check_timeout=3.0,
    startup_timeout=15.0,
    shutdown_timeout=10.0,
    max_restarts=5,
    restart_delay=5.0,
)
```

### 1.3 Update Server Manager

**File**: `crackerjack/services/server_manager.py`

New functions to add:

- `find_zuban_lsp_processes()` - Locate running zuban LSP processes
- `stop_zuban_lsp()` - Stop LSP server
- `restart_zuban_lsp()` - Restart LSP server
- Update `list_server_status()` to include zuban LSP
- Update `stop_all_servers()` to handle zuban LSP

## Phase 2: CLI Integration

### 2.1 Add CLI Options

**File**: `crackerjack/cli/options.py`

New CLI flags:

```python
@click.option(
    "--start-zuban-lsp",
    is_flag=True,
    help="Start zuban LSP server standalone",
)
@click.option(
    "--no-zuban-lsp",
    is_flag=True,
    help="Disable automatic zuban LSP startup",
)
@click.option(
    "--zuban-lsp-port",
    type=int,
    default=8677,
    help="Port for zuban LSP server (default: 8677)",
)
@click.option(
    "--zuban-lsp-mode",
    type=click.Choice(["tcp", "stdio"]),
    default="tcp",
    help="Transport mode for zuban LSP (default: tcp)",
)
```

### 2.2 Update CLI Handlers

**File**: `crackerjack/cli/handlers.py`

Implement command handling for:

- Starting LSP server standalone
- Managing LSP lifecycle
- Integration with watchdog service

### 2.3 Modify Main Entry Point

**File**: `crackerjack/__main__.py`

Workflow changes:

1. Auto-start zuban LSP by default (unless `--no-zuban-lsp`)
1. Ensure LSP starts before quality checks
1. Add LSP status to workflow reporting
1. Clean shutdown on exit

## Phase 3: MCP Server Integration

### 3.1 Create MCP Tools for LSP

**File**: `crackerjack/mcp/tools/lsp_tools.py`

```python
@mcp_app.tool()
async def get_zuban_lsp_status() -> dict:
    """Check if zuban LSP server is running and healthy."""


@mcp_app.tool()
async def restart_zuban_lsp() -> dict:
    """Restart the zuban LSP server."""


@mcp_app.tool()
async def get_type_diagnostics(file_path: str) -> dict:
    """Fetch real-time type errors for a file."""


@mcp_app.tool()
async def configure_zuban_lsp(settings: dict) -> dict:
    """Adjust LSP settings on the fly."""
```

### 3.2 Enhance MCP Server Core

**File**: `crackerjack/mcp/server_core.py`

- Register LSP tools with MCP server
- Add LSP status to comprehensive status reporting
- Include LSP health in MCP monitoring

### 3.3 Add MCP Slash Commands

Create new slash command files:

- `/crackerjack:lsp-status` - Check LSP server status
- `/crackerjack:lsp-restart` - Restart LSP server
- `/crackerjack:lsp-diagnostics` - Get current type errors

## Phase 4: Enhanced Zuban Adapter

### 4.1 Upgrade Zuban Adapter

**File**: `crackerjack/adapters/zuban_adapter.py`

Enhancements:

```python
class ZubanAdapter(BaseRustToolAdapter):
    def __init__(self, context, use_lsp: bool = True):
        self.use_lsp = use_lsp
        self.lsp_client = None

    async def get_lsp_diagnostics(self) -> list[TypeIssue]:
        """Get real-time diagnostics from LSP server."""

    def get_command_args(self, target_files):
        """Fallback to CLI mode if LSP unavailable."""
```

### 4.2 Create LSP Client Wrapper

**File**: `crackerjack/adapters/lsp_client.py`

```python
class ZubanLSPClient:
    """Minimal LSP client for zuban communication."""

    async def connect(self, port: int = 8677) -> bool:
        """Connect to zuban LSP server."""

    async def initialize(self) -> dict:
        """Send initialize request."""

    async def text_document_did_open(self, file_path: Path) -> None:
        """Notify server of opened document."""

    async def text_document_did_change(self, file_path: Path, content: str) -> None:
        """Notify server of document changes."""

    async def get_diagnostics(self) -> list[dict]:
        """Retrieve current diagnostics."""
```

## Phase 5: Workflow Integration

### 5.1 Normal Workflow Enhancement

**File**: `crackerjack/core/phase_coordinator.py`

Integration points:

1. Start LSP server in initialization phase
1. Use LSP for real-time feedback during fixes
1. Integrate LSP diagnostics with AI agents
1. Show LSP status in progress reporting

### 5.2 Test Integration

**File**: `crackerjack/managers/test_manager.py`

- Run type checks via LSP before test execution
- Correlate test failures with type errors
- Provide faster feedback loop

### 5.3 AI Agent Enhancement

**File**: `crackerjack/agents/refactoring_agent.py`

Benefits for AI agents:

- Real-time validation of fixes
- Reduced fix-check cycles
- Improved accuracy with live type information

## Phase 6: Configuration & Documentation

### 6.1 Configuration

**File**: `pyproject.toml`

```toml
[tool.crackerjack]
# Zuban LSP Configuration
zuban_lsp_enabled = true  # Enable by default
zuban_lsp_port = 8677
zuban_lsp_mode = "tcp"  # or "stdio"
zuban_lsp_auto_restart = true
zuban_lsp_max_restarts = 5
zuban_lsp_memory_limit_mb = 512  # Restart if exceeds
```

### 6.2 Update Documentation

Files to update:

- `CLAUDE.md` - Add LSP commands and workflow
- `README.md` - Document LSP benefits
- `AI-REFERENCE.md` - Add LSP decision tree

### 6.3 IDE Configuration Guide

**File**: `docs/IDE_SETUP.md`

#### PyCharm Configuration

1. Install "LSP Support" plugin from JetBrains Marketplace
1. Configure LSP client:
   - Server: `localhost:8677` (TCP mode)
   - Or stdio command: `uv run zuban server`
1. Enable for Python files
1. Configure diagnostics display

#### VS Code Configuration

```json
{
  "languageServerExample.trace.server": "verbose",
  "python.linting.enabled": false,
  "zuban-lsp": {
    "command": ["uv", "run", "zuban", "server"],
    "filetypes": ["python"],
    "initializationOptions": {}
  }
}
```

## Implementation Strategy

### Timeline

- **Week 1**: Phases 1-2 (Core infrastructure and CLI)

  - Days 1-2: LSP service implementation
  - Days 3-4: Service watchdog integration
  - Days 5-7: CLI options and handlers

- **Week 2**: Phases 3-4 (MCP integration and adapter)

  - Days 1-2: MCP tools development
  - Days 3-4: LSP client implementation
  - Days 5-7: Adapter enhancement

- **Week 3**: Phases 5-6 (Workflow and documentation)

  - Days 1-3: Workflow integration
  - Days 4-5: Configuration setup
  - Days 6-7: Documentation and testing

### Priority Order

1. **Critical Path**: LSP service → Watchdog → CLI integration
1. **Enhancement Path**: MCP tools → Adapter upgrade → AI integration
1. **Polish Path**: Configuration → Documentation → IDE guides

## Benefits

### Performance Improvements

- **20-200x faster** type checking than pyright
- **Real-time feedback** without running CLI commands
- **Reduced CPU usage** with persistent server
- **Instant validation** for AI agent fixes

### Developer Experience

- **Faster iteration cycles** with live feedback
- **Better error context** with continuous checking
- **Seamless integration** with existing workflow
- **Optional IDE support** without dependency

### AI Agent Enhancements

- **Better fix accuracy** with real-time validation
- **Reduced retry cycles** for type errors
- **Contextual awareness** of type issues
- **Faster convergence** to correct solutions

## Technical Considerations

### Port Management

- Default port: **8677**
- Avoid conflicts:
  - MCP Server: 8676
  - WebSocket: 8675
  - HTTP monitoring: 8678
- Configurable via CLI and config file

### Process Lifecycle

- Leverage existing watchdog for reliability
- Automatic restart on failure
- Exponential backoff for restart attempts
- Clean shutdown on exit

### Memory Management

- Monitor LSP server memory usage
- Restart if exceeds threshold (512MB default)
- Log memory statistics for debugging
- Implement memory leak detection

### Compatibility

- Maintain backward compatibility with CLI-only mode
- Graceful degradation if LSP fails
- Support both TCP and stdio transports
- Work with UV environment

### Error Handling

- Graceful fallback to CLI mode
- Clear error messages for debugging
- Retry logic for connection failures
- Health check timeouts

## Testing Plan

### Unit Tests

```python
# test_zuban_lsp_service.py
def test_lsp_service_start_stop():
    """Test LSP service lifecycle."""


def test_lsp_health_check():
    """Test health check functionality."""


def test_lsp_auto_restart():
    """Test automatic restart on failure."""
```

### Integration Tests

```python
# test_lsp_integration.py
def test_workflow_with_lsp():
    """Test complete workflow with LSP enabled."""


def test_mcp_lsp_tools():
    """Test MCP tool interactions with LSP."""


def test_lsp_fallback():
    """Test fallback to CLI when LSP unavailable."""
```

### Performance Tests

- Benchmark LSP vs CLI mode
- Measure memory usage over time
- Test concurrent file checking
- Stress test with large codebases

### End-to-End Tests

- Full workflow with LSP enabled
- MCP server interaction tests
- AI agent integration tests
- Multi-project scenarios

## Risk Mitigation

### Potential Risks

1. **LSP server instability**

   - Mitigation: Watchdog with auto-restart

1. **Memory leaks in long-running server**

   - Mitigation: Periodic restart, memory monitoring

1. **Port conflicts**

   - Mitigation: Configurable ports, automatic port finding

1. **Compatibility issues**

   - Mitigation: Fallback to CLI mode

### Rollback Plan

If issues arise:

1. `--no-zuban-lsp` flag disables LSP
1. Configuration toggle in pyproject.toml
1. Fallback to CLI mode automatically
1. Clear documentation for disabling

## Success Metrics

### Quantitative Metrics

- **Type check speed**: >10x improvement
- **Memory usage**: \<512MB steady state
- **Uptime**: >99% with auto-restart
- **Error detection**: Same accuracy as CLI

### Qualitative Metrics

- **Developer satisfaction**: Faster feedback
- **AI agent efficiency**: Fewer retry cycles
- **Integration smoothness**: No workflow disruption
- **Documentation clarity**: Easy IDE setup

## Conclusion

This comprehensive plan integrates zuban's LSP capabilities into crackerjack's existing architecture, providing significant performance improvements and enhanced developer experience while maintaining backward compatibility and separation of IDE configuration concerns.

The implementation leverages existing infrastructure (service watchdog, MCP server, CLI framework) to minimize new code and maximize reliability. The phased approach ensures each component is thoroughly tested before proceeding to the next phase.

With this integration, crackerjack will offer state-of-the-art type checking performance with real-time feedback, benefiting both human developers and AI agents in their quest for high-quality Python code.
