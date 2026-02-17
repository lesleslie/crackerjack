______________________________________________________________________

## name: session-checkpoint description: Mid-session quality checkpoint with workflow analysis, bottleneck detection, and optimization recommendations

# Session Checkpoint

Perform mid-session quality checkpoint with comprehensive workflow analysis and optimization.

## 🎯 What This Does

This skill provides a mid-session pause point to:

1. **Quality Verification**: Run quality checks via crackerjack
1. **Workflow Analysis**: Detect bottlenecks and inefficiencies
1. **Progress Tracking**: Measure session progress and achievements
1. **Optimization**: Provide recommendations for workflow improvement
1. **Memory Capture**: Store key insights for future sessions

## 📋 When to Checkpoint

**Ideal timing for checkpoints:**

- **After feature completion**: Before moving to next task
- **Before commit**: Ensure quality standards met
- **Session midpoint**: Halfway through planned work
- **When stuck**: Get fresh perspective on issues
- **Before context switch**: Preserving current work state

**Signs you need a checkpoint:**

- Code has changed significantly
- Tests are failing or quality degraded
- Feeling stuck or uncertain
- About to switch tasks
- Session has been running >1 hour

## 🚀 Interactive Checkpoint Workflow

### Step 1: Checkpoint Type Selection

**What type of checkpoint do you need?**

1. **Quick Quality Check** (Fast, 30-60 seconds)

   - Fast hooks only (formatting, linting)
   - Test count verification
   - Quick quality snapshot
   - Good for: Frequent checkpoints

1. **Comprehensive Checkpoint** (Thorough, 2-5 minutes)

   - Full quality workflow (fast hooks + tests + comprehensive)
   - Workflow analysis
   - Bottleneck detection
   - Recommendations
   - Good for: Feature completion, before commits

1. **Deep Analysis** (Complete, 5-10 minutes)

   - Everything in comprehensive
   - Session metrics analysis
   - Quality trends
   - Memory consolidation
   - Good for: Session midpoint, major milestones

1. **Custom Checkpoint** (Choose specific checks)

   - Select which analyses to run
   - Focus on specific concerns
   - Flexible configuration

### Step 2: Quality Verification

**What quality checks should run?**

**Essential Checks** (Recommended):

- [ ] **Fast Hooks** - Formatting, linting, basic checks (~5s)
- [ ] **Test Verification** - Run test suite, verify all pass
- [ ] **Coverage Check** - Ensure coverage not decreased

**Comprehensive Checks** (Before commits):

- [ ] **Type Checking** - Pyright static analysis
- [ ] **Security Scan** - Bandit vulnerability detection
- [ ] **Dead Code** - Vulture unused code detection
- [ ] **Complexity** - Complexipy complexity limits
- [ ] **Modernization** - Refurb improvement suggestions

**Optional Analyses**:

- [ ] **Workflow Analysis** - Detect bottlenecks
- [ ] **Session Metrics** - Track productivity patterns
- [ ] **Quality Trends** - Coverage and test trends
- [ ] **Memory Consolidation** - Store insights for future

### Step 3: Workflow Analysis

**What aspects should be analyzed?**

**Productivity:**

- [ ] **Task Completion** - What's been accomplished
- [ ] **Time Distribution** - How time was spent
- [ ] **Velocity** - Tasks per hour
- [ ] **Blockers** - What slowed progress

**Code Quality:**

- [ ] **Coverage Changes** - Did coverage increase/decrease
- [ ] **Test Health** - New tests, test failures
- [ ] **Complexity** - New complexity issues
- [ ] **Technical Debt** - Accumulating issues

**Workflow Patterns:**

- [ ] **Bottleneck Detection** - Where time is wasted
- [ ] **Error Patterns** - Recurring issues
- [ ] **Tool Usage** - Which tools are used most
- [ ] **Efficiency** - Optimization opportunities

## 💡 Common Checkpoint Workflows

### Workflow 1: Quick Quality Verification

**Best for**: Frequent checkpoints, fast feedback

```bash
# Run quick quality checkpoint

Session Checkpoint: Quick Quality Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Running fast hooks...
✓ trailing-whitespace: PASS
✓ end-of-file-fixer: PASS
✓ ruff-format: PASS
✓ ruff-check: PASS
✓ gitleaks: PASS

Test verification...
✓ 42 tests passing
✓ Coverage: 47% (↑5% from last checkpoint)

Quality Snapshot:
  Status: ✅ All checks passing
  Coverage: 47% (+5%)
  Tests: 42 passing
  Complexity: No new issues

⏱️  Duration: 45 seconds

💡 No immediate actions needed.
   Continue with current work.
```

**Timeline**: 30-60 seconds

### Workflow 2: Comprehensive Feature Completion

**Best for**: Before commits, feature completion

```bash
# Full comprehensive checkpoint

Session Checkpoint: Comprehensive Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Quality Verification:
┌──────────────────────────────────┐
│ Fast Hooks        │ ✅ PASS (5s) │
│ Test Suite        │ ✅ PASS (18s)│
│ Type Checking      │ ✅ PASS (12s)│
│ Security Scan      │ ✅ PASS (8s) │
│ Dead Code          │ ✅ PASS (6s) │
│ Complexity         │ ✅ PASS (4s) │
└──────────────────────────────────┘

All quality checks passing!

Workflow Analysis:
┌──────────────────────────────────────┐
│ Session Duration    │ 2 hours 15 min  │
│ Tasks Completed     │ 3 features      │
│ Files Modified      │ 12 files        │
│ Tests Added         │ 15 new tests    │
│ Coverage Change     │ 42% → 47% (+5%) │
└──────────────────────────────────────┘

Bottleneck Detection:
✅ No significant bottlenecks detected
✅ Clean workflow patterns
✅ Optimal tool usage

Recommendations:
💡 Ready for commit - all checks passing
💡 Consider adding integration tests for auth module
💡 Documentation: Update API docs for new endpoints

Quality Trends:
  Coverage: Steady increase (42% → 47%)
  Tests: +15 this session
  Complexity: Stable (no new violations)

⏱️  Duration: 3 minutes 45 seconds

💡 Excellent progress! Quality improving steadily.
   Ready to commit or continue work.
```

**Timeline**: 2-5 minutes

### Workflow 3: Deep Session Analysis

**Best for**: Session midpoint, major milestones, understanding patterns

```bash
# Deep analysis with memory consolidation

Session Checkpoint: Deep Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Quality verification passes - see comprehensive output]

Session Metrics Analysis:
┌─────────────────────────────────────────┐
│ Total Session Time    │ 3 hours 20 min  │
│ Active Coding Time    │ 2 hours 45 min  │
│ Quality Check Time    │ 25 minutes      │
│ Planning/Research     │ 10 minutes      │
│                      │                 │
│ Tasks Completed       │ 5 features      │
│ Bugs Fixed            │ 2 bugs          │
│ Tests Added           │ 28 tests        │
│ Docs Updated          │ 3 files         │
│                      │                 │
│ Files Modified        │ 18 files        │
│ Lines Added           │ +847 lines      │
│ Lines Removed         │ -312 lines      │
│ Net Change            │ +535 lines      │
└─────────────────────────────────────────┘

Quality Trend Analysis:
Coverage:
  Session Start: 42%
  Current:       49%
  Change:        +7% ✅ Excellent progress

Test Health:
  Start:  34 tests
  Current: 62 tests
  Added:  28 new tests ✅

Complexity:
  Violations: 0
  Trend: Stable
  Status: Healthy

Productivity Analysis:
Velocity: 1.5 tasks/hour
Trend:  Above average
Rating: ⭐⭐⭐⭐☆ (4/5)

Workflow Efficiency:
Optimal tool usage detected
✓ Efficient use of crackerjack
✓ Good test-first approach
✓ Regular quality checkpoints

Bottleneck Detection:
⚠️  Minor bottleneck identified
   - Issue: Frequent context switching between tasks
   - Impact: ~10% overhead
   - Recommendation: Group related tasks together

Error Patterns:
No recurring errors detected
Clean error handling patterns

Memory Consolidation:
Stored 5 insights for future sessions:
1. "Test-driven approach reduces iteration count by 40%"
2. "Complexity checks catch design issues early"
3. "Fast hooks retry fixes 90% of formatting issues"
4. "Parallel tests 3x faster on this codebase"
5. "Context switching overhead measurable in metrics"

Recommendations:
💡 Continue current workflow - very effective
💡 Address context switching bottleneck for 10% gain
💡 Add integration tests for API endpoints
💡 Consider increasing coverage target to 55%

Action Items:
1. Group related tasks to reduce context switching
2. Add integration tests for auth module
3. Update API documentation
4. Plan next feature implementation

⏱️  Duration: 8 minutes 30 seconds

💡 Outstanding session! Quality trends excellent.
   Productivity above average. Minor optimizations available.
```

**Timeline**: 5-10 minutes

### Workflow 4: Issue Investigation

**Best for**: When stuck, debugging, quality degraded

```bash
# Checkpoint to investigate issues

Session Checkpoint: Issue Investigation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Quality Verification:
┌────────────────────────────────────┐
│ Fast Hooks  │ ❌ FAIL (2 issues)   │
│ Test Suite  │ ❌ FAIL (3 failing)  │
└────────────────────────────────────┘

Issues Detected:

Fast Hook Issues:
1. ruff-check: 2 linting issues
   - auth.py:45: F401 'unused_import' imported but unused
   - user.py:78: E501 line too long (95 > 88)

Test Failures:
1. test_login_missing_token
   - File: tests/test_auth.py:23
   - Error: AssertionError: Expected 401, got 200
   - Impact: Authentication bypass vulnerability

2. test_user_delete_admin
   - File: tests/test_user.py:67
   - Error: PermissionError: Admin deletion not allowed
   - Impact: Test expects wrong behavior

3. test_coverage_regression
   - File: tests/test_coverage.py:12
   - Error: Coverage 45% < 50% threshold
   - Impact: Coverage decreased from 47% to 45%

Root Cause Analysis:
Pattern: New auth feature introduced issues
Cause: Insufficient testing before implementation

Workflow Analysis:
┌─────────────────────────────────────┐
│ Recent Changes  │ 5 files modified  │
│ Time Since Last │ 45 minutes        │
│ Checkpoint       │                   │
└─────────────────────────────────────┘

Bottleneck Detected:
⚠️  Quality gate violation
   - Issue: Tests failing, coverage decreased
   - Impact: Blocking progress
   - Cause: Insufficient testing in development cycle

Recommendations (Priority Order):
🔴 CRITICAL:
   1. Fix authentication bypass vulnerability
   2. Restore coverage to 47% minimum

🟡 HIGH:
   3. Fix unused import
   4. Fix line length issue
   5. Clarify admin deletion behavior

🟢 MEDIUM:
   6. Add pre-commit quality gate to catch earlier
   7. Run tests before marking feature complete

Suggested Workflow:
1. Use crackerjack AI fixing:
   python -m crackerjack run --ai-fix --run-tests

2. Manually verify auth fix:
   pytest tests/test_auth.py::test_login_missing_token -v

3. Restore coverage:
   pytest --cov=auth --cov-report=term-missing

4. Re-run checkpoint to verify fixes

Action Plan:
[ ] Fix auth vulnerability (CRITICAL)
[ ] Restore coverage to 47% (CRITICAL)
[ ] Fix linting issues (HIGH)
[ ] Add tests for admin deletion (HIGH)
[ ] Re-run checkpoint to verify

⏱️  Duration: 4 minutes

💡 Quality issues detected but actionable.
   Use AI fixing to resolve quickly.
```

**Timeline**: 3-5 minutes + fix time

## 🔍 Understanding Checkpoint Results

### Quality Status Interpretation

**All Checks Passing** ✅:

- Safe to commit
- Continue work or merge
- No immediate actions needed

**Some Checks Failing** ⚠️:

- Review issues carefully
- Critical issues block commit
- Use AI fixing for auto-fixable issues
- Manual intervention for complex issues

**Many Checks Failing** ❌:

- Stop and assess
- Don't commit until resolved
- May indicate larger problems
- Consider rollback if recent changes broke things

### Bottleneck Detection

**Common Bottlenecks:**

1. **Context Switching** (~10-20% overhead)

   - Symptom: Frequent task changes
   - Solution: Group related tasks

1. **Quality Gate Delays** (~15-30% overhead)

   - Symptom: Fixing issues late in cycle
   - Solution: Test-first development

1. **Tool Configuration** (~5-10% overhead)

   - Symptom: Suboptimal tool settings
   - Solution: Optimize parallelization, caching

1. **Environment Issues** (~20-40% overhead)

   - Symptom: Slow operations, timeouts
   - Solution: Check dependencies, clear caches

### Workflow Patterns

**Optimal Patterns** ✅:

- Test-driven development
- Regular quality checkpoints
- Incremental feature development
- Clean commits with quality gates

**Suboptimal Patterns** ⚠️:

- Code-first, test-later
- Large feature dumps
- Infrequent checkpoints
- Bypassing quality gates

## 🎨 Checkpoint Configuration

### Checkpoint Triggers

**Automatic Triggers** (Optional):

```yaml
# .session-buddy.yaml
checkpoint:
  auto_trigger: true
  interval: 30m          # Every 30 minutes
  on_quality_drop: true  # When coverage decreases
  on_test_failure: true  # When tests fail
  on_feature_complete: true  # After git commit
```

**Manual Triggers**:

- Run this skill explicitly
- Use MCP tool: `checkpoint()`
- Command line: `python -m session_buddy checkpoint`

### Checkpoint Depth

**Quick** (30-60s):

- Fast hooks only
- Test count
- Coverage snapshot

**Standard** (2-5min):

- Full quality workflow
- Workflow analysis
- Basic recommendations

**Deep** (5-10min):

- Everything in standard
- Session metrics
- Trend analysis
- Memory consolidation

## ⚠️ Common Issues

### Issue: "Checkpoint takes too long"

**Cause**: Running comprehensive checks too frequently

**Solution**:

```bash
# Use quick checkpoints for frequency
# Comprehensive checkpoints only when needed

# Quick: Every 30 minutes
python -m session_buddy checkpoint --quick

# Comprehensive: Before commits
python -m session_buddy checkpoint --comprehensive
```

### Issue: "Bottleneck detection not working"

**Cause**: Insufficient session data

**Solution**:

```bash
# Need more session history
# Continue work, checkpoint again later

# Or manually analyze specific aspect
python -m session_buddy checkpoint --analyze workflow
```

### Issue: "Quality keeps failing"

**Cause**: Chronic quality issues, not addressing root causes

**Solution**:

```bash
# Use deep analysis to find patterns
python -m session_buddy checkpoint --deep

# Review:
# - Recurring issues
# - Error patterns
# - Workflow inefficiencies

# Consider:
# - Test-driven development
# - Smaller increments
# - More frequent checkpoints
```

## 🎯 Best Practices

### DO ✅

- **Checkpoint frequently** - Every 30-60 minutes of active work
- **Use appropriate depth** - Quick for frequent, comprehensive for milestones
- **Review recommendations** - They're based on your patterns
- **Store insights** - Memory consolidation helps future sessions
- **Address critical issues** - Don't ignore security/test failures

### DON'T ❌

- **Don't skip checkpoints** - You miss quality trends and insights
- **Don't ignore recommendations** - They're personalized to your workflow
- **Don't checkpoint too frequently** - Every 5-10 minutes is overkill
- **Don't skip quality checks** - Even quick checkpoints should verify basic quality

## 📚 Related Skills

- `session-start` - Initialize session with setup
- `crackerjack-run` - Run quality checks with AI fixing
- `session-end` - End session with final summary

## 🔗 Further Reading

- **Workflow Optimization**: `docs/workflow-optimization.md`
- **Bottleneck Detection**: `docs/bottleneck-analysis.md`
- **Quality Trends**: `docs/quality-metrics.md`
