# CLAUDE Quick Start & Command Reference

Quick reference for common Crackerjack development tasks.

> **For architecture overview**, see [CLAUDE_ARCHITECTURE.md](./CLAUDE_ARCHITECTURE.md)
> **For working protocols**, see [CLAUDE_PROTOCOLS.md](./CLAUDE_PROTOCOLS.md)
> **For code patterns**, see [CLAUDE_PATTERNS.md](./CLAUDE_PATTERNS.md)

## Essential Commands

### Daily Development (Most Common)

```bash
# Recommended daily workflow (quality + tests + AI fixes)
python -m crackerjack run --ai-fix --run-tests

# Quality checks only (faster iteration)
python -m crackerjack run

# With tests (no AI auto-fixing)
python -m crackerjack run --run-tests
```

### Testing Specific Scenarios

```bash
# Single test
pytest tests/test_file.py::TestClass::test_method -v

# Test file
pytest tests/test_file.py -v

# Test directory
pytest tests/test_dir/ -v

# With coverage report
pytest --cov=crackerjack --cov-report=html

# Run tests via crackerjack (auto-detects workers)
python -m crackerjack run --run-tests
python -m crackerjack run --run-tests --test-workers 4  # Explicit workers
python -m crackerjack run --run-tests --test-workers 1  # Sequential debugging
python -m crackerjack run --run-tests --test-workers -2  # Fractional (half cores)
```

**Test Performance:**

- Auto-detection (default): 3-4x faster on 8-core systems
- Sequential (--test-workers 1): For debugging flaky tests
- Fractional (--test-workers -2): Conservative parallelization

### MCP Server Management

```bash
python -m crackerjack start      # Start MCP server
python -m crackerjack stop       # Stop server
python -m crackerjack restart    # Restart server
python -m crackerjack status     # Check server status
python -m crackerjack health     # Health check
```

### Release Workflow

```bash
# Full release (bump version + quality + tests + publish)
python -m crackerjack run --all patch

# Quick publish (bump + publish only)
python -m crackerjack run --publish patch
```

### Development Iteration

```bash
# Skip quality hooks for rapid iteration
python -m crackerjack run --skip-hooks

# Strip code (remove docstrings/comments)
python -m crackerjack run --strip-code

# Code cleaning mode
python -m crackerjack run -x

# Interactive mode
python -m crackerjack run -i

# Verbose output
python -m crackerjack run -v
```

### AI Agent Features

```bash
# Standard AI agent mode (recommended)
python -m crackerjack run --ai-fix --run-tests --verbose

# Preview fixes without applying (dry-run mode)
python -m crackerjack run --dry-run --run-tests

# Custom iteration limit
python -m crackerjack run --ai-fix --max-iterations 15

# AI debugging mode
python -m crackerjack run --ai-debug --run-tests
```

### Configuration Management

```bash
# Show coverage status
python -m crackerjack run --coverage-status

# Generate API documentation
python -m crackerjack run --generate-docs

# Validate existing documentation
python -m crackerjack run --validate-docs

# Check for configuration updates
python -m crackerjack run --check-config-updates

# Refresh configuration cache
python -m crackerjack run --refresh-cache
```

### Performance & Debugging

```bash
# Display cache statistics
python -m crackerjack run --cache-stats

# Clear all caches
python -m crackerjack run --clear-cache

# Run in benchmark mode
python -m crackerjack run --benchmark

# Enable development monitors
python -m crackerjack run --dev
```

### Advanced Features

```bash
# Enable parallel phase execution
python -m crackerjack run --enable-parallel-phases --run-tests -c

# Run orchestrated workflow
python -m crackerjack run --orchestrated

# Enhanced monitoring
python -m crackerjack run --enhanced-monitor

# Service watchdog
python -m crackerjack run --watchdog
```

### Dependency Management

```bash
# Install dependencies using UV
uv pip install <package>

# Check dependencies
uv pip check

# Sync lock file
uv sync

# Update specific dependency
uv lock --upgrade-package <package>
```

## Command Shorthands

Crackerjack provides many short flags:

| Short | Long | Description |
|-------|--------|-------------|
| `-t` | `--run-tests` | Run test suite |
| `-x` | `--strip-code` | Strip code mode |
| `-c` | `--comp` | Run comprehensive hooks only |
| `-v` | `--verbose` | Verbose output |
| `-i` | `--interactive` | Interactive mode |
| `-a` | `--all` | Full release workflow |
| `-b` | `--bump` | Bump version |
| `-p` | `--publish` | Publish to PyPI |

## Common Workflows

### Initial Setup

```bash
# Install dependencies
uv sync

# Run initial quality checks
python -m crackerjack run

# Run with tests
python -m crackerjack run --run-tests
```

### Feature Development

```bash
# Development iteration (skip hooks for speed)
python -m crackerjack run --skip-hooks

# Quality check before committing
python -m crackerjack run

# Full workflow with AI fixing
python -m crackerjack run --ai-fix --run-tests
```

### Pre-Commit Workflow

```bash
# Standard quality check
python -m crackerjack run

# With tests
python -m crackerjack run --run-tests

# With AI auto-fixing
python -m crackerjack run --ai-fix --run-tests
```

### Release Process

```bash
# Full release (recommended)
python -m crackerjack run --all patch

# Or step-by-step:
python -m crackerjack run --bump patch      # Bump version
python -m crackerjack run                   # Quality checks
python -m crackerjack run --run-tests        # Run tests
python -m crackerjack run --publish patch     # Publish to PyPI
```

## Quality Hook Reference

### Fast Hooks (~5 seconds)

- Ruff formatting
- Trailing whitespace cleanup
- UV lock file updates
- Security credential detection
- Spell checking (codespell)

### Comprehensive Hooks (~30 seconds)

- **Zuban** (Rust type checker): 20-200x faster than pyright
- **Bandit**: Security analysis
- **Complexipy**: Complexity analysis
- **Refurb**: Python idiom checks
- **Creosote**: Unused dependency detection
- **Skylos** (Rust): Dead code detection, 20x faster than vulture
- **Pyright**: Type checking (alternative)

## Troubleshooting

### Testing Issues

```bash
# Slow tests (enable auto-detection)
python -m crackerjack run --run-tests  # Default auto-detects

# Flaky tests (run sequentially to debug)
python -m crackerjack run --run-tests --test-workers 1

# Out of memory errors
python -m crackerjack run --run-tests --test-workers -2  # Use half cores
```

### Import Errors

```bash
# Always import protocols from models/protocols.py
from crackerjack.models.protocols import Console, TestManagerProtocol

# Never import concrete classes
# ❌ from crackerjack.managers.test_manager import TestManager
```

### Quality Gate Failures

```bash
# Run comprehensive checks
python -m crackerjack run -c

# Fix complexity issues
# Break functions into helpers (max 15 complexity)

# Enable AI auto-fixing
python -m crackerjack run --ai-fix
```

### MCP Server Issues

```bash
# Server won't start
python -m crackerjack start --verbose

# Check server status
python -m crackerjack status

# Test server health
python -m crackerjack health
```

## Configuration Reference

### pyproject.toml

Key configuration sections:

```toml
[tool.crackerjack]
# Test workers (0 = auto-detect)
test_workers = 0

# MCP server ports
mcp_http_port = 8676
mcp_websocket_port = 8675

# Terminal width
terminal_width = 70

# Timeout values (in seconds)
zuban_timeout = 60
refurb_timeout = 600
```

### Settings Files

**Runtime Configuration:**

- `settings/crackerjack.yaml` - Base configuration (committed)
- `settings/local.yaml` - Local overrides (gitignored)

**Priority Order:**

1. `settings/local.yaml` - Highest priority
1. `settings/crackerjack.yaml` - Base configuration
1. Default values - Fallback

**Example local.yaml:**

```yaml
# Enable verbose output
verbose: true

# Set test workers
test_workers: 4

# Enable AI debugging
ai_debug: true

# Skills tracking
skills:
  enabled: true
  backend: auto
  min_similarity: 0.3
```

## See Also

- **[CLAUDE_ARCHITECTURE.md](./CLAUDE_ARCHITECTURE.md)**: Directory structure, layers, patterns
- **[CLAUDE_PROTOCOLS.md](./CLAUDE_PROTOCOLS.md)**: Code review, evidence, compliance
- **[CLAUDE_PATTERNS.md](./CLAUDE_PATTERNS.md)**: Code standards, conventions
- **[README.md](./README.md)**: Complete project documentation
