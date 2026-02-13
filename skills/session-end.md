---
name: session-end
description: End Claude session with comprehensive cleanup, learning capture, quality summary, and handoff file creation for next session continuity
---

# Session End Workflow

End a Claude session with intelligent cleanup, learning capture, and handoff preparation.

## 🎯 What This Does

This skill orchestrates session completion with:

1. **Final Quality Check**: Verify code quality before closing
2. **Session Metrics**: Capture productivity and quality achievements
3. **Learning Extraction**: Consolidate insights and patterns
4. **Cleanup**: Remove temporary files, consolidate logs
5. **Handoff Creation**: Generate context file for next session
6. **Recommendations**: Provide actionable next steps

## 📋 Before You End

**Pre-end checklist:**

- [ ] **Commit work** - Preserve changes in git
- [ ] **Run quality checks** - Ensure standards met
- [ ] **Document progress** - Notes on what was accomplished
- [ ] **Save context** - Important details for next session

**Questions to consider:**

- Did you complete what you planned?
- What were the key accomplishments?
- What should be continued next time?
- Are there any blocking issues?
- What would improve the next session?

## 🚀 Interactive Session End

### Step 1: End Session Type

**What type of session end do you need?**

1. **Clean End** (Recommended for most sessions)
   - Final quality verification
   - Metrics and learning capture
   - Cleanup and handoff
   - Duration: 2-4 minutes

2. **Quick End** (Fast, minimal overhead)
   - Basic cleanup only
   - No quality checks
   - Minimal capture
   - Duration: <30 seconds

3. **Comprehensive End** (Complete analysis)
   - Everything in clean end
   - Deep trend analysis
   - Extended memory consolidation
   - Detailed handoff document
   - Duration: 5-10 minutes

4. **Emergency End** (Force quit)
   - Immediate cleanup
   - Minimal capture
   - For: System issues, forced termination
   - Duration: <10 seconds

### Step 2: Quality Verification

**What should be checked before closing?**

**Essential Checks** (Recommended):
- [ ] **Fast Hooks** - Formatting, linting (~5s)
- [ ] **Test Verification** - Ensure tests passing
- [ ] **Coverage Check** - No coverage regression

**Optional Checks** (Comprehensive end):
- [ ] **Comprehensive Hooks** - Full quality gate
- [ ] **Git Status** - Uncommitted changes
- [ ] **Documentation** - Updated docs

**Skip Checks** (Quick/Emergency end):
- Skip all quality verification
- Just cleanup and close
- Use when: System issues, time pressure

### Step 3: Cleanup Options

**What should be cleaned up?**

**Standard Cleanup** (Recommended):
- [ ] **Temp Files** - Remove temporary artifacts
- [ ] **Log Consolidation** - Merge and compress logs
- [ ] **Cache Cleanup** - Clear stale caches
- [ ] **Process Cleanup** - Terminate background processes

**Extended Cleanup** (Comprehensive end):
- [ ] All standard cleanup
- [ ] **Archive Old Sessions** - Compress session history
- [ ] **Database Maintenance** - Vacuum, optimize
- [ ] **Memory Optimization** - Consolidate embeddings

**Minimal Cleanup** (Quick end):
- [ ] Essential temp files only
- [ ] Keep logs for debugging
- [ ] Skip database maintenance

### Step 4: Handoff Preparation

**What should be preserved for next session?**

**Essential Context** (Always included):
- [ ] **Session Summary** - What was accomplished
- [ ] **Current Status** - Quality metrics, test counts
- [ ] **Next Steps** - Recommended priorities
- [ ] **Blocking Issues** - Anything preventing progress

**Extended Context** (Comprehensive end):
- [ ] All essential context
- [ ] **Work Patterns** - What worked well
- [ ] **Lessons Learned** - Key insights
- [ ] **Technical Decisions** - Rationale for choices
- [ ] **Code References** - Important files/functions

**Minimal Context** (Quick end):
- [ ] Session summary only
- [ ] Current status snapshot

## 💡 Common Session End Workflows

### Workflow 1: Clean End (Recommended)

**Best for**: Normal session completion, most common workflow

```bash
# Standard clean session end

Session End: Clean End
═══════════════════════════════════════════════

Final Quality Verification:
┌────────────────────────────────────┐
│ Fast Hooks     │ ✅ PASS (5s)      │
│ Test Suite     │ ✅ PASS (18s)     │
│ Coverage       │ ✅ 49% (no regression)│
└────────────────────────────────────┘

✅ Quality verification passed

Session Metrics:
┌─────────────────────────────────────┐
│ Duration          │ 3h 20m          │
│ Tasks Completed   │ 5 features      │
│ Bugs Fixed        │ 2 bugs          │
│ Tests Added       │ 28 tests        │
│ Files Modified     │ 18 files        │
│ Coverage Change   │ 42% → 49% (+7%) │
└─────────────────────────────────────┘

Learning Extraction:
Captured 5 key insights:
1. "Test-driven development reduces iteration time by 40%"
2. "Parallel tests significantly faster on this codebase"
3. "Fast hooks retry catches 90% of formatting issues"
4. "Quality checkpoints every 30min prevent late failures"
5. "Session continuity improves decision quality"

Cleanup Activities:
✓ Removed 47 temporary files
✓ Consolidated 12 log files
✓ Cleared stale cache entries
✓ Terminated 3 background processes

Handoff Created: .session-handoff.md
┌─────────────────────────────────────┐
│ Session Date     │ 2025-02-10       │
│ Duration         │ 3h 20m           │
│ Final Quality    │ 85/100 ⭐⭐⭐⭐☆ │
│                 │                   │
│ Completed:       │                   │
│ ✓ User authentication module        │
│ ✓ Password reset flow               │
│ ✓ Admin user management            │
│ ✓ Rate limiting middleware          │
│ ✓ API documentation                │
│                 │                   │
│ Next Session Priorities:           │
│ 1. Add integration tests for auth   │
│ 2. Refactor login() complexity      │
│ 3. Update API docs for new endpoints│
│ 4. Consider coverage target 55%     │
│                 │                   │
│ Blocking Issues:  None             │
│ Open Questions:  None              │
└─────────────────────────────────────┘

Recommendations:
💡 Excellent session! Quality improved steadily.
💡 Test-driven approach very effective.
💡 Ready to continue with integration tests.

Next Session Suggestions:
1. Start with integration tests for auth module
2. Consider increasing coverage target to 55%
3. Review API documentation completeness
4. Plan permissions system implementation

Session ended successfully! ✅

⏱️  Duration: 3 minutes 15 seconds
```

**Timeline**: 2-4 minutes

### Workflow 2: Quick End

**Best for**: Fast session termination, time pressure

```bash
# Quick session end

Session End: Quick End
════════════════════════════════

Skipping quality verification...

Session Metrics:
┌─────────────────────────────────────┐
│ Duration          │ 45m             │
│ Tasks Completed   │ 1 feature       │
│ Files Modified     │ 5 files         │
└─────────────────────────────────────┘

Cleanup Activities:
✓ Removed 12 temporary files
✓ Terminated 1 background process

Handoff Created: .session-handoff.md
Quick summary only.

Session ended (quick mode)! ✅

⏱️  Duration: 18 seconds
```

**Timeline**: <30 seconds

### Workflow 3: Comprehensive End

**Best for**: Major milestones, project completion, deep analysis

```bash
# Comprehensive session end with full analysis

Session End: Comprehensive Analysis
═══════════════════════════════════════════════

[Quality verification passes - see clean end output]

Session Metrics: Extended
┌─────────────────────────────────────────┐
│ Duration          │ 5h 45m              │
│ Active Coding     │ 4h 30m              │
│ Quality Checks    │ 45m                 │
│ Planning/Research │ 30m                 │
│                  │                      │
│ Tasks Completed   │ 8 features          │
│ Bugs Fixed        │ 4 bugs              │
│ Tests Added       │ 47 tests            │
│ Docs Updated      │ 6 files             │
│ Files Modified     │ 28 files            │
│ Lines Added       │ +1,247 lines        │
│ Lines Removed     │ -428 lines          │
│ Net Change        │ +819 lines          │
└─────────────────────────────────────────┘

Quality Trend Analysis (This Session):
Coverage Progression:
  Start:  42%
  Mid:    47% (checkpoint 1)
  Mid:    49% (checkpoint 2)
  End:    52%
  Total Change: +10% 🎉 Excellent!

Test Health Progression:
  Start:  34 tests
  Mid:    62 tests
  Mid:    73 tests
  End:    89 tests
  Added: 55 new tests 🎉

Complexity Trends:
  Violations detected: 0
  Complex functions refactored: 3
  Overall complexity: Reduced ✅

Productivity Analysis:
Velocity: 1.4 tasks/hour
Efficiency: 78% (active coding / total time)
Rating: ⭐⭐⭐⭐⭐ (5/5) Outstanding!

Workflow Pattern Analysis:
✅ Test-driven development - Consistently applied
✅ Regular checkpoints - Every 45-60 minutes
✅ Incremental features - Small, focused changes
✅ Quality-first approach - No bypassing gates
✅ Good documentation - Docs updated with features

Optimal Patterns Detected:
1. "Test-first reduces iteration count by 45%"
2. "Checkpoints prevent quality regressions"
3. "Small commits enable easy rollback"
4. "Documentation with code reduces debt"

Areas for Improvement:
1. Context switching between tasks (~8% overhead)
   - Solution: Group related features together
2. Some test redundancy detected (~5%)
   - Solution: Review test coverage, remove duplicates

Error Pattern Analysis:
No recurring errors
Clean error handling patterns throughout
Good test coverage of edge cases

Session Learning Summary:
Captured 12 key insights:

Technical Insights:
1. "Pytest fixtures reduce test boilerplate by 60%"
2. "Async tests need proper cleanup to avoid flakiness"
3. "Type checking catches 30% of bugs before tests"
4. "Complexity limits guide better API design"

Workflow Insights:
5. "Test-driven development is 40% faster overall"
6. "Checkpoint every 45min optimal for this codebase"
7. "Small commits enable rapid rollback when needed"
8. "Documentation with code prevents tech debt"

Tool Insights:
9. "Parallel tests 3.5x faster on this codebase"
10. "AI fixing resolves 85% of issues automatically"
11. "Coverage ratchet prevents regression"
12. "Session continuity improves decision quality"

Memory Consolidation:
Stored 12 insights in session database
Consolidated patterns for future reference
Indexed for cross-session learning

Deep Cleanup Activities:
✓ Removed 89 temporary files
✓ Consolidated and compressed 28 log files
✓ Cleared stale cache entries (save ~200MB)
✓ Optimized session database (VACUUM)
✓ Archived old session history (3 sessions)
✓ Consolidated embeddings (save ~150MB)
✓ Terminminated 5 background processes

Total cleanup saved: ~350MB disk space

Comprehensive Handoff Created: .session-handoff.md
┌─────────────────────────────────────────────┐
│ SESSION SUMMARY                             │
├─────────────────────────────────────────────┤
│ Date              │ 2025-02-10              │
│ Duration          │ 5h 45m                  │
│ Quality Score     │ 92/100 ⭐⭐⭐⭐⭐         │
│ Productivity      │ 5/5 stars               │
│                                             │
│ COMPLETED WORK                            │
│ ├─ Features: 8 completed                   │
│ │  ├─ User authentication                  │
│ │  ├─ Password reset                      │
│ │  ├─ Admin management                    │
│ │  ├─ Rate limiting                       │
│ │  ├─ Session management                  │
│ │  ├─ API documentation                   │
│ │  ├─ Integration tests                   │
│ │  └─ Performance optimization            │
│ ├─ Bugs Fixed: 4                          │
│ ├─ Tests Added: 47                         │
│ ├─ Docs Updated: 6 files                   │
│ └─ Files Modified: 28                      │
│                                             │
│ QUALITY ACHIEVEMENTS                       │
│ ├─ Coverage: 42% → 52% (+10%) 🎉          │
│ ├─ Tests: 34 → 89 (+55) 🎉                │
│ ├─ Complexity: Reduced, 0 violations       │
│ └─ Security: No vulnerabilities            │
│                                             │
│ NEXT SESSION PRIORITIES                    │
│ 1. Add E2E tests for auth flows            │
│ 2. Implement permissions system            │
│ 3. Performance testing for rate limiter    │
│ 4. Consider coverage target 60%            │
│ 5. Architecture review for scalability    │
│                                             │
│ TECHNICAL DECISIONS                        │
│ ├─ Chose pytest over unittest              │
│ │  Rationale: Better fixtures, parallel    │
│ ├─ Used FastAPI for API                    │
│ │  Rationale: Async, type safety, docs     │
│ └─ Implemented rate limiting with Redis   │
│    Rationale: Distributed systems ready    │
│                                             │
│ LESSONS LEARNED                            │
│ ├─ Test-driven development is 40% faster   │
│ ├─ Regular checkpoints prevent failures   │
│ ├─ Small commits enable rapid rollback     │
│ └─ Session continuity improves decisions  │
│                                             │
│ BLOCKING ISSUES                            │
│ None ✅                                    │
│                                             │
│ OPEN QUESTIONS                             │
│ 1. Should we use Redis for session storage?│
│ 2. What's the target user scale?          │
│ 3. Do we need multi-factor auth?          │
└─────────────────────────────────────────────┘

Recommendations:
🎉 Outstanding session! Quality and productivity exceptional.
💡 Test-driven approach highly effective.
💡 Regular checkpoints prevented quality issues.
💡 Session continuity enabled good decisions.

Next Session Plan:
1. Review and prioritize open questions
2. Implement permissions system (test-first!)
3. Add E2E tests for critical flows
4. Consider performance testing
5. Plan architecture review session

Session ended successfully! ✅

Total elapsed time: 8 minutes 45 seconds
```

**Timeline**: 5-10 minutes

### Workflow 4: Emergency End

**Best for**: System issues, forced termination

```bash
# Emergency session end

Session End: Emergency Termination
═════════════════════════════════════

Emergency cleanup initiated...

Skipping all verification...
Minimal cleanup only...
Basic handoff creation...

✓ Temp files removed
✓ Processes terminated
✓ Basic handoff created

Session ended (emergency mode)! ⚠️

⏱️  Duration: 7 seconds
```

**Timeline**: <10 seconds

## 🔍 Understanding Handoff Files

### Handoff File Structure

**Location**: `.session-handoff.md` in project root

**Sections**:
1. **Session Summary** - Date, duration, quality score
2. **Completed Work** - Features, bugs, tests, docs
3. **Quality Achievements** - Coverage, test counts
4. **Next Priorities** - Recommended next steps
5. **Technical Decisions** - Rationale for choices
6. **Lessons Learned** - Key insights
7. **Blocking Issues** - Anything preventing progress
8. **Open Questions** - Unresolved items

### Handoff Usage

**Next Session Start**:
```bash
# Session automatically loads handoff
Session Start: Welcome back!

📋 Previous Session Handoff:
[Shows .session-handoff.md contents]

Restoring context...
✓ Loaded priorities
✓ Loaded technical decisions
✓ Loaded lessons learned
✓ Ready to continue!
```

**Benefits**:
- Seamless context restoration
- Avoids redoing work
- Preserves learnings
- Informed recommendations

## 🎨 End Configuration

### Auto-End Behavior

**Automatic on Disconnect**:
```yaml
# .session-buddy.yaml
session:
  auto_end: true
  end_mode: clean  # quick, clean, comprehensive

  auto_cleanup:
    temp_files: true
    log_consolidation: true
    cache_clear: true
```

### Manual End

**Explicit Command**:
```bash
# End with specific mode
python -m session_buddy end --mode clean

# Or use this skill
/session:end
```

### Quality Gate

**Require Passing Checks**:
```yaml
# .session-buddy.yaml
session:
  quality_gate: true
  require_tests_pass: true
  require_coverage_no_regression: true
```

## ⚠️ Common Issues

### Issue: "Quality check failed, can't end session"

**Cause**: Quality gate enabled, checks not passing

**Solution**:
```bash
# Option 1: Fix issues first
python -m crackerjack run --ai-fix --run-tests

# Option 2: Override quality gate
python -m session_buddy end --force

# Option 3: Quick end (skips checks)
python -m session_buddy end --mode quick
```

### Issue: "Handoff file not created"

**Cause**: Permissions, disk space, or file lock

**Solution**:
```bash
# Check permissions
ls -la .session-handoff.md

# Check disk space
df -h

# Try alternative location
python -m session_buddy end --handoff /tmp/handoff.md
```

### Issue: "Cleanup stuck/hanging"

**Cause**: Background process not terminating

**Solution**:
```bash
# Force quit cleanup
python -m session_buddy end --timeout 5

# Or skip cleanup
python -m session_buddy end --skip-cleanup
```

## 🎯 Best Practices

### DO ✅

- **Commit before ending** - Preserve your work
- **Run quality checks** - Ensure standards met
- **Review handoff file** - Verify accuracy
- **Clean end recommended** - Balance thoroughness vs time
- **Load handoff next session** - Continuity is valuable

### DON'T ❌

- **Don't end without committing** - Lose work risk
- **Don't skip quality checks** - May miss issues
- **Don't ignore recommendations** - Personalized to your patterns
- **Don't use emergency end unless necessary** - Loses valuable data
- **Don't delete handoff file** - Next session needs it

## 📚 Related Skills

- `session-start` - Begin session with setup
- `session-checkpoint` - Mid-session quality check
- `crackerjack-run` - Quality checks with AI fixing

## 🔗 Further Reading

- **Session Lifecycle**: `docs/session-lifecycle.md`
- **Handoff Format**: `docs/handoff-specification.md`
- **Memory Consolidation**: `docs/memory-system.md`
