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
