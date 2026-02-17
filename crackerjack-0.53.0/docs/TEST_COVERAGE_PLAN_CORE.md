# Test Coverage Plan: Core Infrastructure Modules

## Overview

This document outlines the comprehensive test coverage strategy for crackerjack's 5 core infrastructure modules that currently have **zero coverage**.

## Target Modules

### 1. Workflow Orchestrator (`workflow_orchestrator.py`)

**Lines of Code**: 167
**Current Coverage**: 0%

**Key Classes/Functions**:

- `WorkflowPipeline`: Main orchestration class
- `WorkflowResult`: Dataclass for results
- `_workflow_result_success()`: Result validation helper
- `_adapt_options()`: Options adaptation

**Test Strategy**:

1. **Initialization Tests**: Verify proper setup of console, settings, session, phases
1. **Workflow Execution Tests**: Test async/sync workflow execution paths
1. **Phase Delegation Tests**: Ensure proper delegation to PhaseCoordinator
1. **Cache Clearing Tests**: Verify Oneiric cache clearing functionality
1. **Error Handling Tests**: Test exception handling and session finalization
1. **Helper Function Tests**: Test result success logic and options adaptation

**Test Cases** (20+ tests):

- `test_workflow_pipeline_initialization`: Verify all dependencies injected
- `test_run_complete_workflow_success`: Happy path workflow execution
- `test_run_complete_workflow_failure`: Exception handling and session finalization
- `test_run_fast_hooks_only`: Delegation to phases
- `test_run_comprehensive_hooks_only`: Delegation to phases
- `test_execute_workflow_sync_wrapper`: Sync wrapper functionality
- `test_clear_oneiric_cache`: Cache database clearing
- `test_clear_oneiric_cache_no_db`: Graceful handling when cache doesn't exist
- `test_workflow_result_success_all_true`: Success with all True results
- `test_workflow_result_success_mixed`: Failure with False in results
- `test_workflow_result_success_no_results`: Default success when no results
- `test_initialize_workflow_session`: Session tracking initialization
- `test_run_cleaning_phase`: Cleaning phase delegation
- `test_run_testing_phase`: Testing phase delegation
- `test_verbose_logging`: Verify verbose mode logging
- `test_non_verbose_logging`: Verify non-verbose mode logging

______________________________________________________________________

### 2. Phase Coordinator (`phase_coordinator.py`)

**Lines of Code**: 1,670
**Current Coverage**: 0%

**Key Classes/Functions**:

- `PhaseCoordinator`: Main phase orchestration class
- Hook execution methods: `run_fast_hooks_only()`, `run_comprehensive_hooks_only()`
- Phase methods: `run_testing_phase()`, `run_cleaning_phase()`, `run_configuration_phase()`
- AI fix methods: `_apply_ai_fix_for_fast_hooks()`, `_apply_ai_fix_for_tests()`
- Progress tracking and result rendering

**Test Strategy**:

1. **Initialization Tests**: Verify all services and dependencies setup
1. **Fast Hooks Tests**: Test fast hook execution with retry logic
1. **Comprehensive Hooks Tests**: Test comprehensive hook execution
1. **Testing Phase Tests**: Test test execution and AI fix integration
1. **Cleaning Phase Tests**: Test code cleaning functionality
1. **AI Fix Tests**: Test AI agent fix application for hooks and tests
1. **Progress Tracking Tests**: Test progress bar and callback setup
1. **Result Rendering Tests**: Test table/rendering for plain and rich output
1. **Configuration Phase Tests**: Test config cleanup and updates
1. **Publishing Phase Tests**: Test version bump and publishing workflow
1. **Commit Phase Tests**: Test git commit and push functionality

**Test Cases** (40+ tests):

- `test_phase_coordinator_initialization`: Verify all dependencies
- `test_logger_property`: Logger getter/setter functionality
- `test_run_fast_hooks_only_success`: Happy path fast hooks
- `test_run_fast_hooks_only_skip_hooks`: Skip hooks flag
- `test_run_fast_hooks_with_retry`: Retry logic on failure
- `test_run_fast_hooks_duplicate_prevention`: Duplicate invocation detection
- `test_apply_ai_fix_for_fast_hooks_success`: AI fix success path
- `test_apply_ai_fix_for_fast_hooks_failure`: AI fix failure path
- `test_classify_safe_test_failures`: Test failure classification
- `test_run_comprehensive_hooks_only_success`: Happy path comprehensive hooks
- `test_run_comprehensive_hooks_only_ai_fix`: AI fix retry
- `test_run_testing_phase_success`: Test execution success
- `test_run_testing_phase_with_ai_fix`: Test AI fix integration
- `test_run_cleaning_phase_with_files`: Clean Python files
- `test_run_cleaning_phase_no_files`: Handle no Python files
- `test_run_configuration_phase_no_updates`: Skip when no updates needed
- `test_run_config_cleanup_phase`: Config cleanup execution
- `test_run_documentation_cleanup_phase`: Documentation cleanup
- `test_run_git_cleanup_phase`: Git cleanup execution
- `test_run_doc_update_phase`: Documentation updates
- `test_execute_hooks_once`: Single hook execution
- `test_create_progress_bar`: Progress bar creation
- `test_setup_progress_callbacks`: Callback setup
- `test_run_hooks_with_progress_success`: Progress tracking success
- `test_run_hooks_with_progress_error`: Progress tracking error handling
- `test_process_hook_results_success`: Result processing success
- `test_process_hook_results_failure`: Result processing failure
- `test_display_hook_phase_header`: Header display
- `test_report_hook_results_passed`: Passed hooks reporting
- `test_report_hook_results_failed`: Failed hooks reporting
- `test_render_plain_hook_results`: Plain text rendering
- `test_render_rich_hook_results`: Rich rendering with table
- `test_calculate_hook_statistics`: Statistics calculation
- `test_update_json_hook_issue_counts`: JSON issue count extraction
- `test_strip_ansi`: ANSI code stripping
- `test_is_plain_output`: Plain output detection
- `test_format_hook_summary`: Summary formatting
- `test_status_style`: Status color mapping
- `test_determine_version_type`: Version type determination
- `test_execute_publishing_workflow`: Publishing workflow
- `test_run_commit_phase`: Commit and push workflow

______________________________________________________________________

### 3. Performance Monitor (`performance_monitor.py`)

**Lines of Code**: 358
**Current Coverage**: 0%

**Key Classes/Functions**:

- `OperationMetrics`: Dataclass for operation metrics
- `TimeoutEvent`: Dataclass for timeout tracking
- `AsyncPerformanceMonitor`: Main performance tracking class
- Global functions: `get_performance_monitor()`, `reset_performance_monitor()`

**Test Strategy**:

1. **Metrics Tests**: Test operation metric recording and calculations
1. **Timeout Tests**: Test timeout event tracking
1. **Performance Alert Tests**: Test threshold-based alerting
1. **Summary Stats Tests**: Test aggregate statistics
1. **Export Tests**: Test JSON export functionality
1. **Reporting Tests**: Test console report generation
1. **Circuit Breaker Tests**: Test circuit breaker event tracking
1. **Thread Safety Tests**: Test lock-based concurrent access

**Test Cases** (30+ tests):

- `test_operation_metrics_initialization`: Metrics dataclass setup
- `test_operation_metrics_success_rate`: Success rate calculation
- `test_operation_metrics_average_time`: Average time calculation
- `test_operation_metrics_recent_average_time`: Recent average calculation
- `test_operation_metrics_min_max_time`: Min/max tracking
- `test_async_performance_monitor_initialization`: Monitor setup
- `test_record_operation_start`: Start time recording
- `test_record_operation_success`: Success recording
- `test_record_operation_failure`: Failure recording
- `test_record_operation_timeout`: Timeout recording
- `test_get_operation_metrics_existing`: Retrieve existing metrics
- `test_get_operation_metrics_nonexistent`: Return None for non-existent
- `test_get_all_metrics`: Get all metrics copy
- `test_get_recent_timeout_events`: Get recent timeouts
- `test_get_performance_alerts_success_rate`: Alert on low success rate
- `test_get_performance_alerts_critical_time`: Alert on critical response time
- `test_get_performance_alerts_warning_time`: Alert on warning response time
- `test_get_performance_alerts_no_alerts`: No alerts when thresholds met
- `test_get_summary_stats`: Summary statistics calculation
- `test_get_summary_stats_no_operations`: Empty stats
- `test_export_metrics_json`: JSON export functionality
- `test_export_metrics_json_file_creation`: File creation
- `test_print_performance_report`: Report generation
- `test_print_performance_report_with_alerts`: Report with alerts
- `test_print_performance_report_with_timeouts`: Report with timeouts
- `test_record_circuit_breaker_event`: Circuit breaker tracking
- `test_performance_thresholds_defaults`: Default threshold configuration
- `test_performance_thresholds_custom`: Custom threshold configuration
- `test_get_performance_monitor_singleton`: Singleton pattern
- `test_reset_performance_monitor`: Reset functionality
- `test_thread_safety_metrics_recording`: Concurrent access safety
- `test_recent_times_maxlen`: Deque max length enforcement

______________________________________________________________________

### 4. Resource Manager (`resource_manager.py`)

**Lines of Code**: 430
**Current Coverage**: 0%

**Key Classes/Functions**:

- `ResourceManager`: Main resource lifecycle management
- `ManagedResource`: Abstract base for managed resources
- `ManagedTemporaryFile`: Managed temp file
- `ManagedTemporaryDirectory`: Managed temp directory
- `ManagedProcess`: Managed subprocess
- `ManagedTask`: Managed asyncio task
- `ManagedFileHandle`: Managed file handle
- `ResourceContext`: Context manager for resources
- `ResourceLeakDetector`: Leak detection utility

**Test Strategy**:

1. **ResourceManager Tests**: Test resource registration and cleanup
1. **ManagedResource Tests**: Test base class functionality
1. **ManagedTemporaryFile Tests**: Test temp file lifecycle
1. **ManagedTemporaryDirectory Tests**: Test temp dir lifecycle
1. **ManagedProcess Tests**: Test process cleanup
1. **ManagedTask Tests**: Test task cancellation
1. **ManagedFileHandle Tests**: Test file handle cleanup
1. **ResourceContext Tests**: Test context manager usage
1. **Global Manager Tests**: Test global manager registration
1. **Leak Detector Tests**: Test leak detection functionality

**Test Cases** (35+ tests):

- `test_resource_manager_initialization`: Manager setup
- `test_register_resource`: Resource registration
- `test_register_cleanup_callback`: Callback registration
- `test_cleanup_all_resources`: Cleanup all registered resources
- `test_cleanup_all_callbacks`: Cleanup all callbacks
- `test_cleanup_all_closed_state`: Closed state handling
- `test_resource_manager_async_context_manager`: Async context manager
- `test_resource_manager_register_after_closed`: Register after closed
- `test_managed_resource_initialization`: Base resource setup
- `test_managed_resource_close`: Close method
- `test_managed_temporary_file_initialization`: Temp file creation
- `test_managed_temporary_file_write_read`: Write and read operations
- `test_managed_temporary_file_cleanup`: Cleanup deletion
- `test_managed_temporary_file_write_after_close`: Error on write after close
- `test_managed_temporary_directory_initialization`: Temp dir creation
- `test_managed_temporary_directory_cleanup`: Cleanup deletion
- `test_managed_process_initialization`: Process wrapping
- `test_managed_process_cleanup_terminate`: Graceful termination
- `test_managed_process_cleanup_kill`: Force kill on timeout
- `test_managed_task_initialization`: Task wrapping
- `test_managed_task_cleanup`: Task cancellation
- `test_managed_file_handle_initialization`: File handle wrapping
- `test_managed_file_handle_cleanup`: Handle closing
- `test_resource_context_initialization`: Context setup
- `test_resource_context_managed_temp_file`: Temp file factory
- `test_resource_context_managed_temp_dir`: Temp dir factory
- `test_resource_context_managed_process`: Process factory
- `test_resource_context_managed_task`: Task factory
- `test_resource_context_async_context_manager`: Context manager usage
- `test_with_resource_cleanup_context_manager`: Helper context manager
- `test_with_temp_file_context_manager`: Temp file helper
- `test_with_temp_dir_context_manager`: Temp dir helper
- `test_with_managed_process_context_manager`: Process helper
- `test_register_global_resource_manager`: Global registration
- `test_cleanup_all_global_resources`: Global cleanup
- `test_resource_leak_detector_initialization`: Detector setup
- `test_leak_detector_track_file`: File tracking
- `test_leak_detector_track_process`: Process tracking
- `test_leak_detector_track_task`: Task tracking
- `test_leak_detector_get_leak_report`: Leak report generation
- `test_leak_detector_has_potential_leaks`: Leak detection
- `test_enable_leak_detection`: Enable detector
- `test_disable_leak_detection`: Disable and get report

______________________________________________________________________

### 5. Async Workflow Orchestrator (`async_workflow_orchestrator.py`)

**Lines of Code**: 50
**Current Coverage**: 0%

**Key Classes/Functions**:

- `AsyncWorkflowPipeline`: Async wrapper around WorkflowPipeline
- `run_complete_workflow_async()`: Standalone async runner

**Test Strategy**:

1. **Initialization Tests**: Verify proper setup
1. **Async Execution Tests**: Test async workflow execution
1. **Delegation Tests**: Verify delegation to WorkflowPipeline
1. **Timeout Manager Tests**: Verify timeout manager integration

**Test Cases** (10+ tests):

- `test_async_workflow_pipeline_initialization`: Verify setup
- `test_run_complete_workflow_async_success`: Happy path async execution
- `test_run_complete_workflow_async_failure`: Exception handling
- `test_run_complete_workflow_async_function`: Standalone function
- `test_timeout_manager_initialization`: Timeout manager setup
- `test_delegation_to_workflow_pipeline`: Verify delegation

______________________________________________________________________

## Test File Structure

```
tests/integration/core/
├── __init__.py
├── test_workflow_orchestrator.py      (20+ tests, 600+ lines)
├── test_phase_coordinator.py          (40+ tests, 1200+ lines)
├── test_performance_monitor.py        (30+ tests, 800+ lines)
├── test_resource_manager.py           (35+ tests, 1000+ lines)
└── test_async_workflow_orchestrator.py (10+ tests, 300+ lines)
```

**Total**: 135+ tests, 3,900+ lines of test code

## Coverage Targets

| Module | Target Coverage | Priority |
|--------|----------------|----------|
| workflow_orchestrator.py | 75% | High |
| phase_coordinator.py | 70% | High |
| performance_monitor.py | 80% | High |
| resource_manager.py | 80% | High |
| async_workflow_orchestrator.py | 85% | Medium |

**Overall Target**: 75%+ coverage for core infrastructure

## Testing Principles

1. **Protocol-Based DI**: Mock protocols, not concrete classes
1. **Async Testing**: Use `pytest-asyncio` for async methods
1. **Simplicity**: Prefer simple synchronous config tests over complex async tests
1. **Complexity ≤15**: Extract helpers if test complexity exceeds 15
1. **Docstrings**: All tests must have docstrings explaining what they verify
1. **Both Paths**: Test both success and failure paths
1. **Edge Cases**: Test edge cases (empty inputs, None values, etc.)
1. **Thread Safety**: Test concurrent access where applicable

## Execution Commands

```bash
# Run all core tests
python -m pytest tests/integration/core/ -v

# Run specific test file
python -m pytest tests/integration/core/test_workflow_orchestrator.py -v

# Check coverage
python -m pytest tests/integration/core/ --cov=crackerjack.core --cov-report=term-missing

# Generate HTML coverage report
python -m pytest tests/integration/core/ --cov=crackerjack.core --cov-report=html
```

## Success Criteria

- All 5 modules have ≥60% coverage
- All tests pass consistently
- No flaky tests (async tests that hang)
- Complexity ≤15 per test function
- All public methods tested
- All error paths tested
- Documentation complete
