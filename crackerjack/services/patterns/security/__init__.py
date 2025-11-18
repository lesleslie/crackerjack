"""Security-related patterns for credential detection, path traversal, and unsafe operations.

This module aggregates all security patterns from specialized submodules:
- credentials: Hardcoded credentials, secrets, tokens, and passwords (9 patterns)
- path_traversal: Directory traversal and unsafe path access (19 patterns)
- unsafe_operations: Weak crypto, insecure random, subprocess injection (14 patterns)
- code_injection: SQL injection, code eval, system commands (8 patterns)

Total: 50 security patterns
"""

from ..core import ValidatedPattern
from .code_injection import PATTERNS as CODE_INJECTION_PATTERNS
from .credentials import PATTERNS as CREDENTIAL_PATTERNS
from .path_traversal import PATTERNS as PATH_TRAVERSAL_PATTERNS
from .unsafe_operations import PATTERNS as UNSAFE_OPERATION_PATTERNS

PATTERNS: dict[str, ValidatedPattern] = (
    CREDENTIAL_PATTERNS
    | PATH_TRAVERSAL_PATTERNS
    | UNSAFE_OPERATION_PATTERNS
    | CODE_INJECTION_PATTERNS
)
