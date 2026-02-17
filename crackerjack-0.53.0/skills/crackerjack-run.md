______________________________________________________________________

## name: crackerjack-run description: Run crackerjack quality checks with AI-powered auto-fixing, intelligent session integration, and comprehensive workflow guidance

# Crackerjack Quality Workflow

Run crackerjack quality checks with AI-powered auto-fixing and intelligent session integration.

## 🎯 What This Does

This skill orchestrates a comprehensive quality enforcement workflow:

1. **Smart Execution Strategy**: Tries session-mgmt integration first, falls back to standard
1. **Pre-Execution Safety**: Checks for conflicts, verifies services, auto-starts if needed
1. **Iterative AI Fixing**: Up to 10 iterations of fast hooks → tests → comprehensive → AI fix
1. **Comprehensive Coverage**: Formatting, type checking, security, complexity, tests
1. **Zero Manual Intervention**: AI agents fix ALL issues automatically

## 📋 Before You Run

**Check system status:**

```bash
# Check for running jobs (prevents conflicts)
python -m crackerjack status

# Verify MCP server is running
python -m crackerjack health
```

**Current status questions:**

- Are there any active crackerjack jobs? (prevents file conflicts)
- Is this the first run or a follow-up iteration?
- Do you want debug output (immediate) or background execution?
- Are you working with tests or just quality hooks?

## 🚀 Interactive Workflow Selection

### Step 1: Choose Your Workflow

**What type of quality check do you need?**

1. **Daily Development** (Recommended for routine work)

   ```bash
   python -m crackerjack run -t --ai-fix
   ```

   - Fast hooks + tests + AI fixing
   - ~5-15 seconds for fast hooks
   - Tests run in parallel (3-4x faster)
   - Iterative fixing up to 10 cycles

1. **Full CI/CD Simulation** (Comprehensive, like production)

   ```bash
   python -m crackerjack run --all --run-tests -c
   ```

   - All quality gates including comprehensive hooks
   - Full test suite
   - Type checking, security scanning, complexity analysis
   - Slower but complete (30-60 seconds)

1. **Quick Format Check** (Fastest, no tests)

   ```bash
   python -m crackerjack run
   ```

   - Just fast hooks (formatting, basic linting)
   - ~5 seconds
   - Good for pre-commit checks

1. **Debug Mode** (Troubleshooting)

   ```bash
   python -m crackerjack run --ai-debug --run-tests
   ```

   - Shows detailed AI decision-making
   - Displays all analysis output
   - Helps understand why fixes succeed/fail

### Step 2: Session Integration Strategy

**How should execution be handled?**

**Automatic** (Recommended):

- Tries session-mgmt integration first (enhanced context)
- Falls back to standard crackerjack if unavailable
- Best of both worlds, no configuration needed

**Manual Override**:

```bash
# Force session-mgmt execution
await mcp.call_tool("session_mgmt_crackerjack_run", {})

# Force standard execution
python -m crackerjack run --ai-fix --run-tests
```

### Step 3: Performance Options

**Parallelization tuning:**

- [ ] **Auto-detect workers** (Default, recommended)

  - `test_workers: 0` in settings
  - 3-4x faster on 8-core systems
  - Safe memory limits (2GB per worker)

- [ ] **Explicit worker count**

  - `--test-workers 4` for 4 parallel workers
  - Good for consistent performance

- [ ] **Sequential execution** (Debugging)

  - `--test-workers 1` for single worker
  - Best for debugging flaky tests

- [ ] **Conservative parallelization**

  - `--test-workers -2` for half of CPU cores
  - Good for resource-constrained systems

**Phase parallelization:**

- [ ] **Enable parallel phases** (20-30% faster)
  - Tests and comprehensive hooks run concurrently
  - `--enable-parallel-phases` or `enable_parallel_phases: true`
  - Best for: Full CI/CD simulation

## 💡 Common Workflows

### Workflow 1: Daily Development Loop

**Best for**: Routine development, iterative work

```bash
# 1. Make your changes
# Edit files...

# 2. Run daily workflow
python -m crackerjack run -t --ai-fix

# 3. AI automatically fixes issues:
# Iteration 1: Formatting + imports
# Iteration 2: Type hints + tests
# Iteration 3: Final quality checks
# ...
# ✅ All hooks pass, all tests pass
```

**Timeline:**

- Fast hooks: ~5 seconds (with retry)
- Tests: ~15-20 seconds (parallel, 4 workers)
- AI fixing: ~10-30 seconds per iteration
- Total: 2-4 iterations typical (1-2 minutes)

### Workflow 2: Before Commit

**Best for**: Pre-commit quality gate

```bash
# Full quality check before committing
python -m crackerjack run --run-tests -c --ai-fix

# Includes:
# - Fast hooks (formatting, linting)
# - Full test suite
# - Comprehensive hooks (type checking, security, complexity)
# - AI fixing for all issues
```

**What gets checked:**

- ✅ Trailing whitespace, end-of-file fixer
- ✅ Ruff formatting and linting
- ✅ Gitleaks (secrets detection)
- ✅ All tests (collects ALL failures)
- ✅ Pyright type checking
- ✅ Bandit security scanning
- ✅ Vulture dead code detection
- ✅ Refurb modernization suggestions
- ✅ Creosote unused dependencies
- ✅ Complexipy complexity limits

### Workflow 3: CI/CD Simulation

**Best for**: Validating production readiness

```bash
# Full CI/CD workflow with maximum parallelization
python -m crackerjack run --all --run-tests -c --enable-parallel-phases

# Performance optimizations:
# - Tests run in parallel (4 workers on 8-core system)
# - Comprehensive hooks run parallel to tests
# - 20-30% faster than sequential execution
```

**Timeline (typical project):**

- Sequential: 90 seconds (60s tests + 30s comprehensive)
- Parallel: 60 seconds (max of 60s, 30s)
- **Speedup: 33% faster**

### Workflow 4: Debug Quality Issues

**Best for**: Understanding why fixes fail

```bash
# Debug mode with detailed output
python -m crackerjack run --ai-debug --run-tests

# Shows:
# - AI agent analysis for each issue
# - Fix strategies attempted
# - Why some fixes succeed/fail
# - Agent confidence scores
# - Iteration-by-iteration progress
```

**Use when:**

- AI fixing isn't working as expected
- Need to understand issue patterns
- Want to improve fix success rate
- Debugging specific quality failures

### Workflow 5: Maximum Performance

**Best for**: Large codebases, CI/CD optimization

```bash
# Ultimate parallelization
python -m crackerjack run \
  --enable-parallel-phases \
  --test-workers 4 \
  --run-tests \
  -c \
  --ai-fix

# Combines:
# - Tests run across 4 workers (pytest-xdist)
# - Comprehensive hooks run parallel to tests (phase parallelization)
# - AI fixing for all issues
# - Maximum throughput on multi-core systems
```

**Performance impact (8-core system):**

- Base (1 worker, sequential): ~90 seconds
- Test parallelization (4 workers): ~60 seconds
- Phase parallelization: ~60 seconds
- Both combined: ~45 seconds
- **Total speedup: 2x faster**

## 🔍 Understanding the Execution Cycle

### Iteration Structure (Up to 10 Cycles)

**Each iteration does:**

```
┌─────────────────────────────────────────┐
│ 1. Fast Hooks (~5s)                     │
│    - trailing-whitespace                │
│    - end-of-file-fixer                  │
│    - ruff-format                        │
│    - ruff-check                         │
│    - gitleaks                           │
│    └─→ If fail: Retry once             │
└─────────────────────────────────────────┘
              ↓ (pass or retried)
┌─────────────────────────────────────────┐
│ 2. Full Test Suite (collect ALL)        │
│    - Run ALL tests, don't stop first    │
│    - Gather complete failure list       │
│    - Parallel execution (auto-detect)   │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 3. Comprehensive Hooks (collect ALL)    │
│    - pyright (type checking)            │
│    - bandit (security)                  │
│    - vulture (dead code)                │
│    - refurb (modernization)             │
│    - creosote (unused deps)             │
│    - complexipy (complexity)            │
│    - Gather ALL failures                │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 4. AI Batch Fixing (ALL issues)         │
│    - Analyze tests + comprehensive      │
│    - Fix type errors                    │
│    - Fix security issues                │
│    - Remove dead code                   │
│    - Fix test failures                  │
│    - Apply refactoring                  │
│    - Fix all hook failures              │
└─────────────────────────────────────────┘
              ↓
    Repeat until ALL pass or max 10 iterations
```

### Why 10 Iterations?

**Typical convergence pattern:**

- Iteration 1-2: Fix formatting, imports, basic issues (~80% of issues)
- Iteration 3-4: Fix type hints, test failures (~15% of issues)
- Iteration 5+: Complex refactoring, edge cases (~5% of issues)

**Most projects converge in 2-4 iterations.**

## 🎨 Command Options Reference

### Essential Options

| Option | Short | Description | When to Use |
|--------|-------|-------------|-------------|
| `--run-tests` | `-t` | Run full test suite | Always (recommended) |
| `--ai-fix` | | Enable AI auto-fixing | Always (recommended) |
| `--comprehensive` | `-c` | Run comprehensive hooks | Before commits, CI/CD |
| `--all` | | All quality gates | Full CI/CD simulation |
| `--verbose` | `-v` | Show detailed output | Debugging |
| `--ai-debug` | `-x` | Debug AI decisions | Troubleshooting |

### Performance Options

| Option | Description | Default |
|--------|-------------|---------|
| `--test-workers N` | Set explicit worker count | 0 (auto-detect) |
| `--enable-parallel-phases` | Run tests + hooks in parallel | false |
| `--parallel-phases` | Short form | false |

### Debug Options

| Option | Description |
|--------|-------------|
| `--debug` | Run in foreground with visible output |
| `--ai-debug` | Show AI decision-making |
| `--strip-code` | Code cleaning mode |
| `--skip-hooks` | Skip hooks during iteration |

### Advanced Options

| Option | Description |
|--------|-------------|
| `--run-tests-only` | Only run tests, no hooks |
| `--comprehensive-only` | Only comprehensive hooks |
| `--fast-hooks-only` | Only fast hooks |
| `--ai-fix-once` | Single AI fixing pass |

## 📊 Progress Monitoring

**Real-time progress tracking:**

```bash
# In another terminal, monitor progress
python -m crackerjack status

# Shows:
# - Active job ID and status
# - Current iteration number
# - Current stage (fast_hooks/tests/comprehensive/ai_fix)
# - Error counts by type
# - Stage progress percentage
# - Overall progress percentage
```

**WebSocket monitoring** (if available):

- Real-time updates via localhost:8675
- Progress streaming to TUI monitor
- Web interface for visual monitoring

## ⚠️ Common Issues

### Issue: "Job already running"

**Cause**: Pre-execution check detected active job

**Solution**:

```bash
# Check existing jobs
python -m crackerjack status

# Wait for completion or force stop
kill <job_pid>

# Or run in different project directory
cd /path/to/other/project
python -m crackerjack run -t --ai-fix
```

### Issue: "Tests fail only in parallel"

**Cause**: Shared state, test interdependencies

**Solution**:

```bash
# Debug with sequential execution
python -m crackerjack run --test-workers 1 --run-tests

# Fix shared state issues
# - Use proper fixtures
# - Avoid singletons
# - Ensure test isolation
```

### Issue: "AI fixing not converging"

**Cause**: Complex issues requiring manual intervention

**Solution**:

```bash
# Run with debug output
python -m crackerjack run --ai-debug --run-tests

# Review AI analysis:
# - What agents are being used?
# - What fixes are attempted?
# - Why do they fail?

# Manual intervention for complex cases
```

### Issue: "Out of memory during parallel tests"

**Cause**: Too many workers for available memory

**Solution**:

```bash
# Reduce worker count
python -m crackerjack run --test-workers 2 --run-tests

# Or use fractional
python -m crackerjack run --test-workers -2 --run-tests

# Or disable auto-detection globally
export CRACKERJACK_DISABLE_AUTO_WORKERS=1
```

## 🎯 Best Practices

### DO ✅

- **Run before every commit**: `python -m crackerjack run -t --ai-fix`
- **Use parallel tests**: Default auto-detect is optimal
- **Enable parallel phases for CI/CD**: 20-30% faster
- **Monitor long-running jobs**: `python -m crackerjack status`
- **Review AI fixes**: Check what AI changed after first run

### DON'T ❌

- **Don't skip tests**: Always use `--run-tests` or `-t`
- **Don't ignore failing hooks**: AI will fix them automatically
- **Don't run multiple jobs concurrently**: Wait for completion
- **Don't use excessive workers**: Let auto-detect optimize
- **Don't disable AI fixing**: It's the whole point of crackerjack

## 📚 Related Skills

- `crackerjack-init` - Set up crackerjack for your project
- `session-checkpoint` - Mid-session quality verification
- `session-end` - End session with quality summary

## 🔗 Further Reading

- **Architecture**: `ARCHITECTURE.md` - Protocol-based design
- **Quality Framework**: `CLAUDE.md` - Fix Now vs Later decisions
- **AI Agents**: `docs/AI_FIX_EXPECTED_BEHAVIOR.md` - What gets auto-fixed
- **Testing**: `docs/features/PARALLEL_EXECUTION.md` - Test parallelization guide
