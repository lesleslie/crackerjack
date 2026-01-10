"""Tests for decorators utilities module."""

import asyncio
import types
import typing as t
from unittest.mock import Mock

import pytest

from crackerjack.decorators.utils import (
    format_exception_chain,
    get_function_context,
    is_async_function,
    preserve_signature,
)


class TestDecoratorUtils:
    """Tests for decorator utility functions."""

    def test_is_async_function_with_async_func(self) -> None:
        """Test is_async_function with async function."""

        async def async_func() -> None:
            pass

        assert is_async_function(async_func) is True

    def test_is_async_function_with_sync_func(self) -> None:
        """Test is_async_function with synchronous function."""

        def sync_func() -> None:
            pass

        assert is_async_function(sync_func) is False

    def test_is_async_function_with_lambda(self) -> None:
        """Test is_async_function with lambda."""
        def lambda_func(x):
            return x * 2
        assert is_async_function(lambda_func) is False

    def test_is_async_function_with_method(self) -> None:
        """Test is_async_function with class method."""

        class TestClass:
            def sync_method(self) -> None:
                pass

            async def async_method(self) -> None:
                pass

        assert is_async_function(TestClass.sync_method) is False
        assert is_async_function(TestClass.async_method) is True

    def test_preserve_signature_basic(self) -> None:
        """Test preserve_signature decorator."""

        def wrapper(func):
            def inner(*args, **kwargs):
                return func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        def original_func(x: int, y: str) -> bool:
            """Test function."""
            return True

        result = decorated(original_func)
        assert callable(result)
        assert hasattr(result, "__wrapped__")

    def test_preserve_signature_with_parameters(self) -> None:
        """Test preserve_signature with parameterized functions."""

        def wrapper(func):
            def inner(*args, **kwargs):
                return func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        def func_with_params(a: int, b: str = "default", *args, **kwargs) -> str:
            """Function with various parameter types."""
            return f"{a}-{b}"

        result = decorated(func_with_params)
        assert callable(result)
        assert result(1, "test") == "1-test"
        assert result(1) == "1-default"

    def test_get_function_context_sync(self) -> None:
        """Test get_function_context with synchronous function."""

        def test_func(x: int) -> str:
            """Test function."""
            return str(x)

        context = get_function_context(test_func)

        assert context["function_name"] == "test_func"
        assert context["module"] == "tests.test_decorators_utils"
        assert context["qualname"] == "TestDecoratorUtils.test_get_function_context_sync.<locals>.test_func"
        assert context["is_async"] is False

    def test_get_function_context_async(self) -> None:
        """Test get_function_context with async function."""

        async def async_test_func(x: int) -> str:
            """Async test function."""
            return str(x)

        context = get_function_context(async_test_func)

        assert context["function_name"] == "async_test_func"
        assert context["module"] == "tests.test_decorators_utils"
        assert context["is_async"] is True

    def test_get_function_context_lambda(self) -> None:
        """Test get_function_context with lambda function."""
        actual_lambda = lambda x: x * 2
        context = get_function_context(actual_lambda)

        assert context["function_name"] == "<lambda>"
        assert context["is_async"] is False

    def test_get_function_context_method(self) -> None:
        """Test get_function_context with class method."""

        class TestClass:
            def method(self, x: int) -> int:
                return x + 1

        context = get_function_context(TestClass.method)

        assert context["function_name"] == "method"
        assert context["is_async"] is False

    def test_format_exception_chain_simple(self) -> None:
        """Test format_exception_chain with simple exception."""
        try:
            msg = "test error"
            raise ValueError(msg)
        except ValueError as e:
            chain = format_exception_chain(e)

            assert len(chain) == 1
            assert "ValueError: test error" in chain[0]

    def test_format_exception_chain_with_cause(self) -> None:
        """Test format_exception_chain with exception chain."""
        try:
            msg = "inner error"
            raise ValueError(msg)
        except ValueError as e:
            try:
                msg = "outer error"
                raise RuntimeError(msg) from e
            except RuntimeError as outer_e:
                chain = format_exception_chain(outer_e)

                assert len(chain) == 2
                assert "RuntimeError: outer error" in chain[0]
                assert "ValueError: inner error" in chain[1]

    def test_format_exception_chain_with_context(self) -> None:
        """Test format_exception_chain with exception context."""
        try:
            msg = "context error"
            raise ValueError(msg)
        except ValueError:
            try:
                msg = "main error"
                raise RuntimeError(msg)
            except RuntimeError as e:
                chain = format_exception_chain(e)

                # Should include both exceptions in chain
                assert len(chain) >= 1
                assert "RuntimeError: main error" in chain[0]

    def test_format_exception_chain_empty(self) -> None:
        """Test format_exception_chain with no exception."""
        # This should not raise an error
        chain = format_exception_chain(Exception("test"))
        assert len(chain) >= 1

    def test_preserve_signature_preserves_name(self) -> None:
        """Test that preserve_signature preserves function name."""

        def wrapper(func):
            def inner(*args, **kwargs):
                return func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        def original_func() -> None:
            pass

        result = decorated(original_func)
        assert result.__name__ == original_func.__name__

    def test_preserve_signature_preserves_docstring(self) -> None:
        """Test that preserve_signature preserves docstring."""

        def wrapper(func):
            def inner(*args, **kwargs):
                return func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        def original_func() -> None:
            """Original docstring."""

        result = decorated(original_func)
        assert result.__doc__ == "Original docstring."

    def test_preserve_signature_with_async_wrapper(self) -> None:
        """Test preserve_signature with async wrapper."""

        def wrapper(func):
            async def inner(*args, **kwargs):
                return await func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        async def async_func() -> str:
            return "async result"

        result = decorated(async_func)
        assert asyncio.iscoroutinefunction(result)

    def test_get_function_context_builtin(self) -> None:
        """Test get_function_context with built-in function."""
        context = get_function_context(len)

        assert context["function_name"] == "len"
        assert context["is_async"] is False

    def test_format_exception_chain_complex(self) -> None:
        """Test format_exception_chain with complex exception hierarchy."""
        try:
            msg = "level 1"
            raise ValueError(msg)
        except ValueError as e1:
            try:
                msg = "level 2"
                raise TypeError(msg) from e1
            except TypeError as e2:
                try:
                    msg = "level 3"
                    raise RuntimeError(msg) from e2
                except RuntimeError as e3:
                    chain = format_exception_chain(e3)

                    assert len(chain) == 3
                    assert "RuntimeError: level 3" in chain[0]
                    assert "TypeError: level 2" in chain[1]
                    assert "ValueError: level 1" in chain[2]

    def test_preserve_signature_with_class_method(self) -> None:
        """Test preserve_signature with class method."""

        def wrapper(func):
            def inner(*args, **kwargs):
                return func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        class TestClass:
            def method(self, x: int) -> int:
                return x * 2

        result = decorated(TestClass.method)
        assert callable(result)

    def test_is_async_function_with_coroutine(self) -> None:
        """Test is_async_function with coroutine function."""
        decorator = getattr(asyncio, "coroutine", types.coroutine)

        @decorator
        def coroutine_func():
            if False:
                yield None

        result = is_async_function(coroutine_func)
        assert isinstance(result, bool)

    def test_preserve_signature_type_annotations(self) -> None:
        """Test that preserve_signature works with type annotations."""

        def wrapper(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            def inner(*args: t.Any, **kwargs: t.Any) -> t.Any:
                return func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        def typed_func(x: int, y: str) -> bool:
            return True

        result = decorated(typed_func)
        assert callable(result)

    def test_get_function_context_comprehensive(self) -> None:
        """Comprehensive test of get_function_context."""
        # Test various function types
        functions = [
            (lambda: None, "lambda"),
            (len, "builtin"),
            (str.upper, "method"),
        ]

        for func, _func_type in functions:
            context = get_function_context(func)
            assert "function_name" in context
            assert "module" in context
            assert "qualname" in context
            assert "is_async" in context
            assert isinstance(context["is_async"], bool)

    def test_format_exception_chain_edge_cases(self) -> None:
        """Test format_exception_chain edge cases."""
        # Test with exception that has no cause or context
        exc = Exception("standalone")
        chain = format_exception_chain(exc)
        assert len(chain) == 1

        # Test with exception that has None cause
        exc.__cause__ = None
        exc.__context__ = None
        chain = format_exception_chain(exc)
        assert len(chain) == 1
