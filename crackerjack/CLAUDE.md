# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Clean Code Philosophy (READ FIRST)

**EVERY LINE OF CODE IS A LIABILITY. The best code is no code.**

- **DRY (Don't Repeat Yourself)**: If you write it twice, you're doing it wrong
- **YAGNI (You Ain't Gonna Need It)**: Build only what's needed NOW
- **KISS (Keep It Simple, Stupid)**: Complexity is the enemy of maintainability
- **Less is More**: Prefer 10 lines that are clear over 100 that are clever
- **Code is Read 10x More Than Written**: Optimize for readability
- **Self-Documenting Code**: Code should explain itself; comments only for "why", not "what". Variable names should **ALWAYS** be clear and descriptive, even in inline map/filter functions.

## Project Overview

Crackerjack is an opinionated Python project management tool that unifies UV, Ruff, pytest, and pre-commit into a single workflow. It enforces consistent code quality from setup to deployment and includes AI agent integration via MCP (Model Context Protocol).

**Key Dependencies**: Python 3.13+, UV package manager, pre-commit hooks, pytest

## Core Development Commands

### Primary Workflows

```bash
# Quality checks only (most common during development)
python -m crackerjack

# With testing
python -m crackerjack -t

# Code cleaning with TODO detection (blocks if TODOs found)
python -m crackerjack -x

# Full release workflow with version bump and publishing
python -m crackerjack -a patch

# Interactive mode with rich UI
python -m crackerjack -i

# Skip hooks during development iterations
python -m crackerjack --skip-hooks

# AI Agent mode with autonomous auto-fixing (STANDARD PROCESS)
python -m crackerjack --ai-agent -t

# AI Agent mode with full debugging and verbose output
python -m crackerjack --ai-debug -t

# Start MCP server for AI agent integration
python -m crackerjack --start-mcp-server

# Stop all running MCP servers
python -m crackerjack --stop-mcp-server

# Restart MCP server (stop and start again)
python -m crackerjack --restart-mcp-server

# Start dedicated WebSocket progress server (runs on localhost:8675)
python -m crackerjack --start-websocket-server

# Start multi-project progress monitor with Textual TUI
python -m crackerjack --monitor

# Start enhanced progress monitor with advanced MetricCard widgets (recommended)
python -m crackerjack --enhanced-monitor

# Start MCP server with custom WebSocket port
python -m crackerjack --start-mcp-server --websocket-port 8675

# Restart MCP server with custom WebSocket port
python -m crackerjack --restart-mcp-server --websocket-port 8675

# Start service watchdog to monitor and auto-restart MCP and WebSocket servers
python -m crackerjack --watchdog
```

### Terminal Recovery

**If your terminal gets stuck after quitting the monitor (no history, character input issues):**

```bash
# Option 1: Use the recovery script
./fix_terminal.sh

# Option 2: Manual recovery commands
stty sane; reset; exec $SHELL -l

# Option 3: Simple reset
reset
```

**The enhanced terminal restoration automatically handles:**

- Mouse tracking disabling
- Alternate screen buffer exit
- Focus events restoration
- Bracketed paste mode cleanup
- Full terminal input/output restoration

### AI Agent Auto-Fixing Process

**The AI agent provides intelligent, autonomous code fixing that goes far beyond basic tool auto-fixes:**

#### Two Types of Auto-Fixing

**1. Hook Auto-Fix Modes (Limited Scope)**

- Basic formatting tools like `ruff --fix`, `trailing-whitespace --fix`
- Only handle simple style issues (whitespace, import order, basic formatting)
- Cannot fix logic errors, type issues, security problems, or test failures

**2. AI Agent Auto-Fixing (Comprehensive Intelligence)**

- Analyzes ALL error types: hooks, tests, type checking, security, complexity
- Reads source code, understands context, and makes intelligent modifications
- Fixes actual bugs, adds missing type annotations, resolves test failures
- Handles complex issues that require code understanding and logic changes

#### Standard AI Agent Iterative Process

**This is the recommended standard process for achieving code quality compliance:**

```bash
# AI Agent mode with automatic fixing between iterations
python -m crackerjack --ai-agent -t

# The AI agent follows this optimal workflow order in each iteration:
# 1. Fast Hooks (formatting) → Retry once if any fail (fixes often cascade)
# 2. Full Test Suite → Collect ALL test failures (don't stop on first)
# 3. Comprehensive Hooks → Collect ALL quality issues (don't stop on first)
# 4. AI Analysis & Batch Fixing → Fix ALL collected issues in one pass
# 5. Repeat entire cycle until all checks pass (up to 10 iterations)

# CRITICAL: The AI agent only moves to the next iteration AFTER applying fixes
# This ensures that each iteration validates the fixes from the previous iteration
```

**What the AI Agent Auto-Fixes:**

- **Type Errors**: Adds missing type annotations, fixes type mismatches
- **Security Issues**: Removes hardcoded paths, fixes subprocess vulnerabilities
- **Dead Code**: Removes unused imports, variables, and functions
- **Test Failures**: Fixes missing fixtures, import errors, assertion issues
- **Code Quality**: Applies refactoring suggestions, reduces complexity
- **Dependency Issues**: Removes unused dependencies from pyproject.toml
- **Hook Failures**: All formatting, linting, and style issues

**Benefits of AI Agent Auto-Fixing:**

- **Autonomous Operation**: Requires no manual intervention
- **Intelligent Analysis**: Understands code context and intent
- **Comprehensive Coverage**: Fixes all error types, not just formatting
- **Iterative Improvement**: Continues until perfect code quality achieved
- **Learning Capability**: Adapts fixing strategies based on codebase patterns

#### Sub-Agent Architecture

**Crackerjack uses specialized sub-agents for domain-specific code quality issues:**

**Available Sub-Agents:**

- **DocumentationAgent**: Documentation consistency and changelog management

  - **Primary Expertise**: `IssueType.DOCUMENTATION` (documentation consistency, changelog updates)
  - **Capabilities**:
    - Auto-generates changelog entries from git commits during version bumps
    - Maintains consistency across all .md files (agent counts, references)
    - Updates README examples when APIs change
    - Adds newly discovered error patterns to CLAUDE.md
    - Cross-validates documentation references
    - Integrates with publish workflow for automatic changelog updates
  - **Philosophy Alignment**: Reduces manual documentation maintenance (YAGNI principle)
  - **Confidence**: 0.8 for documentation issues

- **RefactoringAgent**: Structural code improvements and complexity reduction

  - **Primary Expertise**: `IssueType.COMPLEXITY` (cognitive complexity ≤13)
  - **Secondary Expertise**: `IssueType.DEAD_CODE` (unused imports, variables, functions)
  - **Capabilities**:
    - Breaks down complex functions into helper methods
    - Removes unused imports, variables, and functions using AST analysis
    - Extracts common patterns into reusable utilities
    - Applies dependency injection and Protocol patterns
  - **Philosophy Alignment**: Perfect fit with DRY, YAGNI, KISS principles

- **PerformanceAgent**: Performance optimization and algorithmic improvements

  - **Primary Expertise**: `IssueType.PERFORMANCE` (performance anti-patterns and bottlenecks)
  - **Capabilities**:
    - Detects and fixes nested loops with O(n²) complexity
    - Transforms inefficient list concatenation (`list += [item]` → `list.append(item)`)
    - Optimizes string building (concatenation → list.append + join pattern)
    - Identifies repeated expensive operations in loops (file I/O, function calls)
    - Applies AST-based pattern recognition for accurate detection
    - **Real Code Transformation**: Actually modifies code, not just comments
  - **Philosophy Alignment**: KISS principle through algorithmic efficiency

- **DRYAgent**: Don't Repeat Yourself violation detection and fixing

  - **Primary Expertise**: `IssueType.DRY_VIOLATION` (code duplication and repetition)
  - **Capabilities**:
    - Detects duplicate code patterns and repeated functionality
    - Suggests extracting common patterns to utility functions
    - Recommends creating base classes or mixins for repeated functionality
    - Identifies opportunities for code consolidation and refactoring
  - **Philosophy Alignment**: Core DRY principle enforcement

- **FormattingAgent**: Code style and formatting issues

  - **Primary Expertise**: `IssueType.FORMATTING`, `IssueType.IMPORT_ERROR`
  - **Capabilities**:
    - Handles code style and formatting violations
    - Fixes import-related formatting issues
    - Ensures consistent code formatting standards

- **SecurityAgent**: Security vulnerabilities and best practices

  - **Primary Expertise**: `IssueType.SECURITY`
  - **Capabilities**:
    - Detects and fixes security vulnerabilities (hardcoded paths, unsafe operations)
    - Applies security best practices
    - Identifies potential security risks in code patterns

- **ImportOptimizationAgent**: Import statement optimization and cleanup

  - **Primary Expertise**: `IssueType.IMPORT_ERROR`, `IssueType.DEAD_CODE`
  - **Capabilities**:
    - Optimizes import statements and organization
    - Removes unused imports and dead code
    - Consolidates and reorganizes import patterns
    - **Real Code Transformation**: Restructures import statements

- **TestCreationAgent**: Test coverage and quality improvements

  - **Primary Expertise**: `IssueType.TEST_FAILURE`, `IssueType.DEPENDENCY`
  - **Capabilities**:
    - Fixes test failures and missing test dependencies
    - Improves test coverage and quality
    - Handles dependency-related testing issues

- **TestSpecialistAgent**: Advanced testing scenarios and fixtures

  - **Primary Expertise**: `IssueType.IMPORT_ERROR`, `IssueType.TEST_FAILURE`
  - **Capabilities**:
    - Handles complex testing scenarios and fixture management
    - Fixes advanced test failures and import issues in test files
    - Specializes in testing framework integration

**Agent Coordination:**

- **AgentCoordinator** routes issues to appropriate agents based on confidence scoring
- **Single-agent mode**: High confidence (≥0.7) issues handled by best-match agent
- **Collaborative mode**: Lower confidence issues processed by multiple agents
- **Batch processing**: Issues grouped by type for efficient parallel processing

**Agent Integration:**

```python
# Automatic integration - all agents are registered and coordinated
# 9 total agents: DocumentationAgent, RefactoringAgent, PerformanceAgent, FormattingAgent,
#                SecurityAgent, TestCreationAgent, TestSpecialistAgent, ImportOptimizationAgent, DRYAgent

# Agent confidence scoring examples:
# DocumentationAgent:
# - 0.8 confidence for documentation issues (primary expertise)
# RefactoringAgent:
# - 0.9 confidence for complexity issues (primary expertise)
# - 0.8 confidence for dead code issues (secondary expertise)
# PerformanceAgent:
# - 0.85 confidence for performance issues (primary expertise)
# - Real code transformations with AST-based detection

# Works with all agents for comprehensive code quality fixes
```

### Temporary File Management

**Crackerjack automatically manages temporary files created during execution:**

```bash
# Default behavior (recommended)
python -m crackerjack  # Auto-cleanup: keeps 5 debug logs, 10 coverage files

# Customize cleanup behavior
python -m crackerjack --no-cleanup  # Disable automatic cleanup
python -m crackerjack --keep-debug-logs 10  # Keep more debug files
python -m crackerjack --keep-coverage-files 20  # Keep more coverage files
```

**Files managed:**

- `crackerjack-debug-*.log` - Debug logs from each run (default: keep 5 most recent)
- `.coverage.*` - Coverage data files from pytest-cov (default: keep 10 most recent)

**Configuration**: Cleanup behavior can be controlled via CLI options or disabled entirely for debugging purposes.

### Testing & Development

```bash
# Run specific test
python -m pytest tests/test_specific.py::TestClass::test_method -v

# Run with coverage
python -m pytest --cov=crackerjack --cov-report=html

# Run tests with specific worker count
python -m crackerjack -t --test-workers 4

# Benchmark mode
python -m crackerjack --benchmark

# Progress monitoring for WebSocket MCP jobs
python -m crackerjack.mcp.progress_monitor <job_id> ws://localhost:8675

# Run with experimental hooks (pyrefly, ty)
python -m crackerjack --experimental-hooks

# Debug AI agent workflows with detailed logging
python -m crackerjack --ai-debug -t

# Enable verbose output for troubleshooting
python -m crackerjack --verbose -t

```

### Version Management

```bash
# Bump version without publishing
python -m crackerjack --bump patch   # 0.30.3 -> 0.30.4
python -m crackerjack --bump minor   # 0.30.3 -> 0.31.0
python -m crackerjack --bump major   # 0.30.3 -> 1.0.0

# Bump version without git tags
python -m crackerjack --bump patch --no-git-tags

# Skip version consistency verification
python -m crackerjack --bump patch --skip-version-check

# Publish to PyPI (requires UV_PUBLISH_TOKEN or keyring)
python -m crackerjack -p patch
```

### UVX Integration

**Crackerjack can be executed via uvx for isolated environments:**

```bash
# For installed crackerjack (from PyPI)
uvx crackerjack --help
uvx crackerjack -t
uvx crackerjack --start-mcp-server

# For local development version
uvx --from /Users/les/Projects/crackerjack crackerjack --help
uvx --from /Users/les/Projects/crackerjack crackerjack -t
uvx --from /Users/les/Projects/crackerjack crackerjack --start-mcp-server
```

**Benefits**: Isolated execution, no dependency conflicts, consistent environment across systems.

## Architecture Overview

**Recently refactored from monolithic `crackerjack.py` to modular architecture:**

### Core Orchestration Layer

- **`core/workflow_orchestrator.py`**: Main entry point with `WorkflowOrchestrator` and `WorkflowPipeline` classes
- **`core/container.py`**: Basic dependency injection container using protocols for loose coupling
- **`core/enhanced_container.py`**: Advanced DI container with lifecycle management
  - **ServiceLifetime** enum: `SINGLETON`, `TRANSIENT`, `SCOPED` service lifetimes
  - **ServiceDescriptor** dataclass: Comprehensive service registration with factory support
  - **Thread-safe**: Singleton instances with thread-local scoping
  - **Dependency resolution**: Automatic dependency injection with circular dependency detection
- **`__main__.py`**: Simplified CLI entry point (reduced from 601 to 122 lines via modularization)

### Coordinator Layer (Workflow Management)

- **`core/session_coordinator.py`**: Session tracking, cleanup handlers, progress management
- **`core/phase_coordinator.py`**: Individual workflow phases (cleaning, config, hooks, testing, publishing, commit)
- **`core/async_workflow_orchestrator.py`**: Async workflow coordination with parallel execution
  - **Async/await patterns**: Non-blocking workflow execution
  - **Parallel hook execution**: Concurrent pre-commit hook processing
  - **Progress streaming**: Real-time progress updates via WebSocket
  - **Error aggregation**: Collects all errors before batch processing by AI agents

### Domain Managers (Business Logic)

- **`managers/hook_manager.py`**: Pre-commit hook execution with fast→comprehensive two-stage system
- **`managers/test_manager.py`**: Test execution, coverage analysis, environment validation
- **`managers/publish_manager.py`**: Version bumping, git tagging, PyPI publishing with authentication

### Component Interaction Patterns

**Dependency Flow:**

```
WorkflowOrchestrator → SessionCoordinator → PhaseCoordinator → Managers
                   ↓
Container (DI) → Protocols → Concrete Implementations
```

**Critical Interfaces in `models/protocols.py`:**

- `HookManagerProtocol`, `TestManagerProtocol`, `PublishManagerProtocol`
- Always import protocols, never concrete classes for dependency injection
- **Common Error**: `from ..managers.test_manager import TestManager` ❌
- **Correct**: `from ..models.protocols import TestManagerProtocol` ✅

**Enhanced Dependency Injection Patterns** (using `EnhancedContainer`):

```python
from crackerjack.core.enhanced_container import EnhancedContainer, ServiceLifetime

# Service registration with lifecycle management
container.register_service(
    interface=HookManagerProtocol,
    implementation=AsyncHookManager,
    lifetime=ServiceLifetime.SINGLETON,  # Shared instance
)

# Factory-based registration for complex initialization
container.register_factory(
    interface=TestManagerProtocol,
    factory=lambda: create_test_manager_with_config(),
    lifetime=ServiceLifetime.SCOPED,  # Per-session instance
)

# Automatic dependency resolution
hook_manager = container.resolve(HookManagerProtocol)  # Returns singleton
test_manager = container.resolve(TestManagerProtocol)  # Creates scoped instance
```

### Infrastructure Services

- **`services/filesystem.py`**: Basic file operations with caching, batching, and security validation
- **`services/enhanced_filesystem.py`**: Advanced filesystem operations
  - **Atomic Operations**: Ensures file consistency during concurrent operations
  - **XDG Compliance**: Follows XDG Base Directory Specification for config/cache/data
  - **Backup Management**: Automatic backup creation with rotation policies
  - **Performance Monitoring**: File operation timing and performance metrics
  - **Security Validation**: Path traversal prevention and secure temp file handling
- **`services/git.py`**: Git operations (commit, push, file tracking) with intelligent commit messages
- **`services/config.py`**: Configuration management for pyproject.toml and .pre-commit-config.yaml
- **`services/unified_config.py`**: Centralized configuration management across all components
- **`services/security.py`**: Token handling, command validation, secure temp file creation
- **`services/health_metrics.py`**: System health monitoring and performance benchmarking
- **`services/contextual_ai_assistant.py`**: AI-powered code analysis and suggestions

### MCP Integration (AI Agent Support)

**Refactored from monolithic 3,116-line server to modular architecture (70% line reduction):**

- **`mcp/server.py`**: Backward compatibility wrapper (32 lines, imports from modular implementation)
- **`mcp/server_core.py`**: Core MCP server configuration and setup (194 lines)
- **`mcp/tools/`**: Modular tool implementations:
  - `core_tools.py`: Basic execution and stage tools
  - `monitoring_tools.py`: Status monitoring and health checks
  - `progress_tools.py`: Progress tracking and job management
  - `execution_tools.py`: Auto-fixing and workflow execution
- **`mcp/context.py`**: Context manager for dependency injection and state management
- **`mcp/state.py`**: Thread-safe session state management with async locks
- **`mcp/cache.py`**: Thread-safe error pattern caching and fix result tracking
- **`mcp/rate_limiter.py`**: Rate limiting, resource management, and DoS protection
- **`mcp/file_monitor.py`**: Event-based file monitoring with watchdog
- **Entry point**: `python -m crackerjack --start-mcp-server`

**WebSocket Server (refactored from 1,479 lines to modular architecture - 35% reduction):**

- **`mcp/websocket_server.py`**: Backward compatibility wrapper (imports from modular implementation)
- **`mcp/websocket/server.py`**: Main WebSocket server class (101 lines)
- **`mcp/websocket/app.py`**: FastAPI application setup (26 lines)
- **`mcp/websocket/jobs.py`**: Job lifecycle and progress management (197 lines)
- **`mcp/websocket/endpoints.py`**: HTTP endpoint definitions (545 lines)
- **`mcp/websocket/websocket_handler.py`**: WebSocket connection handling (75 lines)
- **Entry point**: `python -m crackerjack --start-websocket-server`

### CLI Interface (Modular Command Handling)

- **`cli/options.py`**: CLI option definitions and models (213 lines)
- **`cli/handlers.py`**: Mode handlers for different execution types (124 lines)
- **`cli/utils.py`**: CLI utility functions (17 lines)

### Advanced Orchestration

- **`orchestration/advanced_orchestrator.py`**: Advanced workflow orchestration with parallel execution strategies
- **`orchestration/execution_strategies.py`**: Pluggable execution strategies for different workflow types
- **`orchestration/test_progress_streamer.py`**: Real-time test progress streaming with Rich UI

### Plugin System

- **`plugins/base.py`**: Base plugin interface and lifecycle management
- **`plugins/loader.py`**: Dynamic plugin loading with dependency resolution
- **`plugins/hooks.py`**: Pre-commit hook plugins with custom validation rules
- **`plugins/managers.py`**: Plugin-specific manager implementations

### Legacy Components (Stable, Integrated)

- **`code_cleaner.py`**: Modernized code cleaning with AST parsing and protocol-based architecture
- **`dynamic_config.py`**: Configuration generation and management
- **`interactive.py`**: Rich UI interactive mode with clean architecture
- **`api.py`**: Public API with TODO detection for code cleaning operations

## Quality Process

### Optimal AI Agent Workflow Order

**Proper execution order for maximum efficiency (used by `/crackerjack:run`):**

1. **Fast Hooks First** (~5 seconds): `trailing-whitespace`, `end-of-file-fixer`, `ruff-format`, `ruff-check`, `gitleaks`

   - **Package-focused**: `ruff-check` now runs only on `crackerjack/` package code, excludes `tests/`
   - **Repository-wide**: Other fast hooks (formatting) still run on entire repository
   - If any formatting hooks fail → **Retry fast hooks once** (formatting fixes often resolve downstream issues)
   - Only proceed when fast hooks pass or have been retried

1. **Full Test Suite** (~variable): Run ALL tests, collect ALL failures

   - **Don't stop on first failure** - gather complete list of test issues
   - Tests are more critical than lint issues, so run before comprehensive hooks

1. **Comprehensive Hooks** (~30 seconds): `pyright`, `bandit`, `vulture`, `refurb`, `creosote`, `complexipy`

   - **Package-focused by default**: Only run on `crackerjack/` package code, excludes `tests/`, `examples/`
   - **Don't stop on first failure** - gather complete list of quality issues
   - Use `--with-tests` flag (future) to include tests in comprehensive quality checks

1. **AI Analysis & Batch Fixing**: Process ALL collected failures together

   - More efficient than fixing one issue at a time
   - AI can consider dependencies between fixes

### Testing Configuration

- **Framework**: pytest with asyncio auto mode
- **Coverage**: Incremental ratchet system targeting 100% coverage
- **Timeout**: 300 seconds per test (configurable with --test-timeout)
- **Workers**: Auto-detected based on CPU count (override with --test-workers)
- **Config file**: `pyproject.toml` contains pytest configuration

## Code Standards

### Clean Code Principles (Applied)

Following our philosophy that **EVERY LINE OF CODE IS A LIABILITY**:

- **DRY**: Extract common patterns into reusable functions/classes
- **YAGNI**: Implement only current requirements, not future "what-ifs"
- **KISS**: Choose simple solutions over clever ones
- **Readability First**: Code should be self-explanatory
- **Descriptive Names**: `user_count` not `uc`, even in map/filter functions

### Python 3.13+ Requirements

- Modern type hints with `|` unions instead of `Union`
- Protocol-based interfaces in `models/protocols.py`
- Pathlib over os.path
- `import typing as t` convention
- Pydantic BaseModel for configuration with validation

### Quality Rules (Enforced by Tools)

- **Cognitive complexity ≤15** per function (Complexipy) - KISS principle in action
- **No hardcoded temp paths** (Security: Bandit B108) - use `tempfile` module
- **UV tool execution**: Always use `uv run` for external tools
- **No shell=True** in subprocess calls
- **Type annotations required**: All functions must have return type hints
- **Protocol compliance**: Use protocols for dependency injection interfaces
- **TODO detection**: Code cleaning (`-x`) requires resolving all TODO comments first

### Refactoring Patterns for Complexity Reduction

```python
# GOOD: Break complex methods into smaller helper methods
def complex_method(self, data: dict) -> bool:
    if not self._validate_input(data):
        return self._handle_invalid_input()

    processed = self._process_data(data)
    return self._save_results(processed)


def _validate_input(self, data: dict) -> bool:
    # Single responsibility validation logic
    pass


def _handle_invalid_input(self) -> bool:
    # Focused error handling
    pass
```

### Error Prevention Patterns

```python
# AVOID: Hardcoded temp paths (Security issue)
config_path = "/tmp/test-config.yaml"  # BAD

# USE: Proper temp file handling
import tempfile

with tempfile.NamedTemporaryFile(suffix=".yaml") as f:
    config_path = f.name

# AVOID: try/except pass (Refurb FURB107)
try:
    risky_operation()
except Exception:
    pass  # BAD

# USE: contextlib.suppress
from contextlib import suppress

with suppress(Exception):
    risky_operation()

# AVOID: Lists in membership tests (Refurb FURB109)
if status in ["error", "failed", "timeout"]:  # BAD
    handle_error()

# USE: Tuples for immutable membership tests
if status in ("error", "failed", "timeout"):  # GOOD
    handle_error()

# AVOID: Manual list building (FURB138)
issues = []
for item in data:
    if condition(item):
        issues.append(process(item))

# USE: List comprehensions
issues = [process(item) for item in data if condition(item)]

# AVOID: Dictionary get with if/else (FURB184)
emoji = AGENT_EMOJIS.get(agent_type)
if emoji:
    return emoji
return "🤖"

# USE: Dictionary get with default
return AGENT_EMOJIS.get(agent_type, "🤖")

# AVOID: Lambda for simple attribute access (FURB118)
sorted_items = sorted(items, key=lambda x: x["priority"])

# USE: operator.itemgetter
from operator import itemgetter

sorted_items = sorted(items, key=itemgetter("priority"))
```

## Development Workflow

### Making Changes

1. **Run quality checks**: `python -m crackerjack`
1. **Run with tests**: `python -m crackerjack -t` (for comprehensive validation)
1. **Address remaining issues**: Manual fixes for any issues that tools cannot resolve
1. **Get AI code review**: When gemini-cli MCP server is connected, have Gemini review your completed work with `mcp__gemini-cli__ask-gemini` for a second opinion on code quality
1. **Commit changes**: Use `python -m crackerjack -c` for auto-commit with intelligent messages

### Testing Individual Components

```bash
# Test specific manager
python -m pytest tests/test_managers.py -v

# Test core orchestration
python -m pytest tests/test_coordinator_integration.py -v

# Test MCP integration
python -m pytest tests/test_mcp_server.py -v

# Run failing test in isolation
python -m pytest tests/test_crackerjack.py::TestClass::test_method -v -s
```

### Common Development Issues

- **Import errors**: Check `models/protocols.py` for interface definitions
- **Type errors**: Use `t.cast()` for complex type scenarios, ensure proper type annotations
- **Complexity violations**: Break large methods into focused helper methods
- **Test failures**: Check mock paths for new architecture

## MCP Server Integration

**WebSocket-based MCP server with real-time progress streaming:**

### Server Features

- **🌐 Dual Protocol Support**: MCP protocol tools + WebSocket server on localhost:8675
- **🎨 Real-time Progress**: Live progress updates with Rich formatting
- **🔄 Auto-Fallback**: Graceful fallback from WebSocket to polling
- **📊 Job Tracking**: Comprehensive job progress and iteration monitoring
- **🛑 Signal Handling**: Graceful shutdown with Ctrl+C support

### MCP Server Usage

**For live progress monitoring with `/crackerjack:run`:**

```bash
# Step 1: Start the dedicated WebSocket server (in a separate terminal)
python -m crackerjack --start-websocket-server

# Step 2: Use /crackerjack:run in Claude - progress will be available at:
# - WebSocket: ws://localhost:8675/ws/progress/{job_id}
# - Test page: http://localhost:8675/test
# - Status: http://localhost:8675/
```

**Alternative - Start MCP server with WebSocket support:**

```bash
# Starts server on localhost:8675 with WebSocket + MCP protocol support
python -m crackerjack --start-mcp-server --websocket-port 8675
```

**Progress monitoring:**

```bash
# Monitor specific job by ID via WebSocket
python -m crackerjack.mcp.progress_monitor abc123-def456

# Monitor with custom WebSocket URL
python -m crackerjack.mcp.progress_monitor abc123-def456 ws://localhost:8675
```

**Enhanced API integration:**

```python
from crackerjack.mcp.progress_monitor import (
    run_crackerjack_with_enhanced_progress,
)

# Uses WebSocket monitoring with Rich display
await run_crackerjack_with_enhanced_progress(client, "/crackerjack:run")
```

### Server Architecture

- **WebSocket Server**: Runs on localhost:8675 for progress streaming
- **MCP Protocol**: FastMCP-based tools for AI agent integration
- **Progress Queue**: `asyncio.Queue` for real-time job updates
- **Rich Components**: Formatted progress panels and status displays
- **Job Management**: Background task execution with progress tracking

### Available MCP Tools

- `execute_crackerjack`: Start iterative auto-fixing workflow
- `get_job_progress`: Get current progress for running jobs
- `get_comprehensive_status`: Get complete system status (servers, jobs, health)
- `run_crackerjack_stage`: Execute specific workflow stages
- `analyze_errors`: Intelligent error pattern analysis
- `session_management`: Track iteration state and checkpoints
- `get_stage_status`: Get workflow stage completion status
- `get_server_stats`: Get MCP server resource usage and statistics

### Dependencies

- `fastmcp>=2.10.6`: MCP server framework
- `uvicorn>=0.32.1`: WebSocket server support
- `websockets>=15.0.1`: WebSocket client connections
- `fastapi>=0.116.1`: HTTP/WebSocket endpoint framework
- `rich>=14`: Terminal formatting and progress displays

### Slash Commands

**Location**: Available in `crackerjack.slash_commands` module for other packages to use

**`/crackerjack:run`**: Run full iterative auto-fixing with AI agent, tests, progress tracking, and verbose output

**`/crackerjack:status`**: Get comprehensive system status including MCP server health, WebSocket server status, active jobs, progress tracking, and resource usage

**`/crackerjack:init`**: Initialize or update project configuration with intelligent smart merge (preserves existing configurations, never overwrites project identity)

**Programmatic Access**:

```python
from crackerjack.slash_commands import list_available_commands, get_slash_command_path

# List all available commands
commands = list_available_commands()  # ['run', 'init']

# Get path to specific command
command_path = get_slash_command_path("run")
command_content = command_path.read_text()
```

## Configuration Details

**Tool Configuration** (from `pyproject.toml`):

- **Coverage requirement**: Ratchet system - never decrease, always improve toward 100%
- **Cognitive complexity**: ≤13 per function (complexipy)
- **Python version**: 3.13+ required
- **Test timeout**: 300 seconds per test
- **Type checking**: Strict mode with Pyright
- **Security scanning**: Bandit with custom exclusions

## Service Watchdog

**Automatic monitoring and restart system for MCP and WebSocket servers.**

### Overview

The Service Watchdog provides enterprise-grade monitoring and automatic recovery for Crackerjack's server components. It ensures continuous availability by detecting failures and restarting services automatically.

### Usage

```bash
# Start watchdog to monitor both MCP and WebSocket servers
python -m crackerjack --watchdog
```

### Monitored Services

1. **MCP Server** (`--start-mcp-server`)

   - Process monitoring (detects crashes)
   - No HTTP health checks (stdio-based protocol)
   - Auto-restart on process termination

1. **WebSocket Server** (`--start-websocket-server`)

   - Process monitoring (detects crashes)
   - HTTP health checks (`http://localhost:8675/`)
   - Auto-restart on process or health check failures

### Features

- **Real-time Monitoring**: Continuous process and health monitoring
- **Intelligent Restart**: Rate-limited restarts with exponential backoff
- **Rich Dashboard**: Live status display with service health, restart counts, and errors
- **Rate Limiting**: Maximum 10 restarts per 5-minute window to prevent restart loops
- **Health Checks**: HTTP endpoint monitoring for WebSocket server
- **Error Tracking**: Logs and displays last error for each service
- **Graceful Shutdown**: Proper cleanup on Ctrl+C

### Dashboard Display

The watchdog shows a real-time table with:

- **Service**: Service name (MCP Server, WebSocket Server)
- **Status**: ✅ Running / ❌ Stopped
- **Health**: 🟢 Healthy / 🔴 Unhealthy / N/A
- **Restarts**: Total restart count for the session
- **Last Error**: Most recent error message (truncated)

### Configuration

Default configuration monitors:

- **Health Check Interval**: 30 seconds
- **Restart Delay**: 5 seconds between restart attempts
- **Max Restarts**: 10 per 5-minute window
- **Health Timeout**: 10 seconds for HTTP checks

### Use Cases

- **Development**: Automatic recovery during active development sessions
- **CI/CD**: Ensure services stay running during automated testing
- **Production**: High-availability deployment with automatic failover
- **Debugging**: Monitor service stability and identify recurring issues

### Dependencies

- `aiohttp`: HTTP health check client
- `rich`: Dashboard display and formatting
- `asyncio`: Concurrent monitoring and restart management

## Architecture Migration Notes

**Key changes from monolithic to modular:**

- `Crackerjack` class methods → `WorkflowOrchestrator` + coordinator delegation
- Direct tool execution → Manager pattern with dependency injection
- Hardcoded workflows → Configurable phase execution with retry logic
- Manual error handling → Automatic fixing with intelligent retry

**Modular Architecture Notes:**

- **Clean Architecture**: Direct use of modern class names (`InteractiveCLI`, `WorkflowManager`, `CodeCleaner`)
- **Modular CLI**: Options and handlers moved to dedicated modules (`cli/options.py`, `cli/handlers.py`)
- **Protocol-based Design**: Dependency injection through protocols for better testability

**Refactoring Achievements (January 2025):**

- **70% line reduction** in MCP server (3,116 lines → 921 lines across 6 focused modules)
- **35% line reduction** in WebSocket server (1,479 lines → 944 lines across 5 modules)
- **80% line reduction** in CLI entry point (601 lines → 122 lines via delegation)
- **Code Quality Improvements**:
  - Fixed all 31+ refurb violations in agents directory (FURB107, FURB109, FURB118, FURB135, FURB138, FURB184)
  - Reduced complex functions from 32 to 29 total, with major reductions:
    - `_execute_crackerjack_sync`: complexity 34 → 3 (91% reduction)
    - `TestManagementImpl::run_tests`: complexity 33 → 2 (94% reduction)
    - All 5 fast hooks now passing consistently
- **Improved maintainability** through single responsibility principle
- **Better testability** with focused, isolated modules
- **Enhanced security** with modular validation and error handling
- **Protocol-based interfaces** for better dependency injection and testing
- **Performance Improvements**: Enhanced async/await patterns, parallel execution, and caching strategies
- **Plugin Architecture**: Extensible plugin system for custom hooks and workflow extensions
- **Health Monitoring**: Comprehensive system health metrics and performance benchmarking

## Test Coverage Requirements

**CRITICAL**: The coverage ratchet system prevents regression and targets 100% coverage.

- **Never reduce coverage below current baseline** - coverage can only improve
- **Add tests to increase coverage** incrementally toward 100%
- **Current Status**: Test coverage at 10.11% baseline, targeting 100%
- Existing test files cover various modules including core components, managers, and async workflows
- Focus testing on modules with 0% coverage: plugins, MCP server, enhanced filesystem, unified config

## Current Quality Status (January 2025)

**✅ COMPLETED:**

- All 31+ refurb violations fixed in agents directory
- Fast hooks: All 5 passing consistently
- Major complexity reductions (34→3, 33→2)
- Import errors and protocol compliance fixed

**🔄 IN PROGRESS:**

- Complexipy violations: Some functions still > 15 complexity
- Test coverage: Working toward 100% via incremental improvements

**⚠️ CRITICAL PRIORITIES:**

1. **Fix existing test failures first** (before adding new tests)
1. Add tests strategically to reach next milestone toward 100% coverage
1. Complete remaining complexity reductions
1. Final integration and release preparation

**Key User Directive**: Always prioritize fixing failures of existing tests over creating new tests, especially when coverage issues are being addressed.

### Current Test Strategy (Post-Architectural Refactoring)

**Strategic Testing Approach**:

- **Import-only tests**: Fast, reliable coverage for basic module loading and interface compliance
- **Protocol compliance tests**: Ensure all implementations properly follow interface contracts
- **Async pattern testing**: Comprehensive validation of async/await workflows without hanging tests
- **Integration testing**: End-to-end validation of dependency injection and workflow orchestration
- **Performance regression testing**: Automated detection of performance degradation in async workflows

## Important Instruction Reminders

- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (\*.md) or README files unless explicitly requested
- MAINTAIN coverage ratchet - never decrease coverage, always improve toward 100%

## Coding Standards Memories

- Do not reduce coverage below current baseline. Instead add tests to increase coverage toward 100% target.
- **Debugging Approach Memory**: Focus on test errors first then move on to failures when debugging tests

## Critical Quality Standards

- **Test Quality**: Never create async tests that hang indefinitely. When testing async components like `BatchedStateSaver`, prefer simple synchronous tests that verify configuration and basic state rather than complex async workflows that can cause test suite timeouts.
- **Honest Progress Reporting**: Always report actual coverage percentages and test results accurately. If coverage is 10.17%, report it as 10.17%, not "approaching 15%" or other optimistic estimates.
- **Import Error Prevention**: Common import error pattern: `TestManager` vs `TestManagerProtocol` in `async_workflow_orchestrator.py`. Always use protocol interfaces from `models/protocols.py`.

## Development Standards

- be honest when describing the things you have accomplished. if tasks have not been completed to their full extent we need to know so sugarcoating your accomplishments for your, and especially our, benefit helps nobody.

- be very critical and comprehensive when performing code or documentation reviews/audits. pride ourselves on our attention to detail and take the time to do things right the first time. always still assume failure on the first try, when making edits, so our work is double checked and bulletproof.

## Common Failure Patterns to Avoid

### Async Test Hangs

```python
# AVOID: Complex async tests that can hang
@pytest.mark.asyncio
async def test_batch_processing(self, batched_saver):
    await batched_saver.start()
    # Complex async workflow that might hang


# PREFER: Simple synchronous config tests
def test_batch_configuration(self, batched_saver):
    assert batched_saver.max_batch_size == expected_size
    assert not batched_saver._running
```

### Import Error Prevention

```python
# WRONG: Importing concrete classes instead of protocols
from ..managers.test_manager import TestManager

# CORRECT: Use protocol interfaces for dependency injection
from ..models.protocols import TestManagerProtocol
```

- DO NOT CREATE ANY NEW TESTS UNTIL CURRENTLY FAILING OR ERRORING TESTS HAVE EITHER BEEN FIXED OR REMOVED!
- always be honest with your answers. do not embelish on progress.
- always clean up after yourself
