# Phase 2 Parallel Execution Plan

**Created**: 2025-10-09
**Status**: 🚀 IN PROGRESS
**Timeline**: 1-2 weeks (compressed via parallel execution)
**Threads**: 3 parallel execution threads

## Executive Summary

We're executing Phase 2 of the Comprehensive Improvement Plan with **3 parallel execution threads** to maximize velocity. This approach compresses 3-4 weeks of sequential work into 1-2 weeks.

### Parallel Execution Threads

| Thread | Task | Agent | Effort | Lines Saved |
|--------|------|-------|--------|-------------|
| **MAIN** | Decompose `_get_dashboard_html()` | Human + jinja2-template-designer | 1-2 weeks | -700 |
| **THREAD 1** | Complete protocol migration | architecture-council | 1-2 weeks | - |
| **THREAD 2** | Add ACB `depends.inject` | acb-specialist | 1-2 weeks | -1,200 |

**Total Impact**: -1,900 lines, 2 major architectural improvements

## Thread Details

### MAIN THREAD: Dashboard HTML Template Extraction

**File**: `crackerjack/mcp/websocket/monitoring_endpoints.py`
**Function**: `_get_dashboard_html()` (lines 1713-2935, **1,223 lines**)
**Problem**: 81x complexity limit violation, untestable, unmaintainable

**Strategy**:

```
crackerjack/
└── templates/               # NEW: Jinja2 template directory
    ├── dashboard/
    │   ├── base.html.j2        # Base layout with head, scripts
    │   ├── overview.html.j2     # System overview section
    │   ├── jobs.html.j2         # Jobs table section
    │   ├── agents.html.j2       # AI agents section
    │   ├── performance.html.j2  # Performance metrics
    │   └── logs.html.j2         # Logs section
    ├── components/
    │   ├── metric_card.html.j2  # Reusable metric card
    │   ├── table.html.j2        # Generic data table
    │   └── chart.html.j2        # Chart component
    └── layouts/
        └── websocket_base.html.j2  # WebSocket dashboard base
```

**Implementation Steps**:

1. ✅ **Analyze current HTML function** (1,223 lines)
   - Identify logical sections
   - Map data dependencies
   - Find reusable components

2. **Create Jinja2 template structure**
   - Set up `templates/` directory
   - Create base template with inheritance
   - Extract components (cards, tables, charts)

3. **Extract HTML by section**
   - Head/scripts → `base.html.j2`
   - Overview metrics → `overview.html.j2`
   - Jobs table → `jobs.html.j2`
   - AI agents → `agents.html.j2`
   - Performance → `performance.html.j2`
   - Logs → `logs.html.j2`

4. **Create template renderer**
   ```python
   # crackerjack/services/template_service.py
   from jinja2 import Environment, FileSystemLoader

   class TemplateService:
       def __init__(self):
           self.env = Environment(loader=FileSystemLoader('templates'))

       def render_dashboard(self, data: dict) -> str:
           template = self.env.get_template('dashboard/base.html.j2')
           return template.render(**data)
   ```

5. **Replace function with template call**
   ```python
   def _get_dashboard_html() -> str:
       template_service = TemplateService()
       data = _prepare_dashboard_data()
       return template_service.render_dashboard(data)
   ```

6. **Add template tests**
   - Test each component independently
   - Test data binding
   - Test conditional rendering

**Success Criteria**:
- ✅ Function reduced from 1,223 → <50 lines
- ✅ All templates under 100 lines each
- ✅ Components reusable across dashboards
- ✅ 100% test coverage on templates
- ✅ Zero functionality changes (visual identical)

---

### THREAD 1: Protocol Migration (architecture-council)

**Goal**: Complete migration to protocol-based dependency injection

**Current State**:
- Partial protocol usage in coordinators
- Some managers still use concrete imports
- Inconsistent DI patterns

**Target**:
```python
# ❌ BEFORE: Concrete imports
from crackerjack.managers.hook_manager import HookManager

class Coordinator:
    def __init__(self, hook_manager: HookManager):
        self.hook_manager = hook_manager

# ✅ AFTER: Protocol-based
from crackerjack.models.protocols import HookManagerProtocol

class Coordinator:
    def __init__(self, hook_manager: HookManagerProtocol):
        self.hook_manager = hook_manager
```

**Files to Migrate**:
- `crackerjack/core/workflow_orchestrator.py`
- `crackerjack/coordinators/*.py`
- `crackerjack/managers/*.py`
- `crackerjack/services/*.py`

**Agent Instructions**:
```
Task: Complete protocol migration for all orchestration components

Context:
- Existing protocols defined in models/protocols.py
- Partial migration already done for coordinators
- Need consistent protocol usage across entire codebase

Requirements:
1. Audit all imports in orchestration layer
2. Replace concrete imports with protocol imports
3. Update type annotations to use protocols
4. Verify no circular import issues
5. Ensure all tests still pass

Success Criteria:
- Zero concrete class imports in orchestration
- All DI uses protocol types
- pyright/mypy validation passes
- All 29 cache tests + 26 decorator tests pass
```

---

### THREAD 2: ACB Dependency Injection (acb-specialist)

**Goal**: Replace manual DI with ACB `depends.inject` decorators

**Current State**:
- Manual service initialization in `__init__` methods
- Boilerplate DI code throughout codebase
- Not leveraging ACB's DI capabilities

**Target**:
```python
# ❌ BEFORE: Manual DI
class WorkflowOrchestrator:
    def __init__(self):
        self.hook_manager = HookManager(console=self.console)
        self.test_manager = TestManager(
            console=self.console,
            config=self.config
        )
        self.publish_manager = PublishManager(...)
        # 50+ lines of manual initialization

# ✅ AFTER: ACB DI
from acb.depends import depends

class WorkflowOrchestrator:
    hook_manager: HookManagerProtocol = depends.inject()
    test_manager: TestManagerProtocol = depends.inject()
    publish_manager: PublishManagerProtocol = depends.inject()

    # ACB handles initialization automatically
```

**Benefits**:
- Remove 1,200 lines of boilerplate DI code
- Automatic dependency resolution
- Better testability (easy mocking)
- Consistent initialization patterns

**Agent Instructions**:
```
Task: Implement ACB dependency injection across core services

Context:
- ACB framework already integrated (cache adapter working)
- Need to extend depends.inject to all services
- Current manual DI in orchestrators, coordinators, managers

Requirements:
1. Audit current manual DI code
2. Configure ACB DI for all service protocols
3. Replace manual __init__ with depends.inject
4. Update tests to use ACB DI patterns
5. Verify cache adapter still works (already using ACB)

Success Criteria:
- All services use depends.inject
- Remove 1,200+ lines of boilerplate
- All tests pass (29 cache + 26 decorator + others)
- ACB integration score: 6/10 → 8/10
```

---

## Coordination & Integration

### Daily Sync Points

**Morning**: Review overnight agent progress
**Midday**: Resolve any integration conflicts
**Evening**: Merge completed work, run full test suite

### Integration Strategy

1. **Merge Order**:
   - Thread 2 (ACB DI) merges first (foundation)
   - Thread 1 (Protocol) merges second (builds on DI)
   - Main (Templates) merges last (uses both)

2. **Conflict Resolution**:
   - Protocol changes take precedence
   - ACB DI must not break cache adapter
   - Templates isolated (minimal conflicts)

3. **Testing**:
   - Each thread maintains passing tests
   - Integration tests run after each merge
   - Full regression suite before completion

### Risk Mitigation

**Risk**: Agents make incompatible changes
**Mitigation**: Clear interfaces defined upfront (protocols)

**Risk**: Breaking cache adapter (working well)
**Mitigation**: Cache adapter tests must pass at all times

**Risk**: Merge conflicts from parallel work
**Mitigation**: Clear file ownership, daily syncs

## Timeline

### Week 1

**Days 1-2**: Setup + Analysis
- ✅ Create this plan
- ✅ Launch parallel agents
- Main: Analyze HTML structure
- Thread 1: Audit protocol usage
- Thread 2: Audit current DI patterns

**Days 3-5**: Core Implementation
- Main: Create Jinja2 templates (sections 1-3)
- Thread 1: Migrate orchestrators + coordinators
- Thread 2: Implement depends.inject for core services

### Week 2

**Days 1-3**: Complete Implementation
- Main: Finish templates (sections 4-6) + tests
- Thread 1: Migrate managers + services
- Thread 2: Extend DI to all services

**Days 4-5**: Integration + Testing
- Merge Thread 2 (ACB DI)
- Merge Thread 1 (Protocols)
- Merge Main (Templates)
- Full test suite
- Quality check

## Success Metrics

### Code Quality

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Lines of Code** | 113,624 | 111,724 | -1,900 |
| **Largest Function** | 1,223 lines | <50 lines | -96% |
| **Quality Score** | 69/100 | 75/100 | +6 |
| **Architecture** | 85/100 | 88/100 | +3 |
| **ACB Integration** | 6/10 | 8/10 | +2 |

### Technical Debt Reduction

- ✅ Critical complexity violation resolved
- ✅ Manual DI boilerplate eliminated
- ✅ Protocol consistency achieved
- ✅ Template testability achieved

## Next Steps

After Phase 2 completion:

1. **Phase 3**: ACB Deep Integration
   - Event-driven orchestration
   - Universal query interface
   - Full adapter architecture

2. **Phase 4**: Excellence & Scale
   - Test coverage → 100%
   - Service consolidation
   - Performance optimization

---

**Status**: 🚀 IN PROGRESS
**Last Updated**: 2025-10-09
**Next Checkpoint**: End of Week 1 (5 days)
