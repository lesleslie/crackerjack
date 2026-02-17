# Cross References

This document shows where API components are used throughout the codebase.

## AIRecommendation

**Referenced in:**

- ContextualAIAssistant.display_recommendations() parameter

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

## AgentCapability

**Referenced in:**

- AgentSelector.\_generate_score_reasoning() parameter
- AgentSelector.\_assess_complexity() parameter
- AgentSelector.\_generate_recommendations() parameter
- AgentRegistry.get_agents_by_capability() parameter

## AgentContext

**Referenced in:**

- AgentCoordinator.__init__() parameter
- ProactiveAgent.__init__() parameter
- PerformanceAgent.__init__() parameter
- TestSpecialistAgent.__init__() parameter
- SecurityAgent.__init__() parameter
- FormattingAgent.__init__() parameter
- TestCreationAgent.__init__() parameter
- ImportOptimizationAgent.__init__() parameter
- SubAgent.__init__() parameter
- AgentRegistry.create_all() parameter

## AgentPerformanceMetrics

**Referenced in:**

- AdaptiveLearningSystem.\_update_basic_counters() parameter
- AdaptiveLearningSystem.\_update_execution_averages() parameter
- AdaptiveLearningSystem.\_update_capability_success_rates() parameter
- AdaptiveLearningSystem.\_update_performance_trend() parameter
- AdaptiveLearningSystem.\_calculate_metrics_score() parameter

## AgentRegistry

**Referenced in:**

- AgentSelector.__init__() parameter
- AgentOrchestrator.__init__() parameter

## AgentScore

**Referenced in:**

- AgentSelector.\_assess_complexity() parameter
- AgentSelector.\_generate_recommendations() parameter
- AgentOrchestrator.\_generate_recommendations() parameter

## AgentSelector

**Referenced in:**

- AgentOrchestrator.__init__() parameter

## AntiPattern

**Referenced in:**

- PatternDetector.\_generate_solution_key() parameter
- PatternDetector.\_find_cached_pattern_for_anti_pattern() parameter
- PatternDetector.\_create_temp_issue_for_lookup() parameter

## AsyncCleanupProtocol

**Referenced in:**

- ResourceManagerProtocol.register_resource() parameter

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
- PackageBackupService.restore_from_backup() parameter
- PackageBackupService.cleanup_backup() parameter
- PackageBackupService.\_validate_backup() parameter
- PackageBackupService.\_stage_backup_files() parameter
- PackageBackupService.\_commit_restoration() parameter

## BaseRustToolAdapter

**Referenced in:**

- ZubanAdapter base class
- SkylsAdapter base class

## BenchmarkResult

**Referenced in:**

- BenchmarkSuite.add_result() parameter

## BenchmarkSuite

**Referenced in:**

- PerformanceBenchmarker.export_benchmark_results() parameter

## CacheAnalytics

**Referenced in:**

- EnhancedCacheHandlers.\_create_analytics_table() parameter
- EnhancedCacheHandlers.\_create_insights_panel() parameter
- EnhancedCacheHandlers.\_generate_optimization_suggestions() parameter

## CacheOptimizationSuggestion

**Referenced in:**

- EnhancedCacheHandlers.\_create_suggestions_panel() parameter
- EnhancedCacheHandlers.\_apply_optimization_suggestion() parameter

## CachedHookExecutor

**Referenced in:**

- SmartCacheManager.__init__() parameter

## ChangelogEntry

**Referenced in:**

- ChangelogGenerator.update_changelog() parameter
- ChangelogGenerator.\_generate_changelog_section() parameter
- ChangelogGenerator.\_display_changelog_preview() parameter

## CleaningResult

**Referenced in:**

- CrackerjackAPI.\_report_safe_cleaning_results() parameter
- CrackerjackAPI.\_report_cleaning_results() parameter
- CleaningErrorHandler.log_cleaning_result() parameter
- CodeCleaner.\_handle_cleaning_failure() parameter
- CodeCleaner.\_handle_cleaning_success() parameter
- PhaseCoordinator.\_report_package_cleaning_results() parameter

## CleaningStepProtocol

**Referenced in:**

- CleaningPipeline.clean_file() parameter
- CleaningPipeline.\_apply_cleaning_pipeline() parameter

## CommandResult

**Referenced in:**

- EnhancedCommandRunner.handle_result() parameter

## Config

**Referenced in:**

- DynamicConfigGenerator.\_should_include_hook() parameter
- ServiceWatchdog.add_service() parameter
- AsyncTimeoutManager.__init__() parameter
- PhaseCoordinator.__init__() parameter
- ServiceWatchdog.__init__() parameter
- ServiceWatchdog.\_determine_restart_reason() parameter
- ServiceWatchdog.\_get_service_status() parameter
- ServiceWatchdog.\_get_service_health() parameter
- ResourceMonitor.__init__() parameter
- RateLimitMiddleware.__init__() parameter
- MCPServerContext.__init__() parameter
- MCPContextManager.__init__() parameter
- StrategySelector.select_strategy() parameter
- OrchestrationPlanner.create_execution_plan() parameter
- OrchestrationPlanner.\_create_test_plan() parameter
- OrchestrationPlanner.\_create_ai_plan() parameter
- ProgressStreamer.__init__() parameter
- AdvancedWorkflowOrchestrator.__init__() parameter
- SecureSubprocessExecutor.__init__() parameter
- InitializationService.__init__() parameter
- SecureInputValidator.__init__() parameter

## ConfigMergeService

**Referenced in:**

- PhaseCoordinator.__init__() parameter
- InitializationService.__init__() parameter

## ConfigMergeServiceProtocol

**Referenced in:**

- PhaseCoordinator.__init__() parameter
- ConfigMergeService base class
- InitializationService.__init__() parameter

## ConfigMode

**Referenced in:**

- DynamicConfigGenerator.\_should_include_hook() parameter

## ConfigSource

**Referenced in:**

- EnvironmentConfigSource base class
- FileConfigSource base class
- PyprojectConfigSource base class
- OptionsConfigSource base class
- DefaultConfigSource base class

## ConnectionMetrics

**Referenced in:**

- WebSocketResourceLimiter.\_check_message_count() parameter

## CoverageRatchetProtocol

**Referenced in:**

- TestManager.__init__() parameter

## CrackerjackCache

**Referenced in:**

- AgentCoordinator.__init__() parameter
- EnhancedCacheHandlers.__init__() parameter
- CachedHookExecutor.__init__() parameter
- QualityBaselineService.__init__() parameter
- FileHasher.__init__() parameter
- EnhancedQualityBaselineService.__init__() parameter

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

## CustomHookDefinition

**Referenced in:**

- CustomHookPlugin.__init__() parameter
- CustomHookPlugin.\_execute_command_hook() parameter

## DependencyContainer

**Referenced in:**

- DependencyResolver.__init__() parameter
- ServiceCollectionBuilder.__init__() parameter

## DependencyVulnerability

**Referenced in:**

- DependencyMonitorService.\_run_vulnerability_tool() parameter
- DependencyMonitorService.\_process_vulnerability_result() parameter
- DependencyMonitorService.\_report_vulnerabilities() parameter

## DocumentationGeneratorProtocol

**Referenced in:**

- DocumentationGeneratorImpl base class
- DocumentationServiceImpl.__init__() parameter

## DocumentationServiceProtocol

**Referenced in:**

- DocumentationServiceImpl base class

## EnhancedDependencyContainer

**Referenced in:**

- DependencyResolver.__init__() parameter
- ServiceCollectionBuilder.__init__() parameter

## EnhancedNestedLoopAnalyzer

**Referenced in:**

- PerformanceAgent.\_build_nested_loop_issues() parameter

## EnhancedUsageAnalyzer

**Referenced in:**

- UsageDataCollector.get_results() parameter

## ErrorCode

**Referenced in:**

- CrackerjackError.__init__() parameter
- ConfigError.__init__() parameter
- ExecutionError.__init__() parameter
- TestExecutionError.__init__() parameter
- FileError.__init__() parameter

## ErrorHandlingMixin

**Referenced in:**

- PhaseCoordinator base class

## ErrorPattern

**Referenced in:**

- ErrorCache.\_update_existing_pattern() parameter
- ErrorCache.\_update_existing_pattern() parameter
- ErrorCache.\_merge_fixes() parameter

## ExecutionContext

**Referenced in:**

- ZubanAdapter.__init__() parameter
- RustToolHookManager.__init__() parameter
- RustToolAdapter.__init__() parameter
- BaseRustToolAdapter.__init__() parameter
- SkylsAdapter.__init__() parameter
- StrategySelector.select_strategy() parameter
- StrategySelector.\_select_adaptive_strategy() parameter
- StrategySelector.select_hook_subset() parameter
- StrategySelector.\_create_selective_strategy() parameter
- OrchestrationPlanner.create_execution_plan() parameter
- OrchestrationPlanner.\_create_test_plan() parameter
- OrchestrationPlanner.\_create_ai_plan() parameter
- AdvancedWorkflowOrchestrator.\_adapt_execution_plan() parameter

## ExecutionPlan

**Referenced in:**

- AdvancedWorkflowOrchestrator.\_adapt_execution_plan() parameter

## ExecutionRecord

**Referenced in:**

- AdaptiveLearningSystem.\_update_basic_counters() parameter
- AdaptiveLearningSystem.\_update_execution_averages() parameter
- AdaptiveLearningSystem.\_update_capability_success_rates() parameter
- AdaptiveLearningSystem.\_calculate_windowed_success_rates() parameter

## ExecutionStrategy

**Referenced in:**

- AgentOrchestrator.\_create_error_result() parameter
- StrategySelector.select_hook_subset() parameter
- OrchestrationPlanner.\_create_test_plan() parameter
- ParallelHookExecutor.__init__() parameter

## FailedGitResult

**Referenced in:**

- GitService.\_handle_commit_failure() parameter
- GitService.\_handle_hook_error() parameter

## FileHasher

**Referenced in:**

- SmartFileWatcher.__init__() parameter

## FileSystemInterface

**Referenced in:**

- PhaseCoordinator.__init__() parameter
- PublishManagerImpl.__init__() parameter
- EnhancedFileSystemService base class
- HealthMetricsService.__init__() parameter
- ConfigMergeService.__init__() parameter
- ContextualAIAssistant.__init__() parameter
- DependencyMonitorService.__init__() parameter

## FileSystemService

**Referenced in:**

- InitializationService.__init__() parameter

## FixResult

**Referenced in:**

- AsyncWorkflowPipeline.\_report_fix_results() parameter
- AsyncWorkflowPipeline.\_report_successful_fixes() parameter
- AsyncWorkflowPipeline.\_report_failed_fixes() parameter
- ProactiveAgent.\_cache_successful_pattern() parameter
- AgentTracker.track_agent_complete() parameter
- FixResult.merge_with() parameter
- RegressionPreventionSystem.\_check_pattern_match() parameter
- RegressionPreventionSystem.\_build_failure_text() parameter
- RegressionPreventionSystem.\_check_agent_specific_failure() parameter
- PatternCache.cache_successful_pattern() parameter

## GitInterface

**Referenced in:**

- PhaseCoordinator.__init__() parameter
- ConfigMergeService.__init__() parameter

## GitService

**Referenced in:**

- ChangelogGenerator.__init__() parameter
- CommitMessageGenerator.__init__() parameter
- InitializationService.__init__() parameter

## HookDefinition

**Referenced in:**

- CustomHookPlugin.__init__() parameter
- CustomHookPlugin.\_execute_command_hook() parameter
- CachedHookExecutor.\_is_cache_valid() parameter
- HookExecutor.execute_single_hook() parameter
- HookExecutor.\_run_hook_subprocess() parameter
- HookExecutor.\_create_hook_result_from_process() parameter
- HookExecutor.\_extract_issues_from_process_output() parameter
- HookExecutor.\_create_timeout_result() parameter
- HookExecutor.\_create_error_result() parameter
- ParallelHookExecutor.analyze_hook_dependencies() parameter
- ParallelHookExecutor.can_execute_in_parallel() parameter
- ParallelHookExecutor.can_execute_in_parallel() parameter
- ParallelHookExecutor.\_can_parallelize_group() parameter

## HookExecutor

**Referenced in:**

- SmartCacheManager.__init__() parameter

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

- PhaseCoordinator.__init__() parameter
- SecurityAwareHookManager base class

## HookMetadata

**Referenced in:**

- DynamicConfigGenerator.\_should_include_hook() parameter
- DynamicConfigGenerator.group_hooks_by_repo() parameter

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
- MinimalProgressStreamer.update_hook_progress() parameter
- ProgressStreamer.update_hook_progress() parameter

## HookResult

**Referenced in:**

- HookManagerImpl.get_hook_summary() parameter
- AsyncHookManager.get_hook_summary() parameter
- AsyncHookExecutor.\_display_hook_result() parameter
- AsyncHookExecutor.\_print_summary() parameter
- IndividualHookExecutor.\_update_hook_progress_status() parameter
- IndividualHookExecutor.\_print_hook_summary() parameter
- IndividualHookExecutor.\_print_individual_summary() parameter
- CachedHookExecutor.\_is_cache_valid() parameter
- HookExecutor.\_display_hook_result() parameter
- HookExecutor.\_handle_retries() parameter
- HookExecutor.\_retry_formatting_hooks() parameter
- HookExecutor.\_retry_all_hooks() parameter
- HookExecutor.\_print_summary() parameter
- CorrelationTracker.record_iteration() parameter
- CrackerjackCache.set_hook_result() parameter
- CrackerjackCache.set_expensive_hook_result() parameter

## HookStrategy

**Referenced in:**

- AsyncHookExecutor.\_print_strategy_header() parameter
- AsyncHookExecutor.\_print_summary() parameter
- IndividualHookExecutor.\_finalize_execution_result() parameter
- IndividualHookExecutor.\_print_strategy_header() parameter
- IndividualHookExecutor.\_print_individual_summary() parameter
- CachedHookExecutor.execute_strategy() parameter
- CachedHookExecutor.\_get_relevant_files_for_strategy() parameter
- CachedHookExecutor.\_strategy_affects_python_only() parameter
- CachedHookExecutor.\_strategy_affects_config_only() parameter
- SmartCacheManager.get_optimal_cache_strategy() parameter
- HookExecutor.execute_strategy() parameter
- HookExecutor.\_print_strategy_header() parameter
- HookExecutor.\_execute_sequential() parameter
- HookExecutor.\_execute_parallel() parameter
- HookExecutor.\_handle_retries() parameter
- HookExecutor.\_retry_formatting_hooks() parameter
- HookExecutor.\_retry_all_hooks() parameter
- HookExecutor.\_print_summary() parameter
- StrategySelector.select_hook_subset() parameter
- StrategySelector.\_create_selective_strategy() parameter
- OrchestrationPlanner.create_execution_plan() parameter
- OrchestrationPlanner.\_estimate_strategy_duration() parameter

## ImportAnalysis

**Referenced in:**

- ImportOptimizationAgent.\_are_optimizations_needed() parameter
- ImportOptimizationAgent.\_prepare_fix_results() parameter
- ImportOptimizationAgent.\_apply_import_optimizations() parameter
- ImportOptimizationAgent.\_apply_all_optimization_steps() parameter
- ImportOptimizationAgent.\_extract_file_metrics() parameter

## InteractiveTask

**Referenced in:**

- InteractiveTask.__init__() parameter
- InteractiveWorkflowManager.execute_task() parameter
- InteractiveWorkflowManager.\_handle_task_failure() parameter

## Issue

**Referenced in:**

- ProactiveWorkflowPipeline.\_evaluate_planning_need() parameter
- ArchitecturalAssessment.__init__() parameter
- AsyncWorkflowPipeline.\_create_generic_issue() parameter
- IntelligentAgentSystem.\_map_issue_to_task_context() parameter
- AgentCoordinator.\_group_issues_by_type() parameter
- AgentCoordinator.\_create_issue_hash() parameter
- AgentCoordinator.\_prioritize_issues_by_plan() parameter
- AgentCoordinator.\_should_use_architect_for_group() parameter
- AgentCoordinator.\_is_critical_group() parameter
- RefactoringAgent.\_has_complexity_markers() parameter
- RefactoringAgent.\_has_dead_code_markers() parameter
- RefactoringAgent.\_validate_complexity_issue() parameter
- RefactoringAgent.\_validate_dead_code_issue() parameter
- ProactiveAgent.\_get_planning_cache_key() parameter
- ProactiveAgent.\_cache_successful_pattern() parameter
- ArchitectAgent.\_get_specialist_approach() parameter
- ArchitectAgent.\_get_internal_approach() parameter
- ArchitectAgent.\_get_recommended_patterns() parameter
- ArchitectAgent.\_get_cached_patterns_for_issue() parameter
- ArchitectAgent.\_analyze_dependencies() parameter
- ArchitectAgent.\_identify_risks() parameter
- ArchitectAgent.\_get_validation_steps() parameter
- PerformanceAgent.\_validate_performance_issue() parameter
- DRYAgent.\_validate_dry_issue() parameter
- AgentTracker.track_agent_processing() parameter
- TestSpecialistAgent.\_check_general_test_failure() parameter
- TestSpecialistAgent.\_identify_failure_type() parameter
- SecurityAgent.\_identify_vulnerability_type() parameter
- SecurityAgent.\_is_regex_validation_issue() parameter
- TestCreationAgent.\_log_analysis() parameter
- ImportOptimizationAgent.\_validate_issue() parameter
- StateManager.\_process_stage_issues() parameter
- TypeIssue base class
- DeadCodeIssue base class
- RegressionPreventionSystem.register_regression_pattern() parameter
- RegressionPreventionSystem.\_generate_issue_signature() parameter
- RegressionPreventionSystem.\_check_pattern_match() parameter
- RegressionPreventionSystem.\_build_failure_text() parameter
- RegressionPreventionSystem.\_check_agent_specific_failure() parameter
- RegressionPreventionSystem.\_create_regression_alert() parameter
- PatternCache.cache_successful_pattern() parameter
- PatternCache.get_patterns_for_issue() parameter
- PatternCache.get_best_pattern_for_issue() parameter
- PatternDetector.\_create_temp_issue_for_lookup() parameter

## IssueType

**Referenced in:**

- AsyncWorkflowPipeline.\_create_generic_issue() parameter
- TestSpecialistAgent.\_check_general_test_failure() parameter
- RegressionPreventionSystem.register_regression_pattern() parameter
- RegressionPreventionSystem.\_generate_issue_signature() parameter
- PatternDetector.\_create_temp_issue_for_lookup() parameter

## JobManager

**Referenced in:**

- WebSocketHandler.__init__() parameter

## LazyLoader

**Referenced in:**

- MemoryOptimizer.register_lazy_object() parameter

## LearningInsight

**Referenced in:**

- AdaptiveLearningSystem.\_is_duplicate_insight() parameter

## MCPServerConfig

**Referenced in:**

- MCPServerContext.__init__() parameter
- MCPContextManager.__init__() parameter

## MajorUpdate

**Referenced in:**

- DependencyMonitorService.\_report_major_updates() parameter

## ManagedResource

**Referenced in:**

- ManagedWebSocketConnection base class
- ManagedHTTPClient base class
- ManagedWebSocketServer base class
- ManagedSubprocess base class
- ManagedTemporaryFile base class
- ManagedTemporaryDirectory base class
- ManagedProcess base class
- ManagedTask base class
- ManagedFileHandle base class

## ManagedWebSocketServer

**Referenced in:**

- WebSocketHealthMonitor.add_server() parameter
- WebSocketHealthMonitor.remove_server() parameter

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
- WorkflowPipeline.\_initialize_workflow_session() parameter
- WorkflowPipeline.\_log_workflow_startup_debug() parameter
- WorkflowPipeline.\_configure_session_cleanup() parameter
- WorkflowPipeline.\_log_workflow_startup_info() parameter
- WorkflowPipeline.\_is_publishing_workflow() parameter
- WorkflowPipeline.\_execute_optional_cleaning_phase() parameter
- WorkflowPipeline.\_start_iteration_tracking() parameter
- WorkflowPipeline.\_run_initial_fast_hooks() parameter
- WorkflowPipeline.\_finalize_ai_workflow_success() parameter
- WorkflowPipeline.\_run_fast_hooks_phase() parameter
- WorkflowPipeline.\_run_testing_phase() parameter
- WorkflowPipeline.\_run_comprehensive_hooks_phase() parameter
- WorkflowPipeline.\_run_code_cleaning_phase() parameter
- WorkflowPipeline.\_run_post_cleaning_fast_hooks() parameter
- WorkflowPipeline.\_execute_standard_hooks_workflow() parameter
- WorkflowPipeline.\_initialize_ai_fixing_phase() parameter
- WorkflowPipeline.\_prepare_ai_fixing_environment() parameter
- WorkflowPipeline.\_check_security_gates_for_publishing() parameter
- WorkflowPipeline.\_execute_monitored_fast_hooks_phase() parameter
- WorkflowPipeline.\_execute_monitored_cleaning_phase() parameter
- WorkflowPipeline.\_execute_monitored_comprehensive_phase() parameter
- WorkflowOrchestrator.\_initialize_session_tracking() parameter
- WorkflowOrchestrator.run_cleaning_phase() parameter
- WorkflowOrchestrator.run_fast_hooks_only() parameter
- WorkflowOrchestrator.run_comprehensive_hooks_only() parameter
- WorkflowOrchestrator.run_hooks_phase() parameter
- WorkflowOrchestrator.run_testing_phase() parameter
- WorkflowOrchestrator.run_publishing_phase() parameter
- WorkflowOrchestrator.run_commit_phase() parameter
- WorkflowOrchestrator.run_configuration_phase() parameter
- AsyncWorkflowPipeline.\_create_parallel_tasks() parameter
- AsyncWorkflowOrchestrator.run_complete_workflow() parameter
- AsyncWorkflowOrchestrator.run_cleaning_phase() parameter
- AsyncWorkflowOrchestrator.run_fast_hooks_only() parameter
- AsyncWorkflowOrchestrator.run_comprehensive_hooks_only() parameter
- AsyncWorkflowOrchestrator.run_hooks_phase() parameter
- AsyncWorkflowOrchestrator.run_testing_phase() parameter
- AsyncWorkflowOrchestrator.run_publishing_phase() parameter
- AsyncWorkflowOrchestrator.run_commit_phase() parameter
- AsyncWorkflowOrchestrator.run_configuration_phase() parameter
- SessionCoordinator.initialize_session_tracking() parameter
- PhaseCoordinator.run_cleaning_phase() parameter
- PhaseCoordinator.run_configuration_phase() parameter
- PhaseCoordinator.\_execute_configuration_steps() parameter
- PhaseCoordinator.\_handle_smart_config_merge() parameter
- PhaseCoordinator.\_update_configuration_files() parameter
- PhaseCoordinator.\_perform_smart_config_merge() parameter
- PhaseCoordinator.run_hooks_phase() parameter
- PhaseCoordinator.run_fast_hooks_only() parameter
- PhaseCoordinator.run_comprehensive_hooks_only() parameter
- PhaseCoordinator.run_testing_phase() parameter
- PhaseCoordinator.run_publishing_phase() parameter
- PhaseCoordinator.\_determine_version_type() parameter
- PhaseCoordinator.\_execute_publishing_workflow() parameter
- PhaseCoordinator.\_handle_successful_publish() parameter
- PhaseCoordinator.run_commit_phase() parameter
- PhaseCoordinator.execute_hooks_with_retry() parameter
- PhaseCoordinator.\_get_commit_message() parameter
- PhaseCoordinator.\_execute_hooks_with_retry() parameter
- PhaseCoordinator.\_process_hook_results() parameter
- PhaseCoordinator.\_handle_hook_failures() parameter
- PhaseCoordinator.\_handle_parallel_hook_failures() parameter
- PhaseCoordinator.\_retry_hooks_after_autofix() parameter
- GlobalLockConfig.from_options() parameter
- HookPluginBase.execute_hook() parameter
- CustomHookPlugin.execute_hook() parameter
- HookPluginRegistry.execute_custom_hook() parameter
- PluginManager.execute_custom_hook() parameter
- TestCommandBuilder.build_command() parameter
- TestCommandBuilder.get_optimal_workers() parameter
- TestCommandBuilder.get_test_timeout() parameter
- TestCommandBuilder.\_add_coverage_options() parameter
- TestCommandBuilder.\_add_worker_options() parameter
- TestCommandBuilder.\_add_benchmark_options() parameter
- TestCommandBuilder.\_add_timeout_options() parameter
- TestCommandBuilder.\_add_verbosity_options() parameter
- TestManagementImpl.\_get_optimal_workers() parameter
- TestManagementImpl.\_get_test_timeout() parameter
- TestManagementImpl.run_tests() parameter
- TestManagementImpl.\_execute_test_workflow() parameter
- TestManagementImpl.\_execute_tests_with_appropriate_mode() parameter
- TestManagementImpl.\_determine_execution_mode() parameter
- TestManagementImpl.\_build_test_command() parameter
- TestManagementImpl.\_add_coverage_options() parameter
- TestManagementImpl.\_add_worker_options() parameter
- TestManagementImpl.\_add_benchmark_options() parameter
- TestManagementImpl.\_add_timeout_options() parameter
- TestManagementImpl.\_add_verbosity_options() parameter
- TestManagementImpl.\_print_test_start_message() parameter
- TestManagementImpl.get_test_command() parameter
- TestManager.run_tests() parameter
- TestManager.get_test_command() parameter
- TestManager.\_execute_test_workflow() parameter
- TestManager.\_print_test_start_message() parameter
- TestManager.\_get_timeout() parameter
- ConfigurationServiceProtocol.update_precommit_config() parameter
- ConfigurationServiceProtocol.update_pyproject_config() parameter
- TestManagerProtocol.run_tests() parameter
- OptionsAdapter.from_options_protocol() parameter
- OptionsAdapter.to_options_protocol() parameter
- LegacyOptionsWrapper.__init__() parameter
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
- ExecutionContext.__init__() parameter
- AdvancedWorkflowOrchestrator.\_configure_verbose_mode() parameter
- TestProgressStreamer.build_pytest_command() parameter
- ConfigurationService.update_precommit_config() parameter
- ConfigurationService.\_determine_config_mode() parameter
- ConfigurationService.update_pyproject_config() parameter
- OptionsConfigSource.__init__() parameter
- UnifiedConfigurationService.__init__() parameter

## OptionsProtocol

**Referenced in:**

- WorkflowPipeline.\_initialize_workflow_session() parameter
- WorkflowPipeline.\_log_workflow_startup_debug() parameter
- WorkflowPipeline.\_configure_session_cleanup() parameter
- WorkflowPipeline.\_log_workflow_startup_info() parameter
- WorkflowPipeline.\_is_publishing_workflow() parameter
- WorkflowPipeline.\_execute_optional_cleaning_phase() parameter
- WorkflowPipeline.\_start_iteration_tracking() parameter
- WorkflowPipeline.\_run_initial_fast_hooks() parameter
- WorkflowPipeline.\_finalize_ai_workflow_success() parameter
- WorkflowPipeline.\_run_fast_hooks_phase() parameter
- WorkflowPipeline.\_run_testing_phase() parameter
- WorkflowPipeline.\_run_comprehensive_hooks_phase() parameter
- WorkflowPipeline.\_run_code_cleaning_phase() parameter
- WorkflowPipeline.\_run_post_cleaning_fast_hooks() parameter
- WorkflowPipeline.\_execute_standard_hooks_workflow() parameter
- WorkflowPipeline.\_initialize_ai_fixing_phase() parameter
- WorkflowPipeline.\_prepare_ai_fixing_environment() parameter
- WorkflowPipeline.\_check_security_gates_for_publishing() parameter
- WorkflowPipeline.\_execute_monitored_fast_hooks_phase() parameter
- WorkflowPipeline.\_execute_monitored_cleaning_phase() parameter
- WorkflowPipeline.\_execute_monitored_comprehensive_phase() parameter
- WorkflowOrchestrator.\_initialize_session_tracking() parameter
- WorkflowOrchestrator.run_cleaning_phase() parameter
- WorkflowOrchestrator.run_fast_hooks_only() parameter
- WorkflowOrchestrator.run_comprehensive_hooks_only() parameter
- WorkflowOrchestrator.run_hooks_phase() parameter
- WorkflowOrchestrator.run_testing_phase() parameter
- WorkflowOrchestrator.run_publishing_phase() parameter
- WorkflowOrchestrator.run_commit_phase() parameter
- WorkflowOrchestrator.run_configuration_phase() parameter
- AsyncWorkflowPipeline.\_create_parallel_tasks() parameter
- AsyncWorkflowOrchestrator.run_complete_workflow() parameter
- AsyncWorkflowOrchestrator.run_cleaning_phase() parameter
- AsyncWorkflowOrchestrator.run_fast_hooks_only() parameter
- AsyncWorkflowOrchestrator.run_comprehensive_hooks_only() parameter
- AsyncWorkflowOrchestrator.run_hooks_phase() parameter
- AsyncWorkflowOrchestrator.run_testing_phase() parameter
- AsyncWorkflowOrchestrator.run_publishing_phase() parameter
- AsyncWorkflowOrchestrator.run_commit_phase() parameter
- AsyncWorkflowOrchestrator.run_configuration_phase() parameter
- SessionCoordinator.initialize_session_tracking() parameter
- PhaseCoordinator.run_cleaning_phase() parameter
- PhaseCoordinator.run_configuration_phase() parameter
- PhaseCoordinator.\_execute_configuration_steps() parameter
- PhaseCoordinator.\_handle_smart_config_merge() parameter
- PhaseCoordinator.\_update_configuration_files() parameter
- PhaseCoordinator.\_perform_smart_config_merge() parameter
- PhaseCoordinator.run_hooks_phase() parameter
- PhaseCoordinator.run_fast_hooks_only() parameter
- PhaseCoordinator.run_comprehensive_hooks_only() parameter
- PhaseCoordinator.run_testing_phase() parameter
- PhaseCoordinator.run_publishing_phase() parameter
- PhaseCoordinator.\_determine_version_type() parameter
- PhaseCoordinator.\_execute_publishing_workflow() parameter
- PhaseCoordinator.\_handle_successful_publish() parameter
- PhaseCoordinator.run_commit_phase() parameter
- PhaseCoordinator.execute_hooks_with_retry() parameter
- PhaseCoordinator.\_get_commit_message() parameter
- PhaseCoordinator.\_execute_hooks_with_retry() parameter
- PhaseCoordinator.\_process_hook_results() parameter
- PhaseCoordinator.\_handle_hook_failures() parameter
- PhaseCoordinator.\_handle_parallel_hook_failures() parameter
- PhaseCoordinator.\_retry_hooks_after_autofix() parameter
- GlobalLockConfig.from_options() parameter
- HookPluginBase.execute_hook() parameter
- CustomHookPlugin.execute_hook() parameter
- HookPluginRegistry.execute_custom_hook() parameter
- PluginManager.execute_custom_hook() parameter
- TestCommandBuilder.build_command() parameter
- TestCommandBuilder.get_optimal_workers() parameter
- TestCommandBuilder.get_test_timeout() parameter
- TestCommandBuilder.\_add_coverage_options() parameter
- TestCommandBuilder.\_add_worker_options() parameter
- TestCommandBuilder.\_add_benchmark_options() parameter
- TestCommandBuilder.\_add_timeout_options() parameter
- TestCommandBuilder.\_add_verbosity_options() parameter
- TestManagementImpl.\_get_optimal_workers() parameter
- TestManagementImpl.\_get_test_timeout() parameter
- TestManagementImpl.run_tests() parameter
- TestManagementImpl.\_execute_test_workflow() parameter
- TestManagementImpl.\_execute_tests_with_appropriate_mode() parameter
- TestManagementImpl.\_determine_execution_mode() parameter
- TestManagementImpl.\_build_test_command() parameter
- TestManagementImpl.\_add_coverage_options() parameter
- TestManagementImpl.\_add_worker_options() parameter
- TestManagementImpl.\_add_benchmark_options() parameter
- TestManagementImpl.\_add_timeout_options() parameter
- TestManagementImpl.\_add_verbosity_options() parameter
- TestManagementImpl.\_print_test_start_message() parameter
- TestManagementImpl.get_test_command() parameter
- TestManager.run_tests() parameter
- TestManager.get_test_command() parameter
- TestManager.\_execute_test_workflow() parameter
- TestManager.\_print_test_start_message() parameter
- TestManager.\_get_timeout() parameter
- ConfigurationServiceProtocol.update_precommit_config() parameter
- ConfigurationServiceProtocol.update_pyproject_config() parameter
- TestManagerProtocol.run_tests() parameter
- OptionsAdapter.from_options_protocol() parameter
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
- ExecutionContext.__init__() parameter
- AdvancedWorkflowOrchestrator.\_configure_verbose_mode() parameter
- TestProgressStreamer.build_pytest_command() parameter
- ConfigurationService.update_precommit_config() parameter
- ConfigurationService.\_determine_config_mode() parameter
- ConfigurationService.update_pyproject_config() parameter
- OptionsConfigSource.__init__() parameter
- UnifiedConfigurationService.__init__() parameter

## OrchestrationConfig

**Referenced in:**

- StrategySelector.select_strategy() parameter
- OrchestrationPlanner.create_execution_plan() parameter
- OrchestrationPlanner.\_create_test_plan() parameter
- OrchestrationPlanner.\_create_ai_plan() parameter
- ProgressStreamer.__init__() parameter
- AdvancedWorkflowOrchestrator.__init__() parameter

## PackageCleaningResult

**Referenced in:**

- CrackerjackAPI.\_report_safe_cleaning_results() parameter
- PhaseCoordinator.\_report_package_cleaning_results() parameter

## PatternCache

**Referenced in:**

- PatternDetector.__init__() parameter

## PerformanceCache

**Referenced in:**

- GitOperationCache.__init__() parameter
- FileSystemCache.__init__() parameter
- CommandResultCache.__init__() parameter

## PerformanceMetric

**Referenced in:**

- AdaptiveLearningSystem.\_update_basic_counters() parameter
- AdaptiveLearningSystem.\_update_execution_averages() parameter
- AdaptiveLearningSystem.\_update_capability_success_rates() parameter
- AdaptiveLearningSystem.\_update_performance_trend() parameter
- AdaptiveLearningSystem.\_calculate_metrics_score() parameter

## PhaseCoordinator

**Referenced in:**

- WorkflowPipeline.__init__() parameter
- AsyncWorkflowPipeline.__init__() parameter

## PhasePerformance

**Referenced in:**

- WorkflowPerformance.add_phase() parameter

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

## PluginType

**Referenced in:**

- PluginRegistry.get_by_type() parameter
- PluginRegistry.get_enabled() parameter
- PluginManager.list_plugins() parameter

## Priority

**Referenced in:**

- AsyncWorkflowPipeline.\_create_generic_issue() parameter
- StateManager.get_issues_by_priority() parameter

## ProactiveAgent

**Referenced in:**

- ArchitectAgent base class

## ProjectContext

**Referenced in:**

- ContextualAIAssistant.\_generate_recommendations() parameter
- ContextualAIAssistant.\_get_testing_recommendations() parameter
- ContextualAIAssistant.\_get_code_quality_recommendations() parameter
- ContextualAIAssistant.\_get_security_recommendations() parameter
- ContextualAIAssistant.\_get_maintenance_recommendations() parameter
- ContextualAIAssistant.\_get_workflow_recommendations() parameter
- ContextualAIAssistant.\_get_documentation_recommendations() parameter

## ProjectHealth

**Referenced in:**

- HealthMetricsService.\_save_health_metrics() parameter
- HealthMetricsService.report_health_status() parameter
- HealthMetricsService.\_print_health_metrics() parameter
- HealthMetricsService.\_print_health_recommendations() parameter
- HealthMetricsService.\_get_lint_errors_metrics() parameter
- HealthMetricsService.\_get_test_coverage_metrics() parameter
- HealthMetricsService.\_get_dependency_age_metrics() parameter
- HealthMetricsService.\_get_trend_direction() parameter
- HealthMetricsService.\_get_coverage_trend_direction() parameter

## PublishManager

**Referenced in:**

- PhaseCoordinator.__init__() parameter

## QualityAlert

**Referenced in:**

- EnhancedQualityBaselineService.generate_recommendations() parameter

## QualityBaselineService

**Referenced in:**

- EnhancedQualityBaselineService base class

## QualityMetrics

**Referenced in:**

- QualityBaselineService.\_identify_improvements() parameter
- QualityBaselineService.\_identify_regressions() parameter

## QualityReport

**Referenced in:**

- EnhancedQualityBaselineService.export_report() parameter

## QualityTrend

**Referenced in:**

- EnhancedQualityBaselineService.generate_recommendations() parameter

## RateLimitConfig

**Referenced in:**

- ResourceMonitor.__init__() parameter
- RateLimitMiddleware.__init__() parameter

## RegisteredAgent

**Referenced in:**

- AgentSelector.\_calculate_context_score() parameter
- AgentSelector.\_score_description_matches() parameter
- AgentSelector.\_score_keyword_matches() parameter
- AgentSelector.\_generate_score_reasoning() parameter
- AgentOrchestrator.\_build_consensus() parameter

## RegressionAlert

**Referenced in:**

- RegressionPreventionSystem.\_log_critical_regression() parameter

## RegressionPattern

**Referenced in:**

- RegressionPreventionSystem.\_check_pattern_match() parameter
- RegressionPreventionSystem.\_check_agent_specific_failure() parameter
- RegressionPreventionSystem.\_create_regression_alert() parameter
- RegressionPreventionSystem.\_simulate_regression_test() parameter

## ResourceLimits

**Referenced in:**

- WebSocketResourceLimiter.__init__() parameter

## ResourceManager

**Referenced in:**

- ManagedWebSocketConnection.__init__() parameter
- ManagedHTTPClient.__init__() parameter
- ManagedWebSocketServer.__init__() parameter
- ManagedSubprocess.__init__() parameter
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

## ResourcePool

**Referenced in:**

- MemoryOptimizer.register_resource_pool() parameter

## ResourceProtocol

**Referenced in:**

- ResourceManager.register_resource() parameter

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

## SecurityServiceProtocol

**Referenced in:**

- PublishManagerImpl.__init__() parameter

## ServiceConfig

**Referenced in:**

- ServiceWatchdog.add_service() parameter
- ServiceWatchdog.__init__() parameter
- ServiceWatchdog.\_determine_restart_reason() parameter
- ServiceWatchdog.\_get_service_status() parameter
- ServiceWatchdog.\_get_service_health() parameter

## ServiceDescriptor

**Referenced in:**

- DependencyResolver.create_instance() parameter
- EnhancedDependencyContainer.\_create_service_instance() parameter
- EnhancedDependencyContainer.\_get_or_create_singleton() parameter
- EnhancedDependencyContainer.\_get_or_create_scoped() parameter
- EnhancedDependencyContainer.\_create_transient_instance() parameter

## ServiceScope

**Referenced in:**

- DependencyResolver.create_instance() parameter
- EnhancedDependencyContainer.get() parameter
- EnhancedDependencyContainer.set_current_scope() parameter
- EnhancedDependencyContainer.\_create_service_instance() parameter
- EnhancedDependencyContainer.\_get_or_create_scoped() parameter

## ServiceStatus

**Referenced in:**

- ServiceWatchdog.\_prepare_service_startup() parameter
- ServiceWatchdog.\_finalize_successful_startup() parameter
- ServiceWatchdog.\_handle_service_start_failure() parameter

## SessionCoordinator

**Referenced in:**

- WorkflowPipeline.__init__() parameter
- AsyncWorkflowPipeline.__init__() parameter
- PhaseCoordinator.__init__() parameter
- ProgressStreamer.__init__() parameter
- AdvancedWorkflowOrchestrator.__init__() parameter

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

## SubAgent

**Referenced in:**

- AgentRegistry.\_infer_capabilities_from_agent() parameter
- AgentCoordinator.\_is_built_in_agent() parameter
- RefactoringAgent base class
- ProactiveAgent base class
- PerformanceAgent base class
- DocumentationAgent base class
- DRYAgent base class
- TestSpecialistAgent base class
- SecurityAgent base class
- FormattingAgent base class
- TestCreationAgent base class
- ImportOptimizationAgent base class
- AgentRegistry.register() parameter

## SubprocessSecurityConfig

**Referenced in:**

- SecureSubprocessExecutor.__init__() parameter

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
- AgentSelector.\_analyze_task_capabilities() parameter
- AgentSelector.\_analyze_text_patterns() parameter
- AgentSelector.\_analyze_context() parameter
- AgentSelector.\_analyze_file_patterns() parameter
- AgentSelector.\_analyze_error_types() parameter
- AgentSelector.\_calculate_context_score() parameter
- AgentSelector.\_score_keyword_matches() parameter
- AdaptiveLearningSystem.\_infer_task_capabilities() parameter
- AdaptiveLearningSystem.\_hash_task() parameter
- AdaptiveLearningSystem.get_agent_recommendations() parameter
- AgentOrchestrator.\_map_task_to_issue_type() parameter
- AgentOrchestrator.\_map_task_priority_to_severity() parameter
- AbstractTaskResource.__init__() parameter
- InteractiveTask.__init__() parameter
- InteractiveWorkflowManager.execute_task() parameter
- InteractiveWorkflowManager.\_handle_task_failure() parameter
- IndividualHookExecutor.\_handle_process_timeout() parameter

## TaskDefinition

**Referenced in:**

- Task.__init__() parameter
- WorkflowManager.load_workflow() parameter

## TaskDescription

**Referenced in:**

- AgentSelector.\_analyze_task_capabilities() parameter
- AgentSelector.\_analyze_text_patterns() parameter
- AgentSelector.\_analyze_context() parameter
- AgentSelector.\_analyze_file_patterns() parameter
- AgentSelector.\_analyze_error_types() parameter
- AgentSelector.\_calculate_context_score() parameter
- AgentSelector.\_score_keyword_matches() parameter
- AdaptiveLearningSystem.\_infer_task_capabilities() parameter
- AdaptiveLearningSystem.\_hash_task() parameter
- AdaptiveLearningSystem.get_agent_recommendations() parameter
- AgentOrchestrator.\_map_task_to_issue_type() parameter
- AgentOrchestrator.\_map_task_priority_to_severity() parameter

## TaskExecutor

**Referenced in:**

- Task.__init__() parameter
- WorkflowManager.set_task_executor() parameter

## TaskStatus

**Referenced in:**

- WorkflowManager.\_add_status_branch() parameter

## TestManager

**Referenced in:**

- PhaseCoordinator.__init__() parameter

## TestManagerProtocol

**Referenced in:**

- PhaseCoordinator.__init__() parameter

## TestProgress

**Referenced in:**

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
- TestExecutor.\_emit_ai_progress() parameter
- TestManagementImpl.\_start_reader_threads() parameter
- TestManagementImpl.\_create_stdout_reader() parameter
- TestManagementImpl.\_process_test_output_line() parameter
- TestManagementImpl.\_update_display_if_needed() parameter
- TestManagementImpl.\_get_refresh_interval() parameter
- TestManagementImpl.\_get_current_content_signature() parameter
- TestManagementImpl.\_create_monitor_thread() parameter
- TestManagementImpl.\_mark_test_as_stuck() parameter
- TestManagementImpl.\_wait_for_completion() parameter
- TestManagementImpl.\_cleanup_threads() parameter
- TestManagementImpl.\_parse_test_line() parameter
- TestManagementImpl.\_handle_collection_completion() parameter
- TestManagementImpl.\_handle_session_events() parameter
- TestManagementImpl.\_handle_collection_progress() parameter
- TestManagementImpl.\_handle_test_execution() parameter
- TestManagementImpl.\_handle_running_test() parameter
- TestManagementImpl.\_extract_current_test() parameter
- TestManagementImpl.\_execute_test_process_with_progress() parameter
- TestManagementImpl.\_read_stdout_with_progress() parameter
- TestManagementImpl.\_emit_ai_progress() parameter
- PytestOutputParser.\_process_test_result_line() parameter
- PytestOutputParser.\_update_test_progress() parameter
- TestProgressStreamer.set_test_callback() parameter
- TestProgressStreamer.\_attach_failure_details() parameter
- TestProgressStreamer.\_print_test_summary() parameter
- TestProgressStreamer.\_print_failed_test_details() parameter

## TestSuiteProgress

**Referenced in:**

- AdvancedWorkflowOrchestrator.\_update_test_suite_progress() parameter
- PytestOutputParser.\_process_test_collection_line() parameter
- PytestOutputParser.\_process_test_result_line() parameter
- PytestOutputParser.\_update_suite_counts() parameter
- PytestOutputParser.\_process_coverage_line() parameter
- PytestOutputParser.\_process_current_test_line() parameter
- TestProgressStreamer.set_progress_callback() parameter
- TestProgressStreamer.\_finalize_suite_progress() parameter
- TestProgressStreamer.\_build_success_result() parameter
- TestProgressStreamer.\_handle_test_execution_error() parameter
- TestProgressStreamer.\_handle_line_output() parameter
- TestProgressStreamer.\_parse_line_for_progress() parameter
- TestProgressStreamer.\_print_test_summary() parameter
- TestProgressStreamer.\_print_test_counts() parameter
- TestProgressStreamer.\_print_timing_stats() parameter
- TestProgressStreamer.\_print_coverage_stats() parameter

## TimeoutConfig

**Referenced in:**

- AsyncTimeoutManager.__init__() parameter

## ToolResult

**Referenced in:**

- RustToolHookManager.create_consolidated_report() parameter

## UsageDataCollector

**Referenced in:**

- RefactoringAgent.\_create_enhanced_usage_analyzer() parameter
- EnhancedUsageAnalyzer.__init__() parameter

## ValidationConfig

**Referenced in:**

- SecureInputValidator.__init__() parameter

## WebSocketServer

**Referenced in:**

- WebSocketHealthMonitor.add_server() parameter
- WebSocketHealthMonitor.remove_server() parameter

## WorkflowBuilder

**Referenced in:**

- InteractiveCLI.\_add_setup_phase() parameter
- InteractiveCLI.\_add_config_phase() parameter
- InteractiveCLI.\_add_cleaning_phase() parameter
- InteractiveCLI.\_add_fast_hooks_phase() parameter
- InteractiveCLI.\_add_testing_phase() parameter
- InteractiveCLI.\_add_comprehensive_hooks_phase() parameter
- InteractiveCLI.\_add_version_phase() parameter
- InteractiveCLI.\_add_publish_phase() parameter
- InteractiveCLI.\_add_commit_phase() parameter
- InteractiveCLI.\_add_pr_phase() parameter

## WorkflowOptions

**Referenced in:**

- CrackerjackAPI.run_interactive_workflow() parameter
- InteractiveCLI.create_dynamic_workflow() parameter
- InteractiveCLI.run_interactive_workflow() parameter
- OptionsAdapter.to_options_protocol() parameter
- LegacyOptionsWrapper.__init__() parameter

## WorkflowOrchestrator

**Referenced in:**

- InteractiveWorkflowManager.__init__() parameter

## WorkflowPerformance

**Referenced in:**

- PerformanceMonitor.\_calculate_basic_workflow_stats() parameter
- PerformanceMonitor.\_calculate_cache_statistics() parameter
- PerformanceMonitor.\_calculate_parallelization_statistics() parameter
- PerformanceMonitor.\_check_performance_warnings() parameter
- PerformanceMonitor.\_check_duration_warning() parameter
- PerformanceMonitor.\_check_memory_warning() parameter
- PerformanceMonitor.\_check_cache_warning() parameter

## all

**Referenced in:**

- \_DocstringFinder.__init__() parameter
- RegexVisitor.visit_Call() parameter
- WorkflowOrchestrator.\_register_cleanup() parameter
- AsyncWorkflowOrchestrator.\_register_cleanup() parameter
- ResourceManager.register_cleanup_callback() parameter
- DependencyResolver.\_create_from_factory() parameter
- EnhancedDependencyContainer.register_singleton() parameter
- EnhancedDependencyContainer.register_transient() parameter
- EnhancedDependencyContainer.register_scoped() parameter
- SessionCoordinator.register_cleanup() parameter
- DependencyContainer.register_transient() parameter
- PhaseCoordinator.execute_hooks_with_retry() parameter
- PhaseCoordinator.\_execute_hooks_with_retry() parameter
- PhaseCoordinator.\_execute_single_hook_attempt() parameter
- PhaseCoordinator.\_handle_parallel_hook_failures() parameter
- PhaseCoordinator.\_retry_hooks_after_autofix() parameter
- ParallelTaskExecutor.execute_tasks() parameter
- PluginLoader.\_try_factory_function() parameter
- TestExecutor.execute_with_ai_progress() parameter
- TestExecutor.\_run_test_command_with_ai_progress() parameter
- TestExecutor.\_execute_test_process_with_progress() parameter
- TestExecutor.\_read_stdout_with_progress() parameter
- TestExecutor.\_emit_ai_progress() parameter
- TestManagementImpl.set_progress_callback() parameter
- TestManager.set_progress_callback() parameter
- ComplexityAnalyzer.__init__() parameter
- BuiltinAnalyzer.visit_Call() parameter
- EnhancedUsageAnalyzer.visit_Call() parameter
- EnhancedUsageAnalyzer.\_process_function_call() parameter
- AsyncProgressMonitor.subscribe() parameter
- AsyncProgressMonitor.unsubscribe() parameter
- PollingProgressMonitor.subscribe() parameter
- PollingProgressMonitor.unsubscribe() parameter
- ProgressFileHandler.__init__() parameter
- ProgressFileHandler.__init__() parameter
- MCPServerContext.add_startup_task() parameter
- MCPServerContext.add_shutdown_task() parameter
- ResourceManagerProtocol.register_cleanup_callback() parameter
- IndividualHookExecutor.set_progress_callback() parameter
- TestProgressStreamer.set_progress_callback() parameter
- TestProgressStreamer.set_test_callback() parameter
- SecureSubprocessExecutor.\_handle_process_error() parameter
- SecurityVisitor.visit_Call() parameter
- LazyLoader.__init__() parameter
- ResourcePool.__init__() parameter
- DependencyMonitorService.\_run_vulnerability_tool() parameter
- DependencyMonitorService.\_process_vulnerability_result() parameter

## log

**Referenced in:**

- ResourceManager.__init__() parameter
- ChangelogGenerator.update_changelog() parameter
- ChangelogGenerator.\_generate_changelog_section() parameter
- ChangelogGenerator.\_display_changelog_preview() parameter
- LogManager.setup_rotating_file_handler() parameter

## read

**Referenced in:**

- TestExecutor.\_cleanup_threads() parameter
- TestManagementImpl.\_cleanup_threads() parameter

## set

**Referenced in:**

- CrackerjackAPI.\_should_skip_file() parameter
- Task.can_run() parameter
- CodeCleaner.\_should_include_file_path() parameter
- AutofixCoordinator.\_get_hook_specific_fixes() parameter
- AgentSelector.\_generate_score_reasoning() parameter
- AgentSelector.\_assess_complexity() parameter
- AgentSelector.\_generate_recommendations() parameter
- ImportOptimizationAgent.\_check_redundant_imports() parameter
- ImportOptimizationAgent.\_remove_old_mixed_imports() parameter
- CrackerjackDashboard.\_remove_obsolete_panels() parameter
- GitService.\_generate_category_messages() parameter
- ConfigMergeService.\_get_consolidated_patterns() parameter
- SubprocessSecurityConfig.__init__() parameter
- SubprocessSecurityConfig.__init__() parameter
- StatusAuthenticator.add_api_key() parameter
- StatusSecurityManager.__init__() parameter
- PerformanceCache.set() parameter
- JobManager.\_create_broadcast_tasks() parameter
