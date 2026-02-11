# Phase 3: Learning & Optimization Implementation Plan

## Overview

This plan implements Task 44-49 from the Git Metrics Symbiotic Ecosystem Integration, adding learning and optimization capabilities to the crackerjack ecosystem.

## Components to Implement

### Task 44: Skill Strategy Effectiveness Tracking
**File**: `crackerjack/integration/skills_effectiveness_tracking.py`

Track which skills/agents work best for specific problem contexts.

**Key Classes**:
- `SkillAttemptRecord`: Record of skill/agent invocation attempt
- `SkillEffectivenessMetrics`: Aggregated metrics for skill effectiveness
- `SkillsEffectivenessTracker`: Main tracker implementation

**Integration**:
- Extend `SkillsTrackerProtocol` with effectiveness tracking
- Store records in Session-Buddy SQLite database
- Enable semantic search via Akosha for "skills that worked for similar queries"

### Task 45: Akosha Query Optimization Learning
**File**: Extend `crackerjack/integration/akosha_integration.py`

Learn from search interactions to improve query effectiveness.

**Key Classes**:
- `QueryInteractionRecord`: Track search result clicks/skips
- `AkoshaQueryOptimizer`: Learn and adapt query strategies

**Features**:
- Track click-through rates on search results
- Learn query patterns that lead to success
- Adaptive ranking based on user satisfaction
- Query reformulation suggestions

### Task 46: Oneiric DAG Optimization Learning
**File**: `crackerjack/integration/oneiric_learning.py` (NEW)

Learn optimal DAG execution patterns.

**Key Classes**:
- `DAGExecutionRecord`: Record of DAG execution
- `OneiricDAGOptimizer`: Learn optimal execution strategies

**Features**:
- Learn optimal task ordering
- Recommend parallelization strategies
- Track resource usage patterns
- Optimize based on historical performance

### Task 47: Dhruva Adapter Selection Learning
**File**: `crackerjack/integration/dhruva_integration.py` (NEW)

Learn which adapters work best for specific file types.

**Key Classes**:
- `AdapterAttemptRecord`: Record of adapter usage
- `DhruvaAdapterLearner`: Learn optimal adapter selection

**Features**:
- Track adapter success rates by file type
- Recommend adapters based on history
- Learn from adapter errors

### Task 48: Mahavishnu Workflow Strategy Memory
**File**: Extend `crackerjack/integration/mahavishnu_integration.py`

Learn which workflows work best for different project characteristics.

**Key Classes**:
- `WorkflowExecutionRecord`: Record of workflow execution
- `MahavishnuWorkflowLearner`: Learn optimal workflow strategies

**Features**:
- Track workflow success by project characteristics
- Recommend workflows based on project metrics
- Learn resource-efficient strategies

## Architecture Compliance

All components follow crackerjack's protocol-based design:

1. **Protocol-First Design**: All interfaces defined as protocols
2. **Constructor Injection**: All dependencies via `__init__`
3. **Graceful Degradation**: NoOp implementations when services unavailable
4. **Type Safety**: Complete type hints, frozen dataclasses
5. **Storage**: Use existing backends (Session-Buddy, Akosha, SQLite)

## Configuration

Add to `CrackerjackSettings`:

```yaml
learning:
  enabled: true
  effectiveness_tracking_enabled: true
  min_sample_size: 10
  adaptation_rate: 0.1
```

## Integration Points

- **Skills Tracking**: Extend existing protocol for effectiveness
- **Agent Selection**: Check metrics before agent invocation
- **Agent Orchestrator**: Boost historically effective choices
- **Oneiric**: Learn optimal DAG execution
- **Adapters**: Recommend based on success history

## Testing Strategy

Comprehensive test coverage for:
- Data model validation
- Storage operations
- Learning algorithm effectiveness
- Integration with existing components
- Graceful degradation scenarios

## Expected Outcomes

- Self-improving systems that learn from usage
- Cross-component learning insights
- Adaptive behavior over time
- Measurable performance improvements

## Implementation Order

1. Skills Effectiveness Tracking (Task 44)
2. Akosha Query Optimization (Task 45)
3. Oneiric DAG Learning (Task 46)
4. Dhruva Adapter Learning (Task 47)
5. Mahavishnu Workflow Learning (Task 48)
6. Configuration updates
7. Testing and validation
8. Documentation updates

## Dependencies

- **Existing**: Session-Buddy, Akosha, Mahavishnu integration
- **New**: NumPy for embeddings, SQLite for storage
- **Testing**: pytest, pytest-asyncio
