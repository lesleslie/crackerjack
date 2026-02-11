# Phase 1 Gap Analysis: Skills Metrics Integration

**Date**: 2026-02-10
**Status**: ✅ **60-80% COMPLETE** - Infrastructure Exists, Integration Layer Missing

---

## Executive Summary

**Finding**: Session-buddy already has **substantial skills metrics infrastructure** in place from Phase 4 implementation. Phase 1 is approximately **60-80% complete** with core storage, analytics, and recommendation engine already implemented.

**Remaining Work**: Primarily integration bridge between crackerjack and session-buddy, plus data migration from existing JSON files.

**Updated Timeline**: Phase 1 can be completed in **3-5 days** instead of the originally planned 1 week.

---

## What Already Exists ✅

### 1. Core Data Models (100% Complete)

**File**: `session_buddy/core/skills_tracker.py` (905 lines)

```python
@dataclass
class SkillInvocation:
    """Single skill usage event with session context.

    Enhanced from crackerjack implementation:
    - session_id for correlation with workflows ✅
    - user_query for semantic search analysis ✅
    - alternatives_considered for learning from rejections ✅
    - selection_rank for recommendation effectiveness ✅
    """
    skill_name: str
    invoked_at: str
    session_id: str
    workflow_path: str | None = None
    completed: bool = False
    duration_seconds: float | None = None
    user_query: str | None = None
    alternatives_considered: list[str] = field(default_factory=list)
    selection_rank: int | None = None
    follow_up_actions: list[str] = field(default_factory=list)
    error_type: str | None = None
```

**Status**: ✅ **All required fields present**

---

### 2. Dhruva Storage Layer (100% Complete)

**File**: `session_buddy/storage/skills_storage.py` (1958 lines)

**Key Methods Implemented**:

| Method | Purpose | Status |
|--------|---------|--------|
| `store_invocation()` | Store skill usage with ACID guarantees | ✅ Complete |
| `search_by_query()` | Semantic search via embeddings | ✅ Complete |
| `search_by_query_workflow_aware()` | Phase-aware recommendations | ✅ Complete |
| `get_workflow_skill_effectiveness()` | Phase-based analytics | ✅ Complete |
| `identify_workflow_bottlenecks()` | Bottleneck detection | ✅ Complete |
| `get_workflow_phase_transitions()` | Transition tracking | ✅ Complete |
| `detect_anomalies()` | Z-score anomaly detection | ✅ Complete |
| `aggregate_hourly_metrics()` | Time-series aggregation | ✅ Complete |

**Status**: ✅ **Complete with all Phase 1-4 features**

---

### 3. Skills Tracker API (100% Complete)

**File**: `session_buddy/core/skills_tracker.py`

**Key Methods Implemented**:

| Method | Purpose | Status |
|--------|---------|--------|
| `track_invocation()` | Track skill with context | ✅ Complete |
| `recommend_skills()` | Semantic search recommendations | ✅ Complete |
| `get_session_summary()` | Session-specific metrics | ✅ Complete |
| `generate_workflow_report()` | Workflow correlation report | ✅ Complete |
| `generate_phase_heatmap()` | ASCII heatmap visualization | ✅ Complete |
| `export_metrics()` | JSON export | ✅ Complete |

**Status**: ✅ **Complete with enhanced features**

---

### 4. V4 Database Schema (100% Complete)

**File**: `session_buddy/storage/migrations/V4__phase4_extensions__up.sql`

**Tables Created** (13 total):

| Table | Purpose | Phase | Status |
|-------|---------|-------|--------|
| `skill_metrics_cache` | Real-time metrics cache | Phase 4 | ✅ Complete |
| `skill_time_series` | Hourly granularity data | Phase 4 | ✅ Complete |
| `skill_anomalies` | Anomaly detection results | Phase 4 | ✅ Complete |
| `skill_community_baselines` | Cross-user aggregates | Phase 2 | ✅ Complete |
| `skill_user_interactions` | Collaborative filtering | Phase 2 | ✅ Complete |
| `skill_clusters` | Skill clusters | Phase 2 | ✅ Complete |
| `skill_cluster_membership` | Cluster mappings | Phase 2 | ✅ Complete |
| `ab_test_configs` | A/B test configs | Phase 3 | ✅ Complete |
| `ab_test_assignments` | User assignments | Phase 3 | ✅ Complete |
| `ab_test_outcomes` | Test results | Phase 3 | ✅ Complete |
| `skill_categories` | Taxonomy | Phase 3 | ✅ Complete |
| `skill_category_mapping` | Skill-to-category | Phase 3 | ✅ Complete |
| `skill_dependencies` | Co-occurrence patterns | Phase 3 | ✅ Complete |

**Status**: ✅ **All Phase 1-4 tables present**

---

## What's Missing ❌

### 1. Crackerjack Integration Bridge (0% Complete)

**Needed**: Modify crackerjack's agent system to call session-buddy

**Files to Modify**:
- `crackerjack/agents/agent_context.py` - Add session-buddy integration
- `crackerjack/agents/base_agent.py` - Hook into agent lifecycle
- `crackerjack/runtime/oneiric_workflow.py` - Track skill usage

**Implementation Required**:
```python
# Pseudocode for integration
class AgentContext:
    def __init__(self, ...):
        # NEW: Initialize skills tracker
        from session_buddy.core.skills_tracker import get_session_tracker

        self.skills_tracker = get_session_tracker(
            session_id=self.session_id,
            db_path=self.config.skills_db_path
        )

    def track_skill_usage(self, skill_name: str, completed: bool, ...):
        """Track skill invocation with session-buddy."""
        completer = self.skills_tracker.track_invocation(
            skill_name=skill_name,
            workflow_path=self.workflow_path,
            user_query=self.user_query,
            alternatives_considered=self.alternatives,
            selection_rank=self.selection_rank
        )
        completer(completed=completed, ...)
```

**Estimated Time**: 1-2 days

---

### 2. Data Migration (0% Complete)

**Needed**: Migrate existing JSON metrics to Dhruva database

**Source**: `.crackerjack/skill_metrics.json` (if exists)
**Target**: `.session-buddy/skills.db` (Dhruva)

**Implementation Required**:
```python
# Pseudocode for migration
def migrate_skills_metrics(
    json_path: Path,
    db_path: Path,
) -> MigrationResult:
    """Migrate from JSON to Dhruva database."""

    # Load JSON
    data = json.loads(json_path.read_text())

    # Create storage
    storage = SkillsStorage(db_path=db_path)

    # Migrate invocations
    for inv_data in data["invocations"]:
        storage.store_invocation(
            skill_name=inv_data["skill_name"],
            invoked_at=inv_data["invoked_at"],
            session_id=inv_data["session_id"],
            # ... map all fields
        )

    return MigrationResult(
        invocations_migrated=len(data["invocations"]),
        skills_migrated=len(data["skills"])
    )
```

**Estimated Time**: 0.5-1 day

---

### 3. Testing & Validation (0% Complete)

**Needed**: Comprehensive test coverage for integration

**Test Files to Create**:
- `tests/test_skills_integration.py` - Integration tests
- `tests/test_skills_migration.py` - Migration tests
- `tests/test_skills_recommender.py` - Recommendation tests

**Estimated Time**: 1-2 days

---

## Updated Phase 1 Implementation Plan

### Original Timeline: 1 week (5 days)
### Updated Timeline: 3-5 days

| Task | Original Estimate | Actual Estimate | Status |
|------|------------------|-----------------|--------|
| Core data models | 1 day | ✅ **DONE** | Complete |
| Dhruva storage | 2 days | ✅ **DONE** | Complete |
| Skills tracker API | 1 day | ✅ **DONE** | Complete |
| V4 schema migration | 1 day | ✅ **DONE** | Complete |
| **Crackerjack integration** | 0 days | **1-2 days** | ⏳ Pending |
| **Data migration** | 0 days | **0.5-1 day** | ⏳ Pending |
| **Testing & validation** | 0 days | **1-2 days** | ⏳ Pending |

**Total Remaining Work**: **2.5-5 days**

---

## Recommended Implementation Order

### Step 1: Data Migration (0.5-1 day)

**Priority**: High - Foundation for everything else

**Tasks**:
1. Create migration script: `scripts/migrate_skills_to_sessionbuddy.py`
2. Handle edge cases (corrupted JSON, missing fields)
3. Validate migrated data
4. Create rollback script

**Success Criteria**:
- All JSON data successfully migrated to Dhruva
- Migration script handles edge cases gracefully
- Rollback script tested and working

---

### Step 2: Crackerjack Integration (1-2 days)

**Priority**: High - Enables ongoing skill tracking

**Tasks**:
1. Modify `AgentContext` to initialize skills tracker
2. Hook into agent lifecycle (`__enter__`, `__exit__`)
3. Track skill usage in `oneiric_workflow.py`
4. Add skill recommendations to agent selection
5. Handle errors gracefully (session-buddy unavailable)

**Success Criteria**:
- All agent invocations tracked in session-buddy
- No breaking changes to existing agent behavior
- Error handling works when session-buddy unavailable

---

### Step 3: Testing & Validation (1-2 days)

**Priority**: Medium - Quality assurance

**Tasks**:
1. Create integration test suite
2. Test migration script with real data
3. Test crackerjack integration end-to-end
4. Performance test (track 100+ invocations)
5. Validate data consistency

**Success Criteria**:
- 80%+ test coverage for new code
- All tests passing
- No performance regression
- Data consistency validated

---

## Architecture Decision: Integration Approach

### Option A: Tight Coupling (Recommended for Phase 1)

**Approach**: Crackerjack directly calls session-buddy APIs

```python
# In crackerjack/agents/agent_context.py
from session_buddy.core.skills_tracker import get_session_tracker

class AgentContext:
    def __init__(self, session_id: str):
        self.skills_tracker = get_session_tracker(session_id)
```

**Pros**:
- ✅ Simple to implement
- ✅ Fast performance (direct API calls)
- ✅ Low latency

**Cons**:
- ❌ Tight coupling between projects
- ❌ Harder to test in isolation

**Recommendation**: Use for Phase 1 (MVP), refactor to Option B in Phase 2

---

### Option B: MCP Bridge (Recommended for Phase 2+)

**Approach**: Use session-buddy MCP server for integration

```python
# In crackerjack/agents/agent_context.py
class AgentContext:
    async def track_skill_usage(self, skill_name: str, ...):
        await self.session_buddy_mcp.call_tool(
            "track_invocation",
            skill_name=skill_name,
            ...
        )
```

**Pros**:
- ✅ Loose coupling (MCP protocol)
- ✅ Easier to test (mock MCP server)
- ✅ Supports remote deployment

**Cons**:
- ❌ More complex to implement
- ❌ Slightly higher latency
- ❌ Requires async/await

**Recommendation**: Refactor to this approach in Phase 2 (Cross-Session Learning)

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Session-buddy unavailable during agent execution | Medium | Medium | Graceful degradation, try/except |
| Migration data loss | Low | High | Backup before migration, test rollback |
| Performance regression | Low | Medium | Benchmark before/after, use caching |
| Breaking existing agent behavior | Low | High | Comprehensive testing, feature flags |

---

## Success Criteria

Phase 1 is complete when:

- ✅ All existing JSON data migrated to Dhruva
- ✅ All crackerjack agent invocations tracked in session-buddy
- ✅ Skill recommendations available via `recommend_skills()`
- ✅ 80%+ test coverage for new code
- ✅ No breaking changes to existing agent behavior
- ✅ Performance regression <10%
- ✅ Documentation updated (CLAUDE.md, README.md)

---

## Next Steps

### Immediate (Today)

1. **Review this gap analysis** with user
2. **Confirm approach**: Option A (tight coupling) vs Option B (MCP bridge)
3. **Create migration script** for existing JSON data

### This Week

1. **Complete data migration** (0.5-1 day)
2. **Implement crackerjack integration** (1-2 days)
3. **Write tests** (1-2 days)

### Next Week

1. **Validate integration** with real workflows
2. **Performance testing**
3. **Documentation**
4. **Begin Phase 2 planning** (semantic search enhancements)

---

## Conclusion

**Phase 1 is 60-80% complete** with substantial infrastructure already in place from session-buddy Phase 4. The remaining work is primarily integration and migration, which can be completed in **3-5 days**.

**Key Insight**: Session-buddy already has enterprise-grade skills tracking infrastructure. We don't need to build it—we just need to connect crackerjack to it.

**Recommendation**: Proceed with Step 1 (data migration) followed by Step 2 (crackerjack integration) using Option A (tight coupling) for the MVP, with plans to refactor to Option B (MCP bridge) in Phase 2.

---

**Analysis Completed**: 2026-02-10
**Status**: Ready for implementation
**Estimated Completion**: 3-5 days
