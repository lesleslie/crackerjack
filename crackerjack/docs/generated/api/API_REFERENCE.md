# API Reference


This document provides comprehensive API reference for all protocols, services, and managers in the codebase.
**Total Protocols:** 0
**Total Classes:** 998
**Total Functions:** 5959
**Total Modules:** 519



No protocols found.



## documentation_cleanup
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/documentation_cleanup.py`

## DocumentationCleanupResult



**Base Classes:** None


No methods defined.


## ArchiveMapping



**Base Classes:** None


No methods defined.


## DocumentationCleanup



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (ConsoleProtocol | None): 
- `pkg_path` (Path | None): 
- `git_service` (GitInterface | None): 
- `settings` (CrackerjackSettings | None): 
**Returns:** None

#### `cleanup_documentation`

**Parameters:**
- `self` (): 
- `dry_run` (bool): 
**Returns:** DocumentationCleanupResult

#### `rollback_cleanup`

**Parameters:**
- `self` (): 
- `backup_metadata` (BackupMetadata): 
**Returns:** bool

#### `_detect_archivable_files`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `_detect_archivable_files_legacy`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `_is_essential_file`

**Parameters:**
- `self` (): 
- `filename` (str): 
**Returns:** bool

#### `_matches_archive_patterns`

**Parameters:**
- `self` (): 
- `filename` (str): 
**Returns:** bool

#### `_build_archive_mappings`

**Parameters:**
- `self` (): 
**Returns:** list[ArchiveMapping]

#### `_determine_archive_subdirectory`

**Parameters:**
- `self` (): 
- `filename` (str): 
**Returns:** str | None

#### `_validate_preconditions`

**Parameters:**
- `self` (): 
- `archivable_files` (list[Path] | None): 
**Returns:** tuple[(bool, str | None)]

#### `_create_backup`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** BackupMetadata | None

#### `_calculate_backup_checksum`

**Parameters:**
- `self` (): 
- `file_checksums` (dict[(str, str)]): 
**Returns:** str

#### `_move_files_to_archive`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
- `dry_run` (bool): 
**Returns:** tuple[(int, dict[(str, list[str])])]

#### `_count_essential_files`

**Parameters:**
- `self` (): 
**Returns:** int

#### `_generate_summary`

**Parameters:**
- `self` (): 
- `result` (DocumentationCleanupResult): 
**Returns:** str

#### `_generate_backup_id`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_display_completion`

**Parameters:**
- `self` (): 
- `result` (DocumentationCleanupResult): 
**Returns:** None



## pycharm_mcp_integration
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pycharm_mcp_integration.py`

## CircuitBreakerState



**Base Classes:** None


#### `record_failure`

**Parameters:**
- `self` (): 
**Returns:** None

#### `record_success`

**Parameters:**
- `self` (): 
**Returns:** None

#### `can_execute`

**Parameters:**
- `self` (): 
**Returns:** bool



## SearchResult



**Base Classes:** None


No methods defined.


## PyCharmMCPAdapter



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `mcp_client` (t.Any | None): 
- `timeout` (float): 
- `max_results` (int): 
- `allowed_roots` (t.Sequence[str | Path] | None): 
**Returns:** None

#### `_fallback_search`

**Parameters:**
- `self` (): 
- `pattern` (str): 
- `file_pattern` (str | None): 
**Returns:** list[SearchResult]

#### `_fallback_replace`

**Parameters:**
- `self` (): 
- `file_path` (str): 
- `search_text` (str): 
- `replace_text` (str): 
**Returns:** bool

#### `_sanitize_regex`

**Parameters:**
- `self` (): 
- `pattern` (str): 
**Returns:** str

#### `_is_safe_path`

**Parameters:**
- `self` (): 
- `file_path` (str): 
**Returns:** bool

#### `_normalize_allowed_roots`

**Parameters:**
- `self` (): 
- `allowed_roots` (t.Sequence[str | Path] | None): 
**Returns:** tuple[(Path, Ellipsis)]

#### `_get_cached`

**Parameters:**
- `self` (): 
- `key` (str): 
**Returns:** t.Any | None

#### `_set_cached`

**Parameters:**
- `self` (): 
- `key` (str): 
- `value` (t.Any): 
- `ttl` (float): 
**Returns:** None

#### `clear_cache`

**Parameters:**
- `self` (): 
**Returns:** None



## MahavishnuPycharmMCPClient



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `server_url` (str | None): 
- `timeout_seconds` (float): 
**Returns:** None

#### `_normalize_result`

**Parameters:**
- `self` (): 
- `result` (t.Any): 
**Returns:** dict[(str, t.Any)]

#### `_extract_list`

**Parameters:**
- `self` (): 
- `payload` (dict[(str, t.Any)]): 
- `key` (str): 
**Returns:** list[dict[(str, t.Any)]]



## tool_filter
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/tool_filter.py`

## FilterConfig



**Base Classes:** None


No methods defined.


## FilterResult



**Base Classes:** None


#### `tools_filtered_out`

**Parameters:**
- `self` (): 
**Returns:** int

#### `files_filtered_out`

**Parameters:**
- `self` (): 
**Returns:** int



## ToolFilter



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `config` (FilterConfig): 
- `executor` (IncrementalExecutor | None): 
**Returns:** None

#### `filter_tools`

**Parameters:**
- `self` (): 
- `available_tools` (list[str]): 
**Returns:** FilterResult

#### `filter_files`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `all_files` (list[Path]): 
**Returns:** FilterResult

#### `_apply_patterns`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
- `patterns` (list[str]): 
- `include` (bool): 
**Returns:** list[Path]

#### `should_run_tool`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
**Returns:** bool

#### `get_filtered_files`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `all_files` (list[Path]): 
**Returns:** list[Path]

#### `estimate_time_savings`

**Parameters:**
- `self` (): 
- `tool_execution_times` (dict[(str, float)]): 
- `file_execution_time_per_file` (float): 
**Returns:** dict[(str, float)]

#### `generate_filter_summary`

**Parameters:**
- `self` (): 
- `tool_result` (FilterResult | None): 
- `file_result` (FilterResult | None): 
**Returns:** str



## validation_rate_limiter
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/validation_rate_limiter.py`

## ValidationRateLimit



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `max_failures` (int): 
- `window_seconds` (int): 
- `block_duration` (int): 
**Returns:** None



## ValidationRateLimiter



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

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



## self_patcher
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/self_patcher.py`

## SelfPatcher



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `repo_root` (Path): 
- `shadow_mode` (bool): 
- `validation_timeout_seconds` (int): 
**Returns:** None

#### `sentinel_path`

**Parameters:**
- `self` (): 
**Returns:** Path

#### `validate_diff`

**Parameters:**
- `self` (): 
- `proposal` (ImprovementProposal): 
**Returns:** tuple[(bool, str)]

#### `_write_sentinel`

**Parameters:**
- `self` (): 
- `improvement_id` (str): 
**Returns:** None

#### `_delete_sentinel`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_apply_diff_to_working_tree`

**Parameters:**
- `self` (): 
- `diff` (str): 
**Returns:** None

#### `_git_revert_working_tree`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_git_commit`

**Parameters:**
- `self` (): 
- `improvement_id` (str): 
**Returns:** None



## logging
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/logging.py`

## LoggingContext



**Base Classes:** None


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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/metrics.py`

## MetricsCollector



**Base Classes:** None


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
#### `execute`

**Parameters:**
- `self` (): 
- `sql` (str): 
- `params` (tuple): 
**Returns:** None

#### `execute_query`

**Parameters:**
- `self` (): 
- `sql` (str): 
- `params` (tuple): 
**Returns:** list[sqlite3.Row]

#### `track_provider_selection`

**Parameters:**
- `self` (): 
- `provider_id` (str): 
- `success` (bool): 
- `latency_ms` (float | None): 
**Returns:** None

#### `track_agent_execution`

**Parameters:**
- `self` (): 
- `job_id` (str): 
- `agent_name` (str): 
- `issue_type` (str): 
- `success` (bool): 
- `confidence` (float): 
- `fixes_applied` (int): 
- `files_modified` (int): 
- `remaining_issues` (int): 
- `execution_time_ms` (float | None): 
**Returns:** None

#### `get_provider_stats`

**Parameters:**
- `self` (): 
- `provider_id` (str | None): 
**Returns:** list[dict]

#### `get_agent_stats`

**Parameters:**
- `self` (): 
- `agent_name` (str | None): 
**Returns:** list[dict]

#### `get_agent_success_rate`

**Parameters:**
- `self` (): 
- `agent_name` (str): 
**Returns:** float

#### `get_provider_availability`

**Parameters:**
- `self` (): 
- `provider_id` (str): 
- `hours` (int): 
**Returns:** float

#### `get_agent_confidence_distribution`

**Parameters:**
- `self` (): 
- `agent_name` (str): 
**Returns:** dict[(str, int)]

#### `close`

**Parameters:**
- `self` (): 
**Returns:** None



## documentation_generator
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/documentation_generator.py`

**Implements Protocols:**
- DocumentationGeneratorProtocol

## MarkdownTemplateRenderer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_init_builtin_templates`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Template)]

#### `render_template`

**Parameters:**
- `self` (): 
- `template_name` (str): 
- `context` (dict[(str, t.Any)]): 
**Returns:** str

#### `_get_api_reference_template`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_get_function_doc_template`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_get_class_doc_template`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_get_protocol_doc_template`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_get_module_doc_template`

**Parameters:**
- `self` (): 
**Returns:** str



## DocumentationGeneratorImpl



**Base Classes:** DocumentationGeneratorProtocol


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `generate_api_reference`

**Parameters:**
- `self` (): 
- `api_data` (dict[(str, t.Any)]): 
**Returns:** str

#### `generate_user_guide`

**Parameters:**
- `self` (): 
- `template_context` (dict[(str, t.Any)]): 
**Returns:** str

#### `generate_changelog_update`

**Parameters:**
- `self` (): 
- `version` (str): 
- `changes` (dict[(str, t.Any)]): 
**Returns:** str

#### `render_template`

**Parameters:**
- `self` (): 
- `template_path` (Path): 
- `context` (dict[(str, t.Any)]): 
**Returns:** str

#### `generate_cross_references`

**Parameters:**
- `self` (): 
- `api_data` (dict[(str, t.Any)]): 
**Returns:** dict[(str, list[str])]

#### `_generate_overview`

**Parameters:**
- `self` (): 
- `api_data` (dict[(str, t.Any)]): 
**Returns:** str

#### `_generate_protocols_section`

**Parameters:**
- `self` (): 
- `protocols` (dict[(str, t.Any)]): 
**Returns:** str

#### `_generate_services_section`

**Parameters:**
- `self` (): 
- `services` (dict[(str, t.Any)]): 
**Returns:** str

#### `_generate_managers_section`

**Parameters:**
- `self` (): 
- `managers` (dict[(str, t.Any)]): 
**Returns:** str

#### `_format_methods`

**Parameters:**
- `self` (): 
- `methods` (list[dict[(str, t.Any)]]): 
**Returns:** str

#### `_calculate_api_stats`

**Parameters:**
- `self` (): 
- `api_data` (dict[(str, t.Any)]): 
**Returns:** dict[(str, int)]

#### `_find_references_to_name`

**Parameters:**
- `self` (): 
- `name` (str): 
- `api_data` (dict[(str, t.Any)]): 
**Returns:** list[str]

#### `_find_protocol_references`

**Parameters:**
- `self` (): 
- `name` (str): 
- `protocols` (dict[(str, t.Any)]): 
**Returns:** list[str]

#### `_find_protocol_method_references`

**Parameters:**
- `self` (): 
- `name` (str): 
- `protocol_name` (str): 
- `methods` (list[dict[(str, t.Any)]]): 
**Returns:** list[str]

#### `_find_module_references`

**Parameters:**
- `self` (): 
- `name` (str): 
- `modules` (dict[(str, t.Any)]): 
**Returns:** list[str]

#### `_find_class_references`

**Parameters:**
- `self` (): 
- `name` (str): 
- `classes` (list[dict[(str, t.Any)]]): 
**Returns:** list[str]

#### `_find_class_method_references`

**Parameters:**
- `self` (): 
- `name` (str): 
- `class_name` (str): 
- `methods` (list[dict[(str, t.Any)]]): 
**Returns:** list[str]

#### `_find_method_parameter_references`

**Parameters:**
- `self` (): 
- `name` (str): 
- `method_name` (str): 
- `parameters` (list[dict[(str, t.Any)]]): 
**Returns:** list[str]



## file_io_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/file_io_service.py`

## FileIOService



**Base Classes:** None


#### `read_text_file_sync`

**Parameters:**
- `path` (str | Path): 
- `encoding` (str): 
**Returns:** str

#### `write_text_file_sync`

**Parameters:**
- `path` (str | Path): 
- `content` (str): 
- `encoding` (str): 
- `create_dirs` (bool): 
**Returns:** None

#### `read_json_file_sync`

**Parameters:**
- `path` (str | Path): 
**Returns:** dict

#### `write_json_file_sync`

**Parameters:**
- `path` (str | Path): 
- `data` (dict): 
- `create_dirs` (bool): 
- `indent` (int): 
**Returns:** None

#### `read_binary_file_sync`

**Parameters:**
- `path` (str | Path): 
**Returns:** bytes

#### `write_binary_file_sync`

**Parameters:**
- `path` (str | Path): 
- `data` (bytes): 
- `create_dirs` (bool): 
**Returns:** None

#### `file_exists`

**Parameters:**
- `path` (str | Path): 
**Returns:** bool

#### `directory_exists`

**Parameters:**
- `path` (str | Path): 
**Returns:** bool



## file_hasher
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/file_hasher.py`

## FileHasher



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `cache` (CrackerjackCache | None): 
**Returns:** None

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `shutdown_all_instances`

**Parameters:**
- `cls` (): 
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



## pool_scaler
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pool_scaler.py`

## PoolScaler



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console | None): 
- `scale_up_threshold` (int): 
- `scale_down_threshold` (int): 
- `check_interval` (int): 
**Returns:** None

#### `get_status`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## git
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/git.py`

## FailedGitResult



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `command` (list[str]): 
- `error` (str): 
**Returns:** None



## GitService



**Base Classes:** GitInterface


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (ConsoleInterface | Path | None): 
- `pkg_path` (Path | None): 
- `auth_fallback` (bool): 
- `persist_fallback` (bool): 
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

#### `_is_auth_failure`

**Parameters:**
- `self` (): 
- `stderr` (str): 
**Returns:** bool

#### `_try_auth_fallback`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_get_remote_url`

**Parameters:**
- `self` (): 
- `remote` (str): 
**Returns:** str | None

#### `_set_remote_url`

**Parameters:**
- `self` (): 
- `url` (str): 
- `remote` (str): 
**Returns:** bool

#### `_ssh_to_https`

**Parameters:**
- `self` (): 
- `ssh_url` (str): 
**Returns:** str

#### `_https_to_ssh`

**Parameters:**
- `self` (): 
- `https_url` (str): 
**Returns:** str

#### `push_with_tags`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_try_auth_fallback_with_tags`

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
- `categories` (dict[(str, list[str])]): 
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

#### `get_changed_files_by_extension`

**Parameters:**
- `self` (): 
- `extensions` (list[str]): 
- `include_staged` (bool): 
- `include_unstaged` (bool): 
**Returns:** list[Path]

#### `get_current_commit_hash`

**Parameters:**
- `self` (): 
**Returns:** str | None

#### `reset_hard`

**Parameters:**
- `self` (): 
- `commit_hash` (str): 
**Returns:** bool

#### `checkout_files`
Revert the given paths in BOTH the working tree AND index to HEAD.
**Parameters:**
- `self` (): 
- `files` (list[str]): 
**Returns:** bool

#### `rm_files`
Stage removals for ``files`` (paths relative to ``self.pkg_path``).
**Parameters:**
- `self` (): 
- `files` (list[str]): 
**Returns:** bool

#### `get_changed_files_since`

**Parameters:**
- `self` (): 
- `since` (str): 
- `project_root` (Path): 
**Returns:** list[str]

#### `get_unstaged_files`

**Parameters:**
- `self` (): 
**Returns:** list[str]



## enhanced_filesystem
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/enhanced_filesystem.py`

**Implements Protocols:**
- EnhancedFileSystemServiceProtocol

- ServiceProtocol

## FileCache



**Base Classes:** None


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


#### `__init__`

**Parameters:**
- `self` (): 
- `batch_size` (int): 
**Returns:** None



## EnhancedFileSystemService



**Base Classes:** EnhancedFileSystemServiceProtocol, ServiceProtocol


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

#### `_validate_file_exists`

**Parameters:**
- `path` (Path): 
**Returns:** None

#### `_handle_read_error`

**Parameters:**
- `error` (Exception): 
- `path` (Path): 
**Returns:** None

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
- `self` (): 
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
- `self` (): 
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



## improvement_generator
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/improvement_generator.py`

## ImprovementProposal



**Base Classes:** None


#### `is_auto_apply_candidate`

**Parameters:**
- `self` (): 
**Returns:** bool



## ImprovementGenerator



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `repository` (FailureMetricsRepository): 
- `recorder` (FailureRecorder | None): 
- `min_failures` (int): 
- `max_per_day` (int): 
**Returns:** None

#### `_reset_daily_count_if_new_day`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_build_generation_prompt`

**Parameters:**
- `self` (): 
- `failure_context` (str): 
- `current_impl` (str): 
**Returns:** str



## incremental_executor
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/incremental_executor.py`

## FileHash



**Base Classes:** None


No methods defined.


## CacheEntry



**Base Classes:** None


No methods defined.


## ExecutionResult



**Base Classes:** None


#### `cache_effective`

**Parameters:**
- `self` (): 
**Returns:** bool



## IncrementalExecutor



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `cache_dir` (Path | None): 
- `ttl_seconds` (int): 
- `profiler` (ToolProfiler | None): 
**Returns:** None

#### `_compute_file_hash`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** FileHash

#### `_cache_key`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `file_hash` (FileHash): 
**Returns:** str

#### `_load_cache`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_save_cache`

**Parameters:**
- `self` (): 
**Returns:** None

#### `execute_incremental`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `files` (list[Path]): 
- `tool_func` (Callable[([Path], Any)]): 
- `force_rerun` (bool): 
**Returns:** ExecutionResult

#### `get_changed_files`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `files` (list[Path]): 
**Returns:** list[Path]

#### `invalidate_file`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** int

#### `clear_cache`

**Parameters:**
- `self` (): 
- `tool_name` (str | None): 
**Returns:** int

#### `get_cache_stats`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]

#### `_estimate_cache_size`

**Parameters:**
- `self` (): 
**Returns:** float



## doc_update_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/doc_update_service.py`

## CodeChange



**Base Classes:** None


No methods defined.


## DocUpdate



**Base Classes:** None


No methods defined.


## DocUpdateResult



**Base Classes:** None


No methods defined.


## DocUpdateService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console): 
- `pkg_path` (Path): 
- `git_service` (GitInterface): 
- `settings` (CrackerjackSettings | None): 
**Returns:** None

#### `settings`

**Parameters:**
- `self` (): 
**Returns:** DocUpdateSettings

#### `_run_git_command`

**Parameters:**
- `self` (): 
- `args` (list[str]): 
**Returns:** Mock

#### `update_documentation`

**Parameters:**
- `self` (): 
- `dry_run` (bool): 
**Returns:** DocUpdateResult

#### `_analyze_code_changes`

**Parameters:**
- `self` (): 
**Returns:** list[CodeChange]

#### `_get_git_diff`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_parse_git_diff`

**Parameters:**
- `self` (): 
- `diff_output` (str): 
**Returns:** list[CodeChange]

#### `_extract_line_number`

**Parameters:**
- `self` (): 
- `hunk_header` (str): 
**Returns:** int | None

#### `_generate_doc_updates`

**Parameters:**
- `self` (): 
- `changes` (list[CodeChange]): 
**Returns:** list[DocUpdate]

#### `_identify_doc_files`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `_build_update_prompt`

**Parameters:**
- `self` (): 
- `doc_file` (str): 
- `current_content` (str): 
- `changes` (list[CodeChange]): 
**Returns:** str

#### `_is_change_relevant`

**Parameters:**
- `self` (): 
- `change` (CodeChange): 
- `doc_file` (str): 
**Returns:** bool

#### `_calculate_confidence`

**Parameters:**
- `self` (): 
- `original` (str): 
- `updated` (str): 
**Returns:** float

#### `_apply_doc_updates`

**Parameters:**
- `self` (): 
- `updates` (list[DocUpdate]): 
**Returns:** int

#### `_create_update_commits`

**Parameters:**
- `self` (): 
- `updates` (list[DocUpdate]): 
**Returns:** None

#### `_generate_dry_run_summary`

**Parameters:**
- `self` (): 
- `updates` (list[DocUpdate]): 
**Returns:** str

#### `_generate_update_summary`

**Parameters:**
- `self` (): 
- `updates` (list[DocUpdate]): 
- `applied_count` (int): 
**Returns:** str



## swarm_client
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/swarm_client.py`

**Implements Protocols:**
- Protocol

## SwarmMode



**Base Classes:** Enum


No methods defined.


## SwarmTask



**Base Classes:** None


No methods defined.


## SwarmResult



**Base Classes:** None


No methods defined.


## SwarmClientProtocol



**Base Classes:** Protocol


#### `mode`

**Parameters:**
- `self` (): 
**Returns:** SwarmMode



## MahavishnuSwarmClient



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `mcp_port` (int): 
- `mcp_caller` (Callable[([str, dict[str, t.Any]], Awaitable[t.Any])] | None): 
**Returns:** None

#### `mode`

**Parameters:**
- `self` (): 
**Returns:** SwarmMode



## LocalSequentialClient



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `agent_executor` (Callable[([SwarmTask], Awaitable[SwarmResult])] | None): 
**Returns:** None

#### `mode`

**Parameters:**
- `self` (): 
**Returns:** SwarmMode



## SwarmManager



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `prefer_parallel` (bool): 
- `worker_count` (int): 
- `mcp_port` (int): 
- `agent_executor` (Callable[([SwarmTask], Awaitable[SwarmResult])] | None): 
**Returns:** None

#### `mode`

**Parameters:**
- `self` (): 
**Returns:** SwarmMode

#### `is_parallel`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `is_initialized`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_create_tasks_from_issues`

**Parameters:**
- `self` (): 
- `issues` (list[dict[(str, t.Any)]]): 
**Returns:** list[SwarmTask]

#### `_create_fix_prompt`

**Parameters:**
- `self` (): 
- `issue` (dict[(str, t.Any)]): 
**Returns:** str

#### `get_status`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## pool_client
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pool_client.py`

## CrackerjackPoolClient



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `mcp_server_url` (str): 
- `timeout` (int): 
**Returns:** None

#### `_build_tool_command`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `files` (list[Path]): 
**Returns:** list[str]



## frontmatter
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/frontmatter.py`

## Issue



**Base Classes:** None


#### `format`

**Parameters:**
- `self` (): 
- `path` (str): 
**Returns:** str



## FileResult



**Base Classes:** None


#### `issues`

**Parameters:**
- `self` (): 
**Returns:** list[Issue]

#### `add`

**Parameters:**
- `self` (): 
- `issue` (Issue): 
**Returns:** None



## VocabFileNotFoundError

The topic vocabulary file is missing from the configured location.

**Base Classes:** Exception


No methods defined.


## file_chunker
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/file_chunker.py`

## FileChunker



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `chunk_size` (int): 
- `overlap_percentage` (int): 
- `settings` (FileChunkingSettings | None): 
**Returns:** None

#### `chunk_files`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** list[list[Path]]

#### `should_chunk_files`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** bool

#### `estimate_parallel_benefit`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
- `workers` (int): 
**Returns:** dict[(str, float)]



## version_checker
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/version_checker.py`

## VersionInfo



**Base Classes:** None


No methods defined.


## VersionChecker



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console | None): 
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
**Returns:** tuple[(list[int], int)]

#### `_normalize_version_parts`

**Parameters:**
- `self` (): 
- `current_parts` (list[int]): 
- `latest_parts` (list[int]): 
**Returns:** tuple[(list[int], list[int])]

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



## template_applicator
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/template_applicator.py`

## TemplateApplicator



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (t.Any | None): 
- `detector` (TemplateDetector | None): 
**Returns:** None

#### `_select_template`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `template_name` (str | None): 
- `interactive` (bool): 
**Returns:** str

#### `_load_and_prepare_template`

**Parameters:**
- `self` (): 
- `template_name` (str): 
- `package_name` (str): 
- `project_path` (Path): 
- `force` (bool): 
**Returns:** dict[(str, t.Any)] | None

#### `apply_template`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `_detect_package_name`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
**Returns:** str | None

#### `_replace_placeholders`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
- `package_name` (str): 
- `project_path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `_smart_merge_configs`

**Parameters:**
- `self` (): 
- `template_config` (dict[(str, t.Any)]): 
- `existing_path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `_merge_tool_section`

**Parameters:**
- `self` (): 
- `existing` (dict[(str, t.Any)]): 
- `template` (dict[(str, t.Any)]): 
- `section_name` (str): 
**Returns:** dict[(str, t.Any)]

#### `_merge_nested_dict`

**Parameters:**
- `self` (): 
- `existing` (dict[(str, t.Any)]): 
- `template` (dict[(str, t.Any)]): 
- `section_name` (str): 
**Returns:** dict[(str, t.Any)]

#### `get_available_templates`

**Parameters:**
- `self` (): 
**Returns:** list[str]



## vector_store
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/vector_store.py`

## VectorStore



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `config` (SemanticConfig): 
- `db_path` (Path | None): 
- `embedding_service` (EmbeddingService | None): 
**Returns:** None

#### `_initialize_database`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_get_connection`

**Parameters:**
- `self` (): 
**Returns:** t.Generator[sqlite3.Connection]

#### `index_file`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `progress_callback` (t.Callable[([IndexingProgress], None)] | None): 
**Returns:** list[EmbeddingVector]

#### `_prepare_file_for_indexing`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** str | None

#### `_process_file_content`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `current_hash` (str): 
**Returns:** dict[(str, t.Any)]

#### `_create_embedding_vectors`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `current_hash` (str): 
- `chunk_data` (dict[(str, t.Any)]): 
- `progress_callback` (t.Callable[([IndexingProgress], None)] | None): 
**Returns:** list[EmbeddingVector]

#### `_validate_file_for_indexing`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** None

#### `_matches_pattern`

**Parameters:**
- `self` (): 
- `file_path` (str | Path): 
- `pattern` (str): 
**Returns:** bool

#### `_needs_reindexing`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `current_hash` (str): 
**Returns:** bool

#### `_get_existing_embeddings`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** list[EmbeddingVector]

#### `_store_embeddings`

**Parameters:**
- `self` (): 
- `embeddings` (list[EmbeddingVector]): 
**Returns:** None

#### `_update_file_tracking`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `file_hash` (str): 
- `chunk_count` (int): 
**Returns:** None

#### `search`

**Parameters:**
- `self` (): 
- `query` (SearchQuery): 
**Returns:** list[SearchResult]

#### `_get_all_embeddings`

**Parameters:**
- `self` (): 
- `file_types` (list[str] | None): 
**Returns:** list[dict[(str, t.Any)]]

#### `_get_context_lines`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `start_line` (int): 
- `end_line` (int): 
- `context_count` (int): 
**Returns:** list[str]

#### `get_stats`

**Parameters:**
- `self` (): 
**Returns:** IndexStats

#### `remove_file`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** bool

#### `clear_index`

**Parameters:**
- `self` (): 
**Returns:** None

#### `close`

**Parameters:**
- `self` (): 
**Returns:** None

#### `__enter__`

**Parameters:**
- `self` (): 
**Returns:** t.Self

#### `__exit__`

**Parameters:**
- `self` (): 
- `exc_type` (type[BaseException] | None): 
- `exc_val` (BaseException | None): 
- `exc_tb` (object): 
**Returns:** None



## pattern_cache
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/pattern_cache.py`

## CachedPattern



**Base Classes:** None


No methods defined.


## PatternCache



**Base Classes:** None


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
**Returns:** list[dict[(str, t.Any)]]

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



## mahavishnu_discovery
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/mahavishnu_discovery.py`

## MahavishnuUnreachable

Internal: probe failed. Callers should NOT raise this — soft fallback.

**Base Classes:** Exception


No methods defined.


## failure_metrics_repository
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/failure_metrics_repository.py`

## FailureMetricsRepository

Failure metrics store.

**Base Classes:** None


No methods defined.


## anomaly_detector
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/anomaly_detector.py`

## MetricPoint



**Base Classes:** None


No methods defined.


## AnomalyDetection



**Base Classes:** None


No methods defined.


## BaselineModel



**Base Classes:** None


No methods defined.


## AnomalyDetector



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `baseline_window` (int): 
- `sensitivity` (float): 
- `min_samples` (int): 
**Returns:** None

#### `add_metric`

**Parameters:**
- `self` (): 
- `metric_type` (str): 
- `value` (float): 
- `timestamp` (datetime | None): 
- `metadata` (dict[(str, t.Any)] | None): 
**Returns:** None

#### `_update_baseline`

**Parameters:**
- `self` (): 
- `metric_type` (str): 
**Returns:** None

#### `_detect_seasonal_patterns`

**Parameters:**
- `self` (): 
- `history` (list[MetricPoint]): 
**Returns:** dict[(str, float)]

#### `_detect_anomaly`

**Parameters:**
- `self` (): 
- `point` (MetricPoint): 
**Returns:** AnomalyDetection | None

#### `_get_seasonal_adjustment`

**Parameters:**
- `self` (): 
- `point` (MetricPoint): 
- `baseline` (BaselineModel): 
**Returns:** float

#### `_calculate_severity`

**Parameters:**
- `self` (): 
- `point` (MetricPoint): 
- `baseline` (BaselineModel): 
- `lower_bound` (float): 
- `upper_bound` (float): 
**Returns:** str

#### `_is_critical_threshold_breached`

**Parameters:**
- `self` (): 
- `point` (MetricPoint): 
**Returns:** bool

#### `_threshold_breached_in_direction`

**Parameters:**
- `self` (): 
- `value` (float): 
- `threshold` (float): 
- `direction` (str): 
**Returns:** bool

#### `_calculate_z_score`

**Parameters:**
- `self` (): 
- `point` (MetricPoint): 
- `baseline` (BaselineModel): 
- `lower_bound` (float): 
- `upper_bound` (float): 
**Returns:** float

#### `_severity_from_z_score`

**Parameters:**
- `self` (): 
- `z_score` (float): 
**Returns:** str

#### `_calculate_confidence`

**Parameters:**
- `self` (): 
- `point` (MetricPoint): 
- `baseline` (BaselineModel): 
**Returns:** float

#### `_generate_anomaly_description`

**Parameters:**
- `self` (): 
- `point` (MetricPoint): 
- `baseline` (BaselineModel): 
- `lower_bound` (float): 
- `upper_bound` (float): 
- `severity` (str): 
**Returns:** str

#### `get_anomalies`

**Parameters:**
- `self` (): 
- `metric_type` (str | None): 
- `severity` (str | None): 
- `since` (datetime | None): 
- `limit` (int): 
**Returns:** list[AnomalyDetection]

#### `get_baseline_summary`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, dict[(str, t.Any)])]

#### `export_model`

**Parameters:**
- `self` (): 
- `output_path` (str | Path): 
**Returns:** None



## backup_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/backup_service.py`

## BackupMetadata



**Base Classes:** BaseModel


No methods defined.


## BackupValidationResult



**Base Classes:** BaseModel


No methods defined.


## PackageBackupService



**Base Classes:** BaseModel


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



## pool_orchestrator
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pool_orchestrator.py`

**Implements Protocols:**
- ServiceProtocol

## PoolExecutionResult



**Base Classes:** None


#### `passed_count`

**Parameters:**
- `self` (): 
**Returns:** int

#### `failed_count`

**Parameters:**
- `self` (): 
**Returns:** int



## PoolOrchestrator



**Base Classes:** ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `pool_client` (t.Any): 
- `pkg_path` (Path): 
- `console` (ConsoleInterface): 
- `verbose` (bool): 
- `debug` (bool): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

#### `_is_pool_available`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_execute_single_hook_standard`

**Parameters:**
- `self` (): 
- `hook` (HookDefinition): 
- `file_filter` (t.Any): 
**Returns:** HookResult

#### `_get_files_for_hook`

**Parameters:**
- `self` (): 
- `hook` (HookDefinition): 
- `file_filter` (t.Any): 
**Returns:** list[Path] | None

#### `_group_hooks_by_files`

**Parameters:**
- `self` (): 
- `hooks` (list[HookDefinition]): 
- `file_filter` (t.Any): 
**Returns:** dict[(str, list[Path])]

#### `_convert_pool_results_to_hook_results`

**Parameters:**
- `self` (): 
- `pool_results` (dict[(str, dict[(str, t.Any)])]): 
- `hooks` (list[HookDefinition]): 
**Returns:** list[HookResult]



## coverage_badge_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/coverage_badge_service.py`

## CoverageBadgeService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `project_root` (Path): 
- `console` (Console | None): 
**Returns:** None

#### `update_readme_coverage_badge`

**Parameters:**
- `self` (): 
- `coverage_percent` (float): 
**Returns:** bool

#### `_generate_badge_url`

**Parameters:**
- `self` (): 
- `coverage_percent` (float): 
**Returns:** str

#### `_get_badge_color`

**Parameters:**
- `self` (): 
- `coverage_percent` (float): 
**Returns:** str

#### `_has_coverage_badge`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** bool

#### `_update_existing_badge`

**Parameters:**
- `self` (): 
- `content` (str): 
- `new_badge_url` (str): 
**Returns:** str

#### `_insert_new_badge`

**Parameters:**
- `self` (): 
- `content` (str): 
- `badge_url` (str): 
**Returns:** str

#### `_find_badge_insertion_point`

**Parameters:**
- `self` (): 
- `lines` (list[str]): 
**Returns:** int | None

#### `_insert_after_title`

**Parameters:**
- `self` (): 
- `content` (str): 
- `badge_url` (str): 
**Returns:** str

#### `should_update_badge`

**Parameters:**
- `self` (): 
- `coverage_percent` (float): 
**Returns:** bool

#### `_extract_current_coverage`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** float | None



## filesystem
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/filesystem.py`

## FileSystemService



**Base Classes:** FileSystemInterface


#### `clean_trailing_whitespace_and_newlines`

**Parameters:**
- `content` (str): 
**Returns:** str

#### `_validate_path_exists`

**Parameters:**
- `self` (): 
- `path_obj` (Path): 
- `operation` (str): 
**Returns:** None

#### `_handle_permission_error`

**Parameters:**
- `self` (): 
- `error` (PermissionError): 
- `path` (str | Path): 
- `operation` (str): 
**Returns:** None

#### `_handle_unicode_error`

**Parameters:**
- `self` (): 
- `error` (UnicodeDecodeError): 
- `path` (str | Path): 
**Returns:** None

#### `_handle_os_error`

**Parameters:**
- `self` (): 
- `error` (OSError): 
- `path` (str | Path): 
- `operation` (str): 
**Returns:** None

#### `_handle_disk_space_error`

**Parameters:**
- `self` (): 
- `error` (OSError): 
- `path` (str | Path): 
- `operation` (str): 
**Returns:** None

#### `_read_file_with_error_handling`

**Parameters:**
- `self` (): 
- `path_obj` (Path): 
- `path` (str | Path): 
**Returns:** str

#### `_ensure_parent_directory_exists`

**Parameters:**
- `self` (): 
- `path` (str | Path): 
- `path_obj` (Path): 
**Returns:** None

#### `_is_disk_space_error`

**Parameters:**
- `self` (): 
- `error` (OSError): 
**Returns:** bool

#### `_is_pyproject_file`

**Parameters:**
- `self` (): 
- `path_obj` (Path): 
**Returns:** bool

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

#### `_validate_file_path`

**Parameters:**
- `self` (): 
- `path_obj` (Path): 
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



## doc_categorizer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/doc_categorizer.py`

## CategoryConfig



**Base Classes:** TypedDict


No methods defined.


## CategoryResult



**Base Classes:** None


No methods defined.


## DocumentationCategorizer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `docs_root` (Path): 
**Returns:** None

#### `derive_archive_area`
Return the archive area (relative to ``self.docs_root``) that a
file should be archived under, derived from its parent directory.
**Parameters:**
- `self` (): 
- `filepath` (Path): 
**Returns:** str

#### `archive_target_path`
Compose the full archive target path for ``filepath`` given its
category subdir name. The result lives under
``<archive_area>/.archive/<category_subdir>/`` relative to the
docs_root.
**Parameters:**
- `self` (): 
- `filepath` (Path): 
- `category_subdir` (str): 
**Returns:** Path

#### `_resolve_collision`
If ``target_path`` already exists, append a numeric suffix.
**Parameters:**
- `target_path` (Path): 
**Returns:** Path

#### `categorize_file`

**Parameters:**
- `self` (): 
- `filepath` (Path): 
**Returns:** CategoryResult

#### `analyze_all`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, list[dict[(str, str)]])]

#### `get_archivable_files`
Return the list of files that should be archived.
**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `get_archive_subdirectory`
Return the category sub-directory for ``filepath``.
**Parameters:**
- `self` (): 
- `filepath` (Path): 
**Returns:** str | None

#### `should_keep_in_root`

**Parameters:**
- `self` (): 
- `filepath` (Path): 
**Returns:** bool

#### `should_keep_in_docs`

**Parameters:**
- `self` (): 
- `filepath` (Path): 
**Returns:** bool



## security
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/security.py`

**Implements Protocols:**
- SecurityServiceProtocol

## SecurityService



**Base Classes:** SecurityServiceProtocol


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

#### `_validate_token`

**Parameters:**
- `self` (): 
- `token` (str): 
**Returns:** None

#### `_create_token_file`

**Parameters:**
- `self` (): 
- `token` (str): 
- `prefix` (str): 
**Returns:** Path

#### `_set_secure_permissions`

**Parameters:**
- `self` (): 
- `temp_file` (Path): 
**Returns:** None

#### `_write_token_to_file`

**Parameters:**
- `self` (): 
- `fd` (int): 
- `temp_file` (Path): 
- `token` (str): 
**Returns:** None

#### `_cleanup_on_error`

**Parameters:**
- `self` (): 
- `temp_file` (Path): 
**Returns:** None

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
**Returns:** list[dict[(str, t.Any)]]

#### `is_safe_subprocess_call`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
**Returns:** bool

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None



## dependency_analyzer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/dependency_analyzer.py`

## DependencyNode



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## DependencyEdge



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## DependencyGraph



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## DependencyAnalyzer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `project_root` (Path): 
**Returns:** None

#### `analyze_project`

**Parameters:**
- `self` (): 
**Returns:** DependencyGraph

#### `_discover_python_files`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_analyze_file`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** None

#### `_generate_clusters`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_calculate_metrics`

**Parameters:**
- `self` (): 
**Returns:** None



## DependencyVisitor



**Base Classes:** ast.NodeVisitor


#### `__init__`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `project_root` (Path): 
**Returns:** None

#### `visit_Module`

**Parameters:**
- `self` (): 
- `node` (ast.Module): 
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

#### `visit_ClassDef`

**Parameters:**
- `self` (): 
- `node` (ast.ClassDef): 
**Returns:** None

#### `visit_FunctionDef`

**Parameters:**
- `self` (): 
- `node` (ast.FunctionDef): 
**Returns:** None

#### `visit_Call`

**Parameters:**
- `self` (): 
- `node` (ast.Call): 
**Returns:** None

#### `_calculate_complexity`

**Parameters:**
- `self` (): 
- `node` (ast.AST): 
**Returns:** int

#### `_get_decorator_name`

**Parameters:**
- `self` (): 
- `decorator` (ast.AST): 
**Returns:** str

#### `_resolve_name`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** str

#### `_get_current_context_id`

**Parameters:**
- `self` (): 
- `line_number` (int): 
**Returns:** str | None



## api_extractor
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/api_extractor.py`

**Implements Protocols:**
- APIExtractorProtocol

## PythonDocstringParser



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `parse_docstring`

**Parameters:**
- `self` (): 
- `docstring` (str | None): 
**Returns:** dict[(str, t.Any)]

#### `_is_section_header`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** bool

#### `_extract_parameters`

**Parameters:**
- `self` (): 
- `docstring` (str): 
**Returns:** dict[(str, str)]

#### `_extract_returns`

**Parameters:**
- `self` (): 
- `docstring` (str): 
**Returns:** str

#### `_extract_raises`

**Parameters:**
- `self` (): 
- `docstring` (str): 
**Returns:** list[str]



## APIExtractorImpl



**Base Classes:** APIExtractorProtocol


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `extract_from_python_files`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** dict[(str, t.Any)]

#### `extract_protocol_definitions`

**Parameters:**
- `self` (): 
- `protocol_file` (Path): 
**Returns:** dict[(str, t.Any)]

#### `extract_service_interfaces`

**Parameters:**
- `self` (): 
- `service_files` (list[Path]): 
**Returns:** dict[(str, t.Any)]

#### `extract_cli_commands`

**Parameters:**
- `self` (): 
- `cli_files` (list[Path]): 
**Returns:** dict[(str, t.Any)]

#### `extract_mcp_tools`

**Parameters:**
- `self` (): 
- `mcp_files` (list[Path]): 
**Returns:** dict[(str, t.Any)]

#### `_extract_module_info`

**Parameters:**
- `self` (): 
- `tree` (ast.AST): 
- `file_path` (Path): 
- `source_code` (str): 
**Returns:** dict[(str, t.Any)]

#### `_create_base_module_info`

**Parameters:**
- `self` (): 
- `tree` (ast.AST): 
- `file_path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `_populate_module_components`

**Parameters:**
- `self` (): 
- `module_info` (dict[(str, t.Any)]): 
- `tree` (ast.AST): 
- `source_code` (str): 
**Returns:** None

#### `_process_ast_node`

**Parameters:**
- `self` (): 
- `module_info` (dict[(str, t.Any)]): 
- `node` (ast.AST): 
- `source_code` (str): 
**Returns:** None

#### `_extract_class_info`

**Parameters:**
- `self` (): 
- `node` (ast.ClassDef): 
- `source_code` (str): 
**Returns:** dict[(str, t.Any)]

#### `_build_base_class_info`

**Parameters:**
- `self` (): 
- `node` (ast.ClassDef): 
- `parsed_doc` (dict[(str, t.Any)]): 
**Returns:** dict[(str, t.Any)]

#### `_extract_class_methods`

**Parameters:**
- `self` (): 
- `class_info` (dict[(str, t.Any)]): 
- `node` (ast.ClassDef): 
- `source_code` (str): 
**Returns:** None

#### `_determine_method_visibility`

**Parameters:**
- `self` (): 
- `method_name` (str): 
**Returns:** str

#### `_extract_function_info`

**Parameters:**
- `self` (): 
- `node` (ast.FunctionDef): 
- `source_code` (str): 
**Returns:** dict[(str, t.Any)]

#### `_extract_protocol_info`

**Parameters:**
- `self` (): 
- `node` (ast.ClassDef): 
- `source_code` (str): 
**Returns:** dict[(str, t.Any)]

#### `_extract_service_info`

**Parameters:**
- `self` (): 
- `tree` (ast.AST): 
- `file_path` (Path): 
- `source_code` (str): 
**Returns:** dict[(str, t.Any)] | None

#### `_create_service_info_structure`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `_populate_service_classes`

**Parameters:**
- `self` (): 
- `service_info` (dict[(str, t.Any)]): 
- `tree` (ast.AST): 
- `source_code` (str): 
**Returns:** None

#### `_process_service_class`

**Parameters:**
- `self` (): 
- `service_info` (dict[(str, t.Any)]): 
- `node` (ast.ClassDef): 
- `source_code` (str): 
**Returns:** None

#### `_extract_implemented_protocols`

**Parameters:**
- `self` (): 
- `service_info` (dict[(str, t.Any)]): 
- `node` (ast.ClassDef): 
**Returns:** None

#### `_add_class_to_service_info`

**Parameters:**
- `self` (): 
- `service_info` (dict[(str, t.Any)]): 
- `class_info` (dict[(str, t.Any)]): 
**Returns:** None

#### `_extract_cli_info`

**Parameters:**
- `self` (): 
- `tree` (ast.AST): 
- `source_code` (str): 
**Returns:** dict[(str, t.Any)]

#### `_extract_class_cli_options`

**Parameters:**
- `self` (): 
- `class_node` (ast.ClassDef): 
- `cli_info` (dict[(str, t.Any)]): 
**Returns:** None

#### `_is_cli_field`

**Parameters:**
- `self` (): 
- `item` (ast.stmt): 
**Returns:** bool

#### `_create_cli_field_info`

**Parameters:**
- `self` (): 
- `item` (ast.AnnAssign): 
**Returns:** dict[(str, t.Any)] | None

#### `_extract_mcp_python_tools`

**Parameters:**
- `self` (): 
- `tree` (ast.AST): 
- `source_code` (str): 
**Returns:** dict[(str, t.Any)] | None

#### `_extract_mcp_markdown_docs`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** dict[(str, t.Any)]

#### `_is_protocol_class`

**Parameters:**
- `self` (): 
- `node` (ast.ClassDef): 
**Returns:** bool

#### `_get_node_name`

**Parameters:**
- `self` (): 
- `node` (ast.AST): 
**Returns:** str

#### `_get_annotation_string`

**Parameters:**
- `self` (): 
- `annotation` (ast.AST | None): 
**Returns:** str

#### `_process_annotation_node`

**Parameters:**
- `self` (): 
- `annotation` (ast.AST): 
**Returns:** str

#### `_process_attribute_annotation`

**Parameters:**
- `self` (): 
- `annotation` (ast.Attribute): 
**Returns:** str

#### `_process_subscript_annotation`

**Parameters:**
- `self` (): 
- `annotation` (ast.Subscript): 
**Returns:** str

#### `_process_union_annotation`

**Parameters:**
- `self` (): 
- `annotation` (ast.BinOp): 
**Returns:** str

#### `_process_tuple_annotation`

**Parameters:**
- `self` (): 
- `annotation` (ast.Tuple): 
**Returns:** str

#### `_get_fallback_annotation`

**Parameters:**
- `self` (): 
- `annotation` (ast.AST): 
**Returns:** str

#### `_extract_import_info`

**Parameters:**
- `self` (): 
- `node` (ast.Import | ast.ImportFrom): 
**Returns:** dict[(str, t.Any)]



## improvement_overseer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/improvement_overseer.py`

## OverseerVerdict



**Base Classes:** None


No methods defined.


## ImprovementOverseer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `model` (str): 
**Returns:** None

#### `build_review_context`

**Parameters:**
- `self` (): 
- `proposal` (ImprovementProposal): 
- `constitution` (str): 
- `failure_context` (str): 
**Returns:** dict[(str, Any)]



## changelog_automation
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/changelog_automation.py`

## ChangelogEntry



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `entry_type` (str): 
- `description` (str): 
- `commit_hash` (str): 
- `breaking_change` (bool): 
**Returns:** None

#### `to_markdown`

**Parameters:**
- `self` (): 
**Returns:** str



## ChangelogGenerator



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console | None): 
- `git_service` (t.Any): 
**Returns:** None

#### `parse_commit_message`

**Parameters:**
- `self` (): 
- `commit_message` (str): 
- `commit_hash` (str): 
**Returns:** ChangelogEntry | None

#### `_parse_non_conventional_commit`

**Parameters:**
- `self` (): 
- `header` (str): 
- `body` (str): 
- `commit_hash` (str): 
**Returns:** ChangelogEntry | None

#### `_format_description`

**Parameters:**
- `self` (): 
- `description` (str): 
- `scope` (str): 
- `commit_type` (str): 
**Returns:** str

#### `generate_changelog_entries`

**Parameters:**
- `self` (): 
- `since_version` (str | None): 
- `target_file` (Path | None): 
**Returns:** dict[(str, list[ChangelogEntry])]

#### `_get_git_commits`

**Parameters:**
- `self` (): 
- `since_version` (str | None): 
**Returns:** str | None

#### `_tag_exists`

**Parameters:**
- `self` (): 
- `tag` (str): 
**Returns:** bool

#### `_build_git_log_command`

**Parameters:**
- `self` (): 
- `since_version` (str | None): 
**Returns:** list[str]

#### `_parse_commits_to_entries`

**Parameters:**
- `self` (): 
- `git_output` (str): 
**Returns:** dict[(str, list[ChangelogEntry])]

#### `_process_commit_line`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** ChangelogEntry | None

#### `_get_full_commit_message`

**Parameters:**
- `self` (): 
- `commit_hash` (str): 
- `fallback_message` (str): 
**Returns:** str

#### `_add_entry_to_collection`

**Parameters:**
- `self` (): 
- `entry` (ChangelogEntry): 
- `entries_by_type` (dict[(str, list[ChangelogEntry])]): 
**Returns:** None

#### `update_changelog`

**Parameters:**
- `self` (): 
- `changelog_path` (Path): 
- `new_version` (str): 
- `entries_by_type` (dict[(str, list[ChangelogEntry])] | None): 
**Returns:** bool

#### `_generate_changelog_section`

**Parameters:**
- `self` (): 
- `version` (str): 
- `entries_by_type` (dict[(str, list[ChangelogEntry])]): 
**Returns:** str

#### `_insert_new_section`

**Parameters:**
- `self` (): 
- `existing_content` (str): 
- `new_section` (str): 
**Returns:** str

#### `generate_changelog_from_commits`

**Parameters:**
- `self` (): 
- `changelog_path` (Path): 
- `version` (str): 
- `since_version` (str | None): 
**Returns:** bool

#### `_display_changelog_preview`

**Parameters:**
- `self` (): 
- `entries_by_type` (dict[(str, list[ChangelogEntry])]): 
**Returns:** None



## cache
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/cache.py`

## CacheStats



**Base Classes:** None


#### `hit_rate`

**Parameters:**
- `self` (): 
**Returns:** float

#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## CrackerjackCache



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `cache_dir` (Path | None): 
- `enable_disk_cache` (bool): 
- `backend` (Any | None): 
**Returns:** None

#### `_run_async`

**Parameters:**
- `coro` (Awaitable[Any]): 
**Returns:** Any

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

**Parameters:**
- `self` (): 
- `hook_name` (str): 
- `file_hashes` (list[str]): 
- `tool_version` (str | None): 
**Returns:** HookResult | None

#### `set_expensive_hook_result`

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
**Returns:** Any | None

#### `set_config_data`

**Parameters:**
- `self` (): 
- `config_key` (str): 
- `data` (Any): 
**Returns:** None

#### `get`

**Parameters:**
- `self` (): 
- `key` (str): 
- `default` (Any): 
**Returns:** Any

#### `set`

**Parameters:**
- `self` (): 
- `key` (str): 
- `value` (Any): 
- `ttl_seconds` (int | None): 
**Returns:** None

#### `get_agent_decision`

**Parameters:**
- `self` (): 
- `agent_name` (str): 
- `issue_hash` (str): 
**Returns:** Any | None

#### `set_agent_decision`

**Parameters:**
- `self` (): 
- `agent_name` (str): 
- `issue_hash` (str): 
- `decision` (Any): 
**Returns:** None

#### `get_quality_baseline`

**Parameters:**
- `self` (): 
- `git_hash` (str): 
**Returns:** dict[(str, Any)] | None

#### `set_quality_baseline`

**Parameters:**
- `self` (): 
- `git_hash` (str): 
- `metrics` (dict[(str, Any)]): 
**Returns:** None

#### `invalidate_hook_cache`

**Parameters:**
- `hook_name` (str | None): 
**Returns:** None

#### `cleanup_all`

**Returns:** dict[(str, int)]

#### `get_cache_stats`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]

#### `_get_hook_cache_key`

**Parameters:**
- `hook_name` (str): 
- `file_hashes` (list[str]): 
**Returns:** str

#### `_get_versioned_hook_cache_key`

**Parameters:**
- `self` (): 
- `hook_name` (str): 
- `file_hashes` (list[str]): 
- `tool_version` (str | None): 
**Returns:** str



## log_manager
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/log_manager.py`

## LogManager



**Base Classes:** None


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
**Returns:** dict[(str, dict[(str, int | str | float)])]

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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/config_merge.py`

**Implements Protocols:**
- ConfigMergeServiceProtocol

## ConfigMergeService



**Base Classes:** ConfigMergeServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (ConsoleInterface | None): 
- `filesystem` (FileSystemInterface | None): 
- `git_service` (GitInterface | None): 
- `logger` (t.Any | None): 
**Returns:** None

#### `smart_merge_pyproject`

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

#### `smart_merge_pre_commit_config`

**Parameters:**
- `self` (): 
- `source_content` (dict[(str, t.Any)]): 
- `target_path` (str | t.Any): 
- `project_name` (str): 
**Returns:** dict[(str, t.Any)]

#### `write_pre_commit_config`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
- `target_path` (str | t.Any): 
**Returns:** None

#### `write_pyproject_config`

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

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None



## ParsedContent



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None



## documentation_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/documentation_service.py`

**Implements Protocols:**
- DocumentationServiceProtocol

## DocumentationServiceImpl



**Base Classes:** DocumentationServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `pkg_path` (Path): 
- `api_extractor` (APIExtractorProtocol | None): 
- `doc_generator` (DocumentationGeneratorProtocol | None): 
**Returns:** None

#### `_categorize_source_files`

**Parameters:**
- `self` (): 
- `source_paths` (list[Path]): 
**Returns:** dict[(str, list[Path])]

#### `_extract_specialized_apis`

**Parameters:**
- `self` (): 
- `categorized_files` (dict[(str, list[Path])]): 
**Returns:** dict[(str, t.Any)]

#### `extract_api_documentation`

**Parameters:**
- `self` (): 
- `source_paths` (list[Path]): 
**Returns:** dict[(str, t.Any)]

#### `generate_documentation`

**Parameters:**
- `self` (): 
- `template_name` (str): 
- `context` (dict[(str, t.Any)]): 
**Returns:** str

#### `validate_documentation`

**Parameters:**
- `self` (): 
- `doc_paths` (list[Path]): 
**Returns:** list[dict[(str, t.Any)]]

#### `update_documentation_index`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `get_documentation_coverage`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `_find_source_files`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `_count_documentation_items`

**Parameters:**
- `self` (): 
- `api_data` (dict[(str, t.Any)]): 
**Returns:** tuple[(int, int)]

#### `_count_protocol_items`

**Parameters:**
- `self` (): 
- `protocols` (dict[(str, t.Any)]): 
**Returns:** tuple[(int, int)]

#### `_count_module_items`

**Parameters:**
- `self` (): 
- `modules` (dict[(str, t.Any)]): 
**Returns:** tuple[(int, int)]

#### `_count_class_items`

**Parameters:**
- `self` (): 
- `classes` (list[dict[(str, t.Any)]]): 
**Returns:** tuple[(int, int)]

#### `_count_function_items`

**Parameters:**
- `self` (): 
- `functions` (list[dict[(str, t.Any)]]): 
**Returns:** tuple[(int, int)]

#### `_count_method_items`

**Parameters:**
- `self` (): 
- `methods` (list[dict[(str, t.Any)]]): 
**Returns:** tuple[(int, int)]

#### `generate_full_api_documentation`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_ensure_directories`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_check_internal_links`

**Parameters:**
- `self` (): 
- `content` (str): 
- `doc_path` (Path): 
**Returns:** list[dict[(str, t.Any)]]

#### `_check_empty_sections`

**Parameters:**
- `self` (): 
- `content` (str): 
- `doc_path` (Path): 
**Returns:** list[dict[(str, t.Any)]]

#### `_check_version_references`

**Parameters:**
- `self` (): 
- `content` (str): 
- `doc_path` (Path): 
**Returns:** list[dict[(str, t.Any)]]

#### `_generate_index_content`

**Parameters:**
- `self` (): 
- `api_docs` (list[Path]): 
- `guide_docs` (list[Path]): 
- `root_docs` (list[Path]): 
**Returns:** str

#### `_generate_protocol_documentation`

**Parameters:**
- `self` (): 
- `protocols` (dict[(str, t.Any)]): 
**Returns:** str

#### `_generate_service_documentation`

**Parameters:**
- `self` (): 
- `services` (dict[(str, t.Any)]): 
**Returns:** str

#### `_generate_service_section`

**Parameters:**
- `self` (): 
- `service_name` (str): 
- `service_info` (dict[(str, t.Any)]): 
**Returns:** list[str]

#### `_generate_protocols_implemented`

**Parameters:**
- `self` (): 
- `protocols` (list[str]): 
**Returns:** list[str]

#### `_generate_service_classes`

**Parameters:**
- `self` (): 
- `classes` (list[dict[(str, t.Any)]]): 
**Returns:** list[str]

#### `_generate_public_methods`

**Parameters:**
- `self` (): 
- `methods` (list[dict[(str, t.Any)]]): 
**Returns:** list[str]

#### `_generate_cli_documentation`

**Parameters:**
- `self` (): 
- `commands` (dict[(str, t.Any)]): 
**Returns:** str

#### `_format_cross_references`

**Parameters:**
- `self` (): 
- `cross_refs` (dict[(str, list[str])]): 
**Returns:** str

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None



## heatmap_generator
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/heatmap_generator.py`

## HeatMapCell



**Base Classes:** None


No methods defined.


## HeatMapData



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## HeatMapGenerator



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `add_error_data`

**Parameters:**
- `self` (): 
- `file_path` (str): 
- `line_number` (int): 
- `error_type` (str): 
- `severity` (str): 
- `timestamp` (datetime | None): 
- `metadata` (dict[(str, t.Any)] | None): 
**Returns:** None

#### `add_metric_data`

**Parameters:**
- `self` (): 
- `identifier` (str): 
- `metrics` (dict[(str, float)]): 
- `metadata` (dict[(str, t.Any)] | None): 
**Returns:** None

#### `generate_error_frequency_heatmap`

**Parameters:**
- `self` (): 
- `time_window` (timedelta): 
- `granularity` (str): 
**Returns:** HeatMapData

#### `_get_time_bucket_config`

**Parameters:**
- `self` (): 
- `time_window` (timedelta): 
- `granularity` (str): 
**Returns:** dict[(str, t.Any)]

#### `_create_time_buckets`

**Parameters:**
- `self` (): 
- `start_time` (datetime): 
- `bucket_config` (dict[(str, t.Any)]): 
**Returns:** list[datetime]

#### `_build_error_matrix`

**Parameters:**
- `self` (): 
- `start_time` (datetime): 
- `end_time` (datetime): 
- `time_buckets` (list[datetime]): 
- `bucket_config` (dict[(str, t.Any)]): 
**Returns:** dict[(str, t.Any)]

#### `_find_time_bucket_index`

**Parameters:**
- `self` (): 
- `error_time` (datetime): 
- `start_time` (datetime): 
- `time_buckets` (list[datetime]): 
- `bucket_size` (timedelta): 
**Returns:** int

#### `_create_frequency_cells`

**Parameters:**
- `self` (): 
- `file_paths` (list[str]): 
- `time_buckets` (list[datetime]): 
- `error_matrix` (dict[(str, t.Any)]): 
**Returns:** list[HeatMapCell]

#### `_create_frequency_labels`

**Parameters:**
- `self` (): 
- `file_paths` (list[str]): 
- `time_buckets` (list[datetime]): 
- `x_label_format` (str): 
**Returns:** tuple[(list[str], list[str])]

#### `_calculate_max_errors`

**Parameters:**
- `self` (): 
- `error_matrix` (dict[(str, t.Any)]): 
**Returns:** int

#### `generate_code_complexity_heatmap`

**Parameters:**
- `self` (): 
- `project_root` (str | Path): 
**Returns:** HeatMapData

#### `_extract_file_complexity_data`

**Parameters:**
- `self` (): 
- `dependency_graph` (DependencyGraph): 
- `project_root` (Path): 
**Returns:** dict[(str, t.Any)]

#### `_create_complexity_cells`

**Parameters:**
- `self` (): 
- `file_complexity` (dict[(str, t.Any)]): 
**Returns:** list[HeatMapCell]

#### `_create_complexity_cell`

**Parameters:**
- `self` (): 
- `x` (int): 
- `y` (int): 
- `func_data` (dict[(str, t.Any)]): 
- `file_path` (str): 
**Returns:** HeatMapCell

#### `_get_complexity_level`

**Parameters:**
- `self` (): 
- `complexity` (int): 
**Returns:** str

#### `_create_complexity_labels`

**Parameters:**
- `self` (): 
- `file_complexity` (dict[(str, t.Any)]): 
- `cells` (list[HeatMapCell]): 
**Returns:** tuple[(list[str], list[str])]

#### `_calculate_max_complexity`

**Parameters:**
- `self` (): 
- `file_complexity` (dict[(str, t.Any)]): 
**Returns:** int

#### `generate_quality_metrics_heatmap`

**Parameters:**
- `self` (): 
**Returns:** HeatMapData

#### `_get_default_quality_heatmap`

**Parameters:**
- `self` (): 
**Returns:** HeatMapData

#### `_get_quality_metric_types`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `_calculate_metric_max_values`

**Parameters:**
- `self` (): 
- `metric_types` (list[str]): 
**Returns:** dict[(str, float)]

#### `_create_quality_metric_cells`

**Parameters:**
- `self` (): 
- `identifiers` (list[str]): 
- `metric_types` (list[str]): 
- `max_values` (dict[(str, float)]): 
**Returns:** list[HeatMapCell]

#### `_calculate_quality_score`

**Parameters:**
- `self` (): 
- `metric_type` (str): 
- `intensity` (float): 
**Returns:** float

#### `_determine_quality_level`

**Parameters:**
- `self` (): 
- `quality_score` (float): 
**Returns:** str

#### `generate_test_failure_heatmap`

**Parameters:**
- `self` (): 
- `time_window` (timedelta): 
**Returns:** HeatMapData

#### `_filter_test_errors`

**Parameters:**
- `self` (): 
- `time_window` (timedelta): 
**Returns:** list[dict[(str, t.Any)]]

#### `_group_test_errors_by_matrix`

**Parameters:**
- `self` (): 
- `test_errors` (list[dict[(str, t.Any)]]): 
**Returns:** defaultdict[(str, defaultdict[(str, int)])]

#### `_collect_error_types`

**Parameters:**
- `self` (): 
- `test_matrix` (defaultdict[(str, defaultdict[(str, int)])]): 
**Returns:** list[str]

#### `_calculate_max_test_failures`

**Parameters:**
- `self` (): 
- `test_matrix` (defaultdict[(str, defaultdict[(str, int)])]): 
**Returns:** int

#### `_create_test_failure_cells`

**Parameters:**
- `self` (): 
- `test_matrix` (defaultdict[(str, defaultdict[(str, int)])]): 
- `test_files` (list[str]): 
- `error_types` (list[str]): 
- `max_failures` (int): 
**Returns:** list[HeatMapCell]

#### `_build_test_failure_metadata`

**Parameters:**
- `self` (): 
- `time_window` (timedelta): 
- `max_failures` (int): 
- `test_files` (list[str]): 
- `error_types` (list[str]): 
**Returns:** dict[(str, t.Any)]

#### `export_heatmap_data`

**Parameters:**
- `self` (): 
- `heatmap` (HeatMapData): 
- `output_path` (str | Path): 
- `format_type` (str): 
**Returns:** None

#### `generate_html_visualization`

**Parameters:**
- `self` (): 
- `heatmap` (HeatMapData): 
**Returns:** str



## file_filter
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/file_filter.py`

**Implements Protocols:**
- SmartFileFilterProtocol

- ServiceProtocol

## SmartFileFilter



**Base Classes:** SmartFileFilterProtocol, ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `git_service` (GitServiceProtocol): 
- `project_root` (Path | None): 
- `full_scan_threshold` (int): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

#### `get_changed_files`

**Parameters:**
- `self` (): 
- `since` (str): 
**Returns:** list[Path]

#### `get_staged_files`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `get_unstaged_files`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `filter_by_pattern`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
- `pattern` (str): 
**Returns:** list[Path]

#### `filter_by_tool`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
- `tool` (str): 
**Returns:** list[Path]

#### `get_all_modified_files`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `filter_by_extensions`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
- `extensions` (list[str]): 
**Returns:** list[Path]

#### `get_python_files`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** list[Path]

#### `get_markdown_files`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** list[Path]

#### `get_changed_python_files_incremental`

**Parameters:**
- `self` (): 
- `base_branch` (str): 
- `since` (str): 
**Returns:** list[Path]

#### `get_all_python_files_in_package`

**Parameters:**
- `self` (): 
- `package_dir` (Path | None): 
**Returns:** list[Path]

#### `should_include`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** bool

#### `filter_files`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** list[Path]

#### `should_use_incremental_scan`

**Parameters:**
- `self` (): 
- `base_branch` (str): 
**Returns:** bool

#### `get_files_for_qa_scan`

**Parameters:**
- `self` (): 
- `package_dir` (Path | None): 
- `base_branch` (str): 
- `force_incremental` (bool): 
- `force_full` (bool): 
**Returns:** list[Path]



## secure_subprocess
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/secure_subprocess.py`

## SecurityError



**Base Classes:** Exception


No methods defined.


## CommandValidationError



**Base Classes:** SecurityError


No methods defined.


## EnvironmentValidationError



**Base Classes:** SecurityError


No methods defined.


## SubprocessSecurityConfig



**Base Classes:** None


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
**Returns:** None



## SecureSubprocessExecutor



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `config` (SubprocessSecurityConfig | None): 
**Returns:** None

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
**Returns:** tuple[(list[str], list[str])]

#### `_has_dangerous_patterns`

**Parameters:**
- `self` (): 
- `arg` (str): 
- `index` (int): 
- `issues` (list[str]): 
- `command` (list[str]): 
**Returns:** bool

#### `_is_allowed_git_pattern`

**Parameters:**
- `self` (): 
- `arg` (str): 
**Returns:** bool

#### `_check_dangerous_patterns_in_commit_message`

**Parameters:**
- `self` (): 
- `arg` (str): 
- `index` (int): 
- `issues` (list[str]): 
**Returns:** bool

#### `_check_dangerous_patterns_in_other_contexts`

**Parameters:**
- `self` (): 
- `arg` (str): 
- `index` (int): 
- `issues` (list[str]): 
**Returns:** bool

#### `_is_git_commit_message`

**Parameters:**
- `self` (): 
- `index` (int): 
- `command` (list[str]): 
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



## smart_scheduling
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/smart_scheduling.py`

**Implements Protocols:**
- SmartSchedulingServiceProtocol

- ServiceProtocol

## SmartSchedulingService



**Base Classes:** SmartSchedulingServiceProtocol, ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `console` (Console | None): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
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



## smart_file_filter_v2
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/smart_file_filter_v2.py`

**Implements Protocols:**
- ServiceProtocol

## SmartFileFilterV2



**Base Classes:** ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `repo_path` (Path): 
- `use_incremental` (bool): 
- `full_scan_interval_days` (int): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

#### `get_files_for_scan`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `force_incremental` (bool): 
**Returns:** list[Path]

#### `mark_scan_complete`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `files` (list[Path]): 
- `was_full_scan` (bool): 
**Returns:** None



## prompt_evolution
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/prompt_evolution.py`

## FailedFixAttempt



**Base Classes:** None


No methods defined.


## SuccessfulFixPattern



**Base Classes:** None


No methods defined.


## PromptEvolution



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `storage_path` (Path | None): 
**Returns:** None

#### `record_failed_fix`

**Parameters:**
- `self` (): 
- `issue` (Issue): 
- `attempted_fix` (str): 
- `failure_reason` (str): 
- `context` (dict[(str, str)] | None): 
**Returns:** None

#### `record_successful_fix`

**Parameters:**
- `self` (): 
- `issue` (Issue): 
- `before_code` (str): 
- `after_code` (str): 
**Returns:** None

#### `get_evolved_prompt`

**Parameters:**
- `self` (): 
- `issue` (Issue): 
- `base_prompt` (str): 
**Returns:** str

#### `analyze_failure_patterns`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, list[str])]

#### `get_success_rate`

**Parameters:**
- `self` (): 
- `issue_type` (str): 
- `error_code` (str): 
**Returns:** float

#### `_extract_error_code`

**Parameters:**
- `self` (): 
- `message` (str): 
**Returns:** str

#### `_generate_pattern_description`

**Parameters:**
- `self` (): 
- `before` (str): 
- `after` (str): 
**Returns:** str

#### `_save_state`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_load_state`

**Parameters:**
- `self` (): 
**Returns:** None



## security_logger
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/security_logger.py`

## SecurityEventType



**Base Classes:** StrEnum


No methods defined.


## SecurityEventLevel



**Base Classes:** StrEnum


No methods defined.


## SecurityEvent



**Base Classes:** BaseModel


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## SecurityLogger



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `logger_name` (str): 
**Returns:** None

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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/intelligent_commit.py`

## CommitMessageGenerator



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `git_service` (GitInterface): 
- `console` (Console | None): 
**Returns:** None

#### `generate_commit_message`

**Parameters:**
- `self` (): 
- `include_body` (bool): 
- `conventional_commits` (bool): 
**Returns:** str

#### `_analyze_changes`

**Parameters:**
- `self` (): 
- `staged_files` (list[str]): 
**Returns:** dict[(str, t.Any)]

#### `_determine_commit_type`

**Parameters:**
- `self` (): 
- `analysis` (dict[(str, t.Any)]): 
**Returns:** str

#### `_get_commit_type_checks`

**Parameters:**
- `self` (): 
**Returns:** list[tuple[(str, t.Callable[(Ellipsis, t.Any)])]]

#### `_is_fix_commit`

**Parameters:**
- `self` (): 
- `patterns` (set[t.Any]): 
- `files` (list[t.Any]): 
- `file_types` (set[t.Any]): 
**Returns:** bool

#### `_is_feat_commit`

**Parameters:**
- `self` (): 
- `patterns` (set[t.Any]): 
- `files` (list[t.Any]): 
- `file_types` (set[t.Any]): 
**Returns:** bool

#### `_is_test_commit`

**Parameters:**
- `self` (): 
- `patterns` (set[t.Any]): 
- `files` (list[t.Any]): 
- `file_types` (set[t.Any]): 
**Returns:** bool

#### `_is_docs_commit`

**Parameters:**
- `self` (): 
- `patterns` (set[t.Any]): 
- `files` (list[t.Any]): 
- `file_types` (set[t.Any]): 
**Returns:** bool

#### `_is_style_commit`

**Parameters:**
- `self` (): 
- `patterns` (set[t.Any]): 
- `files` (list[t.Any]): 
- `file_types` (set[t.Any]): 
**Returns:** bool

#### `_is_refactor_commit`

**Parameters:**
- `self` (): 
- `patterns` (set[t.Any]): 
- `files` (list[t.Any]): 
- `file_types` (set[t.Any]): 
**Returns:** bool

#### `_determine_scope`

**Parameters:**
- `self` (): 
- `analysis` (dict[(str, t.Any)]): 
**Returns:** str | None

#### `_generate_subject`

**Parameters:**
- `self` (): 
- `analysis` (dict[(str, t.Any)]): 
**Returns:** str

#### `_build_conventional_header`

**Parameters:**
- `self` (): 
- `commit_type` (str): 
- `scope` (str | None): 
- `subject` (str): 
**Returns:** str

#### `_generate_body`

**Parameters:**
- `self` (): 
- `analysis` (dict[(str, t.Any)]): 
**Returns:** str

#### `commit_with_generated_message`

**Parameters:**
- `self` (): 
- `include_body` (bool): 
- `conventional_commits` (bool): 
- `dry_run` (bool): 
**Returns:** bool



## config_template
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/config_template.py`

## ConfigUpdateInfo



**Base Classes:** None


No methods defined.


## ConfigVersion



**Base Classes:** None


No methods defined.


## ConfigTemplateService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console): 
- `pkg_path` (Path): 
**Returns:** None

#### `_load_config_templates`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, ConfigVersion)]

#### `_create_pyproject_template`

**Parameters:**
- `self` (): 
**Returns:** ConfigVersion

#### `_build_pyproject_tools`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `_build_ruff_config`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `_build_pytest_config`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `get_template`

**Parameters:**
- `self` (): 
- `config_type` (str): 
- `version` (str | None): 
**Returns:** ConfigVersion | None

#### `check_updates`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
**Returns:** dict[(str, ConfigUpdateInfo)]

#### `_load_current_versions`

**Parameters:**
- `self` (): 
- `version_file` (Path): 
**Returns:** dict[(str, str)]

#### `_version_compare`

**Parameters:**
- `self` (): 
- `version1` (str): 
- `version2` (str): 
**Returns:** int

#### `_generate_diff_preview`

**Parameters:**
- `self` (): 
- `config_type` (str): 
- `project_path` (Path): 
**Returns:** str

#### `_create_config_diff`

**Parameters:**
- `self` (): 
- `current` (dict[(str, t.Any)]): 
- `new` (dict[(str, t.Any)]): 
**Returns:** str

#### `_collect_config_changes`

**Parameters:**
- `self` (): 
- `current` (dict[(str, t.Any)]): 
- `new` (dict[(str, t.Any)]): 
- `changes` (list[str]): 
- `path` (str): 
**Returns:** None

#### `_collect_additions_and_modifications`

**Parameters:**
- `self` (): 
- `current` (dict[(str, t.Any)]): 
- `new` (dict[(str, t.Any)]): 
- `changes` (list[str]): 
- `path` (str): 
**Returns:** None

#### `_collect_removals`

**Parameters:**
- `self` (): 
- `current` (dict[(str, t.Any)]): 
- `new` (dict[(str, t.Any)]): 
- `changes` (list[str]): 
- `path` (str): 
**Returns:** None

#### `_is_nested_dict`

**Parameters:**
- `self` (): 
- `new_value` (t.Any): 
- `current_value` (t.Any): 
**Returns:** bool

#### `apply_update`

**Parameters:**
- `self` (): 
- `config_type` (str): 
- `project_path` (Path): 
- `interactive` (bool): 
**Returns:** bool

#### `_apply_pyproject_update`

**Parameters:**
- `self` (): 
- `template` (ConfigVersion): 
- `project_path` (Path): 
- `interactive` (bool): 
**Returns:** bool

#### `_confirm_update`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_update_version_tracking`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `config_type` (str): 
- `version` (str): 
**Returns:** None

#### `_invalidate_cache`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
**Returns:** None

#### `get_config_hash`

**Parameters:**
- `self` (): 
- `config_path` (Path): 
**Returns:** str

#### `list_available_templates`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, str)]



## initialization
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/initialization.py`

## InitializationService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (t.Any | None): 
- `filesystem` (FileSystemService | None): 
- `git_service` (GitService | None): 
- `pkg_path` (Path | None): 
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
- `template` (str | None): 
- `interactive` (bool): 
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

#### `_apply_merge_strategy`

**Parameters:**
- `self` (): 
- `merge_strategy` (str): 
- `source_file` (Path): 
- `target_file` (Path): 
- `file_name` (str): 
- `project_name` (str): 
- `force` (bool): 
- `results` (dict[(str, t.Any)]): 
**Returns:** None

#### `_handle_replace_if_missing`

**Parameters:**
- `self` (): 
- `source_file` (Path): 
- `target_file` (Path): 
- `file_name` (str): 
- `project_name` (str): 
- `force` (bool): 
- `results` (dict[(str, t.Any)]): 
**Returns:** None

#### `_handle_default_strategy`

**Parameters:**
- `self` (): 
- `source_file` (Path): 
- `target_file` (Path): 
- `file_name` (str): 
- `project_name` (str): 
- `force` (bool): 
- `results` (dict[(str, t.Any)]): 
**Returns:** None

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

#### `_apply_template`

**Parameters:**
- `self` (): 
- `target_path` (Path): 
- `package_name` (str): 
- `template_name` (str | None): 
- `interactive` (bool): 
- `force` (bool): 
- `results` (dict[(str, t.Any)]): 
**Returns:** None



## status_authentication
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/status_authentication.py`

## AccessLevel



**Base Classes:** StrEnum


No methods defined.


## AuthenticationMethod



**Base Classes:** StrEnum


No methods defined.


## AuthCredentials



**Base Classes:** None


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


No methods defined.


## AccessDeniedError



**Base Classes:** AuthenticationError


No methods defined.


## ExpiredCredentialsError



**Base Classes:** AuthenticationError


No methods defined.


## StatusAuthenticator



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `secret_key` (str | None): 
- `default_access_level` (AccessLevel): 
- `enable_local_only` (bool): 
**Returns:** None

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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/status_security_manager.py`

## StatusSecurityError



**Base Classes:** Exception


No methods defined.


## AccessDeniedError



**Base Classes:** StatusSecurityError


No methods defined.


## ResourceLimitExceededError



**Base Classes:** StatusSecurityError


No methods defined.


## RateLimitExceededError



**Base Classes:** StatusSecurityError


No methods defined.


## StatusSecurityManager



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `max_concurrent_requests` (int): 
- `rate_limit_per_minute` (int): 
- `max_resource_usage_mb` (int): 
- `allowed_paths` (set[str] | None): 
**Returns:** None

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


#### `__init__`

**Parameters:**
- `self` (): 
- `security_manager` (StatusSecurityManager): 
- `request_id` (str): 
- `client_id` (str): 
- `operation` (str): 
**Returns:** None



## version_analyzer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/version_analyzer.py`

## VersionBumpType



**Base Classes:** Enum


No methods defined.


## VersionBumpRecommendation



**Base Classes:** None


No methods defined.


## BreakingChangeAnalyzer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `analyze`

**Parameters:**
- `self` (): 
- `entries` (list[ChangelogEntry]): 
**Returns:** tuple[(bool, list[str], float)]



## FeatureAnalyzer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `analyze`

**Parameters:**
- `self` (): 
- `entries` (list[ChangelogEntry]): 
**Returns:** tuple[(bool, list[str], list[str], float)]



## ConventionalCommitAnalyzer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `analyze`

**Parameters:**
- `self` (): 
- `entries` (list[ChangelogEntry]): 
**Returns:** dict[(str, Any)]



## VersionAnalyzer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `git_service` (GitService): 
- `console` (Console | None): 
**Returns:** None

#### `_get_current_version`

**Parameters:**
- `self` (): 
**Returns:** str | None

#### `_calculate_next_version`

**Parameters:**
- `self` (): 
- `current` (str): 
- `bump_type` (VersionBumpType): 
**Returns:** str

#### `_is_pre_release`
Return True when ``version`` is a pre-1.0.0 release (major == 0).
**Parameters:**
- `version` (str | None): 
**Returns:** bool

#### `_collect_changelog_entries`

**Parameters:**
- `self` (): 
- `since_version` (str | None): 
**Returns:** list[ChangelogEntry]

#### `_create_no_changes_recommendation`

**Parameters:**
- `self` (): 
- `current_version` (str): 
**Returns:** VersionBumpRecommendation

#### `_analyze_entries_and_recommend`

**Parameters:**
- `self` (): 
- `current_version` (str): 
- `all_entries` (list[ChangelogEntry]): 
**Returns:** VersionBumpRecommendation

#### `_determine_bump_type`

**Parameters:**
- `self` (): 
- `has_breaking` (bool): 
- `breaking_changes` (list[str]): 
- `breaking_confidence` (float): 
- `has_features` (bool): 
- `new_features` (list[str]): 
- `feature_confidence` (float): 
- `bug_fixes` (list[str]): 
- `all_entries` (list[ChangelogEntry]): 
- `confident_features` (list[str] | None): 
- `current_version` (str | None): 
**Returns:** tuple[(VersionBumpType, float, list[str])]

#### `display_recommendation`

**Parameters:**
- `self` (): 
- `recommendation` (VersionBumpRecommendation): 
**Returns:** None

#### `_display_summary`

**Parameters:**
- `self` (): 
- `recommendation` (VersionBumpRecommendation): 
**Returns:** None

#### `_display_reasoning`

**Parameters:**
- `self` (): 
- `recommendation` (VersionBumpRecommendation): 
**Returns:** None

#### `_display_changes`

**Parameters:**
- `self` (): 
- `recommendation` (VersionBumpRecommendation): 
**Returns:** None

#### `_display_change_list`

**Parameters:**
- `self` (): 
- `changes` (list[str]): 
- `title` (str): 
- `color` (str): 
**Returns:** None

#### `_display_commit_analysis`

**Parameters:**
- `self` (): 
- `recommendation` (VersionBumpRecommendation): 
**Returns:** None



## thread_safe_status_collector
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/thread_safe_status_collector.py`

## StatusSnapshot



**Base Classes:** None


No methods defined.


## ThreadSafeStatusCollector



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `timeout` (float): 
**Returns:** None

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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pattern_detector.py`

## AntiPatternConfig



**Base Classes:** t.TypedDict


No methods defined.


## AntiPattern



**Base Classes:** None


No methods defined.


## PatternDetector



**Base Classes:** None


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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/debug.py`

## AIAgentDebugger



**Base Classes:** None


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

#### `_print_verbose`

**Parameters:**
- `self` (): 
- `message` (str): 
- `level` (str): 
**Returns:** None

#### `_print_debug_header`

**Parameters:**
- `self` (): 
**Returns:** None

#### `debug_operation`

**Parameters:**
- `self` (): 
- `operation` (str): 
**Returns:** t.Generator[str]

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

#### `reset_deduplicator`

**Parameters:**
- `self` (): 
**Returns:** None

#### `export_debug_data`

**Parameters:**
- `self` (): 
- `output_path` (Path | None): 
**Returns:** Path



## NoOpDebugger



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_print_verbose`

**Parameters:**
- `self` (): 
- `message` (str): 
- `level` (str): 
**Returns:** None

#### `reset_deduplicator`

**Parameters:**
- `self` (): 
**Returns:** None

#### `debug_operation`

**Parameters:**
- `self` (): 
- `operation` (str): 
**Returns:** t.Generator[str]

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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/secure_status_formatter.py`

**Implements Protocols:**
- SecureStatusFormatterProtocol

- ServiceProtocol

## StatusVerbosity



**Base Classes:** StrEnum


No methods defined.


## SecureStatusFormatter



**Base Classes:** SecureStatusFormatterProtocol, ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `project_root` (Path | None): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

#### `format_status`

**Parameters:**
- `self` (): 
- `status_data` (dict[(str, t.Any)]): 
- `verbosity` (StatusVerbosity): 
- `user_context` (str | None): 
**Returns:** dict[(str, t.Any)]

#### `format`

**Parameters:**
- `self` (): 
- `status` (t.Any): 
**Returns:** str

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



## git_cleanup_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/git_cleanup_service.py`

## DirtyWorkingTreeError

Raised when the working tree is dirty and unsafe rewrites are forbidden.

**Base Classes:** Exception


No methods defined.


## GitCommandResult



**Base Classes:** None


No methods defined.


## GitCleanupResult



**Base Classes:** None


No methods defined.


## GitCleanupService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console): 
- `pkg_path` (Path): 
- `git_service` (GitInterface): 
- `settings` (CrackerjackSettings | None): 
**Returns:** None

#### `_run_git_command`

**Parameters:**
- `self` (): 
- `args` (list[str]): 
**Returns:** GitCommandResult

#### `settings`

**Parameters:**
- `self` (): 
**Returns:** GitCleanupSettings

#### `cleanup_git_deleted_files`

**Parameters:**
- `self` (): 
- `dry_run` (bool): 
**Returns:** GitCleanupResult

#### `_validate_working_tree_clean`

**Parameters:**
- `self` (): 
**Returns:** tuple[(bool, str | None)]

#### `_load_gitignore_patterns`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `_get_gitignore_changes`

**Parameters:**
- `self` (): 
- `gitignore_patterns` (list[str]): 
**Returns:** list[Path]

#### `_categorize_files`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** tuple[(list[Path], list[Path])]

#### `_remove_from_index_cached`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** int

#### `_remove_from_index_hard`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** int

#### `_suggest_filter_branch`

**Parameters:**
- `self` (): 
- `large_cleanup` (bool): 
**Returns:** bool

#### `_generate_dry_run_summary`

**Parameters:**
- `self` (): 
- `config_files` (list[Path]): 
- `cache_dirs` (list[Path]): 
**Returns:** str

#### `_generate_cleanup_summary`

**Parameters:**
- `self` (): 
- `removed_cached` (int): 
- `removed_hard` (int): 
- `config_files` (list[Path]): 
- `cache_dirs` (list[Path]): 
- `suggest_filter_branch` (bool): 
**Returns:** str



## file_modifier
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/file_modifier.py`

**Implements Protocols:**
- SafeFileModifierProtocol

- ServiceProtocol

## SafeFileModifier



**Base Classes:** SafeFileModifierProtocol, ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `backup_dir` (Path | None): 
- `max_file_size` (int): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

#### `_ensure_backup_dir`

**Parameters:**
- `self` (): 
**Returns:** None

#### `modify_file`

**Parameters:**
- `self` (): 
- `file_path` (Path | str): 
- `new_content` (str): 
**Returns:** None

#### `_validate_fix_inputs`

**Parameters:**
- `self` (): 
- `path` (Path): 
- `fixed_content` (str): 
**Returns:** dict[(str, str | bool | None)]

#### `_validate_python_syntax`

**Parameters:**
- `self` (): 
- `content` (str): 
- `path` (Path): 
**Returns:** dict[(str, str | bool | None)]

#### `_read_original_content`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, str | bool | None)]

#### `_create_dry_run_result`

**Parameters:**
- `self` (): 
- `diff` (str): 
**Returns:** dict[(str, str | bool | None)]

#### `_handle_backup`

**Parameters:**
- `self` (): 
- `path` (Path): 
- `original_content` (str): 
- `create_backup` (bool): 
- `diff` (str): 
**Returns:** dict[(str, t.Any)]

#### `_atomic_write_fix`

**Parameters:**
- `self` (): 
- `path` (Path): 
- `fixed_content` (str): 
- `diff` (str): 
- `backup_path` (Path | None): 
- `file_path` (str): 
**Returns:** dict[(str, t.Any)]

#### `_check_file_exists`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_check_is_symlink`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_check_is_file`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_check_forbidden_patterns`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_check_file_size`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_check_file_writable`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_check_path_traversal`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_check_symlinks_in_path_chain`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_validate_file_path`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, bool | str)]

#### `_create_backup`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `content` (str): 
**Returns:** Path

#### `_restore_backup`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
- `backup_path` (Path): 
**Returns:** None

#### `_generate_diff`

**Parameters:**
- `self` (): 
- `original` (str): 
- `fixed` (str): 
- `filename` (str): 
**Returns:** str



## template_detector
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/template_detector.py`

## TemplateDetector



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (t.Any | None): 
**Returns:** None

#### `detect_template`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
**Returns:** str

#### `_analyze_project`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `config` (dict[(str, t.Any)]): 
**Returns:** dict[(str, bool)]

#### `_has_mcp_dependencies`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
**Returns:** bool

#### `_has_ai_agent_indicators`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `config` (dict[(str, t.Any)]): 
**Returns:** bool

#### `_has_complex_quality_tools`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
**Returns:** bool

#### `_is_library_project`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `config` (dict[(str, t.Any)]): 
**Returns:** bool

#### `_has_complex_dependencies`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
**Returns:** bool

#### `get_template_description`

**Parameters:**
- `self` (): 
- `template` (str): 
**Returns:** str

#### `prompt_manual_selection`

**Parameters:**
- `self` (): 
- `auto_detected` (str): 
**Returns:** str



## config_parsers
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/config_parsers.py`

**Implements Protocols:**
- t.Protocol

## ConfigParser



**Base Classes:** t.Protocol


#### `load`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `save`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
- `path` (Path): 
**Returns:** None

#### `extensions`

**Parameters:**
- `self` (): 
**Returns:** list[str]



## JSONParser



**Base Classes:** None


#### `extensions`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `load`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `save`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
- `path` (Path): 
**Returns:** None



## YAMLParser



**Base Classes:** None


#### `extensions`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `load`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `save`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
- `path` (Path): 
**Returns:** None



## TOMLParser



**Base Classes:** None


#### `extensions`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `load`

**Parameters:**
- `self` (): 
- `path` (Path): 
**Returns:** dict[(str, t.Any)]

#### `save`

**Parameters:**
- `self` (): 
- `config` (dict[(str, t.Any)]): 
- `path` (Path): 
**Returns:** None

#### `_load_toml_from_text`

**Parameters:**
- `content` (str): 
**Returns:** dict[(str, t.Any)]

#### `_dump_toml`

**Parameters:**
- `config` (dict[(str, t.Any)]): 
**Returns:** str



## ConfigParserRegistry



**Base Classes:** None


#### `register`

**Parameters:**
- `cls` (): 
- `parser` (ConfigParser): 
**Returns:** None

#### `get_parser`

**Parameters:**
- `cls` (): 
- `path` (Path | str): 
**Returns:** ConfigParser

#### `get_parser_by_format`

**Parameters:**
- `cls` (): 
- `format` (str): 
**Returns:** ConfigParser

#### `list_formats`

**Parameters:**
- `cls` (): 
**Returns:** list[str]

#### `is_supported`

**Parameters:**
- `cls` (): 
- `path` (Path | str): 
**Returns:** bool



## message_deduplicator
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/message_deduplicator.py`

## MessageDeduplicator



**Base Classes:** None


#### `add_message`

**Parameters:**
- `self` (): 
- `message` (str): 
- `level` (str): 
- `context` (dict[(str, Any)] | None): 
**Returns:** bool

#### `should_show`

**Parameters:**
- `self` (): 
- `message` (str): 
- `level` (str): 
**Returns:** bool

#### `get_duplicates`

**Parameters:**
- `self` (): 
**Returns:** list[dict[(str, Any)]]

#### `get_summary`

**Parameters:**
- `self` (): 
**Returns:** str

#### `print_summary`

**Parameters:**
- `self` (): 
- `console` (Any): 
**Returns:** None

#### `reset`

**Parameters:**
- `self` (): 
**Returns:** None

#### `total_messages`

**Parameters:**
- `self` (): 
**Returns:** int

#### `unique_messages`

**Parameters:**
- `self` (): 
**Returns:** int

#### `duplicate_count`

**Parameters:**
- `self` (): 
**Returns:** int



## config_integrity
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/config_integrity.py`

**Implements Protocols:**
- ConfigIntegrityServiceProtocol

- ServiceProtocol

## ConfigIntegrityService



**Base Classes:** ConfigIntegrityServiceProtocol, ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `project_path` (Path): 
- `console` (Console | None): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/parallel_executor.py`

**Implements Protocols:**
- ParallelHookExecutorProtocol

- ServiceProtocol

- AsyncCommandExecutorProtocol

- ServiceProtocol

## ExecutionStrategy



**Base Classes:** StrEnum


No methods defined.


## ExecutionGroup



**Base Classes:** None


No methods defined.


## ParallelHookExecutor



**Base Classes:** ParallelHookExecutorProtocol, ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `logger` (LoggerProtocol | None): 
- `cache` (PerformanceCacheProtocol | None): 
- `max_workers` (int): 
- `timeout_seconds` (int): 
- `strategy` (ExecutionStrategy): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

#### `analyze_hook_dependencies`

**Parameters:**
- `self` (): 
- `hooks` (list[HookDefinition]): 
**Returns:** dict[(str, list[HookDefinition])]

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



**Base Classes:** AsyncCommandExecutorProtocol, ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `logger` (LoggerProtocol | None): 
- `cache` (PerformanceCacheProtocol | None): 
- `max_workers` (int): 
- `cache_results` (bool): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

#### `_get_cache_key`

**Parameters:**
- `self` (): 
- `command` (list[str]): 
- `cwd` (Path | None): 
**Returns:** str



## pool_router
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pool_router.py`

## PoolRouter



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console | None): 
**Returns:** None

#### `_get_routing_reason`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `worker_type` (str): 
**Returns:** str

#### `get_routing_summary`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## pypistats_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pypistats_service.py`

## DownloadTrendClass



**Base Classes:** StrEnum


No methods defined.


## PackageStatsSnapshot



**Base Classes:** None


No methods defined.


## PypiStatsService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `drop_warn_threshold` (float): 
**Returns:** None

#### `get_snapshot`

**Parameters:**
- `self` (): 
- `package` (str): 
**Returns:** PackageStatsSnapshot | None

#### `classify_download_trend`

**Parameters:**
- `self` (): 
- `snapshot` (PackageStatsSnapshot): 
**Returns:** DownloadTrendClass



## failure_recorder
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/failure_recorder.py`

**Implements Protocols:**
- Protocol

## FixAttemptRecord



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## TrendClassification



**Base Classes:** None


No methods defined.


## _SessionBuddyProtocol



**Base Classes:** Protocol


No methods defined.


## FailureRecorder



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `repository` (FailureMetricsRepository): 
- `session_buddy` (_SessionBuddyProtocol | None): 
- `akosha_mcp_client` (Any | None): 
**Returns:** None



## refurb_fixer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/refurb_fixer.py`

## SafeRefurbFixer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_check_ast_grep`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_run_ast_grep_fix`

**Parameters:**
- `self` (): 
- `content` (str): 
- `rule` (dict): 
**Returns:** tuple[(str, int)]

#### `fix_file`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** int

#### `fix_package`

**Parameters:**
- `self` (): 
- `package_dir` (Path): 
**Returns:** int

#### `_apply_fixes`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb102_ast_grep`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb102_regex`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb107`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_find_furb107_matches`

**Parameters:**
- `self` (): 
- `lines` (list[str]): 
**Returns:** list[tuple[(int, tuple[(int, int | None, str)])]]

#### `_match_try_block`

**Parameters:**
- `self` (): 
- `line` (str): 
- `i` (int): 
- `lines` (list[str]): 
**Returns:** tuple[(int, int | None, str)] | None

#### `_scan_except_handlers`

**Parameters:**
- `self` (): 
- `start` (int): 
- `indent` (str): 
- `body_indent` (str): 
- `lines` (list[str]): 
**Returns:** tuple[(int, int | None, str)] | None

#### `_match_except_line`

**Parameters:**
- `self` (): 
- `line` (str): 
- `indent` (str): 
**Returns:** str | None

#### `_is_inline_pass_except`

**Parameters:**
- `self` (): 
- `lines` (list[str]): 
- `j` (int): 
- `indent` (str): 
- `curr_line` (str): 
**Returns:** bool

#### `_evaluate_pass_except`

**Parameters:**
- `self` (): 
- `lines` (list[str]): 
- `pass_only_except` (tuple[(int, int | None, str)] | None | str): 
- `inline_pass` (bool): 
- `j` (int): 
- `exception_type` (str): 
**Returns:** tuple[(int, int | None, str)] | None | str

#### `_get_body_indent`

**Parameters:**
- `self` (): 
- `j` (int): 
- `lines` (list[str]): 
**Returns:** str

#### `_apply_furb107_fixes`

**Parameters:**
- `self` (): 
- `lines` (list[str]): 
- `matches` (list[tuple[(int, tuple[(int, int | None, str)])]]): 
**Returns:** tuple[(str, int)]

#### `_fix_furb109`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb113`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_collect_append_stmts`

**Parameters:**
- `tree` (): 
**Returns:** list[tuple]

#### `_group_consecutive_appends`

**Parameters:**
- `append_stmts` (list[tuple]): 
**Returns:** list[tuple[(int, int, str, list[str])]]

#### `_apply_extend_replacements`

**Parameters:**
- `content` (str): 
- `spans` (list[tuple[(int, int, str, list[str])]]): 
**Returns:** str

#### `_fix_furb118`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb115`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb126`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb110`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb123`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb142`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb148`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb161`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb124`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb138`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb108`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb117`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb173`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb183`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb143`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb141`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb135`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]

#### `_fix_furb111`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** tuple[(str, int)]



## _StartswithTupleTransformer



**Base Classes:** ast.NodeTransformer


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `visit_BoolOp`

**Parameters:**
- `self` (): 
- `node` (ast.BoolOp): 
**Returns:** ast.AST

#### `_group_startswith_calls`

**Parameters:**
- `self` (): 
- `values` (list[ast.AST]): 
**Returns:** dict[(int, list[ast.Call])]

#### `_try_transform_group`

**Parameters:**
- `self` (): 
- `node` (ast.BoolOp): 
- `calls` (list[ast.Call]): 
**Returns:** ast.AST | None

#### `_extract_string_args`

**Parameters:**
- `self` (): 
- `calls` (list[ast.Call]): 
**Returns:** list[ast.Constant]

#### `_create_combined_call`

**Parameters:**
- `self` (): 
- `template` (ast.Call): 
- `string_args` (list[ast.Constant]): 
**Returns:** ast.Call

#### `_build_replacement`

**Parameters:**
- `self` (): 
- `node` (ast.BoolOp): 
- `calls` (list[ast.Call]): 
- `new_call` (ast.Call): 
**Returns:** ast.AST

#### `_is_startswith_call`

**Parameters:**
- `self` (): 
- `node` (ast.AST): 
**Returns:** bool

#### `_is_simple_string_arg`

**Parameters:**
- `self` (): 
- `call` (ast.Call): 
**Returns:** bool

#### `_get_object_key`

**Parameters:**
- `self` (): 
- `node` (ast.AST): 
**Returns:** int | None



## _MembershipTupleTransformer



**Base Classes:** ast.NodeTransformer


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `visit_Compare`

**Parameters:**
- `self` (): 
- `node` (ast.Compare): 
**Returns:** ast.AST

#### `_should_convert_to_tuple`

**Parameters:**
- `self` (): 
- `op` (ast.cmpop): 
- `comparator` (ast.AST): 
**Returns:** bool

#### `_is_safe_list`

**Parameters:**
- `self` (): 
- `node` (ast.List): 
**Returns:** bool

#### `_is_simple_element`

**Parameters:**
- `self` (): 
- `node` (ast.AST): 
**Returns:** bool



## _ForLoopTupleTransformer



**Base Classes:** ast.NodeTransformer


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `visit_For`

**Parameters:**
- `self` (): 
- `node` (ast.For): 
**Returns:** ast.AST

#### `_is_safe_list`

**Parameters:**
- `self` (): 
- `node` (ast.List): 
**Returns:** bool

#### `_is_simple_element`

**Parameters:**
- `self` (): 
- `node` (ast.AST): 
**Returns:** bool



## config_cleanup
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/config_cleanup.py`

## ConfigCleanupResult



**Base Classes:** None


No methods defined.


## MergeStrategy



**Base Classes:** None


No methods defined.


## ConfigCleanupService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (ConsoleProtocol | None): 
- `pkg_path` (Path | None): 
- `git_service` (GitInterface | None): 
- `settings` (CrackerjackSettings | None): 
**Returns:** None

#### `cleanup_configs`

**Parameters:**
- `self` (): 
- `dry_run` (bool): 
**Returns:** ConfigCleanupResult

#### `rollback_cleanup`

**Parameters:**
- `self` (): 
- `backup_metadata` (BackupMetadata): 
**Returns:** bool

#### `_detect_config_files`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `_detect_cache_dirs`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `_detect_output_files`

**Parameters:**
- `self` (): 
**Returns:** list[Path]

#### `_build_merge_strategies`

**Parameters:**
- `self` (): 
**Returns:** list[MergeStrategy]

#### `_validate_preconditions`

**Parameters:**
- `self` (): 
**Returns:** tuple[(bool, str | None)]

#### `_create_backup`

**Parameters:**
- `self` (): 
- `files` (list[Path]): 
**Returns:** BackupMetadata | None

#### `_calculate_backup_checksum`

**Parameters:**
- `self` (): 
- `file_checksums` (dict[(str, str)]): 
**Returns:** str

#### `_merge_all_configs`

**Parameters:**
- `self` (): 
- `config_files` (list[Path]): 
- `dry_run` (bool): 
**Returns:** tuple[(int, dict[(str, str)])]

#### `_load_pyproject_config`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)] | None

#### `_merge_config_files`

**Parameters:**
- `self` (): 
- `config_files` (list[Path]): 
- `pyproject_config` (dict[(str, t.Any)]): 
- `dry_run` (bool): 
**Returns:** tuple[(int, dict[(str, str)])]

#### `_handle_dry_run_merge`

**Parameters:**
- `self` (): 
- `filename` (str): 
- `strategy` (MergeStrategy): 
**Returns:** None

#### `_merge_single_file`

**Parameters:**
- `self` (): 
- `config_file` (Path): 
- `strategy` (MergeStrategy): 
- `pyproject_config` (dict[(str, t.Any)]): 
**Returns:** bool

#### `_apply_merge_strategy`

**Parameters:**
- `self` (): 
- `config_file` (Path): 
- `pyproject_config` (dict[(str, t.Any)]): 
- `strategy` (MergeStrategy): 
**Returns:** dict[(str, t.Any)]

#### `_write_pyproject_config`

**Parameters:**
- `self` (): 
- `pyproject_config` (dict[(str, t.Any)]): 
**Returns:** None

#### `_get_strategy_for_file`

**Parameters:**
- `self` (): 
- `filename` (str): 
**Returns:** MergeStrategy | None

#### `_merge_ini_file`

**Parameters:**
- `self` (): 
- `ini_file` (Path): 
- `pyproject_config` (dict): 
- `target_section` (str): 
**Returns:** dict

#### `_convert_ini_value`

**Parameters:**
- `self` (): 
- `value` (str): 
**Returns:** str | bool | int

#### `_merge_pattern_file`

**Parameters:**
- `self` (): 
- `pattern_file` (Path): 
- `pyproject_config` (dict): 
- `target_section` (str): 
**Returns:** dict

#### `_merge_json_file`

**Parameters:**
- `self` (): 
- `json_file` (Path): 
- `pyproject_config` (dict): 
- `target_section` (str): 
**Returns:** dict

#### `_get_target_section`

**Parameters:**
- `self` (): 
- `config` (dict): 
- `section_path` (str): 
**Returns:** dict

#### `_merge_json_value`

**Parameters:**
- `self` (): 
- `target_dict` (dict): 
- `key` (str): 
- `value` (t.Any): 
**Returns:** None

#### `_merge_json_lists`

**Parameters:**
- `self` (): 
- `target_dict` (dict): 
- `key` (str): 
- `value` (list): 
**Returns:** None

#### `_merge_json_dicts`

**Parameters:**
- `self` (): 
- `target_dict` (dict): 
- `key` (str): 
- `value` (dict): 
**Returns:** None

#### `_merge_ignore_file`

**Parameters:**
- `self` (): 
- `ignore_file` (Path): 
- `pyproject_config` (dict): 
- `target_section` (str): 
**Returns:** dict

#### `_remove_standalone_configs`

**Parameters:**
- `self` (): 
- `config_files` (list[Path]): 
- `dry_run` (bool): 
**Returns:** int

#### `_cleanup_cache_dirs`

**Parameters:**
- `self` (): 
- `cache_dirs` (list[Path]): 
- `dry_run` (bool): 
**Returns:** int

#### `_cleanup_output_files`

**Parameters:**
- `self` (): 
- `output_files` (list[Path]): 
- `dry_run` (bool): 
**Returns:** int

#### `_generate_summary`

**Parameters:**
- `self` (): 
- `result` (ConfigCleanupResult): 
**Returns:** str

#### `_generate_backup_id`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_smart_merge_gitignore`

**Parameters:**
- `self` (): 
- `dry_run` (bool): 
**Returns:** bool

#### `_display_completion`

**Parameters:**
- `self` (): 
- `result` (ConfigCleanupResult): 
**Returns:** None



## import_resolution
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/import_resolution.py`

## ImportSpec



**Base Classes:** NamedTuple


No methods defined.


## memory_aware_scanner
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/memory_aware_scanner.py`

## MemoryAwareScanner



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console | None): 
- `cache_duration` (int): 
**Returns:** None

#### `_generate_cache_key`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `files` (list[Path]): 
**Returns:** str

#### `_is_known_good`

**Parameters:**
- `self` (): 
- `file_str` (str): 
- `cached_results` (dict[(str, Any)]): 
**Returns:** bool



## tool_version_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/tool_version_service.py`

## ToolVersionService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console | None): 
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



## incremental_scanner
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/incremental_scanner.py`

## IncrementalScanner



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `repo_path` (Path): 
- `full_scan_interval_days` (int): 
**Returns:** None

#### `get_scan_strategy`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `force_full` (bool): 
**Returns:** tuple[(ScanStrategy, list[Path])]

#### `_get_changed_files_git`

**Parameters:**
- `self` (): 
**Returns:** list[Path] | None

#### `_should_force_full_scan`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
**Returns:** bool

#### `_get_all_python_files`

**Parameters:**
- `self` (): 
**Returns:** list[Path]



## command_execution_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/command_execution_service.py`

## CommandExecutionService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `default_timeout` (int): 
**Returns:** None

#### `_get_executable`

**Parameters:**
- `self` (): 
- `cmd` (str | list[str]): 
**Returns:** str

#### `run_command_sync`

**Parameters:**
- `self` (): 
- `cmd` (str | list[str]): 
- `cwd` (str | Path | None): 
- `env` (dict[(str, str)] | None): 
- `timeout` (int | None): 
- `capture_output` (bool): 
- `check` (bool): 
**Returns:** subprocess.CompletedProcess



## memory_optimizer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/memory_optimizer.py`

## MemoryStats



**Base Classes:** None


No methods defined.


## LazyLoader



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `factory` (Callable[([], Any)]): 
- `logger` (LoggerProtocol): 
- `name` (str): 
- `auto_dispose` (bool): 
**Returns:** None

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
**Returns:** None



## ResourcePool



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `factory` (Callable[([], Any)]): 
- `logger` (LoggerProtocol): 
- `max_size` (int): 
- `name` (str): 
**Returns:** None

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


#### `__init__`

**Parameters:**
- `self` (): 
- `logger` (LoggerProtocol): 
**Returns:** None

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


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

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



## bounded_status_operations
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/bounded_status_operations.py`

**Implements Protocols:**
- BoundedStatusOperationsProtocol

- ServiceProtocol

## OperationState



**Base Classes:** StrEnum


No methods defined.


## OperationLimits



**Base Classes:** None


No methods defined.


## OperationMetrics



**Base Classes:** None


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


No methods defined.


## CircuitBreakerOpenError



**Base Classes:** Exception


No methods defined.


## BoundedStatusOperations



**Base Classes:** BoundedStatusOperationsProtocol, ServiceProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `limits` (OperationLimits | None): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/secure_path_utils.py`

## SecurePathValidator



**Base Classes:** None


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



## frontmatter_validator
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/frontmatter_validator.py`

## FrontmatterValidationIssue



**Base Classes:** None


#### `__getitem__`

**Parameters:**
- `self` (): 
- `key` (str): 
**Returns:** str | int



## FrontmatterValidationResult



**Base Classes:** None


#### `from_payload`

**Parameters:**
- `cls` (): 
- `payload` (dict[(str, t.Any)] | list[t.Any]): 
- `exit_success` (bool): 
**Returns:** FrontmatterValidationResult

#### `_from_file_results`

**Parameters:**
- `cls` (): 
- `payload` (list[t.Any]): 
- `exit_success` (bool): 
**Returns:** FrontmatterValidationResult

#### `_issue_from_payload`

**Parameters:**
- `issue` (t.Any): 
**Returns:** FrontmatterValidationIssue



## FrontmatterValidationError



**Base Classes:** Exception


#### `__init__`

**Parameters:**
- `self` (): 
- `message` (str): 
- `result` (FrontmatterValidationResult | None): 
- `reason` (str): 
**Returns:** None



## FrontmatterValidator



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `pkg_path` (Path | None): 
- `timeout_seconds` (int): 
**Returns:** None

#### `validate`

**Parameters:**
- `self` (): 
- `strict` (bool): 
- `allow_nonstandard` (bool): 
- `validate_links` (bool): 
- `store` (str | None): 
- `skip_link_note` (bool): 
- `vocab_path` (Path | None): 
**Returns:** FrontmatterValidationResult

#### `validate_or_raise`

**Parameters:**
- `self` (): 
**Returns:** FrontmatterValidationResult



## config_service
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/config_service.py`

## ConfigService



**Base Classes:** None


#### `load_config`

**Parameters:**
- `path` (str | Path): 
**Returns:** dict[(str, Any)]

#### `validate_config`

**Parameters:**
- `config` (dict[(str, Any)]): 
- `model_class` (type[BaseModel]): 
**Returns:** BaseModel

#### `save_config`

**Parameters:**
- `config` (dict[(str, Any)]): 
- `path` (str | Path): 
- `format` (str | None): 
**Returns:** None

#### `merge_configs`

**Parameters:**
- `base_config` (dict[(str, Any)]): 
- `override_config` (dict[(str, Any)]): 
**Returns:** dict[(str, Any)]



## profiler
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/profiler.py`

## ProfileResult



**Base Classes:** None


#### `mean_time`

**Parameters:**
- `self` (): 
**Returns:** float

#### `median_time`

**Parameters:**
- `self` (): 
**Returns:** float

#### `std_dev_time`

**Parameters:**
- `self` (): 
**Returns:** float

#### `mean_memory`

**Parameters:**
- `self` (): 
**Returns:** float

#### `cache_hit_rate`

**Parameters:**
- `self` (): 
**Returns:** float



## Bottleneck



**Base Classes:** None


No methods defined.


## ComparisonReport



**Base Classes:** None


#### `time_ratio`

**Parameters:**
- `self` (): 
**Returns:** float



## ToolProfiler



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `cache_dir` (Path | None): 
**Returns:** None

#### `profile_tool`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `tool_func` (Callable[([], Any)]): 
- `runs` (int): 
**Returns:** ProfileResult

#### `compare_phases`

**Parameters:**
- `self` (): 
**Returns:** ComparisonReport

#### `identify_bottlenecks`

**Parameters:**
- `self` (): 
**Returns:** list[Bottleneck]

#### `generate_report`

**Parameters:**
- `self` (): 
**Returns:** str



## input_validator
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/input_validator.py`

## ValidationConfig



**Base Classes:** BaseModel


No methods defined.


## ValidationResult



**Base Classes:** BaseModel


No methods defined.


## InputSanitizer



**Base Classes:** None


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

#### `_check_json_depth`

**Parameters:**
- `cls` (): 
- `obj` (t.Any): 
- `max_depth` (int): 
- `current_depth` (int): 
**Returns:** int

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
- `original_is_absolute` (bool): 
**Returns:** ValidationResult



## SecureInputValidator



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `config` (ValidationConfig | None): 
**Returns:** None

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



## workflow_optimization
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/workflow_optimization.py`

## WorkflowRecommendation



**Base Classes:** None


No methods defined.


## WorkflowInsights



**Base Classes:** None


No methods defined.


## WorkflowOptimizationEngine



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `session_metrics` (SessionMetrics): 
**Returns:** None

#### `analyze_velocity_patterns`

**Parameters:**
- `self` (): 
- `days_back` (int): 
**Returns:** dict[(str, float)]

#### `identify_bottlenecks`

**Parameters:**
- `self` (): 
- `quality_metrics` (dict[(str, float)]): 
**Returns:** list[str]

#### `generate_recommendations`

**Parameters:**
- `self` (): 
- `insights` (dict[(str, object)]): 
**Returns:** list[WorkflowRecommendation]

#### `generate_insights`

**Parameters:**
- `self` (): 
**Returns:** WorkflowInsights

#### `_calculate_velocity_score`

**Parameters:**
- `self` (): 
- `velocity` (float): 
**Returns:** float

#### `_calculate_velocity_stability`

**Parameters:**
- `self` (): 
**Returns:** float

#### `_calculate_velocity_trend`

**Parameters:**
- `self` (): 
- `days_back` (int): 
**Returns:** float

#### `_calculate_quality_correlations`

**Parameters:**
- `self` (): 
- `quality_metrics` (dict[(str, float)]): 
**Returns:** dict[(str, float)]



## safe_code_modifier
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/safe_code_modifier.py`

## ValidationSeverity



**Base Classes:** StrEnum


No methods defined.


## ValidationIssue



**Base Classes:** None


No methods defined.


## ValidationResult



**Base Classes:** None


#### `errors`

**Parameters:**
- `self` (): 
**Returns:** list[ValidationIssue]

#### `warnings`

**Parameters:**
- `self` (): 
**Returns:** list[ValidationIssue]



## BackupMetadata



**Base Classes:** None


No methods defined.


## SafeCodeModifier



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (Console): 
- `project_path` (Path): 
- `max_backups` (int): 
**Returns:** None

#### `apply_with_backup`
Write ``new_content`` to ``path``, optionally leaving a ``.bak`` sibling.
**Parameters:**
- `self` (): 
- `new_content` (str): 
**Returns:** None



## predictive_analytics
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/predictive_analytics.py`

**Implements Protocols:**
- t.Protocol

## PredictorProtocol



**Base Classes:** t.Protocol


#### `predict`

**Parameters:**
- `self` (): 
- `values` (list[float]): 
- `periods` (int): 
**Returns:** list[float]



## TrendAnalysis



**Base Classes:** None


No methods defined.


## Prediction



**Base Classes:** None


No methods defined.


## CapacityForecast



**Base Classes:** None


No methods defined.


## MovingAveragePredictor



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `window_size` (int): 
**Returns:** None

#### `predict`

**Parameters:**
- `self` (): 
- `values` (list[float]): 
- `periods` (int): 
**Returns:** list[float]



## LinearTrendPredictor



**Base Classes:** None


#### `predict`

**Parameters:**
- `self` (): 
- `values` (list[float]): 
- `periods` (int): 
**Returns:** list[float]



## SeasonalPredictor



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `season_length` (int): 
**Returns:** None

#### `predict`

**Parameters:**
- `self` (): 
- `values` (list[float]): 
- `periods` (int): 
**Returns:** list[float]



## PredictiveAnalyticsEngine



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `history_limit` (int): 
**Returns:** None

#### `add_metric`

**Parameters:**
- `self` (): 
- `metric_type` (str): 
- `value` (float): 
- `timestamp` (datetime | None): 
**Returns:** None

#### `_update_trend_analysis`

**Parameters:**
- `self` (): 
- `metric_type` (str): 
**Returns:** None

#### `_calculate_trend`

**Parameters:**
- `self` (): 
- `values` (list[float]): 
**Returns:** tuple[(str, float)]

#### `_calculate_confidence_intervals`

**Parameters:**
- `self` (): 
- `historical` (list[float]): 
- `predictions` (list[float]): 
**Returns:** list[tuple[(float, float)]]

#### `predict_metric`

**Parameters:**
- `self` (): 
- `metric_type` (str): 
- `periods_ahead` (int): 
- `predictor_name` (str | None): 
**Returns:** list[Prediction]

#### `_calculate_model_accuracy`

**Parameters:**
- `self` (): 
- `metric_type` (str): 
- `predictor_name` (str): 
**Returns:** float

#### `analyze_capacity_requirements`

**Parameters:**
- `self` (): 
- `resource_type` (str): 
- `current_usage` (float): 
- `threshold` (float): 
**Returns:** CapacityForecast

#### `_generate_capacity_recommendations`

**Parameters:**
- `self` (): 
- `resource_type` (str): 
- `current_usage` (float): 
- `threshold` (float): 
- `estimated_exhaustion` (datetime | None): 
**Returns:** list[str]

#### `get_trend_summary`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, dict[(str, t.Any)])]

#### `export_analytics_data`

**Parameters:**
- `self` (): 
- `output_path` (str | Path): 
**Returns:** None



## marker_tracker
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/marker_tracker.py`

## MarkerTracker



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `repo_path` (Path): 
**Returns:** None

#### `_init_db`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_files_needing_scan`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `all_files` (list[Path]): 
**Returns:** list[Path]

#### `mark_scanned`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
- `files` (list[Path]): 
**Returns:** None

#### `mark_full_scan_complete`

**Parameters:**
- `self` (): 
- `tool_name` (str): 
**Returns:** None

#### `_calculate_file_hash`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** str



## unified_config
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/unified_config.py`

## UnifiedConfigurationService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `pkg_path` (Path): 
- `options` (OptionsProtocol | None): 
**Returns:** None

#### `get_config`

**Parameters:**
- `self` (): 
- `reload` (bool): 
**Returns:** CrackerjackSettings

#### `_load_unified_config`

**Parameters:**
- `self` (): 
**Returns:** CrackerjackSettings

#### `get_logging_config`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `get_hook_execution_config`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `get_testing_config`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `get_cache_config`

**Returns:** dict[(str, t.Any)]

#### `validate_current_config`

**Parameters:**
- `self` (): 
**Returns:** bool



## coverage_ratchet
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/coverage_ratchet.py`

**Implements Protocols:**
- CoverageRatchetProtocol

## CoverageRatchetService



**Base Classes:** CoverageRatchetProtocol


#### `__init__`

**Parameters:**
- `self` (): 
- `pkg_path` (Path): 
- `console` (Console | None): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
**Returns:** None

#### `initialize_baseline`

**Parameters:**
- `self` (): 
- `initial_coverage` (float): 
**Returns:** None

#### `_ratchet_metadata`
Build the staleness metadata block for a ratchet write.
**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `_refresh_freshness`
Refresh the staleness metadata after a fresh measurement.
**Parameters:**
- `self` (): 
**Returns:** bool

#### `get_ratchet_data`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `get_status_report`

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

#### `calculate_coverage_gap`

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

#### `raise_floor`
Raise the enforced floor to ``new_coverage`` and rewrite the ratchet.
**Parameters:**
- `self` (): 
- `new_coverage` (float): 
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

#### `get_coverage_improvement_needed`

**Parameters:**
- `self` (): 
**Returns:** float

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

#### `lower_baseline`
Lower the enforced coverage floor, with a recorded reason.
**Parameters:**
- `self` (): 
- `new_coverage` (float): 
- `reason` (str): 
**Returns:** None

#### `mirror_to_pyproject`
Write --cov-fail-under=<coverage> to pyproject.toml.
**Parameters:**
- `self` (): 
- `coverage` (float): 
**Returns:** None

#### `report_status`

**Parameters:**
- `self` (): 
**Returns:** str



## mermaid_renderer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/mermaid_renderer.py`

## MermaidBlock

A fenced mermaid block found in a `.md` file.

**Base Classes:** None


No methods defined.


## MermaidValidationError

A mermaid block that failed to parse.

**Base Classes:** None


#### `relpath`

**Parameters:**
- `self` (): 
**Returns:** str



## connection_pool
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/connection_pool.py`

## HTTPConnectionPool



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `timeout` (float): 
- `connect_timeout` (float): 
- `max_connections` (int): 
- `max_per_host` (int): 
**Returns:** None

#### `is_closed`

**Parameters:**
- `self` (): 
**Returns:** bool



## core
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/patterns/core.py`

## CompiledPatternCache



**Base Classes:** None


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
**Returns:** dict[(str, int | list[str])]



## ValidatedPattern



**Base Classes:** None


#### `__post_init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_validate`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_validate_compile_pattern`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_validate_replacement_syntax`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_validate_pattern_safety`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_run_test_cases`

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
- `count` (int | None): 
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



## operations
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/patterns/operations.py`

## RegexPatternsService



**Base Classes:** None


#### `update_pyproject_version`

**Parameters:**
- `self` (): 
- `content` (str): 
- `new_version` (str): 
**Returns:** str

#### `remove_coverage_fail_under`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** str

#### `update_version_in_changelog`

**Parameters:**
- `self` (): 
- `content` (str): 
- `new_version` (str): 
**Returns:** str

#### `mask_tokens_in_text`

**Parameters:**
- `self` (): 
- `text` (str): 
**Returns:** str



## quality_intelligence
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/quality_intelligence.py`

## AnomalyType



**Base Classes:** StrEnum


No methods defined.


## PatternType



**Base Classes:** StrEnum


No methods defined.


## QualityAnomaly



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## QualityPattern



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## QualityPrediction



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## QualityInsights



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## QualityIntelligenceService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `quality_service` (EnhancedQualityBaselineService): 
- `anomaly_sensitivity` (float): 
- `min_data_points` (int): 
**Returns:** None

#### `_get_recent_baselines`

**Parameters:**
- `self` (): 
- `days` (int): 
**Returns:** list[Any]

#### `_has_enough_data`

**Parameters:**
- `self` (): 
- `days` (int): 
**Returns:** bool

#### `detect_anomalies`

**Parameters:**
- `self` (): 
- `days` (int): 
**Returns:** list[QualityAnomaly]

#### `identify_patterns`

**Parameters:**
- `self` (): 
- `days` (int): 
**Returns:** list[QualityPattern]

#### `generate_advanced_predictions`

**Parameters:**
- `self` (): 
- `horizon_days` (int): 
**Returns:** list[QualityPrediction]

#### `generate_comprehensive_insights`

**Parameters:**
- `self` (): 
- `analysis_days` (int): 
**Returns:** QualityInsights

#### `_get_default_metrics`

**Parameters:**
- `self` (): 
**Returns:** list[str]



## anti_ai_flavor_adapter
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/anti_ai_flavor_adapter.py`

## AntiAIFlavorReport



**Base Classes:** None


#### `is_clean`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict



## anti_ai_flavor
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/anti_ai_flavor.py`

## AntiAIFlavorMatch



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, int | str)]



## AntiAIFlavorDetector



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `phrases` (Sequence[str] | None): 
- `whitelist` (Sequence[WhitelistEntry] | WhitelistEntry | None): 
- `case_sensitive` (bool): 
**Returns:** None

#### `detect`

**Parameters:**
- `self` (): 
- `text` (str): 
**Returns:** list[AntiAIFlavorMatch]

#### `_is_whitelisted`

**Parameters:**
- `self` (): 
- `phrase` (str): 
- `line_text` (str): 
**Returns:** bool

#### `load_phrases_from_yaml`

**Parameters:**
- `path` (Path): 
**Returns:** tuple[(str, Ellipsis)]



## quality_baseline_enhanced
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/quality/quality_baseline_enhanced.py`

## TrendDirection



**Base Classes:** StrEnum


No methods defined.


## AlertSeverity



**Base Classes:** StrEnum


No methods defined.


## EnhancedQualityBaselineService



**Base Classes:** None


#### `get_recent_baselines`

**Parameters:**
- `self` (): 
- `limit` (int): 


## test_result_parser
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/testing/test_result_parser.py`

## TestErrorType



**Base Classes:** str, Enum


No methods defined.


## TestFailure



**Base Classes:** None


#### `to_issue`

**Parameters:**
- `self` (): 
**Returns:** Issue



## TestResultParser



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `parse_text_output`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** list[TestFailure]

#### `parse_json_output`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** list[TestFailure]

#### `_split_failure_sections`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** list[str]

#### `_parse_failure_section`

**Parameters:**
- `self` (): 
- `section` (str): 
**Returns:** TestFailure | None

#### `_extract_test_name`

**Parameters:**
- `self` (): 
- `section` (str): 
**Returns:** str | None

#### `_extract_test_location`

**Parameters:**
- `self` (): 
- `section` (str): 
- `test_name` (str): 
**Returns:** tuple[(Path, int | None)]

#### `_determine_stage`

**Parameters:**
- `self` (): 
- `section` (str): 
**Returns:** str

#### `_build_error_patterns`

**Parameters:**
- `self` (): 
**Returns:** dict[(TestErrorType, list[str])]

#### `_parse_json_test`

**Parameters:**
- `self` (): 
- `test_data` (dict): 
**Returns:** TestFailure | None

#### `_check_fixture_error`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_import_error`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_mock_spec_error`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_attribute_error`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_validation_error`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_type_error`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_assertion_error`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_hardcoded_path`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_undefined_name`

**Parameters:**
- `self` (): 
- `section` (str): 
- `section_lower` (str): 
**Returns:** tuple[(TestErrorType, str)] | None

#### `_check_generic_error`

**Parameters:**
- `self` (): 
- `section` (str): 
**Returns:** tuple[(TestErrorType, str)]

#### `_classify_error`

**Parameters:**
- `self` (): 
- `section` (str): 
**Returns:** tuple[(TestErrorType, str)]

#### `parse_statistics`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** dict[(str, t.Any)]

#### `_strip_ansi_codes`

**Parameters:**
- `self` (): 
- `text` (str): 
**Returns:** str

#### `_extract_pytest_summary`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** re.Match[str] | None

#### `_parse_summary_match`

**Parameters:**
- `self` (): 
- `match` (re.Match[str]): 
- `output` (str): 
**Returns:** tuple[(str, float)]

#### `_extract_test_metrics`

**Parameters:**
- `self` (): 
- `summary_text` (str): 
- `stats` (dict[(str, t.Any)]): 
**Returns:** None

#### `_calculate_total_tests`

**Parameters:**
- `self` (): 
- `stats` (dict[(str, t.Any)]): 
- `output` (str): 
**Returns:** None

#### `_parse_test_lines_by_token`

**Parameters:**
- `self` (): 
- `output` (str): 
- `stats` (dict[(str, t.Any)]): 
**Returns:** None

#### `_parse_metric_patterns`

**Parameters:**
- `self` (): 
- `output` (str): 
- `stats` (dict[(str, t.Any)]): 
**Returns:** bool

#### `_parse_legacy_patterns`

**Parameters:**
- `self` (): 
- `output` (str): 
- `stats` (dict[(str, t.Any)]): 
**Returns:** None

#### `_fallback_count_tests`

**Parameters:**
- `self` (): 
- `output` (str): 
- `stats` (dict[(str, t.Any)]): 
**Returns:** None

#### `_extract_coverage_from_output`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** float | None



## run_state_store
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/testing/run_state_store.py`

## RunStateStore

SQLite-backed store of per-test run results.

**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `db_path` (Path): 
**Returns:** None

#### `db_path`

**Parameters:**
- `self` (): 
**Returns:** Path

#### `_connect`

**Parameters:**
- `self` (): 
**Returns:** Generator[sqlite3.Connection]

#### `_ensure_schema`

**Parameters:**
- `self` (): 
**Returns:** None

#### `record_run`
Record one test run and its per-test results.
**Parameters:**
- `self` (): 
**Returns:** str

#### `get_run`
Return the most recent run for a commit, or ``None``.
**Parameters:**
- `self` (): 
- `repo` (str): 
- `commit_sha` (str): 
- `worktree` (str | None): 
**Returns:** dict[(str, t.Any)] | None

#### `list_runs`
Return every recorded run for a commit, newest first.
**Parameters:**
- `self` (): 
- `repo` (str): 
- `commit_sha` (str): 
**Returns:** list[dict[(str, t.Any)]]

#### `get_test_results`
Return the per-test results recorded for a run.
**Parameters:**
- `self` (): 
- `run_id` (str): 
**Returns:** list[dict[(str, t.Any)]]

#### `summarize`
Aggregate the recorded runs.
**Parameters:**
- `self` (): 
- `repo` (str | None): 
**Returns:** dict[(str, int)]

#### `get_status_map`
Return ``{node_id: status}`` for a run - the diffing primitive.
**Parameters:**
- `self` (): 
- `run_id` (str): 
**Returns:** dict[(str, str)]

#### `_count_statuses`

**Parameters:**
- `tests` (list[dict[(str, t.Any)]]): 
**Returns:** dict[(str, int)]



## test_result_renderer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/testing/test_result_renderer.py`

## TestResultRenderer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (ConsoleInterface): 
**Returns:** None

#### `render_test_results_panel`

**Parameters:**
- `self` (): 
- `stats` (dict[(str, t.Any)]): 
- `workers` (int | str): 
- `success` (bool): 
**Returns:** None

#### `render_banner`

**Parameters:**
- `self` (): 
- `title` (str): 
**Returns:** None

#### `should_render_test_panel`

**Parameters:**
- `self` (): 
- `stats` (dict[(str, t.Any)]): 
**Returns:** bool

#### `render_parsing_error_message`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None



## coverage_manager
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/testing/coverage_manager.py`

## CoverageManager



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (ConsoleInterface): 
- `pkg_path` (Path): 
- `coverage_ratchet` (CoverageRatchetProtocol | None): 
- `coverage_badge` (CoverageBadgeServiceProtocol | None): 
**Returns:** None

#### `process_coverage_ratchet`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `attempt_coverage_extraction`

**Parameters:**
- `self` (): 
**Returns:** float | None

#### `handle_coverage_extraction_result`

**Parameters:**
- `self` (): 
- `current_coverage` (float | None): 
**Returns:** float | None

#### `update_coverage_badge`

**Parameters:**
- `self` (): 
- `ratchet_result` (dict[(str, t.Any)]): 
**Returns:** None

#### `handle_ratchet_result`

**Parameters:**
- `self` (): 
- `ratchet_result` (dict[(str, t.Any)]): 
**Returns:** bool

#### `_get_coverage_from_file`

**Parameters:**
- `self` (): 
**Returns:** float | None

#### `_try_service_coverage`

**Parameters:**
- `self` (): 
**Returns:** float | None

#### `_handle_zero_coverage_fallback`

**Parameters:**
- `self` (): 
- `current_coverage` (float | None): 
**Returns:** None

#### `_get_fallback_coverage`

**Parameters:**
- `self` (): 
- `ratchet_result` (dict[(str, t.Any)]): 
- `current_coverage` (float | None): 
**Returns:** float | None

#### `_handle_coverage_improvement`

**Parameters:**
- `self` (): 
- `ratchet_result` (dict[(str, t.Any)]): 
**Returns:** None



## contextual_ai_assistant
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/contextual_ai_assistant.py`

## AIRecommendation



**Base Classes:** None


No methods defined.


## ProjectContext



**Base Classes:** None


No methods defined.


## ContextualAIAssistant



**Base Classes:** None


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

#### `_get_help_keyword_mapping`

**Parameters:**
- `self` (): 
**Returns:** list[tuple[(list[str], str)]]

#### `_query_contains_keywords`

**Parameters:**
- `self` (): 
- `query` (str): 
- `keywords` (list[str]): 
**Returns:** bool



## embeddings
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/embeddings.py`

## EmbeddingService



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `config` (SemanticConfig): 
**Returns:** None

#### `session`

**Parameters:**
- `self` (): 
**Returns:** Any

#### `tokenizer`

**Parameters:**
- `self` (): 
**Returns:** Any

#### `_load_model`

**Parameters:**
- `self` (): 
**Returns:** None

#### `generate_embedding`

**Parameters:**
- `self` (): 
- `text` (str): 
**Returns:** list[float]

#### `_generate_fallback_embedding`

**Parameters:**
- `self` (): 
- `text` (str): 
**Returns:** list[float]

#### `generate_embeddings_batch`

**Parameters:**
- `self` (): 
- `texts` (list[str]): 
**Returns:** list[list[float]]

#### `calculate_similarity`

**Parameters:**
- `self` (): 
- `embedding1` (list[float]): 
- `embedding2` (list[float]): 
**Returns:** float

#### `calculate_similarities_batch`

**Parameters:**
- `self` (): 
- `query_embedding` (list[float]): 
- `embeddings` (list[list[float]]): 
**Returns:** list[float]

#### `get_text_hash`

**Parameters:**
- `self` (): 
- `text` (str): 
**Returns:** str

#### `get_file_hash`

**Parameters:**
- `self` (): 
- `file_path` (Path): 
**Returns:** str

#### `chunk_text`

**Parameters:**
- `self` (): 
- `text` (str): 
**Returns:** list[str]

#### `_split_into_sentences`

**Parameters:**
- `self` (): 
- `text` (str): 
**Returns:** list[str]

#### `is_model_available`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `get_model_info`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, Any)]



## advanced_optimizer
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/ai/advanced_optimizer.py`

## ResourceMetrics



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## PerformanceProfile



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## OptimizationRecommendation



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## ScalingMetrics



**Base Classes:** None


#### `to_dict`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## ConnectionPool



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `max_connections` (int): 
- `cleanup_interval` (int): 
**Returns:** None

#### `add_connection`

**Parameters:**
- `self` (): 
- `connection_id` (str): 
- `websocket` (t.Any): 
- `metadata` (dict[(str, t.Any)] | None): 
**Returns:** None

#### `remove_connection`

**Parameters:**
- `self` (): 
- `connection_id` (str): 
**Returns:** None

#### `update_activity`

**Parameters:**
- `self` (): 
- `connection_id` (str): 
**Returns:** None

#### `_cleanup_stale_connections`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_stats`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]



## DataCompactionManager



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `storage_dir` (Path): 
- `max_storage_gb` (float): 
**Returns:** None

#### `_load_compaction_rules`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, dict[(str, t.Any)])]

#### `_create_metrics_raw_config`

**Returns:** dict[(str, t.Any)]

#### `_create_metrics_hourly_config`

**Returns:** dict[(str, t.Any)]

#### `_create_metrics_daily_config`

**Returns:** dict[(str, t.Any)]

#### `_create_error_patterns_config`

**Returns:** dict[(str, t.Any)]

#### `_create_dependency_graphs_config`

**Returns:** dict[(str, t.Any)]

#### `compact_data`

**Parameters:**
- `self` (): 
- `data_type` (str): 
**Returns:** dict[(str, t.Any)]

#### `_calculate_cutoff_date`

**Parameters:**
- `rules` (dict[(str, t.Any)]): 
**Returns:** datetime

#### `_process_data_directory`

**Parameters:**
- `self` (): 
- `data_type` (str): 
- `cutoff_date` (datetime): 
**Returns:** dict[(str, int | float)]

#### `_should_compact_file`

**Parameters:**
- `file_path` (Path): 
- `cutoff_date` (datetime): 
**Returns:** bool

#### `_build_compaction_result`

**Parameters:**
- `data_type` (str): 
- `rules` (dict[(str, t.Any)]): 
- `stats` (dict[(str, int | float)]): 
**Returns:** dict[(str, t.Any)]

#### `get_storage_usage`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `_calculate_storage_sizes`

**Parameters:**
- `self` (): 
**Returns:** tuple[(int, dict[(str, int)])]

#### `_calculate_data_type_size`

**Parameters:**
- `self` (): 
- `data_type` (str): 
**Returns:** int

#### `_build_storage_usage_report`

**Parameters:**
- `self` (): 
- `total_size` (int): 
- `type_sizes` (dict[(str, int)]): 
**Returns:** dict[(str, t.Any)]

#### `_calculate_utilization_percent`

**Parameters:**
- `self` (): 
- `total_size` (int): 
**Returns:** float



## AdvancedOptimizer



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `config_dir` (Path): 
- `storage_dir` (Path): 
**Returns:** None

#### `_load_performance_profile`

**Parameters:**
- `self` (): 
**Returns:** PerformanceProfile

#### `collect_resource_metrics`

**Parameters:**
- `self` (): 
**Returns:** ResourceMetrics

#### `analyze_scaling_needs`

**Parameters:**
- `self` (): 
**Returns:** ScalingMetrics

#### `generate_optimization_recommendations`

**Parameters:**
- `self` (): 
**Returns:** list[OptimizationRecommendation]

#### `_generate_cpu_recommendations`

**Parameters:**
- `metrics` (ResourceMetrics): 
**Returns:** list[OptimizationRecommendation]

#### `_generate_memory_recommendations`

**Parameters:**
- `metrics` (ResourceMetrics): 
**Returns:** list[OptimizationRecommendation]

#### `_generate_storage_recommendations`

**Parameters:**
- `storage_usage` (dict[(str, t.Any)]): 
**Returns:** list[OptimizationRecommendation]

#### `_generate_connection_recommendations`

**Parameters:**
- `self` (): 
**Returns:** list[OptimizationRecommendation]

#### `_generate_scaling_recommendations`

**Parameters:**
- `self` (): 
- `scaling_metrics` (ScalingMetrics): 
**Returns:** list[OptimizationRecommendation]

#### `optimize_configuration`

**Parameters:**
- `self` (): 
- `strategy` (str | None): 
**Returns:** dict[(str, t.Any)]

#### `_get_latest_metrics`

**Parameters:**
- `self` (): 
**Returns:** ResourceMetrics | None

#### `_apply_all_optimizations`

**Parameters:**
- `self` (): 
- `metrics` (ResourceMetrics): 
- `strategy` (str): 
**Returns:** list[str]

#### `_apply_memory_optimizations`

**Parameters:**
- `self` (): 
- `metrics` (ResourceMetrics): 
**Returns:** list[str]

#### `_apply_performance_optimizations`

**Parameters:**
- `self` (): 
- `metrics` (ResourceMetrics): 
- `strategy` (str): 
**Returns:** list[str]

#### `_apply_storage_optimizations`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `_build_optimization_result`

**Parameters:**
- `strategy` (str): 
- `optimizations_applied` (list[str]): 
**Returns:** dict[(str, t.Any)]

#### `get_advanced_status`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `_calculate_health_score`

**Parameters:**
- `self` (): 
**Returns:** float



## _trusted_publishing
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pypi_auth/_trusted_publishing.py`

## TrustedPublishingProvider



**Base Classes:** None


#### `is_available`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `resolve`

**Parameters:**
- `self` (): 
**Returns:** PyPIAuth | None



## _providers
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pypi_auth/_providers.py`

## _EnvVarPyPIAuth



**Base Classes:** PyPIAuth


#### `source`

**Parameters:**
- `self` (): 
**Returns:** str



## _KeyringPyPIAuth



**Base Classes:** PyPIAuth


#### `source`

**Parameters:**
- `self` (): 
**Returns:** str



## EnvVarAuthProvider



**Base Classes:** None


#### `is_available`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `resolve`

**Parameters:**
- `self` (): 
**Returns:** PyPIAuth | None



## KeyringAuthProvider



**Base Classes:** None


#### `is_available`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `resolve`

**Parameters:**
- `self` (): 
**Returns:** PyPIAuth | None



## _auth
**Path:** `/Users/les/Projects/crackerjack/crackerjack/services/pypi_auth/_auth.py`

**Implements Protocols:**
- t.Protocol

## PyPIAuth



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `value` (str): 
**Returns:** None

#### `as_uv_publish_token`

**Parameters:**
- `self` (): 
**Returns:** str

#### `is_trusted_publishing`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `source`

**Parameters:**
- `self` (): 
**Returns:** str

#### `__repr__`

**Parameters:**
- `self` (): 
**Returns:** str

#### `__str__`

**Parameters:**
- `self` (): 
**Returns:** str

#### `__eq__`

**Parameters:**
- `self` (): 
- `other` (object): 
**Returns:** bool

#### `__hash__`

**Parameters:**
- `self` (): 
**Returns:** int

#### `__reduce__`

**Parameters:**
- `self` (): 
**Returns:** t.NoReturn



## _TrustedPublishingSentinel



**Base Classes:** PyPIAuth


#### `__init__`

**Parameters:**
- `self` (): 
**Returns:** None

#### `as_uv_publish_token`

**Parameters:**
- `self` (): 
**Returns:** str

#### `is_trusted_publishing`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `source`

**Parameters:**
- `self` (): 
**Returns:** str



## PyPIAuthProvider



**Base Classes:** t.Protocol


#### `is_available`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `resolve`

**Parameters:**
- `self` (): 
**Returns:** PyPIAuth | None






## publish_manager
**Path:** `/Users/les/Projects/crackerjack/crackerjack/managers/publish_manager.py`

## _NullGitService



**Base Classes:** None


#### `is_git_repo`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `rm_files`

**Parameters:**
- `self` (): 
- `files` (list[str]): 
**Returns:** bool



## _NullVersionAnalyzer



**Base Classes:** None


No methods defined.


## _NullChangelogGenerator



**Base Classes:** None


#### `generate_changelog_from_commits`

**Parameters:**
- `self` (): 
**Returns:** bool



## _RegexPatterns



**Base Classes:** None


#### `update_pyproject_version`

**Parameters:**
- `self` (): 
- `content` (str): 
- `version` (str): 
**Returns:** str



## PublishManagerImpl



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `git_service` (GitServiceProtocol | None): 
- `version_analyzer` (VersionAnalyzerProtocol | None): 
- `changelog_generator` (ChangelogGeneratorProtocol | None): 
- `filesystem` (FileSystemInterface | None): 
- `security` (SecurityServiceProtocol | None): 
- `regex_patterns` (RegexPatternsProtocol | None): 
- `console` (ConsoleInterface | None): 
- `pkg_path` (Path | None): 
- `dry_run` (bool): 
- `publish_url` (str | None): 
- `publish_token_env` (str | None): 
**Returns:** None

#### `_resolve_console`

**Parameters:**
- `self` (): 
- `console` (ConsoleInterface | None): 
**Returns:** ConsoleInterface

#### `_resolve_pkg_path`

**Parameters:**
- `self` (): 
- `pkg_path` (Path | None): 
**Returns:** Path

#### `_resolve_git_service`

**Parameters:**
- `self` (): 
- `git_service` (GitServiceProtocol | None): 
**Returns:** GitServiceProtocol | _NullGitService

#### `_resolve_version_analyzer`

**Parameters:**
- `self` (): 
- `version_analyzer` (VersionAnalyzerProtocol | None): 
**Returns:** VersionAnalyzerProtocol | _NullVersionAnalyzer

#### `_resolve_changelog_generator`

**Parameters:**
- `self` (): 
- `changelog_generator` (ChangelogGeneratorProtocol | None): 
**Returns:** ChangelogGeneratorProtocol | _NullChangelogGenerator

#### `_resolve_regex_patterns`

**Parameters:**
- `self` (): 
- `regex_patterns` (RegexPatternsProtocol | None): 
**Returns:** RegexPatternsProtocol

#### `_resolve_filesystem`

**Parameters:**
- `self` (): 
- `filesystem` (FileSystemInterface | None): 
**Returns:** FileSystemInterface

#### `_resolve_security`

**Parameters:**
- `self` (): 
- `security` (SecurityServiceProtocol | None): 
**Returns:** SecurityServiceProtocol

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

#### `_update_python_version_files`

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

#### `_resolve_bump_type`
Apply AI recommendation override or interactive prompt.
**Parameters:**
- `self` (): 
- `recommendation` (t.Any): 
- `version_type` (str): 
**Returns:** str

#### `_perform_bump`
Calculate new version, apply edits, restore on error.
**Parameters:**
- `self` (): 
- `current_version` (str): 
- `version_type` (str): 
**Returns:** str

#### `_snapshot_bump_files`
Read the version-bearing files before mutation.
**Parameters:**
- `self` (): 
**Returns:** dict[(Path, str | None)]

#### `_restore_bump_files`
Restore the version-bearing files from a pre-bump snapshot.
**Parameters:**
- `self` (): 
- `snapshot` (dict[(Path, str | None)]): 
**Returns:** None

#### `_prompt_for_version_type`

**Parameters:**
- `self` (): 
- `recommendation` (t.Any): 
**Returns:** str

#### `_get_version_recommendation`

**Parameters:**
- `self` (): 
**Returns:** t.Any

#### `_display_version_analysis`

**Parameters:**
- `self` (): 
- `recommendation` (t.Any): 
**Returns:** None

#### `validate_auth`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_resolve_pypi_auth`

**Parameters:**
- `self` (): 
**Returns:** PyPIAuth | None

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

#### `_validate_release_audit`
Run release-audit check before any publish/bump operation.
**Parameters:**
- `self` (): 
**Returns:** bool

#### `_validate_gitignore_conformance`
Verify the Bodai canonical `.gitignore` snippet is installed.
**Parameters:**
- `self` (): 
**Returns:** bool

#### `_attempt_gitignore_sync`
Run `crackerjack gitignore sync --pkg-path <self.pkg_path>`.
**Parameters:**
- `self` (): 
**Returns:** bool

#### `_detect_source_root`
Return the first existing source-package directory under project_root.
**Parameters:**
- `self` (): 
- `project_root` (Path): 
**Returns:** Path | None

#### `_perform_publish_workflow`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_perform_publish_workflow_with_retry`

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

#### `_execute_publish_to_custom_registry`
Publish to a non-PyPI registry (``--publish-url`` set).
**Parameters:**
- `self` (): 
**Returns:** bool

#### `_resolve_custom_token_env_name`
Pick the env var to read for a custom-registry token.
**Parameters:**
- `self` (): 
**Returns:** str | None

#### `_execute_publish_to_pypi_public`
Publish to public PyPI using the standard auth chain.
**Parameters:**
- `self` (): 
**Returns:** bool

#### `_dispatch_publish`
Run the ``uv publish`` subprocess and resolve success/failure.
**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `extra_env` (dict[(str, str)] | None): 
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

#### `create_git_tag_local`

**Parameters:**
- `self` (): 
- `version` (str): 
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

#### `_parse_project_section_fallback`

**Parameters:**
- `self` (): 
- `content` (str): 
**Returns:** dict[(str, t.Any)]

#### `_should_process_line`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** bool

#### `_update_project_state`

**Parameters:**
- `self` (): 
- `line` (str): 
- `current_state` (bool): 
**Returns:** bool

#### `_parse_line_if_valid`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** tuple[(str, t.Any)] | None

#### `_parse_value`

**Parameters:**
- `self` (): 
- `raw_value` (str): 
**Returns:** t.Any

#### `_update_changelog_for_version`

**Parameters:**
- `self` (): 
- `old_version` (str): 
- `new_version` (str): 
**Returns:** None



## test_command_builder
**Path:** `/Users/les/Projects/crackerjack/crackerjack/managers/test_command_builder.py`

## TestCommandBuilder



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `pkg_path` (Path | None): 
- `console` (Console | None): 
- `settings` (CrackerjackSettings | None): 
**Returns:** None

#### `get_project_name`
Stable identifier for the project, valid across worktrees.
**Parameters:**
- `self` (): 
**Returns:** str

#### `get_json_report_path`
Path to the machine-readable pytest result file for this run.
**Parameters:**
- `self` (): 
**Returns:** Path

#### `reset_report_path`
Start a new run, which gets a fresh report path.
**Parameters:**
- `self` (): 
**Returns:** None

#### `_add_json_report_options`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
**Returns:** None

#### `build_command`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
**Returns:** list[str]

#### `build_xcode_command`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
**Returns:** list[str]

#### `_handle_not_implemented_error`

**Parameters:**
- `self` (): 
- `print_info` (bool): 
**Returns:** int

#### `_handle_general_error`

**Parameters:**
- `self` (): 
- `print_info` (bool): 
- `e` (Exception): 
**Returns:** int

#### `get_optimal_workers`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
- `print_info` (bool): 
**Returns:** int | str

#### `_check_emergency_rollback`

**Parameters:**
- `self` (): 
- `print_info` (bool): 
**Returns:** bool

#### `_check_explicit_workers`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
- `print_info` (bool): 
**Returns:** int | None

#### `_check_auto_detection`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
- `print_info` (bool): 
**Returns:** str | int | None

#### `_check_fractional_workers`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
- `print_info` (bool): 
**Returns:** int | None

#### `_apply_memory_limit`

**Parameters:**
- `self` (): 
- `workers` (int): 
**Returns:** int

#### `get_test_timeout`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
**Returns:** int

#### `_detect_package_name`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_add_coverage_options`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `options` (OptionsProtocol): 
**Returns:** None

#### `_add_incremental_coverage_options`
Disable coverage collection for a run that selects tests.
**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
**Returns:** None

#### `_print_incremental_coverage_disabled_message`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_check_project_disabled_xdist`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_load_pytest_addopts`

**Parameters:**
- `self` (): 
- `pyproject_path` (Path): 
**Returns:** str | None

#### `_addopts_disables_xdist`

**Parameters:**
- `self` (): 
- `addopts` (str): 
**Returns:** bool

#### `_has_compact_no_xdist_flag`

**Parameters:**
- `self` (): 
- `parsed_opts` (list[str]): 
**Returns:** bool

#### `_add_worker_options`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `options` (OptionsProtocol): 
**Returns:** None

#### `_print_xdist_disabled_message`

**Parameters:**
- `self` (): 
**Returns:** None

#### `_should_skip_xdist_for_benchmark`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
**Returns:** bool

#### `_add_worker_count_options`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `workers` (str | int): 
**Returns:** None

#### `_add_auto_workers`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `dist_mode` (str): 
**Returns:** None

#### `_add_explicit_workers`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `workers` (int): 
- `dist_mode` (str): 
**Returns:** None

#### `_print_worker_message`

**Parameters:**
- `self` (): 
- `worker_count` (str): 
- `dist_mode` (str | None): 
**Returns:** None

#### `_print_sequential_message`

**Parameters:**
- `self` (): 
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
**Path:** `/Users/les/Projects/crackerjack/crackerjack/managers/hook_manager.py`

## HookManagerImpl



**Base Classes:** None


#### `_setup_git_service`

**Parameters:**
- `self` (): 
- `use_incremental` (bool): 
- `pkg_path` (Path): 
- `git_service` (GitServiceProtocol | None): 
**Returns:** GitServiceProtocol | None

#### `_setup_executor`

**Parameters:**
- `self` (): 
- `pkg_path` (Path): 
- `verbose` (bool): 
- `quiet` (bool): 
- `debug` (bool): 
- `enable_tool_proxy` (bool): 
- `use_incremental` (bool): 
- `git_service` (t.Any): 
- `file_filter` (t.Any | None): 
- `enable_hooks` (list[str] | None): 
**Returns:** None

#### `_load_from_project_config`

**Parameters:**
- `self` (): 
- `config_path` (Path): 
- `enable_orchestration` (bool | None): 
- `orchestration_mode` (str | None): 
**Returns:** None

#### `_create_default_orchestration_config`

**Parameters:**
- `self` (): 
- `enable_orchestration` (bool | None): 
- `orchestration_mode` (str | None): 
- `enable_caching` (bool): 
- `cache_backend` (str): 
**Returns:** None

#### `_load_orchestration_config`

**Parameters:**
- `self` (): 
- `pkg_path` (Path): 
- `orchestration_config` (t.Any): 
- `enable_orchestration` (bool | None): 
- `orchestration_mode` (str | None): 
- `enable_caching` (bool): 
- `cache_backend` (str): 
**Returns:** None

#### `__init__`

**Parameters:**
- `self` (): 
- `pkg_path` (Path): 
- `verbose` (bool): 
- `quiet` (bool): 
- `debug` (bool): 
- `enable_tool_proxy` (bool): 
- `use_incremental` (bool): 
- `orchestration_config` (t.Any): 
- `enable_orchestration` (bool | None): 
- `orchestration_mode` (str | None): 
- `enable_caching` (bool): 
- `cache_backend` (str): 
- `console` (t.Any): 
- `settings` (CrackerjackSettings | None): 
- `file_filter` (t.Any | None): 
- `enable_hooks` (list[str] | None): 
- `adapter_learner_integration` (t.Any | None): 
**Returns:** None

#### `set_config_path`

**Parameters:**
- `self` (): 
- `config_path` (Path): 
**Returns:** None

#### `set_active_tool`
Set the ``--tool`` scope (or clear it with ``None``).
**Parameters:**
- `self` (): 
- `name` (str | None): 
**Returns:** None

#### `_filter_strategy_for_tool`

**Parameters:**
- `self` (): 
- `strategy` (HookStrategy): 
- `active_tool` (str | None): 
**Returns:** HookStrategy

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

#### `configure_tool_proxy`

**Parameters:**
- `self` (): 
- `enable` (bool): 
**Returns:** None

#### `get_execution_info`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `get_hook_ids`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `get_hook_count`

**Parameters:**
- `self` (): 
- `suite_name` (str): 
**Returns:** int

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
- `results` (list[HookResult]): 
- `elapsed_time` (float | None): 
**Returns:** dict[(str, t.Any)]

#### `validate_hooks_config`

**Returns:** bool



## _FallbackOrchestrationConfig



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `enable_caching` (bool): 
- `cache_backend` (str): 
**Returns:** None



## test_progress
**Path:** `/Users/les/Projects/crackerjack/crackerjack/managers/test_progress.py`

## TestProgress



**Base Classes:** None


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

#### `tests_per_second`

**Parameters:**
- `self` (): 
**Returns:** float

#### `overall_status_color`

**Parameters:**
- `self` (): 
**Returns:** str

#### `update`

**Parameters:**
- `self` (): 
**Returns:** None

#### `append_stdout`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** None

#### `append_stderr`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** None

#### `get_stdout`

**Parameters:**
- `self` (): 
**Returns:** str

#### `get_stderr`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_create_progress_bar`

**Parameters:**
- `self` (): 
- `width` (int): 
**Returns:** str

#### `_format_eta`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_format_test_rate`

**Parameters:**
- `self` (): 
**Returns:** str

#### `format_progress`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_format_collection_progress`

**Parameters:**
- `self` (): 
**Returns:** str

#### `_format_progress_counters`

**Parameters:**
- `self` (): 
**Returns:** list[str]

#### `_format_execution_progress`

**Parameters:**
- `self` (): 
**Returns:** str



## async_hook_manager
**Path:** `/Users/les/Projects/crackerjack/crackerjack/managers/async_hook_manager.py`

## AsyncHookManager



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (ConsoleInterface): 
- `pkg_path` (Path): 
- `async_executor` (AsyncHookExecutorProtocol | None): 
- `config_loader` (HookConfigLoaderProtocol | None): 
- `max_concurrent` (int): 
- `verbose` (bool): 
- `test_dir` (str): 
**Returns:** None

#### `set_config_path`

**Parameters:**
- `self` (): 
- `config_path` (Path): 
**Returns:** None

#### `get_hook_count`

**Parameters:**
- `self` (): 
- `suite_name` (str): 
**Returns:** int

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
- `results` (list[HookResult]): 
- `elapsed_time` (float | None): 
**Returns:** dict[(str, t.Any)]



## test_executor
**Path:** `/Users/les/Projects/crackerjack/crackerjack/managers/test_executor.py`

## TestExecutor



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (RichConsole): 
- `pkg_path` (Path): 
**Returns:** None

#### `_detect_target_project_dir`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
**Returns:** Path

#### `_find_pytest_index`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
**Returns:** int

#### `_find_project_from_test_args`

**Parameters:**
- `self` (): 
- `test_args` (list[str]): 
**Returns:** Path

#### `_get_project_dir_from_path`

**Parameters:**
- `self` (): 
- `test_path` (Path): 
**Returns:** Path

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
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
- `timeout` (int): 
**Returns:** subprocess.CompletedProcess[str]

#### `_pre_collect_tests`

**Parameters:**
- `self` (): 
- `original_cmd` (list[str]): 
**Returns:** int

#### `_execute_with_live_progress`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `timeout` (int): 
- `progress` (TestProgress | None): 
**Returns:** subprocess.CompletedProcess[str]

#### `_run_test_command_with_ai_progress`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
- `timeout` (int): 
- `progress` (TestProgress | None): 
**Returns:** subprocess.CompletedProcess[str]

#### `_should_try_xdist_fallback`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
**Returns:** bool

#### `_get_optimal_worker_count_from_cmd`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
**Returns:** int

#### `_run_with_xdist_fallback`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `progress` (TestProgress): 
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
- `timeout` (int): 
**Returns:** subprocess.CompletedProcess[str]

#### `_did_xdist_timeout`

**Parameters:**
- `self` (): 
- `result` (subprocess.CompletedProcess): 
- `progress` (TestProgress): 
**Returns:** bool

#### `_remove_xdist_from_cmd`

**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
**Returns:** list[str]

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
Run *cmd*, streaming its output while it runs.
**Parameters:**
- `self` (): 
- `cmd` (list[str]): 
- `env` (dict[(str, str)]): 
- `progress` (TestProgress): 
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
- `timeout` (int): 
- `stall_timeout` (int | None): 
**Returns:** subprocess.CompletedProcess[str]

#### `_read_stdout_with_progress`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
- `progress` (TestProgress): 
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
- `timeout` (int): 
**Returns:** list[str]

#### `_setup_nonblocking_io`

**Parameters:**
- `self` (): 
- `stream` (t.TextIO): 
**Returns:** bool

#### `_read_stdout_blocking`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
- `start_time` (float): 
- `last_output_time` (float): 
- `progress` (TestProgress): 
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
- `timeout` (int): 
**Returns:** list[str]

#### `_read_stdout_loop`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
- `stdout_lines` (list[str]): 
- `progress` (TestProgress): 
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
- `start_time` (float): 
- `last_output_time` (float): 
- `timeout` (int): 
**Returns:** list[str]

#### `_process_has_terminated`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
**Returns:** bool

#### `_read_remaining_output`

**Parameters:**
- `self` (): 
- `stdout` (t.TextIO): 
- `stdout_lines` (list[str]): 
- `progress` (TestProgress): 
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
**Returns:** None

#### `_wait_for_readable_stdout`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
- `timeout` (int): 
- `start_time` (float): 
- `last_output_time` (float): 
**Returns:** bool

#### `_read_line_with_timeout`

**Parameters:**
- `self` (): 
- `stdout` (t.TextIO): 
- `timeout` (int): 
**Returns:** str

#### `_process_line`
Record one output line; return the refreshed last-output time.
**Parameters:**
- `self` (): 
- `line` (str): 
- `stdout_lines` (list[str]): 
- `progress` (TestProgress): 
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
- `last_output_time` (float): 
**Returns:** float

#### `_read_stderr_lines`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
- `timeout` (int): 
**Returns:** list[str]

#### `_read_stderr_blocking`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
- `start_time` (float): 
- `last_output_time` (float): 
- `timeout` (int): 
**Returns:** list[str]

#### `_read_stderr_loop`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
- `stderr_lines` (list[str]): 
- `start_time` (float): 
- `last_output_time` (float): 
- `timeout` (int): 
**Returns:** list[str]

#### `_read_remaining_stderr`

**Parameters:**
- `self` (): 
- `stderr` (t.TextIO): 
- `stderr_lines` (list[str]): 
**Returns:** None

#### `_wait_for_readable_stderr`

**Parameters:**
- `self` (): 
- `process` (subprocess.Popen[str]): 
- `last_output_time` (float): 
- `timeout` (int): 
**Returns:** bool

#### `_read_stderr_line`

**Parameters:**
- `self` (): 
- `stderr` (t.TextIO): 
**Returns:** str

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
- `progress_callback` (t.Callable[([dict[str, t.Any]], None)]): 
**Returns:** None



## test_manager
**Path:** `/Users/les/Projects/crackerjack/crackerjack/managers/test_manager.py`

## RatchetResult



**Base Classes:** None


No methods defined.


## TestManager



**Base Classes:** None


#### `__init__`

**Parameters:**
- `self` (): 
- `console` (ConsoleInterface | None): 
- `pkg_path` (Path | None): 
- `coverage_ratchet` (CoverageRatchetProtocol | None): 
- `coverage_badge` (CoverageBadgeServiceProtocol | None): 
- `command_builder` (TestCommandBuilder | None): 
- `lsp_client` (t.Any | None): 
- `result_parser` (TestResultParser | None): 
- `result_renderer` (TestResultRenderer | None): 
- `coverage_manager` (CoverageManager | None): 
- `run_state_db_path` (Path | None): 
**Returns:** None

#### `run_with_ratchet_check`
Post-test ratchet gate. Reads coverage.json, compares to ratchet.
**Parameters:**
- `self` (): 
**Returns:** RatchetResult

#### `set_progress_callback`

**Parameters:**
- `self` (): 
- `callback` (t.Callable[([dict[str, t.Any]], None)] | None): 
**Returns:** None

#### `initialize`

**Parameters:**
- `self` (): 
**Returns:** None

#### `cleanup`

**Parameters:**
- `self` (): 
**Returns:** None

#### `health_check`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `shutdown`

**Parameters:**
- `self` (): 
**Returns:** None

#### `metrics`

**Parameters:**
- `self` (): 
**Returns:** dict[(str, t.Any)]

#### `is_healthy`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `register_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `cleanup_resource`

**Parameters:**
- `self` (): 
- `resource` (t.Any): 
**Returns:** None

#### `record_error`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `increment_requests`

**Parameters:**
- `self` (): 
**Returns:** None

#### `get_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
**Returns:** t.Any

#### `set_custom_metric`

**Parameters:**
- `self` (): 
- `name` (str): 
- `value` (t.Any): 
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

#### `_run_pytest_if_needed`

**Parameters:**
- `self` (): 
- `run_pytest` (bool): 
- `options` (OptionsProtocol): 
- `start_time` (float): 
**Returns:** bool

#### `_discard_run_report`
Remove this run's JSON report.
**Parameters:**
- `self` (): 
**Returns:** None

#### `last_run_was_incremental`
Whether the last test run selected a subset of the suite.
**Parameters:**
- `self` (): 
**Returns:** bool

#### `_record_run_state`
Record this run's per-test results in the shared run-state store.
**Parameters:**
- `self` (): 
- `result` (subprocess.CompletedProcess[str]): 
- `options` (OptionsProtocol): 
- `start_time` (float): 
**Returns:** int | None

#### `_resolve_git_identity`
Resolve the current commit and branch, tolerating a non-git tree.
**Parameters:**
- `self` (): 
**Returns:** tuple[(str, str | None)]

#### `_run_xcode_if_needed`

**Parameters:**
- `self` (): 
- `run_xcode` (bool): 
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

#### `_get_coverage_from_file`

**Parameters:**
- `self` (): 
**Returns:** float | None

#### `_handle_no_ratchet_status`

**Parameters:**
- `self` (): 
- `direct_coverage` (float | None): 
**Returns:** dict[(str, t.Any)]

#### `_get_final_coverage`

**Parameters:**
- `self` (): 
- `ratchet_coverage` (float): 
- `direct_coverage` (float | None): 
**Returns:** float

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

#### `_execute_xcode_tests`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
**Returns:** bool

#### `_handle_test_success`

**Parameters:**
- `self` (): 
- `output` (str): 
- `duration` (float): 
- `options` (OptionsProtocol): 
- `workers` (int | str): 
**Returns:** bool

#### `_handle_test_failure`

**Parameters:**
- `self` (): 
- `stderr` (str): 
- `stdout` (str): 
- `duration` (float): 
- `options` (OptionsProtocol): 
- `workers` (int | str): 
**Returns:** bool

#### `_handle_failure_with_output`

**Parameters:**
- `self` (): 
- `clean_output` (str): 
**Returns:** None

#### `_handle_failure_without_output`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
- `duration` (float): 
- `workers` (int | str): 
**Returns:** None

#### `_handle_test_error`

**Parameters:**
- `self` (): 
- `start_time` (float): 
- `error` (Exception): 
**Returns:** bool

#### `_parse_test_statistics`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** dict[(str, t.Any)]

#### `_should_render_test_panel`

**Parameters:**
- `self` (): 
- `stats` (dict[(str, t.Any)]): 
**Returns:** bool

#### `_render_test_results_panel`

**Parameters:**
- `self` (): 
- `stats` (dict[(str, t.Any)]): 
- `workers` (int | str): 
- `success` (bool): 
**Returns:** None

#### `_render_banner`

**Parameters:**
- `self` (): 
- `title` (str): 
**Returns:** None

#### `_process_coverage_ratchet`

**Parameters:**
- `self` (): 
**Returns:** bool

#### `_extract_failure_lines`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** list[str]

#### `_extract_from_short_summary`

**Parameters:**
- `self` (): 
- `lines` (list[str]): 
**Returns:** list[str]

#### `_parse_summary_failed_line`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** str | None

#### `_extract_from_test_paths`

**Parameters:**
- `self` (): 
- `lines` (list[str]): 
**Returns:** list[str]

#### `_try_extract_test_name`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** str | None

#### `_strip_ansi_codes`

**Parameters:**
- `text` (str): 
**Returns:** str

#### `_split_output_sections`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** list[tuple[(str, str)]]

#### `_process_line_for_section`

**Parameters:**
- `self` (): 
- `line` (str): 
- `current_type` (str): 
- `current_section` (list[str]): 
- `sections` (list[tuple[(str, str)]]): 
**Returns:** tuple[(str, list[str])]

#### `_is_summary_boundary`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** bool

#### `_is_failure_start`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** bool

#### `_is_footer_start`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** bool

#### `_handle_section_transition`

**Parameters:**
- `self` (): 
- `line` (str): 
- `current_type` (str): 
- `current_section` (list[str]): 
- `sections` (list[tuple[(str, str)]]): 
- `new_type` (str): 
**Returns:** tuple[(str, list[str])]

#### `_handle_failure_section`

**Parameters:**
- `self` (): 
- `line` (str): 
- `current_type` (str): 
- `current_section` (list[str]): 
- `sections` (list[tuple[(str, str)]]): 
**Returns:** tuple[(str, list[str])]

#### `_render_formatted_output`

**Parameters:**
- `self` (): 
- `output` (str): 
- `options` (OptionsProtocol): 
**Returns:** None

#### `_try_structured_rendering`

**Parameters:**
- `self` (): 
- `clean_output` (str): 
- `options` (OptionsProtocol): 
**Returns:** bool

#### `_render_structured_failures_with_summary`

**Parameters:**
- `self` (): 
- `clean_output` (str): 
- `failures` (list[TestFailure]): 
- `options` (OptionsProtocol): 
**Returns:** None

#### `_render_parsing_error_message`

**Parameters:**
- `self` (): 
- `error` (Exception): 
**Returns:** None

#### `_render_fallback_sections`

**Parameters:**
- `self` (): 
- `clean_output` (str): 
- `options` (OptionsProtocol): 
**Returns:** None

#### `_render_failure_section`

**Parameters:**
- `self` (): 
- `section_content` (str): 
**Returns:** None

#### `_parse_failure_header`

**Parameters:**
- `self` (): 
- `line` (str): 
- `current_failure` (TestFailure | None): 
**Returns:** tuple[(TestFailure | None, bool)]

#### `_parse_location_and_assertion`

**Parameters:**
- `self` (): 
- `line` (str): 
- `current_failure` (TestFailure): 
- `in_traceback` (bool): 
**Returns:** bool

#### `_parse_captured_section_header`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** tuple[(bool, str | None)]

#### `_parse_traceback_line`

**Parameters:**
- `self` (): 
- `line` (str): 
- `lines` (list[str]): 
- `i` (int): 
- `current_failure` (TestFailure): 
**Returns:** bool

#### `_parse_captured_output`

**Parameters:**
- `self` (): 
- `line` (str): 
- `capture_type` (str | None): 
- `current_failure` (TestFailure): 
**Returns:** bool

#### `_extract_structured_failures`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** list[TestFailure]

#### `_update_parsing_state`

**Parameters:**
- `self` (): 
- `result` (dict[(str, t.Any)]): 
- `state` (dict[(str, t.Any)]): 
**Returns:** dict[(str, t.Any)]

#### `_enrich_failures_from_short_summary`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
- `output` (str): 
**Returns:** None

#### `_parse_short_summary`

**Parameters:**
- `self` (): 
- `output` (str): 
**Returns:** list[dict[(str, str)]]

#### `_parse_summary_failure_line`

**Parameters:**
- `self` (): 
- `line` (str): 
**Returns:** dict[(str, str)] | None

#### `_determine_failure_status`

**Parameters:**
- `self` (): 
- `error_message` (str): 
**Returns:** str

#### `_create_failures_from_summary`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
- `summary_failures` (list[dict[(str, str)]]): 
**Returns:** None

#### `_enrich_existing_failures`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
- `summary_failures` (list[dict[(str, str)]]): 
**Returns:** None

#### `_try_enrich_named_failure`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
- `test_path` (str): 
- `error_message` (str): 
- `status` (str): 
**Returns:** bool

#### `_try_enrich_unnamed_failure`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
- `test_path` (str): 
- `error_message` (str): 
- `status` (str): 
**Returns:** bool

#### `_match_unnamed_failures`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
- `summary_failures` (list[dict[(str, str)]]): 
**Returns:** None

#### `_parse_failure_line`

**Parameters:**
- `self` (): 
- `line` (str): 
- `lines` (list[str]): 
- `index` (int): 
- `current_failure` (TestFailure | None): 
- `in_traceback` (bool): 
- `in_captured` (bool): 
- `capture_type` (str | None): 
**Returns:** dict[(str, t.Any)]

#### `_render_structured_failure_panels`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
**Returns:** None

#### `_render_single_failure`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
- `index` (int): 
- `total` (int): 
- `style` (str): 
**Returns:** None

#### `_print_failure_header`

**Parameters:**
- `self` (): 
- `index` (int): 
- `failure` (TestFailure): 
- `style` (str): 
**Returns:** None

#### `_print_failure_location`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
**Returns:** None

#### `_print_failure_status`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
- `style` (str): 
**Returns:** None

#### `_print_failure_summary`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
**Returns:** None

#### `_get_failure_summary`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
**Returns:** str | None

#### `_truncate_text`

**Parameters:**
- `self` (): 
- `text` (str): 
- `max_length` (int): 
**Returns:** str

#### `_print_failure_traceback`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
**Returns:** None

#### `_get_traceback_preview`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
**Returns:** str | None

#### `_build_simple_failure_list`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
**Returns:** str

#### `_group_failures_by_file`

**Parameters:**
- `self` (): 
- `failures` (list[TestFailure]): 
**Returns:** dict[(str, list[TestFailure])]

#### `_render_file_failure_header`

**Parameters:**
- `self` (): 
- `file_path` (str): 
- `file_failures` (list[TestFailure]): 
**Returns:** None

#### `_render_single_failure_panel`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
- `index` (int): 
- `total` (int): 
**Returns:** None

#### `_create_failure_details_table`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
**Returns:** Table

#### `_build_failure_components`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
- `table` (Table): 
**Returns:** list[t.Any]

#### `_get_duration_note`

**Parameters:**
- `self` (): 
- `failure` (TestFailure): 
**Returns:** str | None

#### `_get_timeout`

**Parameters:**
- `self` (): 
- `options` (OptionsProtocol): 
**Returns:** int

#### `configure_lsp_diagnostics`

**Parameters:**
- `self` (): 
- `enable` (bool): 
**Returns:** None






