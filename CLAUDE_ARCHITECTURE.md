# CLAUDE Architecture & Directory Structure

This file provides detailed architecture and directory structure guidance for Crackerjack development.

> **For quick command reference**, see [CLAUDE_QUICKSTART.md](./CLAUDE_QUICKSTART.md)
> **For working protocols**, see [CLAUDE_PROTOCOLS.md](./CLAUDE_PROTOCOLS.md)
> **For code patterns**, see [CLAUDE_PATTERNS.md](./CLAUDE_PATTERNS.md)

## Directory Structure Overview

Crackerjack is organized into **23 top-level modules** under `crackerjack/`:

### Core Architecture Layers

```
crackerjack/
├── cli/                    # Command-line interface and option handling
├── core/                   # Core orchestration, retry logic, resource management
├── managers/                # Hook and test execution management
├── services/                # File I/O, git operations, configuration, security
├── models/                  # Protocol definitions and data structures
├── config/                  # Settings and configuration management
└── runtime/                 # Oneiric workflow execution and health monitoring
```

**Layer Responsibilities:**

**CLI Layer** (`cli/`):

- Entry point via typer CLI
- Option parsing and validation
- Command routing to handlers
- User interaction and display

**Coordinator Layer** (`core/`, `runtime/`):

- Session coordination
- Workflow orchestration (legacy workflows, Oneiric)
- Resource management and lifecycle
- Async/sync execution strategies

**Manager Layer** (`managers/`):

- Hook execution orchestration
- Test management and execution
- Publish operations
- Adapter coordination

**Service Layer** (`services/`):

- File system operations
- Git integration
- Configuration management
- Security auditing
- Logging and monitoring

### Quality Enforcement

```
crackerjack/
├── adapters/                # 18 QA tool adapters (format, lint, type-check, security)
├── tools/                   # Custom quality check scripts
└── decorators/              # Pattern-based error handling and retry logic
```

**Adapter Categories:**

- **Format**: Ruff formatting, mdformat
- **Lint**: Codespell, complexity analysis
- **Security**: Bandit security scanning, Gitleaks secret detection
- **Type**: Zuban type checking (Rust, 20-200x faster than pyright)
- **Refactor**: Refurb (Python idioms), Creosote (unused deps)
- **Complexity**: Complexipy analysis
- **Utility**: Various validation checks

### AI & Intelligence

```
crackerjack/
├── agents/                  # 12 specialized AI agents for auto-fixing
├── intelligence/             # Agent orchestration and learning systems
└── integration/              # Session-buddy skills tracking
```

**AI Agents:**

- SecurityAgent: Shell injection, weak crypto, token exposure
- RefactoringAgent: Complexity ≤15, dead code removal
- PerformanceAgent: O(n²) detection, optimization
- DocumentationAgent: Changelog, .md consistency
- TestCreationAgent: Test failures, fixtures
- DRYAgent: Code duplication patterns
- FormattingAgent: Style violations, imports
- ImportOptimizationAgent: Import cleanup
- TestSpecialistAgent: Advanced testing scenarios
- SemanticAgent: Semantic analysis, code comprehension
- ArchitectAgent: Architecture patterns, design recommendations
- EnhancedProactiveAgent: Proactive prevention, predictive monitoring

### Infrastructure

```
crackerjack/
├── mcp/                     # MCP server with 6 tool categories
├── exceptions/               # Custom exception hierarchy
├── utils/                    # Shared utilities and helpers
├── ui/                      # Rich console and progress displays
└── shell/                    # Shell command execution
```

**MCP Tools Categories:**

- Core tools: Job execution, monitoring, error analysis
- Intelligence tools: Semantic search, skill tracking
- Progress tools: Real-time status updates
- Workflow tools: Stage execution, session management
- Proactive tools: Pattern-based issue prevention
- Skill tools: Agent metrics and recommendations

### Configuration & Plugins

```
crackerjack/
├── plugins/                  # Hook registration and lifecycle
├── parsers/                  # Configuration and data parsing
├── slash_commands/            # Custom slash command handlers
└── hooks/                    # Git hook integration
```

### Entry Points

**CLI Mode** (`python -m crackerjack`):

- Entry: `crackerjack/__main__.py`
- Uses typer for CLI interface
- Interactive development workflow
- Quality checks and testing
- Version management and publishing

**MCP Server Mode** (`python -m crackerjack start`):

- Entry: `crackerjack/server.py`
- FastMCP server
- AI agent integration
- Real-time progress tracking
- Job management and monitoring

## Key Architectural Patterns

### Protocol-Based Dependency Injection

**THE MOST CRITICAL PATTERN**: Always import protocols, never concrete classes

```python
# ✅ GOLD STANDARD
from crackerjack.models.protocols import Console, TestManagerProtocol


def __init__(
    self,
    console: Console,
    test_manager: TestManagerProtocol,
) -> None:
    self.console = console
    self.test_manager = test_manager


# ❌ WRONG - Direct class imports
from crackerjack.managers.test_manager import TestManager
from rich.console import Console as RichConsole
```

**Constructor Injection**: All dependencies via `__init__`, no factory functions
**Module-level singletons**: Only `logger = logging.getLogger(__name__)`

### legacy Dependency Injection

Used in CLI handlers via `@depends.inject()` decorator:

```python
from legacy.depends import depends, Inject
from crackerjack.models.protocols import Console


@depends.inject
def setup_environment(console: Inject[Console] = None) -> None:
    """Protocol-based injection with decorator."""
    if console is None:
        from rich.console import Console

        console = Console()
    console.print("[green]Environment ready[/green]")
```

**Key Features:**

- Module-level registration via `depends.set()`
- Runtime-checkable protocols for type safety
- Async-first design with lifecycle management
- Clean separation of concerns

### Execution Modes

**Quality Hook Strategies:**

1. **Fast Hooks** (~5s): formatting, basic checks

   - Ruff formatting, trailing whitespace, UV lock updates
   - Auto-retry on failure (1 attempt)

1. **Comprehensive Hooks** (~30s): type checking, security, complexity

   - Zuban (Rust), Bandit, Complexipy, Refurb, etc.
   - AI batch-fixing after collection

1. **Parallel Execution**:

   - Test parallelization: pytest-xdist (auto-detect workers)
   - Phase parallelization: tests + comprehensive hooks run concurrently
   - Result: 3-4x faster overall workflow

### Workflow Orchestration

**Two Workflow Engines:**

1. **BasicWorkflowEngine** (legacy, default since Phase 4.2):

   - Real-time output streaming
   - Non-blocking async execution
   - Content-based caching (70% hit rate)

1. **WorkflowOrchestrator** (legacy-based, opt-out):

   - SessionCoordinator with protocol-based DI
   - Phase coordinators
   - Legacy orchestration layer

**Execution Flow:**

```
User Command
    ↓
CLI Handlers (cli/)
    ↓
Coordinators (runtime/, core/)
    ↓
Managers (managers/)
    ↓
Services (services/) + Adapters (adapters/)
```

## Finding Code

**For Understanding Components:**

| Want to understand... | Go to... |
|---------------------|-----------|
| CLI command structure | `cli/` - Typer app, option definitions |
| Quality hooks | `adapters/` - 18 QA adapters |
| Test execution | `managers/` - HookManager, TestManager |
| Workflow phases | `runtime/` - Oneiric workflow DAG |
| AI agents | `agents/` - 12 specialized agents |
| MCP integration | `mcp/` - Server, tools, endpoints |
| Configuration | `config/` - Settings loading, templates |
| Protocols | `models/protocols.py` - All protocol definitions |

**For Implementation Patterns:**

| Pattern | Location | Key Principle |
|---------|----------|----------------|
| Protocol-based DI | Entire codebase | Import from `models.protocols` only |
| Constructor injection | `__init__` methods | No factory functions |
| legacy patterns | CLI handlers | `@depends.inject()` decorator |
| Error handling | `decorators/` | Retry, timeout, suppression |
| Adapter pattern | `adapters/` | QAAdapterBase, check() method |
| Agent context | `agents/` | Dataclass with isolated context |

## Architecture Compliance

**Phase 2-7 Refactoring Status**: ✅ **100% Protocol Compliant**

| Layer | Compliance | Notes |
|-------|-----------|--------|
| CLI Handlers | 100% ✅ | `@depends.inject` + protocol imports |
| Services | 100% ✅ | Constructor injection, lifecycle management |
| Managers | 100% ✅ | Protocol-based injection |
| Coordinators | 100% ✅ | Phase coordinators, async workflows |
| Orchestration | 100% ✅ | SessionCoordinator, ServiceWatchdog |
| Agent System | 100% ✅ | AgentContext pattern |
| Adapters | 100% ✅ | Constructor injection (Phase 4) |
| MCP Integration | 100% ✅ | MCPServerCLIFactory patterns |

**Verification:**

```bash
# Check for protocol compliance
grep -r "from crackerjack" crackerjack/ --include="*.py" | grep -v protocols | grep -v __pycache__
```

Should return empty (all imports use protocols).

## Performance Architecture

**Optimization Strategies:**

1. **Intelligent Caching**:

   - Content-based keys with file hash verification
   - LRU eviction with TTL
   - 70% cache hit rate

1. **Parallel Execution**:

   - Up to 11 concurrent adapters
   - Dependency-aware scheduling
   - Semaphore control prevents exhaustion

1. **Rust Tool Integration**:

   - **Skylos**: Dead code detection (20x faster than vulture)
   - **Zuban**: Type checking (20-200x faster than pyright)
   - 6,000+ operations/second throughput

1. **Test Parallelization**:

   - pytest-xdist with auto-detected workers
   - Memory-based limiting (2GB per worker minimum)
   - Fractional workers support (--test-workers -2)

1. **Phase Parallelization**:

   - Tests and comprehensive hooks run concurrently
   - 20-30% faster workflow time
   - Opt-in via `--enable-parallel-phases`

## Migration History

**Phase 8 (Latest)**: MCP server integration, AI auto-fixing enhancements
**Phase 7**: Oneiric workflow integration, async coordinators
**Phase 6**: MCPServerCLIFactory patterns, protocol standardization
**Phase 5**: legacy framework removal, protocol-based DI
**Phase 4**: Adapter constructor injection, legacy `depends.set()` removal
**Phase 3**: Service layer refactoring
**Phase 2**: Complete architecture audit

*See `docs/archive/phase-completions/` for detailed completion reports.*
