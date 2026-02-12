# Skills Tracking Examples

Practical examples demonstrating skills tracking integration between Crackerjack and Session-Buddy.

## Prerequisites

Ensure you have the latest dependencies installed:

```bash
cd /path/to/crackerjack
uv sync
```

## Examples

### Example 1: Basic Tracking (`example_1_basic_tracking.py`)

**Demonstrates**:

- Creating a skills tracker
- Tracking agent invocations
- Completing tracking with success/failure

**Use case**: Simple manual tracking outside `AgentOrchestrator`

**Run**:

```bash
python examples/skills_tracking/example_1_basic_tracking.py
```

**What you'll learn**:

- How to create a tracker with `create_skills_tracker()`
- Using `AgentContext.track_skill_invocation()` to start tracking
- Calling the completer function to record success/failure

______________________________________________________________________

### Example 2: Agent Recommendations (`example_2_recommendations.py`)

**Demonstrates**:

- Getting agent recommendations for a problem
- Processing recommendation results
- Using recommendations for agent selection

**Use case**: Intelligent agent selection based on historical data

**Run**:

```bash
python examples/skills_tracking/example_2_recommendations.py
```

**What you'll learn**:

- Using `AgentContext.get_skill_recommendations()` to find best agents
- Understanding recommendation scores and similarity metrics
- Selecting agents based on weighted scoring

______________________________________________________________________

### Example 3: Workflow-Phase-Aware Recommendations (`example_3_workflow_aware.py`)

**Demonstrates**:

- Getting recommendations for specific Oneiric workflow phases
- Comparing recommendations across phases
- Selecting agents based on phase-specific effectiveness

**Use case**: Optimize agent selection by workflow phase

**Run**:

```bash
python examples/skills_tracking/example_3_workflow_aware.py
```

**What you'll learn**:

- How `workflow_phase` parameter affects recommendations
- Comparing agent effectiveness across different phases
- Phase-aware agent routing for optimal performance

______________________________________________________________________

### Example 4: Error Handling (`example_4_error_handling.py`)

**Demonstrates**:

- Handling tracking errors gracefully
- Fallback when tracking unavailable
- Using NoOp tracker for testing

**Use case**: Robust error handling in production

**Run**:

```bash
python examples/skills_tracking/example_4_error_handling.py
```

**What you'll learn**:

- Safe patterns for error handling
- Using `NoOpSkillsTracker` for testing
- Graceful degradation when tracking fails

______________________________________________________________________

## Quick Start

Run all examples:

```bash
# Example 1: Basic tracking
python examples/skills_tracking/example_1_basic_tracking.py

# Example 2: Recommendations
python examples/skills_tracking/example_2_recommendations.py

# Example 3: Workflow-aware
python examples/skills_tracking/example_3_workflow_aware.py

# Example 4: Error handling
python examples/skills_tracking/example_4_error_handling.py
```

## Expected Output

Each example will output detailed information about:

- ✅ Tracker initialization
- ✅ Tracking operations
- ✅ Recommendations (if applicable)
- ✅ Error handling (if applicable)
- ✅ Summary of what was demonstrated

## Configuration

Examples use the default configuration from `settings/local.yaml`:

```yaml
skills:
  enabled: true
  backend: auto  # Tries MCP, falls back to direct
  db_path: null  # Uses default: .session-buddy/skills.db
```

To test with different configurations:

```python
# In your example
tracker = create_skills_tracker(
    session_id="test",
    backend="direct",  # Force direct backend
)

# Or disable tracking
tracker = NoOpSkillsTracker()  # Zero overhead
```

## Troubleshooting

**"Session-buddy not available"**:

```bash
# Install session-buddy
uv add session-buddy
```

**"No recommendations returned"**:

- Expected if database is empty (no historical data)
- Run some agent invocations first to populate database

**"MCP connection failed"**:

- Examples will automatically fall back to direct tracking
- Check MCP server status: `python -m crackerjack status`

## See Also

- **`docs/features/SKILLS_INTEGRATION.md`**: Complete feature documentation
- **`CLAUDE.md`**: Developer guide with integration patterns
- **`README.md`**: Skills tracking overview
