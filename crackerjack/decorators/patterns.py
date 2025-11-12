"""Error pattern detection and caching decorator."""

import typing as t
from functools import wraps
from pathlib import Path

from ..errors import CrackerjackError
from ..mcp.cache import ErrorCache, ErrorPattern
from .utils import get_function_context, is_async_function


def cache_errors(
    cache_dir: Path | None = None,
    error_type: str | None = None,
    auto_analyze: bool = True,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Detect and cache error patterns for analysis and auto-fixing.

    Args:
        cache_dir: Directory for error cache (default: ~/.cache/crackerjack-mcp)
        error_type: Override error type classification (default: auto-detect)
        auto_analyze: Automatically analyze errors for patterns (default: True)

    Returns:
        Decorated function with error pattern caching

    Example:
        >>> from pathlib import Path
        >>>
        >>> @cache_errors(error_type="lint", auto_analyze=True)
        >>> async def run_linter(files: list[Path]) -> bool:
        ...     # Errors are automatically cached and analyzed
        ...     return await linter.run(files)

        >>> @cache_errors()
        >>> def execute_command(cmd: list[str]) -> bool:
        ...     # Error patterns tracked for future auto-fix
        ...     return subprocess.run(cmd).returncode == 0

    Notes:
        - Integrates with Crackerjack's ErrorCache system
        - Tracks error frequency and common fixes
        - Enables intelligent auto-fix suggestions
        - Works with AI agents for pattern recognition
    """
    error_cache = ErrorCache(cache_dir=cache_dir)

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):
            return _create_async_wrapper(func, error_cache, error_type, auto_analyze)
        return _create_sync_wrapper(func, error_cache, error_type, auto_analyze)

    return decorator


def _create_async_wrapper(
    func: t.Callable[..., t.Any],
    error_cache: ErrorCache,
    error_type: str | None,
    auto_analyze: bool,
) -> t.Callable[..., t.Any]:
    """Create async wrapper with error caching."""

    @wraps(func)
    async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        try:
            result = await func(*args, **kwargs)
            await _handle_result_analysis(
                result, error_cache, func, error_type, auto_analyze
            )
            return result
        except CrackerjackError as e:
            await _cache_crackerjack_error(error_cache, e, func, error_type)
            raise
        except Exception as e:
            await _handle_generic_exception(
                e, error_cache, func, error_type, auto_analyze
            )
            raise

    return async_wrapper


def _create_sync_wrapper(
    func: t.Callable[..., t.Any],
    error_cache: ErrorCache,
    error_type: str | None,
    auto_analyze: bool,
) -> t.Callable[..., t.Any]:
    """Create sync wrapper with error caching."""

    @wraps(func)
    def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        try:
            result = func(*args, **kwargs)
            _handle_result_analysis_sync(
                result, error_cache, func, error_type, auto_analyze
            )
            return result
        except CrackerjackError as e:
            _cache_crackerjack_error_sync(error_cache, e, func, error_type)
            raise
        except Exception as e:
            _handle_generic_exception_sync(
                e, error_cache, func, error_type, auto_analyze
            )
            raise

    return sync_wrapper


async def _handle_result_analysis(
    result: t.Any,
    cache: ErrorCache,
    func: t.Callable[..., t.Any],
    error_type: str | None,
    auto_analyze: bool,
) -> None:
    """Handle result error analysis for async functions."""
    if not auto_analyze or not isinstance(result, dict):
        return
    if "error" in result or "errors" in result:
        await _analyze_result_errors(cache, result, func, error_type)


def _handle_result_analysis_sync(
    result: t.Any,
    cache: ErrorCache,
    func: t.Callable[..., t.Any],
    error_type: str | None,
    auto_analyze: bool,
) -> None:
    """Handle result error analysis for sync functions."""
    if not auto_analyze or not isinstance(result, dict):
        return
    if "error" in result or "errors" in result:
        _analyze_result_errors_sync(cache, result, func, error_type)


async def _handle_generic_exception(
    error: Exception,
    cache: ErrorCache,
    func: t.Callable[..., t.Any],
    error_type: str | None,
    auto_analyze: bool,
) -> None:
    """Handle generic exception caching for async functions."""
    if auto_analyze:
        await _cache_exception(cache, error, func, error_type)


def _handle_generic_exception_sync(
    error: Exception,
    cache: ErrorCache,
    func: t.Callable[..., t.Any],
    error_type: str | None,
    auto_analyze: bool,
) -> None:
    """Handle generic exception caching for sync functions."""
    if auto_analyze:
        _cache_exception_sync(cache, error, func, error_type)


async def _analyze_result_errors(
    cache: ErrorCache,
    result: dict[str, t.Any],
    func: t.Callable[..., t.Any],
    error_type_override: str | None,
) -> None:
    """Analyze errors from result dictionary (async)."""
    error_data = result.get("error") or result.get("errors", "")
    if isinstance(error_data, str) and error_data:
        context = get_function_context(func)
        detected_type = error_type_override or context["function_name"]

        pattern = cache.create_pattern_from_error(error_data, detected_type)
        if pattern:
            await cache.add_pattern(pattern)


def _analyze_result_errors_sync(
    cache: ErrorCache,
    result: dict[str, t.Any],
    func: t.Callable[..., t.Any],
    error_type_override: str | None,
) -> None:
    """Analyze errors from result dictionary (sync)."""
    import asyncio

    error_data = result.get("error") or result.get("errors", "")
    if isinstance(error_data, str) and error_data:
        context = get_function_context(func)
        detected_type = error_type_override or context["function_name"]

        pattern = cache.create_pattern_from_error(error_data, detected_type)
        if pattern:
            # Run async method in sync context
            asyncio.run(cache.add_pattern(pattern))


async def _cache_crackerjack_error(
    cache: ErrorCache,
    error: CrackerjackError,
    func: t.Callable[..., t.Any],
    error_type_override: str | None,
) -> None:
    """Cache a CrackerjackError (async)."""
    get_function_context(func)
    detected_type = error_type_override or error.error_code.name

    pattern = ErrorPattern(
        pattern_id=f"{detected_type}_{error.error_code.value}_{hash(error.message) % 10000}",
        error_type=detected_type,
        error_code=str(error.error_code.value),
        message_pattern=error.message,
        common_fixes=[error.recovery] if error.recovery else None,
        auto_fixable=False,
    )

    await cache.add_pattern(pattern)


def _cache_crackerjack_error_sync(
    cache: ErrorCache,
    error: CrackerjackError,
    func: t.Callable[..., t.Any],
    error_type_override: str | None,
) -> None:
    """Cache a CrackerjackError (sync)."""
    import asyncio

    get_function_context(func)
    detected_type = error_type_override or error.error_code.name

    pattern = ErrorPattern(
        pattern_id=f"{detected_type}_{error.error_code.value}_{hash(error.message) % 10000}",
        error_type=detected_type,
        error_code=str(error.error_code.value),
        message_pattern=error.message,
        common_fixes=[error.recovery] if error.recovery else None,
        auto_fixable=False,
    )

    asyncio.run(cache.add_pattern(pattern))


async def _cache_exception(
    cache: ErrorCache,
    error: Exception,
    func: t.Callable[..., t.Any],
    error_type_override: str | None,
) -> None:
    """Cache a generic exception (async)."""
    get_function_context(func)
    detected_type = error_type_override or type(error).__name__

    error_message = str(error)
    pattern = cache.create_pattern_from_error(error_message, detected_type)

    if pattern:
        await cache.add_pattern(pattern)


def _cache_exception_sync(
    cache: ErrorCache,
    error: Exception,
    func: t.Callable[..., t.Any],
    error_type_override: str | None,
) -> None:
    """Cache a generic exception (sync)."""
    import asyncio

    get_function_context(func)
    detected_type = error_type_override or type(error).__name__

    error_message = str(error)
    pattern = cache.create_pattern_from_error(error_message, detected_type)

    if pattern:
        asyncio.run(cache.add_pattern(pattern))
