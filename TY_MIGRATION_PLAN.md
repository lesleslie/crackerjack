# Ty Type Checker Migration Plan

**Status**: Planning Phase (2025-2026)
**Current Type Checker**: Zuban v0.0.22 (Rust-based, stable)
**Target Type Checker**: Ty (Astral, pre-alpha v0.0.0a6)
**Recommendation**: Monitor Ty development, migrate when stable (estimated 2026)

## Executive Summary

While Ty shows superior architecture and configuration design compared to Pyrefly, it is currently in pre-alpha and not suitable for production use. Zuban remains the stable choice for Crackerjack's type checking needs.

## Current State (2025)

### Zuban (Production)

- **Version**: 0.0.22
- **Status**: Stable, production-ready
- **Performance**: 20-200x faster than Pyright
- **Integration**: Fully integrated with Crackerjack workflows
- **Configuration**: Working LSP server, strict mode enabled

### Ty (Monitoring)

- **Version**: 0.0.0a6 (pre-alpha)
- **Status**: Experimental, development only
- **Maturity**: Beta expected late 2025
- **Vendor**: Astral (uv, Ruff proven track record)
- **Architecture**: Superior configuration design, better developer experience

### Pyrefly (Not Recommended)

- **Version**: 0.32.0 (alpha)
- **Status**: Meta internal tool, limited public focus
- **Timeline**: Production target end-of-2025 (for Meta)
- **Decision**: Skip in favor of Ty

## Migration Timeline

### Phase 1: Monitoring (2025 - Current)

**Status**: In Progress ✅

**Actions Completed**:

- [x] Add ty>=0.0.0a6 to development dependencies
- [x] Create TyAdapter implementation (experimental status)
- [x] Document migration plan

**Ongoing Monitoring**:

- [ ] Track Ty release notes and version updates
- [ ] Monitor Astral blog for stability announcements
- [ ] Test Ty on sample projects (not production code)
- [ ] Compare performance metrics with Zuban periodically

### Phase 2: Beta Testing (Late 2025 - Early 2026)

**Status**: Not Started

**Triggers**:

- Ty reaches beta status (v0.1.0+)
- Astral announces production-readiness commitment
- Community adoption reaches critical mass

**Actions**:

- [ ] Enable TyAdapter in non-production environments
- [ ] Run parallel type checking (Zuban + Ty) on CI
- [ ] Compare error detection quality
- [ ] Measure performance impact
- [ ] Collect developer feedback on UX

### Phase 3: Gradual Migration (Mid-2026)

**Status**: Not Started

**Prerequisites**:

- Ty reaches stable 1.0 release
- Zero critical bugs in issue tracker
- Astral provides migration guide from other type checkers
- Performance benchmarks show ≥10x improvement over Zuban

**Actions**:

- [ ] Create comprehensive migration playbook
- [ ] Update CLAUDE.md with Ty as primary type checker
- [ ] Migrate fast hooks to use Ty
- [ ] Update QA adapter configuration
- [ ] Train team on Ty-specific patterns

### Phase 4: Full Production (Late 2026)

**Status**: Not Started

**Final Steps**:

- [ ] Replace Zuban with Ty in pyproject.toml main dependencies
- [ ] Update all documentation and tutorials
- [ ] Archive Zuban adapter (mark as deprecated)
- [ ] Remove Zuban from dependencies (breaking change)

## Configuration Strategy

### Current Zuban Configuration

```toml
[tool.zuban]
strict = true
show_error_codes = true

[tool.zuban.lsp]
host = "127.0.0.1"
port = 8677
timeout = 10.0
enable_diagnostics = true
real_time_feedback = true
```

### Proposed Ty Configuration (Future)

```toml
[tool.ty]
# Ty has superior configuration architecture
# Exact options TBD based on final release

# Expected features based on Astral patterns:
strict = true
show_error_codes = true
cache_dir = ".ty_cache"

# LSP integration (if supported)
[tool.ty.lsp]
enable = true
port = 8678  # Different from Zuban to allow parallel testing
```

### Adapter Settings Migration

```python
# Current: ZubanSettings
class ZubanSettings(ToolAdapterSettings):
    tool_name: str = "zuban"
    strict_mode: bool = False
    follow_imports: str = "normal"
    incremental: bool = True


# Future: TySettings (already implemented in crackerjack/adapters/type/ty.py)
class TySettings(ToolAdapterSettings):
    tool_name: str = "ty"
    strict_mode: bool = False
    follow_imports: str = "normal"
    incremental: bool = True
    # Additional Ty-specific settings as they become available
```

## Decision Criteria

### Why Monitor Ty?

1. **Vendor Trust**: Astral (uv, Ruff) has proven track record of delivering production-quality tools
1. **Architecture**: Superior configuration design compared to competitors
1. **Performance Promise**: Following Ruff's pattern of dramatic speed improvements
1. **Python 3.13+ Focus**: Aligns with Crackerjack's Python 3.13+ requirement

### Why Not Pyrefly?

1. **Meta Internal**: Primarily built for Meta's internal use case
1. **Limited Public Focus**: Unclear roadmap for public users
1. **Alpha Status**: Still many missing features
1. **Generic Design**: Less opinionated than Astral's focused tools

### Why Keep Zuban Now?

1. **Production Stable**: No critical bugs, works reliably
1. **Fast Performance**: Already 20-200x faster than Pyright
1. **Full Integration**: Completely integrated with Crackerjack workflows
1. **Zero Migration Risk**: No need to change what works

## Risk Management

### Technical Risks

- **Early Adoption**: Ty is pre-alpha, bugs expected
- **Breaking Changes**: API may change before 1.0
- **Performance Regression**: Initial versions may not match final performance
- **Migration Complexity**: Type checker migration can surface hidden issues

### Mitigation Strategies

1. **Parallel Testing**: Run Zuban + Ty side-by-side during beta phase
1. **Gradual Rollout**: Enable Ty incrementally (dev → CI → production)
1. **Easy Rollback**: Keep Zuban available as fallback during migration
1. **Version Pinning**: Pin Ty versions strictly during testing phases

## Success Metrics

### Ty Must Demonstrate

1. **Stability**: \<5 critical bugs per quarter after 1.0 release
1. **Performance**: ≥10x faster than Zuban on Crackerjack codebase
1. **Accuracy**: ≥98% type error detection compared to Zuban
1. **Developer Experience**: Positive feedback from team (survey >4/5)
1. **Community Adoption**: ≥1000 GitHub stars, active issue resolution

### Migration Success Indicators

1. **Zero Regressions**: No new type errors introduced during migration
1. **Performance Gain**: ≥50% reduction in CI type checking time
1. **Team Velocity**: No slowdown in development speed
1. **Quality Metrics**: Coverage and quality scores maintained or improved

## Open Questions

1. **LSP Support**: Will Ty provide LSP server like Zuban?
1. **Configuration Migration**: Will Astral provide automated migration tools?
1. **Plugin Ecosystem**: Will Ty support custom plugins/extensions?
1. **IDE Integration**: What IDEs will have first-class Ty support?

## Resources

### Official Links

- Ty GitHub: https://github.com/astral-sh/ty (when public)
- Astral Blog: https://astral.sh/blog
- Ty Documentation: TBD

### Internal References

- Adapter Implementation: `crackerjack/adapters/type/ty.py`
- Zuban Adapter: `crackerjack/adapters/type/zuban.py`
- Type Check Configuration: `pyproject.toml` [tool.zuban]

### Related Migration Guides

- Ruff Migration (Success Story): `docs/RUFF_MIGRATION.md` (if exists)
- UV Migration (Success Story): `docs/UV_MIGRATION.md` (if exists)

## Appendix: Comparison Matrix

| Feature | Zuban | Ty (Future) | Pyrefly |
|---------|-------|-------------|---------|
| Status | Stable | Pre-alpha | Alpha |
| Performance | 20-200x vs Pyright | TBD (likely 10-100x) | Unknown |
| Python 3.13+ | ✅ Yes | ✅ Yes | ✅ Yes |
| LSP Server | ✅ Yes | ❓ Unknown | ❌ No |
| Configuration | Good | Excellent | Basic |
| Vendor | Independent | Astral | Meta |
| Public Focus | ✅ High | ✅ High | ⚠️ Limited |
| Release Timeline | Released | Beta late 2025 | Stable end-2025 |
| Migration Risk | N/A | Medium | High |
| Recommendation | ✅ Use Now | 📅 Monitor | ❌ Skip |

______________________________________________________________________

**Last Updated**: 2025-01-12
**Next Review**: 2025-06-01 (check Ty beta status)
**Owner**: Crackerjack Core Team
