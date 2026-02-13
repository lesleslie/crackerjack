# CLAUDE Working Protocols

Comprehensive guide to protocols for working with Crackerjack codebase.

> **For architecture overview**, see [CLAUDE_ARCHITECTURE.md](./CLAUDE_ARCHITECTURE.md)
> **For quick commands**, see [CLAUDE_QUICKSTART.md](./CLAUDE_QUICKSTART.md)
> **For code patterns**, see [CLAUDE_PATTERNS.md](./CLAUDE_PATTERNS.md)

## Table of Contents

- [Code Review Protocol](#code-review-protocol)
- [Agent Selection Protocol](#agent-selection-protocol)
- [Evidence Protocol](#evidence-protocol)
- [Architecture Compliance Protocol](#architecture-compliance-protocol)
- [Quality Decision Framework](#quality-decision-framework-fix-now-or-later)

## Code Review Protocol

**Purpose**: Ensure systematic, comprehensive review of code changes, PRs, and implementations.

### Protocol Steps

#### 1. READ FULL CONTEXT

- Read entire modified files before suggesting changes
- Check imports against `pyproject.toml` dependencies
- Verify architectural compliance with protocol-based design
- **Verification**: Can you explain what code does without looking at it again?

```bash
# Dependency verification
uv pip check  # Should pass without errors
```

#### 2. VALIDATE ARCHITECTURAL COMPLIANCE

- Check imports: `from crackerjack.models.protocols import ...` ✅
- Check constructor injection: all dependencies via `__init__`
- Check no legacy patterns: no `depends.set()`, no global singletons
- **Verification**: Run grep to check for direct class imports

```bash
# Should return empty (all imports use protocols)
grep -r "from crackerjack" crackerjack/ --include="*.py" | grep -v protocols | grep -v __pycache__
```

#### 3. VERIFY DEPENDENCIES

- Every new import has corresponding entry in `pyproject.toml`
- Version constraints specified if needed
- No undeclared dependencies

#### 4. CHECK QUALITY STANDARDS

- Complexity ≤15 per function (run `python -m crackerjack run --comprehensive`)
- No hardcoded paths or placeholders
- Type annotations present
- **Verification**: Quality gates pass, no complexity warnings

#### 5. VALIDATE TESTS

- New code has corresponding tests
- Coverage not decreased (ratchet system)
- Tests use synchronous patterns where possible
- **Verification**: `python -m crackerjack run --run-tests` passes

#### 6. RUN QUALITY GATES

- Execute full quality workflow: `python -m crackerjack run --run-tests -c`
- Review ALL failures, not just first one
- Fix issues before claiming "done"
- **Verification**: Exit code 0, no failures

#### 7. PROVIDE EVIDENCE

- Reference specific files and line numbers
- Show code snippets for claims
- Never guess or assume
- **Verification**: Every claim has `[filename]:[line]` evidence

### When to Use This Protocol

✅ **Use:**

- Before suggesting code changes
- After implementing features
- When reviewing PRs
- Before claiming work is "complete"

❌ **Not for:**

- Simple typo fixes or obvious bugs
- Questions that don't require code analysis
- Documentation-only changes

## Agent Selection Protocol

**Purpose**: Ensure appropriate use of 83 global AI agents + 12 Crackerjack agents for task-specific expertise.

### Crackerjack's 12 AI Agents

1. **RefactoringAgent** (0.9): Complexity ≤15, dead code removal
1. **PerformanceAgent** (0.85): O(n²) detection, optimization
1. **SecurityAgent** (0.8): Hardcoded paths, unsafe operations
1. **DocumentationAgent** (0.8): Changelog, .md consistency
1. **TestCreationAgent** (0.8): Test failures, fixtures
1. **DRYAgent** (0.8): Code duplication patterns
1. **FormattingAgent** (0.8): Style violations, imports
1. **ImportOptimizationAgent**: Import cleanup, reorganization
1. **TestSpecialistAgent** (0.8): Advanced testing scenarios
1. **SemanticAgent** (0.85): Semantic analysis, code comprehension
1. **ArchitectAgent** (0.85): Architecture patterns, design recommendations
1. **EnhancedProactiveAgent** (0.9): Proactive prevention, predictive monitoring

### Global Agent Ecosystem

**Available via Task tool** - 83 specialized agents in `/Users/les/.claude/agents/`:

**Categories:**

- **Programming Languages** (8): Python, JavaScript, TypeScript, Go, Rust, Java, C/C++
- **Databases & Storage** (9): PostgreSQL, MySQL, SQLite, Redis, Vector DBs
- **AI & ML** (4): Gemini AI, Vector embeddings, General AI/ML
- **Communication Protocols** (4): WebSocket, gRPC, GraphQL, REST APIs
- **Frontend & Design** (8): React/Vue, HTMX, CSS, Web Components
- **Backend & Architecture** (6): Backend design, authentication, microservices
- **DevOps & Infrastructure** (8): Docker, Terraform, cloud platforms, Kubernetes
- **Testing & Quality** (5): Testing, pytest, coverage, quality validation
- **Security & Compliance** (3): Security auditing, authentication, privacy

### Key Selection Rules

1. **Language-Specific Tasks** → Use language specialists

   - Python → `python-pro`
   - JavaScript/TypeScript → `javascript-pro`, `typescript-pro`
   - Go → `golang-pro`
   - Rust → `rust-pro`
   - Java → `java-pro`

1. **Database & Storage** → Use database specialists

   - PostgreSQL → `postgresql-specialist`
   - SQLite → `sqlite-specialist`
   - Vector Search → `vector-database-specialist`

1. **Infrastructure & DevOps** → Use infrastructure specialists

   - Docker → `docker-specialist`
   - Kubernetes → `kubernetes-specialist`
   - Monitoring → `observability-incident-lead`

1. **Testing & Quality** → Use quality specialists

   - Code Review → `code-reviewer` or `superpowers:code-reviewer`
   - pytest → `pytest-hypothesis-specialist`
   - Test Coverage → `test-coverage-review-specialist`

1. **Security** → Use security specialists

   - Security Audit → `security-auditor`
   - Authentication → `authentication-specialist`
   - Privacy → `privacy-officer`

1. **Architecture & Design** → Use architecture specialists

   - Feature Architecture → `feature-dev:code-architect`
   - System Architecture → `architecture-council`
   - Frontend Design → `frontend-developer`

### Usage Protocol

```python
# ✅ Correct pattern - specific specialist
Task(subagent_type="python-pro", prompt="Review this Python code for security issues")

# ❌ WRONG - generalist for specialist task
Task(
    subagent_type="general-assistant",
    prompt="Review this Python code for security issues",
)
```

### Workflows vs Agents

- Complex multi-phase task → Use workflows (check `/workflows:WORKFLOW-CATALOG`)
- Feature delivery → `feature-dev:feature-dev`
- PR review → `pr-review-toolkit:review-pr`
- Architecture planning → `Plan` agent (not Task)

## Evidence Protocol

**Purpose**: Ensure all claims, assertions, and responses are backed by specific, verifiable code evidence.

### Format 1: Implementation Status

*When user asks "Is X implemented?"*

````markdown
Looking at [filename] (lines [start]-[end]):

```python
[code snippet]
````

[Explanation of what this shows]

````

### Format 2: Code Review Findings

*When identifying issues or violations*

```markdown
**Issue**: [Brief description]
**Location**: [filename]:[line]
**Evidence**:
```python
[problematic code]
````

**Impact**: [What problem this causes]
**Fix**: [Specific fix]

````

### Format 3: Verification Claims

*When claiming something is "fixed" or "done"*

```markdown
**Verification**: [what was verified]
**Method**: [how verification was performed]
**Evidence**: [output, logs, or test results]
**Status**: ✅ Verified / ❌ Failed
````

### Mandatory Evidence For

✅ **Required for:**

- Implementation status claims
- Architecture compliance assertions
- Bug fix verification
- Performance improvements
- Security assessments
- Test coverage changes

❌ **No evidence required for:**

- Straightforward questions
- Opinion-based requests
- Documentation/explanation requests (unless citing specific behavior)

## Architecture Compliance Protocol

**Purpose**: Systematic verification that code follows Crackerjack's protocol-based architecture.

### Compliance Checklist

#### 1. IMPORT COMPLIANCE

- All imports use protocols from `models/protocols.py`
- No direct class imports from other crackerjack modules
- **Verification**: Should return empty

```bash
grep -r "from crackerjack" crackerjack/ --include="*.py" | grep -v protocols | grep -v __pycache__
```

#### 2. CONSTRUCTOR INJECTION

- All dependencies injected via `__init__`
- No factory functions like `get_test_manager()`
- No module-level singletons

```python
# ✅ Correct - Constructor injection
def __init__(
    self,
    console: Console,
    cache: CrackerjackCache,
) -> None:
    self.console = console
    self.cache = cache


# ❌ WRONG - Factory function
self.tracker = get_agent_tracker()
self.timeout_manager = get_timeout_manager()
```

#### 3. PROTOCOL DEFINITIONS

- Custom types defined as protocols in `models/protocols.py`
- All protocol methods have type annotations
- `@runtime_checkable` decorator if using `isinstance()`

#### 4. LIFECYCLE MANAGEMENT

- No global state
- Proper cleanup patterns (context managers or explicit teardown)
- Resource management handled correctly

#### 5. NO LEGACY PATTERNS

- No `depends.set()` patterns (except in CLI handlers)
- No DI container usage
- No `@inject` decorators from old framework
- **Verification**: Should return empty

```bash
grep -r "depends\." crackerjack/ --include="*.py"
```

### Non-Compliance Response

When architecture violations are found:

1. Document issue with specific location and evidence
1. Explain why it matters (impact on architecture, testing, maintenance)
1. Provide correct pattern example
1. Offer to refactor

### Integration with Quality Gates

- **Automated checks**: `python -m crackerjack run -c`

  - Import verification
  - Complexity checking
  - Type checking

- **Manual checks**: Constructor injection, protocol definitions, lifecycle management

- **Protocol**: Always run automated checks BEFORE claiming architectural compliance

## Quality Decision Framework: "Fix Now or Later?"

**Purpose**: Unified decision framework for when to fix issues immediately vs. defer them.

### Quick Decision Matrix

| Issue Type | Not Touching Code | Touching Right Now | Action |
|------------|-------------------|-------------------|--------|
| Quality gates/tests failing | → | → | **FIX NOW** (Blocker) |
| Complexity >15 | File issue | → | **FIX NOW** (While-Here) |
| Known bottleneck (has evidence) | → | → | **FIX NOW** (Critical) |
| "Could be better" (no evidence) | → | → | **DEFER** (YAGNI) |

### Fix Now Categories

#### BLOCKERS (Never proceed without fixing)

- ✅ Test failures → Fix before adding features
- ✅ Complexity >15 → Refactor immediately
- ✅ Coverage decrease → Restore baseline first
- ✅ Quality gate failures → Fix ALL failures
- ✅ Architecture violations → Protocol-based design compliance
- ✅ Security issues → Fix immediately, never defer

**Verification**: `python -m crackerjack run --run-tests -c` passes

#### WHILE-HERE FIXES (Fix when touching code)

- ✅ Nearby complexity issues (you're already there)
- ✅ Improve readability while you understand code
- ✅ Add missing tests for code you're modifying
- ✅ Update outdated comments/documentation
- ✅ Fix architectural violations in same file

**Protocol**: "I'm already touching this code, fix nearby issues too"

#### CRITICAL ISSUES (Fix even if not touching)

- ✅ Confirmed performance bottlenecks (requires profiling evidence)
- ✅ Security vulnerabilities (CVE reports, security audits)
- ✅ Data loss risks, race conditions, memory leaks

**Evidence Required**: Document impact with metrics/data before treating as critical

### Defer Categories

#### PERFORMANCE OPTIMIZATIONS (Without evidence)

- ❌ "This function looks slow" (no measurements)
- ❌ "I'll cache this result" (no evidence it's called frequently)
- **Protocol**: Profile first, confirm bottleneck, then optimize

#### NICE-TO-HAVE REFACTORING (Not touching code)

- ❌ "This function could be more elegant" (but works fine)
- ❌ "I prefer a different pattern" (personal preference)
- **Protocol**: File issue for future consideration

#### SPECULATIVE IMPROVEMENTS (YAGNI violations)

- ❌ "Let's add this parameter in case we need it"
- ❌ "I'll make this flexible for future use cases"
- **Protocol**: "You Aren't Gonna Need It" - wait for actual requirement

### Protocol Checklist

```markdown
[ ] Does it break quality gates or tests?
    → YES: Fix now (Blocker)

[ ] Am I already touching this code right now?
    → YES: Fix now (While-Here)

[ ] Is there profiling/evidence it's a critical bottleneck?
    → YES: Fix now (Critical), document evidence

[ ] Is it just "could be better" without evidence?
    → YES: Defer/Ignore (YAGNI/KISS)

[ ] Have I run quality gates after my fixes?
    → Verification: python -m crackerjack run --run-tests -c
```

### Anti-Patterns to Avoid

- ❌ "I'll fix it later" (for blockers) → Compound failures
- ❌ Premature optimization → No measurements, unnecessary complexity
- ❌ Refactoring spree → Rewriting working code without understanding
- ❌ "While I'm here" trap → Came for typo, stayed for 4 hours refactoring

**Key Insight**: Fix what's broken, what you're touching, or what's proven critical. Defer everything else.

## See Also

- **[CLAUDE_ARCHITECTURE.md](./CLAUDE_ARCHITECTURE.md)**: Directory structure and layers
- **[CLAUDE_QUICKSTART.md](./CLAUDE_QUICKSTART.md)**: Commands and common tasks
- **[CLAUDE_PATTERNS.md](./CLAUDE_PATTERNS.md)**: Code standards and conventions
- **[README.md](./README.md)**: Complete project documentation
