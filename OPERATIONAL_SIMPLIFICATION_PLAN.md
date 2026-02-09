# Crackerjack Operational Simplification Plan

**Track 4: Ecosystem Improvement Plan**

## Objective

Improve the operational simplicity of Crackerjack by implementing better defaults, configuration profiles, progressive complexity, and enhanced documentation.

## Current State Analysis

### Strengths
- Comprehensive configuration system with Pydantic settings
- Rich CLI with extensive options
- Good documentation structure (QUICKSTART.md exists)
- Modular architecture with adapters and managers

### Pain Points
- Overwhelming CLI options (100+ parameters in `run` command)
- No preset profiles for common workflows
- Missing sensible defaults in core module
- No progressive complexity guidance
- Configuration scattered across multiple files

## Implementation Plan

### Phase 1: Add Sensible Defaults (1 day)
**Status**: Pending

**Tasks**:
1. Create `crackerjack/core/defaults.py` module
2. Define production-ready defaults for common settings
3. Integrate defaults into settings loading
4. Add validation for default values

**Deliverables**:
- `/Users/les/Projects/crackerjack/crackerjack/core/defaults.py`
- Updated settings integration
- Tests for default values

**Success Criteria**:
- ✅ Sensible defaults defined
- ✅ Defaults automatically applied
- ✅ No breaking changes to existing configs

### Phase 2: Create Configuration Profiles (1 day)
**Status**: Pending

**Tasks**:
1. Create profile system with 3 presets:
   - `quick`: Fast checks (ruff only, 1 minute)
   - `standard`: Standard checks (ruff + pytest + coverage, 5 minutes)
   - `comprehensive`: All checks (15 minutes)
2. Create profile YAML files in `settings/profiles/`
3. Add profile loading logic
4. Add `--profile` CLI option

**Deliverables**:
- `/Users/les/Projects/crackerjack/settings/profiles/quick.yaml`
- `/Users/les/Projects/crackerjack/settings/profiles/standard.yaml`
- `/Users/les/Projects/crackerjack/settings/profiles/comprehensive.yaml`
- Profile loading system
- CLI integration

**Success Criteria**:
- ✅ 3 profile presets created
- ✅ Profile loading works
- ✅ CLI `--profile` option functional
- ✅ Can override profile settings with CLI args

### Phase 3: CLI Improvements (1 day)
**Status**: Pending

**Tasks**:
1. Add `--profile` option to `run` command
2. Add `--quick` and `--thorough` shortcuts
3. Improve help text and error messages
4. Add profile validation

**Deliverables**:
- Updated `crackerjack/__main__.py`
- Updated `crackerjack/cli/options.py`
- Better error messages

**Success Criteria**:
- ✅ `--profile` option works
- ✅ `--quick` = `--profile quick`
- ✅ `--thorough` = `--profile comprehensive`
- ✅ Help text is clear and concise

### Phase 4: Progressive Documentation (2 days)
**Status**: Pending

**Tasks**:
1. Create `docs/guides/progressive-complexity.md`
2. Update QUICKSTART.md with progressive levels
3. Add profile usage examples
4. Create decision tree for choosing profiles

**Deliverables**:
- `/Users/les/Projects/crackerjack/docs/guides/progressive-complexity.md`
- Updated `/Users/les/Projects/crackerjack/QUICKSTART.md`
- Profile decision tree

**Success Criteria**:
- ✅ Progressive complexity guide created
- ✅ Quickstart updated with 3 levels
- ✅ Clear decision tree for profile selection
- ✅ Examples for each level

## Timeline

- **Phase 1**: Day 1 (Sensible Defaults)
- **Phase 2**: Day 2 (Configuration Profiles)
- **Phase 3**: Day 3 (CLI Improvements)
- **Phase 4**: Days 4-5 (Progressive Documentation)

**Total**: 5 days

## Key Design Decisions

### 1. Default Values Strategy
- Use conservative defaults that work for 80% of projects
- Allow easy override via CLI args or config files
- Document rationale for each default

### 2. Profile Design
- **Quick**: Fast feedback during development (< 1 minute)
  - Ruff linting only
  - No tests, no coverage
  - Parallel execution enabled

- **Standard**: Balanced checks for pre-commit (2-5 minutes)
  - Ruff + pytest + coverage
  - Standard quality gates
  - Incremental tests

- **Comprehensive**: Full CI/CD pipeline (10-15 minutes)
  - All checks enabled
  - Full test suite
  - Security scanning
  - Complexity analysis

### 3. CLI Option Priority
1. Explicit CLI arguments (highest)
2. Profile settings
3. Project config (`crackerjack.toml`)
4. User config (`~/.crackerjack/config.toml`)
5. Defaults (lowest)

### 4. Backward Compatibility
- All changes are additive
- Existing configs continue to work
- New options are opt-in
- No breaking changes to CLI

## Success Metrics

### Quantitative
- Time to first successful run: < 30 seconds (from 2+ minutes)
- Documentation comprehension: 3 levels vs flat structure
- CLI option discovery: 3 profiles vs 100+ options

### Qualitative
- User confidence in default settings
- Clearer mental model of Crackerjack capabilities
- Easier onboarding for new users
- Better progressive disclosure of complexity

## Risks & Mitigation

### Risk 1: Default values don't fit all projects
**Mitigation**: Make defaults easily overridable, document rationale

### Risk 2: Profiles too rigid for custom workflows
**Mitigation**: Allow profile inheritance and partial overrides

### Risk 3: Too many profiles causing decision paralysis
**Mitigation**: Start with 3 well-defined profiles, add more based on user feedback

### Risk 4: Breaking existing configurations
**Mitigation**: Additive changes only, extensive testing

## Testing Strategy

### Unit Tests
- Default value validation
- Profile loading logic
- CLI option precedence

### Integration Tests
- End-to-end profile execution
- Profile override behavior
- Error handling for invalid profiles

### Manual Testing
- User experience walkthrough
- Documentation clarity
- Profile selection decision tree

## Next Steps

1. **Start Phase 1**: Create `defaults.py` module
2. **Define default values**: Research industry standards
3. **Create profile system**: Design profile inheritance
4. **Update CLI**: Add profile options
5. **Write documentation**: Progressive complexity guide

## Open Questions

1. Should profiles be versioned?
2. How to handle profile updates when Crackerjack upgrades?
3. Should we allow custom user profiles in `~/.crackerjack/profiles/`?
4. How to profile performance for each preset?

## References

- Current config: `/Users/les/Projects/crackerjack/settings/crackerjack.yaml`
- Current CLI: `/Users/les/Projects/crackerjack/crackerjack/__main__.py`
- Settings module: `/Users/les/Projects/crackerjack/crackerjack/config/settings.py`
- Existing docs: `/Users/les/Projects/crackerjack/QUICKSTART.md`

---

**Last Updated**: 2025-02-09
**Status**: Planning Complete, Ready to Implement
**Owner**: UX Researcher Agent
