"""Code-related patterns."""

from .detection import PATTERNS as DETECTION_PATTERNS
from .imports import PATTERNS as IMPORT_PATTERNS
from .paths import PATTERNS as PATH_PATTERNS
from .performance import PATTERNS as PERFORMANCE_PATTERNS
from .replacement import PATTERNS as REPLACEMENT_PATTERNS

PATTERNS: dict[str, object] = (
    IMPORT_PATTERNS
    | PATH_PATTERNS
    | PERFORMANCE_PATTERNS
    | DETECTION_PATTERNS
    | REPLACEMENT_PATTERNS
)
