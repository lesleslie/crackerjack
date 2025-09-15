# Experimental Features Evaluation

This document tracks the evaluation and potential promotion of experimental features in crackerjack.

## Current Experimental Features

### 🔬 Pyrefly - Advanced Python Static Analysis

- **Entry**: `python -m pyrefly --check`
- **Target Files**: `^crackerjack/.*\.py$`
- **Stage**: Manual only
- **Time Estimate**: 5.0 seconds
- **Dependencies**: `pyrefly >= 0.1.0`

**Evaluation Criteria**:

- [ ] **Availability**: Tool consistently available across environments
- [ ] **Stability**: No crashes or inconsistent results across runs
- [ ] **Value Added**: Catches issues not found by existing tools (ruff, bandit, etc.)
- [ ] **Performance**: Stays within 5s time budget
- [ ] **Integration**: Works reliably with pre-commit workflow

**Current Status**: 🔴 **Failed Evaluation**

- ❌ **Availability**: Tool not available in environment (`No module named pyrefly`)
- ❌ **Reliability**: Cannot test due to availability issues
- **Decision**: Remove from experimental registry

### ⚡ Ty - Fast Type Checking Acceleration

- **Entry**: `python -m ty --check`
- **Target Files**: `^crackerjack/.*\.py$`
- **Stage**: Manual only
- **Time Estimate**: 2.0 seconds
- **Dependencies**: `ty >= 0.1.0`

**Evaluation Criteria**:

- [ ] **Availability**: Tool consistently available across environments
- [ ] **Stability**: Reliable type checking without false positives
- [ ] **Performance**: Significantly faster than existing type checkers
- [ ] **Accuracy**: Type checking results match or exceed zuban/pyright
- [ ] **Integration**: Seamless workflow integration

**Current Status**: 🔴 **Failed Evaluation**

- ❌ **Availability**: Tool not available in environment (`No module named ty`)
- ❌ **Reliability**: Cannot test due to availability issues
- **Decision**: Remove from experimental registry

## Promotion Framework

### Phase 1: Experimental (Current)

- ✅ Added to experimental hook registry
- ✅ Available via `--experimental-hooks` or individual flags
- ✅ Limited to `manual` stage only
- ✅ Documented in CLAUDE.md and AI-REFERENCE.md

### Phase 2: Evaluation

- [ ] Performance benchmarking completed
- [ ] Stability testing across environments
- [ ] Value assessment vs existing tools
- [ ] Community feedback collected

### Phase 3: Conditional Promotion

**Criteria for promotion to comprehensive mode**:

1. **Zero reliability issues** over 30-day evaluation period
1. **Measurable value added** beyond existing tools
1. **Performance within budget** (pyrefly ≤5s, ty ≤2s)
1. **Cross-platform compatibility** verified
1. **Team consensus** on value proposition

### Phase 4: Full Integration

- Move from experimental registry to appropriate tier (2 or 3)
- Change stage from `manual` to `pre-push` or `pre-commit`
- Update documentation to reflect stable status
- Add to default comprehensive workflow

## Evaluation Timeline

### Week 1-2: Initial Testing

- [ ] Test experimental hooks on development machine
- [ ] Verify tools install and run correctly
- [ ] Document any installation or runtime issues

### Week 3-4: Performance Assessment

- [ ] Benchmark execution times across different codebase sizes
- [ ] Compare value-add vs existing tools
- [ ] Test integration with AI agent workflow

### Month 2: Stability Testing

- [ ] Cross-platform testing (macOS, Linux, Windows via CI)
- [ ] Long-term stability assessment
- [ ] Integration testing with full workflow

### Month 3: Decision Point

- [ ] Compile evaluation results
- [ ] Make promotion/retention/removal decision
- [ ] Update documentation and configurations accordingly

## Removal Criteria

Experimental features will be **removed** if:

1. **Unreliable**: Frequent crashes or inconsistent results
1. **No value added**: Duplicates existing tool capabilities
1. **Performance issues**: Exceeds time budget or slows workflow
1. **Maintenance burden**: Requires significant ongoing support
1. **Compatibility issues**: Breaks across different environments

## Final Decision

**Status**: 🔴 **Experimental Hooks Removed**

Both pyrefly and ty failed the initial availability testing phase and have been removed from the experimental registry.

**Decision Rationale**:

1. **Failed Availability Criteria**: Both tools returned `No module named [tool]` errors
1. **Cannot Proceed with Evaluation**: Without basic availability, further testing is impossible
1. **Clean Removal Executed**: Tools removed from both `.pre-commit-config.yaml` and `dynamic_config.py`

**Actions Taken**:

- ✅ Removed pyrefly and ty from experimental hook registry
- ✅ Updated documentation to reflect framework status
- ✅ Preserved experimental hook evaluation framework for future candidates
- ✅ Documented removal criteria and process

**Framework Status**: **Ready for Future Evaluation**

The experimental hook framework remains fully functional and documented, ready to evaluate future tool candidates that meet the basic availability requirements.
