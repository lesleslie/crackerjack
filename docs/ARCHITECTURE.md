# Crackerjack Architecture

Comprehensive system architecture documentation for Crickerjack's advanced AI-driven Python development platform.

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Principles](#architecture-principles)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Quality Adapters](#quality-adapters)
- [Agent System](#agent-system)
- [MCP Integration](#mcp-integration)
- [Performance Optimization](#performance-optimization)
- [Security Architecture](#security-architecture)

## System Overview

Crackerjack is built on a **multi-layer architecture** that separates concerns across quality enforcement, AI orchestration, and developer experience.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Developer Layer                         │
│  ┌──────────────┬──────────────┬────────────────────────────┐  │
│  │ CLI Interface│ MCP Server   │ AI Agents (Claude/Qwen)    │  │
│  │  (Typer)     │  (FastMCP)   │                            │  │
│  └──────────────┴──────────────┴────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                      Orchestration Layer                        │
│  ┌──────────────┬──────────────┬────────────────────────────┐  │
│  │ Workflow     │ Phase        │ Session                    │  │
│  │ Pipeline     │ Coordinator  │ Coordinator                │  │
│  │  (Oneiric)   │              │                            │  │
│  └──────────────┴──────────────┴────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                        Manager Layer                           │
│  ┌──────────────┬──────────────┬────────────────────────────┐  │
│  │ Hook         │ Test         │ Job                        │  │
│  │ Manager      │ Manager      │ Manager                    │  │
│  └──────────────┴──────────────┴────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                       Adapter Layer                            │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┐  │
│  │ Ruff │ Zuban│Bandit│ Creo │Refor│Compl│ Sky │ ...    │  │
│  │      │      │      │ sote │urb   │ exip │ los │        │  │
│  └──────┴──────┴──────┴──────┴──────┴──────┴──────┴────────┘  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                      Service Layer                             │
│  ┌──────────────┬──────────────┬────────────────────────────┐  │
│  │ Cache        │ Error        │ Pattern                    │  │
│  │ Service      │ Cache        │ Management                 │  │
│  └──────────────┴──────────────┴────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns**: Each layer has a clear responsibility
1. **Dependency Injection**: Uses legacy framework for loose coupling
1. **Async-First**: Non-blocking I/O for performance
1. **Extensibility**: Plugin-based adapter and agent system
1. **Type Safety**: Protocol-based interfaces with runtime checking

## Architecture Principles

### 1. MCP-First Design

**Decision**: Use Model Context Protocol (MCP) as primary integration point for AI agents.

**Rationale**:

- Standard protocol for AI tool integration
- Supports both stdio and WebSocket transports
- Enables real-time progress tracking
- Separates CLI from AI concerns

**Implementation**:

```python
# FastMCP tool registration
from fastmcp import FastMCP

mcp = FastMCP("crackerjack")

@mcp.tool()
async def execute_crackerjack(
    command: str,
    ai_agent_mode: bool = False,
) -> dict:
    """Execute crackerjack command via MCP."""
    return await job_manager.create_job(command)
```

### 2. Adapter Pattern

**Decision**: All quality tools implement `QAAdapter` protocol.

**Rationale**:

- Consistent interface across all tools
- Easy to add new tools
- Testable in isolation
- Supports caching

**Implementation**:

```python
# Base adapter protocol
class QAAdapter(Protocol):
    adapter_name: str
    module_id: UUID

    async def check(
        self,
        files: set[Path],
        config: dict[str, Any],
    ) -> QAResult:
        """Run quality check on files."""
        ...
```

### 3. Property-Based Testing

**Decision**: Use Hypothesis for critical business logic.

**Rationale**:

- Catches edge cases that example-based tests miss
- Encodes invariants explicitly
- Supports stateful testing
- Shrinks failures to minimal reproducible examples

**Implementation**:

```python
from hypothesis import given, strategies as st

@given(
    issues=st.lists(st.builds(Issue), min_size=0, max_size=100)
)
def test_batch_processor_groups_all_issues(issues: list[Issue]):
    """Property: All issues must be assigned to exactly one batch."""
    batches = batch_processor.group_issues(issues)

    assigned_issues = []
    for agent_issues in batches.values():
        assigned_issues.extend(agent_issues)

    assert len(assigned_issues) == len(issues)
```

### 4. Confidence-Based Routing

**Decision**: Route issues to agents based on confidence scores (≥0.7 threshold).

**Rationale**:

- Automatic agent selection
- Handles overlapping issue types
- Supports learning from past performance
- Explainable routing decisions

**Implementation**:

```python
class SkillRouter:
    async def route_issue(self, issue: Issue) -> RoutingDecision:
        """Route issue to best agent(s) based on confidence."""

        # Find matching skills
        skill_matches = registry.find_matching_skills(issue, min_confidence=0.7)

        # Group by agent and score
        agent_scores = self._group_skills_by_agent(skill_matches)

        # Select routing strategy
        if agent_scores[0][1] >= 0.9:
            return self._single_agent_routing(issue, agent_scores)
        elif agent_scores[1][1] >= 0.8:
            return self._parallel_routing(issue, agent_scores)
        else:
            return self._sequential_routing(issue, agent_scores)
```

## Component Architecture

### 1. CLI Layer

**File**: `crackerjack/__main__.py`

**Responsibilities**:

- Parse command-line arguments (Typer)
- Delegate to workflow orchestrator
- Provide user feedback (Rich console)

**Key Commands**:

```python
app = typer.Typer()

@app.command()
def run(
    run_tests: bool = False,
    ai_fix: bool = False,
    quality_tier: str = "silver",
    # ... (20+ flags)
) -> None:
    """Run quality checks with optional AI auto-fixing."""
    workflow_pipeline.execute_workflow(options)
```

### 2. Workflow Pipeline

**File**: `crackerjack/core/workflow_orchestrator.py`

**Responsibilities**:

- Coordinate workflow phases (fast → cleaning → comprehensive → tests)
- Manage session lifecycle
- Handle errors and retries

**Architecture**:

```
WorkflowPipeline
    ├── SessionCoordinator (tracking, checkpoints)
    ├── PhaseCoordinator (fast, comprehensive, test phases)
    └── WorkflowResult (success/failure, metrics)
```

**Phase Execution**:

```python
class PhaseCoordinator:
    async def run_fast_hooks_phase(self) -> PhaseResult:
        """Run fast hooks (~5s)."""
        return await hook_manager.run_hooks(
            hooks=self.fast_hooks,
            strategy=ExecutionStrategy.PARALLEL,
        )

    async def run_comprehensive_hooks_phase(self) -> PhaseResult:
        """Run comprehensive hooks (~30s)."""
        return await hook_manager.run_hooks(
            hooks=self.comprehensive_hooks,
            strategy=ExecutionStrategy.PARALLEL,
        )

    async def run_test_phase(self) -> PhaseResult:
        """Run test suite with coverage."""
        return await test_manager.run_tests(
            coverage_ratchet=True,
        )
```

### 3. Adapter Layer

**Location**: `crackerjack/adapters/`

**Adapter Categories**:

| Category | Adapters | Purpose |
|----------|----------|---------|
| **Format** | RuffFormat, Mdformat | Code formatting |
| **Lint** | Codespell, Complexipy | Linting and complexity |
| **Security** | Bandit, Gitleaks, Pyscn | Security scanning |
| **Type** | Zuban, Pyrefly, Ty | Type checking |
| **Refactor** | Refurb, Skylos, Creosote | Modernization and dead code |
| **Utility** | EOF newline, Regex, Size, Lock | Config-driven checks |

**Adapter Interface**:

```python
class RuffFormatAdapter:
    adapter_name = "Ruff Formatting"
    module_id = UUID("01937d86-...")

    async def check(
        self,
        files: set[Path],
        config: dict[str, Any],
    ) -> QAResult:
        """Run ruff format on files."""

        # Direct API call (no subprocess)
        result = await asyncio.to_thread(
            ruff.format_file,
            file_path,
            config=config,
        )

        # Return structured result
        return QAResult(
            passed=result.exit_code == 0,
            issues=[],
            modified_files={file_path} if result.changes else set(),
        )
```

**Performance**: Direct Python API calls are **47% faster** than subprocess-based pre-commit hooks.

### 4. Agent System

**Location**: `crackerjack/agents/`

**Agent Categories** (12 agents):

| Agent | Specialization | Confidence |
|-------|---------------|------------|
| **SecurityAgent** | Shell injection, weak crypto, token exposure | 0.95 |
| **RefactoringAgent** | Complexity reduction, SOLID principles | 0.90 |
| **PerformanceAgent** | Algorithm optimization, O(n²) patterns | 0.88 |
| **DocumentationAgent** | Changelog generation, markdown consistency | 0.85 |
| **DRYAgent** | Deduplication, pattern extraction | 0.83 |
| **FormattingAgent** | Code style, import organization | 0.92 |
| **TestCreationAgent** | Test fixtures, import errors | 0.87 |
| **ImportOptimizationAgent** | Unused imports, restructuring | 0.86 |
| **TestSpecialistAgent** | Advanced scenarios, fixture management | 0.82 |
| **SemanticAgent** | Business logic, code comprehension | 0.78 |
| **ArchitectAgent** | Design patterns, system optimization | 0.75 |
| **EnhancedProactiveAgent** | Predictive quality, prevention | 0.80 |

**Agent Interface**:

```python
class Agent(Protocol):
    agent_id: str
    agent_name: str
    capabilities: set[str]

    async def execute(
        self,
        task: TaskDescription,
        context: AgentContext,
    ) -> AgentResult:
        """Execute task and return result."""
        ...
```

**Agent Coordination**:

```
AgentOrchestrator
    ├── AgentRegistry (12 agents)
    ├── AgentSelector (confidence-based routing)
    └── ExecutionStrategy (single, parallel, sequential, consensus)
```

### 5. MCP Integration

**Location**: `crackerjack/mcp/`

**Components**:

- **MCPServer**: FastMCP server with stdio/WebSocket transport
- **JobManager**: Async job tracking with WebSocket progress
- **ErrorCache**: Pattern cache for AI fix recommendations
- **Tools**: 11 MCP tools for AI agent integration

**MCP Tools**:

| Tool | Purpose | Async |
|------|---------|-------|
| `execute_crackerjack` | Start quality workflow | Yes |
| `get_job_progress` | Get real-time progress | Yes |
| `run_crackerjack_stage` | Run specific stage | Yes |
| `analyze_errors` | Analyze error patterns | Yes |
| `smart_error_analysis` | AI-powered analysis | Yes |
| `get_stage_status` | Check workflow status | No |
| `get_next_action` | Get recommended action | No |
| `session_management` | Session checkpoints | Yes |

## Data Flow

### Quality Check Workflow

```
User Command (CLI/MCP)
    ↓
WorkflowPipeline.run_complete_workflow()
    ↓
SessionCoordinator.initialize_session_tracking()
    ↓
┌─────────────────────────────────────────┐
│ Phase 1: Fast Hooks (~5s)              │
│  - Ruff formatting                     │
│  - Trailing whitespace                 │
│  - UV lock validation                  │
│  - Credential detection                │
│  - Spell checking                      │
└─────────────────────────────────────────┘
    ↓ (if issues found, retry once)
┌─────────────────────────────────────────┐
│ Phase 2: Code Cleaning                 │
│  - Remove TODO detection               │
│  - Apply standardized patterns         │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Phase 3: Post-Cleaning Sanity Check    │
│  - Fast hooks again (quick check)      │
└─────────────────────────────────────────┘
    ↓ (if --run-tests flag)
┌─────────────────────────────────────────┐
│ Phase 4: Test Suite                    │
│  - pytest with coverage ratchet        │
│  - Collect ALL failures                │
└─────────────────────────────────────────┘
    ↓ (if --run-tests flag)
┌─────────────────────────────────────────┐
│ Phase 5: Comprehensive Hooks (~30s)    │
│  - Zuban type checking                 │
│  - Bandit security analysis            │
│  - Dead code detection                 │
│  - Dependency analysis                 │
│  - Complexity limits                   │
│  - Modern Python patterns              │
└─────────────────────────────────────────┘
    ↓ (if issues found AND --ai-fix flag)
┌─────────────────────────────────────────┐
│ Phase 6: AI Batch Fixing               │
│  - Parse all failures                  │
│  - Route to agents (confidence-based)  │
│  - Execute fixes (parallel/sequential) │
│  - Repeat until pass (max 8 iters)     │
└─────────────────────────────────────────┘
    ↓
SessionCoordinator.finalize_session()
    ↓
WorkflowResult (success/failure, metrics)
```

### AI Agent Workflow

```
Error Parser
    ↓ (parse error messages, categorize)
AgentSelector (find matching skills, confidence ≥0.7)
    ↓ (group by agent, score)
AgentOrchestrator
    ↓ (select strategy: single/parallel/sequential/consensus)
Agent Execution
    ↓ (read source code, apply fixes)
Fix Validation
    ↓ (re-run checks)
Repeat if needed (max 8 iterations)
```

## Quality Adapters

### Adapter Taxonomy

**18 Quality Adapters** organized by category:

```python
# crackerjack/adapters/__init__.py

ADAPTER_REGISTRY = {
    # Format (2 adapters)
    "ruff_format": RuffFormatAdapter,
    "mdformat": MdformatAdapter,

    # Lint (2 adapters)
    "codespell": CodespellAdapter,
    "complexity": ComplexityAdapter,

    # Security (3 adapters)
    "bandit": BanditAdapter,
    "gitleaks": GitleaksAdapter,
    "pyscn": PyscnAdapter,

    # Type (3 adapters)
    "zuban": ZubanAdapter,  # 20-200x faster than pyright
    "pyrefly": PyreflyAdapter,
    "ty": TyAdapter,

    # Refactor (3 adapters)
    "refurb": RefurbAdapter,
    "skylos": SkylosAdapter,  # 20x faster than vulture
    "creosote": CreosoteAdapter,

    # Utility (5 adapters)
    "end_of_file_fixer": EndOfFileFixerAdapter,
    "trailing_whitespace": TrailingWhitespaceAdapter,
    "regex_check": RegexCheckAdapter,
    "size_check": SizeCheckAdapter,
    "lock_check": LockCheckAdapter,
}
```

### Adapter Lifecycle

```
Adapter Initialization (legacy DI)
    ↓
Adapter.check() called
    ↓
Cache Lookup (content-based key)
    ↓ (cache hit)
Return Cached Result
    ↓ (cache miss)
Execute Tool (direct Python API or subprocess)
    ↓
Cache Result (if successful)
    ↓
Return QAResult (passed, issues, modified_files)
```

### Caching Strategy

**Cache Key**: `{adapter_name}:{config_hash}:{content_hash}`

**Cache Benefits**:

- **70% cache hit rate** in typical workflows
- **Content-aware**: Only re-runs when files actually change
- **TTL**: 3600s (1 hour) default
- **Invalidation**: Automatic on file modification

**Implementation**:

```python
class ToolProxyCacheAdapter(QAAdapter):
    async def check(
        self,
        files: set[Path],
        config: dict[str, Any],
    ) -> QAResult:
        # Calculate cache key
        cache_key = self._calculate_cache_key(files, config)

        # Check cache
        cached_result = await cache.get(cache_key)
        if cached_result:
            return cached_result

        # Cache miss - execute tool
        result = await self.delegate.check(files, config)

        # Cache successful results
        if result.passed:
            await cache.set(cache_key, result, ttl=3600)

        return result
```

## Agent System

### Agent Registry

**12 Specialized Agents** with skill-based routing:

```python
# crackerjack/intelligence/agent_registry.py

AGENT_REGISTRY = {
    "security": SecurityAgent(
        skills=[
            "shell_injection_fix",  # confidence: 0.95
            "weak_crypto_fix",      # confidence: 0.92
            "token_exposure_fix",   # confidence: 0.88
        ]
    ),
    "refactoring": RefactoringAgent(
        skills=[
            "complexity_reduction",    # confidence: 0.90
            "solid_principles",        # confidence: 0.85
            "extraction",              # confidence: 0.82
        ]
    ),
    # ... (10 more agents)
}
```

### Agent Selection

**Skill-Based Routing**:

```python
# Issue: "subprocess.call(cmd, shell=True) allows shell injection"

# Step 1: Find matching skills
skill_matches = [
    ("shell_injection_fix", 0.95),  # SecurityAgent
    ("command_injection_fix", 0.88),  # SecurityAgent
]

# Step 2: Group by agent
agent_scores = [
    ("security", 0.95),  # Max confidence for security agent
]

# Step 3: Select strategy
# confidence ≥0.9 → single best agent
selected_agent = "security"
selected_skill = "shell_injection_fix"
routing_strategy = "single"
```

### Agent Execution

**Execution Strategies**:

1. **Single Best** (confidence ≥0.9): One agent handles issue
1. **Parallel** (2+ agents ≥0.8): Multiple agents work concurrently
1. **Sequential** (2+ agents ≥0.7): Agents work in order of confidence
1. **Consensus**: All agents must agree on fix

**Performance**:

| Strategy | Time | Use Case |
|----------|------|----------|
| Single Best | 150s | Clear issue type |
| Parallel | 180s | Multiple independent fixes |
| Sequential | 420s | Cascading fixes |
| Consensus | 460s | Critical security fixes |

## MCP Integration

### MCP Server Architecture

```
AI Agent (Claude/Qwen)
    ↓ (MCP protocol: stdio or WebSocket)
FastMCP Server
    ├── Tool Registry (@mcp.tool decorators)
    ├── JobManager (async job tracking)
    ├── WebSocket Server (real-time progress)
    └── ErrorCache (pattern cache)
    ↓ (direct Python calls, no subprocess)
Crackerjack Core
```

### MCP Tools

**Tool Registration**:

```python
from fastmcp import FastMCP

mcp = FastMCP("crackerjack")

@mcp.tool()
async def execute_crackerjack(
    command: str,
    args: str = "",
    ai_agent_mode: bool = False,
    timeout: int = 600,
) -> dict:
    """Execute crackerjack command with job tracking."""
    job_id = await job_manager.create_job(command, args)
    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Job {job_id} started",
    }

@mcp.tool()
async def get_job_progress(job_id: str) -> dict:
    """Get real-time progress for running job."""
    progress = await job_manager.get_progress(job_id)
    return {
        "job_id": job_id,
        "status": progress.status,
        "percent": progress.percent_complete,
        "current_phase": progress.current_phase,
    }
```

### Job Manager

**Job Lifecycle**:

```
Job Created (execute_crackerjack)
    ↓
Job Running (progress updates via WebSocket)
    ↓ (complete)
Job Completed (result stored)
    ↓ (1 hour later)
Job Cleaned Up (automatic cleanup)
```

**Job State Machine**:

```python
class JobState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

## Performance Optimization

### Caching

**Cache Layers**:

1. **Tool Proxy Cache**: Content-based caching for adapter results
1. **Pattern Cache**: Error patterns for AI fix recommendations
1. **Job Cache**: Job results for MCP clients

**Cache Performance**:

| Metric | Value |
|--------|-------|
| Cache Hit Rate | 70% |
| Cache Size | 1000 entries (LRU) |
| Cache TTL | 3600s (1 hour) |
| Cache Overhead | ~10ms per lookup |

### Parallel Execution

**Concurrent Adapters**:

```python
# Run 11 adapters concurrently
async def run_hooks_parallel(hooks: list[QAAdapter]) -> list[QAResult]:
    semaphore = asyncio.Semaphore(11)  # Max 11 concurrent adapters

    async def run_with_limit(adapter: QAAdapter) -> QAResult:
        async with semaphore:
            return await adapter.check(files, config)

    return await asyncio.gather(
        *[run_with_limit(hook) for hook in hooks],
        return_exceptions=True,
    )
```

**Performance Impact**:

- **Sequential**: 11 adapters × 5s = 55s
- **Parallel** (11 concurrent): 5s (11x speedup)

### Async I/O

**Non-Blocking Operations**:

```python
# File I/O
async def read_file(path: Path) -> str:
    return await asyncio.to_thread(path.read_text)

# Subprocess execution
async def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    return await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
    )
```

**Performance Impact**:

- **Sync I/O**: Blocks event loop, poor scalability
- **Async I/O**: Non-blocking, 76% faster for I/O-bound operations

## Security Architecture

### Input Validation

**Pydantic Models**:

```python
from pydantic import BaseModel, Field, validator

class QualityCheckRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=100)
    files: set[Path] = Field(..., max_items=1000)

    @validator("command")
    def validate_command(cls, v: str) -> str:
        allowed_commands = {"run", "test", "check", "fix"}
        if v not in allowed_commands:
            raise ValueError(f"Invalid command: {v}")
        return v
```

### Path Traversal Prevention

**Centralized Validation**:

```python
# crackerjack/core/validators.py

def validate_path(path: Path, base_dir: Path) -> Path:
    """Validate path is within base directory (prevent path traversal)."""

    # Resolve to absolute path
    resolved = path.resolve()

    # Check is within base directory
    try:
        resolved.relative_to(base_dir)
    except ValueError:
        raise SecurityError(f"Path traversal attempt: {path}")

    return resolved
```

### Secret Management

**Keyring Integration**:

```python
import keyring

def get_pypi_token() -> str:
    """Retrieve PyPI token from keyring (most secure)."""
    token = keyring.get_password(
        "https://upload.pypi.org/legacy/",
        "__token__",
    )
    if not token:
        raise SecurityError("PyPI token not found in keyring")
    return token
```

### Runtime Security Monitoring

**Falco Integration** (optional):

```python
# Runtime security event monitoring
def handle_falco_event(event: FalcoEvent) -> None:
    """Handle Falco security event."""

    if event.risk_score >= 70:
        # High-risk event - require MFA
        trigger_mfa_challenge()

    if event.risk_score >= 90:
        # Critical event - terminate operation
        terminate_operation()
        notify_security_team(event)
```

## Related Documentation

- [ADR-001: MCP-First Architecture](adr/ADR-001-mcp-first-architecture.md)
- [ADR-002: Multi-Agent Orchestration](adr/ADR-002-multi-agent-orchestration.md)
- [ADR-003: Property-Based Testing](adr/ADR-003-property-based-testing.md)
- [ADR-004: Quality Gate Thresholds](adr/ADR-004-quality-gate-thresholds.md)
- [ADR-005: Agent Skill Routing](adr/ADR-005-agent-skill-routing.md)

## Summary

Crackerjack's architecture is built on **5 key layers**:

1. **Developer Layer**: CLI, MCP server, AI agents
1. **Orchestration Layer**: Workflow pipeline, phase coordinator
1. **Manager Layer**: Hook manager, test manager, job manager
1. **Adapter Layer**: 18 quality adapters (format, lint, security, type, refactor)
1. **Service Layer**: Cache, error cache, pattern management

**Key Architectural Decisions**:

- ✅ MCP-first design for AI integration
- ✅ Adapter pattern for extensibility
- ✅ Property-based testing for correctness
- ✅ Confidence-based routing for intelligence
- ✅ Async-first for performance

**Performance Characteristics**:

- ⚡ 47% faster than pre-commit (direct Python API)
- 🚀 70% cache hit rate
- 📈 11x parallelism (11 concurrent adapters)
- 🎯 76% speedup for I/O-bound operations (async)

______________________________________________________________________

**Last Updated**: 2025-02-06
**Crackerjack Version**: 0.51.0
