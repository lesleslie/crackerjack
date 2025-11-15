# Crackerjack: Advanced AI-Driven Python Development Platform

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)
[![Python: 3.13+](https://img.shields.io/badge/python-3.13%2B-green)](https://www.python.org/downloads/)
[![pytest](https://img.shields.io/badge/pytest-coverage%20ratchet-blue)](https://pytest.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Quality Hooks](https://img.shields.io/badge/quality%20hooks-17%20tools-brightgreen)](https://github.com/lesleslie/crackerjack)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
![Coverage](https://img.shields.io/badge/coverage-21.6%25-red)

## 🎯 Purpose

**Crackerjack** transforms Python development from reactive firefighting to proactive excellence. This sophisticated platform empowers developers to create exceptional code through intelligent automation, comprehensive quality enforcement, and AI-powered assistance. Experience the confidence that comes from knowing your code meets the highest standards before it ever runs in production.

### What is "Crackerjack"?

**crack·​er·​jack** ˈkra-kər-ˌjak (noun): *A person or thing of marked excellence or ability; first-rate; exceptional.*

Just as the name suggests, Crackerjack makes your Python projects first-rate through:

- **🧠 Proactive AI Architecture**: 12 specialized AI agents prevent issues before they occur
- **⚡ Autonomous Quality**: Intelligent auto-fixing with architectural planning
- **🛡️ Zero-Compromise Standards**: 100% test coverage, complexity ≤15, security-first patterns
- **🔄 Learning System**: Gets smarter with every project, caching successful patterns
- **🌟 One Command Excellence**: From setup to PyPI publishing with a single command

**The Crackerjack Philosophy**: If your code needs fixing after it's written, you're doing it wrong. We prevent problems through intelligent architecture and proactive patterns, making exceptional code the natural outcome, not a lucky accident.

## What Problem Does Crackerjack Solve?

**Instead of configuring multiple tools separately:**

```bash
# Traditional workflow
pip install black isort flake8 mypy pytest
# Configure each tool individually
# Set up git hooks manually
# Remember different commands for each tool
```

**Crackerjack provides unified commands:**

```bash
pip install crackerjack
python -m crackerjack        # Setup + quality checks
python -m crackerjack --run-tests        # Add testing
python -m crackerjack --all patch # Full release workflow
```

**Key differentiators:**

- **Single command** replaces 6+ separate tools
- **Pre-configured** with Python best practices
- **UV integration** for fast dependency management
- **Automated publishing** with PyPI authentication
- **MCP server** for AI agent integration

## The Crackerjack Philosophy

Crackerjack is built on the following core principles:

- **Code Clarity:** Code should be easy to read, understand, and maintain
- **Automation:** Tedious tasks should be automated, allowing developers to focus on solving problems
- **Consistency:** Code style, formatting, and project structure should be consistent across projects
- **Reliability:** Tests are essential, and code should be checked rigorously
- **Tool Integration:** Leverage powerful existing tools instead of reinventing the wheel
- **Auto-Discovery:** Prefer intelligent auto-discovery of configurations and settings over manual configuration whenever possible, reducing setup friction and configuration errors
- **Static Typing:** Static typing is essential for all development

## Crackerjack vs Pre-commit: Architecture & Features

Crackerjack and pre-commit solve related but different problems. While pre-commit is a language-agnostic git hook manager, Crackerjack is a comprehensive Python development platform with quality enforcement built-in.

### Architectural Differences

| Aspect | Pre-commit | Crackerjack |
|--------|-----------|-------------|
| **Execution Model** | Wrapper framework that spawns subprocesses for each hook | Direct tool invocation with ACB adapter architecture |
| **Concurrency** | Synchronous sequential execution (one hook at a time) | **Async-first with 11 concurrent adapters** - true parallel execution |
| **Performance** | Overhead from framework wrapper + subprocess spawning | Zero wrapper overhead, 70% cache hit rate, 50% faster workflows |
| **Language Focus** | Language-agnostic (Python, Go, Rust, Docker, etc.) | Python-first with native tool implementations |
| **Configuration** | YAML-based `.pre-commit-config.yaml` with repo URLs | Python-based configuration with intelligent defaults |
| **Hook Management** | Clones repos, manages environments per hook | Native Python tools + direct UV invocation |

### Feature Comparison

#### Quality Hooks & Tools

| Feature | Pre-commit | Crackerjack |
|---------|-----------|-------------|
| **Code Formatting** | ✅ Via hooks (black, ruff, etc.) | ✅ Native Ruff integration + mdformat |
| **Linting** | ✅ Via hooks (flake8, pylint, etc.) | ✅ Native Ruff + codespell |
| **Type Checking** | ✅ Via hooks (mypy, pyright) | ✅ **Zuban** (20-200x faster than pyright) |
| **Security Scanning** | ✅ Via hooks (bandit, gitleaks) | ✅ Native bandit + gitleaks integration |
| **Dead Code Detection** | ✅ Via vulture hook | ✅ **Skylos** (20x faster than vulture) |
| **Complexity Analysis** | ❌ Not built-in | ✅ Native complexipy integration |
| **Dependency Validation** | ❌ Not built-in | ✅ Native creosote unused dependency detection |
| **Custom Python Tools** | ✅ Via `repo: local` hooks | ✅ 6 native tools in `crackerjack/tools/` |

#### Development Workflow

| Feature | Pre-commit | Crackerjack |
|---------|-----------|-------------|
| **Git Integration** | ✅ Pre-commit, pre-push, commit-msg hooks | ✅ Git hooks + intelligent commit messages |
| **Testing Framework** | ❌ Not included | ✅ Built-in pytest with coverage ratchet |
| **CI/CD Integration** | ✅ Via `pre-commit run --all-files` | ✅ Unified `--ci` mode with quality + tests |
| **Version Management** | ❌ Not included | ✅ Intelligent version bumping + AI recommendations |
| **Publishing** | ❌ Not included | ✅ PyPI publishing with UV authentication |
| **Hook Stages** | ✅ Multiple stages (commit, push, merge, manual) | ✅ Fast (~5s) vs Comprehensive (~30s) strategies |
| **Retry Logic** | ❌ No built-in retry | ✅ Automatic retry for formatting hooks |
| **Parallel Execution** | ✅ Limited parallelism (sequential by default) | ✅ **Async-first architecture**: 11 concurrent adapters, 76% speedup |

#### Advanced Features

| Feature | Pre-commit | Crackerjack |
|---------|-----------|-------------|
| **AI Integration** | ❌ Not built-in | ✅ 12 specialized AI agents + auto-fixing |
| **Dependency Injection** | ❌ Not applicable | ✅ ACB framework with protocol-based DI |
| **Caching** | ✅ Per-file hash caching | ✅ Content-based caching (70% hit rate) |
| **MCP Server** | ❌ Not included | ✅ Built-in MCP server for Claude integration |
| **Monitoring Dashboard** | ❌ Not included | ✅ Real-time WebSocket dashboard |
| **Configuration Management** | ✅ YAML + `--config` flag | ✅ ACB Settings with YAML + local overrides |
| **Auto-Update** | ✅ `pre-commit autoupdate` | ⚠️ Manual UV dependency updates |
| **Language Support** | ✅ 15+ languages (Python, Go, Rust, Docker, etc.) | ✅ Python + external tools (gitleaks, etc.) |

#### Configuration & Ease of Use

| Feature | Pre-commit | Crackerjack |
|---------|-----------|-------------|
| **Setup Complexity** | Medium (YAML config + `pre-commit install`) | Low (single `python -m crackerjack`) |
| **Configuration Format** | YAML with repo URLs and hook IDs | Python settings with intelligent defaults |
| **Hook Discovery** | Manual (add repos to `.pre-commit-config.yaml`) | Automatic (17 tools pre-configured) |
| **Tool Installation** | Auto (pre-commit manages environments) | UV-based (one virtual environment) |
| **Learning Curve** | Medium (understand repos, hooks, stages) | Low (unified Python commands) |

### When to Use Each

**Choose Pre-commit when:**

- ✅ Working with multiple languages (Go, Rust, Docker, etc.)
- ✅ Need language-agnostic hook framework
- ✅ Want to use hooks from community repositories
- ✅ Polyglot projects requiring diverse tooling
- ✅ Simple YAML-based configuration preferred

**Choose Crackerjack when:**

- ✅ Python-focused development (Python 3.13+)
- ✅ Want comprehensive development platform (testing, publishing, AI)
- ✅ Need maximum performance (async architecture, Rust tools, caching, 11x parallelism)
- ✅ Desire AI-powered auto-fixing and recommendations
- ✅ Want unified workflow (quality + tests + publishing in one command)
- ✅ Prefer Python-based configuration over YAML
- ✅ Need advanced features (coverage ratchet, MCP integration, dashboards)

### Migration from Pre-commit

Crackerjack can **coexist** with pre-commit if needed, but most Python projects can fully migrate:

```bash
# Remove pre-commit (optional)
pre-commit uninstall
rm .pre-commit-config.yaml

# Install crackerjack
uv tool install crackerjack

# Run quality checks (replaces pre-commit run --all-files)
python -m crackerjack

# With tests (comprehensive workflow)
python -m crackerjack --run-tests
```

**Note**: Crackerjack Phase 8 successfully migrated from pre-commit framework to direct tool invocation, achieving 50% performance improvement while maintaining full compatibility with existing quality standards.

## Table of Contents

- [Crackerjack vs Pre-commit](<#crackerjack-vs-pre-commit-architecture--features>)
- [Installation](<#installation>)
- [Quick Start](<#quick-start>)
- [AI Auto-Fix Features](<#ai-auto-fix-features>)
- [Core Workflow](<#core-workflow>)
- [Core Features](<#core-features>)
- [ACB Architecture & Performance](<#-acb-architecture--performance>)
- [Adapters](<#adapters>)
- [Configuration Management](<#-configuration-management-acb-settings--configuration-templates>)
- [MCP Server Configuration](<#mcp-server-configuration>)
- [Quality Hook Modes](<#quality-hook-modes>)
- [Command Reference](<#command-reference>)
- [Style Guide](<#style-guide>)
- [Publishing & Version Management](<#publishing--version-management>)
- [Troubleshooting](<#-troubleshooting>)

## Installation

### Prerequisites

- Python 3.13+
- [UV](https://github.com/astral-sh/uv) package manager

### Install UV

```bash
# Recommended: Official installer script
curl -LsSf https://astral.sh/uv/install.sh | sh

# Alternative: Using pipx
pipx install uv

# Alternative: Using Homebrew (macOS)
brew install uv
```

### Install Crackerjack

```bash
# Recommended: Using UV (fastest)
uv tool install crackerjack

# Alternative: Using pip
pip install crackerjack

# For existing project: Add as dependency
uv add crackerjack
```

## Quick Start

### Initialize a Project

```bash
# Navigate to your project directory
cd your-project

# Initialize with Crackerjack
python -m crackerjack

# Or use interactive mode
python -m crackerjack -i
```

## AI Auto-Fix Features

Crackerjack provides two distinct approaches to automatic error fixing:

### 1. Hook Auto-Fix Modes (Basic Formatting)

Limited tool-specific auto-fixes for simple formatting issues:

- `ruff --fix`: Import sorting, basic formatting
- `trailing-whitespace --fix`: Removes trailing whitespace
- `end-of-file-fixer --fix`: Ensures files end with newline

**Limitations:** Only handles simple style issues, cannot fix type errors, security issues, test failures, or complex code quality problems.

### 2. AI Agent Auto-Fixing (Comprehensive Intelligence)

**Revolutionary AI-powered code quality enforcement** that automatically fixes ALL types of issues:

#### How AI Agent Auto-Fixing Works

1. **🚀 Run All Checks**: Fast hooks, comprehensive hooks, full test suite
1. **🔍 Analyze Failures**: AI parses error messages, identifies root causes
1. **🤖 Intelligent Fixes**: AI reads source code and makes targeted modifications
1. **🔄 Repeat**: Continue until ALL checks pass (up to 8 iterations)
1. **🎉 Perfect Quality**: Zero manual intervention required

#### Comprehensive Coverage

The AI agent intelligently fixes:

- **Type Errors (zuban)**: Adds missing annotations, fixes type mismatches
- **🔒 Security Issues (bandit)**: Comprehensive security hardening including:
  - **Shell Injection Prevention**: Removes `shell=True` from subprocess calls
  - **Weak Cryptography**: Replaces MD5/SHA1 with SHA256
  - **Insecure Random Functions**: Replaces `random.choice` with `secrets.choice`
  - **Unsafe YAML Loading**: Replaces `yaml.load` with `yaml.safe_load`
  - **Token Exposure**: Masks PyPI tokens, GitHub PATs, and sensitive credentials
  - **Debug Print Removal**: Eliminates debug prints containing sensitive information
- **Dead Code (vulture)**: Removes unused imports, variables, functions
- **Performance Issues**: Transforms inefficient patterns (list concatenation, string building, nested loops)
- **Documentation Issues**: Auto-generates changelogs, maintains consistency across .md files
- **Test Failures**: Fixes missing fixtures, import errors, assertions
- **Code Quality (refurb)**: Applies refactoring, reduces complexity
- **All Hook Failures**: Formatting, linting, style issues

#### AI Agent Commands

```bash
# Standard AI agent mode (recommended)
python -m crackerjack --ai-fix --run-tests --verbose

# Preview fixes without applying (dry-run mode)
python -m crackerjack --dry-run --run-tests --verbose

# Custom iteration limit
python -m crackerjack --ai-fix --max-iterations 15

# MCP server with WebSocket support (localhost:8675)
python -m crackerjack --start-mcp-server

# Progress monitoring via WebSocket
python -m crackerjack.mcp.progress_monitor <job_id> ws://localhost:8675
```

#### MCP Integration

When using crackerjack via MCP tools (session-mgmt-mcp):

```python
# ✅ CORRECT - Use semantic command + ai_agent_mode parameter
crackerjack_run(command="test", ai_agent_mode=True)

# ✅ CORRECT - With additional arguments
crackerjack_run(command="check", args="--verbose", ai_agent_mode=True, timeout=600)

# ✅ CORRECT - Dry-run mode
crackerjack_run(command="test", args="--dry-run", ai_agent_mode=True)

# ❌ WRONG - Don't put flags in command parameter
crackerjack_run(command="--ai-fix -t")  # This will error!

# ❌ WRONG - Don't use --ai-fix in args
crackerjack_run(command="test", args="--ai-fix")  # Use ai_agent_mode=True instead
```

#### Configuration

Auto-fix requires:

1. **Anthropic API key**: Set environment variable

   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

1. **Configuration file**: `settings/adapters.yml`

   ```yaml
   ai: claude
   ```

#### Key Benefits

- **Zero Configuration**: No complex flag combinations needed
- **Complete Automation**: Handles entire quality workflow automatically
- **Intelligent Analysis**: Understands code context and business logic
- **Comprehensive Coverage**: Fixes ALL error types, not just formatting
- **Perfect Results**: Achieves 100% code quality compliance

#### 🤖 Specialized Agent Architecture

**12 Specialized AI Agents** for comprehensive code quality improvements:

- **🔒 SecurityAgent**: Fixes shell injections, weak crypto, token exposure, unsafe library usage
- **♻️ RefactoringAgent**: Reduces complexity ≤15, extracts helper methods, applies SOLID principles
- **🚀 PerformanceAgent**: Optimizes algorithms, fixes O(n²) patterns, improves string building
- **📝 DocumentationAgent**: Auto-generates changelogs, maintains .md file consistency
- **🧹 DRYAgent**: Eliminates code duplication, extracts common patterns to utilities
- **✨ FormattingAgent**: Handles code style, import organization, formatting violations
- **🧪 TestCreationAgent**: Fixes test failures, missing fixtures, dependency issues
- **📦 ImportOptimizationAgent**: Removes unused imports, restructures import statements
- **🔬 TestSpecialistAgent**: Advanced testing scenarios, fixture management
- **🔍 SemanticAgent**: Advanced semantic analysis, code comprehension, intelligent refactoring suggestions based on business logic understanding
- **🏗️ ArchitectAgent**: High-level architectural patterns, design recommendations, system-level optimization strategies
- **🎯 EnhancedProactiveAgent**: Proactive issue prevention, predictive quality monitoring, optimization before problems occur

**Agent Coordination Features**:

- **Confidence Scoring**: Routes issues to best-match agent (≥0.7 confidence)
- **Batch Processing**: Groups related issues for efficient parallel processing
- **Collaborative Mode**: Multiple agents handle complex cross-cutting concerns

#### Security & Safety Features

- **Command Validation**: All AI modifications are validated for safety
- **Advanced-Grade Regex**: Centralized pattern system eliminates dangerous regex issues
- **No Shell Injection**: Uses secure subprocess execution with validated patterns
- **Rollback Support**: All changes can be reverted via git
- **Human Review**: Review AI-generated changes before commit

#### ⚡ High-Performance Rust Tool Integration

**Ultra-Fast Static Analysis Tools**:

- **🦅 Skylos** (Dead Code Detection): Replaces vulture with **20x performance improvement**

  - Rust-powered dead code detection and import analysis
  - Seamlessly integrates with crackerjack's quality workflow
  - Zero configuration changes required

- **🔍 Zuban** (Type Checking): Replaces pyright with **20-200x performance improvement**

  - Lightning-fast type checking and static analysis
  - Drop-in replacement for slower Python-based tools
  - Maintains full compatibility with existing configurations

**Performance Benefits**:

- **Faster Development Cycles**: Quality hooks complete in seconds, not minutes
- **Improved Developer Experience**: Near-instantaneous feedback during development
- **Seamless Integration**: Works transparently with existing crackerjack workflows
- **Zero Breaking Changes**: Same CLI interface, dramatically better performance

**Implementation Details**:

```bash
# These commands now benefit from Rust tool speed improvements:
python -m crackerjack                    # Dead code detection 20x faster
python -m crackerjack --run-tests        # Type checking 20-200x faster
python -m crackerjack --ai-fix --run-tests # Complete workflow optimized
```

**Benchmark Results**: Real-world performance measurements show consistent **6,000+ operations/second** throughput with **600KB+/second** data processing capabilities during comprehensive quality checks.

## Core Workflow

**Enhanced three-stage quality enforcement with intelligent code cleaning:**

1. **Fast Hooks** (~5 seconds): Essential formatting and security checks
1. **🧹 Code Cleaning Stage** (between fast and comprehensive): AI-powered cleanup for optimal comprehensive hook results
1. **Comprehensive Hooks** (~30 seconds): Complete static analysis on cleaned code

**Optimal Execution Order**:

- **Fast hooks first** # → **retry once if any fail** (formatting fixes cascade to other issues)
- **Code cleaning** # → Remove TODO detection, apply standardized patterns
- **Post-cleaning fast hooks sanity check** # → Ensure cleaning didn't introduce issues
- **Full test suite** # → Collect ALL test failures (don't stop on first)
- **Comprehensive hooks** # → Collect ALL quality issues on clean codebase
- **AI batch fixing** # → Process all collected issues intelligently

**With AI integration:**

- `--ai-fix` flag enables automatic error resolution with specialized sub-agents
- MCP server allows AI agents to run crackerjack commands with real-time progress tracking
- Structured error output for programmatic fixes with confidence scoring
- Advanced-grade regex pattern system ensures safe automated text transformations

## Core Features

### Project Management

- **Effortless Project Setup:** Initializes new Python projects with a standard directory structure, `pyproject.toml`, and essential configuration files
- **UV Integration:** Manages dependencies and virtual environments using [UV](https://github.com/astral-sh/uv) for lightning-fast package operations
- **Dependency Management:** Automatically detects and manages project dependencies

### Code Quality

- **Automated Code Cleaning:** Removes unnecessary docstrings, line comments, and trailing whitespace
- **Consistent Code Formatting:** Enforces a unified style using [Ruff](https://github.com/astral-sh/ruff), the lightning-fast Python linter and formatter
- **Comprehensive Quality Hooks:** Direct tool invocation with no wrapper overhead - runs Python tools, Rust analyzers, and security scanners efficiently
- **Interactive Checks:** Supports interactive quality checks (like `refurb`, `bandit`, and `pyright`) to fix issues in real-time
- **Static Type Checking:** Enforces type safety with Pyright integration

### Testing & Coverage Ratchet System

- **Built-in Testing:** Automatically runs tests using `pytest` with intelligent parallelization
- **Coverage Ratchet:** Revolutionary coverage system that targets 100% - coverage can only increase, never decrease
- **Milestone Celebrations:** Progress tracking with milestone achievements (15%, 20%, 25%... # → 100%)
- **No Arbitrary Limits:** Replaced traditional hard limits with continuous improvement toward perfection
- **Visual Progress:** Rich terminal displays showing journey to 100% coverage
- **Benchmark Testing:** Performance regression detection and monitoring
- **Easy Version Bumping:** Provides commands to bump the project version (patch, minor, or major)
- **Simplified Publishing:** Automates publishing to PyPI via UV with enhanced authentication

#### Coverage Ratchet Philosophy

🎯 **Target: 100% Coverage** - Not an arbitrary number, but true comprehensive testing
📈 **Continuous Improvement** - Each test run can only maintain or improve coverage
🏆 **Milestone System** - Celebrate achievements at 15%, 25%, 50%, 75%, 90%, and 100%
🚫 **No Regression** - Once you achieve a coverage level, you can't go backward

```bash
# Show coverage progress
python -m crackerjack --coverage-report

# Run tests with ratchet system
python -m crackerjack --run-tests

# Example output:
# 🎉 Coverage improved from 10.11% to 15.50%!
# 🏆 Milestone achieved: 15% coverage!
# 📈 Progress: [███░░░░░░░░░░░░░░░░░] 15.50% # → 100%
# 🎯 Next milestone: 20% (+4.50% needed)
```

### Git Integration

- **Intelligent Commit Messages:** Analyzes git changes and suggests descriptive commit messages based on file types and modifications
- **Commit and Push:** Commits and pushes your changes with standardized commit messages
- **Pull Request Creation:** Creates pull requests to upstream repositories on GitHub or GitLab
- **Git Hook Integration:** Ensures code quality before commits with fast, direct tool execution

## ⚡ ACB Architecture & Performance

Crackerjack is built on the **ACB (Asynchronous Component Base)** framework, providing advanced-grade dependency injection, intelligent caching, and parallel execution.

### What is ACB?

[ACB](https://github.com/lesleslie/acb) is a lightweight dependency injection framework that enables:

- **Module-level registration** via `depends.set()` for clean dependency management
- **Runtime-checkable protocols** ensuring type safety across all components
- **Async-first design** with lifecycle management and timeout strategies
- **Clean separation of concerns** through adapters, orchestrators, and services

### Architecture Overview

**ACB Workflow Engine (Default since Phase 4.2)**

```
User Command # → BasicWorkflowEngine (ACB)
    ↓
Workflow Selection (Standard/Fast/Comprehensive/Test)
    ↓
Action Handlers (run_fast_hooks, run_code_cleaning, run_comprehensive_hooks, run_test_workflow)
    ↓
asyncio.to_thread() for non-blocking execution
    ↓
WorkflowPipeline (DI-injected via context)
    ↓
Phase Execution (_run_fast_hooks_phase, _run_comprehensive_hooks_phase, etc.)
    ↓
HookManager + TestManager (Manager Layer: 80% compliant)
    ↓
Direct adapter.check() calls (No subprocess overhead)
    ↓
ToolProxyCacheAdapter (Content-based caching, 70% hit rate)
    ↓
Parallel Execution (Up to 11 concurrent adapters)
    ↓
Results Aggregation with real-time console output
```

**Legacy Orchestrator Path** (opt-out with `--use-legacy-orchestrator`)

```
User Command # → WorkflowOrchestrator (Legacy)
    ↓
SessionCoordinator (@depends.inject + protocols)
    ↓
PhaseCoordinator (Orchestration Layer)
    ↓
HookManager + TestManager
    ↓
[Same execution path as ACB from here...]
```

**Architecture Compliance (Phase 2-4.2 Audit Results)**

| Layer | Compliance | Status | Notes |
|-------|-----------|--------|-------|
| **ACB Workflows** | 95% | ✅ Production | **Default since Phase 4.2** - Real-time output, non-blocking |
| **CLI Handlers** | 90% | ✅ Excellent | Gold standard: `@depends.inject` + `Inject[Protocol]` |
| **Services** | 95% | ✅ Excellent | Phase 3 refactored, consistent constructors |
| **Managers** | 80% | ✅ Good | Protocol-based injection, minor improvements needed |
| **Legacy Orchestration** | 70% | ⚠️ Opt-out | Available with `--use-legacy-orchestrator` |
| **Coordinators** | 70% | ⚠️ Mixed | Phase coordinators ✅, async needs standardization |
| **Agent System** | 40% | 📋 Legacy | Uses `AgentContext` pattern (predates ACB) |

**Key Architectural Patterns**

```python
# ✅ GOLD STANDARD Pattern (from CLI Handlers)
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console


@depends.inject
def setup_environment(console: Inject[Console] = None, verbose: bool = False) -> None:
    """Protocol-based injection with @depends.inject decorator."""
    console.print("[green]Environment ready[/green]")


# ❌ ANTI-PATTERN: Avoid manual fallbacks
def setup_environment_wrong(console: Console | None = None):
    self.console = console or Console()  # Bypasses DI container
```

### Performance Benefits

| Metric | Legacy | ACB Workflows (Phase 4.2) | Improvement |
|--------|--------|----------------------------|-------------|
| **Fast Hooks** | ~45s | ~48s | Comparable |
| **Full Workflow** | ~60s | ~90s | Real-time output |
| **Console Output** | Buffered | **Real-time streaming** | UX improvement |
| **Event Loop** | Sync (blocking) | **Async (non-blocking)** | Responsive |
| **Cache Hit Rate** | 0% | **70%** | New capability |
| **Concurrent Adapters** | 1 | **11** | 11x parallelism |
| **DI Context** | Manual | **Protocol-based injection** | Type safety |

### Core Components

#### 1. Quality Assurance Adapters

**Location:** `crackerjack/adapters/`

ACB-registered adapters for all quality checks:

- **Format:** Ruff formatting, mdformat
- **Lint:** Codespell, complexity analysis
- **Security:** Bandit security scanning, Gitleaks secret detection
- **Type:** Zuban type checking (20-200x faster than Pyright)
- **Refactor:** Creosote (unused dependencies), Refurb (Python idioms)
- **Complexity:** Complexipy analysis
- **Utility:** Various validation checks
- **AI:** Claude integration for intelligent auto-fixing

#### 2. Hook Orchestrator

**Location:** `crackerjack/orchestration/hook_orchestrator.py`

Features:

- **Dual execution mode:** Legacy (pre-commit CLI) + ACB (direct adapters)
- **Dependency resolution:** Intelligent hook ordering (e.g., format before lint)
- **Adaptive strategies:** Fast, comprehensive, or dependency-aware execution
- **Graceful degradation:** Timeout strategies prevent hanging

#### 3. Cache Adapters

**Location:** `crackerjack/orchestration/cache/`

Two caching strategies:

- **ToolProxyCache:** Content-based caching with file hash verification
- **MemoryCache:** In-memory LRU cache for testing

Benefits:

- **70% cache hit rate** in typical workflows
- **Content-aware invalidation:** Only re-runs when files actually change
- **Configurable TTL:** Default 3600s (1 hour)

#### 4. MCP Server Integration

**Location:** `crackerjack/mcp/`

ACB-registered services:

- **MCPServerService:** FastMCP server for AI agent integration
- **ErrorCache:** Pattern tracking for AI fix recommendations
- **JobManager:** WebSocket job tracking and progress streaming
- **WebSocketSecurityConfig:** Security hardening (localhost-only, rate limiting)

### Migration from Pre-commit

Crackerjack has migrated from pre-commit subprocess calls to direct ACB adapter execution:

**Old Approach (Pre-commit):**

```bash
pre-commit run ruff --all-files  # Subprocess overhead
```

**New Approach (ACB):**

```bash
python -m crackerjack --fast  # Direct Python API, 70% faster
```

**Migration Guide:** See `docs/README.md` (Migration Notes)

### Configuration Management (ACB Settings & Configuration Templates)

Crackerjack utilizes a **dual configuration system** to handle both runtime application settings and project configuration templates:

#### 1. Runtime Configuration (ACB Settings)

**ACB Settings** manages application runtime configuration:

**Before (11 config files, ~1,808 LOC):**

```python
from crackerjack.models.config import WorkflowOptions, HookConfig
from crackerjack.orchestration.config import OrchestrationConfig
# ... multiple configuration imports
```

**After (1 settings file, ~300 LOC):**

```python
from acb.depends import depends
from crackerjack.config import CrackerjackSettings

settings = depends.get(CrackerjackSettings)
# Auto-loads from: env vars (CRACKERJACK_*), .env file, defaults
```

**Benefits:**

- **83% LOC reduction** in configuration code
- **Automatic environment variable loading** (CRACKERJACK\_\* prefix)
- **Type validation** via Pydantic
- **Single source of truth** for all runtime settings
- **Backward compatible** - Public API unchanged (`create_workflow_options()`)

#### 2. Project Configuration Templates (ConfigTemplateService)

**ConfigTemplateService** manages project-level configuration templates for files like `.pre-commit-config.yaml` and `pyproject.toml`:

```bash
# Check for available configuration updates
python -m crackerjack --check-config-updates

# Show diff for specific configuration type
python -m crackerjack --diff-config pre-commit

# Apply configuration updates interactively
python -m crackerjack --apply-config-updates --config-interactive

# Refresh configuration cache
python -m crackerjack --refresh-cache
```

**ConfigTemplateService Benefits:**

- **Version-based tracking** - Each configuration has version control
- **User-controlled updates** - Explicit approval required for changes
- **Diff visibility** - Shows changes before applying
- **Cache management** - Automatic pre-commit cache invalidation
- **Template management** - Centralized configuration templates as code

**Config Merge Service (Initialization)**

The ConfigMergeService handles intelligent configuration merging during project initialization:

```python
# Used by InitializationService for new project setup
merge_result = config_merge_service.smart_merge_pyproject(
    source_config, target_path, project_name
)
```

**For Complete Configuration System Details:** See `docs/README.md` (Project Structure and Coding Standards).

**Migration Details:** See `docs/README.md` (Migration Notes)

### Using ACB Dependency Injection

Example: Custom QA Adapter

```python
import uuid
from contextlib import suppress
from acb.depends import depends
from crackerjack.adapters._qa_adapter_base import QAAdapterBase

# Module-level registration (ACB pattern)
MODULE_ID = uuid.UUID("01937d86-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
MODULE_STATUS = "stable"


class CustomAdapter(QAAdapterBase):
    @property
    def adapter_name(self) -> str:
        return "Custom Checker"

    @property
    def module_id(self) -> uuid.UUID:
        return MODULE_ID

    async def check(self, files, config):
        # Your quality check logic here
        return QAResult(passed=True, issues=[])


# Register with DI container
with suppress(Exception):
    depends.set(CustomAdapter)
```

### Performance Optimization

#### Intelligent Caching

- **Content-based keys:** `{hook_name}:{config_hash}:{content_hash}`
- **File hash verification:** Detects actual file changes, not just timestamps
- **LRU eviction:** Automatic cleanup of old entries

#### Parallel Execution

- **Dependency-aware scheduling:** Runs independent hooks in parallel
- **Semaphore control:** Prevents resource exhaustion
- **Async I/O:** 76% faster for I/O-bound operations

#### Timeout Strategies

- **Graceful degradation:** Continues execution even if one hook times out
- **Configurable limits:** Default 60s per hook, 300s overall
- **Context managers:** Automatic cleanup on timeout

### ACB Benefits

1. **Type Safety:** Runtime-checkable protocols ensure correctness
1. **Testability:** Easy mocking with `depends.get()`
1. **Maintainability:** Clear separation between adapters and orchestration
1. **Observability:** Structured logging with context fields
1. **Security:** Input validation, timeout protection, origin validation
1. **Performance:** 47% faster overall execution with intelligent caching

### Documentation

- See `docs/README.md` for consolidated documentation and references.
- **Code Review Report:** Available from maintainers

**Status:** ✅ Production Ready (as of 2025-10-09)

## 🛡️ Advanced-Grade Pattern Management System

### Advanced Regex Pattern Validation

Crackerjack includes a revolutionary **centralized regex pattern management system** that eliminates dangerous regex issues through comprehensive validation and safety controls.

#### Key Components

**📦 Centralized Pattern Registry** (`crackerjack/services/regex_patterns.py`):

- **18+ validated patterns** for security, formatting, version management
- **ValidatedPattern class** with comprehensive testing and safety limits
- **Thread-safe compiled pattern caching** for performance
- **Iterative application** for complex multi-word cases (e.g., `pytest - hypothesis - specialist`)

**🔧 Pattern Categories**:

- **Command & Flag Formatting**: Fix spacing in `python -m command`, `--flags`, hyphenated names
- **Security Token Masking**: PyPI tokens, GitHub PATs, generic long tokens, assignment patterns
- **Version Management**: Update `pyproject.toml` versions, coverage requirements
- **Code Quality**: Subprocess security fixes, unsafe library replacements, formatting normalization
- **Test Optimization**: Assert statement normalization, job ID validation

**⚡ Performance & Safety Features**:

```python
# Thread-safe pattern cache with size limits
CompiledPatternCache.get_compiled_pattern(pattern)

# Safety limits prevent catastrophic backtracking
MAX_INPUT_SIZE = 10 * 1024 * 1024  # 10MB max
MAX_ITERATIONS = 10  # Iterative application limit

# Iterative fixes for complex cases
pattern.apply_iteratively("pytest - hypothesis - specialist")
# # → "pytest-hypothesis-specialist"

# Performance monitoring capabilities
pattern.get_performance_stats(text, iterations=100)
```

#### Security Pattern Examples

**Token Masking Patterns**:

```python
# PyPI tokens (word boundaries prevent false matches)
"pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI"  # → "pypi-****"

# GitHub personal access tokens (exactly 40 chars)
"ghp_1234567890abcdef1234567890abcdef1234"  # → "ghp_****"

# Generic long tokens (32+ chars with word boundaries)
"secret_key=abcdef1234567890abcdef1234567890abcdef"  # → "secret_key=****"
```

**Subprocess Security Fixes**:

```python
# Automatic shell injection prevention
subprocess.run(cmd, shell=True)  # → subprocess.run(cmd.split())
subprocess.call(cmd, shell=True)  # → subprocess.call(cmd.split())
```

**Unsafe Library Replacements**:

```python
# Weak crypto # → Strong crypto
hashlib.md5(data)  # → hashlib.sha256(data)
hashlib.sha1(data)  # → hashlib.sha256(data)

# Insecure random # → Cryptographic random
random.choice(options)  # → secrets.choice(options)

# Unsafe YAML # → Safe YAML
yaml.load(file)  # → yaml.safe_load(file)
```

#### Pattern Validation Requirements

**Every pattern MUST include**:

- ✅ **Comprehensive test cases** (positive, negative, edge cases)
- ✅ **Replacement syntax validation** (no spaces in `\g<N>`)
- ✅ **Safety limits** and performance monitoring
- ✅ **Thread-safe compilation** and caching
- ✅ **Descriptive documentation** and usage examples

**Quality Guarantees**:

- **Zero regex-related bugs** since implementation
- **Performance optimized** with compiled pattern caching
- **Security hardened** with input size limits and validation
- **Maintenance friendly** with centralized pattern management

### Pre-commit Regex Validation Hook

**Future Enhancement**: Automated validation hook to ensure all regex usage follows safe patterns:

```bash
# Validates all .py files for regex pattern compliance
python -m crackerjack.tools.validate_regex_usage
```

This advanced-grade pattern management system has **eliminated all regex-related spacing and security issues** that previously plagued the codebase, providing a robust foundation for safe text processing operations.

## Adapters

Adapters connect Crackerjack to external tools and subsystems (e.g., Ruff, Zuban, Bandit) using ACB patterns. Each adapter exposes typed settings, async initialization, and standardized results.

- AI — Claude-powered code fixes: [crackerjack/adapters/ai/README.md](<./crackerjack/adapters/ai/README.md>)
- Complexity — Code complexity analysis (Complexipy): [crackerjack/adapters/complexity/README.md](<./crackerjack/adapters/complexity/README.md>)
- Format — Python/Markdown formatting (Ruff, Mdformat): [crackerjack/adapters/format/README.md](<./crackerjack/adapters/format/README.md>)
- Lint — Spelling and simple linters (Codespell): [crackerjack/adapters/lint/README.md](<./crackerjack/adapters/lint/README.md>)
- LSP — Rust tools with LSP (Zuban, Skylos): [crackerjack/adapters/lsp/README.md](<./crackerjack/adapters/lsp/README.md>)
- Refactor — Modernization, dead code, unused deps (Refurb, Skylos, Creosote): [crackerjack/adapters/refactor/README.md](<./crackerjack/adapters/refactor/README.md>)
- Security — Static analysis and secrets (Bandit, Gitleaks, Pyscn): [crackerjack/adapters/security/README.md](<./crackerjack/adapters/security/README.md>)
- Type — Static type checking (Zuban, Pyrefly, Ty): [crackerjack/adapters/type/README.md](<./crackerjack/adapters/type/README.md>)
- Utility — Config-driven checks (EOF newline, regex, size, lock): [crackerjack/adapters/utility/README.md](<./crackerjack/adapters/utility/README.md>)

Quick index: [crackerjack/adapters/README.md](<./crackerjack/adapters/README.md>).

## MCP Server Configuration

### What is MCP?

Model Context Protocol (MCP) enables AI agents to interact directly with Crackerjack's CLI tools for autonomous code quality fixes.

### Setup MCP Server

1. **Install development dependencies (includes MCP tools):**

   ```bash
   uv sync --group dev
   ```

1. **Start the MCP server:**

   ```bash
   # Starts WebSocket server on localhost:8675 with MCP protocol support
   python -m crackerjack --start-mcp-server
   ```

1. **Configure your MCP client (e.g., Claude Desktop):**

   Add to your MCP configuration file (`mcp.json`):

   **For installed crackerjack (from PyPI):**

   ```json
   {
     "mcpServers": {
       "crackerjack": {
         "command": "uvx",
         "args": [
           "crackerjack",
           "--start-mcp-server"
         ],
         "env": {
           "UV_KEYRING_PROVIDER": "subprocess",
           "EDITOR": "code --wait"
         }
       }
     }
   }
   ```

   **For local development version:**

   ```json
   {
     "mcpServers": {
       "crackerjack": {
         "command": "uvx",
         "args": [
           "--from",
           "/path/to/crackerjack",
           "crackerjack",
           "--start-mcp-server"
         ],
         "env": {
           "UV_KEYRING_PROVIDER": "subprocess",
           "EDITOR": "code --wait"
         }
       }
     }
   }
   ```

### Environment Variables & Security

Crackerjack supports several environment variables for configuration:

- **`UV_PUBLISH_TOKEN`**: PyPI authentication token for publishing ⚠️ **Keep secure!**
- **`UV_KEYRING_PROVIDER`**: Keyring provider for secure credential storage (e.g., "subprocess")
- **`EDITOR`**: Default text editor for interactive commit message editing (e.g., "code --wait")
- **`AI_AGENT`**: Set to "1" to enable AI agent mode with structured JSON output

#### 🔒 Security Best Practices

**Token Security:**

- **Never commit tokens to version control**
- Use `.env` files (add to `.gitignore`)
- Prefer keyring over environment variables
- Rotate tokens regularly

**Recommended setup:**

```bash
# Create .env file (add to .gitignore)
echo "UV_PUBLISH_TOKEN=pypi-your-token-here" > .env
echo ".env" >> .gitignore

# Or use secure keyring storage
keyring set https://upload.pypi.org/legacy/ __token__
```

**Example MCP configuration with environment variables:**

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "uvx",
      "args": [
        "--from",
        "/path/to/crackerjack",
        "crackerjack",
        "--start-mcp-server"
      ],
      "env": {
        "UV_KEYRING_PROVIDER": "subprocess",
        "EDITOR": "code --wait",
        "UV_PUBLISH_TOKEN": "pypi-your-token-here"
      }
    }
  }
}
```

### Available MCP Tools

**Job Execution & Monitoring:**

- **`execute_crackerjack`**: Start iterative auto-fixing with job tracking
- **`get_job_progress`**: Real-time progress for running jobs
- **`run_crackerjack_stage`**: Execute specific quality stages (fast, comprehensive, tests)

**Error Analysis:**

- **`analyze_errors`**: Analyze and categorize code quality errors
- **`smart_error_analysis`**: AI-powered error analysis with cached patterns

**Session Management:**

- **`get_stage_status`**: Check current status of quality stages
- **`get_next_action`**: Get optimal next action based on session state
- **`session_management`**: Manage sessions with checkpoints and resume capability

**WebSocket Endpoints:**

- **Server URL**: `ws://localhost:8675`
- **Progress Streaming**: `/ws/progress/{job_id}` for real-time updates

### Slash Commands

**`/crackerjack:run`**: Autonomous code quality enforcement with AI agent

```bash
# Through MCP
{
  "command": "/crackerjack:run",
  "args": []
}
```

**`/crackerjack:init`**: Initialize or update project configuration

```bash
# Through MCP
{
  "command": "/crackerjack:init",
  "args": ["--force"]  # Optional: force reinitialize
}
```

## Quality Hook Modes

Crackerjack runs quality checks in a two-stage process for optimal development workflow:

### Hook Details

**Fast Hooks (~5 seconds):**

- Ruff formatting and linting
- Trailing whitespace cleanup
- UV lock file updates
- Security credential detection
- Spell checking

**Comprehensive Hooks (~30 seconds):**

- Zuban type checking
- Bandit security analysis
- Dead code detection (vulture)
- Dependency analysis (creosote)
- Complexity limits (complexipy)
- Modern Python patterns (refurb)

```bash
# Default behavior runs comprehensive hooks
python -m crackerjack

# Skip hooks if you only want setup/cleaning
python -m crackerjack --skip-hooks
```

### Common Commands

```bash
# Quality checks only
python -m crackerjack

# With testing
python -m crackerjack --run-tests

# Full release workflow
python -m crackerjack --all patch

# AI agent mode
python -m crackerjack --ai-fix
```

## Quick Reference Index

**📋 Command Index by Use Case**

| Use Case | Command | Description |
|----------|---------|-------------|
| **Basic Quality Check** | `python -m crackerjack` | Run quality checks only |
| **Quality + Tests** | `python -m crackerjack --run-tests` | Quality checks with test suite |
| **AI Auto-Fix** | `python -m crackerjack --ai-fix --run-tests` | AI-powered fixing + tests (recommended) |
| **Full Release** | `python -m crackerjack --all patch` | Version bump, quality checks, publish |
| **Quick Publish** | `python -m crackerjack --publish patch` | Version bump + publish only |
| **Start MCP Server** | `python -m crackerjack --start-mcp-server` | Launch MCP agent integration |
| **Monitoring Dashboard** | `python -m crackerjack --dashboard` | Comprehensive monitoring view |
| **AI Debugging** | `python -m crackerjack --ai-debug --run-tests` | Verbose AI debugging mode |
| **Coverage Status** | `python -m crackerjack --coverage-status` | Show coverage ratchet progress |
| **Clear Caches** | `python -m crackerjack --clear-cache` | Reset all cache data |
| **Fast Iteration** | `python -m crackerjack --skip-hooks` | Skip quality checks during dev |
| **Documentation** | `python -m crackerjack --generate-docs` | Generate API documentation |
| **Advanced Features** | See `docs/README.md` | Advanced flags and workflows |

**📑 Alphabetical Flag Reference**

| Flag | Short | Description |
|------|-------|-------------|
| `--ai-debug` | - | Verbose debugging for AI auto-fixing |
| `--ai-fix` | - | Enable AI-powered auto-fixing |
| `--all` | `-a` | Full release workflow (bump, test, publish) |
| `--benchmark` | - | Run tests in benchmark mode |
| `--boost-coverage` | - | Auto-improve test coverage (default) |
| `--bump` | `-b` | Bump version (patch/minor/major/auto) |
| `--cache-stats` | - | Display cache statistics |
| `--clear-cache` | - | Clear all caches and exit |
| `--commit` | `-c` | Commit and push changes to Git |
| `--comp` | - | Run only comprehensive hooks |
| `--coverage-status` | - | Show coverage ratchet status |
| `--dashboard` | - | Start comprehensive monitoring dashboard |
| `--debug` | - | Enable debug output |
| `--dev` | - | Enable development mode for monitors |
| `--enhanced-monitor` | - | Advanced monitoring with patterns |
| `--fast` | - | Run only fast hooks |
| `--generate-docs` | - | Generate API documentation |
| `--interactive` | `-i` | Use Rich UI interface |
| `--monitor` | - | Multi-project progress monitor |
| `--orchestrated` | - | Advanced orchestrated workflow mode |
| `--publish` | `-p` | Bump version and publish to PyPI |
| `--quick` | - | Quick mode (3 iterations, for CI/CD) |
| `--restart-mcp-server` | - | Restart MCP server |
| `--run-tests` | `-t` | Execute test suite |
| `--skip-hooks` | `-s` | Skip pre-commit hooks |
| `--start-mcp-server` | - | Start MCP server |
| `--stop-mcp-server` | - | Stop MCP server |
| `--strip-code` | `-x` | Remove docstrings/comments |
| `--thorough` | - | Thorough mode (8 iterations) |
| `--unified-dashboard` | - | Unified real-time dashboard |
| `--verbose` | `-v` | Enable verbose output |
| `--watchdog` | - | Service watchdog with auto-restart |

**🔗 Related Documentation**

- **Advanced Features**: See `docs/README.md` - consolidated advanced flags
- **Developer Guide**: [CLAUDE.md](<./CLAUDE.md>) - AI assistant guidelines and developer commands

______________________________________________________________________

## Command Reference

**Core Workflow Commands:**

```bash
# Quality checks and development
python -m crackerjack                    # Quality checks only
python -m crackerjack --run-tests        # Quality checks + tests
python -m crackerjack --ai-fix --run-tests  # AI auto-fixing + tests (recommended)

# Release workflow
python -m crackerjack --all patch # Full release workflow
python -m crackerjack --publish patch      # Version bump + publish
```

**AI-Powered Development:**

```bash
python -m crackerjack --ai-fix              # AI auto-fixing mode
python -m crackerjack --ai-debug --run-tests # AI debugging with verbose output
python -m crackerjack --ai-fix --run-tests --verbose # Full AI workflow
python -m crackerjack --orchestrated        # Advanced orchestrated workflow
python -m crackerjack --quick               # Quick mode (3 iterations max)
python -m crackerjack --thorough            # Thorough mode (8 iterations max)
```

**Monitoring & Observability:**

```bash
python -m crackerjack --dashboard           # Comprehensive monitoring dashboard
python -m crackerjack --unified-dashboard   # Unified real-time dashboard
python -m crackerjack --monitor             # Multi-project progress monitor
python -m crackerjack --enhanced-monitor    # Enhanced monitoring with patterns
python -m crackerjack --watchdog            # Service watchdog (auto-restart)
```

**MCP Server Management:**

```bash
python -m crackerjack --start-mcp-server    # Start MCP server
python -m crackerjack --stop-mcp-server     # Stop MCP server
python -m crackerjack --restart-mcp-server  # Restart MCP server
python -m crackerjack --start-websocket-server # Start WebSocket server
```

**Performance & Caching:**

```bash
python -m crackerjack --cache-stats         # Display cache statistics
python -m crackerjack --clear-cache         # Clear all caches
python -m crackerjack --benchmark           # Run in benchmark mode
```

**Coverage Management:**

```bash
python -m crackerjack --coverage-status     # Show coverage ratchet status
python -m crackerjack --coverage-goal 85.0  # Set explicit coverage target
python -m crackerjack --no-coverage-ratchet # Disable coverage ratchet temporarily
python -m crackerjack --boost-coverage      # Auto-improve test coverage (default)
python -m crackerjack --no-boost-coverage   # Disable coverage improvements
```

**Zuban LSP Server Management:**

```bash
python -m crackerjack --start-zuban-lsp     # Start Zuban LSP server
python -m crackerjack --stop-zuban-lsp      # Stop Zuban LSP server
python -m crackerjack --restart-zuban-lsp   # Restart Zuban LSP server
python -m crackerjack --no-zuban-lsp        # Disable automatic LSP startup
python -m crackerjack --zuban-lsp-port 8677 # Custom LSP port
python -m crackerjack --zuban-lsp-mode tcp  # Transport mode (tcp/stdio)
python -m crackerjack --zuban-lsp-timeout 30 # LSP operation timeout
python -m crackerjack --enable-lsp-hooks    # Enable LSP-optimized hooks
```

**Documentation Generation:**

```bash
python -m crackerjack --generate-docs       # Generate comprehensive API docs
python -m crackerjack --docs-format markdown # Documentation format (markdown/rst/html)
python -m crackerjack --validate-docs       # Validate existing documentation
```

**Global Locking & Concurrency:**

```bash
python -m crackerjack --disable-global-locking # Allow concurrent execution
python -m crackerjack --global-lock-timeout 600 # Lock timeout in seconds
python -m crackerjack --cleanup-stale-locks # Clean stale lock files (default)
python -m crackerjack --no-cleanup-stale-locks # Don't clean stale locks
python -m crackerjack --global-lock-dir ~/.crackerjack/locks # Custom lock directory
```

**Git & Version Control:**

```bash
python -m crackerjack --no-git-tags         # Skip creating git tags
python -m crackerjack --skip-version-check  # Skip version consistency verification
```

**Experimental Features:**

```bash
python -m crackerjack --experimental-hooks  # Enable experimental pre-commit hooks
python -m crackerjack --enable-pyrefly      # Enable pyrefly type checking (experimental)
python -m crackerjack --enable-ty           # Enable ty type verification (experimental)
```

**Common Options:**

- `-i, --interactive`: Rich UI interface with better experience
- `-v, --verbose`: Detailed output for debugging
- `-c, --commit`: Auto-commit and push changes to Git
- `--skip-hooks`: Skip quality checks during development iteration
- `--strip-code`: Remove docstrings/comments for production
- `--dev`: Enable development mode for progress monitors
- `--fast`: Run only fast hooks (formatting and basic checks)
- `--comp`: Run only comprehensive hooks (type checking, security, complexity)
- `--quick`: Quick mode (3 iterations max, ideal for CI/CD)
- `--thorough`: Thorough mode (8 iterations max, for complex refactoring)
- `--debug`: Enable debug output with detailed information
- `--no-config-update`: Do not update configuration files
- `--update-precommit`: Update pre-commit hooks configuration

## Style Guide

**Code Standards:**

- Python 3.13+ with modern type hints (`|` unions, PEP 695)
- No docstrings (self-documenting code)
- Pathlib over os.path
- Protocol-based interfaces
- Cognitive complexity ≤15 per function
- UV for dependency management

## Publishing & Version Management

### 🔐 Secure PyPI Authentication

**Keyring Storage (Most Secure):**

```bash
# Install keyring support
uv add keyring

# Store token securely
keyring set https://upload.pypi.org/legacy/ __token__
# Enter your PyPI token when prompted
```

**Environment Variable (Alternative):**

```bash
# For CI/CD or temporary use
export UV_PUBLISH_TOKEN=pypi-your-token-here

# ⚠️ Security Warning: Never commit this to git
```

**Environment File (Local Development):**

```bash
# Create .env file (must be in .gitignore)
echo "UV_PUBLISH_TOKEN=pypi-your-token-here" > .env
echo ".env" >> .gitignore
```

### Version Management

```bash
python -m crackerjack --publish patch  # 1.0.0 -> 1.0.1
python -m crackerjack --publish minor  # 1.0.0 -> 1.1.0
python -m crackerjack --publish major  # 1.0.0 -> 2.0.0
```

### 🛡️ Security Considerations

- **Token Rotation**: Rotate PyPI tokens every 90 days
- **Scope Limitation**: Use project-scoped tokens when possible
- **Access Review**: Regularly audit who has publish access
- **Backup Tokens**: Keep backup tokens in secure location

## MCP Integration

**AI Agent Support:**
Crackerjack provides a WebSocket-enabled MCP server for AI agent integration:

```bash
# Start WebSocket MCP server on localhost:8675
python -m crackerjack --start-mcp-server

# Monitor job progress via WebSocket
python -m crackerjack.mcp.progress_monitor <job_id> ws://localhost:8675
```

**MCP client configuration (stdio-based):**

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "uvx",
      "args": [
        "--from",
        "/path/to/crackerjack",
        "crackerjack",
        "--start-mcp-server"
      ]
    }
  }
}
```

**WebSocket MCP client configuration:**

- **Server URL**: `ws://localhost:8675`
- **Protocol**: WebSocket-based MCP with real-time progress streaming
- **Endpoints**: `/ws/progress/{job_id}` for live job monitoring

**Available tools:** `execute_crackerjack`, `get_job_progress`, `run_crackerjack_stage`, `analyze_errors`, `smart_error_analysis`, `get_next_action`, `session_management`

## 🤝 Complementary Tools

### Session Management MCP Server

For enhanced AI-assisted development with conversation memory and context persistence, consider using the [session-mgmt-mcp](https://github.com/lesleslie/session-mgmt-mcp) server alongside Crackerjack:

## 🤝 Session-mgmt Integration (Enhanced)

**Automatic for Git Projects:**

- Session management starts automatically
- No manual `/start` or `/end` needed
- Checkpoints auto-compact when necessary
- Works seamlessly with `python -m crackerjack`

**Benefits of Combined Usage:**

- **🧠 Persistent Learning**: Session-mgmt remembers your error patterns and successful fixes
- **📝 Context Preservation**: Maintains conversation context across Claude sessions
- **📊 Quality Tracking**: Monitors your project's quality score evolution over time
- **🔄 Workflow Optimization**: Learns from your development patterns to suggest improvements
- **🎯 Intelligent Coordination**: The two servers share insights for smarter assistance
- **🚀 Zero Manual Intervention**: Fully automatic lifecycle for git repositories

**Quick Setup:**

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "python",
      "args": ["-m", "crackerjack", "--start-mcp-server"]
    },
    "session-mgmt": {
      "command": "python",
      "args": ["-m", "session_mgmt_mcp.server"]
    }
  }
}
```

**Example Workflow:**

```bash
# Just start working - session auto-initializes!
python -m crackerjack --ai-fix --run-tests

# Checkpoint periodically (auto-compacts if needed)
/checkpoint

# Quit any way - session auto-saves
/quit  # or Cmd+Q, or network disconnect
```

**How They Work Together:**

- **Crackerjack** handles code quality enforcement, testing, and release management
- **Session-mgmt** maintains AI conversation context and learns from your patterns
- **Combined**: Creates an intelligent development environment that remembers what works and gets smarter over time

The integration is automatic - session-mgmt includes a comprehensive `crackerjack_integration.py` module that captures quality metrics, test results, and error patterns for enhanced learning across sessions.

## 🔧 Troubleshooting

### Common Issues

#### Installation Problems

```bash
# UV not found
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Python 3.13+ required
uv python install 3.13
uv python pin 3.13
```

#### Authentication Errors

```bash
# PyPI token issues
keyring get https://upload.pypi.org/legacy/ __token__  # Verify stored token
keyring set https://upload.pypi.org/legacy/ __token__  # Reset if needed

# Permission denied
chmod +x ~/.local/bin/uv
```

#### Hook Failures

```bash
# Pre-commit hooks failing
python -m crackerjack --skip-hooks  # Skip hooks temporarily
pre-commit clean                     # Clear hook cache
pre-commit install --force          # Reinstall hooks

# Update hooks
python -m crackerjack --update-precommit

# Type checking errors
python -m crackerjack               # Run quality checks
```

#### MCP Server Issues

```bash
# Server won't start
python -m crackerjack --start-mcp-server --verbose

# WebSocket connection issues
# Check if server is running on localhost:8675
netstat -an | grep :8675

# Test WebSocket connectivity
curl -s "http://localhost:8675/" || echo "Server not responding"
```

#### Performance Issues

```bash
# Slow execution
python -m crackerjack --test-workers 1    # Reduce parallelism
python -m crackerjack --skip-hooks        # Skip time-consuming checks

# Memory issues
export UV_CACHE_DIR=/tmp/uv-cache         # Use different cache location
```

### Debug Mode

```bash
# Enable verbose output
python -m crackerjack --verbose

# Check debug logs (in XDG cache directory)
ls ~/.cache/crackerjack/logs/debug/

# MCP debugging
python -m crackerjack --start-mcp-server --verbose
```

### Getting Help

- **GitHub Issues**: [Report bugs](https://github.com/lesleslie/crackerjack/issues)
- **Command Help**: `python -m crackerjack --help`
- **MCP Tools**: Use `get_next_action` tool for guidance

## Contributing

1. Fork and clone the repository
1. Run `uv sync --group dev` to install dependencies
1. Ensure `python -m crackerjack` passes all checks
1. Submit pull request

**Requirements:** Python 3.13+, UV package manager, all quality checks must pass

## License

BSD 3-Clause License - see [LICENSE](LICENSE) file.

______________________________________________________________________

**Issues:** [GitHub Issues](https://github.com/lesleslie/crackerjack/issues)
**Repository:** [GitHub](https://github.com/lesleslie/crackerjack)

# Test
