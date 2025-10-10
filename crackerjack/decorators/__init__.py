"""
Composable error handling decorators for Crackerjack.

This module provides a comprehensive set of decorators for error handling,
retry logic, timeout enforcement, and graceful degradation. All decorators
support both synchronous and asynchronous functions and can be stacked for
complex error handling scenarios.

Basic Usage:
    >>> from crackerjack.decorators import retry, handle_errors, with_timeout
    >>>
    >>> @retry(max_attempts=3)
    >>> @with_timeout(seconds=30)
    >>> async def fetch_data(url: str) -> dict:
    ...     # Implementation
    ...     pass

Integration:
    - Uses CrackerjackError and subclasses from crackerjack.errors
    - Integrates with Rich console for beautiful output
    - Works alongside ErrorHandlingMixin
    - Supports Crackerjack's logging infrastructure
"""

from .error_handling import (
    graceful_degradation,
    handle_errors,
    log_errors,
)
from .patterns import cache_errors
from .retry import retry
from .timeout import with_timeout
from .validation import validate_args

__all__ = [
    "retry",
    "handle_errors",
    "with_timeout",
    "log_errors",
    "graceful_degradation",
    "validate_args",
    "cache_errors",
]
