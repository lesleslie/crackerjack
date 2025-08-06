# Workflow Knowledge Base

## Purpose
This document serves as a persistent knowledge base for workflow automation, verification methodologies, and testing practices developed through multiple ChatGPT/Claude sessions. **This should be consulted in future sessions to avoid rebuilding knowledge from scratch.**

## Core Methodologies

### Paranoid Verification Workflow ⭐
**Principle**: Assume failure until proven otherwise at every step

**Implementation Files**:
- `crackerjack/verification_toolkit.py` - Complete system state capture
- `crackerjack/location_tracker.py` - Location tracking with verification
- `docs/VERIFICATION_WORKFLOW.md` - Detailed methodology documentation

**Key Practices**:
1. **📍 BEFORE**: Capture current location, processes, network state
2. **🎯 ACTION**: Execute with timeout and error handling
3. **📍 AFTER**: Re-capture all state information
4. **✅ VERIFY**: Compare before/after, check expected changes
5. **📄 LOG**: Document everything with timestamps and evidence

**Proven Success**: Successfully caught and recovered from real iTerm2 API failure during development

### Location Tracking System
**Purpose**: Track exact desktop/app/window/tab location before/after every action

**Implementation**: `crackerjack/location_tracker.py`

**Features**:
- AppleScript-based location detection
- iTerm2 window/tab specific tracking
- Human verification fallback via GUI prompts
- Complete movement history with timestamps
- JSON logging of all location changes

**Critical Functions**:
```python
from crackerjack.location_tracker import start_workflow, capture_location, verify_location

workflow_id = start_workflow("my_workflow")
before_state = capture_location("before_action")
# ... execute action ...
after_state = capture_location("after_action")
success = verify_location(expected_window=2, expected_tab=2)
```

## Automation Tools Ecosystem

### GUI Prompt System
**Location**: `~/Projects/claude/experiments/gui_prompt_system.py`

**Purpose**: Cross-window communication when Claude isn't active

**Features**:
- Topmost dialogs that appear over any application
- Choice dialogs, confirmations, input prompts
- JSON output for programmatic use
- Window detection to avoid unnecessary prompts

**Usage**:
```bash
python3 ~/Projects/claude/experiments/gui_prompt_system.py \
  --type choice \
  --title "Verification Check" \
  --message "Which window are you in?" \
  --choices "W1T1" "W1T2" "W2T1" "W2T2" \
  --json
```

### Workflow Orchestrator
**Location**: `~/Projects/claude/automation-tools/workflow_orchestrator.py`

**Purpose**: Multi-window automation with fail-safes

**Features**:
- iTerm2 window/tab switching with verification
- Location tracking and recovery
- Integration with GUI prompt system
- Manual override options for failed automation

**Key Methods**:
- `switch_to_window_tab(window, tab)` - Verified window switching
- `execute_command_in_tab(command)` - Command execution with verification
- `prompt_if_needed()` - Context-aware user prompting

### Progress Monitor Integration
**Components**:
- `crackerjack/mcp/enhanced_progress_monitor.py` - TUI progress monitor
- `crackerjack/mcp/websocket_server.py` - WebSocket progress server
- `crackerjack/mcp/server.py` - MCP server with context management

**Known Issues**:
- Context initialization prevents progress file creation (crackerjack/mcp/context.py:364-369)
- Monitor runs in Window 2, Tab 2 ONLY
- WebSocket server on localhost:8675

## Testing Best Practices

### AI Agent Testing
**Multi-Layer Strategy**:
1. **Functional Coverage**: Test all error types and autonomous fixing
2. **Context Understanding**: Verify code comprehension and intelligent modifications
3. **Iterative Fixing**: Test up to 10 iteration workflows
4. **Learning Adaptation**: Verify strategy adaptation based on patterns

**Key Frameworks**: LangChain/LangGraph, AutoGen, CrewAI

### MCP Protocol Testing
**Dynamic Context Challenges**:
1. **Data Variability**: Test with changing external data sources
2. **Multiple Integration Points**: Verify each connection individually and combined
3. **Protocol Compliance**: Ensure proper MCP message formatting
4. **Security Validation**: Test authentication, authorization, input sanitization

### WebSocket Real-Time Testing
**Connection Management**:
1. **State Management**: Monitor connection lifecycle and transitions
2. **Message Flow**: Verify bidirectional handling and progress updates
3. **Performance Metrics**: Track latency, throughput, resource utilization
4. **Resilience**: Test disconnections, reconnections, error recovery

**Tools**: Playwright, pytest-asyncio, fastapi-testclient

## Architecture Patterns

### Verification-First Development
1. **Never assume success** - every action must be verified
2. **Multiple verification points** - location, processes, network, files
3. **Graceful failure handling** - clear diagnostics and recovery
4. **Evidence-based workflows** - complete logging for debugging

### Human-in-Loop Integration
1. **Context-aware prompting** - only prompt when needed
2. **Fallback verification** - human confirmation when automation fails
3. **Clear success/failure reporting** - unambiguous results
4. **Manual override capabilities** - escape hatches for edge cases

## File Locations Quick Reference

### Core Implementation Files
- `crackerjack/verification_toolkit.py` - System state capture and verification
- `crackerjack/location_tracker.py` - Location tracking with AppleScript
- `docs/VERIFICATION_WORKFLOW.md` - Complete methodology documentation

### Automation Tools
- `~/Projects/claude/experiments/gui_prompt_system.py` - Cross-window prompts
- `~/Projects/claude/automation-tools/workflow_orchestrator.py` - Multi-window automation
- `~/Projects/claude/automation-tools/` - Additional automation utilities

### Progress Monitoring
- `crackerjack/mcp/enhanced_progress_monitor.py` - TUI monitor (Window 2, Tab 2)
- `crackerjack/mcp/websocket_server.py` - Progress WebSocket server (port 8675)
- `crackerjack/mcp/context.py` - Context management (has known initialization bug)

## Session Continuity Protocol

### For Future Chat Sessions
1. **Read this document first** - Avoid rebuilding existing knowledge
2. **Check memory system** - Use `mcp__memory__read_graph` to see stored entities
3. **Verify file locations** - Confirm automation tools are still present
4. **Test verification system** - Quick location tracking test to ensure functionality

### Memory System Integration
- Knowledge stored in MCP memory system with entity relationships
- Core entities: Paranoid Verification Workflow, Location Tracking System, GUI Prompt System
- Relationships map dependencies and integrations between components

### Knowledge Persistence Strategy
This document should be updated whenever:
- New automation tools are created
- Verification methodologies are enhanced
- Testing practices are developed
- Integration patterns are discovered
- Bugs are found and fixed

## Critical Success Factors

1. **Always verify** - Never assume automated actions worked
2. **Track location religiously** - Know where you are, were, and going
3. **Use human verification** - GUI prompts when automation fails
4. **Document everything** - Complete evidence trails for debugging
5. **Test systematically** - Multi-layer verification for all components
6. **Persist knowledge** - Update this document and memory system

**Remember**: The goal is to never rebuild this workflow knowledge from scratch again. This document and the memory system should provide complete context for future automation development.
