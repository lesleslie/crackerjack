# MCP Server Version Update Report

**Date:** January 1, 2026
**Status:** Updates Available

## Summary

Checked all MCP servers in `~/.claude/.mcp.json` with pinned versions against latest available versions.

**2 servers need updates**

______________________________________________________________________

## Updates Available ⚠

### 1. server-memory (Model Context Protocol)

| Current | Latest | Package |
|---------|--------|---------|
| 2025.9.25 | **2025.11.25** | @modelcontextprotocol/server-memory |

**Update command:**

```bash
claude mcp remove memory -s project
claude mcp add --transport stdio memory -- npx -y @modelcontextprotocol/server-memory@2025.11.25
```

**Or edit ~/.claude/.mcp.json:**

```json
"memory": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-memory@2025.11.25"]
}
```

______________________________________________________________________

### 2. mcp-gitlab

| Current | Latest | Package |
|---------|--------|---------|
| 2.0.6 | **2.0.21** | @zereight/mcp-gitlab |

**Update command:**

```bash
claude mcp remove gitlab -s project
claude mcp add --transport stdio gitlab -- npx -y @zereight/mcp-gitlab@2.0.21
```

**Or edit ~/.claude/.mcp.json:**

```json
"gitlab": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@zereight/mcp-gitlab@2.0.21"]
}
```

______________________________________________________________________

## Using "latest" Tag ℹ️

The following servers are configured without version pinning:

### 3. mcp-turso-cloud

| Configuration | Latest Available | Recommendation |
|---------------|------------------|----------------|
| `"mcp-turso-cloud"` | 0.0.11 | **Pin to specific version** |

**Current config (unpinned):**

```json
"turso-cloud": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "mcp-turso-cloud"]
}
```

**Recommended (pinned):**

```json
"turso-cloud": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "mcp-turso-cloud@0.0.11"]
}
```

### 4. logfire-mcp (Python package)

Using `"logfire-mcp@latest"` - Consider pinning to specific version for stability.

### 5. penpot-mcp (Python package)

Using `"penpot-mcp"` without version - Consider pinning to specific version.

______________________________________________________________________

## Up to Date ✅

The following servers are already on the latest version:

| Server | Version | Package |
|--------|---------|---------|
| macos_automator | 0.4.1 | @steipete/macos-automator-mcp |
| peekaboo | 2.0.3 | @steipete/peekaboo-mcp |

______________________________________________________________________

## Recommendations

### High Priority

1. **Update server-memory**: Security and bug fixes (2 month old version)
1. **Update mcp-gitlab**: 15 patch versions behind (bug fixes)

### Medium Priority

3. **Pin mcp-turso-cloud** to 0.0.11 for stability
1. **Consider pinning Python packages** (logfire-mcp, penpot-mcp)

### Update Strategy

**Option A: Update All Now (Recommended)**

```bash
# Update memory
claude mcp remove memory -s project
claude mcp add --transport stdio memory -- npx -y @modelcontextprotocol/server-memory@2025.11.25

# Update gitlab
claude mcp remove gitlab -s project
claude mcp add --transport stdio gitlab -- npx -y @zereight/mcp-gitlab@2.0.21

# Pin turso-cloud
claude mcp remove turso-cloud -s project
claude mcp add --transport stdio turso-cloud -- npx -y mcp-turso-cloud@0.0.11
```

**Option B: Manual Edit**
Edit `~/.claude/.mcp.json` directly and restart Claude Code.

______________________________________________________________________

## Version Check Method

```bash
# Check npm packages
npm view @modelcontextprotocol/server-memory version
npm view @zereight/mcp-gitlab version
npm view mcp-turso-cloud version

# Check current versions in .mcp.json
cat ~/.claude/.mcp.json | grep -A 3 '"memory"'
cat ~/.claude/.mcp.json | grep -A 3 '"gitlab"'
```

______________________________________________________________________

## Notes

- All version checks performed on January 1, 2026
- Versions retrieved from npm registry
- Python packages (logfire-mcp, penpot-mcp) not checked against PyPI
- Always test updates in non-critical environments first
