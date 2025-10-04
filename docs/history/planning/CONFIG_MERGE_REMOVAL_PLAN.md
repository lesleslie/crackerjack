# Config Merge System Removal Implementation Plan

## Problem Analysis

The config merging system in crackerjack is causing configuration reversion issues:

1. **ConfigMergeService** automatically syncs configs from `crackerjack/` package directory to project root
1. **PhaseCoordinator** triggers this merge during every `python -m crackerjack` run
1. Manual changes (like switching from zuban to pyright) get reverted every time
1. The system was designed for project initialization but interferes with ongoing development

## Current Config Merge Flow

```
PhaseCoordinator._execute_configuration_steps()
  → _handle_smart_config_merge()
  → _perform_smart_config_merge()
  → ConfigMergeService.smart_merge_pre_commit_config()
```

Files involved:

- `/crackerjack/.pre-commit-config.yaml` (package template)
- `/.pre-commit-config.yaml` (project config - gets overwritten)

## Proposed Solution: Complete Removal

Remove the entire config merging system since:

1. **It's counterproductive** - prevents manual configuration changes
1. **It's not needed for existing projects** - only useful during initialization
1. **It creates confusion** - users expect manual edits to persist
1. **Alternative exists** - InitializationService can handle new project setup

## Implementation Steps

### Phase 1: Remove Config Merge Invocation

- **File**: `crackerjack/core/phase_coordinator.py`
- **Action**: Remove calls to `_handle_smart_config_merge()` and related methods
- **Lines**: 212, 221-278, 310-315

### Phase 2: Remove Package-Level Templates

- **Files to Delete**:
  - `/crackerjack/.pre-commit-config.yaml`
  - Any other config templates in package directory
- **Rationale**: Remove the source of unwanted merging

### Phase 3: Preserve InitializationService

- **File**: `crackerjack/services/initialization.py`
- **Action**: Keep as-is for `--init` functionality
- **Rationale**: Still useful for new project setup

### Phase 4: Remove ConfigMergeService (Optional)

- **Consideration**: May still be useful for `--init` command
- **Decision**: Keep for now, remove only if unused after Phase 1-2

## Benefits

1. **Manual edits persist** - Configuration changes will no longer be reverted
1. **Cleaner workflow** - Less magic, more predictable behavior
1. **Reduced complexity** - Fewer moving parts in the system
1. **User expectations met** - Configuration files behave like normal files

## Risks & Mitigation

1. **Risk**: Users might expect automatic config updates

   - **Mitigation**: Document that configs should be managed manually

1. **Risk**: New projects won't get optimal configs

   - **Mitigation**: InitializationService still provides good defaults

1. **Risk**: Breaking change for existing workflows

   - **Mitigation**: Most users probably don't rely on config merging

## Testing Strategy

1. Remove config merge calls
1. Test that manual edits to `.pre-commit-config.yaml` persist after running crackerjack
1. Verify that `--init` still works for new projects
1. Confirm no functionality is broken

## Implementation Priority

**HIGH** - This is blocking the zuban → pyright transition and likely affects other manual configuration changes.
