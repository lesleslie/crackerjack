# AI-Fix Test Failure & Test Environment Implementation Plan

**Date**: 2026-02-05
**Status**: Planning Phase
**Priority**: High

______________________________________________________________________

## Executive Summary

This plan extends Crackerjack's AI-fix system to automatically detect, diagnose, and repair:

1. **Failing tests** in project codebases
1. **Test environment issues** (pytest exceptions, configuration problems)
1. **Self-healing** (crackerjack fixing its own test failures)
1. **Dead code** (unused variables, imports, functions, classes) with AI-powered cleanup

**Current Gaps**:

- AI-fix only handles static analysis issues (ruff, creosote, etc.) but ignores test failures
- Vulture exists but is not activated in the workflow
- deadcode tool has auto-fix but is not integrated
- No AI-agent for intelligently deciding which dead code to remove

**Expected Outcomes**:

- **Test Failures**: AI-fix can fix 60-80% of test failures automatically
- **Dead Code**: AI-fix can safely remove 80-90% of dead code with human confirmation
- **Performance**: Fast hooks: ~5s → ~11s (adding Vulture), Comprehensive: ~30s → ~80s (already includes Skylos)

______________________________________________________________________

## Track 2: Dead Code Detection Integration (Parallel Implementation)

**Status**: Ready to start (can run in parallel with Track 1: Test Failures)
**Priority**: High (quick wins with high impact)
**Duration**: 2-3 weeks

### Overview

This track adds intelligent dead code detection and removal to crackerjack's AI-fix workflow, leveraging three complementary tools:

| Tool | Speed | Findings | Best For | Auto-Fix |
|------|-------|----------|---------|----------|
| **deadcode** | 2.2s ⚡ | Conservative (0 issues in crackerjack) | Fast sanity checks | ✅ Yes |
| **Vulture** | 6.1s 🎯 | Moderate (22 actionable issues) | Daily cleanup | ❌ No |
| **Skylos** | 49.6s 🛡️ | Comprehensive (626 items) | Deep security analysis | ❌ No |

**Key Insight from session-buddy Analysis**:

```
Performance: deadcode (2.2s) < Vulture (6.1s) < Skylos (49.6s)
Findings:  deadcode (0) < Vulture (22) < Skylos (626)
Trade-off: Speed vs. Comprehensiveness
```

### Tool Comparison Results

**What Each Tool Found in crackerjack**:

**🦅 Vulture: 22 Actionable Issues (100% confidence)**

- 17 unused exception variables (anti-pattern in 5 files)
  ```python
  except Exception as exc_type, exc_value, traceback:  # ❌ All unused
      pass
  ```
- 2 unused imports:
  - `runtime_checkable` in `reflection/storage.py`
  - `List` in `sync.py` (using `list` instead)
- 3 unused parameters:
  - `max_age_hours` in `token_optimizer.py:589`
  - `recursive` in `app_monitor.py:44`
  - `frame` in `shutdown_manager.py:196`

**💀 deadcode: 0 Issues (Conservative)**

- Focuses on entire unused functions/classes
- Ignores "small" issues (variables, imports, parameters)
- Useful for fast sanity checks but misses actionable cleanup

**🛡️ Skylos: 626 Items (Most Comprehensive)**

- Dead code (like vulture's 22 issues)
- Security smells
- Code quality issues
- Tainted data flows
- Potential vulnerabilities
- 8x slower but 28x more findings than vulture

### Recommended Architecture

**Three-Tier Strategy** (mirrors session-buddy workflow):

```
┌─────────────────────────────────────────────────────────────┐
│ 📅 Dead Code Detection Workflow                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Fast Hooks (~11s total, up from ~5s):                      │
│  ─────────────────────────────────────────                   │
│  1. Existing fast tools (~5s)                               │
│  2. Vulture (~6s) ← ADD HERE                                │
│     → Catches daily dead code accumulation                   │
│     → AI-fix removes with high confidence (0.8+)             │
│                                                             │
│  Comprehensive Hooks (~80s total, already ~30s):             │
│  ────────────────────────────────────────────                │
│  1. Existing comprehensive tools (~30s)                      │
│  2. Skylos (~50s) ← ALREADY ACTIVE                          │
│     → Deep analysis monthly                                 │
│     → AI-fix reviews with human confirmation                 │
│                                                             │
│  Optional: deadcode with Auto-Fix                           │
│  ─────────────────────────────────────                       │
│  python -m deadcode --fix --dry-run                         │
│  → Preview auto-cleanup before applying                      │
│  → Conservative, safe removals only                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2A: Activate Vulture in Fast Hooks

**File**: `crackerjack/config/tool_commands.py` (or equivalent hook configuration)

**Add Vulture to fast hooks**:

```python
@register_hook(
    name="vulture",
    stage="fast",
    command=["uv", "run", "vulture", "crackerjack", "--min-confidence", "90"],
    description="Find unused Python code (fast daily check)",
)
```

**Rationale**:

- **6.1s** is acceptable for fast hooks (total: ~11s)
- **22 actionable issues** with 100% confidence = safe to auto-remove
- **Daily frequency** prevents dead code accumulation
- **High confidence threshold (90%)** reduces false positives

### Phase 2B: Create DeadCodeRemovalAgent

**File**: `crackerjack/agents/dead_code_agent.py` (NEW)

**Purpose**: Intelligently decide which dead code to remove safely

**Handles**: `IssueType.DEAD_CODE` (already exists)

**Capabilities**:

```python
class DeadCodeRemovalAgent(SubAgent):
    """Agent for safe dead code removal with AI-powered decision making."""

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.name = "DeadCodeRemovalAgent"

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.DEAD_CODE, IssueType.IMPORT_ERROR}

    async def can_handle(self, issue: Issue) -> float:
        """Determine if we can safely remove this dead code."""
        if issue.type not in self.get_supported_types():
            return 0.0

        confidence = float(issue.metadata.get("confidence", 0.0))

        # High confidence (>90) from Vulture: Safe to auto-remove
        if confidence >= 0.9:
            return 0.95

        # Medium confidence (70-90): Require human confirmation
        if confidence >= 0.7:
            return 0.7

        # Low confidence (<70): Too risky, skip
        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Remove dead code with safety checks."""
        dead_code_type = issue.metadata.get(
            "dead_code_type"
        )  # "variable", "import", "function", etc.

        if dead_code_type == "unused_variable":
            return await self._remove_unused_variable(issue)

        if dead_code_type == "unused_import":
            return await self._remove_unused_import(issue)

        if dead_code_type == "unused_parameter":
            return await self._handle_unused_parameter(issue)

        if dead_code_type == "unused_function":
            return await self._handle_unused_function(issue)

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Unsupported dead code type: {dead_code_type}"],
        )
```

**Safety Mechanisms**:

1. **Confidence Threshold**: Only auto-remove with ≥90% confidence
1. **Read-Only Analysis**: Check file context before removal
1. **Preserve Docstrings**: Don't remove functions with docstrings (likely public API)
1. **Skip Test Files**: Dead code in tests might be intentional (fixtures, test helpers)
1. **Git History**: Check if code was recently added (\<7 days) - might be WIP

```python
def _is_safe_to_remove(self, issue: Issue) -> tuple[bool, str]:
    """Check if dead code is safe to remove.

    Returns:
        (is_safe, reason)
    """
    file_path = Path(issue.file_path)

    # Skip test files
    if "test" in file_path.parts:
        return False, "Test files excluded"

    # Check if code has docstring (likely public API)
    content = self.context.get_file_content(file_path)
    if "def " in issue.message and '"""' in content:
        return False, "Function has docstring (likely public API)"

    # Check git history (recently added code)
    is_recent, commit_age = self._check_git_history(file_path)
    if is_recent and commit_age < 7:
        return False, f"Added {commit_age} days ago (might be WIP)"

    # Check for decorators (@app.route, @dataclass, etc.)
    if self._has_decorator(content, issue):
        return False, "Has decorator (framework hook)"

    return True, "Safe to remove"
```

### Phase 2C: Integrate deadcode Auto-Fix (Optional)

**File**: `crackerjack/adapters/refactor/deadcode.py` (NEW)

**Purpose**: Wrapper for deadcode tool's auto-fix capability

```python
class DeadcodeAdapter(BaseToolAdapter):
    """Adapter for deadcode tool with auto-fix support."""

    def __init__(self, config: dict[str, t.Any]):
        super().__init__(config)
        self.tool_name = "deadcode"
        self.has_autofix = True

    def run_with_fix(self, args: list[str]) -> HookResult:
        """Run deadcode with auto-fix enabled."""
        # Check if --fix flag is supported
        if "--fix" in args:
            return self._run_autofix(args)

        # Dry-run mode: just detect
        return super().run(args)

    def _run_autofix(self, args: list[str]) -> HookResult:
        """Run deadcode in auto-fix mode."""
        fix_args = args + ["--fix"]

        result = subprocess.run(
            ["uv", "run", "deadcode"] + fix_args,
            capture_output=True,
            text=True,
            timeout=60,
        )

        return HookResult(
            name=self.tool_name,
            status="passed" if result.returncode == 0 else "fixed",
            output=result.stdout,
            error=result.stderr,
            metadata={
                "autofix_applied": True,
                "files_modified": self._parse_fixed_files(result.stdout),
            },
        )
```

**Configuration**:

```yaml
# settings/crackerjack.yaml
tools:
  deadcode:
    enabled: true
    stage: "fast"  # or "comprehensive" for conservative approach
    autofix: false  # Set to true for automatic removal
    confidence: 90  # Minimum confidence threshold
    exclude_patterns:
      - "tests/*"
      - "*/conftest.py"
```

### Phase 2D: Agent Routing for Dead Code

**File**: `crackerjack/agents/coordinator.py`

**Update ISSUE_TYPE_TO_AGENTS**:

```python
IssueType.DEAD_CODE: [
    "DeadCodeRemovalAgent",     # NEW: Primary handler
    "ImportOptimizationAgent",   # Handles unused imports
    "RefactoringAgent",          # Handles unused functions/classes
],
```

**Priority Order**:

1. **DeadCodeRemovalAgent**: Specialized for safe dead code removal
1. **ImportOptimizationAgent**: Handles import-specific issues
1. **RefactoringAgent**: Fallback for complex refactoring scenarios

### Performance Impact Analysis

**Current Fast Hooks**: ~5s
**With Vulture**: ~11s (120% increase, still acceptable)

**Current Comprehensive Hooks**: ~30s
**With Skylos**: ~80s (already active, this is baseline)

**Recommendation**:

- ✅ **Add Vulture to fast hooks**: 6s is acceptable for daily workflow
- ✅ **Skylos stays in comprehensive**: 50s is acceptable for weekly/monthly runs
- ⚠️ **deadcode auto-fix**: Use manually (`--fix --dry-run`) until confidence high

### Expected Outcomes

**Quantitative**:

- **Vulture**: 22 issues → 0 issues (100% removal rate)
- **Auto-fix confidence**: 90%+ (only high-confidence removals)
- **False positive rate**: \<5% (conservative threshold)
- **Time to clean**: \<30 seconds (vs. manual ~2 hours)

**Qualitative**:

- **Codebase hygiene**: Daily dead code cleanup prevents accumulation
- **Developer confidence**: High confidence threshold means safe removals
- **Workflow integration**: Seamless with existing fast/comprehensive phases

### Safety & Validation

**Multi-Layer Safety**:

1. **Tool Confidence**: Vulture 90%+ threshold
1. **Agent Safety Checks**: `_is_safe_to_remove()` with 5 checks
1. **Human Confirmation**: Medium-confidence issues (70-90%) require review
1. **Rollback Capability**: Git-based recovery if needed
1. **Validation**: Re-run tools after removal to confirm

**Example Safety Decision Tree**:

```
Vulture detects unused variable (95% confidence)
    ↓
DeadCodeRemovalAgent.can_handle() → 0.95 confidence
    ↓
_is_safe_to_remove() checks:
    ├─ Is it a test file? → YES → Skip
    ├─ Has docstring? → NO → Continue
    ├─ Recently added? → NO → Continue
    ├─ Has decorator? → NO → Continue
    └─ Public API? → NO → Safe to remove
    ↓
Apply fix with 0.95 confidence
```

### Integration with AI-Fix Workflow

**How dead code flows through AI-fix**:

```
1. Fast Hooks Run
   ↓
2. Vulture detects 22 unused items
   ↓
3. HookResult created with metadata:
   {
     "name": "vulture",
     "status": "failed",
     "output": "...",
     "metadata": {
       "dead_code_items": [
         {
           "file": "crackerjack/foo.py",
           "line": 42,
           "type": "unused_variable",
           "name": "exc_type",
           "confidence": 95
         },
         ...
       ]
     }
   }
   ↓
4. _parse_hook_results_to_issues()
   ↓
5. Each dead code item → Issue:
   Issue(
     type=IssueType.DEAD_CODE,
     message="Unused variable 'exc_type' at foo.py:42",
     file_path="crackerjack/foo.py",
     line_number=42,
     metadata={
       "dead_code_type": "unused_variable",
       "confidence": 0.95,
       "variable_name": "exc_type",
     }
   )
   ↓
6. DeadCodeRemovalAgent.analyze_and_fix()
   ↓
7. Safety checks → Remove variable
   ↓
8. Re-run Vulture → Confirm 21 items remaining
```

### Testing Strategy

**Unit Tests** (`tests/agents/test_dead_code_agent.py`):

```python
class TestDeadCodeRemovalAgent:
    def test_removes_unused_variable(self):
        """Test removal of simple unused variable."""
        # Create file with unused variable
        # Run agent
        # Verify variable removed

    def test_skips_public_api(self):
        """Test that public API (with docstrings) is preserved."""
        # Create function with docstring
        # Run agent
        # Verify function NOT removed

    def test_checks_git_history(self):
        """Test that recently added code is preserved."""
        # Create file with unused code
        # Git commit it
        # Run agent
        # Verify code NOT removed (too recent)
```

**Integration Tests** (`tests/integration/test_dead_code_workflow.py`):

```python
class TestDeadCodeWorkflow:
    def test_vulture_integration(self):
        """Test Vulture → Issue → Agent → Fix flow."""
        # Run Vulture
        # Parse results
        # Create Issues
        # Run DeadCodeRemovalAgent
        # Verify fixes applied

    def test_confidence_threshold(self):
        """Test that low-confidence issues are skipped."""
        # Create Vulture result with 60% confidence
        # Verify agent returns 0.0 confidence
```

### Rollout Plan

**Week 1: Vulture Integration**

- Add Vulture to fast hooks
- Configure 90% confidence threshold
- Test on crackerjack codebase
- Measure: Should find ~22 issues

**Week 2: DeadCodeRemovalAgent**

- Implement agent with safety checks
- Add to ISSUE_TYPE_TO_AGENTS routing
- Test on sample dead code
- Validate safety mechanisms

**Week 3: Integration & Validation**

- End-to-end workflow testing
- Performance impact measurement
- Documentation
- User education

**Week 4: Optional - deadcode Auto-Fix**

- Evaluate deadcode results
- Add adapter if beneficial
- Compare with Vulture results
- Decide on activation

### Open Questions

1. **Confidence Threshold**: Is 90% too conservative? Should we lower to 80%?

   - **Recommendation**: Start at 90%, lower based on false positive rate

1. **Auto-Fix Activation**: Should deadcode's `--fix` be enabled by default?

   - **Recommendation**: Manual mode first, auto-fix after validation

1. **Skylos Integration**: Should Skylos dead code findings go through AI-fix?

   - **Recommendation**: Yes, but with human confirmation (too many false positives)

1. **Frequency**: Should Vulture run in CI or just locally?

   - **Recommendation**: Both - fast hooks locally, as optional CI check

______________________________________________________________________

## Phase 1: Understanding Current Architecture

### Current AI-Fix Flow

```
Hook Results (fast/comprehensive)
    ↓
_parse_hook_results_to_issues() [autofix_coordinator.py:756]
    ↓
List[Issue] with IssueType
    ↓
AgentCoordinator.handle_issues_proactively()
    ↓
Specialized Agents (TestSpecialistAgent, TestCreationAgent, etc.)
    ↓
FixResult applied to files
```

### Current Test Agents

| Agent | Handles | Confidence | Gap |
|-------|---------|------------|-----|
| **TestSpecialistAgent** | TEST_FAILURE, IMPORT_ERROR | 0.7-1.0 | ✅ Exists but not getting test data |
| **TestCreationAgent** | TEST_FAILURE, COVERAGE_IMPROVEMENT, TEST_ORGANIZATION | 0.85-0.95 | ✅ Exists but not getting test data |

### Key Missing Components

1. **Test Result Parsing**: No conversion from pytest output → Issues
1. **Test Environment Diagnostics**: No agent for pytest/config/environment issues
1. **Self-Healing**: No mechanism to fix crackerjack's own test failures

______________________________________________________________________

## Phase 2: Test Result Parsing Infrastructure

### 2.1 Create TestResultParser

**File**: `crackerjack/parsers/test_result_parser.py` (NEW)

**Purpose**: Parse pytest output into structured test failure data

**Key Responsibilities**:

```python
class TestResultParser:
    """Parse pytest output into structured test failure information."""

    def parse_test_output(self, output: str) -> list[TestFailure]:
        """Parse pytest stdout/stderr into TestFailure objects.

        Returns:
            List of TestFailure with:
            - test_id: "tests/test_foo.py::TestClass::test_method"
            - error_type: "AssertionError", "FixtureNotFound", etc.
            - error_message: Full error traceback
            - file_path: Path to test file
            - line_number: Line where failure occurred
        """
```

**Implementation Strategy**:

1. Use existing pytest output patterns from `services/patterns/testing/pytest_output.py`
1. Parse test collection failures (import errors, syntax errors)
1. Parse test execution failures (assertions, fixtures, exceptions)
1. Extract file paths and line numbers from tracebacks
1. Distinguish between test code failures vs. test infrastructure failures

**Test Failure Categories**:

```python
class TestFailureCategory(Enum):
    PROJECT_CODE = "project_code"  # Bug in code being tested
    TEST_CODE = "test_code"  # Bug in test itself
    TEST_FIXTURE = "test_fixture"  # Fixture issue
    TEST_ENVIRONMENT = "test_environment"  # Pytest/config issue
    IMPORT_ERROR = "import_error"  # Missing dependency
```

### 2.2 Extend Hook Result → Issue Conversion

**File**: `crackerjack/core/autofix_coordinator.py`

**Modify**: `_parse_hook_results_to_issues()` method

**Add**: Test result detection and conversion logic

```python
def _parse_hook_results_to_issues(self, hook_results: Sequence[object]) -> list[Issue]:
    """Parse hook results into issues, including test failures."""

    # EXISTING: Parse static analysis hook results
    issues = self._parse_static_analysis_results(hook_results)

    # NEW: Parse test results
    test_failures = self._parse_test_results(hook_results)
    issues.extend(test_failures)

    return self._deduplicate_issues(issues)


def _parse_test_results(self, hook_results: Sequence[object]) -> list[Issue]:
    """Extract test failures from hook results and convert to Issues."""
    from crackerjack.parsers.test_result_parser import TestResultParser

    parser = TestResultParser()
    test_issues: list[Issue] = []

    for result in hook_results:
        hook_name = getattr(result, "name", "")
        if "pytest" not in hook_name.lower():
            continue

        raw_output = self._extract_raw_output(result)
        test_failures = parser.parse_test_output(raw_output)

        for failure in test_failures:
            issue = Issue(
                type=self._map_test_failure_to_issue_type(failure),
                message=failure.error_message,
                file_path=str(failure.file_path),
                line_number=failure.line_number,
                stage="test",
                metadata={
                    "test_id": failure.test_id,
                    "error_type": failure.error_type,
                    "category": failure.category.value,
                },
            )
            test_issues.append(issue)

    return test_issues


def _map_test_failure_to_issue_type(self, failure: TestFailure) -> IssueType:
    """Map test failure category to IssueType."""
    if failure.category == TestFailureCategory.TEST_ENVIRONMENT:
        return IssueType.TEST_ENVIRONMENT  # NEW TYPE
    if failure.category == TestFailureCategory.IMPORT_ERROR:
        return IssueType.IMPORT_ERROR
    return IssueType.TEST_FAILURE
```

______________________________________________________________________

## Phase 3: Test Environment Diagnostic Agent

### 3.1 Create TestEnvironmentAgent

**File**: `crackerjack/agents/test_environment_agent.py` (NEW)

**Purpose**: Diagnose and repair test environment issues (pytest config, fixtures, dependencies)

**Handles**: `IssueType.TEST_ENVIRONMENT` (NEW)

**Capabilities**:

1. **Pytest Configuration Issues**:

   - Missing pytest plugins
   - Incorrect pytest.ini/pyproject.toml settings
   - Conflicting test markers
   - Test discovery problems

1. **Fixture Issues**:

   - Missing fixtures (autouse, conftest)
   - Fixture scope problems
   - Fixture dependency cycles

1. **Test Environment Issues**:

   - Missing test dependencies
   - Path resolution problems
   - PYTHONPATH issues
   - Test isolation failures

```python
class TestEnvironmentAgent(SubAgent):
    """Agent for diagnosing and repairing test environment issues."""

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.name = "TestEnvironmentAgent"

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.TEST_ENVIRONMENT, IssueType.IMPORT_ERROR}

    async def can_handle(self, issue: Issue) -> float:
        """Check if this is a test environment issue we can fix."""
        if issue.type not in self.get_supported_types():
            return 0.0

        message_lower = issue.message.lower()

        # High confidence for detectable patterns
        if any(pattern in message_lower for pattern in self._get_diagnostic_patterns()):
            return 0.95

        # Medium confidence for general test errors
        if "pytest" in message_lower or "fixture" in message_lower:
            return 0.7

        return 0.0

    def _get_diagnostic_patterns(self) -> list[str]:
        """Return patterns indicating test environment issues."""
        return [
            "unknown option",
            "unrecognized arguments",
            "no fixture named",
            "fixture not found",
            "error importing",
            "collection error",
            "import error",
            "module not found",
            "test discovery error",
            "conftest",
        ]

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Diagnose and fix test environment issues."""
        # Implementation in Phase 4
```

______________________________________________________________________

## Phase 4: Agent Implementation Details

### 4.1 TestEnvironmentAgent Fix Strategies

#### Strategy 1: Missing Pytest Plugins

**Pattern**: `unknown option: --cov`

**Diagnosis**:

```python
def _check_missing_plugins(self, issue: Issue) -> dict[str, t.Any]:
    """Check if issue is due to missing pytest plugin."""
    message_lower = issue.message.lower()

    if "unknown option" in message_lower:
        option = self._extract_unknown_option(issue.message)
        plugin_map = {
            "--cov": "pytest-cov",
            "--asyncio": "pytest-asyncio",
            "--benchmark": "pytest-benchmark",
            "--mock": "pytest-mock",
        }

        if option in plugin_map:
            return {
                "diagnosis": "missing_plugin",
                "plugin": plugin_map[option],
                "option": option,
            }

    return {"diagnosis": "unknown"}
```

**Fix**:

```python
def _install_missing_plugin(self, plugin_name: str) -> FixResult:
    """Install missing pytest plugin via uv."""
    import subprocess

    try:
        result = subprocess.run(
            ["uv", "add", "--dev", plugin_name],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return FixResult(
                success=True,
                confidence=0.95,
                fixes_applied=[f"Installed pytest plugin: {plugin_name}"],
            )
    except Exception as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to install {plugin_name}: {e}"],
        )
```

#### Strategy 2: Fixture Issues

**Pattern**: `fixture 'temp_pkg_path' not found`

**Diagnosis**:

```python
def _diagnose_fixture_issue(self, issue: Issue) -> dict[str, t.Any]:
    """Diagnose fixture-related issues."""
    message = issue.message

    if "fixture" in message.lower() and "not found" in message.lower():
        fixture_name = self._extract_fixture_name(message)

        # Check if fixture exists in any conftest.py
        fixture_locations = self._find_fixture_definition(fixture_name)

        if not fixture_locations:
            return {
                "diagnosis": "missing_fixture",
                "fixture_name": fixture_name,
                "suggestion": f"Create fixture in conftest.py",
            }

        # Check if fixture is in scope
        return {
            "diagnosis": "fixture_scope",
            "fixture_name": fixture_name,
            "locations": fixture_locations,
        }

    return {"diagnosis": "unknown"}
```

**Fix**:

```python
def _create_missing_fixture(self, fixture_name: str, test_path: Path) -> FixResult:
    """Create missing fixture in appropriate conftest.py."""
    # Find nearest conftest.py or create new one
    conftest_path = self._find_or_create_conftest(test_path)

    # Generate fixture code based on name patterns
    fixture_code = self._generate_fixture_code(fixture_name)

    # Add fixture to conftest.py
    if self._add_fixture_to_conftest(conftest_path, fixture_code):
        return FixResult(
            success=True,
            confidence=0.85,
            fixes_applied=[f"Created fixture: {fixture_name}"],
            files_modified=[str(conftest_path)],
        )
```

#### Strategy 3: Import Errors in Tests

**Pattern**: `ImportError: No module named 'crackerjack.utils'`

**Diagnosis**:

```python
def _diagnose_import_error(self, issue: Issue) -> dict[str, t.Any]:
    """Diagnose import errors in tests."""
    message = issue.message

    if "importerror" in message.lower() or "modulenotfounderror" in message.lower():
        module_name = self._extract_module_name(message)

        # Check if module exists in project
        module_exists = self._check_module_exists(module_name)

        # Check if PYTHONPATH issue
        path_issue = self._check_path_issue(module_name)

        return {
            "diagnosis": "import_error",
            "module": module_name,
            "exists": module_exists,
            "path_issue": path_issue,
        }

    return {"diagnosis": "unknown"}
```

**Fix**:

```python
def _fix_import_error(self, diagnosis: dict[str, t.Any]) -> FixResult:
    """Fix import errors in test environment."""
    if diagnosis["path_issue"]:
        # Add PYTHONPATH fix to conftest.py
        return self._add_pythonpath_fix(diagnosis["module"])

    if not diagnosis["exists"]:
        # Module doesn't exist - might need to be created
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Module {diagnosis['module']} does not exist"],
        )

    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=["Unable to diagnose import error"],
    )
```

### 4.2 Extend TestSpecialistAgent

**File**: `crackerjack/agents/test_specialist_agent.py`

**Enhancements**:

1. **Parse structured test failures** (use TestResultParser output)
1. **Fix project code bugs** detected by tests
1. **Fix test code bugs** (incorrect assertions, wrong expectations)
1. **Apply patches based on failure type**

```python
async def analyze_and_fix(self, issue: Issue) -> FixResult:
    """Fix test failures using structured failure data."""
    failure_data = issue.metadata.get("test_failure")

    if notfailure_data:
        # Fallback to existing pattern-based approach
        return await self._fix_with_patterns(issue)

    category = failure_data.get("category")
    test_id = failure_data.get("test_id")

    if category == TestFailureCategory.PROJECT_CODE:
        return await self._fix_project_code_failure(issue, failure_data)

    if category == TestFailureCategory.TEST_CODE:
        return await self._fix_test_code_failure(issue, failure_data)

    if category == TestFailureCategory.IMPORT_ERROR:
        return await self._fix_import_failure(issue, failure_data)

    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Unknown test failure category: {category}"],
    )
```

______________________________________________________________________

## Phase 5: Integration Points

### 5.1 Extend IssueType Enum

**File**: `crackerjack/agents/base.py`

**Add new issue type**:

```python
class IssueType(Enum):
    # ... existing types ...

    TEST_ENVIRONMENT = "test_environment"  # NEW
```

### 5.2 Update Agent Routing

**File**: `crackerjack/agents/coordinator.py`

**Add to ISSUE_TYPE_TO_AGENTS mapping**:

```python
IssueType.TEST_ENVIRONMENT: [
    "TestEnvironmentAgent",
    "TestSpecialistAgent",
    "ImportOptimizationAgent",
],
```

### 5.3 Modify Test Execution Hook

**File**: `crackerjack/managers/test_manager.py` (or equivalent)

**Enhance test execution to capture structured output**:

```python
def execute_tests(self, cmd: list[str]) -> HookResult:
    """Execute tests and capture structured failure data."""

    # Run pytest with JSON output for easier parsing
    json_cmd = cmd + ["--json-report", "--json-report-file=test_results.json"]

    result = subprocess.run(json_cmd, capture_output=True, text=True)

    # Parse JSON output if available
    if Path("test_results.json").exists():
        test_results = json.loads(Path("test_results.json").read_text())
        structured_failures = self._extract_failures_from_json(test_results)
    else:
        # Fallback to stdout parsing
        parser = TestResultParser()
        structured_failures = parser.parse_test_output(result.stdout + result.stderr)

    return HookResult(
        name="pytest",
        status="failed" if structured_failures else "passed",
        output=result.stdout,
        error=result.stderr,
        metadata={"test_failures": [f.model_dump() for f in structured_failures]},
    )
```

______________________________________________________________________

## Phase 6: Self-Healing (Crackerjack Fixing Itself)

### 6.1 Detecting Crackerjack's Own Test Failures

**File**: `crackerjack/core/autofix_coordinator.py`

**Add**: Self-detection and special handling

```python
def _parse_hook_results_to_issues(self, hook_results: Sequence[object]) -> list[Issue]:
    """Parse hook results into issues, with self-healing support."""

    # Detect if we're fixing crackerjack itself
    is_self_healing = self._is_self_healing_session()

    issues = []

    for result in hook_results:
        # ... existing parsing ...

        # NEW: Tag crackerjack's own test failures for special handling
        if is_self_healing and self._is_crackerjack_test_failure(result):
            for issue in hook_issues:
                issue.metadata["self_healing"] = True
                issue.metadata["priority"] = Priority.URGENT

    return issues


def _is_self_healing_session(self) -> bool:
    """Check if current session is crackerjack testing itself."""
    import os

    # Check if running in crackerjack's own test suite
    test_path = self.pkg_path / "tests"
    if not test_path.exists():
        return False

    # Check if pyproject.toml is crackerjack's
    pyproject = self.pkg_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        return 'name = "crackerjack"' in content

    return False
```

### 6.2 Self-Healing Safety Mechanisms

**File**: `crackerjack/agents/safe_code_modifier.py` (NEW)

**Purpose**: Extra safety when modifying crackerjack's own codebase

```python
class SafeCodeModifier:
    """Safe code modification for self-healing scenarios."""

    def __init__(self, context: AgentContext):
        self.context = context
        self.backup_service = BackupService()

    def apply_fix_safely(self, issue: Issue, fix: FixResult) -> FixResult:
        """Apply fix with extra safety checks for self-healing."""
        if not issue.metadata.get("self_healing"):
            # Normal fix application
            return self._apply_fix_directly(issue, fix)

        # Self-healing: extra precautions
        self.logger.warning("Self-healing mode: applying fix to crackerjack itself")

        # 1. Create backup before modifying
        self.backup_service.create_backup(issue.file_path)

        # 2. Validate fix doesn't break critical infrastructure
        if self._is_critical_file(issue.file_path):
            return self._handle_critical_file_fix(issue, fix)

        # 3. Apply fix with validation
        result = self._apply_fix_directly(issue, fix)

        # 4. Run smoke tests to verify basic functionality
        if result.success:
            smoke_test_passed = self._run_smoke_tests()
            if not smoke_test_passed:
                # Rollback
                self.backup_service.restore_backup(issue.file_path)
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=["Fix failed smoke tests, rolled back"],
                )

        return result

    def _is_critical_file(self, file_path: Path) -> bool:
        """Check if file is critical infrastructure."""
        critical_patterns = [
            "coordinator.py",
            "__main__.py",
            "autofix_coordinator.py",
            "agents/base.py",
        ]
        return any(pattern in str(file_path) for pattern in critical_patterns)

    def _run_smoke_tests(self) -> bool:
        """Run basic smoke tests to verify crackerjack still works."""
        import subprocess

        try:
            # Test basic import
            result = subprocess.run(
                ["python", "-c", "import crackerjack; print('OK')"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
```

______________________________________________________________________

## Phase 7: Testing & Validation

### 7.1 Test Result Parser Tests

**File**: `tests/parsers/test_test_result_parser.py` (NEW)

```python
import pytest
from crackerjack.parsers.test_result_parser import TestResultParser, TestFailureCategory


class TestTestResultParser:
    def test_parse_assertion_error(self):
        """Test parsing assertion errors from pytest output."""
        output = """
        tests/test_foo.py::TestClass::test_method FAILED
        assert x == y
        AssertionError: assert 1 == 2
        """

        parser = TestResultParser()
        failures = parser.parse_test_output(output)

        assert len(failures) == 1
        assert failures[0].test_id == "tests/test_foo.py::TestClass::test_method"
        assert failures[0].error_type == "AssertionError"
        assert failures[0].category == TestFailureCategory.PROJECT_CODE

    def test_parse_fixture_not_found(self):
        """Test parsing fixture not found errors."""
        output = """
        tests/test_bar.py::test_something FAILED
        fixture 'temp_pkg_path' not found
        """

        parser = TestResultParser()
        failures = parser.parse_test_output(output)

        assert len(failures) == 1
        assert failures[0].category == TestFailureCategory.TEST_FIXTURE

    def test_parse_import_error(self):
        """Test parsing import errors in tests."""
        output = """
        ERROR collecting tests/test_baz.py
        ImportError: No module named 'missing_module'
        """

        parser = TestResultParser()
        failures = parser.parse_test_output(output)

        assert len(failures) == 1
        assert failures[0].category == TestFailureCategory.IMPORT_ERROR
```

### 7.2 TestEnvironmentAgent Tests

**File**: `tests/agents/test_test_environment_agent.py` (NEW)

```python
import pytest
from crackerjack.agents.base import Issue, IssueType
from crackerjack.agents.test_environment_agent import TestEnvironmentAgent


class TestTestEnvironmentAgent:
    @pytest.fixture
    def agent(self, temp_dir):
        context = AgentContext(project_path=temp_dir)
        return TestEnvironmentAgent(context)

    def test_detects_missing_plugin(self, agent):
        """Test detection of missing pytest plugins."""
        issue = Issue(
            type=IssueType.TEST_ENVIRONMENT,
            message="error: unrecognized arguments: --cov",
            file_path="tests/test_foo.py",
        )

        confidence = await agent.can_handle(issue)
        assert confidence >= 0.95

    def test_installs_missing_plugin(self, agent, mock_subprocess):
        """Test installation of missing pytest plugin."""
        # Mock subprocess to avoid actual installation
        # ... test implementation ...

    def test_creates_missing_fixture(self, agent, temp_dir):
        """Test creation of missing fixtures."""
        # Create test file using non-existent fixture
        test_file = temp_dir / "tests" / "test_foo.py"
        test_file.write_text("""
        def test_something(temp_pkg_path):
            assert True
        """)

        issue = Issue(
            type=IssueType.TEST_ENVIRONMENT,
            message="fixture 'temp_pkg_path' not found",
            file_path=str(test_file),
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success
        assert "Created fixture: temp_pkg_path" in result.fixes_applied

        # Verify fixture was created in conftest.py
        conftest = temp_dir / "tests" / "conftest.py"
        assert conftest.exists()
        assert "temp_pkg_path" in conftest.read_text()
```

### 7.3 End-to-End Integration Tests

**File**: `tests/integration/test_ai_fix_test_failures.py` (NEW)

```python
import pytest
from crackerjack.core.autofix_coordinator import AutofixCoordinator


class TestAIFixTestFailures:
    def test_fixes_simple_assertion_error(self, test_project):
        """Test AI-fix can fix simple assertion errors in tests."""
        # Create failing test
        test_file = test_project / "tests" / "test_math.py"
        test_file.write_text("""
        def test_addition():
            result = 1 + 1
            assert result == 3  # Bug: should be 2
        """)

        # Create source file
        src_file = test_project / "math.py"
        src_file.write_text("""
        def add(a, b):
            return a + b
        """)

        # Run pytest
        result = subprocess.run(["pytest"], capture_output=True)

        # Apply AI-fix
        coordinator = AutofixCoordinator(pkg_path=test_project)
        hook_results = [create_pytest_hook_result(result)]
        success = coordinator.apply_comprehensive_stage_fixes(hook_results)

        assert success

        # Verify test now passes
        result = subprocess.run(["pytest"], capture_output=True)
        assert result.returncode == 0

    def test_fixes_missing_fixture(self, test_project):
        """Test AI-fix can create missing fixtures."""
        # Similar structure for fixture creation test
        pass

    def test_self_healing_crackerjack(self, crackerjack_repo):
        """Test AI-fix can fix crackerjack's own test failures."""
        # Skip in normal CI, only run in dedicated self-healing tests
        if not os.environ.get("CRACKERJACK_SELF_HEALING_TEST"):
            pytest.skip("Set CRACKERJACK_SELF_HEALING_TEST=1 to enable")

        # Introduce a test failure in crackerjack
        # Run AI-fix on itself
        # Verify it can fix the issue
        pass
```

______________________________________________________________________

## Phase 8: Configuration & Settings

### 8.1 Add Test AI-Fix Settings

**File**: `crackerjack/config/settings.py`

**Add to AISettings**:

```python
class AISettings(BaseSettings):
    # ... existing settings ...

    # Test failure AI-fix settings
    test_ai_fix_enabled: bool = True
    test_ai_fix_self_healing: bool = True  # Fix crackerjack's own tests
    test_ai_fix_max_iterations: int = 5
    test_ai_fix_confidence_threshold: float = 0.7
```

### 8.2 CLI Options

**File**: `crackerjack/cli/options.py`

**Add test AI-fix flags**:

```python
@click.option(
    "--ai-fix-tests",
    is_flag=True,
    help="Enable AI-fix for test failures (in addition to static analysis)",
)
@click.option(
    "--self-healing",
    is_flag=True,
    help="Allow AI-fix to modify crackerjack's own codebase when fixing its tests",
)
```

______________________________________________________________________

## Phase 9: Rollout Strategy

### Stage 1: Project Code Test Failures (Week 1-2)

1. Implement TestResultParser
1. Extend TestSpecialistAgent to fix project code bugs
1. Test on sample projects with known test failures
1. Measure fix rate (target: 60%+)

### Stage 2: Test Environment Issues (Week 3-4)

1. Implement TestEnvironmentAgent
1. Handle pytest config, fixtures, import errors
1. Test on projects with test infrastructure issues
1. Measure fix rate (target: 70%+)

### Stage 3: Self-Healing (Week 5-6)

1. Implement self-healing detection
1. Add safety mechanisms (SafeCodeModifier)
1. Test on crackerjack's own test suite
1. Gradual rollout with manual review gate

### Stage 4: Production Readiness (Week 7-8)

1. Comprehensive integration testing
1. Performance optimization
1. Documentation updates
1. User education (blog post, examples)

______________________________________________________________________

## Phase 10: Success Metrics

### Quantitative Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Test failure fix rate (project code) | 0% | 60%+ | Fix rate on sample failures |
| Test failure fix rate (test env) | 0% | 70%+ | Fix rate on env issues |
| Self-healing fix rate | 0% | 50%+ | Fix rate on crackerjack tests |
| False positive rate | N/A | \<10% | Incorrect fixes applied |
| Time to fix (avg) | Manual | \<2 min | Automated fix duration |

### Qualitative Metrics

1. **User Feedback**: "Test failures are automatically fixed" ✅
1. **Developer Experience**: "No more wrestling with test fixtures" ✅
1. **CI/CD Integration**: "AI-fix runs in CI, prevents blocking PRs" ✅
1. **Self-Healing**: "Crackerjack fixes its own bugs" ✅

______________________________________________________________________

## Risks & Mitigations

### Risk 1: Breaking Tests with Incorrect Fixes

**Mitigation**:

- Confidence threshold (only apply fixes with ≥0.7 confidence)
- Validation: Re-run tests after each fix
- Rollback: Revert fixes if tests fail again
- Manual review gate for critical code changes

### Risk 2: Self-Healing Loop (Infinite Fixes)

**Mitigation**:

- Max iteration limit (hard stop after 5 iterations)
- Convergence detection (stop if issue count doesn't decrease)
- Smoke test validation (verify basic functionality after fixes)
- Manual intervention trigger (if >3 failed fixes)

### Risk 3: Performance Impact (Slow Parsing)

**Mitigation**:

- Lazy parsing (only parse if AI-fix enabled)
- Parallel test result parsing (for large suites)
- Caching (reuse parsed results across iterations)
- Streaming parsing (don't load entire output into memory)

### Risk 4: False Positives (Fixing Non-Issues)

**Mitigation**:

- Conservative confidence thresholds
- Human-in-the-loop for critical files
- Fix validation (re-run tools/tests)
- Metrics tracking (detect high false positive rates)

______________________________________________________________________

## Dependencies & Prerequisites

### Track 1: Test Failure Components

1. ✅ **TestSpecialistAgent** - Already exists, needs enhancement
1. ✅ **TestCreationAgent** - Already exists, needs enhancement
1. ❌ **TestResultParser** - NEW (Phase 2)
1. ❌ **TestEnvironmentAgent** - NEW (Phase 3)
1. ❌ **IssueType.TEST_ENVIRONMENT** - NEW (Phase 5)
1. ❌ **SafeCodeModifier** - NEW (Phase 6)

### Track 2: Dead Code Components

1. ✅ **Vulture** - Already exists, needs activation in hooks
1. ✅ **Skylos** - Already active in comprehensive hooks
1. ✅ **deadcode** - Already installed, needs adapter integration
1. ❌ **DeadCodeRemovalAgent** - NEW (Phase 2B)
1. ❌ **DeadcodeAdapter** - NEW (Phase 2C, optional)

### External Dependencies

1. **pytest-json-report** - For structured test output parsing (Track 1)

   ```bash
   uv add --dev pytest-json-report
   ```

1. **Existing patterns** - Already have pytest/error_patterns.py (Track 1)

1. **Vulture** - Already in dependencies, just needs configuration (Track 2)

1. **deadcode** - Already in dependencies, needs adapter wrapper (Track 2, optional)

______________________________________________________________________

## Implementation Timeline (Parallel Tracks)

**Strategy**: Two independent tracks running simultaneously for maximum efficiency

### Track 1: Test Failure AI-Fix (8 weeks)

| Week | Phase | Deliverables | Track 2 Parallel Work |
|------|-------|--------------|----------------------|
| 1 | Planning & Design | Plan document, architecture review | Vulture integration |
| 2 | Phase 2 | TestResultParser implementation | DeadCodeRemovalAgent |
| 3 | Phase 3 | TestEnvironmentAgent implementation | Agent routing updates |
| 4 | Phase 4 | TestSpecialistAgent enhancements | Integration testing |
| 5 | Phase 5 | Integration (test → Issue conversion) | Safety validation |
| 6 | Phase 6 | Self-healing implementation | Performance testing |
| 7 | Phase 7 | Comprehensive testing + validation | Documentation |
| 8 | Phase 8 | Documentation + rollout | Final validation |

**Track 1 Total**: 8 weeks

### Track 2: Dead Code Detection (4 weeks)

| Week | Phase | Deliverables | Track 1 Parallel Work |
|------|-------|--------------|----------------------|
| 1 | Phase 2A | Vulture integration to fast hooks | Planning & Design |
| 2 | Phase 2B | DeadCodeRemovalAgent implementation | TestResultParser |
| 3 | Phase 2D | Agent routing + coordination updates | TestEnvironmentAgent |
| 4 | Validation | End-to-end testing, documentation | TestSpecialistAgent |

**Track 2 Total**: 4 weeks (finishes earlier, quick wins)

### Combined Weekly Breakdown

```
Week 1: Foundation
  ├─ Track 1: Architecture design, plan review
  └─ Track 2: Add Vulture to fast hooks (6.1s added)

Week 2: Core Components
  ├─ Track 1: TestResultParser (parse pytest → Issues)
  └─ Track 2: DeadCodeRemovalAgent (safe removal logic)

Week 3: Specialized Agents
  ├─ Track 1: TestEnvironmentAgent (pytest/config/imports)
  └─ Track 2: Agent routing updates (DEAD_CODE type)

Week 4: Integration & Testing
  ├─ Track 1: TestSpecialistAgent enhancements
  └─ Track 2: End-to-end dead code workflow testing

Week 5: Cross-Track Integration
  ├─ Track 1: Hook result → Issue conversion (tests)
  └─ Track 2: ✅ COMPLETE, validation & documentation

Week 6-8: Track 1 Continuation
  └─ Self-healing, testing, documentation, rollout

Benefits of Parallel Approach:
  ✅ Track 2 delivers value in 4 weeks (quick wins)
  ✅ Both tracks use same AI-fix infrastructure
  ✅ Lessons from Track 2 inform Track 1 implementation
  ✅ Reduced total time (8 weeks vs. 12 weeks sequential)
```

### Resource Allocation

**Recommended Team Structure**:

- **Developer A**: Focus on Track 1 (test failures)
- **Developer B**: Focus on Track 2 (dead code) for weeks 1-4, then join Track 1
- **QA Engineer**: Parallel testing for both tracks
- **Architecture Review**: Combined review sessions

**Total Duration**: 8 weeks (Track 2 finishes in week 4)

______________________________________________________________________

## Open Questions

1. **Scope of self-healing**: Should crackerjack fix ALL its own test failures, or only safe ones?

   - **Recommendation**: Start with 50% (conservative), expand based on success rate

1. **Test isolation**: Should AI-fix run tests in isolation or full suite?

   - **Recommendation**: Run only failing tests first, then full suite for validation

1. **Fix verification**: How to verify fixes don't break other tests?

   - **Recommendation**: Always run full test suite after applying fixes

1. **Confidence thresholds**: Should test failures have different thresholds than static analysis?

   - **Recommendation**: Yes, test failures need higher confidence (0.8 vs 0.7) due to complexity

______________________________________________________________________

## Next Steps

### Immediate Actions (Week 1)

**Both Tracks Start in Parallel**:

1. **Review and approve this plan** with architecture team
1. **Create two GitHub projects** (one for each track):
   - `project/track-1-test-failures`
   - `project/track-2-dead-code`
1. **Set up feature branches**:
   - `feature/ai-fix-test-failures` (Track 1)
   - `feature/ai-fix-dead-code` (Track 2)
1. **Week 1 Kickoff** (both tracks):
   - **Track 1**: Architecture design, review existing patterns
   - **Track 2**: Activate Vulture in fast hooks, measure baseline

### Track 2 Quick Wins (Weeks 1-4)

**Why start with Track 2?**

- ✅ Faster to implement (4 weeks vs 8 weeks)
- ✅ Higher confidence (90%+ from Vulture)
- ✅ Lower risk (dead code removal vs. test fixing)
- ✅ Immediate value (clean up 22 issues in crackerjack)

**Track 2 First Week Deliverables**:

- Vulture integrated into fast hooks
- Baseline measurement: ~22 issues expected
- DeadCodeRemovalAgent skeleton with safety checks
- Agent routing updated for DEAD_CODE type

### Track 1 Foundation (Weeks 1-2)

**Parallel with Track 2**:

- TestResultParser design and implementation
- Extend pytest error patterns (already have good foundation)
- TestEnvironmentAgent architecture
- Both tracks inform AI-fix infrastructure improvements

### Weekly Sync Structure

**Combined Standup** (30 minutes, Mondays):

- Track 1 progress: Test failure parsing, agent development
- Track 2 progress: Dead code removal, safety validation
- Cross-track issues: Shared infrastructure, AI-fix coordination
- Blockers and dependencies

**Separate Deep Dives** (Track-specific, Wednesdays):

- Track 1 Deep Dive: Test parsing, environment diagnostics (1 hour)
- Track 2 Deep Dive: Safety mechanisms, confidence thresholds (1 hour)

### Success Criteria

**Track 1 Success** (8 weeks):

- ✅ Test failures automatically detected and converted to Issues
- ✅ TestEnvironmentAgent handles 70%+ of environment issues
- ✅ Self-healing fixes 50%+ of crackerjack's own test failures
- ✅ Zero test breakages from incorrect AI-fixes

**Track 2 Success** (4 weeks):

- ✅ Vulture active in fast hooks (6.1s added to runtime)
- ✅ 22 dead code issues safely removed (100% of high-confidence)
- ✅ DeadCodeRemovalAgent with 5 safety checks operational
- ✅ \<5% false positive rate on dead code removal

### Risk Mitigation for Parallel Development

**Risk**: Track 2 influences Track 1 decisions
**Mitigation**:

- Weekly architecture reviews ensure consistency
- Track 2 finishes early, lessons inform Track 1
- Shared AI-fix infrastructure tested by both tracks

**Risk**: Resource contention (2 developers, 1 QA)
**Mitigation**:

- Clear track ownership minimizes conflicts
- Track 2 finishes in week 4, freeing Developer B
- Combined reviews maximize knowledge sharing

______________________________________________________________________

**Document Status**: Ready for review with parallel implementation approach
**Last Updated**: 2026-02-05
**Author**: AI Agent (Claude Sonnet 4.5)
**Reviewers**: Architecture Team, QA Team
**Tracks**: 2 parallel implementation tracks
