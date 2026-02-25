# Multi-Agent AI Fix Quality System Design

**Date:** 2025-02-12
**Status:** Approved for Implementation
**Author:** Claude + User Collaboration

## Problem Statement

The current AI-fix workflow has a **2.7% success rate** on comprehensive hooks, with agents generating broken Python code:

- 108 syntax errors per run
- Duplicate definitions, incomplete code blocks, unclosed parentheses
- Misplaced `from __future__` imports
- More iterations = more damage (negative progress)

**Root Cause:** Agents generate code in isolation without:

1. Reading full file context
1. Validating generated code before applying
1. Understanding Python syntax rules
1. Iterating with feedback

**Key Insight:** Manual CLI fixes work 100% of the time because they follow a systematic workflow that agents don't replicate.

## Solution: 4-Layer Architecture

A layered system where each layer adds validation and fallback capabilities, building on successful CLI workflows.

### Layer 1: Read-First Foundation

**Purpose:** Ensure every agent has full context before generating code.

**Requirements:**

- All agents MUST read full file before `_generate_fix()`
- Use `Edit` tool exclusively (syntax-validating)
- Enforce minimal diff size (< 50 lines per fix)
- Context passed to all generation steps

**Implementation:**

```python
async def fix_issue(self, issue: Issue) -> FixResult:
    # 1. Read full file context (MANDATORY)
    file_content = await self._read_file_context(issue.file_path)

    # 2. Generate fix using context
    fix = await self._generate_fix(issue, file_content)

    # 3. Apply using Edit tool (syntax-validating)
    result = await self._apply_fix_with_edit(fix)

    # 4. Validate syntax
    if not self._validate_syntax(result):
        return await self._retry_with_more_context(issue)
```

### Layer 2: Two-Stage Pipeline

**Purpose:** Separate planning from execution to validate fixes before they break code.

**Architecture:**

```
STAGE 1: Analysis Team
├── ContextAgent: Reads file, extracts relevant context
├── PatternAgent: Identifies anti-patterns to avoid
└── PlanningAgent: Creates minimal fix plan

Output: FixPlan object (NOT code yet)
    - file_path: str
    - issue_type: str
    - proposed_changes: list[ChangeSpec]
    - rationale: str
    - risk_level: "low" | "medium" | "high"

↓ [Plan Validation by Power Trio]

STAGE 2: Fixer Team
├── RefactoringAgent: Executes complexity fixes
├── ArchitectAgent: Executes architectural fixes
├── SecurityAgent: Executes security fixes
└── FormattingAgent: Executes style fixes

Constraint: MUST execute exactly what plan specifies
```

**Key Innovation:** Plans are validated by a different agent team than created them (Power Trio validation).

**Data Structures:**

```python
@dataclass
class ChangeSpec:
    """Atomic change specification."""
    line_range: tuple[int, int]  # (start, end)
    old_code: str
    new_code: str
    reason: str

@dataclass
class FixPlan:
    """Validated fix plan."""
    file_path: str
    issue_type: str
    changes: list[ChangeSpec]
    rationale: str
    risk_level: str
    validated_by: str  # Which agent validated this plan
```

### Layer 3: Interactive Fix Loop

**Purpose:** Implement continuous validation and retry logic, mimicking successful manual CLI workflow.

**The Fix Loop Pattern:**

```
┌─────────────────────────────────────────┐
│ INTERACTIVE FIX LOOP (per fix attempt)  │
├─────────────────────────────────────────┤
│ 1. READ        ← Read full file (L1)    │
│ 2. GENERATE    ← Create fix from plan   │
│ 3. VALIDATE    ← Run ALL validators     │
│ 4. APPLY       ← If ANY check passes    │
│ 5. VERIFY      ← Post-apply validation  │
│                                         │
│ If ALL fail → RETRY with feedback       │
│ (max 3 retries per fix)                 │
└─────────────────────────────────────────┘
```

**Power Trio Validation Teams:**

| Validation Type | Validator Agent | Checks |
|----------------|-----------------|--------|
| **Syntax** | `SyntaxValidator` | AST parse, compile check, parenthesis matching |
| **Logic** | `LogicChecker` | Pattern compliance, duplicate detection, import rules |
| **Behavior** | `BehaviorValidator` | Test execution, side-effect detection |

**Critical Decision: Permissive Validation**

Apply fix if **ANY** validation passes (not ALL):

```python
syntax_result = await self.syntax_validator.validate(fix)
logic_result = await self.logic_checker.validate(fix)
behavior_result = await self.behavior_validator.validate(fix)

# Apply if ANY validation passes
if any(r.valid for r in [syntax_result, logic_result, behavior_result]):
    return await self._apply_fix(fix)

# Only retry if ALL fail
if attempt < max_retries:
    feedback = self._combine_feedback(all_results)
    plan = self._add_feedback(plan, feedback)
    continue  # Retry
```

**Validation Matrix:**

| Syntax | Logic | Behavior | Action |
|--------|-------|----------|--------|
| ✅ | ✅ | ✅ | APPLY (ideal) |
| ✅ | ✅ | ❌ | APPLY (tests might not exist) |
| ✅ | ❌ | ✅ | APPLY (minor style issue) |
| ✅ | ❌ | ❌ | APPLY (syntax valid) |
| ❌ | ✅ | ✅ | APPLY (logic correct) |
| ❌ | ✅ | ❌ | RETRY (ambiguous) |
| ❌ | ❌ | ✅ | RETRY (ambiguous) |
| ❌ | ❌ | ❌ | RETRY (clear failure) |

### Layer 4: Fallback Wrapper

**Purpose:** When all else fails, fall back to direct Claude Code API calls that use the same workflow as successful manual CLI fixes.

**Fallback Trigger Conditions:**

- Syntax validation fails 3 times in a row
- Logic validation fails 2 times in a row
- Agent returns "I don't know how to fix this"
- Generated fix > 100 lines (too risky)
- User explicitly requests fallback (`--prefer-manual` flag)

**Implementation:**

```python
class FallbackOrchestrator:
    """Fallback to direct Claude Code API when agents fail."""

    async def fix_with_fallback(
        self,
        issue: Issue,
        failed_attempts: list[FixAttempt]
    ) -> FixResult:
        # Try agent-based fixing first (Layers 1-3)
        agent_result = await self._try_agent_fix(issue)
        if agent_result.success:
            return agent_result

        # Build context from failures
        context = self._build_fallback_context(issue, failed_attempts)

        # Call Claude Code directly (same as manual CLI)
        claude_result = await self._call_claude_code_direct(context)

        # Learn from success
        if claude_result.success:
            await self._store_successful_pattern(issue, failed_attempts, claude_result.fix)

        return claude_result
```

**The Learning Loop:**

Every successful fallback teaches the agents:

1. Store successful fix pattern
1. Update agent prompts for next time
1. Reduce fallback usage over time

## Implementation Phases

### Phase 1: Foundation (Layer 1)

- Modify `ProactiveAgent` base class
- Add `_read_file_context()` method
- Enforce Edit tool usage
- Add syntax validation

### Phase 2: Planning System (Layer 2)

- Create `FixPlan` and `ChangeSpec` dataclasses
- Implement Analysis Team agents
- Implement Fixer Team agents
- Add plan validation step

### Phase 3: Validation Loop (Layer 3)

- Implement Power Trio validators
- Add validation loop logic
- Implement permissive validation
- Add retry with feedback

### Phase 4: Fallback System (Layer 4)

- Implement `FallbackOrchestrator`
- Add Claude Code direct API integration
- Implement learning loop
- Add pattern library

### Phase 5: Integration & Testing

- Integrate all layers into `AutofixCoordinator`
- Update existing agents to use new workflow
- Add comprehensive tests
- Performance benchmarking

## Success Metrics

**Current State:**

- Fast hooks: 100% success (16/16) ✅
- Comprehensive hooks: 2.7% success ❌
- 108 syntax errors per run ❌

**Target State:**

- Fast hooks: Maintain 100% success
- Comprehensive hooks: 80%+ success
- Fallback usage: < 20% initially, decreasing over time
- Syntax errors: < 5 per run
- Code quality: All fixes validated before application

## Research Sources

This design is based on current research and best practices:

- [SagaLLM: Context Management, Validation, and Transaction](https://www.vldb.org/pvldb/vol18/p4874-chang.pdf) - Multi-agent validation
- [Rethinking Code Migration with LLM-based Agents](https://arxiv.org/html/2602.09944v1) - 4-stage collaborative loop (Feb 11, 2025)
- [Multi-Agent LLM Code Generation for Tabular QA](https://aclanthology.org/) - Framework separation
- [5 Best Practices for Reviewing AI-Generated Code](https://brightsec.com/blog/5-best-practices-for-reviewing-and-approving-ai-generated-code/) - Untrusted by default
- [AI Coding Best Practices in 2025](https://dev.to/ranndy360/ai-coding-best-practices-in-2025-4eel) - Small increments
- [Addy Osmani's LLM Coding Practices](https://addyosmani.com/) - Claude Code practices
