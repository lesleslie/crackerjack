# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Quick Links

**📋 Essential Documentation:**

**🎯 Task-Based Navigation:**
| Want to... | Go to... |
|-------------|----------|
| **Understand codebase** | [Architecture](#directory-structure-overview) → See layered design, entry points, and module organization |
| **Start development** | [Quick Start](#essential-commands) → Daily workflow, testing, server management |
| **Run quality checks** | [Quick Start → Quality Hook Reference](#quality-hook-reference) → Fast vs comprehensive hooks |
| **Fix quality issues** | [Protocols → Code Review Protocol](#code-review-protocol) → Systematic review process |
| **Select AI agent** | [Protocols → Agent Selection](#agent-selection-protocol) → When to use specialized agents |
| **Implement patterns** | [Patterns → Code Standards](#core-code-standards) → Quality rules, naming, testing |
| **Verify architecture** | [Protocols → Architecture Compliance](#architecture-compliance-protocol) → Protocol-based DI verification |
| **Make fix decisions** | [Protocols → Decision Framework](#quality-decision-framework-fix-now-or-later) → What to fix now vs defer |

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
# Daily development (quality + tests + AI fixes) - RECOMMENDED
python -m crackerjack run --ai-fix --run-tests

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

**12 Specialized Agents** for auto-fixing quality issues:

- **RefactoringAgent** (0.9): Complexity ≤15, dead code removal
- **PerformanceAgent** (0.85): O(n²) detection, optimization
- **SecurityAgent** (0.8): Hardcoded paths, unsafe operations
- **DocumentationAgent** (0.8): Changelog, .md consistency
- **TestCreationAgent** (0.8): Test failures, fixtures
- **DRYAgent** (0.8): Code duplication
- **FormattingAgent** (0.8): Style violations, imports
- **ImportOptimizationAgent**: Import cleanup
- **TestSpecialistAgent** (0.8): Advanced testing
- **SemanticAgent** (0.85): Semantic analysis, intelligent refactoring
- **ArchitectAgent** (0.85): Architecture patterns, design recommendations
- **EnhancedProactiveAgent** (0.9): Proactive prevention, predictive monitoring

**Usage**: `--ai-fix` enables batch fixing; confidence ≥0.7 for specific agents

## High-Performance Rust Integration

Ultra-fast static analysis with seamless Python integration:

- **🦅 Skylos**: Dead code detection (**20x faster** than vulture)
- **🔍 Zuban**: Type checking (**20-200x faster** than pyright)
- **🚀 Performance**: 6,000+ operations/second throughput

**Benefits**: Pre-commit hooks complete in seconds, AI agents get faster feedback.

## Skills Tracking Integration

Crackerjack integrates with **session-buddy** for comprehensive metrics tracking and intelligent agent recommendations.

**What it tracks**:

- Agent selection (and why)
- User queries triggering selection
- Alternative agents considered
- Success/failure rates
- Performance metrics by workflow phase

## MCP Server Integration

**Note**: Uses global MCP configuration in `~/.claude/.mcp.json`.

**Features**: MCP protocol, real-time progress tracking, job management

```bash
python -m crackerjack start  # Start MCP server
```

## Coverage Status

**Current**: 21.6% (baseline: 19.6%, targeting 100% via ratchet system)

See [COVERAGE_POLICY.md](docs/reference/COVERAGE_POLICY.md) for complete details.

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

<!-- CRACKERJACK INTEGRATION START -->
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Quick Links

**📋 Essential Documentation:**

**🎯 Task-Based Navigation:**
| Want to... | Go to... |
|-------------|----------|
| **Understand codebase** | [Architecture](#directory-structure-overview) → See layered design, entry points, and module organization |
| **Start development** | [Quick Start](#essential-commands) → Daily workflow, testing, server management |
| **Run quality checks** | [Quick Start → Quality Hook Reference](#quality-hook-reference) → Fast vs comprehensive hooks |
| **Fix quality issues** | [Protocols → Code Review Protocol](#code-review-protocol) → Systematic review process |
| **Select AI agent** | [Protocols → Agent Selection](#agent-selection-protocol) → When to use specialized agents |
| **Implement patterns** | [Patterns → Code Standards](#core-code-standards) → Quality rules, naming, testing |
| **Verify architecture** | [Protocols → Architecture Compliance](#architecture-compliance-protocol) → Protocol-based DI verification |
| **Make fix decisions** | [Protocols → Decision Framework](#quality-decision-framework-fix-now-or-later) → What to fix now vs defer |

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
# Daily development (quality + tests + AI fixes) - RECOMMENDED
python -m crackerjack run --ai-fix --run-tests

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

**12 Specialized Agents** for auto-fixing quality issues:

- **RefactoringAgent** (0.9): Complexity ≤15, dead code removal
- **PerformanceAgent** (0.85): O(n²) detection, optimization
- **SecurityAgent** (0.8): Hardcoded paths, unsafe operations
- **DocumentationAgent** (0.8): Changelog, .md consistency
- **TestCreationAgent** (0.8): Test failures, fixtures
- **DRYAgent** (0.8): Code duplication
- **FormattingAgent** (0.8): Style violations, imports
- **ImportOptimizationAgent**: Import cleanup
- **TestSpecialistAgent** (0.8): Advanced testing
- **SemanticAgent** (0.85): Semantic analysis, intelligent refactoring
- **ArchitectAgent** (0.85): Architecture patterns, design recommendations
- **EnhancedProactiveAgent** (0.9): Proactive prevention, predictive monitoring

**Usage**: `--ai-fix` enables batch fixing; confidence ≥0.7 for specific agents

## High-Performance Rust Integration

Ultra-fast static analysis with seamless Python integration:

- **🦅 Skylos**: Dead code detection (**20x faster** than vulture)
- **🔍 Zuban**: Type checking (**20-200x faster** than pyright)
- **🚀 Performance**: 6,000+ operations/second throughput

**Benefits**: Pre-commit hooks complete in seconds, AI agents get faster feedback.

## Skills Tracking Integration

Crackerjack integrates with **session-buddy** for comprehensive metrics tracking and intelligent agent recommendations.

**What it tracks**:

- Agent selection (and why)
- User queries triggering selection
- Alternative agents considered
- Success/failure rates
- Performance metrics by workflow phase

## MCP Server Integration

**Note**: Uses global MCP configuration in `~/.claude/.mcp.json`.

**Features**: MCP protocol, real-time progress tracking, job management

```bash
python -m crackerjack start  # Start MCP server
```

## Coverage Status

**Current**: 21.6% (baseline: 19.6%, targeting 100% via ratchet system)

See [COVERAGE_POLICY.md](docs/reference/COVERAGE_POLICY.md) for complete details.

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
<!-- CRACKERJACK INTEGRATION END -->
