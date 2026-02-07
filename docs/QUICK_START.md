# Crackerjack Quick Start Guide

Get started with Crackerjack in 5 minutes. This guide covers installation, basic usage, and common workflows.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Common Workflows](#common-workflows)
- [Configuration](#configuration)
- [Next Steps](#next-steps)

## Prerequisites

Before installing Crackerjack, ensure you have:

- **Python 3.13+**: Check with `python --version`
- **UV Package Manager**: Recommended for fast dependency management
- **Git Repository**: Crackerjack works best with version control

**Check Python Version**:

```bash
python --version
# Expected: Python 3.13.x

# If not 3.13, install it
uv python install 3.13
uv python pin 3.13
```

**Install UV** (if not installed):

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using Homebrew (macOS)
brew install uv

# Verify installation
uv --version
```

## Installation

### Option 1: UV Tool Installation (Recommended)

```bash
# Install as global tool
uv tool install crackerjack

# Verify installation
crackerjack --version
# Expected: Crackerjack 0.51.0
```

### Option 2: Project Dependency

```bash
# Navigate to your project
cd your-project

# Add as development dependency
uv add crackerjack --dev

# Verify installation
python -m crackerjack --version
```

### Option 3: Pip Installation

```bash
# Install using pip
pip install crackerjack

# Verify installation
python -m crackerjack --version
```

## Basic Usage

### 1. Run Quality Checks

The simplest way to use Crackerjack:

```bash
# Navigate to your project
cd your-project

# Run quality checks (fast + comprehensive hooks)
python -m crackerjack run
```

**Expected Output**:

```
🚀 Starting Crackerjack quality checks...

✅ Fast hooks completed in 4.8s
   ✓ Ruff formatting
   ✓ Trailing whitespace cleanup
   ✓ UV lock file validation
   ✓ Credential detection
   ✓ Spell checking

✅ Comprehensive hooks completed in 28.3s
   ✓ Zuban type checking
   ✓ Bandit security analysis
   ✓ Dead code detection
   ✓ Dependency analysis
   ✓ Complexity limits
   ✓ Modern Python patterns

🎉 All quality checks passed!
```

### 2. Run Quality Checks with Tests

```bash
# Quality checks + test suite
python -m crackerjack run --run-tests
```

**Expected Output**:

```
✅ Fast hooks completed in 4.8s
✅ Comprehensive hooks completed in 28.3s

🧪 Running tests...
✅ 324 tests passed in 12.5s
📊 Coverage: 75.3% (+2.1% from baseline)

🎉 Quality checks and tests passed!
```

### 3. AI Auto-Fixing (Recommended)

Let Crackerjack automatically fix quality issues:

```bash
# AI auto-fixing + tests
python -m crackerjack run --ai-fix --run-tests
```

**What It Does**:

1. Runs all quality checks
2. Collects all failures
3. AI analyzes each issue
4. Applies targeted fixes
5. Re-runs checks
6. Repeats until all pass (max 8 iterations)

**Expected Output**:

```
🚀 Starting AI auto-fixing...

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

### 4. Preview Fixes (Dry Run)

See what AI would fix without applying changes:

```bash
# Preview AI fixes
python -m crackerjack run --ai-fix --dry-run --run-tests
```

## Common Workflows

### Workflow 1: Development Cycle

**Typical development workflow**:

```bash
# 1. Make code changes
vim src/my_module.py

# 2. Run quality checks
python -m crackerjack run

# 3. If issues found, fix automatically
python -m crackerjack run --ai-fix

# 4. Run tests
python -m crackerjack run --run-tests

# 5. Commit and push
git add .
git commit -m "Add new feature"
git push
```

### Workflow 2: Pre-Commit Quality Gate

**Before committing code**:

```bash
# 1. Stage changes
git add .

# 2. Run quality checks
python -m crackerjack run --run-tests

# 3. If issues found, auto-fix
python -m crackerjack run --ai-fix --run-tests

# 4. Commit
git commit -m "Add feature"
```

### Workflow 3: CI/CD Pipeline

**In CI/CD (GitHub Actions, GitLab CI, etc.)**:

```yaml
# .github/workflows/quality.yml
name: Quality Checks

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install UV
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install Crackerjack
        run: uv tool install crackerjack

      - name: Run Quality Checks
        run: python -m crackerjack run --run-tests
```

### Workflow 4: Coverage Ratchet

**Track coverage improvements**:

```bash
# Check coverage status
python -m crackerjack run --coverage-status

# Run tests with ratchet
python -m crackerjack run --run-tests

# Expected: Coverage can only increase, never decrease
📈 Coverage improved from 70.0% to 72.5%!
🏆 Milestone achieved: 75% coverage! (+2.5% to next milestone)
```

### Workflow 5: Release Publishing

**Full release workflow**:

```bash
# 1. Ensure all checks pass
python -m crackerjack run --run-tests

# 2. Bump version and publish (patch release)
python -m crackerjack run --publish patch

# This will:
# - Bump version (e.g., 1.0.0 → 1.0.1)
# - Run quality checks
# - Run tests
# - Build package
# - Publish to PyPI
```

## Configuration

### Minimal Configuration (Zero Config)

Crackerjack works out of the box with sensible defaults:

```bash
# Just run it
python -m crackerjack run
```

**Default Settings**:
- **Fast hooks**: ~5 seconds (formatting, basic checks)
- **Comprehensive hooks**: ~30 seconds (type checking, security, complexity)
- **Quality tier**: Silver (standard for production code)
- **Coverage ratchet**: Enabled (continuous improvement)

### Quality Tier Configuration

**Choose quality tier based on project type**:

```bash
# Bronze (minimum acceptable)
python -m crackerjack run --quality-tier bronze

# Silver (standard, default)
python -m crackerjack run --quality-tier silver

# Gold (excellence)
python -m crackerjack run --quality-tier gold
```

**Tier Comparison**:

| Metric | Bronze | Silver | Gold |
|--------|--------|--------|------|
| Coverage | ≥50% | ≥80% | ≥95% |
| Complexity | ≤25 | ≤15 | ≤10 |
| Type Coverage | ≥30% | ≥60% | ≥80% |

### Coverage Goal Configuration

**Set explicit coverage goal**:

```bash
# Set coverage goal to 85%
python -m crackerjack run --coverage-goal 85.0 --run-tests

# Or disable ratchet temporarily
python -m crackerjack run --no-coverage-ratchet --run-tests
```

### AI Integration Configuration

**Enable AI auto-fixing**:

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run with AI
python -m crackerjack run --ai-fix --run-tests
```

**AI Configuration File** (`settings/adapters.yml`):

```yaml
# AI adapter configuration
ai: claude  # Use Claude AI

# Or specify model
ai:
  provider: claude
  model: claude-3-5-sonnet-20241022
  max_tokens: 8192
  temperature: 0.0  # Deterministic fixes
```

## Next Steps

### Learn More

- **Full Documentation**: See [README.md](../README.md) for comprehensive documentation
- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- **Migration Guide**: See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) if migrating from pre-commit
- **Quality Gates**: See [QUALITY_GATE_SETUP.md](QUALITY_GATE_SETUP.md) for CI/CD integration

### Advanced Features

**Explore advanced Crackerjack features**:

```bash
# MCP server (AI agent integration)
python -m crackerjack start

# Multi-project monitoring
python -m crackerjack run --monitor

# Enhanced monitoring with patterns
python -m crackerjack run --enhanced-monitor

# Service watchdog with auto-restart
python -m crackerjack run --watchdog

# Zuban LSP server (ultra-fast type checking)
python -m crackerjack run --start-zuban-lsp
```

### Customize Configuration

**Create custom configuration**:

```bash
# Edit pyproject.toml for tool settings
vim pyproject.toml

# Edit settings/mcp_settings.yml for MCP server
vim settings/mcp_settings.yml

# Edit settings/quality.yml for quality gates
vim settings/quality.yml
```

### Join the Community

- **GitHub**: [https://github.com/lesleslie/crackerjack](https://github.com/lesleslie/crackerjack)
- **Issues**: [Report bugs or request features](https://github.com/lesleslie/crackerjack/issues)
- **Discussions**: [Ask questions or share ideas](https://github.com/lesleslie/crackerjack/discussions)

## Troubleshooting

### Issue: "Python version too old"

**Solution**:

```bash
uv python install 3.13
uv python pin 3.13
```

### Issue: "Quality checks fail"

**Solution**:

```bash
# Run with AI auto-fixing
python -m crackerjack run --ai-fix

# Or skip hooks temporarily
python -m crackerjack run --skip-hooks --run-tests
```

### Issue: "Slow execution"

**Solution**:

```bash
# Run fast hooks only
python -m crackerjack run --fast

# Check cache stats
python -m crackerjack run --cache-stats
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more troubleshooting tips.

## Summary

**You've learned**:
- ✅ How to install Crackerjack
- ✅ How to run quality checks
- ✅ How to use AI auto-fixing
- ✅ Common development workflows
- ✅ Basic configuration

**Ready to go deeper?**
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Read [USER_GUIDE.md](USER_GUIDE.md) for comprehensive usage
- Read [AGENT_DEVELOPMENT.md](AGENT_DEVELOPMENT.md) for custom agents

**Quick Reference**:

```bash
# Quality checks only
python -m crackerjack run

# Quality + tests
python -m crackerjack run --run-tests

# AI auto-fixing + tests
python -m crackerjack run --ai-fix --run-tests

# Coverage status
python -m crackerjack run --coverage-status

# Help
python -m crackerjack run --help
```

---

**Last Updated**: 2025-02-06
**Crackerjack Version**: 0.51.0
