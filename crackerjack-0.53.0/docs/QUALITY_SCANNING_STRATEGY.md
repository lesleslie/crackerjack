# Crackerjack Quality Scanning: Strategic Decision Framework

## Executive Summary

We need to optimize slow quality hooks (refurb, complexipy, skylos) that take 10+ minutes per scan. Three complementary approaches are available:

1. **Incremental Scanning**: Scan only changed files (10-20x faster)
1. **Mahavishnu Pools**: Parallel tool execution (2.5-3x faster)
1. **Combined Approach**: Incremental + Pools (30-60x faster for typical commits)

**Recommendation**: Implement **Combined Approach** in phases for maximum impact with manageable risk.

______________________________________________________________________

## Current State Analysis

### Tool Performance (Full Repository Scan)

| Tool | Time | Purpose | Alternative |
|------|------|---------|-------------|
| **refurb** | 290s | Python modernization suggestions | None (keep!) |
| **complexipy** | 605s | Cognitive complexity analysis | ruff complexity (10-20x faster) |
| **skylos** | 60s | Dead code detection (Rust) | vulture (Python, 2-5x slower) |
| **semgrep** | 70s | Security vulnerability patterns | None (security critical) |
| **gitleaks** | 29s | Secret detection | None (security critical) |

**Total Slow Tools**: ~1054 seconds (17.5 minutes)

### Tool Classification by Usage Pattern

**Frequently Run (Daily Workflows)**:

- Should be FAST: \<60 seconds
- Tools: ruff, vulture, codespell, check-jsonschema
- Current: ✅ Already fast

**Moderately Frequent (Pre-commit, CI)**:

- Should be MODERATE: 1-3 minutes
- Tools: refurb, skylos, semgrep
- Current: ❌ 290s, 60s, 70s (too slow)

**Less Frequent (Publish, Release)**:

- Can be SLOW: 5-10 minutes acceptable
- Tools: complexipy, full security scans
- Current: ⚠️ 605s (too slow even for publish)

______________________________________________________________________

## Decision Matrix

### Option 1: Tool Substitution (Quick Win)

**Approach**: Replace slow tools with faster alternatives for daily workflows.

| Tool | Current | Alternative | Speedup | Trade-off |
|------|---------|-------------|---------|-----------|
| complexipy | 605s | ruff complexity | 10-20x | Fewer complexity metrics |
| skylos | 60s | vulture | 0.5x (slower) | Python vs Rust, different detection |

**Implementation**:

```yaml
# .crackerjack.yaml
tools:
  complexity:
    daily: ruff      # Fast, good enough for daily
    publish: complexipy  # Comprehensive for releases

  dead_code:
    daily: vulture    # Slower but good enough
    publish: skylos   # Fastest, most comprehensive
```

**Pros**:

- ✅ Easy to implement (1 hour)
- ✅ No architectural changes
- ✅ Immediate speedup (10-20x for complexity)

**Cons**:

- ❌ Loses some tool capabilities
- ❌ Two sets of tool outputs to maintain
- ❌ Doesn't solve root problem (full scans)

**Effort**: 1-2 hours
**Impact**: 5-10x speedup for workflows that use complexipy
**Risk**: Low

______________________________________________________________________

### Option 2: Incremental Scanning (High Impact)

**Approach**: Scan only files changed since last successful run.

**Three Implementation Variants**:

#### 2A: Git-Diff-Based (Simplest)

```python
# Scan files changed since HEAD~1
files = git diff --name-only HEAD~1 HEAD
refurb [files]
```

**Effort**: 2-3 hours
**Speedup**: 10-20x for small commits
**Risk**: Low

#### 2B: Marker-Based (Most Accurate)

```python
# Track per-file scan timestamps
if file.hash != last_scanned_hash:
    scan(file)
```

**Effort**: 4-6 hours
**Speedup**: 15-30x (handles edge cases better)
**Risk**: Medium (database management)

#### 2C: Hybrid (Recommended)

```python
# Use git-diff with periodic full scans
if days_since_last_full_scan > 7:
    full_scan()
else:
    incremental_scan()
```

**Effort**: 3-4 hours
**Speedup**: 10-20x (with safety net)
**Risk**: Low

**Pros**:

- ✅ Dramatic speedup for typical commits
- ✅ Works with all tools
- ✅ Minimal behavior change

**Cons**:

- ❌ Can miss issues in refactored code
- ❌ Requires periodic full scans
- ❌ Adds complexity to hook system

______________________________________________________________________

### Option 3: Mahavishnu Pools (Scalability)

**Approach**: Distribute tool execution across worker pools for parallel processing.

**Architecture**:

```
Crackerjack → Mahavishnu Pool Manager → 8 Parallel Workers
    ↓                                          ↓
  File List                                  refurb (files 1-10)
    ↓                                          ↓
  Task Distributor                           complexipy (files 11-20)
    ↓                                          ↓
  Result Aggregator                         skylos (files 21-30)
                                               ↓
                                            [5 more workers...]
```

**Effort**: 4-6 hours (Phase 1), +4 hours (optimization)
**Speedup**: 2.5-3x for full scans, 3-6x for incremental
**Risk**: Medium (mahavishnu dependency)

**Pros**:

- ✅ Scales to large codebases
- ✅ Works with all tools transparently
- ✅ Fault isolation (worker crashes don't affect others)
- ✅ Can use Kubernetes for massive parallelism

**Cons**:

- ❌ Mahavishnu must be running
- ❌ More complex architecture
- ❌ Debugging distributed execution harder
- ❌ Resource overhead (pool management)

______________________________________________________________________

### Option 4: Combined Approach (Maximum Impact) ⭐ RECOMMENDED

**Approach**: Use incremental scanning for file filtering + mahavishnu pools for parallel execution.

**Workflow**:

```
1. File Scanner (git-diff)
   └─> Get 20 changed files

2. Task Distributor
   └─> Split into 4 chunks (5 files each)

3. Mahavishnu Pool (8 workers)
   ├─> Worker 1: refurb chunk 1
   ├─> Worker 2: refurb chunk 2
   ├─> Worker 3: complexipy chunk 1
   ├─> Worker 4: complexipy chunk 2
   ├─> Worker 5: skylos chunk 1
   ├─> Worker 6: skylos chunk 2
   ├─> Worker 7: semgrep all files
   └─> Worker 8: gitleaks all files

4. Result Aggregator
   └─> Combine outputs, generate report
```

**Performance**:
| Commit Size | Old Time | New Time | Speedup |
|-------------|----------|----------|---------|
| Small (5-10 files) | 10+ min | 10-20s | **30-60x** |
| Medium (10-50 files) | 10+ min | 20-40s | **15-30x** |
| Large (50+ files) | 10+ min | 2-3 min | **3-5x** |
| Publish (full scan) | 10+ min | 3-4 min | **2.5-3x** |

**Implementation Phases**:

- **Phase 1** (2-3 hours): Git-diff incremental scanning
- **Phase 2** (2-3 hours): Mahavishnu pool integration
- **Phase 3** (1-2 hours): Combine incremental + pools
- **Phase 4** (2-3 hours): Optimization and monitoring

**Total Effort**: 7-11 hours
**Total Speedup**: 30-60x for typical commits
**Risk**: Medium (complex but phased)

______________________________________________________________________

## Recommendations by Use Case

### Daily Development Workflow

**Goal**: \<60 second feedback for typical commits

**Solution**: Option 2C (Hybrid Incremental)

- Use git-diff for changed files
- Run tools only on changes
- Weekly full scan as safety net
- **Time**: 30-60s (vs 10+ min)
- **Effort**: 3-4 hours

### Pre-commit/CI Workflow

**Goal**: 1-3 minutes for comprehensive checks

**Solution**: Option 4 (Combined) - Phase 1 & 2

- Incremental scanning (git-diff)
- Mahavishnu pools (8 workers)
- Run all changed files in parallel
- **Time**: 20-40s (vs 10+ min)
- **Effort**: 4-6 hours

### Publish/Release Workflow

**Goal**: Comprehensive checks in 5-10 minutes

**Solution**: Option 3 (Mahavishnu Pools) + Tool Substitution

- Full repository scan
- Mahavishnu pools for parallel execution
- Use complexipy only for publish (not daily)
- **Time**: 3-4 min (vs 10+ min)
- **Effort**: 2-3 hours (pools) + 1 hour (config)

______________________________________________________________________

## Tool-Specific Recommendations

### refurb (Python Modernization)

**Status**: ✅ Keep using!
**Reason**: Actively maintained, finds useful modernization opportunities for Python 3.13+
**Strategy**:

- Daily: Incremental scan (changed files only)
- Publish: Full scan with mahavishnu pools
  **Time Savings**: 290s → 10-30s (incremental), ~100s (pooled)

### complexipy (Cognitive Complexity)

**Status**: ⚠️ Too slow for daily use
**Reason**: 605 seconds is excessive even for publish
**Strategy**:

- Daily: Use ruff complexity instead (10-20x faster)
- Publish: Use complexipy with mahavishnu pools (3-4x faster than current)
  **Time Savings**: 605s → 5s (ruff), ~150s (pooled complexipy)

### skylos (Dead Code Detection)

**Status**: ✅ Excellent, but position wrong
**Reason**: Rust-based, fastest dead code detector available
**Strategy**:

- Daily: Use vulture (slower but good enough)
- Publish: Use skylos (fastest and most comprehensive)
  **Time Savings**: 60s → 30s (vulture), ~20s (pooled skylos)

______________________________________________________________________

## Implementation Priority

### Quick Wins (1-2 hours, 5-10x speedup)

1. ✅ Switch daily complexity to ruff
1. ✅ Use vulture for daily dead code detection
1. ✅ Keep skylos, refurb, complexipy for publish only

**Impact**: Most workflows see 5-10x speedup immediately
**Risk**: None (tool configuration only)

### High Impact (3-4 hours, 10-20x speedup)

4. ✅ Implement git-diff incremental scanning
1. ✅ Add weekly full scan safety net
1. ✅ Update hook configuration

**Impact**: Typical commits 10-20x faster
**Risk**: Low (proven git-diff approach)

### Maximum Impact (7-11 hours total, 30-60x speedup)

7. ✅ Integrate mahavishnu pools (Phase 1)
1. ✅ Combine incremental + pools (Phase 2)
1. ✅ Add monitoring and optimization (Phase 3)

**Impact**: All workflows 30-60x faster for typical commits
**Risk**: Medium (but mitigated by phased approach)

______________________________________________________________________

## Configuration Examples

### Daily Workflow (Fast)

```yaml
# .crackerjack.yaml.daily

mode: incremental
incremental:
  use_git_diff: true
  fallback_to_full: false

tools:
  fast:
    - ruff           # Formatting, complexity
    - vulture        # Dead code
    - codespell      # Typos
    - refurb         # Modernization (incremental)
```

**Expected Time**: 30-60 seconds for typical commits

### Publish Workflow (Comprehensive)

```yaml
# .crackerjack.yaml.publish

mode: full
pools:
  enabled: true
  workers: 8

tools:
  fast:
    - ruff
    - refurb
    - skylos

  comprehensive:
    - complexipy     # Only for publish
    - semgrep        # Security
    - gitleaks       # Secrets
```

**Expected Time**: 3-4 minutes for full scan

______________________________________________________________________

## Migration Path

### Week 1: Tool Substitution

- [ ] Switch daily workflow to ruff + vulture
- [ ] Keep refurb, skylos, complexipy for publish
- [ ] Update documentation
- [ ] Test with team

### Week 2: Incremental Scanning

- [ ] Implement git-diff scanner
- [ ] Add weekly full scan
- [ ] Update hook runners
- [ ] Monitor cache hit rates

### Week 3: Mahavishnu Integration

- [ ] Restart and connect mahavishnu MCP
- [ ] Implement pool client
- [ ] Add pool-based hooks
- [ ] Benchmark performance

### Week 4: Optimization

- [ ] Combine incremental + pools
- [ ] Add monitoring dashboards
- [ ] Tune worker counts
- [ ] Document best practices

______________________________________________________________________

## Open Questions for Consultants

1. **Tool Strategy**: Do you agree refurb is valuable for Python 3.13+ codebases?
1. **Incremental Approach**: Git-diff (simple) vs marker-based (accurate)?
1. **Full Scan Frequency**: Weekly, bi-weekly, or monthly?
1. **Pool Workers**: How many workers? (4, 8, 16?)
1. **Mahavishnu Availability**: Running in all environments? (local, CI, docker)
1. **Fallback Strategy**: What if mahavishna is unavailable?
1. **Metrics**: What should we track? (scan times, cache hit rates, tool failures?)
1. **Team Workflow**: How often do you publish? (affects full scan frequency)

______________________________________________________________________

## Decision Framework

### Choose Option 1 (Tool Substitution) if:

- ✅ You need immediate results
- ✅ Minimal implementation effort
- ✅ Willing to accept different tool outputs
- ❌ Don't need full repository scans

### Choose Option 2 (Incremental Scanning) if:

- ✅ Most commits touch \<50 files
- ✅ Can accept weekly full scans
- ✅ Want simple, proven approach
- ❌ Don't have mahavishnu available

### Choose Option 3 (Mahavishnu Pools) if:

- ✅ Large codebase (>100k files)
- ✅ Have mahavishnu infrastructure
- ✅ Need full scans regularly
- ❌ Can handle distributed complexity

### Choose Option 4 (Combined) if:

- ✅ Want maximum performance (30-60x faster)
- ✅ Willing to invest 7-11 hours
- ✅ Have mahavishnu or can set it up
- ✅ Want scalable, future-proof solution
- ⭐ **RECOMMENDED FOR MOST TEAMS**

______________________________________________________________________

## Next Steps

1. **🔍 Review This Document**: Share with team and consultants
1. **💬 Discuss Strategy**: Answer open questions, prioritize approach
1. **🚀 Choose Path**: Select option(s) based on constraints
1. **📋 Implementation**: Follow phased migration path
1. **📊 Measure Success**: Track metrics and optimize

______________________________________________________________________

**Prepared by**: Claude Sonnet 4.5
**Date**: 2026-02-13
**Status**: Ready for decision
**Related Docs**:

- `docs/INTEGRAL_SCANNING_OPTIONS.md` - Incremental scanning details
- `docs/MAHAVISHNU_POOL_INTEGRATION.md` - Pool architecture
