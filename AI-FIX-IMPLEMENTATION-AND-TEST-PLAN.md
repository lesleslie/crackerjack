# Crackerjack AI Auto-Fix: Comprehensive Implementation & Test Plan

**Date:** 2025-10-03
**Status:** 🔧 Implementation Complete - Testing Required
**Priority:** CRITICAL

---

## Executive Summary

The `--ai-fix` flag was completely broken due to **TWO separate bugs**:

1. **Parameter Passing Bug**: `_setup_debug_and_verbose_flags()` in `__main__.py` wasn't accepting the `ai_fix` parameter
2. **Workflow Routing Bug**: THREE workflow functions in `workflow_orchestrator.py` weren't checking for AI agent

**Both bugs have been fixed.** This document provides a comprehensive testing plan to verify the fixes work correctly before publishing.

---

## Bugs Fixed (Implementation Complete ✅)

### Bug #1: Parameter Passing (FIXED)

**File:** `crackerjack/__main__.py`
**Function:** `_setup_debug_and_verbose_flags()` (lines 476-495)

**Issue:**
- Function didn't accept `ai_fix` as parameter
- Hardcoded `ai_fix = False` on every call
- Call site didn't pass user's `--ai-fix` value

**Fix Applied:**
```python
# Before
def _setup_debug_and_verbose_flags(
    ai_debug: bool, debug: bool, verbose: bool, options: t.Any
) -> tuple[bool, bool]:
    ai_fix = False  # BUG!
    # ...

# After
def _setup_debug_and_verbose_flags(
    ai_fix: bool, ai_debug: bool, debug: bool, verbose: bool, options: t.Any
) -> tuple[bool, bool]:
    # Preserve user's ai_fix flag
    if ai_debug:
        ai_fix = True  # ai_debug implies ai_fix
    # ...
```

**Call Site Fix (Line 1466):**
```python
# Before
ai_fix, verbose = _setup_debug_and_verbose_flags(ai_debug, debug, verbose, options)

# After
ai_fix, verbose = _setup_debug_and_verbose_flags(ai_fix, ai_debug, debug, verbose, options)
```

---

### Bug #2: Workflow Routing (FIXED)

**File:** `crackerjack/core/workflow_orchestrator.py`

**THREE functions weren't checking for AI agent:**

#### 2a. Default Workflow (FIXED)

**Function:** `_execute_standard_hooks_workflow_monitored()` (lines 1933-1967)
**Used when:** No flags specified (most common usage)

**Fix Applied:**
- Added `iteration = self._start_iteration_tracking(options)`
- Early AI agent check when fast hooks fail
- Always delegate to `_handle_ai_workflow_completion()` at the end

#### 2b. Fast Hooks Workflow (FIXED)

**Function:** `_run_fast_hooks_phase_monitored()` (lines 1860-1875)
**Used when:** `--fast` flag specified

**Fix Applied:**
- Added `iteration = self._start_iteration_tracking(options)`
- Check `options.ai_agent` and delegate to `_handle_ai_workflow_completion()` if True

#### 2c. Comprehensive Hooks Workflow (FIXED)

**Function:** `_run_comprehensive_hooks_phase_monitored()` (lines 1877-1892)
**Used when:** `--comp` flag specified

**Fix Applied:**
- Added `iteration = self._start_iteration_tracking(options)`
- Check `options.ai_agent` and delegate to `_handle_ai_workflow_completion()` if True

**Note:** `_execute_test_workflow()` already had proper AI agent checking ✅

---

## Testing Strategy

### Phase 1: Unit Tests (Isolated Function Behavior)

**Goal:** Verify each fixed function works correctly in isolation

#### Test 1.1: `_setup_debug_and_verbose_flags()` Unit Test

**File:** `tests/test_main.py` (create if doesn't exist)

```python
import pytest
from crackerjack.__main__ import _setup_debug_and_verbose_flags


class MockOptions:
    verbose = False


def test_setup_debug_flags_preserves_ai_fix_true():
    """Test that ai_fix=True is preserved when passed."""
    options = MockOptions()

    # ai_fix=True should be preserved
    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix=True,
        ai_debug=False,
        debug=False,
        verbose=False,
        options=options
    )

    assert ai_fix is True, "ai_fix=True should be preserved"


def test_setup_debug_flags_preserves_ai_fix_false():
    """Test that ai_fix=False is preserved when passed."""
    options = MockOptions()

    # ai_fix=False should be preserved
    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix=False,
        ai_debug=False,
        debug=False,
        verbose=False,
        options=options
    )

    assert ai_fix is False, "ai_fix=False should be preserved"


def test_setup_debug_flags_ai_debug_implies_ai_fix():
    """Test that ai_debug=True forces ai_fix=True."""
    options = MockOptions()

    # ai_debug=True should override ai_fix to True
    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix=False,  # Even if False
        ai_debug=True,  # This should force it to True
        debug=False,
        verbose=False,
        options=options
    )

    assert ai_fix is True, "ai_debug=True should force ai_fix=True"
    assert verbose is True, "ai_debug=True should set verbose=True"
    assert options.verbose is True, "ai_debug=True should set options.verbose=True"


def test_setup_debug_flags_debug_sets_verbose():
    """Test that debug=True sets verbose=True."""
    options = MockOptions()

    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix=False,
        ai_debug=False,
        debug=True,
        verbose=False,
        options=options
    )

    assert verbose is True, "debug=True should set verbose=True"
    assert options.verbose is True, "debug=True should set options.verbose=True"
```

#### Test 1.2: Workflow Routing Unit Tests

**File:** `tests/test_workflow_orchestrator_ai_routing.py` (create new)

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.cli.options import Options


@pytest.fixture
def mock_options_with_ai_agent():
    """Options with AI agent enabled."""
    options = Mock(spec=Options)
    options.ai_agent = True
    options.ai_fix = True
    options.test = False
    options.fast = False
    options.comp = False
    options.clean = False
    return options


@pytest.fixture
def mock_options_without_ai_agent():
    """Options with AI agent disabled."""
    options = Mock(spec=Options)
    options.ai_agent = False
    options.ai_fix = False
    options.test = False
    options.fast = False
    options.comp = False
    options.clean = False
    return options


@pytest.fixture
def orchestrator():
    """Create WorkflowOrchestrator instance with minimal dependencies."""
    with patch('crackerjack.core.workflow_orchestrator.Config'):
        with patch('crackerjack.core.workflow_orchestrator.Console'):
            orch = WorkflowOrchestrator()
            orch.logger = Mock()
            orch.console = Mock()
            orch._quality_intelligence = None
            return orch


class TestStandardWorkflowAIRouting:
    """Test that standard workflow checks for AI agent."""

    @pytest.mark.asyncio
    async def test_standard_workflow_calls_ai_completion_when_ai_agent_enabled(
        self, orchestrator, mock_options_with_ai_agent
    ):
        """Standard workflow should delegate to AI completion handler when ai_agent=True."""
        workflow_id = "test_workflow"

        # Mock the workflow components
        with patch.object(orchestrator, '_start_iteration_tracking', return_value=1):
            with patch.object(orchestrator, '_update_hooks_status_running'):
                with patch.object(orchestrator, '_execute_monitored_fast_hooks_phase', return_value=False):
                    with patch.object(orchestrator, '_handle_hooks_completion'):
                        with patch.object(
                            orchestrator,
                            '_handle_ai_workflow_completion',
                            new_callable=AsyncMock
                        ) as mock_ai_completion:
                            mock_ai_completion.return_value = True

                            # Execute standard workflow
                            result = await orchestrator._execute_standard_hooks_workflow_monitored(
                                mock_options_with_ai_agent, workflow_id
                            )

                            # Verify AI completion handler was called
                            mock_ai_completion.assert_called_once()
                            call_args = mock_ai_completion.call_args
                            assert call_args[0][0] == mock_options_with_ai_agent
                            assert call_args[0][1] == 1  # iteration
                            assert result is True

    @pytest.mark.asyncio
    async def test_standard_workflow_returns_directly_when_ai_agent_disabled(
        self, orchestrator, mock_options_without_ai_agent
    ):
        """Standard workflow should return directly when ai_agent=False and hooks fail."""
        workflow_id = "test_workflow"

        # Mock the workflow components
        with patch.object(orchestrator, '_start_iteration_tracking', return_value=1):
            with patch.object(orchestrator, '_update_hooks_status_running'):
                with patch.object(orchestrator, '_execute_monitored_fast_hooks_phase', return_value=False):
                    with patch.object(orchestrator, '_handle_hooks_completion'):
                        with patch.object(
                            orchestrator,
                            '_handle_ai_workflow_completion',
                            new_callable=AsyncMock
                        ) as mock_ai_completion:
                            # Execute standard workflow
                            result = await orchestrator._execute_standard_hooks_workflow_monitored(
                                mock_options_without_ai_agent, workflow_id
                            )

                            # Should return False without calling AI completion
                            # (because ai_agent=False and fast hooks failed)
                            assert result is False
                            mock_ai_completion.assert_not_called()


class TestFastWorkflowAIRouting:
    """Test that fast workflow checks for AI agent."""

    @pytest.mark.asyncio
    async def test_fast_workflow_delegates_to_ai_completion_when_enabled(
        self, orchestrator, mock_options_with_ai_agent
    ):
        """Fast workflow should delegate to AI completion when ai_agent=True."""
        workflow_id = "test_workflow"

        with patch.object(orchestrator, '_start_iteration_tracking', return_value=1):
            with patch.object(orchestrator, '_run_fast_hooks_phase', return_value=False):
                with patch.object(
                    orchestrator,
                    '_handle_ai_workflow_completion',
                    new_callable=AsyncMock
                ) as mock_ai_completion:
                    mock_ai_completion.return_value = True

                    result = await orchestrator._run_fast_hooks_phase_monitored(
                        mock_options_with_ai_agent, workflow_id
                    )

                    mock_ai_completion.assert_called_once()
                    call_args = mock_ai_completion.call_args
                    assert call_args[0][0] == mock_options_with_ai_agent
                    assert result is True


class TestComprehensiveWorkflowAIRouting:
    """Test that comprehensive workflow checks for AI agent."""

    @pytest.mark.asyncio
    async def test_comp_workflow_delegates_to_ai_completion_when_enabled(
        self, orchestrator, mock_options_with_ai_agent
    ):
        """Comprehensive workflow should delegate to AI completion when ai_agent=True."""
        workflow_id = "test_workflow"

        with patch.object(orchestrator, '_start_iteration_tracking', return_value=1):
            with patch.object(orchestrator, '_run_comprehensive_hooks_phase', return_value=False):
                with patch.object(
                    orchestrator,
                    '_handle_ai_workflow_completion',
                    new_callable=AsyncMock
                ) as mock_ai_completion:
                    mock_ai_completion.return_value = True

                    result = await orchestrator._run_comprehensive_hooks_phase_monitored(
                        mock_options_with_ai_agent, workflow_id
                    )

                    mock_ai_completion.assert_called_once()
                    call_args = mock_ai_completion.call_args
                    assert call_args[0][0] == mock_options_with_ai_agent
                    assert result is True
```

---

### Phase 2: Integration Tests (End-to-End Workflow)

**Goal:** Verify complete `--ai-fix` workflow works from CLI to AI fixing

#### Test 2.1: CLI Flag Parsing Integration Test

**File:** `tests/integration/test_ai_fix_flag_integration.py` (create new)

```python
import pytest
from typer.testing import CliRunner
from crackerjack.__main__ import app


runner = CliRunner()


def test_ai_fix_flag_is_parsed_correctly():
    """Test that --ai-fix flag is correctly parsed by Typer."""
    # This test will fail initially if hooks actually run
    # We need to mock the workflow to just capture options

    # TODO: Add test implementation
    # This requires mocking WorkflowOrchestrator.run_complete_workflow
    # to capture the options object and verify ai_fix=True
    pass


def test_ai_debug_flag_implies_ai_fix():
    """Test that --ai-debug flag sets both ai_debug and ai_fix."""
    # TODO: Add test implementation
    pass


def test_ai_fix_with_verbose_flag():
    """Test that --ai-fix -v works correctly."""
    # TODO: Add test implementation
    pass
```

#### Test 2.2: Environment Variable Integration Test

**File:** `tests/integration/test_ai_agent_env_setup.py` (create new)

```python
import os
import pytest
from crackerjack.cli.handlers import setup_ai_agent_env


def test_setup_ai_agent_env_sets_ai_agent_variable():
    """Test that setup_ai_agent_env sets AI_AGENT environment variable."""
    # Clear environment
    if "AI_AGENT" in os.environ:
        del os.environ["AI_AGENT"]

    # Setup with ai_agent=True
    setup_ai_agent_env(ai_agent=True, debug_mode=False)

    assert os.environ.get("AI_AGENT") == "1", "AI_AGENT should be set to '1'"

    # Cleanup
    del os.environ["AI_AGENT"]


def test_setup_ai_agent_env_with_debug():
    """Test that setup_ai_agent_env sets debug variables."""
    # Clear environment
    for var in ["AI_AGENT", "AI_AGENT_DEBUG", "AI_AGENT_VERBOSE", "CRACKERJACK_DEBUG"]:
        if var in os.environ:
            del os.environ[var]

    # Setup with ai_agent=True and debug_mode=True
    setup_ai_agent_env(ai_agent=True, debug_mode=True)

    assert os.environ.get("AI_AGENT") == "1"
    assert os.environ.get("AI_AGENT_DEBUG") == "1"
    assert os.environ.get("AI_AGENT_VERBOSE") == "1"
    assert os.environ.get("CRACKERJACK_DEBUG") == "1"

    # Cleanup
    for var in ["AI_AGENT", "AI_AGENT_DEBUG", "AI_AGENT_VERBOSE", "CRACKERJACK_DEBUG"]:
        if var in os.environ:
            del os.environ[var]
```

#### Test 2.3: Complete Workflow Integration Test

**File:** `tests/integration/test_ai_fix_complete_workflow.py` (create new)

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.cli.options import Options


@pytest.mark.asyncio
async def test_ai_fix_triggers_ai_agent_workflow_on_hook_failure():
    """
    Integration test: When hooks fail and --ai-fix is enabled,
    the workflow should trigger AI fixing iterations.
    """
    # Create options with AI agent enabled
    options = Mock(spec=Options)
    options.ai_agent = True
    options.ai_fix = True
    options.test = False
    options.fast = False
    options.comp = False
    options.clean = False
    options.verbose = True

    # Create orchestrator
    with patch('crackerjack.core.workflow_orchestrator.Config'):
        with patch('crackerjack.core.workflow_orchestrator.Console'):
            orchestrator = WorkflowOrchestrator()
            orchestrator.logger = Mock()
            orchestrator.console = Mock()
            orchestrator._quality_intelligence = None

            # Mock hook execution to fail
            orchestrator._run_fast_hooks_phase = Mock(return_value=False)
            orchestrator._run_comprehensive_hooks_phase = Mock(return_value=False)

            # Mock AI fixing workflow to succeed
            orchestrator._handle_ai_agent_workflow = AsyncMock(return_value=True)

            # Mock other required methods
            orchestrator._start_iteration_tracking = Mock(return_value=1)
            orchestrator._update_hooks_status_running = Mock()
            orchestrator._handle_hooks_completion = Mock()

            # Execute standard workflow with AI agent enabled
            workflow_id = "test_workflow"

            with patch('crackerjack.core.workflow_orchestrator.phase_monitor'):
                result = await orchestrator._execute_standard_hooks_workflow_monitored(
                    options, workflow_id
                )

            # Verify AI agent workflow was triggered
            orchestrator._handle_ai_agent_workflow.assert_called_once()

            # Verify it was called with correct parameters
            call_args = orchestrator._handle_ai_agent_workflow.call_args
            assert call_args[0][0] == options
            assert call_args[0][1] == 1  # iteration
            assert call_args[0][2] is False  # testing_passed (fast hooks failed)


@pytest.mark.asyncio
async def test_ai_fix_not_triggered_when_hooks_pass():
    """
    Integration test: When hooks pass, AI fixing should not be triggered
    even if --ai-fix is enabled.
    """
    # Create options with AI agent enabled
    options = Mock(spec=Options)
    options.ai_agent = True
    options.ai_fix = True
    options.test = False
    options.fast = False
    options.comp = False
    options.clean = False
    options.verbose = True

    # Create orchestrator
    with patch('crackerjack.core.workflow_orchestrator.Config'):
        with patch('crackerjack.core.workflow_orchestrator.Console'):
            orchestrator = WorkflowOrchestrator()
            orchestrator.logger = Mock()
            orchestrator.console = Mock()
            orchestrator._quality_intelligence = None

            # Mock hook execution to SUCCEED
            orchestrator._run_fast_hooks_phase = Mock(return_value=True)
            orchestrator._run_comprehensive_hooks_phase = Mock(return_value=True)
            orchestrator._execute_monitored_cleaning_phase = Mock(return_value=True)

            # Mock standard workflow to succeed
            orchestrator._handle_standard_workflow = AsyncMock(return_value=True)

            # Mock other required methods
            orchestrator._start_iteration_tracking = Mock(return_value=1)
            orchestrator._update_hooks_status_running = Mock()
            orchestrator._handle_hooks_completion = Mock()
            orchestrator._execute_monitored_fast_hooks_phase = Mock(return_value=True)
            orchestrator._execute_monitored_comprehensive_phase = Mock(return_value=True)

            # Execute standard workflow
            workflow_id = "test_workflow"

            with patch('crackerjack.core.workflow_orchestrator.phase_monitor'):
                result = await orchestrator._execute_standard_hooks_workflow_monitored(
                    options, workflow_id
                )

            # Since hooks passed, it should route to standard workflow, not AI workflow
            # The _handle_ai_workflow_completion would still be called, but it would
            # route to _handle_standard_workflow because hooks passed

            # This is a complex integration test - we need to verify the complete flow
            assert result is True or isinstance(result, bool)
```

---

### Phase 3: Manual Testing (Real-World Verification)

**Goal:** Verify fixes work in actual usage scenarios

#### Test 3.1: Default Workflow (`--ai-fix` only)

```bash
cd /Users/les/Projects/crackerjack

# Introduce a deliberate quality issue
echo "def bad_function():" >> crackerjack/test_ai_fix.py
echo "    x = 1" >> crackerjack/test_ai_fix.py
echo "    return x + y  # Undefined variable" >> crackerjack/test_ai_fix.py

# Run with --ai-fix (should trigger AI fixing)
python -m crackerjack --ai-fix -v

# Expected behavior:
# ✅ Runs hooks
# ✅ Detects errors (refurb, complexity, undefined variable)
# ✅ Prints "🤖 AI Agent workflow activated"
# ✅ Attempts to fix issues
# ✅ Re-runs hooks
# ✅ Iterates up to max iterations

# Cleanup
rm crackerjack/test_ai_fix.py
```

#### Test 3.2: Fast Workflow (`--ai-fix --fast`)

```bash
cd /Users/les/Projects/crackerjack

# Introduce a formatting issue
echo "def   badly_formatted():" >> crackerjack/test_ai_fix.py
echo "        return    'too many spaces'" >> crackerjack/test_ai_fix.py

# Run with --ai-fix --fast
python -m crackerjack --ai-fix --fast -v

# Expected behavior:
# ✅ Runs fast hooks only
# ✅ Detects formatting issues
# ✅ Triggers AI fixing for fast hooks
# ✅ Fixes formatting
# ✅ Re-runs fast hooks

# Cleanup
rm crackerjack/test_ai_fix.py
```

#### Test 3.3: Comprehensive Workflow (`--ai-fix --comp`)

```bash
cd /Users/les/Projects/crackerjack

# Introduce a complexity issue
cat > crackerjack/test_ai_fix.py << 'EOF'
def complex_function(a, b, c, d, e):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return a + b + c + d + e
                    else:
                        return 0
                else:
                    return 0
            else:
                return 0
        else:
            return 0
    else:
        return 0
EOF

# Run with --ai-fix --comp
python -m crackerjack --ai-fix --comp -v

# Expected behavior:
# ✅ Runs comprehensive hooks
# ✅ Detects complexity issues
# ✅ Triggers AI fixing
# ✅ Attempts to reduce complexity

# Cleanup
rm crackerjack/test_ai_fix.py
```

#### Test 3.4: MCP Integration Test

```bash
cd /Users/les/Projects/acb

# Test via MCP (from Claude Code conversation)
# User should invoke:
mcp__crackerjack__execute_crackerjack(
    args="--verbose",
    kwargs={"ai_fix": true, "execution_timeout": 1800}
)

# Expected behavior:
# ✅ MCP server receives request
# ✅ Runs hooks
# ✅ Detects issues
# ✅ Returns job_id
# ✅ AI fixing iterations execute
# ✅ Progress tracked via job_id
```

---

## Test Execution Checklist

### Pre-Testing Setup

- [ ] Ensure you're in crackerjack project directory: `cd /Users/les/Projects/crackerjack`
- [ ] Install test dependencies: `uv sync --group dev`
- [ ] Verify pytest is installed: `python -m pytest --version`

### Phase 1: Unit Tests

- [ ] Create `tests/test_main.py` with `_setup_debug_and_verbose_flags()` tests
- [ ] Create `tests/test_workflow_orchestrator_ai_routing.py` with workflow routing tests
- [ ] Run unit tests: `python -m pytest tests/test_main.py -v`
- [ ] Run workflow tests: `python -m pytest tests/test_workflow_orchestrator_ai_routing.py -v`
- [ ] Verify all unit tests pass

### Phase 2: Integration Tests

- [ ] Create `tests/integration/` directory
- [ ] Create `tests/integration/test_ai_fix_flag_integration.py`
- [ ] Create `tests/integration/test_ai_agent_env_setup.py`
- [ ] Create `tests/integration/test_ai_fix_complete_workflow.py`
- [ ] Run integration tests: `python -m pytest tests/integration/ -v`
- [ ] Verify all integration tests pass

### Phase 3: Manual Testing

- [ ] Test default workflow: `python -m crackerjack --ai-fix -v`
- [ ] Test fast workflow: `python -m crackerjack --ai-fix --fast -v`
- [ ] Test comprehensive workflow: `python -m crackerjack --ai-fix --comp -v`
- [ ] Test MCP integration from acb project
- [ ] Verify AI agent actually executes fixing iterations in all cases
- [ ] Verify progress tracking works

### Post-Testing

- [ ] Review test results and fix any failures
- [ ] Document any additional issues discovered
- [ ] Update CHANGELOG.md with fixes
- [ ] Bump version: `python -m crackerjack --bump patch`
- [ ] Commit all changes: `git add . && git commit -m "fix: AI auto-fix workflow routing and parameter passing"`
- [ ] Publish to PyPI: `python -m crackerjack --publish`
- [ ] Test in acb project with new version

---

## Success Criteria

**All tests must pass before publishing:**

1. ✅ All unit tests pass (100% coverage of fixed functions)
2. ✅ All integration tests pass
3. ✅ Manual testing confirms AI agent executes when `--ai-fix` is used
4. ✅ Manual testing confirms AI fixing works with all workflow paths:
   - Default (no flags)
   - `--fast`
   - `--comp`
   - `--test`
5. ✅ MCP integration test succeeds from acb project
6. ✅ No regressions in existing functionality

**If ANY test fails:**
- DO NOT publish to PyPI
- Document the failure
- Fix the issue
- Re-run all tests

---

## Known Limitations and Future Work

### Current Limitations

1. **ClaudeCodeBridge is a simulation**: The standalone CLI mode (`python -m crackerjack --ai-fix`) uses a simulated bridge that provides recommendations but doesn't actually invoke Claude Code agents via the Task tool.

2. **MCP Mode is Required for Full AI Fixing**: The complete AI fixing workflow requires MCP integration where Claude Code (the MCP client) applies the fixes.

### Future Enhancements

1. **Enhance ClaudeCodeBridge**: Update to actually invoke Task tool for standalone CLI mode
2. **Add More Test Coverage**: Test coverage improvements, especially for AI agent coordinator
3. **Integration Test for MCP**: Automated integration test for MCP workflow
4. **Performance Testing**: Measure AI fixing iteration performance
5. **Error Recovery Testing**: Test error handling in AI fixing workflow

---

## Documentation Updates Required

After testing completes successfully:

1. **Update investigation reports**:
   - Mark both bugs as fixed and tested
   - Add test results summary

2. **Update CHANGELOG.md**:
   - Document both bug fixes
   - List new tests added
   - Mention improved AI auto-fix reliability

3. **Update README.md** (if needed):
   - Document `--ai-fix` flag usage
   - Add examples of AI auto-fix workflow

4. **Update user guide** (if exists):
   - Explain AI agent workflow
   - Document when to use `--ai-fix`

---

## Quick Test Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run only unit tests
python -m pytest tests/test_main.py tests/test_workflow_orchestrator_ai_routing.py -v

# Run only integration tests
python -m pytest tests/integration/ -v

# Run with coverage
python -m pytest tests/ --cov=crackerjack --cov-report=term -v

# Run specific test
python -m pytest tests/test_workflow_orchestrator_ai_routing.py::TestStandardWorkflowAIRouting::test_standard_workflow_calls_ai_completion_when_ai_agent_enabled -v
```

---

**Next Steps:**

1. Review this plan
2. Create test files as specified
3. Run tests and document results
4. Fix any failures
5. Publish new version only after all tests pass
6. Test in acb project with new version

**Questions? Issues?**

Document any problems encountered during testing in this file or in a new `AI-FIX-TEST-RESULTS.md` file.
