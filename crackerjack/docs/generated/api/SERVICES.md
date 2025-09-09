# Service Reference

This document describes all service implementations in the codebase.

## api_extractor

**Location:** `crackerjack/services/api_extractor.py`

**Implements:**

- APIExtractorProtocol

### PythonDocstringParser

Parser for extracting structured information from Python docstrings.

**Public Methods:**

- `parse_docstring`: Parse a docstring and extract structured information.

### APIExtractorImpl

Implementation of API documentation extraction from source code.

**Public Methods:**

- `extract_from_python_files`: Extract API documentation from Python files.
- `extract_protocol_definitions`: Extract protocol definitions from protocols.py file.
- `extract_service_interfaces`: Extract service interfaces and their methods.
- `extract_cli_commands`: Extract CLI command definitions and options.
- `extract_mcp_tools`: Extract MCP tool definitions and their capabilities.

## backup_service

**Location:** `crackerjack/services/backup_service.py`

### BackupMetadata

### BackupValidationResult

### PackageBackupService

**Public Methods:**

- `model_post_init`:
- `create_package_backup`:
- `restore_from_backup`:
- `cleanup_backup`:

## bounded_status_operations

**Location:** `crackerjack/services/bounded_status_operations.py`

### OperationState

### OperationLimits

### OperationMetrics

**Public Methods:**

- `duration`:
- `is_completed`:

### OperationLimitExceededError

### CircuitBreakerOpenError

### BoundedStatusOperations

**Public Methods:**

- `get_operation_status`:
- `reset_circuit_breaker`:

## cache

**Location:** `crackerjack/services/cache.py`

### CacheEntry

**Public Methods:**

- `is_expired`:
- `age_seconds`:
- `touch`:
- `to_dict`:
- `from_dict`:

### CacheStats

**Public Methods:**

- `hit_rate`:
- `to_dict`:

### InMemoryCache

**Public Methods:**

- `get`:
- `set`:
- `invalidate`:
- `clear`:
- `cleanup_expired`:

### FileCache

**Public Methods:**

- `get`:
- `set`:
- `invalidate`:
- `clear`:
- `cleanup_expired`:

### CrackerjackCache

**Public Methods:**

- `get_hook_result`:
- `set_hook_result`:
- `get_expensive_hook_result`: Get hook result with disk cache fallback for expensive hooks.
- `set_expensive_hook_result`: Set hook result in both memory and disk cache for expensive hooks.
- `get_file_hash`:
- `set_file_hash`:
- `get_config_data`:
- `set_config_data`:
- `get_agent_decision`: Get cached AI agent decision based on issue content.
- `set_agent_decision`: Cache AI agent decision for future use.
- `get_quality_baseline`: Get quality baseline metrics for a specific git commit.
- `set_quality_baseline`: Store quality baseline metrics for a git commit.
- `invalidate_hook_cache`:
- `cleanup_all`:
- `get_cache_stats`:

## changelog_automation

**Location:** `crackerjack/services/changelog_automation.py`

### ChangelogEntry

Represents a single changelog entry.

**Public Methods:**

- `to_markdown`: Convert entry to markdown format.

### ChangelogGenerator

Generate and update changelogs based on git commits.

**Public Methods:**

- `parse_commit_message`: Parse a commit message into a changelog entry.
- `generate_changelog_entries`: Generate changelog entries from git commits.
- `update_changelog`: Update the changelog file with new entries.
- `generate_changelog_from_commits`: Generate and update changelog from git commits.

## config

**Location:** `crackerjack/services/config.py`

### ConfigurationService

**Public Methods:**

- `update_precommit_config`:
- `get_temp_config_path`:
- `validate_config`:
- `backup_config`:
- `restore_config`:
- `get_config_info`:
- `update_pyproject_config`:

## config_integrity

**Location:** `crackerjack/services/config_integrity.py`

### ConfigIntegrityService

**Public Methods:**

- `check_config_integrity`:

## config_merge

**Location:** `crackerjack/services/config_merge.py`

**Implements:**

- ConfigMergeServiceProtocol

### ConfigMergeService

**Public Methods:**

- `smart_merge_pyproject`:
- `smart_merge_pre_commit_config`:
- `smart_append_file`:
- `smart_merge_gitignore`:
- `write_pyproject_config`:
- `write_pre_commit_config`:

### ParsedContent

## contextual_ai_assistant

**Location:** `crackerjack/services/contextual_ai_assistant.py`

### AIRecommendation

### ProjectContext

### ContextualAIAssistant

**Public Methods:**

- `get_contextual_recommendations`:
- `display_recommendations`:
- `get_quick_help`:

## coverage_ratchet

**Location:** `crackerjack/services/coverage_ratchet.py`

### CoverageRatchetService

**Public Methods:**

- `initialize_baseline`:
- `get_ratchet_data`:
- `get_baseline`:
- `get_baseline_coverage`:
- `update_baseline_coverage`:
- `is_coverage_regression`:
- `get_coverage_improvement_needed`:
- `update_coverage`:
- `get_progress_visualization`:
- `get_status_report`:
- `display_milestone_celebration`:
- `show_progress_with_spinner`:
- `get_coverage_report`:
- `check_and_update_coverage`:

## debug

**Location:** `crackerjack/services/debug.py`

### AIAgentDebugger

**Public Methods:**

- `debug_operation`:
- `log_mcp_operation`:
- `log_agent_activity`:
- `log_workflow_phase`:
- `log_error_event`:
- `print_debug_summary`:
- `log_iteration_start`:
- `log_iteration_end`:
- `log_test_failures`:
- `log_test_fixes`:
- `log_hook_failures`:
- `log_hook_fixes`:
- `set_workflow_success`:
- `export_debug_data`:

### NoOpDebugger

**Public Methods:**

- `debug_operation`:
- `log_mcp_operation`:
- `log_agent_activity`:
- `log_workflow_phase`:
- `log_error_event`:
- `print_debug_summary`:
- `export_debug_data`:
- `log_iteration_start`:
- `log_iteration_end`:
- `log_test_failures`:
- `log_test_fixes`:
- `log_hook_failures`:
- `log_hook_fixes`:
- `set_workflow_success`:

## dependency_monitor

**Location:** `crackerjack/services/dependency_monitor.py`

### DependencyVulnerability

### MajorUpdate

### DependencyMonitorService

**Public Methods:**

- `check_dependency_updates`:
- `force_check_updates`:

## documentation_generator

**Location:** `crackerjack/services/documentation_generator.py`

**Implements:**

- DocumentationGeneratorProtocol

### MarkdownTemplateRenderer

Simple template renderer for markdown documentation.

**Public Methods:**

- `render_template`: Render a template with the given context.

### DocumentationGeneratorImpl

Implementation of documentation generation from extracted API data.

**Public Methods:**

- `generate_api_reference`: Generate complete API reference documentation.
- `generate_user_guide`: Generate user guide documentation.
- `generate_changelog_update`: Generate changelog entry for a version.
- `render_template`: Render a template file with the given context.
- `generate_cross_references`: Generate cross-reference mappings for API components.

## documentation_service

**Location:** `crackerjack/services/documentation_service.py`

**Implements:**

- DocumentationServiceProtocol

### DocumentationServiceImpl

Main service for automated documentation generation and maintenance.

**Public Methods:**

- `extract_api_documentation`: Extract API documentation from source code files.
- `generate_documentation`: Generate documentation using specified template.
- `validate_documentation`: Validate documentation for issues and inconsistencies.
- `update_documentation_index`: Update the main documentation index with links to all docs.
- `get_documentation_coverage`: Calculate documentation coverage metrics.
- `generate_full_api_documentation`: Generate complete API documentation for the project.

## enhanced_filesystem

**Location:** `crackerjack/services/enhanced_filesystem.py`

### FileCache

**Public Methods:**

- `get`:
- `put`:
- `clear`:
- `get_stats`:

### BatchFileOperations

### EnhancedFileSystemService

**Public Methods:**

- `read_file`:
- `write_file`:
- `file_exists`:
- `create_directory`:
- `delete_file`:
- `list_files`:
- `get_cache_stats`:
- `clear_cache`:
- `exists`:
- `mkdir`:

## file_hasher

**Location:** `crackerjack/services/file_hasher.py`

### FileHasher

**Public Methods:**

- `get_file_hash`:
- `get_directory_hash`:
- `get_files_hash_list`:
- `has_files_changed`:
- `get_project_files_hash`:
- `invalidate_cache`:

### SmartFileWatcher

**Public Methods:**

- `register_files`:
- `check_changes`:
- `invalidate_changed_files`:

## filesystem

**Location:** `crackerjack/services/filesystem.py`

### FileSystemService

**Public Methods:**

- `clean_trailing_whitespace_and_newlines`:
- `read_file`:
- `write_file`:
- `exists`:
- `mkdir`:
- `glob`:
- `rglob`:
- `copy_file`:
- `remove_file`:
- `get_file_size`:
- `get_file_mtime`:
- `read_file_chunked`:
- `read_lines_streaming`:

## git

**Location:** `crackerjack/services/git.py`

### FailedGitResult

### GitService

**Public Methods:**

- `is_git_repo`:
- `get_changed_files`:
- `get_staged_files`:
- `add_files`:
- `add_all_files`:
- `commit`:
- `push`:
- `get_current_branch`:
- `get_commit_message_suggestions`:
- `get_unpushed_commit_count`:

## health_metrics

**Location:** `crackerjack/services/health_metrics.py`

### ProjectHealth

**Public Methods:**

- `needs_init`:
- `get_health_score`:
- `get_recommendations`:

### HealthMetricsService

**Public Methods:**

- `collect_current_metrics`:
- `analyze_project_health`:
- `report_health_status`:
- `get_health_trend_summary`:

## initialization

**Location:** `crackerjack/services/initialization.py`

### InitializationService

**Public Methods:**

- `initialize_project`:
- `setup_git_hooks`:
- `validate_project_structure`:
- `initialize_project_full`:
- `check_uv_installed`:

## input_validator

**Location:** `crackerjack/services/input_validator.py`

### ValidationConfig

### ValidationResult

### InputSanitizer

**Public Methods:**

- `sanitize_string`:
- `sanitize_json`:
- `sanitize_path`:

### SecureInputValidator

**Public Methods:**

- `validate_project_name`:
- `validate_job_id`:
- `validate_command_args`:
- `validate_json_payload`:
- `validate_file_path`:
- `validate_environment_var`:

## intelligent_commit

**Location:** `crackerjack/services/intelligent_commit.py`

### CommitMessageGenerator

Generate intelligent commit messages based on changes and context.

**Public Methods:**

- `generate_commit_message`: Generate an intelligent commit message based on staged changes.
- `commit_with_generated_message`: Generate commit message and create commit.

## log_manager

**Location:** `crackerjack/services/log_manager.py`

### LogManager

**Public Methods:**

- `log_dir`:
- `debug_dir`:
- `error_dir`:
- `audit_dir`:
- `create_debug_log_file`:
- `create_error_log_file`:
- `rotate_logs`:
- `cleanup_all_logs`:
- `migrate_legacy_logs`:
- `get_log_stats`:
- `setup_rotating_file_handler`:
- `print_log_summary`:

## logging

**Location:** `crackerjack/services/logging.py`

### LoggingContext

## memory_optimizer

**Location:** `crackerjack/services/memory_optimizer.py`

### MemoryStats

### LazyLoader

**Public Methods:**

- `is_loaded`:
- `access_count`:
- `get`:
- `dispose`:

### ResourcePool

**Public Methods:**

- `acquire`:
- `release`:
- `clear`:
- `get_stats`:

### MemoryProfiler

**Public Methods:**

- `start_profiling`:
- `record_checkpoint`:
- `get_summary`:

### MemoryOptimizer

**Public Methods:**

- `get_instance`:
- `register_lazy_object`:
- `notify_lazy_load`:
- `register_resource_pool`:
- `get_resource_pool`:
- `start_profiling`:
- `record_checkpoint`:
- `get_memory_stats`:
- `optimize_memory`:

## metrics

**Location:** `crackerjack/services/metrics.py`

### MetricsCollector

**Public Methods:**

- `start_job`:
- `end_job`:
- `record_error`:
- `record_hook_execution`:
- `record_test_execution`:
- `record_orchestration_execution`:
- `record_strategy_decision`:
- `record_individual_test`:
- `get_orchestration_stats`:
- `get_all_time_stats`:

## parallel_executor

**Location:** `crackerjack/services/parallel_executor.py`

### ExecutionStrategy

### ExecutionGroup

### ExecutionResult

### ParallelExecutionResult

**Public Methods:**

- `success_rate`:
- `overall_success`:

### ParallelHookExecutor

**Public Methods:**

- `analyze_hook_dependencies`:
- `can_execute_in_parallel`:

### AsyncCommandExecutor

## pattern_cache

**Location:** `crackerjack/services/pattern_cache.py`

### CachedPattern

### PatternCache

**Public Methods:**

- `cache_successful_pattern`:
- `get_patterns_for_issue`:
- `get_best_pattern_for_issue`:
- `use_pattern`:
- `update_pattern_success_rate`:
- `get_pattern_statistics`:
- `cleanup_old_patterns`:
- `clear_cache`:
- `export_patterns`:
- `import_patterns`:

## pattern_detector

**Location:** `crackerjack/services/pattern_detector.py`

### AntiPatternConfig

### AntiPattern

### PatternDetector

### ComplexityVisitor

**Public Methods:**

- `visit_FunctionDef`:

### PerformanceVisitor

**Public Methods:**

- `visit_For`:

### SecurityVisitor

**Public Methods:**

- `visit_Call`:

### ImportVisitor

**Public Methods:**

- `visit_Import`:
- `visit_ImportFrom`:

## performance_benchmarks

**Location:** `crackerjack/services/performance_benchmarks.py`

### BenchmarkResult

**Public Methods:**

- `time_improvement_percentage`:
- `memory_improvement_percentage`:
- `cache_hit_ratio`:
- `parallelization_ratio`:

### BenchmarkSuite

**Public Methods:**

- `average_time_improvement`:
- `average_memory_improvement`:
- `overall_cache_hit_ratio`:
- `add_result`:

### PerformanceBenchmarker

**Public Methods:**

- `export_benchmark_results`:

## performance_cache

**Location:** `crackerjack/services/performance_cache.py`

### CacheEntry

**Public Methods:**

- `is_expired`:
- `access`:

### CacheStats

**Public Methods:**

- `hit_ratio`:

### PerformanceCache

**Public Methods:**

- `get`:
- `set`:
- `invalidate`:
- `clear`:
- `get_stats`:

### GitOperationCache

**Public Methods:**

- `get_branch_info`:
- `set_branch_info`:
- `get_file_status`:
- `set_file_status`:
- `invalidate_repo`:

### FileSystemCache

**Public Methods:**

- `get_file_stats`:
- `set_file_stats`:
- `invalidate_file`:

### CommandResultCache

**Public Methods:**

- `get_command_result`:
- `set_command_result`:
- `invalidate_commands`:

## performance_monitor

**Location:** `crackerjack/services/performance_monitor.py`

### PerformanceMetric

### PhasePerformance

**Public Methods:**

- `finalize`:

### WorkflowPerformance

**Public Methods:**

- `add_phase`:
- `finalize`:

### PerformanceBenchmark

### PerformanceMonitor

**Public Methods:**

- `start_workflow`:
- `end_workflow`:
- `start_phase`:
- `end_phase`:
- `record_metric`:
- `record_parallel_operation`:
- `record_sequential_operation`:
- `benchmark_operation`:
- `get_performance_summary`:
- `get_benchmark_trends`:
- `export_performance_data`:

### phase_monitor

**Public Methods:**

- `record_parallel_op`:
- `record_sequential_op`:
- `record_metric`:

## quality_baseline

**Location:** `crackerjack/services/quality_baseline.py`

### QualityMetrics

Quality metrics for a specific commit/session.

**Public Methods:**

- `to_dict`:
- `from_dict`:

### QualityBaselineService

Service for tracking and persisting quality baselines across sessions.

**Public Methods:**

- `get_current_git_hash`: Get current git commit hash.
- `calculate_quality_score`: Calculate overall quality score (0-100).
- `record_baseline`: Record quality baseline for current commit.
- `get_baseline`: Get quality baseline for specific commit (or current commit).
- `compare_with_baseline`: Compare current metrics with baseline.
- `get_recent_baselines`: Get recent baselines (requires git log parsing since cache is keyed by hash).

## quality_baseline_enhanced

**Location:** `crackerjack/services/quality_baseline_enhanced.py`

### TrendDirection

Quality trend direction.

### AlertSeverity

Alert severity levels.

### QualityTrend

Quality trend analysis over time.

**Public Methods:**

- `to_dict`:

### QualityAlert

Quality alert for significant changes.

**Public Methods:**

- `to_dict`:

### QualityReport

Comprehensive quality report.

**Public Methods:**

- `to_dict`:

### EnhancedQualityBaselineService

Enhanced quality baseline service with advanced analytics.

**Public Methods:**

- `analyze_quality_trend`: Analyze quality trend over specified period.
- `check_quality_alerts`: Check for quality alerts based on thresholds.
- `generate_recommendations`: Generate actionable recommendations.
- `generate_comprehensive_report`: Generate comprehensive quality report.
- `export_report`: Export quality report to file.
- `set_alert_threshold`: Update alert threshold for specific metric.
- `get_alert_thresholds`: Get current alert thresholds.

## regex_patterns

**Location:** `crackerjack/services/regex_patterns.py`

### CompiledPatternCache

**Public Methods:**

- `get_compiled_pattern`:
- `get_compiled_pattern_with_flags`:
- `clear_cache`:
- `get_cache_stats`:

### ValidatedPattern

**Public Methods:**

- `apply`:
- `apply_iteratively`:
- `apply_with_timeout`:
- `test`:
- `search`:
- `findall`:
- `get_performance_stats`:

## secure_path_utils

**Location:** `crackerjack/services/secure_path_utils.py`

### SecurePathValidator

**Public Methods:**

- `validate_safe_path`:
- `validate_file_path`:
- `secure_path_join`:
- `normalize_path`:
- `is_within_directory`:
- `safe_resolve`:
- `validate_file_size`:
- `create_secure_backup_path`:
- `create_secure_temp_file`:

### AtomicFileOperations

**Public Methods:**

- `atomic_write`:
- `atomic_backup_and_write`:

### SubprocessPathValidator

**Public Methods:**

- `validate_subprocess_cwd`:
- `validate_executable_path`:

## secure_status_formatter

**Location:** `crackerjack/services/secure_status_formatter.py`

### StatusVerbosity

### SecureStatusFormatter

**Public Methods:**

- `format_status`:
- `format_error_response`:

## secure_subprocess

**Location:** `crackerjack/services/secure_subprocess.py`

### SecurityError

### CommandValidationError

### EnvironmentValidationError

### SubprocessSecurityConfig

### SecureSubprocessExecutor

**Public Methods:**

- `execute_secure`:

## security

**Location:** `crackerjack/services/security.py`

### SecurityService

**Public Methods:**

- `mask_tokens`:
- `mask_command_output`:
- `create_secure_token_file`:
- `cleanup_token_file`:
- `get_masked_env_summary`:
- `validate_token_format`:
- `create_secure_command_env`:
- `validate_file_safety`:
- `check_hardcoded_secrets`:
- `is_safe_subprocess_call`:

## security_logger

**Location:** `crackerjack/services/security_logger.py`

### SecurityEventType

### SecurityEventLevel

### SecurityEvent

**Public Methods:**

- `to_dict`:

### SecurityLogger

**Public Methods:**

- `log_security_event`:
- `log_path_traversal_attempt`:
- `log_file_size_exceeded`:
- `log_dangerous_path_detected`:
- `log_backup_created`:
- `log_file_cleaned`:
- `log_atomic_operation`:
- `log_validation_failed`:
- `log_temp_file_created`:
- `log_rate_limit_exceeded`:
- `log_subprocess_execution`:
- `log_subprocess_environment_sanitized`:
- `log_subprocess_command_validation`:
- `log_subprocess_timeout`:
- `log_subprocess_failure`:
- `log_dangerous_command_blocked`:
- `log_environment_variable_filtered`:
- `log_status_access_attempt`:
- `log_sensitive_data_sanitized`:
- `log_status_information_disclosure`:

## smart_scheduling

**Location:** `crackerjack/services/smart_scheduling.py`

### SmartSchedulingService

**Public Methods:**

- `should_scheduled_init`:
- `record_init_timestamp`:

## status_authentication

**Location:** `crackerjack/services/status_authentication.py`

### AccessLevel

### AuthenticationMethod

### AuthCredentials

**Public Methods:**

- `is_expired`:
- `has_operation_access`:

### AuthenticationError

### AccessDeniedError

### ExpiredCredentialsError

### StatusAuthenticator

**Public Methods:**

- `authenticate_request`:
- `is_operation_allowed`:
- `add_api_key`:
- `revoke_api_key`:
- `get_auth_status`:

## status_security_manager

**Location:** `crackerjack/services/status_security_manager.py`

### StatusSecurityError

### AccessDeniedError

### ResourceLimitExceededError

### RateLimitExceededError

### StatusSecurityManager

**Public Methods:**

- `validate_request`:
- `get_security_status`:

### RequestLock

## thread_safe_status_collector

**Location:** `crackerjack/services/thread_safe_status_collector.py`

### StatusSnapshot

### ThreadSafeStatusCollector

**Public Methods:**

- `clear_cache`:
- `get_collection_status`:

## tool_version_service

**Location:** `crackerjack/services/tool_version_service.py`

### ToolVersionService

**Public Methods:**

- `check_config_integrity`:
- `should_scheduled_init`:
- `record_init_timestamp`:

## unified_config

**Location:** `crackerjack/services/unified_config.py`

### CrackerjackConfig

**Public Methods:**

- `validate_package_path`:
- `validate_log_file`:
- `validate_test_workers`:
- `validate_min_coverage`:
- `validate_log_level`:

### ConfigSource

**Public Methods:**

- `load`:
- `is_available`:

### EnvironmentConfigSource

**Public Methods:**

- `load`:

### FileConfigSource

**Public Methods:**

- `is_available`:
- `load`:

### PyprojectConfigSource

**Public Methods:**

- `is_available`:
- `load`:

### OptionsConfigSource

**Public Methods:**

- `load`:

### UnifiedConfigurationService

**Public Methods:**

- `get_config`:
- `get_precommit_config_mode`:
- `get_logging_config`:
- `get_hook_execution_config`:
- `get_testing_config`:
- `get_cache_config`:
- `validate_current_config`:

### Config

### DefaultConfigSource

**Public Methods:**

- `load`:

## validation_rate_limiter

**Location:** `crackerjack/services/validation_rate_limiter.py`

### ValidationRateLimit

### ValidationRateLimiter

**Public Methods:**

- `is_blocked`:
- `record_failure`:
- `get_remaining_attempts`:
- `get_block_time_remaining`:
- `get_client_stats`:
- `cleanup_expired_data`:
- `update_rate_limits`:
- `get_all_stats`:

## version_checker

**Location:** `crackerjack/services/version_checker.py`

### VersionInfo

### VersionChecker

## websocket_resource_limiter

**Location:** `crackerjack/services/websocket_resource_limiter.py`

### ConnectionMetrics

**Public Methods:**

- `connection_duration`:
- `idle_time`:

### ResourceLimits

### ResourceExhaustedError

### WebSocketResourceLimiter

**Public Methods:**

- `validate_new_connection`:
- `register_connection`:
- `unregister_connection`:
- `validate_message`:
- `track_message`:
- `get_resource_status`:
- `get_connection_metrics`:
