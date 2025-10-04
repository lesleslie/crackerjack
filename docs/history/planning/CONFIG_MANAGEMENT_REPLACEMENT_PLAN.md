# Config Management System Replacement Plan

## Executive Summary

Replace the current ConfigMergeService and file-copying system with a cleaner, version-based pull configuration system that eliminates file copying, gives users control over updates, and properly manages pre-commit caching.

## Current System Problems

### 1. File Copying Overhead

- **Issue**: 6 config files are copied TO the package directory on every `python -m crackerjack` run
- **Files copied**: `.pre-commit-config.yaml`, `CLAUDE.md`, `RULES.md`, `.gitignore`, `example.mcp.json`, `uv.lock`
- **Location**: `_copy_config_files_to_package()` in PhaseCoordinator (lines 251-295)
- **Impact**: Unnecessary I/O, confusing self-referential copying for crackerjack itself

### 2. Dual Configuration Systems

- **ConfigMergeService**: Automatically merges configs from package templates to project
- **DynamicConfigGenerator**: Dynamically generates `.pre-commit-config.yaml`
- **Problem**: Both systems can overwrite manual changes, causing conflicts

### 3. Pre-commit Cache Issues

- **Location**: `~/.cache/pre-commit/`
- **Problem**: Cached environments don't refresh when config changes
- **Symptom**: Old hooks (like zuban) still appear even after config updates
- **Current workaround**: Manual `pre-commit clean && pre-commit install`

### 4. Forced Automatic Updates

- **Problem**: ConfigMergeService forces "smart merges" without user consent
- **Impact**: Manual configuration changes get reverted
- **Example**: Switching from zuban to pyright gets undone on next run

## Proposed Solution: Version-Based Pull Configuration System

### Core Principles

1. **No file copying**: Templates stored as Python data structures
1. **Pull-based updates**: Users explicitly request config updates
1. **Version tracking**: Each config has a version number
1. **Diff visibility**: Show changes before applying
1. **Cache management**: Automatic pre-commit cache invalidation

## Implementation Architecture

### 1. ConfigTemplateService (New)

```python
# crackerjack/services/config_template.py


class ConfigTemplateService:
    """Version-based configuration template management."""

    CONFIG_VERSIONS = {
        "pre-commit": "3.0.0",
        "pyproject": "1.2.0",
        "gitignore": "1.0.0",
    }

    def get_template(self, config_type: str, version: str = None) -> dict:
        """Get config template as structured data."""
        pass

    def check_updates(self, project_path: Path) -> dict[str, UpdateInfo]:
        """Check if newer config versions are available."""
        pass

    def generate_diff(self, config_type: str, current: dict, new: dict) -> str:
        """Generate readable diff between configs."""
        pass

    def apply_update(
        self, config_type: str, project_path: Path, interactive: bool = False
    ) -> bool:
        """Apply config update with optional interactive mode."""
        pass
```

### 2. Config Templates as Code

```python
# crackerjack/config_templates/__init__.py

PRE_COMMIT_TEMPLATE = {
    "version": "3.0.0",
    "repos": [
        {
            "repo": "local",
            "hooks": [
                {
                    "id": "validate-regex-patterns",
                    "name": "validate-regex-patterns",
                    "entry": "uv run python -m crackerjack.tools.validate_regex_patterns",
                    "language": "system",
                    "files": r"\.py$",
                }
            ],
        }
    ],
}

PYPROJECT_TEMPLATE = {
    "version": "1.2.0",
    "tool": {
        "ruff": {
            "target-version": "py313",
            "line-length": 88,
            # ... rest of config
        }
    },
}
```

### 3. New CLI Commands

```bash
# Check for available updates
python -m crackerjack --check-config-updates

# Show diff between current and latest
python -m crackerjack --diff-config [config-name]

# Apply updates (with confirmation)
python -m crackerjack --apply-config-updates

# Apply updates interactively (choose which to apply)
python -m crackerjack --apply-config-updates --interactive

# Force cache refresh
python -m crackerjack --refresh-cache
```

### 4. Config Version Tracking

```yaml
# .crackerjack-config.yaml (new file in project root)
version: "1.0.0"
configs:
  pre-commit:
    version: "3.0.0"
    last_updated: "2025-01-12"
    pinned: false
  pyproject:
    version: "1.2.0"
    last_updated: "2025-01-12"
    pinned: true  # Don't auto-suggest updates
```

### 5. Pre-commit Cache Management

```python
class PreCommitCacheManager:
    """Manage pre-commit cache to prevent staleness."""

    def get_config_hash(self, config_path: Path) -> str:
        """Generate hash of current config."""
        pass

    def should_refresh_cache(self, config_path: Path) -> bool:
        """Check if cache needs refresh based on config changes."""
        pass

    def refresh_cache(self) -> bool:
        """Run pre-commit clean and gc."""
        subprocess.run(["pre-commit", "clean"])
        subprocess.run(["pre-commit", "gc"])
        subprocess.run(["pre-commit", "install"])
        return True
```

## Migration Plan

### Phase 1: Add New System (Week 1)

1. Create ConfigTemplateService
1. Convert existing configs to template format
1. Add version tracking
1. Implement diff generation
1. Add new CLI commands

### Phase 2: Integration (Week 2)

1. Add PreCommitCacheManager
1. Integrate cache management with updates
1. Add config version tracking file
1. Update documentation

### Phase 3: Deprecate Old System (Week 3)

1. Mark ConfigMergeService as deprecated
1. Remove `_copy_config_files_to_package` from PhaseCoordinator
1. Update InitializationService to use new system
1. Add migration warnings

### Phase 4: Remove Old System (Week 4)

1. Delete ConfigMergeService
1. Clean up all smart merge code
1. Remove package-level config templates
1. Final testing and validation

## Benefits

### For Crackerjack Project

- No more self-referential file copying
- Cleaner codebase without merge logic
- Faster execution (no I/O for copying)

### For Other Projects Using Crackerjack

- Control over when to update configs
- See changes before applying
- Pin configs to specific versions
- No surprise overwrites

### For Development

- Pre-commit cache properly managed
- No more stale hook issues
- Faster iteration cycles

## Implementation Checklist

- [ ] Create ConfigTemplateService class
- [ ] Convert configs to Python templates
- [ ] Add version tracking system
- [ ] Implement diff generation
- [ ] Add new CLI commands
- [ ] Create PreCommitCacheManager
- [ ] Add config hash tracking
- [ ] Implement update mechanism
- [ ] Add interactive update mode
- [ ] Create migration documentation
- [ ] Remove \_copy_config_files_to_package
- [ ] Deprecate ConfigMergeService
- [ ] Update InitializationService
- [ ] Add tests for new system
- [ ] Update user documentation

## Success Criteria

1. **Zero file copying**: No configs copied to package directory
1. **User control**: Updates only when explicitly requested
1. **Version visibility**: Clear tracking of config versions
1. **Cache freshness**: Pre-commit cache automatically managed
1. **Backward compatibility**: Smooth migration path

## Risk Mitigation

1. **Risk**: Breaking existing projects

   - **Mitigation**: Gradual migration with deprecation warnings

1. **Risk**: Complex diff generation

   - **Mitigation**: Start with simple text diffs, enhance later

1. **Risk**: User confusion

   - **Mitigation**: Clear documentation and migration guide

## Timeline

- **Week 1**: Core implementation
- **Week 2**: Integration and testing
- **Week 3**: Migration and deprecation
- **Week 4**: Cleanup and documentation

## Next Steps

1. Review and approve this plan
1. Create feature branch
1. Begin implementation with ConfigTemplateService
1. Regular testing during development
1. User acceptance testing before merge
