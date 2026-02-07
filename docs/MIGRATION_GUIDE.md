# Migration Guide: Migrating to Crackerjack

This guide helps you migrate your project from basic quality checks or pre-commit hooks to Crackerjack's comprehensive quality enforcement platform.

## Table of Contents

- [Why Migrate to Crackerjack?](#why-migrate-to-crackerjack)
- [Migration Paths](#migration-paths)
  - [From Pre-commit](#from-pre-commit)
  - [From Basic Quality Tools](#from-basic-quality-tools)
  - [From No Quality Checks](#from-no-quality-checks)
- [Step-by-Step Migration](#step-by-step-migration)
- [Configuration Migration](#configuration-migration)
- [CI/CD Migration](#cicd-migration)
- [Troubleshooting](#troubleshooting)
- [Rollback Plan](#rollback-plan)

## Why Migrate to Crackerjack?

**Key Benefits**:

1. **Performance**: 47% faster than pre-commit due to direct Python API calls
2. **AI Integration**: 12 specialized AI agents for automatic error fixing
3. **Unified Workflow**: Quality checks + testing + publishing in one command
4. **Coverage Ratchet**: Revolutionary coverage system targeting 100%
5. **Zero Configuration**: 17 tools pre-configured with Python best practices

**Comparison with Pre-commit**:

| Feature | Pre-commit | Crackerjack |
|---------|-----------|-------------|
| **Performance** | Baseline | **47% faster** |
| **AI Integration** | ❌ No | ✅ 12 specialized agents |
| **Coverage Ratchet** | ❌ No | ✅ Targets 100% |
| **Publishing** | ❌ No | ✅ Built-in PyPI publishing |
| **Testing** | ❌ No | ✅ Built-in pytest integration |
| **Type Checking** | Via hooks | ✅ **Zuban (20-200x faster)** |

## Migration Paths

### From Pre-commit

**Pre-commit Configuration** (`.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
```

**Migration Steps**:

1. **Install Crackerjack**:

```bash
# Using UV (recommended)
uv tool install crackerjack

# Or using pip
pip install crackerjack
```

2. **Remove Pre-commit Configuration**:

```bash
# Uninstall pre-commit hooks
pre-commit uninstall

# Remove configuration file
rm .pre-commit-config.yaml

# Remove pre-commit from dependencies
uv remove pre-commit
```

3. **Initialize Crackerjack**:

```bash
# Auto-detect project and set up quality checks
python -m crackerjack run
```

4. **Verify Migration**:

```bash
# Run quality checks
python -m crackerjack run

# Expected output: All quality checks pass
```

**What Changed**:

- ✅ **Ruff formatting** → Crackerjack Ruff adapter (direct Python call, 47% faster)
- ✅ **Black formatting** → Crackerjack Ruff adapter (unified formatting)
- ✅ **Flake8 linting** → Crackerjack Ruff adapter (faster, more features)
- ✅ **Bandit security** → Crackerjack Bandit adapter (direct Python call)

**Benefits**:

- ⚡ **47% faster**: Direct Python API instead of subprocess overhead
- 🤖 **AI integration**: Automatic error fixing with specialized agents
- 🎯 **Coverage ratchet**: Continuous improvement toward 100% coverage
- 📦 **All-in-one**: Quality + tests + publishing in one command

### From Basic Quality Tools

**Existing Setup** (multiple tools configured separately):

```bash
# Format code
black .
ruff format .

# Lint code
flake8 .
pylint src/

# Type check
mypy src/

# Security scan
bandit -r src/

# Run tests
pytest
```

**Migration Steps**:

1. **Install Crackerjack**:

```bash
uv tool install crackerjack
```

2. **Uninstall Individual Tools** (optional, Crackerjack includes them):

```bash
uv remove black ruff flake8 pylint mypy bandit
```

3. **Run Crackerjack**:

```bash
# Replace all above commands with one
python -m crackerjack run

# With tests
python -m crackerjack run --run-tests
```

4. **Update CI/CD** (see [CI/CD Migration](#cicd-migration))

**What Changed**:

- ✅ **5 separate commands** → **1 unified command**
- ✅ **Manual configuration** → **Zero configuration (pre-configured)**
- ✅ **No AI integration** → **AI auto-fixing available**

### From No Quality Checks

**Starting from Scratch**:

```bash
# Navigate to your project
cd your-project

# Install Crackerjack
uv tool install crackerjack

# Initialize project with quality checks
python -m crackerjack run

# Expected output: Quality checks run, any issues are reported
```

**What You Get**:

- ✅ **17 quality tools** pre-configured (formatting, linting, security, type checking, etc.)
- ✅ **Zero configuration**: Just run `python -m crackerjack run`
- ✅ **Best practices**: All tools configured with Python community standards

## Step-by-Step Migration

### Phase 1: Preparation (5 minutes)

1. **Create Backup**:

```bash
# Create a git commit before migration
git add .
git commit -m "Backup: Before Crackerjack migration"

# Or create a branch
git checkout -b backup-before-crackerjack
```

2. **Check Python Version**:

```bash
# Crackerjack requires Python 3.13+
python --version

# If not 3.13+, install it
uv python install 3.13
uv python pin 3.13
```

3. **Install UV Package Manager** (if not installed):

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### Phase 2: Installation (2 minutes)

1. **Install Crackerjack**:

```bash
# Using UV (recommended)
uv tool install crackerjack

# Or using pip
pip install crackerjack

# Or add as project dependency
uv add crackerjack --dev
```

2. **Verify Installation**:

```bash
python -m crackerjack --version
# Expected output: Crackerjack 0.51.0
```

### Phase 3: Initial Run (3 minutes)

1. **Run Quality Checks**:

```bash
python -m crackerjack run
```

2. **Review Output**:

```
✅ Fast hooks completed in 4.8s
✅ Comprehensive hooks completed in 28.3s
✅ All quality checks passed!
```

3. **If Issues Found**:

```bash
# Run with AI auto-fixing (recommended)
python -m crackerjack run --ai-fix --run-tests

# Or run with verbose output to see details
python -m crackerjack run --verbose
```

### Phase 4: Configuration (5 minutes)

1. **Review Auto-Generated Configuration**:

```bash
# Check if configuration was created
cat settings/mcp_settings.yml
cat pyproject.toml  # Crackerjack tool configuration
```

2. **Customize Thresholds** (optional):

```bash
# Edit quality tiers
python -m crackerjack run --quality-tier bronze  # Start with bronze
python -m crackerjack run --quality-tier silver  # Standard (default)
python -m crackerjack run --quality-tier gold    # Excellence
```

3. **Set Coverage Ratchet** (optional):

```bash
# Check current coverage
python -m crackerjack run --coverage-status

# Set coverage goal (default: continuous improvement)
python -m crackerjack run --coverage-goal 80.0
```

### Phase 5: CI/CD Integration (10 minutes)

See [CI/CD Migration](#cicd-migration) for detailed instructions.

### Phase 6: Team Adoption (ongoing)

1. **Update Documentation**:

```markdown
# CONTRIBUTING.md

## Quality Checks

We use [Crackerjack](https://github.com/lesleslie/crackerjack) for quality enforcement.

### Running Quality Checks

```bash
# Quality checks only
python -m crackerjack run

# Quality checks + tests
python -m crackerjack run --run-tests

# AI auto-fixing
python -m crackerjack run --ai-fix --run-tests
```

### Pre-Commit

We no longer use pre-commit. Quality checks are run via Crackerjack before pushing.
```

2. **Train Team**:

```bash
# Quick demo
python -m crackerjack run --help

# Show AI capabilities
python -m crackerjack run --ai-fix --dry-run --run-tests
```

3. **Monitor Adoption**:

```bash
# Check quality metrics over time
python -m crackerjack run --coverage-status
python -m crackerjack run --cache-stats
```

## Configuration Migration

### From Pre-commit Config to Crackerjack

**Pre-commit Config** (`.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--extend-select, I, --fix]
      - id: ruff-format

  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        args: [--line-length=88]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: [-c, pyproject.toml]
```

**Crackerjack Config** (auto-generated in `pyproject.toml`):

```toml
[tool.ruff]
target-version = "py313"
line-length = 88

[tool.ruff.lint]
extend-select = ["I"]  # Import sorting

[tool.bandit]
skips = ["B101", "B607"]  # Skip specific checks
```

**Key Changes**:

- ✅ **Repo URLs** → Not needed (direct Python API)
- ✅ **Hook IDs** → Not needed (adapters auto-registered)
- ✅ **Rev versions** → Managed by UV dependency management
- ✅ **Args** → Migrated to `pyproject.toml` tool sections

### Environment Variables

**Pre-commit**:

```bash
export PRE_COMMIT_HOME=/path/to/cache
```

**Crackerjack**:

```bash
# No environment variables needed for basic usage
# Advanced: MCP server configuration
export CRACKERJACK_MCP_HOST="127.0.0.1"
export CRACKERJACK_MCP_PORT=8676

# AI integration
export ANTHROPIC_API_KEY=sk-ant-...
```

## CI/CD Migration

### GitHub Actions

**Before** (Pre-commit):

```yaml
name: Quality Checks

on: [push, pull_request]

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - uses: pre-commit/action@v3.0.0
```

**After** (Crackerjack):

```yaml
name: Quality Checks

on: [push, pull_request]

jobs:
  crackerjack:
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

      - name: Upload Coverage Reports
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: coverage-reports
          path: htmlcov/
```

### GitLab CI

**Before** (Pre-commit):

```yaml
quality:
  script:
    - pip install pre-commit
    - pre-commit run --all-files
```

**After** (Crackerjack):

```yaml
quality:
  script:
    - pip install uv
    - uv tool install crackerjack
    - python -m crackerjack run --run-tests
  coverage: '/(?i)lines.*\s+(\d+\.\d+)%/'
  artifacts:
    paths:
      - htmlcov/
```

### Jenkins

**Before** (Pre-commit):

```groovy
stage('Quality') {
    steps {
        sh 'pre-commit run --all-files'
    }
}
```

**After** (Crackerjack):

```groovy
stage('Quality') {
    steps {
        sh 'uv tool install crackerjack || true'
        sh 'python -m crackerjack run --run-tests'
    }
    post {
        always {
            publishHTML(target: [
                reportDir: 'htmlcov',
                reportFiles: 'index.html',
                reportName: 'Coverage Report'
            ])
        }
    }
}
```

## Troubleshooting

### Issue: "Python version too old"

**Error**:

```
ERROR: Crackerjack requires Python 3.13+
```

**Solution**:

```bash
# Install Python 3.13
uv python install 3.13

# Pin to Python 3.13
uv python pin 3.13

# Verify
python --version
# Expected output: Python 3.13.x
```

### Issue: "Quality checks fail after migration"

**Error**:

```
❌ Ruff formatting issues found
❌ Type checking errors found
```

**Solution**:

```bash
# Run with AI auto-fixing
python -m crackerjack run --ai-fix --run-tests

# Or run with dry-run to preview fixes
python -m crackerjack run --ai-fix --dry-run --run-tests

# Or skip quality checks temporarily
python -m crackerjack run --skip-hooks --run-tests
```

### Issue: "Coverage decreased after migration"

**Error**:

```
❌ Coverage regressed from 75.0% to 70.0%
```

**Solution**:

```bash
# Check coverage status
python -m crackerjack run --coverage-status

# Temporarily disable ratchet
python -m crackerjack run --no-coverage-ratchet --run-tests

# Or set explicit lower goal
python -m crackerjack run --coverage-goal 70.0 --run-tests
```

### Issue: "Pre-commit hooks still running"

**Symptom**: Pre-commit hooks run even after uninstalling.

**Solution**:

```bash
# Uninstall hooks
pre-commit uninstall --all

# Remove hook files
rm .git/hooks/pre-commit
rm .git/hooks/pre-push

# Verify
ls .git/hooks/ | grep pre-commit
# Expected: No output
```

### Issue: "Performance slower than expected"

**Symptom**: Crackerjack takes longer than pre-commit.

**Solution**:

```bash
# Check cache hit rate
python -m crackerjack run --cache-stats

# Expected: 70%+ cache hit rate

# Clear cache if corrupted
python -m crackerjack run --clear-cache

# Run fast hooks only
python -m crackerjack run --fast
```

## Rollback Plan

If migration fails, you can rollback to pre-commit:

### Step 1: Restore Backup

```bash
# Restore git commit
git revert HEAD

# Or checkout backup branch
git checkout backup-before-crackerjack
```

### Step 2: Reinstall Pre-commit

```bash
# Install pre-commit
uv add pre-commit --dev

# Restore .pre-commit-config.yaml from backup
git checkout backup-before-crackerjack -- .pre-commit-config.yaml

# Install hooks
pre-commit install
```

### Step 3: Verify Rollback

```bash
# Run pre-commit
pre-commit run --all-files

# Expected: Pre-commit hooks run successfully
```

### Step 4: Uninstall Crackerjack (Optional)

```bash
# Remove from dependencies
uv remove crackerjack

# Or remove tool installation
uv tool uninstall crackerjack
```

## Migration Checklist

Use this checklist to ensure complete migration:

- [ ] Backup current state (git commit or branch)
- [ ] Verify Python 3.13+ is installed
- [ ] Install UV package manager
- [ ] Install Crackerjack
- [ ] Run initial quality checks (`python -m crackerjack run`)
- [ ] Fix any quality issues (with or without AI)
- [ ] Update CI/CD configuration
- [ ] Update team documentation
- [ ] Train team on Crickerjack usage
- [ ] Monitor quality metrics for 1 week
- [ ] Remove pre-commit configuration (after successful migration)
- [ ] Archive old quality tool configurations

## Next Steps

After successful migration:

1. **Enable AI Integration**:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m crackerjack run --ai-fix --run-tests
```

2. **Set Quality Tier**:

```bash
# Start with bronze, aim for gold
python -m crackerjack run --quality-tier silver
```

3. **Configure MCP Server** (optional):

```bash
python -m crackerjack start
```

4. **Explore Advanced Features**:

```bash
# Coverage ratchet
python -m crackerjack run --coverage-status

# Performance monitoring
python -m crackerjack run --monitor

# Enhanced monitoring with patterns
python -m crackerjack run --enhanced-monitor
```

## Support

- **Documentation**: [Crackerjack Documentation](https://github.com/lesleslie/crackerjack)
- **Issues**: [GitHub Issues](https://github.com/lesleslie/crackerjack/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lesleslie/crackerjack/discussions)

## Summary

**Migration Time**: 30-60 minutes for most projects

**Benefits**:
- ⚡ 47% faster quality checks
- 🤖 AI-powered error fixing
- 🎯 Coverage ratchet toward 100%
- 📦 Unified workflow (quality + tests + publishing)

**Risk**: Low (can rollback easily with git)

**Recommendation**: Migrate during a quiet period, monitor for 1 week, then remove pre-commit configuration.

---

**Last Updated**: 2025-02-06
**Crackerjack Version**: 0.51.0
