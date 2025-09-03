"""Utility functions for session-mgmt-mcp."""

from .database_pool import DatabaseConnectionPool, get_database_pool
from .file_utils import (
    _cleanup_session_logs,
    _cleanup_temp_files,
    _cleanup_uv_cache,
    validate_claude_directory,
)
from .format_utils import (
    _build_search_header,
    _format_efficiency_metrics,
    _format_monitoring_status,
    _format_no_data_message,
    _format_quality_alerts,
    _format_search_results,
    _format_statistics_header,
)
from .git_operations import (
    create_checkpoint_commit,
    create_commit,
    get_git_status,
    get_staged_files,
    is_git_repository,
    stage_files,
)
from .git_utils import (
    _optimize_git_repository,
    _parse_git_status,
    _stage_and_commit_files,
)
from .lazy_imports import (
    LazyImport,
    LazyLoader,
    get_dependency_status,
    lazy_loader,
    log_dependency_status,
    optional_dependency,
    require_dependency,
)
from .logging import SessionLogger, get_session_logger
from .quality_utils import (
    _analyze_quality_trend,
    _extract_quality_scores,
    _generate_quality_trend_recommendations,
    _get_intelligence_error_result,
    _get_time_based_recommendations,
)

__all__ = [
    # Existing utilities
    "DatabaseConnectionPool",
    "LazyImport",
    "LazyLoader",
    "SessionLogger",
    "_analyze_quality_trend",
    "_build_search_header",
    # New extracted utilities
    "_cleanup_session_logs",
    "_cleanup_temp_files",
    "_cleanup_uv_cache",
    "_extract_quality_scores",
    "_format_efficiency_metrics",
    "_format_monitoring_status",
    "_format_no_data_message",
    "_format_quality_alerts",
    "_format_search_results",
    "_format_statistics_header",
    "_generate_quality_trend_recommendations",
    "_get_intelligence_error_result",
    "_get_time_based_recommendations",
    "_optimize_git_repository",
    "_parse_git_status",
    "_stage_and_commit_files",
    "create_checkpoint_commit",
    "create_commit",
    "get_database_pool",
    "get_dependency_status",
    "get_git_status",
    "get_session_logger",
    "get_staged_files",
    "is_git_repository",
    "lazy_loader",
    "log_dependency_status",
    "optional_dependency",
    "require_dependency",
    "stage_files",
    "validate_claude_directory",
]
