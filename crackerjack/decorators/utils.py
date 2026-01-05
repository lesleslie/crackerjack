"""Shared utilities for error handling decorators."""

import asyncio
import inspect
import typing as t
from functools import wraps

F = t.TypeVar("F", bound=t.Callable[..., t.Any])


def is_async_function(func: t.Callable[..., t.Any]) -> bool:
    """Check if a function is async."""
    return asyncio.iscoroutinefunction(func)


def preserve_signature[F: t.Callable[..., t.Any]](
    wrapper: F,
) -> t.Callable[[t.Callable[..., t.Any]], F]:
    """Preserve function signature in decorators."""

    def decorator(func: t.Callable[..., t.Any]) -> F:
        wrapped = wrapper(func)
        return t.cast(F, wraps(func)(wrapped))

    return decorator


def get_function_context(func: t.Callable[..., t.Any]) -> dict[str, t.Any]:
    """Extract context information from a function for error reporting."""
    name = getattr(func, "__name__", type(func).__name__)
    qualname = getattr(func, "__qualname__", name)
    module = getattr(
        func,
        "__module__",
        getattr(getattr(func, "__objclass__", None), "__module__", "builtins"),
    )
    return {
        "function_name": name,
        "module": module,
        "qualname": qualname,
        "is_async": is_async_function(func),
    }


def format_exception_chain(exc: BaseException) -> list[str]:
    """Format exception chain for logging."""
    chain: list[str] = []
    current: BaseException | None = exc

    while current is not None:
        chain.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__

    return chain


def get_callable_params(func: t.Callable[..., t.Any]) -> list[inspect.Parameter]:
    """Get function parameters using inspect."""
    try:
        sig = inspect.signature(func)
        return list(sig.parameters.values())
    except (ValueError, TypeError):
        return []
