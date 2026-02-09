# Crackerjack Quickstart (5 minutes)

Crackerjack is the quality control and CI/CD automation tool for the ecosystem. It validates code quality, runs tests, and enforces development standards across all projects.

## Level 1: Basic Quality Checks (1 minute) ✅

Get started immediately with the most common quality checks.

### Installation

```bash
# Install from PyPI
pip install crackerjack

# Or install with development dependencies
pip install crackerjack[dev]

# Verify installation
crackerjack --version
```

### Run Quality Checks

```bash
# Run with default standard profile (recommended for most use cases)
crackerjack run

# Run with quick profile for fast feedback during development
crackerjack run --quick

# Run with comprehensive profile for full CI/CD validation
crackerjack run --thorough
```

### Understanding Profiles

Crackerjack uses **profiles** to provide progressive complexity:

| Profile | Time | Use Case | What Runs |
|---------|------|----------|-----------|
| **quick** | 1 min | Active development | Ruff linting only |
| **standard** | 2-5 min | Pre-commit, push | Ruff + tests + coverage |
| **comprehensive** | 10-15 min | CI/CD, release | All checks including security |

### Check Status

```bash
# View overall quality metrics
crackerjack status

# View execution history
crackerjack history

# View current configuration
crackerjack config show
```

### List Available Profiles

```bash
# List all profiles
crackerjack profile list

# Show profile details
crackerjack profile show standard

# Compare profiles
crackerjack profile compare quick comprehensive
```

## Level 2: CI/CD Integration (2 minutes) 🚀

Integrate Crackerjack into your CI/CD pipeline for automated quality checks.

### Initialize CI/CD Configuration

```bash
# Initialize GitHub Actions
crackerjack init-ci --platform github

# Initialize GitLab CI
crackerjack init-ci --platform gitlab

# Initialize generic CI
crackerjack init-ci --platform generic
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
crackerjack install-hooks

# Run pre-commit checks manually
crackerjack run --profile standard

# Uninstall hooks
crackerjack uninstall-hooks
```

### Quality Gates

```bash
# Run with default quality gates
crackerjack run

# Check if project passes quality gates
crackerjack check-gate

# View gate requirements
crackerjack gate show default
```

## Level 3: Custom Quality Gates (2 minutes) 🚦

Configure custom quality thresholds and checks for your project.

### Set Custom Thresholds

```bash
# Set coverage threshold
crackerjack config set coverage.min_coverage 80

# Set complexity threshold
crackerjack config set complexity.max_complexity 15

# Set multiple thresholds at once
crackerjack set-threshold --coverage 80 --complexity 15
```

### Add Custom Checks

```bash
# Add custom check
crackerjack add-check --name "security-scan" --command "bandit -r ."

# Add check with timeout
crackerjack add-check --name "integration-tests" --command "pytest tests/integration/" --timeout 300

# Add check with dependencies
crackerjack add-check --name "type-check" --command "mypy ." --depends "ruff"
```

### Create Custom Quality Gates

```bash
# Create new quality gate
crackerjack gate create strict --description "Strict quality requirements"

# Add checks to gate
crackerjack gate add-check strict --check ruff --check pytest --check bandit

# Set gate thresholds
crackerjack gate set-threshold strict --coverage 90 --complexity 10

# Use custom gate
crackerjack run --gate strict
```

## Configuration

Crackerjack uses a hierarchical configuration system:

1. **Profile defaults** (built-in: quick, standard, comprehensive)
1. **Default values** (sensible production defaults)
1. `crackerjack.toml` (project-level, committed)
1. `~/.crackerjack/config.toml` (user-level, local)
1. Environment variables (`CRACKERJACK_*`)
1. Command-line arguments (highest priority)

### Example Configuration

```toml
# crackerjack.toml
[profile]
name = "standard"  # quick, standard, or comprehensive

[testing]
enabled = true
coverage = true
coverage_threshold = 80
parallel = true
incremental = true

[quality_gates]
fail_on_test_errors = true
fail_on_coverage = true
coverage_threshold = 80
fail_on_complexity = false

[ruff]
select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "SIM"]
ignore = ["E502"]  # Line too long

[performance]
parallel_execution = true
cache_enabled = true
timeout = 300

[output]
verbose = false
show_progress = true
color = true
```

## AI Auto-Fix (Experimental)

Crackerjack can automatically fix some issues using AI:

```bash
# Run checks with AI-powered auto-fix
crackerjack run --ai-fix

# Auto-fix with specific provider
crackerjack run --ai-fix --provider openai
crackerjack run --ai-fix --provider anthropic

# Dry run to see what would be fixed
crackerjack run --ai-fix --dry-run
```

**Note**: AI auto-fix requires API keys and is experimental.

## MCP Integration

Crackerjack provides MCP server capabilities for integration with AI tools:

```bash
# Start MCP server
crackerjack mcp start

# Check MCP server status
crackerjack mcp status

# Run health probe
crackerjack mcp health

# Stop MCP server
crackerjack mcp stop
```

## Common Workflows

### Pre-Commit Workflow

```bash
# 1. Make code changes
vim src/my_module.py

# 2. Quick check while developing
crackerjack run --quick

# 3. Standard check before committing
crackerjack run

# 4. Commit if checks pass
git add .
git commit -m "Add new feature"
```

### Quick Fix Cycle

```bash
# 1. Run checks to find issues
crackerjack run

# 2. Auto-fix what's possible
crackerjack run --ai-fix

# 3. Verify fixes
crackerjack run

# 4. Check if ready for commit
crackerjack check-gate
```

### Continuous Monitoring

```bash
# Start background monitoring
crackerjack monitor start

# Check monitor status
crackerjack monitor status

# View monitor logs
crackerjack monitor logs

# Stop monitoring
crackerjack monitor stop
```

## Progressive Complexity

Crackerjack is designed for **progressive complexity** - start simple and add features as needed:

1. **Start with `--quick`**: Fast feedback during development (1 minute)
1. **Use `standard`**: Pre-commit and push validation (2-5 minutes)
1. **Use `--thorough`**: Full CI/CD pipeline (10-15 minutes)

For detailed guidance, see [docs/guides/progressive-complexity.md](docs/guides/progressive-complexity.md).

## Next Steps

- **[Progressive Complexity Guide](docs/guides/progressive-complexity.md)** - Detailed guide for choosing the right profile
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Deep dive into Crackerjack architecture
- **[docs/guides/](docs/guides/)** - Detailed guides for specific topics
- **[docs/reference/](docs/reference/)** - Complete reference documentation
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and updates

## Getting Help

```bash
# General help
crackerjack --help

# Command-specific help
crackerjack run --help
crackerjack profile --help

# Version info
crackerjack --version
```

## Troubleshooting

### Checks Failing

```bash
# Run with verbose output
crackerjack run --verbose

# Run specific check in isolation
crackerjack run --check pytest --verbose

# Check configuration
crackerjack config show
```

### Profile Not Found

```bash
# List available profiles
crackerjack profile list

# Show profile details
crackerjack profile show standard

# Compare profiles to understand differences
crackerjack profile compare quick standard
```

### Performance Issues

```bash
# Run with quick profile for faster feedback
crackerjack run --quick

# Reduce parallel workers
crackerjack run --test-workers 2

# Increase timeout
crackerjack run --timeout 600

# Run with performance profiling
crackerjack run --profile
```

### AI Fix Not Working

```bash
# Verify API keys
crackerjack config show ai_fix

# Test AI connection
crackerjack test-ai

# Check AI fix logs
crackerjack logs --filter ai-fix
```

## Quick Reference

| Command | Description |
|---------|-------------|
| `crackerjack run` | Run standard checks (default) |
| `crackerjack run --quick` | Run quick checks (1 minute) |
| `crackerjack run --thorough` | Run comprehensive checks (10-15 minutes) |
| `crackerjack run --profile <name>` | Run with specific profile |
| `crackerjack profile list` | List all profiles |
| `crackerjack profile show <name>` | Show profile details |
| `crackerjack status` | View quality metrics |
| `crackerjack history` | View execution history |
| `crackerjack config show` | View configuration |

______________________________________________________________________

**Ready to learn more?** See [docs/guides/progressive-complexity.md](docs/guides/progressive-complexity.md) for a detailed guide on progressive complexity.
