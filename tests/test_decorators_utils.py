"""Tests for decorators utilities module."""

import asyncio
import typing as t
import types
from unittest.mock import Mock

import pytest

from crackerjack.decorators.utils import (
    is_async_function,
    preserve_signature,
    get_function_context,
    format_exception_chain,
)


class TestDecoratorUtils:
    """Tests for decorator utility functions."""

    def test_is_async_function_with_async_func(self):
        """Test is_async_function with async function."""

        async def async_func():
            pass

        assert is_async_function(async_func) is True

    def test_is_async_function_with_sync_func(self):
        """Test is_async_function with synchronous function."""

        def sync_func():
            pass

        assert is_async_function(sync_func) is False

    def test_is_async_function_with_lambda(self):
        """Test is_async_function with lambda."""

        lambda_func = lambda x: x * 2
        assert is_async_function(lambda_func) is False

    def test_is_async_function_with_method(self):
        """Test is_async_function with class method."""

        class TestClass:
            def sync_method(self):
                pass

            async def async_method(self):
                pass

        assert is_async_function(TestClass.sync_method) is False
        assert is_async_function(TestClass.async_method) is True

    def test_preserve_signature_basic(self):
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
        assert hasattr(result, '__wrapped__')

    def test_preserve_signature_with_parameters(self):
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

    def test_get_function_context_sync(self):
        """Test get_function_context with synchronous function."""

        def test_func(x: int) -> str:
            """Test function."""
            return str(x)

        context = get_function_context(test_func)

        assert context["function_name"] == "test_func"
        assert context["module"] == "tests.test_decorators_utils"
        assert context["qualname"] == "TestDecoratorUtils.test_get_function_context_sync.<locals>.test_func"
        assert context["is_async"] is False

    def test_get_function_context_async(self):
        """Test get_function_context with async function."""

        async def async_test_func(x: int) -> str:
            """Async test function."""
            return str(x)

        context = get_function_context(async_test_func)

        assert context["function_name"] == "async_test_func"
        assert context["module"] == "tests.test_decorators_utils"
        assert context["is_async"] is True

    def test_get_function_context_lambda(self):
        """Test get_function_context with lambda function."""

        lambda_func = lambda x: x * 2
        context = get_function_context(lambda_func)

        assert context["function_name"] == "<lambda>"
        assert context["is_async"] is False

    def test_get_function_context_method(self):
        """Test get_function_context with class method."""

        class TestClass:
            def method(self, x: int) -> int:
                return x + 1

        context = get_function_context(TestClass.method)

        assert context["function_name"] == "method"
        assert context["is_async"] is False

    def test_format_exception_chain_simple(self):
        """Test format_exception_chain with simple exception."""

        try:
            raise ValueError("test error")
        except ValueError as e:
            chain = format_exception_chain(e)

            assert len(chain) == 1
            assert "ValueError: test error" in chain[0]

    def test_format_exception_chain_with_cause(self):
        """Test format_exception_chain with exception chain."""

        try:
            raise ValueError("inner error")
        except ValueError as e:
            try:
                raise RuntimeError("outer error") from e
            except RuntimeError as outer_e:
                chain = format_exception_chain(outer_e)

                assert len(chain) == 2
                assert "RuntimeError: outer error" in chain[0]
                assert "ValueError: inner error" in chain[1]

    def test_format_exception_chain_with_context(self):
        """Test format_exception_chain with exception context."""

        try:
            raise ValueError("context error")
        except ValueError:
            try:
                raise RuntimeError("main error")
            except RuntimeError as e:
                chain = format_exception_chain(e)

                # Should include both exceptions in chain
                assert len(chain) >= 1
                assert "RuntimeError: main error" in chain[0]

    def test_format_exception_chain_empty(self):
        """Test format_exception_chain with no exception."""

        # This should not raise an error
        chain = format_exception_chain(Exception("test"))
        assert len(chain) >= 1

    def test_preserve_signature_preserves_name(self):
        """Test that preserve_signature preserves function name."""

        def wrapper(func):
            def inner(*args, **kwargs):
                return func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        def original_func():
            pass

        result = decorated(original_func)
        assert result.__name__ == original_func.__name__

    def test_preserve_signature_preserves_docstring(self):
        """Test that preserve_signature preserves docstring."""

        def wrapper(func):
            def inner(*args, **kwargs):
                return func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        def original_func():
            """Original docstring."""
            pass

        result = decorated(original_func)
        assert result.__doc__ == "Original docstring."

    def test_preserve_signature_with_async_wrapper(self):
        """Test preserve_signature with async wrapper."""

        def wrapper(func):
            async def inner(*args, **kwargs):
                return await func(*args, **kwargs)
            return inner

        decorated = preserve_signature(wrapper)

        async def async_func():
            return "async result"

        result = decorated(async_func)
        assert asyncio.iscoroutinefunction(result)

    def test_get_function_context_builtin(self):
        """Test get_function_context with built-in function."""

        context = get_function_context(len)

        assert context["function_name"] == "len"
        assert context["is_async"] is False

    def test_format_exception_chain_complex(self):
        """Test format_exception_chain with complex exception hierarchy."""

        try:
            raise ValueError("level 1")
        except ValueError as e1:
            try:
                raise TypeError("level 2") from e1
            except TypeError as e2:
                try:
                    raise RuntimeError("level 3") from e2
                except RuntimeError as e3:
                    chain = format_exception_chain(e3)

                    assert len(chain) == 3
                    assert "RuntimeError: level 3" in chain[0]
                    assert "TypeError: level 2" in chain[1]
                    assert "ValueError: level 1" in chain[2]

    def test_preserve_signature_with_class_method(self):
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

    def test_is_async_function_with_coroutine(self):
        """Test is_async_function with coroutine function."""

        decorator = getattr(asyncio, "coroutine", types.coroutine)

        @decorator
        def coroutine_func():
            if False:
                yield None

        result = is_async_function(coroutine_func)
        assert isinstance(result, bool)

    def test_preserve_signature_type_annotations(self):
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

    def test_get_function_context_comprehensive(self):
        """Comprehensive test of get_function_context."""

        # Test various function types
        functions = [
            (lambda: None, "lambda"),
            (len, "builtin"),
            (str.upper, "method"),
        ]

        for func, func_type in functions:
            context = get_function_context(func)
            assert "function_name" in context
            assert "module" in context
            assert "qualname" in context
            assert "is_async" in context
            assert isinstance(context["is_async"], bool)

    def test_format_exception_chain_edge_cases(self):
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
