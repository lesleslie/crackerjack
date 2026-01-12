# Test Failure Fix Plan

## Current Status

- **Total Tests**: 3,530
- **Passing**: 3,451 (97.8%)
- **Failing**: 79 (2.2%)
- **Coverage**: 45% (baseline: 21.6%, targeting 100%)

## Failure Categories

### 1. PyscnAdapter Tests (4 failures)

**Location**: `tests/adapters/test_pyscn_adapter.py`

**Issue**: Test expectations don't match implementation

- `test_build_command_basic` - expects `--format json --severity low` flags, impl uses `check --max-complexity`
- `test_build_command_with_options` - expects various flags that aren't implemented
- `test_parse_json_output` - expects JSON parsing, impl only does text parsing
- `test_parse_text_output` - parsing logic changed

**Fix Strategy**: Update tests to match actual simplified implementation

### 2. SessionCoordinator Tests (6 failures)

**Location**: `tests/unit/core/test_session_coordinator.py`

**Issue**: `session_tracker` attribute is None

- Tests expect `coordinator.session_tracker` to be initialized
- Implementation may have changed initialization logic
- Need to check `SessionCoordinator` constructor and initialization

**Fix Strategy**: Investigate session_tracker initialization, update tests or impl

### 3. Security Service Tests (5 failures)

**Location**: `tests/unit/services/test_security.py`

**Issue**: Hardcoded secret detection tests failing

- `test_check_hardcoded_secrets_api_key`
- `test_check_hardcoded_secrets_password`
- `test_check_hardcoded_secrets_token`
- `test_check_hardcoded_secrets_line_numbers`
- `test_check_hardcoded_secrets_masked_values`

**Fix Strategy**: Check security service implementation, update test expectations

### 4. Other Test Failures (64 failures)

#### Skylos Adapter Tests (3 failures)

- `test_skylos_adapter_build_command`
- `test_skylos_adapter_build_command_no_files`
- `test_skylos_adapter_detect_package_name`

#### Large File Detection Tests (6 failures)

- `test_get_git_tracked_files_success`
- `test_detects_file_above_threshold`
- `test_multiple_files_mixed_sizes`
- `test_enforce_all_flag`
- `test_cli_mixed_valid_and_large`
- `test_threshold_boundary_conditions`

#### YAML Validation Tests (2 failures)

- `test_detects_invalid_indentation`
- `test_yaml_anchors_and_aliases`

#### Trailing Whitespace Tests (2 failures)

- `test_preserves_newline_type`
- `test_python_file_with_code`

#### Code Cleaner Tests (1 failure)

- `test_apply_formatting_patterns` - expects spacing after commas

#### WorkflowOptions Tests (2 failures)

- `test_from_args_with_attributes`
- `test_from_args_missing_attributes`

#### And 48+ more...

## Execution Order

### Phase 1: High-Impact, Low-Risk Fixes (Quick Wins)

1. **PyscnAdapter** (4 tests) - Update test expectations
1. **Code Cleaner** (1 test) - Simple expectation fix
1. **WorkflowOptions** (2 tests) - Attribute handling

### Phase 2: Core Functionality (Medium Risk)

4. **SessionCoordinator** (6 tests) - May need impl changes
1. **Security Service** (5 tests) - Core security functionality

### Phase 3: Adapter & Tool Tests (Lower Priority)

6. **Skylos Adapter** (3 tests)
1. **Large File Detection** (6 tests)
1. **YAML Validation** (2 tests)
1. **Trailing Whitespace** (2 tests)

### Phase 4: Remaining Tests

10. All other failures (48+ tests)

## Coverage Improvement Strategy

After fixing test failures, focus on:

1. **High-value, low-coverage modules**:

   - `crackerjack/services/health_metrics.py` (0%)
   - `crackerjack/services/heatmap_generator.py` (0%)
   - `crackerjack/services/intelligent_commit.py` (0%)
   - `crackerjack/services/metrics.py` (0%)

1. **Medium-coverage, high-value modules**:

   - `crackerjack/services/patterns/utils.py` (0%)
   - `crackerjack/services/regex_utils.py` (0%)
   - `crackerjack/services/file_modifier.py` (20%)
   - `crackerjack/services/lsp_client.py` (17%)

## Success Criteria

- ✅ All 79 tests passing
- ✅ Coverage improved to 50%+ (from 45%)
- ✅ No new test failures introduced
- ✅ All changes follow Crackerjack architecture patterns

## Notes

- Always run `python -m crackerjack run` after fixes
- Use protocol-based imports from `models/protocols.py`
- Maintain coverage ratchet - never decrease
- Keep tests simple and synchronous when possible
