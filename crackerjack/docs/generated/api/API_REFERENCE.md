# API Reference

## Overview

This document provides comprehensive API reference for all protocols, services, and managers in the codebase.
**Total Protocols:** 0
**Total Classes:** 504
**Total Functions:** 3551
**Total Modules:** 191

## Protocols

No protocols found.

## Services

## quality_baseline

**Path:** `crackerjack/services/quality_baseline.py`

## QualityMetrics

Quality metrics for a specific commit/session.

**Base Classes:** None

### Methods

#### `to_dict`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `from_dict`

**Parameters:**

- `cls` ():
- `data` (dict[(str, t.Any)]):
  **Returns:** QualityMetrics

## QualityBaselineService

Service for tracking and persisting quality baselines across sessions.

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache` (CrackerjackCache | None):
  **Returns:** None

#### `get_current_git_hash`

Get current git commit hash.
**Parameters:**

- `self` ():
  **Returns:** str | None

#### `calculate_quality_score`

Calculate overall quality score (0-100).
**Parameters:**

- `self` ():
- `coverage_percent` (float):
- `test_pass_rate` (float):
- `hook_failures` (int):
- `complexity_violations` (int):
- `security_issues` (int):
- `type_errors` (int):
- `linting_issues` (int):
  **Returns:** int

#### `record_baseline`

Record quality baseline for current commit.
**Parameters:**

- `self` ():
- `coverage_percent` (float):
- `test_count` (int):
- `test_pass_rate` (float):
- `hook_failures` (int):
- `complexity_violations` (int):
- `security_issues` (int):
- `type_errors` (int):
- `linting_issues` (int):
  **Returns:** QualityMetrics | None

#### `get_baseline`

Get quality baseline for specific commit (or current commit).
**Parameters:**

- `self` ():
- `git_hash` (str | None):
  **Returns:** QualityMetrics | None

#### `compare_with_baseline`

Compare current metrics with baseline.
**Parameters:**

- `self` ():
- `current_metrics` (dict[(str, t.Any)]):
- `baseline_git_hash` (str | None):
  **Returns:** dict[(str, t.Any)]

#### `_identify_improvements`

Identify areas that improved since baseline.
**Parameters:**

- `self` ():
- `baseline` (QualityMetrics):
- `current` (dict[(str, t.Any)]):
  **Returns:** list[str]

#### `_identify_regressions`

Identify areas that regressed since baseline.
**Parameters:**

- `self` ():
- `baseline` (QualityMetrics):
- `current` (dict[(str, t.Any)]):
  **Returns:** list[str]

#### `get_recent_baselines`

Get recent baselines (requires git log parsing since cache is keyed by hash).
**Parameters:**

- `self` ():
- `limit` (int):
  **Returns:** list[QualityMetrics]

## validation_rate_limiter

**Path:** `crackerjack/services/validation_rate_limiter.py`

## ValidationRateLimit

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `max_failures` (int):
- `window_seconds` (int):
- `block_duration` (int):

## ValidationRateLimiter

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():

#### `is_blocked`

**Parameters:**

- `self` ():
- `client_id` (str):
  **Returns:** bool

#### `record_failure`

**Parameters:**

- `self` ():
- `client_id` (str):
- `validation_type` (str):
- `severity` (SecurityEventLevel):
  **Returns:** bool

#### `get_remaining_attempts`

**Parameters:**

- `self` ():
- `client_id` (str):
- `validation_type` (str):
  **Returns:** int

#### `get_block_time_remaining`

**Parameters:**

- `self` ():
- `client_id` (str):
  **Returns:** int

#### `get_client_stats`

**Parameters:**

- `self` ():
- `client_id` (str):
  **Returns:** dict[(str, t.Any)]

#### `cleanup_expired_data`

**Parameters:**

- `self` ():
  **Returns:** int

#### `update_rate_limits`

**Parameters:**

- `self` ():
- `validation_type` (str):
- `max_failures` (int):
- `window_seconds` (int):
- `block_duration` (int):
  **Returns:** None

#### `get_all_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## logging

**Path:** `crackerjack/services/logging.py`

## LoggingContext

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `operation` (str):
  **Returns:** None

#### `__enter__`

**Parameters:**

- `self` ():
  **Returns:** str

#### `__exit__`

**Parameters:**

- `self` ():
- `exc_type` (type[BaseException] | None):
- `exc_val` (BaseException | None):
- `_` (TracebackType | None):
  **Returns:** None

## metrics

**Path:** `crackerjack/services/metrics.py`

## MetricsCollector

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `db_path` (Path | None):
  **Returns:** None

#### `_init_database`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_get_connection`

**Parameters:**

- `self` ():

#### `start_job`

**Parameters:**

- `self` ():
- `job_id` (str):
- `ai_agent` (bool):
- `metadata` (dict[(str, Any)] | None):
  **Returns:** None

#### `end_job`

**Parameters:**

- `self` ():
- `job_id` (str):
- `status` (str):
- `iterations` (int):
- `error_message` (str | None):
  **Returns:** None

#### `record_error`

**Parameters:**

- `self` ():
- `job_id` (str):
- `error_type` (str):
- `error_category` (str):
- `error_message` (str):
- `file_path` (str | None):
- `line_number` (int | None):
  **Returns:** None

#### `record_hook_execution`

**Parameters:**

- `self` ():
- `job_id` (str):
- `hook_name` (str):
- `hook_type` (str):
- `execution_time_ms` (int):
- `status` (str):
  **Returns:** None

#### `record_test_execution`

**Parameters:**

- `self` ():
- `job_id` (str):
- `total_tests` (int):
- `passed` (int):
- `failed` (int):
- `skipped` (int):
- `execution_time_ms` (int):
- `coverage_percent` (float | None):
  **Returns:** None

#### `record_orchestration_execution`

**Parameters:**

- `self` ():
- `job_id` (str):
- `execution_strategy` (str):
- `progress_level` (str):
- `ai_mode` (str):
- `iteration_count` (int):
- `strategy_switches` (int):
- `correlation_insights` (dict[(str, Any)]):
- `total_execution_time_ms` (int):
- `hooks_execution_time_ms` (int):
- `tests_execution_time_ms` (int):
- `ai_analysis_time_ms` (int):
  **Returns:** None

#### `record_strategy_decision`

**Parameters:**

- `self` ():
- `job_id` (str):
- `iteration` (int):
- `previous_strategy` (str | None):
- `selected_strategy` (str):
- `decision_reason` (str):
- `context_data` (dict[(str, Any)]):
- `effectiveness_score` (float | None):
  **Returns:** None

#### `record_individual_test`

**Parameters:**

- `self` ():
- `job_id` (str):
- `test_id` (str):
- `test_file` (str):
- `test_class` (str | None):
- `test_method` (str | None):
- `status` (str):
- `execution_time_ms` (int | None):
- `error_message` (str | None):
- `error_traceback` (str | None):
  **Returns:** None

#### `get_orchestration_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

#### `_update_daily_summary`

**Parameters:**

- `self` ():
- `conn` (sqlite3.Connection):
- `date` (date):
  **Returns:** None

#### `get_all_time_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

## documentation_generator

**Path:** `crackerjack/services/documentation_generator.py`

**Implements Protocols:**

- DocumentationGeneratorProtocol

## MarkdownTemplateRenderer

Simple template renderer for markdown documentation.

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_init_builtin_templates`

Initialize built-in template strings.
**Parameters:**

- `self` ():
  **Returns:** dict[(str, Template)]

#### `render_template`

Render a template with the given context.
**Parameters:**

- `self` ():
- `template_name` (str):
- `context` (dict[(str, t.Any)]):
  **Returns:** str

#### `_get_api_reference_template`

Get the API reference template.
**Parameters:**

- `self` ():
  **Returns:** str

#### `_get_function_doc_template`

Get the function documentation template.
**Parameters:**

- `self` ():
  **Returns:** str

#### `_get_class_doc_template`

Get the class documentation template.
**Parameters:**

- `self` ():
  **Returns:** str

#### `_get_protocol_doc_template`

Get the protocol documentation template.
**Parameters:**

- `self` ():
  **Returns:** str

#### `_get_module_doc_template`

Get the module documentation template.
**Parameters:**

- `self` ():
  **Returns:** str

## DocumentationGeneratorImpl

Implementation of documentation generation from extracted API data.

**Base Classes:** DocumentationGeneratorProtocol

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
  **Returns:** None

#### `generate_api_reference`

Generate complete API reference documentation.
**Parameters:**

- `self` ():
- `api_data` (dict[(str, t.Any)]):
  **Returns:** str

#### `generate_user_guide`

Generate user guide documentation.
**Parameters:**

- `self` ():
- `template_context` (dict[(str, t.Any)]):
  **Returns:** str

#### `generate_changelog_update`

Generate changelog entry for a version.
**Parameters:**

- `self` ():
- `version` (str):
- `changes` (dict[(str, t.Any)]):
  **Returns:** str

#### `render_template`

Render a template file with the given context.
**Parameters:**

- `self` ():
- `template_path` (Path):
- `context` (dict[(str, t.Any)]):
  **Returns:** str

#### `generate_cross_references`

Generate cross-reference mappings for API components.
**Parameters:**

- `self` ():
- `api_data` (dict[(str, t.Any)]):
  **Returns:** dict\[(str, list[str])\]

#### `_generate_overview`

Generate overview section for API documentation.
**Parameters:**

- `self` ():
- `api_data` (dict[(str, t.Any)]):
  **Returns:** str

#### `_generate_protocols_section`

Generate the protocols section of API documentation.
**Parameters:**

- `self` ():
- `protocols` (dict[(str, t.Any)]):
  **Returns:** str

#### `_generate_services_section`

Generate the services section of API documentation.
**Parameters:**

- `self` ():
- `services` (dict[(str, t.Any)]):
  **Returns:** str

#### `_generate_managers_section`

Generate the managers section of API documentation.
**Parameters:**

- `self` ():
- `managers` (dict[(str, t.Any)]):
  **Returns:** str

#### `_format_methods`

Format method information for documentation.
**Parameters:**

- `self` ():
- `methods` (list\[dict[(str, t.Any)]\]):
  **Returns:** str

#### `_calculate_api_stats`

Calculate statistics about the API data.
**Parameters:**

- `self` ():
- `api_data` (dict[(str, t.Any)]):
  **Returns:** dict[(str, int)]

#### `_find_references_to_name`

Find all places where an API component is referenced.
**Parameters:**

- `self` ():
- `name` (str):
- `api_data` (dict[(str, t.Any)]):
  **Returns:** list[str]

## file_hasher

**Path:** `crackerjack/services/file_hasher.py`

## FileHasher

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache` (CrackerjackCache | None):
  **Returns:** None

#### `get_file_hash`

**Parameters:**

- `self` ():
- `file_path` (Path):
- `algorithm` (str):
  **Returns:** str

#### `get_directory_hash`

**Parameters:**

- `self` ():
- `directory` (Path):
- `patterns` (list[str] | None):
  **Returns:** str

#### `get_files_hash_list`

**Parameters:**

- `self` ():
- `files` (list[Path]):
  **Returns:** list[str]

#### `has_files_changed`

**Parameters:**

- `self` ():
- `files` (list[Path]):
- `cached_hashes` (list[str]):
  **Returns:** bool

#### `_compute_file_hash`

**Parameters:**

- `self` ():
- `file_path` (Path):
- `algorithm` (str):
  **Returns:** str

#### `get_project_files_hash`

**Parameters:**

- `self` ():
- `project_path` (Path):
  **Returns:** dict[(str, str)]

#### `_should_ignore_file`

**Parameters:**

- `self` ():
- `file_path` (Path):
  **Returns:** bool

#### `invalidate_cache`

**Parameters:**

- `self` ():
- `file_path` (Path | None):
  **Returns:** None

## SmartFileWatcher

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `file_hasher` (FileHasher):
  **Returns:** None

#### `register_files`

**Parameters:**

- `self` ():
- `files` (list[Path]):
  **Returns:** None

#### `check_changes`

**Parameters:**

- `self` ():
  **Returns:** list[Path]

#### `invalidate_changed_files`

**Parameters:**

- `self` ():
  **Returns:** int

## git

**Path:** `crackerjack/services/git.py`

## FailedGitResult

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `error` (str):
  **Returns:** None

## GitService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path | None):
  **Returns:** None

#### `_run_git_command`

**Parameters:**

- `self` ():
- `args` (list[str]):
  **Returns:** subprocess.CompletedProcess[str] | FailedGitResult

#### `is_git_repo`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `get_changed_files`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `get_staged_files`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `add_files`

**Parameters:**

- `self` ():
- `files` (list[str]):
  **Returns:** bool

#### `add_all_files`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `commit`

**Parameters:**

- `self` ():
- `message` (str):
  **Returns:** bool

#### `_handle_commit_failure`

**Parameters:**

- `self` ():
- `result` (subprocess.CompletedProcess[str] | FailedGitResult):
- `message` (str):
  **Returns:** bool

#### `_retry_commit_after_restage`

**Parameters:**

- `self` ():
- `message` (str):
  **Returns:** bool

#### `_handle_hook_error`

**Parameters:**

- `self` ():
- `result` (subprocess.CompletedProcess[str] | FailedGitResult):
  **Returns:** bool

#### `push`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_display_push_success`

**Parameters:**

- `self` ():
- `push_output` (str):
  **Returns:** None

#### `_display_no_commits_message`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_parse_pushed_refs`

**Parameters:**

- `self` ():
- `lines` (list[str]):
  **Returns:** list[str]

#### `_display_push_results`

**Parameters:**

- `self` ():
- `pushed_refs` (list[str]):
  **Returns:** None

#### `_display_commit_count_push`

**Parameters:**

- `self` ():
  **Returns:** None

#### `get_current_branch`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `get_commit_message_suggestions`

**Parameters:**

- `self` ():
- `changed_files` (list[str]):
  **Returns:** list[str]

#### `_categorize_files`

**Parameters:**

- `self` ():
- `files` (list[str]):
  **Returns:** set[str]

#### `_get_file_category`

**Parameters:**

- `self` ():
- `file` (str):
- `categories` (dict\[(str, list[str])\]):
  **Returns:** str

#### `_generate_category_messages`

**Parameters:**

- `self` ():
- `file_categories` (set[str]):
  **Returns:** list[str]

#### `_generate_single_category_message`

**Parameters:**

- `self` ():
- `category` (str):
  **Returns:** list[str]

#### `_generate_specific_messages`

**Parameters:**

- `self` ():
- `files` (list[str]):
  **Returns:** list[str]

#### `get_unpushed_commit_count`

**Parameters:**

- `self` ():
  **Returns:** int

## enhanced_filesystem

**Path:** `crackerjack/services/enhanced_filesystem.py`

## FileCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `max_size` (int):
- `default_ttl` (float):
  **Returns:** None

#### `get`

**Parameters:**

- `self` ():
- `key` (str):
  **Returns:** str | None

#### `put`

**Parameters:**

- `self` ():
- `key` (str):
- `content` (str):
- `ttl` (float | None):
  **Returns:** None

#### `_evict`

**Parameters:**

- `self` ():
- `key` (str):
  **Returns:** None

#### `_evict_lru`

**Parameters:**

- `self` ():
  **Returns:** None

#### `clear`

**Parameters:**

- `self` ():
  **Returns:** None

#### `get_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

## BatchFileOperations

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `batch_size` (int):
  **Returns:** None

## EnhancedFileSystemService

**Base Classes:** FileSystemInterface

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache_size` (int):
- `cache_ttl` (float):
- `batch_size` (int):
- `enable_async` (bool):
  **Returns:** None

#### `read_file`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** str

#### `write_file`

**Parameters:**

- `self` ():
- `path` (str | Path):
- `content` (str):
  **Returns:** None

#### `_get_cache_key`

**Parameters:**

- `path` (Path):
  **Returns:** str

#### `_get_from_cache`

**Parameters:**

- `self` ():
- `cache_key` (str):
- `path` (Path):
  **Returns:** str | None

#### `_read_file_direct`

**Parameters:**

- `path` (Path):
  **Returns:** str

#### `_write_file_direct`

**Parameters:**

- `path` (Path):
- `content` (str):
  **Returns:** None

#### `file_exists`

**Parameters:**

- `path` (str | Path):
  **Returns:** bool

#### `create_directory`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** None

#### `delete_file`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** None

#### `list_files`

**Parameters:**

- `path` (str | Path):
- `pattern` (str):
  **Returns:** Iterator[Path]

#### `get_cache_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

#### `clear_cache`

**Parameters:**

- `self` ():
  **Returns:** None

#### `exists`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** bool

#### `mkdir`

**Parameters:**

- `self` ():
- `path` (str | Path):
- `parents` (bool):
  **Returns:** None

## config

**Path:** `crackerjack/services/config.py`

## ConfigurationService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
  **Returns:** None

#### `update_precommit_config`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** bool

#### `get_temp_config_path`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `_determine_config_mode`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** str

#### `validate_config`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `backup_config`

**Parameters:**

- `self` ():
  **Returns:** Path | None

#### `restore_config`

**Parameters:**

- `self` ():
- `backup_file` (Path):
  **Returns:** bool

#### `get_config_info`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `update_pyproject_config`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** bool

#### `_run_precommit_autoupdate`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_execute_precommit_autoupdate`

**Parameters:**

- `self` ():
  **Returns:** subprocess.CompletedProcess[str]

#### `_display_autoupdate_results`

**Parameters:**

- `self` ():
- `stdout` (str):
  **Returns:** None

#### `_has_updates`

**Parameters:**

- `self` ():
- `stdout` (str):
  **Returns:** bool

#### `_is_update_line`

**Parameters:**

- `self` ():
- `line` (str):
  **Returns:** bool

#### `_handle_autoupdate_error`

**Parameters:**

- `self` ():
- `stderr` (str):
  **Returns:** None

#### `_update_dynamic_config_versions`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_extract_version_updates`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, str)]

#### `_update_dynamic_config_file`

**Parameters:**

- `self` ():
- `version_updates` (dict[(str, str)]):
  **Returns:** None

#### `_apply_version_updates`

**Parameters:**

- `self` ():
- `config_path` (Path):
- `version_updates` (dict[(str, str)]):
  **Returns:** None

## version_checker

**Path:** `crackerjack/services/version_checker.py`

## VersionInfo

**Base Classes:** None

### Methods

No methods defined.

## VersionChecker

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
  **Returns:** None

#### `_create_installed_version_info`

**Parameters:**

- `self` ():
- `tool_name` (str):
- `current_version` (str):
- `latest_version` (str | None):
  **Returns:** VersionInfo

#### `_create_missing_tool_info`

**Parameters:**

- `self` ():
- `tool_name` (str):
  **Returns:** VersionInfo

#### `_create_error_version_info`

**Parameters:**

- `self` ():
- `tool_name` (str):
- `error` (Exception):
  **Returns:** VersionInfo

#### `_get_ruff_version`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `_get_pyright_version`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `_get_precommit_version`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `_get_uv_version`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `_get_tool_version`

**Parameters:**

- `self` ():
- `tool_name` (str):
  **Returns:** str | None

#### `_version_compare`

**Parameters:**

- `self` ():
- `current` (str):
- `latest` (str):
  **Returns:** int

#### `_parse_version_parts`

**Parameters:**

- `self` ():
- `version` (str):
  **Returns:** tuple\[(list[int], int)\]

#### `_normalize_version_parts`

**Parameters:**

- `self` ():
- `current_parts` (list[int]):
- `latest_parts` (list[int]):
  **Returns:** tuple\[(list[int], list[int])\]

#### `_compare_numeric_parts`

**Parameters:**

- `self` ():
- `current_parts` (list[int]):
- `latest_parts` (list[int]):
  **Returns:** int

#### `_handle_length_differences`

**Parameters:**

- `self` ():
- `current_len` (int):
- `latest_len` (int):
- `current_parts` (list[int]):
- `latest_parts` (list[int]):
  **Returns:** int

#### `_compare_when_current_shorter`

**Parameters:**

- `self` ():
- `current_len` (int):
- `latest_len` (int):
- `latest_parts` (list[int]):
  **Returns:** int

#### `_compare_when_latest_shorter`

**Parameters:**

- `self` ():
- `latest_len` (int):
- `current_len` (int):
- `current_parts` (list[int]):
  **Returns:** int

## pattern_cache

**Path:** `crackerjack/services/pattern_cache.py`

## CachedPattern

**Base Classes:** None

### Methods

No methods defined.

## PatternCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `project_path` (Path):
  **Returns:** None

#### `_load_patterns`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_save_patterns`

**Parameters:**

- `self` ():
  **Returns:** None

#### `cache_successful_pattern`

**Parameters:**

- `self` ():
- `issue` (Issue):
- `plan` (dict[(str, t.Any)]):
- `result` (FixResult):
  **Returns:** str

#### `get_patterns_for_issue`

**Parameters:**

- `self` ():
- `issue` (Issue):
  **Returns:** list[CachedPattern]

#### `get_best_pattern_for_issue`

**Parameters:**

- `self` ():
- `issue` (Issue):
  **Returns:** CachedPattern | None

#### `use_pattern`

**Parameters:**

- `self` ():
- `pattern_id` (str):
  **Returns:** bool

#### `update_pattern_success_rate`

**Parameters:**

- `self` ():
- `pattern_id` (str):
- `success` (bool):
  **Returns:** None

#### `get_pattern_statistics`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `_get_most_used_patterns`

**Parameters:**

- `self` ():
- `limit` (int):
  **Returns:** list\[dict[(str, t.Any)]\]

#### `cleanup_old_patterns`

**Parameters:**

- `self` ():
- `max_age_days` (int):
- `min_usage_count` (int):
  **Returns:** int

#### `clear_cache`

**Parameters:**

- `self` ():
  **Returns:** None

#### `export_patterns`

**Parameters:**

- `self` ():
- `export_path` (Path):
  **Returns:** bool

#### `import_patterns`

**Parameters:**

- `self` ():
- `import_path` (Path):
- `merge` (bool):
  **Returns:** bool

## backup_service

**Path:** `crackerjack/services/backup_service.py`

## BackupMetadata

**Base Classes:** BaseModel

### Methods

No methods defined.

## BackupValidationResult

**Base Classes:** BaseModel

### Methods

No methods defined.

## PackageBackupService

**Base Classes:** BaseModel

### Methods

#### `model_post_init`

**Parameters:**

- `self` ():
- `_` (t.Any):
  **Returns:** None

#### `create_package_backup`

**Parameters:**

- `self` ():
- `package_directory` (Path):
- `base_directory` (Path | None):
  **Returns:** BackupMetadata

#### `restore_from_backup`

**Parameters:**

- `self` ():
- `backup_metadata` (BackupMetadata):
- `base_directory` (Path | None):
  **Returns:** None

#### `cleanup_backup`

**Parameters:**

- `self` ():
- `backup_metadata` (BackupMetadata):
  **Returns:** None

#### `_generate_backup_id`

**Parameters:**

- `self` ():
  **Returns:** str

#### `_create_backup_directory`

**Parameters:**

- `self` ():
- `backup_id` (str):
  **Returns:** Path

#### `_create_temp_restore_directory`

**Parameters:**

- `self` ():
- `backup_id` (str):
  **Returns:** Path

#### `_filter_package_files`

**Parameters:**

- `self` ():
- `python_files` (list[Path]):
- `package_directory` (Path):
  **Returns:** list[Path]

#### `_perform_backup`

**Parameters:**

- `self` ():
- `files_to_backup` (list[Path]):
- `package_directory` (Path):
- `backup_dir` (Path):
- `backup_id` (str):
  **Returns:** BackupMetadata

#### `_calculate_backup_checksum`

**Parameters:**

- `self` ():
- `file_checksums` (dict[(str, str)]):
  **Returns:** str

#### `_validate_backup`

**Parameters:**

- `self` ():
- `backup_metadata` (BackupMetadata):
  **Returns:** BackupValidationResult

#### `_stage_backup_files`

**Parameters:**

- `self` ():
- `backup_metadata` (BackupMetadata):
- `temp_restore_dir` (Path):
  **Returns:** None

#### `_commit_restoration`

**Parameters:**

- `self` ():
- `backup_metadata` (BackupMetadata):
- `temp_restore_dir` (Path):
- `base_directory` (Path | None):
  **Returns:** None

#### `_cleanup_backup_directory`

**Parameters:**

- `self` ():
- `directory` (Path):
  **Returns:** None

## health_metrics

**Path:** `crackerjack/services/health_metrics.py`

## ProjectHealth

**Base Classes:** None

### Methods

#### `needs_init`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_is_trending_up`

**Parameters:**

- `self` ():
- `values` (list[int] | list[float]):
- `min_points` (int):
  **Returns:** bool

#### `_is_trending_down`

**Parameters:**

- `self` ():
- `values` (list[int] | list[float]):
- `min_points` (int):
  **Returns:** bool

#### `get_health_score`

**Parameters:**

- `self` ():
  **Returns:** float

#### `get_recommendations`

**Parameters:**

- `self` ():
  **Returns:** list[str]

## HealthMetricsService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `filesystem` (FileSystemInterface):
- `console` (Console | None):
  **Returns:** None

#### `collect_current_metrics`

**Parameters:**

- `self` ():
  **Returns:** ProjectHealth

#### `_load_health_history`

**Parameters:**

- `self` ():
  **Returns:** ProjectHealth

#### `_save_health_metrics`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
  **Returns:** None

#### `_count_lint_errors`

**Parameters:**

- `self` ():
  **Returns:** int | None

#### `_get_test_coverage`

**Parameters:**

- `self` ():
  **Returns:** float | None

#### `_check_existing_coverage_files`

**Parameters:**

- `self` ():
  **Returns:** float | None

#### `_generate_coverage_report`

**Parameters:**

- `self` ():
  **Returns:** float | None

#### `_get_coverage_from_command`

**Parameters:**

- `self` ():
  **Returns:** float | None

#### `_calculate_dependency_ages`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, int)]

#### `_load_project_data`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `_extract_all_dependencies`

**Parameters:**

- `self` ():
- `project_data` (dict[(str, t.Any)]):
  **Returns:** list[str]

#### `_get_ages_for_dependencies`

**Parameters:**

- `self` ():
- `dependencies` (list[str]):
  **Returns:** dict[(str, int)]

#### `_extract_package_name`

**Parameters:**

- `self` ():
- `dep_spec` (str):
  **Returns:** str | None

#### `_get_package_age`

**Parameters:**

- `self` ():
- `package_name` (str):
  **Returns:** int | None

#### `_fetch_package_data`

**Parameters:**

- `self` ():
- `package_name` (str):
  **Returns:** dict[(str, t.Any)] | None

#### `_extract_upload_time`

**Parameters:**

- `self` ():
- `package_data` (dict[(str, t.Any)]):
  **Returns:** str | None

#### `_calculate_days_since_upload`

**Parameters:**

- `self` ():
- `upload_time` (str):
  **Returns:** int | None

#### `_assess_config_completeness`

**Parameters:**

- `self` ():
  **Returns:** float

#### `_assess_pyproject_config`

**Parameters:**

- `self` ():
  **Returns:** tuple[(float, int)]

#### `_assess_project_metadata`

**Parameters:**

- `self` ():
- `data` (dict[(str, t.Any)]):
  **Returns:** tuple[(float, int)]

#### `_assess_tool_configs`

**Parameters:**

- `self` ():
- `data` (dict[(str, t.Any)]):
  **Returns:** tuple[(float, int)]

#### `_assess_precommit_config`

**Parameters:**

- `self` ():
  **Returns:** tuple[(float, int)]

#### `_assess_ci_config`

**Parameters:**

- `self` ():
  **Returns:** tuple[(float, int)]

#### `_assess_documentation_config`

**Parameters:**

- `self` ():
  **Returns:** tuple[(float, int)]

#### `analyze_project_health`

**Parameters:**

- `self` ():
- `save_metrics` (bool):
  **Returns:** ProjectHealth

#### `report_health_status`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
  **Returns:** None

#### `_print_health_summary`

**Parameters:**

- `self` ():
- `health_score` (float):
  **Returns:** None

#### `_get_health_status_display`

**Parameters:**

- `self` ():
- `health_score` (float):
  **Returns:** tuple[(str, str, str)]

#### `_print_health_metrics`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
  **Returns:** None

#### `_print_health_recommendations`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
  **Returns:** None

#### `get_health_trend_summary`

**Parameters:**

- `self` ():
- `days` (int):
  **Returns:** dict[(str, Any)]

#### `_get_lint_errors_metrics`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
  **Returns:** dict[(str, str | int | None)]

#### `_get_test_coverage_metrics`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
  **Returns:** dict[(str, str | float | None)]

#### `_get_dependency_age_metrics`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
  **Returns:** dict[(str, float | int | None)]

#### `_get_trend_direction`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
- `trend_data` (list[int]):
  **Returns:** str

#### `_get_coverage_trend_direction`

**Parameters:**

- `self` ():
- `health` (ProjectHealth):
- `coverage_trend` (list[float]):
  **Returns:** str

## filesystem

**Path:** `crackerjack/services/filesystem.py`

## FileSystemService

**Base Classes:** None

### Methods

#### `clean_trailing_whitespace_and_newlines`

**Parameters:**

- `content` (str):
  **Returns:** str

#### `read_file`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** str

#### `write_file`

**Parameters:**

- `self` ():
- `path` (str | Path):
- `content` (str):
  **Returns:** None

#### `exists`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** bool

#### `mkdir`

**Parameters:**

- `self` ():
- `path` (str | Path):
- `parents` (bool):
  **Returns:** None

#### `glob`

**Parameters:**

- `self` ():
- `pattern` (str):
- `path` (str | Path | None):
  **Returns:** list[Path]

#### `rglob`

**Parameters:**

- `self` ():
- `pattern` (str):
- `path` (str | Path | None):
  **Returns:** list[Path]

#### `copy_file`

**Parameters:**

- `self` ():
- `src` (str | Path):
- `dst` (str | Path):
  **Returns:** None

#### `_normalize_copy_paths`

**Parameters:**

- `self` ():
- `src` (str | Path):
- `dst` (str | Path):
  **Returns:** tuple[(Path, Path)]

#### `_validate_copy_source`

**Parameters:**

- `self` ():
- `src_path` (Path):
  **Returns:** None

#### `_prepare_copy_destination`

**Parameters:**

- `self` ():
- `dst_path` (Path):
  **Returns:** None

#### `_perform_file_copy`

**Parameters:**

- `self` ():
- `src_path` (Path):
- `dst_path` (Path):
- `src` (str | Path):
- `dst` (str | Path):
  **Returns:** None

#### `remove_file`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** None

#### `get_file_size`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** int

#### `get_file_mtime`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** float

#### `read_file_chunked`

**Parameters:**

- `self` ():
- `path` (str | Path):
- `chunk_size` (int):
  **Returns:** Iterator[str]

#### `read_lines_streaming`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** Iterator[str]

## websocket_resource_limiter

**Path:** `crackerjack/services/websocket_resource_limiter.py`

## ConnectionMetrics

**Base Classes:** None

### Methods

#### `connection_duration`

**Parameters:**

- `self` ():
  **Returns:** float

#### `idle_time`

**Parameters:**

- `self` ():
  **Returns:** float

## ResourceLimits

**Base Classes:** None

### Methods

No methods defined.

## ResourceExhaustedError

**Base Classes:** Exception

### Methods

No methods defined.

## WebSocketResourceLimiter

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `limits` (ResourceLimits | None):

#### `_setup_limiter_components`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_initialize_connection_tracking`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_initialize_metrics_tracking`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_initialize_cleanup_system`

**Parameters:**

- `self` ():
  **Returns:** None

#### `validate_new_connection`

**Parameters:**

- `self` ():
- `client_id` (str):
- `client_ip` (str):
  **Returns:** None

#### `_check_ip_blocking_status`

**Parameters:**

- `self` ():
- `client_ip` (str):
- `current_time` (float):
  **Returns:** None

#### `_check_total_connection_limit`

**Parameters:**

- `self` ():
- `client_id` (str):
- `client_ip` (str):
  **Returns:** None

#### `_check_per_ip_connection_limit`

**Parameters:**

- `self` ():
- `client_id` (str):
- `client_ip` (str):
- `current_time` (float):
  **Returns:** None

#### `register_connection`

**Parameters:**

- `self` ():
- `client_id` (str):
- `client_ip` (str):
  **Returns:** None

#### `unregister_connection`

**Parameters:**

- `self` ():
- `client_id` (str):
- `client_ip` (str):
  **Returns:** None

#### `validate_message`

**Parameters:**

- `self` ():
- `client_id` (str):
- `message_size` (int):
  **Returns:** None

#### `_check_message_size`

**Parameters:**

- `self` ():
- `client_id` (str):
- `message_size` (int):
  **Returns:** None

#### `_get_connection_metrics`

**Parameters:**

- `self` ():
- `client_id` (str):
  **Returns:** ConnectionMetrics

#### `_check_message_count`

**Parameters:**

- `self` ():
- `client_id` (str):
- `metrics` (ConnectionMetrics):
  **Returns:** None

#### `_check_message_rate`

**Parameters:**

- `self` ():
- `client_id` (str):
  **Returns:** None

#### `track_message`

**Parameters:**

- `self` ():
- `client_id` (str):
- `message_size` (int):
- `is_sent` (bool):
  **Returns:** None

#### `_cleanup_expired_connections`

**Parameters:**

- `self` ():
- `current_time` (float):
  **Returns:** int

#### `_find_expired_connections`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `_remove_expired_connection`

**Parameters:**

- `self` ():
- `client_id` (str):
  **Returns:** bool

#### `_cleanup_empty_ip_entries`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_cleanup_expired_ip_blocks`

**Parameters:**

- `self` ():
- `current_time` (float):
  **Returns:** None

#### `_log_cleanup_results`

**Parameters:**

- `self` ():
- `cleanup_count` (int):
  **Returns:** None

#### `get_resource_status`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `get_connection_metrics`

**Parameters:**

- `self` ():
- `client_id` (str):
  **Returns:** ConnectionMetrics | None

## security

**Path:** `crackerjack/services/security.py`

## SecurityService

**Base Classes:** None

### Methods

#### `mask_tokens`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** str

#### `mask_command_output`

**Parameters:**

- `self` ():
- `stdout` (str):
- `stderr` (str):
  **Returns:** tuple[(str, str)]

#### `create_secure_token_file`

**Parameters:**

- `self` ():
- `token` (str):
- `prefix` (str):
  **Returns:** Path

#### `cleanup_token_file`

**Parameters:**

- `self` ():
- `token_file` (Path):
  **Returns:** None

#### `get_masked_env_summary`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, str)]

#### `validate_token_format`

**Parameters:**

- `self` ():
- `token` (str):
- `token_type` (str | None):
  **Returns:** bool

#### `create_secure_command_env`

**Parameters:**

- `self` ():
- `base_env` (dict[(str, str)] | None):
- `additional_vars` (dict[(str, str)] | None):
  **Returns:** dict[(str, str)]

#### `validate_file_safety`

**Parameters:**

- `self` ():
- `path` (str | Path):
  **Returns:** bool

#### `check_hardcoded_secrets`

**Parameters:**

- `self` ():
- `content` (str):
  **Returns:** list\[dict[(str, t.Any)]\]

#### `is_safe_subprocess_call`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
  **Returns:** bool

## api_extractor

**Path:** `crackerjack/services/api_extractor.py`

**Implements Protocols:**

- APIExtractorProtocol

## PythonDocstringParser

Parser for extracting structured information from Python docstrings.

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `parse_docstring`

Parse a docstring and extract structured information.
**Parameters:**

- `self` ():
- `docstring` (str | None):
  **Returns:** dict[(str, t.Any)]

#### `_is_section_header`

Check if a line is a docstring section header.
**Parameters:**

- `self` ():
- `line` (str):
  **Returns:** bool

#### `_extract_parameters`

Extract parameter documentation from docstring.
**Parameters:**

- `self` ():
- `docstring` (str):
  **Returns:** dict[(str, str)]

#### `_extract_returns`

Extract return value documentation from docstring.
**Parameters:**

- `self` ():
- `docstring` (str):
  **Returns:** str

#### `_extract_raises`

Extract exception documentation from docstring.
**Parameters:**

- `self` ():
- `docstring` (str):
  **Returns:** list[str]

## APIExtractorImpl

Implementation of API documentation extraction from source code.

**Base Classes:** APIExtractorProtocol

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
  **Returns:** None

#### `extract_from_python_files`

Extract API documentation from Python files.
**Parameters:**

- `self` ():
- `files` (list[Path]):
  **Returns:** dict[(str, t.Any)]

#### `extract_protocol_definitions`

Extract protocol definitions from protocols.py file.
**Parameters:**

- `self` ():
- `protocol_file` (Path):
  **Returns:** dict[(str, t.Any)]

#### `extract_service_interfaces`

Extract service interfaces and their methods.
**Parameters:**

- `self` ():
- `service_files` (list[Path]):
  **Returns:** dict[(str, t.Any)]

#### `extract_cli_commands`

Extract CLI command definitions and options.
**Parameters:**

- `self` ():
- `cli_files` (list[Path]):
  **Returns:** dict[(str, t.Any)]

#### `extract_mcp_tools`

Extract MCP tool definitions and their capabilities.
**Parameters:**

- `self` ():
- `mcp_files` (list[Path]):
  **Returns:** dict[(str, t.Any)]

#### `_extract_module_info`

Extract information from a Python module.
**Parameters:**

- `self` ():
- `tree` (ast.AST):
- `file_path` (Path):
- `source_code` (str):
  **Returns:** dict[(str, t.Any)]

#### `_extract_class_info`

Extract information from a class definition.
**Parameters:**

- `self` ():
- `node` (ast.ClassDef):
- `source_code` (str):
  **Returns:** dict[(str, t.Any)]

#### `_extract_function_info`

Extract information from a function definition.
**Parameters:**

- `self` ():
- `node` (ast.FunctionDef):
- `source_code` (str):
  **Returns:** dict[(str, t.Any)]

#### `_extract_protocol_info`

Extract detailed information from a protocol definition.
**Parameters:**

- `self` ():
- `node` (ast.ClassDef):
- `source_code` (str):
  **Returns:** dict[(str, t.Any)]

#### `_extract_service_info`

Extract service implementation information.
**Parameters:**

- `self` ():
- `tree` (ast.AST):
- `file_path` (Path):
- `source_code` (str):
  **Returns:** dict[(str, t.Any)]

#### `_extract_cli_info`

Extract CLI command and option information.
**Parameters:**

- `self` ():
- `tree` (ast.AST):
- `source_code` (str):
  **Returns:** dict[(str, t.Any)]

#### `_extract_mcp_python_tools`

Extract MCP tool information from Python files.
**Parameters:**

- `self` ():
- `tree` (ast.AST):
- `source_code` (str):
  **Returns:** dict[(str, t.Any)]

#### `_extract_mcp_markdown_docs`

Extract MCP tool documentation from markdown files.
**Parameters:**

- `self` ():
- `content` (str):
  **Returns:** dict[(str, t.Any)]

#### `_is_protocol_class`

Check if a class is a Protocol definition.
**Parameters:**

- `self` ():
- `node` (ast.ClassDef):
  **Returns:** bool

#### `_get_node_name`

Get the name from an AST node.
**Parameters:**

- `self` ():
- `node` (ast.AST):
  **Returns:** str

#### `_get_annotation_string`

Convert an annotation AST node to a string representation.
**Parameters:**

- `self` ():
- `annotation` (ast.AST | None):
  **Returns:** str

#### `_extract_import_info`

Extract import statement information.
**Parameters:**

- `self` ():
- `node` (ast.Import | ast.ImportFrom):
  **Returns:** dict[(str, t.Any)]

## performance_monitor

**Path:** `crackerjack/services/performance_monitor.py`

## PerformanceMetric

**Base Classes:** None

### Methods

No methods defined.

## PhasePerformance

**Base Classes:** None

### Methods

#### `finalize`

**Parameters:**

- `self` ():
- `end_time` (datetime | None):
  **Returns:** None

## WorkflowPerformance

**Base Classes:** None

### Methods

#### `add_phase`

**Parameters:**

- `self` ():
- `phase` (PhasePerformance):
  **Returns:** None

#### `finalize`

**Parameters:**

- `self` ():
- `success` (bool):
  **Returns:** None

#### `_calculate_performance_score`

**Parameters:**

- `self` ():
  **Returns:** float

## PerformanceBenchmark

**Base Classes:** None

### Methods

#### `__post_init__`

**Parameters:**

- `self` ():
  **Returns:** None

## PerformanceMonitor

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `data_retention_days` (int):
- `benchmark_history_size` (int):

#### `_initialize_data_structures`

**Parameters:**

- `self` ():
- `history_size` (int):
  **Returns:** None

#### `_initialize_services`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_initialize_thresholds`

**Parameters:**

- `self` ():
  **Returns:** None

#### `start_workflow`

**Parameters:**

- `self` ():
- `workflow_id` (str):
  **Returns:** None

#### `end_workflow`

**Parameters:**

- `self` ():
- `workflow_id` (str):
- `success` (bool):
  **Returns:** WorkflowPerformance

#### `start_phase`

**Parameters:**

- `self` ():
- `workflow_id` (str):
- `phase_name` (str):
  **Returns:** None

#### `end_phase`

**Parameters:**

- `self` ():
- `workflow_id` (str):
- `phase_name` (str):
- `success` (bool):
  **Returns:** PhasePerformance

#### `record_metric`

**Parameters:**

- `self` ():
- `workflow_id` (str):
- `phase_name` (str):
- `metric_name` (str):
- `value` (float):
- `unit` (str):
- `metadata` (dict[(str, t.Any)] | None):
  **Returns:** None

#### `record_parallel_operation`

**Parameters:**

- `self` ():
- `workflow_id` (str):
- `phase_name` (str):
  **Returns:** None

#### `record_sequential_operation`

**Parameters:**

- `self` ():
- `workflow_id` (str):
- `phase_name` (str):
  **Returns:** None

#### `benchmark_operation`

**Parameters:**

- `self` ():
- `operation_name` (str):
- `duration_seconds` (float):
  **Returns:** PerformanceBenchmark

#### `get_performance_summary`

**Parameters:**

- `self` ():
- `last_n_workflows` (int):
  **Returns:** dict[(str, Any)]

#### `_calculate_basic_workflow_stats`

**Parameters:**

- `self` ():
- `workflows` (list[WorkflowPerformance]):
  **Returns:** dict[(str, Any)]

#### `_calculate_cache_statistics`

**Parameters:**

- `self` ():
- `workflows` (list[WorkflowPerformance]):
  **Returns:** dict[(str, Any)]

#### `_calculate_parallelization_statistics`

**Parameters:**

- `self` ():
- `workflows` (list[WorkflowPerformance]):
  **Returns:** dict[(str, Any)]

#### `get_benchmark_trends`

**Parameters:**

- `self` ():
  **Returns:** dict\[(str, dict[(str, Any)])\]

#### `_calculate_benchmark_basic_stats`

**Parameters:**

- `self` ():
- `history_list` (list[float]):
  **Returns:** dict[(str, float)]

#### `_calculate_trend_percentage`

**Parameters:**

- `self` ():
- `history_list` (list[float]):
  **Returns:** float

#### `export_performance_data`

**Parameters:**

- `self` ():
- `output_path` (Path):
  **Returns:** None

#### `_check_performance_warnings`

**Parameters:**

- `self` ():
- `workflow` (WorkflowPerformance):
  **Returns:** None

#### `_check_duration_warning`

**Parameters:**

- `self` ():
- `workflow` (WorkflowPerformance):
  **Returns:** list[str]

#### `_check_memory_warning`

**Parameters:**

- `self` ():
- `workflow` (WorkflowPerformance):
  **Returns:** list[str]

#### `_check_cache_warning`

**Parameters:**

- `self` ():
- `workflow` (WorkflowPerformance):
  **Returns:** list[str]

## phase_monitor

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `workflow_id` (str):
- `phase_name` (str):

#### `__enter__`

**Parameters:**

- `self` ():

#### `__exit__`

**Parameters:**

- `self` ():
- `exc_type` (type[BaseException] | None):
- `exc_val` (BaseException | None):
- `exc_tb` (object | None):
  **Returns:** None

#### `record_parallel_op`

**Parameters:**

- `self` ():

#### `record_sequential_op`

**Parameters:**

- `self` ():

#### `record_metric`

**Parameters:**

- `self` ():
- `name` (str):
- `value` (float):
- `unit` (str):

## changelog_automation

**Path:** `crackerjack/services/changelog_automation.py`

## ChangelogEntry

Represents a single changelog entry.

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `entry_type` (str):
- `description` (str):
- `commit_hash` (str):
- `breaking_change` (bool):
  **Returns:** None

#### `to_markdown`

Convert entry to markdown format.
**Parameters:**

- `self` ():
  **Returns:** str

## ChangelogGenerator

Generate and update changelogs based on git commits.

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `git_service` (GitService):
  **Returns:** None

#### `parse_commit_message`

Parse a commit message into a changelog entry.
**Parameters:**

- `self` ():
- `commit_message` (str):
- `commit_hash` (str):
  **Returns:** ChangelogEntry | None

#### `_parse_non_conventional_commit`

Parse non-conventional commit messages.
**Parameters:**

- `self` ():
- `header` (str):
- `body` (str):
- `commit_hash` (str):
  **Returns:** ChangelogEntry | None

#### `_format_description`

Format the changelog description.
**Parameters:**

- `self` ():
- `description` (str):
- `scope` (str):
- `commit_type` (str):
  **Returns:** str

#### `generate_changelog_entries`

Generate changelog entries from git commits.
**Parameters:**

- `self` ():
- `since_version` (str | None):
- `target_file` (Path | None):
  **Returns:** dict\[(str, list[ChangelogEntry])\]

#### `update_changelog`

Update the changelog file with new entries.
**Parameters:**

- `self` ():
- `changelog_path` (Path):
- `new_version` (str):
- `entries_by_type` (dict\[(str, list[ChangelogEntry])\] | None):
  **Returns:** bool

#### `_generate_changelog_section`

Generate a new changelog section.
**Parameters:**

- `self` ():
- `version` (str):
- `entries_by_type` (dict\[(str, list[ChangelogEntry])\]):
  **Returns:** str

#### `_insert_new_section`

Insert new section into existing changelog content.
**Parameters:**

- `self` ():
- `existing_content` (str):
- `new_section` (str):
  **Returns:** str

#### `generate_changelog_from_commits`

Generate and update changelog from git commits.
**Parameters:**

- `self` ():
- `changelog_path` (Path):
- `version` (str):
- `since_version` (str | None):
  **Returns:** bool

#### `_display_changelog_preview`

Display a preview of generated changelog entries.
**Parameters:**

- `self` ():
- `entries_by_type` (dict\[(str, list[ChangelogEntry])\]):
  **Returns:** None

## cache

**Path:** `crackerjack/services/cache.py`

## CacheEntry

**Base Classes:** None

### Methods

#### `is_expired`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `age_seconds`

**Parameters:**

- `self` ():
  **Returns:** int

#### `touch`

**Parameters:**

- `self` ():
  **Returns:** None

#### `to_dict`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `from_dict`

**Parameters:**

- `cls` ():
- `data` (dict[(str, t.Any)]):
  **Returns:** CacheEntry

## CacheStats

**Base Classes:** None

### Methods

#### `hit_rate`

**Parameters:**

- `self` ():
  **Returns:** float

#### `to_dict`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## InMemoryCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `max_entries` (int):
- `default_ttl` (int):
  **Returns:** None

#### `get`

**Parameters:**

- `self` ():
- `key` (str):
  **Returns:** t.Any | None

#### `set`

**Parameters:**

- `self` ():
- `key` (str):
- `value` (t.Any):
- `ttl_seconds` (int | None):
  **Returns:** None

#### `invalidate`

**Parameters:**

- `self` ():
- `key` (str):
  **Returns:** bool

#### `clear`

**Parameters:**

- `self` ():
  **Returns:** None

#### `cleanup_expired`

**Parameters:**

- `self` ():
  **Returns:** int

#### `_evict_lru`

**Parameters:**

- `self` ():
  **Returns:** None

## FileCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache_dir` (Path):
- `namespace` (str):
  **Returns:** None

#### `get`

**Parameters:**

- `self` ():
- `key` (str):
  **Returns:** t.Any | None

#### `set`

**Parameters:**

- `self` ():
- `key` (str):
- `value` (t.Any):
- `ttl_seconds` (int):
  **Returns:** None

#### `invalidate`

**Parameters:**

- `self` ():
- `key` (str):
  **Returns:** bool

#### `clear`

**Parameters:**

- `self` ():
  **Returns:** None

#### `cleanup_expired`

**Parameters:**

- `self` ():
  **Returns:** int

#### `_get_cache_file`

**Parameters:**

- `self` ():
- `key` (str):
  **Returns:** Path

## CrackerjackCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache_dir` (Path | None):
- `enable_disk_cache` (bool):
  **Returns:** None

#### `get_hook_result`

**Parameters:**

- `self` ():
- `hook_name` (str):
- `file_hashes` (list[str]):
  **Returns:** HookResult | None

#### `set_hook_result`

**Parameters:**

- `self` ():
- `hook_name` (str):
- `file_hashes` (list[str]):
- `result` (HookResult):
  **Returns:** None

#### `get_expensive_hook_result`

Get hook result with disk cache fallback for expensive hooks.
**Parameters:**

- `self` ():
- `hook_name` (str):
- `file_hashes` (list[str]):
- `tool_version` (str | None):
  **Returns:** HookResult | None

#### `set_expensive_hook_result`

Set hook result in both memory and disk cache for expensive hooks.
**Parameters:**

- `self` ():
- `hook_name` (str):
- `file_hashes` (list[str]):
- `result` (HookResult):
- `tool_version` (str | None):
  **Returns:** None

#### `get_file_hash`

**Parameters:**

- `self` ():
- `file_path` (Path):
  **Returns:** str | None

#### `set_file_hash`

**Parameters:**

- `self` ():
- `file_path` (Path):
- `file_hash` (str):
  **Returns:** None

#### `get_config_data`

**Parameters:**

- `self` ():
- `config_key` (str):
  **Returns:** t.Any | None

#### `set_config_data`

**Parameters:**

- `self` ():
- `config_key` (str):
- `data` (t.Any):
  **Returns:** None

#### `get_agent_decision`

Get cached AI agent decision based on issue content.
**Parameters:**

- `self` ():
- `agent_name` (str):
- `issue_hash` (str):
  **Returns:** t.Any | None

#### `set_agent_decision`

Cache AI agent decision for future use.
**Parameters:**

- `self` ():
- `agent_name` (str):
- `issue_hash` (str):
- `decision` (t.Any):
  **Returns:** None

#### `get_quality_baseline`

Get quality baseline metrics for a specific git commit.
**Parameters:**

- `self` ():
- `git_hash` (str):
  **Returns:** dict[(str, t.Any)] | None

#### `set_quality_baseline`

Store quality baseline metrics for a git commit.
**Parameters:**

- `self` ():
- `git_hash` (str):
- `metrics` (dict[(str, t.Any)]):
  **Returns:** None

#### `invalidate_hook_cache`

**Parameters:**

- `self` ():
- `hook_name` (str | None):
  **Returns:** None

#### `cleanup_all`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, int)]

#### `get_cache_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `_get_hook_cache_key`

**Parameters:**

- `self` ():
- `hook_name` (str):
- `file_hashes` (list[str]):
  **Returns:** str

#### `_get_versioned_hook_cache_key`

Get cache key with tool version for disk cache invalidation.
**Parameters:**

- `self` ():
- `hook_name` (str):
- `file_hashes` (list[str]):
- `tool_version` (str | None):
  **Returns:** str

## log_manager

**Path:** `crackerjack/services/log_manager.py`

## LogManager

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `app_name` (str):
  **Returns:** None

#### `_get_log_directory`

**Parameters:**

- `self` ():
  **Returns:** Path

#### `_setup_directories`

**Parameters:**

- `self` ():
  **Returns:** None

#### `log_dir`

**Parameters:**

- `self` ():
  **Returns:** Path

#### `debug_dir`

**Parameters:**

- `self` ():
  **Returns:** Path

#### `error_dir`

**Parameters:**

- `self` ():
  **Returns:** Path

#### `audit_dir`

**Parameters:**

- `self` ():
  **Returns:** Path

#### `create_debug_log_file`

**Parameters:**

- `self` ():
- `session_id` (str | None):
  **Returns:** Path

#### `create_error_log_file`

**Parameters:**

- `self` ():
- `error_type` (str):
  **Returns:** Path

#### `rotate_logs`

**Parameters:**

- `self` ():
- `log_dir` (Path):
- `pattern` (str):
- `max_files` (int):
- `max_age_days` (int):
  **Returns:** int

#### `cleanup_all_logs`

**Parameters:**

- `self` ():
- `debug_max_files` (int):
- `error_max_files` (int):
- `audit_max_files` (int):
- `max_age_days` (int):
  **Returns:** dict[(str, int)]

#### `migrate_legacy_logs`

**Parameters:**

- `self` ():
- `source_dir` (Path):
- `dry_run` (bool):
  **Returns:** dict[(str, int)]

#### `get_log_stats`

**Parameters:**

- `self` ():
  **Returns:** dict\[(str, dict[(str, int | str)])\]

#### `setup_rotating_file_handler`

**Parameters:**

- `self` ():
- `logger` (logging.Logger):
- `log_type` (str):
- `max_bytes` (int):
- `backup_count` (int):
  **Returns:** logging.FileHandler

#### `print_log_summary`

**Parameters:**

- `self` ():
  **Returns:** None

## config_merge

**Path:** `crackerjack/services/config_merge.py`

**Implements Protocols:**

- ConfigMergeServiceProtocol

## ConfigMergeService

**Base Classes:** ConfigMergeServiceProtocol

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `filesystem` (FileSystemInterface):
- `git_service` (GitInterface):
  **Returns:** None

#### `smart_merge_pyproject`

**Parameters:**

- `self` ():
- `source_content` (dict[(str, t.Any)]):
- `target_path` (str | t.Any):
- `project_name` (str):
  **Returns:** dict[(str, t.Any)]

#### `smart_merge_pre_commit_config`

**Parameters:**

- `self` ():
- `source_content` (dict[(str, t.Any)]):
- `target_path` (str | t.Any):
- `project_name` (str):
  **Returns:** dict[(str, t.Any)]

#### `smart_append_file`

**Parameters:**

- `self` ():
- `source_content` (str):
- `target_path` (str | t.Any):
- `start_marker` (str):
- `end_marker` (str):
- `force` (bool):
  **Returns:** str

#### `smart_merge_gitignore`

**Parameters:**

- `self` ():
- `patterns` (list[str]):
- `target_path` (str | t.Any):
  **Returns:** str

#### `_create_new_gitignore`

**Parameters:**

- `self` ():
- `target_path` (Path):
- `patterns` (list[str]):
  **Returns:** str

#### `_parse_existing_gitignore_content`

**Parameters:**

- `self` ():
- `lines` (list[str]):
  **Returns:** t.Any

#### `_init_parser_state`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, bool)]

#### `_process_gitignore_line`

**Parameters:**

- `self` ():
- `line` (str):
- `parsed` (t.Any):
- `state` (dict[(str, bool)]):
  **Returns:** dict[(str, bool)]

#### `_handle_crackerjack_header`

**Parameters:**

- `self` ():
- `state` (dict[(str, bool)]):
  **Returns:** dict[(str, bool)]

#### `_should_skip_empty_line`

**Parameters:**

- `self` ():
- `stripped` (str):
- `state` (dict[(str, bool)]):
  **Returns:** bool

#### `_collect_pattern_if_present`

**Parameters:**

- `self` ():
- `stripped` (str):
- `parsed` (t.Any):
- `state` (dict[(str, bool)]):
  **Returns:** None

#### `_add_line_if_non_crackerjack`

**Parameters:**

- `self` ():
- `line` (str):
- `parsed` (t.Any):
- `state` (dict[(str, bool)]):
  **Returns:** None

#### `_is_crackerjack_header`

**Parameters:**

- `self` ():
- `line` (str):
  **Returns:** bool

#### `_build_merged_gitignore_content`

**Parameters:**

- `self` ():
- `parsed_content` (t.Any):
- `new_patterns` (list[str]):
  **Returns:** str

#### `_get_consolidated_patterns`

**Parameters:**

- `self` ():
- `existing_patterns` (set[str]):
- `new_patterns` (list[str]):
  **Returns:** list[str]

#### `write_pyproject_config`

**Parameters:**

- `self` ():
- `config` (dict[(str, t.Any)]):
- `target_path` (str | t.Any):
  **Returns:** None

#### `write_pre_commit_config`

**Parameters:**

- `self` ():
- `config` (dict[(str, t.Any)]):
- `target_path` (str | t.Any):
  **Returns:** None

#### `_ensure_crackerjack_dev_dependency`

**Parameters:**

- `self` ():
- `target_config` (dict[(str, t.Any)]):
- `source_config` (dict[(str, t.Any)]):
  **Returns:** None

#### `_merge_tool_configurations`

**Parameters:**

- `self` ():
- `target_config` (dict[(str, t.Any)]):
- `source_config` (dict[(str, t.Any)]):
- `project_name` (str):
  **Returns:** None

#### `_merge_tool_settings`

**Parameters:**

- `self` ():
- `target_tool` (dict[(str, t.Any)]):
- `source_tool` (dict[(str, t.Any)]):
- `tool_name` (str):
- `project_name` (str):
  **Returns:** None

#### `_merge_pytest_markers`

**Parameters:**

- `self` ():
- `target_tools` (dict[(str, t.Any)]):
- `source_tools` (dict[(str, t.Any)]):
  **Returns:** None

#### `_remove_fixed_coverage_requirements`

**Parameters:**

- `self` ():
- `target_config` (dict[(str, t.Any)]):
  **Returns:** None

#### `_replace_project_name_in_tool_config`

**Parameters:**

- `self` ():
- `tool_config` (dict[(str, t.Any)]):
- `project_name` (str):
  **Returns:** dict[(str, t.Any)]

#### `_replace_project_name_in_config_value`

**Parameters:**

- `self` ():
- `value` (t.Any):
- `project_name` (str):
  **Returns:** t.Any

## ParsedContent

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():

## documentation_service

**Path:** `crackerjack/services/documentation_service.py`

**Implements Protocols:**

- DocumentationServiceProtocol

## DocumentationServiceImpl

Main service for automated documentation generation and maintenance.

**Base Classes:** DocumentationServiceProtocol

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
- `api_extractor` (APIExtractorProtocol | None):
- `doc_generator` (DocumentationGeneratorProtocol | None):
  **Returns:** None

#### `extract_api_documentation`

Extract API documentation from source code files.
**Parameters:**

- `self` ():
- `source_paths` (list[Path]):
  **Returns:** dict[(str, t.Any)]

#### `generate_documentation`

Generate documentation using specified template.
**Parameters:**

- `self` ():
- `template_name` (str):
- `context` (dict[(str, t.Any)]):
  **Returns:** str

#### `validate_documentation`

Validate documentation for issues and inconsistencies.
**Parameters:**

- `self` ():
- `doc_paths` (list[Path]):
  **Returns:** list\[dict[(str, str)]\]

#### `update_documentation_index`

Update the main documentation index with links to all docs.
**Parameters:**

- `self` ():
  **Returns:** bool

#### `get_documentation_coverage`

Calculate documentation coverage metrics.
**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `generate_full_api_documentation`

Generate complete API documentation for the project.
**Parameters:**

- `self` ():
  **Returns:** bool

#### `_ensure_directories`

Ensure all necessary documentation directories exist.
**Parameters:**

- `self` ():
  **Returns:** None

#### `_check_internal_links`

Check for broken internal links in documentation.
**Parameters:**

- `self` ():
- `content` (str):
- `doc_path` (Path):
  **Returns:** list\[dict[(str, str)]\]

#### `_check_empty_sections`

Check for empty sections in documentation.
**Parameters:**

- `self` ():
- `content` (str):
- `doc_path` (Path):
  **Returns:** list\[dict[(str, str)]\]

#### `_check_version_references`

Check for outdated version references.
**Parameters:**

- `self` ():
- `content` (str):
- `doc_path` (Path):
  **Returns:** list\[dict[(str, str)]\]

#### `_generate_index_content`

Generate content for the documentation index.
**Parameters:**

- `self` ():
- `api_docs` (list[Path]):
- `guide_docs` (list[Path]):
- `root_docs` (list[Path]):
  **Returns:** str

#### `_generate_protocol_documentation`

Generate focused protocol documentation.
**Parameters:**

- `self` ():
- `protocols` (dict[(str, t.Any)]):
  **Returns:** str

#### `_generate_service_documentation`

Generate focused service documentation.
**Parameters:**

- `self` ():
- `services` (dict[(str, t.Any)]):
  **Returns:** str

#### `_generate_cli_documentation`

Generate CLI reference documentation.
**Parameters:**

- `self` ():
- `commands` (dict[(str, t.Any)]):
  **Returns:** str

#### `_format_cross_references`

Format cross-references into markdown.
**Parameters:**

- `self` ():
- `cross_refs` (dict\[(str, list[str])\]):
  **Returns:** str

## secure_subprocess

**Path:** `crackerjack/services/secure_subprocess.py`

## SecurityError

**Base Classes:** Exception

### Methods

No methods defined.

## CommandValidationError

**Base Classes:** SecurityError

### Methods

No methods defined.

## EnvironmentValidationError

**Base Classes:** SecurityError

### Methods

No methods defined.

## SubprocessSecurityConfig

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `max_command_length` (int):
- `max_arg_length` (int):
- `max_env_var_length` (int):
- `max_env_vars` (int):
- `allowed_executables` (set[str] | None):
- `blocked_executables` (set[str] | None):
- `max_timeout` (float):
- `enable_path_validation` (bool):
- `enable_command_logging` (bool):

## SecureSubprocessExecutor

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `config` (SubprocessSecurityConfig | None):

#### `execute_secure`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `cwd` (Path | str | None):
- `env` (dict[(str, str)] | None):
- `timeout` (float | None):
- `input_data` (str | bytes | None):
- `capture_output` (bool):
- `text` (bool):
- `check` (bool):
  **Returns:** subprocess.CompletedProcess[str]

#### `_execute_with_validation`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `cwd` (Path | str | None):
- `env` (dict[(str, str)] | None):
- `timeout` (float | None):
- `input_data` (str | bytes | None):
- `capture_output` (bool):
- `text` (bool):
- `check` (bool):
- `kwargs` (dict[(str, t.Any)]):
- `start_time` (float):
  **Returns:** subprocess.CompletedProcess[str]

#### `_prepare_execution_params`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `cwd` (Path | str | None):
- `env` (dict[(str, str)] | None):
- `timeout` (float | None):
  **Returns:** dict[(str, t.Any)]

#### `_execute_subprocess`

**Parameters:**

- `self` ():
- `params` (dict[(str, t.Any)]):
- `input_data` (str | bytes | None):
- `capture_output` (bool):
- `text` (bool):
- `check` (bool):
- `kwargs` (dict[(str, t.Any)]):
  **Returns:** subprocess.CompletedProcess[str]

#### `_log_successful_execution`

**Parameters:**

- `self` ():
- `params` (dict[(str, t.Any)]):
- `result` (subprocess.CompletedProcess[str]):
- `start_time` (float):
  **Returns:** None

#### `_handle_timeout_error`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `timeout` (float | None):
- `start_time` (float):
  **Returns:** None

#### `_handle_process_error`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `error` (subprocess.CalledProcessError):
  **Returns:** None

#### `_handle_unexpected_error`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `error` (Exception):
  **Returns:** None

#### `_validate_command`

**Parameters:**

- `self` ():
- `command` (list[str]):
  **Returns:** list[str]

#### `_validate_command_structure`

**Parameters:**

- `self` ():
- `command` (list[str]):
  **Returns:** None

#### `_validate_command_arguments`

**Parameters:**

- `self` ():
- `command` (list[str]):
  **Returns:** tuple\[(list[str], list[str])\]

#### `_has_dangerous_patterns`

**Parameters:**

- `self` ():
- `arg` (str):
- `index` (int):
- `issues` (list[str]):
  **Returns:** bool

#### `_validate_executable_permissions`

**Parameters:**

- `self` ():
- `validated_command` (list[str]):
- `issues` (list[str]):
  **Returns:** None

#### `_handle_validation_results`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `issues` (list[str]):
  **Returns:** None

#### `_validate_cwd`

**Parameters:**

- `self` ():
- `cwd` (Path | str | None):
  **Returns:** Path | None

#### `_sanitize_environment`

**Parameters:**

- `self` ():
- `env` (dict[(str, str)] | None):
  **Returns:** dict[(str, str)]

#### `_validate_environment_size`

**Parameters:**

- `self` ():
- `env` (dict[(str, str)]):
  **Returns:** None

#### `_filter_environment_variables`

**Parameters:**

- `self` ():
- `env` (dict[(str, str)]):
- `filtered_vars` (list[str]):
  **Returns:** dict[(str, str)]

#### `_is_dangerous_environment_key`

**Parameters:**

- `self` ():
- `key` (str):
- `value` (str):
- `filtered_vars` (list[str]):
  **Returns:** bool

#### `_is_environment_value_too_long`

**Parameters:**

- `self` ():
- `key` (str):
- `value` (str):
- `filtered_vars` (list[str]):
  **Returns:** bool

#### `_has_environment_injection`

**Parameters:**

- `self` ():
- `key` (str):
- `value` (str):
- `filtered_vars` (list[str]):
  **Returns:** bool

#### `_add_safe_environment_variables`

**Parameters:**

- `self` ():
- `sanitized_env` (dict[(str, str)]):
  **Returns:** None

#### `_log_environment_sanitization`

**Parameters:**

- `self` ():
- `original_count` (int):
- `sanitized_count` (int):
- `filtered_vars` (list[str]):
  **Returns:** None

#### `_validate_timeout`

**Parameters:**

- `self` ():
- `timeout` (float | None):
  **Returns:** float | None

## contextual_ai_assistant

**Path:** `crackerjack/services/contextual_ai_assistant.py`

## AIRecommendation

**Base Classes:** None

### Methods

No methods defined.

## ProjectContext

**Base Classes:** None

### Methods

No methods defined.

## ContextualAIAssistant

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `filesystem` (FileSystemInterface):
- `console` (Console | None):
  **Returns:** None

#### `get_contextual_recommendations`

**Parameters:**

- `self` ():
- `max_recommendations` (int):
  **Returns:** list[AIRecommendation]

#### `_analyze_project_context`

**Parameters:**

- `self` ():
  **Returns:** ProjectContext

#### `_generate_recommendations`

**Parameters:**

- `self` ():
- `context` (ProjectContext):
  **Returns:** list[AIRecommendation]

#### `_get_testing_recommendations`

**Parameters:**

- `self` ():
- `context` (ProjectContext):
  **Returns:** list[AIRecommendation]

#### `_get_code_quality_recommendations`

**Parameters:**

- `self` ():
- `context` (ProjectContext):
  **Returns:** list[AIRecommendation]

#### `_get_security_recommendations`

**Parameters:**

- `self` ():
- `context` (ProjectContext):
  **Returns:** list[AIRecommendation]

#### `_get_maintenance_recommendations`

**Parameters:**

- `self` ():
- `context` (ProjectContext):
  **Returns:** list[AIRecommendation]

#### `_get_workflow_recommendations`

**Parameters:**

- `self` ():
- `context` (ProjectContext):
  **Returns:** list[AIRecommendation]

#### `_get_documentation_recommendations`

**Parameters:**

- `self` ():
- `context` (ProjectContext):
  **Returns:** list[AIRecommendation]

#### `_has_test_directory`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_get_current_coverage`

**Parameters:**

- `self` ():
  **Returns:** float

#### `_count_current_lint_errors`

**Parameters:**

- `self` ():
  **Returns:** int

#### `_determine_project_size`

**Parameters:**

- `self` ():
  **Returns:** str

#### `_detect_main_languages`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `_has_ci_cd_config`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_has_documentation`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_determine_project_type`

**Parameters:**

- `self` ():
  **Returns:** str

#### `_days_since_last_commit`

**Parameters:**

- `self` ():
  **Returns:** int

#### `_detect_security_issues`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `_get_outdated_dependencies`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `display_recommendations`

**Parameters:**

- `self` ():
- `recommendations` (list[AIRecommendation]):
  **Returns:** None

#### `get_quick_help`

**Parameters:**

- `self` ():
- `query` (str):
  **Returns:** str

## smart_scheduling

**Path:** `crackerjack/services/smart_scheduling.py`

## SmartSchedulingService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `project_path` (Path):
  **Returns:** None

#### `should_scheduled_init`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `record_init_timestamp`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_check_weekly_schedule`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_check_commit_based_schedule`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_check_activity_based_schedule`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_get_last_init_timestamp`

**Parameters:**

- `self` ():
  **Returns:** datetime

#### `_count_commits_since_init`

**Parameters:**

- `self` ():
  **Returns:** int

#### `_has_recent_activity`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_days_since_init`

**Parameters:**

- `self` ():
  **Returns:** int

## security_logger

**Path:** `crackerjack/services/security_logger.py`

## SecurityEventType

**Base Classes:** str, Enum

### Methods

No methods defined.

## SecurityEventLevel

**Base Classes:** str, Enum

### Methods

No methods defined.

## SecurityEvent

**Base Classes:** BaseModel

### Methods

#### `to_dict`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## SecurityLogger

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `logger_name` (str):

#### `_setup_security_logger`

**Parameters:**

- `self` ():
  **Returns:** None

#### `log_security_event`

**Parameters:**

- `self` ():
- `event_type` (SecurityEventType):
- `level` (SecurityEventLevel):
- `message` (str):
- `file_path` (Path | str | None):
- `user_id` (str | None):
- `session_id` (str | None):
  **Returns:** None

#### `_get_logging_level`

**Parameters:**

- `self` ():
- `level` (SecurityEventLevel):
  **Returns:** int

#### `log_path_traversal_attempt`

**Parameters:**

- `self` ():
- `attempted_path` (Path | str):
- `base_directory` (Path | str | None):
  **Returns:** None

#### `log_file_size_exceeded`

**Parameters:**

- `self` ():
- `file_path` (Path | str):
- `file_size` (int):
- `max_size` (int):
  **Returns:** None

#### `log_dangerous_path_detected`

**Parameters:**

- `self` ():
- `path` (Path | str):
- `dangerous_component` (str):
  **Returns:** None

#### `log_backup_created`

**Parameters:**

- `self` ():
- `original_path` (Path | str):
- `backup_path` (Path | str):
  **Returns:** None

#### `log_file_cleaned`

**Parameters:**

- `self` ():
- `file_path` (Path | str):
- `steps_completed` (list[str]):
  **Returns:** None

#### `log_atomic_operation`

**Parameters:**

- `self` ():
- `operation` (str):
- `file_path` (Path | str):
- `success` (bool):
  **Returns:** None

#### `log_validation_failed`

**Parameters:**

- `self` ():
- `validation_type` (str):
- `file_path` (Path | str):
- `reason` (str):
  **Returns:** None

#### `log_temp_file_created`

**Parameters:**

- `self` ():
- `temp_path` (Path | str):
- `purpose` (str):
  **Returns:** None

#### `log_rate_limit_exceeded`

**Parameters:**

- `self` ():
- `limit_type` (str):
- `current_count` (int):
- `max_allowed` (int):
  **Returns:** None

#### `log_subprocess_execution`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `cwd` (str | None):
- `env_vars_count` (int):
  **Returns:** None

#### `log_subprocess_environment_sanitized`

**Parameters:**

- `self` ():
- `original_count` (int):
- `sanitized_count` (int):
- `filtered_vars` (list[str]):
  **Returns:** None

#### `log_subprocess_command_validation`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `validation_result` (bool):
- `issues` (list[str] | None):
  **Returns:** None

#### `log_subprocess_timeout`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `timeout_seconds` (float):
- `actual_duration` (float):
  **Returns:** None

#### `log_subprocess_failure`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `exit_code` (int):
- `error_output` (str):
  **Returns:** None

#### `log_dangerous_command_blocked`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `reason` (str):
- `dangerous_patterns` (list[str]):
  **Returns:** None

#### `log_environment_variable_filtered`

**Parameters:**

- `self` ():
- `variable_name` (str):
- `reason` (str):
- `value_preview` (str | None):
  **Returns:** None

#### `log_status_access_attempt`

**Parameters:**

- `self` ():
- `endpoint` (str):
- `verbosity_level` (str):
- `user_context` (str | None):
- `data_keys` (list[str] | None):
  **Returns:** None

#### `log_sensitive_data_sanitized`

**Parameters:**

- `self` ():
- `data_type` (str):
- `sanitization_count` (int):
- `verbosity_level` (str):
- `patterns_matched` (list[str] | None):
  **Returns:** None

#### `log_status_information_disclosure`

**Parameters:**

- `self` ():
- `disclosure_type` (str):
- `sensitive_info` (str):
- `endpoint` (str):
- `severity` (str):
  **Returns:** None

## intelligent_commit

**Path:** `crackerjack/services/intelligent_commit.py`

## CommitMessageGenerator

Generate intelligent commit messages based on changes and context.

**Base Classes:** None

### Methods

#### `__init__`

Initialize commit message generator.
**Parameters:**

- `self` ():
- `console` (Console):
- `git_service` (GitService):
  **Returns:** None

#### `generate_commit_message`

Generate an intelligent commit message based on staged changes.
**Parameters:**

- `self` ():
- `include_body` (bool):
- `conventional_commits` (bool):
  **Returns:** str

#### `_analyze_changes`

Analyze staged files to understand the nature of changes.
**Parameters:**

- `self` ():
- `staged_files` (list[str]):
  **Returns:** dict[(str, t.Any)]

#### `_determine_commit_type`

Determine the most appropriate commit type.
**Parameters:**

- `self` ():
- `analysis` (dict[(str, t.Any)]):
  **Returns:** str

#### `_determine_scope`

Determine an appropriate scope for the commit.
**Parameters:**

- `self` ():
- `analysis` (dict[(str, t.Any)]):
  **Returns:** str | None

#### `_generate_subject`

Generate a descriptive subject line.
**Parameters:**

- `self` ():
- `analysis` (dict[(str, t.Any)]):
  **Returns:** str

#### `_build_conventional_header`

Build conventional commit header format.
**Parameters:**

- `self` ():
- `commit_type` (str):
- `scope` (str | None):
- `subject` (str):
  **Returns:** str

#### `_generate_body`

Generate detailed commit body.
**Parameters:**

- `self` ():
- `analysis` (dict[(str, t.Any)]):
  **Returns:** str

#### `commit_with_generated_message`

Generate commit message and create commit.
**Parameters:**

- `self` ():
- `include_body` (bool):
- `conventional_commits` (bool):
- `dry_run` (bool):
  **Returns:** bool

## initialization

**Path:** `crackerjack/services/initialization.py`

## InitializationService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `filesystem` (FileSystemService):
- `git_service` (GitService):
- `pkg_path` (Path):
- `config_merge_service` (ConfigMergeServiceProtocol | None):
  **Returns:** None

#### `initialize_project`

**Parameters:**

- `self` ():
- `project_path` (str | Path):
  **Returns:** bool

#### `setup_git_hooks`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `validate_project_structure`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `initialize_project_full`

**Parameters:**

- `self` ():
- `target_path` (Path | None):
- `force` (bool):
  **Returns:** dict[(str, t.Any)]

#### `_create_results_dict`

**Parameters:**

- `self` ():
- `target_path` (Path):
  **Returns:** dict[(str, t.Any)]

#### `_get_config_files`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, str)]

#### `_process_config_file`

**Parameters:**

- `self` ():
- `file_name` (str):
- `merge_strategy` (str):
- `project_name` (str):
- `target_path` (Path):
- `force` (bool):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_should_copy_file`

**Parameters:**

- `self` ():
- `target_file` (Path):
- `force` (bool):
- `file_name` (str):
- `results` (dict[(str, t.Any)]):
  **Returns:** bool

#### `_read_and_process_content`

**Parameters:**

- `self` ():
- `source_file` (Path):
- `should_replace` (bool):
- `project_name` (str):
  **Returns:** str

#### `_write_file_and_track`

**Parameters:**

- `self` ():
- `target_file` (Path):
- `content` (str):
- `file_name` (str):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_skip_existing_file`

**Parameters:**

- `self` ():
- `file_name` (str):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_handle_missing_source_file`

**Parameters:**

- `self` ():
- `file_name` (str):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_handle_file_processing_error`

**Parameters:**

- `self` ():
- `file_name` (str):
- `error` (Exception):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_print_summary`

**Parameters:**

- `self` ():
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_handle_initialization_error`

**Parameters:**

- `self` ():
- `results` (dict[(str, t.Any)]):
- `error` (Exception):
  **Returns:** None

#### `check_uv_installed`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_process_mcp_config`

**Parameters:**

- `self` ():
- `target_path` (Path):
- `force` (bool):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_merge_mcp_config`

**Parameters:**

- `self` ():
- `target_file` (Path):
- `crackerjack_servers` (dict[(str, t.Any)]):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_write_mcp_config_and_track`

**Parameters:**

- `self` ():
- `target_file` (Path):
- `config` (dict[(str, t.Any)]):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_generate_project_claude_content`

**Parameters:**

- `self` ():
- `project_name` (str):
  **Returns:** str

#### `_smart_append_config`

**Parameters:**

- `self` ():
- `source_file` (Path):
- `target_file` (Path):
- `file_name` (str):
- `project_name` (str):
- `force` (bool):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_smart_merge_gitignore`

**Parameters:**

- `self` ():
- `target_file` (Path):
- `project_name` (str):
- `force` (bool):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_smart_merge_config`

**Parameters:**

- `self` ():
- `source_file` (Path):
- `target_file` (Path):
- `file_name` (str):
- `project_name` (str):
- `force` (bool):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_smart_merge_pyproject`

**Parameters:**

- `self` ():
- `source_file` (Path):
- `target_file` (Path):
- `project_name` (str):
- `force` (bool):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_smart_merge_pre_commit_config`

**Parameters:**

- `self` ():
- `source_file` (Path):
- `target_file` (Path):
- `project_name` (str):
- `force` (bool):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_load_source_config`

**Parameters:**

- `self` ():
- `source_file` (Path):
  **Returns:** dict[(str, t.Any)] | None

#### `_perform_config_merge`

**Parameters:**

- `self` ():
- `source_config` (dict[(str, t.Any)]):
- `target_file` (Path):
- `project_name` (str):
  **Returns:** dict[(str, t.Any)]

#### `_should_skip_merge`

**Parameters:**

- `self` ():
- `target_file` (Path):
- `merged_config` (dict[(str, t.Any)]):
- `results` (dict[(str, t.Any)]):
  **Returns:** bool

#### `_write_and_finalize_config`

**Parameters:**

- `self` ():
- `merged_config` (dict[(str, t.Any)]):
- `target_file` (Path):
- `source_config` (dict[(str, t.Any)]):
- `results` (dict[(str, t.Any)]):
  **Returns:** None

#### `_git_add_config_file`

**Parameters:**

- `self` ():
- `target_file` (Path):
  **Returns:** None

#### `_display_merge_success`

**Parameters:**

- `self` ():
- `source_config` (dict[(str, t.Any)]):
  **Returns:** None

## status_authentication

**Path:** `crackerjack/services/status_authentication.py`

## AccessLevel

**Base Classes:** str, Enum

### Methods

No methods defined.

## AuthenticationMethod

**Base Classes:** str, Enum

### Methods

No methods defined.

## AuthCredentials

**Base Classes:** None

### Methods

#### `is_expired`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `has_operation_access`

**Parameters:**

- `self` ():
- `operation` (str):
  **Returns:** bool

## AuthenticationError

**Base Classes:** Exception

### Methods

No methods defined.

## AccessDeniedError

**Base Classes:** AuthenticationError

### Methods

No methods defined.

## ExpiredCredentialsError

**Base Classes:** AuthenticationError

### Methods

No methods defined.

## StatusAuthenticator

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `secret_key` (str | None):
- `default_access_level` (AccessLevel):
- `enable_local_only` (bool):

#### `_generate_secret_key`

**Parameters:**

- `self` ():
  **Returns:** str

#### `_initialize_default_keys`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_generate_api_key`

**Parameters:**

- `self` ():
- `prefix` (str):
  **Returns:** str

#### `authenticate_request`

**Parameters:**

- `self` ():
- `auth_header` (str | None):
- `client_ip` (str | None):
- `operation` (str):
  **Returns:** AuthCredentials

#### `_parse_auth_header`

**Parameters:**

- `self` ():
- `auth_header` (str):
- `operation` (str):
  **Returns:** AuthCredentials

#### `_validate_api_key`

**Parameters:**

- `self` ():
- `api_key` (str):
- `operation` (str):
  **Returns:** AuthCredentials

#### `_validate_jwt_token`

**Parameters:**

- `self` ():
- `token` (str):
- `operation` (str):
  **Returns:** AuthCredentials

#### `_validate_hmac_signature`

**Parameters:**

- `self` ():
- `signature_data` (str):
- `operation` (str):
  **Returns:** AuthCredentials

#### `_validate_credentials`

**Parameters:**

- `self` ():
- `credentials` (AuthCredentials):
- `operation` (str):
  **Returns:** None

#### `_check_operation_access`

**Parameters:**

- `self` ():
- `credentials` (AuthCredentials):
- `operation` (str):
  **Returns:** None

#### `_has_sufficient_access_level`

**Parameters:**

- `self` ():
- `user_level` (AccessLevel):
- `required_level` (AccessLevel):
  **Returns:** bool

#### `is_operation_allowed`

**Parameters:**

- `self` ():
- `operation` (str):
- `access_level` (AccessLevel):
  **Returns:** bool

#### `add_api_key`

**Parameters:**

- `self` ():
- `client_id` (str):
- `access_level` (AccessLevel):
- `expires_at` (float | None):
- `allowed_operations` (set[str] | None):
  **Returns:** str

#### `revoke_api_key`

**Parameters:**

- `self` ():
- `api_key` (str):
  **Returns:** bool

#### `get_auth_status`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## status_security_manager

**Path:** `crackerjack/services/status_security_manager.py`

## StatusSecurityError

**Base Classes:** Exception

### Methods

No methods defined.

## AccessDeniedError

**Base Classes:** StatusSecurityError

### Methods

No methods defined.

## ResourceLimitExceededError

**Base Classes:** StatusSecurityError

### Methods

No methods defined.

## RateLimitExceededError

**Base Classes:** StatusSecurityError

### Methods

No methods defined.

## StatusSecurityManager

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `max_concurrent_requests` (int):
- `rate_limit_per_minute` (int):
- `max_resource_usage_mb` (int):
- `allowed_paths` (set[str] | None):

#### `validate_request`

**Parameters:**

- `self` ():
- `client_id` (str):
- `operation` (str):
- `request_data` (dict[(str, t.Any)] | None):
  **Returns:** None

#### `_check_rate_limit`

**Parameters:**

- `self` ():
- `client_id` (str):
- `operation` (str):
  **Returns:** None

#### `_validate_request_data`

**Parameters:**

- `self` ():
- `client_id` (str):
- `operation` (str):
- `request_data` (dict[(str, t.Any)]):
  **Returns:** None

#### `_contains_path_traversal`

**Parameters:**

- `self` ():
- `value` (str):
  **Returns:** bool

#### `_validate_file_path`

**Parameters:**

- `self` ():
- `client_id` (str):
- `operation` (str):
- `file_path` (str):
  **Returns:** None

#### `_release_request_lock`

**Parameters:**

- `self` ():
- `request_id` (str):
- `client_id` (str):
- `operation` (str):
  **Returns:** None

#### `get_security_status`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## RequestLock

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `security_manager` (StatusSecurityManager):
- `request_id` (str):
- `client_id` (str):
- `operation` (str):

## thread_safe_status_collector

**Path:** `crackerjack/services/thread_safe_status_collector.py`

## StatusSnapshot

**Base Classes:** None

### Methods

No methods defined.

## ThreadSafeStatusCollector

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `timeout` (float):

#### `_build_server_stats_safe`

**Parameters:**

- `self` ():
- `context` (t.Any):
  **Returns:** dict[(str, t.Any)]

#### `_get_cached_data`

**Parameters:**

- `self` ():
- `key` (str):
  **Returns:** dict[(str, t.Any)] | None

#### `_set_cached_data`

**Parameters:**

- `self` ():
- `key` (str):
- `data` (dict[(str, t.Any)]):
  **Returns:** None

#### `clear_cache`

**Parameters:**

- `self` ():
  **Returns:** None

#### `get_collection_status`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## pattern_detector

**Path:** `crackerjack/services/pattern_detector.py`

## AntiPatternConfig

**Base Classes:** t.TypedDict

### Methods

No methods defined.

## AntiPattern

**Base Classes:** None

### Methods

No methods defined.

## PatternDetector

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `project_path` (Path):
- `pattern_cache` (PatternCache):
  **Returns:** None

#### `_check_hardcoded_paths`

**Parameters:**

- `self` ():
- `file_path` (Path):
- `content` (str):
  **Returns:** list[AntiPattern]

#### `_check_subprocess_security`

**Parameters:**

- `self` ():
- `file_path` (Path):
- `tree` (ast.AST):
  **Returns:** list[AntiPattern]

#### `_should_skip_file`

**Parameters:**

- `self` ():
- `file_path` (Path):
  **Returns:** bool

#### `_generate_solution_key`

**Parameters:**

- `self` ():
- `anti_pattern` (AntiPattern):
  **Returns:** str

#### `_find_cached_pattern_for_anti_pattern`

**Parameters:**

- `self` ():
- `anti_pattern` (AntiPattern):
  **Returns:** CachedPattern | None

#### `_map_anti_pattern_to_issue_type`

**Parameters:**

- `self` ():
- `pattern_type` (str):
  **Returns:** IssueType | None

#### `_create_temp_issue_for_lookup`

**Parameters:**

- `self` ():
- `anti_pattern` (AntiPattern):
- `issue_type` (IssueType):
  **Returns:** Issue

## ComplexityVisitor

**Base Classes:** ast.NodeVisitor

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `visit_FunctionDef`

**Parameters:**

- `self` ():
- `node` (ast.FunctionDef):
  **Returns:** None

## PerformanceVisitor

**Base Classes:** ast.NodeVisitor

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `visit_For`

**Parameters:**

- `self` ():
- `node` (ast.For):
  **Returns:** None

## SecurityVisitor

**Base Classes:** ast.NodeVisitor

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `visit_Call`

**Parameters:**

- `self` ():
- `node` (ast.Call):
  **Returns:** None

## ImportVisitor

**Base Classes:** ast.NodeVisitor

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `visit_Import`

**Parameters:**

- `self` ():
- `node` (ast.Import):
  **Returns:** None

#### `visit_ImportFrom`

**Parameters:**

- `self` ():
- `node` (ast.ImportFrom):
  **Returns:** None

## debug

**Path:** `crackerjack/services/debug.py`

## AIAgentDebugger

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `enabled` (bool):
- `verbose` (bool):
  **Returns:** None

#### `_ensure_debug_logging_setup`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_setup_debug_logging`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_print_debug_header`

**Parameters:**

- `self` ():
  **Returns:** None

#### `debug_operation`

**Parameters:**

- `self` ():
- `operation` (str):
  **Returns:** t.Iterator[str]

#### `log_mcp_operation`

**Parameters:**

- `self` ():
- `operation_type` (str):
- `tool_name` (str):
- `params` (dict[(str, Any)] | None):
- `result` (dict[(str, Any)] | None):
- `error` (str | None):
- `duration` (float | None):
  **Returns:** None

#### `log_agent_activity`

**Parameters:**

- `self` ():
- `agent_name` (str):
- `activity` (str):
- `issue_id` (str | None):
- `confidence` (float | None):
- `result` (dict[(str, Any)] | None):
- `metadata` (dict[(str, Any)] | None):
  **Returns:** None

#### `log_workflow_phase`

**Parameters:**

- `self` ():
- `phase` (str):
- `status` (str):
- `details` (dict[(str, Any)] | None):
- `duration` (float | None):
  **Returns:** None

#### `log_error_event`

**Parameters:**

- `self` ():
- `error_type` (str):
- `message` (str):
- `context` (dict[(str, Any)] | None):
- `traceback_info` (str | None):
  **Returns:** None

#### `print_debug_summary`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_print_iteration_breakdown`

**Parameters:**

- `self` ():
- `border_style` (str):
  **Returns:** None

#### `_print_agent_activity_breakdown`

**Parameters:**

- `self` ():
- `border_style` (str):
  **Returns:** None

#### `_print_total_statistics`

**Parameters:**

- `self` ():
- `border_style` (str):
  **Returns:** None

#### `_print_mcp_operation_breakdown`

**Parameters:**

- `self` ():
- `border_style` (str):
  **Returns:** None

#### `log_iteration_start`

**Parameters:**

- `self` ():
- `iteration_number` (int):
  **Returns:** None

#### `log_iteration_end`

**Parameters:**

- `self` ():
- `iteration_number` (int):
- `success` (bool):
  **Returns:** None

#### `log_test_failures`

**Parameters:**

- `self` ():
- `count` (int):
  **Returns:** None

#### `log_test_fixes`

**Parameters:**

- `self` ():
- `count` (int):
  **Returns:** None

#### `log_hook_failures`

**Parameters:**

- `self` ():
- `count` (int):
  **Returns:** None

#### `log_hook_fixes`

**Parameters:**

- `self` ():
- `count` (int):
  **Returns:** None

#### `set_workflow_success`

**Parameters:**

- `self` ():
- `success` (bool):
  **Returns:** None

#### `export_debug_data`

**Parameters:**

- `self` ():
- `output_path` (Path | None):
  **Returns:** Path

## NoOpDebugger

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `debug_operation`

**Parameters:**

- `self` ():
- `operation` (str):
  **Returns:** t.Iterator[str]

#### `log_mcp_operation`

**Parameters:**

- `self` ():
- `operation_type` (str):
- `tool_name` (str):
- `params` (dict[(str, Any)] | None):
- `result` (dict[(str, Any)] | None):
- `error` (str | None):
- `duration` (float | None):
  **Returns:** None

#### `log_agent_activity`

**Parameters:**

- `self` ():
- `agent_name` (str):
- `activity` (str):
- `issue_id` (str | None):
- `confidence` (float | None):
- `result` (dict[(str, Any)] | None):
- `metadata` (dict[(str, Any)] | None):
  **Returns:** None

#### `log_workflow_phase`

**Parameters:**

- `self` ():
- `phase` (str):
- `status` (str):
- `details` (dict[(str, Any)] | None):
- `duration` (float | None):
  **Returns:** None

#### `log_error_event`

**Parameters:**

- `self` ():
- `error_type` (str):
- `message` (str):
- `context` (dict[(str, Any)] | None):
- `traceback_info` (str | None):
  **Returns:** None

#### `print_debug_summary`

**Parameters:**

- `self` ():
  **Returns:** None

#### `export_debug_data`

**Parameters:**

- `self` ():
- `output_path` (Path | None):
  **Returns:** Path

#### `log_iteration_start`

**Parameters:**

- `self` ():
- `iteration_number` (int):
  **Returns:** None

#### `log_iteration_end`

**Parameters:**

- `self` ():
- `iteration_number` (int):
- `success` (bool):
  **Returns:** None

#### `log_test_failures`

**Parameters:**

- `self` ():
- `count` (int):
  **Returns:** None

#### `log_test_fixes`

**Parameters:**

- `self` ():
- `count` (int):
  **Returns:** None

#### `log_hook_failures`

**Parameters:**

- `self` ():
- `count` (int):
  **Returns:** None

#### `log_hook_fixes`

**Parameters:**

- `self` ():
- `count` (int):
  **Returns:** None

#### `set_workflow_success`

**Parameters:**

- `self` ():
- `success` (bool):
  **Returns:** None

## secure_status_formatter

**Path:** `crackerjack/services/secure_status_formatter.py`

## StatusVerbosity

**Base Classes:** str, Enum

### Methods

No methods defined.

## SecureStatusFormatter

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `project_root` (Path | None):

#### `format_status`

**Parameters:**

- `self` ():
- `status_data` (dict[(str, t.Any)]):
- `verbosity` (StatusVerbosity):
- `user_context` (str | None):
  **Returns:** dict[(str, t.Any)]

#### `_log_status_access`

**Parameters:**

- `self` ():
- `status_data` (dict[(str, t.Any)]):
- `verbosity` (StatusVerbosity):
- `user_context` (str | None):
  **Returns:** None

#### `_prepare_data_for_sanitization`

**Parameters:**

- `self` ():
- `status_data` (dict[(str, t.Any)]):
  **Returns:** dict[(str, t.Any)]

#### `_apply_all_sanitization_steps`

**Parameters:**

- `self` ():
- `data` (dict[(str, t.Any)]):
- `verbosity` (StatusVerbosity):
  **Returns:** dict[(str, t.Any)]

#### `_add_security_metadata`

**Parameters:**

- `self` ():
- `data` (dict[(str, t.Any)]):
- `verbosity` (StatusVerbosity):
  **Returns:** dict[(str, t.Any)]

#### `_apply_verbosity_filter`

**Parameters:**

- `self` ():
- `data` (dict[(str, t.Any)]):
- `verbosity` (StatusVerbosity):
  **Returns:** dict[(str, t.Any)]

#### `_sanitize_sensitive_data`

**Parameters:**

- `self` ():
- `data` (dict[(str, t.Any)]):
- `verbosity` (StatusVerbosity):
  **Returns:** dict[(str, t.Any)]

#### `_sanitize_recursive`

**Parameters:**

- `self` ():
- `obj` (t.Any):
- `verbosity` (StatusVerbosity):
  **Returns:** t.Any

#### `_sanitize_string`

**Parameters:**

- `self` ():
- `text` (str):
- `verbosity` (StatusVerbosity):
  **Returns:** str

#### `_apply_string_sanitization_pipeline`

**Parameters:**

- `self` ():
- `text` (str):
- `verbosity` (StatusVerbosity):
  **Returns:** str

#### `_apply_secret_masking_if_needed`

**Parameters:**

- `self` ():
- `text` (str):
- `verbosity` (StatusVerbosity):
  **Returns:** str

#### `_sanitize_paths`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** str

#### `_sanitize_paths_fallback`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** str

#### `_process_path_pattern`

**Parameters:**

- `self` ():
- `text` (str):
- `pattern_str` (str):
  **Returns:** str

#### `_replace_path_match`

**Parameters:**

- `self` ():
- `text` (str):
- `match` (str):
  **Returns:** str

#### `_convert_to_relative_or_redact`

**Parameters:**

- `self` ():
- `text` (str):
- `match` (str):
- `abs_path` (Path):
  **Returns:** str

#### `_sanitize_internal_urls`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** str

#### `_mask_potential_secrets`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** str

#### `_should_skip_secret_masking`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** bool

#### `_get_validated_secret_patterns`

**Parameters:**

- `self` ():
  **Returns:** list[t.Any]

#### `_apply_validated_secret_patterns`

**Parameters:**

- `self` ():
- `text` (str):
- `patterns` (list[t.Any]):
  **Returns:** str

#### `_apply_fallback_secret_patterns`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** str

#### `_mask_pattern_matches`

**Parameters:**

- `self` ():
- `text` (str):
- `matches` (list[str]):
  **Returns:** str

#### `_should_mask_match`

**Parameters:**

- `self` ():
- `match` (str):
  **Returns:** bool

#### `_create_masked_string`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** str

#### `_mask_sensitive_value`

**Parameters:**

- `self` ():
- `value` (str):
  **Returns:** str

#### `_deep_copy_dict`

**Parameters:**

- `self` ():
- `obj` (t.Any):
  **Returns:** t.Any

#### `_get_timestamp`

**Parameters:**

- `self` ():
  **Returns:** float

#### `format_error_response`

**Parameters:**

- `self` ():
- `error_message` (str):
- `verbosity` (StatusVerbosity):
- `include_details` (bool):
  **Returns:** dict[(str, t.Any)]

#### `_create_minimal_error_response`

**Parameters:**

- `self` ():
- `error_type` (str):
  **Returns:** dict[(str, t.Any)]

#### `_create_detailed_error_response`

**Parameters:**

- `self` ():
- `error_message` (str):
- `error_type` (str):
- `verbosity` (StatusVerbosity):
- `include_details` (bool):
  **Returns:** dict[(str, t.Any)]

#### `_should_include_error_details`

**Parameters:**

- `self` ():
- `include_details` (bool):
- `verbosity` (StatusVerbosity):
  **Returns:** bool

#### `_classify_error`

**Parameters:**

- `self` ():
- `error_message` (str):
  **Returns:** str

## performance_cache

**Path:** `crackerjack/services/performance_cache.py`

## CacheEntry

**Base Classes:** None

### Methods

#### `is_expired`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `access`

**Parameters:**

- `self` ():
  **Returns:** t.Any

## CacheStats

**Base Classes:** None

### Methods

#### `hit_ratio`

**Parameters:**

- `self` ():
  **Returns:** float

## PerformanceCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `max_memory_mb` (int):
- `default_ttl_seconds` (int):
- `cleanup_interval_seconds` (int):

#### `get`

**Parameters:**

- `self` ():
- `key` (str):
- `default` (t.Any):
  **Returns:** t.Any

#### `set`

**Parameters:**

- `self` ():
- `key` (str):
- `value` (t.Any):
- `ttl_seconds` (int | None):
- `invalidation_keys` (set[str] | None):
  **Returns:** None

#### `invalidate`

**Parameters:**

- `self` ():
- `invalidation_key` (str):
  **Returns:** int

#### `clear`

**Parameters:**

- `self` ():
  **Returns:** None

#### `get_stats`

**Parameters:**

- `self` ():
  **Returns:** CacheStats

#### `_estimate_memory_usage`

**Parameters:**

- `self` ():
  **Returns:** int

#### `_check_memory_pressure`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_evict_lru_entries`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_cleanup_expired_entries`

**Parameters:**

- `self` ():
  **Returns:** None

## GitOperationCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache` (PerformanceCache):

#### `_make_repo_key`

**Parameters:**

- `self` ():
- `repo_path` (Path):
- `operation` (str):
- `params` (str):
  **Returns:** str

#### `get_branch_info`

**Parameters:**

- `self` ():
- `repo_path` (Path):
  **Returns:** t.Any

#### `set_branch_info`

**Parameters:**

- `self` ():
- `repo_path` (Path):
- `branch_info` (t.Any):
- `ttl_seconds` (int):
  **Returns:** None

#### `get_file_status`

**Parameters:**

- `self` ():
- `repo_path` (Path):
  **Returns:** t.Any

#### `set_file_status`

**Parameters:**

- `self` ():
- `repo_path` (Path):
- `file_status` (t.Any):
- `ttl_seconds` (int):
  **Returns:** None

#### `invalidate_repo`

**Parameters:**

- `self` ():
- `repo_path` (Path):
  **Returns:** None

## FileSystemCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache` (PerformanceCache):

#### `_make_file_key`

**Parameters:**

- `self` ():
- `file_path` (Path):
- `operation` (str):
  **Returns:** str

#### `get_file_stats`

**Parameters:**

- `self` ():
- `file_path` (Path):
  **Returns:** t.Any

#### `set_file_stats`

**Parameters:**

- `self` ():
- `file_path` (Path):
- `stats` (t.Any):
- `ttl_seconds` (int):
  **Returns:** None

#### `invalidate_file`

**Parameters:**

- `self` ():
- `file_path` (Path):
  **Returns:** None

## CommandResultCache

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache` (PerformanceCache):

#### `_make_command_key`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `cwd` (Path | None):
  **Returns:** str

#### `get_command_result`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `cwd` (Path | None):
  **Returns:** t.Any

#### `set_command_result`

**Parameters:**

- `self` ():
- `command` (list[str]):
- `result` (t.Any):
- `cwd` (Path | None):
- `ttl_seconds` (int):
  **Returns:** None

#### `invalidate_commands`

**Parameters:**

- `self` ():
  **Returns:** None

## config_integrity

**Path:** `crackerjack/services/config_integrity.py`

## ConfigIntegrityService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `project_path` (Path):
  **Returns:** None

#### `check_config_integrity`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_check_file_drift`

**Parameters:**

- `self` ():
- `file_path` (Path):
  **Returns:** bool

#### `_has_required_config_sections`

**Parameters:**

- `self` ():
  **Returns:** bool

## parallel_executor

**Path:** `crackerjack/services/parallel_executor.py`

## ExecutionStrategy

**Base Classes:** Enum

### Methods

No methods defined.

## ExecutionGroup

**Base Classes:** None

### Methods

No methods defined.

## ExecutionResult

**Base Classes:** None

### Methods

No methods defined.

## ParallelExecutionResult

**Base Classes:** None

### Methods

#### `success_rate`

**Parameters:**

- `self` ():
  **Returns:** float

#### `overall_success`

**Parameters:**

- `self` ():
  **Returns:** bool

## ParallelHookExecutor

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `max_workers` (int):
- `timeout_seconds` (int):
- `strategy` (ExecutionStrategy):

#### `analyze_hook_dependencies`

**Parameters:**

- `self` ():
- `hooks` (list[HookDefinition]):
  **Returns:** dict\[(str, list[HookDefinition])\]

#### `can_execute_in_parallel`

**Parameters:**

- `self` ():
- `hook1` (HookDefinition):
- `hook2` (HookDefinition):
  **Returns:** bool

#### `_can_parallelize_group`

**Parameters:**

- `self` ():
- `hooks` (list[HookDefinition]):
  **Returns:** bool

## AsyncCommandExecutor

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `max_workers` (int):
- `cache_results` (bool):

#### `__del__`

**Parameters:**

- `self` ():

## tool_version_service

**Path:** `crackerjack/services/tool_version_service.py`

## ToolVersionService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `project_path` (Path | None):
  **Returns:** None

#### `check_config_integrity`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `should_scheduled_init`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `record_init_timestamp`

**Parameters:**

- `self` ():
  **Returns:** None

## memory_optimizer

**Path:** `crackerjack/services/memory_optimizer.py`

## MemoryStats

**Base Classes:** None

### Methods

No methods defined.

## LazyLoader

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `factory` (Callable\[([], Any)\]):
- `name` (str):
- `auto_dispose` (bool):

#### `is_loaded`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `access_count`

**Parameters:**

- `self` ():
  **Returns:** int

#### `get`

**Parameters:**

- `self` ():
  **Returns:** Any

#### `dispose`

**Parameters:**

- `self` ():
  **Returns:** None

#### `__del__`

**Parameters:**

- `self` ():

## ResourcePool

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `factory` (Callable\[([], Any)\]):
- `max_size` (int):
- `name` (str):

#### `acquire`

**Parameters:**

- `self` ():
  **Returns:** Any

#### `release`

**Parameters:**

- `self` ():
- `resource` (Any):
  **Returns:** None

#### `clear`

**Parameters:**

- `self` ():
  **Returns:** None

#### `get_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

## MemoryProfiler

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():

#### `start_profiling`

**Parameters:**

- `self` ():
  **Returns:** None

#### `record_checkpoint`

**Parameters:**

- `self` ():
- `name` (str):
  **Returns:** float

#### `get_summary`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

#### `_get_memory_usage`

**Parameters:**

- `self` ():
  **Returns:** float

## MemoryOptimizer

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():

#### `get_instance`

**Parameters:**

- `cls` ():
  **Returns:** MemoryOptimizer

#### `register_lazy_object`

**Parameters:**

- `self` ():
- `lazy_obj` (LazyLoader):
  **Returns:** None

#### `notify_lazy_load`

**Parameters:**

- `self` ():
- `name` (str):
  **Returns:** None

#### `register_resource_pool`

**Parameters:**

- `self` ():
- `name` (str):
- `pool` (ResourcePool):
  **Returns:** None

#### `get_resource_pool`

**Parameters:**

- `self` ():
- `name` (str):
  **Returns:** ResourcePool | None

#### `start_profiling`

**Parameters:**

- `self` ():
  **Returns:** None

#### `record_checkpoint`

**Parameters:**

- `self` ():
- `name` (str):
  **Returns:** float

#### `get_memory_stats`

**Parameters:**

- `self` ():
  **Returns:** MemoryStats

#### `optimize_memory`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_should_run_gc`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_run_memory_cleanup`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_cleanup_lazy_objects`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_cleanup_resource_pools`

**Parameters:**

- `self` ():
  **Returns:** None

## quality_baseline_enhanced

**Path:** `crackerjack/services/quality_baseline_enhanced.py`

## TrendDirection

Quality trend direction.

**Base Classes:** str, Enum

### Methods

No methods defined.

## AlertSeverity

Alert severity levels.

**Base Classes:** str, Enum

### Methods

No methods defined.

## QualityTrend

Quality trend analysis over time.

**Base Classes:** None

### Methods

#### `to_dict`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## QualityAlert

Quality alert for significant changes.

**Base Classes:** None

### Methods

#### `to_dict`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## QualityReport

Comprehensive quality report.

**Base Classes:** None

### Methods

#### `to_dict`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## EnhancedQualityBaselineService

Enhanced quality baseline service with advanced analytics.

**Base Classes:** QualityBaselineService

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `cache` (CrackerjackCache | None):
- `alert_thresholds` (dict[(str, float)] | None):
  **Returns:** None

#### `analyze_quality_trend`

Analyze quality trend over specified period.
**Parameters:**

- `self` ():
- `days` (int):
- `min_data_points` (int):
  **Returns:** QualityTrend | None

#### `check_quality_alerts`

Check for quality alerts based on thresholds.
**Parameters:**

- `self` ():
- `current_metrics` (dict[(str, t.Any)]):
- `baseline_git_hash` (str | None):
  **Returns:** list[QualityAlert]

#### `generate_recommendations`

Generate actionable recommendations.
**Parameters:**

- `self` ():
- `current_metrics` (dict[(str, t.Any)]):
- `trend` (QualityTrend | None):
- `alerts` (list[QualityAlert]):
  **Returns:** list[str]

#### `generate_comprehensive_report`

Generate comprehensive quality report.
**Parameters:**

- `self` ():
- `current_metrics` (dict[(str, t.Any)] | None):
- `days` (int):
  **Returns:** QualityReport

#### `export_report`

Export quality report to file.
**Parameters:**

- `self` ():
- `report` (QualityReport):
- `output_path` (Path):
- `format` (str):
  **Returns:** None

#### `set_alert_threshold`

Update alert threshold for specific metric.
**Parameters:**

- `self` ():
- `metric` (str):
- `threshold` (float):
  **Returns:** None

#### `get_alert_thresholds`

Get current alert thresholds.
**Parameters:**

- `self` ():
  **Returns:** dict[(str, float)]

## bounded_status_operations

**Path:** `crackerjack/services/bounded_status_operations.py`

## OperationState

**Base Classes:** str, Enum

### Methods

No methods defined.

## OperationLimits

**Base Classes:** None

### Methods

No methods defined.

## OperationMetrics

**Base Classes:** None

### Methods

#### `duration`

**Parameters:**

- `self` ():
  **Returns:** float

#### `is_completed`

**Parameters:**

- `self` ():
  **Returns:** bool

## OperationLimitExceededError

**Base Classes:** Exception

### Methods

No methods defined.

## CircuitBreakerOpenError

**Base Classes:** Exception

### Methods

No methods defined.

## BoundedStatusOperations

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `limits` (OperationLimits | None):

#### `_check_circuit_breaker`

**Parameters:**

- `self` ():
- `operation_type` (str):
  **Returns:** None

#### `_validate_and_reserve_operation`

**Parameters:**

- `self` ():
- `operation_type` (str):
- `client_id` (str):
  **Returns:** str

#### `_record_operation_success`

**Parameters:**

- `self` ():
- `operation_type` (str):
  **Returns:** None

#### `_record_operation_failure`

**Parameters:**

- `self` ():
- `operation_type` (str):
  **Returns:** None

#### `_cleanup_operation`

**Parameters:**

- `self` ():
- `operation_id` (str):
- `metrics` (OperationMetrics):
  **Returns:** None

#### `get_operation_status`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `reset_circuit_breaker`

**Parameters:**

- `self` ():
- `operation_type` (str):
  **Returns:** bool

## secure_path_utils

**Path:** `crackerjack/services/secure_path_utils.py`

## SecurePathValidator

**Base Classes:** None

### Methods

#### `validate_safe_path`

**Parameters:**

- `cls` ():
- `path` (str | Path):
- `base_directory` (Path | None):
  **Returns:** Path

#### `validate_file_path`

**Parameters:**

- `cls` ():
- `file_path` (Path):
- `base_directory` (Path | None):
  **Returns:** Path

#### `secure_path_join`

**Parameters:**

- `cls` ():
- `base` (Path):
  **Returns:** Path

#### `normalize_path`

**Parameters:**

- `cls` ():
- `path` (Path):
  **Returns:** Path

#### `is_within_directory`

**Parameters:**

- `cls` ():
- `path` (Path):
- `directory` (Path):
  **Returns:** bool

#### `safe_resolve`

**Parameters:**

- `cls` ():
- `path` (Path):
- `base_directory` (Path | None):
  **Returns:** Path

#### `_check_malicious_patterns`

**Parameters:**

- `cls` ():
- `path_str` (str):
  **Returns:** None

#### `_validate_resolved_path`

**Parameters:**

- `cls` ():
- `path` (Path):
  **Returns:** None

#### `_check_dangerous_components`

**Parameters:**

- `cls` ():
- `path` (Path):
  **Returns:** None

#### `_validate_within_base_directory`

**Parameters:**

- `cls` ():
- `path` (Path):
- `base_directory` (Path):
  **Returns:** None

#### `validate_file_size`

**Parameters:**

- `cls` ():
- `file_path` (Path):
  **Returns:** None

#### `create_secure_backup_path`

**Parameters:**

- `cls` ():
- `original_path` (Path):
- `base_directory` (Path | None):
  **Returns:** Path

#### `create_secure_temp_file`

**Parameters:**

- `cls` ():
- `suffix` (str):
- `prefix` (str):
- `directory` (Path | None):
- `purpose` (str):
  **Returns:** t.Any

## AtomicFileOperations

**Base Classes:** None

### Methods

#### `atomic_write`

**Parameters:**

- `file_path` (Path):
- `content` (str | bytes):
- `base_directory` (Path | None):
  **Returns:** None

#### `atomic_backup_and_write`

**Parameters:**

- `file_path` (Path):
- `new_content` (str | bytes):
- `base_directory` (Path | None):
  **Returns:** Path

## SubprocessPathValidator

**Base Classes:** None

### Methods

#### `validate_subprocess_cwd`

**Parameters:**

- `cls` ():
- `cwd` (Path | str | None):
  **Returns:** Path | None

#### `validate_executable_path`

**Parameters:**

- `cls` ():
- `executable` (str | Path):
  **Returns:** Path

## performance_benchmarks

**Path:** `crackerjack/services/performance_benchmarks.py`

## BenchmarkResult

**Base Classes:** None

### Methods

#### `time_improvement_percentage`

**Parameters:**

- `self` ():
  **Returns:** float

#### `memory_improvement_percentage`

**Parameters:**

- `self` ():
  **Returns:** float

#### `cache_hit_ratio`

**Parameters:**

- `self` ():
  **Returns:** float

#### `parallelization_ratio`

**Parameters:**

- `self` ():
  **Returns:** float

## BenchmarkSuite

**Base Classes:** None

### Methods

#### `average_time_improvement`

**Parameters:**

- `self` ():
  **Returns:** float

#### `average_memory_improvement`

**Parameters:**

- `self` ():
  **Returns:** float

#### `overall_cache_hit_ratio`

**Parameters:**

- `self` ():
  **Returns:** float

#### `add_result`

**Parameters:**

- `self` ():
- `result` (BenchmarkResult):
  **Returns:** None

## PerformanceBenchmarker

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():

#### `export_benchmark_results`

**Parameters:**

- `self` ():
- `suite` (BenchmarkSuite):
- `output_path` (Path):
  **Returns:** None

## input_validator

**Path:** `crackerjack/services/input_validator.py`

## ValidationConfig

**Base Classes:** BaseModel

### Methods

No methods defined.

## ValidationResult

**Base Classes:** BaseModel

### Methods

No methods defined.

## InputSanitizer

**Base Classes:** None

### Methods

#### `sanitize_string`

**Parameters:**

- `cls` ():
- `value` (t.Any):
- `max_length` (int):
- `allow_shell_chars` (bool):
- `strict_alphanumeric` (bool):
  **Returns:** ValidationResult

#### `_validate_string_type`

**Parameters:**

- `cls` ():
- `value` (t.Any):
  **Returns:** ValidationResult

#### `_validate_string_length`

**Parameters:**

- `cls` ():
- `value` (str):
- `max_length` (int):
  **Returns:** ValidationResult

#### `_validate_string_security`

**Parameters:**

- `cls` ():
- `value` (str):
- `allow_shell_chars` (bool):
  **Returns:** ValidationResult

#### `_validate_string_patterns`

**Parameters:**

- `cls` ():
- `value` (str):
  **Returns:** ValidationResult

#### `_is_strictly_alphanumeric`

**Parameters:**

- `cls` ():
- `value` (str):
  **Returns:** bool

#### `sanitize_json`

**Parameters:**

- `cls` ():
- `value` (str):
- `max_size` (int):
- `max_depth` (int):
  **Returns:** ValidationResult

#### `sanitize_path`

**Parameters:**

- `cls` ():
- `value` (str | Path):
- `base_directory` (Path | None):
- `allow_absolute` (bool):
  **Returns:** ValidationResult

#### `_check_dangerous_components`

**Parameters:**

- `cls` ():
- `path` (Path):
  **Returns:** ValidationResult

#### `_validate_base_directory`

**Parameters:**

- `cls` ():
- `path` (Path):
- `base_directory` (Path):
- `allow_absolute` (bool):
  **Returns:** ValidationResult

#### `_validate_absolute_path`

**Parameters:**

- `cls` ():
- `resolved` (Path):
- `allow_absolute` (bool):
- `base_directory` (Path | None):
  **Returns:** ValidationResult

## SecureInputValidator

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `config` (ValidationConfig | None):

#### `validate_project_name`

**Parameters:**

- `self` ():
- `name` (str):
  **Returns:** ValidationResult

#### `validate_job_id`

**Parameters:**

- `self` ():
- `job_id` (str):
  **Returns:** ValidationResult

#### `validate_command_args`

**Parameters:**

- `self` ():
- `args` (t.Any):
  **Returns:** ValidationResult

#### `validate_json_payload`

**Parameters:**

- `self` ():
- `payload` (str):
  **Returns:** ValidationResult

#### `validate_file_path`

**Parameters:**

- `self` ():
- `path` (str | Path):
- `base_directory` (Path | None):
- `allow_absolute` (bool):
  **Returns:** ValidationResult

#### `validate_environment_var`

**Parameters:**

- `self` ():
- `name` (str):
- `value` (str):
  **Returns:** ValidationResult

#### `_log_validation_failure`

**Parameters:**

- `self` ():
- `validation_type` (str):
- `input_value` (str):
- `reason` (str):
- `level` (SecurityEventLevel):
  **Returns:** None

## unified_config

**Path:** `crackerjack/services/unified_config.py`

## CrackerjackConfig

**Base Classes:** BaseModel

### Methods

#### `validate_package_path`

**Parameters:**

- `cls` ():
- `v` (Any):
  **Returns:** Path

#### `validate_log_file`

**Parameters:**

- `cls` ():
- `v` (Any):
  **Returns:** Path | None

#### `validate_test_workers`

**Parameters:**

- `cls` ():
- `v` (int):
  **Returns:** int

#### `validate_min_coverage`

**Parameters:**

- `cls` ():
- `v` (float):
  **Returns:** float

#### `validate_log_level`

**Parameters:**

- `cls` ():
- `v` (str):
  **Returns:** str

## ConfigSource

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `priority` (int):
  **Returns:** None

#### `load`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `is_available`

**Parameters:**

- `self` ():
  **Returns:** bool

## EnvironmentConfigSource

**Base Classes:** ConfigSource

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `priority` (int):
  **Returns:** None

#### `load`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `_convert_value`

**Parameters:**

- `self` ():
- `value` (str):
  **Returns:** t.Any

## FileConfigSource

**Base Classes:** ConfigSource

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `config_path` (Path):
- `priority` (int):
  **Returns:** None

#### `is_available`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `load`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## PyprojectConfigSource

**Base Classes:** ConfigSource

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `pyproject_path` (Path):
- `priority` (int):
  **Returns:** None

#### `is_available`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `load`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## OptionsConfigSource

**Base Classes:** ConfigSource

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
- `priority` (int):
  **Returns:** None

#### `load`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## UnifiedConfigurationService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
- `options` (OptionsProtocol | None):
  **Returns:** None

#### `_create_default_source`

**Parameters:**

- `self` ():
  **Returns:** ConfigSource

#### `get_config`

**Parameters:**

- `self` ():
- `reload` (bool):
  **Returns:** CrackerjackConfig

#### `_load_unified_config`

**Parameters:**

- `self` ():
  **Returns:** CrackerjackConfig

#### `get_precommit_config_mode`

**Parameters:**

- `self` ():
  **Returns:** str

#### `get_logging_config`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

#### `get_hook_execution_config`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

#### `get_testing_config`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

#### `get_cache_config`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, Any)]

#### `validate_current_config`

**Parameters:**

- `self` ():
  **Returns:** bool

## Config

**Base Classes:** None

### Methods

No methods defined.

## DefaultConfigSource

**Base Classes:** ConfigSource

### Methods

#### `load`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## coverage_ratchet

**Path:** `crackerjack/services/coverage_ratchet.py`

## CoverageRatchetService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `pkg_path` (Path):
- `console` (Console):
  **Returns:** None

#### `initialize_baseline`

**Parameters:**

- `self` ():
- `initial_coverage` (float):
  **Returns:** None

#### `get_ratchet_data`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `get_baseline`

**Parameters:**

- `self` ():
  **Returns:** float

#### `get_baseline_coverage`

**Parameters:**

- `self` ():
  **Returns:** float

#### `update_baseline_coverage`

**Parameters:**

- `self` ():
- `new_coverage` (float):
  **Returns:** bool

#### `is_coverage_regression`

**Parameters:**

- `self` ():
- `current_coverage` (float):
  **Returns:** bool

#### `get_coverage_improvement_needed`

**Parameters:**

- `self` ():
  **Returns:** float

#### `update_coverage`

**Parameters:**

- `self` ():
- `new_coverage` (float):
  **Returns:** dict[(str, t.Any)]

#### `_check_milestones`

**Parameters:**

- `self` ():
- `old_coverage` (float):
- `new_coverage` (float):
- `data` (dict[(str, t.Any)]):
  **Returns:** list[float]

#### `_get_next_milestone`

**Parameters:**

- `self` ():
- `coverage` (float):
  **Returns:** float | None

#### `_update_baseline`

**Parameters:**

- `self` ():
- `new_coverage` (float):
- `data` (dict[(str, t.Any)]):
- `milestones_hit` (list[float]):
  **Returns:** None

#### `_update_pyproject_requirement`

**Parameters:**

- `self` ():
- `new_coverage` (float):
  **Returns:** None

#### `get_progress_visualization`

**Parameters:**

- `self` ():
  **Returns:** str

#### `get_status_report`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `_calculate_trend`

**Parameters:**

- `self` ():
- `data` (dict[(str, t.Any)]):
  **Returns:** str

#### `display_milestone_celebration`

**Parameters:**

- `self` ():
- `milestones` (list[float]):
  **Returns:** None

#### `show_progress_with_spinner`

**Parameters:**

- `self` ():
  **Returns:** None

#### `get_coverage_report`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `check_and_update_coverage`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

## dependency_monitor

**Path:** `crackerjack/services/dependency_monitor.py`

## DependencyVulnerability

**Base Classes:** None

### Methods

No methods defined.

## MajorUpdate

**Base Classes:** None

### Methods

No methods defined.

## DependencyMonitorService

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `filesystem` (FileSystemInterface):
- `console` (Console | None):
  **Returns:** None

#### `check_dependency_updates`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_parse_dependencies`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, str)]

#### `_extract_main_dependencies`

**Parameters:**

- `self` ():
- `project_data` (dict[(str, t.Any)]):
- `dependencies` (dict[(str, str)]):
  **Returns:** None

#### `_extract_optional_dependencies`

**Parameters:**

- `self` ():
- `project_data` (dict[(str, t.Any)]):
- `dependencies` (dict[(str, str)]):
  **Returns:** None

#### `_parse_dependency_spec`

**Parameters:**

- `self` ():
- `spec` (str):
  **Returns:** tuple[(str | None, str | None)]

#### `_check_security_vulnerabilities`

**Parameters:**

- `self` ():
- `dependencies` (dict[(str, str)]):
  **Returns:** list[DependencyVulnerability]

#### `_check_with_safety`

**Parameters:**

- `self` ():
- `dependencies` (dict[(str, str)]):
  **Returns:** list[DependencyVulnerability]

#### `_check_with_pip_audit`

**Parameters:**

- `self` ():
- `dependencies` (dict[(str, str)]):
  **Returns:** list[DependencyVulnerability]

#### `_run_vulnerability_tool`

**Parameters:**

- `self` ():
- `dependencies` (dict[(str, str)]):
- `command_template` (list[str]):
- `parser_func` (t.Callable\[([t.Any], list[DependencyVulnerability])\]):
  **Returns:** list[DependencyVulnerability]

#### `_create_requirements_file`

**Parameters:**

- `self` ():
- `dependencies` (dict[(str, str)]):
  **Returns:** str

#### `_execute_vulnerability_command`

**Parameters:**

- `self` ():
- `command_template` (list[str]):
- `temp_file` (str):
  **Returns:** subprocess.CompletedProcess[str]

#### `_process_vulnerability_result`

**Parameters:**

- `self` ():
- `result` (subprocess.CompletedProcess[str]):
- `parser_func` (t.Callable\[([t.Any], list[DependencyVulnerability])\]):
  **Returns:** list[DependencyVulnerability]

#### `_parse_safety_output`

**Parameters:**

- `self` ():
- `safety_data` (t.Any):
  **Returns:** list[DependencyVulnerability]

#### `_parse_pip_audit_output`

**Parameters:**

- `self` ():
- `audit_data` (t.Any):
  **Returns:** list[DependencyVulnerability]

#### `_check_major_updates`

**Parameters:**

- `self` ():
- `dependencies` (dict[(str, str)]):
  **Returns:** list[MajorUpdate]

#### `_check_package_major_update`

**Parameters:**

- `self` ():
- `package` (str):
- `current_version` (str):
- `cache` (dict[(str, t.Any)]):
- `current_time` (float):
  **Returns:** MajorUpdate | None

#### `_build_cache_key`

**Parameters:**

- `self` ():
- `package` (str):
- `current_version` (str):
  **Returns:** str

#### `_get_cached_major_update`

**Parameters:**

- `self` ():
- `cache_key` (str):
- `cache` (dict[(str, t.Any)]):
- `current_time` (float):
- `package` (str):
- `current_version` (str):
  **Returns:** MajorUpdate | None

#### `_is_cache_entry_valid`

**Parameters:**

- `self` ():
- `cache_key` (str):
- `cache` (dict[(str, t.Any)]):
- `current_time` (float):
  **Returns:** bool

#### `_create_major_update_from_cache`

**Parameters:**

- `self` ():
- `package` (str):
- `current_version` (str):
- `cached_data` (dict[(str, t.Any)]):
  **Returns:** MajorUpdate

#### `_fetch_and_cache_update_info`

**Parameters:**

- `self` ():
- `package` (str):
- `current_version` (str):
- `cache_key` (str):
- `cache` (dict[(str, t.Any)]):
- `current_time` (float):
  **Returns:** MajorUpdate | None

#### `_create_major_update_if_needed`

**Parameters:**

- `self` ():
- `package` (str):
- `current_version` (str):
- `latest_info` (dict[(str, t.Any)]):
- `has_major_update` (bool):
  **Returns:** MajorUpdate | None

#### `_update_cache_entry`

**Parameters:**

- `self` ():
- `cache` (dict[(str, t.Any)]):
- `cache_key` (str):
- `current_time` (float):
- `has_major_update` (bool):
- `latest_info` (dict[(str, t.Any)]):
  **Returns:** None

#### `_get_latest_version_info`

**Parameters:**

- `self` ():
- `package` (str):
  **Returns:** dict[(str, t.Any)] | None

#### `_fetch_pypi_data`

**Parameters:**

- `self` ():
- `package` (str):
  **Returns:** dict[(str, t.Any)]

#### `_validate_pypi_url`

**Parameters:**

- `self` ():
- `url` (str):
  **Returns:** None

#### `_extract_version_info`

**Parameters:**

- `self` ():
- `data` (dict[(str, t.Any)]):
  **Returns:** dict[(str, t.Any)] | None

#### `_get_release_date`

**Parameters:**

- `self` ():
- `releases` (dict[(str, t.Any)]):
- `version` (str):
  **Returns:** str

#### `_has_breaking_changes`

**Parameters:**

- `self` ():
- `version` (str):
  **Returns:** bool

#### `_is_major_version_update`

**Parameters:**

- `self` ():
- `current` (str):
- `latest` (str):
  **Returns:** bool

#### `_should_notify_major_updates`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_load_update_cache`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `_save_update_cache`

**Parameters:**

- `self` ():
- `cache` (dict[(str, t.Any)]):
  **Returns:** None

#### `_report_vulnerabilities`

**Parameters:**

- `self` ():
- `vulnerabilities` (list[DependencyVulnerability]):
  **Returns:** None

#### `_report_major_updates`

**Parameters:**

- `self` ():
- `major_updates` (list[MajorUpdate]):
  **Returns:** None

#### `force_check_updates`

**Parameters:**

- `self` ():
  **Returns:** tuple\[(list[DependencyVulnerability], list[MajorUpdate])\]

## regex_patterns

**Path:** `crackerjack/services/regex_patterns.py`

## CompiledPatternCache

**Base Classes:** None

### Methods

#### `get_compiled_pattern`

**Parameters:**

- `cls` ():
- `pattern` (str):
  **Returns:** Pattern[str]

#### `get_compiled_pattern_with_flags`

**Parameters:**

- `cls` ():
- `cache_key` (str):
- `pattern` (str):
- `flags` (int):
  **Returns:** Pattern[str]

#### `clear_cache`

**Parameters:**

- `cls` ():
  **Returns:** None

#### `get_cache_stats`

**Parameters:**

- `cls` ():
  **Returns:** dict\[(str, int | list[str])\]

## ValidatedPattern

**Base Classes:** None

### Methods

#### `__post_init__`

**Parameters:**

- `self` ():

#### `_validate`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_get_compiled_pattern`

**Parameters:**

- `self` ():
  **Returns:** Pattern[str]

#### `_apply_internal`

**Parameters:**

- `self` ():
- `text` (str):
- `count` (int):
  **Returns:** str

#### `apply`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** str

#### `apply_iteratively`

**Parameters:**

- `self` ():
- `text` (str):
- `max_iterations` (int):
  **Returns:** str

#### `apply_with_timeout`

**Parameters:**

- `self` ():
- `text` (str):
- `timeout_seconds` (float):
  **Returns:** str

#### `test`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** bool

#### `search`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** re.Match[str] | None

#### `findall`

**Parameters:**

- `self` ():
- `text` (str):
  **Returns:** list[str]

#### `get_performance_stats`

**Parameters:**

- `self` ():
- `text` (str):
- `iterations` (int):
  **Returns:** dict[(str, float)]

## Managers

## publish_manager

**Path:** `crackerjack/managers/publish_manager.py`

## PublishManagerImpl

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
- `dry_run` (bool):
- `filesystem` (FileSystemInterface | None):
- `security` (SecurityServiceProtocol | None):
  **Returns:** None

#### `_run_command`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_get_current_version`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `_update_version_in_file`

**Parameters:**

- `self` ():
- `new_version` (str):
  **Returns:** bool

#### `_calculate_next_version`

**Parameters:**

- `self` ():
- `current` (str):
- `bump_type` (str):
  **Returns:** str

#### `bump_version`

**Parameters:**

- `self` ():
- `version_type` (str):
  **Returns:** str

#### `_prompt_for_version_type`

**Parameters:**

- `self` ():
  **Returns:** str

#### `validate_auth`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_collect_auth_methods`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `_check_env_token_auth`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `_check_keyring_auth`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `_report_auth_status`

**Parameters:**

- `self` ():
- `auth_methods` (list[str]):
  **Returns:** bool

#### `_display_auth_setup_instructions`

**Parameters:**

- `self` ():
  **Returns:** None

#### `build_package`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_handle_dry_run_build`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_clean_dist_directory`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_execute_build`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_display_build_artifacts`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_format_file_size`

**Parameters:**

- `self` ():
- `size` (int):
  **Returns:** str

#### `publish_package`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_validate_prerequisites`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_perform_publish_workflow`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_handle_dry_run_publish`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_execute_publish`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_handle_publish_failure`

**Parameters:**

- `self` ():
- `error_msg` (str):
  **Returns:** None

#### `_handle_publish_success`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_display_package_url`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_get_package_name`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `cleanup_old_releases`

**Parameters:**

- `self` ():
- `keep_releases` (int):
  **Returns:** bool

#### `create_git_tag`

**Parameters:**

- `self` ():
- `version` (str):
  **Returns:** bool

#### `get_package_info`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `_update_changelog_for_version`

Update changelog with entries from git commits since last version.
**Parameters:**

- `self` ():
- `old_version` (str):
- `new_version` (str):
  **Returns:** None

## test_command_builder

**Path:** `crackerjack/managers/test_command_builder.py`

## TestCommandBuilder

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `pkg_path` (Path):
  **Returns:** None

#### `build_command`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** list[str]

#### `get_optimal_workers`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** int

#### `get_test_timeout`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** int

#### `_add_coverage_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_worker_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_benchmark_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_timeout_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_verbosity_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_test_path`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
  **Returns:** None

#### `build_specific_test_command`

**Parameters:**

- `self` ():
- `test_pattern` (str):
  **Returns:** list[str]

#### `build_validation_command`

**Parameters:**

- `self` ():
  **Returns:** list[str]

## hook_manager

**Path:** `crackerjack/managers/hook_manager.py`

## HookManagerImpl

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
- `verbose` (bool):
- `quiet` (bool):
  **Returns:** None

#### `set_config_path`

**Parameters:**

- `self` ():
- `config_path` (Path):
  **Returns:** None

#### `run_fast_hooks`

**Parameters:**

- `self` ():
  **Returns:** list[HookResult]

#### `run_comprehensive_hooks`

**Parameters:**

- `self` ():
  **Returns:** list[HookResult]

#### `run_hooks`

**Parameters:**

- `self` ():
  **Returns:** list[HookResult]

#### `validate_hooks_config`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `get_hook_ids`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `install_hooks`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `update_hooks`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `get_hook_summary`

**Parameters:**

- `self` ():
- `results` (list[HookResult]):
  **Returns:** dict[(str, t.Any)]

## test_progress

**Path:** `crackerjack/managers/test_progress.py`

## TestProgress

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `completed`

**Parameters:**

- `self` ():
  **Returns:** int

#### `elapsed_time`

**Parameters:**

- `self` ():
  **Returns:** float

#### `eta_seconds`

**Parameters:**

- `self` ():
  **Returns:** float | None

#### `update`

**Parameters:**

- `self` ():
  **Returns:** None

#### `format_progress`

**Parameters:**

- `self` ():
  **Returns:** str

#### `_format_collection_progress`

**Parameters:**

- `self` ():
  **Returns:** str

#### `_format_execution_progress`

**Parameters:**

- `self` ():
  **Returns:** str

## async_hook_manager

**Path:** `crackerjack/managers/async_hook_manager.py`

## AsyncHookManager

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
- `max_concurrent` (int):
  **Returns:** None

#### `set_config_path`

**Parameters:**

- `self` ():
- `config_path` (Path):
  **Returns:** None

#### `run_fast_hooks`

**Parameters:**

- `self` ():
  **Returns:** list[HookResult]

#### `run_comprehensive_hooks`

**Parameters:**

- `self` ():
  **Returns:** list[HookResult]

#### `install_hooks`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `update_hooks`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `get_hook_summary`

**Parameters:**

- `self` ():
- `results` (list[HookResult]):
  **Returns:** dict[(str, t.Any)]

## test_executor

**Path:** `crackerjack/managers/test_executor.py`

## TestExecutor

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
  **Returns:** None

#### `execute_with_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `execute_with_ai_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `progress_callback` (t.Callable\[(\[dict[str, t.Any]\], None)\]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_execute_with_live_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_run_test_command_with_ai_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `progress_callback` (t.Callable\[(\[dict[str, t.Any]\], None)\]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_initialize_progress`

**Parameters:**

- `self` ():
  **Returns:** TestProgress

#### `_setup_test_environment`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, str)]

#### `_setup_coverage_env`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, str)]

#### `_start_reader_threads`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `live` (Live):
  **Returns:** tuple[(threading.Thread, threading.Thread, threading.Thread)]

#### `_create_stdout_reader`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `live` (Live):
  **Returns:** threading.Thread

#### `_create_stderr_reader`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `live` (Live):
  **Returns:** threading.Thread

#### `_create_monitor_thread`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
  **Returns:** threading.Thread

#### `_process_test_output_line`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** None

#### `_parse_test_line`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** None

#### `_handle_collection_completion`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** bool

#### `_handle_session_events`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** bool

#### `_handle_collection_progress`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** bool

#### `_handle_test_execution`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** bool

#### `_handle_running_test`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** None

#### `_extract_current_test`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** None

#### `_update_display_if_needed`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
- `live` (Live):
  **Returns:** None

#### `_should_refresh_display`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
  **Returns:** bool

#### `_mark_test_as_stuck`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
- `test_name` (str):
  **Returns:** None

#### `_cleanup_threads`

**Parameters:**

- `self` ():
- `threads` (list[threading.Thread]):
  **Returns:** None

#### `_handle_progress_error`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `error_msg` (str):
  **Returns:** None

#### `_execute_test_process_with_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `env` (dict[(str, str)]):
- `progress` (TestProgress):
- `progress_callback` (t.Callable\[(\[dict[str, t.Any]\], None)\]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_read_stdout_with_progress`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `progress_callback` (t.Callable\[(\[dict[str, t.Any]\], None)\]):
  **Returns:** list[str]

#### `_read_stderr_lines`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
  **Returns:** list[str]

#### `_wait_for_process_completion`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `timeout` (int):
  **Returns:** int

#### `_emit_ai_progress`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
- `progress_callback` (t.Callable\[(\[dict[str, t.Any]\], None)\]):
  **Returns:** None

## test_manager_backup

**Path:** `crackerjack/managers/test_manager_backup.py`

## TestProgress

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
  **Returns:** None

#### `completed`

**Parameters:**

- `self` ():
  **Returns:** int

#### `elapsed_time`

**Parameters:**

- `self` ():
  **Returns:** float

#### `eta_seconds`

**Parameters:**

- `self` ():
  **Returns:** float | None

#### `update`

**Parameters:**

- `self` ():
  **Returns:** None

#### `format_progress`

**Parameters:**

- `self` ():
  **Returns:** Align

#### `_format_collection_progress`

**Parameters:**

- `self` ():
  **Returns:** Table

#### `_format_execution_progress`

**Parameters:**

- `self` ():
  **Returns:** Table

## TestManagementImpl

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
  **Returns:** None

#### `set_progress_callback`

**Parameters:**

- `self` ():
- `callback` (t.Callable\[(\[dict[str, t.Any]\], None)\] | None):
  **Returns:** None

#### `set_coverage_ratchet_enabled`

**Parameters:**

- `self` ():
- `enabled` (bool):
  **Returns:** None

#### `get_coverage_ratchet_status`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `_run_test_command`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_run_test_command_with_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
- `show_progress` (bool):
  **Returns:** subprocess.CompletedProcess[str]

#### `_execute_with_live_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_initialize_progress`

**Parameters:**

- `self` ():
  **Returns:** TestProgress

#### `_setup_test_environment`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, str)]

#### `_start_reader_threads`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `stdout_lines` (list[str]):
- `stderr_lines` (list[str]):
- `live` (Live):
- `activity_tracker` (dict[(str, float)]):
  **Returns:** dict[(str, threading.Thread)]

#### `_create_stdout_reader`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `stdout_lines` (list[str]):
- `live` (Live):
- `activity_tracker` (dict[(str, float)]):
  **Returns:** t.Callable\[([], None)\]

#### `_process_test_output_line`

**Parameters:**

- `self` ():
- `line` (str):
- `stdout_lines` (list[str]):
- `progress` (TestProgress):
- `activity_tracker` (dict[(str, float)]):
  **Returns:** None

#### `_update_display_if_needed`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
- `live` (Live):
- `refresh_state` (dict[(str, t.Any)]):
  **Returns:** None

#### `_get_refresh_interval`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
  **Returns:** float

#### `_get_current_content_signature`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
  **Returns:** str

#### `_should_refresh_display`

**Parameters:**

- `self` ():
- `current_time` (float):
- `refresh_state` (dict[(str, t.Any)]):
- `refresh_interval` (float):
- `current_content` (str):
  **Returns:** bool

#### `_create_stderr_reader`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `stderr_lines` (list[str]):
  **Returns:** t.Callable\[([], None)\]

#### `_create_monitor_thread`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `live` (Live):
- `activity_tracker` (dict[(str, float)]):
  **Returns:** t.Callable\[([], None)\]

#### `_mark_test_as_stuck`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
- `stuck_time` (float):
- `live` (Live):
  **Returns:** None

#### `_wait_for_completion`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `progress` (TestProgress):
- `live` (Live):
- `timeout` (int):
  **Returns:** int

#### `_cleanup_threads`

**Parameters:**

- `self` ():
- `threads` (dict[(str, threading.Thread)]):
- `progress` (TestProgress):
- `live` (Live):
  **Returns:** None

#### `_handle_progress_error`

**Parameters:**

- `self` ():
- `error` (Exception):
- `cmd` (list[str]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_parse_test_line`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** None

#### `_handle_collection_completion`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** bool

#### `_handle_session_events`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** bool

#### `_handle_collection_progress`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** bool

#### `_handle_test_execution`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** bool

#### `_handle_running_test`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** None

#### `_extract_current_test`

**Parameters:**

- `self` ():
- `line` (str):
- `progress` (TestProgress):
  **Returns:** None

#### `_run_test_command_with_ai_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
  **Returns:** subprocess.CompletedProcess[str]

#### `_setup_coverage_env`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, str)]

#### `_execute_test_process_with_progress`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
- `env` (dict[(str, str)]):
- `progress` (TestProgress):
  **Returns:** subprocess.CompletedProcess[str]

#### `_read_stdout_with_progress`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `stdout_lines` (list[str]):
- `progress` (TestProgress):
- `last_update_time` (list[float]):
  **Returns:** None

#### `_read_stderr_lines`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `stderr_lines` (list[str]):
  **Returns:** None

#### `_wait_for_process_completion`

**Parameters:**

- `self` ():
- `process` (subprocess.Popen[str]):
- `timeout` (int):
  **Returns:** int

#### `_emit_ai_progress`

**Parameters:**

- `self` ():
- `progress` (TestProgress):
  **Returns:** None

#### `_get_optimal_workers`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** int

#### `_get_test_timeout`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** int

#### `run_tests`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** bool

#### `_execute_test_workflow`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
- `start_time` (float):
  **Returns:** bool

#### `_execute_tests_with_appropriate_mode`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
- `options` (OptionsProtocol):
  **Returns:** subprocess.CompletedProcess[str]

#### `_determine_execution_mode`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** str

#### `_handle_test_timeout`

**Parameters:**

- `self` ():
- `start_time` (float):
  **Returns:** bool

#### `_handle_test_error`

**Parameters:**

- `self` ():
- `start_time` (float):
- `error` (Exception):
  **Returns:** bool

#### `_build_test_command`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** list[str]

#### `_add_coverage_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_worker_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_benchmark_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_timeout_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_add_verbosity_options`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `options` (OptionsProtocol):
- `force_verbose` (bool):
  **Returns:** None

#### `_add_test_path`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
  **Returns:** None

#### `_print_test_start_message`

**Parameters:**

- `self` ():
- `cmd` (list[str]):
- `timeout` (int):
- `options` (OptionsProtocol):
  **Returns:** None

#### `_process_test_results`

**Parameters:**

- `self` ():
- `result` (subprocess.CompletedProcess[str]):
- `duration` (float):
  **Returns:** bool

#### `_process_coverage_ratchet`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_handle_ratchet_result`

**Parameters:**

- `self` ():
- `ratchet_result` (dict[(str, t.Any)]):
  **Returns:** bool

#### `_handle_coverage_improvement`

**Parameters:**

- `self` ():
- `ratchet_result` (dict[(str, t.Any)]):
  **Returns:** None

#### `_display_progress_visualization`

**Parameters:**

- `self` ():
  **Returns:** None

#### `_handle_test_success`

**Parameters:**

- `self` ():
- `output` (str):
- `duration` (float):
  **Returns:** bool

#### `_handle_test_failure`

**Parameters:**

- `self` ():
- `output` (str):
- `duration` (float):
  **Returns:** bool

#### `_extract_failure_lines`

**Parameters:**

- `self` ():
- `output` (str):
  **Returns:** list[str]

#### `get_coverage`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `run_specific_tests`

**Parameters:**

- `self` ():
- `test_pattern` (str):
  **Returns:** bool

#### `validate_test_environment`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `get_test_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `get_test_failures`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `get_test_command`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** list[str]

#### `get_coverage_report`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `has_tests`

**Parameters:**

- `self` ():
  **Returns:** bool

## test_manager

**Path:** `crackerjack/managers/test_manager.py`

## TestManager

**Base Classes:** None

### Methods

#### `__init__`

**Parameters:**

- `self` ():
- `console` (Console):
- `pkg_path` (Path):
- `coverage_ratchet` (CoverageRatchetProtocol | None):
  **Returns:** None

#### `set_progress_callback`

**Parameters:**

- `self` ():
- `callback` (t.Callable\[(\[dict[str, t.Any]\], None)\] | None):
  **Returns:** None

#### `set_coverage_ratchet_enabled`

**Parameters:**

- `self` ():
- `enabled` (bool):
  **Returns:** None

#### `run_tests`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** bool

#### `run_specific_tests`

**Parameters:**

- `self` ():
- `test_pattern` (str):
  **Returns:** bool

#### `validate_test_environment`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `get_coverage_ratchet_status`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `get_test_stats`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `get_test_failures`

**Parameters:**

- `self` ():
  **Returns:** list[str]

#### `get_test_command`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** list[str]

#### `get_coverage_report`

**Parameters:**

- `self` ():
  **Returns:** str | None

#### `get_coverage`

**Parameters:**

- `self` ():
  **Returns:** dict[(str, t.Any)]

#### `has_tests`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_execute_test_workflow`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** subprocess.CompletedProcess[str]

#### `_print_test_start_message`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** None

#### `_handle_test_success`

**Parameters:**

- `self` ():
- `output` (str):
- `duration` (float):
  **Returns:** bool

#### `_handle_test_failure`

**Parameters:**

- `self` ():
- `output` (str):
- `duration` (float):
  **Returns:** bool

#### `_handle_test_error`

**Parameters:**

- `self` ():
- `start_time` (float):
- `error` (Exception):
  **Returns:** bool

#### `_process_coverage_ratchet`

**Parameters:**

- `self` ():
  **Returns:** bool

#### `_handle_ratchet_result`

**Parameters:**

- `self` ():
- `ratchet_result` (dict[(str, t.Any)]):
  **Returns:** bool

#### `_handle_coverage_improvement`

**Parameters:**

- `self` ():
- `ratchet_result` (dict[(str, t.Any)]):
  **Returns:** None

#### `_extract_failure_lines`

**Parameters:**

- `self` ():
- `output` (str):
  **Returns:** list[str]

#### `_get_timeout`

**Parameters:**

- `self` ():
- `options` (OptionsProtocol):
  **Returns:** int

## Generated on: 2025-09-08 16:54:59
