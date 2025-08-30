# Crackerjack uvx Usage Guide

## Overview

Crackerjack can now be executed using `uvx` for isolated execution environments. This is particularly useful for MCP server integration and avoiding dependency conflicts.

## Basic Usage

### Direct uvx Command

**For installed crackerjack (from PyPI):**

```bash
# Run crackerjack with uvx (uses installed package)
uvx crackerjack --help
uvx crackerjack -t
uvx crackerjack --start-mcp-server
uvx crackerjack --start-websocket-server
```

**For local development version:**

```bash
# Run crackerjack with uvx (uses local development version)
uvx --from /Users/les/Projects/crackerjack crackerjack --help
uvx --from /Users/les/Projects/crackerjack crackerjack -t
uvx --from /Users/les/Projects/crackerjack crackerjack --start-mcp-server
uvx --from /Users/les/Projects/crackerjack crackerjack --start-websocket-server
```

### Shell Alias (Optional)

Add to your shell configuration file (`.bashrc`, `.zshrc`, etc.):

```bash
# For installed version:
alias crackerjack-uvx='uvx crackerjack'

# For local development version:
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
1. **No Dependency Conflicts**: Avoids conflicts with system or other project dependencies
1. **Consistent Execution**: Same environment across different projects and systems
1. **MCP Integration**: Works seamlessly with MCP server configurations
1. **Development Convenience**: Can be used from any directory without virtual environment activation

## Verification

Test the setup:

```bash
# Test basic functionality (local development version)
uvx --from /Users/les/Projects/crackerjack crackerjack --help

# Test MCP server (should start and be accessible)
uvx --from /Users/les/Projects/crackerjack crackerjack --start-mcp-server

# Test from different directory
cd /tmp && uvx --from /Users/les/Projects/crackerjack crackerjack --help
```

## Note

For local development, the uvx installation uses `--from /Users/les/Projects/crackerjack` to reference the local development version. For production use with installed crackerjack (from PyPI), you can use the cleaner `uvx crackerjack` command.
