"""Credential and secret detection patterns for security validation.

This module contains patterns for detecting and masking hardcoded credentials,
secrets, tokens, and other sensitive authentication data in code.
"""

import re

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "detect_hardcoded_credentials_advanced": ValidatedPattern(
        name="detect_hardcoded_credentials_advanced",
        pattern=r"(?i)\b(?:password|passwd|pwd|secret|key|token|api_key|"
        r'apikey)\s*[:=]\s*["\'][^"\']{3,}["\']',
        replacement="[HARDCODED_CREDENTIAL_DETECTED]",
        description="Detect hardcoded credentials in various formats "
        "(case insensitive)",
        flags=re.IGNORECASE,
        global_replace=True,
        test_cases=[
            ('password="secret123"', "[HARDCODED_CREDENTIAL_DETECTED]"),
            ("API_KEY = 'abc-123-def'", "[HARDCODED_CREDENTIAL_DETECTED]"),
            ('token: "my-secret-token"', "[HARDCODED_CREDENTIAL_DETECTED]"),
            (
                'username = "user"',
                'username = "user"',
            ),
        ],
    ),
    "detect_hardcoded_secrets": ValidatedPattern(
        name="detect_hardcoded_secrets",
        pattern=r'\b\w*(password|secret|key|token)\w*\s*=\s*[\'"][^\'"]+[\'"]',
        replacement="[SECRET_DETECTED]",
        description="Detect hardcoded secrets in assignments (case insensitive)",
        flags=re.IGNORECASE,
        global_replace=True,
        test_cases=[
            ('password = "secret123"', "[SECRET_DETECTED]"),
            ("api_key = 'abc123def'", "[SECRET_DETECTED]"),
            ('TOKEN = "my-token-here"', "[SECRET_DETECTED]"),
            ("username = 'user123'", "username = 'user123'"),
        ],
    ),
    "fix_hardcoded_jwt_secret": ValidatedPattern(
        name="fix_hardcoded_jwt_secret",
        pattern=r'(JWT_SECRET|jwt_secret)\s*=\s*["\'][^"\']+["\']',
        replacement=r'\1 = os.getenv("JWT_SECRET", "")',
        description="Replace hardcoded JWT secrets with environment variables",
        global_replace=True,
        test_cases=[
            (
                'JWT_SECRET = "hardcoded-secret"',
                'JWT_SECRET = os.getenv("JWT_SECRET", "")',
            ),
            ('jwt_secret = "my-secret"', 'jwt_secret = os.getenv("JWT_SECRET", "")'),
            ('other_var = "value"', 'other_var = "value"'),
        ],
    ),
    "mask_generic_long_token": ValidatedPattern(
        name="mask_generic_long_token",
        pattern=r"\b[a-zA-Z0-9_-]{32,}\b",
        replacement="****",
        description="Mask generic long tokens (32+ chars, word boundaries to avoid"
        " false positives)",
        global_replace=True,
        test_cases=[
            ("secret_key=abcdef1234567890abcdef1234567890abcdef", "secret_key=****"),
            (
                "Short token abc123def456",
                "Short token abc123def456",
            ),
            (
                "File path "
                "/very/long/path/that/should/not/be/masked/even/though/its/long",
                "File path "
                "/very/long/path/that/should/not/be/masked/even/though/its/long",
            ),
            ("API_KEY=verylongapikeyhere1234567890123456", "API_KEY=****"),
            (
                "Long-token_with-underscores_123456789012345678",
                "****",
            ),
        ],
    ),
    "mask_github_token": ValidatedPattern(
        name="mask_github_token",
        pattern=r"\bghp_[a-zA-Z0-9]{36}\b",
        replacement="ghp_****",
        description="Mask GitHub personal access tokens (exactly 40 chars total"
        " with word boundaries)",
        global_replace=True,
        test_cases=[
            ("ghp_1234567890abcdef1234567890abcdef1234", "ghp_****"),
            (
                "GITHUB_TOKEN=ghp_1234567890abcdef1234567890abcdef1234",
                "GITHUB_TOKEN=ghp_****",
            ),
            ("ghp_short", "ghp_short"),
            (
                "ghp_1234567890abcdef1234567890abcdef12345",
                "ghp_1234567890abcdef1234567890abcdef12345",
            ),
            (
                "Multiple ghp_1234567890abcdef1234567890abcdef1234 and"
                " ghp_abcdef1234567890abcdef12345678901234",
                "Multiple ghp_**** and ghp_****",
            ),
        ],
    ),
    "mask_password_assignment": ValidatedPattern(
        name="mask_password_assignment",
        pattern=r"(?i)\b(password\s*[=: ]\s*)['\"]([^'\"]{8,})['\"]",
        replacement=r"\1'****'",
        description="Mask password assignments in various formats (case insensitive)",
        global_replace=True,
        test_cases=[
            ('password="secret123456"', "password='****'"),
            ("password='my_long_password'", "password='****'"),
            ('password: "another_secret_password"', "password: '****'"),
            ("password = 'spaced_password_assignment'", "password = '****'"),
            ('password="short"', 'password="short"'),
            (
                "not_password='should_not_be_masked'",
                "not_password='should_not_be_masked'",
            ),
            ('PASSWORD="UPPERCASE_PASSWORD"', "PASSWORD='****'"),
        ],
    ),
    "mask_pypi_token": ValidatedPattern(
        name="mask_pypi_token",
        pattern=r"\bpypi-[a-zA-Z0-9_-]{12,}\b",
        replacement="pypi-****",
        description="Mask PyPI authentication tokens (word boundaries to prevent"
        " false matches)",
        global_replace=True,
        test_cases=[
            ("pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI", "pypi-****"),
            (
                "Using token: pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI for upload",
                "Using token: pypi-**** for upload",
            ),
            ("pypi-short", "pypi-short"),
            (
                "not pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI",
                "not pypi-****",
            ),
            (
                "Multiple pypi-token1234567890 and pypi-anothertokenhere",
                "Multiple pypi-**** and pypi-****",
            ),
        ],
    ),
    "mask_token_assignment": ValidatedPattern(
        name="mask_token_assignment",
        pattern=r"(?i)\b(token\s*[=: ]\s*)['\"]([^'\"]{8,})['\"]",
        replacement=r"\1'****'",
        description="Mask token assignments in various formats (case insensitive)",
        global_replace=True,
        test_cases=[
            ('token="abc123def456789"', "token='****'"),
            ("token='long_secret_token_here'", "token='****'"),
            ('token: "another_secret_token"', "token: '****'"),
            ("token = 'spaced_assignment_token'", "token = '****'"),
            ('token="short"', 'token="short"'),
            (
                "not_token='should_not_be_masked'",
                "not_token='should_not_be_masked'",
            ),
            ('TOKEN="UPPERCASE_TOKEN_HERE"', "TOKEN='****'"),
        ],
    ),
    "remove_debug_prints_with_secrets": ValidatedPattern(
        name="remove_debug_prints_with_secrets",
        pattern=r"print\s*\([^)]*(?: password|secret|key|token)[^)]*\)",
        replacement="",
        description="Remove debug print statements that contain sensitive information",
        global_replace=True,
        test_cases=[
            ('print("password: ", password)', ""),
            ("print(f'Token: {token}')", ""),
            ("print('Debug secret value')", ""),
            (
                "print('Normal debug message')",
                "print('Normal debug message')",
            ),
            ('print("API key is", key)', ""),
        ],
    ),
}
