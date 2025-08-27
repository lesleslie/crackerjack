# Crackerjack uvx Usage Guide

## Overview

Crackerjack can now be executed using `uvx` for isolated execution environments. This is particularly useful for MCP server integration and avoiding dependency conflicts.

## Basic Usage

### Direct uvx Command

```bash
# Run crackerjack with uvx (installs in isolated environment)
uvx --from /Users/les/Projects/crackerjack crackerjack --help

# Run crackerjack with tests
uvx --from /Users/les/Projects/crackerjack crackerjack -t

# Start MCP server
uvx --from /Users/les/Projects/crackerjack crackerjack --start-mcp-server

# Start WebSocket server
uvx --from /Users/les/Projects/crackerjack crackerjack --start-websocket-server
```

### Shell Alias (Optional)

Add to your shell configuration file (`.bashrc`, `.zshrc`, etc.):

```bash
# Crackerjack uvx alias
alias crackerjack-uvx='uvx --from /Users/les/Projects/crackerjack crackerjack'
```

Then use:

```bash
crackerjack-uvx --help
crackerjack-uvx -t
crackerjack-uvx --start-mcp-server
```

## MCP Server Integration

### Updated Configuration

All MCP servers in `~/Projects` have been automatically updated to use the uvx command:

```json
{
  "crackerjack": {
    "command": "uvx",
    "args": [
      "--from",
      "/Users/les/Projects/crackerjack",
      "crackerjack",
      "--start-mcp-server"
    ],
    "env": {
      "UV_KEYRING_PROVIDER": "subprocess",
      "EDITOR": "code --wait"
    }
  }
}
```

### Projects Updated

- ✅ /Users/les/Projects/jinja2-async-environment/.mcp.json
- ✅ /Users/les/Projects/starlette-async-jinja/.mcp.json
- ✅ /Users/les/Projects/excalidraw-mcp/.mcp.json
- ✅ /Users/les/Projects/crackerjack/.mcp.json
- ✅ /Users/les/Projects/splashstand/.mcp.json
- ✅ /Users/les/Projects/fastblocks/.mcp.json
- ✅ /Users/les/Projects/session-mgmt-mcp/.mcp.json
- ✅ /Users/les/Projects/acb/.mcp.json

## Benefits

1. **Isolated Environment**: Each uvx execution runs in its own isolated Python environment
2. **No Dependency Conflicts**: Avoids conflicts with system or other project dependencies
3. **Consistent Execution**: Same environment across different projects and systems
4. **MCP Integration**: Works seamlessly with MCP server configurations
5. **Development Convenience**: Can be used from any directory without virtual environment activation

## Verification

Test the setup:

```bash
# Test basic functionality
uvx --from /Users/les/Projects/crackerjack crackerjack --help

# Test MCP server (should start and be accessible)
uvx --from /Users/les/Projects/crackerjack crackerjack --start-mcp-server

# Test from different directory
cd /tmp && uvx --from /Users/les/Projects/crackerjack crackerjack --help
```

## Note

The uvx installation uses the local development version of crackerjack from `/Users/les/Projects/crackerjack`, ensuring you're always using the latest local changes.