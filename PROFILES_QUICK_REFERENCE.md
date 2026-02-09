# Crackerjack Profiles - Quick Reference

## Three Profiles, Three Use Cases

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  QUICK (< 1 min)          STANDARD (2-5 min)     COMPREHENSIVE  │
│  ────────────────         ─────────────────      (10-15 min)   │
│                                                                 │
│  Use Case:                Use Case:             Use Case:        │
│  Active development       Pre-commit, push      CI/CD, release  │
│                                                                 │
│  Checks:                  Checks:               Checks:          │
│  ✓ Ruff linting           ✓ Ruff linting        ✓ Ruff all       │
│  ✗ Tests                  ✓ Tests (incremental) ✓ Tests (full)   │
│  ✗ Coverage               ✓ Coverage             ✓ Coverage       │
│  ✗ Security               ✗ Security             ✓ Security       │
│  ✗ Complexity             ✗ Complexity           ✓ Complexity     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Command Reference

### Basic Usage

```bash
# Run with standard profile (default)
crackerjack run

# Run with quick profile
crackerjack run --quick

# Run with comprehensive profile
crackerjack run --thorough

# Run with specific profile
crackerjack run --profile standard
```

### Profile Management

```bash
# List all profiles
crackerjack profile list

# Show profile details
crackerjack profile show standard

# Compare two profiles
crackerjack profile compare quick comprehensive
```

### Profile Override

```bash
# Use profile but override specific settings
crackerjack run --profile standard --no-coverage
crackerjack run --profile comprehensive --timeout 900
crackerjack run --quick --run-tests
```

## Decision Tree

```
Need to run checks?
 │
 ├─ Are you actively coding?
 │  └─ Yes → Use: crackerjack run --quick
 │
 ├─ Are you committing or pushing?
 │  └─ Yes → Use: crackerjack run
 │
 └─ Are you running CI/CD?
    └─ Yes → Use: crackerjack run --thorough
```

## Profile Comparison Table

| Setting | Quick | Standard | Comprehensive |
|---------|-------|----------|----------------|
| **Execution Time** | < 1 min | 2-5 min | 10-15 min |
| **Ruff Checks** | E, F | E, W, F, I, N, UP, B, C4, SIM | All rules |
| **Tests** | ✗ | ✓ (incremental) | ✓ (full) |
| **Coverage** | ✗ | ✓ (80%) | ✓ (80%) |
| **Security** | ✗ | ✗ | ✓ (bandit, safety) |
| **Complexity** | ✗ | ✗ | ✓ (max: 15) |
| **Parallel** | ✗ | ✓ (auto) | ✓ (auto) |
| **Timeout** | 60s | 300s | 600s |

## Quality Gates

| Gate | Quick | Standard | Comprehensive |
|------|-------|----------|----------------|
| Fail on Ruff errors | ✓ | ✓ | ✓ |
| Fail on test errors | ✗ | ✓ | ✓ |
| Fail on coverage | ✗ | ✓ | ✓ |
| Fail on complexity | ✗ | ✗ | ✓ |
| Fail on security | ✗ | ✗ | ✓ |

## Workflow Examples

### Development Workflow

```bash
# 1. Make changes
vim src/my_module.py

# 2. Quick check
crackerjack run --quick

# 3. Make more changes
vim src/my_module.py

# 4. Quick check again
crackerjack run --quick
```

### Pre-Commit Workflow

```bash
# 1. Finalize changes
vim src/my_module.py

# 2. Standard check
crackerjack run

# 3. If passes, commit
git add .
git commit -m "Add new feature"
```

### CI/CD Workflow

```yaml
# .github/workflows/ci.yml
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
      - run: crackerjack run --thorough
```

## Troubleshooting

### Too Slow?

```bash
# Use quick profile for faster feedback
crackerjack run --quick

# Reduce parallel workers
crackerjack run --test-workers 2
```

### Too Strict?

```bash
# Use quick profile (minimal checks)
crackerjack run --quick

# Or disable specific checks
crackerjack run --profile standard --no-coverage
```

### Need More Validation?

```bash
# Use comprehensive profile
crackerjack run --thorough

# Or extend timeout for slow tests
crackerjack run --profile comprehensive --timeout 900
```

## Further Reading

- **[Progressive Complexity Guide](docs/guides/progressive-complexity.md)** - Detailed guide
- **[QUICKSTART.md](QUICKSTART.md)** - Getting started
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Deep dive

---

**Quick Tips**:
- Use `--quick` during active development
- Use default (standard) before committing
- Use `--thorough` in CI/CD pipelines
- Override profile settings with CLI args
- List profiles with `crackerjack profile list`
