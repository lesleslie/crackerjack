# V2 Multi-Agent Quality System - Implementation Plan

> **For Claude:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build 4-layer architecture to prevent AI agents from generating broken code

**Architecture:** Layer 1 (Read-First) → Layer 2 (Analysis Pipeline) → Layer 3 (Validation Loop) → Layer 4 (Fallback)

**Tech Stack:** Python 3.13+, asyncio, ast, rich console, existing agent framework

______________________________________________________________________

## Task Breakdown

### Phase 1: Layer 1 - Read-First Foundation (3-4 hours)

#### Task 1.1: Create File Context Infrastructure

**Files:**

- Create: `crackerjack/agents/file_context.py`
- Modify: `crackerjack/agents/proactive_agent.py` (base class)
- Test: `tests/agents/test_file_context.py`

**Implementation:**

```python
# crackerjack/agents/file_context.py
from pathlib import Path
from typing import Dict
import asyncio
import logging

logger = logging.getLogger(__name__)

class FileContextReader:
    """Thread-safe file context reader with caching for AI agents."""

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def read_file(self, file_path: str | Path) -> str:
        """Read file with caching. Thread-safe."""
        async with self._lock:
            cache_key = str(Path(file_path).absolute())
            if cache_key in self._cache:
                return self._cache[cache_key]
            content = await asyncio.to_thread(Path.read_text, Path(file_path), encoding="utf-8")
            self._cache[cache_key] = content
            return content
```

**Steps:**

1. Create FileContextReader class
1. Add \_read_file_context() to ProactiveAgent base class
1. Make it MANDATORY before \_generate_fix()
1. Add comprehensive tests
1. Commit: "feat: add file context reading infrastructure"

______________________________________________________________________

#### Task 1.2: Enforce Edit Tool Usage

**Files:**

- Modify: `crackerjack/agents/proactive_agent.py`
- Test: `tests/agents/test_edit_tool_enforcement.py`

**Implementation:**

```python
# In ProactiveAgent._apply_fix_with_edit():
from crackerjack.agents.file_context import FileContextReader

async def _apply_fix_with_edit(
    self,
    file_path: str,
    old_code: str,
    new_code: str
) -> bool:
    """Apply fix using Edit tool (syntax-validating)."""
    # Read file first
    reader = FileContextReader()
    await reader.read_file(file_path)

    # Validate diff size
    MAX_DIFF_LINES = 50
    old_lines = old_code.split('\n')
    new_lines = new_code.split('\n')

    if len(old_lines) > MAX_DIFF_LINES or len(new_lines) > MAX_DIFF_LINES:
        logger.warning(f"Diff too large: {len(old_lines)} → {len(new_lines)} lines")
        return False

    # Use Edit tool (placeholder - integrate with actual Edit tool)
    # For now, direct file write
    Path(file_path).write_text(new_code)
    return True
```

**Steps:**

1. Add \_apply_fix_with_edit() method to ProactiveAgent
1. Add MAX_DIFF_LINES = 50 constant
1. Add diff size validation
1. Add tests
1. Commit: "feat: enforce edit tool usage and diff limits"

______________________________________________________________________

#### Task 1.3: Add Diff Size Enforcement

**Files:**

- Modify: `crackerjack/agents/proactive_agent.py`
- Test: `tests/agents/test_diff_size_limit.py`

**Implementation:**

```python
# Already part of Task 1.2, add separate validation:
def _validate_diff_size(self, old_code: str, new_code: str) -> bool:
    """Validate diff size is within acceptable limits."""
    MAX_DIFF_LINES = 50

    def count_lines(code: str) -> int:
        return len([line for line in code.split('\n') if line.strip()])

    old_count = count_lines(old_code)
    new_count = count_lines(new_code)

    if old_count > MAX_DIFF_LINES or new_count > MAX_DIFF_LINES:
        return False
    return True
```

**Steps:**

1. Extract \_validate_diff_size() from Task 1.2
1. Add as separate method
1. Add tests for various diff sizes
1. Commit: "feat: add diff size validation"

______________________________________________________________________

#### Task 1.4: Add AST-Based Syntax Validation

**Files:**

- Create: `crackerjack/agents/syntax_validator.py`
- Modify: `crackerjack/agents/proactive_agent.py`
- Create: `tests/agents/test_syntax_validation.py`
- Test fixture: `tests/fixtures/sample.py` (syntax error cases)

**Implementation:**

```python
# crackerjack/agents/syntax_validator.py
import ast
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of code validation."""
    valid: bool
    errors: List[str]

class SyntaxValidator:
    """AST-based syntax validation for generated code."""

    async def validate(self, code: str) -> ValidationResult:
        """Validate Python code using AST parsing."""
        try:
            ast.parse(code)
            return ValidationResult(valid=True, errors=[])
        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            return ValidationResult(valid=False, errors=[error_msg])
        except ValueError as e:
            return ValidationResult(valid=False, errors=[str(e)])
```

**Steps:**

1. Create SyntaxValidator class
1. Add \_validate_syntax() to ProactiveAgent
1. Make validation run before applying fixes
1. Create test fixtures for common syntax errors
1. Commit: "feat: add AST-based syntax validation"

______________________________________________________________________

### Phase 2: Layer 2 - Two-Stage Pipeline (5-7 hours)

#### Task 2.1: Create FixPlan Data Structures

**Files:**

- Create: `crackerjack/models/fix_plan.py`
- Test: `tests/models/test_fix_plan.py`

**Implementation:**

```python
# crackerjack/models/fix_plan.py
from dataclasses import dataclass
from typing import List
from enum import Enum

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass
class ChangeSpec:
    """Atomic change specification."""
    line_range: tuple[int, int]
    old_code: str
    new_code: str
    reason: str

@dataclass
class FixPlan:
    """Validated fix plan from analysis team."""
    file_path: str
    issue_type: str
    changes: List[ChangeSpec]
    rationale: str
    risk_level: RiskLevel
    validated_by: str
```

**Steps:**

1. Create ChangeSpec and FixPlan dataclasses
1. Add risk assessment
1. Add validation tracking field
1. Create tests
1. Commit: "feat: add fix plan data structures"

______________________________________________________________________

#### Task 2.2: Create ContextAgent (Analysis Stage)

**Files:**

- Create: `crackerjack/agents/context_agent.py`
- Modify: `crackerjack/agents/proactive_agent.py` to inherit from
- Test: `tests/agents/test_context_agent.py`

**Implementation:**

```python
# crackerjack/agents/context_agent.py
from ast import NodeVisitor, parse
from typing import Dict, Any

from crackerjack.agents.proactive_agent import ProactiveAgent
from crackerjack.models.fix_plan import FixPlan

class ContextAgent(ProactiveAgent):
    """Extracts file context around issue location."""

    async def extract_context(self, issue) -> Dict[str, Any]:
        """Extract function/class context using AST."""
        await self._read_file_context(issue.file_path)

        # Parse AST
        tree = parse(self._file_cache[issue.file_path])

        # Find relevant node
        visitor = ContextVisitor(issue.line_number)
        tree.visit(visitor)

        return {
            "imports": visitor.imports,
            "functions": visitor.functions,
            "classes": visitor.classes,
            "context": visitor.context
        }
```

**Steps:**

1. Create ContextAgent extending ProactiveAgent
1. Implement AST-based context extraction
1. Add ContextVisitor class
1. Handle edge cases (file not found, parse errors)
1. Commit: "feat: add context extraction agent"

______________________________________________________________________

#### Task 2.3: Create PatternAgent (Analysis Stage)

**Files:**

- Create: `crackerjack/agents/pattern_agent.py`
- Test: `tests/agents/test_pattern_agent.py`

**Implementation:**

```python
# crackerjack/agents/pattern_agent.py
from typing import List
import re

from crackerjack.agents.proactive_agent import ProactiveAgent

class PatternAgent(ProactiveAgent):
    """Identifies anti-patterns to avoid during fixing."""

    async def identify_anti_patterns(self, context: Dict[str, Any]) -> List[str]:
        """Check for common pitfalls."""
        warnings = []

        code = context.get("code", "")

        # Check for duplicate definitions
        if self._check_duplicate_definitions(code):
            warnings.append("Duplicate function/class definitions detected")

        # Check for unclosed brackets
        if self._check_unclosed_brackets(code):
            warnings.append("Unclosed parentheses/brackets detected")

        # Check for future imports placement
        if self._check_future_imports(code):
            warnings.append("Future imports must be at top of file")

        return warnings

    def _check_duplicate_definitions(self, code: str) -> bool:
        """Check for duplicate function/class names."""
        # Implementation...

    def _check_unclosed_brackets(self, code: str) -> bool:
        """Check for bracket matching."""
        open_parens = code.count('(')
        close_parens = code.count(')')
        return open_parens != close_parens
```

**Steps:**

1. Create PatternAgent extending ProactiveAgent
1. Implement anti-pattern detection methods
1. Add tests for each pattern type
1. Return warnings list instead of just boolean
1. Commit: "feat: add pattern detection agent"

______________________________________________________________________

#### Task 2.4: Create PlanningAgent (Analysis Stage)

**Files:**

- Create: `crackerjack/agents/planning_agent.py`
- Test: `tests/agents/test_planning_agent.py`

**Implementation:**

```python
# crackerjack/agents/planning_agent.py
from crackerjack.agents.proactive_agent import ProactiveAgent
from crackerjack.models.fix_plan import FixPlan, ChangeSpec, RiskLevel

class PlanningAgent(ProactiveAgent):
    """Creates FixPlans from context and patterns."""

    async def create_fix_plan(
        self,
        issue,
        context: Dict[str, Any],
        warnings: List[str]
    ) -> FixPlan:
        """Create minimal, targeted fix plan."""
        await self._read_file_context(issue.file_path)

        # Generate changes
        changes = self._generate_minimal_changes(issue, context, warnings)

        # Assess risk
        risk = self._assess_risk(changes, context)

        return FixPlan(
            file_path=issue.file_path,
            issue_type=issue.type.value,
            changes=changes,
            rationale=self._generate_rationale(changes, warnings),
            risk_level=risk,
            validated_by="PlanningAgent"
        )
```

**Steps:**

1. Create PlanningAgent extending ProactiveAgent
1. Implement change generation logic
1. Add risk assessment (LOW/MEDIUM/HIGH)
1. Add minimal diff enforcement (max 10-15 lines per change)
1. Commit: "feat: add planning agent"

______________________________________________________________________

#### Task 2.5: Create AnalysisCoordinator (Parallel Orchestration)

**Files:**

- Create: `crackerjack/agents/analysis_coordinator.py`
- Test: `tests/agents/test_analysis_coordinator.py`

**Implementation:**

```python
# crackerjack/agents/analysis_coordinator.py
import asyncio
from typing import List

from crackerjack.agents.context_agent import ContextAgent
from crackerjack.agents.pattern_agent import PatternAgent
from crackerjack.agents.planning_agent import PlanningAgent
from crackerjack.models.fix_plan import FixPlan

class AnalysisCoordinator:
    """Runs analysis team in parallel with semaphore."""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.context_agent = ContextAgent()
        self.pattern_agent = PatternAgent()
        self.planning_agent = PlanningAgent()

    async def analyze_issue(self, issue) -> FixPlan:
        """Analyze issue with parallel agents (controlled concurrency)."""
        async with self.semaphore:
            # Context must be extracted first (PatternAgent needs it)
            context = await self.context_agent.extract_context(issue)
            patterns = await self.pattern_agent.identify_anti_patterns(context)
            plan = await self.planning_agent.create_fix_plan(issue, context, patterns)
            return plan
```

**Steps:**

1. Create AnalysisCoordinator with semaphore
1. ContextAgent runs first, PatternAgent waits
1. Both use file context reader (cached, thread-safe)
1. Bounded concurrency (max 10 parallel analyses)
1. Commit: "feat: add analysis coordinator with parallel execution"

______________________________________________________________________

#### Task 2.6: Update Existing Fixer Agents

**Files:**

- Modify: `crackerjack/agents/refactoring_agent.py`
- Modify: `crackerjack/agents/architect_agent.py`
- Modify: `crackerjack/agents/security_agent.py`
- Test: `tests/agents/test_fixer_agents.py`

**Implementation:**
Update all fixer agents to accept `FixPlan` as input:

```python
# Update agent signatures
async def execute_fix_plan(self, plan: FixPlan) -> FixResult:
    """Execute FixPlan instead of raw Issue."""
    fixes_applied = []

    for change in plan.changes:
        # Apply change using Edit tool
        success = await self._apply_fix_with_edit(
            plan.file_path,
            change.old_code,
            change.new_code
        )

        if success:
            fixes_applied.append(change)

    return FixResult(
        success=len(fixes_applied) == len(plan.changes),
        fixes_applied=fixes_applied,
        remaining_issues=[] if len(fixes_applied) == len(plan.changes) else plan.changes
    )
```

**Steps:**

1. Update RefactoringAgent to use FixPlan
1. Update ArchitectAgent to use FixPlan
1. Update SecurityAgent to use FixPlan
1. Add tests for plan execution
1. Commit: "feat: update fixer agents to use FixPlan"

______________________________________________________________________

### Phase 3: Layer 3 - Interactive Fix Loop (4-6 hours)

#### Task 3.1: Create LogicValidator

**Files:**

- Create: `crackerjack/agents/logic_validator.py`
- Test: `tests/agents/test_logic_validator.py`

**Implementation:**

```python
# crackerjack/agents/logic_validator.py
from typing import List
from crackerjack.agents.syntax_validator import ValidationResult

class LogicValidator(ValidationAgent):
    """Validates logic and patterns in fixes."""

    async def validate(self, fix: FixPlan) -> ValidationResult:
        """Check for duplicate definitions, import placement, complete blocks."""
        errors = []

        for change in fix.changes:
            # Check for duplicate definitions in new_code
            if self._has_duplicate_definitions(change.new_code):
                errors.append(f"Duplicate definition in change: {change.reason}")

            # Check import order
            if self._has_misplaced_imports(change.new_code):
                errors.append("Future imports not at top of file")

        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

**Steps:**

1. Create LogicValidator extending ValidationAgent
1. Implement duplicate definition checking
1. Implement import order validation
1. Add tests
1. Commit: "feat: add logic validator"

______________________________________________________________________

#### Task 3.2: Create BehaviorValidator

**Files:**

- Create: `crackerjack/agents/behavior_validator.py`
- Test: `tests/agents/test_behavior_validator.py`

**Implementation:**

```python
# crackerjack/agents/behavior_validator.py
from typing import List, Optional
from crackerjack.agents.syntax_validator import ValidationResult

class BehaviorValidator(ValidationAgent):
    """Validates behavior by running tests if available."""

    async def validate(self, fix: FixPlan) -> ValidationResult:
        """Run tests and verify function signatures."""
        errors = []

        # Try to run tests if available
        if fix.test_path:
            test_passed = await self._run_tests(fix.test_path)
            if not test_passed:
                errors.append(f"Tests failed for {fix.test_path}")
        else:
            # Check for side effects
            if self._has_breaking_changes(fix):
                errors.append("Breaking changes to function signatures")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def _run_tests(self, test_path: str) -> bool:
        """Run pytest for specific test file."""
        import subprocess
        result = subprocess.run(
            ["pytest", test_path, "-v"],
            capture_output=True,
            timeout=30
        )
        return result.returncode == 0
```

**Steps:**

1. Create BehaviorValidator extending ValidationAgent
1. Add test running capability
1. Add side effect detection
1. Add tests
1. Commit: "feat: add behavior validator"

______________________________________________________________________

#### Task 3.3: Create ValidationCoordinator (Power Trio)

**Files:**

- Create: `crackerjack/agents/validation_coordinator.py`
- Test: `tests/agents/test_validation_coordinator.py`

**Implementation:**

```python
# crackerjack/agents/validation_coordinator.py
import asyncio
from typing import List, Tuple
from dataclasses import dataclass

from crackerjack.agents.syntax_validator import SyntaxValidator, ValidationResult
from crackerjack.agents.logic_validator import LogicValidator
from crackerjack.agents.behavior_validator import BehaviorValidator
from crackerjack.models.fix_plan import FixPlan

@dataclass
class ValidationSummary:
    """Summary of all validation results."""
    syntax_result: ValidationResult
    logic_result: ValidationResult
    behavior_result: ValidationResult

class ValidationCoordinator:
    """Runs Power Trio validators in PARALLEL."""

    def __init__(self):
        self.syntax = SyntaxValidator()
        self.logic = LogicValidator()
        self.behavior = BehaviorValidator()

    async def validate_fix(self, fix: FixPlan) -> Tuple[bool, str]:
        """Run ALL 3 validators in parallel. Apply if ANY passes."""
        # Run in parallel
        syntax_result, logic_result, behavior_result = await asyncio.gather(
            self.syntax.validate(fix),
            self.logic.validate(fix),
            self.behavior.validate(fix)
        )

        # Permissive: apply if ANY passes
        is_valid = any([
            syntax_result.valid,
            logic_result.valid,
            behavior_result.valid
        ])

        if not is_valid:
            # Combine feedback for retry
            errors = []
            errors.extend(syntax_result.errors)
            errors.extend(logic_result.errors)
            errors.extend(behavior_result.errors)
            feedback = "\n".join(errors)
        else:
            feedback = "Fix validated"

        return is_valid, feedback
```

**Steps:**

1. Create ValidationCoordinator with Power Trio
1. Run all 3 validators in parallel (asyncio.gather)
1. Implement permissive logic (apply if ANY passes)
1. Combine feedback when all fail
1. Add tests
1. Commit: "feat: add validation coordinator with power trio"

______________________________________________________________________

#### Task 3.4: Integrate Validation Loop with Rollback

**Files:**

- Modify: `crackerjack/core/autofix_coordinator.py`
- Test: `tests/integration/test_validation_loop.py`

**Implementation:**
Update `_apply_ai_agent_fixes()` to use validation loop:

```python
# In AutofixCoordinator._apply_ai_agent_fixes():
from crackerjack.agents.analysis_coordinator import AnalysisCoordinator
from crackerjack.agents.validation_coordinator import ValidationCoordinator
from crackerjack.agents.fixer_coordinator import FixerCoordinator

async def _apply_ai_agent_fixes(
    self,
    hook_results: Sequence[object],
    stage: str = "fast"
) -> bool:
    # Setup coordinators
    analysis_coordinator = AnalysisCoordinator()
    validation_coordinator = ValidationCoordinator()
    fixer_coordinator = FixerCoordinator()  # From Task 2.7

    issues = self._collect_fixable_issues(hook_results)

    # Stage 1: Analysis (parallel)
    plans = await analysis_coordinator.analyze_issues(issues)

    # Stage 2: Execution with validation loop
    for plan in plans:
        for attempt in range(3):  # Max 3 retries
            # Generate fix from plan
            fix_result = await fixer_coordinator.execute_plan(plan)

            # Validate BEFORE applying (Power Trio in parallel)
            is_valid, feedback = await validation_coordinator.validate_fix(fix_result.fix)

            if is_valid:
                # Apply fix
                await self._apply_fix(fix_result.fix)

                # Run tests if available
                if fix_result.test_path:
                    test_passed = await self._run_test(fix_result.test_path)
                    if not test_passed:
                        await self._rollback_fix(fix_result.fix)
                        break  # Skip to next issue

            else:
                # Update plan with feedback and retry
                plan = await self._update_plan_with_feedback(plan, feedback)
                continue

        return self._check_convergence(plans)
```

**Steps:**

1. Import new coordinators
1. Replace direct agent calls with AnalysisCoordinator
1. Add validation loop with max 3 retries
1. Implement rollback mechanism
1. Add test execution
1. Commit: "feat: integrate validation loop with rollback"

______________________________________________________________________

### Phase 4: Layer 4 - Fallback Wrapper (3-4 hours)

#### Task 4.1: Create FallbackOrchestrator

**Files:**

- Create: `crackerjack/agents/fallback_orchestrator.py`
- Test: `tests/agents/test_fallback_orchestrator.py`

**Implementation:**

```python
# crackerjack/agents/fallback_orchestrator.py
from typing import List, Optional
import logging

from crackerjack.agents.proactive_agent import ProactiveAgent

logger = logging.getLogger(__name__)

class FallbackOrchestrator(ProactiveAgent):
    """Fallback to Claude Code when parallel agents fail."""

    async def fix_with_fallback(
        self,
        issue,
        failed_attempts: List[object],
        max_attempts: int = 3
    ) -> FixResult:
        """Try parallel agents first, then fallback to Claude Code."""
        # Try parallel agents first
        for attempt in range(max_attempts):
            result = await self._try_parallel_agents(issue)
            if result.success:
                await self._learn_pattern(issue, failed_attempts, result)
                return result

        # All parallel agents failed - use fallback
        logger.warning(f"Parallel agents failed, using fallback for {issue.id}")
        claude_result = await self._call_claude_code_direct(issue, failed_attempts)
        return claude_result

    async def _try_parallel_agents(self, issue) -> FixResult:
        """Try all fixer agents in parallel."""
        # Implementation...

    async def _call_claude_code_direct(self, issue, attempts) -> FixResult:
        """Call Claude Code API directly."""
        # Implementation - use existing Claude Code bridge if available
        pass
```

**Steps:**

1. Create FallbackOrchestrator extending ProactiveAgent
1. Implement max attempt tracking
1. Add parallel agent retry logic
1. Add Claude Code API integration
1. Add learning from successes
1. Commit: "feat: add fallback orchestrator"

______________________________________________________________________

#### Task 4.2: Create PatternLibrary

**Files:**

- Create: `crackerjack/agents/pattern_library.py`
- Test: `tests/agents/test_pattern_library.py`

**Implementation:**

```python
# crackerjack/agents/pattern_library.py
from dataclasses import dataclass
from typing import List

@dataclass
class FixPattern:
    """Successful fix pattern for learning."""
    issue_type: str
    error_pattern: str
    successful_approach: str
    agent_failures: List[str]
    success_count: int = 0
    usage_count: int = 0

class PatternLibrary:
    """Store and retrieve successful fix patterns."""

    def __init__(self):
        self.patterns: List[FixPattern] = []

    async def store(self, pattern: FixPattern) -> None:
        """Store successful pattern."""
        pattern.success_count = 1
        self.patterns.append(pattern)

    async def find_similar(self, issue) -> List[FixPattern]:
        """Find patterns similar to current issue."""
        # Implementation...
        return []

    async def update_agent_prompts(self, pattern: FixPattern) -> None:
        """Update agent prompts based on learned patterns."""
        # Implementation...
```

**Steps:**

1. Create FixPattern dataclass
1. Create PatternLibrary with store/retrieve methods
1. Add similarity search by issue type
1. Add agent prompt update capability
1. Commit: "feat: add pattern library for learning"

______________________________________________________________________

#### Task 4.3: Integrate Fallback into AutofixCoordinator

**Files:**

- Modify: `crackerjack/core/autofix_coordinator.py`
- Test: `tests/integration/test_fallback_integration.py`

**Implementation:**
Add fallback trigger to `_apply_ai_agent_fixes()`:

```python
# In AutofixCoordinator:
from crackerjack.agents.fallback_orchestrator import FallbackOrchestrator

def __init__(self, ...):
    # ... existing code ...
    self.fallback_orchestrator = FallbackOrchestrator()

async def _apply_ai_agent_fixes(
    self,
    hook_results: Sequence[object],
    stage: str = "fast"
) -> bool:
    # ... existing validation loop code ...

    # Fallback triggers
    MAX_SYNTAX_FAILURES = 3
    MAX_LOGIC_FAILURES = 2
    MAX_DIFF_LINES = 100  # Too large for agents

    if self._should_try_fallback(fixes_applied, remaining):
        result = await self.fallback_orchestrator.fix_with_fallback(
            issues=self._collect_fixable_issues(hook_results),
            failed_attempts=self._get_failed_attempts()
        )
        return result.success
```

**Steps:**

1. Add fallback orchestrator to __init__
1. Define fallback trigger conditions
1. Integrate fallback call in main loop
1. Track fallback usage metrics
1. Decrease threshold over time as agents improve
1. Commit: "feat: integrate fallback mechanism"

______________________________________________________________________

### Phase 5: Integration & Testing (3-4 hours)

#### Task 5.1: Update All Existing Agents

**Files:**

- Modify: `crackerjack/agents/proactive_agent.py` (ensure all agents inherit)
- Test: `tests/agents/test_all_agents_updated.py`

**Implementation:**
Ensure all agents use new infrastructure:

```python
# Verify all agents inherit from updated ProactiveAgent:
- RefactoringAgent
- ArchitectAgent
- SecurityAgent
- FormattingAgent
- TestCreationAgent
- DRYAgent
- ImportOptimizationAgent
- SemanticAgent
```

**Steps:**

1. Audit all agent files for ProactiveAgent inheritance
1. Update any that don't inherit
1. Add \_read_file_context() call if missing
1. Update \_generate_fix() to use \_apply_fix_with_edit()
1. Commit: "feat: update all agents to use new infrastructure"

______________________________________________________________________

#### Task 5.2: Add Integration Tests

**Files:**

- Create: `tests/integration/test_ai_fix_workflow.py`
- Test fixtures: `tests/fixtures/ai_fix_scenarios/`

**Implementation:**
End-to-end workflow test:

```python
# tests/integration/test_ai_fix_workflow.py
import pytest

async def test_full_workflow_with_validation():
    """Test complete AI fix workflow with validation."""
    # Setup
    issues = [create_test_issue()]

    # Run workflow
    result = await autofix_coordinator._apply_ai_agent_fixes(
        hook_results=[],
        stage="test"
    )

    # Assert validation happened
    assert result.validation_count > 0
    assert result.rollback_count >= 0

    # Assert fixes were applied
    assert result.fixes_applied > 0
```

**Steps:**

1. Create test scenarios with various issue types
1. Test full workflow end-to-end
1. Verify validation loop runs
1. Verify rollback mechanism works
1. Verify Power Trio runs in parallel
1. Commit: "feat: add comprehensive integration tests"

______________________________________________________________________

#### Task 5.3: Add Performance Benchmarks

**Files:**

- Create: `tests/benchmarks/test_agent_performance.py`
- Benchmark fixtures: `tests/fixtures/performance_issues.py`

**Implementation:**

```python
# tests/benchmarks/test_agent_performance.py
import pytest
import time

from crackerjack.agents.analysis_coordinator import AnalysisCoordinator
from crackerjack.agents.fixer_coordinator import FixerCoordinator

def test_analysis_parallel_speed():
    """Benchmark parallel analysis performance."""
    issues = [create_test_issue() for _ in range(100)]

    start = time.time()
    coordinator = AnalysisCoordinator(max_concurrent=10)
    results = asyncio.run(coordinator.analyze_issues(issues))
    elapsed = time.time() - start

    assert elapsed < 5.0  # Should complete in < 5 seconds
    assert len(results) == 100

def test_fixer_performance():
    """Benchmark fixer execution speed."""
    # Implementation...
```

**Steps:**

1. Create analysis speed benchmark (100 issues, < 5s target)
1. Create fixer performance benchmark
1. Measure parallel execution speedup
1. Track success rates by agent type
1. Generate performance report
1. Commit: "feat: add agent performance benchmarks"

______________________________________________________________________

#### Task 5.4: Update Documentation

**Files:**

- Modify: `CLAUDE_ARCHITECTURE.md`
- Modify: `CLAUDE_QUICKSTART.md`
- Create: `docs/reference/AI_FIX_QUALITY_SYSTEM.md`

**Implementation:**

```markdown
# CLAUDE_ARCHITECTURE.md - Add new agents section

## AI Agents

### Analysis Layer
- **ContextAgent** - Extracts file context using AST
- **PatternAgent** - Identifies anti-patterns (duplicates, unclosed brackets)
- **PlanningAgent** - Creates FixPlan from context + patterns

### Validation Layer (Power Trio)
- **SyntaxValidator** - AST-based validation
- **LogicValidator** - Checks for duplicates, import placement
- **BehaviorValidator** - Runs tests, checks signatures
- **ValidationCoordinator** - Runs all 3 in parallel, permissive logic

### Execution Layer
- **FixerCoordinator** - Routes FixPlans to appropriate fixer agents
- **FallbackOrchestrator** - Falls back to Claude Code when agents fail

### Learning System
- **PatternLibrary** - Stores successful patterns, updates agent prompts
```

**Steps:**

1. Document new agent architecture
1. Add quick start guide for new system
1. Document troubleshooting procedures
1. Create diagrams showing data flow
1. Add migration guide from old to new system
1. Commit: "docs: comprehensive V2 quality system documentation"

````

**Steps:**
1. Update architecture with 4-layer diagram
2. Add usage examples for each layer
3. Add troubleshooting section
4. Add performance tuning guide
5. Document rollback procedures
6. Commit: "docs: complete V2 quality system documentation"

---

## Implementation Order

**Recommended Sequence:**
1. **Phase 1 Tasks 1.1-1.4** (Foundation) - Do first
2. **Phase 2 Tasks 2.1-2.6** (Pipeline) - Build on Phase 1
3. **Phase 3 Tasks 3.1-3.4** (Validation) - Build on Phases 1+2
4. **Phase 4 Tasks 4.1-4.3** (Fallback) - Build on Phases 1+2+3
5. **Phase 5 Tasks 5.1-5.4** (Integration) - Integrate all layers

**Total Tasks:** 23 tasks across 5 phases
**Estimated Time:** 20-24 hours

---

## Success Metrics

### Target Goals
- **Syntax errors:** Reduce from 108 per run → < 10 per run initially
- **Success rate:** Increase from 2.7% → 60%+ initially, 80%+ with learning
- **Fallback usage:** < 30% initially, decreasing to < 10% over time
- **Parallel speedup:** 1.5-2x faster than sequential execution

### Validation Commands
```bash
# Verify agents use new infrastructure
grep -r "_read_file_context" crackerjack/agents/

# Check parallel execution
pytest tests/benchmarks/test_agent_performance.py -v

# Run integration test
pytest tests/integration/test_ai_fix_workflow.py -v
````

______________________________________________________________________

## Testing Strategy

### Unit Tests

- File context reading
- Syntax validation (error cases)
- Pattern detection (duplicates, brackets, imports)
- Logic validation
- Behavior validation

### Integration Tests

- Full workflow with validation loop
- Rollback mechanism
- Fallback triggering
- Performance benchmarks

### Acceptance Criteria

✅ All unit tests pass
✅ Integration test passes (validation runs, rollback works)
✅ Performance benchmarks meet targets (analysis < 5s for 100 issues)
✅ No regression in existing functionality

______________________________________________________________________

**End of Implementation Plan**
