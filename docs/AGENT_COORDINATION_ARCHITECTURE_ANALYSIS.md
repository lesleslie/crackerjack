# Agent Coordination Architecture Analysis

## Executive Summary

**Current Problem**: TYPE_ERROR issues are routed to ArchitectAgent with confidence 0.1 (effectively 0.0 after threshold checks), despite RefactoringAgent being capable of handling them with confidence 0.7-0.9. Result: 0% issue reduction.

**Root Cause**: Multiple architectural flaws in agent selection algorithm

**Impact**: System fails to fix issues despite having capable agents

---

## Problem Analysis

### 1. The Selection Algorithm Flaw

**Location**: `crackerjack/agents/coordinator.py:202-212`

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

**Issue**: The algorithm has TWO problems:

1. **Issue Type Filter First** (line 153-166):
   ```python
   # Only considers agents in ISSUE_TYPE_TO_AGENTS mapping
   preferred_agent_names = ISSUE_TYPE_TO_AGENTS.get(issue_type, [])
   specialist_agents = [
       agent for agent in self.agents
       if agent.__class__.__name__ in preferred_agent_names
   ]
   ```

2. **Then Score Within Filtered Set** (line 214-228):
   ```python
   async def _score_all_specialists(
       self,
       specialists: list[SubAgent],
       issue: Issue,
   ) -> list[tuple[SubAgent, float]]:
       candidates: list[tuple[SubAgent, float]] = []
       for agent in specialists:
           score = await agent.can_handle(issue)
           candidates.append((agent, score))
       return candidates
   ```

### 2. The Mapping Configuration Error

**Location**: `crackerjack/agents/coordinator.py:23-52`

```python
ISSUE_TYPE_TO_AGENTS: dict[IssueType, list[str]] = {
    IssueType.FORMATTING: ["FormattingAgent", "ArchitectAgent"],
    IssueType.TYPE_ERROR: ["ArchitectAgent"],  # ❌ RefactoringAgent MISSING!
    # ... other types
}
```

**Problem**: RefactoringAgent is NOT listed for TYPE_ERROR, so it's never considered.

### 3. The Confidence Mismatch

**RefactoringAgent** (lines 75-76):
```python
if issue.type == IssueType.TYPE_ERROR:
    return await self._is_fixable_type_error(issue)  # Returns 0.7-0.9
```

**ArchitectAgent** (lines 40-41):
```python
if issue.type == IssueType.TYPE_ERROR:
    return 0.1  # Let RefactoringAgent handle it
```

**Result**: ArchitectAgent returns 0.1, but since RefactoringAgent isn't in the filtered list, ArchitectAgent wins by default with 0.1, which then fails.

---

## Architectural Design Issues

### Issue 1: Dual Source of Truth

**Problem**: Issue type support is defined in TWO places:

1. **ISSUE_TYPE_TO_AGENTS mapping** (coordinator.py:23)
2. **agent.get_supported_types()** (each agent)

**Why This Is Bad**:
- Mapping can get out of sync with actual agent capabilities
- RefactoringAgent.get_supported_types() returns TYPE_ERROR, but mapping doesn't include it
- No validation ensures consistency

### Issue 2: Priority vs Confidence Selection

**Current Design**: Pure confidence-based selection within filtered list

**Problem**: When list is wrong (missing RefactoringAgent), system fails silently

**Example**:
- Filtered agents: [ArchitectAgent] only
- ArchitectAgent.can_handle() returns 0.1
- RefactoringAgent.can_handle() would return 0.9, but never gets called
- System picks ArchitectAgent with 0.1 → fails

### Issue 3: Overlapping Issue Type Ownership

**Problem**: Both agents claim TYPE_ERROR support:

```python
# RefactoringAgent (refactoring_agent.py:68)
def get_supported_types(self) -> set[IssueType]:
    return {IssueType.COMPLEXITY, IssueType.DEAD_CODE, IssueType.TYPE_ERROR}

# ArchitectAgent (architect_agent.py:27-28)
def get_supported_types(self) -> set[IssueType]:
    return {
        IssueType.TYPE_ERROR,  # Claims support
        IssueType.TEST_ORGANIZATION,
    }
```

**ArchitectAgent's Intent** (line 40-41):
```python
if issue.type == IssueType.TYPE_ERROR:
    return 0.1  # Let RefactoringAgent handle it
```

**Problem**: ArchitectAgent claims TYPE_ERROR in get_supported_types() but returns 0.1 confidence, creating confusion about actual ownership.

### Issue 4: No Fallback Mechanism

**Problem**: When ArchitectAgent fails with 0.1 confidence, system doesn't try RefactoringAgent.

**Missing Pattern**:
- Try primary agent (ArchitectAgent)
- If confidence < threshold OR execution fails
- Try fallback agent (RefactoringAgent)
- No such fallback chain exists

---

## Architectural Recommendations

### Recommendation 1: Eliminate ISSUE_TYPE_TO_AGENTS Mapping

**Rationale**: Single source of truth should be `agent.get_supported_types()`

**Implementation**:

```python
# ❌ REMOVE THIS
ISSUE_TYPE_TO_AGENTS: dict[IssueType, list[str]] = {
    IssueType.TYPE_ERROR: ["ArchitectAgent"],  # Wrong!
    # ...
}

# ✅ REPLACE WITH
async def _find_specialist_agents(self, issue_type: IssueType) -> list[SubAgent]:
    """Find all agents that support this issue type."""
    return [
        agent for agent in self.agents
        if issue_type in agent.get_supported_types()
    ]
```

**Benefits**:
- Single source of truth
- Automatically discovers all capable agents
- Can't get out of sync

---

### Recommendation 2: Implement Priority-Based Selection

**Rationale**: Some agents should be tried before others, even if both claim support.

**Implementation**:

```python
# Add priority to agents
class SubAgent(ABC):
    @property
    def priority(self) -> int:
        """Lower number = higher priority (tried first)."""
        return 100  # Default priority

    @abstractmethod
    async def can_handle(self, issue: Issue) -> float:
        """Confidence score (0.0-1.0)."""
        pass


# RefactoringAgent sets higher priority
class RefactoringAgent(SubAgent):
    @property
    def priority(self) -> int:
        return 10  # Try RefactoringAgent first for TYPE_ERROR


# ArchitectAgent sets lower priority
class ArchitectAgent(SubAgent):
    @property
    def priority(self) -> int:
        return 50  # Fallback after specialists fail


# Selection algorithm
async def _find_best_specialist(
    self,
    specialists: list[SubAgent],
    issue: Issue,
) -> SubAgent | None:
    # Group by priority
    by_priority = sorted(specialists, key=lambda a: a.priority)

    # Try each priority level
    for priority_group in self._group_by_priority(by_priority):
        candidates = await self._score_all_specialists(priority_group, issue)

        best_agent, best_score = self._find_highest_scoring_agent(candidates)

        # If best agent in this priority level has sufficient confidence, use it
        if best_score >= 0.5:
            return best_agent

        # Otherwise, try next priority level

    return None  # No agent could handle it
```

**Benefits**:
- Clear ownership hierarchy
- RefactoringAgent tried before ArchitectAgent
- ArchitectAgent acts as fallback
- No hardcoded mappings needed

---

### Recommendation 3: Fix ArchitectAgent's TYPE_ERROR Claim

**Option A: Remove Claim** (Recommended)

```python
# architect_agent.py
def get_supported_types(self) -> set[IssueType]:
    """Return issue types handled by this agent.

    ArchitectAgent delegates TYPE_ERROR to RefactoringAgent.
    """
    return {
        # IssueType.TYPE_ERROR,  # ❌ Remove - delegated to RefactoringAgent
        IssueType.TEST_ORGANIZATION,
    }

async def can_handle(self, issue: Issue) -> float:
    """Check if we can handle this issue."""
    if issue.type == IssueType.TEST_ORGANIZATION:
        return 0.1
    return 0.0
```

**Option B: Keep Claim But Delegate in analyze_and_fix**

```python
# architect_agent.py
def get_supported_types(self) -> set[IssueType]:
    return {
        IssueType.TYPE_ERROR,  # ✅ Keep - we delegate it
        IssueType.TEST_ORGANIZATION,
    }

async def analyze_and_fix(self, issue: Issue) -> FixResult:
    # Delegate to RefactoringAgent
    if issue.type == IssueType.TYPE_ERROR:
        self.log(f"Delegating TYPE_ERROR to RefactoringAgent")
        return await self._refactoring_agent.analyze_and_fix(issue)

    # Handle other types
    return await self.analyze_and_fix_proactively(issue)
```

**Recommendation**: Option A (remove claim) is cleaner - ArchitectAgent shouldn't claim types it delegates.

---

### Recommendation 4: Implement Fallback Chain

**Rationale**: When primary agent fails, try fallback agents before giving up.

**Implementation**:

```python
async def _handle_with_single_agent(
    self,
    agent: SubAgent,
    issue: Issue,
) -> FixResult:
    """Try to handle issue with agent, using fallbacks if needed."""
    self.logger.info(f"Attempting {agent.name} for issue: {issue.message[:100]}")

    confidence = await agent.can_handle(issue)

    # Skip if confidence too low
    if confidence < 0.3:
        self.logger.info(f"{agent.name} confidence too low ({confidence:.2f}), trying fallback")
        return await self._try_fallback_agents(agent, issue)

    # Try the agent
    result = await self._execute_agent(agent, issue)

    # If failed, try fallbacks
    if not result.success:
        self.logger.info(f"{agent.name} failed, trying fallback agents")
        return await self._try_fallback_agents(agent, issue)

    return result


async def _try_fallback_agents(
    self,
    failed_agent: SubAgent,
    issue: Issue,
) -> FixResult:
    """Try alternative agents for this issue type."""
    fallback_candidates = [
        agent for agent in self.agents
        if agent != failed_agent
        and issue.type in agent.get_supported_types()
    ]

    for fallback in fallback_candidates:
        self.logger.info(f"Trying fallback agent {fallback.name}")

        confidence = await fallback.can_handle(issue)
        if confidence < 0.3:
            continue

        result = await self._execute_agent(fallback, issue)
        if result.success:
            self.logger.info(f"Fallback agent {fallback.name} succeeded")
            return result

    # All fallbacks failed
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"All agents failed for {issue.type.value}"],
    )
```

**Benefits**:
- Automatic fallback when primary agent fails
- Maximizes chance of successful fix
- No manual fallback configuration needed

---

### Recommendation 5: Exclusive Issue Type Ownership

**Rationale**: Each issue type should have ONE primary owner to avoid confusion.

**Implementation**:

```python
# crackerjack/agents/issue_type_owners.py
"""Define exclusive ownership of issue types.

Each issue type has exactly one PRIMARY owner.
Other agents can only handle if explicitly delegated by primary owner.
"""

ISSUE_TYPE_OWNERSHIP: dict[IssueType, str] = {
    IssueType.FORMATTING: "FormattingAgent",
    IssueType.TYPE_ERROR: "RefactoringAgent",  # ✅ Clear owner
    IssueType.SECURITY: "SecurityAgent",
    IssueType.TEST_FAILURE: "TestSpecialistAgent",
    IssueType.IMPORT_ERROR: "ImportOptimizationAgent",
    IssueType.COMPLEXITY: "RefactoringAgent",
    IssueType.DEAD_CODE: "RefactoringAgent",
    IssueType.DEPENDENCY: "TestCreationAgent",
    IssueType.DRY_VIOLATION: "DRYAgent",
    IssueType.PERFORMANCE: "PerformanceAgent",
    IssueType.DOCUMENTATION: "DocumentationAgent",
    IssueType.TEST_ORGANIZATION: "TestCreationAgent",
}


# Validation in coordinator
def __init__(self, ...) -> None:
    self._validate_ownership_consistency()

def _validate_ownership_consistency(self) -> None:
    """Ensure ownership map matches actual agent capabilities."""
    for issue_type, owner_name in ISSUE_TYPE_OWNERSHIP.items():
        owner = next(
            (a for a in self.agents if a.__class__.__name__ == owner_name),
            None,
        )

        if not owner:
            raise ValueError(f"Owner {owner_name} not found for {issue_type.value}")

        if issue_type not in owner.get_supported_types():
            raise ValueError(
                f"Owner {owner_name} doesn't support {issue_type.value}"
            )

        # Check no other agent claims this type (except owner)
        for agent in self.agents:
            if agent != owner and issue_type in agent.get_supported_types():
                self.logger.warning(
                    f"{agent.name} claims {issue_type.value} but "
                    f"{owner_name} is the owner. This may cause conflicts."
                )
```

**Benefits**:
- Clear responsibility for each issue type
- Validation prevents ownership drift
- Easy to understand who handles what
- Conflicting claims detected at startup

---

## Recommended Solution: Combined Approach

### Phase 1: Immediate Fix (Critical Path)

**Action**: Fix ISSUE_TYPE_TO_AGENTS mapping

```python
# coordinator.py line 25
ISSUE_TYPE_TO_AGENTS: dict[IssueType, list[str]] = {
    IssueType.TYPE_ERROR: ["RefactoringAgent", "ArchitectAgent"],  # ✅ Add RefactoringAgent first
    # ...
}
```

**Impact**: Immediate fix, RefactoringAgent will be selected

**Risk**: None - just adding missing agent to list

---

### Phase 2: Architecture Cleanup (Recommended)

**Actions**:

1. **Remove ISSUE_TYPE_TO_AGENTS mapping**
2. **Use agent.get_supported_types() as single source of truth**
3. **Add priority property to SubAgent**
4. **Implement priority-based selection**

**Benefits**:
- Eliminates dual source of truth
- Clear ownership hierarchy
- Can't get out of sync
- More maintainable

**Risk**: Medium - requires testing to ensure fallback behavior works

---

### Phase 3: Long-Term Architecture (Best Practice)

**Actions**:

1. **Implement ISSUE_TYPE_OWNERSHIP map**
2. **Add validation at startup**
3. **Remove overlapping claims**
4. **ArchitectAgent removes TYPE_ERROR claim**
5. **Implement fallback chain**

**Benefits**:
- Clear ownership prevents confusion
- Automatic fallback on failure
- Validation catches configuration errors
- Self-documenting architecture

**Risk**: Low - validation prevents bad states

---

## Testing Strategy

### Test Case 1: TYPE_ERROR Selection

```python
@pytest.mark.asyncio
async def test_type_error_selects_refactoring_agent():
    """TYPE_ERROR should select RefactoringAgent, not ArchitectAgent."""
    coordinator = AgentCoordinator(context, tracker, debugger)
    coordinator.initialize_agents()

    issue = Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.MEDIUM,
        message="missing return type",
    )

    result = await coordinator.handle_issues([issue])

    # Verify RefactoringAgent was called
    assert tracker.agent_calls["RefactoringAgent"] > 0
    assert tracker.agent_calls.get("ArchitectAgent", 0) == 0

    # Verify issue was fixed
    assert result.success
```

### Test Case 2: Fallback on Failure

```python
@pytest.mark.asyncio
async def test_fallback_when_primary_fails():
    """When primary agent fails, fallback should be tried."""
    # Mock RefactoringAgent to fail
    with mock.patch.object(
        RefactoringAgent,
        "analyze_and_fix",
        return_value=FixResult(success=False, confidence=0.0),
    ):
        coordinator = AgentCoordinator(context, tracker, debugger)
        coordinator.initialize_agents()

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="missing return type",
        )

        result = await coordinator.handle_issues([issue])

        # Verify fallback was tried
        assert tracker.agent_calls["ArchitectAgent"] > 0
```

### Test Case 3: Priority-Based Selection

```python
@pytest.mark.asyncio
async def test_priority_ordering():
    """Agents should be tried in priority order."""
    coordinator = AgentCoordinator(context, tracker, debugger)
    coordinator.initialize_agents()

    # Both agents claim TYPE_ERROR
    refactoring = coordinator.get_agent("RefactoringAgent")
    architect = coordinator.get_agent("ArchitectAgent")

    assert refactoring.priority < architect.priority  # RefactoringAgent first

    # Verify selection order
    issue = Issue(type=IssueType.TYPE_ERROR, ...)

    best = await coordinator._find_best_specialist([refactoring, architect], issue)

    assert best == refactoring  # Selected due to priority
```

---

## Conclusion

### Root Causes Identified

1. **Configuration Error**: ISSUE_TYPE_TO_AGENTS missing RefactoringAgent for TYPE_ERROR
2. **Dual Source of Truth**: Mapping vs get_supported_types() can diverge
3. **No Priority System**: All agents equal, no fallback hierarchy
4. **Overlapping Claims**: Both agents claim TYPE_ERROR, unclear who should win
5. **No Fallback**: When primary fails, system gives up instead of trying alternatives

### Recommended Actions

**Immediate** (5 minutes):
- Fix ISSUE_TYPE_TO_AGENTS mapping to include RefactoringAgent

**Short-term** (1 hour):
- Remove ISSUE_TYPE_TO_AGENTS, use get_supported_types() only
- Add priority property to agents
- Implement priority-based selection

**Long-term** (1 day):
- Implement ISSUE_TYPE_OWNERSHIP map
- Add validation at startup
- Implement fallback chain
- Remove overlapping claims from ArchitectAgent

### Expected Impact

**Before**: 0% issue reduction (ArchitectAgent with 0.1 confidence fails)

**After**: 70-90% issue reduction (RefactoringAgent with 0.7-0.9 confidence succeeds)

**Risk**: Low - changes are additive and backward compatible

---

## Code Examples

See sections above for complete implementation examples of:

- Priority-based selection algorithm
- Fallback chain implementation
- Ownership validation
- Test cases
