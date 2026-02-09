# Comprehensive Hooks Timeout Fix - Implementation Plan

## Executive Summary

**Problem**: Comprehensive hooks workflow times out before reaching AI-fix stage, preventing agents from automatically fixing 20 refurb issues.

**Root Cause**: Timeout handling terminates workflow instead of preserving partial results for AI-fix.

**Solution**: Implement graceful timeout handling with progress monitoring and warnings.

---

## Guild Consultation Results

### Performance Engineer Analysis

**Key Findings:**
- **Codebase scale**: 395 Python files, 119,350 lines of code
- **complexipy timeout**: 300s is too small for this codebase size
- **skylos timeout**: 720s (12 minutes) - need to understand why Rust tool is slow
- **Configuration mismatch**: Settings define different timeouts than hooks use

**Recommendations:**
1. **Immediate**: Increase timeouts to realistic values (complexipy: 600s, skylos: 900s)
2. **Short-term**: Enable incremental mode (90% performance improvement)
3. **Long-term**: Implement caching and parallel execution optimization

### Workflow Orchestrator Analysis

**Key Findings:**
- Hooks already run in parallel (COMPREHENSIVE_STRATEGY.parallel=True)
- Problem is individual hook timeouts terminating workflow early
- Need to preserve partial results when timeouts occur
- AI-fix coordinator only processes "failed" results, not "timeout" results

**Recommendations:**
1. **Critical**: Modify timeout handling to preserve partial output
2. **High**: Update AI-fix to process timeout results
3. **Medium**: Add progress bars and timeout warnings
4. **Low**: Implement adaptive timeouts based on historical data

---

## Task List Created

1. **Task 1**: Fix comprehensive hooks timeout behavior (HIGH PRIORITY)
2. **Task 2**: Optimize Rust tool timeouts (HIGH PRIORITY)
3. **Task 3**: Add comprehensive hooks progress display (MEDIUM PRIORITY)
4. **Task 4**: Implement timeout warning system (MEDIUM PRIORITY)

---

## Recommended Starting Point

**Begin with Task 1** - This unblocks the AI-fix workflow immediately and allows the 20 refurb issues to be automatically fixed, regardless of whether complexipy or skylos timeout.

**Implementation time**: 2-3 hours
**Impact**: AI-fix can process issues even when some hooks timeout
**Risk**: Low (isolated changes to timeout handling)

Would you like me to start implementing Task 1?
