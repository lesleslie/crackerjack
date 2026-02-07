# Crackerjack CLI Reference

Complete command-line interface reference for Crackerjack.

## Table of Contents

- [Core Commands](#core-commands)
- [Quality Check Commands](#quality-check-commands)
- [AI Integration Commands](#ai-integration-commands)
- [Testing Commands](#testing-commands)
- [Coverage Commands](#coverage-commands)
- [MCP Server Commands](#mcp-server-commands)
- [Publishing Commands](#publishing-commands)
- [Monitoring Commands](#monitoring-commands)
- [Configuration Commands](#configuration-commands)
- [Advanced Options](#advanced-options)

## Core Commands

### `crackerjack run`

**Description**: Run quality checks with optional AI auto-fixing and testing.

**Usage**:

```bash
python -m crackerjack run [OPTIONS]
```

**Basic Examples**:

```bash
# Quality checks only (default)
python -m crackerjack run

# Quality checks + tests
python -m crackerjack run --run-tests

# AI auto-fixing + tests (recommended)
python -m crackerjack run --ai-fix --run-tests

# Fast mode (skip comprehensive hooks)
python -m crackerjack run --fast
```

**Output**:

```
🚀 Starting Crackerjack quality checks...

✅ Fast hooks completed in 4.8s
   ✓ Ruff formatting (23 files)
   ✓ Trailing whitespace cleanup
   ✓ UV lock file validation
   ✓ Credential detection
   ✓ Spell checking

✅ Comprehensive hooks completed in 28.3s
   ✓ Zuban type checking (45 files)
   ✓ Bandit security analysis (23 files)
   ✓ Dead code detection
   ✓ Dependency analysis
   ✓ Complexity limits
   ✓ Modern Python patterns

🎉 All quality checks passed!
```

### `crackerjack start`

**Description**: Start MCP server for AI agent integration.

**Usage**:

```bash
python -m crackerjack start [OPTIONS]
```

**Examples**:

```bash
# Start MCP server (stdio transport)
python -m crackerjack start

# Start with verbose logging
python -m crackerjack start --verbose

# Start with custom port
python -m crackerjack start --mcp-port 8676
```

### `crackerjack status`

**Description**: Check MCP server status.

**Usage**:

```bash
python -m crackerjack status
```

**Output**:

```
📊 MCP Server Status

Server: Running
PID: 12345
Uptime: 2h 34m
Port: 8676 (HTTP), 8675 (WebSocket)

Active Jobs: 3
  - job_abc123: Running (45%)
  - job_def456: Running (78%)
  - job_ghi789: Completed

Cache Stats:
  - Hit Rate: 72%
  - Size: 847 entries
  - TTL: 3600s
```

### `crackerjack health`

**Description**: Health check for MCP server.

**Usage**:

```bash
python -m crackerjack health [--probe]
```

**Examples**:

```bash
# Basic health check
python -m crackerjack health

# Liveness probe (for Kubernetes)
python -m crackerjack health --probe
```

**Output**:

```
✅ MCP Server is healthy

Components:
  ✓ WebSocket Server
  ✓ Job Manager
  ✓ Error Cache
  ✓ Tool Registry

Metrics:
  - Active Jobs: 3
  - Queue Depth: 0
  - Memory Usage: 145MB
  - CPU Usage: 2.3%
```

## Quality Check Commands

### `--fast`

**Description**: Run only fast hooks (~5 seconds).

**Usage**:

```bash
python -m crackerjack run --fast
```

**Fast Hooks**:
- Ruff formatting
- Trailing whitespace cleanup
- UV lock file validation
- Credential detection
- Spell checking

### `--comp` (Comprehensive)

**Description**: Run only comprehensive hooks (~30 seconds).

**Usage**:

```bash
python -m crackerjack run --comp
```

**Comprehensive Hooks**:
- Zuban type checking
- Bandit security analysis
- Dead code detection
- Dependency analysis
- Complexity limits
- Modern Python patterns

### `--skip-hooks`

**Description**: Skip quality checks (useful for rapid iteration).

**Usage**:

```bash
python -m crackerjack run --skip-hooks --run-tests
```

**Use Case**: During development, when you want to run tests without waiting for quality checks.

### `--quality-tier`

**Description**: Set quality tier (bronze, silver, gold).

**Usage**:

```bash
python -m crackerjack run --quality-tier silver
```

**Tiers**:

| Tier | Coverage | Complexity | Type Coverage |
|------|----------|------------|---------------|
| Bronze | ≥50% | ≤25 | ≥30% |
| Silver | ≥80% | ≤15 | ≥60% |
| Gold | ≥95% | ≤10 | ≥80% |

## AI Integration Commands

### `--ai-fix`

**Description**: Enable AI-powered auto-fixing.

**Usage**:

```bash
python -m crackerjack run --ai-fix
```

**How It Works**:

1. Run all quality checks
2. Collect all failures
3. AI analyzes each issue
4. Applies targeted fixes
5. Re-runs checks
6. Repeats until all pass (max 8 iterations)

**Output**:

```
🤖 AI Auto-Fixing Enabled

Iteration 1/8:
  ❌ 12 issues found
  🤖 AI analyzing issues...
  ✅ 10 issues fixed automatically
  ❌ 2 issues require manual review

Iteration 2/8:
  ❌ 2 issues remaining
  🤖 AI analyzing issues...
  ✅ 2 issues fixed automatically

✅ All quality checks passed after 2 iterations!
```

### `--ai-debug`

**Description**: Verbose debugging for AI auto-fixing.

**Usage**:

```bash
python -m crackerjack run --ai-fix --ai-debug --run-tests
```

**Output Includes**:
- AI agent selection reasoning
- Confidence scores for each fix
- Prompt/response details
- Fix validation results

### `--dry-run`

**Description**: Preview AI fixes without applying changes.

**Usage**:

```bash
python -m crackerjack run --ai-fix --dry-run
```

**Use Case**: Review what AI would change before applying fixes.

### `--max-iterations`

**Description**: Set maximum iterations for AI auto-fixing.

**Usage**:

```bash
python -m crackerjack run --ai-fix --max-iterations 15
```

**Default**: 8 iterations
**CI/CD Recommended**: 3 iterations (`--quick` mode)

### `--quick`

**Description**: Quick mode (3 iterations max, for CI/CD).

**Usage**:

```bash
python -m crackerjack run --ai-fix --quick --run-tests
```

**Use Case**: CI/CD pipelines where speed is critical.

### `--thorough`

**Description**: Thorough mode (8 iterations max, for complex refactoring).

**Usage**:

```bash
python -m crackerjack run --ai-fix --thorough --run-tests
```

**Use Case**: Complex refactoring tasks that require multiple iterations.

## Testing Commands

### `--run-tests` / `-t`

**Description**: Execute test suite with coverage ratchet.

**Usage**:

```bash
python -m crackerjack run --run-tests
```

**Output**:

```
🧪 Running tests...

✅ 324 tests passed in 12.5s
📊 Coverage: 75.3% (+2.1% from baseline)
🏆 Milestone achieved: 75% coverage!
📈 Progress: [████████░░░░░░░░░░░] 75.3% → 100%
🎯 Next milestone: 80% (+4.7% needed)
```

### `--xcode-tests`

**Description**: Run Xcode tests (macOS only).

**Usage**:

```bash
python -m crackerjack run --xcode-tests --xcode-project MyProject.xcodeproj --xcode-scheme MyScheme
```

**Options**:
- `--xcode-project`: Path to Xcode project
- `--xcode-scheme`: Scheme to test
- `--xcode-destination`: Destination string
- `--xcode-configuration`: Build configuration

### `--benchmark`

**Description**: Run tests in benchmark mode.

**Usage**:

```bash
python -m crackerjack run --benchmark
```

**Output**:

```
📊 Benchmark Results

test_fast_operation:
  Mean: 0.002s
  StdDev: 0.0001s
  Min: 0.0018s
  Max: 0.0025s

test_slow_operation:
  Mean: 1.234s
  StdDev: 0.012s
  Min: 1.220s
  Max: 1.250s
```

## Coverage Commands

### `--coverage-status`

**Description**: Show coverage ratchet status.

**Usage**:

```bash
python -m crackerjack run --coverage-status
```

**Output**:

```
📊 Coverage Ratchet Status

Current Coverage: 75.3%
Baseline Coverage: 70.0%
Improvement: +5.3%

Milestones:
  ✅ 15% achieved
  ✅ 25% achieved
  ✅ 50% achieved
  ✅ 75% achieved
  ⏳ 80% (next, +4.7% needed)
  ⏳ 90% (+14.7% needed)
  ⏳ 100% (+24.7% needed)
```

### `--coverage-goal`

**Description**: Set explicit coverage goal.

**Usage**:

```bash
python -m crackerjack run --coverage-goal 85.0 --run-tests
```

**Default**: Continuous improvement (no explicit goal, ratchet only)

### `--no-coverage-ratchet`

**Description**: Disable coverage ratchet temporarily.

**Usage**:

```bash
python -m crackerjack run --no-coverage-ratchet --run-tests
```

**Use Case**: When you need to temporarily decrease coverage (rare).

### `--boost-coverage`

**Description**: Auto-improve test coverage (default).

**Usage**:

```bash
python -m crackerjack run --boost-coverage --run-tests
```

**Enabled by default**: AI will suggest new tests to increase coverage.

### `--no-boost-coverage`

**Description**: Disable coverage improvements.

**Usage**:

```bash
python -m crackerjack run --no-boost-coverage --run-tests
```

## Publishing Commands

### `--publish` / `-p`

**Description**: Bump version and publish to PyPI.

**Usage**:

```bash
python -m crackerjack run --publish [VERSION_TYPE]
```

**Version Types**:
- `patch`: 1.0.0 → 1.0.1 (bug fixes)
- `minor`: 1.0.0 → 1.1.0 (new features)
- `major`: 1.0.0 → 2.0.0 (breaking changes)

**Examples**:

```bash
# Patch release (bug fixes)
python -m crackerjack run --publish patch

# Minor release (new features)
python -m crackerjack run --publish minor

# Major release (breaking changes)
python -m crackerjack run --publish major
```

**Workflow**:

```
1. Bump version in pyproject.toml
2. Run quality checks
3. Run tests
4. Build package
5. Publish to PyPI
```

### `--bump` / `-b`

**Description**: Bump version without publishing.

**Usage**:

```bash
python -m crackerjack run --bump [VERSION_TYPE]
```

**Use Case**: When you want to bump version but publish later.

### `--all` / `-a`

**Description**: Full release workflow (bump, test, publish).

**Usage**:

```bash
python -m crackerjack run --all [VERSION_TYPE]
```

**Equivalent to**:

```bash
python -m crackerjack run --bump [VERSION_TYPE] --run-tests --publish [VERSION_TYPE]
```

## Monitoring Commands

### `--monitor`

**Description**: Multi-project progress monitor.

**Usage**:

```bash
python -m crackerjack run --monitor
```

**Output**:

```
📊 Multi-Project Monitor

Project A:
  Status: Running
  Phase: Comprehensive Hooks
  Progress: 65%
  Issues: 3 found

Project B:
  Status: Completed
  Phase: All
  Progress: 100%
  Issues: 0 found

Project C:
  Status: Failed
  Phase: Fast Hooks
  Progress: 20%
  Issues: 12 found
```

### `--enhanced-monitor`

**Description**: Advanced monitoring with patterns.

**Usage**:

```bash
python -m crackerjack run --enhanced-monitor
```

**Features**:
- Pattern detection
- Anomaly detection
- Predictive alerts
- Historical trends

### `--watchdog`

**Description**: Service watchdog with auto-restart.

**Usage**:

```bash
python -m crackerjack run --watchdog
```

**Features**:
- Monitors MCP server health
- Auto-restart on failure
- Crash detection
- Performance monitoring

## Configuration Commands

### `--cache-stats`

**Description**: Display cache statistics.

**Usage**:

```bash
python -m crackerjack run --cache-stats
```

**Output**:

```
📊 Cache Statistics

Hit Rate: 72.3%
Size: 847 entries
Memory: 45.2MB
TTL: 3600s

Top Entries:
  - ruff_format:main.py:453 hits
  - zuban:type_check:231 hits
  - bandit:security:187 hits
```

### `--clear-cache`

**Description**: Clear all caches and exit.

**Usage**:

```bash
python -m crackerjack run --clear-cache
```

**Use Case**: When cache is corrupted or causing issues.

### `--refresh-cache`

**Description**: Refresh configuration cache.

**Usage**:

```bash
python -m crackerjack run --refresh-cache
```

**Invalidates**: Pre-commit cache, configuration cache, tool cache.

### `--check-config-updates`

**Description**: Check for available configuration updates.

**Usage**:

```bash
python -m crackerjack run --check-config-updates
```

**Output**:

```
📦 Configuration Updates Available

pyproject.toml: Update available
  - ruff: 0.1.0 → 0.2.0
  - zuban: 1.0.0 → 1.1.0

.pre-commit-config.yaml: Update available
  - bandit: 1.7.0 → 1.8.0
```

### `--diff-config`

**Description**: Show diff for specific configuration type.

**Usage**:

```bash
python -m crackerjack run --diff-config pre-commit
```

**Output**: Unified diff of proposed changes.

### `--apply-config-updates`

**Description**: Apply configuration updates interactively.

**Usage**:

```bash
python -m crackerjack run --apply-config-updates --config-interactive
```

**Prompts** for each update: `Apply this update? [y/N]`

## Advanced Options

### `--verbose` / `-v`

**Description**: Enable verbose output.

**Usage**:

```bash
python -m crackerjack run --verbose
```

**Output Includes**:
- Detailed adapter execution
- Cache hits/misses
- Performance metrics
- Error stack traces

### `--debug`

**Description**: Enable debug output with detailed information.

**Usage**:

```bash
python -m crackerjack run --debug
```

**Output Includes**:
- Extremely verbose logging
- Internal state dumps
- Timing information
- Trace logs

### `--interactive` / `-i`

**Description**: Use Rich UI interface with better experience.

**Usage**:

```bash
python -m crackerjack run --interactive
```

**Features**:
- Rich progress bars
- Colored output
- Interactive menus
- Real-time updates

### `--strip-code` / `-x`

**Description**: Remove docstrings/comments for production.

**Usage**:

```bash
python -m crackerjack run --strip-code
```

**Warning**: This is destructive! Backup your code first.

### `--dev`

**Description**: Enable development mode for progress monitors.

**Usage**:

```bash
python -m crackerjack run --dev --monitor
```

**Features**:
- Live reload
- Debug logging
- Profiling enabled

### `--generate-docs`

**Description**: Generate comprehensive API documentation.

**Usage**:

```bash
python -m crackerjack run --generate-docs
```

**Options**:
- `--docs-format`: Documentation format (markdown/rst/html)
- `--validate-docs`: Validate existing documentation

### `--orchestrated`

**Description**: Advanced orchestrated workflow mode.

**Usage**:

```bash
python -m crackerjack run --orchestrated
```

**Features**:
- Complex workflow orchestration
- Multi-phase coordination
- Advanced error handling

## Global Options

### Environment Variables

**Crackerjack** respects these environment variables:

```bash
# PyPI Authentication
export UV_PUBLISH_TOKEN=pypi-your-token-here

# Keyring Provider
export UV_KEYRING_PROVIDER=subprocess

# Default Editor
export EDITOR=code --wait

# AI Integration
export ANTHROPIC_API_KEY=sk-ant-...

# MCP Server
export CRACKERJACK_MCP_HOST=127.0.0.1
export CRACKERJACK_MCP_PORT=8676
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Quality checks failed |
| 2 | Tests failed |
| 3 | Configuration error |
| 4 | Runtime error |

## Help

### `--help`

**Description**: Show help message and exit.

**Usage**:

```bash
python -m crackerjack run --help
```

**Output**: Complete list of options and descriptions.

## Examples

### Common Workflows

**Development Workflow**:

```bash
# 1. Make changes
vim src/my_module.py

# 2. Quality checks
python -m crackerjack run

# 3. Fix issues
python -m crackerjack run --ai-fix

# 4. Run tests
python -m crackerjack run --run-tests

# 5. Commit
git add . && git commit -m "Add feature"
```

**CI/CD Workflow**:

```bash
# Quick mode for CI/CD
python -m crackerjack run --quick --run-tests
```

**Release Workflow**:

```bash
# Full release
python -m crackerjack run --all patch
```

## Summary

**Most Common Commands**:

```bash
# Quality checks
python -m crackerjack run

# Quality + tests
python -m crackerjack run --run-tests

# AI auto-fixing + tests
python -m crackerjack run --ai-fix --run-tests

# Coverage status
python -m crackerjack run --coverage-status

# Publish release
python -m crackerjack run --publish patch
```

**For More Information**:
- [Quick Start Guide](QUICK_START.md)
- [User Guide](USER_GUIDE.md)
- [Architecture](ARCHITECTURE.md)

---

**Last Updated**: 2025-02-06
**Crackerjack Version**: 0.51.0
