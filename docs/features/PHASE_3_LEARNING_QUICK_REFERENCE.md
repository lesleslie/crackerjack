# Phase 3: Learning & Optimization - Quick Reference

## Overview

Phase 3 adds self-learning capabilities to crackerjack ecosystem, enabling components to improve their performance based on historical usage patterns.

## Configuration

Enable/disable learning in `settings/local.yaml` or `settings/crackerjack.yaml`:

```yaml
learning:
  enabled: true
  effectiveness_tracking_enabled: true
  min_sample_size: 10
  adaptation_rate: 0.1
```

## Components

### 1. Skills Effectiveness Tracking

**Purpose**: Learn which agents/skills work best for specific problems

**Database**: `.crackerjack/skills_effectiveness.db`

**Usage**:

```python
from crackerjack.integration import create_skills_effectiveness_tracker

tracker = create_skills_effectiveness_tracker(
    enabled=True,
    db_path=".crackerjack/skills_effectiveness.db",
    min_sample_size=10,
)

# Track agent execution
completer = tracker.track_skill_attempt(
    skill_name="python-pro",
    agent_name="PythonProAgent",
    user_query="Fix type errors in agents module",
    query_embedding=embedding,
    context={"phase": "comprehensive_hooks"},
    alternatives_considered=["code-reviewer", "refactoring-agent"],
)

# Complete with result
completer(success=True, confidence=0.9, execution_time_ms=1500)
```

**Metrics**:

- Success rate per skill
- Average confidence when successful
- Average execution time
- Best/worst contexts for each skill

### 2. Query Optimization Learning

**Purpose**: Improve search query effectiveness through user feedback

**Database**: `.crackerjack/query_learning.db`

**Usage**:

```python
from crackerjack.integration import create_query_optimizer

optimizer = create_query_optimizer(
    enabled=True,
    db_path=".crackerjack/query_learning.db",
    min_interactions=5,
)

# Track search results
completer = optimizer.track_search_results(
    query="type errors in agents",
    results=[{"id": "1", "score": 0.9}, ...],
)

# Complete with user interaction
completer(
    results_clicked=["1"],
    user_satisfaction=0.9,
    outcome="success",
)

# Get query suggestions
suggestions = optimizer.get_query_improvements(
    partial_query="typ",
    similar_queries=["type errors", "type hints"],
)
```

**Features**:

- Click-through rate tracking
- Query pattern learning
- Adaptive ranking based on feedback
- Query reformulation suggestions

### 3. DAG Optimization Learning

**Purpose**: Learn optimal DAG execution strategies

**Database**: `.crackerjack/dag_learning.db`

**Usage**:

```python
from crackerjack.integration import create_dag_optimizer

optimizer = create_dag_optimizer(
    enabled=True,
    db_path=".crackerjack/dag_learning.db",
    min_executions=5,
)

# Track DAG execution
optimizer.track_dag_execution(
    dag_structure={"tasks": ["test", "lint", "typecheck"]},
    task_ordering=["test", "lint", "typecheck"],
    parallelization_strategy="sequential",
    execution_time_ms=5000,
    success=True,
    resource_usage={"cpu": 50, "memory": 1024},
    conflicts_detected=0,
)

# Get optimal strategy
strategy = optimizer.get_execution_strategy(
    dag_structure={"tasks": ["test", "lint"]},
    context={"workers": 4},
)

if strategy:
    print(f"Use: {strategy.recommended_ordering}")
    print(f"Confidence: {strategy.confidence:.2%}")
```

**Learned**:

- Optimal task ordering
- Parallelization strategies
- Expected execution times
- Resource usage patterns

### 4. Adapter Selection Learning

**Purpose**: Learn which adapters work best for file types

**Database**: `.crackerjack/adapter_learning.db`

**Usage**:

```python
from crackerjack.integration import create_adapter_learner

learner = create_adapter_learner(
    enabled=True,
    db_path=".crackerjack/adapter_learning.db",
    min_attempts=5,
)

# Track adapter execution
learner.track_adapter_execution(
    adapter_name="zuban",
    file_path="agents/base.py",
    file_size=1024,
    project_context={"language": "python", "framework": "none"},
    success=True,
    execution_time_ms=500,
    error_type=None,
)

# Get recommendation
recommended = learner.get_adapter_recommendation(
    file_path="test.py",
    project_context={"language": "python"},
    available_adapters=["zuban", "pyright", "mypy"],
)

print(f"Recommended adapter: {recommended}")
```

**Tracked**:

- Success rate by file type
- Execution times
- Common error types
- Best/worst project contexts

### 5. Workflow Strategy Memory

**Purpose**: Learn which workflows work best for project characteristics

**Database**: `.crackerjack/workflow_learning.db`

**Usage**:

```python
from crackerjack.integration import create_workflow_learner

learner = create_workflow_learner(
    enabled=True,
    db_path=".crackerjack/workflow_learning.db",
    min_executions=5,
)

# Track workflow execution
learner.track_workflow_execution(
    workflow_id="comprehensive_hooks",
    project_context={
        "size": "large",
        "language": "python",
        "complexity": "high",
    },
    execution_strategy="parallel",
    execution_time_ms=30000,
    success=True,
    quality_score=0.85,
    resource_efficiency=0.9,
)

# Get recommendation
recommendation = learner.get_workflow_recommendation(
    project_metrics={
        "size": "medium",
        "complexity": "high",
        "language": "python",
    },
    available_workflows=["fast_hooks", "comprehensive_hooks"],
)

if recommendation:
    print(f"Use: {recommendation.workflow_id}")
    print(f"Strategy: {recommendation.recommended_strategy}")
    print(f"Expected quality: {recommendation.expected_quality_score:.2%}")
```

**Learned**:

- Workflow effectiveness by project characteristics
- Optimal execution strategies
- Quality and efficiency scores
- Similar project detection

## Integration Examples

### Agent Orchestrator Integration

```python
from crackerjack.integration import create_skills_effectiveness_tracker
from crackerjack.intelligence import AgentOrchestrator

class LearningAgentOrchestrator(AgentOrchestrator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.effectiveness_tracker = create_skills_effectiveness_tracker()

    def select_agent(self, issue, candidates):
        # Get effectiveness-based boosts
        query_embedding = self._get_embedding(issue.message)
        boosts = self.effectiveness_tracker.get_skill_boosts(
            user_query=issue.message,
            query_embedding=query_embedding,
            context={"phase": self.current_phase},
            candidates=candidates,
        )

        # Apply boosts to selection
        # ... selection logic with boosts ...

        # Track execution
        completer = self.effectiveness_tracker.track_skill_attempt(
            skill_name=selected_agent,
            agent_name=agent_class.__name__,
            user_query=issue.message,
            query_embedding=query_embedding,
            context={"phase": self.current_phase},
            alternatives_considered=candidates,
        )

        return agent, completer
```

### Oneiric Integration

```python
from crackerjack.integration import create_dag_optimizer
from crackerjack.runtime.oneiric_workflow import OneiricWorkflow

class LearningOneiricWorkflow(OneiricWorkflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dag_optimizer = create_dag_optimizer()

    def execute_dag(self, dag_structure, context):
        # Check for learned strategy
        strategy = self.dag_optimizer.get_execution_strategy(
            dag_structure=dag_structure,
            context=context,
        )

        if strategy:
            # Use learned strategy
            task_order = strategy.recommended_ordering
            parallel_config = strategy.recommended_parallelization
        else:
            # Use default strategy
            task_order = self._default_ordering(dag_structure)
            parallel_config = {}

        # Execute and track
        start_time = time.time()
        success = self._execute_tasks(task_order, parallel_config)
        execution_time = int((time.time() - start_time) * 1000)

        self.dag_optimizer.track_dag_execution(
            dag_structure=dag_structure,
            task_ordering=task_order,
            parallelization_strategy=strategy.strategy if strategy else "default",
            execution_time_ms=execution_time,
            success=success,
            resource_usage=self._get_resource_usage(),
            conflicts_detected=self._get_conflicts(),
        )

        return success
```

## Configuration File Example

Create `settings/local.yaml`:

```yaml
# Phase 3: Learning & Optimization
learning:
  enabled: true
  effectiveness_tracking_enabled: true
  min_sample_size: 10
  adaptation_rate: 0.1

  # Individual component settings
  skills_effectiveness_db: .crackerjack/skills_effectiveness.db
  query_learning_db: .crackerjack/query_learning.db
  dag_learning_db: .crackerjack/dag_learning.db
  adapter_learning_db: .crackerjack/adapter_learning.db
  workflow_learning_db: .crackerjack/workflow_learning.db

  # Minimum sample sizes
  query_min_interactions: 5
  dag_min_executions: 5
  adapter_min_attempts: 5
  workflow_min_executions: 5
```

## Monitoring Learning Progress

### Check Skills Effectiveness

```python
from crackerjack.integration import create_skills_effectiveness_tracker

tracker = create_skills_effectiveness_tracker()

# Get metrics for a skill
metrics = tracker.get_skill_metrics("python-pro")

if metrics:
    print(f"Success rate: {metrics.success_rate:.2%}")
    print(f"Total attempts: {metrics.total_attempts}")
    print(f"Avg time: {metrics.avg_execution_time_ms:.0f}ms")
    print(f"Best contexts: {metrics.best_contexts}")
else:
    print("Insufficient data for metrics")
```

### Check Query Patterns

```python
from crackerjack.integration import create_query_optimizer

optimizer = create_query_optimizer()

# Get click-through rate
ctr = optimizer.get_click_through_rate("type errors in agents")
print(f"Click-through rate: {ctr:.2%}")

# Get query suggestions
suggestions = optimizer.get_query_improvements("typ", ["type", "test"])
for suggestion in suggestions:
    print(f"Try: {suggestion.suggested_query}")
    print(f"Confidence: {suggestion.confidence:.2%}")
```

### Check Adapter Performance

```python
from crackerjack.integration import create_adapter_learner

learner = create_adapter_learner()

# Get adapter stats
stats = learner.get_adapter_stats("zuban", ".py")
if stats:
    print(f"Success rate: {stats.success_rate:.2%}")
    print(f"Total attempts: {stats.total_attempts}")
    print(f"Common errors: {stats.common_errors}")

# Get best adapters for file type
best = learner.adapter_learner.get_best_adapters_for_file_type(".py")
for adapter_name, success_rate in best:
    print(f"{adapter_name}: {success_rate:.2%}")
```

### Check Workflow Effectiveness

```python
from crackerjack.integration import create_workflow_learner

learner = create_workflow_learner()

# Get workflow stats
stats = learner.get_workflow_stats(
    "comprehensive_hooks",
    "parallel",
)
if stats:
    print(f"Success rate: {stats.success_rate:.2%}")
    print(f"Quality score: {stats.avg_quality_score:.2%}")
    print(f"Efficiency: {stats.avg_resource_efficiency:.2%}")

# Get best strategies
strategies = learner.workflow_learner.get_best_strategies_for_workflow(
    "comprehensive_hooks"
)
for strategy, score in strategies:
    print(f"{strategy}: {score:.2%}")
```

## Database Maintenance

### Backup Learning Data

```bash
# Backup all learning databases
mkdir -p .crackerjack/backups
cp .crackerjack/*.db .crackerjack/backups/
```

### Reset Learning Data

```python
import os
from pathlib import Path

# Remove learning databases to start fresh
db_files = [
    ".crackerjack/skills_effectiveness.db",
    ".crackerjack/query_learning.db",
    ".crackerjack/dag_learning.db",
    ".crackerjack/adapter_learning.db",
    ".crackerjack/workflow_learning.db",
]

for db_file in db_files:
    if Path(db_file).exists():
        os.remove(db_file)
        print(f"Reset: {db_file}")
```

## Troubleshooting

### Learning Not Working

**Problem**: Learning databases not being created

**Solution**:

1. Check `learning.enabled: true` in settings
1. Verify write permissions for `.crackerjack/`
1. Check logs for database errors

### Insufficient Data Warnings

**Problem**: "Insufficient data for metrics" warnings

**Solution**:

1. Lower `min_sample_size` in settings
1. Wait for more data collection
1. Use manual overrides during initial period

### Poor Recommendations

**Problem**: Learning makes bad recommendations

**Solution**:

1. Reset learning databases
1. Adjust `adaptation_rate` (lower = more conservative)
1. Increase `min_sample_size` for higher confidence

## Performance Considerations

- **Storage Overhead**: ~1KB per skill attempt, ~500B per query interaction
- **Learning Speed**: Immediate recommendations after sufficient data
- **Adaptation Rate**: 10% by default (adjustable)
- **Database Size**: Grows with usage; implement cleanup if needed

## Best Practices

1. **Start Conservative**: Use higher `min_sample_size` initially
1. **Monitor Quality**: Check recommendations before full deployment
1. **Regular Backups**: Backup learning databases periodically
1. **A/B Testing**: Compare learned strategies with defaults
1. **Gradual Rollout**: Enable learning gradually per component

## Next Steps

1. Integrate with agent orchestrator
1. Add UI for viewing learning metrics
1. Implement learning analytics dashboard
1. Add automated database maintenance
1. Create learning quality reports
