# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Clean Code Philosophy (READ FIRST)

**EVERY LINE OF CODE IS A LIABILITY. The best code is no code.**

- **DRY**: If you write it twice, you're doing it wrong
- **YAGNI**: Build only what's needed NOW
- **KISS**: Complexity is the enemy of maintainability
- **Less is More**: Prefer 10 clear lines over 100 clever ones
- **Code is Read 10x More Than Written**: Optimize for readability
- **Self-Documenting Code**: Variable names must be clear and descriptive, even in inline functions

## Design Philosophy

- **Auto-Discovery**: Prefer intelligent auto-discovery of configurations and settings over manual configuration whenever possible, reducing setup friction and configuration errors

## Project Overview

Crackerjack is an opinionated Python project management tool unifying UV, Ruff, pytest, and pre-commit into a single workflow. Enforces consistent code quality with AI agent integration via MCP.

**Key Dependencies**: Python 3.13+, UV, pre-commit, pytest

## Quick Reference

### Most Used Commands

```bash
# Daily development workflow
python -m crackerjack                      # Quality checks only
python -m crackerjack -t                   # With tests
python -m crackerjack --ai-agent -t        # AI auto-fixing (recommended)

# Debugging and monitoring
python -m crackerjack --ai-debug -t        # AI debug mode with verbose output
python -m crackerjack --enhanced-monitor   # Progress monitor with advanced UI
python -m crackerjack --watchdog           # Auto-restart services monitor

# Server management
python -m crackerjack --start-mcp-server      # Start MCP server
python -m crackerjack --start-websocket-server # Start WebSocket server
python -m crackerjack --restart-mcp-server    # Restart MCP server

# Release workflow
python -m crackerjack --bump patch         # Version bump only
python -m crackerjack -a patch              # Full release with publishing
```

### Common Flags

| Flag | Purpose | When to Use |
|------|---------|-------------|
| `-t` | Include tests | Always for comprehensive validation |
| `--ai-agent` | Enable AI auto-fixing | Standard process for quality compliance |
| `--ai-debug` | Verbose AI debugging | When troubleshooting AI agent issues |
| `-x` | Code cleaning mode | When ready to resolve all TODOs |
| `-i` | Interactive mode | For step-by-step workflow control |
| `--skip-hooks` | Skip pre-commit hooks | During rapid development iterations |
| `--quick` | Quick mode (3 iterations) | CI/CD pipelines or rapid testing |
| `--thorough` | Thorough mode (8 iterations) | Complex refactoring or difficult issues |
| `--verbose` | Extra output | When diagnosing issues |

### Agent Selection Guide

**When to Use Which Specialist Agent:**

| Issue Type | Best Agent | Confidence | Use Case |
|------------|------------|------------|----------|
| **Documentation inconsistencies** | DocumentationAgent | 0.8 | Changelog updates, .md file consistency |
| **Cognitive complexity >15** | RefactoringAgent | 0.9 | Breaking down complex functions |
| **Unused imports/dead code** | RefactoringAgent | 0.8 | AST-based cleanup |
| **Performance bottlenecks** | PerformanceAgent | 0.85 | O(n²) loops, string concatenation |
| **Code duplication** | DRYAgent | 0.8 | Extract common patterns |
| **Import/formatting issues** | FormattingAgent | 0.8 | Code style violations |
| **Security vulnerabilities** | SecurityAgent | 0.8 | Hardcoded paths, unsafe operations |
| **Test failures** | TestCreationAgent | 0.8 | Missing fixtures, assertion issues |
| **Complex test scenarios** | TestSpecialistAgent | 0.8 | Advanced test frameworks |

**Decision Tree:**

1. **Type errors?** → Use AI agent auto-fixing (handles all types)
1. **Single issue type?** → Use specific agent with confidence ≥0.7
1. **Multiple issue types?** → Use AI agent batch fixing
1. **Documentation issues?** → Always use DocumentationAgent
1. **Performance issues?** → Always use PerformanceAgent (real code transformation)

## Core Development Commands

### Primary Workflows

```bash
# Quality checks only (most common during development)
python -m crackerjack

# With testing
python -m crackerjack -t

# Code cleaning with TODO detection (blocks if TODOs found)
# Note: Automatically creates backups in temp directory for safety
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

# Quick mode (3 iterations) - ideal for CI/CD
python -m crackerjack --quick --ai-agent -t

# Thorough mode (8 iterations) - for complex refactoring
python -m crackerjack --thorough --ai-agent -t

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

**Two Types of Auto-Fixing:**

**1. Hook Auto-Fix (Limited)**: Basic formatting (`ruff --fix`, whitespace). Cannot fix logic/security/test issues.

**2. AI Agent (Comprehensive)**: Analyzes ALL error types, reads source code, makes intelligent modifications.

#### Standard Process

```bash
# Recommended workflow
python -m crackerjack --ai-agent -t

# AI workflow per iteration:
# 1. Fast Hooks → Retry once if fail
# 2. Full Test Suite → Collect ALL failures
# 3. Comprehensive Hooks → Collect ALL issues
# 4. AI Batch Fixing → Fix ALL collected issues
# 5. Repeat until perfect (up to 5 iterations)
```

**AI Auto-Fixes**: Type errors, security issues, dead code, test failures, complexity, dependencies, hooks

**Benefits**: Autonomous, intelligent, comprehensive, iterative, adaptive

#### Sub-Agent Architecture

**9 specialized agents handle domain-specific issues:**

- **DocumentationAgent** (0.8): Changelog generation, .md consistency, README updates
- **RefactoringAgent** (0.9): Complexity reduction ≤15, dead code removal, AST analysis
- **PerformanceAgent** (0.85): O(n²) detection, string optimization, real code transformation
- **DRYAgent** (0.8): Code duplication detection, pattern extraction, utility creation
- **FormattingAgent** (0.8): Style violations, import formatting, consistency
- **SecurityAgent** (0.8): Hardcoded paths, subprocess vulnerabilities, best practices
- **ImportOptimizationAgent**: Import cleanup, dead code removal, reorganization
- **TestCreationAgent** (0.8): Test failures, fixture management, dependencies
- **TestSpecialistAgent** (0.8): Advanced testing, framework integration

**Coordination**: AgentCoordinator routes by confidence (≥0.7 single-agent, \<0.7 collaborative), batch processing

### Temporary File Management

**Auto-cleanup**: Keeps 5 debug logs, 10 coverage files by default
**Options**: `--no-cleanup`, `--keep-debug-logs N`, `--keep-coverage-files N`

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

**Isolated execution**: `uvx crackerjack -t` (PyPI) or `uvx --from /path crackerjack -t` (local)

## Architecture Overview

**Modular architecture with dependency injection:**

### Core Layers

- **Orchestration**: `WorkflowOrchestrator`, DI containers with lifecycle management
- **Coordinators**: Session/phase coordination, async workflows with parallel execution
- **Managers**: Hook execution (fast→comprehensive), test management, publishing
- **Services**: Filesystem, git, config, security, health monitoring

### Key Patterns

**Dependency Flow**: `__main__.py` → `WorkflowOrchestrator` → Coordinators → Managers → Services

**Critical**: Always import protocols from `models/protocols.py`, never concrete classes

- ❌ `from ..managers.test_manager import TestManager`
- ✅ `from ..models.protocols import TestManagerProtocol`

### MCP Integration

**70% reduction**: 3,116 lines → modular architecture with tools, state management, rate limiting, monitoring
**WebSocket Server**: 35% reduction with FastAPI, job management, progress streaming
**Entry points**: `--start-mcp-server`, `--start-websocket-server`

## Quality Process

### Workflow Order

1. **Fast Hooks** (~5s): formatting, basic checks → retry once if fail
1. **Full Test Suite**: collect ALL failures, don't stop on first
1. **Comprehensive Hooks** (~30s): type checking, security, complexity → collect ALL issues
1. **AI Batch Fixing**: process all collected failures together

### Testing

**Framework**: pytest with asyncio, 300s timeout, auto-detected workers
**Coverage**: Ratchet system targeting 100%, never decrease

## Code Standards

### Principles

- **DRY/YAGNI/KISS**: Extract patterns, build only what's needed, choose simple solutions
- **Python 3.13+**: `|` unions, protocols, pathlib, `import typing as t`, Pydantic

### Quality Rules

- **Complexity ≤15** per function
- **No hardcoded paths** (use `tempfile`)
- **No shell=True** in subprocess
- **Type annotations required**
- **Protocol-based DI**
- **TODO resolution** required for cleaning mode

### Refactoring Pattern

```python
# Break complex methods into helper methods
def complex_method(self, data: dict) -> bool:
    if not self._validate_input(data):
        return self._handle_invalid_input()
    processed = self._process_data(data)
    return self._save_results(processed)
```

### Error Prevention Examples

```python
# Use tempfile, not hardcoded paths
with tempfile.NamedTemporaryFile(suffix=".yaml") as f:
    config_path = f.name

# Use contextlib.suppress, not try/except pass
from contextlib import suppress

with suppress(Exception):
    risky_operation()

# Use tuples for membership tests
if status in ("error", "failed", "timeout"):
    handle_error()

# Use comprehensions, not manual building
issues = [process(item) for item in data if condition(item)]

# Use dict.get with default
return AGENT_EMOJIS.get(agent_type, "🤖")

# Use operator functions, not lambdas
from operator import itemgetter

sorted_items = sorted(items, key=itemgetter("priority"))
```

### Regex Best Practices (CRITICAL)

**⚠️ WARNING: Bad regex caused security vulnerabilities. Always use centralized patterns.**

**NEVER write raw regex. Use centralized registry:**

```python
# ❌ DANGEROUS
text = re.sub(r"(\w+) - (\w+)", r"\g < 1 >-\g < 2 >", text)

# ✅ SAFE
from crackerjack.services.regex_patterns import SAFE_PATTERNS

text = SAFE_PATTERNS["fix_hyphenated_names"].apply(text)
```

**Available patterns**: command spacing, token masking, hyphenation, security fixes (18+ validated patterns)

**FORBIDDEN patterns that cause vulnerabilities:**

- `r"\g < 1 >"` (spaces in replacement - SECURITY ISSUE)
- `r"\g< 1>"` or `r"\g<1 >"` (spacing bugs)
- `r".*"` (overly broad)
- Raw token masking

**Security token masking**: Use word boundaries, comprehensive tests, consistent application
**Emergency fix**: Find with `rg "pattern"`, replace with `SAFE_PATTERNS["pattern_name"].apply(text)`

## Common Issues & Solutions

### Terminal Issues

- **Unresponsive terminal**: `./fix_terminal.sh` or `stty sane; reset; exec $SHELL -l`
- **No progress updates**: Start WebSocket server, verify at http://localhost:8675/

### Development Issues

- **AI agent ineffective**: Use `--ai-debug -t` for analysis
- **Import errors**: Always import protocols from `models/protocols.py`
- **Test hangs**: Avoid complex async tests, use simple synchronous config tests

### Quality Issues

- **Coverage failing**: Never reduce below baseline, add tests incrementally
- **Complexity >15**: Break into helper methods using RefactoringAgent approach
- **Security violations**: Use `SAFE_PATTERNS` for token masking
- **Regex issues**: Never use raw regex, use centralized patterns

### Server Issues

- **MCP not starting**: `--restart-mcp-server` or `--watchdog`
- **WebSocket failures**: Restart with `--websocket-port 8675`

### Performance Issues

- **Slow tests**: Customize `--test-workers N` or `--benchmark`
- **Memory issues**: PerformanceAgent detects O(n²) patterns
- **Slow hooks**: Use `--skip-hooks` during rapid iteration

## Development Workflow

### Standard Process

1. Run quality checks: `python -m crackerjack`
1. Run with tests: `python -m crackerjack -t`
1. Address remaining issues manually
1. Optional AI review: `mcp__gemini-cli__ask-gemini`
1. Commit: `python -m crackerjack -c`

### Testing Components

- **Specific**: `python -m pytest tests/test_managers.py -v`
- **Isolated**: `python -m pytest tests/test_file.py::TestClass::test_method -v -s`

### Common Issues

- **Import errors**: Check `models/protocols.py` for interfaces
- **Type errors**: Use `t.cast()`, ensure annotations
- **Complexity**: Break into helper methods

## MCP Server Integration

### Features

- **Dual Protocol**: MCP tools + WebSocket server on localhost:8675
- **Real-time Progress**: Live updates with Rich formatting
- **Job Tracking**: Comprehensive progress monitoring

### Usage

```bash
# Start WebSocket server
python -m crackerjack --start-websocket-server

# Use /crackerjack:run in Claude
# Progress at: http://localhost:8675/

# Monitor job
python -m crackerjack.mcp.progress_monitor <job_id>
```

### Available Tools

- `execute_crackerjack`: Start auto-fixing workflow
- `get_job_progress`: Get current job progress
- `get_comprehensive_status`: Complete system status
- `analyze_errors`: Error pattern analysis
- `session_management`: Track iterations

### Slash Commands

- **`/crackerjack:run`**: Full auto-fixing with progress tracking
- **`/crackerjack:status`**: System status and health
- **`/crackerjack:init`**: Initialize project configuration

## Configuration

- **Coverage**: Ratchet system targeting 100%
- **Complexity**: ≤15 per function
- **Python**: 3.13+ required
- **Test timeout**: 300s
- **Type checking**: Strict Pyright
- **Security**: Bandit scanning

## Service Watchdog

**Auto-restart system for servers**

### Usage

```bash
python -m crackerjack --watchdog
```

### Features

- **Real-time monitoring**: Process/health checks
- **Auto-restart**: Rate-limited with backoff (max 10/5min)
- **Dashboard**: Live status display
- **Health checks**: HTTP monitoring for WebSocket server
- **Graceful shutdown**: Ctrl+C cleanup

**Monitors**: MCP server (process), WebSocket server (process + HTTP health)

## Recent Achievements (January 2025)

**Refactoring Results:**

- **70% line reduction**: MCP server (3,116 → 921 lines)
- **35% line reduction**: WebSocket server (1,479 → 944 lines)
- **80% line reduction**: CLI entry point (601 → 122 lines)

**Quality Improvements:**

- Fixed all 31+ refurb violations
- Major complexity reductions: 34→3 (91%), 33→2 (94%)
- All 5 fast hooks passing consistently
- Protocol-based interfaces throughout

## Test Coverage Status

**Current**: 10.11% baseline targeting 100%
**Strategy**: Import-only tests, protocol compliance, async validation, integration testing
**Priority**: Fix existing failures first, then add tests incrementally

**Ratchet System**: 2% tolerance, never reduce coverage

## Critical Reminders

### Core Instructions

- Do only what's asked, nothing more
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing existing files
- NEVER proactively create documentation
- MAINTAIN coverage ratchet

### Quality Standards

- **Test Quality**: Avoid async tests that hang, use synchronous config tests
- **Honest Reporting**: Report actual percentages (10.17%, not "approaching 15%")
- **Import Compliance**: Use protocols from `models/protocols.py`
- **Fix failures FIRST** before creating new tests
- Use IDE diagnostics after implementation
- Be critical/comprehensive in reviews
- Use crackerjack-architect agent for compliant code

### Failure Patterns to Avoid

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
- make as few edits as possible by batching related changes together in a single operation.