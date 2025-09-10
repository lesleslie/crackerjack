# Crackerjack API Reference

This document provides comprehensive API documentation for Crackerjack's services, adapters, and MCP integration.

## Table of Contents

- [Core Services](#core-services)
- [AI Agent System](#ai-agent-system)
- [High-Performance Adapters](#high-performance-adapters)
- [Monitoring & Performance](#monitoring--performance)
- [MCP Server Integration](#mcp-server-integration)
- [WebSocket API](#websocket-api)
- [CLI Interface](#cli-interface)
- [Configuration System](#configuration-system)

## Core Services

### WorkflowOrchestrator

**Location**: `crackerjack.core.workflow_orchestrator.WorkflowOrchestrator`

Primary orchestration service coordinating all quality workflow phases.

**Key Methods**:

```python
async def execute_workflow(self, options: Options) -> WorkflowResult:
    """Execute complete quality workflow with specified options."""


async def execute_stage(
    self, stage: WorkflowStage, context: ExecutionContext
) -> StageResult:
    """Execute specific workflow stage."""


async def get_workflow_status(self) -> WorkflowStatus:
    """Get current workflow execution status."""
```

### AgentCoordinator

**Location**: `crackerjack.coordinators.agent_coordinator.AgentCoordinator`

Coordinates AI agent execution with parallel processing and intelligent routing.

**Key Methods**:

```python
async def handle_issues_parallel(self, issues: list[Issue]) -> FixResult:
    """Process issues in parallel using optimized agent selection."""


async def route_to_best_agent(self, issue: Issue) -> SubAgent:
    """Route issue to highest-confidence agent (≥0.7 threshold)."""


async def batch_process_by_type(
    self, issues_by_type: dict[IssueType, list[Issue]]
) -> list[FixResult]:
    """Batch process issues by type for optimal performance."""
```

### SessionCoordinator

**Location**: `crackerjack.coordinators.session_coordinator.SessionCoordinator`

Manages execution sessions with phase tracking and progress monitoring.

**Key Methods**:

```python
async def start_session(self, session_id: str, options: Options) -> Session:
    """Initialize new quality enforcement session."""


async def track_progress(self, session_id: str, phase: WorkflowPhase) -> ProgressUpdate:
    """Track and broadcast session progress updates."""


def get_session_metrics(self, session_id: str) -> SessionMetrics:
    """Get comprehensive session performance metrics."""
```

## AI Agent System

### Specialized Sub-Agents

All agents implement the `SubAgent` protocol with confidence-based routing.

#### RefactoringAgent (Confidence: 0.9)

**Location**: `crackerjack.agents.refactoring_agent.RefactoringAgent`

Handles complexity reduction and code structure improvements.

**Capabilities**:

- Complexity reduction to ≤15 per function
- Method extraction and SOLID principle application
- Dead code elimination
- Code structure optimization

```python
async def analyze_and_fix(self, issue: Issue) -> FixResult:
    """Analyze complexity issues and apply refactoring patterns."""


def get_confidence_score(self, issue: Issue) -> float:
    """Return confidence score for handling this issue type."""
```

#### SecurityAgent (Confidence: 0.8)

**Location**: `crackerjack.agents.security_agent.SecurityAgent`

Fixes security vulnerabilities and unsafe patterns.

**Capabilities**:

- Shell injection prevention
- Hardcoded credential removal
- Unsafe library usage fixes
- Path traversal prevention

#### PerformanceAgent (Confidence: 0.85)

**Location**: `crackerjack.agents.performance_agent.PerformanceAgent`

Optimizes algorithm performance and identifies bottlenecks.

**Capabilities**:

- O(n²) pattern detection and optimization
- String building optimization
- Loop optimization
- Memory usage improvements

#### Additional Agents

- **DocumentationAgent**: Changelog generation, markdown consistency
- **TestCreationAgent**: Test failure fixes, fixture management
- **DRYAgent**: Code duplication elimination
- **FormattingAgent**: Code style and import organization
- **ImportOptimizationAgent**: Import cleanup and restructuring
- **TestSpecialistAgent**: Advanced testing scenarios

### Agent Configuration

```python
from crackerjack.models.protocols import AgentConfigProtocol


class AgentConfig(AgentConfigProtocol):
    confidence_threshold: float = 0.7
    parallel_processing: bool = True
    batch_size: int = 10
    timeout_seconds: int = 300
    enable_caching: bool = True
```

## High-Performance Adapters

### Rust Tool Integration

#### SkylosAdapter

**Location**: `crackerjack.adapters.skylos_adapter.SkylosAdapter`

Ultra-fast dead code detection using Rust-powered Skylos tool.

**Performance**: 20x faster than vulture

```python
class SkylosAdapter(RustToolProtocol):
    async def detect_dead_code(self, file_paths: list[Path]) -> list[DeadCodeIssue]:
        """Detect dead code with 20x performance improvement."""

    async def analyze_imports(self, file_path: Path) -> ImportAnalysis:
        """Analyze import usage patterns."""

    def get_performance_stats(self) -> PerformanceStats:
        """Get Rust tool performance metrics."""
```

#### ZubanAdapter

**Location**: `crackerjack.adapters.zuban_adapter.ZubanAdapter`

Lightning-fast type checking using Rust-powered Zuban tool.

**Performance**: 20-200x faster than pyright

```python
class ZubanAdapter(RustToolProtocol):
    async def check_types(self, file_paths: list[Path]) -> list[TypeIssue]:
        """Perform type checking with 20-200x performance improvement."""

    async def validate_annotations(self, file_path: Path) -> list[AnnotationIssue]:
        """Validate type annotations."""

    def get_benchmark_results(self) -> BenchmarkResults:
        """Get performance benchmark data."""
```

### RustToolManager

**Location**: `crackerjack.adapters.rust_tool_manager.RustToolManager`

Manages lifecycle and execution of Rust-based analysis tools.

```python
class RustToolManager:
    async def execute_tool(self, tool_name: str, args: list[str]) -> ToolResult:
        """Execute Rust tool with validated arguments."""

    def get_tool_performance(self, tool_name: str) -> ToolMetrics:
        """Get performance metrics for specific tool."""

    async def health_check(self) -> dict[str, ToolHealth]:
        """Check health status of all registered tools."""
```

## Monitoring & Performance

### PerformanceBenchmarker

**Location**: `crackerjack.services.performance_benchmarks.PerformanceBenchmarker`

Comprehensive performance benchmarking and monitoring system.

```python
class PerformanceBenchmarker:
    async def run_comprehensive_benchmark(self) -> BenchmarkSuite:
        """Execute complete performance benchmark suite."""

    async def benchmark_memory_optimization(self) -> BenchmarkResult:
        """Benchmark memory optimization effectiveness."""

    async def benchmark_caching_performance(self) -> BenchmarkResult:
        """Benchmark caching system performance."""

    async def benchmark_async_workflows(self) -> BenchmarkResult:
        """Benchmark asynchronous workflow performance."""

    def export_benchmark_results(
        self, suite: BenchmarkSuite, output_path: Path
    ) -> None:
        """Export benchmark results to JSON format."""
```

**BenchmarkResult Schema**:

```python
@dataclass
class BenchmarkResult:
    test_name: str
    baseline_time_seconds: float
    optimized_time_seconds: float
    memory_baseline_mb: float
    memory_optimized_mb: float
    cache_hits: int = 0
    cache_misses: int = 0
    parallel_operations: int = 0
    sequential_operations: int = 0

    @property
    def time_improvement_percentage(self) -> float:
        """Calculate time improvement percentage."""

    @property
    def cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
```

### Performance Cache

**Location**: `crackerjack.services.performance_cache.PerformanceCache`

High-performance caching system with TTL and statistics.

```python
class PerformanceCache:
    async def get_async(self, key: str) -> Any | None:
        """Retrieve cached value asynchronously."""

    async def set_async(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Store value in cache with TTL."""

    def get_stats(self) -> CacheStats:
        """Get cache performance statistics."""

    def clear(self) -> None:
        """Clear all cached data."""
```

### Memory Optimizer

**Location**: `crackerjack.services.memory_optimizer.MemoryOptimizer`

Memory optimization service with lazy loading and garbage collection management.

```python
class MemoryOptimizer:
    def record_checkpoint(self, name: str) -> float:
        """Record memory checkpoint for benchmarking."""

    def optimize_memory_usage(self) -> MemoryOptimizationResult:
        """Optimize current memory usage patterns."""

    def get_memory_stats(self) -> MemoryStats:
        """Get current memory usage statistics."""


class LazyLoader:
    def __init__(self, factory: Callable, identifier: str):
        """Initialize lazy loader with factory function."""

    def load(self) -> Any:
        """Load resource when first accessed."""
```

## MCP Server Integration

### Server Configuration

**Default Ports**:

- HTTP MCP Server: `8676`
- WebSocket Server: `8675`
- Host: `127.0.0.1`

### Available MCP Tools

#### Core Execution Tools

**`execute_crackerjack`**

```python
def execute_crackerjack(
    command: str, args: str = "", timeout: int = 300, working_directory: str = "."
) -> ExecutionResult:
    """Execute crackerjack command with job tracking."""
```

**`run_crackerjack_stage`**

```python
def run_crackerjack_stage(
    stage: str,  # "fast", "comprehensive", "tests"
    args: str = "",
    kwargs: str = "{}",
) -> StageResult:
    """Execute specific crackerjack workflow stage."""
```

#### Monitoring Tools

**`get_job_progress`**

```python
def get_job_progress(job_id: str) -> ProgressUpdate:
    """Get real-time progress for running job."""
```

**`get_comprehensive_status`**

```python
def get_comprehensive_status() -> ComprehensiveStatus:
    """Get complete system status including all services."""
```

**`get_server_stats`**

```python
def get_server_stats() -> ServerStatistics:
    """Get MCP server performance statistics."""
```

#### Analysis Tools

**`smart_error_analysis`**

```python
def smart_error_analysis(use_cache: bool = True) -> ErrorAnalysisResult:
    """Perform AI-powered error analysis with caching."""
```

**`analyze_errors`**

```python
def analyze_errors(args: str, kwargs: str) -> ErrorCategoryReport:
    """Analyze and categorize detected errors."""
```

#### Session Management

**`session_management`**

```python
def session_management(
    action: str,  # "create", "checkpoint", "restore", "cleanup"
    checkpoint_name: str | None = None,
) -> SessionResult:
    """Manage execution sessions with checkpoints."""
```

### Intelligence System

**`intelligence_system_status`**

```python
def intelligence_system_status() -> IntelligenceStatus:
    """Get AI agent system status and capabilities."""
```

**`agent_performance_analysis`**

```python
def agent_performance_analysis() -> AgentPerformanceReport:
    """Get detailed performance analysis of all agents."""
```

**`get_next_action`**

```python
def get_next_action() -> ActionRecommendation:
    """Get intelligent recommendation for next action."""
```

## WebSocket API

### Connection

**Endpoint**: `ws://localhost:8675`

### Progress Streaming

**`/ws/progress/{job_id}`**

Real-time progress updates for running jobs.

**Message Format**:

```json
{
    "job_id": "unique_job_identifier",
    "stage": "current_workflow_stage",
    "progress": 0.75,
    "status": "running|completed|failed",
    "details": {
        "current_operation": "Type checking with Zuban",
        "files_processed": 150,
        "total_files": 200,
        "errors_found": 3,
        "fixes_applied": 12
    },
    "timestamp": "2024-01-20T10:30:00Z"
}
```

### Dashboard Integration

**`/ws/dashboard`**

Real-time dashboard updates with system metrics.

**Message Types**:

- `performance_metrics`: Performance benchmark updates
- `cache_statistics`: Cache hit/miss ratios and performance
- `agent_activity`: AI agent execution status
- `quality_scores`: Code quality metric trends

## CLI Interface

### Command-Line Arguments

#### Core Workflow Options

```bash
--run-tests              # Execute full test suite
--ai-fix                 # Enable AI auto-fixing mode
--ai-debug              # Enable AI debugging with verbose output
--full-release LEVEL     # Complete release workflow (patch|minor|major)
--skip-hooks            # Skip pre-commit hooks during iteration
--strip-code            # Remove docstrings/comments for production
```

#### Monitoring & Performance Options

```bash
--dashboard             # Launch comprehensive monitoring dashboard
--unified-dashboard     # Launch unified real-time dashboard
--monitor              # Multi-project progress monitor
--enhanced-monitor      # Enhanced monitoring with pattern detection
--benchmark            # Run in benchmark mode
--cache-stats          # Display cache performance statistics
--clear-cache          # Clear all performance caches
--watchdog             # Service watchdog with auto-restart
```

#### Server Management Options

```bash
--start-mcp-server      # Start MCP server (HTTP + WebSocket)
--stop-mcp-server       # Stop running MCP server
--restart-mcp-server    # Restart MCP server
--start-websocket-server # Start WebSocket server only
```

#### Development Options

```bash
--verbose              # Detailed output for debugging
--interactive          # Rich UI interface
--commit               # Auto-commit and push changes
--dev                  # Enable development mode
--fast                 # Use faster execution (fewer checks)
--thorough             # Use comprehensive quality checks
--test-workers N       # Specify number of test worker processes
```

### Options Data Model

```python
from crackerjack.cli.options import Options


class Options(BaseModel):
    # Execution Options
    strip_code: bool = False  # Remove docstrings/comments
    ai_fix: bool = False  # Enable AI auto-fixing
    ai_fix_verbose: bool = False  # Verbose AI debugging
    run_tests: bool = False  # Execute test suite
    skip_precommit: bool = False  # Skip pre-commit hooks
    quick_checks: bool = False  # Fast execution mode
    comprehensive: bool = False  # Thorough quality checks

    # Release Options
    full_release: BumpOption | None = None  # Version bump level
    version_bump: BumpOption | None = None  # Publish workflow

    # Monitoring Options
    dashboard: bool = False  # Launch dashboard
    unified_dashboard: bool = False  # Unified dashboard
    monitor: bool = False  # Progress monitor
    benchmark: bool = False  # Benchmark mode
    cache_stats: bool = False  # Show cache stats
    clear_cache: bool = False  # Clear caches

    # Server Options
    start_mcp_server: bool = False  # Start MCP server
    restart_mcp_server: bool = False  # Restart MCP server
    watchdog: bool = False  # Service watchdog

    # Development Options
    verbose: bool = False  # Detailed output
    interactive: bool = False  # Rich UI
    commit: bool = False  # Auto-commit changes
    dev: bool = False  # Development mode

    # Test Configuration
    test_workers: int | None = None  # Test worker count
```

## Configuration System

### Project Configuration

**File**: `pyproject.toml`

```toml
[tool.crackerjack]
mcp_http_port = 8676
mcp_http_host = "127.0.0.1"
mcp_websocket_port = 8675
mcp_http_enabled = true

# Performance tuning
cache_ttl_seconds = 300
max_parallel_agents = 4
benchmark_iterations = 3

# Rust tool configuration
skylos_enabled = true
zuban_enabled = true
rust_tool_timeout = 60
```

### Runtime Configuration

```python
from crackerjack.models.config import CrackerjackConfig


class CrackerjackConfig:
    # Server Configuration
    mcp_http_port: int = 8676
    mcp_websocket_port: int = 8675
    mcp_http_enabled: bool = True

    # Performance Configuration
    cache_ttl_seconds: int = 300
    max_parallel_agents: int = 4
    benchmark_iterations: int = 3

    # Rust Tool Configuration
    skylos_enabled: bool = True
    zuban_enabled: bool = True
    rust_tool_timeout: int = 60

    # AI Agent Configuration
    agent_confidence_threshold: float = 0.7
    enable_agent_caching: bool = True
    agent_timeout_seconds: int = 300
```

### Environment Variables

```bash
# MCP Server Configuration
CRACKERJACK_MCP_PORT=8676
CRACKERJACK_WEBSOCKET_PORT=8675
CRACKERJACK_MCP_HOST=127.0.0.1

# Performance Configuration
CRACKERJACK_CACHE_TTL=300
CRACKERJACK_MAX_AGENTS=4
CRACKERJACK_BENCHMARK_ITERATIONS=3

# AI Agent Configuration
CRACKERJACK_AI_CONFIDENCE=0.7
CRACKERJACK_AGENT_TIMEOUT=300
CRACKERJACK_ENABLE_AGENT_CACHE=true

# Development
CRACKERJACK_LOG_LEVEL=INFO
CRACKERJACK_DEBUG_MODE=false
```

## Type Definitions

### Core Data Models

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


class WorkflowStage(Enum):
    FAST_HOOKS = "fast_hooks"
    TEST_EXECUTION = "test_execution"
    COMPREHENSIVE_HOOKS = "comprehensive_hooks"
    AI_FIXING = "ai_fixing"


class IssueType(Enum):
    COMPLEXITY = "complexity"
    SECURITY = "security"
    PERFORMANCE = "performance"
    FORMATTING = "formatting"
    DOCUMENTATION = "documentation"
    TESTING = "testing"


@dataclass
class Issue:
    type: IssueType
    severity: str
    message: str
    file_path: Optional[str]
    line_number: Optional[int]
    confidence: float


@dataclass
class FixResult:
    success: bool
    issue: Issue
    fix_applied: str
    agent_used: str
    execution_time: float


@dataclass
class WorkflowResult:
    success: bool
    stages_completed: List[WorkflowStage]
    total_issues: int
    issues_fixed: int
    execution_time: float
    performance_metrics: Dict[str, Any]
```

This comprehensive API reference documents all the major services, adapters, and capabilities added in the recent feature implementation phases, providing both human developers and AI agents with complete understanding of the Crackerjack system's capabilities.
