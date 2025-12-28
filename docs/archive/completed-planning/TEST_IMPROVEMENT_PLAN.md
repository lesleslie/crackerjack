# Crackerjack Test Improvement Plan

## Executive Summary

**Current Status:**

- **Coverage**: 19.6% (baseline, targeting 100%)
- **Test Files**: 187 test files covering 334 source files (56% file coverage ratio)
- **Critical Issues**: 120 skipped tests, 277 async tests, 20+ files with meaningless assertions
- **Severe Gaps**: Services (8.6% coverage), Agents (4.3%), Core (6.25%), Security components

## Critical Problems Identified

### 1. Meaningless Test Assertions (BLOCKER)

**Problem**: 20+ test files contain tautological assertions that always pass:

```python
# ❌ This assertion is ALWAYS True - provides zero value
assert result is not None or result is None
```

**Files Affected** (20 files):

- `test_phase_coordinator.py` (10 tests)
- `test_timeout_manager.py` (19 tests)
- `test_performance_monitor.py` (17 tests)
- `test_reference_generator.py` (5 tests)
- And 16 more files...

**Impact**: These tests provide false confidence - they pass without testing anything.

**Solution**: Replace with proper assertions or delete the tests.

### 2. Critical Coverage Gaps

#### Security Components (CRITICAL - 0% coverage)

- `crackerjack/services/security.py` - NO TESTS
- `crackerjack/services/secure_subprocess.py` - NO TESTS
- `crackerjack/services/security_logger.py` - NO TESTS
- `crackerjack/agents/security_agent.py` - NO TESTS

**Risk**: Security vulnerabilities may go undetected.

#### Services Layer (8.6% coverage)

- **64 of 70 services untested** including:
  - `git.py` - NO TESTS (critical!)
  - `filesystem.py` - NO TESTS (critical!)
  - `cache.py` - NO TESTS (critical!)
  - Coverage ratchet, config merge, logging, and 58 more...

#### Agents Layer (4.3% coverage)

- **22 of 9 agents untested** including:
  - `coordinator.py` - NO TESTS (critical!)
  - All 9 specialized agents (RefactoringAgent, SecurityAgent, etc.)

#### Core Layer (6.25% coverage)

- 15 of 16 core files untested

### 3. Excessive Async Tests (277 occurrences)

**Problem**: CLAUDE.md warns: "Avoid async tests that hang, use synchronous config tests"

**High-Risk Files**:

- `test_resource_cleanup_integration.py` (46 async)
- `test_performance_agent_enhanced.py` (22 async)
- `test_websocket_lifecycle.py` (20 async)
- `test_timeout_system.py` (16 async)

**Solution**: Convert to synchronous tests where possible, reduce from 277 to \<50.

### 4. Skipped Tests (120 total)

**Complete Test Classes Skipped**:

- `test_async_hook_executor.py` - "Requires complex nested ACB DI setup"
- `test_api_comprehensive.py` - "Requires complex nested ACB DI setup"

**Solution**: Either implement properly using DI patterns or delete if obsolete.

### 5. Test Organization Issues

**Problems**:

- 147+ test files in root `tests/` directory (should be organized)
- `tests/unit/` directory exists but is **EMPTY**
- Duplicate files: `test_documentation_agent (1).py`, `test_performance_agent (1).py`
- No clear separation between unit, integration, and e2e tests

## Improvement Plan - Phased Approach

### Phase 1: Stop the Bleeding (Week 1) - IMMEDIATE

**Goal**: Fix critical issues that provide false confidence

#### 1.1 Fix/Remove Meaningless Assertions

**Priority**: CRITICAL
**Effort**: 2-3 hours
**Files**: 20 files with tautological assertions

**Action**:

```bash
# Fix these files in priority order:
1. test_phase_coordinator.py (10 tests)
2. test_timeout_manager.py (19 tests)
3. test_performance_monitor.py (17 tests)
4. test_reference_generator.py (5 tests)
5. test_mcp_progress_monitor.py (6 tests)
# ... and 15 more files
```

**Options**:

- Option A: Replace with proper assertions (preferred if functions are used)
- Option B: Delete tests (if functions are deprecated/internal)

**Example Fix**:

```python
# Before (meaningless)
def test_run_cleaning_phase_basic():
    try:
        result = run_cleaning_phase()
        assert result is not None or result is None  # ❌ Always True
    except TypeError:
        pytest.skip("Function requires specific arguments")


# After (meaningful - Option A)
@pytest.mark.unit
def test_run_cleaning_phase_returns_bool():
    """Test that run_cleaning_phase returns boolean success status."""
    # Setup: Create test environment with DI
    result = run_cleaning_phase()

    # Assert meaningful behavior
    assert isinstance(result, bool)
    assert result is True  # Expect success in clean environment


# After (deleted - Option B if function is internal/deprecated)
# Test removed - run_cleaning_phase is an internal coordinator function
# tested via integration tests in test_workflow_integration.py
```

#### 1.2 Remove Duplicate Test Files

**Priority**: HIGH
**Effort**: 15 minutes

```bash
# Delete these duplicate files:
rm tests/test_documentation_agent\ \(1\).py
rm tests/test_performance_agent\ \(1\).py
```

#### 1.3 Test Critical Security Components

**Priority**: CRITICAL
**Effort**: 6-8 hours
**Coverage Target**: 80%+ for security components

**New Test Files Needed**:

```
tests/services/test_security.py
tests/services/test_secure_subprocess.py
tests/services/test_security_logger.py
tests/agents/test_security_agent.py
```

**Example Test Structure**:

```python
# tests/services/test_security.py
import pytest
from crackerjack.services.security import SecurityService
from crackerjack.models.protocols import Console


@pytest.mark.unit
@pytest.mark.security
class TestSecurityService:
    """Unit tests for SecurityService."""

    def test_validate_path_blocks_directory_traversal(self):
        """Ensure path validation blocks ../ attacks."""
        service = SecurityService()

        # Test various directory traversal attempts
        assert not service.validate_path("../etc/passwd")
        assert not service.validate_path("foo/../../etc/passwd")
        assert not service.validate_path("/etc/../etc/passwd")

    def test_validate_path_allows_safe_paths(self):
        """Ensure safe paths are allowed."""
        service = SecurityService()

        assert service.validate_path("valid/path/file.txt")
        assert service.validate_path("./local/file.py")
```

### Phase 2: Core Foundation (Week 2-3)

**Goal**: Achieve solid coverage of foundational services

#### 2.1 Test Core Services

**Priority**: CRITICAL
**Effort**: 16-20 hours
**Coverage Target**: 75%+

**Services to Test (Priority Order)**:

1. `services/git.py` - Git operations (CRITICAL)
1. `services/filesystem.py` - File operations (CRITICAL)
1. `services/cache.py` - Caching system (CRITICAL)
1. `services/config_merge.py` - Configuration (HIGH)
1. `services/logging.py` - Logging (HIGH)
1. `services/coverage_ratchet.py` - Quality enforcement (HIGH)

**New Test Files**:

```
tests/services/test_git.py
tests/services/test_filesystem.py
tests/services/test_cache.py
tests/services/test_config_merge.py
tests/services/test_logging.py
tests/services/test_coverage_ratchet.py
```

#### 2.2 Reorganize Test Structure

**Priority**: HIGH
**Effort**: 4-6 hours

**Goal Structure**:

```
tests/
├── unit/                      # Pure unit tests (no I/O, fast)
│   ├── agents/
│   │   ├── test_coordinator.py
│   │   ├── test_security_agent.py
│   │   └── ...
│   ├── services/
│   │   ├── test_git.py
│   │   ├── test_security.py
│   │   └── ...
│   ├── managers/
│   │   ├── test_hook_manager.py
│   │   └── ...
│   ├── core/
│   ├── cli/
│   └── ...
├── integration/               # Integration tests (I/O, slower)
│   ├── test_workflow_integration.py
│   ├── test_mcp_integration.py
│   └── ...
├── performance/               # Performance/benchmark tests
│   └── test_benchmarks.py
└── conftest.py               # Shared fixtures
```

**Migration Script**:

```bash
# Create unit test structure
mkdir -p tests/unit/{agents,services,managers,core,cli,mcp,orchestration}

# Move existing organized tests (keep as-is)
# Move root tests to appropriate locations (manual review needed)

# Update imports in moved files
```

#### 2.3 Reduce Async Tests

**Priority**: MEDIUM
**Effort**: 8-12 hours

**Strategy**:

1. Identify async tests that can be synchronous (use mocks/stubs)
1. Convert configuration tests to synchronous
1. Keep async only where truly needed (I/O operations, timeouts)

**Target**: Reduce from 277 to \<50 async tests

**Example Conversion**:

```python
# Before (async, can hang)
@pytest.mark.asyncio
async def test_batch_processing(batched_saver):
    await batched_saver.start()
    await batched_saver.save_batch([data1, data2])
    assert batched_saver.queue_size == 0


# After (synchronous, fast)
@pytest.mark.unit
def test_batch_configuration(batched_saver):
    """Test batch saver configuration."""
    assert batched_saver.max_batch_size == 100
    assert batched_saver.flush_interval == 5.0
    assert batched_saver.queue_size == 0
```

### Phase 3: Agent System (Week 4-5)

**Goal**: Test all 12 specialized AI agents

#### 3.1 Create Agent Tests

**Priority**: HIGH
**Effort**: 20-24 hours
**Coverage Target**: 70%+

**Agents to Test**:

1. `coordinator.py` - Agent coordination (CRITICAL)
1. `enhanced_coordinator.py` - Enhanced coordination (CRITICAL)
1. `security_agent.py` - Security fixes (HIGH)
1. `refactoring_agent.py` - Complexity reduction (HIGH)
1. `performance_agent.py` - Performance optimization (HIGH)
1. `dry_agent.py` - Code duplication (MEDIUM)
1. `formatting_agent.py` - Style violations (MEDIUM)
1. `import_optimization_agent.py` - Import cleanup (MEDIUM)
1. `test_creation_agent.py` - Test generation (MEDIUM)
1. `test_specialist_agent.py` - Advanced testing (MEDIUM)
1. `documentation_agent.py` - Documentation (LOW)
1. `semantic_agent.py` - Semantic analysis (LOW)
1. `architect_agent.py` - Architecture patterns (LOW)
1. `enhanced_proactive_agent.py` - Proactive prevention (LOW)

**Test Pattern** (using AgentContext):

```python
# tests/unit/agents/test_refactoring_agent.py
import pytest
from crackerjack.agents.refactoring_agent import RefactoringAgent
from crackerjack.agents.context import AgentContext
from crackerjack.models.protocols import Console


@pytest.mark.unit
class TestRefactoringAgent:
    """Unit tests for RefactoringAgent."""

    @pytest.fixture
    def agent_context(self):
        """Create agent context for testing."""
        return AgentContext(
            package_path="/tmp/test_pkg",
            verbose=False,
            console=Console(),
            # ... other required context
        )

    @pytest.fixture
    def agent(self, agent_context):
        """Create RefactoringAgent instance."""
        return RefactoringAgent(agent_context)

    def test_agent_initialization(self, agent):
        """Test agent initializes correctly."""
        assert agent.name == "refactoring"
        assert agent.confidence_threshold == 0.9

    def test_detects_high_complexity(self, agent):
        """Test detection of functions with complexity >15."""
        code = """
def complex_function(x):
    if x > 0:
        if x > 10:
            if x > 20:
                if x > 30:
                    return "very high"
                return "high"
            return "medium"
        return "low"
    return "negative"
"""
        issues = agent.analyze(code)
        assert len(issues) > 0
        assert any("complexity" in issue.message.lower() for issue in issues)

    def test_suggests_refactoring(self, agent):
        """Test agent suggests breaking complex functions."""
        # Test refactoring suggestions
        pass
```

### Phase 4: Remaining Gaps (Week 6-8)

**Goal**: Fill all major coverage gaps

#### 4.1 Test MCP Components

**Priority**: MEDIUM
**Effort**: 12-16 hours
**Coverage Target**: 60%+

**Files to Test**:

- `mcp/server.py`
- `mcp/websocket_server.py`
- `mcp/progress_monitor.py`
- `mcp/task_manager.py`
- `mcp/cache.py`
- And 11 more MCP files...

#### 4.2 Test Managers

**Priority**: MEDIUM
**Effort**: 8-12 hours

**Untested Managers**:

- `managers/hook_manager.py`
- `managers/publish_manager.py`
- `managers/plugin_manager.py`
- And 6 more...

#### 4.3 Test CLI Layer

**Priority**: MEDIUM
**Effort**: 6-8 hours

**Untested CLI Files**:

- `cli/options.py`
- `cli/output.py`
- And 7 more CLI files...

#### 4.4 Test UI Layer

**Priority**: LOW
**Effort**: 4-6 hours

**Files to Test**:

- `ui/dashboard_renderer.py`

#### 4.5 Test Remaining Services

**Priority**: LOW (after critical services)
**Effort**: 30-40 hours
**Coverage Target**: 50%+

**58 remaining untested services** - prioritize based on usage frequency

### Phase 5: Quality & Refinement (Ongoing)

#### 5.1 Fix Skipped Tests

**Priority**: MEDIUM
**Effort**: 12-16 hours

**Action**: Review all 120 skipped tests:

1. Implement properly using DI patterns (preferred)
1. Delete if obsolete/redundant
1. Document why skipped if legitimately untestable

#### 5.2 Improve Test Isolation

**Priority**: LOW
**Effort**: 8-12 hours

**Actions**:

- Remove builtin injection from conftest.py (305 lines)
- Reduce fixture dependency complexity
- Use proper DI patterns instead of singleton resets

#### 5.3 Performance Test Suite

**Priority**: LOW
**Effort**: 6-8 hours

**Expand `tests/performance/`**:

- Add benchmarks for critical paths
- Use `PerformanceTestHelper` from base_test.py
- Set performance regression thresholds

## Coverage Targets by Module

| Module | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Final Goal |
|--------|---------|---------|---------|---------|---------|------------|
| **services** | 8.6% | 15% | 40% | 50% | 60% | 80% |
| **agents** | 4.3% | 5% | 10% | 70% | 75% | 75% |
| **core** | 6.25% | 10% | 50% | 70% | 80% | 90% |
| **security** | varies | 80% | 85% | 90% | 95% | 95% |
| **mcp** | 12.5% | 15% | 20% | 30% | 60% | 65% |
| **managers** | 33% | 40% | 60% | 70% | 80% | 85% |
| **cli** | 11% | 15% | 30% | 40% | 60% | 70% |
| **orchestration** | 100% | 100% | 100% | 100% | 100% | 100% |
| **Overall** | 19.6% | 25% | 40% | 55% | 70% | 100% |

## Test Quality Metrics

### Current State

- ❌ Meaningless assertions: 120+ occurrences
- ❌ Skipped tests: 120 tests
- ❌ Async tests: 277 tests
- ❌ Test organization: Poor (147+ files in root)
- ❌ Security test coverage: ~0%
- ✅ Good patterns exist: ACB settings, regex patterns, orchestration

### Target State (End of Phase 5)

- ✅ Meaningful assertions: 100%
- ✅ Skipped tests: \<10 (documented reasons)
- ✅ Async tests: \<50 (only where necessary)
- ✅ Test organization: Excellent (unit/integration separation)
- ✅ Security test coverage: 95%+
- ✅ Good patterns: Consistent protocol-based testing

## Quick Wins for Immediate Impact

**Week 1 Quick Wins** (can be done in parallel):

1. **Delete Meaningless Tests** (2 hours)

   - If functions are internal/deprecated, just delete the tests
   - Immediate coverage accuracy improvement

1. **Test `services/security.py`** (3 hours)

   - Critical security component
   - High value, relatively straightforward

1. **Test `services/git.py`** (4 hours)

   - Core functionality
   - Many integration tests already exist (can extract patterns)

1. **Remove Duplicates** (15 minutes)

   - Clean up `(1).py` files

1. **Create Test Organization Structure** (30 minutes)

   - Create `tests/unit/` subdirectories
   - Document new structure in README

**Total Quick Wins**: ~10 hours for major quality improvement

## Measurement & Tracking

### Daily Metrics

```bash
# Run with coverage report
python -m crackerjack --run-tests

# Check coverage by module
coverage report --include="crackerjack/services/*"
coverage report --include="crackerjack/agents/*"
```

### Weekly Goals

- Phase 1 (Week 1): +5.4% coverage (19.6% → 25%)
- Phase 2 (Week 2-3): +15% coverage (25% → 40%)
- Phase 3 (Week 4-5): +15% coverage (40% → 55%)
- Phase 4 (Week 6-8): +15% coverage (55% → 70%)

### Success Criteria

- ✅ Zero meaningless assertions
- ✅ Security coverage >95%
- ✅ Core services coverage >75%
- ✅ Overall coverage >70% (ratchet system)
- ✅ Clear test organization (unit/integration)
- ✅ \<50 async tests
- ✅ \<10 skipped tests

## Implementation Guidelines

### Test Quality Standards

**Every Test Should**:

1. ✅ Have meaningful assertions (not tautologies)
1. ✅ Test one specific behavior
1. ✅ Be independent (no test order dependencies)
1. ✅ Use proper fixtures (protocol-based DI)
1. ✅ Have clear docstrings explaining what is tested
1. ✅ Use appropriate markers (@pytest.mark.unit, etc.)
1. ✅ Follow naming: `test_<action>_<scenario>`

**Avoid**:

1. ❌ Async tests that can hang
1. ❌ Over-mocking (test behavior, not implementation)
1. ❌ Tautological assertions
1. ❌ Testing DI implementation details
1. ❌ Blanket pytest.skip() for entire classes
1. ❌ Builtin injection
1. ❌ Complex fixture dependency chains

### Example: Good Test Structure

```python
# tests/unit/services/test_git.py
import pytest
from pathlib import Path
from crackerjack.services.git import GitService
from crackerjack.models.protocols import Console


@pytest.mark.unit
class TestGitService:
    """Unit tests for GitService.

    Tests core git operations without actual git commands.
    Uses mocks for subprocess calls.
    """

    @pytest.fixture
    def git_service(self, tmp_path):
        """Create GitService instance for testing."""
        return GitService(repo_path=tmp_path)

    def test_initialization_with_valid_repo(self, git_service, tmp_path):
        """Test GitService initializes with valid repository path."""
        assert git_service.repo_path == tmp_path
        assert isinstance(git_service.repo_path, Path)

    def test_is_git_repo_returns_false_for_non_repo(self, git_service):
        """Test is_git_repo returns False for non-git directory."""
        # No .git directory created
        assert git_service.is_git_repo() is False

    def test_is_git_repo_returns_true_for_repo(self, git_service, tmp_path):
        """Test is_git_repo returns True for git directory."""
        # Create .git directory
        (tmp_path / ".git").mkdir()
        assert git_service.is_git_repo() is True

    @pytest.mark.parametrize(
        "branch_name,expected",
        [
            ("main", True),
            ("feature/test", True),
            ("invalid..name", False),
            ("invalid name", False),
        ],
    )
    def test_validate_branch_name(self, git_service, branch_name, expected):
        """Test branch name validation with various inputs."""
        assert git_service.validate_branch_name(branch_name) == expected
```

## Risks & Mitigation

### Risk 1: Test Suite Becomes Too Slow

**Mitigation**:

- Use pytest-xdist for parallelization (already configured)
- Keep unit tests fast (\<100ms each)
- Use integration test markers for slow tests
- Target: Full suite \<60s

### Risk 2: False Coverage Increase

**Mitigation**:

- Focus on behavior testing, not line coverage
- Code review all new tests
- Use mutation testing to verify test quality
- Avoid trivial getters/setters

### Risk 3: Breaking Changes During Refactoring

**Mitigation**:

- One module at a time
- Keep existing integration tests
- Git branch per phase
- Run full suite after each change

### Risk 4: Async Test Instability

**Mitigation**:

- Convert to synchronous where possible
- Use proper timeout configuration
- Mock async operations for unit tests
- Keep async tests in integration suite

## Conclusion

This plan provides a structured approach to improving Crackerjack's test suite from 19.6% to 100% coverage while addressing critical quality issues.

**Immediate Priority** (Week 1):

1. Fix/remove meaningless assertions (120+ tests)
1. Test critical security components (0% → 80%+)
1. Remove duplicate files
1. Test core services (git, filesystem, cache)

**Key Success Factors**:

- Start with critical security/core components
- Fix quality issues before adding more tests
- Reorganize structure for maintainability
- Follow protocol-based DI patterns from CLAUDE.md
- Reduce async tests significantly
- Achieve 70%+ coverage within 8 weeks

**Next Steps**:

1. Review and approve this plan
1. Create tracking board for phases
1. Begin Phase 1 implementation
1. Set up daily coverage monitoring
1. Schedule weekly progress reviews
