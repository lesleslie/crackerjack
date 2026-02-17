# Crackerjack Coverage Policy

**Last Updated:** 2025-11-14

## Current Status

| Metric | Value | Notes |
|--------|-------|-------|
| **Current Coverage** | 21.6% | As shown in README.md badge |
| **Baseline (Floor)** | 19.6% | Never reduce below this |
| **Tolerance** | ±2.0% | Temporary fluctuation allowance |
| **Target** | 100% | Ultimate goal via ratchet system |

## Coverage Ratchet System

### Philosophy

🎯 **Target: 100% Coverage** - Not an arbitrary number, but true comprehensive testing

📈 **Continuous Improvement** - Each test run can only maintain or improve coverage

🏆 **Milestone System** - Celebrate achievements at key percentages

🚫 **No Regression** - Once you achieve a coverage level, you can't go backward

### How It Works

1. **Baseline Protection**: Coverage cannot drop below 19.6% (current baseline)
1. **Tolerance Window**: ±2% fluctuation allowed for test infrastructure changes
1. **Milestone Progression**: Advance through milestones toward 100%
1. **Ratchet Effect**: Each milestone becomes the new minimum

### Milestones

| Milestone | Status | Next Steps |
|-----------|--------|------------|
| 15% | ✅ Achieved | Maintain |
| 20% | ✅ Achieved | Maintain |
| 25% | 🎯 Current Target | +3.4% needed |
| 42% | 📋 Future Milestone | +20.4% needed |
| 50% | 📋 Future Milestone | +28.4% needed |
| 75% | 📋 Future Milestone | +53.4% needed |
| 90% | 📋 Future Milestone | +68.4% needed |
| 100% | 🏆 Ultimate Goal | +78.4% needed |

## Configuration

### pyproject.toml Settings

```toml
[tool.coverage.run]
branch = false
source = ["crackerjack"]
parallel = true  # For pytest-xdist compatibility
concurrency = ["multiprocessing"]

[tool.coverage.report]
# No fail_under - using ratchet system instead
precision = 2
```

### Why No `fail_under` in Config?

The ratchet system is implemented in the test workflow itself, not as a static configuration value. This allows for:

- Dynamic baseline adjustments
- Milestone celebration
- Tolerance windows
- Progress tracking

## Usage

### Check Current Coverage

```bash
# Run tests with coverage
python -m crackerjack --run-tests

# Generate HTML coverage report
python -m crackerjack --coverage-report

# Check coverage status
python -m crackerjack --coverage-status
```

### Coverage Reports

```bash
# Terminal output with missing lines
python -m pytest --cov=crackerjack --cov-report=term-missing

# HTML report (browse .htmlcov/index.html)
python -m pytest --cov=crackerjack --cov-report=html

# JSON report for CI/CD
python -m pytest --cov=crackerjack --cov-report=json
```

### Improving Coverage

**Incremental Approach** (recommended):

- Target 2-5% improvement per development session
- Focus on low-hanging fruit (simple functions, error paths, edge cases)
- Write focused tests (each covers 1-3 lines)
- Time-box efforts (10-15 minutes maximum per session)

**What to Test:**

- ✅ Property getters and setters
- ✅ Simple validation logic
- ✅ Error handling paths
- ✅ String formatting and representations
- ✅ Configuration loading and defaults

**What to Skip (for now):**

- ❌ Complex async operations
- ❌ External integrations (unless mocked)
- ❌ Complex state management
- ❌ Tests that take >3 attempts to debug

## Historical Context

### Coverage Evolution

| Date | Coverage | Event |
|------|----------|-------|
| 2025-01 (baseline) | 19.6% | Baseline established with ratchet system |
| 2025-11-14 | 21.6% | Current status (+2.0% improvement) |

### Coverage by Layer (Approximate)

| Layer | Estimated Coverage | Priority |
|-------|-------------------|----------|
| CLI Handlers | ~40% | High (user-facing) |
| Adapters | ~30% | High (core functionality) |
| Services | ~25% | Medium |
| Orchestration | ~15% | Medium |
| Agents | ~10% | Low (legacy pattern) |
| Managers | ~20% | Medium |

## Frequently Asked Questions

### Why is the target 100%?

100% coverage doesn't mean perfect testing, but it means:

- All code paths are exercised at least once
- Dead code is identified and removed
- Edge cases are considered
- Documentation through examples

### What about the 42% reference?

The 42% mentioned in some docs (RULES.md, AGENTS.md) is a **milestone target**, not the current baseline. It represents:

- Approximately halfway to 100% coverage
- A significant quality achievement
- The next major milestone after 25%

### Can coverage temporarily drop?

Yes, within the ±2% tolerance window for:

- Test infrastructure changes
- Refactoring that temporarily breaks tests
- Major architectural changes

However, any drop must be:

- Temporary (fixed within 1-2 commits)
- Documented with reason
- Compensated in next improvement cycle

### What if I can't maintain the baseline?

If coverage drops below baseline:

1. Identify why (refactoring, removed tests, infrastructure)
1. Add focused tests to recover coverage
1. If baseline is truly too high, discuss with team
1. Never commit code that drops coverage without plan to recover

## References

- **Main README**: Coverage ratchet philosophy and milestones
- **CLAUDE.md**: Developer guidelines and current baseline (19.6%)
- **RULES.md**: Testing philosophy and 42% milestone target
- **AGENTS.md**: General testing guidelines

## Enforcement

### Pre-commit Checks

Coverage checks run as part of the test workflow:

```bash
python -m crackerjack --run-tests
```

### CI/CD Integration

Coverage is tracked in CI but not used as a hard gate. The ratchet system is advisory, allowing developers to see progress and regression without blocking merges.

### Manual Verification

```bash
# Before committing major changes
python -m crackerjack --coverage-status

# If below baseline, add tests before committing
python -m pytest --cov=crackerjack --cov-report=term-missing tests/
```

## Contact

For questions about coverage policy:

- Review this document first
- Check existing coverage reports
- Consult CLAUDE.md for developer guidelines
- Open GitHub issue for policy clarification
