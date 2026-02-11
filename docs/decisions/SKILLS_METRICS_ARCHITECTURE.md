# Skills Metrics: Architectural Decision Record

**Status**: ✅ **APPROVED** - Move to Session-Buddy

**Date**: 2025-02-10

**Decision**: Skills metrics tracking should live in **session-buddy**, not crackerjack.

______________________________________________________________________

## 🎯 Executive Summary

After consultation with 6 specialized agents, the architectural decision is clear:

**Skills are session-scoped activities.** Therefore, skills metrics tracking belongs in **session-buddy**, the session management system.

### Key Insights

1. **Session-Buddy is the natural home** - Skills are used during sessions, tracked alongside session analytics
1. **Storage in Session-Buddy** - Dhruva provides ACID-compliant storage (better than JSON files)
1. **Discovery via Akosha** - Vector search enables finding the right skill for the context
1. **Correlation via Oneiric** - Skills + workflows correlated by session_id
1. **Aggregation via Mahavishnu** - Cross-project insights for workflow optimization

______________________________________________________________________

## 📊 Current State vs. Target State

### Current State (Incomplete)

```
crackerjack/skills/metrics.py  ← Skills tracking in wrong place!
├── SkillInvocation (dataclass)
├── SkillMetrics (dataclass)
├── SkillMetricsTracker (class)
└── JSON storage in .session-buddy/
```

**Problems**:

- ❌ Skills tracking in crackerjack (wrong architectural home)
- ❌ JSON files (no ACID, no versioning)
- ❌ No integration with session analytics
- ❌ No semantic search for skills
- ❌ Limited to single-project scope

### Target State (Complete)

```
session-buddy/
├── core/skills_tracker.py       ← Main tracking logic
├── storage/skills_storage.py     ← Dhruva persistence
├── intelligence/skills_search.py ← Akosha semantic search
├── analytics/skills_correlator.py← Oneiric workflow correlation
└── mcp/tools/skills_analytics.py ← MCP tools for insights

mahavishnu/
└── analytics/skills_aggregator.py← Cross-project aggregation

crackerjack/
└── .claude/skills/*.md          ← Skills remain here (content)
```

**Benefits**:

- ✅ Skills tracking in session-buddy (correct home)
- ✅ Dhruva ACID storage (transactions, versioning)
- ✅ Akosha semantic search (find right skill)
- ✅ Oneiric correlation (skills + workflows)
- ✅ Mahavishnu aggregation (cross-project insights)
- ✅ Integrated with session analytics

______________________________________________________________________

## 🏗️ Architecture Overview

### Layer 1: Session-Buddy (Core Tracking)

**Location**: `/Users/les/Projects/session-buddy/`

**Purpose**: Track skill usage during sessions

**Components**:

1. **`core/skills_tracker.py`**

   ```python
   class SkillsTracker:
       """Track skill invocations during sessions."""

       def track_invocation(
           self,
           skill_name: str,
           session_id: str,
           workflow_path: str | None = None,
           user_query: str | None = None,  # For semantic search
       ) -> Callable:
           """Track a skill invocation with context."""
   ```

1. **`storage/skills_storage.py`**

   ```python
   class SkillsStorage:
       """Dhruva-backed persistent storage for skills metrics."""

       def store_invocation(self, invocation: SkillInvocation) -> None:
           """Store with ACID guarantees."""

       def get_metrics(self, skill_name: str) -> SkillMetrics:
           """Get aggregated metrics."""

       def get_session_skills(self, session_id: str) -> list[SkillInvocation]:
           """Get all skills used in a session."""
   ```

**Integration**:

- Automatically invoked during session lifecycle
- Session start → initialize tracker
- Skill used → track invocation
- Session end → aggregate and store

### Layer 2: Akosha (Semantic Discovery)

**Location**: `/Users/les/Projects/session-buddy/intelligence/`

**Purpose**: Find the right skill based on context

**Components**:

1. **`intelligence/skills_search.py`**
   ```python
   class SkillsSemanticSearch:
       """Semantic search for skill discovery."""

       async def find_skills(
           self,
           query: str,
           session_context: str | None = None,
           max_results: int = 3,
       ) -> list[SkillRecommendation]:
           """Find relevant skills using semantic search + effectiveness."""

       def index_skill(self, skill_path: Path) -> None:
           """Index skill markdown file for search."""
   ```

**Algorithm**:

```python
final_score = (
    semantic_similarity * 0.6 +    # Vector similarity
    effectiveness_score * 0.3 +    # Metrics-based
    context_boost * 0.1            # Session context
) * penalty_factors
```

**Usage**:

```python
# User: "I need to fix type errors"
search = SkillsSemanticSearch()
results = await search.find_skills(
    query="fix type errors in Python code",
    session_context=session.summary,
)

# Results:
# 1. crackerjack-run (0.92) - with debug mode
# 2. crackerjack-run (0.87) - comprehensive
# 3. session-checkpoint (0.45) - quick quality check
```

### Layer 3: Oneiric (Workflow Correlation)

**Location**: `/Users/les/Projects/crackerjack/crackerjack/runtime/`

**Purpose**: Correlate skill usage with workflow execution

**Components**:

1. **`runtime/workflow_events.py`** (in crackerjack)

   ```python
   class WorkflowEventTracker:
       """Emit events during Oneiric workflow execution."""

       def workflow_started(self, workflow_id: str, session_id: str) -> None:
           """Track workflow start."""

       def node_completed(self, node_id: str, session_id: str) -> None:
           """Track workflow node completion."""
   ```

1. **`analytics/skills_correlator.py`** (in session-buddy)

   ```python
   class SkillsWorkflowCorrelator:
       """Correlate skill usage with workflow execution."""

       def correlate_session(self, session_id: str) -> SessionCorrelation:
           """Join skill invocations with workflow events."""

       def generate_report(self, session_id: str) -> str:
           """Generate human-readable correlation report."""
   ```

**Correlation Strategy**:

- Both systems emit events tagged with `session_id`
- Correlator joins by session_id after execution
- Computes combined metrics:
  - Skill duration vs. workflow duration
  - Skills completed vs. workflow nodes completed
  - Pattern detection (interactive vs. automated)

### Layer 4: Mahavishnu (Cross-Project Aggregation)

**Location**: `/Users/les/Projects/mahavishnu/analytics/`

**Purpose**: Aggregate and analyze across all projects

**Components**:

1. **`analytics/skills_aggregator.py`**
   ```python
   class SkillsAggregator:
       """Collect and aggregate skill metrics across projects."""

       def collect_from_projects(self, project_paths: list[Path]) -> None:
           """Read metrics from each project's session-buddy database."""

       def get_cross_project_insights(self) -> CrossProjectInsights:
           """Generate cross-project analytics."""

       def find_effective_patterns(self) -> list[Pattern]:
           """Find patterns of effective skill usage."""
   ```

**Aggregation Strategy**:

- Read from each project's session-buddy Dhruva database
- Compute cross-project statistics:
  - Most used skills across all projects
  - Effectiveness by project type
  - Workflow optimization opportunities
  - Team-level recommendations

**Privacy-First**:

- All aggregation local (no external transmission)
- Opt-in project registration
- Aggregate only (no raw data leaves projects)

______________________________________________________________________

## 🔄 Data Flow

### Complete Flow Example

```
1. User starts session
   session-buddy: start_session()
   └─> Creates session_id = "abc123"
   └─> Initializes SkillsTracker

2. User uses skill
   User: "Help me fix code quality"
   └─> Akosha: semantic_search("fix code quality")
       └─> Recommends: crackerjack-run (comprehensive)

   User selects skill
   └─> SkillsTracker: track_invocation("crackerjack-run", "comprehensive")
       └─> Creates SkillInvocation record

3. Skill executes (interactive guidance)
   User reads skill markdown
   User selects workflow options
   User follows guidance
   └─> Completes skill successfully

4. Mark complete
   SkillsTracker: completer(completed=True, follow_up=["git commit"])
   └─> Updates SkillInvocation with duration, completion
   └─> Dhruva: atomically stores invocation + updates metrics

5. Workflow execution (Oneiric)
   User runs: python -m crackerjack run
   └─> Oneiric: executes workflow DAG
   └─> WorkflowEventTracker: emits events tagged with session_id

6. Session ends
   session-buddy: end_session()
   └─> SkillsCorrelator: correlate_session(session_id)
       └─> Joins skill invocations + workflow events
       └─> Generates correlation report
   └─> SkillsStorage: aggregates session metrics
   └─> Dhruva: commits transaction

7. Cross-project analysis (Mahavishnu)
   Mahavishnu: collect_from_projects([project1, project2, ...])
   └─> Reads from each project's session-buddy database
   └─> Aggregates cross-project statistics
   └─> Generates insights and recommendations
```

______________________________________________________________________

## 📁 File Structure

### Session-Buddy (New Files)

```
session-buddy/
├── core/
│   └── skills_tracker.py          # Main tracking logic
├── storage/
│   ├── skills_storage.py          # Dhruva persistence layer
│   └── skills_schema.sql          # Database schema
├── intelligence/
│   └── skills_search.py           # Akosha semantic search
├── analytics/
│   └── skills_correlator.py       # Oneiric correlation
├── mcp/tools/
│   └── skills_analytics.py        # MCP tools for insights
└── tests/
    ├── test_skills_tracker.py
    ├── test_skills_storage.py
    └── test_skills_search.py
```

### Crackerjack (Modified Files)

```
crackerjack/
├── runtime/
│   └── workflow_events.py         # Emit workflow events
├── runtime/
│   └── oneiric_workflow.py        # Pass session_id to runtime
└── .claude/skills/                # Skills content (unchanged)
    ├── crackerjack-init.md
    ├── crackerjack-run.md
    ├── session-start.md
    ├── session-checkpoint.md
    └── session-end.md
```

### Mahavishnu (New Files)

```
mahavishnu/
├── analytics/
│   └── skills_aggregator.py       # Cross-project aggregation
├── mcp/tools/
│   └── skills_insights.py         # MCP tools for cross-project analytics
└── storage/
    └── skills_analytics.db        # DuckDB for cross-project queries
```

______________________________________________________________________

## 🎯 Implementation Phases

### Phase 1: Core Tracking (Session-Buddy) - Week 1

**Move tracking from crackerjack to session-buddy**:

1. Create `session-buddy/core/skills_tracker.py`

   - Port `crackerjack/skills/metrics.py` logic
   - Integrate with session lifecycle
   - Add session_id tracking

1. Create `session-buddy/storage/skills_storage.py`

   - Implement Dhruva-backed storage
   - Define schema (invocations, metrics, sessions)
   - Add transaction patterns

1. Migrate existing data

   - Export from crackerjack JSON files
   - Import into session-buddy Dhruva
   - Validate data integrity

**Deliverable**: Skills tracking working in session-buddy with Dhruva storage

### Phase 2: Semantic Search (Akosha) - Week 2

**Add skill discovery via semantic search**:

1. Create `session-buddy/intelligence/skills_search.py`

   - Parse skill markdown files
   - Generate embeddings (Akosha)
   - Implement semantic search algorithm

1. Index existing skills

   - Scan `.claude/skills/` directories
   - Chunk and index skills
   - Build embeddings cache

1. Test search quality

   - Validate with sample queries
   - Measure recommendation accuracy
   - Tune scoring algorithm

**Deliverable**: Semantic search finding right skills with 80%+ accuracy

### Phase 3: Workflow Correlation (Oneiric) - Week 3

**Correlate skills with workflows**:

1. Create `crackerjack/runtime/workflow_events.py`

   - Define workflow event structure
   - Emit events during execution
   - Tag with session_id

1. Modify `crackerjack/runtime/oneiric_workflow.py`

   - Accept session_id parameter
   - Pass to event tracker
   - Emit node lifecycle events

1. Create `session-buddy/analytics/skills_correlator.py`

   - Join by session_id
   - Compute combined metrics
   - Generate correlation reports

**Deliverable**: Skills + workflows correlated by session

### Phase 4: Cross-Project Aggregation (Mahavishnu) - Week 4

**Aggregate across all projects**:

1. Create `mahavishnu/analytics/skills_aggregator.py`

   - Collect from project databases
   - Aggregate cross-project statistics
   - Compute effectiveness patterns

1. Create MCP tools

   - `collect_skill_metrics` - manual collection trigger
   - `get_cross_project_insights` - aggregated analytics
   - `find_effective_patterns` - pattern discovery

1. Build analytics dashboard

   - Most used skills
   - Effectiveness by project type
   - Workflow optimization recommendations

**Deliverable**: Cross-project skill analytics

______________________________________________________________________

## 📊 Migration Strategy

### From Crackerjack to Session-Buddy

**Current State**:

```
crackerjack/skills/metrics.py (JSON files)
```

**Migration Steps**:

1. **Dual-Write Period** (1 week)

   ```python
   # Write to both crackerjack JSON and session-buddy Dhruva
   track_skill_dual_write(skill_name, ...)
   ```

1. **Validate** (3-5 days)

   ```python
   # Compare JSON vs Dhruva data
   validate_migration(crackerjack_json, session_buddy_db)
   ```

1. **Cutover** (1 day)

   ```python
   # Switch to session-buddy only
   track_skill_session_buddy_only(skill_name, ...)
   ```

1. **Cleanup** (1 week)

   ```python
   # Remove legacy crackerjack code
   # Delete old JSON files after backup
   ```

**Total Timeline**: 2-3 weeks for safe migration

______________________________________________________________________

## 🎯 Success Metrics

### Technical Metrics

- **Tracking Accuracy**: 100% of skill invocations tracked
- **Storage Reliability**: 99.99% uptime with ACID guarantees
- **Search Accuracy**: >80% relevant skills in top 3 results
- **Correlation Coverage**: 100% of sessions with both skills + workflows
- **Aggregation Performance**: \<5s to aggregate 10+ projects

### User Experience Metrics

- **Skill Discovery Time**: \<10s to find right skill
- **Recommendation Relevance**: >70% user satisfaction
- **Insight Quality**: Actionable recommendations in 90%+ cases
- **Cross-Project Value**: Teams adopt insights within 1 month

______________________________________________________________________

## 🚀 Next Steps

### Immediate Actions

1. **Review this ADR** with team
1. **Confirm architectural decision**
1. **Begin Phase 1 implementation** (core tracking in session-buddy)

### Week 1 Priorities

1. Create `session-buddy/core/skills_tracker.py`
1. Create `session-buddy/storage/skills_storage.py`
1. Implement Dhruva schema
1. Migrate existing data from crackerjack

### Long-Term Vision

- **Skills as first-class session citizens** - tracked alongside session metrics
- **Semantic skill discovery** - find right skill via natural language
- **Workflow correlation** - understand how skills enhance workflows
- **Cross-project insights** - learn from patterns across all projects
- **Continuous improvement** - skills evolve based on effectiveness data

______________________________________________________________________

## 📚 Related Documentation

### Design Documents

- `/Users/les/Projects/crackerjack/docs/design/SKILL_METRICS_STORAGE_SCHEMA.md`
- `/Users/les/Projects/crackerjack/docs/design/SKILL_METRICS_TRANSACTION_PATTERNS.md`
- `/Users/les/Projects/crackerjack/docs/design/SKILL_METRICS_MIGRATION_GUIDE.md`
- `/Users/les/Projects/session-buddy/docs/design/SKILL_METRICS_AGGREGATION.md`
- `/Users/les/Projects/session-buddy/docs/design/SKILL_METRICS_ARCHITECTURE.md`
- `/Users/les/Projects/crackerjack/VECTOR_SKILL_INTEGRATION_PLAN.md`

### Implementation Guides

- `/Users/les/Projects/crackerjack/docs/design/SKILL_METRICS_IMPLEMENTATION.md`
- `/Users/les/Projects/crackerjack/docs/design/SKILL_METRICS_QUICK_REFERENCE.md`

### Agent Consultations

1. **Oneiric Integration**: Workflow orchestration agent
1. **Mahavishnu Aggregation**: Multi-agent coordinator agent
1. **Akosha Search**: Data scientist agent
1. **Dhruva Storage**: Database administrator agent

______________________________________________________________________

## ✅ Decision Rationale

**Why Session-Buddy?**

1. **Skills are session activities** - used during sessions, enhance session value
1. **Session-buddy already tracks sessions** - natural integration point
1. **Cross-cutting concern** - skills used across all projects
1. **Session lifecycle** - start → skills used → end → metrics captured

**Why Not Crackerjack?**

1. **Wrong scope** - crackerjack is quality tools, not session management
1. **Single-project** - crackerjack doesn't see cross-project patterns
1. **Storage limitations** - JSON files vs. Dhruva ACID storage

**Architecture Alignment**:

- **Separation of concerns** - session-buddy manages sessions
- **Specialized storage** - Dhruva for metrics, Akosha for search
- **Workflow integration** - Oneiric correlation by session
- **Cross-project insights** - Mahavishnu aggregation

______________________________________________________________________

**Approved by**: Architecture Review (6 agent consultations)

**Implementation Start**: 2025-02-10

**Target Completion**: 2025-03-10 (4 weeks)
