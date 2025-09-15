# Complexity Refactoring Implementation Plan

## Overview

Systematic refactoring of two high-complexity functions identified by complexipy to bring them under the threshold of 15.

## Current Violations

### 1. ConfigTemplateService.__init__ (config_template.py)

- **Current Complexity**: 19
- **Target**: ≤15
- **Location**: Lines 35-38 and associated `_load_config_templates` method (lines 40-148)

### 2. handle_config_updates (handlers.py)

- **Current Complexity**: 24
- **Target**: ≤15
- **Location**: Lines 357-438

## Refactoring Strategy

### ConfigTemplateService Refactoring

The complexity stems from the massive `_load_config_templates` method containing inline configuration data. The refactoring will:

1. **Extract Configuration Data**: Move inline config data to separate private methods
1. **Create Template Builders**: Individual methods for each template type
1. **Simplify Main Method**: Reduce `_load_config_templates` to orchestration only

**Planned Helper Methods**:

- `_create_precommit_template() -> ConfigVersion`
- `_create_pyproject_template() -> ConfigVersion`
- `_build_precommit_hooks() -> list[dict]`
- `_build_precommit_repos() -> list[dict]`
- `_build_pyproject_tools() -> dict`

### handle_config_updates Refactoring

The complexity stems from multiple conditional branches handling different config update operations. The refactoring will:

1. **Extract Operation Handlers**: Separate method for each operation type
1. **Create Validation Methods**: Input validation and state checking
1. **Simplify Main Function**: Reduce to routing logic only

**Planned Helper Methods**:

- `_handle_check_updates(config_service: ConfigTemplateService, pkg_path: Path) -> None`
- `_handle_apply_updates(config_service: ConfigTemplateService, pkg_path: Path, interactive: bool) -> None`
- `_handle_diff_config(config_service: ConfigTemplateService, pkg_path: Path, config_type: str) -> None`
- `_handle_refresh_cache(config_service: ConfigTemplateService, pkg_path: Path) -> None`
- `_display_available_updates(updates: dict, console: Console) -> None`
- `_apply_config_updates_batch(config_service: ConfigTemplateService, configs: list[str], pkg_path: Path, interactive: bool, console: Console) -> int`

## Implementation Approach

### Phase 1: ConfigTemplateService Refactoring

1. Extract inline configuration data to separate methods
1. Create focused template builder methods
1. Update `_load_config_templates` to use new methods
1. Verify complexity reduction and functionality preservation

### Phase 2: handle_config_updates Refactoring

1. Extract operation-specific handler methods
1. Create helper methods for common operations
1. Update main function to route to appropriate handlers
1. Verify complexity reduction and functionality preservation

### Phase 3: Validation

1. Run complexity analysis to confirm violations resolved
1. Execute tests to ensure functionality preserved
1. Validate crackerjack quality gates pass

## Quality Assurance

### Pre-Refactoring Checklist

- [x] Identify current complexity violations
- [x] Analyze function structure and responsibilities
- [x] Plan helper method decomposition
- [x] Document expected complexity reduction

### Post-Refactoring Validation

- [ ] Complexity ≤15 for all refactored functions
- [ ] All existing tests pass
- [ ] No new type checking errors
- [ ] Crackerjack quality gates pass
- [ ] Public API remains unchanged

## Success Criteria

1. **Complexity Threshold Met**: All functions ≤15 complexity
1. **Functionality Preserved**: All existing behavior maintained
1. **Type Safety**: No new type checking violations
1. **Test Compatibility**: All tests continue to pass
1. **Code Quality**: Improved readability and maintainability

## Risk Mitigation

- **Incremental Approach**: Refactor one function at a time
- **Functionality Preservation**: Maintain exact same public APIs
- **Comprehensive Testing**: Validate each step with test execution
- **Rollback Plan**: Git history allows immediate rollback if issues arise
