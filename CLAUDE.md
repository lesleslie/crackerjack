______________________________________________________________________

## status: active role: canonical date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

For a shorter, tool-neutral bootstrap document, start with `AGENTS.md`.

## Quick Links

For a shorter, tool-neutral bootstrap document, start with `AGENTS.md`.

| Want to... | Go to... |
|-------------|----------|
| **Understand codebase** | [Project Overview](#project-overview) → [Critical Architectural Pattern](#critical-architectural-pattern-protocol-based-design) |
| **Start development** | [Most Common Commands](#most-common-commands) → Daily workflow, testing, server management |
| **Run quality checks** | [Quality Process](#quality-process) → Fast vs comprehensive hooks |
| **AI-assisted auto-fix** | [AI-Assisted Auto-Fix (Workflow Tool — not a shell command)](#ai-assisted-auto-fix-workflow-tool--not-a-shell-command) → Workflow script and knobs |
| **Verify architecture** | [Critical Architectural Pattern](#critical-architectural-pattern-protocol-based-design) → Protocol-based DI verification |

## Project Overview

**Crackerjack** is an opinionated Python project management tool unifying UV, Ruff, pytest, and quality tools into a single workflow with AI agent integration via MCP.

**Key Dependencies**: Python 3.13+, UV, pytest

**IMPORTANT**: Crackerjack does **NOT** use pre-commit.com hooks. It runs its own native tool orchestration system that integrates directly with git. When we say "hooks" in crackerjack, we mean **quality tools that run during our workflow** (ruff, pytest, codespell, etc.) - NOT pre-commit.com hooks.

## Core Features

- **🧠 Proactive AI Architecture**: 12 specialized AI agents prevent issues before they occur
- **⚡ Autonomous Quality**: Intelligent auto-fixing with architectural planning
- **🛡️ Zero-Compromise Standards**: 100% test coverage target, complexity ≤15, security-first patterns
- **🔄 Learning System**: Skills tracking via session-buddy integration for agent recommendations
- **🌟 One Command Excellence**: From setup to PyPI publishing with unified workflow

**Philosophy**: If your code needs fixing after it's written, you're doing it wrong. We prevent problems through intelligent architecture and proactive patterns.

## Most Common Commands

```bash
# Daily development (quality + tests) - RECOMMENDED
python -m crackerjack run --run-tests

# Quality checks only
python -m crackerjack run

# With tests (no AI)
python -m crackerjack run --run-tests

# Single test
pytest tests/test_file.py::TestClass::test_method -v

# Server management
python -m crackerjack start|stop|restart|status|health

# Full release
python -m crackerjack run --all patch
```

### AI-Assisted Auto-Fix (Workflow Tool — not a shell command)

The ai-fix-loop is invoked through Claude Code's `Workflow` tool, not
the shell. The script lives at `.claude/workflows/ai-fix-loop.js` and
runs `crackerjack run -v` itself, so there's no separate `crackerjack
--ai-fix` flag.

Supported knobs (forwarded via `args`):

- `args.maxIterations` — cap on iterations (default 10; clamped to
  a minimum of 10 by the script)
- `args.initialIssueGuard` — abort if baseline issues exceed this
  (default 200)
- `args.auditLogPath` — JSONL output path (default
  `.crackerjack/audit/ai-fix-loop.jsonl`)

```js
// Example invocation (Workflow tool, NOT bash):
Workflow({
  scriptPath: '.claude/workflows/ai-fix-loop.js',
  args: { maxIterations: 10, initialIssueGuard: 200 }
})
```

For the design rationale and contract details, see the **AI Agent
System** section below.

## Critical Architectural Pattern: Protocol-Based Design

Crackerjack uses **protocol-based dependency injection** with constructor injection.

**THE MOST CRITICAL PATTERN**: Always import protocols, never concrete classes

```python
# ✅ GOLD STANDARD: Always import protocols
from crackerjack.models.protocols import Console, TestManagerProtocol


def __init__(
    self,
    console: Console,
    test_manager: TestManagerProtocol,
) -> None:
    """Constructor injection with protocol-based dependencies."""
    self.console = console
    self.test_manager = test_manager


# ❌ WRONG: Direct class imports
from crackerjack.managers.test_manager import TestManager
```

**CLI Handlers**: Use `@depends.inject()` decorator with `Inject[Protocol]` hints
**All other layers**: Constructor injection via `__init__`

**Verification**:

```bash
# Should return empty (all imports use protocols)
grep -r "from crackerjack" crackerjack/ --include="*.py" | grep -v protocols | grep -v __pycache__
```

## Critical Rules

### 1. NEVER MAKE UNAUTHORIZED CHANGES

- **ONLY** modify what is explicitly requested
- **NEVER** change unrelated code
- If you think something else needs changing, **ASK FIRST**

### 2. DEPENDENCY MANAGEMENT IS MANDATORY

- **ALWAYS** update `pyproject.toml` when adding imports
- **NEVER** add import statements without dependencies
- **VERIFY** all dependencies are declared

### 3. NO PLACEHOLDERS - EVER

- **NEVER** use "YOUR_API_KEY", "TODO", or dummy data
- **ALWAYS** use proper variable references or config
- If real values needed, **ASK** explicitly

### 4. QUESTION VS CODE REQUEST DISTINCTION

- **QUESTION** → Provide **ANSWER**, do NOT change code
- Only modify when explicitly requested ("change", "update", "modify", "fix")

### 5. NO ASSUMPTIONS OR GUESSING

- If information missing, **ASK**
- **NEVER** guess versions, APIs, or implementation details
- State clearly what information needed

### 6. SECURITY IS NON-NEGOTIABLE

- **NEVER** put API keys, secrets, or credentials in code
- **ALWAYS** use environment variables for sensitive data
- **ALWAYS** implement input validation and sanitization

### 7. PRESERVE FUNCTIONAL REQUIREMENTS

- **NEVER** change core functionality to "fix" errors
- Fix technical issue, not requirements
- If requirements problematic, **ASK** first

### 8. EVIDENCE-BASED RESPONSES

- When asked if something implemented, **SHOW CODE EVIDENCE**
- Format: `Looking at [filename] (lines X-Y): [code snippet]`
- **NEVER** guess or assume
- If unsure, **SAY SO** and offer to check

## Quality Process

**Workflow Order**:

1. **Fast Tools/Hooks** (~5s): formatting, basic checks → retry once if fail
1. **Full Test Suite**: collect ALL failures (don't stop on first)
1. **Comprehensive Tools/Hooks** (~30s): type checking, security, complexity → collect ALL issues
1. **AI Batch Fixing**: process all failures together (up to 10 iterations)

**Testing**: pytest with asyncio, 300s timeout, auto-detected workers via pytest-xdist
**Coverage**: Ratchet system targeting 100%, never decrease

## Test Parallelization

Crackerjack uses **pytest-xdist** for intelligent parallel execution:

- `test_workers: 0` (default) → Auto-detect via pytest-xdist
- `test_workers: 1` → Sequential execution (no parallelization)
- `test_workers: N` (N > 1) → Explicit worker count
- `test_workers: -N` (N < 0) → Fractional (e.g., -2 = half cores)

**Safety**: Memory-based limiting (2GB per worker minimum), benchmark auto-skip

**Performance**: 3-4x faster on 8-core systems

## Phase Parallelization

When enabled, tests and comprehensive hooks run concurrently (20-30% faster):

```bash
python -m crackerjack run --enable-parallel-phases --run-tests -c
```

## AI Agent System

The internal 12-agent auto-fix system (`--ai-fix`) and its session-buddy
skill-tracking integration have been removed. The replacement is an
external `Workflow`-tool loop (`.claude/workflows/ai-fix-loop.js`) that
runs `crackerjack run -v`, dispatches residual issues to a fix agent,
re-verifies, and repeats with SHA-anchored stash snapshots, rollback on
regression, a JSONL audit trail, and best-effort Akosha logging.

For the design rationale and contract details, see:

- `docs/superpowers/specs/2026-08-06-ai-fix-removal-external-loop-design.md`
  (removal rationale + external-loop design)
- `docs/superpowers/plans/2026-08-06-ai-fix-external-loop.md` (the
  implementation plan; 9 tasks, all completed)

## High-Performance Rust Integration

Ultra-fast static analysis with seamless Python integration:

- **🦅 Skylos**: Dead code detection (**20x faster** than vulture) — runs in the **comprehensive** stage, not fast hooks
- **🔍 Zuban**: Type checking (**20-200x faster** than pyright) — opt-in via `enable_zuban`; `ty` is the default type checker
- **🚀 Performance**: 6,000+ operations/second throughput

**Benefits**: Comprehensive hooks complete faster with Rust-backed tools; AI agents get lower-latency type and dead-code feedback.

## Skills Tracking Integration

Session-buddy skill-tracking for the removed 12-agent system is no
longer active. The replacement external loop ships best-effort
fix-outcome memory to Akosha via `generate_embedding` → `store_memory`
on each successful iteration; see
`docs/superpowers/plans/2026-08-06-ai-fix-external-loop.md` (Task 7)
for the contract and the deterministic `memory_id` scheme.

## MCP Server Integration

**Note**: Uses global MCP configuration in `~/.claude/.mcp.json`.

**Features**: MCP protocol, real-time progress tracking, job management

```bash
python -m crackerjack start  # Start MCP server
```

## Coverage Status

Current coverage is reported in `coverage.json` (generated by pytest) and
the `htmlcov/index.html` page. The ratchet system enforces "never
decrease" against the `current_minimum` baseline stored alongside
`[tool.coverage.report]` (see `crackerjack.services.coverage_ratchet`).

To read the current value:

```bash
python -c "import json; print(json.load(open('coverage.json'))['totals']['percent_covered'])"
```

See [COVERAGE_POLICY.md](docs/reference/COVERAGE_POLICY.md) for the full policy.

## Additional Resources

**For detailed documentation**:

- **[README.md](./README.md)**: Complete project documentation
- **[docs/](./docs/)**: Implementation plans, ADRs, and reference docs

**For comprehensive protocol documentation**:

## Core Reminders

**Quality First**:

- **Take time to do things right first time**: Proper implementation prevents technical debt
- **Check yourself before you wreck yourself**: Always validate work before considering complete
- Run `python -m crackerjack run` to verify
- Don't wait for quality gates to catch preventable mistakes

**Clean Code**:

- Do only what's asked, nothing more
- NEVER create files unless absolutely necessary
- **Exception**: When architectural patterns require it for correctness
- ALWAYS prefer editing existing files
- MAINTAIN coverage ratchet

**Critical Security & Quality Rules** (see sections above):

- Import compliance from `models.protocols.py`
- Constructor injection patterns
- No placeholders or hardcoded secrets
- Evidence-based responses
- Fix failures FIRST before adding features
- Use IDE diagnostics after implementation
