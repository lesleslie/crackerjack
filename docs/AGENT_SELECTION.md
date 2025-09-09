# Agent Selection System

## Overview

Crackerjack's AI agent system automatically selects the most appropriate agent to handle each detected issue. The system uses a sophisticated confidence-based selection algorithm with built-in agent preferences to ensure reliable, predictable fixes.

## Selection Algorithm

### 1. Confidence-Based Selection

Each agent implements a `can_handle(issue)` method that returns a confidence score (0.0-1.0) indicating how well it can handle a specific issue type. The system:

1. **Filters Specialists**: Only agents that declare support for the issue type are considered
1. **Evaluates Confidence**: Each specialist agent returns a confidence score
1. **Applies Preference Logic**: Built-in agents receive preference when scores are close
1. **Selects Best Match**: Returns the agent with the highest adjusted confidence

### 2. Built-in Agent Preference

When confidence scores between agents are close (within 5% threshold), the system prefers built-in Crackerjack agents over external agents for these reasons:

- **Deep Integration**: Built-in agents understand Crackerjack's internal architecture
- **Consistent Patterns**: Use established coding patterns and conventions
- **Reliable Caching**: Agent decisions are cached for faster subsequent runs
- **Quality Assurance**: All built-in agents are tested against Crackerjack's quality standards

**Threshold**: 5% (0.05) difference - provides balance between fairness and reliability.

## Built-in Agent Capabilities

Crackerjack includes 10 specialized built-in agents:

| Agent | Confidence Range | Primary Focus | Issue Types |
|-------|-----------------|---------------|-------------|
| **RefactoringAgent** | 0.9 | Complexity reduction | `COMPLEXITY`, `DEAD_CODE` |
| **PerformanceAgent** | 0.85 | Performance optimization | `PERFORMANCE` |
| **SecurityAgent** | 0.8 | Security vulnerabilities | `SECURITY` |
| **DocumentationAgent** | 0.8 | Documentation consistency | `DOCUMENTATION` |
| **TestCreationAgent** | 0.8 | Test failures and creation | `TEST_FAILURE`, `COVERAGE_IMPROVEMENT` |
| **DRYAgent** | 0.8 | Code duplication | `DRY_VIOLATION` |
| **FormattingAgent** | 0.8 | Code style | `FORMATTING` |
| **ImportOptimizationAgent** | 0.7 | Import organization | `IMPORT_ERROR` |
| **TestSpecialistAgent** | 0.8 | Advanced testing | `TEST_ORGANIZATION` |
| **ArchitectAgent** | 0.9 | Architectural planning | Multiple (proactive mode) |

## Activation and Usage

### CLI Activation

The agent selection system is activated via the `--ai-agent` flag:

```bash
# Enable AI agent auto-fixing
python -m crackerjack --ai-agent -t

# Debug agent selection process
python -m crackerjack --ai-agent --ai-debug -t
```

### Workflow Integration

The agent system is integrated into three workflow orchestrators:

1. **WorkflowOrchestrator** (`_setup_agent_coordinator`)
1. **AsyncWorkflowOrchestrator** (`_create_agent_coordinator`)
1. **ProactiveWorkflow** (`_architect_agent_coordinator`)

All orchestrators use the same `AgentCoordinator` class, ensuring consistent selection logic.

### Selection Process Flow

```
Issue Detected
      ↓
Filter by Issue Type (get applicable agents)
      ↓
Evaluate Confidence (call can_handle() on each)
      ↓
Apply Selection Logic:
  - Find highest confidence score
  - Check for built-in agents within 5% threshold
  - Prefer built-in if close scores exist
      ↓
Return Selected Agent
      ↓
Execute analyze_and_fix()
      ↓
Cache Decision (if confidence > 0.7)
```

## Configuration

### Confidence Thresholds

- **Minimum Confidence**: 0.0 (agents can decline by returning 0.0)
- **Caching Threshold**: 0.7 (successful decisions cached for reuse)
- **Preference Threshold**: 0.05 (5% difference triggers built-in preference)

### Issue Type Mapping

Each issue type is handled by specific agents based on their declared capabilities:

```python
class IssueType(Enum):
    FORMATTING = "formatting"  # FormattingAgent
    TYPE_ERROR = "type_error"  # ArchitectAgent, others
    SECURITY = "security"  # SecurityAgent
    TEST_FAILURE = "test_failure"  # TestCreationAgent
    IMPORT_ERROR = "import_error"  # ImportOptimizationAgent
    COMPLEXITY = "complexity"  # RefactoringAgent, ArchitectAgent
    DEAD_CODE = "dead_code"  # RefactoringAgent
    DEPENDENCY = "dependency"  # ArchitectAgent
    DRY_VIOLATION = "dry_violation"  # DRYAgent, ArchitectAgent
    PERFORMANCE = "performance"  # PerformanceAgent, ArchitectAgent
    DOCUMENTATION = "documentation"  # DocumentationAgent, ArchitectAgent
    TEST_ORGANIZATION = "test_organization"  # TestSpecialistAgent, ArchitectAgent
    COVERAGE_IMPROVEMENT = "coverage_improvement"  # TestCreationAgent
```

## Debugging and Monitoring

### Debug Logging

When `--ai-debug` is enabled, the system logs detailed selection information:

```
INFO: Preferring built-in agent RefactoringAgent (score: 0.87)
      over ExternalAgent (score: 0.90)
      due to 0.03 threshold preference
```

### Agent Tracking

The `AgentTracker` monitors:

- Agent processing times
- Success/failure rates
- Confidence distributions
- Selection patterns

### Performance Caching

Successful agent decisions (confidence > 0.7) are cached using issue hash keys:

- Hash includes: issue type, message, file path, line number
- Cached decisions bypass selection process for identical issues
- Cache improves performance on repeated issues

## Best Practices

### For Agent Development

1. **Accurate Confidence**: Return realistic confidence scores based on actual capability
1. **Issue Type Specificity**: Only claim support for issues you can reliably handle
1. **Consistent Patterns**: Follow established conventions for predictable behavior
1. **Error Handling**: Handle exceptions gracefully to avoid disrupting selection

### For Users

1. **Use Built-in Agents**: Trust the preference system for reliable fixes
1. **Monitor Debug Output**: Use `--ai-debug` to understand selection decisions
1. **Report Issues**: File bugs if agent selection seems inappropriate
1. **Trust Caching**: Let the system cache successful patterns for speed

## Technical Implementation

### Selection Method

The core selection logic in `AgentCoordinator._find_best_specialist()`:

```python
async def _find_best_specialist(
    self,
    specialists: list[SubAgent],
    issue: Issue,
) -> SubAgent | None:
    best_agent = None
    best_score = 0.0
    candidates: list[tuple[SubAgent, float]] = []

    CLOSE_SCORE_THRESHOLD = 0.05

    # Collect all agent scores
    for agent in specialists:
        score = await agent.can_handle(issue)
        candidates.append((agent, score))
        if score > best_score:
            best_score = score
            best_agent = agent

    # Apply preference for built-in agents when scores are close
    if best_agent and best_score > 0:
        for agent, score in candidates:
            if agent != best_agent and self._is_built_in_agent(agent):
                score_difference = best_score - score
                if 0 < score_difference <= CLOSE_SCORE_THRESHOLD:
                    # Built-in agent gets preference
                    best_agent = agent
                    best_score = score
                    break

    return best_agent
```

### Built-in Agent Detection

```python
def _is_built_in_agent(self, agent: SubAgent) -> bool:
    """Check if agent is a built-in Crackerjack agent."""
    built_in_agent_names = {
        "ArchitectAgent",
        "DocumentationAgent",
        "DRYAgent",
        "FormattingAgent",
        "ImportOptimizationAgent",
        "PerformanceAgent",
        "RefactoringAgent",
        "SecurityAgent",
        "TestCreationAgent",
        "TestSpecialistAgent",
    }
    return agent.__class__.__name__ in built_in_agent_names
```

## Future Enhancements

Potential improvements to the agent selection system:

1. **Dynamic Thresholds**: Adjust preference threshold based on agent performance history
1. **Multi-Agent Collaboration**: Allow multiple agents to work on complex issues
1. **Machine Learning**: Use ML to optimize confidence scoring and selection
1. **Agent Specialization**: Create more focused agents for specific domains
1. **Performance Metrics**: Track and optimize selection effectiveness over time

## Troubleshooting

### Common Issues

**Agent Not Selected**

- Check issue type mapping
- Verify agent confidence calculation
- Review debug logs for selection reasoning

**Unexpected Agent Choice**

- Enable `--ai-debug` to see confidence scores
- Check if built-in preference was applied
- Verify issue classification is correct

**Poor Fix Quality**

- Agent may have overestimated confidence
- Consider filing issue for agent improvement
- Check if external agent would be more appropriate

**Cache Not Working**

- Ensure confidence > 0.7 for caching
- Check issue hash consistency
- Verify cache configuration

The agent selection system provides a robust, predictable foundation for AI-assisted code quality improvements in Crackerjack.
