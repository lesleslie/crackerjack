# Ty & Pyrefly Migration Plan: Promoting to Stable and Replacing Zuban Default

## Executive Summary

This plan outlines the comprehensive migration to promote Pyrefly and Ty from experimental/beta status to stable adapters, and replace Zuban with Ty as the default type checker in Crackerjack. The migration includes removing experimental CLI commands and updating all related configurations.

**Source of Truth:** `../oneiric` is the authoritative reference for adapter behavior, defaults, and configuration alignment. Any conflicts should be resolved in favor of the Oneiric implementation.

**Confirmed Decisions:**
- Ty will be the only default type checker.
- Performance gates are not required for the default switch.
- Existing configs should be migrated to the Zuban configuration shape (not experimental flags).

**Oneiric References (source of truth):**
- `../oneiric/CLAUDE.md` documents current Zuban configuration guidance and the `mypy.ini`-only constraint.
- `../oneiric/docs/analysis/PROTOCOLS_IMPLEMENTATION_PLAN.md` notes Zuban as the active type checker for local runs (pyright is legacy).

## Current State Analysis

### Adapter Status Overview

**Zuban (Current Default):**
- Status: `STABLE`
- Enabled by default: `True`
- Location: `crackerjack/adapters/type/zuban.py`
- Integration: LSP server, comprehensive type checking
- Performance: Rust-based, 20-200x faster than traditional tools

**Ty (Experimental):**
- Status: `BETA` (was experimental, now standardized)
- Enabled by default: `False` (disabled as beta)
- Location: `crackerjack/adapters/type/ty.py`
- Features: JSON output, incremental checking, strict mode
- Performance: Python-based type verification

**Pyrefly (Experimental):**
- Status: `BETA` (was experimental, now standardized)
- Enabled by default: `False` (disabled as beta)
- Location: `crackerjack/adapters/type/pyrefly.py`
- Features: JSON output, incremental checking, strict mode
- Performance: Python-based type checking

### Experimental CLI Commands

**Current Experimental Commands:**
- `--experimental-hooks`: Enables experimental hooks (includes pyrefly and ty)
- `--enable-pyrefly`: Enables pyrefly experimental type checking
- `--enable-ty`: Enables ty experimental type verification

**Configuration Settings:**
- `experimental_hooks: bool = False`
- `enable_pyrefly: bool = False`
- `enable_ty: bool = False`

## Migration Phases

### Phase 1: Promote Pyrefly and Ty to Stable Adapters

**Objective:** Elevate Pyrefly and Ty from beta to stable status and enable Ty by default. Pyrefly should remain stable but not default.

#### Tasks:

1. **Update Adapter Status**
   - [ ] Change `MODULE_STATUS` from `AdapterStatus.BETA` to `AdapterStatus.STABLE` in:
     - `crackerjack/adapters/type/ty.py`
     - `crackerjack/adapters/type/pyrefly.py`
   - [ ] Update comments to reflect stable status

2. **Enable by Default**
   - [ ] Change `enabled=False` to `enabled=True` in `get_default_config()` for **Ty only**
   - [ ] Keep Pyrefly stable but **not** default; set explicit precedence rules
   - [ ] Remove comments about being disabled as beta

3. **Remove Experimental CLI Commands**
   - [ ] Remove `--experimental-hooks`, `--enable-pyrefly`, `--enable-ty` from:
     - `crackerjack/cli/options.py` (lines 435-450)
   - [ ] Remove corresponding configuration options from:
     - `crackerjack/config/settings.py`
     - `crackerjack/config/settings_attempt1.py`
     - `crackerjack/models/pydantic_models.py`
     - `crackerjack/models/config_adapter.py`
     - `crackerjack/models/protocols.py`

4. **Update Documentation**
   - [ ] Change status from "Experimental" to "Stable" in:
     - `crackerjack/adapters/type/README.md`
     - `crackerjack/adapters/type/__init__.py`
   - [ ] Remove references to experimental commands in:
     - `crackerjack/cli/README.md`
     - `crackerjack/config/README.md`
   - [ ] Add proper usage examples and configuration details

5. **Add Server Integration**
   - [ ] Add Ty and Pyrefly adapters to server initialization in:
     - `crackerjack/server.py` (similar to zuban pattern)
   - [ ] Document and implement selection precedence (CLI > config > default)
   - [ ] Add proper error handling and logging

### Phase 2: Replace Zuban with Ty as Default

**Objective:** Transition from Zuban to Ty as the primary type checker while maintaining Zuban as an optional alternative.

#### Tasks:

1. **Update Server Configuration**
   - [ ] Replace zuban initialization logic with ty initialization in:
     - `crackerjack/server.py` (lines 120-132)
   - [ ] Keep zuban available but not enabled by default
   - [ ] Add configuration option to choose between ty and zuban
   - [ ] Ensure only Ty is default (Pyrefly is stable but opt-in)

2. **Update Configuration Settings**
   - [ ] Add `ty_enabled: bool = True` to settings
   - [ ] Change `zuban_lsp.enabled` default to `False`
   - [ ] Add migration path for existing users (see Migration & Compatibility)

3. **Update LSP Integration**
   - [ ] Modify `crackerjack/services/lsp_client.py` to support ty alongside zuban
   - [ ] Add ty LSP service similar to zuban LSP service
   - [ ] Update fallback logic to use ty instead of zuban
   - [ ] Verify Ty LSP capability parity vs Zuban (protocol features, binary availability)

4. **Update Hooks and Executors**
   - [ ] Modify `crackerjack/hooks/lsp_hook.py` to use ty as primary type checker
   - [ ] Update `crackerjack/executors/lsp_aware_hook_executor.py` to recognize ty
   - [ ] Add ty to the list of type checking tools

### Phase 3: Cleanup Experimental References

**Objective:** Remove all remaining experimental references and ensure clean transition.

#### Tasks:

1. **Remove Experimental References**
   - [ ] Update `crackerjack/adapters/type/__init__.py` to remove "(experimental)" from descriptions
   - [ ] Remove experimental references from all README files
   - [ ] Update generated API documentation

2. **Update MCP Integration**
   - [ ] Remove experimental flags from:
     - `crackerjack/mcp/tools/workflow_executor.py` (lines 402-404)
     - `crackerjack/mcp/tools/core_tools.py` (lines 275-284)
   - [ ] Update MCP tools to use new stable adapters

3. **Update Main Entry Point**
   - [ ] Remove experimental options from:
     - `crackerjack/__main__.py` (lines 110-112, 220-222)

### Phase 4: Testing and Validation

**Objective:** Ensure all changes work correctly and meet functional requirements.

#### Tasks:

1. **Comprehensive Testing**
   - [ ] Test all three adapters (zuban, ty, pyrefly) individually
   - [ ] Test integration scenarios
   - [ ] Test LSP functionality
   - [ ] Test fallback scenarios
   - [ ] Verify experimental commands are removed and no longer functional

2. **Performance Benchmarking**
   - [ ] Optional: collect comparative benchmarks for observability only

3. **User Acceptance Testing**
   - [ ] Test with real-world codebases
   - [ ] Gather feedback on ty vs zuban
   - [ ] Address any compatibility issues
   - [ ] Verify that users can no longer enable experimental modes

### Phase 5: Documentation and Communication

**Objective:** Provide clear documentation and communication about the changes.

#### Tasks:

1. **Update Documentation**
   - [ ] Create migration guide for users
   - [ ] Update CLI reference documentation
   - [ ] Update adapter documentation with new examples
   - [ ] Update configuration documentation

2. **Create Release Notes**
   - [ ] Document breaking changes
   - [ ] Provide migration instructions
   - [ ] Highlight new features and improvements

3. **Communicate Changes**
   - [ ] Update CHANGELOG.md
   - [ ] Create GitHub release notes
   - [ ] Update project README if needed

## Implementation Details

### Files to Modify

**CLI and Configuration:**
- `crackerjack/cli/options.py` - Remove experimental CLI options
- `crackerjack/config/settings.py` - Remove experimental settings
- `crackerjack/config/settings_attempt1.py` - Remove experimental settings
- `crackerjack/models/pydantic_models.py` - Remove experimental fields
- `crackerjack/models/config_adapter.py` - Remove experimental methods
- `crackerjack/models/protocols.py` - Remove experimental fields
- `crackerjack/__main__.py` - Remove experimental parameters

**Adapter Files:**
- `crackerjack/adapters/type/ty.py` - Update status and enable by default
- `crackerjack/adapters/type/pyrefly.py` - Update status and enable by default
- `crackerjack/adapters/type/__init__.py` - Remove experimental references

**Server Integration:**
- `crackerjack/server.py` - Add ty/pyrefly initialization, replace zuban default

**MCP Integration:**
- `crackerjack/mcp/tools/workflow_executor.py` - Remove experimental flags
- `crackerjack/mcp/tools/core_tools.py` - Remove experimental methods

**Documentation:**
- `crackerjack/adapters/type/README.md` - Update status and examples
- `crackerjack/cli/README.md` - Remove experimental command references
- `crackerjack/config/README.md` - Remove experimental setting references
- Generated API documentation

## Risk Assessment and Mitigation

### Risks:

1. **Breaking Changes:** Removing CLI commands might break existing scripts
2. **Configuration Conflicts:** Existing configs with experimental flags might cause issues
3. **Performance Regression:** Ty might not be as fast as zuban (accepted risk)
4. **Compatibility Issues:** Different type checking behavior between tools
5. **User Confusion:** Changing defaults might confuse existing users
6. **Integration Issues:** LSP and other integrations might need adjustments

### Mitigation Strategies:

1. **Deprecation Warnings:** Add deprecation warnings before complete removal
2. **Configuration Migration:** Provide automated migration for existing configs to the Zuban config shape
3. **Performance Testing:** Optional benchmarking for visibility only
4. **Compatibility Layer:** Add configuration to mimic zuban behavior in ty
5. **Clear Communication:** Document changes and provide migration guides
6. **Gradual Rollout:** Keep zuban available as fallback during transition

## Timeline

### Phase 1: Promotion to Stable (1-2 weeks)
- Week 1: Update adapter status and enable by default
- Week 2: Remove experimental CLI commands and update documentation

### Phase 2: Replace Default (2-3 weeks)
- Week 3: Update server configuration and LSP integration
- Week 4: Update hooks, executors, and MCP integration
- Week 5: Comprehensive testing and validation

### Phase 3: Cleanup and Finalization (1 week)
- Week 6: Remove remaining experimental references
- Week 6: Final documentation updates and release preparation

### Phase 4: Optional Zuban Deprecation (Future)
- 1 month after successful migration: Consider deprecating zuban

## Rollback Plan

If issues arise during migration:

1. **Immediate Rollback:**
   - Revert to zuban as default
   - Restore experimental commands temporarily
   - Keep ty and pyrefly as stable but not default

2. **Issue Resolution:**
   - Address performance/compatibility issues
   - Gather user feedback and fix problems

3. **Re-attempt Migration:**
   - Plan second migration attempt
   - Implement additional safeguards
   - Provide better user communication

## Success Criteria

1. **Functional Success:**
   - All type checking functionality works with ty
   - Pyrefly and ty operate as stable adapters
   - No regression in core functionality

2. **Performance Success:**
   - Ty meets acceptable performance thresholds
   - No significant performance degradation from zuban
   - LSP integration works efficiently

3. **Compatibility Success:**
   - No regression in type checking accuracy
   - Existing workflows continue to function
   - Migration path works for existing users

4. **User Acceptance:**
   - Positive feedback from users on the change
   - Clear understanding of new adapter status
   - Successful adoption of ty as default

5. **Documentation Quality:**
   - Clear, up-to-date documentation for all adapters
   - Comprehensive migration guides
   - Accurate CLI reference documentation

6. **Clean Transition:**
   - Experimental commands successfully removed
   - All experimental settings migrated properly
   - No broken functionality from command removal

## Monitoring and Metrics

Track the following metrics post-migration:

1. **Adapter Usage:**
   - Number of users running ty vs zuban vs pyrefly
   - Frequency of type checking operations

2. **Performance Metrics:**
   - Average execution time for ty vs zuban
   - Memory usage comparisons
   - LSP response times

3. **Error Rates:**
   - Type checking failure rates
   - Configuration errors
   - Integration issues

4. **User Feedback:**
   - GitHub issues related to migration
   - User satisfaction surveys
   - Community discussions

## Checklist for Implementation

- [ ] Update adapter status in ty.py and pyrefly.py
- [ ] Enable adapters by default in get_default_config()
- [ ] Remove experimental CLI commands from options.py
- [ ] Remove experimental settings from all config files
- [ ] Update server.py to add ty/pyrefly initialization
- [ ] Replace zuban default with ty in server.py
- [ ] Update LSP integration for ty support
- [ ] Update hooks and executors for ty
- [ ] Remove experimental references from documentation
- [ ] Update MCP integration to remove experimental flags
- [ ] Update main entry point to remove experimental options
- [ ] Comprehensive testing of all adapters
- [ ] Performance benchmarking
- [ ] User acceptance testing
- [ ] Documentation updates
- [ ] Release notes and communication

## Migration Commands for Users

Provide users with clear migration commands:

```bash
# Before migration (old experimental commands - will be removed)
crackerjack run --experimental-hooks --enable-ty --enable-pyrefly

# After migration (new stable usage)
crackerjack run  # ty enabled by default

# To use zuban specifically (optional)
crackerjack run --zuban-enabled
```

## Migration & Compatibility

Maintain backward compatibility where possible:

1. **Configuration Migration:**
   - Automatically migrate `enable_ty=True`/`enable_pyrefly=True` to the **Zuban configuration shape**
   - Map experimental flags to the new stable settings and emit warnings
   - Preserve user intent: if `enable_pyrefly=True`, keep Pyrefly explicitly enabled (but not default)

2. **CLI Compatibility:**
   - Provide a deprecation window with warnings before removing experimental flags
   - On removal, show helpful error messages and suggest the new config equivalents

3. **Zuban Support:**
   - Keep zuban available as optional type checker
   - Provide clear documentation on how to enable it

This comprehensive plan ensures a smooth transition from experimental to stable status for Pyrefly and Ty adapters while replacing Zuban with Ty as the default type checker, with proper cleanup of all experimental CLI commands and configuration options.
