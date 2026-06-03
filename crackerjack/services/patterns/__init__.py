from . import (
    agents,
    code,
    documentation,
    formatting,
    security,
    templates,
    testing,
    tool_output,
    url_sanitization,
    utilities,
    validation,
    versioning,
)
from .core import (
    MAX_INPUT_SIZE,
    MAX_ITERATIONS,
    PATTERN_CACHE_SIZE,
    CompiledPatternCache,
    ValidatedPattern,
    validate_pattern_safety,
)

_merged_patterns = (
    formatting.PATTERNS
    | versioning.PATTERNS
    | validation.PATTERNS
    | utilities.PATTERNS
    | url_sanitization.PATTERNS
    | agents.PATTERNS
    | templates.PATTERNS
    | code.PATTERNS
    | documentation.PATTERNS
    | tool_output.PATTERNS
    | testing.PATTERNS
    | security.PATTERNS
)
SAFE_PATTERNS: dict[str, ValidatedPattern] = _merged_patterns  # type: ignore[assignment]


from .operations import (
    RegexPatternsService,
    apply_formatting_fixes,
    apply_pattern_iteratively,
    apply_safe_replacement,
    apply_security_fixes,
    apply_test_fixes,
    clear_all_caches,
    detect_dangerous_directory_patterns,
    detect_null_byte_patterns,
    detect_path_traversal_patterns,
    detect_suspicious_path_patterns,
    find_pattern_for_text,
    fix_multi_word_hyphenation,
    get_all_pattern_stats,
    get_cache_info,
    get_pattern_description,
    is_valid_job_id,
    remove_coverage_fail_under,
    sanitize_internal_urls,
    update_coverage_requirement,
    update_pyproject_version,
    update_python_version,
    update_repo_revision,
    validate_all_patterns,
    validate_path_security,
)

__all__ = [
    "MAX_INPUT_SIZE",
    "MAX_ITERATIONS",
    "PATTERN_CACHE_SIZE",
    "SAFE_PATTERNS",
    "CompiledPatternCache",
    "RegexPatternsService",
    "ValidatedPattern",
    "agents",
    "apply_formatting_fixes",
    "apply_pattern_iteratively",
    "apply_safe_replacement",
    "apply_security_fixes",
    "apply_test_fixes",
    "clear_all_caches",
    "code",
    "detect_dangerous_directory_patterns",
    "detect_null_byte_patterns",
    "detect_path_traversal_patterns",
    "detect_suspicious_path_patterns",
    "documentation",
    "find_pattern_for_text",
    "fix_multi_word_hyphenation",
    "formatting",
    "get_all_pattern_stats",
    "get_cache_info",
    "get_pattern_description",
    "is_valid_job_id",
    "remove_coverage_fail_under",
    "sanitize_internal_urls",
    "security",
    "templates",
    "testing",
    "tool_output",
    "update_coverage_requirement",
    "update_pyproject_version",
    "update_python_version",
    "update_repo_revision",
    "url_sanitization",
    "utilities",
    "validate_all_patterns",
    "validate_path_security",
    "validate_pattern_safety",
    "validation",
    "versioning",
]
