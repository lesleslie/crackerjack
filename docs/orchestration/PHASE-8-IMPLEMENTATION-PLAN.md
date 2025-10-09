# Phase 8: Pre-commit Infrastructure Removal - Implementation Plan

## Executive Summary

**Goal:** Remove dependency on the pre-commit framework and implement direct tool invocation while maintaining backward compatibility and all current functionality.

**Scope:** Replace pre-commit hook orchestration with native tool execution via crackerjack's orchestration layer.

**Timeline:** 1-2 weeks (6-7 week mark in overall roadmap)

**Risk Level:** HIGH - This is a breaking architectural change affecting the entire hook execution pipeline

---

## Current Architecture Analysis

### Pre-commit Dependency Chain

```
HookManager
    ↓
HookDefinition.get_command()  ← Returns: ["pre-commit", "run", "hook-name", "--all-files"]
    ↓
HookExecutor.execute()
    ↓
subprocess.run(["pre-commit", "run", ...])
    ↓
Pre-commit Framework
    ↓
Actual Tool (ruff, zuban, gitleaks, etc.)
```

### Problems with Current Architecture

1. **Unnecessary Indirection**
   - Every tool invocation goes through pre-commit
   - Adds latency and complexity
   - Limits control over tool execution

2. **Configuration Duplication**
   - Tool configs in both `.pre-commit-config.yaml` AND native configs
   - Examples: `pyproject.toml` (ruff, bandit), `mypy.ini` (zuban)
   - Risk of config drift

3. **Limited Orchestration Control**
   - Pre-commit controls execution order
   - Can't fully leverage crackerjack's triple parallelism
   - Can't implement custom retry/caching strategies per tool

4. **Dependency Overhead**
   - Requires pre-commit installation
   - Maintains `.pre-commit-config.yaml`
   - Updates require pre-commit compatibility

---

## Target Architecture

### Direct Tool Invocation

```
HookManager
    ↓
HookOrchestrator (with triple parallelism)
    ↓
AdaptiveExecutionStrategy (dependency-aware waves)
    ↓
HookDefinition.get_command()  ← Returns: ["uv", "run", "ruff", "check", "..."]
    ↓
subprocess.run(["uv", "run", "tool", ...])
    ↓
Tool Directly (ruff, zuban, gitleaks, etc.)
```

### Benefits of New Architecture

1. **Direct Control**
   - No intermediary framework
   - Full control over execution environment
   - Direct error handling

2. **Single Source of Truth**
   - Tool configurations in native files only
   - No config duplication
   - Easier maintenance

3. **Enhanced Orchestration**
   - Full triple parallelism capabilities
   - Custom retry logic per tool
   - Advanced caching strategies

4. **Reduced Dependencies**
   - Remove pre-commit from requirements
   - Simpler installation
   - Fewer breaking changes from upstream

---

## Implementation Strategy

### Phase 8.1: Tool Command Mapping (Week 1, Days 1-2)

**Goal:** Create mapping from hook names to direct tool commands

**Tasks:**

1. **Create Tool Registry**
   ```python
   # crackerjack/config/tool_commands.py

   TOOL_COMMANDS = {
       "validate-regex-patterns": [
           "uv", "run", "python", "-m",
           "crackerjack.tools.validate_regex_patterns"
       ],
       "trailing-whitespace": [
           "uv", "run", "python", "-m",
           "crackerjack.tools.trailing_whitespace"  # NEW: native implementation
       ],
       "end-of-file-fixer": [
           "uv", "run", "python", "-m",
           "crackerjack.tools.end_of_file_fixer"  # NEW: native implementation
       ],
       "check-yaml": [
           "uv", "run", "python", "-m",
           "crackerjack.tools.check_yaml"  # NEW: native implementation
       ],
       "check-toml": [
           "uv", "run", "python", "-m",
           "crackerjack.tools.check_toml"  # NEW: native implementation
       ],
       "check-added-large-files": [
           "uv", "run", "python", "-m",
           "crackerjack.tools.check_large_files"  # NEW: native implementation
       ],
       "uv-lock": ["uv", "lock", "--check"],
       "gitleaks": ["gitleaks", "detect", "--no-banner", "-v"],
       "codespell": ["uv", "run", "codespell"],
       "ruff-check": ["uv", "run", "ruff", "check", "."],
       "ruff-format": ["uv", "run", "ruff", "format", "."],
       "mdformat": ["uv", "run", "mdformat", "."],
       "zuban": ["uv", "run", "zuban", "check", "--config-file", "mypy.ini", "./crackerjack"],
       "bandit": ["uv", "run", "bandit", "-c", "pyproject.toml", "-r", "-ll", "crackerjack"],
       "skylos": ["skylos", "crackerjack", "--exclude", "tests"],
       "refurb": ["uv", "run", "refurb", "crackerjack"],
       "creosote": ["uv", "run", "creosote"],
       "complexipy": ["uv", "run", "complexipy", "-d", "low", "--max-complexity-allowed", "15", "crackerjack"],
   }
   ```

2. **Implement Native Tools for Pre-commit Hooks**

   Need to create Python implementations for hooks currently provided by `pre-commit-hooks`:
   - `trailing-whitespace`: Remove trailing whitespace from files
   - `end-of-file-fixer`: Ensure files end with newline
   - `check-yaml`: Validate YAML syntax
   - `check-toml`: Validate TOML syntax
   - `check-added-large-files`: Warn on large file additions

   **Implementation Location:** `crackerjack/tools/` directory

   **Design Pattern:** Follow existing `validate_regex_patterns.py` structure

   **Testing:** Unit tests for each tool in `tests/tools/`

3. **Update HookDefinition**
   ```python
   @dataclass
   class HookDefinition:
       name: str
       command: list[str]  # NEW: Direct command instead of pre-commit invocation
       # ... existing fields ...

       def get_command(self) -> list[str]:
           """Return direct tool command (no pre-commit wrapper)."""
           if self.command:
               return self.command

           # Fallback: use tool registry
           from crackerjack.config.tool_commands import TOOL_COMMANDS
           if self.name in TOOL_COMMANDS:
               return TOOL_COMMANDS[self.name]

           raise ValueError(f"No command defined for hook: {self.name}")
   ```

**Deliverables:**
- ✅ `crackerjack/config/tool_commands.py` - Tool command registry
- ✅ `crackerjack/tools/trailing_whitespace.py` - Native implementation
- ✅ `crackerjack/tools/end_of_file_fixer.py` - Native implementation
- ✅ `crackerjack/tools/check_yaml.py` - Native implementation
- ✅ `crackerjack/tools/check_toml.py` - Native implementation
- ✅ `crackerjack/tools/check_large_files.py` - Native implementation
- ✅ `tests/tools/test_native_tools.py` - Test suite for native tools
- ✅ Updated `HookDefinition.get_command()` method

**Success Criteria:**
- All 17 hooks have direct tool commands defined
- Native tools pass unit tests
- `HookDefinition.get_command()` returns tool commands (not pre-commit commands)

---

### Phase 8.2: Backward Compatibility Layer (Week 1, Days 3-4)

**Goal:** Maintain support for projects still using pre-commit during transition

**Tasks:**

1. **Add Legacy Mode Flag**
   ```python
   @dataclass
   class OrchestrationConfig:
       # ... existing fields ...
       use_precommit_legacy: bool = False  # NEW: Enable pre-commit mode
   ```

2. **Implement Legacy Pre-commit Execution**
   ```python
   # In HookDefinition
   def get_command(self) -> list[str]:
       if self._config.use_precommit_legacy:
           # OLD: Use pre-commit wrapper
           return self._get_precommit_command()
       else:
           # NEW: Direct tool invocation
           return self._get_direct_command()

   def _get_precommit_command(self) -> list[str]:
       """Legacy pre-commit command generation."""
       pre_commit_path = shutil.which("pre-commit") or "pre-commit"
       cmd = [pre_commit_path, "run"]
       if self.config_path:
           cmd.extend(["-c", str(self.config_path)])
       if self.manual_stage:
           cmd.extend(["--hook-stage", "manual"])
       cmd.extend([self.name, "--all-files"])
       return cmd

   def _get_direct_command(self) -> list[str]:
       """Direct tool command (new default)."""
       if self.command:
           return self.command
       from crackerjack.config.tool_commands import TOOL_COMMANDS
       return TOOL_COMMANDS[self.name]
   ```

3. **Environment Variable Override**
   ```python
   # Support CRACKERJACK_USE_PRECOMMIT=1 for easy rollback
   @classmethod
   def from_env(cls) -> OrchestrationConfig:
       # ... existing env loading ...
       use_precommit_legacy = get_bool(
           "CRACKERJACK_USE_PRECOMMIT",
           cls.use_precommit_legacy
       )
       return cls(..., use_precommit_legacy=use_precommit_legacy)
   ```

4. **Update Tests for Both Modes**
   ```python
   @pytest.mark.parametrize("use_precommit", [True, False])
   def test_hook_execution_compatibility(use_precommit: bool):
       """Test that hooks work in both legacy and direct modes."""
       config = OrchestrationConfig(use_precommit_legacy=use_precommit)
       manager = HookManagerImpl(orchestration_config=config)
       results = manager.run_hooks()
       assert all(r.status == "passed" for r in results)
   ```

**Deliverables:**
- ✅ `use_precommit_legacy` flag in OrchestrationConfig
- ✅ Legacy/direct mode switching in `HookDefinition.get_command()`
- ✅ Environment variable support for mode selection
- ✅ Parametrized tests for both execution modes

**Success Criteria:**
- Both legacy (pre-commit) and direct modes work correctly
- Mode can be switched via config or environment variable
- All existing tests pass in both modes

---

### Phase 8.3: Configuration Migration (Week 1, Day 5)

**Goal:** Remove/deprecate `.pre-commit-config.yaml` and consolidate tool configs

**Tasks:**

1. **Tool Configuration Audit**

   For each tool, identify where configuration lives:

   | Tool | Pre-commit Config | Native Config | Action |
   |------|------------------|---------------|--------|
   | ruff | `.pre-commit-config.yaml` | `pyproject.toml` [tool.ruff] | ✅ Use native |
   | bandit | `.pre-commit-config.yaml` (args) | `pyproject.toml` [tool.bandit] | ✅ Use native |
   | zuban | `.pre-commit-config.yaml` (args) | `mypy.ini` | ✅ Use native |
   | codespell | `.pre-commit-config.yaml` (exclude) | `pyproject.toml` [tool.codespell] | ✅ Use native |
   | mdformat | `.pre-commit-config.yaml` (exclude) | None | ⚠️ Add to pyproject.toml |
   | complexipy | `.pre-commit-config.yaml` (args) | None | ⚠️ Add to pyproject.toml |
   | refurb | `.pre-commit-config.yaml` (files) | None | ⚠️ Add to pyproject.toml |
   | creosote | `.pre-commit-config.yaml` (exclude) | None | ⚠️ Add to pyproject.toml |
   | skylos | `.pre-commit-config.yaml` (args) | None | ⚠️ Add to pyproject.toml |
   | gitleaks | `.pre-commit-config.yaml` (exclude) | `.gitleaksignore` | ✅ Use native |

2. **Migrate Configurations to pyproject.toml**
   ```toml
   # pyproject.toml additions

   [tool.mdformat]
   wrap = 100
   number = true

   [tool.complexipy]
   max_complexity = 15

   [tool.refurb]
   python_version = "3.13"

   [tool.creosote]
   paths = ["crackerjack"]
   deps-file = "pyproject.toml"
   exclude-deps = ["pytest", "hypothesis"]

   [tool.skylos]
   paths = ["crackerjack"]
   exclude = ["tests"]
   ```

3. **Create Migration Script**
   ```bash
   # scripts/migrate_from_precommit.py

   # Reads .pre-commit-config.yaml
   # Extracts tool configurations
   # Writes to appropriate native config files
   # Creates backup of .pre-commit-config.yaml
   ```

4. **Update Documentation**
   - Update README.md: Remove pre-commit installation instructions
   - Update CONTRIBUTING.md: Document direct tool configuration
   - Add MIGRATION-GUIDE.md: Step-by-step migration for existing users

**Deliverables:**
- ✅ Consolidated tool configurations in `pyproject.toml`
- ✅ Migration script: `scripts/migrate_from_precommit.py`
- ✅ Updated documentation
- ✅ `.pre-commit-config.yaml` marked as deprecated

**Success Criteria:**
- All tool configurations consolidated in native config files
- No loss of configuration during migration
- Migration script tested on sample projects

---

### Phase 8.4: Hook Definition Updates (Week 2, Days 1-2)

**Goal:** Update FAST_HOOKS and COMPREHENSIVE_HOOKS with direct commands

**Tasks:**

1. **Update Fast Hooks**
   ```python
   FAST_HOOKS = [
       HookDefinition(
           name="validate-regex-patterns",
           command=["uv", "run", "python", "-m", "crackerjack.tools.validate_regex_patterns"],
           is_formatting=True,
           timeout=30,
           retry_on_failure=True,
           security_level=SecurityLevel.HIGH,
       ),
       HookDefinition(
           name="trailing-whitespace",
           command=["uv", "run", "python", "-m", "crackerjack.tools.trailing_whitespace"],
           is_formatting=True,
           retry_on_failure=True,
           security_level=SecurityLevel.LOW,
       ),
       # ... rest of hooks with direct commands
   ]
   ```

2. **Update Comprehensive Hooks**
   ```python
   COMPREHENSIVE_HOOKS = [
       HookDefinition(
           name="zuban",
           command=["uv", "run", "zuban", "check", "--config-file", "mypy.ini", "./crackerjack"],
           timeout=30,
           stage=HookStage.COMPREHENSIVE,
           security_level=SecurityLevel.CRITICAL,
       ),
       # ... rest of hooks with direct commands
   ]
   ```

3. **Remove Pre-commit Detection Logic**
   ```python
   # REMOVE THIS METHOD from HookDefinition:
   def get_command(self) -> list[str]:
       import shutil
       from pathlib import Path

       pre_commit_path = None  # ← Remove this entire method
       current_dir = Path.cwd()
       # ... etc
   ```

4. **Simplify get_command()**
   ```python
   def get_command(self) -> list[str]:
       """Return the command to execute this hook."""
       return self.command  # Simple and direct!
   ```

**Deliverables:**
- ✅ Updated `FAST_HOOKS` with direct commands
- ✅ Updated `COMPREHENSIVE_HOOKS` with direct commands
- ✅ Simplified `HookDefinition.get_command()` method
- ✅ Removed pre-commit-specific logic

**Success Criteria:**
- All hooks defined with direct tool commands
- No references to pre-commit in hook definitions
- `get_command()` is simple and maintainable

---

### Phase 8.5: Dependency Cleanup (Week 2, Day 3)

**Goal:** Remove pre-commit from project dependencies

**Tasks:**

1. **Remove from pyproject.toml**
   ```toml
   # REMOVE:
   [tool.uv]
   dev-dependencies = [
       # "pre-commit>=3.5.0",  ← Remove this line
       "pytest>=8.0.0",
       # ... other deps
   ]
   ```

2. **Remove Pre-commit Config File**
   ```bash
   # Rename for backup (don't delete immediately)
   mv .pre-commit-config.yaml .pre-commit-config.yaml.bak

   # Add to .gitignore
   echo ".pre-commit-config.yaml.bak" >> .gitignore
   ```

3. **Update Installation Scripts**
   ```bash
   # scripts/setup.sh

   # REMOVE:
   # uv run pre-commit install

   # No longer needed with direct tool invocation
   ```

4. **Update CI/CD Pipelines**
   ```yaml
   # .github/workflows/quality.yml

   # BEFORE:
   # - name: Install pre-commit
   #   run: uv sync --dev
   # - name: Run pre-commit
   #   run: uv run pre-commit run --all-files

   # AFTER:
   - name: Install dependencies
     run: uv sync --dev
   - name: Run quality checks
     run: uv run python -m crackerjack --run-tests
   ```

**Deliverables:**
- ✅ Removed `pre-commit` from `pyproject.toml`
- ✅ Archived `.pre-commit-config.yaml`
- ✅ Updated setup/installation scripts
- ✅ Updated CI/CD pipelines

**Success Criteria:**
- `uv sync` no longer installs pre-commit
- Project runs successfully without pre-commit
- CI/CD passes without pre-commit

---

### Phase 8.6: Testing & Validation (Week 2, Days 4-5)

**Goal:** Comprehensive testing of direct tool invocation

**Tasks:**

1. **Update Existing Tests**
   - Review all tests that mock/interact with pre-commit
   - Update to test direct tool invocation
   - Ensure integration tests cover new execution path

2. **Add Direct Invocation Tests**
   ```python
   # tests/config/test_tool_commands.py

   def test_all_hooks_have_commands():
       """Ensure all hooks have direct tool commands defined."""
       from crackerjack.config.tool_commands import TOOL_COMMANDS
       from crackerjack.config.hooks import FAST_HOOKS, COMPREHENSIVE_HOOKS

       all_hooks = FAST_HOOKS + COMPREHENSIVE_HOOKS
       for hook in all_hooks:
           assert hook.name in TOOL_COMMANDS or hook.command

   def test_tool_commands_are_valid():
       """Ensure all tool commands are executable."""
       from crackerjack.config.tool_commands import TOOL_COMMANDS
       import shutil

       for name, cmd in TOOL_COMMANDS.items():
           # First element should be an executable
           assert shutil.which(cmd[0]) is not None, f"{name}: {cmd[0]} not found"
   ```

3. **End-to-End Integration Tests**
   ```python
   def test_full_workflow_without_precommit():
       """Test complete workflow without pre-commit dependency."""
       # Ensure pre-commit is not installed/available
       with patch('shutil.which', return_value=None):
           manager = HookManagerImpl()
           results = manager.run_hooks()
           assert len(results) > 0
           # Should still work via direct tool invocation
   ```

4. **Performance Comparison**
   ```python
   def test_direct_invocation_faster_than_precommit():
       """Verify direct invocation is faster than pre-commit wrapper."""
       # Measure execution time with direct invocation
       # Should be measurably faster (no pre-commit overhead)
   ```

**Deliverables:**
- ✅ Updated test suite for direct invocation
- ✅ New tests for tool command registry
- ✅ Integration tests without pre-commit
- ✅ Performance benchmarks

**Success Criteria:**
- All tests pass without pre-commit installed
- Direct invocation is faster than pre-commit mode
- Test coverage maintained or improved

---

### Phase 8.7: Documentation & Migration Guide (Week 2, Day 6)

**Goal:** Comprehensive documentation for Phase 8 changes

**Tasks:**

1. **Update Main README**
   - Remove pre-commit installation section
   - Add "Tool Configuration" section
   - Update quick start guide

2. **Create Migration Guide**
   ```markdown
   # MIGRATION-GUIDE-PHASE-8.md

   ## Upgrading from Pre-commit to Direct Tool Invocation

   ### Why This Change?
   - Faster execution (no pre-commit overhead)
   - Simpler configuration (single source of truth)
   - Better orchestration control
   - Fewer dependencies

   ### Migration Steps

   1. **Backup your configuration**
      ```bash
      cp .pre-commit-config.yaml .pre-commit-config.yaml.bak
      ```

   2. **Run migration script**
      ```bash
      uv run python scripts/migrate_from_precommit.py
      ```

   3. **Test the migration**
      ```bash
      uv run python -m crackerjack --run-tests
      ```

   4. **Remove pre-commit**
      ```bash
      uv remove pre-commit
      ```

   ### Rollback Plan

   If you encounter issues:
   ```bash
   # Enable legacy mode temporarily
   export CRACKERJACK_USE_PRECOMMIT=1

   # Or add to config
   echo "orchestration:\n  use_precommit_legacy: true" >> .crackerjack.yaml
   ```

   ### Breaking Changes
   - `.pre-commit-config.yaml` no longer used
   - Tool configurations must be in native files
   - `pre-commit install` no longer required

   ### Support
   - Report issues: [GitHub Issues](link)
   - Discussion: [GitHub Discussions](link)
   ```

3. **Update Architecture Documentation**
   - Document new direct invocation architecture
   - Update architecture diagrams
   - Add performance benchmarks

4. **Create Upgrade Checklist**
   ```markdown
   ## Phase 8 Upgrade Checklist

   - [ ] Backup `.pre-commit-config.yaml`
   - [ ] Run migration script
   - [ ] Review tool configurations in `pyproject.toml`
   - [ ] Test all hooks: `uv run python -m crackerjack`
   - [ ] Test with tests: `uv run python -m crackerjack --run-tests`
   - [ ] Update CI/CD pipelines
   - [ ] Remove pre-commit from dependencies
   - [ ] Delete `.pre-commit-config.yaml`
   - [ ] Commit changes
   - [ ] Monitor for issues
   ```

**Deliverables:**
- ✅ Updated README.md
- ✅ MIGRATION-GUIDE-PHASE-8.md
- ✅ Updated architecture documentation
- ✅ Upgrade checklist

**Success Criteria:**
- Clear migration path documented
- All breaking changes documented
- Rollback procedure available
- User can complete migration independently

---

## Risk Assessment & Mitigation

### High Risks

1. **Breaking Change for Existing Users**
   - **Risk:** Projects using crackerjack with pre-commit stop working
   - **Mitigation:**
     - Provide backward compatibility mode (`use_precommit_legacy`)
     - Clear migration guide with rollback instructions
     - Gradual rollout with deprecation warnings

2. **Tool Configuration Loss**
   - **Risk:** Tool configurations not properly migrated from pre-commit
   - **Mitigation:**
     - Automated migration script with validation
     - Manual review checklist
     - Backup original configurations

3. **Performance Regression**
   - **Risk:** Direct invocation slower than pre-commit caching
   - **Mitigation:**
     - Implement crackerjack's own tool result caching
     - Benchmark before/after migration
     - Optimize slow tools individually

### Medium Risks

4. **Native Tool Implementation Bugs**
   - **Risk:** New Python implementations of pre-commit hooks have bugs
   - **Mitigation:**
     - Comprehensive unit tests for each tool
     - Integration tests comparing old vs new behavior
     - Gradual rollout with canary testing

5. **CI/CD Pipeline Breakage**
   - **Risk:** CI pipelines break after removing pre-commit
   - **Mitigation:**
     - Test in isolated CI environment first
     - Provide updated CI templates
     - Document common CI configurations

### Low Risks

6. **Documentation Gaps**
   - **Risk:** Users confused by migration process
   - **Mitigation:**
     - Comprehensive migration guide
     - FAQ section
     - Example migrations

---

## Success Criteria

### Must Have (P0)
- ✅ All hooks execute via direct tool invocation
- ✅ Zero test failures after migration
- ✅ Backward compatibility mode available
- ✅ Migration script tested and working
- ✅ Documentation complete

### Should Have (P1)
- ✅ Performance improvement measured and documented
- ✅ All tool configurations in native files
- ✅ CI/CD templates updated
- ✅ Native implementations for pre-commit-hooks

### Nice to Have (P2)
- ⚠️ Automated configuration validation
- ⚠️ Tool result caching (future enhancement)
- ⚠️ Telemetry for adoption tracking

---

## Rollout Plan

### Phase 1: Internal Testing (Week 2, Day 7)
- Test on crackerjack codebase itself
- Validate all hooks work correctly
- Measure performance improvements

### Phase 2: Beta Testing (Week 3, Day 1-2)
- Release beta version with both modes
- Gather feedback from early adopters
- Fix critical issues

### Phase 3: General Release (Week 3, Day 3)
- Release as minor version (e.g., 0.X.0)
- Include deprecation warnings for pre-commit mode
- Provide migration guide

### Phase 4: Legacy Deprecation (Week 4)
- Announce timeline for removing legacy mode
- Final migration support
- Remove legacy code in next major version

---

## Performance Targets

### Execution Time Improvements

| Scenario | Pre-commit Mode | Direct Mode | Target Improvement |
|----------|----------------|-------------|-------------------|
| Fast hooks only | 5-7s | 3-5s | **~30% faster** |
| Comprehensive hooks | 30-40s | 20-30s | **~30% faster** |
| Full workflow | 35-45s | 23-35s | **~30% faster** |

### Overhead Reduction

| Metric | Pre-commit Mode | Direct Mode | Improvement |
|--------|----------------|-------------|-------------|
| Process spawning | ~2-3s | ~0.5s | **~75% reduction** |
| Config parsing | ~1s | ~0.1s | **~90% reduction** |
| Hook resolution | ~1s | ~0s | **~100% reduction** |

---

## Dependencies

### New Dependencies (None)
- All tools already in `pyproject.toml` as direct dependencies
- No new external dependencies required

### Removed Dependencies
- `pre-commit>=3.5.0` - No longer required

### Tool Version Compatibility
- Ensure all tools work when invoked directly
- May need to update tool versions for direct invocation compatibility

---

## Testing Strategy

### Unit Tests
- Test each native tool implementation individually
- Test tool command registry
- Test backward compatibility mode

### Integration Tests
- Test full workflow without pre-commit
- Test migration script
- Test configuration loading

### Performance Tests
- Benchmark direct invocation vs pre-commit
- Measure overhead reduction
- Validate performance targets

### Regression Tests
- Ensure all existing functionality preserved
- Verify all hooks produce same results
- Check error handling

---

## Monitoring & Rollback

### Monitoring
- Track execution times before/after
- Monitor error rates
- Collect user feedback

### Rollback Procedures

**Immediate Rollback (Critical Issues)**
```bash
# Enable legacy mode via environment variable
export CRACKERJACK_USE_PRECOMMIT=1

# Or restore .pre-commit-config.yaml
mv .pre-commit-config.yaml.bak .pre-commit-config.yaml
uv add pre-commit>=3.5.0
```

**Gradual Rollback (User Issues)**
```yaml
# Add to .crackerjack.yaml
orchestration:
  use_precommit_legacy: true
```

---

## Timeline Summary

| Week | Days | Phase | Deliverables |
|------|------|-------|-------------|
| **Week 1** | 1-2 | Tool Command Mapping | Tool registry, native tools |
| **Week 1** | 3-4 | Backward Compatibility | Legacy mode, dual-mode tests |
| **Week 1** | 5 | Configuration Migration | Config consolidation, migration script |
| **Week 2** | 1-2 | Hook Definition Updates | Direct commands, simplified code |
| **Week 2** | 3 | Dependency Cleanup | Remove pre-commit, update scripts |
| **Week 2** | 4-5 | Testing & Validation | Comprehensive test suite |
| **Week 2** | 6 | Documentation | Migration guide, updated docs |
| **Week 2** | 7 | Internal Testing | Self-validation on crackerjack |
| **Week 3** | 1-2 | Beta Testing | Early adopter feedback |
| **Week 3** | 3+ | General Release | Public release |

**Total Duration:** 2-3 weeks

---

## Conclusion

Phase 8 represents a significant architectural improvement:
- **Removes unnecessary indirection** from pre-commit framework
- **Simplifies configuration** with single source of truth
- **Improves performance** by ~30% across all scenarios
- **Enhances orchestration control** with direct tool invocation
- **Maintains backward compatibility** during transition period

The migration is carefully planned with:
- Comprehensive testing strategy
- Clear rollback procedures
- Detailed documentation
- Gradual rollout plan

**Phase 8 Status:** Ready to begin implementation 🚀
