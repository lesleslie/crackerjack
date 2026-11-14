# Cross References

This document shows where API components are used throughout the codebase.

## AIConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## AIFixEvent

**Referenced in:**

- RunStarted base class

- IterationStarted base class

- AgentDispatched base class

- IssueResolved base class

- IssueFailed base class

- IterationFinished base class

- RunFinished base class

- PhaseChanged base class

- PreflightStarted base class

- PreflightFinished base class

- FixSessionStarted base class

- TierTransitioned base class

- FixSessionFinished base class

## AIRecommendation

**Referenced in:**

- ContextualAIAssistant.display_recommendations() parameter

## AISettings

**Referenced in:**

- AIConfig.from_settings() parameter

## APIExtractorProtocol

**Referenced in:**

- APIExtractorImpl base class

- DocumentationServiceImpl.__init__() parameter

## AbstractFileResource

**Referenced in:**

- AtomicFileWriter base class

- LockedFileResource base class

- SafeDirectoryCreator base class

## AbstractManagedResource

**Referenced in:**

- AbstractFileResource base class

- AbstractProcessResource base class

- AbstractTaskResource base class

- AbstractNetworkResource base class

## AccessLevel

**Referenced in:**

- StatusAuthenticator.__init__() parameter

- StatusAuthenticator.\_has_sufficient_access_level() parameter

- StatusAuthenticator.\_has_sufficient_access_level() parameter

- StatusAuthenticator.is_operation_allowed() parameter

- StatusAuthenticator.add_api_key() parameter

## AdapterAttemptRecord

**Referenced in:**

- AdapterLearnerProtocol.record_adapter_attempt() parameter

- NoOpAdapterLearner.record_adapter_attempt() parameter

- SQLiteAdapterLearner.record_adapter_attempt() parameter

- SQLiteAdapterLearner.\_update_effectiveness_metrics() parameter

## AdvancedConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## AdvancedSettings

**Referenced in:**

- AdvancedConfig.from_settings() parameter

## AntiPattern

**Referenced in:**

- PatternDetector.\_generate_solution_key() parameter

- PatternDetector.\_find_cached_pattern_for_anti_pattern() parameter

- PatternDetector.\_create_temp_issue_for_lookup() parameter

## AsyncCleanupProtocol

**Referenced in:**

- ResourceManagerProtocol.register_resource() parameter

## AsyncCommandExecutorProtocol

**Referenced in:**

- AsyncCommandExecutor base class

## AsyncHookExecutor

**Referenced in:**

- AsyncHookManager.__init__() parameter

## AsyncHookExecutorProtocol

**Referenced in:**

- AsyncHookManager.__init__() parameter

## AuthCredentials

**Referenced in:**

- StatusAuthenticator.\_validate_credentials() parameter

- StatusAuthenticator.\_check_operation_access() parameter

## AuthenticationError

**Referenced in:**

- AccessDeniedError base class

- ExpiredCredentialsError base class

## BackupMetadata

**Referenced in:**

- CodeCleaner.\_handle_no_files_to_process() parameter

- CodeCleaner.\_execute_cleaning_with_backup() parameter

- CodeCleaner.\_finalize_cleaning_result() parameter

- CodeCleaner.\_handle_cleaning_failure() parameter

- CodeCleaner.\_handle_cleaning_success() parameter

- CodeCleaner.\_handle_critical_error() parameter

- CodeCleaner.\_attempt_emergency_restoration() parameter

- CodeCleaner.restore_from_backup_metadata() parameter

- CodeCleaner.restore_emergency_backup() parameter

- CodeCleaner.verify_backup_integrity() parameter

- DocumentationCleanup.rollback_cleanup() parameter

- PackageBackupService.restore_from_backup() parameter

- PackageBackupService.cleanup_backup() parameter

- PackageBackupService.\_validate_backup() parameter

- PackageBackupService.\_stage_backup_files() parameter

- PackageBackupService.\_commit_restoration() parameter

- ConfigCleanupService.rollback_cleanup() parameter

## BaseCodeFixer

**Referenced in:**

- FallbackChainCodeFixer base class

- BaseCodeFixer.__init__() parameter

## BaseCodeFixerSettings

**Referenced in:**

- FallbackChainSettings base class

- BaseCodeFixer.__init__() parameter

## BaselineModel

**Referenced in:**

- AnomalyDetector.\_get_seasonal_adjustment() parameter

- AnomalyDetector.\_calculate_severity() parameter

- AnomalyDetector.\_calculate_z_score() parameter

- AnomalyDetector.\_calculate_confidence() parameter

- AnomalyDetector.\_generate_anomaly_description() parameter

## BoundedStatusOperationsProtocol

**Referenced in:**

- BoundedStatusOperations base class

## CachedHookExecutor

**Referenced in:**

- SmartCacheManager.__init__() parameter

## ChangelogEntry

**Referenced in:**

- ChangelogGenerator.\_add_entry_to_collection() parameter

- ChangelogGenerator.\_add_entry_to_collection() parameter

- ChangelogGenerator.update_changelog() parameter

- ChangelogGenerator.\_generate_changelog_section() parameter

- ChangelogGenerator.\_display_changelog_preview() parameter

- BreakingChangeAnalyzer.analyze() parameter

- FeatureAnalyzer.analyze() parameter

- ConventionalCommitAnalyzer.analyze() parameter

- VersionAnalyzer.\_analyze_entries_and_recommend() parameter

- VersionAnalyzer.\_determine_bump_type() parameter

## ChangelogGenerator

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_changelog_generator() parameter

## ChangelogGeneratorProtocol

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_changelog_generator() parameter

## CleaningConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## CleaningResult

**Referenced in:**

- CrackerjackAPI.\_report_safe_cleaning_results() parameter

- CrackerjackAPI.\_report_cleaning_results() parameter

- CleaningErrorHandler.log_cleaning_result() parameter

- CodeCleaner.\_handle_cleaning_failure() parameter

- CodeCleaner.\_handle_cleaning_success() parameter

## CleaningSettings

**Referenced in:**

- CleaningConfig.from_settings() parameter

## CleaningStepProtocol

**Referenced in:**

- CleaningPipeline.clean_file() parameter

- CleaningPipeline.\_apply_cleaning_pipeline() parameter

## CleanupConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## CleanupSettings

**Referenced in:**

- CleanupConfig.from_settings() parameter

## CloneGroup

**Referenced in:**

- CloneRefactorEngine.confidence_gate() parameter

## CloneType

**Referenced in:**

- CloneGrouper.\_make_group_id() parameter

## CodeChange

**Referenced in:**

- DocUpdateService.\_generate_doc_updates() parameter

- DocUpdateService.\_build_update_prompt() parameter

- DocUpdateService.\_is_change_relevant() parameter

## CommandInfo

**Referenced in:**

- ReferenceGenerator.\_create_command_visitor() parameter

- ReferenceGenerator.\_process_function_node() parameter

- ReferenceGenerator.\_add_basic_example() parameter

- ReferenceGenerator.\_add_parameter_examples() parameter

- ReferenceGenerator.\_assign_command_workflows() parameter

- ReferenceGenerator.\_add_ai_context_to_command() parameter

- ReferenceGenerator.\_add_test_ai_context() parameter

- ReferenceGenerator.\_add_quality_ai_context() parameter

- ReferenceGenerator.\_categorize_commands() parameter

- ReferenceGenerator.\_determine_command_category() parameter

- ReferenceGenerator.\_generate_workflows() parameter

- ReferenceGenerator.\_render_markdown_category() parameter

- ReferenceGenerator.\_render_command_markdown() parameter

- ReferenceGenerator.\_render_html_category() parameter

- ReferenceGenerator.\_render_html_category_commands() parameter

- ReferenceGenerator.\_render_single_html_command() parameter

- ReferenceGenerator.\_serialize_commands() parameter

- ReferenceGenerator.\_serialize_command() parameter

- ReferenceGenerator.\_render_rst_category_commands() parameter

## CommandReference

**Referenced in:**

- ReferenceGenerator.\_render_markdown() parameter

- ReferenceGenerator.\_render_markdown_categories() parameter

- ReferenceGenerator.\_render_html() parameter

- ReferenceGenerator.\_render_html_commands() parameter

- ReferenceGenerator.\_render_json() parameter

- ReferenceGenerator.\_render_yaml() parameter

- ReferenceGenerator.\_render_rst() parameter

- ReferenceGenerator.\_render_rst_categories() parameter

## CommandResult

**Referenced in:**

- EnhancedCommandRunner.handle_result() parameter

## ComponentHealth

**Referenced in:**

- SystemHealthReport.from_category_health() parameter

## ConfigCleanupResult

**Referenced in:**

- ConfigCleanupService.\_generate_summary() parameter

- ConfigCleanupService.\_display_completion() parameter

## ConfigIntegrityServiceProtocol

**Referenced in:**

- ConfigIntegrityService base class

## ConfigManager

**Referenced in:**

- ReferenceGenerator.__init__() parameter

- MkDocsIntegrationService.__init__() parameter

- AITemplateEngine.__init__() parameter

## ConfigManagerProtocol

**Referenced in:**

- ReferenceGenerator.__init__() parameter

- MkDocsIntegrationService.__init__() parameter

- AITemplateEngine.__init__() parameter

## ConfigMergeService

**Referenced in:**

- InitializationService.__init__() parameter

## ConfigMergeServiceProtocol

**Referenced in:**

- ConfigMergeService base class

- InitializationService.__init__() parameter

## ConfigParser

**Referenced in:**

- ConfigParserRegistry.register() parameter

## ConfigVersion

**Referenced in:**

- ConfigTemplateService.\_apply_pyproject_update() parameter

## ConsoleInterface

**Referenced in:**

- CrackerjackAPI.__init__() parameter

- WorkflowBuilder.__init__() parameter

- WorkflowManager.__init__() parameter

- InteractiveCLI.__init__() parameter

- CrackerjackConsole base class

- AsyncWorkflowPipeline.__init__() parameter

- SessionCoordinator.__init__() parameter

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_console() parameter

- AsyncHookManager.__init__() parameter

- TestManager.__init__() parameter

- CrackerjackCLIFacade.__init__() parameter

- AsyncHookExecutor.__init__() parameter

- HookExecutor.__init__() parameter

- GitService.__init__() parameter

- PoolOrchestrator.__init__() parameter

- ConfigMergeService.__init__() parameter

- TestResultRenderer.__init__() parameter

- CoverageManager.__init__() parameter

## CorrelationStorage

**Referenced in:**

- SessionBuddyIntegration.__init__() parameter

## CoverageBadgeService

**Referenced in:**

- TestManager.__init__() parameter

- CoverageManager.__init__() parameter

## CoverageBadgeServiceProtocol

**Referenced in:**

- TestManager.__init__() parameter

- CoverageManager.__init__() parameter

## CoverageManager

**Referenced in:**

- TestManager.__init__() parameter

## CoverageRatchetProtocol

**Referenced in:**

- TestManager.__init__() parameter

- CoverageRatchetService base class

- CoverageManager.__init__() parameter

## CrackerjackCache

**Referenced in:**

- DualOutputGenerator.__init__() parameter

- CachedHookExecutor.__init__() parameter

- FileHasher.__init__() parameter

## CrackerjackConsole

**Referenced in:**

- ServiceWatchdog.__init__() parameter

## CrackerjackError

**Referenced in:**

- Task.fail() parameter

- ConfigError base class

- ExecutionError base class

- TestExecutionError base class

- PublishError base class

- GitError base class

- FileError base class

- CleaningError base class

- NetworkError base class

- DependencyError base class

- ResourceError base class

- ValidationError base class

- TimeoutError base class

- SecurityError base class

- InteractiveTask.fail() parameter

## CrackerjackSettings

**Referenced in:**

- CrackerjackMCPSettings.from_crackerjack_settings() parameter

- TestCommandBuilder.__init__() parameter

- HookManagerImpl.__init__() parameter

- WorkflowOptions.from_settings() parameter

- DocumentationCleanup.__init__() parameter

- DocUpdateService.__init__() parameter

- GitCleanupService.__init__() parameter

- ConfigCleanupService.__init__() parameter

- \_AdaptedOptions.__init__() parameter

## CustomHookDefinition

**Referenced in:**

- CustomHookPlugin.__init__() parameter

- CustomHookPlugin.\_execute_command_hook() parameter

## DAGExecutionRecord

**Referenced in:**

- DAGO_optimizerProtocol.record_execution() parameter

- NoOpDAGO_optimizer.record_execution() parameter

- SQLiteDAGO_optimizer.record_execution() parameter

- SQLiteDAGO_optimizer.\_update_optimal_strategy() parameter

## DependencyGraph

**Referenced in:**

- HeatMapGenerator.\_extract_file_complexity_data() parameter

## DocUpdate

**Referenced in:**

- DocUpdateService.\_apply_doc_updates() parameter

- DocUpdateService.\_create_update_commits() parameter

- DocUpdateService.\_generate_dry_run_summary() parameter

- DocUpdateService.\_generate_update_summary() parameter

## DocumentationCleanup

**Referenced in:**

- DocumentationCleanup.\_generate_summary() parameter

- DocumentationCleanup.\_display_completion() parameter

## DocumentationCleanupResult

**Referenced in:**

- DocumentationCleanup.\_generate_summary() parameter

- DocumentationCleanup.\_display_completion() parameter

## DocumentationGeneratorProtocol

**Referenced in:**

- DocumentationGeneratorImpl base class

- DocumentationServiceImpl.__init__() parameter

## DocumentationResult

**Referenced in:**

- DualOutputGenerator.\_cache_generation_metadata() parameter

## DocumentationServiceProtocol

**Referenced in:**

- DocumentationServiceImpl base class

## EmbeddingService

**Referenced in:**

- VectorStore.__init__() parameter

## EmbeddingVector

**Referenced in:**

- VectorStore.\_store_embeddings() parameter

## EnhancedFileSystemServiceProtocol

**Referenced in:**

- EnhancedFileSystemService base class

## EnhancedQualityBaselineService

**Referenced in:**

- QualityIntelligenceService.__init__() parameter

## Entry

**Referenced in:**

- FailureModeCatalog.add() parameter

- ChangelogGenerator.\_add_entry_to_collection() parameter

- ChangelogGenerator.\_add_entry_to_collection() parameter

- ChangelogGenerator.update_changelog() parameter

- ChangelogGenerator.\_generate_changelog_section() parameter

- ChangelogGenerator.\_display_changelog_preview() parameter

- BreakingChangeAnalyzer.analyze() parameter

- FeatureAnalyzer.analyze() parameter

- ConventionalCommitAnalyzer.analyze() parameter

- VersionAnalyzer.\_analyze_entries_and_recommend() parameter

- VersionAnalyzer.\_determine_bump_type() parameter

- AntiAIFlavorDetector.__init__() parameter

## ErrorCode

**Referenced in:**

- CrackerjackError.__init__() parameter

- ConfigError.__init__() parameter

- ExecutionError.__init__() parameter

- TestExecutionError.__init__() parameter

- FileError.__init__() parameter

## ErrorPattern

**Referenced in:**

- ErrorCache.\_update_existing_pattern() parameter

- ErrorCache.\_update_existing_pattern() parameter

- ErrorCache.\_merge_fixes() parameter

## EvolutionTrigger

**Referenced in:**

- EvolutionEngine.__init__() parameter

## ExecutionConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## ExecutionSettings

**Referenced in:**

- ExecutionConfig.from_settings() parameter

## ExecutionStrategy

**Referenced in:**

- ParallelHookExecutor.__init__() parameter

## FailedGitResult

**Referenced in:**

- GitService.\_handle_commit_failure() parameter

- GitService.\_handle_hook_error() parameter

## FailureMetricsRepository

**Referenced in:**

- ImprovementGenerator.__init__() parameter

- FailureRecorder.__init__() parameter

## FailureModeCatalog

**Referenced in:**

- FailureModeCatalog.add() parameter

- EvolutionEngine.__init__() parameter

## FailureModeCatalogEntry

**Referenced in:**

- FailureModeCatalog.add() parameter

## FailureRecorder

**Referenced in:**

- ImprovementGenerator.__init__() parameter

## FallbackChainSettings

**Referenced in:**

- FallbackChainCodeFixer.__init__() parameter

## FileChunkingSettings

**Referenced in:**

- FileChunker.__init__() parameter

## FileHash

**Referenced in:**

- SmartFileWatcher.__init__() parameter

- IncrementalExecutor.\_cache_key() parameter

## FileHasher

**Referenced in:**

- SmartFileWatcher.__init__() parameter

## FileSystemInterface

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_filesystem() parameter

- FileSystemService base class

- ConfigMergeService.__init__() parameter

- ContextualAIAssistant.__init__() parameter

## FileSystemService

**Referenced in:**

- MkDocsIntegrationService.__init__() parameter

- InitializationService.__init__() parameter

## FileSystemServiceProtocol

**Referenced in:**

- MkDocsIntegrationService.__init__() parameter

## FilterConfig

**Referenced in:**

- ToolFilter.__init__() parameter

## FilterResult

**Referenced in:**

- ToolFilter.generate_filter_summary() parameter

- ToolFilter.generate_filter_summary() parameter

## FixResult

**Referenced in:**

- FixResult.merge_with() parameter

- PatternCache.cache_successful_pattern() parameter

- PatternCache.cache_successful_pattern() parameter

## FrontmatterValidationResult

**Referenced in:**

- PhaseCoordinator.\_format_frontmatter_errors() parameter

- PhaseCoordinator.\_format_frontmatter_warnings() parameter

- FrontmatterValidationError.__init__() parameter

## GenericRegexParser

**Referenced in:**

- ValidateRegexPatternsParser base class

- TrailingWhitespaceParser base class

- EndOfFileFixerParser base class

- FormatJsonParser base class

- MdformatParser base class

- UvLockParser base class

- CheckAstParser base class

## GitConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## GitInterface

**Referenced in:**

- DocumentationCleanup.__init__() parameter

- GitService base class

- DocUpdateService.__init__() parameter

- ConfigMergeService.__init__() parameter

- CommitMessageGenerator.__init__() parameter

- GitCleanupService.__init__() parameter

- ConfigCleanupService.__init__() parameter

- CommitMessageGenerator.__init__() parameter

## GitMetricsReader

**Referenced in:**

- SessionBuddyIntegration.__init__() parameter

## GitMetricsSessionCollector

**Referenced in:**

- SessionCoordinator.__init__() parameter

## GitService

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_git_service() parameter

- HookManagerImpl.\_setup_git_service() parameter

- SmartFileFilter.__init__() parameter

- InitializationService.__init__() parameter

- VersionAnalyzer.__init__() parameter

## GitSettings

**Referenced in:**

- GitConfig.from_settings() parameter

## GitTagVersionSource

**Referenced in:**

- SwiftLifecycle.__init__() parameter

## GitleaksJSONParser

**Referenced in:**

- BetterleaksJSONParser base class

## GlobalLockSettings

**Referenced in:**

- GlobalLockConfig.__init__() parameter

## GradlePropertiesVersionSource

**Referenced in:**

- KotlinLifecycle.__init__() parameter

## HealthCheckResult

**Referenced in:**

- ComponentHealth.from_results() parameter

## HealthStatus

**Referenced in:**

- HealthStatus.__lt__() parameter

## HeatMapCell

**Referenced in:**

- HeatMapGenerator.\_create_complexity_labels() parameter

## HeatMapData

**Referenced in:**

- HeatMapGenerator.export_heatmap_data() parameter

- HeatMapGenerator.generate_html_visualization() parameter

## Hook

**Referenced in:**

- PhaseCoordinator.\_execute_hooks_once() parameter

- PhaseCoordinator.\_run_hooks_with_progress() parameter

- PhaseCoordinator.\_report_hook_results() parameter

- PhaseCoordinator.\_render_hook_results_table() parameter

- PhaseCoordinator.\_render_plain_hook_results() parameter

- PhaseCoordinator.\_calculate_hook_statistics() parameter

- PhaseCoordinator.\_should_update_hook_count() parameter

- PhaseCoordinator.\_try_update_count_from_json() parameter

- PhaseCoordinator.\_print_plain_hook_result() parameter

- PhaseCoordinator.\_render_rich_hook_results() parameter

- PhaseCoordinator.\_build_results_table() parameter

- PhaseCoordinator.to_json() parameter

- PhaseCoordinator.\_format_failing_hooks() parameter

- PhaseCoordinator.\_display_issue_details() parameter

- PhaseCoordinator.\_display_timeout_info() parameter

- PhaseCoordinator.\_display_exit_code_info() parameter

- PhaseCoordinator.\_display_error_message() parameter

- PhaseCoordinator.\_display_generic_failure() parameter

- PhaseCoordinator.\_display_hook_failures() parameter

- PhaseCoordinator.\_print_single_hook_failure() parameter

- PhaseCoordinator.\_print_hook_issues() parameter

- PhaseCoordinator.\_display_failure_reasons() parameter

- PhaseCoordinator.\_display_ruff_failure_details() parameter

- PhaseCoordinator.\_extract_ruff_diagnostics_from_output() parameter

- CustomHookPlugin.__init__() parameter

- CustomHookPlugin.\_execute_command_hook() parameter

- HookPluginRegistry.register_hook_plugin() parameter

- PluginManager.__init__() parameter

- HookManagerImpl.\_filter_strategy_for_tool() parameter

- HookManagerImpl.get_hook_summary() parameter

- AsyncHookManager.__init__() parameter

- AsyncHookManager.__init__() parameter

- AsyncHookManager.get_hook_summary() parameter

- HookConfig.from_settings() parameter

- WorkflowOptions.\_initialize_config_attributes() parameter

- AsyncHookExecutor.__init__() parameter

- AsyncHookExecutor.\_print_strategy_header() parameter

- AsyncHookExecutor.\_execute_hook_sync() parameter

- AsyncHookExecutor.\_execute_hook_sync() parameter

- AsyncHookExecutor.\_log_termination_error() parameter

- AsyncHookExecutor.\_handle_runtime_error() parameter

- AsyncHookExecutor.\_handle_general_error() parameter

- AsyncHookExecutor.\_display_hook_result() parameter

- AsyncHookExecutor.\_print_summary() parameter

- AsyncHookExecutor.\_print_summary() parameter

- IndividualHookExecutor.__init__() parameter

- IndividualHookExecutor.set_progress_callback() parameter

- IndividualHookExecutor.\_update_hook_progress_status() parameter

- IndividualHookExecutor.\_update_hook_progress_status() parameter

- IndividualHookExecutor.\_finalize_execution_result() parameter

- IndividualHookExecutor.\_create_stream_reader_tasks() parameter

- IndividualHookExecutor.\_update_progress_with_line() parameter

- IndividualHookExecutor.\_maybe_callback_progress() parameter

- IndividualHookExecutor.\_print_strategy_header() parameter

- IndividualHookExecutor.\_print_hook_summary() parameter

- IndividualHookExecutor.\_print_hook_summary() parameter

- IndividualHookExecutor.\_print_individual_summary() parameter

- IndividualHookExecutor.\_print_individual_summary() parameter

- IndividualHookExecutor.\_print_individual_summary() parameter

- ProgressHookExecutor.execute_strategy() parameter

- ProgressHookExecutor.\_execute_sequential_with_progress() parameter

- ProgressHookExecutor.\_execute_parallel_with_progress() parameter

- ProgressHookExecutor.\_run_formatting_hook_with_progress() parameter

- ProgressHookExecutor.\_run_formatting_hook_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- ProgressHookExecutor.\_submit_parallel_hooks() parameter

- ProgressHookExecutor.\_collect_parallel_results() parameter

- ProgressHookExecutor.\_collect_parallel_results() parameter

- ProgressHookExecutor.\_process_completed_future() parameter

- ProgressHookExecutor.\_process_completed_future() parameter

- ProgressHookExecutor.\_create_error_result() parameter

- ProgressHookExecutor.\_update_progress_with_result() parameter

- ProgressHookExecutor.\_update_progress_with_error() parameter

- ProgressHookExecutor.\_display_hook_result() parameter

- CachedHookExecutor.execute_strategy() parameter

- CachedHookExecutor.\_initialize_execution_context() parameter

- CachedHookExecutor.\_execute_single_hook_with_cache() parameter

- CachedHookExecutor.\_get_cached_result() parameter

- CachedHookExecutor.\_handle_cache_hit() parameter

- CachedHookExecutor.\_handle_cache_hit() parameter

- CachedHookExecutor.\_handle_cache_miss() parameter

- CachedHookExecutor.\_cache_successful_result() parameter

- CachedHookExecutor.\_cache_successful_result() parameter

- CachedHookExecutor.\_build_execution_result() parameter

- CachedHookExecutor.\_get_relevant_files_for_strategy() parameter

- CachedHookExecutor.\_strategy_affects_python_only() parameter

- CachedHookExecutor.\_strategy_affects_config_only() parameter

- CachedHookExecutor.\_is_cache_valid() parameter

- CachedHookExecutor.\_is_cache_valid() parameter

- SmartCacheManager.__init__() parameter

- SmartCacheManager.get_optimal_cache_strategy() parameter

- HookExecutor.execute_strategy() parameter

- HookExecutor.\_execute_hooks() parameter

- HookExecutor.\_apply_retries_if_needed() parameter

- HookExecutor.\_apply_retries_if_needed() parameter

- HookExecutor.\_create_execution_result() parameter

- HookExecutor.\_create_execution_result() parameter

- HookExecutor.\_calculate_performance_gain() parameter

- HookExecutor.\_calculate_performance_gain() parameter

- HookExecutor.\_print_strategy_header() parameter

- HookExecutor.\_execute_sequential() parameter

- HookExecutor.\_execute_parallel() parameter

- HookExecutor.\_categorize_hooks() parameter

- HookExecutor.\_log_force_enabled_hooks() parameter

- HookExecutor.\_display_skipped_hooks() parameter

- HookExecutor.\_run_hooks_by_type() parameter

- HookExecutor.\_run_hooks_by_type() parameter

- HookExecutor.\_execute_single_hook_with_progress() parameter

- HookExecutor.\_execute_single_hook_with_progress() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_create_run_hook_func() parameter

- HookExecutor.\_create_run_hook_func() parameter

- HookExecutor.\_handle_future_result() parameter

- HookExecutor.execute_single_hook() parameter

- HookExecutor.\_get_changed_files_for_hook() parameter

- HookExecutor.\_run_hook_subprocess() parameter

- HookExecutor.\_run_with_monitoring() parameter

- HookExecutor.\_create_hook_result_from_process() parameter

- HookExecutor.\_should_skip_offline_osv_scanner() parameter

- HookExecutor.\_should_skip_missing_osv_scanner_binary() parameter

- HookExecutor.\_determine_initial_status() parameter

- HookExecutor.\_update_status_for_reporting_tools() parameter

- HookExecutor.\_extract_issues_from_process_output() parameter

- HookExecutor.\_extract_issues_for_reporting_tools() parameter

- HookExecutor.\_extract_issues_for_regular_tools() parameter

- HookExecutor.\_create_timeout_result() parameter

- HookExecutor.\_create_error_result() parameter

- HookExecutor.\_display_hook_result() parameter

- HookExecutor.\_handle_retries() parameter

- HookExecutor.\_handle_retries() parameter

- HookExecutor.\_retry_formatting_hooks() parameter

- HookExecutor.\_retry_formatting_hooks() parameter

- HookExecutor.\_find_failed_formatting_hooks() parameter

- HookExecutor.\_find_failed_formatting_hooks() parameter

- HookExecutor.\_retry_all_formatting_hooks() parameter

- HookExecutor.\_retry_all_formatting_hooks() parameter

- HookExecutor.\_retry_all_hooks() parameter

- HookExecutor.\_retry_all_hooks() parameter

- HookExecutor.\_find_failed_hooks() parameter

- HookExecutor.\_retry_failed_hooks() parameter

- HookExecutor.\_retry_failed_hooks() parameter

- HookExecutor.\_retry_single_hook() parameter

- HookExecutor.\_retry_single_hook() parameter

- HookExecutor.\_retry_single_hook() parameter

- HookExecutor.\_print_summary() parameter

- HookExecutor.\_print_summary() parameter

- HookExecutor.is_concurrent() parameter

- PoolOrchestrator.\_execute_single_hook_standard() parameter

- PoolOrchestrator.\_get_files_for_hook() parameter

- PoolOrchestrator.\_group_hooks_by_files() parameter

- PoolOrchestrator.\_convert_pool_results_to_hook_results() parameter

- CrackerjackCache.set_hook_result() parameter

- CrackerjackCache.set_expensive_hook_result() parameter

- ParallelHookExecutor.analyze_hook_dependencies() parameter

- ParallelHookExecutor.can_execute_in_parallel() parameter

- ParallelHookExecutor.can_execute_in_parallel() parameter

- ParallelHookExecutor.\_can_parallelize_group() parameter

## HookConfig

**Referenced in:**

- AsyncHookManager.__init__() parameter

- WorkflowOptions.\_initialize_config_attributes() parameter

## HookConfigLoader

**Referenced in:**

- AsyncHookManager.__init__() parameter

## HookConfigLoaderProtocol

**Referenced in:**

- AsyncHookManager.__init__() parameter

## HookDefinition

**Referenced in:**

- CustomHookPlugin.__init__() parameter

- CustomHookPlugin.\_execute_command_hook() parameter

- AsyncHookExecutor.\_execute_hook_sync() parameter

- AsyncHookExecutor.\_log_termination_error() parameter

- AsyncHookExecutor.\_handle_runtime_error() parameter

- AsyncHookExecutor.\_handle_general_error() parameter

- ProgressHookExecutor.\_run_formatting_hook_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- ProgressHookExecutor.\_submit_parallel_hooks() parameter

- ProgressHookExecutor.\_collect_parallel_results() parameter

- ProgressHookExecutor.\_process_completed_future() parameter

- ProgressHookExecutor.\_create_error_result() parameter

- ProgressHookExecutor.\_update_progress_with_error() parameter

- CachedHookExecutor.\_execute_single_hook_with_cache() parameter

- CachedHookExecutor.\_get_cached_result() parameter

- CachedHookExecutor.\_handle_cache_hit() parameter

- CachedHookExecutor.\_handle_cache_miss() parameter

- CachedHookExecutor.\_cache_successful_result() parameter

- CachedHookExecutor.\_is_cache_valid() parameter

- HookExecutor.\_log_force_enabled_hooks() parameter

- HookExecutor.\_display_skipped_hooks() parameter

- HookExecutor.\_run_hooks_by_type() parameter

- HookExecutor.\_execute_single_hook_with_progress() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_create_run_hook_func() parameter

- HookExecutor.execute_single_hook() parameter

- HookExecutor.\_get_changed_files_for_hook() parameter

- HookExecutor.\_run_hook_subprocess() parameter

- HookExecutor.\_run_with_monitoring() parameter

- HookExecutor.\_create_hook_result_from_process() parameter

- HookExecutor.\_should_skip_offline_osv_scanner() parameter

- HookExecutor.\_should_skip_missing_osv_scanner_binary() parameter

- HookExecutor.\_determine_initial_status() parameter

- HookExecutor.\_update_status_for_reporting_tools() parameter

- HookExecutor.\_extract_issues_from_process_output() parameter

- HookExecutor.\_extract_issues_for_reporting_tools() parameter

- HookExecutor.\_extract_issues_for_regular_tools() parameter

- HookExecutor.\_create_timeout_result() parameter

- HookExecutor.\_create_error_result() parameter

- PoolOrchestrator.\_execute_single_hook_standard() parameter

- PoolOrchestrator.\_get_files_for_hook() parameter

- PoolOrchestrator.\_group_hooks_by_files() parameter

- PoolOrchestrator.\_convert_pool_results_to_hook_results() parameter

- ParallelHookExecutor.analyze_hook_dependencies() parameter

- ParallelHookExecutor.can_execute_in_parallel() parameter

- ParallelHookExecutor.can_execute_in_parallel() parameter

- ParallelHookExecutor.\_can_parallelize_group() parameter

## HookExecutor

**Referenced in:**

- AsyncHookManager.__init__() parameter

- ProgressHookExecutor base class

- SmartCacheManager.__init__() parameter

## HookExecutorProtocol

**Referenced in:**

- AsyncHookManager.__init__() parameter

## HookLockManager

**Referenced in:**

- AsyncHookExecutor.__init__() parameter

- IndividualHookExecutor.__init__() parameter

## HookLockManagerProtocol

**Referenced in:**

- AsyncHookExecutor.__init__() parameter

- IndividualHookExecutor.__init__() parameter

## HookManager

**Referenced in:**

- SecurityAwareHookManager base class

## HookPluginBase

**Referenced in:**

- CustomHookPlugin base class

- HookPluginRegistry.register_hook_plugin() parameter

## HookPluginRegistry

**Referenced in:**

- PluginManager.__init__() parameter

## HookProgress

**Referenced in:**

- IndividualHookExecutor.set_progress_callback() parameter

- IndividualHookExecutor.\_update_hook_progress_status() parameter

- IndividualHookExecutor.\_create_stream_reader_tasks() parameter

- IndividualHookExecutor.\_update_progress_with_line() parameter

- IndividualHookExecutor.\_maybe_callback_progress() parameter

- IndividualHookExecutor.\_print_hook_summary() parameter

- IndividualHookExecutor.\_print_individual_summary() parameter

## HookResult

**Referenced in:**

- PhaseCoordinator.\_execute_hooks_once() parameter

- PhaseCoordinator.\_run_hooks_with_progress() parameter

- PhaseCoordinator.\_report_hook_results() parameter

- PhaseCoordinator.\_render_hook_results_table() parameter

- PhaseCoordinator.\_render_plain_hook_results() parameter

- PhaseCoordinator.\_calculate_hook_statistics() parameter

- PhaseCoordinator.\_should_update_hook_count() parameter

- PhaseCoordinator.\_try_update_count_from_json() parameter

- PhaseCoordinator.\_print_plain_hook_result() parameter

- PhaseCoordinator.\_render_rich_hook_results() parameter

- PhaseCoordinator.\_build_results_table() parameter

- PhaseCoordinator.to_json() parameter

- PhaseCoordinator.\_format_failing_hooks() parameter

- PhaseCoordinator.\_display_issue_details() parameter

- PhaseCoordinator.\_display_timeout_info() parameter

- PhaseCoordinator.\_display_exit_code_info() parameter

- PhaseCoordinator.\_display_error_message() parameter

- PhaseCoordinator.\_display_generic_failure() parameter

- PhaseCoordinator.\_display_hook_failures() parameter

- PhaseCoordinator.\_print_single_hook_failure() parameter

- PhaseCoordinator.\_print_hook_issues() parameter

- PhaseCoordinator.\_display_failure_reasons() parameter

- PhaseCoordinator.\_display_ruff_failure_details() parameter

- PhaseCoordinator.\_extract_ruff_diagnostics_from_output() parameter

- HookManagerImpl.get_hook_summary() parameter

- AsyncHookManager.get_hook_summary() parameter

- AsyncHookExecutor.\_display_hook_result() parameter

- AsyncHookExecutor.\_print_summary() parameter

- IndividualHookExecutor.\_update_hook_progress_status() parameter

- IndividualHookExecutor.\_print_hook_summary() parameter

- IndividualHookExecutor.\_print_individual_summary() parameter

- ProgressHookExecutor.\_run_formatting_hook_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- ProgressHookExecutor.\_collect_parallel_results() parameter

- ProgressHookExecutor.\_process_completed_future() parameter

- ProgressHookExecutor.\_update_progress_with_result() parameter

- ProgressHookExecutor.\_display_hook_result() parameter

- CachedHookExecutor.\_handle_cache_hit() parameter

- CachedHookExecutor.\_cache_successful_result() parameter

- CachedHookExecutor.\_is_cache_valid() parameter

- HookExecutor.\_apply_retries_if_needed() parameter

- HookExecutor.\_create_execution_result() parameter

- HookExecutor.\_calculate_performance_gain() parameter

- HookExecutor.\_execute_single_hook_with_progress() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_create_run_hook_func() parameter

- HookExecutor.\_handle_future_result() parameter

- HookExecutor.\_display_hook_result() parameter

- HookExecutor.\_handle_retries() parameter

- HookExecutor.\_retry_formatting_hooks() parameter

- HookExecutor.\_find_failed_formatting_hooks() parameter

- HookExecutor.\_retry_all_formatting_hooks() parameter

- HookExecutor.\_retry_all_hooks() parameter

- HookExecutor.\_find_failed_hooks() parameter

- HookExecutor.\_retry_failed_hooks() parameter

- HookExecutor.\_retry_single_hook() parameter

- HookExecutor.\_retry_single_hook() parameter

- HookExecutor.\_print_summary() parameter

- CrackerjackCache.set_hook_result() parameter

- CrackerjackCache.set_expensive_hook_result() parameter

## HookSettings

**Referenced in:**

- HookConfig.from_settings() parameter

## HookStage

**Referenced in:**

- AsyncHookExecutor.\_execute_hook_sync() parameter

## HookStrategy

**Referenced in:**

- HookManagerImpl.\_filter_strategy_for_tool() parameter

- AsyncHookExecutor.\_print_strategy_header() parameter

- AsyncHookExecutor.\_print_summary() parameter

- IndividualHookExecutor.\_finalize_execution_result() parameter

- IndividualHookExecutor.\_print_strategy_header() parameter

- IndividualHookExecutor.\_print_individual_summary() parameter

- ProgressHookExecutor.execute_strategy() parameter

- ProgressHookExecutor.\_execute_sequential_with_progress() parameter

- ProgressHookExecutor.\_execute_parallel_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- CachedHookExecutor.execute_strategy() parameter

- CachedHookExecutor.\_initialize_execution_context() parameter

- CachedHookExecutor.\_build_execution_result() parameter

- CachedHookExecutor.\_get_relevant_files_for_strategy() parameter

- CachedHookExecutor.\_strategy_affects_python_only() parameter

- CachedHookExecutor.\_strategy_affects_config_only() parameter

- SmartCacheManager.get_optimal_cache_strategy() parameter

- HookExecutor.execute_strategy() parameter

- HookExecutor.\_execute_hooks() parameter

- HookExecutor.\_apply_retries_if_needed() parameter

- HookExecutor.\_create_execution_result() parameter

- HookExecutor.\_calculate_performance_gain() parameter

- HookExecutor.\_print_strategy_header() parameter

- HookExecutor.\_execute_sequential() parameter

- HookExecutor.\_execute_parallel() parameter

- HookExecutor.\_categorize_hooks() parameter

- HookExecutor.\_run_hooks_by_type() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_handle_retries() parameter

- HookExecutor.\_retry_formatting_hooks() parameter

- HookExecutor.\_find_failed_formatting_hooks() parameter

- HookExecutor.\_retry_all_formatting_hooks() parameter

- HookExecutor.\_retry_all_hooks() parameter

- HookExecutor.\_retry_failed_hooks() parameter

- HookExecutor.\_retry_single_hook() parameter

- HookExecutor.\_print_summary() parameter

- HookExecutor.is_concurrent() parameter

## Hypothesis

**Referenced in:**

- HypothesisLock.lock() parameter

## ImprovementProposal

**Referenced in:**

- SelfPatcher.validate_diff() parameter

- ImprovementOverseer.build_review_context() parameter

## IncrementalExecutor

**Referenced in:**

- ToolFilter.__init__() parameter

## IndexingProgress

**Referenced in:**

- VectorStore.index_file() parameter

- VectorStore.\_create_embedding_vectors() parameter

## InteractiveTask

**Referenced in:**

- InteractiveTask.__init__() parameter

- InteractiveWorkflowManager.execute_task() parameter

- InteractiveWorkflowManager.\_handle_task_failure() parameter

## InteractiveWorkflowOptions

**Referenced in:**

- CrackerjackAPI.run_interactive_workflow() parameter

- InteractiveCLI.create_dynamic_workflow() parameter

- InteractiveCLI.run_interactive_workflow() parameter

## Issue

**Referenced in:**

- ParserFactory.\_validate_issue_count() parameter

- GenericRegexParser.__init__() parameter

- ProactiveWorkflowPipeline.\_evaluate_planning_need() parameter

- ArchitecturalAssessment.__init__() parameter

- StateManager.\_process_stage_issues() parameter

- FileResult.add() parameter

- PatternCache.cache_successful_pattern() parameter

- PatternCache.get_patterns_for_issue() parameter

- PatternCache.get_best_pattern_for_issue() parameter

- PromptEvolution.record_failed_fix() parameter

- PromptEvolution.record_successful_fix() parameter

- PromptEvolution.get_evolved_prompt() parameter

- PatternDetector.\_create_temp_issue_for_lookup() parameter

- PatternCache.cache_successful_pattern() parameter

- PatternCache.get_patterns_for_issue() parameter

- PatternCache.get_best_pattern_for_issue() parameter

## IssueType

**Referenced in:**

- GenericRegexParser.__init__() parameter

- PatternDetector.\_create_temp_issue_for_lookup() parameter

## JSONParser

**Referenced in:**

- ParserFactory.register_json_parser() parameter

- ParserFactory.\_parse_json_output() parameter

- ParserFactory.\_parse_text_output() parameter

- RuffJSONParser base class

- MypyJSONParser base class

- BanditJSONParser base class

- ComplexipyJSONParser base class

- PyscnJSONParser base class

- SemgrepJSONParser base class

- OsvScannerJSONParser base class

- GitleaksJSONParser base class

- PytestJSONParser base class

- LycheeJSONParser base class

- CheckJSONSchemaJSONParser base class

## Keypair

**Referenced in:**

- SkillsSigner.from_keypair() parameter

## LanguageAdapterBase

**Referenced in:**

- PythonAdapter base class

- WebAdapter base class

- KotlinAdapter base class

- SwiftAdapter base class

## LazyLoader

**Referenced in:**

- MemoryOptimizer.register_lazy_object() parameter

## Lifecycle

**Referenced in:**

- Lifecycle.run() parameter

- PythonLifecycle base class

- PythonLifecycle.run() parameter

- KotlinLifecycle base class

- KotlinLifecycle.run() parameter

- SwiftLifecycle base class

- SwiftLifecycle.run() parameter

## LifecycleOptions

**Referenced in:**

- Lifecycle.run() parameter

- PythonLifecycle.run() parameter

- KotlinLifecycle.run() parameter

- SwiftLifecycle.run() parameter

## LockResult

**Referenced in:**

- HypothesisLock.check_post_hoc() parameter

- LockStore.put() parameter

- InMemoryLockStore.put() parameter

## LoggerProtocol

**Referenced in:**

- ReferenceGenerator.__init__() parameter

- MkDocsIntegrationService.__init__() parameter

- AITemplateEngine.__init__() parameter

- ParallelHookExecutor.__init__() parameter

- AsyncCommandExecutor.__init__() parameter

- LazyLoader.__init__() parameter

- ResourcePool.__init__() parameter

- MemoryProfiler.__init__() parameter

## MCPServerConfig

**Referenced in:**

- MCPServerContext.__init__() parameter

- MCPContextManager.__init__() parameter

- WorkflowOptions.\_initialize_config_attributes() parameter

## MCPServerSettings

**Referenced in:**

- CrackerjackMCPSettings base class

- MCPServerConfig.from_settings() parameter

## MahavishnuConfig

**Referenced in:**

- MahavishnuAggregator.__init__() parameter

## MalformedManifestError

**Referenced in:**

- InvalidManifestAlgorithmError base class

## ManagedResource

**Referenced in:**

- ManagedTemporaryFile base class

- ManagedTemporaryDirectory base class

- ManagedProcess base class

- ManagedTask base class

- ManagedFileHandle base class

## MergeStrategy

**Referenced in:**

- ConfigCleanupService.\_handle_dry_run_merge() parameter

- ConfigCleanupService.\_merge_single_file() parameter

- ConfigCleanupService.\_apply_merge_strategy() parameter

## MetricPoint

**Referenced in:**

- AnomalyDetector.\_detect_seasonal_patterns() parameter

- AnomalyDetector.\_detect_anomaly() parameter

- AnomalyDetector.\_get_seasonal_adjustment() parameter

- AnomalyDetector.\_calculate_severity() parameter

- AnomalyDetector.\_is_critical_threshold_breached() parameter

- AnomalyDetector.\_calculate_z_score() parameter

- AnomalyDetector.\_calculate_confidence() parameter

- AnomalyDetector.\_generate_anomaly_description() parameter

## MkDocsConfig

**Referenced in:**

- MkDocsIntegrationService.\_create_mkdocs_config() parameter

## MkDocsIntegrationService

**Referenced in:**

- MkDocsSiteBuilder.__init__() parameter

## OperationLimits

**Referenced in:**

- BoundedStatusOperations.__init__() parameter

## OperationMetrics

**Referenced in:**

- BoundedStatusOperations.\_cleanup_operation() parameter

## Options

**Referenced in:**

- CrackerjackAPI.run_interactive_workflow() parameter

- InteractiveCLI.create_dynamic_workflow() parameter

- InteractiveCLI.run_interactive_workflow() parameter

- SessionCoordinator.initialize_session_tracking() parameter

- SessionCoordinator.\_setup_logging() parameter

- SessionController.initialize() parameter

- PhaseCoordinator.run_config_cleanup_phase() parameter

- PhaseCoordinator.run_cleaning_phase() parameter

- PhaseCoordinator.run_configuration_phase() parameter

- PhaseCoordinator.\_run_fast_hooks_with_retry() parameter

- PhaseCoordinator.run_coverage_ratchet_phase() parameter

- PhaseCoordinator.run_testing_phase() parameter

- PhaseCoordinator.run_documentation_cleanup_phase() parameter

- PhaseCoordinator.run_plan_index_sync_phase() parameter

- PhaseCoordinator.run_git_cleanup_phase() parameter

- PhaseCoordinator.run_doc_update_phase() parameter

- PhaseCoordinator.run_publishing_phase() parameter

- PhaseCoordinator.run_commit_phase() parameter

- PhaseCoordinator.\_execute_hooks_once() parameter

- PhaseCoordinator.\_display_hook_failures() parameter

- PhaseCoordinator.\_determine_version_type() parameter

- PhaseCoordinator.\_execute_publishing_workflow() parameter

- PhaseCoordinator.\_handle_pre_publish_commit() parameter

- PhaseCoordinator.\_publish_to_pypi() parameter

- PhaseCoordinator.\_finalize_publishing() parameter

- PhaseCoordinator.\_get_commit_message() parameter

- HookPluginBase.execute_hook() parameter

- CustomHookPlugin.execute_hook() parameter

- HookPluginRegistry.execute_custom_hook() parameter

- PluginManager.execute_custom_hook() parameter

- TestCommandBuilder.build_command() parameter

- TestCommandBuilder.build_xcode_command() parameter

- TestCommandBuilder.get_optimal_workers() parameter

- TestCommandBuilder.\_check_explicit_workers() parameter

- TestCommandBuilder.\_check_auto_detection() parameter

- TestCommandBuilder.\_check_fractional_workers() parameter

- TestCommandBuilder.get_test_timeout() parameter

- TestCommandBuilder.\_add_coverage_options() parameter

- TestCommandBuilder.\_add_worker_options() parameter

- TestCommandBuilder.\_should_skip_xdist_for_benchmark() parameter

- TestCommandBuilder.\_add_benchmark_options() parameter

- TestCommandBuilder.\_add_timeout_options() parameter

- TestCommandBuilder.\_add_verbosity_options() parameter

- TestManager.run_tests() parameter

- TestManager.\_run_pytest_if_needed() parameter

- TestManager.\_record_run_state() parameter

- TestManager.\_run_xcode_if_needed() parameter

- TestManager.get_test_command() parameter

- TestManager.\_execute_test_workflow() parameter

- TestManager.\_print_test_start_message() parameter

- TestManager.\_execute_xcode_tests() parameter

- TestManager.\_handle_test_success() parameter

- TestManager.\_handle_test_failure() parameter

- TestManager.\_handle_failure_without_output() parameter

- TestManager.\_render_formatted_output() parameter

- TestManager.\_try_structured_rendering() parameter

- TestManager.\_render_structured_failures_with_summary() parameter

- TestManager.\_render_fallback_sections() parameter

- TestManager.\_get_timeout() parameter

- TestManagerProtocol.run_tests() parameter

- OptionsAdapter.from_options_protocol() parameter

- OptionsAdapter.to_options_protocol() parameter

- CrackerjackCLIFacade.process() parameter

- CrackerjackCLIFacade.\_should_handle_special_mode() parameter

- CrackerjackCLIFacade.\_handle_special_modes() parameter

- CrackerjackCLIFacade.\_handle_advanced_batch() parameter

- InteractiveWorkflowManager.setup_workflow() parameter

- InteractiveWorkflowManager.\_setup_cleaning_task() parameter

- InteractiveWorkflowManager.\_setup_hooks_task() parameter

- InteractiveWorkflowManager.\_setup_testing_task() parameter

- InteractiveWorkflowManager.\_setup_publishing_task() parameter

- InteractiveWorkflowManager.\_setup_commit_task() parameter

- InteractiveWorkflowManager.execute_task() parameter

- InteractiveWorkflowManager.run_workflow() parameter

- InteractiveWorkflowManager.\_initialize_workflow() parameter

- InteractiveWorkflowManager.\_execute_workflow_tasks() parameter

- InteractiveCLI.launch() parameter

- InteractiveCLI.\_get_user_preferences() parameter

- Lifecycle.run() parameter

- UnifiedConfigurationService.__init__() parameter

- PythonLifecycle.run() parameter

- KotlinLifecycle.run() parameter

- SwiftLifecycle.run() parameter

## OptionsProtocol

**Referenced in:**

- SessionCoordinator.initialize_session_tracking() parameter

- SessionCoordinator.\_setup_logging() parameter

- SessionController.initialize() parameter

- PhaseCoordinator.run_config_cleanup_phase() parameter

- PhaseCoordinator.run_cleaning_phase() parameter

- PhaseCoordinator.run_configuration_phase() parameter

- PhaseCoordinator.\_run_fast_hooks_with_retry() parameter

- PhaseCoordinator.run_coverage_ratchet_phase() parameter

- PhaseCoordinator.run_testing_phase() parameter

- PhaseCoordinator.run_documentation_cleanup_phase() parameter

- PhaseCoordinator.run_plan_index_sync_phase() parameter

- PhaseCoordinator.run_git_cleanup_phase() parameter

- PhaseCoordinator.run_doc_update_phase() parameter

- PhaseCoordinator.run_publishing_phase() parameter

- PhaseCoordinator.run_commit_phase() parameter

- PhaseCoordinator.\_execute_hooks_once() parameter

- PhaseCoordinator.\_display_hook_failures() parameter

- PhaseCoordinator.\_determine_version_type() parameter

- PhaseCoordinator.\_execute_publishing_workflow() parameter

- PhaseCoordinator.\_handle_pre_publish_commit() parameter

- PhaseCoordinator.\_publish_to_pypi() parameter

- PhaseCoordinator.\_finalize_publishing() parameter

- PhaseCoordinator.\_get_commit_message() parameter

- HookPluginBase.execute_hook() parameter

- CustomHookPlugin.execute_hook() parameter

- HookPluginRegistry.execute_custom_hook() parameter

- PluginManager.execute_custom_hook() parameter

- TestCommandBuilder.build_command() parameter

- TestCommandBuilder.build_xcode_command() parameter

- TestCommandBuilder.get_optimal_workers() parameter

- TestCommandBuilder.\_check_explicit_workers() parameter

- TestCommandBuilder.\_check_auto_detection() parameter

- TestCommandBuilder.\_check_fractional_workers() parameter

- TestCommandBuilder.get_test_timeout() parameter

- TestCommandBuilder.\_add_coverage_options() parameter

- TestCommandBuilder.\_add_worker_options() parameter

- TestCommandBuilder.\_should_skip_xdist_for_benchmark() parameter

- TestCommandBuilder.\_add_benchmark_options() parameter

- TestCommandBuilder.\_add_timeout_options() parameter

- TestCommandBuilder.\_add_verbosity_options() parameter

- TestManager.run_tests() parameter

- TestManager.\_run_pytest_if_needed() parameter

- TestManager.\_record_run_state() parameter

- TestManager.\_run_xcode_if_needed() parameter

- TestManager.get_test_command() parameter

- TestManager.\_execute_test_workflow() parameter

- TestManager.\_print_test_start_message() parameter

- TestManager.\_execute_xcode_tests() parameter

- TestManager.\_handle_test_success() parameter

- TestManager.\_handle_test_failure() parameter

- TestManager.\_handle_failure_without_output() parameter

- TestManager.\_render_formatted_output() parameter

- TestManager.\_try_structured_rendering() parameter

- TestManager.\_render_structured_failures_with_summary() parameter

- TestManager.\_render_fallback_sections() parameter

- TestManager.\_get_timeout() parameter

- TestManagerProtocol.run_tests() parameter

- OptionsAdapter.from_options_protocol() parameter

- CrackerjackCLIFacade.process() parameter

- CrackerjackCLIFacade.\_should_handle_special_mode() parameter

- CrackerjackCLIFacade.\_handle_special_modes() parameter

- CrackerjackCLIFacade.\_handle_advanced_batch() parameter

- InteractiveWorkflowManager.setup_workflow() parameter

- InteractiveWorkflowManager.\_setup_cleaning_task() parameter

- InteractiveWorkflowManager.\_setup_hooks_task() parameter

- InteractiveWorkflowManager.\_setup_testing_task() parameter

- InteractiveWorkflowManager.\_setup_publishing_task() parameter

- InteractiveWorkflowManager.\_setup_commit_task() parameter

- InteractiveWorkflowManager.execute_task() parameter

- InteractiveWorkflowManager.run_workflow() parameter

- InteractiveWorkflowManager.\_initialize_workflow() parameter

- InteractiveWorkflowManager.\_execute_workflow_tasks() parameter

- InteractiveCLI.launch() parameter

- InteractiveCLI.\_get_user_preferences() parameter

- UnifiedConfigurationService.__init__() parameter

## PackageCleaningResult

**Referenced in:**

- CrackerjackAPI.\_report_safe_cleaning_results() parameter

## PackageStatsSnapshot

**Referenced in:**

- PypiStatsService.classify_download_trend() parameter

## ParallelHookExecutorProtocol

**Referenced in:**

- ParallelHookExecutor base class

## ParameterInfo

**Referenced in:**

- ReferenceGenerator.\_format_parameter_example() parameter

- ReferenceGenerator.\_render_command_parameters_markdown() parameter

- ReferenceGenerator.\_format_parameter_line() parameter

- ReferenceGenerator.\_render_html_command_parameters() parameter

- ReferenceGenerator.\_serialize_parameters() parameter

- ReferenceGenerator.\_serialize_parameter() parameter

- ReferenceGenerator.\_render_rst_command_parameters() parameter

## ParsingError

**Referenced in:**

- ToolSchemaError base class

## PatternCache

**Referenced in:**

- PatternDetector.__init__() parameter

## PerformanceCacheProtocol

**Referenced in:**

- ParallelHookExecutor.__init__() parameter

- AsyncCommandExecutor.__init__() parameter

## PhaseCoordinator

**Referenced in:**

- AsyncWorkflowPipeline.__init__() parameter

## PluginBase

**Referenced in:**

- HookPluginBase base class

- HookPluginRegistry.register_hook_plugin() parameter

- PluginLoader.\_try_instantiate_plugin_class() parameter

- PluginRegistry.register() parameter

## PluginLoader

**Referenced in:**

- PluginDiscovery.__init__() parameter

## PluginMetadata

**Referenced in:**

- HookPluginBase.__init__() parameter

- CustomHookPlugin.__init__() parameter

- PluginLoader.\_create_hook_plugin_from_config() parameter

- PluginBase.__init__() parameter

## PluginRegistry

**Referenced in:**

- PluginLoader.__init__() parameter

- PluginManager.__init__() parameter

- PluginManager.__init__() parameter

## PluginRegistryProtocol

**Referenced in:**

- PluginLoader.__init__() parameter

- PluginManager.__init__() parameter

## PluginType

**Referenced in:**

- PluginRegistry.get_by_type() parameter

- PluginRegistry.get_enabled() parameter

- PluginManager.list_plugins() parameter

## Priority

**Referenced in:**

- StateManager.get_issues_by_priority() parameter

## ProcessMetrics

**Referenced in:**

- ProcessMonitor.monitor_process() parameter

- ProcessMonitor.\_monitor_loop() parameter

- ProcessMonitor.\_perform_health_check() parameter

- ProcessMonitor.\_log_metrics() parameter

- ProcessMonitor.\_check_cpu_activity() parameter

- ProcessMonitor.\_check_cpu_activity() parameter

- ProcessMonitor.\_handle_potential_stall() parameter

- ProcessMonitor.\_handle_potential_stall() parameter

## ProgressConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## ProgressSettings

**Referenced in:**

- ProgressConfig.from_settings() parameter

## ProgressSnapshot

**Referenced in:**

- WorkflowProgressRecorder.record() parameter

- InMemoryRecorder.record() parameter

## ProjectContext

**Referenced in:**

- ContextualAIAssistant.\_generate_recommendations() parameter

- ContextualAIAssistant.\_get_testing_recommendations() parameter

- ContextualAIAssistant.\_get_code_quality_recommendations() parameter

- ContextualAIAssistant.\_get_security_recommendations() parameter

- ContextualAIAssistant.\_get_maintenance_recommendations() parameter

- ContextualAIAssistant.\_get_workflow_recommendations() parameter

- ContextualAIAssistant.\_get_documentation_recommendations() parameter

## ProjectSOP

**Referenced in:**

- SOPPersister.save() parameter

- InMemorySOPPersister.save() parameter

## ProviderID

**Referenced in:**

- ProviderSelectionCLI.\_show_provider_details() parameter

- ProviderSelectionCLI.\_confirm_selection() parameter

- ProviderSelectionCLI.\_save_provider_selection() parameter

- ProviderSelectionCLI.\_get_api_key_env_var() parameter

## PublishConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## PublishSettings

**Referenced in:**

- PublishConfig.from_settings() parameter

## PyPIAuth

**Referenced in:**

- \_EnvVarPyPIAuth base class

- \_KeyringPyPIAuth base class

- \_TrustedPublishingSentinel base class

## PyprojectVersionSource

**Referenced in:**

- PythonLifecycle.__init__() parameter

## RateLimitConfig

**Referenced in:**

- ResourceMonitor.__init__() parameter

- RateLimitMiddleware.__init__() parameter

## RegexParser

**Referenced in:**

- ParserFactory.register_regex_parser() parameter

- ParserFactory.\_parse_json_output() parameter

- ParserFactory.\_parse_text_output() parameter

- CodespellRegexParser base class

- RefurbRegexParser base class

- PyscnRegexParser base class

- RuffFormatRegexParser base class

- ComplexityRegexParser base class

- GenericRegexParser base class

- StructuredDataParser base class

- MypyRegexParser base class

- TyRegexParser base class

- CreosoteRegexParser base class

- LocalLinkCheckerRegexParser base class

- LinkcheckmdRegexParser base class

- JsonSchemaRegexParser base class

- CohesionRegexParser base class

- PymetricaRegexParser base class

- CheckAddedLargeFilesParser base class

- RuffRegexParser base class

- LycheeRegexParser base class

## RegexPatternsProtocol

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_regex_patterns() parameter

## ResourceManager

**Referenced in:**

- ManagedResource.__init__() parameter

- ManagedTemporaryFile.__init__() parameter

- ManagedTemporaryDirectory.__init__() parameter

- ManagedProcess.__init__() parameter

- ManagedTask.__init__() parameter

- ManagedFileHandle.__init__() parameter

- AtomicFileWriter.__init__() parameter

- LockedFileResource.__init__() parameter

- SafeDirectoryCreator.__init__() parameter

- BatchFileOperations.__init__() parameter

## ResourceMetrics

**Referenced in:**

- AdvancedOptimizer.\_generate_cpu_recommendations() parameter

- AdvancedOptimizer.\_generate_memory_recommendations() parameter

- AdvancedOptimizer.\_apply_all_optimizations() parameter

- AdvancedOptimizer.\_apply_memory_optimizations() parameter

- AdvancedOptimizer.\_apply_performance_optimizations() parameter

## ResourcePool

**Referenced in:**

- MemoryOptimizer.register_resource_pool() parameter

## ResourceProtocol

**Referenced in:**

- ResourceManager.register_resource() parameter

## RuleRecord

**Referenced in:**

- RuleStore.add() parameter

## SOPPersister

**Referenced in:**

- EvolutionEngine.__init__() parameter

## SOPProposal

**Referenced in:**

- EvolutionEngine.apply() parameter

## SafeFileModifierProtocol

**Referenced in:**

- SafeFileModifier base class

## ScalingMetrics

**Referenced in:**

- AdvancedOptimizer.\_generate_scaling_recommendations() parameter

## SearchQuery

**Referenced in:**

- VectorStore.search() parameter

## SecureStatusFormatterProtocol

**Referenced in:**

- SecureStatusFormatter base class

## SecureSubprocessExecutor

**Referenced in:**

- GitMetricsCollector.__init__() parameter

## SecurityCheckResult

**Referenced in:**

- SecurityAuditor.\_generate_security_warnings() parameter

- SecurityAuditor.\_generate_security_warnings() parameter

- SecurityAuditor.\_generate_security_warnings() parameter

- SecurityAuditor.\_generate_security_recommendations() parameter

- SecurityAuditor.\_generate_security_recommendations() parameter

- SecurityAuditor.\_generate_security_recommendations() parameter

## SecurityError

**Referenced in:**

- CommandValidationError base class

- EnvironmentValidationError base class

## SecurityEvent

**Referenced in:**

- ValidationRateLimiter.record_failure() parameter

- SecurityLogger.log_security_event() parameter

- SecurityLogger.log_security_event() parameter

- SecurityLogger.\_get_logging_level() parameter

- SecureInputValidator.\_log_validation_failure() parameter

## SecurityEventLevel

**Referenced in:**

- ValidationRateLimiter.record_failure() parameter

- SecurityLogger.log_security_event() parameter

- SecurityLogger.\_get_logging_level() parameter

- SecureInputValidator.\_log_validation_failure() parameter

## SecurityEventType

**Referenced in:**

- SecurityLogger.log_security_event() parameter

## SecurityService

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_security() parameter

## SecurityServiceProtocol

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_security() parameter

- SecurityService base class

## SemanticConfig

**Referenced in:**

- VectorStore.__init__() parameter

- EmbeddingService.__init__() parameter

## ServiceConfig

**Referenced in:**

- ServiceWatchdog.add_service() parameter

- ServiceWatchdog.__init__() parameter

- ServiceWatchdog.\_determine_restart_reason() parameter

- ServiceWatchdog.\_get_service_status() parameter

- ServiceWatchdog.\_get_service_health() parameter

## ServiceProtocol

**Referenced in:**

- MkDocsIntegrationService.__init__() parameter

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_git_service() parameter

- PublishManagerImpl.\_resolve_security() parameter

- HookManagerImpl.\_setup_git_service() parameter

- TestManager.__init__() parameter

- CoverageRatchetProtocol base class

- SecurityServiceProtocol base class

- InitializationServiceProtocol base class

- SmartSchedulingServiceProtocol base class

- UnifiedConfigurationServiceProtocol base class

- ConfigIntegrityServiceProtocol base class

- TestManagerProtocol base class

- BoundedStatusOperationsProtocol base class

- ConfigMergeServiceProtocol base class

- DocumentationServiceProtocol base class

- EnhancedFileSystemServiceProtocol base class

- EnhancedFileSystemService base class

- PoolOrchestrator base class

- SmartFileFilter base class

- SmartFileFilter.__init__() parameter

- SmartSchedulingService base class

- SmartFileFilterV2 base class

- InitializationService.__init__() parameter

- SecureStatusFormatter base class

- SafeFileModifier base class

- ConfigIntegrityService base class

- ParallelHookExecutor base class

- AsyncCommandExecutor base class

- BoundedStatusOperations base class

- CoverageManager.__init__() parameter

## ServiceStatus

**Referenced in:**

- ServiceWatchdog.\_prepare_service_startup() parameter

- ServiceWatchdog.\_get_service_status_display() parameter

## SessionBuddyClient

**Referenced in:**

- SessionBuddyIntegration.__init__() parameter

## SessionCoordinator

**Referenced in:**

- AsyncWorkflowPipeline.__init__() parameter

## SessionMetrics

**Referenced in:**

- WorkflowOptimizationEngine.__init__() parameter

## SettingsActivationRecord

**Referenced in:**

- SettingsPersister.append() parameter

- InMemorySettingsPersister.append() parameter

- HttpSettingsPersister.append() parameter

## SkillsSignerError

**Referenced in:**

- UnknownKeyIdError base class

- MalformedManifestError base class

## SmartFileFilterProtocol

**Referenced in:**

- SmartFileFilter base class

## SmartSchedulingServiceProtocol

**Referenced in:**

- SmartSchedulingService base class

## StageResult

**Referenced in:**

- StateManager.\_update_stage_completion() parameter

- StateManager.\_process_stage_issues() parameter

- StateManager.\_process_stage_fixes() parameter

## StatusSecurityError

**Referenced in:**

- AccessDeniedError base class

- ResourceLimitExceededError base class

- RateLimitExceededError base class

## StatusSecurityManager

**Referenced in:**

- RequestLock.__init__() parameter

## StatusVerbosity

**Referenced in:**

- SecureStatusFormatter.format_status() parameter

- SecureStatusFormatter.\_log_status_access() parameter

- SecureStatusFormatter.\_apply_all_sanitization_steps() parameter

- SecureStatusFormatter.\_add_security_metadata() parameter

- SecureStatusFormatter.\_apply_verbosity_filter() parameter

- SecureStatusFormatter.\_sanitize_sensitive_data() parameter

- SecureStatusFormatter.\_sanitize_recursive() parameter

- SecureStatusFormatter.\_sanitize_string() parameter

- SecureStatusFormatter.\_apply_string_sanitization_pipeline() parameter

- SecureStatusFormatter.\_apply_secret_masking_if_needed() parameter

- SecureStatusFormatter.format_error_response() parameter

- SecureStatusFormatter.\_create_detailed_error_response() parameter

- SecureStatusFormatter.\_should_include_error_details() parameter

## SubprocessSecurityConfig

**Referenced in:**

- SecureSubprocessExecutor.__init__() parameter

## SwarmResult

**Referenced in:**

- LocalSequentialClient.__init__() parameter

- SwarmManager.__init__() parameter

## SwarmTask

**Referenced in:**

- LocalSequentialClient.__init__() parameter

- SwarmManager.__init__() parameter

## Task

**Referenced in:**

- Task.__init__() parameter

- Task.__init__() parameter

- Task.__init__() parameter

- Task.get_resolved_dependencies() parameter

- WorkflowManager.load_workflow() parameter

- WorkflowManager.set_task_executor() parameter

- WorkflowManager.run_task() parameter

- WorkflowManager.\_handle_task_without_executor() parameter

- WorkflowManager.\_execute_task_with_executor() parameter

- WorkflowManager.\_try_execute_task() parameter

- WorkflowManager.\_display_task_result() parameter

- WorkflowManager.\_handle_task_exception() parameter

- WorkflowManager.\_add_status_branch() parameter

- InteractiveCLI.\_should_run_task() parameter

- InteractiveCLI.\_execute_single_task() parameter

- ManagedTask.__init__() parameter

- ResourceContext.managed_task() parameter

- ResourceLeakDetector.track_task() parameter

- ResourceLeakDetector.untrack_task() parameter

- AbstractTaskResource.__init__() parameter

- InteractiveTask.__init__() parameter

- InteractiveWorkflowManager.execute_task() parameter

- InteractiveWorkflowManager.\_handle_task_failure() parameter

- IndividualHookExecutor.\_handle_process_timeout() parameter

- LocalSequentialClient.__init__() parameter

- SwarmManager.__init__() parameter

## TaskDefinition

**Referenced in:**

- Task.__init__() parameter

- WorkflowManager.load_workflow() parameter

## TaskExecutor

**Referenced in:**

- Task.__init__() parameter

- WorkflowManager.set_task_executor() parameter

## TaskStatus

**Referenced in:**

- WorkflowManager.\_add_status_branch() parameter

## Template

**Referenced in:**

- AITemplateEngine.render_template() parameter

- AITemplateEngine.register_template() parameter

- AITemplateEngine.\_apply_inheritance() parameter

- AITemplateEngine.\_apply_inheritance() parameter

- AITemplateEngine.\_apply_ai_optimizations() parameter

- AITemplateEngine.\_apply_ai_optimizations() parameter

- AITemplateEngine.\_render_variables() parameter

- AITemplateEngine.\_render_sections() parameter

- AITemplateEngine.\_post_process_content() parameter

- AITemplateEngine.\_optimize_for_structured_data() parameter

- AITemplateEngine.\_optimize_for_decision_trees() parameter

- AITemplateEngine.\_optimize_for_command_matrices() parameter

- AITemplateEngine.\_optimize_for_step_by_step() parameter

- TemplateApplicator.__init__() parameter

## TemplateContext

**Referenced in:**

- AITemplateEngine.render_template() parameter

- AITemplateEngine.\_apply_inheritance() parameter

- AITemplateEngine.\_apply_ai_optimizations() parameter

- AITemplateEngine.\_render_variables() parameter

- AITemplateEngine.\_render_sections() parameter

- AITemplateEngine.\_post_process_content() parameter

- AITemplateEngine.\_optimize_for_structured_data() parameter

- AITemplateEngine.\_optimize_for_decision_trees() parameter

- AITemplateEngine.\_optimize_for_command_matrices() parameter

- AITemplateEngine.\_optimize_for_step_by_step() parameter

## TemplateDetector

**Referenced in:**

- TemplateApplicator.__init__() parameter

## TestCommandBuilder

**Referenced in:**

- TestManager.__init__() parameter

## TestConfig

**Referenced in:**

- WorkflowOptions.\_initialize_config_attributes() parameter

## TestFailure

**Referenced in:**

- TestManager.\_render_structured_failures_with_summary() parameter

- TestManager.\_parse_failure_header() parameter

- TestManager.\_parse_location_and_assertion() parameter

- TestManager.\_parse_traceback_line() parameter

- TestManager.\_parse_captured_output() parameter

- TestManager.\_enrich_failures_from_short_summary() parameter

- TestManager.\_create_failures_from_summary() parameter

- TestManager.\_enrich_existing_failures() parameter

- TestManager.\_try_enrich_named_failure() parameter

- TestManager.\_try_enrich_unnamed_failure() parameter

- TestManager.\_match_unnamed_failures() parameter

- TestManager.\_parse_failure_line() parameter

- TestManager.\_render_structured_failure_panels() parameter

- TestManager.\_render_single_failure() parameter

- TestManager.\_print_failure_header() parameter

- TestManager.\_print_failure_location() parameter

- TestManager.\_print_failure_status() parameter

- TestManager.\_print_failure_summary() parameter

- TestManager.\_get_failure_summary() parameter

- TestManager.\_print_failure_traceback() parameter

- TestManager.\_get_traceback_preview() parameter

- TestManager.\_build_simple_failure_list() parameter

- TestManager.\_group_failures_by_file() parameter

- TestManager.\_render_file_failure_header() parameter

- TestManager.\_render_single_failure_panel() parameter

- TestManager.\_create_failure_details_table() parameter

- TestManager.\_build_failure_components() parameter

- TestManager.\_get_duration_note() parameter

## TestProgress

**Referenced in:**

- TestExecutor.\_execute_with_live_progress() parameter

- TestExecutor.\_run_test_command_with_ai_progress() parameter

- TestExecutor.\_run_with_xdist_fallback() parameter

- TestExecutor.\_did_xdist_timeout() parameter

- TestExecutor.\_start_reader_threads() parameter

- TestExecutor.\_create_stdout_reader() parameter

- TestExecutor.\_create_stderr_reader() parameter

- TestExecutor.\_create_monitor_thread() parameter

- TestExecutor.\_process_test_output_line() parameter

- TestExecutor.\_parse_test_line() parameter

- TestExecutor.\_handle_collection_completion() parameter

- TestExecutor.\_handle_session_events() parameter

- TestExecutor.\_handle_collection_progress() parameter

- TestExecutor.\_handle_test_execution() parameter

- TestExecutor.\_handle_running_test() parameter

- TestExecutor.\_extract_current_test() parameter

- TestExecutor.\_update_display_if_needed() parameter

- TestExecutor.\_should_refresh_display() parameter

- TestExecutor.\_mark_test_as_stuck() parameter

- TestExecutor.\_handle_progress_error() parameter

- TestExecutor.\_execute_test_process_with_progress() parameter

- TestExecutor.\_read_stdout_with_progress() parameter

- TestExecutor.\_read_stdout_blocking() parameter

- TestExecutor.\_read_stdout_loop() parameter

- TestExecutor.\_read_remaining_output() parameter

- TestExecutor.\_process_line() parameter

- TestExecutor.\_emit_ai_progress() parameter

## TestResult

**Referenced in:**

- TestManager.__init__() parameter

- TestManager.__init__() parameter

## TestResultParser

**Referenced in:**

- TestManager.__init__() parameter

## TestResultRenderer

**Referenced in:**

- TestManager.__init__() parameter

## TestSettings

**Referenced in:**

- TestConfig.from_settings() parameter

## TimeoutConfig

**Referenced in:**

- AsyncTimeoutManager.__init__() parameter

## TimeoutError

**Referenced in:**

- AsyncTimeoutManager.\_handle_custom_timeout_exception() parameter

- AsyncTimeoutManager.\_handle_timeout_case() parameter

## TimeoutStrategy

**Referenced in:**

- AsyncTimeoutManager.\_handle_timeout_error() parameter

- AsyncTimeoutManager.\_handle_custom_timeout_exception() parameter

- AsyncTimeoutManager.\_handle_asyncio_timeout_exception() parameter

- AsyncTimeoutManager.\_handle_cancelled_exception() parameter

- AsyncTimeoutManager.\_handle_generic_exception() parameter

- AsyncTimeoutManager.\_dispatch_exception_handler() parameter

- AsyncTimeoutManager.\_handle_timeout_case() parameter

- AsyncTimeoutManager.\_update_circuit_breaker_on_failure() parameter

## ToolProfiler

**Referenced in:**

- IncrementalExecutor.__init__() parameter

## ValidationConfig

**Referenced in:**

- SecureInputValidator.__init__() parameter

## ValidationResult

**Referenced in:**

- PhaseCoordinator.\_format_frontmatter_errors() parameter

- PhaseCoordinator.\_format_frontmatter_warnings() parameter

- FrontmatterValidationError.__init__() parameter

## VersionAnalyzer

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_version_analyzer() parameter

## VersionAnalyzerProtocol

**Referenced in:**

- PublishManagerImpl.__init__() parameter

- PublishManagerImpl.\_resolve_version_analyzer() parameter

## VersionBumpRecommendation

**Referenced in:**

- VersionAnalyzer.display_recommendation() parameter

- VersionAnalyzer.\_display_summary() parameter

- VersionAnalyzer.\_display_reasoning() parameter

- VersionAnalyzer.\_display_changes() parameter

- VersionAnalyzer.\_display_commit_analysis() parameter

## VersionBumpType

**Referenced in:**

- VersionAnalyzer.\_calculate_next_version() parameter

## VersionSource

**Referenced in:**

- PythonLifecycle.__init__() parameter

- PyprojectVersionSource base class

- KotlinLifecycle.__init__() parameter

- SwiftLifecycle.__init__() parameter

- GitTagVersionSource base class

## VersionSourceError

**Referenced in:**

- VersionNotFoundError base class

- VersionWriteError base class

## WorkflowBuilder

**Referenced in:**

- InteractiveCLI.\_add_setup_phase() parameter

- InteractiveCLI.\_add_config_phase() parameter

- InteractiveCLI.\_add_cleaning_phase() parameter

- InteractiveCLI.\_add_fast_hooks_phase() parameter

- InteractiveCLI.\_add_testing_phase() parameter

- InteractiveCLI.\_add_comprehensive_hooks_phase() parameter

- InteractiveCLI.\_add_coverage_ratchet_phase() parameter

- InteractiveCLI.\_add_version_phase() parameter

- InteractiveCLI.\_add_publish_phase() parameter

- InteractiveCLI.\_add_commit_phase() parameter

- InteractiveCLI.\_add_pr_phase() parameter

## WorkflowExecutionRecord

**Referenced in:**

- WorkflowLearnerProtocol.record_workflow_execution() parameter

- NoOpWorkflowLearner.record_workflow_execution() parameter

- SQLiteWorkflowLearner.record_workflow_execution() parameter

- SQLiteWorkflowLearner.\_update_effectiveness_metrics() parameter

## WorkflowOptions

**Referenced in:**

- CrackerjackAPI.run_interactive_workflow() parameter

- InteractiveCLI.create_dynamic_workflow() parameter

- InteractiveCLI.run_interactive_workflow() parameter

- OptionsAdapter.to_options_protocol() parameter

## WorkflowPipeline

**Referenced in:**

- SessionController.__init__() parameter

## \_InMemorySimpleOps

**Referenced in:**

- \_InMemoryAdvancedOps.__init__() parameter

## \_SessionBuddyProtocol

**Referenced in:**

- FailureRecorder.__init__() parameter

## all

**Referenced in:**

- \_DocstringFinder.__init__() parameter

- RegexVisitor.visit_Call() parameter

- ResourceManager.register_cleanup_callback() parameter

- SessionCoordinator.register_cleanup() parameter

- PhaseCoordinator.\_execute_hooks_once() parameter

- PhaseCoordinator.\_run_hooks_with_progress() parameter

- ParallelTaskExecutor.execute_tasks() parameter

- \_MemoizedWrapper.__init__() parameter

- PluginLoader.\_try_factory_function() parameter

- TestExecutor.execute_with_ai_progress() parameter

- TestExecutor.\_run_test_command_with_ai_progress() parameter

- TestExecutor.\_run_with_xdist_fallback() parameter

- TestExecutor.\_execute_test_process_with_progress() parameter

- TestExecutor.\_read_stdout_with_progress() parameter

- TestExecutor.\_read_stdout_blocking() parameter

- TestExecutor.\_read_stdout_loop() parameter

- TestExecutor.\_read_remaining_output() parameter

- TestExecutor.\_process_line() parameter

- TestExecutor.\_emit_ai_progress() parameter

- TestManager.set_progress_callback() parameter

- \_PhaseTask.__init__() parameter

- MCPServerContext.add_startup_task() parameter

- MCPServerContext.add_shutdown_task() parameter

- ResourceManagerProtocol.register_cleanup_callback() parameter

- IndividualHookExecutor.set_progress_callback() parameter

- ProcessMonitor.monitor_process() parameter

- ProcessMonitor.\_monitor_loop() parameter

- ProcessMonitor.\_perform_health_check() parameter

- ProcessMonitor.\_check_cpu_activity() parameter

- ProcessMonitor.\_handle_potential_stall() parameter

- IncrementalExecutor.execute_incremental() parameter

- MahavishnuSwarmClient.__init__() parameter

- LocalSequentialClient.__init__() parameter

- SwarmManager.__init__() parameter

- VectorStore.index_file() parameter

- VectorStore.\_create_embedding_vectors() parameter

- DependencyVisitor.visit_Call() parameter

- SecureSubprocessExecutor.\_handle_process_error() parameter

- SecurityVisitor.visit_Call() parameter

- \_StartswithTupleTransformer.\_try_transform_group() parameter

- \_StartswithTupleTransformer.\_extract_string_args() parameter

- \_StartswithTupleTransformer.\_create_combined_call() parameter

- \_StartswithTupleTransformer.\_build_replacement() parameter

- \_StartswithTupleTransformer.\_build_replacement() parameter

- \_StartswithTupleTransformer.\_is_simple_string_arg() parameter

- LazyLoader.__init__() parameter

- ResourcePool.__init__() parameter

- ToolProfiler.profile_tool() parameter

- FallbackChainCodeFixer.__init__() parameter

## dict

**Referenced in:**

- CIFeedbackAnalyzer.analyze_ci_failure() parameter

- CIFeedbackAnalyzer.analyze_ci_failure() parameter

- CIFeedbackAnalyzer.\_generate_suggestions() parameter

- CIFeedbackAnalyzer.\_calculate_confidence() parameter

- Task.__init__() parameter

- Task.get_resolved_dependencies() parameter

- WorkflowManager.load_workflow() parameter

- CrackerjackError.__init__() parameter

- ConfigError.__init__() parameter

- ExecutionError.__init__() parameter

- TestExecutionError.__init__() parameter

- PublishError.__init__() parameter

- GitError.__init__() parameter

- FileError.__init__() parameter

- CleaningError.__init__() parameter

- ResourceError.__init__() parameter

- CodeCleaner.\_finalize_cleaning_result() parameter

- \_LineCommentStep.\_should_stop_for_comment() parameter

- \_LineCommentStep.\_update_string_state() parameter

- DualOutputGenerator.\_build_command_matrix() parameter

- DualOutputGenerator.\_format_command_table() parameter

- ReferenceGenerator.\_create_command_visitor() parameter

- ReferenceGenerator.\_process_function_node() parameter

- ReferenceGenerator.\_assign_command_workflows() parameter

- ReferenceGenerator.\_categorize_commands() parameter

- ReferenceGenerator.\_determine_command_category() parameter

- ReferenceGenerator.\_add_command_to_category() parameter

- ReferenceGenerator.\_generate_workflows() parameter

- ReferenceGenerator.\_render_markdown_toc() parameter

- ReferenceGenerator.\_render_markdown_category() parameter

- ReferenceGenerator.\_render_markdown_workflows() parameter

- ReferenceGenerator.\_render_command_examples_markdown() parameter

- ReferenceGenerator.\_render_html_category() parameter

- ReferenceGenerator.\_render_html_category_commands() parameter

- ReferenceGenerator.\_serialize_commands() parameter

- ReferenceGenerator.\_render_rst_category_commands() parameter

- MkDocsIntegrationService.\_create_mkdocs_config() parameter

- MkDocsIntegrationService.\_generate_nav_from_content() parameter

- AITemplateEngine.create_ai_reference_template() parameter

- AITemplateEngine.create_ai_reference_template() parameter

- AITemplateEngine.create_ai_reference_template() parameter

- AITemplateEngine.create_user_guide_template() parameter

- AITemplateEngine.create_user_guide_template() parameter

- AITemplateEngine.create_user_guide_template() parameter

- CrackerjackWebSocketServer.\_can_subscribe_to_channel() parameter

- RuffJSONParser.parse_json() parameter

- RuffJSONParser.\_build_ruff_details() parameter

- RuffJSONParser.get_issue_count() parameter

- MypyJSONParser.parse_json() parameter

- MypyJSONParser.\_validate_mypy_item() parameter

- MypyJSONParser.\_build_mypy_issue() parameter

- MypyJSONParser.get_issue_count() parameter

- BanditJSONParser.parse_json() parameter

- BanditJSONParser.get_issue_count() parameter

- ComplexipyJSONParser.parse_json() parameter

- ComplexipyJSONParser.\_create_complexipy_issue() parameter

- ComplexipyJSONParser.get_issue_count() parameter

- PyscnJSONParser.parse_json() parameter

- PyscnJSONParser.get_issue_count() parameter

- PyscnJSONParser.\_count_complexity_above_threshold() parameter

- PyscnJSONParser.\_count_dead_code_blocks() parameter

- PyscnJSONParser.\_parse_complexity_section() parameter

- PyscnJSONParser.\_parse_dead_code_section() parameter

- SemgrepJSONParser.parse_json() parameter

- SemgrepJSONParser.\_get_extra_data() parameter

- SemgrepJSONParser.get_issue_count() parameter

- OsvScannerJSONParser.parse_json() parameter

- OsvScannerJSONParser.\_extract_source_path() parameter

- OsvScannerJSONParser.\_create_vulnerability_issue() parameter

- OsvScannerJSONParser.get_issue_count() parameter

- OsvScannerJSONParser.\_get_results_list() parameter

- GitleaksJSONParser.parse_json() parameter

- GitleaksJSONParser.get_issue_count() parameter

- PytestJSONParser.parse_json() parameter

- PytestJSONParser.get_issue_count() parameter

- LycheeJSONParser.parse_json() parameter

- LycheeJSONParser.get_issue_count() parameter

- CheckJSONSchemaJSONParser.\_parse_frame() parameter

- CheckJSONSchemaJSONParser.\_extract_frame_file() parameter

- CheckJSONSchemaJSONParser.parse_json() parameter

- CheckJSONSchemaJSONParser.get_issue_count() parameter

- JSONParser.parse_json() parameter

- JSONParser.get_issue_count() parameter

- \_SubprocessExecutor.execute_secure() parameter

- RuntimeFactsBuilder.get_capabilities_summary() parameter

- PhaseCoordinator.\_run_hooks_with_progress() parameter

- PhaseCoordinator.\_restore_progress_callbacks() parameter

- PhaseCoordinator.\_report_hook_results() parameter

- PhaseCoordinator.\_extract_count_from_json_dict() parameter

- PhaseCoordinator.\_print_plain_summary() parameter

- PhaseCoordinator.\_build_summary_text() parameter

- PhaseCoordinator.\_format_hook_summary() parameter

- \_MemoizedWrapper.__init__() parameter

- PluginLoader.\_create_plugin_from_config() parameter

- PluginLoader.\_create_hook_plugin_from_config() parameter

- PluginBase.configure() parameter

- PluginBase.validate_config() parameter

- PluginManager.configure_plugin() parameter

- AdapterAttemptRecord.from_dict() parameter

- AdapterLearnerProtocol.recommend_adapter() parameter

- NoOpAdapterLearner.recommend_adapter() parameter

- SQLiteAdapterLearner.recommend_adapter() parameter

- AdapterLearningIntegration.track_adapter_execution() parameter

- AdapterLearningIntegration.get_adapter_recommendation() parameter

- DAGExecutionRecord.from_dict() parameter

- DAGO_optimizerProtocol.get_optimal_execution_strategy() parameter

- DAGO_optimizerProtocol.get_optimal_execution_strategy() parameter

- NoOpDAGO_optimizer.get_optimal_execution_strategy() parameter

- NoOpDAGO_optimizer.get_optimal_execution_strategy() parameter

- SQLiteDAGO_optimizer.\_compute_dag_hash() parameter

- SQLiteDAGO_optimizer.get_optimal_execution_strategy() parameter

- SQLiteDAGO_optimizer.get_optimal_execution_strategy() parameter

- OneiricLearningIntegration.track_dag_execution() parameter

- OneiricLearningIntegration.track_dag_execution() parameter

- OneiricLearningIntegration.get_execution_strategy() parameter

- OneiricLearningIntegration.get_execution_strategy() parameter

- OneiricLearningIntegration.learn_improved_ordering() parameter

- OneiricLearningIntegration.\_compute_dag_hash() parameter

- QueryInteractionRecord.from_dict() parameter

- QueryOptimizerProtocol.adapt_ranking() parameter

- NoOpQueryOptimizer.adapt_ranking() parameter

- SQLiteQueryOptimizer.adapt_ranking() parameter

- AkoshaLearningIntegration.track_search_results() parameter

- AkoshaLearningIntegration.enhance_search_results() parameter

- WorkflowExecutionRecord.from_dict() parameter

- WorkflowLearnerProtocol.recommend_workflow() parameter

- NoOpWorkflowLearner.recommend_workflow() parameter

- SQLiteWorkflowLearner.recommend_workflow() parameter

- SQLiteWorkflowLearner.\_calculate_project_similarity() parameter

- SQLiteWorkflowLearner.\_calculate_project_similarity() parameter

- MahavishnuLearningIntegration.track_workflow_execution() parameter

- MahavishnuLearningIntegration.get_workflow_recommendation() parameter

- PublishManagerImpl.\_restore_bump_files() parameter

- PublishManagerImpl.\_dispatch_publish() parameter

- TestExecutor.execute_with_ai_progress() parameter

- TestExecutor.\_run_test_command_with_ai_progress() parameter

- TestExecutor.\_run_with_xdist_fallback() parameter

- TestExecutor.\_execute_test_process_with_progress() parameter

- TestExecutor.\_execute_test_process_with_progress() parameter

- TestExecutor.\_read_stdout_with_progress() parameter

- TestExecutor.\_read_stdout_blocking() parameter

- TestExecutor.\_read_stdout_loop() parameter

- TestExecutor.\_read_remaining_output() parameter

- TestExecutor.\_process_line() parameter

- TestExecutor.\_emit_ai_progress() parameter

- TestManager.set_progress_callback() parameter

- TestManager.\_should_render_test_panel() parameter

- TestManager.\_render_test_results_panel() parameter

- TestManager.\_update_parsing_state() parameter

- TestManager.\_update_parsing_state() parameter

- TestManager.\_create_failures_from_summary() parameter

- TestManager.\_enrich_existing_failures() parameter

- TestManager.\_match_unnamed_failures() parameter

- RuntimeHealthSnapshot.from_dict() parameter

- \_FakeToolManager.__init__() parameter

- \_FakeApp.__init__() parameter

- ServiceWatchdog.__init__() parameter

- WorkflowOptions.\_set_default_overrides() parameter

- WorkflowOptions.\_should_skip_override() parameter

- WorkflowOptions.\_set_kwargs_attributes() parameter

- ConfigMergeServiceProtocol.smart_merge_pyproject() parameter

- ConfigMergeServiceProtocol.smart_merge_pre_commit_config() parameter

- ConfigMergeServiceProtocol.write_pyproject_config() parameter

- ConfigMergeServiceProtocol.write_pre_commit_config() parameter

- DocumentationServiceProtocol.generate_documentation() parameter

- DocumentationGeneratorProtocol.generate_api_reference() parameter

- DocumentationGeneratorProtocol.generate_user_guide() parameter

- DocumentationGeneratorProtocol.generate_changelog_update() parameter

- DocumentationGeneratorProtocol.render_template() parameter

- DocumentationGeneratorProtocol.generate_cross_references() parameter

- DocumentationValidatorProtocol.check_documentation_freshness() parameter

- DocumentationValidatorProtocol.validate_cross_references() parameter

- DocumentationValidatorProtocol.calculate_coverage_metrics() parameter

- DocumentationValidatorProtocol.calculate_coverage_metrics() parameter

- DebuggerProtocol.log_agent_activity() parameter

- DebuggerProtocol.log_agent_activity() parameter

- DebuggerProtocol.log_mcp_operation() parameter

- DebuggerProtocol.log_mcp_operation() parameter

- QualityBaselineProtocol.update_baseline() parameter

- SecureSubprocessExecutorProtocol.execute_secure() parameter

- ValidationReport.from_result() parameter

- QualityGateReport.from_result() parameter

- SessionMetrics.from_dict() parameter

- HealthCheckResult.healthy() parameter

- HealthCheckResult.degraded() parameter

- HealthCheckResult.unhealthy() parameter

- SystemHealthReport.from_category_health() parameter

- CloneLocation.from_dict() parameter

- CloneGrouper.group_pairs() parameter

- CloneGrouper.\_make_group_id() parameter

- AsyncHookExecutor.\_format_log() parameter

- HookOutputParser.\_parse_ruff_check() parameter

- HookOutputParser.\_parse_ruff_check() parameter

- HookOutputParser.\_parse_pyright() parameter

- HookOutputParser.\_parse_pyright() parameter

- HookOutputParser.\_parse_bandit() parameter

- HookOutputParser.\_parse_bandit() parameter

- HookOutputParser.\_parse_vulture() parameter

- HookOutputParser.\_parse_vulture() parameter

- HookOutputParser.\_parse_complexipy() parameter

- HookOutputParser.\_parse_complexipy() parameter

- HookOutputParser.\_parse_default_hook() parameter

- HookOutputParser.\_parse_default_hook() parameter

- IndividualHookExecutor.\_finalize_execution_result() parameter

- ProgressHookExecutor.\_collect_parallel_results() parameter

- ProgressHookExecutor.\_collect_parallel_results() parameter

- ProgressHookExecutor.\_process_completed_future() parameter

- ProgressHookExecutor.\_process_completed_future() parameter

- CachedHookExecutor.\_execute_single_hook_with_cache() parameter

- CachedHookExecutor.\_handle_cache_hit() parameter

- CachedHookExecutor.\_handle_cache_miss() parameter

- CachedHookExecutor.\_build_execution_result() parameter

- SmartCacheManager.should_use_cache_for_hook() parameter

- HookExecutor.\_handle_future_result() parameter

- HookExecutor.\_run_with_monitoring() parameter

- HookExecutor.\_extract_semgrep_results() parameter

- HookExecutor.\_extract_semgrep_errors() parameter

- HookExecutor.\_extract_osv_vulnerability_issues() parameter

- HookExecutor.\_update_path() parameter

- QualityBaselineRecord.update_from_dict() parameter

- \_InMemorySimpleOps.\_update_existing() parameter

- \_InMemorySimpleOps.\_update_entity_fields() parameter

- \_InMemorySimpleOps.\_create_new() parameter

- DocumentationCleanup.\_calculate_backup_checksum() parameter

- MahavishnuPycharmMCPClient.\_extract_list() parameter

- ToolFilter.estimate_time_savings() parameter

- MarkdownTemplateRenderer.render_template() parameter

- DocumentationGeneratorImpl.generate_api_reference() parameter

- DocumentationGeneratorImpl.generate_user_guide() parameter

- DocumentationGeneratorImpl.generate_changelog_update() parameter

- DocumentationGeneratorImpl.render_template() parameter

- DocumentationGeneratorImpl.generate_cross_references() parameter

- DocumentationGeneratorImpl.\_generate_overview() parameter

- DocumentationGeneratorImpl.\_generate_protocols_section() parameter

- DocumentationGeneratorImpl.\_generate_services_section() parameter

- DocumentationGeneratorImpl.\_generate_managers_section() parameter

- DocumentationGeneratorImpl.\_format_methods() parameter

- DocumentationGeneratorImpl.\_calculate_api_stats() parameter

- DocumentationGeneratorImpl.\_find_references_to_name() parameter

- DocumentationGeneratorImpl.\_find_protocol_references() parameter

- DocumentationGeneratorImpl.\_find_protocol_method_references() parameter

- DocumentationGeneratorImpl.\_find_module_references() parameter

- DocumentationGeneratorImpl.\_find_class_references() parameter

- DocumentationGeneratorImpl.\_find_class_method_references() parameter

- DocumentationGeneratorImpl.\_find_method_parameter_references() parameter

- FileIOService.write_json_file_sync() parameter

- GitService.\_get_file_category() parameter

- MahavishnuSwarmClient.__init__() parameter

- SwarmManager.\_create_tasks_from_issues() parameter

- SwarmManager.\_create_fix_prompt() parameter

- TemplateApplicator.\_replace_placeholders() parameter

- TemplateApplicator.\_smart_merge_configs() parameter

- TemplateApplicator.\_merge_tool_section() parameter

- TemplateApplicator.\_merge_tool_section() parameter

- TemplateApplicator.\_merge_nested_dict() parameter

- TemplateApplicator.\_merge_nested_dict() parameter

- VectorStore.\_create_embedding_vectors() parameter

- PatternCache.cache_successful_pattern() parameter

- AnomalyDetector.add_metric() parameter

- PackageBackupService.\_calculate_backup_checksum() parameter

- PoolOrchestrator.\_convert_pool_results_to_hook_results() parameter

- SecurityService.create_secure_command_env() parameter

- SecurityService.create_secure_command_env() parameter

- APIExtractorImpl.\_populate_module_components() parameter

- APIExtractorImpl.\_process_ast_node() parameter

- APIExtractorImpl.\_build_base_class_info() parameter

- APIExtractorImpl.\_extract_class_methods() parameter

- APIExtractorImpl.\_populate_service_classes() parameter

- APIExtractorImpl.\_process_service_class() parameter

- APIExtractorImpl.\_extract_implemented_protocols() parameter

- APIExtractorImpl.\_add_class_to_service_info() parameter

- APIExtractorImpl.\_add_class_to_service_info() parameter

- APIExtractorImpl.\_extract_class_cli_options() parameter

- ChangelogGenerator.\_add_entry_to_collection() parameter

- ChangelogGenerator.update_changelog() parameter

- ChangelogGenerator.\_generate_changelog_section() parameter

- ChangelogGenerator.\_display_changelog_preview() parameter

- CrackerjackCache.set_quality_baseline() parameter

- ConfigMergeService.smart_merge_pyproject() parameter

- ConfigMergeService.\_process_gitignore_line() parameter

- ConfigMergeService.\_handle_crackerjack_header() parameter

- ConfigMergeService.\_should_skip_empty_line() parameter

- ConfigMergeService.\_collect_pattern_if_present() parameter

- ConfigMergeService.\_add_line_if_non_crackerjack() parameter

- ConfigMergeService.smart_merge_pre_commit_config() parameter

- ConfigMergeService.write_pre_commit_config() parameter

- ConfigMergeService.write_pyproject_config() parameter

- ConfigMergeService.\_ensure_crackerjack_dev_dependency() parameter

- ConfigMergeService.\_ensure_crackerjack_dev_dependency() parameter

- ConfigMergeService.\_merge_tool_configurations() parameter

- ConfigMergeService.\_merge_tool_configurations() parameter

- ConfigMergeService.\_merge_tool_settings() parameter

- ConfigMergeService.\_merge_tool_settings() parameter

- ConfigMergeService.\_merge_pytest_markers() parameter

- ConfigMergeService.\_merge_pytest_markers() parameter

- ConfigMergeService.\_remove_fixed_coverage_requirements() parameter

- ConfigMergeService.\_replace_project_name_in_tool_config() parameter

- DocumentationServiceImpl.\_extract_specialized_apis() parameter

- DocumentationServiceImpl.generate_documentation() parameter

- DocumentationServiceImpl.\_count_documentation_items() parameter

- DocumentationServiceImpl.\_count_protocol_items() parameter

- DocumentationServiceImpl.\_count_module_items() parameter

- DocumentationServiceImpl.\_count_class_items() parameter

- DocumentationServiceImpl.\_count_function_items() parameter

- DocumentationServiceImpl.\_count_method_items() parameter

- DocumentationServiceImpl.\_generate_protocol_documentation() parameter

- DocumentationServiceImpl.\_generate_service_documentation() parameter

- DocumentationServiceImpl.\_generate_service_section() parameter

- DocumentationServiceImpl.\_generate_service_classes() parameter

- DocumentationServiceImpl.\_generate_public_methods() parameter

- DocumentationServiceImpl.\_generate_cli_documentation() parameter

- DocumentationServiceImpl.\_format_cross_references() parameter

- HeatMapGenerator.add_error_data() parameter

- HeatMapGenerator.add_metric_data() parameter

- HeatMapGenerator.add_metric_data() parameter

- HeatMapGenerator.\_create_time_buckets() parameter

- HeatMapGenerator.\_build_error_matrix() parameter

- HeatMapGenerator.\_create_frequency_cells() parameter

- HeatMapGenerator.\_calculate_max_errors() parameter

- HeatMapGenerator.\_create_complexity_cells() parameter

- HeatMapGenerator.\_create_complexity_cell() parameter

- HeatMapGenerator.\_create_complexity_labels() parameter

- HeatMapGenerator.\_calculate_max_complexity() parameter

- HeatMapGenerator.\_create_quality_metric_cells() parameter

- HeatMapGenerator.\_group_test_errors_by_matrix() parameter

- HeatMapGenerator.\_collect_error_types() parameter

- HeatMapGenerator.\_calculate_max_test_failures() parameter

- HeatMapGenerator.\_create_test_failure_cells() parameter

- SecureSubprocessExecutor.execute_secure() parameter

- SecureSubprocessExecutor.\_execute_with_validation() parameter

- SecureSubprocessExecutor.\_execute_with_validation() parameter

- SecureSubprocessExecutor.\_prepare_execution_params() parameter

- SecureSubprocessExecutor.\_execute_subprocess() parameter

- SecureSubprocessExecutor.\_execute_subprocess() parameter

- SecureSubprocessExecutor.\_log_successful_execution() parameter

- SecureSubprocessExecutor.\_sanitize_environment() parameter

- SecureSubprocessExecutor.\_validate_environment_size() parameter

- SecureSubprocessExecutor.\_filter_environment_variables() parameter

- SecureSubprocessExecutor.\_add_safe_environment_variables() parameter

- PromptEvolution.record_failed_fix() parameter

- CommitMessageGenerator.\_determine_commit_type() parameter

- CommitMessageGenerator.\_determine_scope() parameter

- CommitMessageGenerator.\_generate_subject() parameter

- CommitMessageGenerator.\_generate_body() parameter

- ConfigTemplateService.\_create_config_diff() parameter

- ConfigTemplateService.\_create_config_diff() parameter

- ConfigTemplateService.\_collect_config_changes() parameter

- ConfigTemplateService.\_collect_config_changes() parameter

- ConfigTemplateService.\_collect_additions_and_modifications() parameter

- ConfigTemplateService.\_collect_additions_and_modifications() parameter

- ConfigTemplateService.\_collect_removals() parameter

- ConfigTemplateService.\_collect_removals() parameter

- InitializationService.\_apply_merge_strategy() parameter

- InitializationService.\_handle_replace_if_missing() parameter

- InitializationService.\_handle_default_strategy() parameter

- InitializationService.\_process_config_file() parameter

- InitializationService.\_should_copy_file() parameter

- InitializationService.\_write_file_and_track() parameter

- InitializationService.\_skip_existing_file() parameter

- InitializationService.\_handle_missing_source_file() parameter

- InitializationService.\_handle_file_processing_error() parameter

- InitializationService.\_print_summary() parameter

- InitializationService.\_handle_initialization_error() parameter

- InitializationService.\_process_mcp_config() parameter

- InitializationService.\_merge_mcp_config() parameter

- InitializationService.\_merge_mcp_config() parameter

- InitializationService.\_write_mcp_config_and_track() parameter

- InitializationService.\_write_mcp_config_and_track() parameter

- InitializationService.\_smart_append_config() parameter

- InitializationService.\_smart_merge_gitignore() parameter

- InitializationService.\_smart_merge_config() parameter

- InitializationService.\_smart_merge_pyproject() parameter

- InitializationService.\_apply_template() parameter

- StatusSecurityManager.validate_request() parameter

- StatusSecurityManager.\_validate_request_data() parameter

- ThreadSafeStatusCollector.\_set_cached_data() parameter

- AIAgentDebugger.log_mcp_operation() parameter

- AIAgentDebugger.log_mcp_operation() parameter

- AIAgentDebugger.log_agent_activity() parameter

- AIAgentDebugger.log_agent_activity() parameter

- AIAgentDebugger.log_workflow_phase() parameter

- AIAgentDebugger.log_error_event() parameter

- NoOpDebugger.log_mcp_operation() parameter

- NoOpDebugger.log_mcp_operation() parameter

- NoOpDebugger.log_agent_activity() parameter

- NoOpDebugger.log_agent_activity() parameter

- NoOpDebugger.log_workflow_phase() parameter

- NoOpDebugger.log_error_event() parameter

- SecureStatusFormatter.format_status() parameter

- SecureStatusFormatter.\_log_status_access() parameter

- SecureStatusFormatter.\_prepare_data_for_sanitization() parameter

- SecureStatusFormatter.\_apply_all_sanitization_steps() parameter

- SecureStatusFormatter.\_add_security_metadata() parameter

- SecureStatusFormatter.\_apply_verbosity_filter() parameter

- SecureStatusFormatter.\_sanitize_sensitive_data() parameter

- TemplateDetector.\_analyze_project() parameter

- TemplateDetector.\_has_mcp_dependencies() parameter

- TemplateDetector.\_has_ai_agent_indicators() parameter

- TemplateDetector.\_has_complex_quality_tools() parameter

- TemplateDetector.\_is_library_project() parameter

- TemplateDetector.\_has_complex_dependencies() parameter

- ConfigParser.save() parameter

- JSONParser.save() parameter

- YAMLParser.save() parameter

- TOMLParser.save() parameter

- TOMLParser.\_dump_toml() parameter

- MessageDeduplicator.add_message() parameter

- SafeRefurbFixer.\_run_ast_grep_fix() parameter

- ConfigCleanupService.\_calculate_backup_checksum() parameter

- ConfigCleanupService.\_merge_config_files() parameter

- ConfigCleanupService.\_merge_single_file() parameter

- ConfigCleanupService.\_apply_merge_strategy() parameter

- ConfigCleanupService.\_write_pyproject_config() parameter

- ConfigCleanupService.\_merge_ini_file() parameter

- ConfigCleanupService.\_merge_pattern_file() parameter

- ConfigCleanupService.\_merge_json_file() parameter

- ConfigCleanupService.\_get_target_section() parameter

- ConfigCleanupService.\_merge_json_value() parameter

- ConfigCleanupService.\_merge_json_lists() parameter

- ConfigCleanupService.\_merge_json_dicts() parameter

- ConfigCleanupService.\_merge_json_dicts() parameter

- ConfigCleanupService.\_merge_ignore_file() parameter

- MemoryAwareScanner.\_is_known_good() parameter

- CommandExecutionService.run_command_sync() parameter

- FrontmatterValidationResult.from_payload() parameter

- ConfigService.validate_config() parameter

- ConfigService.save_config() parameter

- ConfigService.merge_configs() parameter

- ConfigService.merge_configs() parameter

- WorkflowOptimizationEngine.identify_bottlenecks() parameter

- WorkflowOptimizationEngine.generate_recommendations() parameter

- WorkflowOptimizationEngine.\_calculate_quality_correlations() parameter

- CoverageRatchetService.\_check_milestones() parameter

- CoverageRatchetService.\_update_baseline() parameter

- CoverageRatchetService.\_calculate_trend() parameter

- PatternCache.cache_successful_pattern() parameter

- TestResultParser.\_parse_json_test() parameter

- TestResultParser.\_extract_test_metrics() parameter

- TestResultParser.\_calculate_total_tests() parameter

- TestResultParser.\_parse_test_lines_by_token() parameter

- TestResultParser.\_parse_metric_patterns() parameter

- TestResultParser.\_parse_legacy_patterns() parameter

- TestResultParser.\_fallback_count_tests() parameter

- RunStateStore.\_count_statuses() parameter

- TestResultRenderer.render_test_results_panel() parameter

- TestResultRenderer.should_render_test_panel() parameter

- CoverageManager.update_coverage_badge() parameter

- CoverageManager.handle_ratchet_result() parameter

- CoverageManager.\_get_fallback_coverage() parameter

- CoverageManager.\_handle_coverage_improvement() parameter

- CommitMessageGenerator.\_determine_commit_type() parameter

- CommitMessageGenerator.\_determine_scope() parameter

- CommitMessageGenerator.\_generate_subject() parameter

- CommitMessageGenerator.\_generate_body() parameter

- ConnectionPool.add_connection() parameter

- DataCompactionManager.\_calculate_cutoff_date() parameter

- DataCompactionManager.\_build_compaction_result() parameter

- DataCompactionManager.\_build_compaction_result() parameter

- DataCompactionManager.\_build_storage_usage_report() parameter

- AdvancedOptimizer.\_generate_storage_recommendations() parameter

- TenantContextPack.\_body_keys_must_be_known_files() parameter

- BaseCodeFixer.\_validate_fix_quality() parameter

- BaseCodeFixer.\_enhance_prompt_for_retry() parameter

## fail

**Referenced in:**

- QueryOptimizerProtocol.track_search_interaction() parameter

- NoOpQueryOptimizer.track_search_interaction() parameter

- SQLiteQueryOptimizer.track_search_interaction() parameter

- SQLiteQueryOptimizer.\_update_query_pattern() parameter

## init

**Referenced in:**

- Task.__init__() parameter

- WorkflowManager.load_workflow() parameter

- CustomHookPlugin.__init__() parameter

- CustomHookPlugin.\_execute_command_hook() parameter

- AsyncHookExecutor.\_execute_hook_sync() parameter

- AsyncHookExecutor.\_log_termination_error() parameter

- AsyncHookExecutor.\_handle_runtime_error() parameter

- AsyncHookExecutor.\_handle_general_error() parameter

- ProgressHookExecutor.\_run_formatting_hook_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- ProgressHookExecutor.\_submit_parallel_hooks() parameter

- ProgressHookExecutor.\_collect_parallel_results() parameter

- ProgressHookExecutor.\_process_completed_future() parameter

- ProgressHookExecutor.\_create_error_result() parameter

- ProgressHookExecutor.\_update_progress_with_error() parameter

- CachedHookExecutor.\_execute_single_hook_with_cache() parameter

- CachedHookExecutor.\_get_cached_result() parameter

- CachedHookExecutor.\_handle_cache_hit() parameter

- CachedHookExecutor.\_handle_cache_miss() parameter

- CachedHookExecutor.\_cache_successful_result() parameter

- CachedHookExecutor.\_is_cache_valid() parameter

- HookExecutor.\_log_force_enabled_hooks() parameter

- HookExecutor.\_display_skipped_hooks() parameter

- HookExecutor.\_run_hooks_by_type() parameter

- HookExecutor.\_execute_single_hook_with_progress() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_create_run_hook_func() parameter

- HookExecutor.execute_single_hook() parameter

- HookExecutor.\_get_changed_files_for_hook() parameter

- HookExecutor.\_run_hook_subprocess() parameter

- HookExecutor.\_run_with_monitoring() parameter

- HookExecutor.\_create_hook_result_from_process() parameter

- HookExecutor.\_should_skip_offline_osv_scanner() parameter

- HookExecutor.\_should_skip_missing_osv_scanner_binary() parameter

- HookExecutor.\_determine_initial_status() parameter

- HookExecutor.\_update_status_for_reporting_tools() parameter

- HookExecutor.\_extract_issues_from_process_output() parameter

- HookExecutor.\_extract_issues_for_reporting_tools() parameter

- HookExecutor.\_extract_issues_for_regular_tools() parameter

- HookExecutor.\_create_timeout_result() parameter

- HookExecutor.\_create_error_result() parameter

- PoolOrchestrator.\_execute_single_hook_standard() parameter

- PoolOrchestrator.\_get_files_for_hook() parameter

- PoolOrchestrator.\_group_hooks_by_files() parameter

- PoolOrchestrator.\_convert_pool_results_to_hook_results() parameter

- ParallelHookExecutor.analyze_hook_dependencies() parameter

- ParallelHookExecutor.can_execute_in_parallel() parameter

- ParallelHookExecutor.can_execute_in_parallel() parameter

- ParallelHookExecutor.\_can_parallelize_group() parameter

## list

**Referenced in:**

- CommandRunner.run_command() parameter

- EnhancedCommandRunner.run() parameter

- CIFeedbackAnalyzer.\_generate_suggestions() parameter

- CIFeedbackAnalyzer.\_calculate_confidence() parameter

- CrackerjackAPI.run_quality_checks() parameter

- CrackerjackAPI.\_handle_todos_found() parameter

- CrackerjackAPI.\_display_todo_summary() parameter

- CrackerjackAPI.\_report_cleaning_results() parameter

- CrackerjackAPI.\_scan_files_for_todos() parameter

- WorkflowBuilder.add_task() parameter

- WorkflowBuilder.add_conditional_task() parameter

- CleaningPipeline.clean_file() parameter

- CleaningPipeline.\_apply_cleaning_pipeline() parameter

- CodeCleaner.\_execute_cleaning_with_backup() parameter

- CodeCleaner.\_handle_cleaning_failure() parameter

- CodeCleaner.\_handle_cleaning_failure() parameter

- CodeCleaner.\_handle_cleaning_failure() parameter

- CodeCleaner.\_handle_cleaning_success() parameter

- CodeCleaner.\_handle_cleaning_success() parameter

- CodeCleaner.\_create_docstring_finder_class() parameter

- \_DocstringFinder.__init__() parameter

- DualOutputGenerator.\_format_command_table() parameter

- ReferenceGenerator.\_assign_command_workflows() parameter

- ReferenceGenerator.\_determine_command_category() parameter

- ReferenceGenerator.\_add_command_to_category() parameter

- ReferenceGenerator.\_render_markdown_toc() parameter

- ReferenceGenerator.\_render_markdown_category() parameter

- ReferenceGenerator.\_render_markdown_workflows() parameter

- ReferenceGenerator.\_render_command_parameters_markdown() parameter

- ReferenceGenerator.\_render_command_examples_markdown() parameter

- ReferenceGenerator.\_render_command_related_markdown() parameter

- ReferenceGenerator.\_render_html_category() parameter

- ReferenceGenerator.\_render_html_category_commands() parameter

- ReferenceGenerator.\_render_html_command_parameters() parameter

- ReferenceGenerator.\_serialize_parameters() parameter

- ReferenceGenerator.\_render_rst_category_commands() parameter

- ReferenceGenerator.\_render_rst_command_parameters() parameter

- AITemplateEngine.create_ai_reference_template() parameter

- AITemplateEngine.create_user_guide_template() parameter

- AITemplateEngine.create_user_guide_template() parameter

- ParserFactory.\_validate_issue_count() parameter

- RuffJSONParser.parse_json() parameter

- RuffJSONParser.get_issue_count() parameter

- MypyJSONParser.parse_json() parameter

- MypyJSONParser.get_issue_count() parameter

- BanditJSONParser.parse_json() parameter

- BanditJSONParser.get_issue_count() parameter

- ComplexipyJSONParser.\_search_ast_for_line_number() parameter

- ComplexipyJSONParser.parse_json() parameter

- ComplexipyJSONParser.get_issue_count() parameter

- PyscnJSONParser.parse_json() parameter

- PyscnJSONParser.get_issue_count() parameter

- SemgrepJSONParser.parse_json() parameter

- SemgrepJSONParser.get_issue_count() parameter

- OsvScannerJSONParser.parse_json() parameter

- OsvScannerJSONParser.get_issue_count() parameter

- OsvScannerJSONParser.\_get_results_list() parameter

- GitleaksJSONParser.parse_json() parameter

- GitleaksJSONParser.get_issue_count() parameter

- PytestJSONParser.parse_json() parameter

- PytestJSONParser.get_issue_count() parameter

- LycheeJSONParser.parse_json() parameter

- LycheeJSONParser.get_issue_count() parameter

- CheckJSONSchemaJSONParser.parse_json() parameter

- CheckJSONSchemaJSONParser.get_issue_count() parameter

- MypyRegexParser.\_extract_mypy_line_number() parameter

- MypyRegexParser.\_extract_mypy_message() parameter

- RuffRegexParser.\_try_parse_diagnostic_format() parameter

- RuffRegexParser.\_skip_multiline_context() parameter

- JSONParser.parse_json() parameter

- JSONParser.get_issue_count() parameter

- ProactiveWorkflowPipeline.\_evaluate_planning_need() parameter

- ArchitecturalAssessment.__init__() parameter

- SessionCoordinator.complete_task() parameter

- SessionCoordinator.\_update_completed_task() parameter

- \_SubprocessExecutor.execute_secure() parameter

- RuntimeFactsBuilder.get_capabilities_summary() parameter

- PhaseCoordinator.\_classify_safe_test_failures() parameter

- PhaseCoordinator.\_execute_hooks_once() parameter

- PhaseCoordinator.\_run_hooks_with_progress() parameter

- PhaseCoordinator.\_report_hook_results() parameter

- PhaseCoordinator.\_render_hook_results_table() parameter

- PhaseCoordinator.\_render_plain_hook_results() parameter

- PhaseCoordinator.\_calculate_hook_statistics() parameter

- PhaseCoordinator.\_render_rich_hook_results() parameter

- PhaseCoordinator.\_build_results_table() parameter

- PhaseCoordinator.\_format_issues() parameter

- PhaseCoordinator.to_json() parameter

- PhaseCoordinator.\_format_failing_hooks() parameter

- PhaseCoordinator.\_display_hook_failures() parameter

- PhaseCoordinator.\_clean_python_files() parameter

- PhaseCoordinator.\_report_cleaning_results() parameter

- PhaseCoordinator.\_attempt_rollback_version_bump_files() parameter

- PhaseCoordinator.\_get_commit_message() parameter

- PhaseCoordinator.\_interactive_commit_message_selection() parameter

- PhaseCoordinator.\_display_commit_suggestions() parameter

- PhaseCoordinator.\_process_commit_choice() parameter

- PhaseCoordinator.\_execute_commit_and_push() parameter

- ParallelTaskExecutor.execute_tasks() parameter

- HookDefinition.build_command() parameter

- SecurityAuditor.audit_hook_results() parameter

- SecurityAuditor.audit_hook_results() parameter

- SecurityAuditor.\_generate_security_warnings() parameter

- SecurityAuditor.\_generate_security_warnings() parameter

- SecurityAuditor.\_generate_security_warnings() parameter

- SecurityAuditor.\_generate_security_recommendations() parameter

- SecurityAuditor.\_generate_security_recommendations() parameter

- SecurityAuditor.\_generate_security_recommendations() parameter

- HookPluginBase.execute_hook() parameter

- HookPluginBase.should_run_hook() parameter

- CustomHookPlugin.__init__() parameter

- CustomHookPlugin.execute_hook() parameter

- CustomHookPlugin.\_execute_command_hook() parameter

- HookPluginRegistry.execute_custom_hook() parameter

- HookPluginRegistry.get_hooks_for_files() parameter

- PluginDiscovery.load_discovered_plugins() parameter

- PluginManager.execute_custom_hook() parameter

- SkillsTrackerProtocol.track_invocation() parameter

- NoOpSkillsTracker.track_invocation() parameter

- SessionBuddyDirectTracker.track_invocation() parameter

- SessionBuddyMCPTracker.track_invocation() parameter

- SkillExecutionContext.from_agent_execution() parameter

- AdapterLearnerProtocol.recommend_adapter() parameter

- NoOpAdapterLearner.recommend_adapter() parameter

- SQLiteAdapterLearner.recommend_adapter() parameter

- AdapterLearningIntegration.get_adapter_recommendation() parameter

- DAGO_optimizerProtocol.learn_task_ordering() parameter

- NoOpDAGO_optimizer.learn_task_ordering() parameter

- SQLiteDAGO_optimizer.learn_task_ordering() parameter

- OneiricLearningIntegration.track_dag_execution() parameter

- OneiricLearningIntegration.learn_improved_ordering() parameter

- SkillsTracker.track_invocation() parameter

- QueryOptimizerProtocol.track_search_interaction() parameter

- QueryOptimizerProtocol.track_search_interaction() parameter

- QueryOptimizerProtocol.get_query_suggestions() parameter

- QueryOptimizerProtocol.adapt_ranking() parameter

- NoOpQueryOptimizer.track_search_interaction() parameter

- NoOpQueryOptimizer.track_search_interaction() parameter

- NoOpQueryOptimizer.get_query_suggestions() parameter

- NoOpQueryOptimizer.adapt_ranking() parameter

- SQLiteQueryOptimizer.track_search_interaction() parameter

- SQLiteQueryOptimizer.track_search_interaction() parameter

- SQLiteQueryOptimizer.get_query_suggestions() parameter

- SQLiteQueryOptimizer.adapt_ranking() parameter

- AkoshaLearningIntegration.track_search_results() parameter

- AkoshaLearningIntegration.enhance_search_results() parameter

- AkoshaLearningIntegration.get_query_improvements() parameter

- WorkflowLearnerProtocol.recommend_workflow() parameter

- NoOpWorkflowLearner.recommend_workflow() parameter

- SQLiteWorkflowLearner.recommend_workflow() parameter

- MahavishnuLearningIntegration.get_workflow_recommendation() parameter

- GitMetricsReader.get_metrics() parameter

- NoOpGitMetricsReader.get_metrics() parameter

- SessionBuddyIntegration.\_average_metric() parameter

- SessionBuddyIntegration.\_mode_metric() parameter

- SessionBuddyIntegration.\_calculate_quality_velocity_correlation() parameter

- SessionBuddyIntegration.\_calculate_conventional_quality_correlation() parameter

- \_NullGitService.rm_files() parameter

- PublishManagerImpl.\_run_command() parameter

- PublishManagerImpl.\_dispatch_publish() parameter

- TestCommandBuilder.\_add_json_report_options() parameter

- TestCommandBuilder.\_add_coverage_options() parameter

- TestCommandBuilder.\_add_incremental_coverage_options() parameter

- TestCommandBuilder.\_has_compact_no_xdist_flag() parameter

- TestCommandBuilder.\_add_worker_options() parameter

- TestCommandBuilder.\_add_worker_count_options() parameter

- TestCommandBuilder.\_add_auto_workers() parameter

- TestCommandBuilder.\_add_explicit_workers() parameter

- TestCommandBuilder.\_add_benchmark_options() parameter

- TestCommandBuilder.\_add_timeout_options() parameter

- TestCommandBuilder.\_add_verbosity_options() parameter

- TestCommandBuilder.\_add_test_path() parameter

- HookManagerImpl.\_setup_executor() parameter

- HookManagerImpl.__init__() parameter

- HookManagerImpl.get_hook_summary() parameter

- AsyncHookManager.get_hook_summary() parameter

- TestExecutor.\_detect_target_project_dir() parameter

- TestExecutor.\_find_pytest_index() parameter

- TestExecutor.\_find_project_from_test_args() parameter

- TestExecutor.execute_with_progress() parameter

- TestExecutor.execute_with_ai_progress() parameter

- TestExecutor.\_pre_collect_tests() parameter

- TestExecutor.\_execute_with_live_progress() parameter

- TestExecutor.\_run_test_command_with_ai_progress() parameter

- TestExecutor.\_should_try_xdist_fallback() parameter

- TestExecutor.\_get_optimal_worker_count_from_cmd() parameter

- TestExecutor.\_run_with_xdist_fallback() parameter

- TestExecutor.\_remove_xdist_from_cmd() parameter

- TestExecutor.\_cleanup_threads() parameter

- TestExecutor.\_execute_test_process_with_progress() parameter

- TestExecutor.\_read_stdout_loop() parameter

- TestExecutor.\_read_remaining_output() parameter

- TestExecutor.\_process_line() parameter

- TestExecutor.\_read_stderr_loop() parameter

- TestExecutor.\_read_remaining_stderr() parameter

- TestManager.\_extract_from_short_summary() parameter

- TestManager.\_extract_from_test_paths() parameter

- TestManager.\_process_line_for_section() parameter

- TestManager.\_process_line_for_section() parameter

- TestManager.\_handle_section_transition() parameter

- TestManager.\_handle_section_transition() parameter

- TestManager.\_handle_failure_section() parameter

- TestManager.\_handle_failure_section() parameter

- TestManager.\_render_structured_failures_with_summary() parameter

- TestManager.\_parse_traceback_line() parameter

- TestManager.\_enrich_failures_from_short_summary() parameter

- TestManager.\_create_failures_from_summary() parameter

- TestManager.\_create_failures_from_summary() parameter

- TestManager.\_enrich_existing_failures() parameter

- TestManager.\_enrich_existing_failures() parameter

- TestManager.\_try_enrich_named_failure() parameter

- TestManager.\_try_enrich_unnamed_failure() parameter

- TestManager.\_match_unnamed_failures() parameter

- TestManager.\_match_unnamed_failures() parameter

- TestManager.\_parse_failure_line() parameter

- TestManager.\_render_structured_failure_panels() parameter

- TestManager.\_build_simple_failure_list() parameter

- TestManager.\_group_failures_by_file() parameter

- TestManager.\_render_file_failure_header() parameter

- ServiceConfig.__init__() parameter

- ServiceWatchdog.__init__() parameter

- ErrorCache.\_merge_fixes() parameter

- StateManager.\_process_stage_issues() parameter

- StateManager.\_process_stage_fixes() parameter

- SessionTracker.complete_task() parameter

- CommandRunner.execute_command() parameter

- GitInterface.add_files() parameter

- GitInterface.checkout_files() parameter

- GitInterface.rm_files() parameter

- SecurityAwareHookManager.get_security_critical_failures() parameter

- SecurityAwareHookManager.has_security_critical_failures() parameter

- SecurityAwareHookManager.get_security_audit_report() parameter

- SecurityAwareHookManager.get_security_audit_report() parameter

- SecurityServiceProtocol.is_safe_subprocess_call() parameter

- ConfigMergeServiceProtocol.smart_merge_gitignore() parameter

- DocumentationServiceProtocol.extract_api_documentation() parameter

- DocumentationServiceProtocol.validate_documentation() parameter

- APIExtractorProtocol.extract_from_python_files() parameter

- APIExtractorProtocol.extract_service_interfaces() parameter

- APIExtractorProtocol.extract_cli_commands() parameter

- APIExtractorProtocol.extract_mcp_tools() parameter

- DocumentationValidatorProtocol.check_documentation_freshness() parameter

- ChangelogGeneratorProtocol.update_changelog() parameter

- QualityIntelligenceProtocol.analyze_trends() parameter

- SmartFileFilterProtocol.filter_files() parameter

- SecureSubprocessExecutorProtocol.execute_secure() parameter

- InteractiveTask.__init__() parameter

- InteractiveWorkflowManager.add_task() parameter

- ToolExecutionError.__init__() parameter

- ToolExecutionError.\_format_output() parameter

- CloneGrouper.group_pairs() parameter

- AsyncHookExecutor.\_execute_hook_sync() parameter

- AsyncHookExecutor.\_execute_hook_sync() parameter

- AsyncHookExecutor.\_process_semgrep_matches() parameter

- AsyncHookExecutor.\_print_summary() parameter

- HookOutputParser.parse_hook_output() parameter

- HookOutputParser.\_parse_ruff_check() parameter

- HookOutputParser.\_parse_pyright() parameter

- HookOutputParser.\_parse_bandit() parameter

- HookOutputParser.\_parse_vulture() parameter

- HookOutputParser.\_parse_complexipy() parameter

- HookOutputParser.\_parse_default_hook() parameter

- HookOutputParser.\_parse_generic_output() parameter

- IndividualHookExecutor.\_create_stream_reader_tasks() parameter

- IndividualHookExecutor.\_create_stream_reader_tasks() parameter

- IndividualHookExecutor.\_update_progress_with_line() parameter

- IndividualHookExecutor.\_handle_process_timeout() parameter

- IndividualHookExecutor.\_create_completed_process() parameter

- IndividualHookExecutor.\_create_completed_process() parameter

- IndividualHookExecutor.\_create_completed_process() parameter

- IndividualHookExecutor.\_print_individual_summary() parameter

- IndividualHookExecutor.\_print_individual_summary() parameter

- ToolProxy.execute_tool() parameter

- ToolProxy.\_execute_through_adapter() parameter

- ToolProxy.\_execute_direct() parameter

- ToolProxy.\_args_to_file_paths() parameter

- ToolProxy.\_try_fallback_tools() parameter

- ProgressHookExecutor.\_run_formatting_hook_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- ProgressHookExecutor.\_run_parallel_hooks_with_progress() parameter

- ProgressHookExecutor.\_submit_parallel_hooks() parameter

- ProgressHookExecutor.\_collect_parallel_results() parameter

- ProgressHookExecutor.\_process_completed_future() parameter

- CachedHookExecutor.\_get_cached_result() parameter

- CachedHookExecutor.\_cache_successful_result() parameter

- HookExecutor.__init__() parameter

- HookExecutor.\_apply_retries_if_needed() parameter

- HookExecutor.\_create_execution_result() parameter

- HookExecutor.\_calculate_performance_gain() parameter

- HookExecutor.\_display_skipped_hooks() parameter

- HookExecutor.\_run_hooks_by_type() parameter

- HookExecutor.\_execute_single_hook_with_progress() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_execute_parallel_hooks() parameter

- HookExecutor.\_create_run_hook_func() parameter

- HookExecutor.\_create_run_hook_func() parameter

- HookExecutor.\_handle_future_result() parameter

- HookExecutor.\_filter_files_by_hook_type() parameter

- HookExecutor.\_run_with_monitoring() parameter

- HookExecutor.\_update_status_for_reporting_tools() parameter

- HookExecutor.\_handle_no_issues_for_failed_hook() parameter

- HookExecutor.\_calculate_issues_count() parameter

- HookExecutor.\_extract_complexity_from_parts() parameter

- HookExecutor.\_parse_file_line() parameter

- HookExecutor.\_add_function_entries() parameter

- HookExecutor.\_parse_continuation_line() parameter

- HookExecutor.\_format_osv_vulnerability_message() parameter

- HookExecutor.\_process_matches() parameter

- HookExecutor.\_handle_retries() parameter

- HookExecutor.\_retry_formatting_hooks() parameter

- HookExecutor.\_find_failed_formatting_hooks() parameter

- HookExecutor.\_retry_all_formatting_hooks() parameter

- HookExecutor.\_retry_all_hooks() parameter

- HookExecutor.\_find_failed_hooks() parameter

- HookExecutor.\_retry_failed_hooks() parameter

- HookExecutor.\_retry_failed_hooks() parameter

- HookExecutor.\_retry_single_hook() parameter

- HookExecutor.\_retry_single_hook() parameter

- HookExecutor.\_print_summary() parameter

- \_InMemorySimpleOps.__init__() parameter

- \_InMemoryModelInterface.__init__() parameter

- DocumentationCleanup.\_validate_preconditions() parameter

- DocumentationCleanup.\_create_backup() parameter

- DocumentationCleanup.\_move_files_to_archive() parameter

- ToolFilter.filter_tools() parameter

- ToolFilter.filter_files() parameter

- ToolFilter.\_apply_patterns() parameter

- ToolFilter.\_apply_patterns() parameter

- ToolFilter.get_filtered_files() parameter

- DocumentationGeneratorImpl.\_format_methods() parameter

- DocumentationGeneratorImpl.\_find_protocol_method_references() parameter

- DocumentationGeneratorImpl.\_find_class_references() parameter

- DocumentationGeneratorImpl.\_find_class_method_references() parameter

- DocumentationGeneratorImpl.\_find_method_parameter_references() parameter

- FileHasher.get_directory_hash() parameter

- FileHasher.get_files_hash_list() parameter

- FileHasher.has_files_changed() parameter

- FileHasher.has_files_changed() parameter

- SmartFileWatcher.register_files() parameter

- FailedGitResult.__init__() parameter

- GitService.\_run_git_command() parameter

- GitService.add_files() parameter

- GitService.\_parse_pushed_refs() parameter

- GitService.\_display_push_results() parameter

- GitService.get_commit_message_suggestions() parameter

- GitService.\_categorize_files() parameter

- GitService.\_get_file_category() parameter

- GitService.\_generate_specific_messages() parameter

- GitService.get_changed_files_by_extension() parameter

- GitService.checkout_files() parameter

- GitService.rm_files() parameter

- IncrementalExecutor.execute_incremental() parameter

- IncrementalExecutor.get_changed_files() parameter

- DocUpdateService.\_run_git_command() parameter

- DocUpdateService.\_generate_doc_updates() parameter

- DocUpdateService.\_build_update_prompt() parameter

- DocUpdateService.\_apply_doc_updates() parameter

- DocUpdateService.\_create_update_commits() parameter

- DocUpdateService.\_generate_dry_run_summary() parameter

- DocUpdateService.\_generate_update_summary() parameter

- SwarmManager.\_create_tasks_from_issues() parameter

- CrackerjackPoolClient.\_build_tool_command() parameter

- FileChunker.chunk_files() parameter

- FileChunker.should_chunk_files() parameter

- FileChunker.estimate_parallel_benefit() parameter

- VersionChecker.\_normalize_version_parts() parameter

- VersionChecker.\_normalize_version_parts() parameter

- VersionChecker.\_compare_numeric_parts() parameter

- VersionChecker.\_compare_numeric_parts() parameter

- VersionChecker.\_handle_length_differences() parameter

- VersionChecker.\_handle_length_differences() parameter

- VersionChecker.\_compare_when_current_shorter() parameter

- VersionChecker.\_compare_when_latest_shorter() parameter

- VectorStore.\_store_embeddings() parameter

- VectorStore.\_get_all_embeddings() parameter

- AnomalyDetector.\_detect_seasonal_patterns() parameter

- PackageBackupService.\_filter_package_files() parameter

- PackageBackupService.\_perform_backup() parameter

- PoolOrchestrator.\_group_hooks_by_files() parameter

- PoolOrchestrator.\_convert_pool_results_to_hook_results() parameter

- CoverageBadgeService.\_find_badge_insertion_point() parameter

- SecurityService.is_safe_subprocess_call() parameter

- APIExtractorImpl.extract_from_python_files() parameter

- APIExtractorImpl.extract_service_interfaces() parameter

- APIExtractorImpl.extract_cli_commands() parameter

- APIExtractorImpl.extract_mcp_tools() parameter

- ChangelogGenerator.\_add_entry_to_collection() parameter

- ChangelogGenerator.update_changelog() parameter

- ChangelogGenerator.\_generate_changelog_section() parameter

- ChangelogGenerator.\_display_changelog_preview() parameter

- CrackerjackCache.get_hook_result() parameter

- CrackerjackCache.set_hook_result() parameter

- CrackerjackCache.get_expensive_hook_result() parameter

- CrackerjackCache.set_expensive_hook_result() parameter

- CrackerjackCache.\_get_hook_cache_key() parameter

- CrackerjackCache.\_get_versioned_hook_cache_key() parameter

- ConfigMergeService.smart_merge_gitignore() parameter

- ConfigMergeService.\_create_new_gitignore() parameter

- ConfigMergeService.\_parse_existing_gitignore_content() parameter

- ConfigMergeService.\_build_merged_gitignore_content() parameter

- ConfigMergeService.\_get_consolidated_patterns() parameter

- DocumentationServiceImpl.\_categorize_source_files() parameter

- DocumentationServiceImpl.\_extract_specialized_apis() parameter

- DocumentationServiceImpl.extract_api_documentation() parameter

- DocumentationServiceImpl.validate_documentation() parameter

- DocumentationServiceImpl.\_count_class_items() parameter

- DocumentationServiceImpl.\_count_function_items() parameter

- DocumentationServiceImpl.\_count_method_items() parameter

- DocumentationServiceImpl.\_generate_index_content() parameter

- DocumentationServiceImpl.\_generate_index_content() parameter

- DocumentationServiceImpl.\_generate_index_content() parameter

- DocumentationServiceImpl.\_generate_protocols_implemented() parameter

- DocumentationServiceImpl.\_generate_service_classes() parameter

- DocumentationServiceImpl.\_generate_public_methods() parameter

- DocumentationServiceImpl.\_format_cross_references() parameter

- HeatMapGenerator.\_build_error_matrix() parameter

- HeatMapGenerator.\_find_time_bucket_index() parameter

- HeatMapGenerator.\_create_frequency_cells() parameter

- HeatMapGenerator.\_create_frequency_cells() parameter

- HeatMapGenerator.\_create_frequency_labels() parameter

- HeatMapGenerator.\_create_frequency_labels() parameter

- HeatMapGenerator.\_create_complexity_labels() parameter

- HeatMapGenerator.\_calculate_metric_max_values() parameter

- HeatMapGenerator.\_create_quality_metric_cells() parameter

- HeatMapGenerator.\_create_quality_metric_cells() parameter

- HeatMapGenerator.\_group_test_errors_by_matrix() parameter

- HeatMapGenerator.\_create_test_failure_cells() parameter

- HeatMapGenerator.\_create_test_failure_cells() parameter

- HeatMapGenerator.\_build_test_failure_metadata() parameter

- HeatMapGenerator.\_build_test_failure_metadata() parameter

- SmartFileFilter.filter_by_pattern() parameter

- SmartFileFilter.filter_by_tool() parameter

- SmartFileFilter.filter_by_extensions() parameter

- SmartFileFilter.filter_by_extensions() parameter

- SmartFileFilter.get_python_files() parameter

- SmartFileFilter.get_markdown_files() parameter

- SmartFileFilter.filter_files() parameter

- SecureSubprocessExecutor.execute_secure() parameter

- SecureSubprocessExecutor.\_execute_with_validation() parameter

- SecureSubprocessExecutor.\_prepare_execution_params() parameter

- SecureSubprocessExecutor.\_handle_timeout_error() parameter

- SecureSubprocessExecutor.\_handle_process_error() parameter

- SecureSubprocessExecutor.\_handle_unexpected_error() parameter

- SecureSubprocessExecutor.\_validate_command() parameter

- SecureSubprocessExecutor.\_validate_command_structure() parameter

- SecureSubprocessExecutor.\_validate_command_arguments() parameter

- SecureSubprocessExecutor.\_has_dangerous_patterns() parameter

- SecureSubprocessExecutor.\_has_dangerous_patterns() parameter

- SecureSubprocessExecutor.\_check_dangerous_patterns_in_commit_message() parameter

- SecureSubprocessExecutor.\_check_dangerous_patterns_in_other_contexts() parameter

- SecureSubprocessExecutor.\_is_git_commit_message() parameter

- SecureSubprocessExecutor.\_validate_executable_permissions() parameter

- SecureSubprocessExecutor.\_validate_executable_permissions() parameter

- SecureSubprocessExecutor.\_handle_validation_results() parameter

- SecureSubprocessExecutor.\_handle_validation_results() parameter

- SecureSubprocessExecutor.\_filter_environment_variables() parameter

- SecureSubprocessExecutor.\_is_dangerous_environment_key() parameter

- SecureSubprocessExecutor.\_is_environment_value_too_long() parameter

- SecureSubprocessExecutor.\_has_environment_injection() parameter

- SecureSubprocessExecutor.\_log_environment_sanitization() parameter

- SmartFileFilterV2.mark_scan_complete() parameter

- SecurityLogger.log_file_cleaned() parameter

- SecurityLogger.log_subprocess_execution() parameter

- SecurityLogger.log_subprocess_environment_sanitized() parameter

- SecurityLogger.log_subprocess_command_validation() parameter

- SecurityLogger.log_subprocess_command_validation() parameter

- SecurityLogger.log_subprocess_timeout() parameter

- SecurityLogger.log_subprocess_failure() parameter

- SecurityLogger.log_dangerous_command_blocked() parameter

- SecurityLogger.log_dangerous_command_blocked() parameter

- SecurityLogger.log_status_access_attempt() parameter

- SecurityLogger.log_sensitive_data_sanitized() parameter

- CommitMessageGenerator.\_analyze_changes() parameter

- CommitMessageGenerator.\_is_fix_commit() parameter

- CommitMessageGenerator.\_is_feat_commit() parameter

- CommitMessageGenerator.\_is_test_commit() parameter

- CommitMessageGenerator.\_is_docs_commit() parameter

- CommitMessageGenerator.\_is_style_commit() parameter

- CommitMessageGenerator.\_is_refactor_commit() parameter

- ConfigTemplateService.\_collect_config_changes() parameter

- ConfigTemplateService.\_collect_additions_and_modifications() parameter

- ConfigTemplateService.\_collect_removals() parameter

- BreakingChangeAnalyzer.analyze() parameter

- FeatureAnalyzer.analyze() parameter

- ConventionalCommitAnalyzer.analyze() parameter

- VersionAnalyzer.\_analyze_entries_and_recommend() parameter

- VersionAnalyzer.\_determine_bump_type() parameter

- VersionAnalyzer.\_determine_bump_type() parameter

- VersionAnalyzer.\_determine_bump_type() parameter

- VersionAnalyzer.\_determine_bump_type() parameter

- VersionAnalyzer.\_determine_bump_type() parameter

- VersionAnalyzer.\_display_change_list() parameter

- SecureStatusFormatter.\_apply_validated_secret_patterns() parameter

- SecureStatusFormatter.\_mask_pattern_matches() parameter

- GitCleanupService.\_run_git_command() parameter

- GitCleanupService.\_get_gitignore_changes() parameter

- GitCleanupService.\_categorize_files() parameter

- GitCleanupService.\_remove_from_index_cached() parameter

- GitCleanupService.\_remove_from_index_hard() parameter

- GitCleanupService.\_generate_dry_run_summary() parameter

- GitCleanupService.\_generate_dry_run_summary() parameter

- GitCleanupService.\_generate_cleanup_summary() parameter

- GitCleanupService.\_generate_cleanup_summary() parameter

- ParallelHookExecutor.analyze_hook_dependencies() parameter

- ParallelHookExecutor.\_can_parallelize_group() parameter

- AsyncCommandExecutor.\_get_cache_key() parameter

- SafeRefurbFixer.\_find_furb107_matches() parameter

- SafeRefurbFixer.\_match_try_block() parameter

- SafeRefurbFixer.\_scan_except_handlers() parameter

- SafeRefurbFixer.\_is_inline_pass_except() parameter

- SafeRefurbFixer.\_evaluate_pass_except() parameter

- SafeRefurbFixer.\_get_body_indent() parameter

- SafeRefurbFixer.\_apply_furb107_fixes() parameter

- SafeRefurbFixer.\_apply_furb107_fixes() parameter

- SafeRefurbFixer.\_group_consecutive_appends() parameter

- SafeRefurbFixer.\_apply_extend_replacements() parameter

- \_StartswithTupleTransformer.\_group_startswith_calls() parameter

- \_StartswithTupleTransformer.\_try_transform_group() parameter

- \_StartswithTupleTransformer.\_extract_string_args() parameter

- \_StartswithTupleTransformer.\_create_combined_call() parameter

- \_StartswithTupleTransformer.\_build_replacement() parameter

- ConfigCleanupService.\_create_backup() parameter

- ConfigCleanupService.\_merge_all_configs() parameter

- ConfigCleanupService.\_merge_config_files() parameter

- ConfigCleanupService.\_merge_json_lists() parameter

- ConfigCleanupService.\_remove_standalone_configs() parameter

- ConfigCleanupService.\_cleanup_cache_dirs() parameter

- ConfigCleanupService.\_cleanup_output_files() parameter

- MemoryAwareScanner.\_generate_cache_key() parameter

- CommandExecutionService.\_get_executable() parameter

- CommandExecutionService.run_command_sync() parameter

- FrontmatterValidationResult.from_payload() parameter

- FrontmatterValidationResult.\_from_file_results() parameter

- MovingAveragePredictor.predict() parameter

- LinearTrendPredictor.predict() parameter

- SeasonalPredictor.predict() parameter

- PredictiveAnalyticsEngine.\_calculate_trend() parameter

- PredictiveAnalyticsEngine.\_calculate_confidence_intervals() parameter

- PredictiveAnalyticsEngine.\_calculate_confidence_intervals() parameter

- PredictorProtocol.predict() parameter

- MarkerTracker.get_files_needing_scan() parameter

- MarkerTracker.mark_scanned() parameter

- CoverageRatchetService.\_update_baseline() parameter

- CoverageRatchetService.display_milestone_celebration() parameter

- AntiAIFlavorDetector.__init__() parameter

- RunStateStore.\_count_statuses() parameter

- ContextualAIAssistant.display_recommendations() parameter

- ContextualAIAssistant.\_query_contains_keywords() parameter

- CommitMessageGenerator.\_analyze_changes() parameter

- CommitMessageGenerator.\_is_fix_commit() parameter

- CommitMessageGenerator.\_is_feat_commit() parameter

- CommitMessageGenerator.\_is_test_commit() parameter

- CommitMessageGenerator.\_is_docs_commit() parameter

- CommitMessageGenerator.\_is_style_commit() parameter

- CommitMessageGenerator.\_is_refactor_commit() parameter

- EmbeddingService.generate_embeddings_batch() parameter

- EmbeddingService.calculate_similarity() parameter

- EmbeddingService.calculate_similarity() parameter

- EmbeddingService.calculate_similarities_batch() parameter

- EmbeddingService.calculate_similarities_batch() parameter

- PredictorProtocol.predict() parameter

- MovingAveragePredictor.predict() parameter

- LinearTrendPredictor.predict() parameter

- SeasonalPredictor.predict() parameter

- PredictiveAnalyticsEngine.\_calculate_trend() parameter

- PredictiveAnalyticsEngine.\_calculate_confidence_intervals() parameter

- PredictiveAnalyticsEngine.\_calculate_confidence_intervals() parameter

- AdvancedOptimizer.\_build_optimization_result() parameter

- BaseCodeFixer.\_raise_if_dangerous_imports_found() parameter

- BaseCodeFixer.\_validate_fix_quality() parameter

- BaseCodeFixer.\_enhance_prompt_for_retry() parameter

## process

**Referenced in:**

- ManagedProcess.__init__() parameter

- ResourceContext.managed_process() parameter

- GitMetricsCollector.__init__() parameter

- TestExecutor.\_did_xdist_timeout() parameter

- TestExecutor.\_start_reader_threads() parameter

- TestExecutor.\_create_stdout_reader() parameter

- TestExecutor.\_create_stderr_reader() parameter

- TestExecutor.\_handle_progress_error() parameter

- TestExecutor.\_read_stdout_with_progress() parameter

- TestExecutor.\_read_stdout_blocking() parameter

- TestExecutor.\_read_stdout_loop() parameter

- TestExecutor.\_process_has_terminated() parameter

- TestExecutor.\_wait_for_readable_stdout() parameter

- TestExecutor.\_read_stderr_lines() parameter

- TestExecutor.\_read_stderr_blocking() parameter

- TestExecutor.\_read_stderr_loop() parameter

- TestExecutor.\_wait_for_readable_stderr() parameter

- TestExecutor.\_wait_for_process_completion() parameter

- TestManager.\_record_run_state() parameter

- IndividualHookExecutor.\_create_stream_reader_tasks() parameter

- IndividualHookExecutor.\_handle_process_timeout() parameter

- IndividualHookExecutor.\_create_completed_process() parameter

- ProcessMonitor.monitor_process() parameter

- ProcessMonitor.\_monitor_loop() parameter

- ProcessMonitor.\_should_stop_monitoring() parameter

- HookExecutor.\_display_hook_output_if_needed() parameter

- HookExecutor.\_create_hook_result_from_process() parameter

- HookExecutor.\_should_skip_offline_osv_scanner() parameter

- HookExecutor.\_determine_initial_status() parameter

- HookExecutor.\_update_status_for_reporting_tools() parameter

- HookExecutor.\_determine_exit_code_and_error() parameter

- HookExecutor.\_handle_no_issues_for_failed_hook() parameter

- HookExecutor.\_extract_issues_from_process_output() parameter

- HookExecutor.\_extract_issues_for_regular_tools() parameter

- HookExecutor.\_parse_hook_output() parameter

- HookExecutor.\_parse_semgrep_output() parameter

- HookExecutor.\_parse_semgrep_json_output() parameter

- GitService.\_handle_commit_failure() parameter

- GitService.\_handle_hook_error() parameter

- SecureSubprocessExecutor.__init__() parameter

- SecureSubprocessExecutor.\_log_successful_execution() parameter

- SecureSubprocessExecutor.\_handle_process_error() parameter

## read

**Referenced in:**

- TestExecutor.\_cleanup_threads() parameter

- ProgressHookExecutor.\_submit_parallel_hooks() parameter

## set

**Referenced in:**

- CrackerjackAPI.\_should_skip_file() parameter

- Task.can_run() parameter

- CodeCleaner.\_should_include_file_path() parameter

- CheckJSONSchemaJSONParser.\_parse_frame() parameter

- ExtractionTargetClassifier.\_has_local_repo_imports() parameter

- ExtractionTargetClassifier.\_is_foundational() parameter

- HookExecutor.\_extract_osv_vulnerability_issues() parameter

- GitService.\_generate_category_messages() parameter

- ConfigMergeService.\_get_consolidated_patterns() parameter

- SubprocessSecurityConfig.__init__() parameter

- SubprocessSecurityConfig.__init__() parameter

- CommitMessageGenerator.\_is_fix_commit() parameter

- CommitMessageGenerator.\_is_fix_commit() parameter

- CommitMessageGenerator.\_is_feat_commit() parameter

- CommitMessageGenerator.\_is_feat_commit() parameter

- CommitMessageGenerator.\_is_test_commit() parameter

- CommitMessageGenerator.\_is_test_commit() parameter

- CommitMessageGenerator.\_is_docs_commit() parameter

- CommitMessageGenerator.\_is_docs_commit() parameter

- CommitMessageGenerator.\_is_style_commit() parameter

- CommitMessageGenerator.\_is_style_commit() parameter

- CommitMessageGenerator.\_is_refactor_commit() parameter

- CommitMessageGenerator.\_is_refactor_commit() parameter

- StatusAuthenticator.add_api_key() parameter

- StatusSecurityManager.__init__() parameter

- CommitMessageGenerator.\_is_fix_commit() parameter

- CommitMessageGenerator.\_is_fix_commit() parameter

- CommitMessageGenerator.\_is_feat_commit() parameter

- CommitMessageGenerator.\_is_feat_commit() parameter

- CommitMessageGenerator.\_is_test_commit() parameter

- CommitMessageGenerator.\_is_test_commit() parameter

- CommitMessageGenerator.\_is_docs_commit() parameter

- CommitMessageGenerator.\_is_docs_commit() parameter

- CommitMessageGenerator.\_is_style_commit() parameter

- CommitMessageGenerator.\_is_style_commit() parameter

- CommitMessageGenerator.\_is_refactor_commit() parameter

- CommitMessageGenerator.\_is_refactor_commit() parameter

## sign

**Referenced in:**

- APIExtractorImpl.\_create_cli_field_info() parameter

## source

**Referenced in:**

- ResourceManager.register_resource() parameter

- ManagedResource.__init__() parameter

- ManagedTemporaryFile.__init__() parameter

- ManagedTemporaryDirectory.__init__() parameter

- ManagedProcess.__init__() parameter

- ManagedTask.__init__() parameter

- ManagedFileHandle.__init__() parameter

- AtomicFileWriter.__init__() parameter

- LockedFileResource.__init__() parameter

- SafeDirectoryCreator.__init__() parameter

- BatchFileOperations.__init__() parameter

- MemoryOptimizer.register_resource_pool() parameter

- AdvancedOptimizer.\_generate_cpu_recommendations() parameter

- AdvancedOptimizer.\_generate_memory_recommendations() parameter

- AdvancedOptimizer.\_apply_all_optimizations() parameter

- AdvancedOptimizer.\_apply_memory_optimizations() parameter

- AdvancedOptimizer.\_apply_performance_optimizations() parameter

## sync

**Referenced in:**

- \_DocstringFinder.visit_AsyncFunctionDef() parameter

- DocstringFinder.visit_AsyncFunctionDef() parameter

- ManagedProcess.__init__() parameter

- ManagedTask.__init__() parameter

- ResourceContext.managed_process() parameter

- ResourceContext.managed_task() parameter

- ResourceLeakDetector.track_task() parameter

- ResourceLeakDetector.untrack_task() parameter

- AsyncHookManager.__init__() parameter

- ServiceWatchdog.__init__() parameter

- ResourceManagerProtocol.register_resource() parameter

- AbstractTaskResource.__init__() parameter

- AsyncHookExecutor.\_get_pending_hook_tasks() parameter

- IndividualHookExecutor.\_create_stream_reader_tasks() parameter

- IndividualHookExecutor.\_handle_process_timeout() parameter

- IndividualHookExecutor.\_handle_process_timeout() parameter

- IndividualHookExecutor.\_create_completed_process() parameter

## tag

**Referenced in:**

- StateManager.\_update_stage_completion() parameter

- StateManager.\_process_stage_issues() parameter

- StateManager.\_process_stage_fixes() parameter

- AsyncHookExecutor.\_execute_hook_sync() parameter
