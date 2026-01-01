# Complexity Refactoring Plan - 2025-12-31

**Generated:** 2025-12-31
**Total Issues:** 21 functions with complexity > 15
**Target:** Reduce all to ≤ 15

## Summary by File

| File | Functions | Complexities | Priority |
|------|------------|--------------|----------|
| `managers/test_manager.py` | 4 | 20, 21, 24, 25 | **HIGH** |
| `tests/test_fast_hooks_behavior.py` | 1 | 24 | MEDIUM |
| `tools/validate_regex_patterns_standalone.py` | 1 | 22 | LOW |
| `mcp/tools/skill_tools.py` | 3 | 16, 16, 21 | **HIGH** |
| `tests/test_syntax_validation.py` | 1 | 20 | MEDIUM |
| `agents/semantic_agent.py` | 1 | 20 | **HIGH** |
| `models/config.py` | 1 | 18 | MEDIUM |
| `services/config_service.py` | 1 | 18 | MEDIUM |
| `tests/test_terminal_state.py` | 1 | 19 | LOW |
| `agents/helpers/performance/performance_recommender.py` | 2 | 16, 19 | **HIGH** |
| `data/repository.py` | 1 | 16 | MEDIUM |
| `scripts/audit_command_consistency.py` | 1 | 16 | LOW |
| `tests/test_ai_agent_workflow.py` | 1 | 16 | LOW |
| `tests/test_terminal_restoration.py` | 1 | 16 | LOW |

## Detailed Function List

### 1. managers/test_manager.py (4 functions - HIGHEST PRIORITY)

#### TestManager::\_split_output_sections (complexity: 20)

**Location:** `crackerjack/managers/test_manager.py`
**Strategy:** Extract section parsing logic

- `_identify_section_boundaries()` - Find section start/end markers
- `_extract_section_content()` - Extract content between markers
- `_validate_section_structure()` - Validate section completeness

#### TestManager::\_extract_structured_failures (complexity: 21)

**Location:** `crackerjack/managers/test_manager.py`
**Strategy:** Extract failure parsing logic

- `_parse_failure_block()` - Parse individual failure blocks
- `_extract_test_path()` - Extract test file path
- `_extract_error_context()` - Extract error lines and context

#### TestManager::\_render_formatted_output (complexity: 24)

**Location:** `crackerjack/managers/test_manager.py`
**Strategy:** Extract rendering logic

- `_render_summary_section()` - Render summary statistics
- `_render_failure_list()` - Render formatted failure list
- `_apply_syntax_highlighting()` - Apply code highlighting

#### TestManager::\_render_structured_failure_panels (complexity: 25)

**Location:** `crackerjack/managers/test_manager.py`
**Strategy:** Extract panel rendering logic

- `_create_failure_panel()` - Create individual failure panel
- `_format_error_content()` - Format error message content
- `_add_panel_metadata()` - Add file/line metadata to panel

### 2. tests/test_fast_hooks_behavior.py (1 function)

#### test_workflow_order (complexity: 24)

**Location:** `tests/test_fast_hooks_behavior.py`
**Strategy:** Extract test assertions into helpers

- `_assert_hook_execution_order()` - Verify hook sequence
- `_assert_failure_counts()` - Verify expected failures
- `_assert_retry_behavior()` - Verify retry logic

### 3. tools/validate_regex_patterns_standalone.py (1 function)

#### main (complexity: 22)

**Location:** `tools/validate_regex_patterns_standalone.py`
**Strategy:** Extract validation steps

- `_load_pattern_definitions()` - Load regex patterns
- `_validate_pattern_syntax()` - Check regex syntax
- `_test_pattern_matching()` - Test pattern examples

### 4. mcp/tools/skill_tools.py (3 functions - HIGH PRIORITY)

#### \_search_agent_skills (complexity: 16)

**Location:** `crackerjack/mcp/tools/skill_tools.py`
**Strategy:** Extract search logic

- `_build_agent_search_query()` - Construct search query
- `_filter_agent_results()` - Filter matching agents
- `_format_agent_skills()` - Format agent skill info

#### \_search_hybrid_skills (complexity: 16)

**Location:** `crackerjack/mcp/tools/skill_tools.py`
**Strategy:** Extract hybrid search logic

- `_search_skill_files()` - Search .skill files
- `_search_workflow_files()` - Search workflow files
- `_merge_hybrid_results()` - Merge and dedupe results

#### \_register_get_skill_info (complexity: 21)

**Location:** `crackerjack/mcp/tools/skill_tools.py`
**Strategy:** Extract skill registration logic

- `_load_skill_metadata()` - Load skill file metadata
- `_validate_skill_content()` - Validate skill structure
- `_register_skill_tool()` - Register skill as MCP tool

### 5. tests/test_syntax_validation.py (1 function)

#### TestWalrusOperatorSyntax::test_walrus_operators_have_no_spaces (complexity: 20)

**Location:** `tests/test_syntax_validation.py`
**Strategy:** Extract test assertions

- `_check_file_syntax()` - Check single file syntax
- `_assert_no_spaces_around_walrus()` - Assert walrus format
- `_report_violations()` - Report syntax violations

### 6. agents/semantic_agent.py (1 function - HIGH PRIORITY)

#### SemanticAgent::\_generate_semantic_recommendations (complexity: 20)

**Location:** `crackerjack/agents/semantic_agent.py`
**Strategy:** Extract recommendation logic

- `_analyze_code_patterns()` - Analyze code for patterns
- `_generate_transform_suggestions()` - Suggest transformations
- `_rank_recommendations()` - Rank by confidence/score

### 7. models/config.py (1 function)

#### WorkflowOptions::\_set_default_overrides (complexity: 18)

**Location:** `crackerjack/models/config.py`
**Strategy:** Extract override application

- `_apply_boolean_override()` - Apply boolean setting override
- `_apply_string_override()` - Apply string setting override
- `_apply_numeric_override()` - Apply numeric setting override

### 8. services/config_service.py (1 function)

#### \_dump_toml (complexity: 18)

**Location:** `crackerjack/services/config_service.py`
**Strategy:** Extract TOML serialization

- `_serialize_tool_config()` - Serialize tool configuration
- `_serialize_hook_config()` - Serialize hook configuration
- `_format_toml_output()` - Format final TOML structure

### 9. tests/test_terminal_state.py (1 function)

#### check_terminal_state (complexity: 19)

**Location:** `tests/test_terminal_state.py`
**Strategy:** Extract terminal validation

- `_check_terminal_settings()` - Check terminal mode settings
- `_check_signal_handling()` - Check signal handler state
- `_check_fd_state()` - Check file descriptor state

### 10. agents/helpers/performance/performance_recommender.py (2 functions - HIGH PRIORITY)

#### PerformanceRecommender::\_add_join_statement (complexity: 16)

**Location:** `crackerjack/agents/helpers/performance/performance_recommender.py`
**Strategy:** Extract join logic

- `_build_join_clause()` - Build SQL JOIN clause
- `_validate_join_conditions()` - Validate join requirements
- `_format_join_statement()` - Format final statement

#### PerformanceRecommender::\_find_candidate_indices (complexity: 19)

**Location:** `crackerjack/agents/helpers/performance/performance_recommender.py`
**Strategy:** Extract index search logic

- `_scan_table_indices()` - Scan existing indices
- `_filter_candidate_indices()` - Filter by criteria
- `_rank_index_candidates()` - Rank by potential impact

### 11. data/repository.py (1 function)

#### \_InMemorySimpleOps::create_or_update (complexity: 16)

**Location:** `crackerjack/data/repository.py`
**Strategy:** Extract CRUD operations

- `_validate_entity_data()` - Validate entity structure
- `_update_existing_entity()` - Update if exists
- `_create_new_entity()` - Create if new

### 12. scripts/audit_command_consistency.py (1 function)

#### compare_commands (complexity: 16)

**Location:** `scripts/audit_command_consistency.py`
**Strategy:** Extract comparison logic

- `_load_command_definitions()` - Load command metadata
- `_compare_command_signatures()` - Compare signatures
- `_report_inconsistencies()` - Report mismatches

### 13. tests/test_ai_agent_workflow.py (1 function)

#### AIAgentWorkflowTester::generate_test_report (complexity: 16)

**Location:** `tests/test_ai_agent_workflow.py`
**Strategy:** Extract report generation

- `_collect_test_metrics()` - Collect test statistics
- `_format_report_sections()` - Format report sections
- `_write_report_output()` - Write report to file

### 14. tests/test_terminal_restoration.py (1 function)

#### test_terminal_restoration (complexity: 16)

**Location:** `tests/test_terminal_restoration.py`
**Strategy:** Extract test validation

- `_save_terminal_state()` - Save initial terminal state
- `_trigger_terminal_change()` - Trigger state change
- `_verify_restoration()` - Verify state restoration

## Implementation Order

### Phase 1: CRITICAL Core Functionality (4 files, 10 functions)

1. **managers/test_manager.py** - 4 functions (90 total complexity)
1. **mcp/tools/skill_tools.py** - 3 functions (53 total complexity)
1. **agents/semantic_agent.py** - 1 function (20 complexity)
1. **agents/helpers/performance/performance_recommender.py** - 2 functions (35 complexity)

**Rationale:** These are core Crackerjack services used in daily workflows.

### Phase 2: Supporting Infrastructure (4 files, 4 functions)

5. **models/config.py** - 1 function (18 complexity)
1. **services/config_service.py** - 1 function (18 complexity)
1. **data/repository.py** - 1 function (16 complexity)
1. **tools/validate_regex_patterns_standalone.py** - 1 function (22 complexity)

**Rationale:** Configuration and data management infrastructure.

### Phase 3: Test Code (6 files, 7 functions)

9. **tests/test_fast_hooks_behavior.py** - 1 function (24 complexity)
1. **tests/test_syntax_validation.py** - 1 function (20 complexity)
1. **tests/test_terminal_state.py** - 1 function (19 complexity)
1. **tests/test_ai_agent_workflow.py** - 1 function (16 complexity)
1. **tests/test_terminal_restoration.py** - 1 function (16 complexity)
1. **scripts/audit_command_consistency.py** - 1 function (16 complexity)

**Rationale:** Test maintenance and scripts (lower priority than production code).

## Refactoring Pattern (from CLAUDE.md)

```python
# BEFORE: Complex method with high cognitive complexity
def complex_method(self, data: dict) -> bool:
    # 20+ lines of nested logic
    if condition1:
        if condition2:
            for item in items:
                # more nested logic
                if nested_condition:
                    return result
    return False

# AFTER: Extracted helpers following single responsibility principle
def complex_method(self, data: dict) -> bool:
    """Orchestrates the workflow using clear helper methods."""
    if not self._validate_input(data):
        return self._handle_invalid_input()
    processed = self._process_data(data)
    return self._save_results(processed)

def _validate_input(self, data: dict) -> bool:
    """Clear, single-purpose validation logic."""
    return bool(data and isinstance(data, dict))

def _handle_invalid_input(self) -> bool:
    """Clear error handling with user feedback."""
    self.console.print("[red]Invalid input[/red]")
    return False

def _process_data(self, data: dict) -> dict:
    """Clear data transformation logic."""
    return {k: v for k, v in data.items() if v}

def _save_results(self, processed: dict) -> bool:
    """Clear persistence logic."""
    self.repository.save(processed)
    return True
```

## Success Criteria

- ✅ All 21 functions reduced to complexity ≤ 15
- ✅ No behavior changes (100% functional preservation)
- ✅ All type annotations maintained
- ✅ All tests passing
- ✅ No coverage regression
- ✅ Clean `python -m crackerjack run` result

## Verification Steps

After each file refactoring:

1. Run `uv run complexipy <file> --failed` to verify complexity reduction
1. Run `python -m pytest tests/<specific_test>.py -v` for relevant tests
1. Check for any import or type errors

After all refactoring:

1. Run full complexipy scan: `uv run complexipy . --failed` (should find 0 issues)
1. Run full test suite: `python -m crackerjack run --run-tests`
1. Run quality checks: `python -m crackerjack run`

## Progress Tracking

- [ ] Phase 1: Core functionality (10 functions)
- [ ] Phase 2: Infrastructure (4 functions)
- [ ] Phase 3: Test code (7 functions)
- [ ] Final verification
