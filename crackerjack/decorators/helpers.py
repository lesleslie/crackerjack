import asyncio
import inspect
import typing as t
from functools import wraps

F = t.TypeVar("F", bound=t.Callable[..., t.Any])


def is_async_function(func: t.Callable[..., t.Any]) -> bool:
    return asyncio.iscoroutinefunction(func)


def preserve_signature[F: t.Callable[..., t.Any]](
    wrapper: F,
) -> t.Callable[[t.Callable[..., t.Any]], F]:
    def decorator(func: t.Callable[..., t.Any]) -> F:
        wrapped = wraps(func)(wrapper)

        wrapped.__wrapped__ = func  # type: ignore[attr-defined]
        return t.cast(F, wrapped)

    return decorator


def get_function_context(func: t.Callable[..., t.Any]) -> dict[str, t.Any]:
    return {
        "function_name": func.__name__,
        "module": func.__module__,
        "qualname": func.__qualname__,
        "is_async": is_async_function(func),
    }


def format_exception_chain(exc: BaseException) -> list[str]:
    chain: list[str] = []
    current: BaseException | None = exc

    while current is not None:
        chain.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__

    return chain


def get_callable_params(func: t.Callable[..., t.Any]) -> list[inspect.Parameter]:
    try:
        sig = inspect.signature(func)
        return list(sig.parameters.values())
    except (ValueError, TypeError):
        return []
