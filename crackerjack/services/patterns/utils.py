"""Utility functions for regex pattern operations."""

import re

# Import for type checking - circular import avoided
from typing import TYPE_CHECKING

from .core import MAX_ITERATIONS, CompiledPatternCache, ValidatedPattern

if TYPE_CHECKING:
    pass  # SAFE_PATTERNS imported at runtime to avoid circular imports


def validate_all_patterns() -> dict[str, bool]:
    """Validate all patterns in the registry."""
    from . import SAFE_PATTERNS

    results: dict[str, bool] = {}
    for name, pattern in SAFE_PATTERNS.items():
        try:
            pattern._validate()
            results[name] = True
        except ValueError as e:
            results[name] = False
            print(f"Pattern '{name}' failed validation: {e}")
    return results


def find_pattern_for_text(text: str) -> list[str]:
    """Find all patterns that match the given text."""
    from . import SAFE_PATTERNS

    return [name for name, pattern in SAFE_PATTERNS.items() if pattern.test(text)]


def apply_safe_replacement(text: str, pattern_name: str) -> str:
    """Apply a named pattern to text."""
    from . import SAFE_PATTERNS

    if pattern_name not in SAFE_PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern_name}")

    return SAFE_PATTERNS[pattern_name].apply(text)


def get_pattern_description(pattern_name: str) -> str:
    """Get description for a named pattern."""
    from . import SAFE_PATTERNS

    if pattern_name not in SAFE_PATTERNS:
        return "Unknown pattern"

    return SAFE_PATTERNS[pattern_name].description


def fix_multi_word_hyphenation(text: str) -> str:
    """Fix multi-word hyphenation iteratively."""
    from . import SAFE_PATTERNS

    return SAFE_PATTERNS["fix_spaced_hyphens"].apply_iteratively(text)


def update_pyproject_version(content: str, new_version: str) -> str:
    """Update version in pyproject.toml content."""
    from . import SAFE_PATTERNS

    pattern_obj = SAFE_PATTERNS["update_pyproject_version"]

    temp_pattern = ValidatedPattern(
        name="temp_version_update",
        pattern=pattern_obj.pattern,
        replacement=f"\\g<1>{new_version}\\g<3>",
        description=f"Update version to {new_version}",
        test_cases=[
            ('version = "1.2.3"', f'version = "{new_version}"'),
        ],
    )

    return re.compile(pattern_obj.pattern, re.MULTILINE).sub(
        temp_pattern.replacement, content
    )


def apply_formatting_fixes(content: str) -> str:
    """Apply common formatting fixes to content."""
    from . import SAFE_PATTERNS

    pattern = SAFE_PATTERNS["remove_trailing_whitespace"]
    content = re.compile(pattern.pattern, re.MULTILINE).sub(
        pattern.replacement, content
    )

    content = SAFE_PATTERNS["normalize_multiple_newlines"].apply(content)

    return content


def apply_security_fixes(content: str) -> str:
    """Apply common security fixes to content."""
    from . import SAFE_PATTERNS

    content = SAFE_PATTERNS["fix_subprocess_run_shell"].apply(content)
    content = SAFE_PATTERNS["fix_subprocess_call_shell"].apply(content)
    content = SAFE_PATTERNS["fix_subprocess_popen_shell"].apply(content)

    content = SAFE_PATTERNS["fix_unsafe_yaml_load"].apply(content)
    content = SAFE_PATTERNS["fix_weak_md5_hash"].apply(content)
    content = SAFE_PATTERNS["fix_weak_sha1_hash"].apply(content)
    content = SAFE_PATTERNS["fix_insecure_random_choice"].apply(content)

    content = SAFE_PATTERNS["remove_debug_prints_with_secrets"].apply(content)

    return content


def apply_test_fixes(content: str) -> str:
    """Apply common test-related fixes to content."""
    from . import SAFE_PATTERNS

    return SAFE_PATTERNS["normalize_assert_statements"].apply(content)


def is_valid_job_id(job_id: str) -> bool:
    """Check if a job ID is valid."""
    from . import SAFE_PATTERNS

    return SAFE_PATTERNS["validate_job_id_alphanumeric"].test(job_id)


def remove_coverage_fail_under(addopts: str) -> str:
    """Remove --cov-fail-under from pytest addopts."""
    from . import SAFE_PATTERNS

    return SAFE_PATTERNS["remove_coverage_fail_under"].apply(addopts)


def update_coverage_requirement(content: str, new_coverage: float) -> str:
    """Update coverage requirement to a new value."""
    from . import SAFE_PATTERNS

    pattern_obj = SAFE_PATTERNS["update_coverage_requirement"]

    temp_pattern = ValidatedPattern(
        name="temp_coverage_update",
        pattern=pattern_obj.pattern,
        replacement=f"\\1{new_coverage: .0f}",
        description=f"Update coverage to {new_coverage}",
        test_cases=[
            ("--cov-fail-under=85", f"--cov-fail-under={new_coverage: .0f}"),
        ],
    )

    return re.compile(pattern_obj.pattern).sub(temp_pattern.replacement, content)


def update_repo_revision(content: str, repo_url: str, new_revision: str) -> str:
    """Update repository revision in content."""
    escaped_url = re.escape(repo_url)
    pattern = rf'("repo": "{escaped_url}".*?"rev": )"([^"]+)"'
    replacement = rf'\1"{new_revision}"'

    return re.compile(pattern, re.DOTALL).sub(replacement, content)


def sanitize_internal_urls(text: str) -> str:
    """Sanitize all internal URLs in text."""
    from . import SAFE_PATTERNS

    url_patterns = [
        "sanitize_localhost_urls",
        "sanitize_127_urls",
        "sanitize_any_localhost_urls",
        "sanitize_ws_localhost_urls",
        "sanitize_ws_127_urls",
        "sanitize_simple_localhost_urls",
        "sanitize_simple_ws_localhost_urls",
    ]

    result = text
    for pattern_name in url_patterns:
        result = SAFE_PATTERNS[pattern_name].apply(result)

    return result


def apply_pattern_iteratively(
    text: str, pattern_name: str, max_iterations: int = MAX_ITERATIONS
) -> str:
    """Apply a pattern iteratively until no more changes."""
    from . import SAFE_PATTERNS

    if pattern_name not in SAFE_PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern_name}")

    return SAFE_PATTERNS[pattern_name].apply_iteratively(text, max_iterations)


def get_all_pattern_stats() -> dict[str, dict[str, float] | dict[str, str]]:
    """Get performance statistics for all patterns."""
    from . import SAFE_PATTERNS

    test_text = "python - m crackerjack - t with pytest - hypothesis - specialist"
    stats: dict[str, dict[str, float] | dict[str, str]] = {}

    for name, pattern in SAFE_PATTERNS.items():
        try:
            pattern_stats = pattern.get_performance_stats(test_text, iterations=10)
            stats[name] = pattern_stats
        except Exception as e:
            stats[name] = {"error": str(e)}

    return stats


def clear_all_caches() -> None:
    """Clear all pattern caches."""
    CompiledPatternCache.clear_cache()


def get_cache_info() -> dict[str, int | list[str]]:
    """Get cache statistics."""
    return CompiledPatternCache.get_cache_stats()


def detect_path_traversal_patterns(path_str: str) -> list[str]:
    """Detect path traversal patterns in a path string."""
    from . import SAFE_PATTERNS

    detected = []
    traversal_patterns = [
        "detect_directory_traversal_basic",
        "detect_directory_traversal_backslash",
        "detect_url_encoded_traversal",
        "detect_double_url_encoded_traversal",
    ]

    for pattern_name in traversal_patterns:
        pattern = SAFE_PATTERNS[pattern_name]
        if pattern.test(path_str):
            detected.append(pattern_name)

    return detected


def detect_null_byte_patterns(path_str: str) -> list[str]:
    """Detect null byte patterns in a path string."""
    from . import SAFE_PATTERNS

    detected = []
    null_patterns = [
        "detect_null_bytes_url",
        "detect_null_bytes_literal",
        "detect_utf8_overlong_null",
    ]

    for pattern_name in null_patterns:
        pattern = SAFE_PATTERNS[pattern_name]
        if pattern.test(path_str):
            detected.append(pattern_name)

    return detected


def detect_dangerous_directory_patterns(path_str: str) -> list[str]:
    """Detect dangerous directory access patterns in a path string."""
    from . import SAFE_PATTERNS

    detected = []
    dangerous_patterns = [
        "detect_sys_directory_pattern",
        "detect_proc_directory_pattern",
        "detect_etc_directory_pattern",
        "detect_boot_directory_pattern",
        "detect_dev_directory_pattern",
        "detect_root_directory_pattern",
        "detect_var_log_directory_pattern",
        "detect_bin_directory_pattern",
        "detect_sbin_directory_pattern",
    ]

    for pattern_name in dangerous_patterns:
        pattern = SAFE_PATTERNS[pattern_name]
        if pattern.test(path_str):
            detected.append(pattern_name)

    return detected


def detect_suspicious_path_patterns(path_str: str) -> list[str]:
    """Detect suspicious path patterns in a path string."""
    from . import SAFE_PATTERNS

    detected = []
    suspicious_patterns = [
        "detect_parent_directory_in_path",
        "detect_suspicious_temp_traversal",
        "detect_suspicious_var_traversal",
    ]

    for pattern_name in suspicious_patterns:
        pattern = SAFE_PATTERNS[pattern_name]
        if pattern.test(path_str):
            detected.append(pattern_name)

    return detected


def validate_path_security(path_str: str) -> dict[str, list[str]]:
    """Validate path security by checking for various attack patterns."""
    return {
        "traversal_patterns": detect_path_traversal_patterns(path_str),
        "null_bytes": detect_null_byte_patterns(path_str),
        "dangerous_directories": detect_dangerous_directory_patterns(path_str),
        "suspicious_patterns": detect_suspicious_path_patterns(path_str),
    }


class RegexPatternsService:
    """Service class that implements RegexPatternsProtocol.

    Wraps module-level regex pattern functions to provide a protocol-compliant interface.
    """

    def update_pyproject_version(self, content: str, new_version: str) -> str:
        """Update version in pyproject.toml content."""
        return update_pyproject_version(content, new_version)

    def remove_coverage_fail_under(self, content: str) -> str:
        """Remove --cov-fail-under from pytest addopts."""
        return remove_coverage_fail_under(content)

    def update_version_in_changelog(self, content: str, new_version: str) -> str:
        """Update version in changelog content."""
        # Placeholder implementation - can be enhanced later
        return content

    def mask_tokens_in_text(self, text: str) -> str:
        """Mask sensitive tokens in text."""
        return sanitize_internal_urls(text)
