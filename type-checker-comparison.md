# Python Type Checker Comparison & Implementation Plan

## Executive Summary

**Recommendation**: Implement **Zuban** as immediate pyright replacement (drop-in compatible), keep **ty** and **pyrefly** as experimental hooks until mature.

## Type Checker Comparison Matrix

| Feature | Pyright | Zuban | ty (Astral) | Pyrefly (Meta) |
|---------|---------|--------|-------------|----------------|
| **Language** | TypeScript | Rust | Rust | Rust |
| **Speed** | Baseline (1x) | 20-200x faster than mypy | 100x faster than mypy | 35x faster than Pyre |
| **Memory** | High | ~50% of ty/pyrefly | Moderate | Moderate |
| **Maturity** | Production | Alpha (69% tests pass) | Preview (15% tests) | Alpha (58% tests) |
| **Drop-in Replace** | - | Yes (pyright mode) | No | No |
| **LSP Support** | Full | Most features | Planned | Basic |
| **License** | MIT | AGPL v3 / Commercial | MIT | MIT |
| **Release Date** | Production | Beta 2025 | Production late 2025 | Production end 2025 |

## Detailed Analysis

### Zuban - Immediate Replacement Candidate

**Pros:**

- **Drop-in replacement** for pyright with `zuban check` command
- **Dual modes**: Pyright-like (default) and Mypy-compatible (`zmypy`)
- **Best performance**: 20-200x faster than mypy, uses less memory than competitors
- **Most mature**: 69% test suite pass rate vs 15% (ty) and 58% (pyrefly)
- **LSP ready**: Most features implemented (diagnostics, completions, goto, references)
- **14 years experience**: Built by Jedi's creator

**Cons:**

- AGPL v3 license (commercial available)
- Alpha status (but most mature of new tools)
- Some false positives expected

**Implementation:**

```bash
# Simple replacement
pip install zuban
zuban check  # Replaces pyright
zuban server # LSP server
```

### ty (Astral) - Experimental Hook

**Pros:**

- **Astral ecosystem**: Integrates with ruff and uv
- **MIT license**: Consistent with other Astral tools
- **Future potential**: Type-aware lints for ruff planned
- **Performance**: 2-3x faster than pyrefly in benchmarks

**Cons:**

- **Not drop-in**: Requires configuration changes
- **Low maturity**: Only 15% test pass rate
- **Late 2025 production**: Not ready until end of year

### Pyrefly (Meta) - Experimental Hook

**Pros:**

- **Instagram scale**: Proven on massive codebases
- **Fast**: 1.8M lines/second
- **WebAssembly support**: Browser playground

**Cons:**

- **Not drop-in**: Different from pyright/mypy
- **Medium maturity**: 58% test pass rate
- **Meta-focused**: May prioritize internal needs

## Implementation Strategy

### Phase 1: Zuban as Pyright Replacement

```python
# pyproject.toml
# REMOVE: "pyright>=1.1.403"
# ADD: "zuban>=0.1.0"

# dynamic_config.py
"zuban": {
    "id": "zuban",
    "name": "zuban",
    "repo": "https://github.com/zubanls/zuban",
    "entry": "uv run zuban",
    "args": ["check"],  # Pyright-like mode
    "tier": 3,
}
```

### Phase 2: Keep ty & pyrefly as Experimental

```python
# Already in dynamic_config.py under "experimental"
"pyrefly": {
    "id": "pyrefly",
    "experimental": True,
    "entry": "python -m pyrefly",
    "args": ["--check"],
}

"ty": {
    "id": "ty",
    "experimental": True,
    "entry": "python -m ty",
    "args": ["--check"],
}
```

### Phase 3: LSP Integration (Optional)

```python
# For zuban language server
"zuban-lsp": {
    "command": ["uv", "run", "zuban", "server"],
    "port": 6005,  # Different from pyright's 6003
}
```

## Migration Plan

### Immediate Actions (Zuban)

1. **Remove pyright** from pyproject.toml
1. **Add zuban** dependency
1. **Update dynamic_config.py** with zuban entry
1. **Update hooks.py** to use zuban instead of pyright
1. **Test with**: `zuban check crackerjack/`
1. **Verify LSP**: `zuban server` for IDE integration

### Experimental Hooks (ty & pyrefly)

1. **Keep existing** experimental hook definitions
1. **Enable with**: `python -m crackerjack --experimental-hooks`
1. **Monitor maturity** through 2025
1. **Re-evaluate** when production-ready

## Advantages of This Approach

1. **Immediate Performance Gains**: Zuban provides 20-200x speedup now
1. **Zero Migration Cost**: Drop-in replacement for pyright
1. **Future Flexibility**: ty/pyrefly remain available as they mature
1. **Risk Mitigation**: Can revert to pyright if needed
1. **Best of Both Worlds**: Production-ready replacement + experimental options

## Disadvantages & Risks

1. **License Consideration**: AGPL v3 (but commercial available)
1. **Alpha Software**: May have false positives
1. **Limited Community**: Smaller than pyright/mypy
1. **Multiple Tools**: Managing 3 type checkers adds complexity

## Complementary vs Overlapping

### Overlapping (Choose One)

- **Zuban vs Pyright**: Direct replacement, same functionality
- **ty vs Pyrefly**: Both experimental Rust-based checkers

### Complementary (Can Use Together)

- **Zuban + Experimental Hooks**: Production + preview features
- **Type Checking + Dead Code (Skylos)**: Different purposes
- **Zuban LSP + IDE**: Enhanced development experience

## Sub-Agent Selection for Implementation

### For Zuban Implementation

1. **python-pro**: Dependency updates and configuration
1. **crackerjack-architect**: Ensure proper integration patterns
1. **test-specialist**: Validate type checking accuracy
1. **critical-audit-specialist**: Review for false positives

### For Experimental Hooks

1. **refactoring-specialist**: Keep code clean for future migration
1. **monitoring-specialist**: Track performance metrics
1. **test-creation-agent**: Build compatibility tests

## Execution Timeline

### Week 1: Zuban Integration

- Day 1-2: Remove pyright, add zuban
- Day 3-4: Update configurations
- Day 5: Test and validate

### Week 2: Experimental Setup

- Day 1: Verify ty/pyrefly hooks work
- Day 2-3: Create performance benchmarks
- Day 4-5: Document usage patterns

### Week 3: Production Validation

- Full test suite with zuban
- Performance comparisons
- Team training on new tools

## Command Examples

```bash
# Current (pyright)
python -m crackerjack  # Uses pyright

# After zuban implementation
python -m crackerjack  # Uses zuban check

# With experimental hooks
python -m crackerjack --experimental-hooks  # Includes ty/pyrefly

# Zuban-specific modes
zuban check            # Pyright-like checking
zmypy                  # Mypy compatibility mode
zuban server           # LSP server
zuban mypy --config mypy.ini  # Use mypy config
```

## Decision: Recommended Approach

**Implement Zuban immediately** as pyright replacement because:

1. It's the most mature of new tools (69% test pass)
1. True drop-in replacement (no code changes)
1. Best performance/memory characteristics
1. Production LSP support

**Keep ty & pyrefly experimental** because:

1. Not production-ready (15% and 58% test pass)
1. Not drop-in replacements
1. Can evaluate as they mature through 2025
1. No cost to keeping as experimental options

This gives us immediate performance benefits while maintaining flexibility for the future.
