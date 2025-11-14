"""Backward compatibility wrapper for refactored patterns module.

This module re-exports everything from the new patterns/ directory structure
to maintain backward compatibility with existing code that imports from
crackerjack.services.regex_patterns.

The actual implementation has been split into domain-specific modules:
- patterns/core.py - Base classes and utilities
- patterns/formatting.py - Formatting patterns
- patterns/security/ - Security-related patterns
- patterns/testing/ - Test-related patterns
- patterns/code/ - Code analysis patterns
- patterns/documentation/ - Documentation patterns
- patterns/tool_output/ - Tool output parsing patterns
- And more...

All imports should work exactly as before.
"""

# Re-export everything from the new patterns module
from .patterns import *  # noqa: F401, F403

__all__ = [
    # Core classes
    "ValidatedPattern",
    "CompiledPatternCache",
    "validate_pattern_safety",
    "MAX_INPUT_SIZE",
    "MAX_ITERATIONS",
    "PATTERN_CACHE_SIZE",
    # Main registry
    "SAFE_PATTERNS",
    # Utility functions
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
