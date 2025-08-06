# Sub-Agent Monitoring Design

## Overview

Integrate sub-agent status tracking into the Crackerjack progress monitoring TUI to provide real-time visibility into the multi-agent system's operation.

## Current Progress Monitor Structure

The `CrackerjackDashboard` (in `progress_monitor.py`) currently displays:

- Job status table
- Individual job panels with progress bars
- Error counts and status
- Stage progress (fast_hooks, tests, comprehensive_hooks)

## Sub-Agent Information to Track

### Agent Activity Data

```json
{
  "agent_activity": {
    "coordinator_status": "active", // active, idle, error
    "active_agents": [
      {
        "agent_type": "FormattingAgent",
        "confidence": 0.95,
        "status": "processing", // evaluating, processing, completed, failed
        "current_issue": {
          "type": "FORMATTING",
          "message": "Ruff formatting issues",
          "priority": "medium",
          "file_count": 3
        },
        "start_time": 1642531200,
        "processing_time": 2.5
      },
      {
        "agent_type": "SecurityAgent",
        "confidence": 0.87,
        "status": "evaluating",
        "current_issue": {
          "type": "SECURITY",
          "message": "Hardcoded temp paths detected",
          "priority": "high",
          "file_count": 1
        },
        "start_time": 1642531205,
        "processing_time": 1.2
      }
    ],
    "agent_registry": {
      "total_agents": 4,
      "initialized_agents": 4,
      "agent_types": ["FormattingAgent", "TestSpecialistAgent", "TestCreationAgent", "SecurityAgent"]
    },
    "performance_stats": {
      "total_issues_processed": 15,
      "cache_hits": 3,
      "cache_misses": 12,
      "average_processing_time": 3.2,
      "success_rate": 0.87
    }
  }
}
```

## UI Design Changes

### 1. Add Agent Status Panel

Add a new collapsible panel titled "🤖 AI Agents" with:

```
┌─ 🤖 AI Agents ─────────────────────────────────────────┐
│ Coordinator: ✅ Active (4 agents)                      │
│                                                        │
│ Agent          Status      Issue Type    Confidence    │
│ ──────────────────────────────────────────────────────│
│ 🎨 Format      Processing  FORMATTING    95%          │
│ 🔒 Security    Evaluating  SECURITY      87%          │
│ 🧪 Tests       Idle        -             -            │
│ ➕ TestCreate  Idle        -             -            │
│                                                        │
│ Stats: 15 issues | 87% success | 3.2s avg             │
└────────────────────────────────────────────────────────┘
```

### 2. Enhanced Job Panels

Add agent information to individual job panels:

```
┌─ 📁 crackerjack ──────────────── 💓 ──┐
│ Iteration 2/10 | comprehensive_hooks  │
│ ████████████████████████████████ 80%  │
│                                       │
│ 🤖 Agents: 2 active, 1 cached fix     │
│ • SecurityAgent: Processing (2.1s)    │
│ • FormattingAgent: Completed ✅       │
│                                       │
│ Errors: 3 remaining, 5 fixed         │
│ └─ Hardcoded paths: 2                 │
│ └─ Import issues: 1                   │
└───────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Data Integration

1. **Extend MCP Server**: Add agent tracking to `mcp/server.py`
   - Track agent initialization in `_apply_intelligent_fixes`
   - Log agent performance metrics
   - Store agent status in progress data

2. **Update Progress Data Structure**: Extend job progress JSON to include agent data:
   ```python
   progress_data = {
       # ... existing fields ...
       "agent_activity": agent_tracker.get_status(),
       "agent_performance": agent_tracker.get_metrics()
   }
   ```

### Phase 2: UI Implementation

1. **Create AgentStatusPanel**: New widget for agent monitoring
   ```python
   class AgentStatusPanel(Widget):
       def __init__(self, agent_data: dict):
           self.agent_data = agent_data
           # DataTable for agent status
           # Progress indicators for active agents
   ```

2. **Integrate into CrackerjackDashboard**: Add agent panel to main layout

3. **Update JobPanel**: Add agent mini-status to individual jobs

### Phase 3: Real-time Updates

1. **Agent Status Streaming**: WebSocket updates for agent status changes
2. **Performance Metrics**: Rolling averages for processing times
3. **Cache Hit Visualization**: Show cached vs. new fixes

## Technical Requirements

### Agent Tracking Service

```python
class AgentTracker:
    def __init__(self):
        self.active_agents = {}
        self.performance_metrics = {}

    def track_agent_start(self, agent_type: str, issue: Issue):
        """Track when an agent starts processing."""

    def track_agent_complete(self, agent_type: str, result: FixResult):
        """Track when an agent completes processing."""

    def get_status(self) -> dict:
        """Get current agent status for progress reporting."""

    def get_metrics(self) -> dict:
        """Get performance metrics."""
```

### Integration Points

1. **AgentCoordinator**: Instrument with tracking calls
2. **MCP Server**: Include agent data in progress updates
3. **Progress Monitor**: Parse and display agent data

## Benefits

1. **Transparency**: Users see which agents are working on their code
2. **Performance Insight**: Identify slow or failing agents
3. **Debugging**: Understand agent routing decisions
4. **Trust Building**: Show AI agent decision-making process
5. **Optimization**: Identify bottlenecks in agent processing

## Example Flow

1. User runs `/crackerjack:run`
2. Coordinator initializes 4 agents
3. Progress TUI shows "🤖 AI Agents: 4 ready"
4. Issues detected: 10 formatting, 3 security, 2 test failures
5. Agent assignment displayed in real-time:
   - FormattingAgent: 10 issues (confidence 95%)
   - SecurityAgent: 3 issues (confidence 90%)
   - TestSpecialistAgent: 2 issues (confidence 88%)
6. Processing updates show in agent panel
7. Completion shows success rates and times

This design provides comprehensive visibility into the multi-agent system while integrating seamlessly with the existing progress monitoring infrastructure.
