"""Centralized pattern registry for safe regex operations.

This module provides backward compatibility with the old regex_patterns.py
by automatically loading all patterns from domain-specific modules.

The patterns are organized by domain:
- formatting: Text formatting and spacing patterns
- versioning: Version number extraction and updates
- validation: Input validation patterns
- utilities: General utility extraction patterns
- url_sanitization: URL sanitization for localhost addresses
- agents: Agent count management patterns
- templates: Template processing patterns
- code: Code-related patterns (imports, paths, performance, detection, replacement)
- documentation: Documentation patterns (docstrings, badges, comments)
- tool_output: Linter/checker output parsing (ruff, pyright, bandit, mypy, vulture, complexipy)
- testing: Test output and error patterns
- security: Security patterns (credentials, path_traversal, unsafe_operations, code_injection)

For backward compatibility, the main SAFE_PATTERNS dict contains all patterns.
"""

# Import standalone modules
# Import subdirectories
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

# Build the complete SAFE_PATTERNS registry for backward compatibility
SAFE_PATTERNS: dict[str, ValidatedPattern] = (
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

# Import utility functions for backward compatibility
from .utils import (
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
    update_repo_revision,
    validate_all_patterns,
    validate_path_security,
)

# Export everything for convenience
__all__ = [
    # Core classes and utilities
    "ValidatedPattern",
    "CompiledPatternCache",
    "validate_pattern_safety",
    "MAX_INPUT_SIZE",
    "MAX_ITERATIONS",
    "PATTERN_CACHE_SIZE",
    # Main registry (backward compatibility)
    "SAFE_PATTERNS",
    # Module namespaces for organized access
    "formatting",
    "versioning",
    "validation",
    "utilities",
    "url_sanitization",
    "agents",
    "templates",
    "code",
    "documentation",
    "tool_output",
    "testing",
    "security",
    # Utility functions (backward compatibility)
    "validate_all_patterns",
    "find_pattern_for_text",
    "apply_safe_replacement",
    "get_pattern_description",
    "fix_multi_word_hyphenation",
    "update_pyproject_version",
    "apply_formatting_fixes",
    "apply_security_fixes",
    "apply_test_fixes",
    "is_valid_job_id",
    "remove_coverage_fail_under",
    "update_coverage_requirement",
    "update_repo_revision",
    "sanitize_internal_urls",
    "apply_pattern_iteratively",
    "get_all_pattern_stats",
    "clear_all_caches",
    "get_cache_info",
    "detect_path_traversal_patterns",
    "detect_null_byte_patterns",
    "detect_dangerous_directory_patterns",
    "detect_suspicious_path_patterns",
    "validate_path_security",
    "RegexPatternsService",
]
