import asyncio
import inspect
import typing as t
from functools import wraps


def is_async_function(func: t.Callable[..., t.Any]) -> bool:
    return asyncio.iscoroutinefunction(func)


def preserve_signature[F: t.Callable[..., t.Any]](
    wrapper: F,
) -> t.Callable[[t.Callable[..., t.Any]], F]:
    def decorator(func: t.Callable[..., t.Any]) -> F:

        func_is_async = is_async_function(func)


        wrapped_func = wrapper(func)


        wrapped_is_async = is_async_function(wrapped_func)

        if func_is_async and wrapped_is_async:

            @wraps(func)
            async def async_wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
                return await wrapped_func(*args, **kwargs)

            async_wrapped.__wrapped__ = func  # type: ignore[attr-defined]
            return t.cast(F, async_wrapped)
        else:

            @wraps(func)
            def sync_wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
                return wrapped_func(*args, **kwargs)

            sync_wrapped.__wrapped__ = func  # type: ignore[attr-defined]
            return t.cast(F, sync_wrapped)

    return decorator


def get_function_context(func: t.Callable[..., t.Any]) -> dict[str, t.Any]:
    return {
        "function_name": getattr(func, "__name__", "<builtin>"),
        "module": getattr(func, "__module__", "<builtin>"),
        "qualname": getattr(func, "__qualname__", "<builtin>"),
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
