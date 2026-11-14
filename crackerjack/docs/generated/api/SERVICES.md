# Service Reference

This document describes all service implementations in the codebase.

## \_auth

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pypi_auth/_auth.py`

**Implements:**

- t.Protocol

### PyPIAuth

**Public Methods:**

- `as_uv_publish_token`:

- `is_trusted_publishing`:

- `source`:

### \_TrustedPublishingSentinel

**Public Methods:**

- `as_uv_publish_token`:

- `is_trusted_publishing`:

- `source`:

### PyPIAuthProvider

**Public Methods:**

- `is_available`:

- `resolve`:

## \_providers

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pypi_auth/_providers.py`

### \_EnvVarPyPIAuth

**Public Methods:**

- `source`:

### \_KeyringPyPIAuth

**Public Methods:**

- `source`:

### EnvVarAuthProvider

**Public Methods:**

- `is_available`:

- `resolve`:

### KeyringAuthProvider

**Public Methods:**

- `is_available`:

- `resolve`:

## \_trusted_publishing

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pypi_auth/_trusted_publishing.py`

### TrustedPublishingProvider

**Public Methods:**

- `is_available`:

- `resolve`:

## advanced_optimizer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/advanced_optimizer.py`

### ResourceMetrics

**Public Methods:**

- `to_dict`:

### PerformanceProfile

**Public Methods:**

- `to_dict`:

### OptimizationRecommendation

**Public Methods:**

- `to_dict`:

### ScalingMetrics

**Public Methods:**

- `to_dict`:

### ConnectionPool

**Public Methods:**

- `add_connection`:

- `remove_connection`:

- `update_activity`:

- `get_stats`:

### DataCompactionManager

**Public Methods:**

- `compact_data`:

- `get_storage_usage`:

### AdvancedOptimizer

**Public Methods:**

- `collect_resource_metrics`:

- `analyze_scaling_needs`:

- `generate_optimization_recommendations`:

- `optimize_configuration`:

- `get_advanced_status`:

## anomaly_detector

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/anomaly_detector.py`

### MetricPoint

### AnomalyDetection

### BaselineModel

### AnomalyDetector

**Public Methods:**

- `add_metric`:

- `get_anomalies`:

- `get_baseline_summary`:

- `export_model`:

## anti_ai_flavor

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/anti_ai_flavor.py`

### AntiAIFlavorMatch

**Public Methods:**

- `to_dict`:

### AntiAIFlavorDetector

**Public Methods:**

- `detect`:

- `load_phrases_from_yaml`:

## anti_ai_flavor_adapter

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/anti_ai_flavor_adapter.py`

### AntiAIFlavorReport

**Public Methods:**

- `is_clean`:

- `to_dict`:

## api_extractor

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/api_extractor.py`

**Implements:**

- APIExtractorProtocol

### PythonDocstringParser

**Public Methods:**

- `parse_docstring`:

### APIExtractorImpl

**Public Methods:**

- `extract_from_python_files`:

- `extract_protocol_definitions`:

- `extract_service_interfaces`:

- `extract_cli_commands`:

- `extract_mcp_tools`:

## backup_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/backup_service.py`

### BackupMetadata

### BackupValidationResult

### PackageBackupService

**Public Methods:**

- `model_post_init`:

- `create_package_backup`:

- `restore_from_backup`:

- `cleanup_backup`:

## bounded_status_operations

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/bounded_status_operations.py`

**Implements:**

- BoundedStatusOperationsProtocol

- ServiceProtocol

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

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `get_operation_status`:

- `reset_circuit_breaker`:

## cache

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/cache.py`

### CacheStats

**Public Methods:**

- `hit_rate`:

- `to_dict`:

### CrackerjackCache

**Public Methods:**

- `get_hook_result`:

- `set_hook_result`:

- `get_expensive_hook_result`:

- `set_expensive_hook_result`:

- `get_file_hash`:

- `set_file_hash`:

- `get_config_data`:

- `set_config_data`:

- `get`:

- `set`:

- `get_agent_decision`:

- `set_agent_decision`:

- `get_quality_baseline`:

- `set_quality_baseline`:

- `invalidate_hook_cache`:

- `cleanup_all`:

- `get_cache_stats`:

## changelog_automation

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/changelog_automation.py`

### ChangelogEntry

**Public Methods:**

- `to_markdown`:

### ChangelogGenerator

**Public Methods:**

- `parse_commit_message`:

- `generate_changelog_entries`:

- `update_changelog`:

- `generate_changelog_from_commits`:

## command_execution_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/command_execution_service.py`

### CommandExecutionService

**Public Methods:**

- `run_command_sync`:

## config_cleanup

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/config_cleanup.py`

### ConfigCleanupResult

### MergeStrategy

### ConfigCleanupService

**Public Methods:**

- `cleanup_configs`:

- `rollback_cleanup`:

## config_integrity

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/config_integrity.py`

**Implements:**

- ConfigIntegrityServiceProtocol

- ServiceProtocol

### ConfigIntegrityService

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `check_config_integrity`:

## config_merge

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/config_merge.py`

**Implements:**

- ConfigMergeServiceProtocol

### ConfigMergeService

**Public Methods:**

- `smart_merge_pyproject`:

- `smart_append_file`:

- `smart_merge_gitignore`:

- `smart_merge_pre_commit_config`:

- `write_pre_commit_config`:

- `write_pyproject_config`:

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `get_custom_metric`:

- `increment_requests`:

- `record_error`:

- `set_custom_metric`:

### ParsedContent

## config_parsers

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/config_parsers.py`

**Implements:**

- t.Protocol

### ConfigParser

**Public Methods:**

- `load`:

- `save`:

- `extensions`:

### JSONParser

**Public Methods:**

- `extensions`:

- `load`:

- `save`:

### YAMLParser

**Public Methods:**

- `extensions`:

- `load`:

- `save`:

### TOMLParser

**Public Methods:**

- `extensions`:

- `load`:

- `save`:

### ConfigParserRegistry

**Public Methods:**

- `register`:

- `get_parser`:

- `get_parser_by_format`:

- `list_formats`:

- `is_supported`:

## config_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/config_service.py`

### ConfigService

**Public Methods:**

- `load_config`:

- `validate_config`:

- `save_config`:

- `merge_configs`:

## config_template

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/config_template.py`

### ConfigUpdateInfo

### ConfigVersion

### ConfigTemplateService

**Public Methods:**

- `get_template`:

- `check_updates`:

- `apply_update`:

- `get_config_hash`:

- `list_available_templates`:

## connection_pool

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/connection_pool.py`

### HTTPConnectionPool

**Public Methods:**

- `is_closed`:

## contextual_ai_assistant

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/contextual_ai_assistant.py`

### AIRecommendation

### ProjectContext

### ContextualAIAssistant

**Public Methods:**

- `get_contextual_recommendations`:

- `display_recommendations`:

- `get_quick_help`:

## core

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/patterns/core.py`

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

## coverage_badge_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/coverage_badge_service.py`

### CoverageBadgeService

**Public Methods:**

- `update_readme_coverage_badge`:

- `should_update_badge`:

## coverage_manager

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/testing/coverage_manager.py`

### CoverageManager

**Public Methods:**

- `process_coverage_ratchet`:

- `attempt_coverage_extraction`:

- `handle_coverage_extraction_result`:

- `update_coverage_badge`:

- `handle_ratchet_result`:

## coverage_ratchet

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/coverage_ratchet.py`

**Implements:**

- CoverageRatchetProtocol

### CoverageRatchetService

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `initialize_baseline`:

- `get_ratchet_data`:

- `get_status_report`:

- `get_baseline`:

- `get_baseline_coverage`:

- `update_baseline_coverage`:

- `is_coverage_regression`:

- `calculate_coverage_gap`:

- `update_coverage`:

- `raise_floor`: Raise the enforced floor to `new_coverage` and rewrite the ratchet.

- `get_progress_visualization`:

- `get_coverage_improvement_needed`:

- `display_milestone_celebration`:

- `show_progress_with_spinner`:

- `get_coverage_report`:

- `check_and_update_coverage`:

- `lower_baseline`: Lower the enforced coverage floor, with a recorded reason.

- `mirror_to_pyproject`: Write --cov-fail-under=<coverage> to pyproject.toml.

- `report_status`:

## debug

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/debug.py`

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

- `reset_deduplicator`:

- `export_debug_data`:

### NoOpDebugger

**Public Methods:**

- `reset_deduplicator`:

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

## dependency_analyzer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/dependency_analyzer.py`

### DependencyNode

**Public Methods:**

- `to_dict`:

### DependencyEdge

**Public Methods:**

- `to_dict`:

### DependencyGraph

**Public Methods:**

- `to_dict`:

### DependencyAnalyzer

**Public Methods:**

- `analyze_project`:

### DependencyVisitor

**Public Methods:**

- `visit_Module`:

- `visit_Import`:

- `visit_ImportFrom`:

- `visit_ClassDef`:

- `visit_FunctionDef`:

- `visit_Call`:

## doc_categorizer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/doc_categorizer.py`

### CategoryConfig

### CategoryResult

### DocumentationCategorizer

**Public Methods:**

- `derive_archive_area`: Return the archive area (relative to `self.docs_root`) that a
  file should be archived under, derived from its parent directory.

- `archive_target_path`: Compose the full archive target path for `filepath` given its
  category subdir name. The result lives under
  `<archive_area>/.archive/<category_subdir>/` relative to the
  docs_root.

- `categorize_file`:

- `analyze_all`:

- `get_archivable_files`: Return the list of files that should be archived.

- `get_archive_subdirectory`: Return the category sub-directory for `filepath`.

- `should_keep_in_root`:

- `should_keep_in_docs`:

## doc_update_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/doc_update_service.py`

### CodeChange

### DocUpdate

### DocUpdateResult

### DocUpdateService

**Public Methods:**

- `settings`:

- `update_documentation`:

## documentation_cleanup

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/documentation_cleanup.py`

### DocumentationCleanupResult

### ArchiveMapping

### DocumentationCleanup

**Public Methods:**

- `cleanup_documentation`:

- `rollback_cleanup`:

## documentation_generator

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/documentation_generator.py`

**Implements:**

- DocumentationGeneratorProtocol

### MarkdownTemplateRenderer

**Public Methods:**

- `render_template`:

### DocumentationGeneratorImpl

**Public Methods:**

- `generate_api_reference`:

- `generate_user_guide`:

- `generate_changelog_update`:

- `render_template`:

- `generate_cross_references`:

## documentation_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/documentation_service.py`

**Implements:**

- DocumentationServiceProtocol

### DocumentationServiceImpl

**Public Methods:**

- `extract_api_documentation`:

- `generate_documentation`:

- `validate_documentation`:

- `update_documentation_index`:

- `get_documentation_coverage`:

- `generate_full_api_documentation`:

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `get_custom_metric`:

- `increment_requests`:

- `record_error`:

- `set_custom_metric`:

## embeddings

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/embeddings.py`

### EmbeddingService

**Public Methods:**

- `session`:

- `tokenizer`:

- `generate_embedding`:

- `generate_embeddings_batch`:

- `calculate_similarity`:

- `calculate_similarities_batch`:

- `get_text_hash`:

- `get_file_hash`:

- `chunk_text`:

- `is_model_available`:

- `get_model_info`:

## enhanced_filesystem

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/enhanced_filesystem.py`

**Implements:**

- EnhancedFileSystemServiceProtocol

- ServiceProtocol

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

## failure_metrics_repository

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/failure_metrics_repository.py`

### FailureMetricsRepository

Failure metrics store.

## failure_recorder

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/failure_recorder.py`

**Implements:**

- Protocol

### FixAttemptRecord

**Public Methods:**

- `to_dict`:

### TrendClassification

### \_SessionBuddyProtocol

### FailureRecorder

## file_chunker

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/file_chunker.py`

### FileChunker

**Public Methods:**

- `chunk_files`:

- `should_chunk_files`:

- `estimate_parallel_benefit`:

## file_filter

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/file_filter.py`

**Implements:**

- SmartFileFilterProtocol

- ServiceProtocol

### SmartFileFilter

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `get_changed_files`:

- `get_staged_files`:

- `get_unstaged_files`:

- `filter_by_pattern`:

- `filter_by_tool`:

- `get_all_modified_files`:

- `filter_by_extensions`:

- `get_python_files`:

- `get_markdown_files`:

- `get_changed_python_files_incremental`:

- `get_all_python_files_in_package`:

- `should_include`:

- `filter_files`:

- `should_use_incremental_scan`:

- `get_files_for_qa_scan`:

## file_hasher

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/file_hasher.py`

### FileHasher

**Public Methods:**

- `shutdown`:

- `shutdown_all_instances`:

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

## file_io_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/file_io_service.py`

### FileIOService

**Public Methods:**

- `read_text_file_sync`:

- `write_text_file_sync`:

- `read_json_file_sync`:

- `write_json_file_sync`:

- `read_binary_file_sync`:

- `write_binary_file_sync`:

- `file_exists`:

- `directory_exists`:

## file_modifier

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/file_modifier.py`

**Implements:**

- SafeFileModifierProtocol

- ServiceProtocol

### SafeFileModifier

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `modify_file`:

## filesystem

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/filesystem.py`

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

## frontmatter

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/frontmatter.py`

### Issue

**Public Methods:**

- `format`:

### FileResult

**Public Methods:**

- `issues`:

- `add`:

### VocabFileNotFoundError

The topic vocabulary file is missing from the configured location.

## frontmatter_validator

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/frontmatter_validator.py`

### FrontmatterValidationIssue

### FrontmatterValidationResult

**Public Methods:**

- `from_payload`:

### FrontmatterValidationError

### FrontmatterValidator

**Public Methods:**

- `validate`:

- `validate_or_raise`:

## git

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/git.py`

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

- `push_with_tags`:

- `get_current_branch`:

- `get_commit_message_suggestions`:

- `get_unpushed_commit_count`:

- `get_changed_files_by_extension`:

- `get_current_commit_hash`:

- `reset_hard`:

- `checkout_files`: Revert the given paths in BOTH the working tree AND index to HEAD.

- `rm_files`: Stage removals for `files` (paths relative to `self.pkg_path`).

- `get_changed_files_since`:

- `get_unstaged_files`:

## git_cleanup_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/git_cleanup_service.py`

### DirtyWorkingTreeError

Raised when the working tree is dirty and unsafe rewrites are forbidden.

### GitCommandResult

### GitCleanupResult

### GitCleanupService

**Public Methods:**

- `settings`:

- `cleanup_git_deleted_files`:

## heatmap_generator

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/heatmap_generator.py`

### HeatMapCell

### HeatMapData

**Public Methods:**

- `to_dict`:

### HeatMapGenerator

**Public Methods:**

- `add_error_data`:

- `add_metric_data`:

- `generate_error_frequency_heatmap`:

- `generate_code_complexity_heatmap`:

- `generate_quality_metrics_heatmap`:

- `generate_test_failure_heatmap`:

- `export_heatmap_data`:

- `generate_html_visualization`:

## import_resolution

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/import_resolution.py`

### ImportSpec

## improvement_generator

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/improvement_generator.py`

### ImprovementProposal

**Public Methods:**

- `is_auto_apply_candidate`:

### ImprovementGenerator

## improvement_overseer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/improvement_overseer.py`

### OverseerVerdict

### ImprovementOverseer

**Public Methods:**

- `build_review_context`:

## incremental_executor

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/incremental_executor.py`

### FileHash

### CacheEntry

### ExecutionResult

**Public Methods:**

- `cache_effective`:

### IncrementalExecutor

**Public Methods:**

- `execute_incremental`:

- `get_changed_files`:

- `invalidate_file`:

- `clear_cache`:

- `get_cache_stats`:

## incremental_scanner

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/incremental_scanner.py`

### IncrementalScanner

**Public Methods:**

- `get_scan_strategy`:

## initialization

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/initialization.py`

### InitializationService

**Public Methods:**

- `initialize_project`:

- `setup_git_hooks`:

- `validate_project_structure`:

- `initialize_project_full`:

- `check_uv_installed`:

## input_validator

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/input_validator.py`

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

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/intelligent_commit.py`

### CommitMessageGenerator

**Public Methods:**

- `generate_commit_message`:

- `commit_with_generated_message`:

## log_manager

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/log_manager.py`

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

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/logging.py`

### LoggingContext

## mahavishnu_discovery

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/mahavishnu_discovery.py`

### MahavishnuUnreachable

Internal: probe failed. Callers should NOT raise this — soft fallback.

## marker_tracker

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/marker_tracker.py`

### MarkerTracker

**Public Methods:**

- `get_files_needing_scan`:

- `mark_scanned`:

- `mark_full_scan_complete`:

## memory_aware_scanner

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/memory_aware_scanner.py`

### MemoryAwareScanner

## memory_optimizer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/memory_optimizer.py`

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

## mermaid_renderer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/mermaid_renderer.py`

### MermaidBlock

A fenced mermaid block found in a `.md` file.

### MermaidValidationError

A mermaid block that failed to parse.

**Public Methods:**

- `relpath`:

## message_deduplicator

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/message_deduplicator.py`

### MessageDeduplicator

**Public Methods:**

- `add_message`:

- `should_show`:

- `get_duplicates`:

- `get_summary`:

- `print_summary`:

- `reset`:

- `total_messages`:

- `unique_messages`:

- `duplicate_count`:

## metrics

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/metrics.py`

### MetricsCollector

**Public Methods:**

- `execute`:

- `execute_query`:

- `track_provider_selection`:

- `track_agent_execution`:

- `get_provider_stats`:

- `get_agent_stats`:

- `get_agent_success_rate`:

- `get_provider_availability`:

- `get_agent_confidence_distribution`:

- `close`:

## operations

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/patterns/operations.py`

### RegexPatternsService

**Public Methods:**

- `update_pyproject_version`:

- `remove_coverage_fail_under`:

- `update_version_in_changelog`:

- `mask_tokens_in_text`:

## parallel_executor

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/parallel_executor.py`

**Implements:**

- ParallelHookExecutorProtocol

- ServiceProtocol

- AsyncCommandExecutorProtocol

- ServiceProtocol

### ExecutionStrategy

### ExecutionGroup

### ParallelHookExecutor

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `analyze_hook_dependencies`:

- `can_execute_in_parallel`:

### AsyncCommandExecutor

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

## pattern_cache

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/pattern_cache.py`

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

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pattern_detector.py`

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

## pool_client

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pool_client.py`

### CrackerjackPoolClient

## pool_orchestrator

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pool_orchestrator.py`

**Implements:**

- ServiceProtocol

### PoolExecutionResult

**Public Methods:**

- `passed_count`:

- `failed_count`:

### PoolOrchestrator

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `record_error`:

- `increment_requests`:

- `register_resource`:

- `cleanup_resource`:

- `get_custom_metric`:

- `set_custom_metric`:

## pool_router

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pool_router.py`

### PoolRouter

**Public Methods:**

- `get_routing_summary`:

## pool_scaler

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pool_scaler.py`

### PoolScaler

**Public Methods:**

- `get_status`:

## predictive_analytics

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/predictive_analytics.py`

**Implements:**

- t.Protocol

### PredictorProtocol

**Public Methods:**

- `predict`:

### TrendAnalysis

### Prediction

### CapacityForecast

### MovingAveragePredictor

**Public Methods:**

- `predict`:

### LinearTrendPredictor

**Public Methods:**

- `predict`:

### SeasonalPredictor

**Public Methods:**

- `predict`:

### PredictiveAnalyticsEngine

**Public Methods:**

- `add_metric`:

- `predict_metric`:

- `analyze_capacity_requirements`:

- `get_trend_summary`:

- `export_analytics_data`:

## profiler

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/profiler.py`

### ProfileResult

**Public Methods:**

- `mean_time`:

- `median_time`:

- `std_dev_time`:

- `mean_memory`:

- `cache_hit_rate`:

### Bottleneck

### ComparisonReport

**Public Methods:**

- `time_ratio`:

### ToolProfiler

**Public Methods:**

- `profile_tool`:

- `compare_phases`:

- `identify_bottlenecks`:

- `generate_report`:

## prompt_evolution

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/prompt_evolution.py`

### FailedFixAttempt

### SuccessfulFixPattern

### PromptEvolution

**Public Methods:**

- `record_failed_fix`:

- `record_successful_fix`:

- `get_evolved_prompt`:

- `analyze_failure_patterns`:

- `get_success_rate`:

## pycharm_mcp_integration

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pycharm_mcp_integration.py`

### CircuitBreakerState

**Public Methods:**

- `record_failure`:

- `record_success`:

- `can_execute`:

### SearchResult

### PyCharmMCPAdapter

**Public Methods:**

- `clear_cache`:

### MahavishnuPycharmMCPClient

## pypistats_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/pypistats_service.py`

### DownloadTrendClass

### PackageStatsSnapshot

### PypiStatsService

**Public Methods:**

- `get_snapshot`:

- `classify_download_trend`:

## quality_baseline_enhanced

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/quality_baseline_enhanced.py`

### TrendDirection

### AlertSeverity

### EnhancedQualityBaselineService

**Public Methods:**

- `get_recent_baselines`:

## quality_intelligence

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/quality_intelligence.py`

### AnomalyType

### PatternType

### QualityAnomaly

**Public Methods:**

- `to_dict`:

### QualityPattern

**Public Methods:**

- `to_dict`:

### QualityPrediction

**Public Methods:**

- `to_dict`:

### QualityInsights

**Public Methods:**

- `to_dict`:

### QualityIntelligenceService

**Public Methods:**

- `detect_anomalies`:

- `identify_patterns`:

- `generate_advanced_predictions`:

- `generate_comprehensive_insights`:

## refurb_fixer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/refurb_fixer.py`

### SafeRefurbFixer

**Public Methods:**

- `fix_file`:

- `fix_package`:

### \_StartswithTupleTransformer

**Public Methods:**

- `visit_BoolOp`:

### \_MembershipTupleTransformer

**Public Methods:**

- `visit_Compare`:

### \_ForLoopTupleTransformer

**Public Methods:**

- `visit_For`:

## run_state_store

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/testing/run_state_store.py`

### RunStateStore

SQLite-backed store of per-test run results.

**Public Methods:**

- `db_path`:

- `record_run`: Record one test run and its per-test results.

- `get_run`: Return the most recent run for a commit, or `None`.

- `list_runs`: Return every recorded run for a commit, newest first.

- `get_test_results`: Return the per-test results recorded for a run.

- `summarize`: Aggregate the recorded runs.

- `get_status_map`: Return `{node_id: status}` for a run - the diffing primitive.

## safe_code_modifier

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/safe_code_modifier.py`

### ValidationSeverity

### ValidationIssue

### ValidationResult

**Public Methods:**

- `errors`:

- `warnings`:

### BackupMetadata

### SafeCodeModifier

**Public Methods:**

- `apply_with_backup`: Write `new_content` to `path`, optionally leaving a `.bak` sibling.

## secure_path_utils

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/secure_path_utils.py`

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

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/secure_status_formatter.py`

**Implements:**

- SecureStatusFormatterProtocol

- ServiceProtocol

### StatusVerbosity

### SecureStatusFormatter

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `format_status`:

- `format`:

- `format_error_response`:

## secure_subprocess

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/secure_subprocess.py`

### SecurityError

### CommandValidationError

### EnvironmentValidationError

### SubprocessSecurityConfig

### SecureSubprocessExecutor

**Public Methods:**

- `execute_secure`:

## security

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/security.py`

**Implements:**

- SecurityServiceProtocol

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

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `get_custom_metric`:

- `increment_requests`:

- `record_error`:

- `set_custom_metric`:

## security_logger

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/security_logger.py`

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

## self_patcher

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/self_patcher.py`

### SelfPatcher

**Public Methods:**

- `sentinel_path`:

- `validate_diff`:

## smart_file_filter_v2

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/smart_file_filter_v2.py`

**Implements:**

- ServiceProtocol

### SmartFileFilterV2

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `get_files_for_scan`:

- `mark_scan_complete`:

## smart_scheduling

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/smart_scheduling.py`

**Implements:**

- SmartSchedulingServiceProtocol

- ServiceProtocol

### SmartSchedulingService

**Public Methods:**

- `initialize`:

- `cleanup`:

- `health_check`:

- `shutdown`:

- `metrics`:

- `is_healthy`:

- `register_resource`:

- `cleanup_resource`:

- `record_error`:

- `increment_requests`:

- `get_custom_metric`:

- `set_custom_metric`:

- `should_scheduled_init`:

- `record_init_timestamp`:

## status_authentication

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/status_authentication.py`

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

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/status_security_manager.py`

### StatusSecurityError

### AccessDeniedError

### ResourceLimitExceededError

### RateLimitExceededError

### StatusSecurityManager

**Public Methods:**

- `validate_request`:

- `get_security_status`:

### RequestLock

## swarm_client

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/swarm_client.py`

**Implements:**

- Protocol

### SwarmMode

### SwarmTask

### SwarmResult

### SwarmClientProtocol

**Public Methods:**

- `mode`:

### MahavishnuSwarmClient

**Public Methods:**

- `mode`:

### LocalSequentialClient

**Public Methods:**

- `mode`:

### SwarmManager

**Public Methods:**

- `mode`:

- `is_parallel`:

- `is_initialized`:

- `get_status`:

## template_applicator

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/template_applicator.py`

### TemplateApplicator

**Public Methods:**

- `apply_template`:

- `get_available_templates`:

## template_detector

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/template_detector.py`

### TemplateDetector

**Public Methods:**

- `detect_template`:

- `get_template_description`:

- `prompt_manual_selection`:

## test_result_parser

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/testing/test_result_parser.py`

### TestErrorType

### TestFailure

**Public Methods:**

- `to_issue`:

### TestResultParser

**Public Methods:**

- `parse_text_output`:

- `parse_json_output`:

- `parse_statistics`:

## test_result_renderer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/testing/test_result_renderer.py`

### TestResultRenderer

**Public Methods:**

- `render_test_results_panel`:

- `render_banner`:

- `should_render_test_panel`:

- `render_parsing_error_message`:

## thread_safe_status_collector

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/thread_safe_status_collector.py`

### StatusSnapshot

### ThreadSafeStatusCollector

**Public Methods:**

- `clear_cache`:

- `get_collection_status`:

## tool_filter

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/tool_filter.py`

### FilterConfig

### FilterResult

**Public Methods:**

- `tools_filtered_out`:

- `files_filtered_out`:

### ToolFilter

**Public Methods:**

- `filter_tools`:

- `filter_files`:

- `should_run_tool`:

- `get_filtered_files`:

- `estimate_time_savings`:

- `generate_filter_summary`:

## tool_version_service

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/tool_version_service.py`

### ToolVersionService

**Public Methods:**

- `check_config_integrity`:

- `should_scheduled_init`:

- `record_init_timestamp`:

## unified_config

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/unified_config.py`

### UnifiedConfigurationService

**Public Methods:**

- `get_config`:

- `get_logging_config`:

- `get_hook_execution_config`:

- `get_testing_config`:

- `get_cache_config`:

- `validate_current_config`:

## validation_rate_limiter

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/validation_rate_limiter.py`

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

## vector_store

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/vector_store.py`

### VectorStore

**Public Methods:**

- `index_file`:

- `search`:

- `get_stats`:

- `remove_file`:

- `clear_index`:

- `close`:

## version_analyzer

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/version_analyzer.py`

### VersionBumpType

### VersionBumpRecommendation

### BreakingChangeAnalyzer

**Public Methods:**

- `analyze`:

### FeatureAnalyzer

**Public Methods:**

- `analyze`:

### ConventionalCommitAnalyzer

**Public Methods:**

- `analyze`:

### VersionAnalyzer

**Public Methods:**

- `display_recommendation`:

## version_checker

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/version_checker.py`

### VersionInfo

### VersionChecker

## workflow_optimization

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/workflow_optimization.py`

### WorkflowRecommendation

### WorkflowInsights

### WorkflowOptimizationEngine

**Public Methods:**

- `analyze_velocity_patterns`:

- `identify_bottlenecks`:

- `generate_recommendations`:

- `generate_insights`:
