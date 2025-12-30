# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crackerjack is an opinionated Python project management tool unifying UV, Ruff, pytest, and pre-commit into a single workflow with AI agent integration via MCP.

**Key Dependencies**: Python 3.13+, UV, pre-commit, pytest

**Clean Code Philosophy**: DRY/YAGNI/KISS - Every line is a liability. Optimize for readability with self-documenting code.

## CRITICAL SECURITY & QUALITY RULES

### 1. NEVER MAKE UNAUTHORIZED CHANGES

- **ONLY** modify what is explicitly requested.
- **NEVER** change unrelated code, files, or functionality.
- If you think something else needs changing, **ASK FIRST**.
- Changing anything not explicitly requested is considered **prohibited change**.

### 2. DEPENDENCY MANAGEMENT IS MANDATORY

- **ALWAYS** update pyproject.toml when adding imports.
- **NEVER** add import statements without corresponding dependency entries.
- **VERIFY** all dependencies are properly declared before suggesting code.

### 3. NO PLACEHOLDERS - EVER

- **NEVER** use placeholder values like "YOUR_API_KEY", "TODO", or dummy data.
- **ALWAYS** use proper variable references or configuration patterns.
- If real values are needed, **ASK** for them explicitly.
- Use environment variables or config files, not hardcoded values.

### 4. QUESTION VS CODE REQUEST DISTINCTION

- When a user asks a **QUESTION**, provide an **ANSWER** - do NOT change code.
- Only modify code when explicitly requested with phrases like "change", "update", "modify", "fix".
- **NEVER** assume a question is a code change request.

### 5. NO ASSUMPTIONS OR GUESSING

- If information is missing, **ASK** for clarification.
- **NEVER** guess library versions, API formats, or implementation details.
- **NEVER** make assumptions about user requirements or use cases.
- State clearly what information you need to proceed.

### 6. SECURITY IS NON-NEGOTIABLE

- **NEVER** put API keys, secrets, or credentials in client-side code.
- **ALWAYS** implement proper authentication and authorization.
- **ALWAYS** use environment variables for sensitive data.
- **ALWAYS** implement proper input validation and sanitization.

### 7. PRESERVE FUNCTIONAL REQUIREMENTS

- **NEVER** change core functionality to "fix" errors.
- When encountering errors, fix the technical issue, not the requirements.
- If requirements seem problematic, **ASK** before changing them.

### 8. EVIDENCE-BASED RESPONSES

- When asked if something is implemented, **SHOW CODE EVIDENCE**.
- Format: "Looking at the code: [filename] (lines X-Y): [relevant code snippet]"
- **NEVER** guess or assume implementation status.
- If unsure, **SAY SO** and offer to check specific files.

## Essential Commands

**IMPORTANT**: Crackerjack has a two-level CLI structure:

- `python -m crackerjack --help` shows **command list** (start, stop, run, etc.)
- `python -m crackerjack run --help` shows **all 100+ quality options** (-t, -x, -c, --ai-fix, etc.)

All quality-checking flags live under the `run` subcommand!

```bash
# Help commands
python -m crackerjack run --help        # Shows command list
python -m crackerjack run --help    # Shows ALL options (640 lines!)

# Daily workflow
python -m crackerjack run                       # Quality checks
python -m crackerjack run --run-tests           # With tests
python -m crackerjack run -t                    # Short form
python -m crackerjack run --ai-fix --run-tests  # AI auto-fixing (recommended)
python -m crackerjack run --ai-fix -t           # Short form

# Development
python -m crackerjack run --ai-debug --run-tests # Debug AI issues
python -m crackerjack run --skip-hooks           # Skip hooks during iteration
python -m crackerjack run --strip-code           # Code cleaning mode
python -m crackerjack run -x                     # Short form
python -m crackerjack run -x -t --ai-fix         # Combined shortcuts

# MCP Server management
python -m crackerjack start          # Start MCP server
python -m crackerjack stop           # Stop MCP server
python -m crackerjack restart        # Restart MCP server
python -m crackerjack status         # Check server status
python -m crackerjack health         # Server health check

# Additional server options (via run command)
python -m crackerjack run --watchdog             # Monitor/restart services

# Release workflow
python -m crackerjack run --all patch  # Full release workflow

# Testing options
python -m pytest tests/test_file.py::TestClass::test_method -v  # Specific test
python -m pytest --cov=crackerjack --cov-report=html             # Coverage
python -m crackerjack run --run-tests                            # Auto-detect workers (default)
python -m crackerjack run --run-tests --test-workers 4           # Explicit workers
python -m crackerjack run --run-tests --test-workers 1           # Sequential execution
python -m crackerjack run --run-tests --test-workers -2          # Fractional (half cores)

# Standalone test command (simpler, no quality checks)
python -m crackerjack run-tests              # Just run pytest
python -m crackerjack run-tests --workers 4  # With explicit workers
```

## Architecture

**Modular Oneiric Architecture**: `__main__.py` → CLI Handlers → Coordinators → Managers → Services

### Critical Architectural Pattern: Protocol-Based Design

Crackerjack uses **protocol-based dependency injection** with constructor injection:

```python
# ✅ GOLD STANDARD: Always import protocols, never concrete classes
from crackerjack.models.protocols import Console, TestManagerProtocol


def setup_ai_agent_env(
    ai_agent: bool, debug_mode: bool = False, console: Console | None = None
) -> None:
    """All functions use protocol-based dependencies via constructor injection."""
    if console is None:
        from rich.console import Console

        console = Console()
    console.print("[green]AI agent environment configured[/green]")


class SessionCoordinator:
    def __init__(
        self,
        console: Console,
        test_manager: TestManagerProtocol,
        pkg_path: Path,
    ) -> None:
        """Constructor injection with protocol-based dependencies."""
        self.console = console
        self.test_manager = test_manager
        self.pkg_path = pkg_path
```

**THE MOST CRITICAL PATTERN**: Always import protocols from `models/protocols.py`, never concrete classes

```python
# ❌ Wrong - Direct class imports (BREAKS ARCHITECTURE)
from crackerjack.managers.test_manager import TestManager
from rich.console import Console as RichConsole

# ✅ Correct - Protocol imports (FOLLOWS ARCHITECTURE)
from crackerjack.models.protocols import TestManagerProtocol, Console
```

### Anti-Patterns to Avoid

```python
# ❌ Global singletons
console = Console()  # At module level

# ❌ Factory functions without dependency injection
self.tracker = get_agent_tracker()
self.timeout_manager = get_timeout_manager()


# ✅ Correct - Constructor injection
def __init__(
    self,
    console: Console,
    cache: CrackerjackCache,
    tracker: AgentTrackerProtocol,
) -> None:
    self.console = console
    self.cache = cache
    self.tracker = tracker


# ✅ Correct - Module-level logger
logger = logging.getLogger(__name__)
```

### Core Layers & Compliance Status

**🎉 FULLY COMPLETE** - All Components (Phase 5-7 Completion)

Based on Phase 2-7 refactoring audit (100% ACB-free):

- **CLI Handlers** (100% compliant): Entry points, option processing

  - ✅ All handlers use protocol-based typing
  - ✅ Constructor injection patterns
  - ✅ `CrackerjackCLIFacade` fully integrated
  - ✅ MCPServerCLIFactory integration complete (Phase 6)

- **Services** (100% compliant): Filesystem, git, config, security, health monitoring

  - ✅ All Phase 3 refactored services follow standards
  - ✅ Constructor consistency, lifecycle management
  - ✅ ACB references removed (Phase 5)

- **Managers** (100% compliant): Hook execution (fast→comprehensive), test management, publishing

  - ✅ All managers use protocol-based typing
  - ✅ Constructor injection standard
  - ✅ ACB patterns replaced (Phase 5)

- **Coordinators** (100% compliant): Session/phase coordination, async workflows, parallel execution

  - ✅ Phase coordinators use proper DI
  - ✅ Async coordinators protocol standardization complete
  - ✅ Workflow type hints restored (Phase 6)

- **Orchestration** (100% compliant): `WorkflowOrchestrator`, lifecycle management

  - ✅ `SessionCoordinator` - Gold standard protocol integration
  - ✅ `ServiceWatchdog` - Oneiric-based lifecycle
  - ✅ Oneiric workflow integration complete (Phase 6)

- **Agent System** (100% compliant): AI agents, coordination

  - ✅ All agents use protocol-based design
  - ✅ `AgentContext` pattern for agent isolation
  - ✅ Protocols defined and implemented
  - ✅ No ACB dependencies remaining

- **Adapters** (100% compliant): 18 QA adapters + AI adapters

  - ✅ All adapters use constructor injection (Phase 4)
  - ✅ ACB `depends.set()` patterns removed (Phase 5)
  - ✅ Protocol-based registration via server initialization

- **MCP Integration** (100% compliant): mcp-common integration

  - ✅ MCPServerCLIFactory patterns adopted (Phase 6)
  - ✅ Server lifecycle management complete
  - ✅ Health probes and rate limiting configured

### Architecture Decision Records

**Why Protocol-Based Design?**

- Loose coupling between layers
- Easy testing with mock implementations
- Clear interface contracts
- Runtime type checking via `@runtime_checkable`
- No framework lock-in (ACB removed, pure Python patterns)

**Why AgentContext Pattern for Agents?**

- Dataclass-based context provides agent isolation
- Clean separation of concerns
- Protocols allow flexible implementations
- Works well without complex DI frameworks

## Quality Process

**Workflow Order**:

1. **Fast Hooks** (~5s): formatting, basic checks → retry once if fail
1. **Full Test Suite**: collect ALL failures, don't stop on first
1. **Comprehensive Hooks** (~30s): type checking, security, complexity → collect ALL issues
1. **AI Batch Fixing**: process all collected failures together

**Testing**: pytest with asyncio, 300s timeout, auto-detected workers via pytest-xdist
**Coverage**: Ratchet system targeting 100%, never decrease

### Test Parallelization

Crackerjack uses **pytest-xdist** for intelligent parallel test execution with memory safety:

**Worker Configuration**:

- `test_workers: 0` (default) → Auto-detect via pytest-xdist (`-n auto`)
- `test_workers: 1` → Sequential execution (no parallelization)
- `test_workers: N` (N > 1) → Explicit worker count
- `test_workers: -N` (N < 0) → Fractional (e.g., -2 = half of CPU cores)

**Safety Features**:

- Memory-based limiting: 2GB per worker minimum (prevents OOM)
- Benchmark auto-skip: Benchmarks always run sequentially (parallel skews results)
- Distribution strategy: `--dist=loadfile` (keeps fixtures from same file together)
- Emergency rollback: `export CRACKERJACK_DISABLE_AUTO_WORKERS=1`

**Configuration Priority** (highest to lowest):

1. CLI flag: `--test-workers N`
1. `pyproject.toml`: `[tool.crackerjack] test_workers = N`
1. `settings/crackerjack.yaml`: `test_workers: N`
1. Default: 0 (auto-detect)

**Examples**:

```bash
# Auto-detect (default, recommended)
python -m crackerjack run --run-tests

# Explicit worker count
python -m crackerjack run --run-tests --test-workers 4

# Sequential (debugging flaky tests)
python -m crackerjack run --run-tests --test-workers 1

# Fractional (conservative parallelization)
python -m crackerjack run --run-tests --test-workers -2  # Half cores

# Disable auto-detection globally
export CRACKERJACK_DISABLE_AUTO_WORKERS=1
python -m crackerjack run --run-tests  # Forces sequential
```

**Performance Impact** (8-core MacBook):

- Before (1 worker): ~60s test suite, 12% CPU utilization
- After (auto-detect): ~15-20s test suite, 70-80% CPU utilization (3-4x faster)

## Code Standards

**Quality Rules**:

- **Complexity ≤15** per function
- **No hardcoded paths** (use `tempfile`)
- **No shell=True** in subprocess
- **Type annotations required**
- **Protocol-based DI** (import from `models/protocols.py`)
- **Python 3.13+**: `|` unions, protocols, pathlib

**Refactoring Pattern**: Break complex methods into helpers

```python
def complex_method(self, data: dict) -> bool:
    if not self._validate_input(data):
        return self._handle_invalid_input()
    processed = self._process_data(data)
    return self._save_results(processed)
```

**Critical Regex Safety**: NEVER write raw regex. Use centralized registry:

```python
# ❌ DANGEROUS
text = re.sub(r"(\w+) - (\w+)", r"\g<1>-\g<2>", text)

# ✅ SAFE
from crackerjack.services.regex_patterns import SAFE_PATTERNS

text = SAFE_PATTERNS["fix_hyphenated_names"].apply(text)
```

## Common Issues & Solutions

**Development**:

- **AI agent ineffective**: Use `--ai-debug --run-tests` for analysis
- **Import errors**: Always import protocols from `models/protocols.py`
- **Test hangs**: Avoid complex async tests, use simple synchronous config tests
- **Coverage failing**: Never reduce below baseline, add tests incrementally
- **Complexity >15**: Break into helper methods using RefactoringAgent approach

**Testing Performance**:

- **Slow tests**: Auto-detection enabled by default (3-4x faster)
- **Flaky tests with parallelization**: Use `--test-workers 1` to debug sequentially
- **Out of memory errors**: Reduce `memory_per_worker_gb` in settings or use `--test-workers -2`
- **Tests failing only in parallel**: Check for shared state issues (singletons, DI container)
- **Force sequential globally**: `export CRACKERJACK_DISABLE_AUTO_WORKERS=1`

**Server**:

- **MCP not starting**: `--restart-mcp-server` or `--watchdog`
- **Terminal stuck**: `stty sane; reset; exec $SHELL -l`
- **Coverage data loss with xdist**: Verify `pyproject.toml` has `parallel = true` in `[tool.coverage.run]`

## Oneiric Settings Integration

**Configuration Loading**: Crackerjack uses Oneiric Settings with YAML-based configuration:

```python
from crackerjack.config import CrackerjackSettings

# Option 1: Load directly (synchronous)
settings = CrackerjackSettings.load()

# Option 2: Load asynchronously (for runtime use)
settings = await CrackerjackSettings.load_async()

# Option 3: Access globally configured instance
from crackerjack.config import settings  # Pre-loaded singleton
```

**Configuration Files**:

- `settings/crackerjack.yaml` - Base configuration (committed to git)
- `settings/local.yaml` - Local overrides (gitignored, for development)

**Priority Order** (highest to lowest):

1. `settings/local.yaml` - Local developer overrides
1. `settings/crackerjack.yaml` - Base project configuration
1. Default values in `CrackerjackSettings` class

**Usage Examples**:

```yaml
# settings/local.yaml (gitignored)
verbose: true
max_parallel_hooks: 8
test_workers: 4
ai_debug: true
```

```python
# Access settings in code
from crackerjack.config import CrackerjackSettings


def my_function(settings: CrackerjackSettings | None = None):
    if settings is None:
        settings = CrackerjackSettings.load()
    if settings.verbose:
        print(f"Running with {settings.max_parallel_hooks} parallel hooks")
```

**Implementation Details**:

- Settings automatically loaded during module initialization
- Unknown YAML fields silently ignored (no validation errors)
- Type validation via Pydantic
- Async initialization available for secret loading
- All 60+ configuration fields supported

## MCP Server Integration

**Features**: Dual protocol (MCP + WebSocket), real-time progress, job tracking

```bash
# Start server
python -m crackerjack run --start-mcp-server

# Monitor progress at http://localhost:8675/
python -m crackerjack run.mcp.progress_monitor <job_id>
```

**Available Tools**: `execute_crackerjack`, `get_job_progress`, `get_comprehensive_status`, `analyze_errors`

**Slash Commands**: `/crackerjack:run`, `/crackerjack:status`, `/crackerjack:init`

## Critical Reminders

**Core Instructions**:

- Do only what's asked, nothing more
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing existing files
- MAINTAIN coverage ratchet

**Quality Standards**:

- **Test Quality**: Avoid async tests that hang, use synchronous config tests
- **Import Compliance**: Use protocols from `models/protocols.py`
- **Fix failures FIRST** before creating new tests
- Use IDE diagnostics after implementation

**Failure Patterns to Avoid**:

```python
# ❌ Async tests that hang
@pytest.mark.asyncio
async def test_batch_processing(self, batched_saver):
    await batched_saver.start()  # Can hang


# ✅ Simple synchronous tests
def test_batch_configuration(self, batched_saver):
    assert batched_saver.max_batch_size == expected_size


# ❌ Import concrete classes
from ..managers.test_manager import TestManager

# ✅ Import protocols
from ..models.protocols import TestManagerProtocol
```

**Current Status**: 21.6% coverage (baseline: 19.6%, targeting 100% via ratchet system). See [COVERAGE_POLICY.md](/docs/reference/COVERAGE_POLICY.md) for complete details.

- make sure to run `python -m crackerjack run` after every editing/debugging cycle for quality checking
- always put implementation plans in a md doc for review and reference
- think when you need to think, think harder when you need to think harder

## AI Agent System

**12 Specialized Agents** handle domain-specific issues:

- **RefactoringAgent** (0.9): Complexity ≤15, dead code removal
- **PerformanceAgent** (0.85): O(n²) detection, optimization
- **SecurityAgent** (0.8): Hardcoded paths, unsafe operations
- **DocumentationAgent** (0.8): Changelog, .md consistency
- **TestCreationAgent** (0.8): Test failures, fixtures
- **DRYAgent** (0.8): Code duplication patterns
- **FormattingAgent** (0.8): Style violations, imports
- **ImportOptimizationAgent**: Import cleanup, reorganization
- **TestSpecialistAgent** (0.8): Advanced testing scenarios
- **SemanticAgent** (0.85): Semantic analysis, code comprehension, intelligent refactoring
- **ArchitectAgent** (0.85): Architecture patterns, design recommendations, system optimization
- **EnhancedProactiveAgent** (0.9): Proactive prevention, predictive monitoring, preemptive optimization

**Usage**: `--ai-fix` enables batch fixing; confidence ≥0.7 uses specific agents

## High-Performance Rust Integration

**Ultra-Fast Static Analysis** with seamless Python integration:

- **🦅 Skylos**: Dead code detection **20x faster** than vulture
- **🔍 Zuban**: Type checking **20-200x faster** than pyright
- **🚀 Performance**: 6,000+ operations/second throughput
- **🔄 Compatibility**: Zero breaking changes, drop-in replacements

**Benefits in Daily Workflow**:

- Pre-commit hooks complete in seconds instead of minutes
- `--run-tests` now blazingly fast with Rust-powered type checking
- AI agents get faster feedback for more efficient fixing cycles
- Development iteration speed dramatically improved
