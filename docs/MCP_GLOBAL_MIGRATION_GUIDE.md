______________________________________________________________________

## status: complete role: historical date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: mcp-design

# MCP Global Configuration Migration Guide

**Date**: 2025-12-29
**Goal**: Consolidate all MCP servers from 14 projects into a single global configuration

______________________________________________________________________

## Summary

✅ **Successfully consolidated 19 unique MCP servers** from 14 active projects into a single `~/.claude/.mcp.json` configuration.

**Why This Matters**:

- **Unified Management**: Enable/disable servers globally from one place
- **No Duplication**: Eliminates redundant server definitions across projects
- **Claude Code Native**: Uses Claude Code's built-in MCP server management UI
- **Simpler Onboarding**: New projects automatically inherit all available servers

______________________________________________________________________

## Server Inventory

### Core Universal Servers (Used in 10+ Projects)

| Server | Type | Projects Using | Priority |
|--------|------|----------------|----------|
| **context7** | stdio | 12/14 | 🔴 High - Documentation search |
| **session-buddy** | HTTP (8678) | 12/14 | 🔴 High - Session management |
| **excalidraw** | HTTP (3032) | 12/14 | 🟡 Medium - Diagram collaboration |
| **macos_automator** | stdio | 12/14 | 🟡 Medium - macOS automation |
| **memory** | stdio | 12/14 | 🟡 Medium - Knowledge graph |
| **crackerjack** | HTTP (8676) | 11/14 | 🔴 High - Quality checks |
| **mermaid** | HTTP (3033) | 11/14 | 🟢 Low - Diagram generation |
| **peekaboo** | stdio | 10/14 | 🟡 Medium - Screenshot/vision |

### Frequently Used Servers (4-9 Projects)

| Server | Type | Projects Using | Priority |
|--------|------|----------------|----------|
| **gitlab** | stdio | 6 | 🟢 Low - GitLab integration |
| **cloud-run** | stdio | 5 | 🟢 Low - GCP Cloud Run |
| **logfire** | stdio (uvx) | 4 | 🟢 Low - Python observability |
| **sentry** | HTTP (external) | 4 | 🟢 Low - Error tracking |
| **upstash** | stdio | 4 | 🟢 Low - Redis/Vector DB |
| **turso-cloud** | stdio | 4 | 🟢 Low - SQLite cloud |

### Specialized Servers (1-3 Projects)

| Server | Type | Projects Using | Priority |
|--------|------|----------------|----------|
| **mailgun** | HTTP (3039) | 3 | 🟢 Low - Email service |
| **playwright** | stdio | 2 | 🟢 Low - Browser automation |
| **penpot** | stdio (uvx) | 2 | 🟢 Low - Design tool |
| **raindropio** | HTTP (3034) | 2 | 🟢 Low - Bookmarks |
| **unifi** | HTTP (3038) | 1 | 🟢 Low - Network management |

______________________________________________________________________

## Priority Recommendations

### 🔴 High Priority (Always Enable)

Keep these running 24/7 - they're used across almost all projects:

```bash
# Enable via Claude Code UI (MCP menu)
✅ context7        # Documentation search
✅ session-buddy   # Session/context tracking
✅ crackerjack     # Quality checks & testing
```

### 🟡 Medium Priority (Enable as Needed)

Enable when working on specific features:

```bash
# macOS-specific tasks
✅ macos_automator  # AppleScript/JXA automation
✅ peekaboo         # Screenshot & vision analysis

# Diagram/visualization work
✅ excalidraw       # Collaborative diagrams
✅ mermaid          # Code-driven diagrams
✅ memory           # Knowledge graph
```

### 🟢 Low Priority (Disable by Default)

Only enable when actively using these services:

```bash
# Cloud services
✅ cloud-run        # GCP deployment
✅ logfire          # Python observability
✅ sentry           # Error tracking
✅ turso-cloud      # SQLite cloud
✅ upstash          # Redis/Vector DB

# Git integration
✅ gitlab           # GitLab operations

# Specialized tools
✅ playwright       # Browser automation
✅ penpot           # Design collaboration
✅ mailgun          # Email service
✅ raindropio       # Bookmark management
✅ unifi            # Network management
```

______________________________________________________________________

## Migration Steps

### Step 1: Global Config Created ✅

**File**: `~/.claude/.mcp.json`

This file now contains all 19 unique servers discovered across your 14 active projects.

**What Changed**:

- ✅ Consolidated duplicate definitions (same server defined in multiple projects)
- ✅ Added descriptions for each server (usage frequency notes)
- ✅ Standardized format (command/args ordering)
- ✅ Removed project-specific quirks (e.g., peekaboo env vars in splashstand)

### Step 2: Disable Auto-Start Script

**File to Edit**: `~/.claude/settings.json`

**Current**:

```json
"hooks": {
  "SessionStart": [
    {
      "matcher": ".*",
      "hooks": [
        {
          "type": "command",
          "command": "nohup ~/.claude/scripts/auto-start-mcp-servers.sh >/dev/null 2>&1 &"
        }
      ]
    }
  ]
}
```

**Action**: Comment out the MCP auto-start hook:

```json
"hooks": {
  "SessionStart": [
    {
      "matcher": ".*",
      "hooks": [
        {
          "type": "command",
          "command": "# nohup ~/.claude/scripts/auto-start-mcp-servers.sh >/dev/null 2>&1 &"
        }
      ]
    }
  ]
}
```

**Why**: Claude Code now manages MCP servers natively from the global config. The shell script is no longer needed.

### Step 3: Remove Project-Level `.mcp.json` Files

**Option A: Complete Cleanup** (Recommended)

Delete all project-specific MCP configs since the global config now covers everything:

```bash
# From project directories
rm /Users/les/Projects/crackerjack/.mcp.json
rm /Users/les/Projects/session-buddy/.mcp.json
rm /Users/les/Projects/excalidraw-mcp/.mcp.json
rm /Users/les/Projects/mcp-common/.mcp.json
# ... etc for all 14 projects
```

**Option B: Keep as Reference** (Conservative)

Keep project configs for documentation purposes:

```bash
# Rename to prevent conflicts
mv /Users/les/Projects/crackerjack/.mcp.json \
   /Users/les/Projects/crackerjack/.mcp.json.backup

mv /Users/les/Projects/session-buddy/.mcp.json \
   /Users/les/Projects/session-buddy/.mcp.json.backup

# ... etc for all projects
```

**Recommendation**: Choose Option A. The global config is the single source of truth now.

### Step 4: Restart Claude Code

1. **Quit Claude Code** completely (Cmd+Q)
1. **Relaunch** Claude Code
1. **Verify**: Open Claude Code settings → MCP Servers
1. **Confirm**: All 19 servers appear in the list

### Step 5: Test Server Connectivity

**Manual Test**:

```bash
# Test HTTP servers
curl http://localhost:8678/mcp        # session-buddy
curl http://localhost:8676/mcp        # crackerjack
curl http://localhost:3032/mcp        # excalidraw
curl http://localhost:3033/mcp        # mermaid
curl http://localhost:3038/mcp        # unifi

# Test stdio servers (via Claude Code)
# Open Claude Code → Settings → MCP Servers → Enable a server
# Then use it in conversation to verify it works
```

**Expected Behavior**:

- HTTP servers should return JSON responses (or 404 for `/mcp` endpoint if no POST)
- stdio servers should auto-start when enabled in Claude Code UI

______________________________________________________________________

## Server Management Workflow

### Daily Usage

**High Priority Servers** (Always On):

```bash
# Via Claude Code UI: Settings → MCP Servers
✅ context7        # Keep enabled
✅ session-buddy   # Keep enabled
✅ crackerjack     # Keep enabled
```

**Medium Priority Servers** (Enable as Needed):

```bash
# Working on macOS features?
Settings → MCP Servers → ✅ macos_automator, ✅ peekaboo

# Creating diagrams?
Settings → MCP Servers → ✅ excalidraw, ✅ mermaid

# Need memory/knowledge?
Settings → MCP Servers → ✅ memory
```

**Low Priority Servers** (Disable When Not in Use):

```bash
# Deploying to GCP?
Settings → MCP Servers → ✅ cloud-run
# (Deploy complete) → Disable

# Debugging errors?
Settings → MCP Servers → ✅ sentry
# (Debugging done) → Disable
```

### Project-Specific Needs

**If a project needs a unique server** not in the global config:

1. **Add to global config** first (preferred)
1. **Create project override** only if necessary:

```json
// /Users/les/Projects/special-project/.mcp.json
{
  "mcpServers": {
    "specialized-tool": {
      "command": "custom-command",
      "args": ["--special-flag"],
      "type": "stdio"
    }
  }
}
```

**Merge Behavior**: Claude Code merges global + project configs (project overrides global).

______________________________________________________________________

## Troubleshooting

### Issue: Server Not Appearing in UI

**Symptoms**: Server defined in `~/.claude/.mcp.json` but not showing in Claude Code

**Solutions**:

1. **Verify JSON syntax**:

   ```bash
   jq . ~/.claude/.mcp.json
   # Should return "parse error:..." if invalid
   ```

1. **Restart Claude Code** (required after config changes)

1. **Check for typos** in server names or commands

### Issue: HTTP Server Not Connecting

**Symptoms**: `http://localhost:PORT/mcp` returns connection refused

**Solutions**:

1. **Verify server is running**:

   ```bash
   lsof -i :8678  # Check session-buddy
   lsof -i :8676  # Check crackerjack
   lsof -i :3032  # Check excalidraw
   ```

1. **Start server manually** (if needed):

   ```bash
   # session-buddy
   cd /Users/les/Projects/session-buddy
   .venv/bin/uvicorn session_buddy.server:http_app --host 127.0.0.1 --port 8678

   # crackerjack
   cd /Users/les/Projects/crackerjack
   .venv/bin/uvicorn crackerjack.mcp.server_core:http_app --host 127.0.0.1 --port 8676
   ```

1. **Check server logs**:

   ```bash
   tail -f /tmp/mcp-session-buddy.log
   tail -f /tmp/mcp-crackerjack.log
   ```

### Issue: stdio Server Not Starting

**Symptoms**: NPX/UVX server fails to start when enabled

**Solutions**:

1. **Verify package exists**:

   ```bash
   npx -y @upstash/context7-mcp@1.0.20 --version
   uvx logfire-mcp@latest --help
   ```

1. **Check network connection** (for首次 downloads):

   ```bash
   npm ping  # Should succeed
   ```

1. **Test manually**:

   ```bash
   npx -y @upstash/context7-mcp@1.0.20
   # Should start interactive session or show help
   ```

### Issue: Port Conflicts

**Symptoms**: Multiple servers trying to use the same port

**Solutions**:

1. **Identify conflict**:

   ```bash
   lsof -i :3033  # What's using mermaid port?
   ```

1. **Kill conflicting process**:

   ```bash
   kill -9 <PID>
   ```

1. **Update port in global config** (if needed):

   ```json
   "mermaid": {
     "url": "http://localhost:3034/mcp",  // Changed from 3033
     "type": "http"
   }
   ```

______________________________________________________________________

## Rollback Plan

If the global config causes issues, rollback to project-specific configs:

### Step 1: Restore Project Configs

```bash
# If you kept backups
mv /Users/les/Projects/crackerjack/.mcp.json.backup \
   /Users/les/Projects/crackerjack/.mcp.json

# ... etc for all projects
```

### Step 2: Remove Global Config

```bash
rm ~/.claude/.mcp.json
```

### Step 3: Re-enable Auto-Start Script

**Edit**: `~/.claude/settings.json`

```json
"hooks": {
  "SessionStart": [
    {
      "matcher": ".*",
      "hooks": [
        {
          "type": "command",
          "command": "nohup ~/.claude/scripts/auto-start-mcp-servers.sh >/dev/null 2>&1 &"
        }
      ]
    }
  ]
}
```

### Step 4: Restart Claude Code

Quit and relaunch to apply changes.

______________________________________________________________________

## Benefits Achieved

✅ **Simplified Management**: 19 servers in one place vs. scattered across 14 projects
✅ **No Duplication**: Eliminated 50+ duplicate server definitions
✅ **Native UI**: Use Claude Code's built-in enable/disable toggle
✅ **Faster Onboarding**: New projects automatically inherit all servers
✅ **Easier Maintenance**: Update server versions in one file
✅ **Better Visibility**: See all available servers at a glance
✅ **Resource Control**: Disable unused servers to free memory/CPU

______________________________________________________________________

## Next Steps

### Immediate (Day 1)

1. ✅ Global config created (`~/.claude/.mcp.json`)
1. ⏳ Disable auto-start script in `~/.claude/settings.json`
1. ⏳ Restart Claude Code and verify servers appear in UI
1. ⏳ Test high-priority servers (context7, session-buddy, crackerjack)

### Week 1

1. ⏳ Remove project-level `.mcp.json` files
1. ⏳ Document server usage patterns (which servers for which tasks)
1. ⏳ Create quick-reference card for common server combinations

### Week 2-4

1. ⏳ Monitor server stability and performance
1. ⏳ Add new servers to global config as needed
1. ⏳ Optimize server enable/disable patterns based on actual usage

______________________________________________________________________

## Appendix: Server Usage Patterns

### Web Development Projects

```
✅ crackerjack     # Quality checks
✅ session-buddy   # Session management
✅ context7        # Documentation
✅ playwright      # Browser testing (as needed)
✅ sentry          # Error tracking (as needed)
```

### Python/Crackerjack Development

```
✅ crackerjack     # Self-testing
✅ session-buddy   # Context tracking
✅ logfire         # Python observability
✅ memory          # Code patterns knowledge
```

### Diagram/Documentation Work

```
✅ excalidraw      # Visual diagrams
✅ mermaid         # Code diagrams
✅ context7        # Documentation search
✅ session-buddy   # Save diagram context
```

### macOS Automation Tasks

```
✅ macos_automator # AppleScript/JXA
✅ peekaboo        # Screenshot analysis
✅ session-buddy   # Task context
```

### Cloud Deployment (GCP)

```
✅ cloud-run       # GCP deployment
✅ crackerjack     # Pre-deploy checks
✅ sentry          # Production monitoring
✅ logfire         # Application observability
```

______________________________________________________________________

**Last Updated**: 2025-12-29
**Status**: ✅ Global config created, awaiting user testing <!-- legacy status — see YAML frontmatter -->
