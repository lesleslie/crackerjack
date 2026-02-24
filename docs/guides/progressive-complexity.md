# Progressive Complexity Guide

This guide helps you use Crackerjack effectively by starting simple and progressively adding complexity as needed.

## Philosophy

Crackerjack can do **a lot** - but you don't need to learn everything at once. This guide introduces features incrementally, based on your needs:

- **Level 1**: Quick feedback during development (1 minute)
- **Level 2**: Standard checks for pre-commit (2-5 minutes)
- **Level 3**: Comprehensive checks for CI/CD (10-15 minutes)

______________________________________________________________________

## Level 1: Quick Development Feedback (1 minute) ⚡

**Goal**: Get fast feedback while coding without waiting for full test runs.

### When to Use

- Active development phase
- Frequent code changes
- Rapid iteration cycles
- Local development machine

### What Runs

- **Ruff linting** (5-10 seconds)
  - Error detection
  - Basic style checks
  - Import sorting

### What Doesn't Run

- Tests (too slow for rapid iteration)
- Coverage tracking
- Security scanning
- Type checking

### Usage

```bash
# Use the quick profile
crackerjack run --profile quick

# Or use the shortcut
crackerjack run --quick
```

### Example Output

```
Crackerjack v1.0.0

Running checks with profile: quick

✓ Ruff linting (8 seconds)

All checks passed!
```

### Next Steps

Once you're ready to commit or push, move to **Level 2**.

______________________________________________________________________

## Level 2: Standard Pre-Commit Checks (2-5 minutes) ✅

**Goal**: Validate code quality before committing or pushing.

### When to Use

- Pre-commit hooks
- Before pushing to remote
- Pull request validation
- Standard CI/CD pipeline

### What Runs

- **Ruff linting** (5-10 seconds)
- **Unit tests** (1-2 minutes)
  - Incremental (only changed files)
  - Parallel execution
- **Coverage tracking** (30 seconds)
  - 80% minimum threshold

### What Doesn't Run

- Full test suite (use incremental)
- Security scanning (optional)
- Type checking (optional)

### Usage

```bash
# Use the standard profile (default)
crackerjack run

# Or explicitly specify
crackerjack run --profile standard
```

### Example Output

```
Crackerjack v1.0.0

Running checks with profile: standard

✓ Ruff linting (8 seconds)
✓ Unit tests (95 seconds) - 234 tests passed
✓ Coverage (42 seconds) - 87% coverage

All checks passed!
```

### Configuration

Create `crackerjack.toml` in your project root:

```toml
[profile]
name = "standard"

[testing]
incremental = true
parallel = true
coverage_threshold = 80

[quality_gates]
fail_on_test_errors = true
fail_on_coverage = true
```

### Next Steps

For full CI/CD or release preparation, move to **Level 3**.

______________________________________________________________________

## Level 3: Comprehensive CI/CD Pipeline (10-15 minutes) 🔍

**Goal**: Complete quality validation for production code.

### When to Use

- Full CI/CD pipeline
- Pre-merge validation
- Release preparation
- Security audits

### What Runs

- **Ruff linting** (5-10 seconds)
  - All rules enabled
- **Full test suite** (3-5 minutes)
  - All tests (not incremental)
  - Parallel execution
  - Performance benchmarks (optional)
- **Coverage analysis** (1 minute)
  - HTML report generation
  - 80% minimum threshold
- **Security scanning** (2-3 minutes)
  - Bandit (static analysis)
  - Safety (dependencies)
- **Type checking** (1-2 minutes, optional)
- **Complexity analysis** (30 seconds)

### Usage

```bash
# Use the comprehensive profile
crackerjack run --profile comprehensive

# Or use the shortcut
crackerjack run --thorough
```

### Example Output

```
Crackerjack v1.0.0

Running checks with profile: comprehensive

✓ Ruff linting (10 seconds)
✓ Full test suite (287 seconds) - 1,247 tests passed
✓ Coverage (58 seconds) - 91% coverage
✓ Bandit security scan (143 seconds) - 0 issues found
✓ Safety dependency check (67 seconds) - 0 vulnerabilities
✓ Complexity analysis (28 seconds) - Average complexity: 6.2

All checks passed!
```

### Configuration

Create `crackerjack.toml` in your project root:

```toml
[profile]
name = "comprehensive"

[testing]
incremental = false  # Run full suite
parallel = true
coverage_threshold = 80
benchmark = true  # Optional

[quality_gates]
fail_on_test_errors = true
fail_on_coverage = true
fail_on_complexity = true
max_complexity = 15
fail_on_security = true

[security]
enabled = true
tools = ["bandit", "safety"]

[complexity]
enabled = true
max_complexity = 15
max_function_length = 50
```

### CI/CD Integration

**GitHub Actions** (`.github/workflows/ci.yml`):

```yaml
name: CI

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install crackerjack
      - run: crackerjack run --profile comprehensive
```

**GitLab CI** (`.gitlab-ci.yml`):

```yaml
quality:
  script:
    - pip install crackerjack
    - crackerjack run --profile comprehensive
```

______________________________________________________________________

## Choosing the Right Profile

Use this decision tree to choose the right profile:

```
Start
 │
 ├─ Are you actively coding and need fast feedback?
 │  └─ Yes → Use **quick** (1 minute)
 │
 ├─ Are you committing or pushing code?
 │  └─ Yes → Use **standard** (2-5 minutes)
 │
 └─ Are you running CI/CD or preparing a release?
    └─ Yes → Use **comprehensive** (10-15 minutes)
```

### Quick Reference

| Situation | Profile | Time | Command |
|-----------|---------|------|---------|
| Active development | quick | 1 min | `crackerjack run --quick` |
| Pre-commit / push | standard | 2-5 min | `crackerjack run` |
| CI/CD pipeline | comprehensive | 10-15 min | `crackerjack run --thorough` |

______________________________________________________________________

## Customizing Profiles

You can customize any profile by overriding specific settings:

```bash
# Use standard profile but with coverage disabled
crackerjack run --profile standard --no-coverage

# Use comprehensive profile but skip security checks
crackerjack run --profile thorough --no-security

# Use quick profile but run tests
crackerjack run --quick --run-tests
```

### Creating Custom Profiles

Create a custom profile file in `settings/profiles/`:

```yaml
# settings/profiles/custom.yaml
profile:
  name: "custom"
  description: "My custom profile"
  execution_time: "5 minutes"

checks:
  enabled:
    - ruff
    - pytest
  disabled:
    - coverage

testing:
  enabled: true
  coverage: false
  parallel: true

quality_gates:
  fail_on_test_errors: true
  fail_on_coverage: false
```

Then use it:

```bash
crackerjack run --profile custom
```

______________________________________________________________________

## Progressive Workflow Example

Here's a typical workflow using progressive complexity:

### 1. Development Phase

```bash
# Make code changes
vim src/my_module.py

# Quick check while coding
crackerjack run --quick

# Make more changes
vim src/my_module.py

# Quick check again
crackerjack run --quick
```

### 2. Commit Phase

```bash
# Ready to commit - run standard checks
crackerjack run

# If all checks pass, commit
git add .
git commit -m "Add new feature"
```

### 3. Push Phase

```bash
# Before pushing, run standard checks again
crackerjack run

# Push to remote
git push origin feature-branch
```

### 4. CI/CD Phase

```yaml
# CI automatically runs comprehensive checks
# No manual action needed
```

______________________________________________________________________

## Tips for Each Level

### Level 1 Tips

- Run frequently during development
- Use in conjunction with your editor's linting
- Don't worry about coverage yet
- Focus on error detection

### Level 2 Tips

- Set up as a pre-commit hook
- Use incremental tests for speed
- Monitor coverage trends over time
- Fix issues before committing

### Level 3 Tips

- Run in CI/CD, not locally (usually)
- Review coverage reports
- Address security issues promptly
- Monitor complexity trends

______________________________________________________________________

## Troubleshooting

### Quick Profile Too Strict

If the quick profile is catching too many issues:

1. Fix the errors (recommended)
1. Or temporarily use specific checks:

```bash
crackerjack run --check ruff --select E,F
```

### Standard Profile Too Slow

If the standard profile is taking too long:

1. Check if tests are inefficient
1. Use incremental testing (default for standard)
1. Reduce parallel workers if machine is overloaded:

```bash
crackerjack run --profile standard --test-workers 2
```

### Comprehensive Profile Timing Out

If the comprehensive profile is timing out:

1. Increase timeout:

```bash
crackerjack run --profile comprehensive --timeout 900
```

2. Or split checks into stages:

```bash
# Stage 1: Quick + tests
crackerjack run --profile standard

# Stage 2: Security + complexity
crackerjack run --check bandit --check complexipy
```

______________________________________________________________________

## Next Steps

- **[QUICKSTART.md](../../QUICKSTART.md)** - Basic usage guide
- **[docs/reference/](../reference/)** - Complete reference documentation

______________________________________________________________________

**Need help?** Use `crackerjack profile list` to see available profiles.
