> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | Intelligence

# Intelligence

AI-powered agent orchestration, selection, and adaptive learning for intelligent code quality automation.

## Overview

The intelligence package provides the core AI agent system for crackerjack, including agent registry, orchestration, selection, and adaptive learning. This system coordinates 12 specialized AI agents to automatically fix code quality issues with confidence scoring and pattern learning.

## Core Components

### Agent Registry (`agent_registry.py`)

Central registry for all AI agents with capability tracking:

**Features:**

- **Agent Registration** - Register agents with metadata and capabilities
- **Capability Discovery** - Find agents by capability requirements
- **Source Tracking** - Track agent origin (built-in, plugin, custom)
- **Metadata Management** - Store agent descriptions, versions, and configuration
- **Dynamic Loading** - Load agents on-demand from various sources

**Agent Metadata:**

```python
@dataclass
class AgentMetadata:
    name: str  # Agent identifier
    description: str  # Human-readable description
    version: str  # Agent version
    capabilities: list[AgentCapability]  # What the agent can do
    confidence_threshold: float  # Minimum confidence to execute
    source: AgentSource  # Where agent came from
```

**Agent Capabilities:**

```python
class AgentCapability(Enum):
    REFACTORING = "refactoring"  # Code restructuring
    PERFORMANCE = "performance"  # Performance optimization
    SECURITY = "security"  # Security fixes
    DOCUMENTATION = "documentation"  # Documentation updates
    TESTING = "testing"  # Test creation/fixes
    DRY = "dry"  # Code deduplication
    FORMATTING = "formatting"  # Code formatting
    IMPORT_OPTIMIZATION = "import_opt"  # Import cleanup
    SEMANTIC_ANALYSIS = "semantic"  # Semantic understanding
    ARCHITECTURE = "architecture"  # Architecture recommendations
    PROACTIVE_PREVENTION = "proactive"  # Proactive issue prevention
```

**Agent Sources:**

```python
class AgentSource(Enum):
    BUILTIN = "builtin"  # Crackerjack built-in agents
    PLUGIN = "plugin"  # Third-party plugins
    CUSTOM = "custom"  # User-defined agents
```

### Agent Selector (`agent_selector.py`)

Intelligent agent selection based on task requirements:

**Features:**

- **Task Analysis** - Analyzes error context to determine requirements
- **Capability Matching** - Matches tasks to agent capabilities
- **Confidence Scoring** - Scores each agent's suitability for task
- **Multi-Agent Selection** - Can select multiple agents for complex tasks
- **Fallback Strategy** - Provides fallback agents if primary unavailable

**Task Context:**

```python
@dataclass
class TaskContext:
    error_type: str  # Type of error/issue
    file_path: Path  # Affected file
    error_message: str  # Full error message
    stack_trace: str | None  # Stack trace if available
    code_snippet: str | None  # Relevant code snippet
    severity: str  # Error severity level
```

**Agent Scoring:**

```python
@dataclass
class AgentScore:
    agent_name: str  # Agent identifier
    score: float  # Suitability score (0.0-1.0)
    confidence: float  # Agent confidence threshold
    reasoning: str  # Why this agent was selected
    capabilities_matched: list[str]  # Matched capabilities
```

### Agent Orchestrator (`agent_orchestrator.py`)

Coordinates agent execution with strategy patterns:

**Features:**

- **Execution Strategies** - Sequential, parallel, or pipeline execution
- **Result Aggregation** - Combines results from multiple agents
- **Error Handling** - Graceful degradation on agent failures
- **Progress Tracking** - Real-time execution progress
- **Rollback Support** - Can rollback failed agent changes

**Execution Strategies:**

```python
class ExecutionStrategy(Enum):
    SEQUENTIAL = "sequential"  # One agent at a time
    PARALLEL = "parallel"  # All agents concurrently
    PIPELINE = "pipeline"  # Output of one feeds next
    CONDITIONAL = "conditional"  # Execute based on conditions
```

**Execution Request:**

```python
@dataclass
class ExecutionRequest:
    task_context: TaskContext  # What to fix
    selected_agents: list[str]  # Which agents to use
    strategy: ExecutionStrategy  # How to execute
    max_concurrent: int = 3  # Max parallel agents
    timeout: int = 300  # Execution timeout
    rollback_on_failure: bool = True  # Rollback if failed
```

**Execution Result:**

```python
@dataclass
class ExecutionResult:
    success: bool  # Overall success
    agents_executed: list[str]  # Agents that ran
    changes_made: list[dict]  # Code changes applied
    errors: list[str]  # Errors encountered
    execution_time: float  # Total execution time
    confidence_scores: dict[str, float]  # Agent confidence scores
```

### Adaptive Learning (`adaptive_learning.py`)

Learns from successful/failed fixes to improve over time:

**Features:**

- **Pattern Learning** - Learns successful fix patterns
- **Failure Analysis** - Analyzes why fixes failed
- **Confidence Adjustment** - Adjusts agent confidence based on history
- **Pattern Caching** - Caches successful patterns for reuse
- **Success Rate Tracking** - Tracks per-agent success rates

**Learning System:**

```python
class AdaptiveLearningSystem:
    def record_success(
        self, agent_name: str, task_context: TaskContext, fix_applied: str
    ) -> None:
        """Record successful fix for learning."""

    def record_failure(
        self, agent_name: str, task_context: TaskContext, error: str
    ) -> None:
        """Record failed fix for analysis."""

    def get_success_rate(self, agent_name: str) -> float:
        """Get agent success rate."""

    def recommend_agent(self, task_context: TaskContext) -> tuple[str, float]:
        """Recommend best agent based on learning."""
```

### Integration (`integration.py`)

Integration layer connecting intelligence system to crackerjack:

**Features:**

- **Workflow Integration** - Integrates agents with ACB workflows
- **Error Routing** - Routes errors to appropriate agents
- **Result Processing** - Processes agent results for display
- **Configuration Management** - Manages agent system configuration

## The 12 Specialized Agents

Crackerjack's intelligence system coordinates 12 specialized agents (defined in `/home/user/crackerjack/crackerjack/agents/`):

### Code Quality Agents

1. **RefactoringAgent** (0.9 confidence)

   - **Capabilities**: REFACTORING
   - **Focus**: Complexity ≤15, dead code removal, method extraction
   - **Triggers**: Cognitive complexity violations, long methods

1. **DRYAgent** (0.8 confidence)

   - **Capabilities**: DRY
   - **Focus**: Code duplication detection and elimination
   - **Triggers**: Duplicate code patterns, repeated logic

1. **FormattingAgent** (0.8 confidence)

   - **Capabilities**: FORMATTING
   - **Focus**: Code style, formatting violations
   - **Triggers**: Ruff format issues, style violations

1. **ImportOptimizationAgent**

   - **Capabilities**: IMPORT_OPTIMIZATION
   - **Focus**: Import cleanup, unused imports, import organization
   - **Triggers**: Unused imports, import violations

### Performance & Security Agents

5. **PerformanceAgent** (0.85 confidence)

   - **Capabilities**: PERFORMANCE
   - **Focus**: O(n²) detection, optimization opportunities
   - **Triggers**: Performance anti-patterns, slow code

1. **SecurityAgent** (0.8 confidence)

   - **Capabilities**: SECURITY
   - **Focus**: Hardcoded paths, unsafe operations, injection vulnerabilities
   - **Triggers**: Bandit violations, security warnings

### Testing & Documentation Agents

7. **TestCreationAgent** (0.8 confidence)

   - **Capabilities**: TESTING
   - **Focus**: Test failures, fixture creation, test coverage
   - **Triggers**: Test failures, missing tests, low coverage

1. **TestSpecialistAgent** (0.8 confidence)

   - **Capabilities**: TESTING
   - **Focus**: Advanced testing scenarios, complex fixtures, mocking
   - **Triggers**: Complex test failures, async test issues

1. **DocumentationAgent** (0.8 confidence)

   - **Capabilities**: DOCUMENTATION
   - **Focus**: Changelog, README consistency, API documentation
   - **Triggers**: Documentation inconsistencies, missing docs

### Advanced Intelligence Agents

10. **SemanticAgent** (0.85 confidence)

    - **Capabilities**: SEMANTIC_ANALYSIS
    - **Focus**: Semantic analysis, code comprehension, intelligent refactoring
    - **Triggers**: Semantic violations, architectural issues

01. **ArchitectAgent** (0.85 confidence)

    - **Capabilities**: ARCHITECTURE
    - **Focus**: Architecture patterns, design recommendations, system optimization
    - **Triggers**: Architectural violations, design issues

01. **EnhancedProactiveAgent** (0.9 confidence)

    - **Capabilities**: PROACTIVE_PREVENTION
    - **Focus**: Proactive prevention, predictive monitoring, preemptive optimization
    - **Triggers**: Quality trends, predicted issues

## Usage Examples

### Agent Registry

```python
from crackerjack.intelligence import AgentRegistry, AgentCapability, get_agent_registry

registry = get_agent_registry()

# Find agents by capability
refactoring_agents = registry.get_agents_by_capability(AgentCapability.REFACTORING)

for agent in refactoring_agents:
    print(f"Agent: {agent.name}")
    print(f"  Confidence: {agent.confidence_threshold}")
    print(f"  Description: {agent.description}")

# Get specific agent
agent = registry.get_agent("refactoring")
```

### Agent Selection

```python
from crackerjack.intelligence import AgentSelector, TaskContext
from pathlib import Path

selector = AgentSelector(registry=registry)

# Create task context from error
task = TaskContext(
    error_type="complexity",
    file_path=Path("src/complex_module.py"),
    error_message="Complexity of 18 exceeds maximum of 15",
    severity="high",
)

# Select best agents for task
selected = selector.select_agents(task, max_agents=3)

for agent_score in selected:
    print(f"Agent: {agent_score.agent_name}")
    print(f"  Score: {agent_score.score:.2f}")
    print(f"  Reasoning: {agent_score.reasoning}")
```

### Agent Orchestration

```python
from crackerjack.intelligence import (
    AgentOrchestrator,
    ExecutionRequest,
    ExecutionStrategy,
    get_agent_orchestrator,
)

orchestrator = get_agent_orchestrator()

# Execute agents with strategy
request = ExecutionRequest(
    task_context=task,
    selected_agents=["refactoring", "semantic"],
    strategy=ExecutionStrategy.SEQUENTIAL,
    timeout=300,
    rollback_on_failure=True,
)

result = await orchestrator.execute(request)

if result.success:
    print(f"✅ Fixed in {result.execution_time:.1f}s")
    print(f"Agents used: {', '.join(result.agents_executed)}")
    print(f"Changes made: {len(result.changes_made)}")
else:
    print(f"❌ Failed: {', '.join(result.errors)}")
```

### Adaptive Learning

```python
from crackerjack.intelligence import AdaptiveLearningSystem, get_learning_system

learning = get_learning_system()

# Record successful fix
learning.record_success(
    agent_name="refactoring",
    task_context=task,
    fix_applied="Extracted method to reduce complexity",
)

# Get success rate
success_rate = learning.get_success_rate("refactoring")
print(f"RefactoringAgent success rate: {success_rate:.1%}")

# Get recommendation based on learning
recommended_agent, confidence = learning.recommend_agent(task)
print(f"Recommended: {recommended_agent} (confidence: {confidence:.2f})")
```

### Full AI-Fixing Workflow

```python
from crackerjack.intelligence import (
    get_agent_registry,
    AgentSelector,
    get_agent_orchestrator,
    get_learning_system,
    ExecutionRequest,
    ExecutionStrategy,
    TaskContext,
)
from pathlib import Path


async def ai_fix_error(error_message: str, file_path: Path) -> bool:
    # Setup
    registry = get_agent_registry()
    selector = AgentSelector(registry=registry)
    orchestrator = get_agent_orchestrator()
    learning = get_learning_system()

    # Create task context
    task = TaskContext(
        error_type="auto_detected",
        file_path=file_path,
        error_message=error_message,
        severity="high",
    )

    # Select agents
    selected = selector.select_agents(task, max_agents=2)
    agent_names = [score.agent_name for score in selected]

    # Execute agents
    request = ExecutionRequest(
        task_context=task,
        selected_agents=agent_names,
        strategy=ExecutionStrategy.SEQUENTIAL,
        timeout=300,
    )

    result = await orchestrator.execute(request)

    # Record for learning
    if result.success:
        for agent_name in result.agents_executed:
            learning.record_success(
                agent_name=agent_name,
                task_context=task,
                fix_applied=str(result.changes_made),
            )
    else:
        for agent_name in result.agents_executed:
            learning.record_failure(
                agent_name=agent_name, task_context=task, error=str(result.errors)
            )

    return result.success
```

## Configuration

Intelligence system configuration through ACB Settings:

```yaml
# settings/crackerjack.yaml

# Agent system
ai_fix_enabled: true
ai_debug: false  # Debug mode for agent development
min_agent_confidence: 0.7  # Minimum confidence to execute

# Agent selection
max_agents_per_task: 3
agent_timeout: 300
agent_parallel_execution: false

# Adaptive learning
learning_enabled: true
learning_cache_ttl: 86400  # 24 hours
success_rate_window: 100  # Last 100 executions

# Execution strategy
default_execution_strategy: "sequential"  # sequential, parallel, pipeline
rollback_on_failure: true
max_rollback_attempts: 1

# Agent-specific configuration
agent_config:
  refactoring:
    max_complexity: 15
    enable_method_extraction: true
  security:
    check_hardcoded_secrets: true
    check_sql_injection: true
  testing:
    auto_create_fixtures: true
    min_coverage_target: 80
```

## Integration with Workflows

Intelligence system integrates with ACB workflows for automated fixing:

```python
from crackerjack.workflows import CrackerjackWorkflowEngine
from crackerjack.intelligence import get_agent_orchestrator

engine = CrackerjackWorkflowEngine()
orchestrator = get_agent_orchestrator()


# Register AI fixing as workflow action
@engine.register_action("ai_fix")
async def ai_fix_action(context):
    errors = context.get("errors", [])
    fixed_count = 0

    for error in errors:
        task = create_task_from_error(error)
        selected = selector.select_agents(task)
        request = create_execution_request(task, selected)

        result = await orchestrator.execute(request)
        if result.success:
            fixed_count += 1

    return {"fixed_count": fixed_count, "total_errors": len(errors)}
```

## Best Practices

1. **Set Appropriate Confidence Thresholds** - Don't set too low or agents may make incorrect changes
1. **Use Learning System** - Enable adaptive learning to improve agent selection over time
1. **Start with High-Confidence Agents** - Begin with RefactoringAgent (0.9) and EnhancedProactiveAgent (0.9)
1. **Monitor Success Rates** - Track agent success rates and adjust confidence thresholds
1. **Sequential for Safety** - Use sequential execution strategy for safety-critical fixes
1. **Enable Rollback** - Always enable rollback for automatic agent execution
1. **Batch Similar Issues** - Group similar errors for more efficient agent execution
1. **Use Semantic Agent** - Leverage SemanticAgent for complex refactoring scenarios
1. **Debug Mode** - Use `--ai-debug` flag when developing or testing agents
1. **Review Changes** - Always review agent-generated changes before committing

## Performance Considerations

### Agent Execution Time

```
Single agent (RefactoringAgent): ~5-15s per fix
Multiple agents (sequential):    ~15-45s per task
Multiple agents (parallel):      ~10-20s per task
Adaptive learning overhead:      ~1-2s per task
```

### Learning System Performance

```
Pattern cache size: ~10-50MB (typical project)
Learning lookup time: <100ms
Success rate calculation: <50ms
Recommendation generation: <200ms
```

## Related

- [Agents](../agents/README.md) - Individual agent implementations
- [Workflows](../workflows/README.md) - Workflow integration
- [Services/AI](../services/ai/README.md) - AI service layer
- [CLAUDE.md](../../docs/guides/CLAUDE.md) - AI agent system overview

## Future Enhancements

- [ ] Agent marketplace for community-contributed agents
- [ ] Multi-agent collaboration for complex tasks
- [ ] Real-time agent performance dashboard
- [ ] Agent A/B testing framework
- [ ] Transfer learning between projects
- [ ] Agent ensemble methods for higher accuracy
- [ ] Custom agent development SDK
- [ ] Agent explainability improvements
