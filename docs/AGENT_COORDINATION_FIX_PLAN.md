# Agent Coordination Fix Implementation Plan

## Overview

This document provides step-by-step implementation of fixes for the agent coordination architecture issues identified in AGENT_COORDINATION_ARCHITECTURE_ANALYSIS.md.

---

## Phase 1: Immediate Fix (Critical Path)

### Issue: Missing RefactoringAgent in ISSUE_TYPE_TO_AGENTS

**File**: `crackerjack/agents/coordinator.py`
**Line**: 25
**Severity**: CRITICAL
**Time**: 5 minutes

#### Current Code (BROKEN)

```python
ISSUE_TYPE_TO_AGENTS: dict[IssueType, list[str]] = {
    IssueType.FORMATTING: ["FormattingAgent", "ArchitectAgent"],
    IssueType.TYPE_ERROR: ["ArchitectAgent"],  # ❌ RefactoringAgent MISSING!
    IssueType.SECURITY: ["SecurityAgent", "ArchitectAgent"],
    # ...
}
```

#### Fixed Code

```python
ISSUE_TYPE_TO_AGENTS: dict[IssueType, list[str]] = {
    IssueType.FORMATTING: ["FormattingAgent", "ArchitectAgent"],
    IssueType.TYPE_ERROR: ["RefactoringAgent", "ArchitectAgent"],  # ✅ Fixed!
    IssueType.SECURITY: ["SecurityAgent", "ArchitectAgent"],
    # ...
}
```

#### Why This Works

- RefactoringAgent is now in the filtered list for TYPE_ERROR
- RefactoringAgent.can_handle() returns 0.7-0.9 for TYPE_ERROR
- ArchitectAgent.can_handle() returns 0.1 for TYPE_ERROR
- RefactoringAgent wins with higher confidence
- Issue gets fixed instead of failing

#### Verification

```bash
# Run quality checks with AI fixing enabled
python -m crackerjack run --ai-fix --run-tests -c

# Check logs for:
# - "RefactoringAgent successfully fixed issue"
# - NOT "ArchitectAgent failed to fix issue"
```

---

## Phase 2: Architecture Cleanup

### Fix 2.1: Add Priority Property to SubAgent

**File**: `crackerjack/agents/base.py`
**New Method**
**Time**: 15 minutes

#### Implementation

```python
# Add to SubAgent class (after get_supported_types method)
class SubAgent(ABC):
    # ... existing code ...

    @property
    def priority(self) -> int:
        """Priority for agent selection.

        Lower number = higher priority (tried first).
        Default: 100 (low priority fallback).

        Specialized agents: 10-50
        Generalist agents: 50-100
        """
        return 100  # Default low priority
```

#### Update RefactoringAgent

**File**: `crackerjack/agents/refactoring_agent.py`

```python
# Add after get_supported_types method (around line 68)
class RefactoringAgent(SubAgent):
    # ... existing code ...

    @property
    def priority(self) -> int:
        """High priority for refactoring tasks.

        Priority 10 ensures this agent is tried before ArchitectAgent (priority 50).
        """
        return 10  # Specialist - try first
```

#### Update ArchitectAgent

**File**: `crackerjack/agents/architect_agent.py`

```python
# Add after get_supported_types method (around line 32)
class ArchitectAgent(ProactiveAgent):
    # ... existing code ...

    @property
    def priority(self) -> int:
        """Medium priority for architectural tasks.

        Priority 50 makes this agent a fallback after specialists fail.
        """
        return 50  # Generalist - fallback after specialists
```

#### Update Other Agents

**File**: `crackerjack/agents/formatting_agent.py`

```python
@property
def priority(self) -> int:
    return 20  # Specialist for formatting
```

**File**: `crackerjack/agents/security_agent.py`

```python
@property
def priority(self) -> int:
    return 20  # Specialist for security
```

**File**: `crackerjack/agents/test_creation_agent.py`

```python
@property
def priority(self) -> int:
    return 30  # Specialist for tests
```

---

### Fix 2.2: Update Selection Algorithm to Use Priority

**File**: `crackerjack/agents/coordinator.py`
**Method**: `_find_best_specialist`
**Lines**: 202-212
**Time**: 30 minutes

#### Current Code (CONFIDENCE-BASED ONLY)

```python
async def _find_best_specialist(
    self,
    specialists: list[SubAgent],
    issue: Issue,
) -> SubAgent | None:
    candidates = await self._score_all_specialists(specialists, issue)
    if not candidates:
        return None

    best_agent, best_score = self._find_highest_scoring_agent(candidates)
    return self._apply_built_in_preference(candidates, best_agent, best_score)
```

#### Fixed Code (PRIORITY-BASED)

```python
async def _find_best_specialist(
    self,
    specialists: list[SubAgent],
    issue: Issue,
) -> SubAgent | None:
    """Find best agent using priority groups and confidence scoring.

    Strategy:
    1. Group agents by priority level
    2. For each priority level (lowest to highest):
       a. Score all agents in that level
       b. If best score >= threshold, use that agent
       c. Otherwise, try next priority level
    3. Return best agent found, or None if no agent has sufficient confidence
    """
    if not specialists:
        return None

    # Group by priority level
    priority_groups = self._group_by_priority(specialists)

    # Try each priority level in order (lowest number = highest priority)
    for priority_level, agents_in_priority in sorted(priority_groups.items()):
        self.logger.debug(
            f"Trying priority level {priority_level} with {len(agents_in_priority)} agents"
        )

        # Score all agents at this priority level
        candidates = await self._score_all_specialists(agents_in_priority, issue)
        if not candidates:
            continue

        # Find best agent at this priority level
        best_agent, best_score = self._find_highest_scoring_agent(candidates)

        # If confidence threshold met, use this agent
        CONFIDENCE_THRESHOLD = 0.3
        if best_score >= CONFIDENCE_THRESHOLD:
            self.logger.info(
                f"Selected {best_agent.name} (priority {priority_level}, "
                f"confidence {best_score:.2f})"
            )
            return best_agent

        # Otherwise, try next priority level
        self.logger.debug(
            f"No agent at priority {priority_level} met threshold "
            f"(best: {best_score:.2f}), trying next level"
        )

    # No agent met confidence threshold
    self.logger.warning("No agent met minimum confidence threshold")
    return None


def _group_by_priority(
    self,
    agents: list[SubAgent],
) -> dict[int, list[SubAgent]]:
    """Group agents by priority level.

    Returns:
        Dictionary mapping priority level to list of agents at that level
    """
    groups: dict[int, list[SubAgent]] = {}

    for agent in agents:
        priority = agent.priority
        if priority not in groups:
            groups[priority] = []
        groups[priority].append(agent)

    return groups
```

#### Why This Works

1. **RefactoringAgent (priority 10)** tried before **ArchitectAgent (priority 50)**
2. Within same priority level, confidence determines winner
3. Fallback to lower priority if higher priority agents lack confidence
4. Clear, predictable selection order

---

### Fix 2.3: Remove ArchitectAgent's TYPE_ERROR Claim

**File**: `crackerjack/agents/architect_agent.py`
**Method**: `get_supported_types`
**Lines**: 20-32
**Time**: 10 minutes

#### Current Code (CONFUSING)

```python
def get_supported_types(self) -> set[IssueType]:
    """Return issue types handled by this agent.

    ArchitectAgent has reduced scope - only handles issues that don't have
    specialized agents. DEPENDENCY and DOCUMENTATION are delegated to
    specialized agents (DependencyAgent and DocumentationAgent).
    """
    return {
        IssueType.TYPE_ERROR,  # Delegates to RefactoringAgent - ❌ CONFUSING!
        # IssueType.DEPENDENCY,  # Delegated to DependencyAgent
        # IssueType.DOCUMENTATION,  # Delegated to DocumentationAgent
        IssueType.TEST_ORGANIZATION,
    }
```

#### Fixed Code

```python
def get_supported_types(self) -> set[IssueType]:
    """Return issue types handled by this agent.

    ArchitectAgent only handles issues without specialized agents.
    TYPE_ERROR is handled by RefactoringAgent.
    DEPENDENCY is handled by DependencyAgent.
    DOCUMENTATION is handled by DocumentationAgent.
    """
    return {
        # IssueType.TYPE_ERROR,  # ✅ Removed - handled by RefactoringAgent
        IssueType.TEST_ORGANIZATION,
    }
```

#### Also Update can_handle

**File**: `crackerjack/agents/architect_agent.py`
**Method**: `can_handle`
**Lines**: 34-46

#### Current Code

```python
async def can_handle(self, issue: Issue) -> float:
    """Check if we can handle this issue.

    VERY LOW confidence - let specialists handle issues first.
    Only act as fallback when no one else can handle.
    """
    if issue.type == IssueType.TYPE_ERROR:
        return 0.1  # Let RefactoringAgent handle it

    if issue.type == IssueType.TEST_ORGANIZATION:
        return 0.1

    return 0.0  # Don't claim to handle types we've delegated
```

#### Fixed Code

```python
async def can_handle(self, issue: Issue) -> float:
    """Check if we can handle this issue.

    ArchitectAgent acts as generalist fallback with low confidence,
    allowing specialized agents to handle their domains first.
    """
    if issue.type == IssueType.TEST_ORGANIZATION:
        return 0.1

    return 0.0  # Don't claim to handle types we don't support
```

#### Also Update analyze_and_fix

**File**: `crackerjack/agents/architect_agent.py`
**Method**: `analyze_and_fix`
**Lines**: 282-305

#### Current Code

```python
async def analyze_and_fix(self, issue: Issue) -> FixResult:
    # Delegate to specialized agents based on issue type
    if issue.type in {
        IssueType.COMPLEXITY,
        IssueType.DRY_VIOLATION,
        IssueType.DEAD_CODE,
    }:
        self.log(f"Delegating to RefactoringAgent for {issue.type.value}")
        return await self._refactoring_agent.analyze_and_fix(issue)

    if issue.type == IssueType.FORMATTING:
        self.log(f"Delegating to FormattingAgent for {issue.type.value}")
        return await self._formatting_agent.analyze_and_fix(issue)

    if issue.type == IssueType.IMPORT_ERROR:
        self.log(f"Delegating to ImportOptimizationAgent for {issue.type.value}")
        return await self._import_agent.analyze_and_fix(issue)

    if issue.type == IssueType.SECURITY:
        self.log(f"Delegating to SecurityAgent for {issue.type.value}")
        return await self._security_agent.analyze_and_fix(issue)

    # For types we still handle, use proactive approach
    return await self.analyze_and_fix_proactively(issue)
```

#### Fixed Code

```python
async def analyze_and_fix(self, issue: Issue) -> FixResult:
    """Handle issue by delegating to specialized agents or proactive handling.

    Delegation rules:
    - RefactoringAgent: COMPLEXITY, DRY_VIOLATION, DEAD_CODE, TYPE_ERROR
    - FormattingAgent: FORMATTING
    - ImportOptimizationAgent: IMPORT_ERROR
    - SecurityAgent: SECURITY
    - ArchitectAgent (proactive): TEST_ORGANIZATION
    """
    # Delegate to RefactoringAgent for refactoring issues
    if issue.type in {
        IssueType.COMPLEXITY,
        IssueType.DRY_VIOLATION,
        IssueType.DEAD_CODE,
        IssueType.TYPE_ERROR,  # ✅ Added TYPE_ERROR delegation
    }:
        self.log(f"Delegating to RefactoringAgent for {issue.type.value}")
        return await self._refactoring_agent.analyze_and_fix(issue)

    if issue.type == IssueType.FORMATTING:
        self.log(f"Delegating to FormattingAgent for {issue.type.value}")
        return await self._formatting_agent.analyze_and_fix(issue)

    if issue.type == IssueType.IMPORT_ERROR:
        self.log(f"Delegating to ImportOptimizationAgent for {issue.type.value}")
        return await self._import_agent.analyze_and_fix(issue)

    if issue.type == IssueType.SECURITY:
        self.log(f"Delegating to SecurityAgent for {issue.type.value}")
        return await self._security_agent.analyze_and_fix(issue)

    # For types we still handle, use proactive approach
    return await self.analyze_and_fix_proactively(issue)
```

---

## Phase 3: Fallback Chain Implementation

### Fix 3.1: Implement Fallback Mechanism

**File**: `crackerjack/agents/coordinator.py`
**New Method**: `_try_fallback_agents`
**Time**: 45 minutes

#### Implementation

```python
async def _handle_with_single_agent(
    self,
    agent: SubAgent,
    issue: Issue,
) -> FixResult:
    """Handle issue with agent, using fallbacks if needed.

    Strategy:
    1. Check agent confidence
    2. If confidence too low, try fallback agents
    3. Execute agent
    4. If execution fails, try fallback agents
    5. Return result (success or failure)

    Args:
        agent: Primary agent to try
        issue: Issue to fix

    Returns:
        FixResult from successful agent, or failure if all agents fail
    """
    self.logger.info(
        f"Attempting {agent.name} (priority {agent.priority}) "
        f"for issue: {issue.message[:100]}"
    )

    # Check confidence first
    confidence = await agent.can_handle(issue)

    MIN_CONFIDENCE_THRESHOLD = 0.3

    if confidence < MIN_CONFIDENCE_THRESHOLD:
        self.logger.info(
            f"{agent.name} confidence too low ({confidence:.2f}), trying fallbacks"
        )
        return await self._try_fallback_agents(agent, issue)

    # Track the attempt
    self.tracker.track_agent_processing(agent.name, issue, confidence)

    self.debugger.log_agent_activity(
        agent_name=agent.name,
        activity="processing_started",
        issue_id=issue.id,
        confidence=confidence,
        metadata={"issue_type": issue.type.value, "severity": issue.severity.value},
    )

    # Execute the agent
    start_time = time.time()
    result = await self._execute_agent(agent, issue)
    execution_time_ms = (time.time() - start_time) * 1000

    # Track execution
    await self._track_agent_execution(
        job_id=self.job_id,
        agent_name=agent.name,
        issue_type=issue.type.value,
        result=result,
        execution_time_ms=execution_time_ms,
    )

    # If failed, try fallbacks
    if not result.success:
        self.logger.warning(
            f"{agent.name} failed to fix issue ({len(result.remaining_issues)} errors), "
            f"trying fallback agents"
        )
        return await self._try_fallback_agents(agent, issue)

    # Success
    self.logger.info(f"{agent.name} successfully fixed issue")
    self.tracker.track_agent_complete(agent.name, result)

    self.debugger.log_agent_activity(
        agent_name=agent.name,
        activity="processing_completed",
        issue_id=issue.id,
        confidence=result.confidence,
        result={
            "success": result.success,
            "remaining_issues": len(result.remaining_issues),
        },
        metadata={"fix_applied": result.success},
    )

    return result


async def _try_fallback_agents(
    self,
    failed_agent: SubAgent,
    issue: Issue,
) -> FixResult:
    """Try alternative agents for this issue type.

    Tries all agents that support this issue type (except the failed one)
    in priority order until one succeeds or all fail.

    Args:
        failed_agent: Agent that already failed or had low confidence
        issue: Issue to fix

    Returns:
        FixResult from first successful fallback, or combined failure
    """
    # Find fallback candidates
    fallback_candidates = [
        agent
        for agent in self.agents
        if agent != failed_agent and issue.type in agent.get_supported_types()
    ]

    if not fallback_candidates:
        self.logger.info("No fallback agents available for this issue type")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"No agents available for {issue.type.value}"],
        )

    # Sort by priority (lowest number = highest priority)
    fallback_candidates.sort(key=lambda a: a.priority)

    self.logger.info(
        f"Found {len(fallback_candidates)} fallback agents: "
        f"{[a.name for a in fallback_candidates]}"
    )

    # Try each fallback in order
    for fallback in fallback_candidates:
        self.logger.info(f"Trying fallback agent {fallback.name} (priority {fallback.priority})")

        confidence = await fallback.can_handle(issue)

        MIN_CONFIDENCE_THRESHOLD = 0.3

        if confidence < MIN_CONFIDENCE_THRESHOLD:
            self.logger.debug(
                f"Fallback {fallback.name} confidence too low ({confidence:.2f}), skipping"
            )
            continue

        # Track fallback attempt
        self.tracker.track_agent_processing(fallback.name, issue, confidence)

        # Execute fallback
        start_time = time.time()
        result = await self._execute_agent(fallback, issue)
        execution_time_ms = (time.time() - start_time) * 1000

        # Track execution
        await self._track_agent_execution(
            job_id=self.job_id,
            agent_name=fallback.name,
            issue_type=issue.type.value,
            result=result,
            execution_time_ms=execution_time_ms,
        )

        if result.success:
            self.logger.info(
                f"Fallback agent {fallback.name} successfully fixed issue "
                f"(confidence: {result.confidence:.2f})"
            )
            self.tracker.track_agent_complete(fallback.name, result)
            return result
        else:
            self.logger.warning(
                f"Fallback agent {fallback.name} also failed "
                f"({len(result.remaining_issues)} errors)"
            )

    # All fallbacks failed
    self.logger.error("All fallback agents failed for this issue")
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[
            f"All {len(fallback_candidates) + 1} agents failed for {issue.type.value}"
        ],
        recommendations=[
            "This issue may require manual intervention",
            "Consider adding a specialized agent for this issue type",
        ],
    )
```

---

### Fix 3.2: Remove Built-in Agent Preference Logic

**File**: `crackerjack/agents/coordinator.py`
**Methods to remove**: `_apply_built_in_preference`, `_should_prefer_built_in_agent`, `_log_built_in_preference`, `_is_built_in_agent`
**Time**: 15 minutes

#### Why Remove This?

The built-in preference logic was a workaround for not having proper priority-based selection. Now that we have priorities, this is redundant and adds complexity.

#### Updated _find_best_specialist (Simplified)

```python
async def _find_best_specialist(
    self,
    specialists: list[SubAgent],
    issue: Issue,
) -> SubAgent | None:
    """Find best agent using priority groups and confidence scoring."""
    if not specialists:
        return None

    # Group by priority level
    priority_groups = self._group_by_priority(specialists)

    # Try each priority level in order
    for priority_level, agents_in_priority in sorted(priority_groups.items()):
        self.logger.debug(
            f"Trying priority level {priority_level} with {len(agents_in_priority)} agents"
        )

        # Score all agents at this priority level
        candidates = await self._score_all_specialists(agents_in_priority, issue)
        if not candidates:
            continue

        # Find best agent at this priority level
        best_agent, best_score = self._find_highest_scoring_agent(candidates)

        # If confidence threshold met, use this agent
        CONFIDENCE_THRESHOLD = 0.3
        if best_score >= CONFIDENCE_THRESHOLD:
            self.logger.info(
                f"Selected {best_agent.name} (priority {priority_level}, "
                f"confidence {best_score:.2f})"
            )
            return best_agent

        # Otherwise, try next priority level
        self.logger.debug(
            f"No agent at priority {priority_level} met threshold "
            f"(best: {best_score:.2f}), trying next level"
        )

    # No agent met confidence threshold
    self.logger.warning("No agent met minimum confidence threshold")
    return None
```

---

## Testing

### Test 1: TYPE_ERROR Selects RefactoringAgent

**File**: `tests/agents/test_coordinator.py` (create if doesn't exist)

```python
import pytest
from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.agents.coordinator import AgentCoordinator


@pytest.mark.asyncio
async def test_type_error_selects_refactoring_agent():
    """TYPE_ERROR should select RefactoringAgent, not ArchitectAgent."""
    from crackerjack.agents.base import AgentContext
    from pathlib import Path

    context = AgentContext(project_path=Path.cwd())

    # Mock tracker and debugger
    from unittest.mock import Mock

    tracker = Mock()
    tracker.register_agents = Mock()
    tracker.set_coordinator_status = Mock()
    tracker.track_agent_processing = Mock()
    tracker.track_agent_complete = Mock()

    debugger = Mock()
    debugger.log_agent_activity = Mock()

    coordinator = AgentCoordinator(context, tracker, debugger)
    coordinator.initialize_agents()

    # Create TYPE_ERROR issue
    issue = Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.MEDIUM,
        message="Function 'test_function' has missing return type",
        file_path="test.py",
        line_number=42,
    )

    # Find specialist agents for TYPE_ERROR
    specialists = await coordinator._find_specialist_agents(IssueType.TYPE_ERROR)

    # Verify RefactoringAgent is in the list
    specialist_names = [a.__class__.__name__ for a in specialists]
    assert "RefactoringAgent" in specialist_names

    # Find best specialist
    best = await coordinator._find_best_specialist(specialists, issue)

    # Verify RefactoringAgent is selected
    assert best is not None
    assert best.__class__.__name__ == "RefactoringAgent"


@pytest.mark.asyncio
async def test_refactoring_agent_has_higher_priority():
    """RefactoringAgent should have higher priority (lower number) than ArchitectAgent."""
    from crackerjack.agents.refactoring_agent import RefactoringAgent
    from crackerjack.agents.architect_agent import ArchitectAgent
    from crackerjack.agents.base import AgentContext
    from pathlib import Path

    context = AgentContext(project_path=Path.cwd())

    refactoring = RefactoringAgent(context)
    architect = ArchitectAgent(context)

    # RefactoringAgent should have lower priority number (higher priority)
    assert refactoring.priority < architect.priority
    assert refactoring.priority == 10
    assert architect.priority == 50


@pytest.mark.asyncio
async def test_fallback_on_primary_failure():
    """When primary agent fails, fallback agents should be tried."""
    from crackerjack.agents.base import AgentContext, FixResult
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    context = AgentContext(project_path=Path.cwd())

    tracker = Mock()
    debugger = Mock()

    coordinator = AgentCoordinator(context, tracker, debugger)
    coordinator.initialize_agents()

    issue = Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.MEDIUM,
        message="Test issue",
    )

    # Mock RefactoringAgent to fail
    refactoring_agent = next(
        a for a in coordinator.agents if a.__class__.__name__ == "RefactoringAgent"
    )

    with patch.object(
        refactoring_agent,
        "analyze_and_fix",
        new_callable=AsyncMock,
        return_value=FixResult(success=False, confidence=0.0, remaining_issues=["Failed"]),
    ):
        result = await coordinator._handle_with_single_agent(refactoring_agent, issue)

        # Result should indicate failure (ArchitectAgent also returns 0.0 for TYPE_ERROR)
        assert result.success is False
```

---

## Verification Steps

### Step 1: Run Tests

```bash
# Run agent coordinator tests
python -m pytest tests/agents/test_coordinator.py -v

# Run all agent tests
python -m pytest tests/agents/ -v
```

### Step 2: Manual Testing

```bash
# Create a test file with type error
cat > /tmp/test_types.py << 'EOF'
def my_function(x):  # Missing return type
    return x * 2
EOF

# Run crackerjack with AI fix
cd /tmp
python -m crackerjack run --ai-fix --run-tests -c

# Check logs for:
# - "RefactoringAgent successfully fixed issue"
# - Added "-> None" to function definition
```

### Step 3: Verify Agent Selection

```bash
# Run with debug mode
python -m crackerjack run --ai-debug --run-tests -c

# Look for log lines like:
# "Selected RefactoringAgent (priority 10, confidence 0.90)"
# NOT "Selected ArchitectAgent (priority 50, confidence 0.10)"
```

---

## Rollback Plan

If issues arise, revert changes:

```bash
# Rollback coordinator.py
git checkout HEAD -- crackerjack/agents/coordinator.py

# Rollback agent files
git checkout HEAD -- crackerjack/agents/base.py
git checkout HEAD -- crackerjack/agents/refactoring_agent.py
git checkout HEAD -- crackerjack/agents/architect_agent.py

# Reapply only Phase 1 (ISSUE_TYPE_TO_AGENTS fix)
# Edit coordinator.py line 25:
# IssueType.TYPE_ERROR: ["RefactoringAgent", "ArchitectAgent"],
```

---

## Summary

### Phase 1: Immediate Fix (5 min)
- Fix ISSUE_TYPE_TO_AGENTS mapping
- Add RefactoringAgent to TYPE_ERROR list
- **Impact**: Immediate fix, low risk

### Phase 2: Architecture Cleanup (1 hour)
- Add priority property to SubAgent
- Implement priority-based selection
- Remove overlapping claims from ArchitectAgent
- **Impact**: Long-term maintainability, prevents future issues

### Phase 3: Fallback Chain (1 hour)
- Implement fallback mechanism
- Remove built-in preference logic
- Add comprehensive tests
- **Impact**: Robustness, automatic fallback on failure

### Total Time: ~2 hours
### Risk Level: Low
### Expected Impact: 70-90% issue reduction (from 0%)
