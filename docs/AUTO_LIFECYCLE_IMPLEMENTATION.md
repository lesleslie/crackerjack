# Session Management Automatic Lifecycle Implementation Plan

## Executive Summary

This document outlines the implementation of automatic session lifecycle management for the session-mgmt MCP server. The enhancement eliminates manual intervention for git-based projects while preserving manual control for non-git workflows.

## Core Architecture Changes

### 1. Automatic Session Lifecycle Detection

**Add FastMCP lifespan handlers to auto-detect client connections:**

- On connection: Check if in git repo → auto-run init logic
- On disconnection: Check if in git repo → auto-run end logic
- Non-git projects: No automatic actions, rely on manual commands

### 2. Enhanced Checkpoint with Auto-Compaction

**Modify checkpoint to execute compaction automatically:**

- When `should_suggest_compact()` returns true
- Execute session-mgmt's internal compaction instead of recommending `/compact`
- Remove confusing "/compact" recommendations

### 3. Command Alias Strategy

**Keep strategic aliases for flexibility:**

- ✅ Keep `/start` → For manual init in non-git projects
- ✅ Keep `/end` → For manual cleanup in non-git projects
- ✅ Keep `/checkpoint` → Universal manual checkpointing
- ❌ Remove auto-hooks from settings.json (replaced by server-side detection)

## Implementation Details

### Phase 1: Core Server Changes

#### 1.1 Add Lifespan Management (session_mgmt_mcp/server.py)

```python
@mcp.lifespan
async def session_lifecycle():
    """Automatic session lifecycle for git repositories only"""
    from session_mgmt_mcp.utils.git_operations import is_git_repository, get_git_root

    current_dir = Path(os.getcwd())

    # Only auto-initialize for git repositories
    if is_git_repository(current_dir):
        try:
            git_root = get_git_root(current_dir)
            logger.info(f"Git repository detected at {git_root}")

            # Run the same logic as the init tool but silently
            await _internal_session_init(auto_mode=True)
            logger.info("✅ Auto-initialized session for git repository")
        except Exception as e:
            logger.warning(f"Auto-init failed (non-critical): {e}")
    else:
        logger.debug("Non-git directory - skipping auto-initialization")

    yield  # Server runs normally

    # On disconnect - cleanup for git repos only
    if is_git_repository(current_dir):
        try:
            await _internal_session_end(auto_mode=True)
            logger.info("✅ Auto-ended session for git repository")
        except Exception as e:
            logger.warning(f"Auto-cleanup failed (non-critical): {e}")
```

#### 1.2 Enhanced Checkpoint with Auto-Compaction

```python
async def checkpoint(name: str | None = None) -> str:
    """Enhanced checkpoint with automatic compaction"""
    # ... existing checkpoint logic ...

    # Auto-compact when needed
    should_compact, reason = should_suggest_compact()

    if should_compact:
        # Execute internal compaction instead of recommending
        results.append("\n🔄 Automatic Compaction")
        results.append(f"📊 Reason: {reason}")

        try:
            compact_result = await _execute_auto_compact()
            results.append("✅ Context automatically optimized")
        except Exception as e:
            results.append(f"⚠️ Auto-compact skipped: {str(e)}")

    # Remove old recommendation text
    # DELETE: "🔄 RECOMMENDATION: Run /compact to optimize context"
```

### Phase 2: Documentation Updates

#### 2.1 Session-mgmt-mcp README.md Updates

Add new section after "Features":

```markdown
## 🚀 Automatic Session Management (NEW!)

**For Git Repositories:**
- ✅ **Automatic initialization** when Claude Code connects
- ✅ **Automatic cleanup** when session ends (quit, crash, or network failure)
- ✅ **Intelligent auto-compaction** during checkpoints
- ✅ **Zero manual intervention** required

**For Non-Git Projects:**
- 📝 Use `/start` for manual initialization
- 📝 Use `/end` for manual cleanup
- 📝 Full session management features available on-demand
```

#### 2.2 Session-mgmt-mcp CLAUDE.md Updates

Replace workflow section:

```markdown
## Recommended Session Workflow

### Git Repositories (Automatic)
1. **Start Claude Code** - Session auto-initializes
2. **Work normally** - Automatic quality tracking
3. **Run `/checkpoint`** - Manual checkpoints with auto-compaction
4. **Exit any way** - Session auto-cleanup on disconnect

### Non-Git Projects (Manual)
1. **Start with**: `/start` (if you want session management)
2. **Checkpoint**: `/checkpoint` as needed
3. **End with**: `/end` before quitting
```

#### 2.3 Crackerjack README.md Updates

Update integration section:

````markdown
## 🤝 Session-mgmt Integration (Enhanced)

**Automatic for Git Projects:**
- Session management starts automatically
- No manual `/start` or `/end` needed
- Checkpoints auto-compact when necessary
- Works seamlessly with `python -m crackerjack`

**Example Workflow:**
```bash
# Just start working - session auto-initializes!
python -m crackerjack --ai-agent -t

# Checkpoint periodically (auto-compacts if needed)
/checkpoint

# Quit any way - session auto-saves
/quit  # or Cmd+Q, or network disconnect
````

````

#### 2.4 Crackerjack CLAUDE.md Updates
Add to workflow section:
```markdown
## Session Management Integration

**Automatic Lifecycle (Git repos only):**
- Session starts automatically when Claude Code connects
- Session ends automatically on disconnect/quit
- No manual commands needed for git repositories

**Manual Commands (still available):**
- `/start` - Manual init for non-git projects
- `/checkpoint` - Create checkpoint (auto-compacts)
- `/end` - Manual cleanup for non-git projects

**Best Practice:**
For Crackerjack projects (always git repos), you can focus on development
without worrying about session management - it's fully automatic!
````

### Phase 3: Configuration Cleanup

#### 3.1 Remove Old Hooks from settings.json

Remove from `/Users/les/.claude/settings.json`:

```json
// REMOVE THESE:
"UserPromptSubmit": [
  {
    "matcher": "/(?:exit|quit)\\b",
    "hooks": [
      {
        "type": "command",
        "command": "~/.claude/scripts/session-manager.sh end"
      }
    ]
  }
]
```

Keep SessionStart hook for MCP server startup only.

### Phase 4: Testing Plan

1. **Git Repository Tests:**

   - Start session in crackerjack → Verify auto-init
   - Run checkpoint → Verify auto-compact when needed
   - Quit various ways → Verify auto-cleanup

1. **Non-Git Directory Tests:**

   - Start session in /tmp → Verify NO auto-init
   - Manual `/start` → Verify works
   - Manual `/end` → Verify works

1. **Failure Recovery Tests:**

   - Force quit Claude Code → Verify cleanup runs
   - Network disconnect → Verify cleanup runs
   - Server crash → Verify graceful degradation

## Benefits

### For Git Repositories (90% of use cases)

- **Zero manual intervention** - Fully automatic lifecycle
- **Crash resilient** - Cleanup runs even on force quit/crash
- **Network failure safe** - Disconnection triggers cleanup
- **Intelligent compaction** - Automatic during checkpoints

### For Non-Git Projects

- **Manual control preserved** - Use `/start` and `/end` as needed
- **Optional session management** - Only when explicitly desired
- **Full feature access** - All session-mgmt features available

## Success Metrics

- ✅ Zero manual commands for git repositories
- ✅ Automatic compaction during checkpoints
- ✅ Cleanup runs on ALL disconnection types
- ✅ Non-git directories unaffected
- ✅ Manual commands still functional

## Migration Path

1. **Update server.py** with lifespan handlers
1. **Test with git repositories** to verify auto-detection
1. **Test with non-git directories** to verify no interference
1. **Update documentation** to reflect new behavior
1. **Clean up old hooks** from settings.json

## Timeline

- Phase 1: Core server changes (1-2 hours)
- Phase 2: Documentation updates (30 mins)
- Phase 3: Configuration cleanup (15 mins)
- Phase 4: Testing (1 hour)

Total: ~3-4 hours implementation time

## Implementation Status

- [ ] Phase 1: Core server changes
- [ ] Phase 2: Documentation updates
- [ ] Phase 3: Configuration cleanup
- [ ] Phase 4: Testing and validation

______________________________________________________________________

*Document created: 2025-09-07*
*Status: Implementation in progress*
