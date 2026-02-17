# MCP Server Investigation Report

**Date:** January 1, 2026
**Issue:** Missing MCP servers in Claude Code

## Executive Summary

Your MCP servers are configured in **TWO DIFFERENT LOCATIONS**, and only ONE is being used by Claude Code:

1. **`~/.claude/.mcp.json`** (NOT USED by Claude Code) - Contains only 4 servers
1. **`~/Library/Application Support/Claude/claude_desktop_config.json`** (USED) - Contains kapture server
1. **Plugin MCP configs** - Loaded from enabled plugins in `~/.claude/plugins/cache/*/`

## Current Situation

### What Claude Code Sees (`claude mcp list`)

```
plugin:context7:context7 - ✓ Connected
plugin:greptile:greptile - ✓ Connected
plugin:playwright:playwright - ✓ Connected
plugin:sentry:sentry - ⚠ Needs authentication
kapture - ✓ Connected
zai-mcp-server - ✓ Connected
web-search-prime - ✓ Connected
web-reader - ✓ Connected
```

### What's in `~/.claude/.mcp.json` (CURRENTLY IGNORED)

```json
{
  "mcpServers": {
    "session-buddy": {"url": "http://localhost:8678/mcp", "type": "http"},
    "crackerjack": {"url": "http://localhost:8676/mcp", "type": "http"},
    "excalidraw": {"url": "http://localhost:3032/mcp", "type": "http"},
    "mermaid": {"url": "http://localhost:3033/mcp", "type": "http"}
  }
}
```

**Only 4 servers** (all HTTP-based local servers)

### What's in Git HEAD (19 SERVERS - NOT COMMITTED)

The git repository still has **all 19 servers** configured:

- 11 stdio servers (context7, macos_automator, memory, peekaboo, gitlab, cloud-run, logfire, upstash, turso-cloud, playwright, penpot)
- 8 HTTP servers (session-buddy, crackerjack, excalidraw, mermaid, mailgun, raindropio, unifi, sentry)

**BUT** you have **UNCOMMITTED CHANGES** that removed 15 servers!

## What Happened

### Timeline

1. **Dec 30, 2025 (commit 5d97d24)** - Documentation cleanup, ADDED .mcp.json with 19 servers
1. **Jan 1, 2026 03:06 AM** - .mcp.json was MODIFIED (uncommitted), 15 servers removed
1. **Current state** - Working directory has only 4 servers, git still has 19

### Evidence

```bash
# Check file modification time
$ stat -f "Modified: %Sm" ~/.claude/.mcp.json
Modified: Jan  1 03:06:33 2026

# Check git status
$ git -C ~/.claude status
Changes not staged for commit:
  modified:   .mcp.json

# Check diff
$ git -C ~/.claude diff HEAD -- .mcp.json
- Removed 15 servers (all npx/uvx stdio + 4 HTTP servers)
```

## Root Cause Analysis

### Why Servers Don't Show Up

**Claude Code does NOT read `~/.claude/.mcp.json`!**

Instead, it reads MCP servers from:

1. **Plugin MCP configs** (PRIMARY SOURCE)

   - Each enabled plugin has its own `.mcp.json`
   - Location: `~/.claude/plugins/cache/<plugin-name>/<version>/.mcp.json`

1. **Claude Desktop config** (SECONDARY SOURCE)

   - Location: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Currently only has "kapture" server

1. **Z.ai infrastructure** (INJECTED)

   - web-search-prime
   - web-reader
   - zai-mcp-server
   - These are likely injected via ZAI_API_KEY environment variable

### Server Configuration Architecture

```
┌─────────────────────────────────────────┐
│ Claude Code MCP Server Discovery        │
├─────────────────────────────────────────┤
│                                         │
│ 1. Plugins (~/.claude/plugins/cache/)   │
│    ├─ context7/.mcp.json               │
│    ├─ greptile/.mcp.json               │
│    ├─ playwright/.mcp.json              │
│    └─ sentry/.mcp.json                  │
│                                         │
│ 2. Claude Desktop Config                │
│    └─ kapture                           │
│                                         │
│ 3. Z.ai Infrastructure                  │
│    ├─ zai-mcp-server                    │
│    ├─ web-search-prime                  │
│    └─ web-reader                        │
│                                         │
│ ❌ NOT READ: ~/.claude/.mcp.json        │
│    (This file is IGNORED by Claude!)    │
└─────────────────────────────────────────┘
```

## The Missing 15 Servers

### Servers Removed (but still in git HEAD)

**Stdio Servers (npx/uvx):**

1. ❌ context7 - NOW LOADED FROM PLUGIN
1. ❌ macos_automator - MISSING
1. ❌ memory - MISSING
1. ❌ peekaboo - MISSING
1. ❌ gitlab - MISSING (plugin exists but disabled)
1. ❌ cloud-run - MISSING
1. ❌ logfire - MISSING
1. ❌ upstash - MISSING
1. ❌ turso-cloud - MISSING
1. ✅ playwright - NOW LOADED FROM PLUGIN
1. ❌ penpot - MISSING

**HTTP Servers:**
12\. ✅ session-buddy - IN ~/.claude/.mcp.json (but ignored)
13\. ✅ crackerjack - IN ~/.claude/.mcp.json (but ignored)
14\. ✅ excalidraw - IN ~/.claude/.mcp.json (but ignored)
15\. ✅ mermaid - IN ~/.claude/.mcp.json (but ignored)
16\. ❌ mailgun (localhost:3039) - MISSING
17\. ❌ raindropio (localhost:3034) - MISSING
18\. ❌ unifi (localhost:3038) - MISSING
19\. ⚠️ sentry (https://mcp.sentry.dev/mcp) - IN PLUGIN but needs auth (requires Sentry credentials)

## Z.ai Integration

### How Z.ai Servers are Configured

```bash
# Environment variables
$ env | grep -i zai
ZAI_API_KEY=43d9b2128076439c98eefcbef405a4e2.3D5wfNSaGjkOdBkC
ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic

# Check server details
$ claude mcp get zai-mcp-server
zai-mcp-server:
  Scope: User config (available in all your projects)
  Status: ✓ Connected
  Type: stdio
  Command: npx
  Args: -y @z_ai/mcp-server
  Environment:
    Z_AI_MODE=ZAI
    Z_AI_API_KEY=43d9b2128076439c98eefcbef405a4e2.3D5wfNSaGjkOdBkC
```

**Theory:** Z.ai intercepts API calls and injects its own MCP servers at runtime, bypassing the normal configuration files.

## Recommendations

### Immediate Actions

1. **Decide on MCP Server Management Strategy:**

   - **Option A:** Use Claude Code CLI (`claude mcp add/remove`) - RECOMMENDED
   - **Option B:** Keep plugin-based configuration
   - **Option C:** Manual configuration in claude_desktop_config.json

1. **Restore Missing Servers (if needed):**

```bash
# Option 1: Revert the uncommitted changes
cd ~/.claude
git checkout HEAD -- .mcp.json

# Option 2: Manually add missing servers via CLI
claude mcp add --transport stdio memory -- npx -y @modelcontextprotocol/server-memory@2025.9.25
claude mcp add --transport stdio peekaboo -- npx -y @steipete/peekaboo-mcp@2.0.3
# ... etc for other servers
```

3. **Make Local HTTP Servers Visible:**

The 4 local servers (session-buddy, crackerjack, excalidraw, mermaid) won't show up because:

- They're in `~/.claude/.mcp.json` (IGNORED)
- They're NOT in plugin configs
- They're NOT in claude_desktop_config.json

**To fix:**

```bash
# Add to Claude Desktop config
cat > ~/Library/Application\ Support/Claude/claude_desktop_config.json << 'EOF'
{
  "mcpServers": {
    "session-buddy": {
      "url": "http://localhost:8678/mcp",
      "type": "http"
    },
    "crackerjack": {
      "url": "http://localhost:8676/mcp",
      "type": "http"
    },
    "excalidraw": {
      "url": "http://localhost:3032/mcp",
      "type": "http"
    },
    "mermaid": {
      "url": "http://localhost:3033/mcp",
      "type": "http"
    },
    "kapture": {
      "command": "npx",
      "args": ["-y", "kapture-mcp@latest", "bridge"],
      "type": "stdio"
    }
  },
  "isUsingBuiltInNodeForMcp": true
}
EOF
```

### Long-Term Solution

**Standardize on ONE configuration method:**

1. **Delete/ignore `~/.claude/.mcp.json`** (it's not being used anyway)
1. **Use `claude mcp add` CLI** for all server configuration
1. **Enable/disable plugins** via Claude Code settings
1. **Document the decision** in your CLAUDE.md

### Understanding Z.ai's Role

**Important:** Z.ai is a PROXY that:

- Intercepts all Anthropic API calls (ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic)
- Injects its own MCP servers (zai-mcp-server, web-search-prime, web-reader)
- May modify MCP server discovery behavior

**This could explain why:**- Your `~/.claude/.mcp.json` is ignored

- Some servers show up that you didn't configure
- Configuration is inconsistent

## Conclusion

The missing servers are due to:

1. **Uncommitted changes** to .mcp.json that removed 15 servers
1. **Claude Code doesn't read** `~/.claude/.mcp.json` anyway
1. **Z.ai proxy** may be interfering with normal MCP discovery
1. **Multiple configuration locations** causing confusion

**Next Steps:**

1. Decide which configuration method to use (CLI recommended)
1. Add missing servers via `claude mcp add` commands
1. Update documentation to reflect the chosen method
1. Test that all servers show up in `claude mcp list`
